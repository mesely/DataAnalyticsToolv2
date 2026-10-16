"""One-week gross-sales benchmark, development selection and untouched rolling holdout."""

from __future__ import annotations
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import hashlib, json, math
import duckdb
from analysis.fingerprint import fingerprint

VERSION = "weekly-gross-v1"


def predict(history, method):
    if method == "naive":
        return history[-1]
    if method == "mean4":
        return sum(history[-4:]) / 4
    raise ValueError("Unknown forecast method")


def metrics(records):
    errors = [r["actual_pence"] - r["predicted_pence"] for r in records]
    denom = sum(r["actual_pence"] for r in records)
    return {
        "mae_gbp": sum(abs(e) for e in errors) / len(errors) / 100,
        "rmse_gbp": math.sqrt(sum(e * e for e in errors) / len(errors)) / 100,
        "wape": sum(abs(e) for e in errors) / denom if denom else None,
        "n": len(records),
    }


def backtest(weeks):
    if len(weeks) < 16:
        return {
            "status": "insufficient_data",
            "reason": "At least 16 complete weeks are required for development and four held-out origins.",
            "complete_weeks": len(weeks),
            "history": weeks,
        }
    if len(weeks) > 260:
        raise ValueError(
            "Forecast supports at most 260 complete weeks; select a shorter date range."
        )
    values = [w["pence"] for w in weeks]
    candidates = {}
    for method in ("naive", "mean4"):
        records = [
            {
                "origin": weeks[i - 1]["period"],
                "target": weeks[i]["period"],
                "train_end_index": i - 1,
                "actual_pence": values[i],
                "predicted_pence": predict(values[:i], method),
            }
            for i in range(4, len(values) - 4)
        ]
        candidates[method] = {"development": metrics(records), "records": records}
    selected = min(candidates, key=lambda m: candidates[m]["development"]["mae_gbp"])

    def holdout(method):
        return [
            {
                "origin": weeks[i - 1]["period"],
                "target": weeks[i]["period"],
                "train_end_index": i - 1,
                "actual_pence": values[i],
                "predicted_pence": predict(values[:i], method),
            }
            for i in range(len(values) - 4, len(values))
        ]

    final_records = holdout(selected)
    residuals = sorted(
        abs(r["actual_pence"] - r["predicted_pence"])
        for r in candidates[selected]["records"]
    )
    # Empirical development residual envelope; explicitly not calibrated probability.
    radius = residuals[min(len(residuals) - 1, math.ceil(0.9 * len(residuals)) - 1)]
    point = predict(values, selected)
    next_week = (
        date.fromisoformat(weeks[-1]["period"]) + timedelta(days=7)
    ).isoformat()
    return {
        "status": "ready",
        "complete_weeks": len(weeks),
        "history": weeks,
        "selected": selected,
        "candidates": candidates,
        "holdout": {
            "selected": metrics(final_records),
            "naive": metrics(holdout("naive")),
            "records": final_records,
        },
        "next": {
            "period": next_week,
            "pence": point,
            "lower_pence": max(0, point - radius),
            "upper_pence": point + radius,
        },
        "uncertainty": {
            "method": "development absolute-error empirical 90th percentile envelope",
            "residual_count": len(residuals),
            "calibrated": False,
        },
        "split": {
            "first_origin": 4,
            "holdout_origins": 4,
            "selection_end_index": len(values) - 5,
            "horizon_weeks": 1,
        },
    }


def forecast(request, metadata, where, args, data_dir):
    start = max(
        date.fromisoformat(metadata["start"]),
        date.fromisoformat(
            (request.get("filters") or {}).get("start", metadata["start"])
        ),
    )
    end = min(
        date.fromisoformat(metadata["end"]),
        date.fromisoformat((request.get("filters") or {}).get("end", metadata["end"])),
    )
    first = start + timedelta(days=(-start.weekday()) % 7)
    last = end - timedelta(days=(end.weekday() + 1) % 7)
    weeks = []
    with duckdb.connect(
        str(data_dir / (metadata["id"] + ".duckdb")), read_only=True
    ) as con:
        rows = con.execute(
            "SELECT order_date::VARCHAR, SUM(line_pence)::BIGINT FROM transactions"
            + where
            + " GROUP BY 1 ORDER BY 1",
            args,
        ).fetchall()
    observed = {date.fromisoformat(d): int(p) for d, p in rows}
    while first + timedelta(days=6) <= last:
        if len(weeks) >= 260:
            raise ValueError("Select at most 260 complete weeks.")
        weeks.append(
            {
                "period": first.isoformat(),
                "pence": sum(
                    observed.get(first + timedelta(days=i), 0) for i in range(7)
                ),
            }
        )
        first += timedelta(days=7)
    result = backtest(weeks)
    if not any(w["pence"] for w in weeks):
        result = {
            "status": "insufficient_data",
            "reason": "No positive gross sales in complete weeks of this scope.",
            "complete_weeks": len(weeks),
            "history": weeks,
        }
    result["notes"] = [
        "Positive invoice-line gross GBP; excludes returns/cancellations and is not net revenue or profit.",
        "Only complete Monday–Sunday weeks; boundary fragments excluded. Dates without observed rows count as zero; collection completeness is not established.",
        "One-step rolling origins use only earlier observations. Final four origins never select the method.",
        "Residual envelope is empirical, not a guaranteed or calibrated prediction interval. Historical records may not represent future trading.",
    ]
    result["scope"] = {
        "filters": request.get("filters") or {},
        "dataset_sha256": metadata["sha256"],
        "observed_start": start.isoformat(),
        "observed_end": end.isoformat(),
    }
    result["build"] = fingerprint()
    result["recipe_version"] = VERSION
    result["output_sha256"] = hashlib.sha256(
        json.dumps(result, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()
    return result


def scenario(baseline_pence, value):
    if not isinstance(value, dict) or set(value) - {
        "volume_pct",
        "price_pct",
        "budget_gbp",
    }:
        raise ValueError("Invalid scenario fields")
    clean = {}
    for key, lo, hi in [
        ("volume_pct", -50, 100),
        ("price_pct", -50, 100),
        ("budget_gbp", 0, 1_000_000),
    ]:
        v = value.get(key, 0)
        if (
            isinstance(v, bool)
            or not isinstance(v, (int, float))
            or not math.isfinite(v)
            or not lo <= v <= hi
        ):
            raise ValueError("Scenario value outside allowed range")
        clean[key] = Decimal(str(v))
    base = Decimal(str(baseline_pence))
    money = lambda n: int(n.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    assumed = money(
        base * (1 + clean["volume_pct"] / 100) * (1 + clean["price_pct"] / 100)
    )
    return {
        "assumptions": {k: float(v) for k, v in clean.items()},
        "baseline_pence": money(base),
        "assumed_gross_pence": assumed,
        "gross_delta_pence": assumed - money(base),
        "budget_pence": money(clean["budget_gbp"] * 100),
        "note": "User assumptions, not predicted causal effects. Price and volume vary independently; demand elasticity, margin, capacity, returns and campaign effectiveness are unknown. Budget is shown separately; gross delta is not profit or ROI.",
    }
