"""Stable source/dependency fingerprint; excludes data, secrets, machine paths and runtime outputs."""
from pathlib import Path
import hashlib
ROOT = Path(__file__).resolve().parent.parent

def fingerprint():
    files = sorted(p for p in (ROOT / "analysis").rglob("*.py") if ".local" not in p.parts and "tests" not in p.parts)
    files += [ROOT / p for p in ["analysis/requirements.txt", "constraints.txt", "pyproject.toml", "core/package-lock.json", "core/src/workbench.ts"]]
    digest = hashlib.sha256()
    for p in files:
        if p.is_file():
            digest.update(str(p.relative_to(ROOT)).encode() + b"\0" + p.read_bytes() + b"\0")
    return {"sha256": digest.hexdigest(), "scheme": "source-dependencies-v1", "files": len(files)}
