"""Bounded JSON worker: data and numbers are computed here, never invented by a model."""

from __future__ import annotations
from pathlib import Path
from collections import Counter
import csv, hashlib, io, json, os, re, sys, time
from datetime import date
import duckdb
from analysis.prepare import DATA, store
from analysis.adapted.guardrails import assess_input
from analysis.adapted.confidence import ConfidenceSignals, assess
from analysis.adapted.language import detect_language
from analysis.adapted.lexical import _BM25

# Local router vocabulary (word-start matches, so short Turkish stems do not hit unrelated words).
_RANK_SUBJECT = re.compile(r"(?<!\w)(product|item|ürün|urun|country|countries|ülke|ulke|market|pazar|where|nerede)", re.I)
_MARKET = re.compile(r"(?<!\w)(country|countries|ülke|ulke|market|pazar|where|nerede)", re.I)
# Rankings the local engine cannot compute: by units/orders, or toward the minimum.
_OTHER_RANK_METRIC = re.compile(r"(?<!\w)(units?|quantit|volume|adet|miktar|orders?|sipariş|siparis|invoices?|fatura)", re.I)
_MIN_DIRECTION = re.compile(r"(?<!\w)(lowest|least|smallest|worst|bottom|en düşük|en az|en kötü)", re.I)
# Questions about change over time; a static total or ranking does not answer them.
_CHANGE = re.compile(r"(?<!\w)(drop|dropp|fall|fell|declin|decreas|increas|rise|rising|rose|grow|düş|azal|art[ıt])", re.I)
_SUMMARY_EXTRA = re.compile(r"(?<!\w)(units?|quantit|sold|sell|market|where|nerede|pazar|miktar|items?|sku|rank|first|top|birinci|lider)", re.I)
_PRODUCT = re.compile(r"(?<!\w)(product|items?|sku|ürün|urun)", re.I)

VERSION = "retail-analysis-v4"
METRICS = [
    {
        "id": "gross_sales",
        "title": "Brüt satış",
        "unit": "GBP",
        "formula": "SUM(line_pence) / 100",
        "note": "İade/iptal hariç pozitif satış; net gelir değildir.",
    },
    {
        "id": "orders",
        "title": "Sipariş",
        "unit": "count",
        "formula": "COUNT(DISTINCT invoice)",
        "note": "Filtreli verideki benzersiz fatura sayısı. Farklı ürün/dönem kırılımlarındaki distinct sayılar her zaman toplamsal değildir.",
    },
    {
        "id": "units",
        "title": "Satılan adet",
        "unit": "count",
        "formula": "SUM(quantity)",
        "note": "Pozitif satış satırlarının miktarı.",
    },
    {
        "id": "aov",
        "title": "Ortalama sipariş",
        "unit": "GBP",
        "formula": "SUM(line_pence) / COUNT(DISTINCT invoice) / 100",
        "note": "Brüt satış / benzersiz sipariş.",
    },
]


def meta(dataset):
    if not re.fullmatch(r"(demo|uci|usr_[a-f0-9]{12}_[a-f0-9]{12})", str(dataset)):
        raise ValueError("Geçersiz veri seti.")
    p = DATA / (dataset + ".json")
    if not p.exists():
        raise ValueError("Veri seti bulunamadı.")
    value = json.loads(p.read_text())
    if dataset == "demo":
        value["title"] = "Perakende örneği"
    if dataset == "uci":
        value[
            "definition"
        ] += " Kargo, hizmet ve Manual gibi pozitif fatura kalemleri korunur; fiziksel ürün satışı olarak ayrıca sınıflandırılmamıştır."
    return value


def filters_for(request, m):
    f = request.get("filters") or {}
    if not isinstance(f, dict):
        raise ValueError("Filtreler nesne olmalı.")
    clauses = []
    args = []
    clean = {}
    for key, operator in [("start", ">="), ("end", "<=")]:
        if f.get(key):
            value = str(f[key])
            date.fromisoformat(value)
            clauses.append(f"order_date {operator} ?::DATE")
            args.append(value)
            clean[key] = value
    if clean.get("start", "0000") > clean.get("end", "9999"):
        raise ValueError("Başlangıç tarihi bitişten sonra olamaz.")
    if f.get("country"):
        if f["country"] not in m["countries"]:
            raise ValueError("Bu ülke veri setinde bulunmuyor.")
        clauses.append("country = ?")
        args.append(f["country"])
        clean["country"] = f["country"]
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), args, clean


def query(con, sql, params=()):
    c = con.execute(sql, params)
    names = [d[0] for d in c.description]
    return [dict(zip(names, row)) for row in c.fetchall()]


def overview(request):
    m = meta(request["dataset"])
    where, args, f = filters_for(request, m)
    con = duckdb.connect(str(DATA / (m["id"] + ".duckdb")), read_only=True)
    sql = (
        'SELECT COUNT(*)::BIGINT AS "rows", COUNT(DISTINCT invoice)::BIGINT orders, COALESCE(SUM(quantity),0)::BIGINT units, COALESCE(SUM(line_pence),0)::BIGINT gross_pence,COUNT(DISTINCT product_id)::BIGINT products FROM transactions'
        + where
    )
    summary = query(con, sql, args)[0]
    summary["gross_sales"] = summary["gross_pence"] / 100
    summary["aov"] = (
        round(summary["gross_sales"] / summary["orders"], 2) if summary["orders"] else 0
    )
    series = query(
        con,
        "SELECT strftime(order_date, '%Y-%m') AS period, SUM(line_pence)::BIGINT pence,COUNT(DISTINCT invoice)::BIGINT orders FROM transactions"
        + where
        + " GROUP BY 1 ORDER BY 1",
        args,
    )
    countries = query(
        con,
        "SELECT country AS label,SUM(line_pence)::BIGINT pence,COUNT(DISTINCT invoice)::BIGINT orders FROM transactions"
        + where
        + " GROUP BY 1 ORDER BY 2 DESC,1 LIMIT 10",
        args,
    )
    products = query(
        con,
        "SELECT product_id,MIN(product) AS label,SUM(line_pence)::BIGINT pence,SUM(quantity)::BIGINT units FROM transactions"
        + where
        + " GROUP BY 1 ORDER BY 3 DESC,1 LIMIT 12",
        args,
    )
    # Stable row sampling; raw customer identifiers are not displayed or exported.
    preview = query(
        con,
        "SELECT invoice,product_id,product,quantity,unit_price::DOUBLE unit_price,order_date::VARCHAR date,country,line_pence::BIGINT line_pence FROM transactions"
        + where
        + " ORDER BY order_date,invoice,product_id,quantity,unit_price,line_pence,product,country LIMIT 30",
        args,
    )
    con.close()
    return {
        "dataset": m,
        "filters": f,
        "summary": summary,
        "series": series,
        "countries": countries,
        "products": products,
        "preview": preview,
        "metrics": METRICS,
        "sql": sql,
        "params": args,
    }


def graph(request):
    import numpy as np
    import pandas as pd
    import networkx as nx
    from analysis.adapted.networks import build_sparse_signed_graph

    m = meta(request["dataset"])
    where, args, f = filters_for(request, m)
    con = duckdb.connect(str(DATA / (m["id"] + ".duckdb")), read_only=True)
    top = query(
        con,
        "SELECT product_id,MIN(product) AS label,SUM(line_pence)::BIGINT pence,COUNT(DISTINCT invoice)::BIGINT orders FROM transactions"
        + where
        + " GROUP BY 1 ORDER BY 3 DESC,1 LIMIT 24",
        args,
    )
    ids = [x["product_id"] for x in top]
    labels = {x["product_id"]: x["label"] for x in top}
    nodes = []
    edges = []
    mode = request.get("graph_mode", "copurchase")
    if mode not in ["copurchase", "similarity"]:
        raise ValueError("Geçersiz ağ yöntemi.")
    if not ids:
        return {
            "nodes": [],
            "edges": [],
            "mode": mode,
            "note": "Bu filtrelerle ilişki hesaplanacak ürün yok.",
        }
    slots = ",".join("?" for _ in ids)
    minimum = int(request.get("min_shared", 2))
    if minimum < 1 or minimum > 100:
        raise ValueError("Ortak sipariş eşiği 1–100 arasında olmalı.")
    if mode == "copurchase":
        edge_sql = f"""WITH selected AS (SELECT DISTINCT invoice,product_id FROM transactions{where}{' AND ' if where else ' WHERE '}product_id IN ({slots})) SELECT a.product_id AS source,b.product_id AS target,COUNT(*)::BIGINT weight FROM selected a JOIN selected b ON a.invoice=b.invoice AND a.product_id<b.product_id GROUP BY 1,2 HAVING COUNT(*)>=? ORDER BY 3 DESC,1,2 LIMIT 150"""
        edges = query(con, edge_sql, [*args, *ids, minimum])
        note = "Kenar ağırlığı: iki ürünün aynı faturada birlikte görüldüğü sipariş sayısı. İlk 24 ürün ve en güçlü en fazla 150 ilişki gösterilir; merkeziyetler bu görünür alt ağ içindir. Fatura hizmet/kargo kalemleri de ürün kodları arasında kalabilir. Tüm veri ağı değildir."
    else:
        matrix = query(
            con,
            f"SELECT product_id,country,SUM(line_pence)::BIGINT AS value FROM transactions{where}"
            + (" AND " if where else " WHERE ")
            + f"product_id IN ({slots}) GROUP BY 1,2",
            [*args, *ids],
        )
        frame = (
            pd.DataFrame(matrix)
            .pivot(index="product_id", columns="country", values="value")
            .fillna(0)
            .reindex(ids, fill_value=0)
        )
        adj = np.zeros((len(ids), len(ids)))
        if len(frame.columns) >= 2:
            adj, _ = build_sparse_signed_graph(frame, k_pos=3, k_neg=2)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                if abs(float(adj[i, j])) >= 0.10:
                    edges.append(
                        {
                            "source": ids[i],
                            "target": ids[j],
                            "weight": round(float(adj[i, j]), 4),
                        }
                    )
        edge_sql = "PoliEco build_sparse_signed_graph(product × country sales matrix); k_pos=3,k_neg=2; abs(weight)>=0.10"
        note = "PoliEco koduyla ülkelere göre satış profili benzerliği. Pozitif/negatif kenar gözlenmiş etkileşim değildir; birlikte alım veya nedensellik anlamına gelmez. Benzerlik için en az iki ülke gerekir; tek ülke filtresinde kenar üretilmez. Topluluklar yalnız pozitif benzerlik kenarlarından bulunur. Derece/betweenness görünür tüm kenarlarda işaretten bağımsız hesaplanır."
    g = nx.Graph()
    g.add_nodes_from(ids)
    for e in edges:
        g.add_edge(
            e["source"], e["target"], weight=abs(e["weight"]), signed_weight=e["weight"]
        )
    from analysis.layout import readable_positions, positive_communities

    pos = readable_positions(g)
    communities = positive_communities(g)
    membership = {n: i for i, c in enumerate(communities) for n in c}
    centrality = nx.betweenness_centrality(g, weight=None)
    for item in top:
        n = item["product_id"]
        nodes.append(
            {
                "id": n,
                "label": labels[n],
                "pence": item["pence"],
                "orders": item["orders"],
                "degree": g.degree(n),
                "brokerage": round(centrality[n], 5),
                "community": membership[n],
                "x": round(float(pos[n][0]), 5),
                "y": round(float(pos[n][1]), 5),
            }
        )
    con.close()
    return {
        "nodes": nodes,
        "edges": edges,
        "mode": mode,
        "note": note,
        "components": nx.number_connected_components(g),
        "communities": len(communities),
        "sql": edge_sql,
        "source_method": (
            "PoliEco similarity kernel + NetworkX seed=47"
            if mode == "similarity"
            else "Observed invoice co-occurrence + NetworkX seed=47"
        ),
        "min_shared": minimum,
        "filters": f,
    }


def explain(request, result):
    prompt = str(request.get("question") or "").strip()
    if not prompt:
        return None
    check = assess_input(prompt)
    if not check.allowed:
        return {
            "status": "refused",
            "reason": check.category,
            "text": "Bu istek güvenli analiz sınırları dışında. Veri, metrik veya ürün ilişkileri hakkında sorabilirsiniz.",
            "mode": "deterministic",
        }
    t = prompt.casefold()
    en = detect_language(prompt) == "en"
    country_change = any(
        re.search(r"(?<!\w)" + re.escape(country.casefold()) + r"(?!\w)", t)
        and result["filters"].get("country") != country
        for country in result["dataset"]["countries"]
    )
    if country_change:
        return {
            "status": "clarify",
            "reason": "explicit_filter_required",
            "text": (
                "Apply the requested country filter, then run the analysis."
                if en
                else "Önce istediğiniz ülkeyi filtrelerden seçip Uygula'ya basın; ardından soruyu çalıştırın."
            ),
            "mode": "deterministic",
        }
    if any(
        x in t
        for x in [
            "net gelir",
            "net revenue",
            "net sales",
            "net income",
            "net ciro",
            "why",
            "neden",
            "predict",
            "next month",
            "margin",
            "growth rate",
            "profit",
            "kâr",
            "kar marj",
            "conversion",
            "dönüşüm",
            "neden düşt",
            "neden artt",
            "caus",
            "forecast",
            "tahmin",
            "gelecek",
        ]
    ):
        return {
            "status": "cannot_verify",
            "reason": "unsupported_metric_or_causality",
            "text": "Bu veri ve yerel açıklama bu hesabı doğrulayamıyor. Brüt satış, sipariş, ürün/ülke kırılımı ve birlikte alım incelenebilir. Kâr, dönüşüm, tahmin veya nedensellik için ek veri/yöntem gerekir.",
            "mode": "deterministic",
        }
    if _CHANGE.search(t):
        return {
            "status": "cannot_verify",
            "reason": "unsupported_metric_or_causality",
            "text": (
                "A change over time needs explicit periods; a static total or ranking does not answer it. Use Change over time or compare two saved analyses."
                if en
                else "Zaman içindeki değişim açık dönemler ister; tek bir toplam veya sıralama bunu yanıtlamaz. Zaman içindeki değişim aracını veya iki analizi karşılaştırmayı kullanın."
            ),
            "mode": "deterministic",
        }
    if _RANK_SUBJECT.search(t) and (_OTHER_RANK_METRIC.search(t) or _MIN_DIRECTION.search(t)):
        return {
            "status": "cannot_verify",
            "reason": "unsupported_ranking_metric",
            "text": (
                "Only the top product or country by gross sales value is computed here. Rankings by units, orders or toward the lowest value are not; use the SQL lab or the ranking tables."
                if en
                else "Burada yalnız brüt satış tutarına göre en üstteki ürün veya ülke hesaplanır. Adet, sipariş veya en düşük değere göre sıralama hesaplanmaz; SQL laboratuvarını veya sıralama tablolarını kullanın."
            ),
            "mode": "deterministic",
        }
    if any(
        x in t
        for x in [
            "birlikte",
            "co-purchase",
            "bought together",
            "network",
            "ilişki",
            "ilişki ağı",
        ]
    ):
        return {
            "status": "clarify",
            "reason": "open_network_tool",
            "text": (
                "Open Relationship network to compute co-purchase or profile similarity with its evidence."
                if en
                else "Birlikte alım veya profil benzerliğini hesaplamak için İlişki ağı bölümünü açın; tanım, eşik ve kanıt orada görünür."
            ),
            "mode": "deterministic",
        }
    if any(
        x in t
        for x in [
            "trend",
            "monthly",
            "aylık",
            "aylik",
            "karşılaştır",
            "karsilastir",
            "compare",
        ]
    ) or (re.search(r"(?<!\w)(month|week|aylara|haftalara|ay ay|hafta hafta)", t) and not _RANK_SUBJECT.search(t)):
        return {
            "status": "clarify",
            "reason": "open_temporal_tool",
            "text": (
                "Use Change over time in Relationship network, or Compare analyses in My findings, to select explicit periods."
                if en
                else "Açık dönemler seçmek için İlişki ağı → Zaman içindeki değişim veya Bulgularım → İki analizi karşılaştırın aracını kullanın."
            ),
            "mode": "deterministic",
        }
    if not _SUMMARY_EXTRA.search(t) and not any(
        x in t
        for x in [
            "satış",
            "satis",
            "gelir",
            "ciro",
            "ürün",
            "urun",
            "ülke",
            "ulke",
            "sipariş",
            "siparis",
            "adet",
            "sales",
            "revenue",
            "product",
            "order",
            "country",
            "trend",
            "özet",
            "ozet",
            "summary",
            "ağ",
            "network",
            "veri",
        ]
    ):
        return {
            "status": "clarify",
            "reason": "unknown_intent",
            "text": "Hangi metriği inceleyelim? Brüt satış, en çok satan ürünler, ülke dağılımı veya ürün ilişkileri sorabilirsiniz.",
            "mode": "deterministic",
        }
    s = result["summary"]
    if not s["rows"]:
        return {
            "status": "cannot_verify",
            "reason": "empty_result",
            "text": "Seçili filtrelerde satış satırı yok. Tarih aralığını genişletin veya ülke filtresini temizleyin.",
            "mode": "deterministic",
        }

    def amount(value):
        value = f"{value:,.2f}"
        return "£" + (
            value if en else value.replace(",", "_").replace(".", ",").replace("_", ".")
        )

    def tally(value):
        text = f"{value:,}"
        return text if en else text.replace(",", ".")

    money = amount(s["gross_sales"])
    claims = [
        {
            "metric": key,
            "value": s[key],
            "unit": "GBP" if key in ["gross_sales", "aov"] else "count",
        }
        for key in ["gross_sales", "orders", "units", "aov"]
    ]
    if _PRODUCT.search(t) and result["products"]:
        first = max(result["products"], key=lambda x: x["pence"])
        claims = [
            {
                "metric": "gross_sales",
                "value": first["pence"] / 100,
                "unit": "GBP",
                "scope": {"product_id": first["product_id"]},
                "rank": 1,
            }
        ]
        text = f"{first['label']}, seçili veride {amount(first['pence']/100)} brüt satışla ilk sırada. Sıralama satış tutarına göredir; miktar ve kâr sıralaması farklı olabilir."
    elif _MARKET.search(t) and result["countries"]:
        first = result["countries"][0]
        claims = [
            {
                "metric": "gross_sales",
                "value": first["pence"] / 100,
                "unit": "GBP",
                "scope": {"country": first["label"]},
                "rank": 1,
            }
        ]
        text = f"{first['label']}, {amount(first['pence']/100)} ile seçili verinin en yüksek brüt satışına sahip ülkesi. Ülke karşılaştırması aynı filtre ve tanımla hesaplandı."
    else:
        text = f"Seçili veride brüt satış {money}; {tally(s['orders'])} sipariş ve {tally(s['units'])} adet ürün var. Ortalama sipariş {amount(s['aov'])}. İade ve iptaller dışlandı; tutar net gelir değildir."
    if en:
        if "scope" in claims[0]:
            text = f"{first['label']} ranks first by gross sales at {amount(first['pence']/100)} in the selected scope. This is a sales-value ranking, not profit or causality."
        else:
            text = f"Selected data: {money} gross sales across {s['orders']:,} orders and {s['units']:,} units. Average order value: {amount(s['aov'])}. Returns/cancellations are excluded; this is not net revenue."
    from analysis.claims import verify_numeric_claims

    supported = verify_numeric_claims(claims, result)
    if not supported:
        return {
            "status": "cannot_verify",
            "reason": "numeric_claim_mismatch",
            "text": "Sayısal iddia hesap kaydıyla eşleşmedi.",
            "mode": "deterministic",
        }
    policies = assess(
        ConfidenceSignals(
            intent="analytics",
            evidence_count=1,
            independent_source_count=1,
            metadata_compatible=True,
            planner_valid=True,
            citations_present=True,
            citations_required=True,
            claim_coverage_checked=True,
            claims_supported=supported,
        )
    )

    return {
        "status": policies.status,
        "reason": "computed_result",
        "text": text,
        "mode": "deterministic",
        "source": "metrics/retail-v1",
        "claims": claims,
    }


def run(request):
    started = time.perf_counter()
    result = overview(request)
    if request.get("include_graph", True):
        result["graph"] = graph(request)
    result["answer"] = explain(request, result)
    from analysis.llm import status, plan_question, INTENTS

    result["provider"] = status()
    if request.get("use_llm") is True and request.get("question"):
        # Local refusal takes precedence: never send policy-refused text to a provider.
        baseline = result["answer"] or {}
        if baseline.get("status") == "refused" or baseline.get("reason") in {
            "unsupported_metric_or_causality",
            "explicit_filter_required",
        }:
            result["planner"] = {"status": "blocked", "intent": "unsupported"}
        else:
            plan = plan_question(str(request["question"]))
            result["planner"] = plan
            result["provider"]["connected"] = plan["status"] == "planned"
            if plan["status"] == "planned":
                canonical = INTENTS[plan["intent"]]
                if request.get("locale") != "en":
                    canonical = {
                        "summary": "Satışları özetle",
                        "products": "En çok satan ürün",
                        "countries": "Ülke satışları",
                        "network": "Birlikte alım",
                        "temporal": "Aylık trend",
                        "unsupported": "Net gelir",
                        "clarify": "belirsiz",
                    }[plan["intent"]]
                result["answer"] = explain({**request, "question": canonical}, result)
                result["answer"]["mode"] = "llama-plan-verified-facts"
    from analysis.fingerprint import fingerprint

    result["build"] = fingerprint()
    from analysis.adapted.identity import content_hash_text

    body = {
        "version": VERSION,
        "dataset_sha256": result["dataset"]["sha256"],
        "filters": result["filters"],
        "build": result["build"],
        "plan": {
            k: v for k, v in result.get("planner", {}).items() if k != "telemetry"
        },
        **{
            key: result.get(key)
            for key in [
                "summary",
                "series",
                "countries",
                "products",
                "preview",
                "graph",
                "answer",
            ]
        },
    }
    result["evidence"] = {
        "recipe_version": VERSION,
        "build": result["build"],
        "dataset_sha256": result["dataset"]["sha256"],
        "output_sha256": content_hash_text(
            json.dumps(body, sort_keys=True, ensure_ascii=False, default=str)
        ),
        "metric_version": "retail-v1",
        "currency": "GBP",
        "sql": result["sql"],
        "parameters": result["params"],
        "source": result["dataset"]["source"],
        "policy": "read-only allowlisted operations; parameterized filters; invoice grain",
        "duration_ms": round((time.perf_counter() - started) * 1000),
    }
    return result


def handle(request):
    action = request.get("action", "run")
    if action == "catalog":
        return {
            "datasets": [meta(x) for x in request.get("ids", ["demo", "uci"])],
            "metrics": METRICS,
            "provider": __import__("analysis.llm", fromlist=["status"]).status(),
        }
    if action == "run":
        return run(request)
    if action in {"forecast", "decisions"}:
        from analysis.forecast import forecast

        m = meta(request["dataset"])
        where, args, _ = filters_for(request, m)
        _, _, clean = filters_for(request, m)
        request = {**request, "filters": clean}
        prediction = forecast(request, m, where, args, DATA)
        if action == "forecast":
            return prediction
        from analysis.decisions import decision_brief

        observed = overview(request)
        observed["graph"] = graph(
            {**request, "graph_mode": "copurchase", "min_shared": 2}
        )
        return decision_brief(request, observed, prediction)
    if action == "graph":
        return graph(request)
    if action == "temporal":
        from analysis.temporal import analyze_temporal

        m = meta(request["dataset"])
        where, args, _ = filters_for(request, m)
        return analyze_temporal(request, m, where, args, DATA)
    if action == "context":
        from analysis.context import search_context

        return search_context(
            request.get("query", ""), meta(request["dataset"]), METRICS
        )
    if action == "sql":
        from analysis.sql_lab import execute_sql

        m = meta(request["dataset"])
        where, args, _ = filters_for(request, m)
        return execute_sql(request, m, where, args, DATA)
    if action == "compare":
        from analysis.sql_lab import compare_results

        return compare_results(request["before"], request["after"])
    if action == "export":
        import base64
        from analysis.adapted.exports import rows_to_csv, rows_to_xlsx

        rows = request.get("rows", [])
        kind = request.get("format")
        if kind not in ["csv", "xlsx"] or not isinstance(rows, list):
            raise ValueError("Geçersiz export.")
        payload = (rows_to_csv if kind == "csv" else rows_to_xlsx)(
            rows, request.get("columns")
        )
        return {
            "base64": base64.b64encode(payload).decode(),
            "format": kind,
            "rows": len(rows),
        }

    if action == "ml":
        from analysis.ml import experiment

        return experiment(request)
    if action == "prepare":
        from analysis.preparation import prepare

        return prepare(request)
    if action == "import":
        if request.get("mapping") is not None:
            from analysis.preparation import prepare, load_table, map_frame, options_for

            prepared = prepare(request)
            if request.get("receipt") != prepared["receipt"]:
                raise ValueError("Önizleme değişti veya eksik. Yeniden önizleyin.")
            raw, _ = map_frame(
                load_table(request)[0],
                request["mapping"],
                options_for(request.get("options")),
            )
            owner = str(request.get("owner", ""))
            if not re.fullmatch("[a-f0-9]{12}", owner):
                raise ValueError("Geçersiz içe aktarma kapsamı.")
            return store(
                "usr_" + owner + "_" + prepared["receipt"][:12],
                str(request.get("title", "Yüklenen CSV"))[:80],
                raw,
                {
                    "kind": "uploaded",
                    "publisher": "Kullanıcı yüklemesi",
                    "license": "user-provided",
                    "description": "Kullanıcı tarafından sağlanan veri; doğruluğu dış kaynaktan teyit edilmedi.",
                    "preparation": {
                        "recipe": prepared["recipe"],
                        "receipt": prepared["receipt"],
                        "preview": prepared["preview"],
                        "source_format": prepared["source_format"],
                    },
                },
            )
        content = str(request.get("csv", ""))
        if len(content.encode()) > 2_000_000:
            raise ValueError("CSV sınırı 2 MB.")
        import pandas as pd

        raw = pd.read_csv(
            io.StringIO(content), dtype={"invoice": str, "product_id": str}
        )
        # Keep uploaded prices representable by the materialized DECIMAL(18,4).
        from decimal import Decimal, InvalidOperation

        price_column = "unit_price" if "unit_price" in raw.columns else "UnitPrice"
        if price_column in raw.columns:
            for value in raw[price_column].dropna():
                try:
                    price = Decimal(str(value))
                except InvalidOperation:
                    continue
                if price.is_finite() and price.as_tuple().exponent < -4:
                    raise ValueError(
                        "Birim fiyat en fazla 4 ondalık basamak içerebilir; sessiz fiyat yuvarlaması yapılmadı."
                    )
        if len(raw) > 10000:
            raise ValueError("CSV sınırı 10.000 satır.")
        owner = str(request.get("owner", ""))
        if not re.fullmatch("[a-f0-9]{12}", owner):
            raise ValueError("Geçersiz içe aktarma kapsamı.")
        dataset = (
            "usr_" + owner + "_" + hashlib.sha256(content.encode()).hexdigest()[:12]
        )
        title = str(request.get("title", "Yüklenen CSV"))[:80]
        return store(
            dataset,
            title,
            raw,
            {
                "kind": "uploaded",
                "publisher": "Kullanıcı yüklemesi",
                "license": "user-provided",
                "description": "Kullanıcı tarafından sağlanan veri; doğruluğu dış kaynaktan teyit edilmedi.",
            },
        )
    if action == "search":
        words = re.findall(r"[^\W_]+", str(request.get("query", "")).casefold())
        docs = [(x["title"] + " " + x["note"]).casefold().split() for x in METRICS]
        scores = _BM25(docs).scores(words)
        return [x for _, x in sorted(zip(scores, METRICS), key=lambda z: -z[0])]
    raise ValueError("Bilinmeyen işlem.")


def main():
    try:
        # CSV remains <=2 MB at the action gate; escaped JSON and two stored
        # <=5 MB analysis artifacts need a larger bounded transport envelope.
        request = json.loads(sys.stdin.read(10_500_000))
        result = handle(request)
        print(
            json.dumps(
                {"ok": True, "result": result},
                ensure_ascii=False,
                default=str,
                allow_nan=False,
            )
        )
    except (ValueError, KeyError, TypeError, duckdb.Error) as e:
        print(json.dumps({"ok": False, "error": str(e)[:250]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
