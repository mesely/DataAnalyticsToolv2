"""v3 / AW-21: metric definitions retail-v1 (default, unchanged) and retail-v2 (customer sales), reconciled.

The UCI Online Retail figures are checked against the line amounts read straight from the transactions table, and
the identities hold inside any filter:
    retail-v1 = retail-v2 + accounting adjustments + marketplace/bank fees
    retail-v2 = merchandise + postage/carriage + manual lines + samples
"""
import duckdb
import pytest

from analysis.chart_studio import chart
from analysis.prepare import DATA
from analysis.scope import SERVICE_CODES, definition, definition_clause, reconciliation
from analysis.worker import filters_for, meta, overview

UCI = meta("uci")


def _sum(where="", args=()):
    with duckdb.connect(str(DATA / "uci.duckdb"), read_only=True) as con:
        return con.execute("SELECT COUNT(*), SUM(line_pence) FROM transactions" + where, list(args)).fetchone()


def test_retail_v1_is_unchanged_and_the_default():
    assert definition(None) == definition("") == "retail-v1" and definition_clause("retail-v1") is None
    where, args, clean = filters_for({"filters": {}}, UCI)
    assert where == "" and clean == {}  # no echo: earlier digests and saved findings keep their meaning
    o = overview({"dataset": "uci", "filters": {}})
    assert o["summary"]["gross_pence"] == 1066668454 and o["scope"]["definition"] == "retail-v1"


def test_retail_v2_leaves_out_bad_debt_and_fees_only():
    o = overview({"dataset": "uci", "filters": {"definition": "retail-v2"}})
    # £10,666,684.54 − Adjust bad debt £11,062.06 − AMAZON FEE £13,761.09 − Bank Charges £165.00
    assert o["summary"]["gross_pence"] == 1066668454 - 1106206 - 1376109 - 16500 == 1064169639
    assert o["filters"] == {"definition": "retail-v2"}
    lines, pence = _sum(" WHERE UPPER(product_id) NOT IN ('B','ADJUST','AMAZONFEE','BANK CHARGES','CRUK')")
    assert (o["summary"]["rows"], o["summary"]["gross_pence"]) == (lines, pence)


def test_reconciliation_identities_hold_on_the_whole_data_and_inside_filters():
    for filters in ({}, {"country": "United Kingdom"}, {"start": "2011-06-01", "end": "2011-08-31"}):
        where, args, _ = filters_for({"filters": filters}, UCI)
        with duckdb.connect(str(DATA / "uci.duckdb"), read_only=True) as con:
            r = reconciliation(con, where, args)
        k = r["kinds"]
        assert r["retail_v1"]["pence"] == _sum(where, args)[1]
        assert r["retail_v1"]["pence"] == r["retail_v2"]["pence"] + k["adjustment"]["pence"] + k["fee"]["pence"]
        assert r["retail_v2"]["pence"] == (r["merchandise"]["pence"] + k["shipping"]["pence"] + k["manual"]["pence"]
                                          + k["sample"]["pence"] + k["discount"]["pence"])
        merch = _sum(where + (" AND " if where else " WHERE ") + "UPPER(product_id) NOT IN ("
                     + ",".join("'" + c + "'" for c in SERVICE_CODES) + ")", args)
        assert (r["merchandise"]["lines"], r["merchandise"]["pence"]) == merch
    whole = overview({"dataset": "uci", "filters": {}})["scope"]["reconciliation"]
    assert whole["retail_v2"]["pence"] == 1064169639 and whole["merchandise"]["pence"] == 1027211887
    assert whole["kinds"]["shipping"]["pence"] == 29140165 and whole["kinds"]["manual"]["pence"] == 7811282


def test_the_dataset_level_exclusions_reconcile_with_the_raw_rows():
    q = UCI["quality"]
    excluded = sum(e["rows"] for e in q["exclusions"])
    assert excluded == q["excluded_rows"] and q["raw_rows"] - excluded == _sum()[0] == 530104


def test_chart_studio_follows_the_definition():
    v1 = chart({"dataset": "uci", "locale": "en", "prompt": "", "base_spec": {"dimension": "country", "top_n": 3}})
    v2 = chart({"dataset": "uci", "locale": "en", "prompt": "", "filters": {"definition": "retail-v2"},
                "base_spec": {"dimension": "country", "top_n": 3}})
    assert v2["scope"]["definition"] == "retail-v2" and v1["scope"]["definition"] == "retail-v1"
    uk1 = next(d["value"] for d in v1["data"] if d["x"] == "United Kingdom")
    uk2 = next(d["value"] for d in v2["data"] if d["x"] == "United Kingdom")
    with duckdb.connect(str(DATA / "uci.duckdb"), read_only=True) as con:
        off = con.execute("SELECT SUM(line_pence) FROM transactions WHERE country = 'United Kingdom' AND "
                          "UPPER(product_id) IN ('B','AMAZONFEE','BANK CHARGES')").fetchone()[0]
    assert round(uk1 - uk2, 2) == off / 100


def test_unknown_definitions_are_rejected():
    with pytest.raises(ValueError):
        filters_for({"filters": {"definition": "retail-v9"}}, UCI)
