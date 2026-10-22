"""Write analysis/llm_routing.json from the frozen test-split measurements (AW-24).

    python -m analysis.evals.routing_table

Per task, the local method is compared with every model that answered all test cases, on the same cases:
- the model is used only when its accuracy beats the local method by at least 3 points AND the paired exact McNemar
  test on the discordant cases gives p < 0.05 (a practically and statistically meaningful advantage);
- otherwise, when the best model answers correctly at least 60 % of the cases the local method misses (n >= 3) and
  the local method can say when it is unsure, "local_then_model" asks the model only then;
- otherwise the local method (free, instant, nothing leaves the machine). Ties go to the local method.
A model that was blocked (quota) on any case is not compared: an incomplete comparison is never reported as one.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from analysis.evals import metrics as M
from analysis.evals.providers import SPECS
from analysis.evals.routing import RESULTS

TABLE = Path(__file__).resolve().parents[1] / "llm_routing.json"
MARGIN, ALPHA, RESCUE_RATE, RESCUE_MIN = 0.03, 0.05, 0.60, 3
TASKS = {  # benchmark task -> (routing task, chosen local method, can the local method say it is unsure?)
    "studio": ("studio_route", "learned", True),
    "intent": ("question_intent", "rules", True),
    "chart": ("chart_plan", "local", True),
}
LABELS = {"gpt-oss-20b": "GPT-OSS 20B · Groq", "gpt-oss-120b": "GPT-OSS 120B · Groq", "qwen3.8-27b": "Qwen3.8 27B · Groq",
          "llama-3.3-70b-hf": "Llama 3.3 70B · Hugging Face"}


def _load(task: str, name: str) -> dict | None:
    path = RESULTS / f"routing-{task}-test-{name}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return data.get(name if name in data else next(iter(data)), None) if name != "local" else data


def decide(task: str) -> dict:
    routing_task, local_name, unsure = TASKS[task]
    local_all = _load(task, "local") or {}
    local = local_all.get(local_name)
    if not local:
        return {}
    ok_local = {r["id"]: bool(r["correct"]) for r in local["rows"]}
    models = []
    for name in SPECS:
        res = _load(task, name)
        res = res.get(f"model:{name}") if res and f"model:{name}" in res else res
        if not res or res.get("blocked") or res["answered"] < res["n"]:
            continue
        ok = {r["id"]: bool(r["correct"]) for r in res["rows"]}
        a_only = sum(1 for i in ok_local if ok_local[i] and not ok.get(i))
        b_only = sum(1 for i in ok_local if ok.get(i) and not ok_local[i])
        models.append({"name": name, "accuracy": res["accuracy"], "p_value": M.mcnemar(a_only, b_only),
                       "rescued": b_only, "lost": a_only, "latency_p50_ms": (res.get("latency_ms") or {}).get("p50"),
                       "tokens": res.get("tokens"), "n": res["n"]})
    local_acc, n = local["accuracy"], local["n"]
    misses = sum(1 for v in ok_local.values() if not v)
    entry = {"local_method": local_name, "local_accuracy": round(local_acc, 4), "n": n,
             "receipt": f"docs/evals/results/routing-{task}-test-*.json",
             "measured_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
             "candidates": {m["name"]: {k: (round(v, 4) if isinstance(v, float) else v) for k, v in m.items() if k != "name"}
                            for m in models}}
    if not models:
        return {**entry, "method": "local", "why": "no model answered every held-out case (quota or not run)"}
    best = max(models, key=lambda m: (m["accuracy"], -(m["latency_p50_ms"] or 0)))
    entry.update({"model": LABELS.get(best["name"], best["name"]), "model_id": SPECS[best["name"]][1],
                  "model_accuracy": round(best["accuracy"], 4), "p_value": round(best["p_value"], 5)})
    gain = best["accuracy"] - local_acc
    if gain >= MARGIN and best["p_value"] < ALPHA:
        return {**entry, "method": "model",
                "why": f"model beats local by {gain * 100:.1f} points (McNemar p = {best['p_value']:.3g})"}
    if unsure and misses >= RESCUE_MIN and best["rescued"] / misses >= RESCUE_RATE and gain > 0:
        return {**entry, "method": "local_then_model",
                "why": f"local first; the model recovers {best['rescued']}/{misses} of local misses"}
    return {**entry, "method": "local",
            "why": (f"local within {abs(gain) * 100:.1f} points of the best model (McNemar p = {best['p_value']:.3g}); "
                    "local is free, instant and private") if gain > 0 else "local is as good as or better than every model"}


def main() -> int:
    table = json.loads(TABLE.read_text()) if TABLE.exists() else {"tasks": {}}
    table["version"] = "llm-routing-v2"
    table["rule"] = {"margin": MARGIN, "alpha": ALPHA, "test": "exact McNemar on paired held-out cases",
                     "rescue_rate": RESCUE_RATE, "rescue_min": RESCUE_MIN, "split": "frozen test (analysis/evals/data)"}
    table.pop("model", None)
    for task, (routing_task, _, _) in TASKS.items():
        decided = decide(task)
        if decided:
            table["tasks"][routing_task] = decided
            print(routing_task, decided["method"], decided.get("why"))
    table["tasks"].pop("question_route", None)  # replaced by question_intent (intent v2)
    TABLE.write_text(json.dumps(table, indent=1, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
