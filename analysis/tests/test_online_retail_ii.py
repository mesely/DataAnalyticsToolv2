"""Online Retail II preparation (uci2): the overlapping 2010-12-01..09 window is taken once, a non-identical
overlap is refused, and the dataset is optional in the catalog. The 45 MB archive is never needed in CI; the
last test runs only where uci2 has been prepared locally."""

import io, json, zipfile
from pathlib import Path
import pandas as pd
import pytest
from analysis.prepare import online_retail_ii_frame, ONLINE_RETAIL_II

COLS = ["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price", "Customer ID", "Country"]


def _row(inv, day, qty=1, price=2.5, sku="001"):
    return [inv, sku, "Cup", qty, pd.Timestamp(day), price, 12345.0, "France"]


def _archive(tmp_path, first, second):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame(first, columns=COLS).to_excel(w, sheet_name="Year 2009-2010", index=False)
        pd.DataFrame(second, columns=COLS).to_excel(w, sheet_name="Year 2010-2011", index=False)
    path = tmp_path / "orii.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(ONLINE_RETAIL_II["member"], buf.getvalue())
    return path


def test_overlap_window_is_taken_once_and_within_sheet_duplicates_are_kept(tmp_path):
    overlap = [_row("536001", "2010-12-01 09:00"), _row("536002", "2010-12-08 10:00")]
    first = [_row("489001", "2009-12-01 08:00"), _row("489001", "2009-12-01 08:00")] + overlap  # in-sheet duplicate kept
    second = overlap + [_row("581587", "2011-12-09 12:00", sku="POST", price=18.0)]
    raw, merge = online_retail_ii_frame(_archive(tmp_path, first, second))
    assert len(raw) == 2 + len(second)  # first-sheet rows before 2010-12-01, plus the whole second sheet
    assert merge == {"sheet_rows": {"Year 2009-2010": 4, "Year 2010-2011": 3}, "overlap_rows_dropped": 2, "overlap_invoices": 2}
    assert set(raw.columns) >= {"InvoiceNo", "UnitPrice", "CustomerID"} and raw.InvoiceNo.tolist().count("536001") == 1
    assert raw.StockCode.tolist()[0] == "001"  # identifiers stay text


def test_non_identical_overlap_is_refused(tmp_path):
    first = [_row("536001", "2010-12-01 09:00", qty=2)]
    second = [_row("536001", "2010-12-01 09:00", qty=3)]
    with pytest.raises(ValueError, match="not an exact duplicate"):
        online_retail_ii_frame(_archive(tmp_path, first, second))


def test_uci2_is_optional_in_the_catalog(tmp_path, monkeypatch):
    import analysis.worker as worker
    for name in ("demo", "uci"):
        src = worker.DATA / (name + ".json")
        if src.exists():
            (tmp_path / (name + ".json")).write_text(src.read_text())
    monkeypatch.setattr(worker, "DATA", tmp_path)
    ids = [d["id"] for d in worker.handle({"action": "catalog", "ids": ["demo", "uci", "uci2"]})["datasets"]]
    assert "uci2" not in ids and "demo" in ids
    with pytest.raises(ValueError, match="bulunamadı"):
        worker.meta("uci2")


LOCAL = Path(__file__).resolve().parents[1] / ".local" / "uci2.json"


@pytest.mark.skipif(not LOCAL.exists(), reason="uci2 not prepared on this machine (python -m analysis.prepare --online-retail-ii <zip>)")
def test_prepared_uci2_registers_seasonal_naive_and_matches_uci_except_the_final_postage_line():
    import duckdb
    from analysis.worker import handle
    meta = json.loads(LOCAL.read_text())
    assert meta["quality"]["raw_rows"] == 1044848 and meta["source"]["merge"]["overlap_rows_dropped"] == 22523
    f = handle({"action": "forecast", "dataset": "uci2"})
    assert f["complete_weeks"] >= 104 and "seasonal_naive" in f["candidates"]
    assert f["split"]["first_origin"] == 53
    v1 = Path(__file__).resolve().parents[1] / ".local" / "uci.duckdb"
    if v1.exists():
        con = duckdb.connect()
        con.execute(f"ATTACH '{v1}' AS v1 (READ_ONLY); ATTACH '{LOCAL.with_suffix('.duckdb')}' AS v2 (READ_ONLY)")
        cols = "invoice, product_id, quantity, unit_price, order_date, country, line_pence"
        extra = con.execute(f"SELECT {cols} FROM v2.transactions WHERE order_date >= DATE '2010-12-01' EXCEPT ALL SELECT {cols} FROM v1.transactions").fetchall()
        missing = con.execute(f"SELECT {cols} FROM v1.transactions EXCEPT ALL SELECT {cols} FROM v2.transactions WHERE order_date >= DATE '2010-12-01'").fetchall()
        assert missing == [] and [(r[0], r[1], r[6]) for r in extra] == [("581587", "POST", 1800)]
