"""Single-dataset expert SQL. Reuses Alper sqlval, adds a narrow local execution boundary."""

import json, threading, time
from datetime import date, datetime
from decimal import Decimal
import duckdb, sqlglot
from sqlglot import expressions as exp
from sqlval import validate_statement
from analysis.adapted.identity import content_hash_text, source_id_for

COLUMNS = [
    "invoice",
    "product_id",
    "product",
    "quantity",
    "unit_price",
    "order_date",
    "country",
    "line_pence",
]
# An explicit small language: new functions require a security+correctness test.
FUNCTIONS = {
    "SUM",
    "COUNT",
    "AVG",
    "MIN",
    "MAX",
    "ROUND",
    "COALESCE",
    "NULLIF",
    "CAST",
    "TRY_CAST",
    "ABS",
    "LOWER",
    "UPPER",
    "LENGTH",
    "STRFTIME",
    "TIME_TO_STR",
    "DATE_TRUNC",
    "TIMESTAMP_TRUNC",
    "EXTRACT",
    "ROW_NUMBER",
    "RANK",
    "DENSE_RANK",
    "LAG",
    "LEAD",
    "SUM_IF",
    "IF",
    "CASE",
    "POWER",
    "DATE_DIFF",
}


def validate_local(statement):
    if (
        not isinstance(statement, str)
        or not statement.strip()
        or len(statement) > 12000
    ):
        raise ValueError("SQL 1–12.000 karakter olmalı.")
    verdict = validate_statement(
        {
            "statement": statement,
            "engine": "duckdb",
            "system": "local",
            "default_schema": "main",
            "objects": [
                {
                    "schema": "main",
                    "name": "transactions",
                    "kind": "table",
                    "columns": COLUMNS,
                }
            ],
        }
    )
    if verdict["verdict"] != "pass":
        raise ValueError(
            "SQL doğrulanamadı: "
            + "; ".join(f["code"] + ": " + f["message"] for f in verdict["findings"])[
                :500
            ]
        )
    tree = sqlglot.parse_one(statement, read="duckdb")
    if len(list(tree.walk())) > 500:
        raise ValueError("Sorgu karmaşıklık sınırını aştı.")
    if tree.find(exp.Join) or any(
        w.args.get("recursive") for w in tree.find_all(exp.With)
    ):
        raise ValueError(
            "Join ve recursive CTE bu laboratuvarda kapalı: satır grain/fanout koruması."
        )
    for table in tree.find_all(exp.Table):
        if table.catalog or not isinstance(table.this, exp.Identifier):
            raise ValueError("Yalnız seçili transactions görünümü sorgulanabilir.")
    for fn in tree.find_all(exp.Func):
        name = (fn.name if isinstance(fn, exp.Anonymous) else fn.sql_name()).upper()
        if name not in FUNCTIONS:
            raise ValueError("İzin verilmeyen fonksiyon: " + name)
    return verdict


def plain(value):
    if isinstance(value, (date, datetime)):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, float) and not __import__("math").isfinite(value):
        return None
    return value


def execute_sql(request, metadata, where, args, data_dir):
    started = time.perf_counter()
    statement = request.get("statement")
    validation = validate_local(statement)
    con = duckdb.connect(str(data_dir / (metadata["id"] + ".duckdb")), read_only=True)
    con.execute("SET memory_limit='128MB'")
    con.execute("SET threads=1")
    con.execute("SET temp_directory=''")
    con.execute("SET max_expression_depth=200")
    con.execute("SET enable_external_access=false")
    view_sql = (
        "SELECT "
        + ",".join(COLUMNS)
        + ' FROM "'
        + metadata["id"]
        + '".main.transactions'
        + where
    )
    # DuckDB views cannot bind parameters. Values come only from validated filters;
    # encode them with the same AST SQL dialect, never interpolate raw user SQL.
    materialized = view_sql
    for value in args:
        materialized = materialized.replace(
            "?", exp.Literal.string(str(value)).sql(dialect="duckdb"), 1
        )
    con.execute("CREATE TEMP VIEW transactions AS " + materialized)
    timer = threading.Timer(5, con.interrupt)
    timer.daemon = True
    timer.start()
    try:
        cursor = con.execute(statement)
        names = [c[0] for c in cursor.description]
        if len(set(names)) != len(names) or len(names) > 30:
            raise ValueError(
                "En fazla 30 benzersiz kolon; kolonlara farklı AS adları verin."
            )
        raw = cursor.fetchmany(501)
        truncated = len(raw) > 500
        rows = [{n: plain(v) for n, v in zip(names, row)} for row in raw[:500]]
    finally:
        timer.cancel()
        con.close()
    canonical = json.dumps(
        {
            "dataset_sha256": metadata["sha256"],
            "statement": statement,
            "scope_sql": view_sql,
            "parameters": args,
            "rows": rows,
            "truncated": truncated,
            "version": "expert-sql-v1",
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    digest = content_hash_text(canonical)
    return {
        "columns": names,
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
        "validation": validation,
        "warnings": [
            "transactions: bir satır = fatura ürün satırı; sipariş için COUNT(DISTINCT invoice).",
            "Sonuç SQL ifadenizi yansıtır; onaylı metrik tanımıyla aynı olduğu varsayılmaz.",
            "Sabit satır sırası için ORDER BY kullanın; sırasız SQL sonucu farklı sırayla gelebilir.",
        ],
        "evidence": {
            "recipe_version": "expert-sql-v1",
            "statement": statement,
            "scope_sql": view_sql,
            "parameters": args,
            "dataset_sha256": metadata["sha256"],
            "output_sha256": digest,
            "source_id": source_id_for("query", digest),
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "limits": {"rows": 500, "memory_mb": 128, "threads": 1, "timeout_s": 5},
            "policy": "sqlval + AST/function allowlist; customer columns excluded; scoped read-only view; external access disabled",
        },
    }


def compare_results(a, b):
    ea, eb = a["evidence"], b["evidence"]
    if ea["metric_version"] != eb["metric_version"] or ea["currency"] != eb["currency"]:
        raise ValueError(
            "Metrik sürümü/para birimi farklı; doğrudan karşılaştırılamaz."
        )
    rows = []
    for key in ["gross_pence", "orders", "units", "aov"]:
        old, new = a["summary"][key], b["summary"][key]
        delta = new - old
        rows.append(
            {
                "metric": key,
                "before": old,
                "after": new,
                "delta": round(delta, 4),
                "percent": round(delta / old * 100, 4) if old else None,
            }
        )
    return {
        "metrics": rows,
        "same_dataset_version": ea["dataset_sha256"] == eb["dataset_sha256"],
        "same_filters": a["filters"] == b["filters"],
        "before_filters": a["filters"],
        "after_filters": b["filters"],
        "metric_version": ea["metric_version"],
        "currency": ea["currency"],
        "note": "B − A; farklı filtre/veri sürümü farklı kapsamdır. Yüzde sıfır bazda tanımsızdır. Farklar nedensellik kanıtı değildir.",
    }
