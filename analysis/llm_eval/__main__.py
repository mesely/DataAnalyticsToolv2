"""python -m analysis.llm_eval [--providers scripted-ideal,scripted-adversarial,local,live] [--out file.json]

`live` uses the configured provider (analysis.llm_setup); `hf` is accepted as the v2.2 name for it."""
import argparse, json, pathlib
from analysis.llm_eval.evaluate import evaluate, markdown, PROVIDERS

ap = argparse.ArgumentParser()
ap.add_argument("--providers", default=",".join(PROVIDERS))
ap.add_argument("--out", default=None)
a = ap.parse_args()
report = evaluate(tuple(a.providers.split(",")))
if a.out:
    pathlib.Path(a.out).write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
print(markdown(report))
