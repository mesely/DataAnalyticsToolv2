"""Chart Studio planning evaluation (llm-eval-v2.2): does a planner turn a request into the right ChartSpec fields?

Each case is a request (Turkish or English), an optional base spec (refinements) and the fields the plan must set.
A case is correct when every expected field matches exactly; field accuracy counts fields individually. The same
cases score the deterministic local planner, scripted stand-ins (an evaluator self-check, not a model) and the live
provider (Groq, a self-hosted Llama server or Hugging Face). Every case is a real call; if the provider cannot be
reached, the row is BLOCKED and no accuracy is reported — a result is never inferred.
"""
from __future__ import annotations

import json

from analysis.llm_eval.providers import ScriptedModel

BASE_COMPARE = {"countries": ["Germany", "France"], "split_by_country": True, "start": "2011-07-01", "end": "2011-12-09"}

CASES = [
    # Subject and breakdown
    {"id": "c01", "prompt": "ülkelere göre sipariş sayısı", "expect": {"metric": "orders", "dimension": "country"}},
    {"id": "c02", "prompt": "orders by country", "expect": {"metric": "orders", "dimension": "country"}},
    {"id": "c03", "prompt": "ilk 5 ürün adet olarak", "expect": {"metric": "units", "dimension": "product", "top_n": 5}},
    {"id": "c04", "prompt": "top 5 products by units", "expect": {"metric": "units", "dimension": "product", "top_n": 5}},
    {"id": "c05", "prompt": "haftalık brüt satış", "expect": {"metric": "gross_sales", "dimension": "week"}},
    {"id": "c06", "prompt": "weekday breakdown of orders", "expect": {"metric": "orders", "dimension": "weekday"}},
    {"id": "c07", "prompt": "aylık ortalama sepet tutarı", "expect": {"metric": "aov", "dimension": "month"}},
    # Periods
    {"id": "c08", "prompt": "son 6 ay", "expect": {"start": "2011-07-01", "end": "2011-12-09"}},
    {"id": "c09", "prompt": "last 8 weeks", "expect": {"end": "2011-12-09"}},
    {"id": "c10", "prompt": "Q4 2011", "expect": {"start": "2011-10-01", "end": "2011-12-09"}},
    {"id": "c11", "prompt": "Mart 2011", "expect": {"start": "2011-03-01", "end": "2011-03-31"}},
    # Countries, comparison, exclusion
    {"id": "c12", "prompt": "Almanya ile Fransa'yı karşılaştır", "expect": {"countries": ["Germany", "France"], "split_by_country": True}},
    {"id": "c13", "prompt": "compare Germany and France", "expect": {"countries": ["Germany", "France"], "split_by_country": True}},
    {"id": "c14", "prompt": "ülkelere göre brüt satış, İngiltere hariç", "expect": {"dimension": "country", "exclude_countries": ["United Kingdom"]}},
    {"id": "c15", "prompt": "orders by country except United Kingdom and EIRE", "expect": {"metric": "orders", "dimension": "country", "exclude_countries": ["United Kingdom", "EIRE"]}},
    # Statistics
    {"id": "c16", "prompt": "aylık ortalama sepet, %95 güven aralığı", "expect": {"metric": "aov", "statistic": "ci95"}},
    {"id": "c17", "prompt": "average order by country with a 95% interval", "expect": {"metric": "aov", "dimension": "country", "statistic": "ci95"}},
    {"id": "c18", "prompt": "trend çizgisi ekle", "expect": {"statistic": "trend"}},
    {"id": "c19", "prompt": "add a 4-period moving average", "expect": {"statistic": "moving_average", "window": 4}},
    {"id": "c20", "prompt": "kontrol bandı göster", "expect": {"statistic": "control_band"}},
    # Refinements keep unmentioned fields
    {"id": "c21", "prompt": "hareketli ortalama ekle", "base": BASE_COMPARE, "expect": {"countries": ["Germany", "France"], "statistic": "moving_average"}},
    {"id": "c22", "prompt": "remove France", "base": BASE_COMPARE, "expect": {"countries": ["Germany"]}},
    {"id": "c23", "prompt": "tüm ülkeler", "base": BASE_COMPARE, "expect": {"countries": [], "split_by_country": False}},
    {"id": "c24", "prompt": "çubuk grafik yap", "expect": {"chart": "bar"}},
]


def _spec(base):
    from analysis.chart_studio import default_spec
    return {**default_spec(), **(base or {})}


def ideal_reply(case):
    """What a perfect planner would return: the full spec with the expected fields applied."""
    return json.dumps({**_spec(case.get("base")), **case["expect"]})


ADVERSARIAL = {
    "c01": "SELECT country, COUNT(*) FROM transactions GROUP BY 1",
    "c05": json.dumps({**_spec(None), "dimension": "week", "sql": "DROP TABLE x"}),
    "c12": json.dumps({**_spec(None), "countries": ["Germany", "Atlantis"], "split_by_country": True}),
    "c16": "Sure! Here is your chart: average order value with a 95% interval.",
}


def _score(spec, expect):
    if spec is None:
        return False, 0, len(expect)
    hits = sum(1 for k, v in expect.items() if spec.get(k) == v)
    return hits == len(expect), hits, len(expect)


def run_chart(provider, catalog, probe=None):
    from analysis.chart_studio import llm_plan, local_plan
    records, blocked = [], None
    for case in CASES:
        base = _spec(case.get("base"))
        if provider == "local":
            plan = local_plan(case["prompt"], base, catalog, "tr")
            spec = plan["spec"] if plan["status"] == "planned" else None
            raw = plan["status"]
        elif provider.startswith("scripted"):
            mode = "ideal" if provider == "scripted-ideal" else "adversarial"
            reply = ideal_reply(case) if mode == "ideal" else ADVERSARIAL.get(case["id"], ideal_reply(case))
            model = ScriptedModel(lambda c, m, r=reply: r).bind(case, mode)
            plan = llm_plan(case["prompt"], base, catalog, model=model, locale="tr")
            spec = plan.get("spec") if plan["status"] == "planned" else None
            raw = plan["status"]
        else:  # live provider; never fabricated
            if blocked is None:
                plan = probe(case, base) if probe else llm_plan(case["prompt"], base, catalog, locale="tr")
                if not probe:
                    from analysis.llm_eval.evaluate import _pause
                    _pause()
                if plan["status"] in {"planned", "no_change"}:
                    spec, raw = plan["spec"], plan["status"]
                elif plan["status"] in {"invalid_plan", "blocked"} or plan.get("error_code") == "json_validate_failed":
                    # a rejected, refused or unparseable reply is a wrong answer, not an outage
                    spec, raw = None, plan.get("error_code") if plan.get("error_code") == "json_validate_failed" else plan["status"]
                else:
                    blocked = {k: plan.get(k) for k in ("status", "error_code", "http_status")}
            if blocked is not None:
                records.append({"id": case["id"], "prompt": case["prompt"], "raw_status": "BLOCKED", "correct": None,
                                "field_hits": None, "fields": len(case["expect"]), "blocked": blocked})
                continue
        correct, hits, total = _score(spec, case["expect"])
        rec = {"id": case["id"], "prompt": case["prompt"], "raw_status": raw, "correct": correct, "field_hits": hits,
               "fields": total}
        if provider not in {"local"} and not provider.startswith("scripted"):
            t = plan.get("telemetry") or {}
            rec.update(latency_ms=t.get("latency_ms"), total_tokens=t.get("total_tokens"))
        if provider == "scripted-adversarial" and case["id"] in ADVERSARIAL:
            rec["adversarial_rejected"] = raw == "invalid_plan"
        records.append(rec)
    return records, blocked


def chart_metrics(records, blocked):
    if blocked is not None:
        return {"chart_spec_accuracy": None, "chart_field_accuracy": None, "chart_adversarial_rejection": None}
    done = [r for r in records if r["correct"] is not None]
    adv = [r["adversarial_rejected"] for r in records if "adversarial_rejected" in r]
    return {
        "chart_spec_accuracy": sum(r["correct"] for r in done) / len(done) if done else None,
        "chart_field_accuracy": sum(r["field_hits"] for r in done) / sum(r["fields"] for r in done) if done else None,
        "chart_adversarial_rejection": sum(adv) / len(adv) if adv else None,
    }
