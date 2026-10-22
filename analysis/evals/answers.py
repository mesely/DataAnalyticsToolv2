"""Grounded answer benchmark (AW-23): does the assistant's knowledge answer contain the required facts, and is every
claim in it supported by the cards it cites?

    python -m analysis.evals.answers --split dev [--retriever lexical] [--mode ranked|all] [--model]

Per answerable case: correct = every required fact appears in the answer (whitespace-normalised, exact text);
faithful = every answer sentence is a sentence of a cited card, or (model answers) every number it states appears in
a cited card; unsupported claim = an answer with a number or a sentence that no cited card supports. Unanswerable
cases are correct when the assistant says no card answers.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from analysis import knowledge_qa as K
from analysis import retrieval as R
from analysis.evals import metrics as M
from analysis.evals.retrieval import Bench, load

_WS = re.compile(r"\s+")


def norm(text: str) -> str:
    return _WS.sub(" ", text).strip()


def supported(answer: dict) -> tuple[bool, list[str]]:
    """Extractive check: each sentence (before the 'see also' line) is verbatim in a cited card body."""
    if answer["status"] != "answered":
        return True, []
    by_id = {c["id"]: c for c in R.cards()}
    pool = [norm(b) for c in answer["citations"] for b in by_id[c["id"]]["body"]]
    main = answer["text"].split("\n\n")[0]
    missing = [s for s in K.sentences(main) if not any(norm(s) in p for p in pool)]
    numbers = K.unsupported_numbers(main, [by_id[c["id"]] for c in answer["citations"]])
    return not missing and not numbers, missing + numbers


def run(cases, retriever=None, mode="ranked", threshold=K.ABSTAIN_SCORE, model_answer=None) -> dict:
    rows, lat = [], []
    for c in cases:
        t0 = time.perf_counter()
        a = K.answer(c["query"], "en" if c["lang"] == "en" else "tr", retriever=retriever, mode=mode, threshold=threshold)
        if model_answer and a["status"] == "answered":
            a = model_answer(c["query"], a)
        lat.append((time.perf_counter() - t0) * 1000)
        if c["answerable"]:
            text = norm(a["text"])
            facts = [f for f in c["required_facts"] if norm(f) in text]
            ok_sup, bad = supported(a) if not a.get("model") else (not a.get("unsupported"), a.get("unsupported", []))
            rows.append({"id": c["id"], "category": c["category"], "answerable": True, "status": a["status"],
                         "correct": a["status"] == "answered" and len(facts) == len(c["required_facts"]),
                         "fact_coverage": len(facts) / len(c["required_facts"]) if c["required_facts"] else 1.0,
                         "cited_primary": c["primary"] in [x["id"] for x in a.get("citations", [])],
                         "faithful": ok_sup, "unsupported": bad, "words": len(a["text"].split())})
        else:
            rows.append({"id": c["id"], "category": c["category"], "answerable": False, "status": a["status"],
                         "correct": a["status"] == "no_card", "faithful": True, "unsupported": [], "words": len(a["text"].split())})
    ans = [r for r in rows if r["answerable"]]
    out = {"n": len(rows), "answer_correctness": M.mean(r["correct"] for r in ans),
           "fact_coverage": M.mean(r["fact_coverage"] for r in ans),
           "citation_coverage": M.mean(r["cited_primary"] for r in ans),
           "faithfulness": M.mean(r["faithful"] for r in rows if r["status"] == "answered"),
           "unsupported_claim_rate": M.mean((not r["faithful"]) for r in rows if r["status"] == "answered"),
           "abstain_correct": M.mean(r["correct"] for r in rows if not r["answerable"]),
           "false_abstain_rate": M.mean(r["status"] != "answered" for r in ans),
           "overall_correct": M.mean(r["correct"] for r in rows),
           "mean_words": M.mean(r["words"] for r in rows), "latency_ms": M.summary_ms(lat), "rows": rows}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev", choices=("dev", "val", "test"))
    ap.add_argument("--retriever", default="lexical")
    ap.add_argument("--mode", default="ranked", choices=("ranked", "all"))
    ap.add_argument("--threshold", type=float, default=K.ABSTAIN_SCORE)
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    bench = Bench()
    fn = bench.configs()[args.retriever]
    res = run(load(args.split), retriever=fn, mode=args.mode, threshold=args.threshold)
    res.update({"split": args.split, "retriever": args.retriever, "mode": args.mode, "threshold": args.threshold,
                "qa_version": K.VERSION})
    print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in res.items() if k != "rows"})
    if args.out:
        Path(args.out).write_text(json.dumps(res, indent=1, ensure_ascii=False, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
