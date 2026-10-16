"""Reproducible full-worker observations on measured public UCI data, without HF calls.
Run from repo: .venv/bin/python -m analysis.evaluate_decisions > report.json
Includes interpreter startup, input/output JSON and all analytic computation. Excludes
HTTP/OIDC/Postgres persistence and browser rendering; not a production SLA or model accuracy.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json, math, os, platform, statistics, subprocess, sys, time
from analysis.fingerprint import fingerprint

ROOT = Path(__file__).resolve().parents[1]


def one(payload):
    env = {
        **os.environ,
        **{
            k: "1"
            for k in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"]
        },
    }
    start = time.perf_counter()
    p = subprocess.run(
        [sys.executable, "-m", "analysis.worker"],
        cwd=ROOT,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=45,
        env=env,
    )
    ms = round((time.perf_counter() - start) * 1000, 2)
    obj = json.loads(p.stdout)
    result = obj.get("result", {})
    return {
        "ms": ms,
        "ok": p.returncode == 0 and obj.get("ok") is True,
        "result": result,
    }


def main():
    stages = []
    last = None
    for action in ["forecast", "decisions"]:
        for concurrency in [1, 3]:
            payload = {
                "action": action,
                "dataset": "uci",
                "use_llm": False,
                "scenario": {"volume_pct": 5, "price_pct": 0, "budget_gbp": 100},
            }
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                observations = list(pool.map(one, [payload] * 9))
            values = sorted(row["ms"] for row in observations)
            stages.append(
                {
                    "action": action,
                    "concurrency": concurrency,
                    "samples": len(values),
                    "p50_ms": statistics.median(values),
                    "sample_p95_ms": values[math.ceil(0.95 * len(values)) - 1],
                    "max_ms": max(values),
                    "failures": sum(not r["ok"] for r in observations),
                    "raw_ms": [r["ms"] for r in observations],
                }
            )
            if action == "decisions":
                last = observations[-1]["result"]
    forecast = last["forecast"]
    print(
        json.dumps(
            {
                "scope": "Full local subprocess, warm cache, public historical UCI records. Small sample; no HTTP/OIDC/PG/browser/HF overhead. Not an SLA, user pilot or LLM accuracy.",
                "environment": {
                    "platform": platform.system(),
                    "machine": platform.machine(),
                    "python": platform.python_version(),
                    "threads_per_worker": 1,
                },
                "source_rows": 530104,
                "build": fingerprint(),
                "observations": stages,
                "forecast": {
                    "weeks": forecast["complete_weeks"],
                    "selected": forecast["selected"],
                    "holdout": forecast["holdout"],
                    "next": forecast["next"],
                    "uncertainty": forecast["uncertainty"],
                },
                "decision_oracle": {
                    "gross_pence": last["artifacts"]["summary"]["gross_pence"],
                    "orders": last["artifacts"]["summary"]["orders"],
                    "recommendations": [
                        {k: c[k] for k in ["id", "support_score", "score_components"]}
                        for c in last["recommendations"]
                    ],
                    "scenario": last["scenario"],
                },
                "live_llm": {"status":"not_executed_by_this_benchmark", "accuracy":None, "successful_answers":None},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
