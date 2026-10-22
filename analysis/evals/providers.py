"""Chat models for the benchmarks: any configured provider and model, chosen per run (keys never printed)."""
from __future__ import annotations

import json
from pathlib import Path

from analysis import llm

SPECS = {
    "gpt-oss-20b": ("groq", "openai/gpt-oss-20b"),
    "gpt-oss-120b": ("groq", "openai/gpt-oss-120b"),
    "qwen3.8-27b": ("groq", "qwen/qwen3.8-27b"),
    "llama-3.3-70b-hf": ("huggingface", "meta-llama/Llama-3.3-70B-Instruct"),
}


def _saved(name: str) -> dict:
    path = Path(llm.LOCAL) / name
    try:
        return json.loads(path.read_text()) if path.exists() and not path.stat().st_mode & 0o077 else {}
    except (OSError, ValueError):
        return {}


def available(name: str) -> bool:
    kind, _ = SPECS[name]
    return bool(_saved("groq-provider.json").get("api_key") if kind == "groq" else _saved("hf-provider.json").get("token"))


def chat(name: str, max_tokens: int):
    kind, model = SPECS[name]
    if kind == "groq":
        creds = {"kind": "groq", "base_url": llm.GROQ_BASE, "model": model, "token": _saved("groq-provider.json")["api_key"]}
    else:
        creds = {"kind": "huggingface", "base_url": llm.HF_ROUTER, "model": model, "token": _saved("hf-provider.json")["token"]}
    return llm.build_chat_model(llm.settings_for(creds, max_tokens))
