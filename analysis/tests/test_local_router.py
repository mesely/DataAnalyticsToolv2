"""Development paraphrases for the deterministic local router (worker.explain).

These wordings are deliberately different from the frozen llm_eval plan cases; fixes are developed
against this file and the llm_eval score is reported afterwards (optimistically, because the failure
categories were first seen there)."""

import pytest
from analysis.worker import overview, explain

BASE = {"dataset": "demo", "include_graph": False}


@pytest.fixture(scope="module")
def result():
    return overview(BASE)


def ask(result, q, locale="en"):
    return explain({**BASE, "question": q, "locale": locale}, result)


@pytest.mark.parametrize("q", [
    "Which market brings in the most?",
    "Hangi pazarda en çok satış var?",
    "Nerede en çok satıyoruz?",
    "Where are our biggest sales?",
])
def test_market_phrasings_rank_countries_by_gross_sales(result, q):
    a = ask(result, q)
    assert a["status"] == "verified" and a["reason"] == "computed_result"
    assert "country" in a["claims"][0]["scope"] and a["claims"][0]["rank"] == 1


@pytest.mark.parametrize("q", [
    "What product has the highest unit volume?",
    "En çok adet satan ürün hangisi?",
    "Which country orders the most units?",
    "Miktar olarak lider ürün hangisi?",
])
def test_quantity_rankings_are_not_answered_with_a_sales_value_ranking(result, q):
    a = ask(result, q)
    assert a["status"] == "cannot_verify" and a["reason"] == "unsupported_ranking_metric"
    assert "claims" not in a


@pytest.mark.parametrize("q", ["How many units did we sell?", "Toplam kaç adet sattık?", "Total quantity sold?"])
def test_total_units_is_still_a_supported_summary(result, q):
    a = ask(result, q)
    assert a["status"] == "verified" and "scope" not in a["claims"][0]


@pytest.mark.parametrize("q", ["Where did sales drop last month?", "Which market is declining?", "Satışlar nerede düştü?"])
def test_change_questions_about_markets_are_not_answered_with_a_static_ranking(result, q):
    assert ask(result, q)["status"] == "cannot_verify"


@pytest.mark.parametrize("q", ["Sales week over week?", "Satışlar aylara göre nasıl?"])
def test_period_questions_point_to_the_time_tool(result, q):
    a = ask(result, q)
    assert a["status"] == "clarify" and a["reason"] == "open_temporal_tool"


@pytest.mark.parametrize("q", ["After last month's promotion, which item ranks first?", "Geçen hafta kampanya vardı; hangi ürün birinci?"])
def test_period_words_in_background_do_not_hijack_a_ranking_question(result, q):
    a = ask(result, q)
    assert a["status"] == "verified" and "product_id" in a["claims"][0]["scope"]


@pytest.mark.parametrize("q", ["Which item earns the most?", "Top SKU by revenue?"])
def test_item_and_sku_wording_ranks_products_not_the_summary(result, q):
    a = ask(result, q)
    assert a["status"] == "verified" and "product_id" in a["claims"][0]["scope"]
