import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from analysis.ml import experiment, split_indices, reject_partition_duplicates
from analysis.adapted.ml_preprocessing import FoldPreprocessor, log_mse_like_counts

DATA = Path(__file__).parents[1] / "data"


def request(name="wine"):
    csv = (DATA / (name + "-ml.csv")).read_text()
    f = pd.read_csv(DATA / (name + "-ml.csv"))
    target = f.columns[-1]
    return dict(
        csv=csv,
        target=target,
        features=f.columns[:-1].tolist(),
        task="classification" if name == "wine" else "regression",
        split="random",
        features_available=True,
        decision_context="Bir gözlem için ölçüm anında bilinen özellikler; bağımsız açık veri örneği.",
    )


def test_preprocessor_is_train_only_unknown_categories_and_no_mutation():
    train = pd.DataFrame({"n": ["0", "1", "1000"], "cat": ["a", "b", "a"]})
    original = train.copy(deep=True)
    p = FoldPreprocessor().fit(train)
    scaler = p.transformer_.named_transformers_["numeric"].named_steps["scale"]
    before = scaler.data_max_.copy()
    transformed = p.transform(pd.DataFrame({"n": ["1000000"], "cat": ["UNSEEN"]}))
    np.testing.assert_array_equal(before, scaler.data_max_)
    assert transformed.shape[1] == 3 and transformed[0, 1:].sum() == 0
    pd.testing.assert_frame_equal(train, original)
    assert p.log_columns_ == ["n"]


def test_classifier_real_holdout_and_deterministic_selection():
    a = experiment(request())
    b = experiment(request())
    assert a["sha256"] == b["sha256"]
    assert a["split"]["train_rows"] == 142 and a["split"]["holdout_rows"] == 36
    assert set(a["split"]["train_indices"]).isdisjoint(a["split"]["holdout_indices"])
    assert a["holdout"]["macro_f1"] > 0.8
    assert sum(map(sum, a["holdout"]["confusion_matrix"])) == 36
    assert len(a["candidates"]) == 3
    assert a["baseline"]["macro_f1"] < a["holdout"]["macro_f1"]


def test_no_pipeline_fit_sees_holdout(monkeypatch):
    seen = []
    original = FoldPreprocessor.fit

    def spy(self, X, y=None):
        seen.extend(X.index.tolist())
        return original(self, X, y)

    monkeypatch.setattr(FoldPreprocessor, "fit", spy)
    card = experiment(request())
    assert not set(seen) & set(card["split"]["holdout_indices"])
    assert set(seen) == set(card["split"]["train_indices"])


def test_regressor_original_scale_errors_and_optional_rmsle():
    card = experiment(request("diabetes"))
    assert card["split"]["holdout_rows"] == 89
    assert card["holdout"]["mae"] > 0 and card["holdout"]["rmse"] > 0
    assert card["holdout"]["rmsle"] is None or card["holdout"]["rmsle"] > 0
    assert log_mse_like_counts([0, 3], [0, 3]) == 0
    for true, pred in [([-1], [0]), ([1], [np.inf]), ([2], [-1])]:
        with pytest.raises(ValueError):
            log_mse_like_counts(true, pred)


def test_numeric_smote_in_fold_runs():
    card = experiment(request() | {"smote": True})
    assert "smote_forest" in [c["model"] for c in card["candidates"]]
    assert card["split"]["holdout_rows"] == 36


def test_group_and_equal_timestamp_boundaries():
    f = pd.DataFrame(
        {
            "g": [str(i // 8) for i in range(160)],
            "day": pd.date_range("2025-01-01", periods=20)
            .repeat(8)
            .strftime("%Y-%m-%d"),
        }
    )
    y = np.array([str(i % 2) for i in range(160)])
    for strategy, key in [("group", "g"), ("time", "day")]:
        train, test, folds = split_indices(f, y, "classification", strategy, key)
        assert set(f.iloc[train][key]).isdisjoint(f.iloc[test][key])
        for a, b in folds:
            assert set(f.iloc[train[a]][key]).isdisjoint(f.iloc[train[b]][key])
            if strategy == "time":
                assert f.iloc[train[a]].day.max() < f.iloc[train[b]].day.min()


def test_exact_feature_duplicates_across_partitions_refused():
    with pytest.raises(ValueError, match="Aynı özellik"):
        reject_partition_duplicates(
            pd.DataFrame({"x": ["a", "a", "b"]}), np.array([0, 2]), np.array([1]), []
        )


@pytest.mark.parametrize(
    "override",
    [
        {"features_available": False},
        {"decision_context": "x"},
        {"target": "missing"},
        {"features": ["cultivar"]},
        {"features": ["alcohol", "alcohol"]},
        {"split": "unknown"},
        {"split": "group", "split_key": "alcohol"},
        {"task": "forecast"},
        {"smote": "true"},
    ],
)
def test_invalid_contracts_refused(override):
    with pytest.raises(ValueError):
        experiment(request() | override)


def test_smote_categorical_refused_and_target_copy_refused():
    r = request()
    f = pd.read_csv(DATA / "wine-ml.csv", dtype=str)
    f["category"] = ["a" if i % 2 else "b" for i in range(len(f))]
    with pytest.raises(ValueError, match="SMOTE"):
        experiment(
            r
            | {
                "csv": f.to_csv(index=False),
                "features": ["category"] + r["features"],
                "smote": True,
            }
        )
    f["copied"] = f.cultivar
    with pytest.raises(ValueError, match="kopyası"):
        experiment(r | {"csv": f.to_csv(index=False), "features": ["copied"]})
