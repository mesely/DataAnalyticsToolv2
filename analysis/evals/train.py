"""Train the learned routers (AW-24) on the dev split (+ the older authored sets), choose C on val, export JSON.

    python -m analysis.evals.train --task studio      # analysis/models/studio-router.json
    python -m analysis.evals.train --task intent      # analysis/models/intent-router.json

The test split is never read here. Training is deterministic (liblinear, fixed data order); the exported model
records the digest of its training data, the chosen C and its val accuracy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from analysis import textclf
from analysis.evals.split import DATA

C_GRID = (0.1, 0.3, 1.0, 3.0, 10.0, 30.0)


def legacy(task: str) -> list[tuple[str, str]]:
    """Older authored sets (llm-eval v2/v3), all written before this benchmark; none is in the new splits."""
    from analysis.llm_eval.cases import PLAN_CASES
    from analysis.llm_eval.heldout import CHART_CASES, GROUP_CASES, QUESTION_CASES

    if task == "studio":
        return ([(c["prompt"], "chart") for c in CHART_CASES + GROUP_CASES]
                + [(q, "decision") for _, _, q, _, _ in QUESTION_CASES + PLAN_CASES])
    rows = []
    for _, _, q, intent, behavior in QUESTION_CASES + PLAN_CASES:
        rows.append((q, "refuse" if behavior == "refuse" else intent))
    return rows


def split_rows(task: str, part: str) -> list[tuple[str, str]]:
    data = json.loads((DATA / f"{task}_{part}.json").read_text())["cases"]
    if task == "studio":
        return [(c["text"], c["expect"]) for c in data]
    return [(c["question"], c["intent"]) for c in data]


def fit(rows, c_value, extras=None):
    from sklearn.linear_model import LogisticRegression

    vec = textclf.vectorizer(extras)
    x = vec.fit_transform([t for t, _ in rows])
    clf = LogisticRegression(C=c_value, max_iter=5000, solver="liblinear" if len({y for _, y in rows}) == 2 else "lbfgs")
    clf.fit(x, [y for _, y in rows])
    return vec, clf


def accuracy(vec, clf, rows) -> float:
    pred = clf.predict(vec.transform([t for t, _ in rows]))
    return sum(p == y for p, (_, y) in zip(pred, rows)) / len(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=("studio", "intent"))
    ap.add_argument("--no-legacy", action="store_true")
    ap.add_argument("--extras", default="", help="domain signal set for the features (e.g. studio)")
    args = ap.parse_args(argv)
    train = split_rows(args.task, "dev") + ([] if args.no_legacy else legacy(args.task))
    val = split_rows(args.task, "val")
    scores = {}
    extras = args.extras or None
    if extras:
        import analysis.router  # noqa: F401 - registers the studio signals
    for c in C_GRID:
        vec, clf = fit(train, c, extras)
        scores[c] = accuracy(vec, clf, val)
    best = max(C_GRID, key=lambda c: (scores[c], -c))  # ties: the stronger regularisation
    vec, clf = fit(train, best, extras)
    digest = hashlib.sha256(json.dumps(train, ensure_ascii=False).encode()).hexdigest()
    path = textclf.export(f"{args.task}-router", vec, clf, meta={
        "version": f"{args.task}-router-learned-v1", "trained_on": "dev split + legacy llm-eval sets" if not args.no_legacy else "dev split",
        "training_rows": len(train), "training_sha256": digest, "C": best, "val_accuracy": round(scores[best], 4),
        **({"extras": extras, "extras_module": "analysis.router"} if extras else {}),
        "val_grid": {str(k): round(v, 4) for k, v in scores.items()}})
    print(path, {"C": best, "val_accuracy": round(scores[best], 4), "grid": scores, "rows": len(train)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
