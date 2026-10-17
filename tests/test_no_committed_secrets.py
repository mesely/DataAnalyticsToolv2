"""No provider credential may be tracked by Git (keys live in analysis/.local or the server environment).

Patterns cover the providers this repository can call: Groq (gsk_), Hugging Face (hf_), OpenAI-style (sk-),
OpenRouter (sk-or-v1-). Test fixtures build fake keys at runtime, so no literal key-shaped string is committed.
"""
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PATTERN = re.compile(rb"(?<![A-Za-z0-9_])(?:gsk_[A-Za-z0-9]{40,}|hf_[A-Za-z0-9]{30,}|sk-(?:or-v1-)?[A-Za-z0-9_-]{32,})")


def tracked_files():
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return [ROOT / p.decode() for p in out.split(b"\0") if p]


def test_no_provider_key_is_tracked():
    hits = []
    for path in tracked_files():
        if not path.is_file() or path.stat().st_size > 5_000_000:
            continue
        for m in PATTERN.finditer(path.read_bytes()):
            hits.append(f"{path.relative_to(ROOT)}: {m.group()[:6].decode()}…")  # never print the key itself
    assert not hits, "provider keys are tracked by Git:\n" + "\n".join(hits)


def test_saved_provider_files_are_ignored():
    for name in ("groq-provider.json", "hf-provider.json", "llama-endpoint.json"):
        r = subprocess.run(["git", "check-ignore", "-q", f"analysis/.local/{name}"], cwd=ROOT)
        assert r.returncode == 0, f"analysis/.local/{name} is not ignored by Git"
