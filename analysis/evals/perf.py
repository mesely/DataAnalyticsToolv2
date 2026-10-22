"""Latency of the analysis worker per action, measured the way the server runs it (AW-25).

    python -m analysis.evals.perf --n 20 --out docs/evals/results/perf-<label>.json

Each sample spawns `python -m analysis.worker` with the request on stdin, as core/src/workbench.ts does, so the
numbers include interpreter start-up, imports, DuckDB open and JSON serialisation (not HTTP, login or Postgres).
`--inproc` measures the same handlers inside one process (what a persistent worker would cost). No model is called
(`use_llm: False`, CONTEXT_LLM_EXTERNAL=off).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from analysis.evals import metrics as M

ROOT = Path(__file__).resolve().parents[2]
REQUESTS = {
    "catalog": {"action": "catalog", "dataset": "uci"},
    "overview+graph": {"action": "run", "dataset": "uci", "use_llm": False},
    "ask:products": {"action": "run", "dataset": "uci", "use_llm": False, "question": "En çok satan ürün hangisi?"},
    "ask:knowledge": {"action": "run", "dataset": "uci", "use_llm": False, "question": "retail-v2 nedir?"},
    "chart:default": {"action": "chart", "dataset": "uci", "prompt": "", "use_llm": False},
    "chart:refine": {"action": "chart", "dataset": "uci", "prompt": "Almanya ile Fransa'yı karşılaştır, son 6 ay", "use_llm": False},
    "chart:tl+cpi": {"action": "chart", "dataset": "uci", "prompt": "bugünkü TL ile göster", "use_llm": False},
    "chart:nato": {"action": "chart", "dataset": "uci", "prompt": "NATO ve NATO dışı satış payı", "use_llm": False},
    "table:page": {"action": "table", "dataset": "uci", "view": "rows", "page": 1, "page_size": 50},
    "table:filter+sort": {"action": "table", "dataset": "uci", "view": "rows", "page": 1, "page_size": 50,
                          "filters_table": [{"column": "product", "op": "contains", "value": "heart"}],
                          "sort": [{"column": "line_pence", "dir": "desc"}]},
    "network:ask": {"action": "network_ask", "dataset": "uci", "question": "En güçlü 5 ürün çifti hangisi?"},
    "route": {"action": "route", "text": "son 6 ayın cirosunu çiz"},
}


def spawn(payload: dict) -> tuple[float, bool, int]:
    env = {**os.environ, "CONTEXT_LLM_EXTERNAL": "off"}
    t0 = time.perf_counter()
    proc = subprocess.run([sys.executable, "-m", "analysis.worker"], cwd=ROOT, input=json.dumps(payload), text=True,
                          capture_output=True, timeout=60, env=env)
    ms = (time.perf_counter() - t0) * 1000
    try:
        ok = bool(json.loads(proc.stdout).get("ok"))
    except ValueError:
        ok = False
    return ms, ok, len(proc.stdout)


def inproc(payload: dict) -> tuple[float, bool, int]:
    from analysis.worker import handle

    os.environ["CONTEXT_LLM_EXTERNAL"] = "off"
    t0 = time.perf_counter()
    try:
        out = json.dumps(handle(dict(payload)), default=str)
        ok = True
    except Exception:  # noqa: BLE001 - a failing handler is reported, not raised
        out, ok = "", False
    return (time.perf_counter() - t0) * 1000, ok, len(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--inproc", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    fn = inproc if args.inproc else spawn
    names = [n for n in args.only.split(",") if n] or list(REQUESTS)
    out = {"mode": "inproc" if args.inproc else "spawn", "n": args.n, "python": sys.version.split()[0], "actions": {}}
    for name in names:
        fn(REQUESTS[name])  # warm the OS cache and (in-process) imports once
        samples = [fn(REQUESTS[name]) for _ in range(args.n)]
        ms = [s[0] for s in samples]
        out["actions"][name] = {**M.summary_ms(ms), "failures": sum(not s[1] for s in samples), "bytes": samples[-1][2]}
        a = out["actions"][name]
        print(f"{name:20} p50 {a['p50']:8.1f}  p95 {a['p95']:8.1f}  p99 {a['p99']:8.1f} ms  fail {a['failures']}  {a['bytes']} B")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
