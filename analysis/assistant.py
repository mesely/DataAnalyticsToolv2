"""The Decision studio's question pipeline (AW-24), one stage per responsibility:

    question → guard → intent (local classifier, or the model when the routing table says so)
             → summary / products / countries : deterministic computation + numeric claim check   (worker.explain)
             → network                          : co-purchase computation on the current graph      (network_qa)
             → temporal                         : monthly series facts, partial periods named        (here)
             → knowledge                        : context-card retrieval, extractive answer, citations (knowledge_qa)
             → unsupported                      : the limitation card that says what is missing and the closest
                                                  analysis that works                               (knowledge_qa)
             → clarify / refuse                 : a short explanation, nothing computed
    → provenance (intent, method, definition, cards) on every answer.

No stage lets a model state a number: the model may only pick the intent; every figure is computed or quoted.
"""
from __future__ import annotations

from analysis import intents, knowledge_qa

VERSION = "assistant-pipeline-v1"
CANONICAL = {
    "tr": {"summary": "Satışları özetle", "products": "En çok satan ürün", "countries": "Ülke satışları"},
    "en": {"summary": "Summarize gross sales", "products": "Which product ranks first by gross sales?",
           "countries": "Which country ranks first by gross sales?"},
}


def decide_intent(request: dict) -> dict:
    """Local intent, or the model's when the routing table measured it better (guard refusal is always final)."""
    from analysis import llm_routing

    q = str(request.get("question") or "")
    local = intents.classify(q)
    if local["intent"] == "refuse" or request.get("use_llm") is False:
        return {**local, "used": "local"}
    tau = llm_routing.entry("question_intent").get("tau", 0.5)  # chosen on the val split (analysis/evals/routing_table.py)
    if request.get("use_llm") is True or llm_routing.use_model("question_intent", local_ok=local["confidence"] >= tau):
        from analysis.llm import plan_intent

        key = llm_routing.cache_key("question_intent", q)
        plan = llm_routing.cache_get(key)
        if plan is None:
            plan = plan_intent(q)
            llm_routing.record_usage(plan.get("telemetry"))
            if plan["status"] == "planned":
                llm_routing.cache_put(key, plan)
        if plan["status"] in ("planned", "blocked"):
            return {"intent": plan["intent"], "method": "model", "used": "model", "version": "intent-system-v2",
                    "local": local["intent"], "telemetry": plan.get("telemetry") or {}}
        return {**local, "used": "local", "fallback": plan["status"], "http_status": plan.get("http_status")}
    return {**local, "used": "local"}


def _temporal(result: dict, en: bool) -> dict:
    """Monthly gross sales facts from the computed series; the partial last/first month is named, not compared."""
    from analysis.worker import period_coverage  # noqa: F401 - the same rule as the overview's partial months

    series = result.get("series") or []
    periods = {p["month"]: p for p in (result.get("scope") or {}).get("periods", [])}
    complete = [s for s in series if not periods.get(s["period"], {}).get("partial")]
    money = lambda p: f"£{p / 100:,.2f}" if en else ("£" + f"{p / 100:,.2f}".translate(str.maketrans(",.", ".,")))  # noqa: E731
    if len(complete) < 2:
        text = ("There are fewer than two complete months in this scope, so no change over time can be stated."
                if en else "Bu kapsamda iki tam ay yok; zaman içindeki değişim söylenemez.")
        return {"status": "clarify", "reason": "too_few_periods", "text": text, "mode": "deterministic"}
    first, last = complete[0], complete[-1]
    hi = max(complete, key=lambda s: (s["pence"], s["period"]))
    lo = min(complete, key=lambda s: (s["pence"], s["period"]))
    change = (last["pence"] - first["pence"]) / first["pence"] if first["pence"] else None
    partial = [m for m, p in periods.items() if p.get("partial")]
    pct = (f"{change * 100:+.1f}%" if en else f"%{change * 100:+.1f}".replace(".", ",")) if change is not None else "—"
    if en:
        text = (f"Gross sales by complete month: highest {hi['period']} ({money(hi['pence'])}), lowest {lo['period']} "
                f"({money(lo['pence'])}); from {first['period']} ({money(first['pence'])}) to {last['period']} "
                f"({money(last['pence'])}) the change is {pct}.")
        if partial:
            text += f" Partial months left out of the comparison: {', '.join(sorted(partial))}."
        text += " For a trend line, a moving average or a control band, open the monthly chart in the Chart studio."
    else:
        text = (f"Tam aylara göre brüt satış: en yüksek {hi['period']} ({money(hi['pence'])}), en düşük {lo['period']} "
                f"({money(lo['pence'])}); {first['period']} ({money(first['pence'])}) ile {last['period']} "
                f"({money(last['pence'])}) arasındaki değişim {pct}.")
        if partial:
            text += f" Karşılaştırmaya katılmayan kısmi aylar: {', '.join(sorted(partial))}."
        text += " Trend çizgisi, hareketli ortalama veya kontrol bandı için aylık grafiği Grafik stüdyosunda açın."
    return {"status": "verified", "reason": "computed_series", "text": text, "mode": "deterministic",
            "evidence": {"first": first, "last": last, "highest": hi, "lowest": lo, "partial": sorted(partial)}}


def _network(request: dict, result: dict, en: bool) -> dict:
    from analysis import network_qa
    from analysis.worker import meta

    if "graph" not in result:
        from analysis.worker import graph

        result["graph"] = graph(request)
    g = result.get("graph") or {}
    plan = network_qa.local_plan(str(request["question"]), g.get("nodes") or [])
    if plan["query"] in ("clarify",):
        plan = {"query": "strongest_pairs", "k": 5, "product": None, "month": None}
    m = meta(request["dataset"])
    plan = network_qa.validate_plan(plan, g.get("nodes") or [], network_qa._months(m))
    text, nodes, edges = network_qa._compute(plan, g, request, m, en)
    return {"status": "verified" if plan["query"] != "unsupported" else "cannot_verify", "reason": "computed_network",
            "text": text, "mode": "deterministic", "network": {"plan": plan, "highlight": {"nodes": nodes, "edges": edges}}}


def answer(request: dict, result: dict) -> tuple[dict | None, dict | None]:
    """(the answer object shown in the Decision studio with its provenance, the intent decision)."""
    from analysis.worker import explain, metric_definition

    q = str(request.get("question") or "").strip()
    if not q:
        return None, None
    en = knowledge_qa._lang(q, request.get("locale", "tr")) == 1  # answer in the question's language
    decision = decide_intent(request)
    intent = decision["intent"]
    out: dict
    if intent == "refuse":
        out = explain(request, result) or {}
        if out.get("status") != "refused":
            out = {"status": "refused", "reason": "prompt_injection", "mode": "deterministic",
                   "text": ("This request is outside the safe analysis boundary. Ask about the data, its measures or "
                            "product relationships." if en else
                            "Bu istek güvenli analiz sınırları dışında. Veri, metrik veya ürün ilişkileri hakkında sorabilirsiniz.")}
    elif intent in ("knowledge", "unsupported"):
        k = knowledge_qa.answer(q, "en" if en else "tr")
        if k["status"] == "answered":
            out = {"status": "answered" if intent == "knowledge" else "cannot_verify",
                   "reason": "knowledge_card" if intent == "knowledge" else "unsupported_metric_or_causality",
                   "text": k["text"], "mode": "retrieved", "citations": k["citations"], "retrieval": {
                       "version": k["version"], "score": k["score"], "retrieved": k["retrieved"],
                       "corpus_sha256": k["corpus_sha256"]}}
        else:
            out = {"status": "clarify", "reason": "no_knowledge_card", "text": k["text"], "mode": "retrieved",
                   "citations": [], "retrieval": {"version": k["version"], "retrieved": k["retrieved"]}}
    elif intent == "network":
        out = _network(request, result, en)
    elif intent == "temporal":
        out = _temporal(result, en)
    elif intent == "clarify":
        local = explain(request, result) or {}
        out = local if local.get("status") == "clarify" else {
            "status": "clarify", "reason": "ambiguous_reference", "mode": "deterministic",
            "text": ("Which measure, period or product do you mean? For example: 'total gross sales', 'best-selling "
                     "product', 'which country sells most', 'how did sales change month by month'." if en else
                     "Hangi ölçüyü, dönemi veya ürünü kastediyorsunuz? Örneğin: 'toplam brüt satış', 'en çok satan ürün', "
                     "'en çok satan ülke', 'satışlar aydan aya nasıl değişti'.")}
    else:  # summary / products / countries: computed and checked against the result (worker.explain)
        out = explain(request, result) or {}
        if out.get("status") != "verified":
            out = explain({**request, "question": CANONICAL["en" if en else "tr"][intent]}, result) or {}
            if out.get("status") == "verified":
                out["mode"] = "intent-plan-verified-facts"
    if decision.get("used") == "model" and out.get("status") == "verified":
        out["mode"] = "model-plan-verified-facts"  # the model chose the question; every figure is computed
    out["intent"] = intent
    out["pipeline"] = {"version": VERSION, "intent": intent, "intent_method": decision.get("method"),
                       "intent_used": decision.get("used"), "confidence": decision.get("confidence"),
                       "definition": metric_definition(request)}
    if decision.get("fallback"):
        out["pipeline"]["fallback"] = decision["fallback"]
    return out, decision
