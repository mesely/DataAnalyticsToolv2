"""Developer code export (AW-16 §1): the current analysis as readable, runnable, checkable code.

``export_code(request)`` renders a deterministic bundle — README, DuckDB SQL, a Python script (only
dependency: duckdb), a dependency-free SVG writer, the filtered rows as Parquet, figures and
``expected.json`` — or one of the two code files on its own. Expected results are produced by running the
generated ``analysis.py`` itself (in-process) against the exported Parquet file, and are cross-checked
against the workbench's own overview numbers before anything is returned.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import shutil
import sys
import tempfile
import textwrap
import types
import zipfile
from pathlib import Path

import duckdb

from analysis.prepare import DATA
from analysis.worker import METRICS, filters_for, meta, overview

FORMATS = ("bundle", "python", "sql")
MAX_DATA_BYTES = 6 * 1024 * 1024
ZIP_DATE = (1980, 1, 1, 0, 0, 0)
COLUMNS = ("invoice", "product_id", "product", "quantity", "unit_price", "line_pence", "order_date", "country")
DATA_PATH = "data/transactions.parquet"
EXPECTED_SCHEMA = "context-layer-analysis-expected/v1"

# ------------------------------------------------------------------------------------------------ SQL
# One source for every query: the Python script binds "@name" tokens as ? parameters (in order of
# appearance), the SQL file inlines the default values. Text is otherwise identical in both files.

SQL = {
    "kpis": """SELECT
    COUNT(*)::BIGINT AS row_count,
    COUNT(DISTINCT invoice)::BIGINT AS orders,
    COALESCE(SUM(quantity), 0)::BIGINT AS units,
    COALESCE(SUM(line_pence), 0)::BIGINT AS gross_pence,
    COUNT(DISTINCT product_id)::BIGINT AS products
FROM sales""",
    "monthly_trend": """SELECT
    strftime(order_date, '%Y-%m') AS month,
    SUM(line_pence)::BIGINT AS gross_pence,
    COUNT(DISTINCT invoice)::BIGINT AS orders,
    SUM(quantity)::BIGINT AS units
FROM sales
GROUP BY month
ORDER BY month""",
    "top_countries": """SELECT
    country,
    SUM(line_pence)::BIGINT AS gross_pence,
    COUNT(DISTINCT invoice)::BIGINT AS orders
FROM sales
GROUP BY country
ORDER BY gross_pence DESC, country
LIMIT @limit""",
    "top_products": """SELECT
    product_id,
    MIN(product) AS product,
    SUM(line_pence)::BIGINT AS gross_pence,
    SUM(quantity)::BIGINT AS units
FROM sales
GROUP BY product_id
ORDER BY gross_pence DESC, product_id
LIMIT @limit""",
    "copurchase_pairs": """WITH candidates AS (
    SELECT product_id
    FROM sales
    GROUP BY product_id
    ORDER BY SUM(line_pence) DESC, product_id
    LIMIT @candidates
),
baskets AS (
    SELECT DISTINCT invoice, product_id
    FROM sales
    WHERE product_id IN (SELECT product_id FROM candidates)
),
labels AS (
    SELECT product_id, MIN(product) AS product
    FROM sales
    GROUP BY product_id
)
SELECT
    a.product_id AS product_a,
    la.product AS product_a_name,
    b.product_id AS product_b,
    lb.product AS product_b_name,
    COUNT(*)::BIGINT AS shared_orders
FROM baskets AS a
JOIN baskets AS b ON a.invoice = b.invoice AND a.product_id < b.product_id
JOIN labels AS la ON la.product_id = a.product_id
JOIN labels AS lb ON lb.product_id = b.product_id
GROUP BY product_a, product_a_name, product_b, product_b_name
HAVING COUNT(*) >= @min_shared
ORDER BY shared_orders DESC, product_a, product_b
LIMIT @limit""",
}
DEFAULTS = {
    "top_countries": {"limit": 10},
    "top_products": {"limit": 10},
    "copurchase_pairs": {"candidates": 24, "min_shared": 2, "limit": 20},
}
QUERY_ORDER = ("kpis", "monthly_trend", "top_countries", "top_products", "copurchase_pairs")

SALES_VIEW = """CREATE OR REPLACE TEMP VIEW sales AS
SELECT invoice, product_id, product, quantity, unit_price, line_pence, order_date, country
FROM read_parquet(getvariable('data_path'))
WHERE (getvariable('start_date') IS NULL OR order_date >= getvariable('start_date')::DATE)
  AND (getvariable('end_date') IS NULL OR order_date <= getvariable('end_date')::DATE)
  AND (getvariable('country') IS NULL OR country = getvariable('country')::VARCHAR)"""

_TOKEN = re.compile(r"@([a-z_]+)")


def _python_sql(name: str) -> tuple[str, list[str]]:
    """SQL with ? placeholders and the parameter names in binding order."""
    body = SQL[name]
    return _TOKEN.sub("?", body), _TOKEN.findall(body)


def _one_line(value) -> str:
    """User-supplied text (an uploaded dataset's title) placed in a comment or heading: one line, no control
    characters, so it can never end a SQL comment or a Markdown heading and inject content after it."""
    return re.sub(r"[\x00-\x1f\x7f\u2028\u2029]+", " ", str(value)).strip()


def _literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _inline(sql: str, params: list) -> str:
    """Replace ? placeholders in order with SQL literals (values are allowlisted/validated upstream)."""
    parts = sql.split("?")
    if len(parts) != len(params) + 1:
        raise ValueError("Parameter count mismatch")
    out = parts[0]
    for value, rest in zip(params, parts[1:]):
        out += _literal(value) + rest
    return out


# --------------------------------------------------------------------------------------------- text

METRIC_EN = {
    "gross_sales": ("Gross sales", "Positive sales excluding returns/cancellations; not net revenue."),
    "orders": ("Orders", "Distinct invoices in the filtered data. Distinct counts are not always additive across breakdowns."),
    "units": ("Units sold", "Quantity on positive sales lines."),
    "aov": ("Average order value", "Gross sales / distinct orders."),
}

L = {
    "en": {
        "py_doc": '''Reproducible retail analysis exported from Context Layer.

Purpose
    Recomputes the workbench results for one dataset scope (KPIs, monthly trend, top countries,
    top products and co-purchase pairs@@CHART_DOC@@) from a Parquet file with DuckDB, writes them
    as CSV files and SVG figures, and can verify them against expected.json.

Inputs
    --data     Parquet file with one row per positive invoice line
               (default: data/transactions.parquet next to this script).
    --start / --end / --country
               Optional filters; the defaults are the scope that was exported.
               Pass an empty string (--country "") to clear a filter.

Outputs
    <out>/*.csv           one CSV per result
    <out>/figures/*.svg   monthly gross sales, top countries, top products@@CHART_FIG@@

How to run
    python -m venv .venv
    .venv/bin/pip install -r requirements.txt
    python analysis.py --check              # recompute and compare with expected.json
    python analysis.py --country Germany --out out-germany

How to modify
    Each result is one function below with its SQL inline. Add a column to a SELECT, add a new
    function and register it in collect(); write_outputs() turns every result into a CSV.
    Values are integers in pence and counts so --check can compare them exactly.
''',
        "c_defaults": "Scope at export time. --check is only meaningful for this scope.",
        "d_scope": "Data file and optional filters; None means no filter.",
        "d_filters": "Filters that are set, in the same shape as expected.json.",
        "c_view": "One filtered view shared by every query; DuckDB variables hold the filters, as in analysis.sql.",
        "d_connect": "Open an in-memory DuckDB database with the filtered `sales` view.",
        "d_rows": "Run a parameterized query and return rows as dictionaries.",
        "d_kpis": "Headline numbers for the scope.\n\n    Grain: the whole scope. gross_pence = SUM(line_pence) (GBP pence, before returns, not net\n    revenue); orders = distinct invoices; units = SUM(quantity).\n    ",
        "d_monthly": "Gross sales, orders and units per calendar month (YYYY-MM).\n\n    Distinct orders are counted per month; the monthly orders do not have to add up to the\n    scope total if an invoice spans months.\n    ",
        "d_countries": "Countries ranked by gross sales (ties broken by name).",
        "d_products": "Products ranked by gross sales. The label is MIN(product) per product_id.",
        "d_pairs": "Product pairs bought on the same invoice.\n\n    Only the `candidates` best-selling products are considered; a pair needs at least\n    `min_shared` shared invoices. This is co-occurrence, not causation.\n    ",
        "d_chart": "The Chart Studio chart that was exported with this bundle.\n\n    One row per bucket (and country when the chart compares countries) with integer totals:\n    pence (gross sales), orders (distinct invoices) and units. Periods without rows are absent\n    here; Chart Studio shows them as zero.\n    ",
        "d_chart_points": "Turn chart rows into (label, value) points per series for the figure.",
        "c_chart": "Chart Studio ChartSpec v1 exported with this bundle (for reference; chart() implements it).",
        "d_collect": "Run every query for the scope and return the results by name.",
        "d_csv": "Write rows to a CSV file with a header row; returns the path.",
        "d_outputs": "Write one CSV per result and the SVG figures into out_dir.",
        "d_figures": "Render the figures with the dependency-free writer in charts.py.",
        "d_check": "Compare results with expected.json exactly and print a table.\n\n    Returns True only when the scope and every value match. Integers are compared exactly.\n    ",
        "d_main": "Command-line entry point; returns the process exit code.",
        "c_cli": "An empty string clears a filter that is set by default.",
        "c_missing": "Data file not found: {args.data}. Pass --data with a Parquet file in the documented columns.",
        "c_wrote": "Wrote {len(written)} files to {args.out}",
        "c_scope_mismatch": "scope differs from expected.json",
        "c_ok": "All {len(checks)} checks match expected.json.",
        "c_fail": "{failed} of {len(checks)} checks differ from expected.json.",
        "c_rows": "{len(wanted)} rows",
        "c_rows_diff": "expected {len(wanted)} rows, got {len(got)}; first difference at row {first}",
        "c_value_diff": "expected {value}, got {got.get(key)}",
        "arg_desc": "Recompute the exported Context Layer analysis.",
        "arg_data": "Parquet file with the transaction rows",
        "arg_start": "first order date to include (YYYY-MM-DD)",
        "arg_end": "last order date to include (YYYY-MM-DD)",
        "arg_country": "country name exactly as in the data",
        "arg_out": "output folder for CSV files and figures",
        "arg_check": "compare with expected.json and exit 1 on any difference",
        "charts_doc": '''Small, dependency-free SVG chart writer (line and horizontal bar charts).

Output is deterministic: the same input always gives byte-identical SVG text. Each SVG carries an
accessible <title> and <desc>. Colours follow the Context Layer palette on white.
''',
        "c_palette": "Context Layer palette.",
        "d_format": "Format a number for axis and value labels (thousands separators, optional £).",
        "d_ticks": "Round axis ticks from zero up to at least `maximum`.",
        "d_coord": "Coordinates with one decimal keep the SVG small and stable.",
        "d_line": "SVG text for a line chart. `points` is [(label, value)] or {series: [(label, value)]}.",
        "d_bar": "SVG text for a horizontal bar chart of [(label, value)] items, in the given order.",
        "d_write_line": "Write a line chart to `path` and return the path.",
        "d_write_bar": "Write a bar chart to `path` and return the path.",
        "desc_line": "{n} points from {first} to {last}. Highest: {top_label} ({top_value}).",
        "desc_bar": "{n} items. Highest: {top_label} ({top_value}).",
        "desc_empty": "No data in this scope.",
        "fig": {"monthly": "Monthly gross sales (GBP)", "countries": "Top countries by gross sales (GBP)",
                "products": "Top products by gross sales (GBP)"},
        "weekdays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "sql_head": "Reproducible retail analysis exported from Context Layer (DuckDB SQL).",
        "sql_run": "Run from this folder:  duckdb < analysis.sql   or   duckdb -c \".read analysis.sql\"",
        "sql_params": "1) Parameters. NULL means no filter. data_path is relative to the folder you run duckdb in.",
        "sql_view": "2) The filtered rows. Every query below reads this view.",
        "sql_grain": "Grain: one row per positive invoice line. Money is integer GBP pence (line_pence).",
        "sql_q": {
            "kpis": "Headline numbers. gross_pence = SUM(line_pence), before returns, not net revenue. orders = distinct invoices.",
            "monthly_trend": "Per calendar month (YYYY-MM). Orders are distinct invoices per month.",
            "top_countries": "Countries ranked by gross sales; ties broken by name.",
            "top_products": "Products ranked by gross sales; label = MIN(product) per product_id.",
            "copurchase_pairs": "Pairs of the 24 best-selling products that share at least 2 invoices. Co-occurrence, not causation.",
            "chart": "The exported Chart Studio chart: integer totals per bucket.",
        },
    },
    "tr": {
        "py_doc": '''Context Layer'dan dışa aktarılmış, yeniden üretilebilir perakende analizi.

Amaç
    Bir veri seti kapsamı için çalışma alanı sonuçlarını (KPI'lar, aylık trend, ilk ülkeler,
    ilk ürünler ve birlikte alım çiftleri@@CHART_DOC@@) DuckDB ile bir Parquet dosyasından yeniden
    hesaplar, CSV ve SVG olarak yazar ve expected.json ile doğrulayabilir.

Girdiler
    --data     Pozitif fatura satırı başına bir satır içeren Parquet dosyası
               (varsayılan: betiğin yanındaki data/transactions.parquet).
    --start / --end / --country
               İsteğe bağlı filtreler; varsayılanlar dışa aktarılan kapsamdır.
               Bir filtreyi kaldırmak için boş metin verin (--country "").

Çıktılar
    <out>/*.csv           her sonuç için bir CSV
    <out>/figures/*.svg   aylık brüt satış, ilk ülkeler, ilk ürünler@@CHART_FIG@@

Nasıl çalıştırılır
    python -m venv .venv
    .venv/bin/pip install -r requirements.txt
    python analysis.py --check              # yeniden hesapla ve expected.json ile karşılaştır
    python analysis.py --country Germany --out out-germany

Nasıl değiştirilir
    Her sonuç aşağıda SQL'i içinde olan tek bir fonksiyondur. Bir SELECT'e sütun ekleyin ya da
    yeni bir fonksiyon yazıp collect() içine kaydedin; write_outputs() her sonucu CSV'ye yazar.
    Değerler kuruş ve sayım cinsinden tam sayıdır; böylece --check birebir karşılaştırır.
''',
        "c_defaults": "Dışa aktarım anındaki kapsam. --check yalnız bu kapsam için anlamlıdır.",
        "d_scope": "Veri dosyası ve isteğe bağlı filtreler; None filtre yok demektir.",
        "d_filters": "Ayarlı filtreler, expected.json ile aynı biçimde.",
        "c_view": "Tüm sorguların paylaştığı filtreli görünüm; filtreler analysis.sql'deki gibi DuckDB değişkenlerindedir.",
        "d_connect": "Filtreli `sales` görünümüyle bellek içi bir DuckDB veritabanı açar.",
        "d_rows": "Parametreli bir sorgu çalıştırır, satırları sözlük olarak döndürür.",
        "d_kpis": "Kapsamın ana göstergeleri.\n\n    Tane: tüm kapsam. gross_pence = SUM(line_pence) (GBP kuruş, iade öncesi, net gelir değildir);\n    orders = benzersiz fatura; units = SUM(quantity).\n    ",
        "d_monthly": "Takvim ayı (YYYY-AA) başına brüt satış, sipariş ve adet.\n\n    Benzersiz siparişler ay bazında sayılır; bir fatura iki aya yayılırsa aylık toplam\n    kapsam toplamına eşit olmayabilir.\n    ",
        "d_countries": "Brüt satışa göre sıralı ülkeler (eşitlikte ada göre).",
        "d_products": "Brüt satışa göre sıralı ürünler. Etiket, product_id başına MIN(product).",
        "d_pairs": "Aynı faturada birlikte alınan ürün çiftleri.\n\n    Yalnız en çok satan `candidates` ürün dikkate alınır; bir çift için en az `min_shared`\n    ortak fatura gerekir. Bu birlikte görülmedir, nedensellik değildir.\n    ",
        "d_chart": "Bu paketle dışa aktarılan Chart Studio grafiği.\n\n    Dilim başına (ülke karşılaştırmasında ülke başına da) tam sayı toplamlar: pence (brüt\n    satış), orders (benzersiz fatura) ve units. Satırı olmayan dönemler burada yer almaz;\n    Chart Studio bunları sıfır olarak gösterir.\n    ",
        "d_chart_points": "Grafik satırlarını şekil için seri başına (etiket, değer) noktalarına çevirir.",
        "c_chart": "Bu paketle dışa aktarılan Chart Studio ChartSpec v1 (başvuru için; chart() bunu uygular).",
        "d_collect": "Kapsam için tüm sorguları çalıştırır, sonuçları adlarıyla döndürür.",
        "d_csv": "Satırları başlıklı bir CSV dosyasına yazar; yolu döndürür.",
        "d_outputs": "Her sonuç için bir CSV ve SVG şekilleri out_dir altına yazar.",
        "d_figures": "Şekilleri charts.py içindeki bağımlılıksız yazıcıyla üretir.",
        "d_check": "Sonuçları expected.json ile birebir karşılaştırır ve tablo yazdırır.\n\n    Yalnız kapsam ve tüm değerler eşleşirse True döner. Tam sayılar birebir karşılaştırılır.\n    ",
        "d_main": "Komut satırı giriş noktası; çıkış kodunu döndürür.",
        "c_cli": "Boş metin, varsayılan olarak ayarlı bir filtreyi kaldırır.",
        "c_missing": "Veri dosyası bulunamadı: {args.data}. Belgelenen sütunlarla bir Parquet dosyasını --data ile verin.",
        "c_wrote": "{args.out} altına {len(written)} dosya yazıldı",
        "c_scope_mismatch": "kapsam expected.json'dan farklı",
        "c_ok": "{len(checks)} denetimin tümü expected.json ile eşleşiyor.",
        "c_fail": "{len(checks)} denetimden {failed} tanesi expected.json'dan farklı.",
        "c_rows": "{len(wanted)} satır",
        "c_rows_diff": "beklenen {len(wanted)} satır, bulunan {len(got)}; ilk fark {first}. satırda",
        "c_value_diff": "beklenen {value}, bulunan {got.get(key)}",
        "arg_desc": "Dışa aktarılan Context Layer analizini yeniden hesaplar.",
        "arg_data": "işlem satırlarını içeren Parquet dosyası",
        "arg_start": "dahil edilecek ilk sipariş tarihi (YYYY-AA-GG)",
        "arg_end": "dahil edilecek son sipariş tarihi (YYYY-AA-GG)",
        "arg_country": "verideki yazımıyla ülke adı",
        "arg_out": "CSV ve şekiller için çıktı klasörü",
        "arg_check": "expected.json ile karşılaştır, fark varsa 1 ile çık",
        "charts_doc": '''Küçük, bağımlılıksız SVG grafik yazıcısı (çizgi ve yatay çubuk grafik).

Çıktı deterministiktir: aynı girdi her zaman bayt bayt aynı SVG metnini verir. Her SVG erişilebilir
bir <title> ve <desc> taşır. Renkler beyaz zemin üzerinde Context Layer paletidir.
''',
        "c_palette": "Context Layer paleti.",
        "d_format": "Eksen ve değer etiketleri için sayı biçimler (binlik ayırıcı, isteğe bağlı £).",
        "d_ticks": "Sıfırdan en az `maximum` değerine kadar yuvarlak eksen işaretleri.",
        "d_coord": "Tek ondalıklı koordinatlar SVG'yi küçük ve kararlı tutar.",
        "d_line": "Çizgi grafik SVG metni. `points` [(etiket, değer)] ya da {seri: [(etiket, değer)]} olabilir.",
        "d_bar": "[(etiket, değer)] öğeleri için verilen sırayla yatay çubuk grafik SVG metni.",
        "d_write_line": "Çizgi grafiği `path` yoluna yazar ve yolu döndürür.",
        "d_write_bar": "Çubuk grafiği `path` yoluna yazar ve yolu döndürür.",
        "desc_line": "{first} – {last} arası {n} nokta. En yüksek: {top_label} ({top_value}).",
        "desc_bar": "{n} öğe. En yüksek: {top_label} ({top_value}).",
        "desc_empty": "Bu kapsamda veri yok.",
        "fig": {"monthly": "Aylık brüt satış (GBP)", "countries": "Brüt satışa göre ilk ülkeler (GBP)",
                "products": "Brüt satışa göre ilk ürünler (GBP)"},
        "weekdays": ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"],
        "sql_head": "Context Layer'dan dışa aktarılmış, yeniden üretilebilir perakende analizi (DuckDB SQL).",
        "sql_run": "Bu klasörde çalıştırın:  duckdb < analysis.sql   veya   duckdb -c \".read analysis.sql\"",
        "sql_params": "1) Parametreler. NULL filtre yok demektir. data_path, duckdb'yi çalıştırdığınız klasöre görelidir.",
        "sql_view": "2) Filtreli satırlar. Aşağıdaki tüm sorgular bu görünümü okur.",
        "sql_grain": "Tane: pozitif fatura satırı başına bir satır. Para, tam sayı GBP kuruştur (line_pence).",
        "sql_q": {
            "kpis": "Ana göstergeler. gross_pence = SUM(line_pence), iade öncesi, net gelir değildir. orders = benzersiz fatura.",
            "monthly_trend": "Takvim ayı (YYYY-AA) başına. Sipariş, ay içindeki benzersiz faturadır.",
            "top_countries": "Brüt satışa göre ülkeler; eşitlikte ada göre.",
            "top_products": "Brüt satışa göre ürünler; etiket = product_id başına MIN(product).",
            "copurchase_pairs": "En çok satan 24 ürün arasında en az 2 ortak faturası olan çiftler. Birlikte görülme, nedensellik değil.",
            "chart": "Dışa aktarılan Chart Studio grafiği: dilim başına tam sayı toplamlar.",
        },
    },
}

# ----------------------------------------------------------------------------------------- templates

CHARTS_TEMPLATE = '''"""@@charts_doc@@"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from html import escape
from pathlib import Path

LOCALE = "@@LOCALE@@"

# @@c_palette@@
COBALT = "#5264df"
NAVY = "#172238"
BRASS = "#b9905b"
MUTED = "#637086"
GRID = "#e4e7ee"
WHITE = "#ffffff"
SERIES_COLORS = (COBALT, BRASS, NAVY, MUTED, "#8e99ea")
FONT = "Inter, Helvetica, Arial, sans-serif"

DESC_LINE = "@@desc_line@@"
DESC_BAR = "@@desc_bar@@"
DESC_EMPTY = "@@desc_empty@@"

Point = tuple[str, float]


def format_number(value: float, unit: str = "") -> str:
    """@@d_format@@"""
    decimals = 0 if abs(value) >= 1000 or float(value).is_integer() else 2
    text = f"{abs(value):,.{decimals}f}"
    if LOCALE == "tr":
        text = text.translate(str.maketrans(",.", ".,"))
    return ("-" if value < 0 else "") + ("£" if unit == "GBP" else "") + text


def nice_ticks(maximum: float, count: int = 5) -> list[float]:
    """@@d_ticks@@"""
    if maximum <= 0:
        return [0.0, 1.0]
    raw = maximum / count
    magnitude = 10 ** math.floor(math.log10(raw))
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw)
    ticks = [0.0]
    while ticks[-1] < maximum - 1e-9:
        ticks.append(round(ticks[-1] + step, 10))
    return ticks


def _f(value: float) -> str:
    """@@d_coord@@"""
    return f"{value:.1f}"


def _header(width: int, height: int, title: str, desc: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="chart-title chart-desc">',
        f'  <title id="chart-title">{escape(title)}</title>',
        f'  <desc id="chart-desc">{escape(desc)}</desc>',
        f'  <rect width="{width}" height="{height}" fill="{WHITE}"/>',
        f'  <text x="24" y="32" font-family="{FONT}" font-size="16" font-weight="600" fill="{NAVY}">'
        f"{escape(title)}</text>",
    ]


def _text(x: float, y: float, value: str, *, anchor: str = "start", size: int = 11, color: str = MUTED) -> str:
    return (f'  <text x="{_f(x)}" y="{_f(y)}" text-anchor="{anchor}" font-family="{FONT}" '
            f'font-size="{size}" fill="{color}">{escape(value)}</text>')


def _short(label: str, limit: int = 34) -> str:
    return label if len(label) <= limit else label[: limit - 1] + "…"


def line_svg(points: Sequence[Point] | Mapping[str, Sequence[Point]], title: str, unit: str,
             *, width: int = 760, height: int = 380) -> str:
    """@@d_line@@"""
    series = {name: list(values) for name, values in points.items()} if isinstance(points, Mapping) else {"": list(points)}
    labels = list(dict.fromkeys(label for values in series.values() for label, _ in values))
    values = [value for items in series.values() for _, value in items]
    if not values:
        return "\\n".join(_header(width, height, title, DESC_EMPTY) + ["</svg>", ""])
    top_label, top_value = max(((label, value) for items in series.values() for label, value in items),
                               key=lambda item: item[1])
    desc = DESC_LINE.format(n=len(labels), first=labels[0], last=labels[-1], top_label=top_label,
                            top_value=format_number(top_value, unit))
    legend = len(series) > 1
    left, right, top, bottom = 88, 24, 72 if legend else 56, 56
    plot_w, plot_h = width - left - right, height - top - bottom
    ticks = nice_ticks(max(values))
    y_max = ticks[-1]
    position = {label: i for i, label in enumerate(labels)}

    def x_of(label: str) -> float:
        return left + (plot_w * position[label] / (len(labels) - 1) if len(labels) > 1 else plot_w / 2)

    def y_of(value: float) -> float:
        return top + plot_h - plot_h * value / y_max

    out = _header(width, height, title, desc)
    for tick in ticks:  # horizontal grid with value labels
        y = y_of(tick)
        out.append(f'  <line x1="{left}" y1="{_f(y)}" x2="{width - right}" y2="{_f(y)}" stroke="{GRID}" stroke-width="1"/>')
        out.append(_text(left - 8, y + 4, format_number(tick, unit), anchor="end"))
    out.append(f'  <line x1="{left}" y1="{top + plot_h}" x2="{width - right}" y2="{top + plot_h}" stroke="{MUTED}" stroke-width="1"/>')
    step = max(1, math.ceil(len(labels) / 12))  # at most ~12 period labels
    for i, label in enumerate(labels):
        if i % step == 0 or i == len(labels) - 1:
            out.append(_text(x_of(label), top + plot_h + 20, label, anchor="middle"))
    for index, (name, items) in enumerate(series.items()):
        color = SERIES_COLORS[index % len(SERIES_COLORS)]
        coords = " ".join(f"{_f(x_of(label))},{_f(y_of(value))}" for label, value in items)
        out.append(f'  <polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2" '
                   'stroke-linejoin="round" stroke-linecap="round"/>')
        for label, value in items:
            out.append(f'  <circle cx="{_f(x_of(label))}" cy="{_f(y_of(value))}" r="3" fill="{color}"/>')
        if legend:
            lx = left + index * 150
            out.append(f'  <rect x="{lx}" y="46" width="12" height="12" rx="2" fill="{color}"/>')
            out.append(_text(lx + 18, 56, _short(name, 20), size=12, color=NAVY))
    out += ["</svg>", ""]
    return "\\n".join(out)


def bar_svg(items: Sequence[Point], title: str, unit: str, *, width: int = 760) -> str:
    """@@d_bar@@"""
    items = list(items)
    row, top, bottom, label_w, value_w = 28, 56, 40, 250, 96
    height = top + row * max(len(items), 1) + bottom
    if not items:
        return "\\n".join(_header(width, height, title, DESC_EMPTY) + ["</svg>", ""])
    top_label, top_value = max(items, key=lambda item: item[1])
    desc = DESC_BAR.format(n=len(items), top_label=top_label, top_value=format_number(top_value, unit))
    left = 24 + label_w
    plot_w = width - left - value_w
    ticks = nice_ticks(max(value for _, value in items))
    x_max = ticks[-1]
    out = _header(width, height, title, desc)
    base = top + row * len(items)
    for tick in ticks:  # vertical grid with value labels
        x = left + plot_w * tick / x_max
        out.append(f'  <line x1="{_f(x)}" y1="{top - 6}" x2="{_f(x)}" y2="{base}" stroke="{GRID}" stroke-width="1"/>')
        out.append(_text(x, base + 18, format_number(tick, unit), anchor="middle"))
    for i, (label, value) in enumerate(items):
        y = top + row * i
        bar = plot_w * value / x_max
        out.append(_text(left - 10, y + 15, _short(label), anchor="end", size=12, color=NAVY))
        out.append(f'  <rect x="{left}" y="{_f(y + 3)}" width="{_f(bar)}" height="18" rx="2" fill="{COBALT}"/>')
        out.append(_text(left + bar + 6, y + 16, format_number(value, unit)))
    out += ["</svg>", ""]
    return "\\n".join(out)


def line_chart(points: Sequence[Point] | Mapping[str, Sequence[Point]], title: str, unit: str, path: Path) -> Path:
    """@@d_write_line@@"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(line_svg(points, title, unit), encoding="utf-8", newline="\\n")
    return path


def bar_chart(items: Sequence[Point], title: str, unit: str, path: Path) -> Path:
    """@@d_write_bar@@"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(bar_svg(items, title, unit), encoding="utf-8", newline="\\n")
    return path
'''

ANALYSIS_TEMPLATE = '''#!/usr/bin/env python3
"""@@py_doc@@"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

import charts

HERE = Path(__file__).resolve().parent
DEFAULT_DATA = HERE / "data" / "transactions.parquet"
EXPECTED_PATH = HERE / "expected.json"

# @@c_defaults@@
DEFAULT_START: str | None = @@START@@
DEFAULT_END: str | None = @@END@@
DEFAULT_COUNTRY: str | None = @@COUNTRY@@

FIGURE_TITLES = @@FIGURE_TITLES@@
WEEKDAYS = @@WEEKDAYS@@


@dataclass(frozen=True)
class Scope:
    """@@d_scope@@"""

    data: Path
    start: str | None = None
    end: str | None = None
    country: str | None = None

    def filters(self) -> dict[str, str]:
        """@@d_filters@@"""
        pairs = (("start", self.start), ("end", self.end), ("country", self.country))
        return {key: value for key, value in pairs if value}


# @@c_view@@
SALES_VIEW_SQL = """
@@SALES_VIEW@@
"""


def connect(scope: Scope) -> duckdb.DuckDBPyConnection:
    """@@d_connect@@"""
    con = duckdb.connect()
    con.execute("SET VARIABLE data_path = ?", [str(scope.data)])
    con.execute("SET VARIABLE start_date = ?", [scope.start])
    con.execute("SET VARIABLE end_date = ?", [scope.end])
    con.execute("SET VARIABLE country = ?", [scope.country])
    con.execute(SALES_VIEW_SQL)
    return con


def _rows(con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    """@@d_rows@@"""
    cursor = con.execute(sql, params or [])
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def kpis(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """@@d_kpis@@"""
    sql = """
@@SQL_kpis@@
    """
    return _rows(con, sql)[0]


def monthly_trend(con: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    """@@d_monthly@@"""
    sql = """
@@SQL_monthly_trend@@
    """
    return _rows(con, sql)


def top_countries(con: duckdb.DuckDBPyConnection, limit: int = @@D_top_countries_limit@@) -> list[dict[str, Any]]:
    """@@d_countries@@"""
    sql = """
@@SQL_top_countries@@
    """
    return _rows(con, sql, @@P_top_countries@@)


def top_products(con: duckdb.DuckDBPyConnection, limit: int = @@D_top_products_limit@@) -> list[dict[str, Any]]:
    """@@d_products@@"""
    sql = """
@@SQL_top_products@@
    """
    return _rows(con, sql, @@P_top_products@@)


def copurchase_pairs(con: duckdb.DuckDBPyConnection, candidates: int = @@D_copurchase_pairs_candidates@@,
                     min_shared: int = @@D_copurchase_pairs_min_shared@@, limit: int = @@D_copurchase_pairs_limit@@) -> list[dict[str, Any]]:
    """@@d_pairs@@"""
    sql = """
@@SQL_copurchase_pairs@@
    """
    return _rows(con, sql, @@P_copurchase_pairs@@)
@@CHART_BLOCK@@

def collect(scope: Scope) -> dict[str, Any]:
    """@@d_collect@@"""
    con = connect(scope)
    try:
        results: dict[str, Any] = {
            "kpis": kpis(con),
            "monthly_trend": monthly_trend(con),
            "top_countries": top_countries(con),
            "top_products": top_products(con),
            "copurchase_pairs": copurchase_pairs(con),
        }@@CHART_COLLECT@@
    finally:
        con.close()
    return results


def write_csv(rows: list[dict[str, Any]], path: Path) -> Path:
    """@@d_csv@@"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else [], lineterminator="\\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_figures(results: dict[str, Any], figures_dir: Path) -> list[Path]:
    """@@d_figures@@"""
    monthly = [(row["month"], row["gross_pence"] / 100) for row in results["monthly_trend"]]
    countries = [(row["country"], row["gross_pence"] / 100) for row in results["top_countries"]]
    products = [(row["product"], row["gross_pence"] / 100) for row in results["top_products"]]
    paths = [
        charts.line_chart(monthly, FIGURE_TITLES["monthly"], "GBP", figures_dir / "monthly_gross_sales.svg"),
        charts.bar_chart(countries, FIGURE_TITLES["countries"], "GBP", figures_dir / "top_countries.svg"),
        charts.bar_chart(products, FIGURE_TITLES["products"], "GBP", figures_dir / "top_products.svg"),
    ]@@CHART_FIGURE@@
    return paths


def write_outputs(results: dict[str, Any], out_dir: Path) -> list[Path]:
    """@@d_outputs@@"""
    paths = []
    for name, value in results.items():
        rows = [value] if isinstance(value, dict) else value
        paths.append(write_csv(rows, out_dir / f"{name}.csv"))
    return paths + write_figures(results, out_dir / "figures")


def check_against_expected(results: dict[str, Any], scope: Scope, expected_path: Path = EXPECTED_PATH) -> bool:
    """@@d_check@@"""
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    checks: list[tuple[bool, str, str]] = []
    filters = scope.filters()
    detail = json.dumps(filters, ensure_ascii=False)
    if filters != expected["filters"]:
        detail += f"  (@@c_scope_mismatch@@: {json.dumps(expected['filters'], ensure_ascii=False)})"
    checks.append((filters == expected["filters"], "scope", detail))
    for name, wanted in expected["results"].items():
        got = json.loads(json.dumps(results.get(name), default=str))  # same JSON types as the file
        if isinstance(wanted, dict):
            for key, value in wanted.items():
                ok = got.get(key) == value
                checks.append((ok, f"{name}.{key}", f"{value}" if ok else f"@@c_value_diff@@"))
            continue
        got = got or []
        detail = f"@@c_rows@@"
        if got != wanted:
            first = next((i for i, (a, b) in enumerate(zip(wanted, got)) if a != b), min(len(wanted), len(got)))
            detail = f"@@c_rows_diff@@"
        checks.append((got == wanted, name, detail))
    width = max(len(label) for _, label, _ in checks)
    for ok, label, detail in checks:
        print(f"{'✓' if ok else '✗'} {label.ljust(width)}  {detail}")
    failed = sum(1 for ok, _, _ in checks if not ok)
    print(f"@@c_ok@@" if not failed else f"@@c_fail@@")
    return not failed


def main(argv: list[str] | None = None) -> int:
    """@@d_main@@"""
    parser = argparse.ArgumentParser(description="@@arg_desc@@")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="@@arg_data@@")
    # @@c_cli@@
    parser.add_argument("--start", default=DEFAULT_START, help="@@arg_start@@")
    parser.add_argument("--end", default=DEFAULT_END, help="@@arg_end@@")
    parser.add_argument("--country", default=DEFAULT_COUNTRY, help="@@arg_country@@")
    parser.add_argument("--out", type=Path, default=Path("out"), help="@@arg_out@@")
    parser.add_argument("--check", action="store_true", help="@@arg_check@@")
    args = parser.parse_args(argv)
    if not args.data.exists():
        print(f"@@c_missing@@", file=sys.stderr)
        return 2
    scope = Scope(data=args.data, start=args.start or None, end=args.end or None, country=args.country or None)
    results = collect(scope)
    written = write_outputs(results, args.out)
    print(f"@@c_wrote@@")
    if args.check:
        return 0 if check_against_expected(results, scope) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

CHART_BLOCK = '''

# @@c_chart@@
CHART_SPEC: dict[str, Any] = @@CHART_SPEC@@
CHART_PARAMS: list[Any] = @@CHART_PARAMS@@


def chart(con: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    """@@d_chart@@"""
    sql = """
@@SQL_chart@@
    """
    return _rows(con, sql, CHART_PARAMS)


def chart_points(rows: list[dict[str, Any]]) -> dict[str, list[tuple[str, float]]]:
    """@@d_chart_points@@"""
    metric = CHART_SPEC["metric"]
    series: dict[str, list[tuple[str, float]]] = {}
    for row in rows:
        if metric == "gross_sales":
            value = row["pence"] / 100
        elif metric == "aov":
            value = row["pence"] / row["orders"] / 100 if row["orders"] else 0.0
        else:
            value = float(row[metric])
        if CHART_SPEC["dimension"] == "weekday":
            label = WEEKDAYS[int(row["x"]) - 1]
        else:
            label = str(row.get("label") or row["x"])
        series.setdefault(str(row["series"]), []).append((label, value))
    return series
'''
CHART_COLLECT = '''
        results["chart"] = chart(con)'''
CHART_FIGURE = '''
    if "chart" in results:
        points = chart_points(results["chart"])
        unit = "GBP" if CHART_SPEC["metric"] in ("gross_sales", "aov") else ""
        path = figures_dir / "chart.svg"
        if CHART_SPEC["dimension"] in ("month", "week") and (CHART_SPEC["chart"] != "bar" or len(points) > 1):
            paths.append(charts.line_chart(points if len(points) > 1 else points.get("all", []),
                                           FIGURE_TITLES["chart"], unit, path))
        else:
            paths.append(charts.bar_chart(points.get("all", []), FIGURE_TITLES["chart"], unit, path))'''


def _fill(template: str, values: dict[str, str]) -> str:
    def sub(match):
        key = match.group(1)
        if key not in values:
            raise KeyError(f"template token {key}")
        return values[key]

    return re.sub(r"@@([A-Za-z0-9_]+)@@", sub, template)


def _py_literal(value: dict) -> str:
    """A dict as a readable Python literal, one key per line."""
    lines = ["{"] + [f"    {key!r}: {item!r}," for key, item in value.items()] + ["}"]
    return "\n".join(lines)


def _indent_sql(sql: str) -> str:
    return textwrap.indent(sql, "        ")


def _charts_source(locale: str) -> str:
    t = L[locale]
    keys = ["charts_doc", "c_palette", "d_format", "d_ticks", "d_coord", "d_line", "d_bar", "d_write_line",
            "d_write_bar", "desc_line", "desc_bar", "desc_empty"]
    return _fill(CHARTS_TEMPLATE, {"LOCALE": locale, **{k: t[k] for k in keys}})


def _analysis_source(locale: str, filters: dict, chart: dict | None) -> str:
    t = L[locale]
    values = {k: v for k, v in t.items() if isinstance(v, str)}
    chart_doc = chart_fig = ""
    if chart:
        chart_doc = ", Chart Studio" if locale == "en" else ", Chart Studio grafiği"
        chart_fig = ", chart"
    values["py_doc"] = _fill(t["py_doc"], {"CHART_DOC": chart_doc, "CHART_FIG": chart_fig}).rstrip("\n") + "\n"
    values.update({
        "START": repr(filters.get("start")), "END": repr(filters.get("end")), "COUNTRY": repr(filters.get("country")),
        "FIGURE_TITLES": _py_literal({**t["fig"], **({"chart": chart["title"]} if chart else {})}),
        "WEEKDAYS": repr(t["weekdays"]),
        "SALES_VIEW": SALES_VIEW,
    })
    for name in QUERY_ORDER:
        sql, names = _python_sql(name)
        values[f"SQL_{name}"] = _indent_sql(sql)
        if names:
            values[f"P_{name}"] = "[" + ", ".join(names) + "]"
        for key, default in DEFAULTS.get(name, {}).items():
            values[f"D_{name}_{key}"] = str(default)
    if chart:
        values["CHART_BLOCK"] = _fill(CHART_BLOCK, {
            "CHART_SPEC": _py_literal(chart["spec"]),
            "CHART_PARAMS": repr(chart["params"]),
            "SQL_chart": _indent_sql(chart["sql"]),
            "d_chart": t["d_chart"], "d_chart_points": t["d_chart_points"], "c_chart": t["c_chart"],
        })
        values["CHART_COLLECT"] = CHART_COLLECT
        values["CHART_FIGURE"] = CHART_FIGURE
    else:
        values["CHART_BLOCK"] = values["CHART_COLLECT"] = values["CHART_FIGURE"] = ""
    return _fill(ANALYSIS_TEMPLATE, values)


def _sql_source(locale: str, m: dict, filters: dict, chart: dict | None, engine: str) -> str:
    t = L[locale]
    line = "-- " + "=" * 76
    head = [
        line,
        f"-- Context Layer · {_one_line(m['title'])} · analysis.sql",
        f"-- {t['sql_head']}",
        f"-- {t['sql_run']}",
        f"-- DuckDB {engine} · dataset SHA-256 {m['sha256']}",
        f"-- {t['sql_grain']}",
        line,
        "",
        f"-- {t['sql_params']}",
        f"SET VARIABLE data_path = {_literal(DATA_PATH)};",
        f"SET VARIABLE start_date = {_literal(filters.get('start'))};",
        f"SET VARIABLE end_date = {_literal(filters.get('end'))};",
        f"SET VARIABLE country = {_literal(filters.get('country'))};",
        "",
        f"-- {t['sql_view']}",
        SALES_VIEW + ";",
    ]
    blocks = []
    for name in QUERY_ORDER:
        sql, names = _python_sql(name)
        params = [DEFAULTS[name][n] for n in names]
        blocks += ["", f"-- name: {name}", f"-- {t['sql_q'][name]}", _inline(sql, params) + ";"]
    if chart:
        blocks += ["", "-- name: chart", f"-- {t['sql_q']['chart']}", _inline(chart["sql"], chart["params"]) + ";"]
    return "\n".join(head + blocks) + "\n"


# ------------------------------------------------------------------------------------------- README


def _md_escape(value) -> str:
    return str(value).replace("|", "\\|")


def _gbp(pence: int, locale: str) -> str:
    text = f"{pence / 100:,.2f}"
    if locale == "tr":
        text = text.translate(str.maketrans(",.", ".,"))
    return "£" + text


def _int(value: int, locale: str) -> str:
    text = f"{value:,}"
    return text.replace(",", ".") if locale == "tr" else text


R = {
    "en": {
        "title": "Context Layer analysis · {dataset}",
        "summary": ("This folder recomputes a Context Layer workbench analysis of **{dataset}** with plain DuckDB SQL "
                    "and a small Python script. It contains the filtered rows, the queries for the KPIs, the monthly "
                    "trend, the top countries and products and the co-purchase pairs{chart}, the figures, and the "
                    "expected results, so you can verify the numbers, then change the analysis and run it again."),
        "chart_summary": ", plus the exported Chart Studio chart",
        "quick": "Quick start",
        "quick_sql": "Or run the SQL directly with the DuckDB command-line client:",
        "no_data": ("> The data file was not included because it is larger than 6 MB. Create a Parquet file with the "
                    "columns in the data dictionary below and pass it with `--data path/to/transactions.parquet` "
                    "(for SQL, change `data_path` at the top of `analysis.sql`)."),
        "tree": "Files",
        "tree_desc": {
            "README.md": "this guide", "analysis.py": "Python script (only dependency: duckdb)",
            "analysis.sql": "the same queries as DuckDB SQL", "charts.py": "dependency-free SVG chart writer",
            "expected.json": "results at export time (integers), used by --check",
            "requirements.txt": "pinned DuckDB version", "data/": "filtered rows (Parquet)",
            "figures/": "pre-rendered SVG figures",
        },
        "scope": "Scope",
        "scope_rows": [("Dataset", "{title} (`{id}`)"), ("Source", "{source}"), ("Licence", "{license}"),
                       ("Dataset SHA-256", "`{sha}`"), ("Filters", "{filters}"), ("Rows in scope", "{rows}"),
                       ("Data file SHA-256", "{data_sha}")],
        "no_filters": "none (whole dataset)",
        "metrics": "Metric definitions",
        "metric_head": "| Metric | Unit | Formula | Note |",
        "dictionary": "Data dictionary",
        "dict_head": "| Column | Type | Description |",
        "columns": {
            "invoice": "Invoice number; one invoice is one order.",
            "product_id": "Product code (stock code).",
            "product": "Product description as recorded on the line.",
            "quantity": "Units on the line (always positive here).",
            "unit_price": "Price per unit in GBP.",
            "line_pence": "Line value: quantity × unit price, rounded to whole pence.",
            "order_date": "Invoice date.",
            "country": "Customer country as recorded by the retailer.",
        },
        "no_customer": "Customer identifiers are deliberately not exported.",
        "results": "Expected results",
        "kpi_head": "| KPI | Value |",
        "kpi_labels": {"row_count": "Rows", "orders": "Orders", "units": "Units", "gross_pence": "Gross sales",
                       "products": "Products", "aov": "Average order value"},
        "countries": "Top countries",
        "country_head": "| # | Country | Gross sales | Orders |",
        "products": "Top products",
        "product_head": "| # | Product | Code | Gross sales | Units |",
        "pairs": "Strongest co-purchase pairs",
        "pair_head": "| Product A | Product B | Shared orders |",
        "chart": "Chart Studio chart",
        "chart_text": "Exported ChartSpec (`CHART_SPEC` in `analysis.py`, query `chart` in `analysis.sql`): **{title}** — {rows} rows.",
        "figures": "Figures",
        "fig_alt": {"monthly_gross_sales": "Monthly gross sales", "top_countries": "Top countries",
                    "top_products": "Top products", "chart": "Chart Studio chart"},
        "change": "How to change it",
        "recipes": [
            ("Another country or period",
             "Use the flags; every query reads the same filtered `sales` view.\n\n"
             "```bash\npython analysis.py --country Germany --start 2011-01-01 --end 2011-06-30 --out out-germany\n```\n\n"
             "The bundled file holds only the exported scope; for a wider scope pass a larger file with `--data`. "
             "`--check` is only meaningful for the exported scope. In SQL, edit the `SET VARIABLE` lines."),
            ("Add a metric",
             "Distinct customers are not available: customer identifiers are excluded from the export. "
             "Units per order is: add this line to the `SELECT` in `kpis()` (and in `analysis.sql`):\n\n"
             "```sql\nROUND(SUM(quantity)::DOUBLE / NULLIF(COUNT(DISTINCT invoice), 0), 2) AS units_per_order,\n```\n\n"
             "It is a float, so add it to `expected.json` only if you also compare it with a tolerance."),
            ("Group by week instead of month",
             "In `monthly_trend()` replace `strftime(order_date, '%Y-%m')` with "
             "`date_trunc('week', order_date)::DATE` (ISO weeks start on Monday); the first and last weeks "
             "of a scope can be partial."),
            ("Export to CSV for a BI tool",
             "`python analysis.py --out exports` writes one CSV per result. For the filtered rows, append to "
             "`analysis.sql`:\n\n```sql\nCOPY (SELECT * FROM sales) TO 'sales.csv' (HEADER);\n```"),
        ],
        "repro": "Reproducibility",
        "repro_text": [
            "`expected.json` holds every result at export time as integers (pence and counts), with the dataset "
            "SHA-256, the filters and the engine version.",
            "`python analysis.py --check` recomputes everything and compares it exactly; it prints a ✓/✗ line per "
            "check and exits with 1 on any difference.",
            "Queries have total orderings (ties broken by key), so results are deterministic. Exports of the same "
            "scope are byte-identical (sorted files, fixed timestamps).",
            "Engine: DuckDB {engine} (`requirements.txt`). Other DuckDB versions should give the same integers but "
            "are not what was tested.",
        ],
        "limits": "Limitations",
        "limits_text": [
            "Gross sales are positive invoice lines before returns; they are not net revenue or profit.",
            "Cancelled invoices and lines with non-positive quantity or price were removed during preparation.",
            "Service lines such as POSTAGE, Manual or bank charges are kept as products where they occur.",
            "Distinct order counts are not additive across months, countries or products.",
            "Co-purchase pairs are restricted to the 24 best-selling products and show co-occurrence, not causation.",
        ],
        "limit_public": "This is public historical data; it is not current or representative market data.",
        "limit_synthetic": "This is synthetic test data, not real commercial records.",
        "attribution": "Data source and attribution",
        "generated": "Generated by Context Layer ({recipe}).",
    },
    "tr": {
        "title": "Context Layer analizi · {dataset}",
        "summary": ("Bu klasör, **{dataset}** için bir Context Layer çalışma alanı analizini düz DuckDB SQL ve küçük bir "
                    "Python betiğiyle yeniden hesaplar. Filtreli satırları; KPI'lar, aylık trend, ilk ülkeler ve ürünler "
                    "ile birlikte alım çiftleri için sorguları{chart}; şekilleri ve beklenen sonuçları içerir. Böylece "
                    "sayıları doğrulayabilir, analizi değiştirip yeniden çalıştırabilirsiniz."),
        "chart_summary": " ve dışa aktarılan Chart Studio grafiğini",
        "quick": "Hızlı başlangıç",
        "quick_sql": "Ya da SQL'i doğrudan DuckDB komut satırı istemcisiyle çalıştırın:",
        "no_data": ("> Veri dosyası 6 MB'tan büyük olduğu için pakete eklenmedi. Aşağıdaki veri sözlüğündeki sütunlarla "
                    "bir Parquet dosyası oluşturup `--data yol/transactions.parquet` ile verin (SQL için "
                    "`analysis.sql` başındaki `data_path` değerini değiştirin)."),
        "tree": "Dosyalar",
        "tree_desc": {
            "README.md": "bu kılavuz", "analysis.py": "Python betiği (tek bağımlılık: duckdb)",
            "analysis.sql": "aynı sorgular, DuckDB SQL olarak", "charts.py": "bağımlılıksız SVG grafik yazıcısı",
            "expected.json": "dışa aktarım anındaki sonuçlar (tam sayı), --check kullanır",
            "requirements.txt": "sabitlenmiş DuckDB sürümü", "data/": "filtreli satırlar (Parquet)",
            "figures/": "önceden üretilmiş SVG şekiller",
        },
        "scope": "Kapsam",
        "scope_rows": [("Veri seti", "{title} (`{id}`)"), ("Kaynak", "{source}"), ("Lisans", "{license}"),
                       ("Veri seti SHA-256", "`{sha}`"), ("Filtreler", "{filters}"), ("Kapsamdaki satır", "{rows}"),
                       ("Veri dosyası SHA-256", "{data_sha}")],
        "no_filters": "yok (tüm veri seti)",
        "metrics": "Metrik tanımları",
        "metric_head": "| Metrik | Birim | Formül | Not |",
        "dictionary": "Veri sözlüğü",
        "dict_head": "| Sütun | Tür | Açıklama |",
        "columns": {
            "invoice": "Fatura numarası; bir fatura bir sipariştir.",
            "product_id": "Ürün kodu (stok kodu).",
            "product": "Satırda kayıtlı ürün açıklaması.",
            "quantity": "Satırdaki adet (burada her zaman pozitif).",
            "unit_price": "GBP cinsinden birim fiyat.",
            "line_pence": "Satır tutarı: adet × birim fiyat, tam kuruşa yuvarlanmış.",
            "order_date": "Fatura tarihi.",
            "country": "Perakendecinin kaydettiği müşteri ülkesi.",
        },
        "no_customer": "Müşteri kimlikleri bilerek dışa aktarılmaz.",
        "results": "Beklenen sonuçlar",
        "kpi_head": "| Gösterge | Değer |",
        "kpi_labels": {"row_count": "Satır", "orders": "Sipariş", "units": "Adet", "gross_pence": "Brüt satış",
                       "products": "Ürün", "aov": "Ortalama sipariş"},
        "countries": "İlk ülkeler",
        "country_head": "| # | Ülke | Brüt satış | Sipariş |",
        "products": "İlk ürünler",
        "product_head": "| # | Ürün | Kod | Brüt satış | Adet |",
        "pairs": "En güçlü birlikte alım çiftleri",
        "pair_head": "| Ürün A | Ürün B | Ortak sipariş |",
        "chart": "Chart Studio grafiği",
        "chart_text": "Dışa aktarılan ChartSpec (`analysis.py` içinde `CHART_SPEC`, `analysis.sql` içinde `chart` sorgusu): **{title}** — {rows} satır.",
        "figures": "Şekiller",
        "fig_alt": {"monthly_gross_sales": "Aylık brüt satış", "top_countries": "İlk ülkeler",
                    "top_products": "İlk ürünler", "chart": "Chart Studio grafiği"},
        "change": "Nasıl değiştirilir",
        "recipes": [
            ("Başka bir ülke veya dönem",
             "Bayrakları kullanın; tüm sorgular aynı filtreli `sales` görünümünü okur.\n\n"
             "```bash\npython analysis.py --country Germany --start 2011-01-01 --end 2011-06-30 --out out-germany\n```\n\n"
             "Paketteki dosya yalnız dışa aktarılan kapsamı içerir; daha geniş bir kapsam için `--data` ile daha büyük "
             "bir dosya verin. `--check` yalnız dışa aktarılan kapsam için anlamlıdır. SQL'de `SET VARIABLE` "
             "satırlarını düzenleyin."),
            ("Metrik ekleyin",
             "Benzersiz müşteri sayısı kullanılamaz: müşteri kimlikleri dışa aktarıma dahil değildir. Sipariş başına "
             "adet için `kpis()` içindeki `SELECT`'e (ve `analysis.sql`'e) şu satırı ekleyin:\n\n"
             "```sql\nROUND(SUM(quantity)::DOUBLE / NULLIF(COUNT(DISTINCT invoice), 0), 2) AS units_per_order,\n```\n\n"
             "Bu bir ondalık sayıdır; `expected.json`'a ancak toleranslı karşılaştırma eklerseniz koyun."),
            ("Ay yerine haftaya göre gruplayın",
             "`monthly_trend()` içinde `strftime(order_date, '%Y-%m')` ifadesini "
             "`date_trunc('week', order_date)::DATE` ile değiştirin (ISO haftaları pazartesi başlar); kapsamın ilk ve "
             "son haftası kısmi olabilir."),
            ("BI aracı için CSV'ye aktarın",
             "`python analysis.py --out exports` her sonuç için bir CSV yazar. Filtreli satırlar için "
             "`analysis.sql` sonuna ekleyin:\n\n```sql\nCOPY (SELECT * FROM sales) TO 'sales.csv' (HEADER);\n```"),
        ],
        "repro": "Yeniden üretilebilirlik",
        "repro_text": [
            "`expected.json`, dışa aktarım anındaki tüm sonuçları tam sayı (kuruş ve sayım) olarak; veri seti "
            "SHA-256'sı, filtreler ve motor sürümüyle birlikte tutar.",
            "`python analysis.py --check` her şeyi yeniden hesaplar ve birebir karşılaştırır; her denetim için ✓/✗ "
            "satırı yazar ve herhangi bir farkta 1 ile çıkar.",
            "Sorgular tam sıralıdır (eşitlikler anahtarla çözülür), dolayısıyla sonuçlar deterministiktir. Aynı "
            "kapsamın dışa aktarımları bayt bayt aynıdır (sıralı dosyalar, sabit zaman damgaları).",
            "Motor: DuckDB {engine} (`requirements.txt`). Diğer DuckDB sürümlerinin aynı tam sayıları vermesi "
            "beklenir ancak test edilen sürüm bu değildir.",
        ],
        "limits": "Sınırlamalar",
        "limits_text": [
            "Brüt satış, iadeler öncesi pozitif fatura satırlarıdır; net gelir veya kâr değildir.",
            "İptal edilen faturalar ve adedi ya da fiyatı pozitif olmayan satırlar hazırlıkta çıkarıldı.",
            "POSTAGE, Manual veya banka masrafı gibi hizmet satırları geçtikleri yerde ürün olarak korunur.",
            "Benzersiz sipariş sayıları aylar, ülkeler veya ürünler arasında toplanamaz.",
            "Birlikte alım çiftleri en çok satan 24 ürünle sınırlıdır ve nedensellik değil birlikte görülme gösterir.",
        ],
        "limit_public": "Bu, kamuya açık tarihsel veridir; güncel veya temsili pazar verisi değildir.",
        "limit_synthetic": "Bu, sentetik test verisidir; gerçek ticari kayıt değildir.",
        "attribution": "Veri kaynağı ve atıf",
        "generated": "Context Layer tarafından üretildi ({recipe}).",
    },
}


def _attribution(source: dict, title: str, locale: str) -> list[str]:
    """Citation lines built from the dataset's own source metadata (nothing hard-coded)."""
    lines = []
    parts = [p for p in [source.get("publisher"), title] if p]
    if parts:
        lines.append(" · ".join(parts))
    licence = "Lisans" if locale == "tr" else "Licence"
    for label, key in [("URL", "url"), ("DOI", "doi"), (licence, "license")]:
        if source.get(key):
            value = source[key]
            if key == "doi":
                value = f"[{value}](https://doi.org/{value})"
            lines.append(f"{label}: {value}")
    if source.get("description"):
        lines.append(str(source["description"]))
    return lines


def _readme(locale: str, m: dict, filters: dict, expected: dict, column_types: dict, data_included: bool,
            data_sha: str, engine: str, chart: dict | None, files: list[str]) -> str:
    r = R[locale]
    res = expected["results"]
    k = res["kpis"]
    out = [f"# {r['title'].format(dataset=_one_line(m['title']))}", ""]
    out += [r["summary"].format(dataset=_one_line(m["title"]), chart=r["chart_summary"] if chart else ""), ""]
    out += [f"## {r['quick']}", "", "```bash", "python -m venv .venv",
            "source .venv/bin/activate      # Windows: .venv\\Scripts\\activate",
            "pip install -r requirements.txt", "python analysis.py --check", "```", "",
            r["quick_sql"], "", "```bash", "duckdb < analysis.sql", "# " + ("or" if locale == "en" else "veya"),
            'duckdb -c ".read analysis.sql"', "```", ""]
    if not data_included:
        out += [r["no_data"], ""]
    out += [f"## {r['tree']}", "", "```text"]
    tree = sorted({f.split("/")[0] + ("/" if "/" in f else "") for f in files})
    width = max(len(x) for x in tree) + 2
    for name in tree:
        if name.endswith("/"):
            out.append(f"{name.ljust(width)}{r['tree_desc'].get(name, '')}")
            for f in sorted(x for x in files if x.startswith(name)):
                out.append(f"  {f[len(name):]}")
        else:
            out.append(f"{name.ljust(width)}{r['tree_desc'].get(name, '')}")
    out += ["```", ""]
    src = m.get("source") or {}
    filter_text = ", ".join(f"{key} = `{value}`" for key, value in filters.items()) or r["no_filters"]
    out += [f"## {r['scope']}", "", "| | |", "|---|---|"]
    for label, value in r["scope_rows"]:
        out.append(f"| {label} | " + _md_escape(value.format(
            title=_one_line(m["title"]), id=m["id"], source=_one_line(src.get("publisher") or src.get("kind") or "—"),
            license=src.get("license") or "—", sha=m["sha256"], filters=filter_text,
            rows=_int(expected["row_count"], locale),
            data_sha=f"`{data_sha}`" if data_included else "—")) + " |")
    out += ["", f"## {r['metrics']}", "", r["metric_head"], "|---|---|---|---|"]
    for metric in METRICS:
        title, note = (metric["title"], metric["note"]) if locale == "tr" else METRIC_EN[metric["id"]]
        out.append(f"| {title} (`{metric['id']}`) | {metric['unit']} | `{metric['formula']}` | {_md_escape(note)} |")
    out += ["", f"## {r['dictionary']}", "", r["dict_head"], "|---|---|---|"]
    for col in COLUMNS:
        out.append(f"| `{col}` | {column_types.get(col, '')} | {r['columns'][col]} |")
    out += ["", r["no_customer"], ""]
    out += [f"## {r['results']}", "", r["kpi_head"], "|---|---:|"]
    labels = r["kpi_labels"]
    for key in ["row_count", "orders", "units", "products"]:
        out.append(f"| {labels[key]} | {_int(k[key], locale)} |")
    out.append(f"| {labels['gross_pence']} | {_gbp(k['gross_pence'], locale)} |")
    aov = round(k["gross_pence"] / k["orders"]) if k["orders"] else 0
    out.append(f"| {labels['aov']} | {_gbp(aov, locale)} |")
    out += ["", f"### {r['countries']}", "", r["country_head"], "|---:|---|---:|---:|"]
    for i, row in enumerate(res["top_countries"], 1):
        out.append(f"| {i} | {_md_escape(row['country'])} | {_gbp(row['gross_pence'], locale)} | {_int(row['orders'], locale)} |")
    out += ["", f"### {r['products']}", "", r["product_head"], "|---:|---|---|---:|---:|"]
    for i, row in enumerate(res["top_products"], 1):
        out.append(f"| {i} | {_md_escape(row['product'])} | `{_md_escape(row['product_id'])}` | "
                   f"{_gbp(row['gross_pence'], locale)} | {_int(row['units'], locale)} |")
    if res["copurchase_pairs"]:
        out += ["", f"### {r['pairs']}", "", r["pair_head"], "|---|---|---:|"]
        for row in res["copurchase_pairs"][:5]:
            out.append(f"| {_md_escape(row['product_a_name'])} | {_md_escape(row['product_b_name'])} | "
                       f"{_int(row['shared_orders'], locale)} |")
    if chart:
        out += ["", f"### {r['chart']}", "", r["chart_text"].format(title=chart["title"], rows=len(res["chart"])), "",
                "```json", json.dumps(chart["spec"], ensure_ascii=False, indent=2), "```"]
    out += ["", f"## {r['figures']}", ""]
    for name in ["monthly_gross_sales", "top_countries", "top_products"] + (["chart"] if chart else []):
        out += [f"![{r['fig_alt'][name]}](figures/{name}.svg)", ""]
    out += [f"## {r['change']}", ""]
    for i, (title, body) in enumerate(r["recipes"], 1):
        out += [f"### {i}. {title}", "", body, ""]
    out += [f"## {r['repro']}", ""]
    out += [f"- {line.format(engine=engine)}" for line in r["repro_text"]] + [""]
    out += [f"## {r['limits']}", ""]
    limits = list(r["limits_text"])
    kind = src.get("kind")
    if kind == "public":
        limits.append(r["limit_public"])
    elif kind == "synthetic":
        limits.append(r["limit_synthetic"])
    out += [f"- {line}" for line in limits] + [""]
    out += [f"## {r['attribution']}", ""]
    out += [f"- {line}" for line in _attribution(src, _one_line(m["title"]), locale)] + [""]
    out += [f"_{r['generated'].format(recipe=m.get('recipe_version', 'retail-v1'))}_", ""]
    return "\n".join(out)


# ------------------------------------------------------------------------------------------- engine


def _load_module(name: str, source: str, filename: str, extra: dict[str, types.ModuleType] | None = None):
    """Execute generated source (our own template, never user input) as a module."""
    module = types.ModuleType(name)
    module.__file__ = filename
    saved = {k: sys.modules.get(k) for k in [name, *(extra or {})]}
    sys.modules[name] = module
    sys.modules.update(extra or {})
    try:
        exec(compile(source, filename, "exec"), module.__dict__)
    finally:
        for key, value in saved.items():
            if value is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value
    return module


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _zip(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            info = zipfile.ZipInfo(path, date_time=ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (0o100755 if path == "analysis.py" else 0o100644) << 16
            archive.writestr(info, files[path])
    return buffer.getvalue()


def _chart_bundle(spec_obj, m: dict, locale: str) -> dict:
    from analysis.chart_studio import compile_query, validate_spec, _T as chart_text

    warnings: list[str] = []
    spec = validate_spec(spec_obj, m, locale=locale, warnings=warnings)
    sql, params = compile_query(spec, start=spec["start"], end=spec["end"], source="sales", with_sd=False,
                                locale=locale)
    title = chart_text[locale]["title"][spec["dimension"]].format(m=chart_text[locale]["metric"][spec["metric"]],
                                                                  n=spec["top_n"])
    return {"spec": spec, "sql": sql, "params": params, "title": title[:1].upper() + title[1:], "warnings": warnings}


def export_code(request: dict) -> dict:
    """Worker action ``code_export`` (AW-16 §1)."""
    m = meta(request["dataset"])
    where, args, clean = filters_for(request, m)
    locale = "en" if request.get("locale") == "en" else "tr"
    kind = request.get("format", "bundle")
    if kind not in FORMATS:
        raise ValueError("Geçersiz dışa aktarım biçimi." if locale == "tr" else "Invalid export format.")
    chart = _chart_bundle(request["chart"], m, locale) if request.get("chart") is not None else None
    engine = duckdb.__version__
    analysis_py = _analysis_source(locale, clean, chart)
    analysis_sql = _sql_source(locale, m, clean, chart, engine)
    stem = f"context-layer-{m['id']}-analysis"
    if kind in ("python", "sql"):
        text = analysis_py if kind == "python" else analysis_sql
        payload = text.encode("utf-8")
        name = "analysis.py" if kind == "python" else "analysis.sql"
        return {
            "format": kind, "filename": f"{stem}.{'py' if kind == 'python' else 'sql'}",
            "content_type": "text/x-python" if kind == "python" else "application/sql",
            "base64": base64.b64encode(payload).decode(), "bytes": len(payload), "sha256": _sha(payload),
            "data_included": False, "files": [{"path": name, "bytes": len(payload), "sha256": _sha(payload)}],
            "preview": {name: text}, "warnings": chart["warnings"] if chart else [],
        }

    charts_py = _charts_source(locale)
    work = Path(tempfile.mkdtemp(prefix="cl-export-"))
    try:
        parquet = work / "transactions.parquet"
        with duckdb.connect(str(DATA / (m["id"] + ".duckdb")), read_only=True) as con:
            con.execute("SET threads = 1")  # single writer thread: byte-stable Parquet
            con.execute(
                "COPY (SELECT " + ", ".join(COLUMNS) + " FROM transactions" + where
                + " ORDER BY order_date, invoice, product_id, quantity, line_pence, unit_price, product, country) TO '"
                + str(parquet).replace("'", "''") + "' (FORMAT parquet, COMPRESSION zstd)",
                args,
            )
        data_bytes = parquet.read_bytes()
        data_included = len(data_bytes) <= MAX_DATA_BYTES
        with duckdb.connect() as con:
            column_types = {name: str(kind_) for name, kind_, *_ in con.execute(
                "DESCRIBE SELECT * FROM read_parquet(?)", [str(parquet)]).fetchall()}
        if "customer_id" in column_types:
            raise ValueError("customer_id must not be exported")

        charts_module = _load_module("charts", charts_py, "charts.py")
        script = _load_module("context_layer_export_analysis", analysis_py, "analysis.py", {"charts": charts_module})
        scope = script.Scope(data=parquet, start=clean.get("start"), end=clean.get("end"), country=clean.get("country"))
        results = json.loads(json.dumps(script.collect(scope), default=str))
        _cross_check(request, clean, results)
        figures_dir = work / "figures"
        script.write_figures(results, figures_dir)

        expected = {
            "schema": EXPECTED_SCHEMA,
            "dataset": {"id": m["id"], "title": m["title"], "sha256": m["sha256"]},
            "filters": clean,
            "engine": f"duckdb {engine}",
            "row_count": results["kpis"]["row_count"],
            "data_file": {"path": DATA_PATH, "included": data_included, "bytes": len(data_bytes),
                          "sha256": _sha(data_bytes)},
            "results": results,
        }
        files: dict[str, bytes] = {
            "analysis.py": analysis_py.encode("utf-8"),
            "analysis.sql": analysis_sql.encode("utf-8"),
            "charts.py": charts_py.encode("utf-8"),
            "expected.json": (json.dumps(expected, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
            "requirements.txt": f"duckdb=={engine}\n".encode(),
        }
        for svg in sorted(figures_dir.glob("*.svg")):
            files[f"figures/{svg.name}"] = svg.read_bytes()
        if data_included:
            files[DATA_PATH] = data_bytes
        readme = _readme(locale, m, clean, expected, column_types, data_included, _sha(data_bytes), engine, chart,
                         sorted([*files, "README.md"]))
        files["README.md"] = readme.encode("utf-8")
    finally:
        shutil.rmtree(work, ignore_errors=True)

    archive = _zip(files)
    return {
        "format": "bundle",
        "filename": f"{stem}.zip",
        "content_type": "application/zip",
        "base64": base64.b64encode(archive).decode(),
        "bytes": len(archive),
        "sha256": _sha(archive),
        "data_included": data_included,
        "files": [{"path": p, "bytes": len(files[p]), "sha256": _sha(files[p])} for p in sorted(files)],
        "preview": {"README.md": readme, "analysis.py": analysis_py, "analysis.sql": analysis_sql},
        "warnings": chart["warnings"] if chart else [],
    }


def _cross_check(request: dict, clean: dict, results: dict) -> None:
    """The exported script must reproduce the workbench overview exactly before anything ships."""
    observed = overview({"dataset": request["dataset"], "filters": clean})
    s, k = observed["summary"], results["kpis"]
    same = (s["rows"], s["orders"], s["units"], s["gross_pence"], s["products"]) == (
        k["row_count"], k["orders"], k["units"], k["gross_pence"], k["products"])
    same = same and [(c["label"], c["pence"], c["orders"]) for c in observed["countries"]] == [
        (c["country"], c["gross_pence"], c["orders"]) for c in results["top_countries"]]
    same = same and [(x["period"], x["pence"], x["orders"]) for x in observed["series"]] == [
        (x["month"], x["gross_pence"], x["orders"]) for x in results["monthly_trend"]]
    if not same:
        raise ValueError("Dışa aktarılan kod çalışma alanı sonuçlarını yeniden üretmedi; paket oluşturulmadı.")
