"""Reproducible full-worker observations on measured public UCI data, without HF calls.
Run from repo: .venv/bin/python -m analysis.evaluate_decisions > report.json
Includes interpreter startup, input/output JSON and all analytic computation. Excludes
HTTP/OIDC/Postgres persistence and browser rendering; not a production SLA or model accuracy.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import argparse, datetime, json, math, os, platform, statistics, subprocess, sys, time
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 3])
    parser.add_argument("--actions", nargs="+", default=["forecast", "decisions"],
                        choices=["forecast", "decisions", "run", "run_filtered"],
                        help="run = dashboard overview+graph+answer; run_filtered = the same with a country filter")
    args = parser.parse_args()
    if not 1 <= args.samples <= 50 or any(n not in (1, 2, 3) for n in args.concurrency):
        parser.error("samples must be 1–50; concurrency must be 1, 2 or 3")
    stages = []
    last = None
    for action in args.actions:
        for concurrency in args.concurrency:
            if action in ("run", "run_filtered"):
                payload = {"action": "run", "dataset": "uci", "use_llm": False,
                           **({"filters": {"country": "France"}} if action == "run_filtered" else {})}
            else:
                payload = {
                    "action": action,
                    "dataset": "uci",
                    "use_llm": False,
                    "scenario": {"volume_pct": 5, "price_pct": 0, "budget_gbp": 100},
                }
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                observations = list(pool.map(one, [payload] * args.samples))
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
    if last is None:  # decisions not requested: compute one brief for the oracle section
        last = one({"action": "decisions", "dataset": "uci", "use_llm": False,
                    "scenario": {"volume_pct": 5, "price_pct": 0, "budget_gbp": 100}})["result"]
    forecast = last["forecast"]
    print(
        json.dumps(
            {
                "scope": "Full local subprocess, warm cache, public historical UCI records. Small sample; no HTTP/OIDC/PG/browser/HF overhead. Not an SLA, user pilot or LLM accuracy.",
                "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "producer": "analysis.evaluate_decisions",
                "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
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
                "live_llm": {
                    "status": "not_executed_by_this_benchmark",
                    "accuracy": None,
                    "successful_answers": None,
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
