"""Refresh the downloaded reference series (v3 G9, AW-20): exchange rates, consumer prices, gold.

    python -m analysis.reference.fetch            # download, check and rewrite the three tables
    python -m analysis.reference.fetch --check    # recompute from the saved downloads only (no network)

The product never downloads at request time: the tables written here ship with the repository and the analyses
read them offline. Each table records its source URL, licence, retrieval time, the raw download's SHA-256 and the
exact series identifiers, so a number computed from it can be traced to the publisher's file.

Sources (first-party publishers, open licences):
- ECB euro foreign exchange reference rates, daily, all currencies quoted per 1 EUR. A GBP cross rate is
  derived as (target per EUR) / (GBP per EUR) on the same fixing day.
- OECD Consumer price indices (DF_PRICES_ALL), national CPI, all items, monthly index 2015 = 100, not seasonally
  adjusted: United Kingdom, Türkiye, United States and the euro area (20).
- World Bank Commodity Price Data (Pink Sheet), monthly average gold price in nominal US dollars per troy ounce.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import zipfile
from pathlib import Path

REF = Path(__file__).resolve().parent
RAW = REF / ".raw"  # the last downloads (ignored by Git); --check recomputes from them
START = "2009-01-01"  # earliest date the tables keep: both UCI datasets start in December 2009

ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"
ECB_CURRENCIES = ("GBP", "USD", "TRY")
OECD_URL = ("https://sdmx.oecd.org/public/rest/data/OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL,1.0/"
            "GBR+TUR+USA+EA20.M.N.CPI.IX._T.N._Z?startPeriod=2009-01&dimensionAtObservation=AllDimensions"
            "&format=csvfilewithlabels")
OECD_AREAS = {"GBR": "GBP", "TUR": "TRY", "USA": "USD", "EA20": "EUR"}
WB_PAGE = "https://www.worldbank.org/en/research/commodity-markets"
WB_SHEET, WB_SERIES = "Monthly Prices", "Gold"


def _get(url: str) -> bytes:
    import httpx

    r = httpx.get(url, follow_redirects=True, timeout=120, headers={"User-Agent": "context-layer-reference/1"})
    r.raise_for_status()
    return r.content


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_fx(raw: bytes, retrieved_at: str) -> dict:
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        text = z.read("eurofxref-hist.csv").decode("utf-8")
    rows = list(csv.DictReader(io.StringIO(text)))
    dates, series = [], {c: [] for c in ECB_CURRENCIES}
    for row in sorted(rows, key=lambda r: r["Date"]):
        if row["Date"] < START:
            continue
        values = {c: (row.get(c) or "").strip() for c in ECB_CURRENCIES}
        if any(v in ("", "N/A") for v in values.values()):
            continue  # a fixing day without every currency is left out rather than half-filled
        dates.append(row["Date"])
        for c in ECB_CURRENCIES:
            series[c].append(float(values[c]))
    return {
        "id": "fx-ecb", "kind": "downloaded-series", "version": dates[-1],
        "title": ["ECB euro referans kurları (günlük)", "ECB euro reference rates (daily)"],
        "publisher": "European Central Bank", "url": ECB_URL,
        "licence": "ECB statistics reuse policy: free reuse with the source acknowledged",
        "retrieved_at": retrieved_at, "raw_sha256": _sha(raw),
        "series_ids": {c: f"EXR.D.{c}.EUR.SP00.A" for c in ECB_CURRENCIES},
        "unit": "units of currency per 1 EUR", "frequency": "daily (TARGET business days)",
        "derivation": "GBP cross rate = (target per EUR) / (GBP per EUR) on the same fixing day",
        "missing_dates": "a date without a fixing (weekend, TARGET holiday) uses the last fixing before it, at most 7 days back",
        "columns": ["date", *ECB_CURRENCIES],
        "rows": [[d, *(series[c][i] for c in ECB_CURRENCIES)] for i, d in enumerate(dates)],
    }


def build_cpi(raw: bytes, retrieved_at: str) -> dict:
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    series: dict[str, dict[str, float]] = {cur: {} for cur in OECD_AREAS.values()}
    for row in rows:
        area = row["REF_AREA"]
        if area in OECD_AREAS and row["OBS_VALUE"] not in ("", None):
            series[OECD_AREAS[area]][row["TIME_PERIOD"]] = float(row["OBS_VALUE"])
    return {
        "id": "cpi-oecd", "kind": "downloaded-series",
        "version": max(max(s) for s in series.values() if s),
        "title": ["OECD tüketici fiyat endeksleri (aylık)", "OECD consumer price indices (monthly)"],
        "publisher": "OECD", "url": OECD_URL, "licence": "CC BY 4.0 (OECD terms and conditions)",
        "retrieved_at": retrieved_at, "raw_sha256": _sha(raw),
        "series_ids": {cur: f"OECD.SDD.TPS:DSD_PRICES@DF_PRICES_ALL/{area}.M.N.CPI.IX._T.N._Z"
                       for area, cur in OECD_AREAS.items()},
        "areas": {cur: area for area, cur in OECD_AREAS.items()},
        "unit": "index, 2015 = 100", "frequency": "monthly", "adjustment": "not seasonally adjusted",
        "missing_dates": "a month after the series' last observation is not extrapolated: the request is refused and the last month is named",
        "months": {cur: dict(sorted(s.items())) for cur, s in series.items()},
    }


def wb_url(page: bytes) -> str:
    import re

    found = sorted(set(re.findall(rb"https://thedocs\.worldbank\.org/[^\"']*CMO-Historical-Data-Monthly\.xlsx", page)))
    if len(found) != 1:
        raise RuntimeError(f"expected one CMO monthly file link on {WB_PAGE}, found {len(found)}")
    return found[0].decode()


def build_gold(raw: bytes, retrieved_at: str, url: str) -> dict:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    ws = wb[WB_SHEET]
    rows = list(ws.iter_rows(values_only=True))
    header_row = next(i for i, r in enumerate(rows) if r and any(isinstance(v, str) and v.strip() == WB_SERIES for v in r))
    col = next(j for j, v in enumerate(rows[header_row]) if isinstance(v, str) and v.strip() == WB_SERIES)
    unit = rows[header_row + 1][col]
    if unit != "($/troy oz)":
        raise RuntimeError(f"unexpected gold unit {unit!r}")
    updated = next((r[0] for r in rows[:header_row] if isinstance(r[0], str) and r[0].startswith("Updated on")), None)
    months = {}
    for r in rows[header_row + 2:]:
        label, value = r[0], r[col]
        if not isinstance(label, str) or len(label) != 7 or label[4] != "M" or not isinstance(value, (int, float)):
            continue
        key = f"{label[:4]}-{label[5:]}"
        if key >= START[:7]:
            months[key] = float(value)
    return {
        "id": "gold-worldbank", "kind": "downloaded-series", "version": max(months),
        "title": ["Dünya Bankası altın fiyatı (aylık ortalama)", "World Bank gold price (monthly average)"],
        "publisher": "World Bank (Commodity Price Data, the Pink Sheet)", "url": url, "page": WB_PAGE,
        "licence": "CC BY 4.0 (World Bank terms of use for datasets)",
        "retrieved_at": retrieved_at, "raw_sha256": _sha(raw), "publisher_note": updated,
        "series_ids": {"USD": f"CMO {WB_SHEET} / {WB_SERIES}"},
        "unit": "US dollars per troy ounce (monthly average)", "frequency": "monthly",
        "grams_per_troy_ounce": 31.1034768,
        "missing_dates": "a month after the series' last observation is not extrapolated: the request is refused and the last month is named",
        "months": dict(sorted(months.items())),
    }


def _dumps(value: dict) -> str:
    """Indented JSON with one line per table row, so a refresh reads as a short diff."""
    rows = value.get("rows")
    if rows is None:
        return json.dumps(value, ensure_ascii=False, indent=1) + "\n"
    head = json.dumps({k: v for k, v in value.items() if k != "rows"}, ensure_ascii=False, indent=1)[:-2]
    body = ",\n".join("  " + json.dumps(r, ensure_ascii=False) for r in rows)
    return head + ',\n "rows": [\n' + body + "\n ]\n}\n"


def _write(name: str, value: dict) -> None:
    (REF / name).write_text(_dumps(value))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="recompute from analysis/reference/.raw without the network")
    args = ap.parse_args(argv)
    RAW.mkdir(exist_ok=True)
    if args.check:
        meta = json.loads((RAW / "downloads.json").read_text())
        ecb, oecd, gold = ((RAW / n).read_bytes() for n in ("ecb.zip", "oecd.csv", "gold.xlsx"))
    else:
        page = _get(WB_PAGE)
        meta = {"retrieved_at": _now(), "gold_url": wb_url(page)}
        ecb, oecd, gold = _get(ECB_URL), _get(OECD_URL), _get(meta["gold_url"])
        for n, raw in (("ecb.zip", ecb), ("oecd.csv", oecd), ("gold.xlsx", gold)):
            (RAW / n).write_bytes(raw)
        (RAW / "downloads.json").write_text(json.dumps(meta, indent=1))
    tables = {
        "fx_ecb.json": build_fx(ecb, meta["retrieved_at"]),
        "cpi_oecd.json": build_cpi(oecd, meta["retrieved_at"]),
        "gold_worldbank.json": build_gold(gold, meta["retrieved_at"], meta["gold_url"]),
    }
    if args.check:
        changed = [n for n, v in tables.items()
                   if json.loads((REF / n).read_text()) != json.loads(json.dumps(v, ensure_ascii=False))]
        print("reference tables match their downloads" if not changed else "differs: " + ", ".join(changed))
        return 1 if changed else 0
    for name, value in tables.items():
        _write(name, value)
        print(name, value["version"], value["raw_sha256"][:12])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
