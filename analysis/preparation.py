"""Bounded CSV/Parquet discovery and explicit, reversible retail preparation recipes (csv-preparation-v2).

Every transformation is an explicit option that appears in the receipt recipe: trim, drop_duplicates,
decimal_comma (quantity/price only, after mapping) and date_format (user-chosen; nothing is guessed).
Identifiers are never converted. Parquet is read by DuckDB with every column cast to text and the same bounds.
"""

from __future__ import annotations
import base64
import csv
import hashlib
import io
import json
import os
import re
import tempfile
from datetime import datetime
from decimal import Decimal, InvalidOperation
import duckdb
import pandas as pd
from analysis.prepare import COLUMNS, normalize

VERSION = "csv-preparation-v2"
MAX_BYTES, MAX_ROWS, MAX_COLUMNS, MAX_FIELD = 2_000_000, 10_000, 60, 4096
DATE_FORMATS = {
    "iso": None,  # YYYY-MM-DD, required as-is
    "dmy_slash": "%d/%m/%Y",
    "mdy_slash": "%m/%d/%Y",
    "dmy_dot": "%d.%m.%Y",
}
_DECIMAL_COMMA = re.compile(r"[+-]?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?")
_DECIMAL_COMMA_CANDIDATE = re.compile(r"[+-]?(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+,\d+)")
_DATE_PATTERNS = {
    "iso": re.compile(r"\d{4}-\d{2}-\d{2}"),
    "slash": re.compile(r"\d{1,2}/\d{1,2}/\d{4}"),
    "dot": re.compile(r"\d{1,2}\.\d{1,2}\.\d{4}"),
}
ALIASES = dict(
    zip(
        COLUMNS,
        [
            "InvoiceNo",
            "StockCode",
            "Description",
            "Quantity",
            "UnitPrice",
            "InvoiceDate",
            "Country",
            "CustomerID",
        ],
    )
)


def _check_header(header):
    if (
        not 1 <= len(header) <= MAX_COLUMNS
        or any(not h or len(h) > 100 for h in header)
        or len(set(header)) != len(header)
    ):
        raise ValueError(
            "1–60 benzersiz, boş olmayan sütun adı gerekiyor (en fazla 100 karakter)."
        )


def read_csv(content):
    if not isinstance(content, str) or not content.strip():
        raise ValueError("CSV boş olamaz.")
    if len(content.encode("utf-8")) > MAX_BYTES or "\x00" in content:
        raise ValueError("UTF-8 CSV sınırı 2 MB; NUL karakteri kabul edilmez.")
    content = content.removeprefix("\ufeff")
    try:
        dialect = csv.Sniffer().sniff(content[:8192], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    try:
        reader = csv.reader(io.StringIO(content, newline=""), dialect, strict=True)
        header = next(reader)
        header = [h.strip() for h in header]
        _check_header(header)
        rows = []
        for line, row in enumerate(reader, 2):
            if not row:  # physical blank lines are not records
                continue
            if len(row) != len(header) or any(len(c) > 4096 for c in row):
                raise ValueError(
                    f"CSV satır {line}: sütun sayısı veya 4.096 karakter alan sınırı geçersiz."
                )
            rows.append(row)
            if len(rows) > 10000:
                raise ValueError("CSV sınırı 10.000 satır.")
    except (csv.Error, StopIteration) as e:
        raise ValueError("CSV tırnakları/başlığı geçersiz.") from e
    if not rows:
        raise ValueError("CSV en az bir veri satırı içermeli.")
    return pd.DataFrame(rows, columns=header), dialect.delimiter


def read_parquet(encoded):
    """Bounded Parquet through DuckDB: ≤ 2 MB of bytes, ≤ 10,000 rows, ≤ 60 columns, every value as text
    (NULL → empty string, like a blank CSV field). No pyarrow dependency."""
    if not isinstance(encoded, str) or not encoded or len(encoded) > MAX_BYTES * 4 // 3 + 4:
        raise ValueError("Parquet sınırı 2 MB.")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as e:
        raise ValueError("Parquet içeriği çözülemedi.") from e
    if len(data) > MAX_BYTES or data[:4] != b"PAR1":
        raise ValueError("Geçerli bir Parquet dosyası (en fazla 2 MB) gerekiyor.")
    fd, path = tempfile.mkstemp(suffix=".parquet")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        with duckdb.connect() as con:
            columns = [r[0] for r in con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [path]).fetchall()]
            header = [str(c).strip() for c in columns]
            _check_header(header)
            count = con.execute("SELECT COUNT(*) FROM read_parquet(?)", [path]).fetchone()[0]
            if count > MAX_ROWS:
                raise ValueError("Parquet sınırı 10.000 satır.")
            if count == 0:
                raise ValueError("Parquet en az bir veri satırı içermeli.")
            select = ", ".join(f'COALESCE(CAST("{c}" AS VARCHAR), \'\') AS "{c}"' for c in columns)
            rows = con.execute(f"SELECT {select} FROM read_parquet(?)", [path]).fetchall()
    except duckdb.Error as e:
        raise ValueError("Parquet dosyası okunamadı.") from e
    finally:
        os.unlink(path)
    frame = pd.DataFrame(rows, columns=header)
    if (frame.map(len) > MAX_FIELD).any().any():
        raise ValueError("Parquet alan sınırı 4.096 karakter.")
    return frame, data


def load_table(request):
    """CSV text or Parquet bytes → text DataFrame plus source identity (format, delimiter, sha256)."""
    if request.get("parquet_base64") is not None:
        frame, data = read_parquet(request["parquet_base64"])
        return frame, {"format": "parquet", "delimiter": None, "source_sha256": hashlib.sha256(data).hexdigest()}
    content = request.get("csv")
    frame, delimiter = read_csv(content)
    return frame, {"format": "csv", "delimiter": delimiter, "source_sha256": hashlib.sha256(content.encode()).hexdigest()}


def receipt(source_sha256, mapping, options, source_format="csv"):
    recipe = {
        "version": VERSION,
        "source_format": source_format,
        "source_sha256": source_sha256,
        "mapping": mapping,
        "options": options,
        "grain": "invoice_line",
        "currency": "GBP",
    }
    digest = hashlib.sha256(
        json.dumps(
            recipe, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()
    return recipe, digest


def options_for(value):
    if value is None:
        value = {}
    if (
        not isinstance(value, dict)
        or set(value) - {"trim", "drop_duplicates", "decimal_comma", "date_format"}
        or any(type(value[k]) is not bool for k in ("trim", "drop_duplicates", "decimal_comma") if k in value)
        or value.get("date_format", "iso") not in DATE_FORMATS
    ):
        raise ValueError(
            "Dönüşümler trim/drop_duplicates/decimal_comma boolean ve date_format iso|dmy_slash|mdy_slash|dmy_dot olmalı."
        )
    return {
        "trim": value.get("trim", True),
        "drop_duplicates": value.get("drop_duplicates", False),
        "decimal_comma": value.get("decimal_comma", False),
        "date_format": value.get("date_format", "iso"),
    }


def convert_decimal_comma(value):
    """`1.234,56` → `1234.56`; `12,5` → `12.5`. Anything else is returned unchanged (and then fails the
    numeric check explicitly instead of being silently coerced)."""
    if value is None or not isinstance(value, str) or not _DECIMAL_COMMA.fullmatch(value.strip()):
        return value
    return value.strip().replace(".", "").replace(",", ".")


def convert_date(value, date_format):
    """Strict conversion of one declared non-ISO format to ISO; unparseable values are returned unchanged
    so the ISO check reports them instead of guessing."""
    pattern = DATE_FORMATS[date_format]
    if pattern is None or value is None or not isinstance(value, str):
        return value
    try:
        return datetime.strptime(value.strip(), pattern).date().isoformat()
    except ValueError:
        return value


def column_type(values):
    if not values:
        return "empty", False
    leading_zero = any(re.fullmatch(r"[+-]?0\d+", x) for x in values)
    if all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", x) for x in values):
        parsed = pd.to_datetime(pd.Series(values), errors="coerce", format="%Y-%m-%d")
        if parsed.notna().all():
            return "date", leading_zero
    if not leading_zero:
        try:
            numbers = [Decimal(x) for x in values]
            if all(x.is_finite() and abs(x) <= Decimal("1e15") for x in numbers):
                return (
                    "integer"
                    if all(x == x.to_integral_value() for x in numbers)
                    else "number"
                ), False
        except InvalidOperation:
            pass
    return "text", leading_zero


def profile_frame(frame):
    columns = []
    for name in frame.columns:
        values = frame[name].str.strip()
        present = values[values != ""].tolist()
        kind, leading = column_type(present)
        columns.append(
            {
                "name": name,
                "type": kind,
                "missing": len(frame) - len(present),
                "distinct": len(set(present)),
                "leading_zero": bool(leading),
                # What the explicit options would act on; the profile itself changes nothing.
                "decimal_comma_candidates": sum(1 for x in present if _DECIMAL_COMMA_CANDIDATE.fullmatch(x)),
                "date_patterns": {k: sum(1 for x in present if p.fullmatch(x)) for k, p in _DATE_PATTERNS.items()},
            }
        )
    return {
        "rows": len(frame),
        "columns": columns,
        "duplicate_rows": int(frame.duplicated().sum()),
    }


def map_frame(frame, mapping, options):
    if not isinstance(mapping, dict) or set(mapping) - set(COLUMNS):
        raise ValueError("Geçersiz perakende alan eşlemesi.")
    required = COLUMNS[:-1]
    if any(not mapping.get(c) for c in required):
        raise ValueError(
            "Sipariş, ürün kodu/adı, miktar, fiyat, tarih ve ülke alanlarını eşleyin."
        )
    selected = [v for v in mapping.values() if v]
    if any(not isinstance(v, str) or v not in frame.columns for v in selected) or len(
        set(selected)
    ) != len(selected):
        raise ValueError("Her hedef için farklı ve mevcut bir kaynak sütun seçin.")
    original_rows = len(frame)
    frame = frame.copy()
    if options["trim"]:
        frame = frame.map(lambda x: x.strip())
    if options["drop_duplicates"]:
        frame = frame.drop_duplicates()
    raw = pd.DataFrame(
        {
            c: frame[mapping[c]] if mapping.get(c) else pd.Series("", index=frame.index)
            for c in COLUMNS
        }
    )
    raw = raw.replace("", None)
    # Explicit, receipt-bound conversions on the mapped numeric/date columns only; identifiers untouched.
    if options.get("decimal_comma"):
        for c in ("quantity", "unit_price"):
            raw[c] = raw[c].map(convert_decimal_comma)
    if options.get("date_format", "iso") != "iso":
        raw["order_date"] = raw.order_date.map(lambda v: convert_date(v, options["date_format"]))
    # Strict format avoids silent dd/mm ↔ mm/dd guessing. Invalid ISO dates are
    # counted by the shared normalizer; ambiguous non-ISO input is refused.
    dates = raw.order_date.dropna().astype(str)
    bad_dates = sum(1 for d in dates if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d))
    if bad_dates:
        raise ValueError(
            f"{bad_dates} tarih değeri seçilen biçime uymuyor. Tarih alanını YYYY-MM-DD biçimine getirin veya doğru tarih biçimini seçin; belirsiz tarih dönüştürülmedi."
        )
    for value in raw.unit_price.dropna():
        try:
            number = Decimal(str(value))
            if number.is_finite() and number.as_tuple().exponent < -4:
                raise ValueError("Birim fiyat en fazla 4 ondalık basamak içerebilir.")
        except InvalidOperation:
            pass  # shared quality rules report excluded invalid numbers
    for c in ("quantity", "unit_price"):
        for value in raw[c].dropna():
            try:
                Decimal(str(value))
            except InvalidOperation as e:
                raise ValueError(
                    "Miktar/fiyat alanları ondalık nokta kullanan sayılar olmalı."
                ) from e
    return raw, original_rows - len(frame)


def prepare(request):
    frame, source = load_table(request)
    report = profile_frame(frame)
    suggested = {
        c: c if c in frame else ALIASES[c] if ALIASES[c] in frame else ""
        for c in COLUMNS
    }
    result = {
        "version": VERSION,
        "source_format": source["format"],
        "source_sha256": source["source_sha256"],
        "delimiter": source["delimiter"],
        "profile": report,
        "suggested_mapping": suggested,
    }
    if request.get("mapping") is not None:
        mapping = request["mapping"]
        options = options_for(request.get("options"))
        raw, removed = map_frame(frame, mapping, options)
        normalized, quality = normalize(raw)
        if normalized.empty:
            raise ValueError(
                "Geçerli pozitif satış satırı bulunamadı. Alan eşlemesini kontrol edin."
            )
        recipe, digest = receipt(source["source_sha256"], mapping, options, source["format"])
        result.update(
            {
                "recipe": recipe,
                "receipt": digest,
                "preview": {
                    "retained_rows": len(normalized),
                    "removed_duplicates": removed,
                    "quality": quality,
                    "gross_pence": int(normalized.line_pence.sum()),
                    "orders": int(normalized.invoice.nunique()),
                    "grain": "invoice_line",
                    "currency": "GBP",
                },
            }
        )
    return result
