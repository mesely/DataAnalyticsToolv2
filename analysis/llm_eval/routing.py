"""Measure the local method and the model on the held-out cases, and derive the routing table (v3 G6).

    python -m analysis.llm_eval.routing --task chart_plan --out receipt-chart.json      # one task, local + live
    python -m analysis.llm_eval.routing --table receipt-*.json                          # write analysis/llm_routing.json

Every live case is a real call; an unreachable provider BLOCKS the rest of that task and nothing is inferred. A task
measured in several sittings (the free tier allows ~200k tokens a day) is resumed with --resume, which keeps the
cases already answered and asks only the rest.

Rule (AW-18): the model is used for a task only when it beats the local method by at least 5 points on the held-out
cases; on a tie the local method wins (free, deterministic, offline). When the model does not win outright but
answers correctly at least 60 % of the cases the local method misses (n >= 3), the task becomes "local_then_model":
the local method runs first and the model is asked only when the local method cannot plan the request.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib

from analysis.llm_eval.heldout import CHART_CASES, GROUP_CASES, question_cases, studio_cases

VERSION = "llm-eval-v3.0"
MARGIN = 0.05
RESCUE_RATE = 0.60
RESCUE_MIN = 3
ROOT = pathlib.Path(__file__).resolve().parents[2]
TABLE = ROOT / "analysis" / "llm_routing.json"
TASKS = ("chart_plan", "question_route", "studio_route", "chart_groups")


def _catalog():
    from analysis.worker import meta

    return meta("uci")


def _done(prior, task, provider):
    if not prior:
        return {}
    rows = ((prior.get("tasks") or {}).get(task) or {}).get(provider, {}).get("records", [])
    return {r["id"]: r for r in rows if r.get("raw_status") != "BLOCKED" and r.get("correct") is not None}


def _chart(provider, prior, task="chart_plan", cases=CHART_CASES):
    from analysis.llm_eval.chart import run_chart

    keep = _done(prior, task, provider)
    todo = [c for c in cases if c["id"] not in keep]
    records, blocked = run_chart(provider, _catalog(), cases=todo) if todo else ([], None)
    by = {**keep, **{r["id"]: r for r in records}}
    return [by[c["id"]] for c in cases if c["id"] in by], blocked


def _questions(provider, prior):
    from analysis.llm_eval.evaluate import run_plan

    keep = _done(prior, "question_route", provider)
    cases = question_cases()
    todo = [c for c in cases if c["id"] not in keep]
    records, blocked = run_plan(provider, todo) if todo else ([], None)
    out = []
    for r in records:
        r["raw_status"] = r["got"].get("raw_status")
        r.update({k: r["got"][k] for k in ("latency_ms", "total_tokens") if r["got"].get(k) is not None})
        r["correct"] = None if r["raw_status"] == "BLOCKED" else bool(r["behavior_correct"] and r["intent_correct"] is not False)
        out.append(r)
    by = {**keep, **{r["id"]: r for r in out}}
    return [by[c["id"]] for c in cases if c["id"] in by], blocked


def _studios(provider, prior):
    from analysis.router import route
    from analysis.llm import plan_studio
    from analysis.llm_eval.evaluate import _pause

    keep = _done(prior, "studio_route", provider)
    records, blocked = [], None
    for case in studio_cases():
        if case["id"] in keep:
            records.append(keep[case["id"]])
            continue
        if provider == "local":
            got, raw, usage = route(case["text"])["studio"], "planned", {}
        elif blocked is None:
            plan = plan_studio(case["text"])
            _pause()
            if plan["status"] == "unavailable" and plan.get("error_code") != "json_validate_failed":
                blocked = {k: plan.get(k) for k in ("status", "error_code", "http_status")}
            got, raw = plan.get("studio"), plan["status"]
            usage = {k: (plan.get("telemetry") or {}).get(k) for k in ("latency_ms", "total_tokens")}
        if blocked is not None and provider != "local":
            records.append({"id": case["id"], "text": case["text"], "raw_status": "BLOCKED", "correct": None, "blocked": blocked})
            continue
        records.append({"id": case["id"], "text": case["text"], "expect": case["expect"], "got": got, "raw_status": raw,
                        "correct": got == case["expect"], **usage})
    return records, blocked


RUNNERS = {"chart_plan": _chart, "question_route": _questions, "studio_route": _studios,
           # Reported on its own (v3.1); it does not change the chart_plan row of the table.
           "chart_groups": lambda p, prior: _chart(p, prior, "chart_groups", GROUP_CASES)}


def summarize(records):
    done = [r for r in records if r.get("correct") is not None]
    tokens = [r.get("total_tokens") for r in done if r.get("total_tokens")]
    lat = sorted(r.get("latency_ms") for r in done if r.get("latency_ms"))
    return {
        "n": len(records),
        "answered": len(done),
        "correct": sum(1 for r in done if r["correct"]),
        "accuracy": (sum(1 for r in done if r["correct"]) / len(done)) if done else None,
        "tokens": sum(tokens) if tokens else None,
        "median_latency_ms": lat[len(lat) // 2] if lat else None,
    }


def measure(task, providers=("local", "live"), prior=None):
    out = {}
    for p in providers:
        records, blocked = RUNNERS[task](p, prior)
        out[p] = {"label": "MEASURED" if blocked is None else "BLOCKED", "blocked": blocked, "summary": summarize(records),
                  "records": records}
    return out


def decide(task, local, live):
    """The routing rule (AW-18) over two measured rows; returns the table entry for one task."""
    ls, ms = local["summary"], live["summary"]
    entry = {"local_accuracy": ls["accuracy"], "model_accuracy": ms["accuracy"], "n": ls["n"],
             "model_answered": ms["answered"]}
    if live["label"] != "MEASURED" or ms["answered"] < ms["n"]:
        return {**entry, "method": "local", "why": "model not measured on every held-out case"}
    if round(ms["accuracy"] - ls["accuracy"], 9) >= MARGIN:
        return {**entry, "method": "model", "why": f"model beats local by >= {int(MARGIN * 100)} points"}
    lby = {r["id"]: r for r in local["records"]}
    missed = [r for r in live["records"] if not lby[r["id"]]["correct"]]
    rescued = sum(1 for r in missed if r["correct"])
    entry.update(local_missed=len(missed), model_rescued=rescued)
    if len(missed) >= RESCUE_MIN and rescued / len(missed) >= RESCUE_RATE:
        return {**entry, "method": "local_then_model",
                "why": f"local is at least as good overall; the model answers {rescued}/{len(missed)} of the cases local misses"}
    return {**entry, "method": "local", "why": "local is at least as good, and the model does not reliably cover its misses"}


def table(receipts):
    tasks = {}
    model = None
    for r in receipts:
        for task, rows in r["tasks"].items():
            if task not in ("chart_plan", "question_route", "studio_route"):
                continue
            tasks[task] = decide(task, rows["local"], rows["live"])
            tasks[task]["receipt"] = r["_path"]
            tasks[task]["measured_at"] = r["generated_at"]
        model = model or r.get("model")
    # Tasks without a local head-to-head keep the local method: the model's focus selection is an annotation on the
    # local ranking, and its narrative passed the validator 1 time in 3 (phase12-llm-eval-groq.json).
    tasks.setdefault("decision_focus", {"method": "local", "why": "no local equivalent to compare against; the checklist ranking stays the reference",
                                        "receipt": "docs/evidence/verification/phase12-llm-eval-groq.json"})
    tasks.setdefault("decision_narrative", {"method": "local", "local_accuracy": 1.0, "model_accuracy": 1 / 3,
                                            "why": "model narrative accepted by the validator 1/3",
                                            "receipt": "docs/evidence/verification/phase12-llm-eval-groq.json"})
    return {"version": "llm-routing-v1", "rule": {"margin": MARGIN, "rescue_rate": RESCUE_RATE, "rescue_min": RESCUE_MIN},
            "model": model, "tasks": dict(sorted(tasks.items()))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=TASKS)
    ap.add_argument("--providers", default="local,live")
    ap.add_argument("--out")
    ap.add_argument("--resume")
    ap.add_argument("--table", nargs="*")
    a = ap.parse_args()
    if a.table is not None:
        receipts = []
        for path in a.table:
            r = json.loads(pathlib.Path(path).read_text())
            r["_path"] = str(pathlib.Path(path).resolve().relative_to(ROOT))
            receipts.append(r)
        TABLE.write_text(json.dumps(table(receipts), indent=1, ensure_ascii=False) + "\n")
        print(TABLE.read_text())
        return
    from analysis.llm import status

    prior = json.loads(pathlib.Path(a.resume).read_text()) if a.resume else None
    report = {"version": VERSION, "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "model": status().get("label"), "tasks": {a.task: measure(a.task, tuple(a.providers.split(",")), prior)}}
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    for p, row in report["tasks"][a.task].items():
        print(a.task, p, row["label"], row["summary"], row.get("blocked") or "")


if __name__ == "__main__":
    main()
