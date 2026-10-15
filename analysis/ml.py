"""Local, bounded model comparison; held-out observations never select a model."""

from __future__ import annotations
import hashlib
import json
import re
import time
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    confusion_matrix,
    recall_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import (
    train_test_split,
    StratifiedKFold,
    KFold,
    GroupShuffleSplit,
    GroupKFold,
    TimeSeriesSplit,
)
from sklearn.pipeline import Pipeline
from analysis.preparation import read_csv, column_type
from analysis.adapted.ml_preprocessing import FoldPreprocessor, log_mse_like_counts
from analysis.fingerprint import fingerprint

VERSION = "ml-experiment-v1"
SEED = 47


def split_indices(frame, y, task, strategy, key):
    indices = np.arange(len(frame))
    if strategy == "random":
        train, test = train_test_split(
            indices,
            test_size=0.2,
            random_state=SEED,
            stratify=y if task == "classification" else None,
        )
        cv = (
            StratifiedKFold(3, shuffle=True, random_state=SEED)
            if task == "classification"
            else KFold(3, shuffle=True, random_state=SEED)
        )
        folds = list(cv.split(train, y[train]))
    elif strategy == "group":
        if (
            key not in frame
            or frame[key].str.strip().eq("").any()
            or frame[key].nunique() < 10
        ):
            raise ValueError("Grup ayrımı için en az 10 dolu grup gerekli.")
        groups = frame[key].values
        train, test = next(
            GroupShuffleSplit(1, test_size=0.2, random_state=SEED).split(
                indices, y, groups
            )
        )
        folds = list(GroupKFold(3).split(train, y[train], groups[train]))
    elif strategy == "time":
        if key not in frame or not frame[key].str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
            raise ValueError("Zaman ayrımı için YYYY-MM-DD tarih sütunu gerekli.")
        dates = pd.to_datetime(frame[key], format="%Y-%m-%d", errors="coerce")
        if dates.isna().any() or dates.nunique() < 10:
            raise ValueError("En az 10 farklı geçerli tarih gerekli.")
        unique = np.sort(dates.unique())
        cutoff = unique[int(len(unique) * 0.8)]
        train, test = (
            indices[(dates < cutoff).values],
            indices[(dates >= cutoff).values],
        )
        devdates = dates.iloc[train].to_numpy()
        unique_dev = np.sort(np.unique(devdates))
        folds = []
        for a, b in TimeSeriesSplit(3).split(unique_dev):
            folds.append(
                (
                    np.flatnonzero(np.isin(devdates, unique_dev[a])),
                    np.flatnonzero(np.isin(devdates, unique_dev[b])),
                )
            )
    else:
        raise ValueError("Ayrım random, group veya time olmalı.")
    if len(train) < 60 or len(test) < 20:
        raise ValueError("Ayrım sonrası en az 60 eğitim / 20 test gözlemi gerekiyor.")
    if task == "classification":
        classes = set(y[train])
        if (
            len(classes) < 2
            or not set(y[test]).issubset(classes)
            or any(set(y[train[a]]) != classes for a, _ in folds)
        ):
            raise ValueError(
                "Eğitim foldlarında bütün sınıflar bulunmalı; daha çok veri veya uygun bir ayrım seçin."
            )
    return np.asarray(train), np.asarray(test), folds


def reject_partition_duplicates(X, train, test, folds):
    # Hash is a partition check, not a privacy/uniqueness guarantee. Values never
    # leave this process; only split indices and a digest enter the model card.
    hashes = pd.util.hash_pandas_object(X, index=False).to_numpy()
    partitions = [(train, test)] + [(train[a], train[b]) for a, b in folds]
    if any(set(hashes[a]) & set(hashes[b]) for a, b in partitions):
        raise ValueError(
            "Aynı özellik satırı eğitim ve doğrulama/test tarafında bulundu. Tekrarları veya grup ayrımını düzeltin."
        )


def candidate_models(task, smote):
    if task == "classification":
        choices = {
            "dummy": DummyClassifier(strategy="most_frequent"),
            "random_forest": RandomForestClassifier(
                n_estimators=64,
                max_depth=8,
                min_samples_leaf=2,
                class_weight="balanced",
                random_state=SEED,
                n_jobs=1,
            ),
            "logistic": LogisticRegression(
                max_iter=400, class_weight="balanced", random_state=SEED
            ),
        }
    else:
        choices = {
            "dummy": DummyRegressor(strategy="median"),
            "random_forest": RandomForestRegressor(
                n_estimators=64,
                max_depth=8,
                min_samples_leaf=2,
                random_state=SEED,
                n_jobs=1,
            ),
            "ridge": Ridge(alpha=1),
        }
    pipelines = {
        name: Pipeline([("prepare", FoldPreprocessor()), ("model", model)])
        for name, model in choices.items()
    }
    if smote:
        from imblearn.pipeline import Pipeline as ImbPipeline
        from imblearn.over_sampling import SMOTE

        pipelines["smote_forest"] = ImbPipeline(
            [
                ("prepare", FoldPreprocessor()),
                ("resample", SMOTE(k_neighbors=2, random_state=SEED)),
                (
                    "model",
                    clone(choices["random_forest"]).set_params(class_weight=None),
                ),
            ]
        )
    return pipelines


def metrics(task, truth, prediction, labels=None):
    if task == "classification":
        label_names = labels
        labels = list(range(len(label_names)))
        return {
            "macro_f1": float(
                f1_score(
                    truth, prediction, labels=labels, average="macro", zero_division=0
                )
            ),
            "balanced_accuracy": float(balanced_accuracy_score(truth, prediction)),
            "accuracy": float(accuracy_score(truth, prediction)),
            "confusion_matrix": confusion_matrix(
                truth, prediction, labels=labels
            ).tolist(),
            "per_class": [
                {
                    "label": label_names[label],
                    "support": int(np.sum(truth == label)),
                    "recall": float(value) if np.any(truth == label) else None,
                }
                for label, value in zip(
                    labels,
                    recall_score(
                        truth, prediction, labels=labels, average=None, zero_division=0
                    ),
                )
            ],
        }
    mse = float(mean_squared_error(truth, prediction))
    r2 = (
        float(r2_score(truth, prediction, force_finite=False))
        if np.var(truth) > 0
        else None
    )
    rmsle = (
        float(np.sqrt(log_mse_like_counts(truth, prediction)))
        if np.min(truth) >= 0 and np.min(prediction) >= 0
        else None
    )
    return {
        "mae": float(mean_absolute_error(truth, prediction)),
        "rmse": float(np.sqrt(mse)),
        "r2": r2,
        "rmsle": rmsle,
    }


def experiment(request):
    started = time.monotonic()
    frame, _ = read_csv(request.get("csv"))
    if not 100 <= len(frame) <= 3000:
        raise ValueError("Model deneyi 100–3.000 satır gerektirir.")
    target = request.get("target")
    features = request.get("features")
    task = request.get("task")
    strategy = request.get("split")
    key = request.get("split_key", "")
    context = request.get("decision_context", "")
    if (
        not isinstance(context, str)
        or not 12 <= len(context.strip()) <= 500
        or request.get("features_available") is not True
    ):
        raise ValueError(
            "Karar anını ve gözlem birimini açıklayın; özelliklerin bu anda bilindiğini doğrulayın."
        )
    if task not in ("classification", "regression") or target not in frame:
        raise ValueError("Geçerli hedef ve görev seçin.")
    if (
        not isinstance(features, list)
        or not 1 <= len(features) <= 30
        or any(
            not isinstance(c, str) or c not in frame or c == target for c in features
        )
        or len(set(features)) != len(features)
    ):
        raise ValueError("Hedeften farklı 1–30 benzersiz özellik seçin.")
    if strategy in ("group", "time") and (key == target or key in features):
        raise ValueError("Ayrım anahtarı hedef/özellik olamaz.")
    frame = frame.map(lambda v: v.strip())
    if frame[target].eq("").any():
        raise ValueError("Hedef değerleri boş olamaz; önce veri hazırlayın.")
    if frame[features].eq("").all(axis=0).any():
        raise ValueError("Tamamen boş özellik kullanılamaz.")
    if task == "classification":
        counts = frame[target].value_counts()
        if not 2 <= len(counts) <= 12 or counts.min() < 10:
            raise ValueError(
                "Sınıflama 2–12 sınıf ve her sınıfta en az 10 gözlem gerektirir."
            )
        labels = sorted(counts.index.tolist())
        y = pd.Categorical(frame[target], categories=labels).codes
    else:
        values = pd.to_numeric(frame[target], errors="coerce").to_numpy(dtype=float)
        if (
            not np.isfinite(values).all()
            or np.max(np.abs(values)) > 1e12
            or np.var(values) == 0
        ):
            raise ValueError(
                "Regresyon hedefi sonlu, değişken ve |değer| ≤ 10¹² olmalı."
            )
        y = values
        labels = None
    for c in features:
        if frame[c].equals(frame[target]):
            raise ValueError("Hedefin kopyası özellik olarak kullanılamaz.")
        if re.search(r"(^|_)(id|uuid|email|customer_id|invoice)($|_)", c, re.I):
            raise ValueError(
                "Kimlik sütunlarını özelliklerden çıkarın; gerekiyorsa grup ayrımında kullanın."
            )
    train, test, folds = split_indices(frame, y, task, strategy, key)
    X = frame[features]
    reject_partition_duplicates(X, train, test, folds)
    smote = request.get("smote", False)
    if type(smote) is not bool:
        raise ValueError("SMOTE seçimi boolean olmalı.")
    if smote:
        if task != "classification" or any(
            column_type(X.iloc[train][c].replace("", np.nan).dropna().tolist())[0]
            not in ("integer", "number")
            for c in features
        ):
            raise ValueError(
                "SMOTE yalnız tamamen sayısal sınıflama özellikleriyle seçilebilir; kategorik veri için sınıf ağırlığı kullanın."
            )
        if any(pd.Series(y[train[a]]).value_counts().min() < 3 for a, _ in folds):
            raise ValueError(
                "SMOTE için her eğitim foldunda sınıf başına en az 3 gözlem gerekli."
            )
    choices = candidate_models(task, smote)
    scores = []
    for name, template in choices.items():
        values = []
        for a, b in folds:
            model = clone(template)
            model.fit(X.iloc[train[a]], y[train[a]])
            pred = model.predict(X.iloc[train[b]])
            values.append(
                float(
                    f1_score(
                        y[train[b]],
                        pred,
                        labels=list(range(len(labels))),
                        average="macro",
                        zero_division=0,
                    )
                )
                if task == "classification"
                else -float(mean_absolute_error(y[train[b]], pred))
            )
        scores.append(
            {
                "model": name,
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
                "fold_scores": values,
            }
        )
    selected = max(scores, key=lambda c: c["mean"])["model"]
    final = clone(choices[selected]).fit(X.iloc[train], y[train])
    baseline = clone(choices["dummy"]).fit(X.iloc[train], y[train])
    final_prediction = final.predict(X.iloc[test])
    base_prediction = baseline.predict(X.iloc[test])
    schema = final.named_steps["prepare"]
    recipe = {
        "version": VERSION,
        "source_sha256": hashlib.sha256(request["csv"].encode()).hexdigest(),
        "target": target,
        "features": features,
        "task": task,
        "split": strategy,
        "split_key": key,
        "seed": SEED,
        "smote": smote,
        "decision_context": context.strip(),
        "features_available": True,
    }
    split = {
        "train_rows": len(train),
        "holdout_rows": len(test),
        "cv_folds": 3,
        "train_indices": train.tolist(),
        "holdout_indices": test.tolist(),
        "folds": [
            {"train": train[a].tolist(), "validation": train[b].tolist()}
            for a, b in folds
        ],
    }
    split["sha256"] = hashlib.sha256(
        json.dumps(split, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    card = {
        "version": VERSION,
        "recipe": recipe,
        "split": split,
        "selection_metric": "macro_f1" if task == "classification" else "negative_mae",
        "candidates": scores,
        "selected_model": selected,
        "holdout": metrics(task, y[test], final_prediction, labels),
        "baseline": metrics(task, y[test], base_prediction, labels),
        "schema": {
            "numeric": schema.numeric_,
            "categorical": schema.categorical_,
            "signed_log": schema.log_columns_,
        },
        "class_distribution": (
            [
                {
                    "label": v,
                    "train": int(np.sum(y[train] == i)),
                    "holdout": int(np.sum(y[test] == i)),
                }
                for i, v in enumerate(labels)
            ]
            if labels
            else []
        ),
        "warnings": [
            "Deney keşif amaçlıdır. Aynı test kümesinde tekrar tekrar seçim yapmak iyimser sonuç üretebilir.",
            "Gelecek/proxy bilgi sızıntısını bütün yönleriyle otomatik saptamaz. Karar-anı özellikleri ve etiket ufku kullanıcı sorumluluğundadır.",
            "Group ve time ayrı stratejilerdir; eşzamanlı grup-zaman izolasyonu uygulanmaz.",
            "Model kartı saklanır; eğitilmiş model ve ham CSV saklanmaz.",
        ]
        + (
            ["RMSLE yalnız özgün ölçekte negatif olmayan hedef/tahmin için raporlanır."]
            if task == "regression"
            else []
        ),
        "fingerprint": fingerprint(),
        "budget": {
            "rows": 3000,
            "features": 30,
            "trees": 64,
            "depth": 8,
            "folds": 3,
            "threads": 1,
        },
    }
    identity = json.dumps(
        card, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )
    from importlib.metadata import version

    card["runtime_versions"] = {
        name: version(name)
        for name in ["scikit-learn", "imbalanced-learn", "pandas", "numpy", "scipy"]
    }
    from pathlib import Path

    for source in json.loads(
        (Path(__file__).parent / "data/ML_PROVENANCE.json").read_text()
    ):
        if source["sha256"] == recipe["source_sha256"]:
            card["source"] = {
                k: source[k] for k in ["title", "url", "description", "sha256"]
            }
    identity = json.dumps(
        card, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )
    card["sha256"] = hashlib.sha256(identity.encode()).hexdigest()
    card["duration_ms"] = round((time.monotonic() - started) * 1000)
    return card
