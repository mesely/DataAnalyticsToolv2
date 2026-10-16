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
    first = r["profile"]["columns"][0]
    assert {k: first[k] for k in ("name", "type", "missing", "distinct", "leading_zero")} == dict(
        name="order", type="text", missing=0, distinct=2, leading_zero=True
    )
    assert first["decimal_comma_candidates"] == 0 and first["date_patterns"] == {"iso": 0, "slash": 0, "dot": 0}
    assert {c["name"]: c["date_patterns"]["iso"] for c in r["profile"]["columns"]}["day"] == 3
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


def _parquet_b64(frame):
    import base64, duckdb, tempfile, os

    fd, path = tempfile.mkstemp(suffix=".parquet")
    os.close(fd)
    con = duckdb.connect()
    con.register("t", frame)
    con.execute(f"COPY t TO '{path}' (FORMAT PARQUET)")
    data = open(path, "rb").read()
    os.unlink(path)
    return base64.b64encode(data).decode(), data


def test_parquet_profile_mapping_and_import_match_csv(tmp_path, monkeypatch):
    import hashlib, io, duckdb, pandas as pd
    import analysis.prepare as storage

    monkeypatch.setattr(storage, "DATA", tmp_path)
    frame = pd.read_csv(io.StringIO(CSV), dtype=str)
    encoded, data = _parquet_b64(frame)
    r = prepare({"parquet_base64": encoded})
    assert r["source_format"] == "parquet" and r["delimiter"] is None
    assert r["source_sha256"] == hashlib.sha256(data).hexdigest()
    assert r["profile"]["rows"] == 3 and r["profile"]["duplicate_rows"] == 1
    assert r["profile"]["columns"][0]["leading_zero"] is True  # "001" survived as text
    assert "Cup" not in str(r)
    mapped = prepare({"parquet_base64": encoded, "mapping": MAP})
    assert mapped["preview"] == prepare({"csv": CSV, "mapping": MAP})["preview"]
    assert mapped["recipe"]["source_format"] == "parquet"
    assert mapped["receipt"] != prepare({"csv": CSV, "mapping": MAP})["receipt"]  # different bytes, different receipt
    m = handle({"action": "import", "parquet_base64": encoded, "mapping": MAP, "owner": "b" * 12, "receipt": mapped["receipt"], "title": "pq"})
    assert m["rows"] == 3 and m["source"]["preparation"]["source_format"] == "parquet"
    con = duckdb.connect(str(tmp_path / (m["id"] + ".duckdb")))
    assert con.sql("SELECT MIN(invoice), SUM(line_pence) FROM transactions").fetchone() == ("001", 1470)


def test_parquet_bounds_and_garbage_are_rejected():
    import base64, pandas as pd
    from analysis.preparation import read_parquet

    for bad in ["", "not base64!", base64.b64encode(b"PAR1 but not parquet").decode(), base64.b64encode(b"x" * 10).decode()]:
        with pytest.raises(ValueError):
            read_parquet(bad)
    too_many_rows, _ = _parquet_b64(pd.DataFrame({"a": ["x"] * 10001}))
    with pytest.raises(ValueError, match="10.000"):
        read_parquet(too_many_rows)
    empty, _ = _parquet_b64(pd.DataFrame({"a": pd.Series([], dtype=str)}))
    with pytest.raises(ValueError):
        read_parquet(empty)
    nulls, _ = _parquet_b64(pd.DataFrame({"a": ["1", None], "b": [None, "2"]}))
    f, _ = read_parquet(nulls)
    assert f.iloc[1]["a"] == "" and f.iloc[0]["b"] == ""  # NULL behaves like a blank CSV field


SEMI = CSV.replace(",", ";")  # a decimal-comma file is semicolon-delimited in practice


def test_decimal_comma_and_date_format_are_explicit_previewed_and_receipt_bound():
    text = SEMI.replace("5.25", "5,25").replace("2.10", "2,10").replace("2025-01-01", "01/02/2025").replace("2025-01-02", "02/02/2025")
    profile = prepare({"csv": text})["profile"]["columns"]
    by = {c["name"]: c for c in profile}
    assert by["price"]["decimal_comma_candidates"] == 3 and by["price"]["type"] == "text"
    assert by["day"]["date_patterns"] == {"iso": 0, "slash": 3, "dot": 0}
    assert by["sku"]["decimal_comma_candidates"] == 0 and by["sku"]["leading_zero"] is True
    with pytest.raises(ValueError, match="tarih"):
        prepare({"csv": text, "mapping": MAP, "options": {"decimal_comma": True}})  # format not chosen → refused
    dmy = prepare({"csv": text, "mapping": MAP, "options": {"decimal_comma": True, "date_format": "dmy_slash"}})
    assert dmy["preview"]["gross_pence"] == 1470 and dmy["preview"]["orders"] == 2
    mdy = prepare({"csv": text, "mapping": MAP, "options": {"decimal_comma": True, "date_format": "mdy_slash"}})
    assert mdy["preview"]["gross_pence"] == 1470 and mdy["receipt"] != dmy["receipt"]  # same totals, different declared meaning
    assert dmy["recipe"]["options"] == {"trim": True, "drop_duplicates": False, "decimal_comma": True, "date_format": "dmy_slash"}
    with pytest.raises(ValueError):
        prepare({"csv": text, "mapping": MAP, "options": {"date_format": "dmy_slash"}})  # "5,25" without decimal_comma → not a number
    with pytest.raises(ValueError):
        options_for({"date_format": "ymd"})
    dotted = SEMI.replace("2025-01-01", "31.01.2025").replace("2025-01-02", "01.02.2025")
    assert prepare({"csv": dotted, "mapping": MAP, "options": {"date_format": "dmy_dot"}})["preview"]["retained_rows"] == 3
    with pytest.raises(ValueError, match="1 tarih"):  # 31/01 cannot be month/day: one value fails, nothing is guessed
        prepare({"csv": SEMI.replace("2025-01-01", "31/01/2025").replace("2025-01-02", "02/02/2025"), "mapping": MAP, "options": {"date_format": "mdy_slash"}})


def test_decimal_comma_never_touches_identifiers_and_thousands_groups_are_exact():
    from analysis.preparation import convert_decimal_comma, convert_date

    assert convert_decimal_comma("1.234,56") == "1234.56" and convert_decimal_comma("12,5") == "12.5"
    assert convert_decimal_comma("1.234.567") == "1234567" and convert_decimal_comma("-0,75") == "-0.75"
    assert convert_decimal_comma("12.5") == "12.5" and convert_decimal_comma("abc") == "abc" and convert_decimal_comma("1,234,5") == "1,234,5"
    assert convert_date("07/08/2025", "dmy_slash") == "2025-08-07" and convert_date("07/08/2025", "mdy_slash") == "2025-07-08"
    assert convert_date("2025-01-01", "dmy_slash") == "2025-01-01"  # unparseable stays as-is; ISO check decides
    text = SEMI.replace("Cup", "1,5")  # a product name that looks numeric must stay a label
    r = prepare({"csv": text, "mapping": MAP, "options": {"decimal_comma": True}})
    assert r["preview"]["retained_rows"] == 3
