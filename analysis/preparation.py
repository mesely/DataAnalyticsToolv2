"""Bounded CSV discovery and explicit, reversible retail preparation recipes."""

from __future__ import annotations
import csv
import hashlib
import io
import json
import re
from decimal import Decimal, InvalidOperation
import pandas as pd
from analysis.prepare import COLUMNS, normalize

VERSION = "csv-preparation-v1"
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


def read_csv(content):
    if not isinstance(content, str) or not content.strip():
        raise ValueError("CSV boş olamaz.")
    if len(content.encode("utf-8")) > 2_000_000 or "\x00" in content:
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
        if (
            not 1 <= len(header) <= 60
            or any(not h or len(h) > 100 for h in header)
            or len(set(header)) != len(header)
        ):
            raise ValueError(
                "1–60 benzersiz, boş olmayan sütun adı gerekiyor (en fazla 100 karakter)."
            )
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


def receipt(content, mapping, options):
    recipe = {
        "version": VERSION,
        "source_sha256": hashlib.sha256(content.encode()).hexdigest(),
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
        or set(value) - {"trim", "drop_duplicates"}
        or any(type(x) is not bool for x in value.values())
    ):
        raise ValueError("Dönüşümler trim/drop_duplicates boolean alanları olmalı.")
    return {
        "trim": value.get("trim", True),
        "drop_duplicates": value.get("drop_duplicates", False),
    }


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
    # Strict format avoids silent dd/mm ↔ mm/dd guessing. Invalid ISO dates are
    # counted by the shared normalizer; ambiguous non-ISO input is refused.
    dates = raw.order_date.dropna().astype(str)
    if any(not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) for d in dates):
        raise ValueError(
            "Tarih alanını YYYY-MM-DD biçimine getirin; belirsiz tarih dönüştürülmedi."
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
    content = request.get("csv")
    frame, delimiter = read_csv(content)
    report = profile_frame(frame)
    suggested = {
        c: c if c in frame else ALIASES[c] if ALIASES[c] in frame else ""
        for c in COLUMNS
    }
    result = {
        "version": VERSION,
        "source_sha256": hashlib.sha256(content.encode()).hexdigest(),
        "delimiter": delimiter,
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
        recipe, digest = receipt(content, mapping, options)
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
