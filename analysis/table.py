"""The data table on the overview (v3 G3): rows or a summary, sorted, filtered, paged, downloadable, askable.

Everything is one parameterised DuckDB query over the prepared dataset: column names come from allowlists, values are
bound parameters, and the global filters (country, dates) apply first. Editing never touches the source: renaming,
hiding and ordering columns are view settings kept by the browser. "Ask the table" plans the request with the Chart
studio planner (same routing table, same validation) and turns the ChartSpec into a summary query, so a question
about the table and a chart request are one measured task.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
from decimal import Decimal

import duckdb

VERSION = "table-v1"
PAGE_SIZES = (25, 50, 100, 500)
MAX_SORT = 3
MAX_FILTERS = 12
MAX_GROUPS = 2
MAX_EXPORT_CELLS = 500_000

# name -> (type, SQL expression, Turkish label, English label). customer_id is never exposed.
ROW_COLUMNS = {
    "invoice": ("text", "invoice", "Fatura", "Invoice"),
    "order_date": ("date", "order_date::VARCHAR", "Tarih", "Date"),
    "country": ("text", "country", "Ülke", "Country"),
    "product_id": ("text", "product_id", "Stok kodu", "Stock code"),
    "product": ("text", "product", "Ürün", "Product"),
    "quantity": ("int", "quantity", "Adet", "Quantity"),
    "unit_price": ("decimal", "unit_price", "Birim fiyat (£)", "Unit price (£)"),
    "line_pence": ("pence", "line_pence", "Satır tutarı", "Line value"),
}
# Filterable expressions for the row columns (dates and decimals compare as their own type, not as text).
ROW_FILTER_SQL = {**{k: v[1] for k, v in ROW_COLUMNS.items()}, "order_date": "order_date", "unit_price": "unit_price"}

GROUPS = {
    "month": ("strftime(order_date,'%Y-%m')", "Ay", "Month"),
    "week": ("strftime(date_trunc('week',order_date),'%Y-%m-%d')", "Hafta", "Week"),
    "weekday": ("isodow(order_date)", "Haftanın günü", "Weekday"),
    "country": ("country", "Ülke", "Country"),
    "product": ("product_id", "Stok kodu", "Stock code"),
}
SUMMARY_MEASURES = {
    "gross_pence": ("pence", "SUM(line_pence)::BIGINT", "Brüt satış", "Gross sales"),
    "orders": ("int", "COUNT(DISTINCT invoice)::BIGINT", "Sipariş", "Orders"),
    "units": ("int", "SUM(quantity)::BIGINT", "Adet", "Units"),
    "lines": ("int", "COUNT(*)::BIGINT", "Satır", "Lines"),
    "aov_pence": ("pence", "(SUM(line_pence)::DOUBLE / NULLIF(COUNT(DISTINCT invoice),0))", "Ortalama sipariş", "Average order"),
}
OPS = {"contains", "eq", "neq", "in", "not_in", "gte", "lte"}
METRIC_COLUMN = {"gross_sales": "gross_pence", "orders": "orders", "units": "units", "aov": "aov_pence"}


def alias(group):
    """Output column of a grouping: the product grouping is the stock code, next to a separate product-name column."""
    return "product_id" if group == "product" else group


def _err(locale, tr, en):
    return ValueError(en if locale == "en" else tr)


def _columns(view, groups, locale):
    i = 3 if locale == "en" else 2
    if view == "rows":
        return [{"name": k, "type": v[0], "label": v[i]} for k, v in ROW_COLUMNS.items()]
    cols = []
    for g in groups:
        cols.append({"name": alias(g), "type": "int" if g == "weekday" else "text", "label": GROUPS[g][1 if locale != "en" else 2]})
        if g == "product":
            cols.append({"name": "product", "type": "text", "label": "Ürün" if locale != "en" else "Product"})
    cols += [{"name": k, "type": v[0], "label": v[i]} for k, v in SUMMARY_MEASURES.items()]
    return cols


def _parse(request, locale):
    view = request.get("view", "rows")
    if view not in ("rows", "summary"):
        raise _err(locale, "Geçersiz tablo görünümü.", "Invalid table view.")
    groups = request.get("group_by") or (["country"] if view == "summary" else [])
    if view == "rows":
        groups = []
    bad_count = view == "summary" and not 1 <= len(groups) <= MAX_GROUPS
    if not isinstance(groups, list) or bad_count or any(g not in GROUPS for g in groups) or len(set(groups)) != len(groups):
        raise _err(locale, "Özet için 1–2 geçerli gruplama seçin.", "Choose 1–2 valid groupings for the summary.")
    size = request.get("page_size", 50)
    page = request.get("page", 1)
    if size not in PAGE_SIZES or type(page) is not int or page < 1 or page > 1_000_000:
        raise _err(locale, "Geçersiz sayfa.", "Invalid page.")
    return view, groups, size, page


def _filter_sql(filters, view, groups, locale):
    """Column filters on the base rows (rows view) or on the grouped output (summary view)."""
    if not isinstance(filters, list) or len(filters) > MAX_FILTERS:
        raise _err(locale, "En fazla 12 sütun filtresi.", "At most 12 column filters.")
    where, having, args, hargs = [], [], [], []
    for f in filters:
        if not isinstance(f, dict) or f.get("op") not in OPS:
            raise _err(locale, "Geçersiz sütun filtresi.", "Invalid column filter.")
        col, op, value = f.get("column"), f["op"], f.get("value")
        if view == "rows" and col in ROW_FILTER_SQL:
            kind, expr, target, targs = ROW_COLUMNS[col][0], ROW_FILTER_SQL[col], where, args
        elif view == "summary" and col in SUMMARY_MEASURES:
            kind, expr, target, targs = SUMMARY_MEASURES[col][0], SUMMARY_MEASURES[col][1], having, hargs
        elif view == "summary" and (col in {alias(g) for g in groups} or (col == "product" and "product" in groups)):
            expr = "MIN(product)" if col == "product" else GROUPS["product" if col == "product_id" else col][0]
            kind, target, targs = ("int" if col == "weekday" else "text"), having, hargs
        elif col == "country":  # always filterable on the base rows
            kind, expr, target, targs = "text", "country", where, args
        else:
            raise _err(locale, f"Bu sütun filtrelenemez: {col}.", f"This column cannot be filtered: {col}.")
        numeric = kind in ("int", "pence", "decimal")
        if op in ("in", "not_in"):
            if not isinstance(value, list) or not 1 <= len(value) <= 50 or not all(isinstance(v, str) for v in value):
                raise _err(locale, "Liste filtresi 1–50 metin değeri alır.", "A list filter takes 1–50 text values.")
            target.append(f"{expr} {'IN' if op == 'in' else 'NOT IN'} ({','.join('?' for _ in value)})")
            targs += value
        elif op == "contains":
            if numeric or not isinstance(value, str) or not value or len(value) > 100:
                raise _err(locale, "İçerir filtresi metin sütunu ve 1–100 karakter ister.", "Contains needs a text column and 1–100 characters.")
            target.append(f"lower({expr}::VARCHAR) LIKE ? ESCAPE '\\'")
            targs.append("%" + value.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
        else:
            if numeric:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise _err(locale, "Sayı filtresi sayı ister.", "A number filter needs a number.")
            elif not isinstance(value, str) or len(value) > 100:
                raise _err(locale, "Geçersiz filtre değeri.", "Invalid filter value.")
            sym = {"eq": "=", "neq": "<>", "gte": ">=", "lte": "<="}[op]
            cast = "::DATE" if kind == "date" else ""
            target.append(f"{expr} {sym} ?{cast}")
            targs.append(value)
    return where, args, having, hargs


def _order(sort, view, groups, columns, locale):
    names = {c["name"] for c in columns}
    if sort is None:
        sort = [{"column": "order_date", "dir": "asc"}, {"column": "invoice", "dir": "asc"}] if view == "rows" else [
            {"column": "gross_pence", "dir": "desc"}]
    if not isinstance(sort, list) or len(sort) > MAX_SORT:
        raise _err(locale, "En fazla 3 sıralama sütunu.", "At most 3 sort columns.")
    parts = []
    for s in sort:
        if not isinstance(s, dict) or s.get("column") not in names or s.get("dir") not in ("asc", "desc"):
            raise _err(locale, "Geçersiz sıralama.", "Invalid sort.")
        parts.append(f'"{s["column"]}" {s["dir"].upper()} NULLS LAST')
    # A total order, so paging never repeats or skips a row.
    tail = ['"invoice"', '"product_id"', '"quantity"', '"unit_price"', '"line_pence"', '"country"', '"order_date"', '"product"'] if view == "rows" else [f'"{alias(g)}"' for g in groups]
    return " ORDER BY " + ", ".join(parts + tail)


def build(request, m, where, args):
    """SQL for the requested view (without paging) and its bound parameters."""
    from analysis.scope import with_products_only

    locale = request.get("locale", "tr")
    view, groups, size, page = _parse(request, locale)
    columns = _columns(view, groups, locale)
    cw, cargs, having, hargs = _filter_sql(request.get("filters_table") or [], view, groups, locale)
    base_where = where
    if view == "summary" and "product" in groups:
        base_where = with_products_only(base_where, request)
    if cw:
        base_where += (" AND " if base_where else " WHERE ") + " AND ".join(cw)
    if view == "rows":
        select = ", ".join(f'{v[1]} AS "{k}"' for k, v in ROW_COLUMNS.items())
        sql = f"SELECT {select} FROM transactions{base_where}"
    else:
        keys = []
        for g in groups:
            keys.append(f'{GROUPS[g][0]} AS "{alias(g)}"')
            if g == "product":
                keys.append('MIN(product) AS "product"')
        measures = ", ".join(f'{v[1]} AS "{k}"' for k, v in SUMMARY_MEASURES.items())
        group_sql = ", ".join(GROUPS[g][0] for g in groups)
        sql = f"SELECT {', '.join(keys)}, {measures} FROM transactions{base_where} GROUP BY {group_sql}"
        if having:
            sql += " HAVING " + " AND ".join(having)
    order = _order(request.get("sort"), view, groups, columns, locale)
    return {"sql": sql, "order": order, "args": [*args, *cargs, *hargs], "columns": columns, "view": view,
            "groups": groups, "page_size": size, "page": page}


def _rows(con, sql, args):
    cur = con.execute(sql, args)
    names = [d[0] for d in cur.description]
    out = []
    for row in cur.fetchall():
        rec = {}
        for k, v in zip(names, row):
            # Exact prices travel as text (no float rounding); the average order is rounded to whole pence.
            rec[k] = round(v) if k == "aov_pence" and v is not None else (format(v.normalize(), "f") if isinstance(v, Decimal) else v)
        out.append(rec)
    return out


def table(request):
    from analysis.worker import DATA, filters_for, meta

    m = meta(request["dataset"])
    where, args, clean = filters_for(request, m)
    q = build(request, m, where, args)
    con = duckdb.connect(str(DATA / (m["id"] + ".duckdb")), read_only=True)
    try:
        total = con.execute(f"SELECT COUNT(*) FROM ({q['sql']})", q["args"]).fetchone()[0]
        offset = (q["page"] - 1) * q["page_size"]
        rows = _rows(con, f"{q['sql']}{q['order']} LIMIT {q['page_size']} OFFSET {offset}", q["args"])
    finally:
        con.close()
    return {"version": VERSION, "view": q["view"], "group_by": q["groups"], "columns": q["columns"], "rows": rows,
            "total": int(total), "page": q["page"], "page_size": q["page_size"],
            "pages": max(1, -(-int(total) // q["page_size"])), "filters": clean,
            "evidence": {"sql": q["sql"] + q["order"], "parameters": q["args"], "dataset_sha256": m["sha256"]}}


def _cell(v):
    """Spreadsheet-safe cell: text starting with = + - @ (or a tab/CR) is neutralised, as in the CSV export."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


def _export_value(col, v):
    if v is None:
        return ""
    if col["type"] == "pence":
        return round(v / 100, 2)
    if col["type"] == "decimal":
        return float(v)
    return v


def export(request):
    from analysis.worker import DATA, filters_for, meta

    locale = request.get("locale", "tr")
    fmt = request.get("format")
    if fmt not in ("csv", "xlsx"):
        raise _err(locale, "Biçim csv veya xlsx olmalı.", "Format must be csv or xlsx.")
    m = meta(request["dataset"])
    where, args, _ = filters_for(request, m)
    q = build({**request, "page": 1, "page_size": 25}, m, where, args)
    con = duckdb.connect(str(DATA / (m["id"] + ".duckdb")), read_only=True)
    try:
        total = con.execute(f"SELECT COUNT(*) FROM ({q['sql']})", q["args"]).fetchone()[0]
        if total * len(q["columns"]) > MAX_EXPORT_CELLS:
            raise _err(
                locale,
                f"İndirme {total:,} satır × {len(q['columns'])} sütun; sınır {MAX_EXPORT_CELLS:,} hücre. Filtreyi daraltın veya özet görünümü indirin.".replace(",", "."),
                f"The download is {total:,} rows × {len(q['columns'])} columns; the limit is {MAX_EXPORT_CELLS:,} cells. Narrow the filter or download the summary view.",
            )
        rows = _rows(con, q["sql"] + q["order"], q["args"])
    finally:
        con.close()
    visible = request.get("columns")
    cols = [c for c in q["columns"] if not visible or c["name"] in visible]
    labels = request.get("labels") if isinstance(request.get("labels"), dict) else {}
    header = [str(labels.get(c["name"]) or c["label"])[:80] for c in cols]
    body = [[_cell(_export_value(c, r.get(c["name"]))) for c in cols] for r in rows]
    name = f"context-layer-{m['id']}-{q['view']}"
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\r\n")
        w.writerow([_cell(h) for h in header])
        w.writerows(body)
        data = ("﻿" + buf.getvalue()).encode("utf-8")  # BOM: Excel opens UTF-8 (ü, ğ, £) correctly
        ctype = "text/csv"
    else:
        from openpyxl import Workbook

        wb = Workbook(write_only=True)
        ws = wb.create_sheet(title="data" if locale == "en" else "veri")
        ws.append([_cell(h) for h in header])
        for row in body:
            ws.append(row)
        out = io.BytesIO()
        wb.save(out)
        data = out.getvalue()
        ctype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return {"filename": f"{name}.{fmt}", "content_type": ctype, "base64": base64.b64encode(data).decode(),
            "rows": len(rows), "columns": len(cols), "sha256": hashlib.sha256(data).hexdigest()}


def spec_to_table(spec):
    """A ChartSpec as a summary-table request: the chart's breakdown, measure, countries, period and top N."""
    groups = [spec["dimension"]]
    if spec.get("split_by_country") and spec["dimension"] in ("month", "week", "weekday") and spec.get("countries"):
        groups.append("country")
    measure = METRIC_COLUMN[spec["metric"]]
    filters = []
    if spec.get("countries"):
        filters.append({"column": "country", "op": "in", "value": spec["countries"]})
    if spec.get("exclude_countries"):
        filters.append({"column": "country", "op": "not_in", "value": spec["exclude_countries"]})
    ranked = spec["dimension"] in ("country", "product")
    if spec.get("sort") in ("value_desc", "value_asc"):
        sort = [{"column": measure, "dir": "desc" if spec["sort"] == "value_desc" else "asc"}]
    elif ranked:
        sort = [{"column": measure, "dir": "desc"}]
    else:
        sort = [{"column": alias(g), "dir": "asc"} for g in groups]
    size = 25
    if ranked:
        size = min(p for p in PAGE_SIZES if p >= spec.get("top_n", 10))
    dates = {k: spec[k] for k in ("start", "end") if spec.get(k)}
    return {"view": "summary", "group_by": groups, "filters_table": filters, "sort": sort, "page": 1, "page_size": size,
            "top_n": spec.get("top_n") if ranked else None, "dates": dates}


def ask(request):
    """Plan a question about the table with the Chart studio planner, then answer it as a summary table."""
    from analysis.chart_studio import chart

    planned = chart({**request, "base_spec": None})
    spec = planned["spec"]
    t = spec_to_table(spec)
    filters = {**(request.get("filters") or {}), **t.pop("dates")}
    top_n = t.pop("top_n")
    out = table({**request, **t, "filters": filters})
    if top_n:
        out["rows"] = out["rows"][:top_n]
        out["note_top_n"] = top_n
    out["asked"] = {"prompt": request.get("prompt", ""), "spec": spec, "planner": planned["planner"],
                    "warnings": planned.get("warnings", []), "request": {**t, "filters": filters}}
    return out
