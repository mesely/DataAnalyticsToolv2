import hashlib
import pytest
from analysis.preparation import read_csv, prepare, map_frame, options_for
from analysis.worker import handle

CSV = "order,sku,title,qty,price,day,market\n001,007,Cup,2,5.25,2025-01-01,France\n002,008,Pen,1,2.10,2025-01-02,Germany\n002,008,Pen,1,2.10,2025-01-02,Germany\n"
MAP = dict(
    zip(
        [
            "invoice",
            "product_id",
            "product",
            "quantity",
            "unit_price",
            "order_date",
            "country",
        ],
        ["order", "sku", "title", "qty", "price", "day", "market"],
    )
)


def test_generic_profile_preserves_identifiers_and_does_not_return_values():
    r = prepare({"csv": CSV})
    assert r["profile"]["rows"] == 3
    assert r["profile"]["duplicate_rows"] == 1
    assert r["profile"]["columns"][0] == dict(
        name="order", type="text", missing=0, distinct=2, leading_zero=True
    )
    assert r["profile"]["columns"][3]["type"] == "integer"
    assert "Cup" not in str(r)
    assert r["source_sha256"] == hashlib.sha256(CSV.encode()).hexdigest()


def test_receipt_binds_transforms_mapping_and_original_bytes():
    r = prepare(dict(csv=CSV, mapping=MAP))
    assert r["preview"]["gross_pence"] == 1470
    assert r["preview"]["retained_rows"] == 3
    dedup = prepare(dict(csv=CSV, mapping=MAP, options={"drop_duplicates": True}))
    assert dedup["preview"]["gross_pence"] == 1260
    assert dedup["preview"]["removed_duplicates"] == 1
    assert r["receipt"] != dedup["receipt"]
    assert prepare(dict(csv=CSV + "\n", mapping=MAP))["receipt"] != r["receipt"]
    assert prepare(dict(csv=CSV, mapping=MAP)) == r  # reset draft / stable replay


@pytest.mark.parametrize(
    "csv",
    [
        "",
        "a,a\n1,2",
        "a,b\n1,2,3",
        'a,b\n"unterminated,1',
        "a,b\n1,\x00",
        "a\n" + "x\n" * 10001,
        "a\n" + "x" * 4097,
    ],
)
def test_rejects_malformed_and_bounded_csv(csv):
    with pytest.raises(ValueError):
        read_csv(csv)


@pytest.mark.parametrize("delimiter", [",", ";", "\t"])
def test_delimiters_and_bom(delimiter):
    f, d = read_csv("\ufeff" + CSV.replace(",", delimiter))
    assert d == delimiter
    assert f.iloc[0]["sku"] == "007"


def test_mapping_precision_ambiguous_dates_and_unsupported_options():
    for change in ({"quantity": "price"}, {"country": "absent"}, {"invoice": ""}):
        with pytest.raises(ValueError):
            prepare(dict(csv=CSV, mapping=MAP | change))
    for text in [
        CSV.replace("2025-01-01", "01/02/2025"),
        CSV.replace("5.25", "5.12345"),
        CSV.replace("5.25", "oops"),
    ]:
        with pytest.raises(ValueError):
            prepare(dict(csv=text, mapping=MAP))
    with pytest.raises(ValueError):
        options_for({"drop_duplicates": "false"})


def test_exact_preview_import_and_owner_recipe_identity(tmp_path, monkeypatch):
    import analysis.prepare as storage

    monkeypatch.setattr(storage, "DATA", tmp_path)
    request = dict(csv=CSV, mapping=MAP, owner="a" * 12, title="Mapped fixture")
    r = prepare(request)
    with pytest.raises(ValueError, match="Önizleme"):
        handle(request | {"action": "import", "receipt": "stale"})
    m = handle(request | {"action": "import", "receipt": r["receipt"]})
    assert m["rows"] == 3 and m["orders"] == 2
    assert m["source"]["preparation"]["preview"] == r["preview"]
    assert m["id"] == "usr_" + "a" * 12 + "_" + r["receipt"][:12]
    other = request | {"options": {"drop_duplicates": True}}
    r2 = prepare(other)
    m2 = handle(other | {"action": "import", "receipt": r2["receipt"]})
    assert m2["id"] != m["id"] and m2["rows"] == 2
    import duckdb

    con = duckdb.connect(str(tmp_path / (m["id"] + ".duckdb")))
    assert (
        con.sql("SELECT SUM(line_pence) FROM transactions").fetchone()[0]
        == r["preview"]["gross_pence"]
    )
    assert con.sql(
        "SELECT MIN(invoice), MIN(product_id) FROM transactions"
    ).fetchone() == ("001", "007")
    assert con.sql("SELECT COUNT(customer_id) FROM transactions").fetchone()[0] == 0
