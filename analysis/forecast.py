"""One-week gross-sales benchmark (weekly-gross-v2).

Registered baselines (naive, seasonal naive, drift, moving means, exponential smoothing, damped Holt) are
compared by one-step rolling-origin error on DEVELOPMENT origins only; the method is selected there.
A FINAL window (the last origins) is evaluated for every candidate afterwards and never influences the
selection. If the naive method wins, it is selected and the product says so.
"""

from __future__ import annotations
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import hashlib, json, math, statistics
import duckdb
from analysis.fingerprint import fingerprint

VERSION = "weekly-gross-v2"
MIN_WEEKS, MAX_WEEKS = 16, 260
FIRST_ORIGIN = 8  # every registered candidate needs at most 8 prior observations
SEASON_WEEKS = 52
MAX_FINAL_ORIGINS = 12
INTERVAL_LEVELS = (0.8, 0.9)


def _ses(history, alpha):
    level = history[0]
    for v in history[1:]:
        level = alpha * v + (1 - alpha) * level
    return level


def _holt(history, alpha, beta, phi):
    level, trend = history[0], history[1] - history[0]
    for v in history[1:]:
        previous = level
        level = alpha * v + (1 - alpha) * (previous + phi * trend)
        trend = beta * (level - previous) + (1 - beta) * phi * trend
    return level + phi * trend


def _drift(history):
    if len(history) < 2:
        return history[-1]
    return history[-1] + (history[-1] - history[0]) / (len(history) - 1)


# Registered candidates, simplest first. Equal development error resolves toward the earlier entry.
CANDIDATES = [
    ("naive", "last observed week", lambda h: h[-1]),
    ("seasonal_naive", "same week one season (52 weeks) earlier", lambda h: h[-SEASON_WEEKS]),
    ("drift", "last week plus the average historical weekly change", _drift),
    ("mean2", "mean of the last 2 weeks", lambda h: sum(h[-2:]) / 2),
    ("mean4", "mean of the last 4 weeks", lambda h: sum(h[-4:]) / 4),
    ("mean8", "mean of the last 8 weeks", lambda h: sum(h[-8:]) / 8),
    ("ses_0.2", "simple exponential smoothing, alpha 0.2", lambda h: _ses(h, 0.2)),
    ("ses_0.5", "simple exponential smoothing, alpha 0.5", lambda h: _ses(h, 0.5)),
    ("ses_0.8", "simple exponential smoothing, alpha 0.8", lambda h: _ses(h, 0.8)),
    ("holt_damped_0.3_0.1", "damped Holt linear trend (alpha 0.3, beta 0.1, phi 0.9)", lambda h: _holt(h, 0.3, 0.1, 0.9)),
    ("holt_damped_0.6_0.1", "damped Holt linear trend (alpha 0.6, beta 0.1, phi 0.9)", lambda h: _holt(h, 0.6, 0.1, 0.9)),
]
_BY_ID = {cid: fn for cid, _, fn in CANDIDATES}
_ORDER = {cid: i for i, (cid, _, _) in enumerate(CANDIDATES)}


def predict(history, method):
    if method not in _BY_ID:
        raise ValueError("Unknown forecast method")
    if method == "seasonal_naive" and len(history) <= SEASON_WEEKS:
        raise ValueError("seasonal_naive needs more than one season of history")
    return _BY_ID[method](history)


def metrics(records, scale_pence=None):
    """MAE/RMSE in GBP, WAPE, sMAPE (pairs with |a|+|f| = 0 skipped), MASE (scaled by the development
    naive MAE when given) and bias (mean actual - predicted, GBP). MAPE is deliberately absent: weekly
    gross can be zero."""
    errors = [r["actual_pence"] - r["predicted_pence"] for r in records]
    n = len(errors)
    mae = sum(abs(e) for e in errors) / n
    denom = sum(abs(r["actual_pence"]) for r in records)
    smape_terms = []
    for r in records:
        d = abs(r["actual_pence"]) + abs(r["predicted_pence"])
        if d > 0:
            smape_terms.append(2 * abs(r["actual_pence"] - r["predicted_pence"]) / d)
    return {
        "mae_gbp": mae / 100,
        "rmse_gbp": math.sqrt(sum(e * e for e in errors) / n) / 100,
        "wape": sum(abs(e) for e in errors) / denom if denom else None,
        "smape": sum(smape_terms) / len(smape_terms) if smape_terms else None,
        "mase": (mae / scale_pence) if scale_pence else None,
        "bias_gbp": sum(errors) / n / 100,
        "n": n,
    }


def _records(weeks, values, fn, origins):
    return [
        {
            "origin": weeks[i - 1]["period"],
            "target": weeks[i]["period"],
            "train_end_index": i - 1,
            "actual_pence": values[i],
            "predicted_pence": fn(values[:i]),
        }
        for i in origins
    ]


def _diagnostics(weeks, values, seasonal_available, scale, selected, candidates, holdout):
    out = []
    n = len(values)
    if not seasonal_available:
        out.append({
            "code": "seasonal_naive_unavailable", "severity": "info",
            "message": f"Seasonal naive (52-week) needs at least {2 * SEASON_WEEKS} complete weeks; {n} available. Yearly seasonality cannot be validated from this history.",
        })
    zero = sum(1 for v in values if v == 0)
    if zero:
        out.append({"code": "zero_weeks", "severity": "warning",
                    "message": f"{zero} complete week(s) have no observed gross sales; they count as zero and may be collection gaps."})
    med = statistics.median(values)
    mad = statistics.median(abs(v - med) for v in values)
    # robust scale: 1.4826*MAD; when more than half the weeks sit exactly at the median, fall back to the mean absolute deviation
    robust = 1.4826 * mad if mad > 0 else statistics.mean(abs(v - med) for v in values)
    if robust > 0:
        outliers = [w["period"] for w, v in zip(weeks, values) if abs(v - med) > 3 * robust]
        if outliers:
            out.append({"code": "outlier_weeks", "severity": "warning",
                        "message": "Weeks far from the typical level (robust 3-sigma): " + ", ".join(outliers[:5]) + (" …" if len(outliers) > 5 else "") + "."})
    if n >= 16 and scale:
        recent, prior = sum(values[-8:]) / 8, sum(values[-16:-8]) / 8
        if abs(recent - prior) > 2 * scale:
            out.append({"code": "possible_level_shift", "severity": "warning",
                        "message": "The mean of the last 8 weeks differs from the previous 8 by more than twice the typical weekly change; a structural change cannot be excluded."})
    dev = candidates[selected]["records"]
    if len(dev) >= 8:
        half = len(dev) // 2
        a = metrics(dev[:half])["mae_gbp"]
        b = metrics(dev[half:])["mae_gbp"]
        if min(a, b) > 0 and max(a, b) / min(a, b) > 2:
            out.append({"code": "unstable_development_error", "severity": "warning",
                        "message": f"The selected method's error differs more than twofold between the first and second half of the development origins ({a:,.0f} vs {b:,.0f} GBP MAE)."})
    naive_dev = candidates["naive"]["development"]["mae_gbp"]
    best_dev = candidates[selected]["development"]["mae_gbp"]
    if selected != "naive" and naive_dev > 0 and (naive_dev - best_dev) / naive_dev < 0.05:
        out.append({"code": "small_selection_margin", "severity": "info",
                    "message": "The selected method beats naive by less than 5% on development origins; the naive method is nearly as good."})
    if holdout["selected"]["mae_gbp"] >= holdout["naive"]["mae_gbp"]:
        out.append({"code": "final_window_worse_than_naive", "severity": "warning",
                    "message": "On the final window the selected method did not beat the naive benchmark; treat the projection as weak."})
    return out


def backtest(weeks):
    if len(weeks) < MIN_WEEKS:
        return {
            "status": "insufficient_data",
            "reason": f"At least {MIN_WEEKS} complete weeks are required for development origins and a final window.",
            "complete_weeks": len(weeks),
            "history": weeks,
        }
    if len(weeks) > MAX_WEEKS:
        raise ValueError(f"Forecast supports at most {MAX_WEEKS} complete weeks; select a shorter date range.")
    values = [w["pence"] for w in weeks]
    n = len(values)
    seasonal_available = n >= 2 * SEASON_WEEKS
    first_origin = SEASON_WEEKS + 1 if seasonal_available else FIRST_ORIGIN
    final_count = min(MAX_FINAL_ORIGINS, max(4, n // 5))
    dev_origins = list(range(first_origin, n - final_count))
    final_origins = list(range(n - final_count, n))
    naive_dev = _records(weeks, values, _BY_ID["naive"], dev_origins)
    scale = sum(abs(r["actual_pence"] - r["predicted_pence"]) for r in naive_dev) / len(naive_dev)
    candidates = {}
    for cid, description, fn in CANDIDATES:
        if cid == "seasonal_naive" and not seasonal_available:
            continue
        dev = _records(weeks, values, fn, dev_origins)
        candidates[cid] = {"description": description, "development": metrics(dev, scale), "records": dev}
    selected = min(candidates, key=lambda c: (candidates[c]["development"]["mae_gbp"], _ORDER[c]))
    # Final window: evaluated for every candidate AFTER selection; it never feeds back into the choice.
    for cid in candidates:
        candidates[cid]["final"] = metrics(_records(weeks, values, _BY_ID[cid], final_origins), scale)
    final_records = _records(weeks, values, _BY_ID[selected], final_origins)
    holdout = {
        "selected": candidates[selected]["final"],
        "naive": candidates["naive"]["final"],
        "records": final_records,
        "origins": final_count,
    }
    residuals = sorted(abs(r["actual_pence"] - r["predicted_pence"]) for r in candidates[selected]["records"])
    radii = {}
    for level in INTERVAL_LEVELS:
        radius = residuals[min(len(residuals) - 1, math.ceil(level * len(residuals)) - 1)]
        covered = sum(1 for r in final_records if abs(r["actual_pence"] - r["predicted_pence"]) <= radius)
        radii[str(level)] = {"radius_pence": radius, "final_window_coverage": covered / len(final_records)}
    point = _BY_ID[selected](values)
    next_week = (date.fromisoformat(weeks[-1]["period"]) + timedelta(days=7)).isoformat()
    naive_final = candidates["naive"]["final"]["mae_gbp"]
    leaderboard = sorted(
        (
            {
                "method": cid,
                "description": c["description"],
                "development_mae_gbp": c["development"]["mae_gbp"],
                "development_mase": c["development"]["mase"],
                "final_mae_gbp": c["final"]["mae_gbp"],
                "final_mase": c["final"]["mase"],
                "final_improvement_vs_naive": (1 - c["final"]["mae_gbp"] / naive_final) if naive_final else None,
                "selected": cid == selected,
            }
            for cid, c in candidates.items()
        ),
        key=lambda row: (row["development_mae_gbp"], _ORDER[row["method"]]),
    )
    result = {
        "status": "ready",
        "complete_weeks": n,
        "history": weeks,
        "selected": selected,
        "selected_description": candidates[selected]["description"],
        "candidates": candidates,
        "leaderboard": leaderboard,
        "holdout": holdout,
        "next": {
            "period": next_week,
            "pence": point,
            "lower_pence": max(0, point - radii["0.9"]["radius_pence"]),
            "upper_pence": point + radii["0.9"]["radius_pence"],
        },
        "uncertainty": {
            "method": "empirical envelope of development absolute errors of the selected method (80% and 90% quantiles); the 90% radius is the displayed band",
            "residual_count": len(residuals),
            "levels": radii,
            "calibrated": False,
            "note": "Final-window coverage is a descriptive check on a handful of points, not a calibration claim.",
        },
        "split": {
            "first_origin": first_origin,
            "development_origins": len(dev_origins),
            "holdout_origins": final_count,
            "selection_end_index": n - final_count - 1,
            "horizon_weeks": 1,
            "selection_rule": "lowest development MAE; ties resolve to the simpler (earlier registered) method",
            "final_window_rule": f"last min({MAX_FINAL_ORIGINS}, max(4, n // 5)) origins; evaluated after selection, never used for it",
            "mase_scale": "development naive one-step MAE",
        },
    }
    result["diagnostics"] = _diagnostics(weeks, values, seasonal_available, scale, selected, candidates, holdout)
    return result


def forecast(request, metadata, where, args, data_dir):
    start = max(
        date.fromisoformat(metadata["start"]),
        date.fromisoformat((request.get("filters") or {}).get("start", metadata["start"])),
    )
    end = min(
        date.fromisoformat(metadata["end"]),
        date.fromisoformat((request.get("filters") or {}).get("end", metadata["end"])),
    )
    first = start + timedelta(days=(-start.weekday()) % 7)
    last = end - timedelta(days=(end.weekday() + 1) % 7)
    weeks = []
    with duckdb.connect(str(data_dir / (metadata["id"] + ".duckdb")), read_only=True) as con:
        rows = con.execute(
            "SELECT order_date::VARCHAR, SUM(line_pence)::BIGINT FROM transactions" + where + " GROUP BY 1 ORDER BY 1",
            args,
        ).fetchall()
    observed = {date.fromisoformat(d): int(p) for d, p in rows}
    while first + timedelta(days=6) <= last:
        if len(weeks) >= MAX_WEEKS:
            raise ValueError(f"Select at most {MAX_WEEKS} complete weeks.")
        weeks.append({"period": first.isoformat(), "pence": sum(observed.get(first + timedelta(days=i), 0) for i in range(7))})
        first += timedelta(days=7)
    result = backtest(weeks)
    if not any(w["pence"] for w in weeks):
        result = {
            "status": "insufficient_data",
            "reason": "No positive gross sales in complete weeks of this scope.",
            "complete_weeks": len(weeks),
            "history": weeks,
        }
    final_count = result.get("split", {}).get("holdout_origins")
    result["notes"] = [
        "Positive invoice-line gross GBP; excludes returns/cancellations and is not net revenue or profit.",
        "Only complete Monday–Sunday weeks; boundary fragments excluded. Dates without observed rows count as zero; collection completeness is not established.",
        "One-step rolling origins use only earlier observations. The method is chosen on development origins; the final "
        + (f"{final_count} " if final_count else "")
        + "origins are evaluated afterwards and never select the method. When the naive method is best, it is selected.",
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
    result["output_sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True, allow_nan=False).encode()).hexdigest()
    return result


def scenario(baseline_pence, value):
    if not isinstance(value, dict) or set(value) - {"volume_pct", "price_pct", "budget_gbp"}:
        raise ValueError("Invalid scenario fields")
    clean = {}
    for key, lo, hi in [("volume_pct", -50, 100), ("price_pct", -50, 100), ("budget_gbp", 0, 1_000_000)]:
        v = value.get(key, 0)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
            raise ValueError("Scenario value outside allowed range")
        clean[key] = Decimal(str(v))
    base = Decimal(str(baseline_pence))
    money = lambda n: int(n.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    assumed = money(base * (1 + clean["volume_pct"] / 100) * (1 + clean["price_pct"] / 100))
    return {
        "assumptions": {k: float(v) for k, v in clean.items()},
        "baseline_pence": money(base),
        "assumed_gross_pence": assumed,
        "gross_delta_pence": assumed - money(base),
        "budget_pence": money(clean["budget_gbp"] * 100),
        "note": "User assumptions, not predicted causal effects. Price and volume vary independently; demand elasticity, margin, capacity, returns and campaign effectiveness are unknown. Budget is shown separately; gross delta is not profit or ROI.",
    }
