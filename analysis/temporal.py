"""Descriptive temporal comparisons: fixed graph universe, coverage and uncertainty."""

import json, math, re, time
from datetime import date
import duckdb, numpy as np, pandas as pd
from analysis.adapted.temporal import (
    stage_months,
    owner_concentration_hhi,
    build_party_affinity,
    negative_edge_share,
)
from analysis.adapted.identity import content_hash_text


def finite(value):
    return round(float(value), 6) if math.isfinite(float(value)) else None


def aov_interval(invoice_pence):
    n = len(invoice_pence)
    if n < 20:
        return {
            "interval": None,
            "reason": "insufficient_orders",
            "n": n,
            "repetitions": 0,
        }
    if n > 50000:
        return {"interval": None, "reason": "sample_limit", "n": n, "repetitions": 0}
    rng = np.random.default_rng(47)
    values = np.asarray(invoice_pence, dtype=np.float64)
    means = [
        float(rng.choice(values, size=n, replace=True).mean() / 100) for _ in range(200)
    ]
    return {
        "interval": [round(float(x), 2) for x in np.quantile(means, [0.025, 0.975])],
        "n": n,
        "seed": 47,
        "repetitions": 200,
        "method": "invoice percentile bootstrap; descriptive iid assumption",
    }


def edge_comparison(before, after):
    a = {(e["source"], e["target"]): e["weight"] for e in before}
    b = {(e["source"], e["target"]): e["weight"] for e in after}
    union = set(a) | set(b)
    changes = [
        {
            "source": k[0],
            "target": k[1],
            "before": a.get(k, 0),
            "after": b.get(k, 0),
            "delta": b.get(k, 0) - a.get(k, 0),
        }
        for k in union
        if a.get(k, 0) != b.get(k, 0)
    ]
    changes.sort(key=lambda x: (-abs(x["delta"]), x["source"], x["target"]))
    return {
        "jaccard": round(len(set(a) & set(b)) / len(union), 6) if union else None,
        "new_edges": len(set(b) - set(a)),
        "lost_edges": len(set(a) - set(b)),
        "shared_edges": len(set(a) & set(b)),
        "changes": changes[:15],
    }


def analyze_temporal(request, metadata, where, args, data_dir):
    started = time.perf_counter()
    pivot = request.get("month")
    window = request.get("window", 1)
    minimum = request.get("min_shared", 2)
    if not isinstance(pivot, str) or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", pivot):
        raise ValueError("Odak ay YYYY-MM biçiminde olmalı.")
    if pivot < metadata["start"][:7] or pivot > metadata["end"][:7]:
        raise ValueError("Odak ay veri setinin tarih aralığında olmalı.")
    if type(window) is not int or not 1 <= window <= 3:
        raise ValueError("Pencere 1–3 ay olmalı.")
    if type(minimum) is not int or not 1 <= minimum <= 100:
        raise ValueError("Ortak sipariş eşiği 1–100 olmalı.")
    windows = stage_months(pivot, window, window)
    all_months = [m for months in windows.values() for m in months]
    con = duckdb.connect(
        str(data_dir / (metadata["id"] + ".duckdb")),
        read_only=True,
        config={"threads": 1, "memory_limit": "256MB"},
    )

    def rows(sql, params=()):
        c = con.execute(sql, params)
        names = [d[0] for d in c.description]
        return [dict(zip(names, r)) for r in c.fetchall()]

    def clause(months):
        return (
            where
            + (" AND " if where else " WHERE ")
            + "strftime(order_date,'%Y-%m') IN ("
            + ",".join("?" for _ in months)
            + ")"
        )

    from analysis.scope import include_service, product_clause

    # Product universe, concentration and networks leave service lines out unless included (analysis/scope.py);
    # the window's sales and order value keep every gross-sales line.
    products_only = "" if include_service(request) else " AND " + product_clause()
    selected = rows(
        "SELECT product_id,MIN(product) AS label,SUM(line_pence)::BIGINT AS p FROM transactions"
        + clause(all_months)
        + products_only
        + " GROUP BY 1 ORDER BY 3 DESC,1 LIMIT 24",
        [*args, *all_months],
    )
    ids = [r["product_id"] for r in selected]
    effective_start = max(
        metadata["start"],
        str((request.get("filters") or {}).get("start") or metadata["start"]),
    )
    effective_end = min(
        metadata["end"],
        str((request.get("filters") or {}).get("end") or metadata["end"]),
    )
    stages = []
    try:
        for stage, months in windows.items():
            scope = clause(months)
            params = [*args, *months]
            summary = rows(
                "SELECT COUNT(*)::BIGINT AS rows,COUNT(DISTINCT invoice)::BIGINT AS orders,COALESCE(SUM(line_pence),0)::BIGINT AS gross_pence FROM transactions"
                + scope,
                params,
            )[0]
            invoices = rows(
                "SELECT invoice,SUM(line_pence)::BIGINT AS p FROM transactions"
                + scope
                + " GROUP BY 1 ORDER BY 1",
                params,
            )
            summary["aov"] = (
                round(summary["gross_pence"] / summary["orders"] / 100, 2)
                if summary["orders"]
                else None
            )
            product_sales = rows(
                "SELECT product_id,SUM(line_pence)::BIGINT AS p FROM transactions"
                + scope
                + products_only
                + " GROUP BY 1 ORDER BY 1",
                params,
            )
            # Shares of the lines counted as products, so they sum to 1 whether or not service lines are included.
            product_total = sum(r["p"] for r in product_sales)
            shares = (
                pd.DataFrame({"agenda_share": [r["p"] / product_total for r in product_sales]})
                if product_total
                else pd.DataFrame()
            )
            summary["product_hhi"] = finite(owner_concentration_hhi(shares))
            edges = []
            negative = None
            if ids:
                slots = ",".join("?" for _ in ids)
                edges = rows(
                    "WITH basket AS (SELECT DISTINCT invoice,product_id FROM transactions"
                    + scope
                    + f" AND product_id IN ({slots})) SELECT a.product_id AS source,b.product_id AS target,COUNT(*)::BIGINT AS weight FROM basket a JOIN basket b ON a.invoice=b.invoice AND a.product_id<b.product_id GROUP BY 1,2 HAVING COUNT(*)>=? ORDER BY 1,2",
                    [*params, *ids, minimum],
                )
                profile = rows(
                    "SELECT product_id,country,SUM(line_pence)::BIGINT AS p FROM transactions"
                    + scope
                    + f" AND product_id IN ({slots}) GROUP BY 1,2",
                    [*params, *ids],
                )
                if profile and len({r["country"] for r in profile}) >= 2:
                    matrix = (
                        pd.DataFrame(profile)
                        .pivot(index="product_id", columns="country", values="p")
                        .fillna(0)
                        .reindex(ids, fill_value=0)
                    )
                    negative = finite(negative_edge_share(build_party_affinity(matrix)))
            first = pd.Period(months[0], freq="M").start_time.date()
            last = pd.Period(months[-1], freq="M").end_time.date()
            covered_start = max(first, date.fromisoformat(effective_start))
            covered_end = min(last, date.fromisoformat(effective_end))
            days = max(0, (covered_end - covered_start).days + 1)
            expected = (last - first).days + 1
            stages.append(
                {
                    "stage": stage,
                    "months": months,
                    "summary": summary,
                    "aov_bootstrap": aov_interval([r["p"] for r in invoices]),
                    "edges": edges,
                    "edge_count": len(edges),
                    "negative_affinity_share": negative,
                    "coverage": {
                        "requested_start": str(first),
                        "requested_end": str(last),
                        "dataset_scope_start": effective_start,
                        "dataset_scope_end": effective_end,
                        "covered_days": days,
                        "requested_days": expected,
                        "partial": days < expected,
                    },
                }
            )
    finally:
        con.close()
    change = edge_comparison(stages[0]["edges"], stages[-1]["edges"])
    result = {
        "dataset_id": metadata["id"],
        "month": pivot,
        "window": window,
        "min_shared": minimum,
        "stages": stages,
        "selected_products": selected,
        "graph_comparison": change,
        "notes": [
            "Dönem toplamları farklı gün/ay sayıları içerir; kapsam eksikliği ve mevsimsellik farkları açıklayabilir.",
            (
                "HHI ürün kalemlerinin brüt satış paylarının kareleri toplamıdır (0–1). Kargo, Manual, ücret ve düzeltme kalemleri dahil edildi."
                if include_service(request)
                else "HHI ürün kalemlerinin brüt satış paylarının kareleri toplamıdır (0–1). Kargo, Manual, ücret ve düzeltme kalemleri ürün sayılmadı; dönem satışı ve AOV bunları içerir."
            ),
            "Ağlar seçilen dönemlerin birleşiminde en yüksek satışlı en fazla24 ürünü aynı evrende tutar. Aynı faturada birlikte alım karşılaştırılır; tüm ürün ağı değildir.",
            "Negatif profil benzerliği payı gözlenmiş olumsuz etkileşim veya birlikte alınmama değildir; tek ülkede hesaplanmaz.",
            "AOV aralığı 200 tekrar/seed47 invoice bootstrap ile betimleyicidir; bağımsız fatura varsayımı zaman/müşteri bağımlılığını kapsamaz. Tahmin, etki testi veya nedensellik değildir.",
            "Kapsam yalnız tarih uçlarından ölçülür; aradaki her günün eksiksiz kaydedildiğini doğrulamaz.",
        ],
    }
    digest = content_hash_text(
        json.dumps(
            {
                "source": metadata["sha256"],
                "filters": request.get("filters") or {},
                "version": "temporal-retail-v1",
                "result": result,
            },
            sort_keys=True,
            ensure_ascii=False,
            default=str,
            allow_nan=False,
        )
    )
    result["evidence"] = {
        "recipe_version": "temporal-retail-v1",
        "dataset_sha256": metadata["sha256"],
        "output_sha256": digest,
        "filters": request.get("filters") or {},
        "month": pivot,
        "window": window,
        "min_shared": minimum,
        "seed": 47,
        "bootstrap_repetitions": 200,
        "selected_product_ids": ids,
        "method": "PoliEco stage_months/HHI/profile affinity + fixed-universe invoice co-purchase",
        "duration_ms": round((time.perf_counter() - started) * 1000),
    }
    return result
