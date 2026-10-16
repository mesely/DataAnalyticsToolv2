"""LLM evaluation harness: evaluator self-checks, deterministic local baseline, BLOCKED labelling for the live provider.
None of these numbers is a real-model accuracy."""
import json
from analysis.llm_eval.evaluate import evaluate, markdown, run_plan
from analysis.llm_eval.cases import plan_cases, PLAN_CASES


def test_scripted_ideal_scores_perfectly_and_adversarial_is_penalised():
    r = evaluate(("scripted-ideal", "scripted-adversarial"))
    ideal = r["providers"]["scripted-ideal"]["metrics"]
    assert ideal["plan_behavior_accuracy"] == 1 and ideal["plan_intent_accuracy"] == 1
    assert ideal["plan_injection_refusal_rate"] == 1 and ideal["plan_abstention_correctness"] == 1
    assert ideal["decide_acceptance_correctness"] == 1 and ideal["decide_citation_precision"] == 1 and ideal["decide_citation_recall"] == 1
    bad = r["providers"]["scripted-adversarial"]["metrics"]
    assert bad["plan_behavior_accuracy"] < 0.7 and bad["plan_output_schema_validity"] < 0.8
    assert bad["decide_acceptance_correctness"] == 1  # the validator rejected every designed-bad reply
    assert bad["decide_citation_precision"] is None   # nothing was accepted, so nothing to cite
    assert r["claims_verifier"]["accuracy"] == 1
    assert "MEASURED (scripted" in r["providers"]["scripted-ideal"]["label"]


def test_local_fallback_baseline_is_deterministic_and_weaker_than_ideal():
    r = evaluate(("local",))
    m = r["providers"]["local"]["metrics"]
    assert m["plan_behavior_accuracy"] == 13 / 19
    assert m["plan_abstention_correctness"] == 5 / 6 and m["plan_injection_refusal_rate"] == 1
    assert m["plan_intent_accuracy"] is None and m["decide_acceptance_correctness"] is None
    assert evaluate(("local",))["providers"]["local"]["metrics"] == m


def test_live_provider_is_labelled_blocked_without_fabricated_metrics():
    probe = lambda: {"status": "unavailable", "error_code": "invalid_request", "http_status": 402}
    r = evaluate(("hf",), probe=probe)
    hf = r["providers"]["hf"]
    assert hf["label"] == "BLOCKED" and "402" in hf["note"]
    assert all(v is None for v in hf["metrics"].values())
    text = json.dumps(r)
    assert "hf_" not in text and "Bearer" not in text
    assert "BLOCKED" in markdown(r)


def test_plan_cases_cover_every_required_category():
    cats = {c["category"] for c in plan_cases()}
    assert {"numeric_lookup", "ranking", "trend_interpretation", "chart_grounding", "unsupported_claim_rejection",
            "missing_data_behavior", "prompt_injection", "adversarial_context"} <= cats
    assert len(PLAN_CASES) == len({c[0] for c in PLAN_CASES})


def test_injection_cases_never_reach_a_scripted_model():
    records, _ = run_plan("scripted-ideal", [c for c in plan_cases() if c["category"] == "prompt_injection"])
    assert all(r["got"]["model_called"] == 0 and r["got"]["behavior"] == "refuse" for r in records)
