"""Groq as the hosted provider: configuration, request shape, rate limits, secrecy and the live-eval accounting.

The HTTP server is a stand-in for api.groq.com (fixed replies); it proves the wiring, not model accuracy. Model
accuracy is measured live by `python -m analysis.llm_eval --providers live` (docs/evidence/verification).
"""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from analysis import llm

FAKE_KEY = "gsk_" + "t" * 52  # shape of a Groq key; not a real one


class _Groq:
    """Answers POST /chat/completions from a queue of (status, content) pairs; the last one repeats."""

    def __init__(self, replies):
        self.requests, self.replies = [], list(replies)
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["content-length"])))
                outer.requests.append({"path": self.path, "body": body, "auth": self.headers.get("authorization")})
                status, content = outer.replies.pop(0) if len(outer.replies) > 1 else outer.replies[0]
                if status == 400:
                    payload = json.dumps({"error": {"message": "Failed to generate JSON. echo: " + FAKE_KEY,
                                                    "type": "invalid_request_error", "code": content}}).encode()
                    self.send_response(400)
                    self.send_header("content-type", "application/json")
                    self.send_header("content-length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                payload = json.dumps({"id": "x", "object": "chat.completion", "model": body["model"],
                                      "choices": [{"index": 0, "finish_reason": "stop",
                                                   "message": {"role": "assistant", "content": content,
                                                               "reasoning": "private chain of thought"}}],
                                      "usage": {"prompt_tokens": 300, "completion_tokens": 60, "total_tokens": 360}}
                                     if status == 200 else {"error": {"message": "Rate limit reached", "type": "tokens"}}).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                if status == 429:
                    self.send_header("retry-after", content or "0")
                self.send_header("content-length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *a):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/openai/v1"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()


@pytest.fixture
def groq(monkeypatch):
    servers = []

    def make(*replies, model=None):
        s = _Groq(replies)
        servers.append(s)
        monkeypatch.setattr(llm, "GROQ_BASE", s.url)
        monkeypatch.setenv("GROQ_API_KEY", FAKE_KEY)
        if model:
            monkeypatch.setenv("GROQ_MODEL", model)
        return s

    yield make
    for s in servers:
        s.httpd.shutdown()


def test_saved_groq_file_is_read_only_when_private(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "LOCAL", tmp_path)
    f = tmp_path / "groq-provider.json"
    f.write_text(json.dumps({"api_key": FAKE_KEY, "model": "openai/gpt-oss-20b"}))
    os.chmod(f, 0o644)
    assert llm.configuration() is None  # a world-readable key file is refused
    os.chmod(f, 0o600)
    st = llm.status()
    assert st["configured"] and st["endpoint"] == "groq" and st["model"] == "openai/gpt-oss-20b"
    assert st["label"] == "GPT-OSS 20B · Groq"
    assert FAKE_KEY not in json.dumps(st) and FAKE_KEY not in repr(llm.configuration())


@pytest.mark.parametrize("key,model,ok", [
    (FAKE_KEY, "openai/gpt-oss-20b", True),
    (FAKE_KEY, "openai/gpt-oss-120b", True),
    (FAKE_KEY, "some/unevaluated-model", False),
    ("sk-not-a-groq-key", "openai/gpt-oss-20b", False),
])
def test_groq_key_shape_and_model_allowlist(monkeypatch, key, model, ok):
    monkeypatch.setenv("GROQ_API_KEY", key)
    monkeypatch.setenv("GROQ_MODEL", model)
    assert (llm.configuration() is not None) is ok


def test_self_hosted_endpoint_takes_precedence_over_groq(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", FAKE_KEY)
    monkeypatch.setenv("LLAMA_BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("LLAMA_MODEL", "llama-3.1-8b-instruct")
    assert llm.status()["endpoint"] == "self-hosted"


def test_reasoning_model_gets_headroom_low_effort_and_json_mode(groq):
    server = groq((200, '{"intent":"countries","scope":"current_filters"}'))
    plan = llm.plan_question("Where do we sell most?")
    assert plan["status"] == "planned" and plan["intent"] == "countries"
    req = server.requests[0]
    assert req["path"] == "/openai/v1/chat/completions" and req["auth"] == "Bearer " + FAKE_KEY
    body = req["body"]
    assert body["model"] == "openai/gpt-oss-20b"
    assert body["reasoning_effort"] == "low" and body["include_reasoning"] is False
    assert body["response_format"] == {"type": "json_object"}
    assert body["max_tokens"] == 100 + llm.REASONING_HEADROOM and body["temperature"] == 0
    # telemetry is an allowlist: no reasoning text, no key, no headers
    assert "private chain of thought" not in json.dumps(plan) and FAKE_KEY not in json.dumps(plan)


def test_with_budget_keeps_headroom_for_every_caller(groq):
    groq((200, "{}"))
    cfg = llm.configuration()
    assert llm.with_budget(cfg, 300).max_tokens == 300 + llm.REASONING_HEADROOM
    assert llm.with_budget(cfg, 1200).max_tokens == 1200 + llm.REASONING_HEADROOM


def test_rate_limit_is_retried_then_answers(groq):
    server = groq((429, ""), (200, '{"intent":"summary","scope":"current_filters"}'))
    assert llm.plan_question("Give me a sales overview")["status"] == "planned"
    assert len(server.requests) == 2


def test_persistent_rate_limit_falls_back_without_a_crash(groq):
    groq((429, ""))
    plan = llm.plan_question("Give me a sales overview")
    assert plan["status"] == "unavailable" and plan["http_status"] == 429


def test_schema_violation_from_groq_is_rejected(groq):
    groq((200, '{"intent":"summary","scope":"current_filters","sql":"DROP TABLE x"}'))
    assert llm.plan_question("Give me a sales overview")["status"] == "invalid_plan"


def test_chart_studio_plans_with_groq_and_computes_locally(groq):
    from analysis.chart_studio import chart

    spec = {"version": 1, "metric": "orders", "dimension": "country", "chart": "bar", "start": None, "end": None,
            "countries": [], "split_by_country": False, "top_n": 5, "statistic": "none", "window": 3, "sort": "value_desc"}
    server = groq((200, json.dumps(spec)))
    r = chart({"dataset": "demo", "prompt": "orders by country, top 5", "use_llm": True, "locale": "en"})
    assert r["planner"]["source"] == "model" and r["spec"]["top_n"] == 5
    assert server.requests[0]["body"]["max_tokens"] == 300 + llm.REASONING_HEADROOM


def test_live_eval_counts_a_rejected_reply_as_wrong_not_as_an_outage():
    from analysis.llm_eval.evaluate import run_plan
    from analysis.llm_eval.cases import plan_cases

    cases = plan_cases()[:3]
    records, blocked = run_plan("live", cases, probe=lambda: {"status": "invalid_plan", "error_code": "schema_rejected"})
    assert blocked is None and all(r["got"]["raw_status"] == "invalid_plan" for r in records)
    assert not any(r["behavior_correct"] for r in records if r["expected"]["behavior"] != "none")


def test_setup_refuses_a_non_groq_key(monkeypatch, capsys):
    from analysis import llm_setup

    monkeypatch.setenv("GROQ_API_KEY", "hf_wrong_provider_token")
    assert llm_setup.main([]) == 1
    assert "gsk_" in capsys.readouterr().out


def test_live_usage_uses_nearest_rank_percentiles():
    from analysis.llm_eval.evaluate import _live_usage

    rows = [{"got": {"latency_ms": float(ms), "total_tokens": 10}} for ms in range(1, 21)]  # 1..20 ms
    u = _live_usage(rows, [{"latency_ms": None}])
    assert u == {"calls": 20, "latency_ms_median": 10.0, "latency_ms_p95": 19.0, "tokens_total": 200}
    assert _live_usage([])["latency_ms_median"] is None


def test_json_generation_failure_is_retried_once(groq):
    server = groq((400, "json_validate_failed"), (200, '{"intent":"summary","scope":"current_filters"}'))
    assert llm.plan_question("Give me a sales overview")["status"] == "planned"
    assert len(server.requests) == 2


def test_other_bad_requests_are_not_retried_and_leak_nothing(groq):
    server = groq((400, "something_else"))
    plan = llm.plan_question("Give me a sales overview")
    assert plan == {"status": "unavailable", "error_code": "invalid_request", "http_status": 400}
    assert len(server.requests) == 1 and FAKE_KEY not in json.dumps(plan)


@pytest.mark.parametrize("dataset", ["demo", "uci"])
def test_every_context_value_is_accepted_when_copied_verbatim(dataset):
    """Regression (AW-17 live run): the context carried raw floats (59858.674000000006 GBP, fractional pence), so
    GPT-OSS copying a supplied value exactly was rejected as an unsupported number."""
    import re
    from analysis.worker import handle
    from analysis import narrative

    brief = handle({"action": "decisions", "dataset": dataset, "objective": "balanced"})
    pk, xml = narrative.packet(brief), narrative.analysis_context_xml(brief)
    items = re.findall(r'<item id="([^"]+)"[^>]*unit="([^"]*)"[^>]*>([^<]*)</item>', xml)
    assert items
    for key, unit, value in items:
        marker = {"pence": " pence", "GBP": " GBP"}.get(unit, "")
        assert narrative.unsupported_numbers(f"{pk['evidence'][key]['measure']} {value}{marker}", [key], pk) == [], key


def test_daily_quota_falls_back_immediately_instead_of_waiting(groq):
    """Groq's free tier also has a tokens-per-day quota; its 429 asks for minutes. Waiting out the deadline only
    delays the local fallback, so the transport returns at once."""
    import time

    server = groq((429, "110"))
    started = time.monotonic()
    plan = llm.plan_question("Give me a sales overview")
    assert plan["status"] == "unavailable" and plan["http_status"] == 429
    assert time.monotonic() - started < 2 and len(server.requests) == 1
