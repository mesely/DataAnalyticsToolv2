"""v3 G6 / AW-18: the routing rule, the administrator's local-only policy, the daily budget and the cache."""

import json

import pytest

from analysis import llm_routing
from analysis.llm_eval import routing as R


def row(acc, records, label="MEASURED"):
    done = [r for r in records if r["correct"] is not None]
    return {"label": label, "summary": {"n": len(records), "answered": len(done),
                                        "accuracy": sum(r["correct"] for r in done) / len(done) if done else None},
            "records": records}


def recs(pattern):
    return [{"id": f"x{i}", "correct": c} for i, c in enumerate(pattern)]


def test_model_must_win_by_five_points():
    local = row(None, recs([True] * 80 + [False] * 20))
    assert R.decide("t", local, row(None, recs([True] * 85 + [False] * 15)))["method"] == "model"
    assert R.decide("t", local, row(None, recs([True] * 84 + [False] * 16)))["method"] != "model"


def test_tie_goes_to_local_unless_the_model_covers_local_misses():
    local = row(None, recs([True] * 8 + [False] * 4))
    covers = row(None, recs([False] * 3 + [True] * 5 + [True] * 3 + [False]))  # same total, rescues 3 of 4 misses
    assert R.decide("t", local, covers)["method"] == "local_then_model"
    misses = row(None, recs([True] * 8 + [False] * 4))
    assert R.decide("t", local, misses)["method"] == "local"


def test_unmeasured_or_blocked_model_never_wins():
    local = row(None, recs([False] * 10))
    blocked = row(None, recs([True] * 5) + [{"id": "x9", "correct": None}], label="BLOCKED")
    assert R.decide("t", local, blocked)["method"] == "local"


def test_table_defaults_and_unknown_methods(monkeypatch, tmp_path):
    path = tmp_path / "llm_routing.json"
    monkeypatch.setattr(llm_routing, "TABLE", path)
    assert llm_routing.entry("chart_plan")["method"] == "local"  # no table: local
    path.write_text(json.dumps({"tasks": {"chart_plan": {"method": "sometimes"}, "studio_route": {"method": "model"}}}))
    assert llm_routing.entry("chart_plan")["method"] == "local"
    assert llm_routing.entry("studio_route")["method"] == "model"


@pytest.fixture()
def configured(monkeypatch, tmp_path):
    monkeypatch.setattr("analysis.llm.status", lambda: {"configured": True, "model": "openai/gpt-oss-20b"})
    monkeypatch.setattr(llm_routing, "TABLE", tmp_path / "t.json")
    (tmp_path / "t.json").write_text(json.dumps({"tasks": {"studio_route": {"method": "model"},
                                                           "chart_plan": {"method": "local_then_model"}}}))
    monkeypatch.delenv("CONTEXT_LLM_EXTERNAL", raising=False)


def test_policy_budget_and_provider_gate_the_model(configured, monkeypatch):
    from analysis import llm

    assert llm_routing.use_model("studio_route")
    assert not llm_routing.use_model("chart_plan") and llm_routing.use_model("chart_plan", local_ok=False)
    monkeypatch.setenv("CONTEXT_LLM_EXTERNAL", "off")
    assert llm_routing.availability() == "policy_local_only" and not llm_routing.use_model("studio_route")
    monkeypatch.delenv("CONTEXT_LLM_EXTERNAL")
    (llm.LOCAL / "llm-policy.json").write_text(json.dumps({"external": False}))
    assert not llm_routing.use_model("studio_route")
    (llm.LOCAL / "llm-policy.json").write_text(json.dumps({"daily_tokens": 1000}))
    llm_routing.record_usage({"total_tokens": 600})
    assert llm_routing.use_model("studio_route")
    llm_routing.record_usage({"total_tokens": 600})
    assert llm_routing.tokens_today() == 1200 and llm_routing.availability() == "daily_budget"
    r = llm_routing.receipt("studio_route", "local")
    assert r["unavailable"] == "daily_budget" and r["method"] == "model"


def test_cache_is_keyed_by_task_model_and_input(configured):
    a = llm_routing.cache_key("chart_plan", "son 6 ay", {"metric": "orders"})
    assert a != llm_routing.cache_key("chart_plan", "son 6 ay", {"metric": "units"})
    assert a != llm_routing.cache_key("studio_route", "son 6 ay", {"metric": "orders"})
    assert llm_routing.cache_get(a) is None
    llm_routing.cache_put(a, {"status": "planned"})
    assert llm_routing.cache_get(a) == {"status": "planned"}


def test_studio_route_uses_the_model_when_the_table_says_so(configured, monkeypatch):
    from analysis.worker import handle

    seen = []
    monkeypatch.setattr("analysis.llm.plan_studio", lambda text: seen.append(text) or {"status": "planned", "studio": "decision", "telemetry": {"total_tokens": 10}})
    out = handle({"action": "route", "text": "son 6 ay"})
    assert out["studio"] == "decision" and out["routing"]["used"] == "model" and seen == ["son 6 ay"]
    handle({"action": "route", "text": "son 6 ay"})
    assert seen == ["son 6 ay"]  # validated plan served from the cache
    monkeypatch.setattr("analysis.llm.plan_studio", lambda text: {"status": "invalid_plan"})
    fb = handle({"action": "route", "text": "Almanya ile Fransa'yı karşılaştır"})
    assert fb["studio"] == "chart" and fb["routing"]["used"] == "local" and fb["routing"]["fallback"] == "invalid_plan"


def test_without_a_provider_everything_is_local_and_says_so():
    from analysis.worker import handle

    out = handle({"action": "route", "text": "son 6 ay"})
    assert out["routing"]["used"] == "local"
