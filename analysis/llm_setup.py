"""Configure and check the optional language-model provider without a secret ever appearing on screen or in Git.

    .venv/bin/python -m analysis.llm_setup                    # Groq (default): prompt for the key (hidden), verify, save
    GROQ_API_KEY=... .venv/bin/python -m analysis.llm_setup   # Groq, key from the environment (CI, servers)
    .venv/bin/python -m analysis.llm_setup --check            # verify the saved Groq configuration only
    .venv/bin/python -m analysis.llm_setup --endpoint http://127.0.0.1:8080/v1 --model llama-3.1-8b-instruct
                                                              # self-hosted OpenAI-compatible server (llama.cpp, Ollama, vLLM)
    .venv/bin/python -m analysis.llm_setup --provider hf      # Hugging Face Inference Providers

Groq: the key is checked against the model list and one minimal JSON completion, then saved to
analysis/.local/groq-provider.json with mode 0600 (ignored by Git). The default model is openai/gpt-oss-20b.
The script reports only "ready" or the exact gate (401 key rejected, 404 model not on this account, 429 rate limit).

Hugging Face: the token is checked against the account API and one completion, and saved to
analysis/.local/hf-provider.json (mode 0600). HTTP 402 means the account has no Inference Provider credits.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

import httpx

CONFIG = Path(__file__).resolve().parent / ".local" / "hf-provider.json"
GROQ_CONFIG = Path(__file__).resolve().parent / ".local" / "groq-provider.json"
ENDPOINT = Path(__file__).resolve().parent / ".local" / "llama-endpoint.json"
MODEL = "meta-llama/Llama-3.3-70B-Instruct"
ROUTER = "https://router.huggingface.co/v1/chat/completions"


def account(token: str) -> dict:
    r = httpx.get("https://huggingface.co/api/whoami-v2", headers={"Authorization": f"Bearer {token}"}, timeout=20)
    if r.status_code != 200:
        return {"ok": False, "http_status": r.status_code}
    d = r.json()
    auth = (d.get("auth") or {}).get("accessToken") or {}
    return {"ok": True, "name": d.get("name"), "token_role": auth.get("role"), "pro": bool(d.get("isPro"))}


def probe(token: str, model: str) -> dict:
    """One tiny completion; returns the provider's status without the response body."""
    body = {"model": model, "messages": [{"role": "user", "content": "Reply with OK."}], "max_tokens": 2, "temperature": 0}
    try:
        r = httpx.post(ROUTER, headers={"Authorization": f"Bearer {token}"}, json=body, timeout=30)
    except httpx.HTTPError as exc:
        return {"ready": False, "reason": f"network error: {type(exc).__name__}"}
    if r.status_code == 200:
        return {"ready": True, "http_status": 200}
    reasons = {
        401: "token rejected (wrong or revoked)",
        403: "token lacks the 'Make calls to Inference Providers' permission",
        402: "no Inference Provider credits on this account: add credits or PRO at huggingface.co/settings/billing",
        429: "rate limited; try again later",
    }
    return {"ready": False, "http_status": r.status_code, "reason": reasons.get(r.status_code, "provider error")}


def probe_endpoint(base_url: str, model: str, api_key: str) -> dict:
    """One tiny completion against a self-hosted OpenAI-compatible server."""
    body = {"model": model, "messages": [{"role": "user", "content": "Reply with OK."}], "max_tokens": 2, "temperature": 0}
    try:
        r = httpx.post(base_url.rstrip("/") + "/chat/completions", json=body, timeout=60,
                       headers={"Authorization": f"Bearer {api_key or 'self-hosted'}"})
    except httpx.HTTPError as exc:
        return {"ready": False, "reason": f"cannot reach {base_url} ({type(exc).__name__})"}
    if r.status_code == 200:
        return {"ready": True, "http_status": 200}
    return {"ready": False, "http_status": r.status_code, "reason": "the server answered with an error; check the model name"}


def setup_endpoint(base_url: str, model: str) -> int:
    if "llama" not in model.lower():
        print("The model name must name a Llama build (for example llama-3.1-8b-instruct).")
        return 1
    api_key = os.environ.get("LLAMA_API_KEY", "")
    status = probe_endpoint(base_url, model, api_key)
    print(f"Endpoint {base_url} · model {model}: {'ready' if status['ready'] else 'not ready'}"
          + (f" (HTTP {status['http_status']})" if status.get("http_status") else "")
          + (f" — {status['reason']}" if status.get("reason") else ""))
    ENDPOINT.parent.mkdir(exist_ok=True)
    fd = os.open(ENDPOINT, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"base_url": base_url, "model": model, **({"api_key": api_key} if api_key else {})}, f)
    os.chmod(ENDPOINT, 0o600)
    print("Saved analysis/.local/llama-endpoint.json (mode 0600, ignored by Git); it takes precedence over Groq and Hugging Face.")
    if status["ready"]:
        print("Next: .venv/bin/python -m analysis.llm_eval --providers local,live --out docs/evidence/verification/llm-eval-live.json")
    return 0 if status["ready"] else 2


def _save(path: Path, value: dict) -> None:
    path.parent.mkdir(exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(value, f)
    os.chmod(path, 0o600)


def probe_groq(key: str, model: str) -> dict:
    """Model availability, then one tiny JSON completion; returns statuses only, never a response body."""
    from analysis.llm import GROQ_BASE

    headers = {"Authorization": f"Bearer {key}"}
    try:
        r = httpx.get(GROQ_BASE + "/models", headers=headers, timeout=20)
        if r.status_code != 200:
            return {"ready": False, "http_status": r.status_code,
                    "reason": "key rejected (wrong or revoked)" if r.status_code == 401 else "provider error"}
        if model not in {m.get("id") for m in r.json().get("data", [])}:
            return {"ready": False, "http_status": 404, "reason": f"{model} is not available to this key"}
        body = {"model": model, "temperature": 0, "max_tokens": 200, "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": 'Return the JSON object {"ok": true}.'},
                             {"role": "user", "content": "ready?"}]}
        if model.startswith("openai/gpt-oss-"):
            body.update(reasoning_effort="low", include_reasoning=False)
        r = httpx.post(GROQ_BASE + "/chat/completions", headers=headers, json=body, timeout=30)
    except httpx.HTTPError as exc:
        return {"ready": False, "reason": f"network error: {type(exc).__name__}"}
    if r.status_code == 200:
        return {"ready": True, "http_status": 200}
    reasons = {401: "key rejected (wrong or revoked)", 429: "rate limited; try again in a minute"}
    return {"ready": False, "http_status": r.status_code, "reason": reasons.get(r.status_code, "provider error")}


def setup_groq(model: str, check: bool) -> int:
    from analysis.llm import _GROQ_MODEL

    if not _GROQ_MODEL.fullmatch(model):
        print(f"{model} is not one of the evaluated Groq models (openai/gpt-oss-20b, openai/gpt-oss-120b).")
        return 1
    if check:
        if not GROQ_CONFIG.exists():
            print("No saved Groq configuration; run without --check.")
            return 1
        cfg = json.loads(GROQ_CONFIG.read_text())
        key, model = cfg.get("api_key", ""), cfg.get("model", model)
    else:
        key = os.environ.get("GROQ_API_KEY", "").strip() or getpass.getpass("Groq API key (input hidden): ").strip()
    if not key.startswith("gsk_"):
        print("That does not look like a Groq API key (expected the gsk_ prefix).")
        return 1
    status = probe_groq(key, model)
    print(f"Groq · {model}: {'ready' if status['ready'] else 'not ready'}"
          + (f" (HTTP {status['http_status']})" if status.get("http_status") else "")
          + (f" — {status['reason']}" if status.get("reason") else ""))
    if not check and status["ready"]:
        _save(GROQ_CONFIG, {"api_key": key, "model": model})
        print("Saved analysis/.local/groq-provider.json (mode 0600, ignored by Git).")
    if status["ready"]:
        print("Next: .venv/bin/python -m analysis.llm_eval --providers local,live --out docs/evidence/verification/llm-eval-live.json")
    return 0 if status["ready"] else 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--provider", choices=("groq", "hf"), default="groq", help="hosted provider (default: groq)")
    ap.add_argument("--check", action="store_true", help="verify the saved configuration without asking for a key")
    ap.add_argument("--model", default=None, help="model id (Groq default: openai/gpt-oss-20b; Hugging Face: %s)" % MODEL)
    ap.add_argument("--endpoint", default=None, help="self-hosted OpenAI-compatible base URL, e.g. http://127.0.0.1:8080/v1")
    a = ap.parse_args(argv)
    if a.endpoint:
        return setup_endpoint(a.endpoint, a.model or "llama-3.1-8b-instruct")
    if a.provider == "groq":
        from analysis.llm import GROQ_DEFAULT_MODEL

        return setup_groq(a.model or os.environ.get("GROQ_MODEL", "") or GROQ_DEFAULT_MODEL, a.check)
    a.model = a.model or os.environ.get("HF_MODEL", MODEL)
    if a.check:
        if not CONFIG.exists():
            print("No saved configuration; run without --check.")
            return 1
        cfg = json.loads(CONFIG.read_text())
        token, model = cfg.get("token", ""), cfg.get("model", a.model)
    else:
        token = getpass.getpass("Hugging Face token (input hidden): ").strip()
        model = a.model
    if not token.startswith("hf_"):
        print("That does not look like a Hugging Face token (expected the hf_ prefix).")
        return 1
    who = account(token)
    if not who["ok"]:
        print(f"Account check failed (HTTP {who['http_status']}).")
        return 1
    print(f"Account: {who['name']} · token type: {who['token_role']} · PRO: {'yes' if who['pro'] else 'no'}")
    status = probe(token, model)
    print(f"Provider: {'ready' if status['ready'] else 'not ready'}"
          + (f" (HTTP {status['http_status']})" if status.get("http_status") else "")
          + (f" — {status['reason']}" if status.get("reason") else ""))
    if not a.check:
        CONFIG.parent.mkdir(exist_ok=True)
        fd = os.open(CONFIG, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump({"token": token, "model": model}, f)
        os.chmod(CONFIG, 0o600)
        print(f"Saved to {CONFIG.relative_to(Path.cwd()) if CONFIG.is_relative_to(Path.cwd()) else CONFIG} (mode 0600, ignored by Git).")
    if status["ready"]:
        print("Next: .venv/bin/python -m analysis.llm_eval --providers local,live --out docs/evidence/verification/llm-eval-live.json")
    return 0 if status["ready"] else 2


if __name__ == "__main__":
    sys.exit(main())
