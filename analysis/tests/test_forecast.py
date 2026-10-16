"""Forecast protocol tests (weekly-gross-v2): registered baselines, development-only selection,
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
