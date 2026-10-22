"""Split the authored evaluation sets into dev / val / test once, and seal the test split (AW-23).

    python -m analysis.evals.split --source <dir with *_cases.json>   # write analysis/evals/data + MANIFEST.json
    python -m analysis.evals.split --verify                            # fail if any split changed since sealing

Stratified by category (conversations as units for multi-turn), seed 20261022: 40 % dev, 20 % val, 40 % test.
The cases were written by an author who saw only the product contract (and, for retrieval, the corpus), never the
planner, router or retriever code. Tune on dev, choose on val, report test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
SEED = 20261022
SHARES = (("dev", 0.4), ("val", 0.2), ("test", 0.4))
SETS = {  # name: (source file, list key, stratum key)
    "retrieval": ("retrieval_cases.json", "cases", "category"),
    "studio": ("studio_cases.json", "cases", "category"),
    "intent": ("intent_cases.json", "cases", "intent"),
    "chart": ("chart_cases.json", "cases", "category"),
    "multiturn": ("multiturn_cases.json", "conversations", "lang"),
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split(items: list, stratum: str) -> dict[str, list]:
    rng = random.Random(SEED)
    groups: dict[str, list] = defaultdict(list)
    for it in items:
        groups[str(it.get(stratum))].append(it)
    out = {name: [] for name, _ in SHARES}
    for key in sorted(groups):
        g = groups[key][:]
        rng.shuffle(g)
        n = len(g)
        n_dev, n_val = round(n * SHARES[0][1]), round(n * SHARES[1][1])
        out["dev"] += g[:n_dev]
        out["val"] += g[n_dev:n_dev + n_val]
        out["test"] += g[n_dev + n_val:]
    for name in out:
        out[name].sort(key=lambda it: it["id"])
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", help="directory holding the authored *_cases.json files")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--sets", default=",".join(SETS), help="which authored sets to split now (each is sealed once)")
    args = ap.parse_args(argv)
    manifest_path = DATA / "MANIFEST.json"
    if args.verify:
        manifest = json.loads(manifest_path.read_text())
        bad = [f for f, h in manifest["files"].items() if _sha(DATA / f) != h]
        print("splits match the manifest" if not bad else "changed since sealing: " + ", ".join(bad))
        return 1 if bad else 0
    manifest = (json.loads(manifest_path.read_text()) if manifest_path.exists() else
                {"seed": SEED, "shares": dict(SHARES), "sources": {}, "files": {}, "counts": {}, "sealed": {}})
    src = Path(args.source)
    DATA.mkdir(parents=True, exist_ok=True)
    for name in [n for n in args.sets.split(",") if n]:
        if name in manifest["sealed"]:
            raise SystemExit(f"{name} is already sealed; a new authored set goes into a new version.")
        file, key, stratum = SETS[name]
        raw = json.loads((src / file).read_text())
        manifest["sources"][file] = _sha(src / file)
        parts = split(raw[key], stratum)
        for part, items in parts.items():
            out = DATA / f"{name}_{part}.json"
            out.write_text(json.dumps({"set": name, "split": part, key: items}, ensure_ascii=False, indent=1) + "\n")
            manifest["files"][out.name] = _sha(out)
            manifest["counts"][out.name] = len(items)
        if raw.get("author_note"):
            manifest.setdefault("author_notes", {})[name] = raw["author_note"]
        import datetime as dt

        manifest["sealed"][name] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    manifest_path.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(manifest["counts"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
