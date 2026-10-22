"""Routing and planning benchmark (AW-24): local methods against hosted models on the same frozen cases.

    python -m analysis.evals.routing --task studio --split val --methods rules-v1,learned,model:gpt-oss-20b
    python -m analysis.evals.routing --task intent|chart|multiturn --split test --methods ...

Every model answer is a real call, cached per (task, model, case) under docs/evals/results/cache/ so an interrupted
run resumes (`--resume`) and a quota stop never invents an answer: the remaining cases are reported BLOCKED and the
comparison says so. Correctness:
- studio: the predicted studio equals the label;
- intent: the predicted intent equals the label (behaviour follows from it);
- chart: every field in `expect` matches the planned spec (country lists as sets; `transform` fields compared on the
  keys given, with absent transform = defaults);
- multiturn: per turn as chart, and per conversation when every turn is right.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from analysis.evals import metrics as M
from analysis.evals.split import DATA

RESULTS = Path(__file__).resolve().parents[2] / "docs" / "evals" / "results"
CACHE = RESULTS / "cache"


def cases(task: str, split: str) -> list[dict]:
    raw = json.loads((DATA / f"{task}_{split}.json").read_text())
    return raw.get("cases") or raw.get("conversations")


# ------------------------------------------------------------------------------------------------ methods

def _catalog():
    from analysis.worker import meta

    return meta("uci")


def studio_method(name: str):
    if name == "rules-v1":
        from analysis.router import route

        return lambda text: (route(text)["studio"], {})
    if name == "learned":
        from analysis import textclf

        def learned(text):
            label, p = textclf.predict("studio-router", text)
            return label, {"confidence": round(p, 4)}
        return learned
    if name == "router":
        from analysis.router import route

        return lambda text: (route(text, method="auto")["studio"], {})
    if name.startswith("model:"):
        from analysis.evals.providers import chat
        from analysis.llm import plan_studio

        model = chat(name[6:], 20)
        return lambda text: _model_out(plan_studio(text, model=model), "studio")
    raise ValueError(name)


def intent_method(name: str):
    if name == "legacy-local":
        from analysis.llm_eval.evaluate import _local_intent
        from analysis.worker import explain, overview

        base = {"dataset": "uci", "include_graph": False, "locale": "en"}
        res = overview(base)

        def legacy(q):
            out = explain({**base, "question": q}, res) or {}
            if out.get("status") == "refused":
                return "refuse", {}
            return _local_intent(out) or "clarify", {}
        return legacy
    if name in ("learned", "rules", "pipeline"):
        from analysis import intents

        method = {"learned": "learned", "rules": "rules", "pipeline": "auto"}[name]

        def local(q):
            out = intents.classify(q, method=method)
            return out["intent"], {"confidence": out["confidence"]}
        return local
    if name.startswith("model:"):
        from analysis.evals.providers import chat
        from analysis.llm import plan_intent

        model = chat(name[6:], 30)
        return lambda q: _model_out(plan_intent(q, model=model), "intent")
    raise ValueError(name)


def chart_method(name: str):
    catalog = _catalog()
    if name == "local":
        from analysis.chart_studio import local_plan

        return lambda prompt, base, locale: (local_plan(prompt, base, catalog, locale)["spec"], {})
    if name.startswith("model:"):
        from analysis.chart_studio import default_spec, llm_plan
        from analysis.evals.providers import chat

        model = chat(name[6:], 300)

        def run(prompt, base, locale):
            plan = llm_plan(prompt, base, catalog, model=model, locale=locale)
            if plan["status"] in ("planned", "no_change"):
                return plan["spec"], {**(plan.get("telemetry") or {}), "raw_status": plan["status"]}
            return None, {"raw_status": plan["status"], "error_code": plan.get("error_code"),
                          "http_status": plan.get("http_status")}
        return run
    raise ValueError(name)


def _model_out(plan: dict, key: str):
    usage = {k: (plan.get("telemetry") or {}).get(k) for k in ("latency_ms", "total_tokens")}
    usage.update({"raw_status": plan["status"], "error_code": plan.get("error_code"), "http_status": plan.get("http_status")})
    return (plan.get(key) if plan["status"] in ("planned", "blocked") else None), usage


def _blocked(meta: dict) -> bool:
    return meta.get("raw_status") == "unavailable" and meta.get("error_code") != "json_validate_failed" and (
        meta.get("http_status") in (429, 401, 403, 413, 498, 503) or meta.get("error_code") in ("rate_limited", "quota", "timeout"))


# ------------------------------------------------------------------------------------------------ scoring

def chart_match(spec: dict | None, expect: dict) -> tuple[bool, list[str]]:
    from analysis.transforms import default as tx_default

    if spec is None:
        return False, ["no_plan"]
    wrong = []
    for key, want in expect.items():
        got = spec.get(key)
        if key in ("countries", "exclude_countries"):
            ok = set(got or []) == set(want or [])
        elif key == "transform":
            have = {**tx_default(), **(got or {})}
            ok = all(have.get(k) == v for k, v in (want or {}).items()) if want else not got
        else:
            ok = got == want
        if not ok:
            wrong.append(key)
    return not wrong, wrong


def _cache_path(task, method, split):
    return CACHE / f"{task}-{method.replace(':', '_').replace('/', '_')}-{split}.json"


def run(task: str, split: str, method: str, resume: bool = True, limit: int | None = None) -> dict:
    data = cases(task, split)[:limit] if limit else cases(task, split)
    cached = {}
    cpath = _cache_path(task, method, split)
    if resume and cpath.exists() and method.startswith("model:"):
        cached = {r["id"]: r for r in json.loads(cpath.read_text())["rows"] if r.get("status") != "BLOCKED"}
    fn = {"studio": studio_method, "intent": intent_method}.get(task, chart_method)(method) if (
        not method.startswith("model:") or len(cached) < len(data)) else None
    rows, blocked = [], None
    for c in data:
        if c["id"] in cached:
            rows.append(cached[c["id"]])
            continue
        if blocked:
            rows.append({"id": c["id"], "status": "BLOCKED", "correct": None})
            continue
        t0 = time.perf_counter()
        if task == "studio":
            got, meta = fn(c["text"])
            row = {"id": c["id"], "category": c.get("category"), "lang": c.get("lang"), "ambiguous": c.get("ambiguous", False),
                   "expect": c["expect"], "got": got, "correct": got == c["expect"]}
        elif task == "intent":
            got, meta = fn(c["question"])
            row = {"id": c["id"], "category": c.get("category"), "lang": c.get("lang"), "expect": c["intent"], "got": got,
                   "correct": got == c["intent"]}
        elif task == "chart":
            from analysis.chart_studio import default_spec

            base = {**default_spec(), **c["base"]} if c.get("base") else None
            spec, meta = fn(c["prompt"], base, "en" if c.get("lang") == "en" else "tr")
            ok, wrong = chart_match(spec, c["expect"])
            row = {"id": c["id"], "category": c.get("category"), "lang": c.get("lang"), "correct": ok, "wrong": wrong,
                   "got": {k: (spec or {}).get(k) for k in c["expect"]}}
        else:  # multiturn
            spec, turns, meta = None, [], {}
            for t in c["turns"]:
                new, meta = fn(t["prompt"], spec, "en" if c.get("lang") == "en" else "tr")
                if new is None and _blocked(meta):
                    break
                spec = new if new is not None else spec
                ok, wrong = chart_match(spec, t["expect"])
                turns.append({"correct": ok, "wrong": wrong})
            row = {"id": c["id"], "lang": c.get("lang"), "turns": turns, "correct": len(turns) == len(c["turns"]) and all(x["correct"] for x in turns)}
        row["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        row.update({k: v for k, v in meta.items() if k in ("total_tokens", "raw_status", "error_code", "http_status", "confidence")})
        if method.startswith("model:") and _blocked(meta):
            blocked = {k: meta.get(k) for k in ("raw_status", "error_code", "http_status")}
            row = {"id": c["id"], "status": "BLOCKED", "correct": None, "blocked": blocked}
        rows.append(row)
        if method.startswith("model:"):
            time.sleep(float(__import__("os").environ.get("EVAL_PAUSE", "0.6")))
    done = [r for r in rows if r.get("correct") is not None]
    n_ok = sum(1 for r in done if r["correct"])
    out = {"task": task, "split": split, "method": method, "n": len(data), "answered": len(done),
           "accuracy": n_ok / len(done) if done else float("nan"), "ci95": M.wilson(n_ok, len(done)),
           "blocked": blocked, "latency_ms": M.summary_ms([r["latency_ms"] for r in done if "latency_ms" in r]) if done else None,
           "tokens": sum(r.get("total_tokens") or 0 for r in done), "rows": rows}
    if task == "multiturn":
        turns = [t for r in done for t in r["turns"]]
        out["turn_accuracy"] = sum(t["correct"] for t in turns) / len(turns) if turns else float("nan")
    if task in ("studio", "intent"):
        labels = sorted({r["expect"] for r in done})
        out["per_class"] = {}
        for lab in labels:
            tp = sum(1 for r in done if r["got"] == lab and r["expect"] == lab)
            pred = sum(1 for r in done if r["got"] == lab)
            gold = sum(1 for r in done if r["expect"] == lab)
            out["per_class"][lab] = {"precision": tp / pred if pred else float("nan"), "recall": tp / gold if gold else float("nan"), "n": gold}
    if method.startswith("model:"):
        CACHE.mkdir(parents=True, exist_ok=True)
        cpath.write_text(json.dumps({"task": task, "split": split, "method": method, "rows": rows}, ensure_ascii=False, indent=1))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=("studio", "intent", "chart", "multiturn"))
    ap.add_argument("--split", default="dev", choices=("dev", "val", "test"))
    ap.add_argument("--methods", required=True)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    results = {}
    for method in args.methods.split(","):
        res = run(args.task, args.split, method, limit=args.limit)
        results[method] = res
        lo, hi = res["ci95"]
        extra = f"  turns {res['turn_accuracy']:.3f}" if "turn_accuracy" in res else ""
        print(f"{args.task:9} {args.split:4} {method:28} acc {res['accuracy']:.3f} [{lo:.3f}, {hi:.3f}] "
              f"n={res['answered']}/{res['n']}{extra}  p50 {res['latency_ms']['p50'] if res['latency_ms'] else '-'} ms"
              f"  tokens {res['tokens']}" + (f"  BLOCKED {res['blocked']}" if res["blocked"] else ""))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=1, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
