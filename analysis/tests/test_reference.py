"""v3 G7 / AW-19: reference country groups and country_group charts."""

import json
from datetime import date

import pytest

from analysis import reference
from analysis.chart_studio import chart, compile_query, local_plan, validate_spec
from analysis.worker import meta

UCI = meta("uci")


def test_reference_table_is_well_formed():
    data = reference.groups()
    assert set(data["groups"]) | {"continent"} == set(reference.GROUP_IDS)
    for gid, g in data["groups"].items():
        assert g["source"] and len(g["label"]) == len(g["outside"]) == 2
        for iso3, (joined, left) in g["members"].items():
            assert len(iso3) == 3 and iso3.isupper()
            assert date.fromisoformat(joined) and (left is None or date.fromisoformat(left) > date.fromisoformat(joined))
    for country in UCI["countries"]:
        info = data["dataset_countries"][country]  # every dataset country is mapped or explicitly unmatched
        assert info.get("iso3") or info.get("unmatched")
    card = reference.card("nato")
    assert card["sha256"] and card["version"] == data["version"]


def test_membership_is_read_at_a_date():
    end = date(2011, 12, 9)
    at_end = reference.classify("nato", ["Sweden", "Finland", "Germany", "Channel Islands", "Atlantis"], end)
    assert {c: v["bucket"] for c, v in at_end.items()} == {
        "Sweden": "outside", "Finland": "outside", "Germany": "member", "Channel Islands": "unmatched", "Atlantis": "unmatched"}
    assert "2024-03-07" in at_end["Sweden"]["note"]
    today = reference.classify("nato", ["Sweden", "Finland"], date(2026, 10, 18))
    assert {v["bucket"] for v in today.values()} == {"member"}
    eu = reference.classify("eu", ["United Kingdom"], date(2011, 12, 9))["United Kingdom"]["bucket"]
    assert eu == "member" and reference.classify("eu", ["United Kingdom"], date(2021, 1, 1))["United Kingdom"]["bucket"] == "outside"
    assert reference.classify("continent", ["RSA", "USA", "Unspecified"], end) == {
        "RSA": {"bucket": "africa", "iso3": "ZAF", "note": None},
        "USA": {"bucket": "north_america", "iso3": "USA", "note": None},
        "Unspecified": {"bucket": "unmatched", "iso3": None, "note": "Ülke belirtilmemiş"},
    }


@pytest.mark.parametrize("prompt,group,as_of", [
    ("ülkeleri nato ülkeleri veya nato dışı diye sınıflandırıp satışlarımızı incele % kaçı nato ülkeleri % kaçı dışında onu bir grafik yap", "nato", "period_end"),
    ("NATO share of sales by today's membership", "nato", "today"),
    ("AB ülkeleri ve AB dışı", "eu", "period_end"),
    ("Avrupa Birliği'ne göre sipariş", "eu", "period_end"),
    ("euro bölgesi payı", "eurozone", "period_end"),
    ("G7 vs the rest", "g7", "period_end"),
    ("OECD üyeleri", "oecd", "period_end"),
    ("kıtalara göre satış", "continent", "period_end"),
])
def test_local_planner_reads_group_requests(prompt, group, as_of):
    plan = local_plan(prompt, None, UCI, "tr")
    s = plan["spec"]
    assert plan["status"] == "planned" and (s["dimension"], s["group"], s["group_as_of"], s["chart"]) == ("country_group", group, as_of, "bar")


def test_nato_shares_match_an_independent_oracle():
    r = chart({"dataset": "uci", "prompt": "NATO / NATO dışı", "use_llm": False})
    members = reference.classify("nato", UCI["countries"], date.fromisoformat(UCI["end"]))
    totals = {"member": 0, "outside": 0, "unmatched": 0}
    for row in _country_totals():
        totals[members[row[0]]["bucket"]] += row[1]
    whole = sum(totals.values())
    got = {d["key"]: d for d in r["data"]}
    for bucket, pence in totals.items():
        assert round(got[bucket]["value"] * 100) == pence
        assert got[bucket]["share"] == round(pence / whole, 6)
    assert [d["key"] for d in r["data"]] == ["member", "outside", "unmatched"]
    assert r["groups"]["as_of"] == UCI["end"] and len(r["groups"]["countries"]) == len(UCI["countries"])
    assert any(s["type"] == "limitation" and "Channel Islands" in s["text"] for s in r["statements"])


def _country_totals():
    import duckdb

    from analysis.prepare import DATA

    with duckdb.connect(str(DATA / "uci.duckdb"), read_only=True) as con:
        return con.execute("SELECT country, SUM(line_pence)::BIGINT FROM transactions GROUP BY 1").fetchall()


def test_membership_is_bound_never_spliced():
    spec = validate_spec({"dimension": "country_group", "group": "nato"}, UCI)
    sql, params = compile_query(spec, groups=[("O'Brien; DROP TABLE x", "member"), ("Germany", "member")])
    assert "DROP" not in sql and params[:2] == ["O'Brien; DROP TABLE x", "member"]
    with pytest.raises(ValueError):
        validate_spec({"dimension": "country_group", "group": "warsaw_pact"}, UCI)
    with pytest.raises(ValueError):
        validate_spec({"dimension": "country_group", "group_as_of": "1990-01-01"}, UCI)
    assert "group" not in validate_spec({"dimension": "month", "group": "nato"}, UCI)


def test_product_charts_leave_service_lines_out_unless_asked():
    default = chart({"dataset": "uci", "prompt": "top 10 products", "use_llm": False})
    assert "DOTCOM POSTAGE" not in {d["x"] for d in default["data"]} and default["scope"]["products_only"]
    both = chart({"dataset": "uci", "prompt": "top 10 products", "use_llm": False, "include_service": True})
    assert "DOTCOM POSTAGE" in {d["x"] for d in both["data"]}


def test_reference_catalog_is_the_retrieval_surface():
    cards = reference.catalog("en")
    assert [c["group"] for c in cards] == list(reference.GROUP_IDS)
    assert all(set(c) == {"id", "group", "label", "source", "version", "sha256", "kind"} for c in cards)
    assert json.dumps(cards)  # serialisable for a planner prompt
