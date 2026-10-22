"""v3 G9 / AW-20: money transforms — currency at the order's date, constant prices, gold, index.

The golden cases below are worked by hand from the published reference values (quoted in the comments), so a
reviewer can check them with a calculator; the chart cases are checked against an independent Decimal oracle that
reads the transactions and the reference tables directly.
"""
from datetime import date
from decimal import Decimal

import duckdb
import pytest

from analysis import transforms as T
from analysis.chart_studio import chart, validate_spec
from analysis.prepare import DATA
from analysis.worker import meta

UCI = meta("uci")
MONEY = ("gross_sales", "aov")


# ------------------------------------------------------------------ reference values (ECB / OECD / World Bank)

def test_reference_tables_carry_their_provenance():
    for data, digest in (T.fx_table(), T.cpi_table(), T.gold_table()):
        assert len(digest) == 64 and len(data["raw_sha256"]) == 64
        assert data["url"].startswith("https://") and data["licence"] and data["retrieved_at"].endswith("Z")
        assert data["series_ids"] and data["unit"] and data["missing_dates"]


def test_ecb_cross_rate_is_hand_checkable():
    # ECB 2011-01-04: 1 EUR = 0.85875 GBP = 2.0744 TRY = 1.3421 USD.
    assert T.fixing(date(2011, 1, 4)) == "2011-01-04"
    assert T.cross_rate("TRY", "2011-01-04") == pytest.approx(2.0744 / 0.85875, rel=1e-12)  # 2.415604...
    assert T.cross_rate("USD", "2011-01-04") == pytest.approx(1.3421 / 0.85875, rel=1e-12)
    assert T.cross_rate("EUR", "2011-01-04") == pytest.approx(1 / 0.85875, rel=1e-12)
    assert T.cross_rate("GBP", "2011-01-04") == 1.0


def test_a_day_without_fixing_uses_the_last_fixing_before_it():
    # Sunday 2011-01-09 -> Friday 2011-01-07 (1 EUR = 0.8383 GBP = 2.0344 TRY); never a later fixing.
    assert T.fixing(date(2011, 1, 9)) == "2011-01-07"
    assert T.fixing(date(2011, 1, 8)) == "2011-01-07"
    rows, prov = T.factors({**T.default(), "currency": "TRY"}, ["2011-01-04", "2011-01-09"])
    assert rows[0] == ("2011-01-04", pytest.approx(2.415604, abs=1e-6), pytest.approx(2.415604, abs=1e-6))
    assert rows[1][1] == pytest.approx(2.0344 / 0.8383, rel=1e-12)  # £100 -> ₺242.68
    assert prov["days_carried_forward"] == 1 and prov["fixings"] == {"first": "2011-01-04", "last": "2011-01-07", "count": 2}


def test_constant_prices_use_the_cpi_of_the_currency_shown():
    # OECD UK CPI (2015 = 100): 2010-12 = 91.7, 2011-01 = 91.8 -> £100 of December 2010 = £100.109 at January 2011 prices.
    rows, prov = T.factors({**T.default(), "real": "2011-01"}, ["2010-12-15", "2011-01-15"])
    assert rows[0][1] == pytest.approx(91.8 / 91.7, rel=1e-12) and rows[0][2] == 1.0  # nominal factor stays 1
    assert rows[1][1] == pytest.approx(1.0)
    assert prov["cpi"]["area"] == "Birleşik Krallık" and prov["cpi"]["base_value"] == 91.8
    # TL at today's prices: rate of the day x Türkiye CPI(latest) / CPI(2011-01) (70.0731).
    tr = {**T.default(), "currency": "TRY", "real": "latest"}
    (day, f, nominal), = T.factors(tr, ["2011-01-04"])[0]
    base = max(T.cpi("TRY"))
    assert nominal == pytest.approx(2.0744 / 0.85875, rel=1e-12)
    assert f == pytest.approx(2.0744 / 0.85875 * T.cpi("TRY")[base] / 70.0731, rel=1e-12)
    assert T.base_month(tr) == base


def test_gold_is_usd_at_the_day_over_the_month_price():
    # £1,000 on 2011-01-04 = $1,562.85 (1.3421 / 0.85875); World Bank gold January 2011 = $1,360/oz.
    (_, per_gbp_oz, _), = T.factors({**T.default(), "unit": "gold_oz"}, ["2011-01-04"])[0]
    assert 1000 * per_gbp_oz == pytest.approx(1000 * 1.3421 / 0.85875 / 1360, rel=1e-12)  # 1.14916 oz
    (_, per_gbp_g, _), = T.factors({**T.default(), "unit": "gold_g"}, ["2011-01-04"])[0]
    assert 1000 * per_gbp_g == pytest.approx(1000 * 1.3421 / 0.85875 / 1360 * 31.1034768, rel=1e-12)  # 35.74 g


def test_today_rate_is_one_rate_for_every_date():
    rows, prov = T.factors({**T.default(), "currency": "USD", "fx": "latest"}, ["2010-12-01", "2011-06-01"])
    assert rows[0][1] == rows[1][1] == pytest.approx(T.cross_rate("USD", T.latest_fixing()))
    assert prov["fixings"]["last"] == T.latest_fixing()
    assert "today" in T.describe(prov, "en")


def test_uncovered_months_are_refused_not_extrapolated():
    with pytest.raises(ValueError, match="2031-01"):
        T.factors({**T.default(), "real": "2031-01"}, ["2011-01-04"])
    with pytest.raises(ValueError, match="CPI"):
        T.factors({**T.default(), "real": "2011-01"}, ["2008-06-02"], locale="en")


# ------------------------------------------------------------------ validation

@pytest.mark.parametrize("obj,expect,warned", [
    ({"currency": "TRY"}, {"currency": "TRY"}, False),
    ({"currency": "GBP"}, None, False),  # identity
    ({"unit": "gold_g", "currency": "TRY", "real": "latest"}, {"unit": "gold_g", "currency": "GBP", "real": None}, True),
    ({"currency": "TRY", "fx": "latest", "real": "latest"}, {"fx": "transaction", "real": "latest"}, True),
    ({"compare": True}, None, True),  # compare needs constant prices
])
def test_combinations_without_a_safe_reading_are_dropped_with_a_warning(obj, expect, warned):
    w = []
    tr = T.validate(obj, metric="gross_sales", time_axis=True, single_series=True, money_metrics=MONEY, warnings=w)
    if expect is None:
        assert tr is None
    else:
        assert all(tr[k] == v for k, v in expect.items())
    assert bool(w) == warned


@pytest.mark.parametrize("obj", [{"currency": "JPY"}, {"real": "2011-13"}, {"rate": 2}, {"index": "yes"}, "TRY"])
def test_invalid_transforms_are_rejected(obj):
    with pytest.raises(ValueError):
        T.validate(obj, metric="gross_sales", time_axis=True, single_series=True, money_metrics=MONEY)


def test_count_metrics_drop_the_transform():
    w = []
    spec = validate_spec({"metric": "units", "transform": {"currency": "TRY"}}, UCI, warnings=w)
    assert "transform" not in spec and w


# ------------------------------------------------------------------ charts against an independent oracle

def _oracle_by_month(factor_of_day):
    with duckdb.connect(str(DATA / "uci.duckdb"), read_only=True) as con:
        rows = con.execute("SELECT order_date, SUM(line_pence) FROM transactions GROUP BY 1").fetchall()
    out = {}
    for d, pence in rows:
        key = d.isoformat()[:7]
        out[key] = out.get(key, Decimal(0)) + Decimal(pence) * Decimal(repr(factor_of_day(d)))
    return {k: (v / 100).quantize(Decimal("0.01")) for k, v in out.items()}


def _chart(spec, locale="tr"):
    return chart({"dataset": "uci", "locale": locale, "prompt": "", "base_spec": spec})


def test_monthly_sales_in_tl_match_the_day_by_day_oracle():
    res = _chart({"metric": "gross_sales", "dimension": "month", "transform": {"currency": "TRY"}})
    oracle = _oracle_by_month(lambda d: T.cross_rate("TRY", T.fixing(d)))
    got = {d["x"]: Decimal(str(d["value"])) for d in res["data"]}
    assert got.keys() == oracle.keys()
    assert all(abs(got[k] - oracle[k]) <= Decimal("0.01") for k in got)
    assert res["unit"] == "TRY" and res["transform"]["currency"] == "TRY"
    # Raw and converted side by side: the GBP column is the untransformed chart.
    plain = {d["x"]: d["value"] for d in _chart({"metric": "gross_sales", "dimension": "month"})["data"]}
    assert {d["x"]: d["gbp"] for d in res["data"]} == plain
    assert any("ECB" in s["text"] for s in res["statements"] if s["type"] == "limitation")


def test_real_and_nominal_series_side_by_side():
    res = _chart({"metric": "gross_sales", "dimension": "month", "transform": {"real": "2011-01", "compare": True}}, "en")
    nominal = {d["x"]: d["value"] for d in res["data"] if d["series"] == "Nominal"}
    real = {d["x"]: d["value"] for d in res["data"] if d["series"] == "Real"}
    cpi = T.cpi("GBP")
    assert nominal["2011-01"] == real["2011-01"]  # the base month is unchanged
    assert real["2010-12"] == pytest.approx(nominal["2010-12"] * cpi["2011-01"] / cpi["2010-12"], abs=0.011)
    assert real["2011-11"] == pytest.approx(nominal["2011-11"] * cpi["2011-01"] / cpi["2011-11"], abs=0.011)


def test_index_starts_at_100_on_the_first_complete_period():
    res = _chart({"metric": "gross_sales", "dimension": "month", "transform": {"index": True}})
    plain = {d["x"]: d["value"] for d in _chart({"metric": "gross_sales", "dimension": "month"})["data"]}
    values = {d["x"]: d["value"] for d in res["data"]}
    assert values["2010-12"] == 100.0 and res["unit"] == "index"
    assert values["2011-11"] == pytest.approx(plain["2011-11"] / plain["2010-12"] * 100, abs=0.01)


def test_gold_chart_and_ci_scale_with_the_order_values():
    res = _chart({"metric": "aov", "dimension": "month", "statistic": "ci95", "transform": {"unit": "gold_g"}}, "en")
    assert res["unit"] == "g" and all(d["lower"] <= d["value"] <= d["upper"] for d in res["data"] if "lower" in d)
    assert "World Bank" in res["transform"]["text"] and res["transform"]["gold"]["unit"] == "g"


def test_shares_and_rankings_use_converted_values():
    res = _chart({"metric": "gross_sales", "dimension": "country", "top_n": 5, "transform": {"currency": "EUR"}}, "en")
    assert res["unit"] == "EUR" and len(res["data"]) == 5
    assert [d["value"] for d in res["data"]] == sorted((d["value"] for d in res["data"]), reverse=True)
    assert any("%" in s["text"] for s in res["statements"] if s["type"] == "calculation")
