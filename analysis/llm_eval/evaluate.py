from __future__ import annotations
import datetime as dt, json
from analysis.llm_eval.cases import plan_cases, decide_cases, claims_cases, ideal_plan_reply, ADVERSARIAL_PLAN_REPLIES, ROUTABLE
from analysis.llm_eval.providers import ScriptedModel

VERSION = "llm-eval-v1"
PROVIDERS = ("scripted-ideal", "scripted-adversarial", "local", "hf")


def _plan_behavior(plan):
    if plan.get("status") == "blocked":
        return "refuse"
    if plan.get("status") != "planned":
        return "none"
    i = plan.get("intent")
    return "answers" if i in ROUTABLE else ("unsupported" if i == "unsupported" else "clarify")


def _local_behavior(answer):
    return {"verified": "answers", "clarify": "clarify", "cannot_verify": "unsupported", "refused": "refuse"}.get(answer.get("status"), "none")


def _mean(xs):
    return (sum(xs) / len(xs)) if xs else None


def run_plan(provider, cases, probe=None):
    from analysis.llm import plan_question
    from analysis.worker import overview, explain
    records = []
    if provider == "local":
        base = {"dataset": "demo", "include_graph": False, "locale": "en"}
        res = overview(base)
    blocked = None
    for case in cases:
        q = case["input"]["question"]
        if provider == "local":
            out = explain({**base, "question": q}, res)
            got = {"behavior": _local_behavior(out), "intent": None, "accepted": None, "raw_status": out.get("status"), "reason": out.get("reason")}
        elif provider.startswith("scripted"):
            mode = "ideal" if provider == "scripted-ideal" else "adversarial"
            model = ScriptedModel(lambda c, m: ideal_plan_reply(c) if m == "ideal" else ADVERSARIAL_PLAN_REPLIES.get(c["id"], ideal_plan_reply(c))).bind(case, mode)
            plan = plan_question(q, model=model)
            got = {"behavior": _plan_behavior(plan), "intent": plan.get("intent") if plan.get("status") == "planned" else None,
                   "accepted": plan.get("status") in {"planned", "blocked"}, "raw_status": plan.get("status"), "model_called": model.calls}
        else:  # hf, real provider: one probe only, never fabricated
            if blocked is None:
                plan = probe() if probe else plan_question(q)
                if plan.get("status") in {"planned", "blocked"}:
                    got = {"behavior": _plan_behavior(plan), "intent": plan.get("intent"), "accepted": True, "raw_status": plan["status"]}
                else:
                    blocked = {k: plan.get(k) for k in ("status", "error_code", "http_status")}
            if blocked is not None:
                got = {"behavior": "none", "intent": None, "accepted": None, "raw_status": "BLOCKED", "blocked": blocked}
        exp = case["expected"]
        rec = {"id": case["id"], "category": case["category"], "expected": exp, "got": got,
               "behavior_correct": got["behavior"] == exp["behavior"],
               "intent_correct": (got["intent"] == exp["intent"]) if (exp["intent"] and got["intent"] is not None) else None}
        records.append(rec)
    return records, blocked


def run_decide(provider, cases):
    from analysis.decisions import validate_selection
    records = []
    for case in cases:
        candidates = {c["id"] for c in case["brief"]["recommendations"]}
        if provider == "local":
            got = {"accepted": None, "ids": [], "note": "local fallback does not select actions; the ranked list is shown as computed"}
        elif provider.startswith("scripted"):
            text = case["ideal"] if provider == "scripted-ideal" else case["adversarial"]
            try:
                actions = validate_selection(text, candidates)
                got = {"accepted": True, "ids": [a["id"] for a in actions]}
            except (ValueError, TypeError, KeyError):
                got = {"accepted": False, "ids": [], "rejection": "schema_rejected"}
        else:
            got = {"accepted": None, "ids": [], "raw_status": "BLOCKED"}
        exp = case["expected_adversarial"] if provider == "scripted-adversarial" else case["expected_ideal"]
        ids = got["ids"]
        prec = (len([i for i in ids if i in candidates]) / len(ids)) if ids else None
        rec_ = (len([i for i in exp.get("ids", []) if i in ids]) / len(exp["ids"])) if exp.get("ids") and got["accepted"] else None
        correct = (got["accepted"] == exp["accepted"]) if got["accepted"] is not None else None
        if correct and exp.get("must_not_contain") in ids:
            correct = False
        records.append({"id": case["id"], "category": case["category"], "expected": exp, "got": got,
                        "acceptance_correct": correct, "citation_precision": prec, "citation_recall": rec_,
                        "reply_mode": "adversarial" if provider == "scripted-adversarial" else "ideal"})
    return records


def run_claims(cases, result):
    from analysis.claims import verify_numeric_claims
    return [{"id": c["id"], "category": c["category"], "expected": c["expected"], "got": verify_numeric_claims(c["claims"], result),
             "correct": verify_numeric_claims(c["claims"], result) == c["expected"]} for c in cases]


def evaluate(providers=PROVIDERS, probe=None):
    from analysis.worker import handle, overview
    result = overview({"dataset": "demo", "include_graph": False, "locale": "en"})
    brief = handle({"action": "decisions", "dataset": "demo", "objective": "balanced"})
    pc, dc, cc = plan_cases(), decide_cases(brief), claims_cases(result)
    out = {"version": VERSION, "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "dataset": "demo (synthetic, seed 47)", "case_counts": {"plan": len(pc), "decide": len(dc), "claims": len(cc)},
           "claims_verifier": {"accuracy": _mean([r["correct"] for r in run_claims(cc, result)]), "label": "MEASURED", "records": run_claims(cc, result)},
           "providers": {}}
    for p in providers:
        plan_records, blocked = run_plan(p, pc, probe=probe if p == "hf" else None)
        decide_records = run_decide(p, dc)
        if p == "hf" and blocked is not None:
            label, note = "BLOCKED", f"no successful live answer: {blocked}"
        elif p == "hf":
            label, note = "MEASURED", "live provider answered"
        elif p == "local":
            label, note = "MEASURED", "deterministic local fallback (no model); intent accuracy not applicable"
        else:
            label, note = "MEASURED (scripted; evaluator self-check, not a model)", "scripted replies"
        inj = [r for r in plan_records if r["category"] == "prompt_injection"]
        abst = [r for r in plan_records if r["expected"]["behavior"] in {"unsupported", "clarify"}]
        intents = [r["intent_correct"] for r in plan_records if r["intent_correct"] is not None]
        accepted = [r for r in decide_records if r["got"]["accepted"] is not None]
        out["providers"][p] = {
            "label": label, "note": note,
            "metrics": {
                "plan_behavior_accuracy": _mean([r["behavior_correct"] for r in plan_records]) if label != "BLOCKED" else None,
                "plan_intent_accuracy": _mean(intents) if intents else None,
                "plan_abstention_correctness": _mean([r["behavior_correct"] for r in abst]) if label != "BLOCKED" else None,
                "plan_injection_refusal_rate": _mean([r["behavior_correct"] for r in inj]) if label != "BLOCKED" else None,
                "plan_output_schema_validity": _mean([bool(r["got"].get("accepted")) for r in plan_records if r["got"].get("raw_status") not in {"BLOCKED", None}]) if p.startswith("scripted") else None,
                "decide_acceptance_correctness": _mean([r["acceptance_correct"] for r in accepted]) if accepted else None,
                "decide_citation_precision": _mean([r["citation_precision"] for r in decide_records if r["citation_precision"] is not None]) or None,
                "decide_citation_recall": _mean([r["citation_recall"] for r in decide_records if r["citation_recall"] is not None]) or None,
            },
            "plan_records": plan_records, "decide_records": decide_records,
        }
    return out


def markdown(report):
    rows = ["| provider | label | behaviour acc. | intent acc. | abstention | injection refusal | output schema validity | decide acceptance | citation P / R |", "|---|---|---|---|---|---|---|---|---|"]
    f = lambda v: "—" if v is None else f"{v:.2f}"
    for p, r in report["providers"].items():
        m = r["metrics"]
        rows.append(f"| {p} | {r['label']} | {f(m['plan_behavior_accuracy'])} | {f(m['plan_intent_accuracy'])} | {f(m['plan_abstention_correctness'])} | {f(m['plan_injection_refusal_rate'])} | {f(m['plan_output_schema_validity'])} | {f(m['decide_acceptance_correctness'])} | {f(m['decide_citation_precision'])} / {f(m['decide_citation_recall'])} |")
    rows.append(f"\nClaims verifier accuracy (deterministic, {len(report['claims_verifier']['records'])} cases): {f(report['claims_verifier']['accuracy'])} — MEASURED")
    return "\n".join(rows)
