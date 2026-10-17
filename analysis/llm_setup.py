"""Configure and check the optional Llama provider without a secret ever appearing on screen or in Git.

    .venv/bin/python -m analysis.llm_setup --endpoint http://127.0.0.1:8080/v1 --model llama-3.1-8b-instruct
                                                      # self-hosted OpenAI-compatible server (llama.cpp, Ollama, vLLM)
    .venv/bin/python -m analysis.llm_setup            # Hugging Face: prompt for a token (hidden), verify, save
    .venv/bin/python -m analysis.llm_setup --check    # verify the saved Hugging Face configuration only

The token is read with getpass, checked against the Hugging Face account API and one minimal chat completion, and
saved to analysis/.local/hf-provider.json with mode 0600 (ignored by Git). The script reports only the account name,
the token's permission type and the provider's answer: "ready", or the exact gate (for example HTTP 402, which means
the account has no Inference Provider credits — a new token does not change that; credits or PRO do).
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
    print("Saved analysis/.local/llama-endpoint.json (mode 0600, ignored by Git); it takes precedence over Hugging Face.")
    if status["ready"]:
        print("Next: .venv/bin/python -m analysis.llm_eval --providers local,hf --out docs/evidence/verification/llm-eval-live.json")
    return 0 if status["ready"] else 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="verify the saved configuration without asking for a token")
    ap.add_argument("--model", default=None, help="model id (Hugging Face default: %s)" % MODEL)
    ap.add_argument("--endpoint", default=None, help="self-hosted OpenAI-compatible base URL, e.g. http://127.0.0.1:8080/v1")
    a = ap.parse_args(argv)
    if a.endpoint:
        return setup_endpoint(a.endpoint, a.model or "llama-3.1-8b-instruct")
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
        print("Next: .venv/bin/python -m analysis.llm_eval --providers local,hf --out docs/evidence/verification/llm-eval-live.json")
    return 0 if status["ready"] else 2


if __name__ == "__main__":
    sys.exit(main())
