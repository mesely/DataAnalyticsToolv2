"""One-week gross-sales benchmark (weekly-gross-v3).

Registered baselines (naive, seasonal naive, drift, moving means, exponential smoothing, damped Holt) are
compared by one-step rolling-origin error on DEVELOPMENT origins only; the method is selected there.
A FINAL window (the last origins) is evaluated for every candidate afterwards and never influences the
selection. If the naive method wins, it is selected and the product says so.

The residual band (v3) registers two scalings — absolute pence and relative-to-forecast — and picks the one
whose ROLLING development coverage is closest to nominal; each rolling radius uses only earlier development
residuals. The final window never informs that choice; its coverage is reported descriptively only.
"""

from __future__ import annotations
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import hashlib, json, math, statistics
import duckdb
from analysis.fingerprint import fingerprint

VERSION = "weekly-gross-v3"
MIN_WEEKS, MAX_WEEKS = 16, 260
FIRST_ORIGIN = 8  # every registered candidate needs at most 8 prior observations
SEASON_WEEKS = 52
MAX_FINAL_ORIGINS = 12
INTERVAL_LEVELS = (0.8, 0.9)
MIN_INTERVAL_RESIDUALS = 8  # rolling coverage is evaluated only once this many earlier residuals exist
INTERVAL_SCALINGS = ("absolute", "relative")


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


def _diagnostics(weeks, values, seasonal_available, scale, selected, candidates, holdout, uncertainty=None):
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
    cov = (uncertainty or {}).get("levels", {}).get("0.9", {}).get("development_rolling_coverage")
    if cov is not None and cov < 0.8:
        out.append({"code": "band_undercovers_development", "severity": "warning",
                    "message": f"The 90% band covered only {cov:.0%} of evaluated development origins when built from earlier residuals; treat the displayed range as optimistic."})
    if holdout["selected"]["mae_gbp"] >= holdout["naive"]["mae_gbp"]:
        out.append({"code": "final_window_worse_than_naive", "severity": "warning",
                    "message": "On the final window the selected method did not beat the naive benchmark; treat the projection as weak."})
    return out


def _quantile_radius(sorted_values, level):
    """Split-conformal finite-sample quantile: the ceil((n+1)·level)-th smallest residual. When that index
    exceeds n the largest residual is used, which is a truncation that may still under-cover."""
    n = len(sorted_values)
    return sorted_values[min(n - 1, math.ceil(level * (n + 1)) - 1)]


def _scaled_errors(records, scaling):
    """Absolute error per record, optionally divided by the forecast. Returns None when a relative scaling is
    undefined (a non-positive forecast), so that scaling is reported as unavailable instead of silently used."""
    out = []
    for r in records:
        e = abs(r["actual_pence"] - r["predicted_pence"])
        if scaling == "absolute":
            out.append(e)
        elif r["predicted_pence"] > 0:
            out.append(e / r["predicted_pence"])
        else:
            return None
    return out


def _rolling_coverage(records, scaled, scaling, level):
    """Share of development origins whose actual lies inside a band whose radius was computed from EARLIER
    development residuals only. Mirrors how the displayed band will be used one step ahead."""
    covered = evaluated = 0
    for k in range(MIN_INTERVAL_RESIDUALS, len(records)):
        q = _quantile_radius(sorted(scaled[:k]), level)
        radius = q if scaling == "absolute" else q * records[k]["predicted_pence"]
        if abs(records[k]["actual_pence"] - records[k]["predicted_pence"]) <= radius:
            covered += 1
        evaluated += 1
    return (covered / evaluated if evaluated else None), evaluated


def interval(dev_records, final_records, point):
    """Band construction with a development-only scaling choice. Final-window coverage is descriptive."""
    scalings = {}
    for scaling in INTERVAL_SCALINGS:
        scaled = _scaled_errors(dev_records, scaling)
        if scaled is None:
            scalings[scaling] = None
            continue
        per_level = {}
        for level in INTERVAL_LEVELS:
            coverage, evaluated = _rolling_coverage(dev_records, scaled, scaling, level)
            per_level[str(level)] = {"development_rolling_coverage": coverage, "development_rolling_n": evaluated}
        scalings[scaling] = per_level
    def distance(scaling):
        rows = scalings[scaling]
        if rows is None or any(r["development_rolling_coverage"] is None for r in rows.values()):
            return math.inf
        return sum(abs(r["development_rolling_coverage"] - float(level)) for level, r in rows.items())
    # Lowest total distance to nominal on development; ties (and no evaluable origins) resolve to absolute.
    chosen = min(INTERVAL_SCALINGS, key=lambda s: (distance(s), INTERVAL_SCALINGS.index(s)))
    scaled_all = sorted(_scaled_errors(dev_records, chosen))
    levels = {}
    for level in INTERVAL_LEVELS:
        q = _quantile_radius(scaled_all, level)
        radius_for = (lambda p: q) if chosen == "absolute" else (lambda p: q * p)
        covered = sum(1 for r in final_records if abs(r["actual_pence"] - r["predicted_pence"]) <= radius_for(r["predicted_pence"]))
        levels[str(level)] = {
            "radius_pence": int(round(radius_for(point))),
            "quantile": q,
            "final_window_coverage": covered / len(final_records) if final_records else None,
            **scalings[chosen][str(level)],
        }
    return {
        "method": "empirical envelope of development errors of the selected method (80% and 90% quantiles); the 90% radius is the displayed band",
        "scaling": chosen,
        "scaling_rule": "absolute pence or relative to the forecast; chosen by rolling development coverage closest to nominal (radius from earlier development residuals only); ties resolve to absolute; the final window never informs the choice",
        "quantile_rule": "finite-sample split-conformal index ceil((n+1)·level), truncated to the largest residual when it exceeds n",
        "residual_count": len(dev_records),
        "levels": levels,
        "scalings": scalings,
        "calibrated": False,
        "note": "Final-window coverage is a descriptive check on a handful of points, not a calibration claim. Development rolling coverage is the honest in-sample check of the band's construction.",
    }


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
    point = _BY_ID[selected](values)
    uncertainty = interval(candidates[selected]["records"], final_records, point)
    radii = uncertainty["levels"]
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
        "uncertainty": uncertainty,
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
    result["diagnostics"] = _diagnostics(weeks, values, seasonal_available, scale, selected, candidates, holdout, uncertainty)
    return result


SLICE_COUNTRIES = 3


def _country_slices(metadata, where, args, data_dir, *, first_week, n_weeks, result):
    """Error slices: the aggregate's selected method and naive, re-run on the leading countries' own weekly
    series over the SAME final origins. Diagnostic only — slices never change the aggregate selection.
    Labels stay in this result (shown to the user) and never enter diagnostics text or model packets."""
    start = date.fromisoformat(first_week)
    with duckdb.connect(str(data_dir / (metadata["id"] + ".duckdb")), read_only=True) as con:
        leaders = [r[0] for r in con.execute(
            "SELECT country FROM transactions" + where + " GROUP BY 1 ORDER BY SUM(line_pence) DESC, country LIMIT " + str(SLICE_COUNTRIES), args
        ).fetchall()]
        if not leaders:
            return []
        rows = con.execute(
            "SELECT country, order_date::VARCHAR, SUM(line_pence)::BIGINT FROM transactions" + where
            + (" AND" if where else " WHERE") + " country IN (" + ",".join("?" * len(leaders)) + ") GROUP BY 1, 2",
            list(args) + leaders,
        ).fetchall()
    observed = {}
    for country, d, p in rows:
        observed.setdefault(country, {})[date.fromisoformat(d)] = int(p)
    final_origins = list(range(n_weeks - result["split"]["holdout_origins"], n_weeks))
    dev_origins = list(range(result["split"]["first_origin"], n_weeks - result["split"]["holdout_origins"]))
    out = []
    for country in leaders:
        days = observed.get(country, {})
        weeks = [{"period": (start + timedelta(days=7 * i)).isoformat(),
                  "pence": sum(days.get(start + timedelta(days=7 * i + k), 0) for k in range(7))} for i in range(n_weeks)]
        values = [w["pence"] for w in weeks]
        if n_weeks < MIN_WEEKS or not any(values):
            out.append({"country": country, "status": "insufficient_data", "complete_weeks": n_weeks})
            continue
        naive_dev = _records(weeks, values, _BY_ID["naive"], dev_origins)
        scale = sum(abs(r["actual_pence"] - r["predicted_pence"]) for r in naive_dev) / len(naive_dev)
        selected = metrics(_records(weeks, values, _BY_ID[result["selected"]], final_origins), scale)
        naive = metrics(_records(weeks, values, _BY_ID["naive"], final_origins), scale)
        out.append({
            "country": country, "status": "ready", "gross_pence": sum(values),
            "final": {"selected": selected, "naive": naive},
            "selected_beats_naive_final": selected["mae_gbp"] < naive["mae_gbp"],
            "zero_weeks": sum(1 for v in values if v == 0),
        })
    return out


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
    if result.get("status") == "ready":
        result["slices"] = _country_slices(metadata, where, args, data_dir, first_week=weeks[0]["period"], n_weeks=len(weeks), result=result)
        disagree = [x for x in result["slices"] if x["status"] == "ready" and not x["selected_beats_naive_final"]]
        if disagree:
            result["diagnostics"].append({
                "code": "slice_disagreement", "severity": "warning",
                "message": f"In {len(disagree)} of {sum(1 for x in result['slices'] if x['status'] == 'ready')} leading-country slices the aggregate's selected method did not beat naive on the final window; the aggregate conclusion does not transfer to every market.",
            })
    final_count = result.get("split", {}).get("holdout_origins")
    result["notes"] = [
        "Positive invoice-line gross GBP; excludes returns/cancellations and is not net revenue or profit.",
        "Only complete Monday–Sunday weeks; boundary fragments excluded. Dates without observed rows count as zero; collection completeness is not established.",
        "One-step rolling origins use only earlier observations. The method is chosen on development origins; the final "
        + (f"{final_count} " if final_count else "")
        + "origins are evaluated afterwards and never select the method. When the naive method is best, it is selected.",
        "Residual envelope is empirical, not a guaranteed or calibrated prediction interval. Historical records may not represent future trading.",
        "Country slices re-run the aggregate's selected method and naive on each leading country's own weeks over the same final origins; they are diagnostic and never change the selection.",
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
