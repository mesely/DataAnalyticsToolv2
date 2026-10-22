"""A small, dependency-free text classifier for routing (AW-24): character n-grams + words, linear weights.

Training happens offline with scikit-learn (`python -m analysis.evals.train`); the product only reads the exported
JSON (vocabulary, weights, intercepts, classes, training data digest) and scores with plain Python, so a worker
process pays ~1 ms, needs no pickle and stays deterministic. Features: binary presence of folded character 2–5-grams
inside word boundaries and of word unigrams, unnormalised (the same as `vectorizer()` below at training time, so
pruning zero-weight features never changes a score).
"""
from __future__ import annotations

import functools
import json
import math
import re
from pathlib import Path

from analysis.retrieval import fold

MODELS = Path(__file__).resolve().parent / "models"
_WORD = re.compile(r"[a-z0-9]+")


def features(text: str) -> set[str]:
    t = " ".join(_WORD.findall(fold(text)))
    out = {"w:" + w for w in t.split()}
    if "?" in text:
        out.add("p:?")  # a question mark is a strong sign of a question to answer
    padded = f" {t} "
    for n in range(2, 6):
        for i in range(len(padded) - n + 1):
            gram = padded[i:i + n]
            if gram.strip():
                out.add("c:" + gram)
    return out


def vectorizer():
    """The scikit-learn vectorizer that reproduces `features` (training only)."""
    from sklearn.feature_extraction.text import CountVectorizer

    return CountVectorizer(analyzer=lambda text: sorted(features(text)), binary=True, lowercase=False)


@functools.lru_cache(maxsize=8)
def load(name: str) -> dict:
    model = json.loads((MODELS / f"{name}.json").read_text())
    model["_index"] = {f: i for i, f in enumerate(model["vocabulary"])}
    return model


def scores(name: str, text: str) -> dict[str, float]:
    """Class probabilities (softmax of the linear scores; one-vs-rest sigmoid for two classes)."""
    m = load(name)
    idx = m["_index"]
    present = [idx[f] for f in features(text) if f in idx]
    raw = [m["intercept"][c] + sum(row[i] for i in present) for c, row in enumerate(m["coef"])]
    classes = m["classes"]
    if len(raw) == 1:  # binary logistic regression: one row for classes[1]
        p = 1 / (1 + math.exp(-raw[0]))
        return {classes[0]: 1 - p, classes[1]: p}
    top = max(raw)
    exps = [math.exp(r - top) for r in raw]
    total = sum(exps)
    return {c: e / total for c, e in zip(classes, exps)}


def predict(name: str, text: str) -> tuple[str, float]:
    s = scores(name, text)
    label = max(s, key=lambda c: (s[c], c))
    return label, s[label]


def export(name: str, vec, clf, *, meta: dict) -> Path:
    """Write a trained (vectorizer, LogisticRegression) pair as JSON, keeping only features with a non-zero weight."""
    import numpy as np

    vocab = vec.get_feature_names_out()
    coef = np.atleast_2d(clf.coef_)
    keep = np.where(np.abs(coef).max(axis=0) > 1e-6)[0]
    out = {
        "name": name, **meta,
        "classes": [str(c) for c in clf.classes_],
        "vocabulary": [str(vocab[i]) for i in keep],
        "coef": [[round(float(row[i]), 5) for i in keep] for row in coef],
        "intercept": [round(float(x), 5) for x in np.atleast_1d(clf.intercept_)],
    }
    MODELS.mkdir(exist_ok=True)
    path = MODELS / f"{name}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n")
    load.cache_clear()
    return path
