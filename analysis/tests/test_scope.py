"""v3 G5: what gross sales leaves out, what product views leave out, and the partial-month disclosure.

A small fixture with merchandise, postage, a manual line, a bad-debt adjustment and every exclusion reason, checked
against hand-computed values (independent of the SQL under test).
"""

import pandas as pd
import pytest

from analysis import prepare, worker
from analysis.scope import SERVICE_CODES, product_clause

DATASET = "usr_5c09e5c09e00_5c09e5c09e00"
ROWS = [
    # invoice, product_id, product, quantity, unit_price, order_date, country, customer_id
    ["1001", "A1", "MUG", 10, 2.0, "2025-01-03", "Germany", "c1"],  # £20.00
    ["1001", "B2", "PLATE", 2, 5.0, "2025-01-03", "Germany", "c1"],  # £10.00
    ["1001", "POST", "POSTAGE", 1, 18.0, "2025-01-03", "Germany", "c1"],  # £18.00 service (shipping)
    ["1002", "A1", "MUG", 1, 2.0, "2025-02-10", "France", "c2"],  # £2.00
    ["1002", "B2", "PLATE", 1, 5.0, "2025-02-10", "France", "c2"],  # £5.00
    ["1002", "DOT", "DOTCOM POSTAGE", 1, 40.0, "2025-02-10", "France", "c2"],  # £40.00 service (shipping)
    ["1003", "M", "Manual", 1, 7.5, "2025-02-11", "France", "c3"],  # £7.50 service (manual)
    ["A1004", "B", "Adjust bad debt", 1, 100.0, "2025-02-12", "France", None],  # £100.00 service (adjustment)
    ["C1005", "A1", "MUG", -3, 2.0, "2025-02-12", "Germany", "c1"],  # excluded: cancelled, -£6.00
    ["1006", "A1", "MUG", -1, 0.0, "2025-02-13", "Germany", None],  # excluded: non-positive quantity, £0
    ["1007", "Z9", "FREE GIFT", 1, 0.0, "2025-02-13", "Germany", None],  # excluded: non-positive price, £0
    ["A1008", "B", "Adjust bad debt", 1, -50.0, "2025-02-14", "France", None],  # excluded: price, -£50.00
]


@pytest.fixture()
def dataset(monkeypatch, tmp_path):
    monkeypatch.setattr(worker, "DATA", tmp_path)
    monkeypatch.setattr(prepare, "DATA", tmp_path)
    prepare.store(
        DATASET,
        "Scope fixture",
        pd.DataFrame(ROWS, columns=prepare.COLUMNS),
        {"kind": "synthetic", "publisher": "test", "license": "CC0"},
    )
    return DATASET


def test_exclusions_are_exclusive_and_add_up(dataset):
    q = worker.meta(dataset)["quality"]
    by = {e["reason"]: e for e in q["exclusions"]}
    assert by["cancelled"] == {"reason": "cancelled", "rows": 1, "pence": -600}
    assert by["nonpositive_quantity"] == {"reason": "nonpositive_quantity", "rows": 1, "pence": 0}
    assert by["nonpositive_price"] == {"reason": "nonpositive_price", "rows": 2, "pence": -5000}
    assert sum(e["rows"] for e in q["exclusions"]) == q["excluded_rows"] == 4
    # The overlapping raw profile stays as it was: the cancellation also counts as a non-positive quantity.
    assert q["nonpositive_quantity"] == 2


def test_gross_sales_keeps_service_lines_but_product_views_do_not(dataset):
    r = worker.run({"dataset": dataset, "include_graph": True})
    # Gross sales (retail-v1): 20 + 10 + 18 + 2 + 5 + 40 + 7.50 + 100 = £202.50.
    assert r["summary"]["gross_pence"] == 20250
    assert [p["product_id"] for p in r["products"]] == ["A1", "B2"]
    assert {n["id"] for n in r["graph"]["nodes"]} == {"A1", "B2"}
    assert r["graph"]["include_service"] is False
    s = r["scope"]
    assert s["include_service"] is False
    assert s["service"]["lines"] == 4 and s["service"]["pence"] == 16550
    assert [(g["kind"], g["pence"]) for g in s["service"]["groups"]] == [
        ("adjustment", 10000),
        ("shipping", 5800),
        ("manual", 750),
    ]


def test_including_service_lines_is_the_analysts_choice(dataset):
    r = worker.run({"dataset": dataset, "include_graph": True, "include_service": True})
    assert r["products"][0]["product_id"] == "B"  # the adjustment would top the ranking — the reason for the default
    assert {"POST", "DOT", "M", "B"} <= {p["product_id"] for p in r["products"]}
    assert r["graph"]["include_service"] is True and r["scope"]["include_service"] is True
    assert r["summary"]["gross_pence"] == 20250  # the total never depends on the switch
    with pytest.raises(ValueError):
        worker.run({"dataset": dataset, "include_graph": False, "include_service": "yes"})


def test_filters_apply_to_the_service_disclosure(dataset):
    r = worker.run({"dataset": dataset, "include_graph": False, "filters": {"country": "Germany"}})
    assert r["scope"]["service"]["lines"] == 1 and r["scope"]["service"]["pence"] == 1800


def test_partial_months_are_reported(dataset):
    periods = worker.run({"dataset": dataset, "include_graph": False})["scope"]["periods"]
    # Valid lines span 2025-01-03 .. 2025-02-12: 29 of 31 days of January, 12 of 28 days of February.
    assert periods == [
        {"edge": "first", "month": "2025-01", "date": "2025-01-03", "covered_days": 29, "month_days": 31, "partial": True},
        {"edge": "last", "month": "2025-02", "date": "2025-02-12", "covered_days": 12, "month_days": 28, "partial": True},
    ]
    one = worker.run({"dataset": dataset, "include_graph": False, "filters": {"start": "2025-02-01", "end": "2025-02-28"}})
    assert one["scope"]["periods"] == [
        {"edge": "only", "month": "2025-02", "date": "2025-02-10", "covered_days": 3, "month_days": 28, "partial": True}
    ]


def test_temporal_concentration_uses_product_shares(dataset):
    from analysis.temporal import analyze_temporal

    m = worker.meta(dataset)
    where, args, _ = worker.filters_for({"filters": {}}, m)
    out = analyze_temporal({"month": "2025-02", "window": 1, "min_shared": 1}, m, where, args, worker.DATA)
    assert all(p["product_id"] in {"A1", "B2"} for p in out["selected_products"])
    feb = next(s for s in out["stages"] if s["months"] == ["2025-02"])
    # February products: MUG £2, PLATE £5 → HHI = (2/7)² + (5/7)² = 29/49; postage, manual and the adjustment are
    # not products, but the window's sales still include them.
    assert feb["summary"]["product_hhi"] == pytest.approx(29 / 49, abs=1e-6)
    assert feb["summary"]["gross_pence"] == 700 + 4000 + 750 + 10000


def test_service_codes_are_constant_sql():
    assert "'POST'" in product_clause() and "'PADS'" not in product_clause()
    assert all(c == c.upper() for c in SERVICE_CODES)
