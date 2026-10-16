"""Forecast protocol tests (weekly-gross-v3): registered baselines, development-only selection,
final window isolation, metrics oracles, seasonal availability and diagnostics."""

from copy import deepcopy
from datetime import date, timedelta
import math, random
import pytest
from analysis.forecast import backtest, metrics, predict, CANDIDATES, SEASON_WEEKS


def series(values, start=date(2024, 1, 1)):
    return [{"period": (start + timedelta(days=7 * i)).isoformat(), "pence": int(v)} for i, v in enumerate(values)]


def test_linear_trend_selects_drift_on_development_and_reports_naive_separately():
    r = backtest(series(10000 + 100 * i for i in range(24)))
    assert r["selected"] == "drift"
    assert r["holdout"]["selected"]["mae_gbp"] == 0 and r["holdout"]["naive"]["mae_gbp"] == 1
    assert r["next"]["pence"] == 12400 and r["next"]["lower_pence"] == r["next"]["upper_pence"] == 12400
    assert r["split"] == {
        "first_origin": 8, "development_origins": 12, "holdout_origins": 4, "selection_end_index": 19,
        "horizon_weeks": 1, "selection_rule": r["split"]["selection_rule"],
        "final_window_rule": r["split"]["final_window_rule"], "mase_scale": "development naive one-step MAE",
    }
    for c in r["candidates"].values():
        assert len(c["records"]) == 12 and all(x["train_end_index"] < 20 for x in c["records"])
        assert c["final"]["n"] == 4
    assert r["leaderboard"][0]["method"] == "drift" and r["leaderboard"][0]["selected"]
    assert r["uncertainty"]["calibrated"] is False
    assert any(d["code"] == "seasonal_naive_unavailable" for d in r["diagnostics"])


def test_noisy_flat_series_prefers_a_simple_method_over_trend_models():
    rng = random.Random(7)
    r = backtest(series(50000 + rng.randint(-500, 500) for _ in range(40)))
    assert r["selected"] in {"naive", "mean2", "mean4", "mean8", "ses_0.2", "ses_0.5", "ses_0.8"}
    assert not r["selected"].startswith("holt")


def test_final_window_never_changes_selection_or_development_numbers():
    original = series(20000 + (i % 5) * 300 for i in range(30))
    changed = deepcopy(original)
    for w in changed[-6:]:  # 30 // 5 = 6 final origins
        w["pence"] *= 50
    a, b = backtest(original), backtest(changed)
    assert a["split"]["holdout_origins"] == 6
    assert a["selected"] == b["selected"]
    for cid in a["candidates"]:
        assert a["candidates"][cid]["development"] == b["candidates"][cid]["development"]
        assert a["candidates"][cid]["records"] == b["candidates"][cid]["records"]
    assert a["holdout"] != b["holdout"]


def test_ties_resolve_to_the_simpler_registered_method():
    r = backtest(series([30000] * 20))
    assert r["selected"] == "naive"  # every candidate has zero error; naive is registered first


def test_metrics_oracle_smape_mase_bias_and_zero_handling():
    rec = [
        {"actual_pence": 1000, "predicted_pence": 900},
        {"actual_pence": 0, "predicted_pence": 0},
        {"actual_pence": 500, "predicted_pence": 700},
    ]
    m = metrics(rec, scale_pence=50)
    assert m["mae_gbp"] == pytest.approx((100 + 0 + 200) / 3 / 100)
    assert m["bias_gbp"] == pytest.approx((100 + 0 - 200) / 3 / 100)
    assert m["smape"] == pytest.approx((2 * 100 / 1900 + 2 * 200 / 1200) / 2)  # the all-zero pair is skipped
    assert m["mase"] == pytest.approx(100 / 50)
    assert m["wape"] == pytest.approx(300 / 1500)
    assert "mape" not in m


def test_seasonal_naive_registered_only_with_two_seasons_and_wins_on_a_seasonal_series():
    short = backtest(series(10000 + 50 * (i % 13) for i in range(60)))
    assert "seasonal_naive" not in short["candidates"]
    pattern = [10000 + 3000 * math.sin(2 * math.pi * k / SEASON_WEEKS) for k in range(SEASON_WEEKS)]
    long = backtest(series(pattern[i % SEASON_WEEKS] + 100 * (i % 3) for i in range(130)))
    assert "seasonal_naive" in long["candidates"]
    assert long["split"]["first_origin"] == SEASON_WEEKS + 1
    assert long["selected"] == "seasonal_naive"
    assert not any(d["code"] == "seasonal_naive_unavailable" for d in long["diagnostics"])


def test_diagnostics_flag_zero_weeks_outliers_and_level_shift():
    spiky = [40000] * 24
    spiky[5] = 0
    spiky[10] = 400000
    codes = {d["code"] for d in backtest(series(spiky))["diagnostics"]}
    assert {"zero_weeks", "outlier_weeks"} <= codes
    shifted = [40000] * 16 + [90000] * 8
    codes = {d["code"] for d in backtest(series(shifted))["diagnostics"]}
    assert "possible_level_shift" in codes and "zero_weeks" not in codes


def test_interval_levels_cover_final_window_descriptively():
    r = backtest(series(10000 + 100 * i + (50 if i % 2 else -50) for i in range(40)))
    levels = r["uncertainty"]["levels"]
    assert set(levels) == {"0.8", "0.9"}
    for v in levels.values():
        assert 0 <= v["final_window_coverage"] <= 1 and v["radius_pence"] >= 0
    assert r["next"]["upper_pence"] - r["next"]["pence"] == levels["0.9"]["radius_pence"]


def test_predict_registry_and_seasonal_guard():
    hist = [float(v) for v in range(1, 20)]
    for cid, _, _ in CANDIDATES:
        if cid == "seasonal_naive":
            with pytest.raises(ValueError):
                predict(hist, cid)
        else:
            assert math.isfinite(predict(hist, cid))
    with pytest.raises(ValueError):
        predict(hist, "lstm")


def test_interval_quantile_is_finite_sample_conformal_index():
    from analysis.forecast import _quantile_radius
    values = sorted([5, 1, 4, 2, 3, 9, 7, 8, 6, 10])
    # ceil((10+1)*0.8) = 9 -> 9th smallest = 9 ; ceil(11*0.9) = 10 -> 10th smallest = 10
    assert _quantile_radius(values, 0.8) == 9 and _quantile_radius(values, 0.9) == 10
    assert _quantile_radius([3], 0.9) == 3  # index beyond n truncates to the largest residual


def test_rolling_coverage_uses_only_earlier_residuals_oracle():
    from analysis.forecast import _rolling_coverage, _scaled_errors, MIN_INTERVAL_RESIDUALS
    # errors grow one unit per origin: 1,2,...; a band from earlier residuals can never cover the next one
    rec = [{"actual_pence": 1000 + i, "predicted_pence": 1000} for i in range(1, 15)]
    cov, n = _rolling_coverage(rec, _scaled_errors(rec, "absolute"), "absolute", 0.9)
    assert n == len(rec) - MIN_INTERVAL_RESIDUALS and cov == 0
    # constant errors are always covered once eight residuals exist
    rec = [{"actual_pence": 1050, "predicted_pence": 1000} for _ in range(14)]
    cov, n = _rolling_coverage(rec, _scaled_errors(rec, "absolute"), "absolute", 0.8)
    assert cov == 1 and n == 6
    # relative scaling is undefined for a non-positive forecast
    assert _scaled_errors([{"actual_pence": 5, "predicted_pence": 0}], "relative") is None


def test_relative_scaling_is_chosen_on_development_when_errors_grow_with_level():
    # Level grows 4% a week while the noise stays a fixed share of the level: relative errors are
    # stationary, absolute errors are not, so rolling development coverage favours the relative band.
    rng = random.Random(5)
    vals = [10000 * (1.04 ** i) * (1 + rng.uniform(-0.2, 0.2)) for i in range(60)]
    r = backtest(series(vals))
    u = r["uncertainty"]
    assert u["scaling"] == "relative" and u["calibrated"] is False
    assert set(u["scalings"]) == {"absolute", "relative"}
    assert u["levels"]["0.9"]["development_rolling_n"] == r["split"]["development_origins"] - 8
    assert r["next"]["upper_pence"] - r["next"]["pence"] == u["levels"]["0.9"]["radius_pence"]


def test_final_window_cannot_change_the_band_scaling_or_development_coverage():
    original = series(20000 + (i % 7) * 500 for i in range(40))
    changed = deepcopy(original)
    for w in changed[-8:]:  # 40 // 5 = 8 final origins
        w["pence"] = w["pence"] * 3
    a, b = backtest(original)["uncertainty"], backtest(changed)["uncertainty"]
    assert a["scaling"] == b["scaling"] and a["scalings"] == b["scalings"]
    for level in a["levels"]:
        assert a["levels"][level]["development_rolling_coverage"] == b["levels"][level]["development_rolling_coverage"]
        assert a["levels"][level]["radius_pence"] == b["levels"][level]["radius_pence"]
    assert any(a["levels"][l]["final_window_coverage"] != b["levels"][l]["final_window_coverage"] for l in a["levels"])


def test_band_undercoverage_diagnostic_fires_on_growing_errors():
    rng = random.Random(3)
    vals = [20000 + rng.randint(-200, 200) + (0 if i < 24 else rng.choice([-9000, 9000])) for i in range(40)]
    codes = {d["code"] for d in backtest(series(vals))["diagnostics"]}
    assert "band_undercovers_development" in codes


def test_nonnegative_domain_applies_before_evaluation_and_relative_radius():
    rng = random.Random(5)
    vals = [int(10000 * 1.04**i * (1 + rng.uniform(-.2, .2))) for i in range(60)]
    original = backtest(series(vals))
    vals[-12:] = [0] * 12
    r = backtest(series(vals))
    assert r["selected"] == original["selected"] == "holt_damped_0.6_0.1"
    assert r["uncertainty"]["scaling"] == original["uncertainty"]["scaling"] == "relative"
    assert r["uncertainty"]["scalings"] == original["uncertainty"]["scalings"]
    assert r["next"]["pence"] == 0
    assert r["next"]["lower_pence"] == r["next"]["upper_pence"] == 0
    assert all(x["predicted_pence"] >= 0 for x in r["holdout"]["records"])
    assert all(x["predicted_pence"] >= 0 for c in r["candidates"].values() for x in c["records"])
    assert all(x["radius_pence"] >= 0 for x in r["uncertainty"]["levels"].values())
    assert "relative_band_collapsed" in {d["code"] for d in r["diagnostics"]}
    assert predict([100, 20, 0], "drift") == 0


def test_interval_width_oracle_and_final_undercoverage_warning():
    from analysis.forecast import interval
    dev = [{"actual_pence": 100, "predicted_pence": 200} for _ in range(12)]
    final = [{"actual_pence": 1000, "predicted_pence": 50} for _ in range(4)]
    u = interval(dev, final, 50)
    for v in u["levels"].values():
        assert v["development_mean_width_gbp"] == 2  # [100,300]
        assert v["final_mean_width_gbp"] == 1.5  # [0,150], clipped at zero
        assert v["final_window_coverage"] == 0
    r = backtest(series([10000] * 24 + [100000 * (i + 1) for i in range(6)]))
    assert "band_undercovers_final" in {d["code"] for d in r["diagnostics"]}


def test_negative_gross_history_is_rejected():
    with pytest.raises(ValueError, match="nonnegative"):
        backtest(series([100] * 19 + [-1]))


def _month_series():
    rng = random.Random(11)
    vals = [20000 + 150 * i + rng.randint(-1500, 1500) for i in range(40)]
    for i in range(34, 40):  # a late ramp the trailing mean lags
        vals[i] += 4000 * (i - 33)
    return series(vals, start=date(2024, 1, 1))


def test_period_slices_partition_records_and_match_independent_oracles():
    r = backtest(_month_series())
    sl = r["period_slices"]
    dev = r["candidates"][r["selected"]]["records"]
    fin = r["holdout"]["records"]
    assert sum(x["n"] for x in sl if x["phase"] == "development") == len(dev)
    assert sum(x["n"] for x in sl if x["phase"] == "final") == len(fin) == r["split"]["holdout_origins"]
    naive_dev = {x["target"]: x for x in r["candidates"]["naive"]["records"]}
    for x in sl:
        recs = [d for d in (dev if x["phase"] == "development" else fin) if d["target"][:7] == x["month"]]
        assert x["n"] == len(recs)
        assert x["selected_mae_gbp"] == pytest.approx(sum(abs(d["actual_pence"] - d["predicted_pence"]) for d in recs) / len(recs) / 100)
        if x["phase"] == "development":
            nv = [naive_dev[d["target"]] for d in recs]
            assert x["naive_mae_gbp"] == pytest.approx(sum(abs(d["actual_pence"] - d["predicted_pence"]) for d in nv) / len(nv) / 100)
    # band counts reconcile with the aggregate uncertainty numbers
    lvl = r["uncertainty"]["levels"]["0.9"]
    dev_band = [x for x in sl if x["phase"] == "development"]
    assert sum(x["band_n"] for x in dev_band) == lvl["development_rolling_n"]
    assert sum(x["band_covered"] for x in dev_band) == pytest.approx(lvl["development_rolling_coverage"] * lvl["development_rolling_n"])
    fin_band = [x for x in sl if x["phase"] == "final"]
    assert sum(x["band_n"] for x in fin_band) == len(fin)
    assert sum(x["band_covered"] for x in fin_band) == pytest.approx(lvl["final_window_coverage"] * len(fin))


def test_period_slices_are_post_selection_and_final_changes_leave_development_untouched():
    a = backtest(_month_series())
    changed = _month_series()
    for w in changed[-8:]:  # 40 // 5 = 8 final origins
        w["pence"] *= 3
    b = backtest(changed)
    assert a["selected"] == b["selected"]
    dev = lambda r: [x for x in r["period_slices"] if x["phase"] == "development"]
    assert dev(a) == dev(b)
    assert [x for x in a["period_slices"] if x["phase"] == "final"] != [x for x in b["period_slices"] if x["phase"] == "final"]


def test_final_month_worse_than_naive_diagnostic_names_months_not_labels():
    vals = [30000 + (i % 4) * 200 for i in range(40)]
    for i in range(32, 40):  # final window: a steady climb, where last-week naive beats any trailing mean
        vals[i] = 30000 + 5000 * (i - 31)
    r = backtest(series(vals, start=date(2024, 1, 1)))
    if r["selected"] == "naive":
        pytest.skip("naive selected on development; the diagnostic only applies to other methods")
    d = [x for x in r["diagnostics"] if x["code"] == "final_month_worse_than_naive"]
    assert d and all(m["month"] in d[0]["message"] for m in r["period_slices"] if m["phase"] == "final" and m["n"] >= 2 and not m["selected_beats_naive"])


def test_every_diagnostic_carries_params_and_a_turkish_template():
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    source = (root / "analysis/forecast.py").read_text()
    codes = set(re.findall(r'"code": "([a-z_]+)"', source))
    ui = (root / "core/web/src/workbench/DecisionStudio.tsx").read_text()
    missing = sorted(c for c in codes if f'case "{c}":' not in ui)
    assert not missing, f"diagnostic codes without a Turkish template: {missing}"
    spiky = [40000] * 24
    spiky[5], spiky[10] = 0, 400000
    for d in backtest(series(spiky))["diagnostics"]:
        assert isinstance(d.get("params"), dict) and d["message"], d["code"]
