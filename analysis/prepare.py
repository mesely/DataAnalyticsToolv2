"""Build source-attributed, immutable local demo datasets and independent fixture oracle."""

from pathlib import Path
import csv, hashlib, json, random, zipfile
from decimal import Decimal, ROUND_HALF_UP
import duckdb

# pandas/numpy are imported inside the functions that need them: the worker imports this module for DATA and
# store on every request, and the forecast/decision/graph actions never touch a DataFrame (AW-14 startup cut).

ROOT = Path(__file__).resolve().parent
DATA = ROOT / ".local"
DATA.mkdir(exist_ok=True)
COLUMNS = [
    "invoice",
    "product_id",
    "product",
    "quantity",
    "unit_price",
    "order_date",
    "country",
    "customer_id",
]


def normalize(raw):
    import numpy as np
    import pandas as pd

    df = raw.copy()
    df.columns = [str(x).strip() for x in df.columns]
    aliases = {
        "InvoiceNo": "invoice",
        "StockCode": "product_id",
        "Description": "product",
        "Quantity": "quantity",
        "UnitPrice": "unit_price",
        "InvoiceDate": "order_date",
        "Country": "country",
        "CustomerID": "customer_id",
    }
    df = df.rename(columns=aliases)
    missing = [c for c in COLUMNS if c not in df]
    if missing:
        raise ValueError("Eksik sütunlar: " + ", ".join(missing))
    n = len(df)
    if n == 0:
        raise ValueError("CSV boş olamaz.")
    df["quantity"] = pd.to_numeric(df.quantity, errors="coerce")
    df["unit_price"] = pd.to_numeric(df.unit_price, errors="coerce")
    df["order_date"] = pd.to_datetime(df.order_date, errors="coerce", format="mixed")
    cancelled = df.invoice.astype(str).str.upper().str.startswith("C")
    numeric_ok = (
        np.isfinite(df.quantity)
        & np.isfinite(df.unit_price)
        & (df.quantity % 1 == 0)
        & (df.quantity <= 1_000_000)
        & (df.unit_price <= 1_000_000)
    )
    valid = (
        numeric_ok
        & (df.quantity > 0)
        & (df.unit_price > 0)
        & df.order_date.notna()
        & (~cancelled)
        & df["product"].notna()
        & df.invoice.notna()
        & df.product_id.notna()
    )
    quality = {
        "raw_rows": n,
        "cancelled_rows": int(cancelled.sum()),
        "nonpositive_quantity": int((df.quantity <= 0).sum()),
        "nonpositive_price": int((df.unit_price <= 0).sum()),
        "missing_customer": int(df.customer_id.isna().sum()),
        "invalid_date": int(df.order_date.isna().sum()),
        "duplicate_rows": int(df.duplicated().sum()),
        "excluded_rows": int((~valid).sum()),
    }
    df = df.loc[valid, COLUMNS].copy()
    for c in ["invoice", "product_id", "product", "country"]:
        df[c] = df[c].fillna("Unknown").astype(str).str.strip()
    df["customer_id"] = df.customer_id.map(
        lambda x: (
            None
            if pd.isna(x) or str(x).strip() == ""
            else hashlib.sha256(str(x).encode()).hexdigest()[:12]
        )
    )
    # Round only at line level; a documented monetary policy, not float accumulation.
    df["line_pence"] = [
        int(
            (Decimal(str(q)) * Decimal(str(p)) * 100).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
        for q, p in zip(df.quantity, df.unit_price)
    ]
    df["quantity"] = df.quantity.astype("int64")
    df["order_date"] = df.order_date.dt.strftime("%Y-%m-%d")
    return df, quality


def store(dataset_id, title, raw, source):
    df, quality = normalize(raw)
    if df.empty:
        raise ValueError("Geçerli pozitif satış satırı bulunamadı.")
    digest = hashlib.sha256(df.to_csv(index=False).encode()).hexdigest()
    target = DATA / (dataset_id + ".duckdb")
    con = duckdb.connect(str(target))
    con.register("incoming", df)
    con.execute(
        "CREATE OR REPLACE TABLE transactions AS SELECT invoice::VARCHAR invoice,product_id::VARCHAR product_id,product::VARCHAR product,quantity::BIGINT quantity,unit_price::DECIMAL(18,4) unit_price,order_date::DATE order_date,country::VARCHAR country,customer_id::VARCHAR customer_id,line_pence::BIGINT line_pence FROM incoming"
    )
    con.close()
    meta = {
        "id": dataset_id,
        "title": title,
        "rows": len(df),
        "columns": len(df.columns),
        "orders": int(df.invoice.nunique()),
        "products": int(df.product_id.nunique()),
        "countries": sorted(df.country.unique().tolist()),
        "start": str(df.order_date.min()),
        "end": str(df.order_date.max()),
        "sha256": digest,
        "quality": quality,
        "currency": "GBP",
        "source": source,
        "schema": [
            {
                "name": c,
                "type": (
                    "number"
                    if c in ["quantity", "unit_price", "line_pence"]
                    else "date" if c == "order_date" else "text"
                ),
                "nullable": bool(df[c].isna().any()),
            }
            for c in df.columns
        ],
        "definition": "Brüt satış = Σ(quantity × unit_price), satır düzeyinde GBP kuruşuna yuvarlanır. İptal/iade ve pozitif olmayan miktar/fiyat dışlanır. Net gelir değildir.",
        "recipe_version": "retail-v1",
    }
    (DATA / (dataset_id + ".json")).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2)
    )
    return meta


def main():
    import pandas as pd

    rnd = random.Random(47)
    rows = []
    products = [
        ("P01", "Seramik kupa", 6.5),
        ("P02", "Keten defter", 12),
        ("P03", "Masa lambası", 29.9),
        ("P04", "Cam vazo", 18.5),
        ("P05", "Ahşap kalemlik", 9),
        ("P06", "Bez çanta", 8.5),
        ("P07", "Çay kutusu", 11),
        ("P08", "Mum seti", 14.5),
    ]
    for i in range(180):
        month = 1 + i // 60
        day = 1 + (i % 27)
        country = ["United Kingdom", "France", "Germany"][i % 3]
        picks = rnd.sample(products, 3)
        if i % 3 == 0:
            picks = products[:2] + [products[3]]
        for pid, name, price in picks:
            rows.append(
                [
                    f"D{i+1:04}",
                    pid,
                    name,
                    rnd.randint(1, 5),
                    price,
                    f"2025-{month:02}-{day:02}",
                    country,
                    f"DEMO-{i%42}",
                ]
            )
    rows.extend(
        [
            ["C0001", "P01", "Seramik kupa", -2, 6.5, "2025-01-02", "France", "DEMO-1"],
            ["BAD1", "P02", "Keten defter", 1, 0, "2025-01-03", "France", None],
        ]
    )
    raw = pd.DataFrame(rows, columns=COLUMNS)
    fixture_path = ROOT / "data" / "demo_retail.csv"
    raw.to_csv(fixture_path, index=False)
    demo = store(
        "demo",
        "Atölye • kontrollü demo",
        raw,
        {
            "kind": "synthetic",
            "publisher": "Context Layer test fixture",
            "url": None,
            "license": "CC0-1.0",
            "seed": 47,
            "description": "Kontrollü test için üretilmiş sentetik veri; gerçek ticari kayıt değildir.",
        },
    )
    # Independent stdlib oracle; deliberately does not call normalize or DuckDB.
    valid = [r for r in rows if not str(r[0]).startswith("C") and r[3] > 0 and r[4] > 0]
    total = sum(
        int(
            (Decimal(str(r[3])) * Decimal(str(r[4])) * 100).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
        for r in valid
    )
    oracle = {
        "dataset": "demo",
        "raw_rows": len(rows),
        "valid_rows": len(valid),
        "orders": len(set(r[0] for r in valid)),
        "units": sum(r[3] for r in valid),
        "gross_pence": total,
        "excluded_rows": 2,
    }
    (ROOT / "data" / "demo_oracle.json").write_text(json.dumps(oracle, indent=2))
    print("demo", demo["rows"], oracle, flush=True)
    archive = Path("/tmp/online-retail.zip")
    if archive.exists():
        with zipfile.ZipFile(archive) as z:
            name = next(n for n in z.namelist() if n.endswith(".xlsx"))
            print("Reading UCI workbook", flush=True)
            with z.open(name) as f:
                retail = pd.read_excel(f, engine="openpyxl")
        meta = store(
            "uci",
            "UCI • Online Retail",
            retail,
            {
                "kind": "public",
                "publisher": "UCI Machine Learning Repository · Daqing Chen",
                "url": "https://archive.ics.uci.edu/dataset/352/online+retail",
                "download_url": "https://archive.ics.uci.edu/static/public/352/online+retail.zip",
                "doi": "10.24432/C5BW33",
                "license": "CC BY 4.0",
                "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                "description": "Birleşik Krallık merkezli perakendecinin 2010–2011 tarihsel işlem verisi. Güncel veya temsili pazar verisi değildir.",
            },
        )
        print("uci", meta["rows"], meta["quality"], flush=True)
    else:
        raise RuntimeError("UCI archive is required; download official source first.")


if __name__ == "__main__":
    main()
