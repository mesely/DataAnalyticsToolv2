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

from analysis.scope import SERVICE_CODES as _SERVICE_CODES

# v3 G5: postage, fees and adjustments are in gross sales but are not products (analysis/scope.py), so the product
# ranking and the co-purchase candidates leave them out, exactly as the workspace does.
PRODUCTS_ONLY = "UPPER(product_id) NOT IN (" + ", ".join("'" + c + "'" for c in sorted(_SERVICE_CODES)) + ")"

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
WHERE @products_only
GROUP BY product_id
ORDER BY gross_pence DESC, product_id
LIMIT @limit""",
    "copurchase_pairs": """WITH candidates AS (
    SELECT product_id
    FROM sales
    WHERE @products_only
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
SQL = {k: v.replace("@products_only", PRODUCTS_ONLY) for k, v in SQL.items()}
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
        "d_chart": "Chart rows: one per bucket (period × series, or ranked category) with integer totals.\n\n    pence = gross sales in GBP pence, orders = distinct invoices, units = SUM(quantity). On a month or\n    week axis every period of the chart scope is present: a period without rows has zeros (average\n    order value is then missing), and `partial` marks a first/last period the scope does not fully\n    cover. These are exactly the values Chart Studio plots.\n    ",
        "d_chart_points": "Turn chart rows into (label, value) points per series for the figure; None is a gap.",
        "c_chart": "Chart Studio ChartSpec v1 exported with this bundle. CHART_VIEW_SQL is generated from it (countries, exclusions and top N are written into the SQL); the Python functions read the metric and the window from here.",
        "c_chart_scope": "Chart scope: the overlap of the dataset's date range, the --start/--end filters and the chart's own dates. analysis.sql runs the same two statements.",
        "c_chart_view": "One row per chart bucket; every chart query reads this view. Same SQL as in analysis.sql.",
        "d_prepare_chart": "Set the chart scope variables and create the `chart_buckets` view on top of `sales`.",
        "d_metric_value": "The plotted value of a chart row in the metric's unit (GBP or a count), as in Chart Studio.\n\n    Average order value is missing (None) for a bucket without orders, never zero.\n    ",
        "d_to_int": "value × scale rounded to an integer for expected.json (halves to even); None stays None.",
        "d_chart_label": "Axis label of a chart row: weekday name, product name or the bucket key.",
        "d_chart_intervals": "Interval bounds in GBP per chart row (aligned with results['chart']); None where there is none.",
        "d_chart_figure": "Write chart.svg: the chart rows with the statistic drawn over them (see chart_overlay).",
        "c_bar_order": "Bar layout: rows arrive in rank or calendar order; the ChartSpec sort is applied as in Chart Studio.",
        "d_overlay_none": "The exported chart has no statistic, so nothing is drawn over the data.",
        "d_overlay_ci95": "Interval whiskers per bucket (lower and upper bound in GBP).",
        "d_overlay_trend": "The fitted trend line, drawn dashed over the complete periods it was fitted on.",
        "d_overlay_band": "The control band: shaded from the lower to the upper limit, with the mean as a dashed line.",
        "d_overlay_ma": "The moving average of each series, drawn dashed in the series colour.",
        "c_ci_level": "Confidence level of the interval. 0.99 gives a 99% interval (expected.json then no longer matches).",
        "d_ci95": "t-based confidence interval of the mean order value per bucket.\n\n    For each bucket with n >= 2 orders: mean ± t(0.5 + level/2, n − 1) · sd / √n, where mean and sd\n    (sample standard deviation) are over the bucket's order totals in pence and t is the Student-t\n    quantile from stats.py. The SQL derives mean and sd from exact integer sums, so the result does not\n    depend on floating-point summation order and is identical on every run. Values are integer pence.\n    Assumes independent order totals and a roughly normal mean; skewed totals and small n can mislead.\n    ",
        "c_stat_scale": "Statistic values are stored ×100 as integers: pence for GBP metrics, hundredths for counts.",
        "c_fraction_scale": "R² and the p-value are stored ×1,000,000 (six decimals) as integers.",
        "d_trend": "Ordinary least-squares trend y = intercept + slope · i over the complete periods.\n\n    i is the period's position in the chart scope (0 = index_origin): partial first/last periods keep\n    their place but are not fitted, and periods without a value (average order value with no orders)\n    are skipped. R² = Sxy² / (Sxx · Syy); the two-sided p-value of the slope uses a t test with n − 2\n    degrees of freedom (stats.py). Needs at least 3 periods. Same estimator as Chart Studio and\n    scipy.stats.linregress. The trend describes the past; it is not a forecast.\n    ",
        "c_p_value": "a perfect fit (R² = 1) has no residual variance; its p-value is reported as 0",
        "c_sigmas": "Width of the control band in standard deviations (3.0 gives the classic 3-sigma limits).",
        "d_band": "Control band: mean ± sigmas · sd of the metric over the complete periods.\n\n    sd is the sample standard deviation (n − 1). Periods outside the band are listed in `outside`;\n    they may lie outside ordinary variation, but the cause cannot be read from this data. Needs at\n    least 3 complete periods.\n    ",
        "d_ma": "Trailing moving average of `window` complete periods, per series.\n\n    Partial periods are removed before the window is applied, so they never enter an average; a point\n    is produced only when the window holds `window` consecutive periods that all have a value. The\n    point is labelled with the window's last period.\n    ",
        "c_ma_skip": "a gap or a missing value inside the window: no point (as in Chart Studio)",
        "overlay": {"none": "", "ci95": "95% confidence interval", "trend": "Linear trend",
                    "control_band": "Control band (mean ± 2 sd)", "moving_average": "{w}-period moving average"},
        "d_overlay": "A statistic drawn over a chart, in the chart's unit.\n\n    intervals  {series: [(label, lower, upper)]}  whiskers with caps (confidence interval)\n    lines      {series: [(label, value)]}         dashed lines (trend, moving average)\n    band       (lower, mean, upper)               shaded band with a dashed mean (control band)\n    label      legend text\n    ",
        "d_segments": "Split a polyline at missing values (None): a gap is drawn as a gap, never as zero.",
        "c_axis_height": "Everything that is drawn sets the height of the value axis, so whiskers and bands are never cut off.",
        "c_clip": "Values below zero (a lower bound can be negative) are cut at the axis; the data keeps them.",
        "c_band_back": "shaded band behind everything else",
        "c_grid_h": "horizontal grid with value labels",
        "c_grid_v": "vertical grid with value labels",
        "c_labels": "at most ~12 period labels; the last one is always shown",
        "c_whiskers": "whiskers with caps",
        "c_dashed": "dashed statistic lines on top of the data",
        "c_bar_legend": "legend under the title: a whisker sample and what it shows",
        "c_series_order": "series in chart order",
        "stats_doc": """Student-t distribution without dependencies: CDF, two-sided p-value and quantile.

analysis.py uses t_quantile() for the confidence interval and t_two_sided_p() for the p-value of the
trend slope. Results agree with scipy.special.stdtr / stdtrit to better than 1e-9 relative error.

Method
    For t > 0 with ν degrees of freedom and x = ν / (ν + t²):
        P(T > t)     = ½ · I_x(ν/2, ½)
        P(0 < T < t) = ½ · I_{1−x}(½, ν/2)
    where I is the regularized incomplete beta function. Both parts come from the continued fraction of
    I (modified Lentz's method, as betacf in Numerical Recipes, 3rd ed., §6.4), evaluated on the side
    where it converges fast and with 1 − x formed exactly, so tiny tails and t close to 0 keep full
    precision. The quantile brackets the root, bisects to about six digits, then polishes it with
    Newton steps on the density.
""",
        "c_stats_constants": "Accuracy target of the continued fraction, a floor that keeps Lentz's method away from division by zero, and an iteration cap.",
        "d_log_beta": "log B(a, b) via log-gamma.",
        "d_betacf": "Continued fraction of the incomplete beta function (Numerical Recipes betacf, modified Lentz).\n\n    Converges quickly for x < (a + 1) / (a + b + 2); otherwise callers use the symmetry\n    I_x(a, b) = 1 − I_{1−x}(b, a).\n    ",
        "c_even_step": "even step d_{2m} of the fraction",
        "c_odd_step": "odd step d_{2m+1}; stop when the update no longer changes the value",
        "d_pair": "(I_x(a, b), I_y(b, a)) with y = 1 − x passed separately, so neither loses precision.\n\n    The two values add up to 1: the smaller one is computed from the continued fraction, the other\n    as its complement.\n    ",
        "c_symmetry": "evaluate the fraction on the side where it converges fast",
        "d_betainc": "Regularized incomplete beta function I_x(a, b) (same as scipy.special.betainc(a, b, x)).",
        "d_split": "(P(T > |t|), P(0 < T < |t|)) for a Student-t variable with df degrees of freedom; they add up to ½.",
        "c_split": "x = df / (df + t²) and 1 − x = t² / (df + t²) are both formed directly",
        "d_cdf": "P(T ≤ t) for a Student-t variable with df degrees of freedom (scipy.special.stdtr(df, t)).",
        "d_two_sided": "Two-sided p-value P(|T| ≥ |t|), as in the slope test of a linear regression.",
        "d_pdf": "Density of the Student-t distribution (used by the Newton steps of t_quantile).",
        "d_quantile": "The t with P(T ≤ t) = p (scipy.special.stdtrit(df, p)); 0 < p < 1 and df > 0.",
        "c_target": "solve on the tail for extreme p and on the centre near ½, where each is accurate",
        "d_gap": "Increasing in t and zero at the quantile.",
        "c_bracket": "double the upper end until it lies beyond the quantile",
        "c_bisect": "bisection to about six significant digits",
        "c_newton": "Newton steps on the density, kept inside the bracket",
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
        "d_line": "SVG text for a line chart.\n\n    `points` is [(label, value)] or {series: [(label, value)]}; a None value is a gap. `overlay`\n    draws a statistic (interval whiskers, dashed lines, a shaded band) over the data.\n    ",
        "d_bar": "SVG text for a horizontal bar chart of [(label, value)] items, in the given order.\n\n    `intervals` adds a (lower, upper) whisker per item; `interval_label` explains it in a legend.\n    ",
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
            "chart": "The exported Chart Studio chart: integer totals per bucket (periods without rows are zeros; `partial` marks incomplete periods).",
            "chart_ci95": "95% interval inputs per bucket: n, mean and sample sd of the order totals (pence). Bounds = mean ± t·sd/√n; DuckDB has no Student-t quantile, so analysis.py computes t with stats.py.",
            "chart_trend": "Linear trend over complete periods (y = metric value, x = period index). The slope's p-value needs the Student-t distribution and is computed in analysis.py (stats.py).",
            "chart_control_band": "Control band over complete periods: mean ± 2 sample standard deviations; `outside` lists the periods beyond it.",
            "chart_moving_average": "Trailing {w}-period moving average. WHERE NOT partial runs before the window, so partial periods never enter an average; QUALIFY keeps only full windows of consecutive periods with a value.",
        },
        "sql_chart_scope": "3) Chart Studio chart scope: the overlap of the dataset's date range, the filters above and the chart's own dates.",
        "sql_chart_view": "4) The chart's buckets. Every chart query below reads this view.",
        "v": {
            "periods": "Every {per} of the chart scope, so a {per} without rows still appears (as a zero), as in Chart Studio.",
            "per": {"month": "month", "week": "week"},
            "series_all": "One series for the whole scope.",
            "series_split": "One series per compared country, in the chart's order.",
            "orders": "One row per order (invoice) per bucket and series inside the chart scope.",
            "totals": "Bucket totals; pence_squared (exact HUGEINT) gives the standard deviation of order totals without rounding.",
            "partial": "A period the scope does not fully cover (first/last) is partial: shown, but left out of statistics.",
            "value": "Plotted value: {what}.",
            "what": {"gross_sales": "gross sales in GBP", "orders": "distinct orders", "units": "units sold",
                     "aov": "average order value in GBP; NULL without orders"},
            "rank": "Rank by the metric (ties by key) and keep the top {n}.",
            "weekday": "Weekday order (1 = Monday).",
            "complete": "complete periods only",
            "no_value": "average order value is NULL in a period without orders",
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
        "d_chart": "Grafik satırları: dilim başına (dönem × seri ya da sıralı kategori) bir satır, tam sayı toplamlarla.\n\n    pence = GBP kuruş cinsinden brüt satış, orders = benzersiz fatura, units = SUM(quantity). Aylık veya\n    haftalık eksende grafik kapsamının her dönemi yer alır: satırı olmayan dönem sıfırdır (ortalama\n    sipariş tutarı o zaman eksiktir); `partial`, kapsamın tam kapsamadığı ilk/son dönemi işaretler.\n    Bunlar Chart Studio'nun çizdiği değerlerin aynısıdır.\n    ",
        "d_chart_points": "Grafik satırlarını şekil için seri başına (etiket, değer) noktalarına çevirir; None bir boşluktur.",
        "c_chart": "Bu paketle dışa aktarılan Chart Studio ChartSpec v1. CHART_VIEW_SQL bundan üretildi (ülkeler, hariç tutulanlar ve ilk N SQL'e yazılıdır); Python fonksiyonları ölçüyü ve pencereyi buradan okur.",
        "c_chart_scope": "Grafik kapsamı: veri setinin tarih aralığı, --start/--end filtreleri ve grafiğin kendi tarihlerinin kesişimi. analysis.sql aynı iki ifadeyi çalıştırır.",
        "c_chart_view": "Grafik dilimi başına bir satır; tüm grafik sorguları bu görünümü okur. analysis.sql'deki SQL'in aynısı.",
        "d_prepare_chart": "Grafik kapsamı değişkenlerini ayarlar ve `sales` üzerine `chart_buckets` görünümünü oluşturur.",
        "d_metric_value": "Bir grafik satırının çizilen değeri, ölçünün biriminde (GBP ya da sayım), Chart Studio'daki gibi.\n\n    Siparişi olmayan dilimde ortalama sipariş tutarı sıfır değil, eksiktir (None).\n    ",
        "d_to_int": "expected.json için değer × ölçek, tam sayıya yuvarlanmış (yarımlar çift sayıya); None aynen kalır.",
        "d_chart_label": "Grafik satırının eksen etiketi: hafta günü adı, ürün adı ya da dilim anahtarı.",
        "d_chart_intervals": "Grafik satırı başına GBP cinsinden aralık sınırları (results['chart'] ile hizalı); aralık yoksa None.",
        "d_chart_figure": "chart.svg'yi yazar: grafik satırları ve üzerlerine çizilen istatistik (bkz. chart_overlay).",
        "c_bar_order": "Çubuk düzeni: satırlar sıra ya da takvim düzeninde gelir; ChartSpec sıralaması Chart Studio'daki gibi uygulanır.",
        "d_overlay_none": "Dışa aktarılan grafikte istatistik yok; verinin üzerine bir şey çizilmez.",
        "d_overlay_ci95": "Dilim başına aralık bıyıkları (GBP cinsinden alt ve üst sınır).",
        "d_overlay_trend": "Uydurulan trend doğrusu; uydurulduğu tam dönemlerin üzerinde kesikli çizilir.",
        "d_overlay_band": "Kontrol bandı: alt sınırdan üst sınıra gölgeli, ortalama kesikli çizgi.",
        "d_overlay_ma": "Her serinin hareketli ortalaması, serinin renginde kesikli çizilir.",
        "c_ci_level": "Aralığın güven düzeyi. 0.99 %99'luk aralık verir (o zaman expected.json artık eşleşmez).",
        "d_ci95": "Dilim başına ortalama sipariş tutarının t tabanlı güven aralığı.\n\n    En az 2 siparişi olan her dilim için: ortalama ± t(0,5 + düzey/2, n − 1) · ss / √n; ortalama ve ss\n    (örneklem standart sapması) dilimin kuruş cinsinden sipariş toplamları üzerindendir, t ise\n    stats.py'deki Student-t kantilidir. SQL ortalama ve ss'yi kesin tam sayı toplamlarından türetir;\n    sonuç kayan nokta toplama sırasına bağlı değildir ve her çalıştırmada aynıdır. Değerler tam sayı\n    kuruştur. Sipariş tutarlarının bağımsız, ortalamanın yaklaşık normal olduğunu varsayar; çarpık\n    tutarlar ve küçük n yanıltabilir.\n    ",
        "c_stat_scale": "İstatistik değerleri ×100 tam sayı olarak saklanır: GBP ölçülerinde kuruş, sayımlarda yüzde birler.",
        "c_fraction_scale": "R² ve p-değeri ×1.000.000 (altı ondalık) tam sayı olarak saklanır.",
        "d_trend": "Tam dönemler üzerinde en küçük kareler trendi: y = kesişim + eğim · i.\n\n    i, dönemin grafik kapsamındaki sırasıdır (0 = index_origin): kısmi ilk/son dönemler yerini korur\n    ama uydurmaya girmez; değeri olmayan dönemler (siparişsiz dönemde ortalama sipariş tutarı)\n    atlanır. R² = Sxy² / (Sxx · Syy); eğimin çift yönlü p-değeri n − 2 serbestlik dereceli t testiyle\n    hesaplanır (stats.py). En az 3 dönem gerekir. Chart Studio ve scipy.stats.linregress ile aynı\n    tahmin edicidir. Trend geçmişi betimler; tahmin değildir.\n    ",
        "c_p_value": "kusursuz uyumda (R² = 1) artık varyansı yoktur; p-değeri 0 olarak verilir",
        "c_sigmas": "Kontrol bandının standart sapma cinsinden genişliği (3.0 klasik 3-sigma sınırlarını verir).",
        "d_band": "Kontrol bandı: tam dönemlerde ölçünün ortalaması ± sigma · ss.\n\n    ss örneklem standart sapmasıdır (n − 1). Bandın dışındaki dönemler `outside` içinde listelenir;\n    olağan değişimin dışında olabilirler ama nedenleri bu veriden okunamaz. En az 3 tam dönem gerekir.\n    ",
        "d_ma": "Seri başına `window` tam dönemlik geriye dönük hareketli ortalama.\n\n    Kısmi dönemler pencere uygulanmadan önce çıkarılır, bu yüzden hiçbir ortalamaya girmez; bir nokta\n    yalnız pencerede değeri olan `window` ardışık dönem varsa üretilir. Nokta, pencerenin son\n    dönemiyle etiketlenir.\n    ",
        "c_ma_skip": "pencerede boşluk ya da eksik değer var: nokta yok (Chart Studio'daki gibi)",
        "overlay": {"none": "", "ci95": "%95 güven aralığı", "trend": "Doğrusal trend",
                    "control_band": "Kontrol bandı (ortalama ± 2 ss)", "moving_average": "{w} dönemlik hareketli ortalama"},
        "d_overlay": "Grafiğin üzerine, grafiğin biriminde çizilen istatistik.\n\n    intervals  {seri: [(etiket, alt, üst)]}   uçlu bıyıklar (güven aralığı)\n    lines      {seri: [(etiket, değer)]}       kesikli çizgiler (trend, hareketli ortalama)\n    band       (alt, ortalama, üst)            kesikli ortalamalı gölgeli bant (kontrol bandı)\n    label      gösterge metni\n    ",
        "d_segments": "Çoklu çizgiyi eksik değerlerde (None) böler: boşluk sıfır olarak değil, boşluk olarak çizilir.",
        "c_axis_height": "Çizilen her şey değer ekseninin yüksekliğini belirler; böylece bıyıklar ve bantlar kesilmez.",
        "c_clip": "Sıfırın altındaki değerler (alt sınır negatif olabilir) eksende kesilir; veri bunları korur.",
        "c_band_back": "gölgeli bant her şeyin arkasında",
        "c_grid_h": "değer etiketli yatay ızgara",
        "c_grid_v": "değer etiketli dikey ızgara",
        "c_labels": "en fazla ~12 dönem etiketi; sonuncusu her zaman gösterilir",
        "c_whiskers": "uçlu bıyıklar",
        "c_dashed": "verinin üzerinde kesikli istatistik çizgileri",
        "c_bar_legend": "başlığın altında gösterge: bir bıyık örneği ve ne gösterdiği",
        "c_series_order": "seriler grafikteki sırayla",
        "stats_doc": """Bağımlılıksız Student-t dağılımı: dağılım fonksiyonu, çift yönlü p-değeri ve kantil.

analysis.py güven aralığı için t_quantile(), trend eğiminin p-değeri için t_two_sided_p() kullanır.
Sonuçlar scipy.special.stdtr / stdtrit ile 1e-9'dan küçük göreli hatayla örtüşür.

Yöntem
    ν serbestlik derecesi, t > 0 ve x = ν / (ν + t²) için:
        P(T > t)     = ½ · I_x(ν/2, ½)
        P(0 < T < t) = ½ · I_{1−x}(½, ν/2)
    Burada I düzenlenmiş eksik beta fonksiyonudur. İki parça da I'nın sürekli kesirinden hesaplanır
    (değiştirilmiş Lentz yöntemi; Numerical Recipes 3. baskı §6.4'teki betacf gibi). Kesir hızlı
    yakınsadığı tarafta değerlendirilir ve 1 − x doğrudan oluşturulur; böylece çok küçük kuyruklar ve
    0'a yakın t tam hassasiyetini korur. Kantil, kökü önce bir aralığa alır, yaklaşık altı haneye kadar
    ikiye böler, sonra yoğunlukla Newton adımları atarak inceltir.
""",
        "c_stats_constants": "Sürekli kesirin doğruluk hedefi, Lentz yöntemini sıfıra bölmeden koruyan taban değer ve yineleme sınırı.",
        "d_log_beta": "log B(a, b), log-gamma ile.",
        "d_betacf": "Eksik beta fonksiyonunun sürekli kesiri (Numerical Recipes betacf, değiştirilmiş Lentz).\n\n    x < (a + 1) / (a + b + 2) için hızlı yakınsar; aksi halde çağıranlar\n    I_x(a, b) = 1 − I_{1−x}(b, a) simetrisini kullanır.\n    ",
        "c_even_step": "kesirin çift adımı d_{2m}",
        "c_odd_step": "tek adım d_{2m+1}; güncelleme değeri artık değiştirmiyorsa dur",
        "d_pair": "y = 1 − x ayrı verildiğinde (I_x(a, b), I_y(b, a)); böylece ikisi de hassasiyet kaybetmez.\n\n    İki değerin toplamı 1'dir: küçük olan sürekli kesirden, diğeri onun tümleyeni olarak hesaplanır.\n    ",
        "c_symmetry": "kesiri hızlı yakınsadığı tarafta değerlendir",
        "d_betainc": "Düzenlenmiş eksik beta fonksiyonu I_x(a, b) (scipy.special.betainc(a, b, x) ile aynı).",
        "d_split": "df serbestlik dereceli bir Student-t değişkeni için (P(T > |t|), P(0 < T < |t|)); toplamları ½'dir.",
        "c_split": "x = df / (df + t²) ve 1 − x = t² / (df + t²) ikisi de doğrudan oluşturulur",
        "d_cdf": "df serbestlik dereceli bir Student-t değişkeni için P(T ≤ t) (scipy.special.stdtr(df, t)).",
        "d_two_sided": "Çift yönlü p-değeri P(|T| ≥ |t|); doğrusal regresyonda eğim testindeki gibi.",
        "d_pdf": "Student-t dağılımının yoğunluğu (t_quantile'ın Newton adımlarında kullanılır).",
        "d_quantile": "P(T ≤ t) = p olan t (scipy.special.stdtrit(df, p)); 0 < p < 1 ve df > 0.",
        "c_target": "uç p için kuyrukta, ½ yakınında merkezde çöz; her biri kendi bölgesinde doğrudur",
        "d_gap": "t'de artan ve kantilde sıfır olan fark.",
        "c_bracket": "üst ucu kantilin ötesine geçene kadar ikiye katla",
        "c_bisect": "yaklaşık altı anlamlı haneye kadar ikiye bölme",
        "c_newton": "yoğunlukla Newton adımları, aralığın içinde tutularak",
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
        "d_line": "Çizgi grafik SVG metni.\n\n    `points` [(etiket, değer)] ya da {seri: [(etiket, değer)]} olabilir; None değer bir boşluktur.\n    `overlay` verinin üzerine bir istatistik çizer (aralık bıyıkları, kesikli çizgiler, gölgeli bant).\n    ",
        "d_bar": "[(etiket, değer)] öğeleri için verilen sırayla yatay çubuk grafik SVG metni.\n\n    `intervals` öğe başına (alt, üst) bir bıyık ekler; `interval_label` bunu bir göstergede açıklar.\n    ",
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
            "chart": "Dışa aktarılan Chart Studio grafiği: dilim başına tam sayı toplamlar (satırı olmayan dönemler sıfır; `partial` eksik dönemleri işaretler).",
            "chart_ci95": "%95 aralığın girdileri: dilim başına n, sipariş toplamlarının ortalaması ve örneklem ss'si (kuruş). Sınırlar = ortalama ± t·ss/√n; DuckDB'de Student-t kantili yok, t'yi analysis.py stats.py ile hesaplar.",
            "chart_trend": "Tam dönemlerde doğrusal trend (y = ölçü değeri, x = dönem sırası). Eğimin p-değeri Student-t dağılımı gerektirir; analysis.py içinde (stats.py) hesaplanır.",
            "chart_control_band": "Tam dönemlerde kontrol bandı: ortalama ± 2 örneklem standart sapması; `outside` bandın dışındaki dönemleri listeler.",
            "chart_moving_average": "Geriye dönük {w} dönemlik hareketli ortalama. WHERE NOT partial pencereden önce çalışır, bu yüzden kısmi dönemler hiçbir ortalamaya girmez; QUALIFY yalnız değeri olan ardışık dönemlerden oluşan tam pencereleri tutar.",
        },
        "sql_chart_scope": "3) Chart Studio grafik kapsamı: veri setinin tarih aralığı, yukarıdaki filtreler ve grafiğin kendi tarihlerinin kesişimi.",
        "sql_chart_view": "4) Grafiğin dilimleri. Aşağıdaki tüm grafik sorguları bu görünümü okur.",
        "v": {
            "periods": "Grafik kapsamındaki her {per}; satırı olmayan bir {per} de (sıfır olarak) yer alır, Chart Studio'daki gibi.",
            "per": {"month": "ay", "week": "hafta"},
            "series_all": "Tüm kapsam için tek seri.",
            "series_split": "Karşılaştırılan her ülke için bir seri, grafikteki sırayla.",
            "orders": "Grafik kapsamında dilim ve seri başına, sipariş (fatura) başına bir satır.",
            "totals": "Dilim toplamları; pence_squared (kesin HUGEINT) sipariş tutarlarının standart sapmasını yuvarlamasız verir.",
            "partial": "Kapsamın tam kapsamadığı dönem (ilk/son) kısmidir: gösterilir ama istatistiklere girmez.",
            "value": "Çizilen değer: {what}.",
            "what": {"gross_sales": "GBP cinsinden brüt satış", "orders": "benzersiz sipariş", "units": "satılan adet",
                     "aov": "GBP cinsinden ortalama sipariş tutarı; siparişsiz dilimde NULL"},
            "rank": "Ölçüye göre sırala (eşitlikte anahtara göre) ve ilk {n} dilimi tut.",
            "weekday": "Hafta günü sırası (1 = pazartesi).",
            "complete": "yalnız tam dönemler",
            "no_value": "siparişsiz dönemde ortalama sipariş tutarı NULL'dır",
        },
    },
}

# ----------------------------------------------------------------------------------------- templates

CHARTS_TEMPLATE = '''"""@@charts_doc@@"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
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

Point = tuple[str, float | None]
Interval = tuple[str, float, float]


@dataclass(frozen=True)
class Overlay:
    """@@d_overlay@@"""

    label: str
    intervals: Mapping[str, Sequence[Interval]] = field(default_factory=dict)
    lines: Mapping[str, Sequence[Point]] = field(default_factory=dict)
    band: tuple[float, float, float] | None = None


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


def _segments(coords: Sequence[tuple[float, float | None]]) -> list[list[tuple[float, float]]]:
    """@@d_segments@@"""
    runs: list[list[tuple[float, float]]] = [[]]
    for x, y in coords:
        if y is None:
            if runs[-1]:
                runs.append([])
        else:
            runs[-1].append((x, y))
    return [run for run in runs if run]


def line_svg(points: Sequence[Point] | Mapping[str, Sequence[Point]], title: str, unit: str,
             *, overlay: Overlay | None = None, width: int = 760, height: int = 380) -> str:
    """@@d_line@@"""
    series = {name: list(values) for name, values in points.items()} if isinstance(points, Mapping) else {"": list(points)}
    labels = list(dict.fromkeys(label for values in series.values() for label, _ in values))
    known = [(label, value) for items in series.values() for label, value in items if value is not None]
    if not known:
        return "\\n".join(_header(width, height, title, DESC_EMPTY) + ["</svg>", ""])
    top_label, top_value = max(known, key=lambda item: item[1])
    desc = DESC_LINE.format(n=len(labels), first=labels[0], last=labels[-1], top_label=top_label,
                            top_value=format_number(top_value, unit))
    # @@c_axis_height@@
    tops = [value for _, value in known]
    if overlay is not None:
        desc += f" {overlay.label}."
        tops += [upper for items in overlay.intervals.values() for _, _, upper in items]
        tops += [value for items in overlay.lines.values() for _, value in items if value is not None]
        tops += [overlay.band[2]] if overlay.band else []
    legend = len(series) > 1 or overlay is not None
    left, right, top, bottom = 88, 24, 72 if legend else 56, 56
    plot_w, plot_h = width - left - right, height - top - bottom
    ticks = nice_ticks(max(tops))
    y_max = ticks[-1]
    position = {label: i for i, label in enumerate(labels)}
    colors = {name: SERIES_COLORS[i % len(SERIES_COLORS)] for i, name in enumerate(series)}

    def x_of(label: str) -> float:
        return left + (plot_w * position[label] / (len(labels) - 1) if len(labels) > 1 else plot_w / 2)

    def y_of(value: float) -> float:
        # @@c_clip@@
        return top + plot_h - plot_h * min(max(value, 0.0), y_max) / y_max

    def overlay_color(name: str) -> str:
        return colors[name] if len(series) > 1 and name in colors else BRASS

    out = _header(width, height, title, desc)
    if overlay is not None and overlay.band:  # @@c_band_back@@
        lower, mean, upper = overlay.band
        out.append(f'  <rect x="{left}" y="{_f(y_of(upper))}" width="{plot_w}" '
                   f'height="{_f(y_of(lower) - y_of(upper))}" fill="{BRASS}" fill-opacity="0.14"/>')
        out.append(f'  <line x1="{left}" y1="{_f(y_of(mean))}" x2="{width - right}" y2="{_f(y_of(mean))}" '
                   f'stroke="{BRASS}" stroke-width="1.5" stroke-dasharray="6 4"/>')
    for tick in ticks:  # @@c_grid_h@@
        y = y_of(tick)
        out.append(f'  <line x1="{left}" y1="{_f(y)}" x2="{width - right}" y2="{_f(y)}" stroke="{GRID}" stroke-width="1"/>')
        out.append(_text(left - 8, y + 4, format_number(tick, unit), anchor="end"))
    out.append(f'  <line x1="{left}" y1="{top + plot_h}" x2="{width - right}" y2="{top + plot_h}" stroke="{MUTED}" stroke-width="1"/>')
    step = max(1, math.ceil(len(labels) / 12))  # @@c_labels@@
    for i, label in enumerate(labels):
        if (i % step == 0 and len(labels) - 1 - i >= step) or i == len(labels) - 1:
            out.append(_text(x_of(label), top + plot_h + 20, label, anchor="middle"))
    if overlay is not None:
        for name, items in overlay.intervals.items():  # @@c_whiskers@@
            color = colors.get(name, NAVY) if len(series) > 1 else NAVY
            for label, lower, upper in items:
                x = x_of(label)
                y1, y2 = y_of(lower), y_of(upper)
                stroke = f'stroke="{color}" stroke-width="1.2"'
                out.append(f'  <line x1="{_f(x)}" y1="{_f(y1)}" x2="{_f(x)}" y2="{_f(y2)}" {stroke}/>')
                for y in (y1, y2):
                    out.append(f'  <line x1="{_f(x - 4)}" y1="{_f(y)}" x2="{_f(x + 4)}" y2="{_f(y)}" {stroke}/>')
    for name, items in series.items():
        color = colors[name]
        for run in _segments([(x_of(label), None if value is None else y_of(value)) for label, value in items]):
            coords = " ".join(f"{_f(x)},{_f(y)}" for x, y in run)
            out.append(f'  <polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2" '
                       'stroke-linejoin="round" stroke-linecap="round"/>')
        for label, value in items:
            if value is not None:
                out.append(f'  <circle cx="{_f(x_of(label))}" cy="{_f(y_of(value))}" r="3" fill="{color}"/>')
    if overlay is not None:
        for name, items in overlay.lines.items():  # @@c_dashed@@
            for run in _segments([(x_of(label), None if value is None else y_of(value)) for label, value in items]):
                coords = " ".join(f"{_f(x)},{_f(y)}" for x, y in run)
                out.append(f'  <polyline points="{coords}" fill="none" stroke="{overlay_color(name)}" '
                           'stroke-width="2" stroke-dasharray="6 4" stroke-linejoin="round" stroke-linecap="round"/>')
    if legend:
        lx = left
        if len(series) > 1:
            for name in series:
                out.append(f'  <rect x="{lx}" y="46" width="12" height="12" rx="2" fill="{colors[name]}"/>')
                out.append(_text(lx + 18, 56, _short(name, 20), size=12, color=NAVY))
                lx += 150
        if overlay is not None:
            if overlay.band:
                out.append(f'  <rect x="{lx}" y="46" width="22" height="12" fill="{BRASS}" fill-opacity="0.14"/>')
            if overlay.band or overlay.lines:
                out.append(f'  <line x1="{lx}" y1="52" x2="{lx + 22}" y2="52" stroke="{BRASS}" stroke-width="2" '
                           'stroke-dasharray="6 4"/>')
            else:
                out.append(f'  <line x1="{lx + 11}" y1="45" x2="{lx + 11}" y2="59" stroke="{NAVY}" stroke-width="1.2"/>')
            out.append(_text(lx + 28, 56, _short(overlay.label, 60), size=12, color=NAVY))
    out += ["</svg>", ""]
    return "\\n".join(out)


def bar_svg(items: Sequence[Point], title: str, unit: str, *,
            intervals: Sequence[tuple[float, float] | None] | None = None, interval_label: str = "",
            width: int = 760) -> str:
    """@@d_bar@@"""
    items = list(items)
    whiskers = list(intervals) if intervals is not None else [None] * len(items)
    row, top, bottom, label_w, value_w = 28, 72 if interval_label else 56, 40, 250, 96
    height = top + row * max(len(items), 1) + bottom
    known = [(label, value) for label, value in items if value is not None]
    if not known:
        return "\\n".join(_header(width, height, title, DESC_EMPTY) + ["</svg>", ""])
    top_label, top_value = max(known, key=lambda item: item[1])
    desc = DESC_BAR.format(n=len(items), top_label=top_label, top_value=format_number(top_value, unit))
    if interval_label:
        desc += f" {interval_label}."
    left = 24 + label_w
    plot_w = width - left - value_w
    ticks = nice_ticks(max([value for _, value in known] + [bounds[1] for bounds in whiskers if bounds]))
    x_max = ticks[-1]

    def x_of(value: float) -> float:
        # @@c_clip@@
        return left + plot_w * min(max(value, 0.0), x_max) / x_max

    out = _header(width, height, title, desc)
    if interval_label:  # @@c_bar_legend@@
        out.append(f'  <line x1="24" y1="52" x2="46" y2="52" stroke="{NAVY}" stroke-width="1.2"/>')
        for x in (24, 46):
            out.append(f'  <line x1="{x}" y1="47" x2="{x}" y2="57" stroke="{NAVY}" stroke-width="1.2"/>')
        out.append(_text(52, 56, interval_label, size=12, color=NAVY))
    base = top + row * len(items)
    for tick in ticks:  # @@c_grid_v@@
        x = x_of(tick)
        out.append(f'  <line x1="{_f(x)}" y1="{top - 6}" x2="{_f(x)}" y2="{base}" stroke="{GRID}" stroke-width="1"/>')
        out.append(_text(x, base + 18, format_number(tick, unit), anchor="middle"))
    for i, ((label, value), bounds) in enumerate(zip(items, whiskers)):
        y = top + row * i
        out.append(_text(left - 10, y + 15, _short(label), anchor="end", size=12, color=NAVY))
        end = left
        if value is not None:
            end = x_of(value)
            out.append(f'  <rect x="{left}" y="{_f(y + 3)}" width="{_f(end - left)}" height="18" rx="2" fill="{COBALT}"/>')
        if bounds:
            x1, x2 = x_of(bounds[0]), x_of(bounds[1])
            stroke = f'stroke="{NAVY}" stroke-width="1.2"'
            out.append(f'  <line x1="{_f(x1)}" y1="{_f(y + 12)}" x2="{_f(x2)}" y2="{_f(y + 12)}" {stroke}/>')
            for x in (x1, x2):
                out.append(f'  <line x1="{_f(x)}" y1="{_f(y + 7)}" x2="{_f(x)}" y2="{_f(y + 17)}" {stroke}/>')
            end = max(end, x2)
        out.append(_text(end + 6, y + 16, "—" if value is None else format_number(value, unit)))
    out += ["</svg>", ""]
    return "\\n".join(out)


def line_chart(points: Sequence[Point] | Mapping[str, Sequence[Point]], title: str, unit: str, path: Path,
               *, overlay: Overlay | None = None) -> Path:
    """@@d_write_line@@"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(line_svg(points, title, unit, overlay=overlay), encoding="utf-8", newline="\\n")
    return path


def bar_chart(items: Sequence[Point], title: str, unit: str, path: Path, *,
              intervals: Sequence[tuple[float, float] | None] | None = None, interval_label: str = "") -> Path:
    """@@d_write_bar@@"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(bar_svg(items, title, unit, intervals=intervals, interval_label=interval_label),
                    encoding="utf-8", newline="\\n")
    return path
'''

STATS_TEMPLATE = '''"""@@stats_doc@@"""

from __future__ import annotations

import math

# @@c_stats_constants@@
EPSILON = 1e-15
TINY = 1e-300
MAX_ITERATIONS = 10_000


def _log_beta(a: float, b: float) -> float:
    """@@d_log_beta@@"""
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    """@@d_betacf@@"""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > TINY else TINY)
    h = d
    for m in range(1, MAX_ITERATIONS + 1):
        m2 = 2 * m
        # @@c_even_step@@
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > TINY else TINY)
        c = 1.0 + aa / c
        c = c if abs(c) > TINY else TINY
        h *= d * c
        # @@c_odd_step@@
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > TINY else TINY)
        c = 1.0 + aa / c
        c = c if abs(c) > TINY else TINY
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < EPSILON:
            return h
    raise ArithmeticError("incomplete beta: continued fraction did not converge")


def _incomplete_beta_pair(x: float, y: float, a: float, b: float) -> tuple[float, float]:
    """@@d_pair@@"""
    if x <= 0.0:
        return 0.0, 1.0
    if y <= 0.0:
        return 1.0, 0.0
    front = math.exp(a * math.log(x) + b * math.log(y) - _log_beta(a, b))
    # @@c_symmetry@@
    if x < (a + 1.0) / (a + b + 2.0):
        lower = front * _beta_continued_fraction(a, b, x) / a
        return lower, 1.0 - lower
    upper = front * _beta_continued_fraction(b, a, y) / b
    return 1.0 - upper, upper


def regularized_incomplete_beta(x: float, a: float, b: float) -> float:
    """@@d_betainc@@"""
    if not 0.0 <= x <= 1.0 or a <= 0 or b <= 0:
        raise ValueError("regularized_incomplete_beta needs 0 <= x <= 1 and a, b > 0")
    return _incomplete_beta_pair(x, 1.0 - x, a, b)[0]


def _t_tail_and_centre(t: float, df: float) -> tuple[float, float]:
    """@@d_split@@"""
    if df <= 0:
        raise ValueError("df must be positive")
    tt = t * t
    if tt == 0.0:
        return 0.5, 0.0
    if math.isinf(tt):
        return 0.0, 0.5
    # @@c_split@@
    tail_twice, centre_twice = _incomplete_beta_pair(df / (df + tt), tt / (df + tt), df / 2.0, 0.5)
    return 0.5 * tail_twice, 0.5 * centre_twice


def t_cdf(t: float, df: float) -> float:
    """@@d_cdf@@"""
    tail, centre = _t_tail_and_centre(t, df)
    return tail if t < 0 else 0.5 + centre


def t_two_sided_p(t: float, df: float) -> float:
    """@@d_two_sided@@"""
    return 2.0 * _t_tail_and_centre(t, df)[0]


def t_pdf(t: float, df: float) -> float:
    """@@d_pdf@@"""
    log_density = (math.lgamma((df + 1.0) / 2.0) - math.lgamma(df / 2.0) - 0.5 * math.log(df * math.pi)
                   - (df + 1.0) / 2.0 * math.log1p(t * t / df))
    return math.exp(log_density)


def t_quantile(p: float, df: float) -> float:
    """@@d_quantile@@"""
    if not 0.0 < p < 1.0:
        raise ValueError("p must be strictly between 0 and 1")
    if p == 0.5:
        return 0.0
    sign = 1.0 if p > 0.5 else -1.0
    tail_target = 1.0 - p if p > 0.5 else p
    centre_target = p - 0.5 if p > 0.5 else 0.5 - p
    # @@c_target@@
    use_tail = tail_target < 0.25

    def gap(t: float) -> float:
        """@@d_gap@@"""
        tail, centre = _t_tail_and_centre(t, df)
        return tail_target - tail if use_tail else centre - centre_target

    lo, hi = 0.0, 1.0
    while gap(hi) < 0.0:  # @@c_bracket@@
        lo, hi = hi, hi * 2.0
    while hi - lo > 1e-6 * hi:  # @@c_bisect@@
        mid = 0.5 * (lo + hi)
        if gap(mid) < 0.0:
            lo = mid
        else:
            hi = mid
    t = 0.5 * (lo + hi)
    for _ in range(50):  # @@c_newton@@
        t_next = min(max(t - gap(t) / t_pdf(t, df), lo), hi)
        if abs(t_next - t) <= 4.0 * EPSILON * t:
            t = t_next
            break
        t = t_next
    return sign * t
'''

ANALYSIS_TEMPLATE = '''#!/usr/bin/env python3
"""@@py_doc@@"""

from __future__ import annotations

import argparse
import csv
import json
@@MATH_IMPORT@@import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

import charts
@@STATS_IMPORT@@
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


# ------------------------------------------------------------------------------------------------
# @@c_chart@@
CHART_SPEC: dict[str, Any] = @@CHART_SPEC@@
OVERLAY_LABEL = @@OVERLAY_LABEL@@
@@STAT_CONSTANTS@@
# @@c_chart_scope@@
CHART_SCOPE_SQL = """
@@CHART_SCOPE@@
"""

# @@c_chart_view@@
CHART_VIEW_SQL = """
@@CHART_VIEW@@
"""


def prepare_chart(con: duckdb.DuckDBPyConnection) -> None:
    """@@d_prepare_chart@@"""
    con.execute(CHART_SCOPE_SQL)
    con.execute(CHART_VIEW_SQL)


def chart(con: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    """@@d_chart@@"""
    sql = """
@@SQL_chart@@
    """
    return _rows(con, sql)


def metric_value(row: dict[str, Any]) -> float | None:
    """@@d_metric_value@@"""
    metric = CHART_SPEC["metric"]
    if metric == "gross_sales":
        return row["pence"] / 100
    if metric in ("orders", "units"):
        return float(row[metric])
    return row["pence"] / row["orders"] / 100 if row["orders"] else None


def to_int(value: float | None, scale: float = 1) -> int | None:
    """@@d_to_int@@"""
    return None if value is None else round(value * scale)
@@STAT_FUNCTIONS@@

def chart_label(row: dict[str, Any]) -> str:
    """@@d_chart_label@@"""
    if CHART_SPEC["dimension"] == "weekday":
        return WEEKDAYS[int(row["x"]) - 1]
    return str(row.get("label") or row["x"])


def chart_points(rows: list[dict[str, Any]]) -> dict[str, list[tuple[str, float | None]]]:
    """@@d_chart_points@@"""
    series: dict[str, list[tuple[str, float | None]]] = {}
    for row in rows:
        series.setdefault(str(row["series"]), []).append((chart_label(row), metric_value(row)))
    return series


def chart_intervals(results: dict[str, Any]) -> list[tuple[float, float] | None]:
    """@@d_chart_intervals@@"""
    intervals = results.get("chart_ci95") or [{} for _ in results["chart"]]
    return [(row["lower_pence"] / 100, row["upper_pence"] / 100) if row.get("lower_pence") is not None else None
            for row in intervals]
@@OVERLAY_FUNCTION@@

def write_chart_figure(results: dict[str, Any], path: Path) -> Path:
    """@@d_chart_figure@@"""
    unit = "GBP" if CHART_SPEC["metric"] in ("gross_sales", "aov") else ""
    points = chart_points(results["chart"])
    overlay = chart_overlay(results)
    title = FIGURE_TITLES["chart"]
    time_axis = CHART_SPEC["dimension"] in ("month", "week")
    drawn_over_time = overlay is not None and bool(overlay.lines or overlay.band)
    if time_axis and (CHART_SPEC["chart"] != "bar" or len(points) > 1 or drawn_over_time):
        series = points if len(points) > 1 else points.get("all", [])
        return charts.line_chart(series, title, unit, path, overlay=overlay)
    # @@c_bar_order@@
    bounds_per_row = chart_intervals(results)
    items = [(label, value, bounds) for (label, value), bounds in zip(points.get("all", []), bounds_per_row)]
    if CHART_SPEC["dimension"] in ("country", "product", "country_group"):
        if CHART_SPEC["sort"] == "value_asc":
            items.reverse()
    elif CHART_SPEC["sort"] != "natural":
        sign = -1 if CHART_SPEC["sort"] == "value_desc" else 1
        items.sort(key=lambda item: (item[1] is None, sign * (item[1] or 0.0), item[0]))
    return charts.bar_chart([(label, value) for label, value, _ in items], title, unit, path,
                            intervals=[bounds for _, _, bounds in items],
                            interval_label=OVERLAY_LABEL if CHART_SPEC["statistic"] == "ci95" else "")
'''
CHART_COLLECT = '''
        prepare_chart(con)
        results["chart"] = chart(con)@@STAT_COLLECT@@'''
CHART_FIGURE = '''
    if "chart" in results:
        paths.append(write_chart_figure(results, figures_dir / "chart.svg"))'''

# One block per statistic: constants, the function(s) that compute it and the overlay drawn on chart.svg.
STAT_BLOCKS = {
    "none": {
        "constants": "",
        "functions": "",
        "collect": "",
        "overlay": '''

def chart_overlay(results: dict[str, Any]) -> charts.Overlay | None:
    """@@d_overlay_none@@"""
    return None
''',
    },
    "ci95": {
        "constants": '''# @@c_ci_level@@
CI_LEVEL = 0.95
''',
        "functions": '''

def chart_ci95(con: duckdb.DuckDBPyConnection, level: float = CI_LEVEL) -> list[dict[str, Any]]:
    """@@d_ci95@@"""
    sql = """
@@SQL_chart_ci95@@
    """
    quantile = 0.5 + level / 2
    out = []
    for row in _rows(con, sql):
        n, mean, sd = row["n"], row["mean_pence"], row["sd_pence"]
        lower = upper = None
        if n >= 2 and sd is not None:
            half = stats.t_quantile(quantile, n - 1) * sd / math.sqrt(n)
            lower, upper = mean - half, mean + half
        out.append({"x": row["x"], "series": row["series"], "n": n, "mean_pence": to_int(mean),
                    "sd_pence": to_int(sd), "lower_pence": to_int(lower), "upper_pence": to_int(upper)})
    return out
''',
        "collect": '''
        results["chart_ci95"] = chart_ci95(con)''',
        "overlay": '''

def chart_overlay(results: dict[str, Any]) -> charts.Overlay | None:
    """@@d_overlay_ci95@@"""
    intervals: dict[str, list[tuple[str, float, float]]] = {}
    for row, bounds in zip(results["chart"], chart_intervals(results)):
        if bounds is not None:
            intervals.setdefault(str(row["series"]), []).append((chart_label(row), *bounds))
    return charts.Overlay(label=OVERLAY_LABEL, intervals=intervals)
''',
    },
    "trend": {
        "constants": '''# @@c_stat_scale@@
STAT_SCALE = 100
# @@c_fraction_scale@@
FRACTION_SCALE = 1_000_000
''',
        "functions": '''

def chart_trend(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """@@d_trend@@"""
    periods = [row for row in rows if row["series"] == "all"]
    points = [(float(index), value) for index, row in enumerate(periods)
              if not row["partial"] and (value := metric_value(row)) is not None]
    result: dict[str, Any] = {"index_origin": periods[0]["x"] if periods else None, "n": len(points),
                              "slope_x100": None, "intercept_x100": None, "r2_x1e6": None, "p_value_x1e6": None}
    if len(points) < 3:
        return result
    n = len(points)
    mean_x = sum(x for x, _ in points) / n
    mean_y = sum(y for _, y in points) / n
    sxx = sum((x - mean_x) ** 2 for x, _ in points)
    syy = sum((y - mean_y) ** 2 for _, y in points)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in points)
    slope = sxy / sxx
    intercept = mean_y - slope * mean_x
    r2 = sxy * sxy / (sxx * syy) if syy > 0 else 1.0
    p_value = 0.0
    if r2 < 1.0:  # @@c_p_value@@
        standard_error = math.sqrt((1 - r2) * syy / (n - 2) / sxx)
        p_value = stats.t_two_sided_p(slope / standard_error, n - 2)
    result.update(slope_x100=to_int(slope, STAT_SCALE), intercept_x100=to_int(intercept, STAT_SCALE),
                  r2_x1e6=to_int(r2, FRACTION_SCALE), p_value_x1e6=to_int(p_value, FRACTION_SCALE))
    return result
''',
        "collect": '''
        results["chart_trend"] = chart_trend(results["chart"])''',
        "overlay": '''

def chart_overlay(results: dict[str, Any]) -> charts.Overlay | None:
    """@@d_overlay_trend@@"""
    trend = results["chart_trend"]
    if trend["slope_x100"] is None:
        return None
    slope, intercept = trend["slope_x100"] / STAT_SCALE, trend["intercept_x100"] / STAT_SCALE
    periods = [row for row in results["chart"] if row["series"] == "all"]
    line = [(chart_label(row), intercept + slope * index) for index, row in enumerate(periods)
            if not row["partial"] and metric_value(row) is not None]
    return charts.Overlay(label=OVERLAY_LABEL, lines={"all": line})
''',
    },
    "control_band": {
        "constants": '''# @@c_stat_scale@@
STAT_SCALE = 100
# @@c_sigmas@@
CONTROL_SIGMAS = 2.0
''',
        "functions": '''

def chart_control_band(rows: list[dict[str, Any]], sigmas: float = CONTROL_SIGMAS) -> dict[str, Any]:
    """@@d_band@@"""
    points = [(row["x"], value) for row in rows
              if row["series"] == "all" and not row["partial"] and (value := metric_value(row)) is not None]
    result: dict[str, Any] = {"n": len(points), "mean_x100": None, "sd_x100": None, "lower_x100": None,
                              "upper_x100": None, "outside": []}
    if len(points) < 3:
        return result
    values = [value for _, value in points]
    mean = sum(values) / len(values)
    sd = math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))
    lower, upper = mean - sigmas * sd, mean + sigmas * sd
    result.update(mean_x100=to_int(mean, STAT_SCALE), sd_x100=to_int(sd, STAT_SCALE),
                  lower_x100=to_int(lower, STAT_SCALE), upper_x100=to_int(upper, STAT_SCALE),
                  outside=[x for x, value in points if value < lower or value > upper])
    return result
''',
        "collect": '''
        results["chart_control_band"] = chart_control_band(results["chart"])''',
        "overlay": '''

def chart_overlay(results: dict[str, Any]) -> charts.Overlay | None:
    """@@d_overlay_band@@"""
    band = results["chart_control_band"]
    if band["mean_x100"] is None:
        return None
    return charts.Overlay(label=OVERLAY_LABEL, band=(band["lower_x100"] / STAT_SCALE, band["mean_x100"] / STAT_SCALE,
                                                     band["upper_x100"] / STAT_SCALE))
''',
    },
    "moving_average": {
        "constants": '''# @@c_stat_scale@@
STAT_SCALE = 100
''',
        "functions": '''

def chart_moving_average(rows: list[dict[str, Any]], window: int = CHART_SPEC["window"]) -> list[dict[str, Any]]:
    """@@d_ma@@"""
    out = []
    for name in dict.fromkeys(row["series"] for row in rows):  # @@c_series_order@@
        periods = [row for row in rows if row["series"] == name]
        complete = [(index, row) for index, row in enumerate(periods) if not row["partial"]]
        for end in range(window - 1, len(complete)):
            frame = complete[end - window + 1:end + 1]
            values = [metric_value(row) for _, row in frame]
            if None in values or frame[-1][0] - frame[0][0] != window - 1:
                continue  # @@c_ma_skip@@
            average = sum(values) / window
            out.append({"x": frame[-1][1]["x"], "series": name, "value_x100": to_int(average, STAT_SCALE)})
    return out
''',
        "collect": '''
        results["chart_moving_average"] = chart_moving_average(results["chart"])''',
        "overlay": '''

def chart_overlay(results: dict[str, Any]) -> charts.Overlay | None:
    """@@d_overlay_ma@@"""
    labels = {(row["x"], row["series"]): chart_label(row) for row in results["chart"]}
    lines: dict[str, list[tuple[str, float | None]]] = {}
    for point in results["chart_moving_average"]:
        lines.setdefault(str(point["series"]), []).append(
            (labels[(point["x"], point["series"])], point["value_x100"] / STAT_SCALE))
    return charts.Overlay(label=OVERLAY_LABEL, lines=lines) if lines else None
''',
    },
}


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


_COMMENT_LINE = re.compile(r"^(\s*)(#|--) (.*)$")


def _wrap_comments(source: str, width: int = 110) -> str:
    """Wrap full-line comments (# in Python, -- in SQL) longer than ``width``, keeping their indentation."""
    out = []
    for line in source.split("\n"):
        match = _COMMENT_LINE.match(line)
        if match and len(line) > width:
            indent, mark, text = match.groups()
            prefix = f"{indent}{mark} "
            out += textwrap.wrap(text, width=width, initial_indent=prefix, subsequent_indent=prefix,
                                 break_long_words=False, break_on_hyphens=False)
        else:
            out.append(line)
    return "\n".join(out)


def _py_text(text: str) -> str:
    """Text for a triple-quoted literal in the generated Python. SQL can carry values from uploaded data (a country
    named with backslashes or quotes): backslashes are doubled and every run of three double quotes is escaped, so
    the Python value is exactly the SQL text and the literal cannot be closed early."""
    return text.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')


def _indent_sql(sql: str) -> str:
    return textwrap.indent(_py_text(sql), "        ")


def _charts_source(locale: str) -> str:
    t = L[locale]
    texts = {k: v for k, v in t.items() if isinstance(v, str)}
    return _wrap_comments(_fill(CHARTS_TEMPLATE, {"LOCALE": locale, **texts}))


def _stats_source(locale: str) -> str:
    """stats.py: dependency-free Student-t CDF and quantile (shipped when the chart needs a t distribution)."""
    t = L[locale]
    return _wrap_comments(_fill(STATS_TEMPLATE, {k: v for k, v in t.items() if isinstance(v, str)}))


def _needs_stats(chart: dict | None) -> bool:
    return bool(chart) and chart["spec"]["statistic"] in ("ci95", "trend")


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
        "MATH_IMPORT": "import math\n" if chart and chart["spec"]["statistic"] in ("ci95", "trend", "control_band") else "",
        "STATS_IMPORT": "import stats\n" if _needs_stats(chart) else "",
    })
    for name in QUERY_ORDER:
        sql, names = _python_sql(name)
        values[f"SQL_{name}"] = _indent_sql(sql)
        if names:
            values[f"P_{name}"] = "[" + ", ".join(names) + "]"
        for key, default in DEFAULTS.get(name, {}).items():
            values[f"D_{name}_{key}"] = str(default)
    if chart:
        statistic = chart["spec"]["statistic"]
        block = STAT_BLOCKS[statistic]
        pieces = {**values, **{f"SQL_{name}": _indent_sql(sql) for name, sql in chart["queries"].items()}}
        values["CHART_BLOCK"] = _fill(CHART_BLOCK, {
            **pieces,
            "CHART_SPEC": _py_literal(chart["spec"]),
            "OVERLAY_LABEL": repr(chart["overlay_label"]),
            "CHART_SCOPE": _py_text(chart["scope"]),
            "CHART_VIEW": _py_text(chart["view"]),
            "STAT_CONSTANTS": _fill(block["constants"], pieces),
            "STAT_FUNCTIONS": _fill(block["functions"], pieces),
            "OVERLAY_FUNCTION": _fill(block["overlay"], pieces),
        })
        values["CHART_COLLECT"] = _fill(CHART_COLLECT, {"STAT_COLLECT": block["collect"]})
        values["CHART_FIGURE"] = CHART_FIGURE
    else:
        values["CHART_BLOCK"] = values["CHART_COLLECT"] = values["CHART_FIGURE"] = ""
    return _wrap_comments(_fill(ANALYSIS_TEMPLATE, values))


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
    if chart:
        head += ["", f"-- {t['sql_chart_scope']}", chart["scope"] + ";", "", f"-- {t['sql_chart_view']}",
                 chart["view"] + ";"]
    blocks = []
    for name in QUERY_ORDER:
        sql, names = _python_sql(name)
        params = [DEFAULTS[name][n] for n in names]
        blocks += ["", f"-- name: {name}", f"-- {t['sql_q'][name]}", _inline(sql, params) + ";"]
    for name, sql in (chart or {}).get("queries", {}).items():
        note = t["sql_q"][name].format(w=chart["spec"]["window"])
        blocks += ["", f"-- name: {name}", f"-- {note}", sql + ";"]
    return _wrap_comments("\n".join(head + blocks)) + "\n"


# ------------------------------------------------------------------------------------------- README


def _md_text(value) -> str:
    """User-derived text inside Markdown prose (a chart title naming uploaded countries): one line, with the
    characters that start emphasis, code, links or HTML escaped."""
    return re.sub(r"([\\`*_\[\]<>#|])", r"\\\1", _one_line(value))


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
            "stats.py": "dependency-free Student-t distribution (interval, p-value)",
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
        "chart_text": ("Exported ChartSpec (`CHART_SPEC` in `analysis.py`; the `chart_buckets` view and the `chart*` queries in "
                       "`analysis.sql`): **{title}** — {rows} rows. On a month or week axis every period of the chart scope "
                       "is listed: periods without rows are zeros (average order value: missing) and a first/last period the "
                       "scope does not fully cover is marked `partial`, exactly as in Chart Studio."),
        "stat": "Statistic: {name}",
        "stat_none": ("The chart has no statistic. Ask Chart Studio for one (95% interval, trend, control band or moving "
                      "average) and export again to get its code."),
        "stat_text": {
            "ci95": [
                "**What it is:** for every bucket with at least 2 orders, the 95% confidence interval of the mean order "
                "value: mean ± t(0.975, n − 1) · sd / √n over the bucket's order totals. The Student-t quantile comes "
                "from `stats.py` (no SciPy needed).",
                "**Assumption:** order totals are independent and their mean is roughly normal. With skewed totals and "
                "small n the interval can mislead; buckets with fewer than 2 orders have no interval.",
                "**Where:** `chart_ci95()` in `analysis.py` (integer pence: `mean_pence`, `sd_pence`, `lower_pence`, "
                "`upper_pence`); the `chart_ci95` query in `analysis.sql` returns n, mean and sd — DuckDB has no t "
                "quantile, so the bounds are computed in Python.",
                "**How to change it:** set `CI_LEVEL = 0.99` in `analysis.py` for a 99% interval. `--check` compares "
                "with the exported 95% values and will then report the difference.",
            ],
            "trend": [
                "**What it is:** an ordinary least-squares line y = intercept + slope · i over the complete periods, "
                "where i counts periods from `index_origin`; with R² and the two-sided p-value of the slope (t test, "
                "n − 2 degrees of freedom, via `stats.py`).",
                "**Assumption:** the trend describes the past; it is not a forecast. The p-value assumes independent, "
                "roughly normal residuals; consecutive periods are often correlated, which makes it optimistic.",
                "**Where:** `chart_trend()` in `analysis.py` (`slope_x100` and `intercept_x100` ×100, `r2_x1e6` and "
                "`p_value_x1e6` in millionths); the `chart_trend` query in `analysis.sql` uses DuckDB's `regr_slope`, "
                "`regr_intercept` and `regr_r2` (the p-value needs the t distribution and is computed in Python).",
                "**How to change it:** partial first/last periods are left out by `not row[\"partial\"]` in "
                "`chart_trend()` and `NOT partial` in the SQL; remove both to fit every period.",
            ],
            "control_band": [
                "**What it is:** the mean of the complete periods ± 2 sample standard deviations; periods outside the "
                "band are listed.",
                "**Assumption:** the periods vary around a stable level. The band flags unusual periods but cannot tell "
                "why they are unusual; a trend or seasonality widens it.",
                "**Where:** `chart_control_band()` in `analysis.py` (`mean_x100`, `sd_x100`, `lower_x100`, `upper_x100`); "
                "the `chart_control_band` query in `analysis.sql` (`AVG` and `STDDEV_SAMP`).",
                "**How to change it:** `CONTROL_SIGMAS = 3.0` in `analysis.py` (and `3 *` instead of `2 *` in the SQL) "
                "gives classic 3-sigma limits.",
            ],
            "moving_average": [
                "**What it is:** a trailing average of the last {w} complete periods per series, labelled with the "
                "window's last period.",
                "**Assumption:** partial periods would pull the average down, so they are removed before the window is "
                "applied (`WHERE NOT partial` runs before the window function); a point needs {w} consecutive periods "
                "with a value.",
                "**Where:** `chart_moving_average()` in `analysis.py` (`value_x100`); the `chart_moving_average` query "
                "in `analysis.sql` (`AVG(value) OVER (... ROWS BETWEEN {w1} PRECEDING AND CURRENT ROW)`).",
                "**How to change it:** set `CHART_SPEC[\"window\"]` in `analysis.py`, and `{w1} PRECEDING`, `= {w}` and "
                "`= {w1}` in `analysis.sql`, to the new window.",
            ],
        },
        "stat_head": {
            "ci95": "| Bucket | n | Mean | Lower | Upper |",
            "trend": "| n | Slope per {per} | Intercept | R² | p-value | Index origin |",
            "control_band": "| n | Mean | SD | Lower | Upper | Outside |",
            "moving_average": "| Period | Series | Moving average |",
        },
        "stat_more": "{n} more rows in `expected.json`.",
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
            "Service lines such as POSTAGE, Manual, fees and accounting adjustments are in gross sales but are not ranked as products or used as co-purchase candidates.",
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
            "stats.py": "bağımlılıksız Student-t dağılımı (aralık, p-değeri)",
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
        "chart_text": ("Dışa aktarılan ChartSpec (`analysis.py` içinde `CHART_SPEC`; `analysis.sql` içinde `chart_buckets` "
                       "görünümü ve `chart*` sorguları): **{title}** — {rows} satır. Aylık veya haftalık eksende grafik "
                       "kapsamının her dönemi listelenir: satırı olmayan dönemler sıfırdır (ortalama sipariş tutarı: eksik), "
                       "kapsamın tam kapsamadığı ilk/son dönem `partial` olarak işaretlenir; Chart Studio'daki gibi."),
        "stat": "İstatistik: {name}",
        "stat_none": ("Grafikte istatistik yok. Chart Studio'dan bir istatistik isteyin (%95 aralık, trend, kontrol bandı "
                      "veya hareketli ortalama) ve kodunu almak için yeniden dışa aktarın."),
        "stat_text": {
            "ci95": [
                "**Nedir:** en az 2 siparişi olan her dilim için ortalama sipariş tutarının %95 güven aralığı: "
                "ortalama ± t(0,975, n − 1) · ss / √n, dilimin sipariş toplamları üzerinden. Student-t kantili "
                "`stats.py`'den gelir (SciPy gerekmez).",
                "**Varsayım:** sipariş tutarları bağımsızdır ve ortalamaları yaklaşık normaldir. Çarpık tutarlar ve küçük "
                "n ile aralık yanıltabilir; 2'den az siparişi olan dilimlerde aralık yoktur.",
                "**Nerede:** `analysis.py` içinde `chart_ci95()` (tam sayı kuruş: `mean_pence`, `sd_pence`, "
                "`lower_pence`, `upper_pence`); `analysis.sql` içindeki `chart_ci95` sorgusu n, ortalama ve ss döndürür "
                "— DuckDB'de t kantili olmadığından sınırlar Python'da hesaplanır.",
                "**Nasıl değiştirilir:** %99'luk aralık için `analysis.py` içinde `CI_LEVEL = 0.99` yapın. `--check` "
                "dışa aktarılan %95 değerlerle karşılaştırır ve farkı raporlar.",
            ],
            "trend": [
                "**Nedir:** tam dönemler üzerinde en küçük kareler doğrusu y = kesişim + eğim · i; i, dönemleri "
                "`index_origin`'den sayar. R² ve eğimin çift yönlü p-değeri (t testi, n − 2 serbestlik derecesi, "
                "`stats.py` ile) verilir.",
                "**Varsayım:** trend geçmişi betimler; tahmin değildir. p-değeri bağımsız ve yaklaşık normal artıklar "
                "varsayar; ardışık dönemler çoğu zaman ilişkilidir ve bu p-değerini iyimser yapar.",
                "**Nerede:** `analysis.py` içinde `chart_trend()` (`slope_x100` ve `intercept_x100` ×100, `r2_x1e6` ve "
                "`p_value_x1e6` milyonda bir); `analysis.sql` içindeki `chart_trend` sorgusu DuckDB'nin `regr_slope`, "
                "`regr_intercept` ve `regr_r2` fonksiyonlarını kullanır (p-değeri t dağılımı gerektirir, Python'da "
                "hesaplanır).",
                "**Nasıl değiştirilir:** kısmi ilk/son dönemler `chart_trend()` içinde `not row[\"partial\"]`, SQL'de "
                "`NOT partial` ile dışarıda bırakılır; tüm dönemlere uydurmak için ikisini de kaldırın.",
            ],
            "control_band": [
                "**Nedir:** tam dönemlerin ortalaması ± 2 örneklem standart sapması; bandın dışındaki dönemler listelenir.",
                "**Varsayım:** dönemler sabit bir düzey etrafında dalgalanır. Bant olağandışı dönemleri işaretler ama "
                "nedenini söyleyemez; trend veya mevsimsellik bandı genişletir.",
                "**Nerede:** `analysis.py` içinde `chart_control_band()` (`mean_x100`, `sd_x100`, `lower_x100`, "
                "`upper_x100`); `analysis.sql` içindeki `chart_control_band` sorgusu (`AVG` ve `STDDEV_SAMP`).",
                "**Nasıl değiştirilir:** `analysis.py` içinde `CONTROL_SIGMAS = 3.0` (SQL'de de `2 *` yerine `3 *`) "
                "klasik 3-sigma sınırlarını verir.",
            ],
            "moving_average": [
                "**Nedir:** seri başına son {w} tam dönemin geriye dönük ortalaması; pencerenin son dönemiyle "
                "etiketlenir.",
                "**Varsayım:** kısmi dönemler ortalamayı aşağı çekerdi; bu yüzden pencere uygulanmadan önce çıkarılır "
                "(`WHERE NOT partial` pencere fonksiyonundan önce çalışır); bir nokta için değeri olan {w} ardışık "
                "dönem gerekir.",
                "**Nerede:** `analysis.py` içinde `chart_moving_average()` (`value_x100`); `analysis.sql` içindeki "
                "`chart_moving_average` sorgusu (`AVG(value) OVER (... ROWS BETWEEN {w1} PRECEDING AND CURRENT ROW)`).",
                "**Nasıl değiştirilir:** `analysis.py` içinde `CHART_SPEC[\"window\"]` ve `analysis.sql` içinde "
                "`{w1} PRECEDING`, `= {w}` ve `= {w1}` değerlerini yeni pencereye göre ayarlayın.",
            ],
        },
        "stat_head": {
            "ci95": "| Dilim | n | Ortalama | Alt | Üst |",
            "trend": "| n | {per} başına eğim | Kesişim | R² | p-değeri | Sıra başlangıcı |",
            "control_band": "| n | Ortalama | SS | Alt | Üst | Dışarıda |",
            "moving_average": "| Dönem | Seri | Hareketli ortalama |",
        },
        "stat_more": "`expected.json` içinde {n} satır daha.",
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
            "POSTAGE, Manual, ücret ve muhasebe düzeltmesi gibi hizmet satırları brüt satışta kalır; ürün sıralamasına ve birlikte alım adaylarına girmez.",
            "Benzersiz sipariş sayıları aylar, ülkeler veya ürünler arasında toplanamaz.",
            "Birlikte alım çiftleri en çok satan 24 ürünle sınırlıdır ve nedensellik değil birlikte görülme gösterir.",
        ],
        "limit_public": "Bu, kamuya açık tarihsel veridir; güncel veya temsili pazar verisi değildir.",
        "limit_synthetic": "Bu, sentetik test verisidir; gerçek ticari kayıt değildir.",
        "attribution": "Veri kaynağı ve atıf",
        "generated": "Context Layer tarafından üretildi ({recipe}).",
    },
}


def _decimal(value: float, decimals: int, locale: str) -> str:
    text = f"{value:,.{decimals}f}"
    return text.translate(str.maketrans(",.", ".,")) if locale == "tr" else text


def _scaled_text(value: int | None, metric: str, locale: str) -> str:
    """A ×100 statistic value from expected.json as display text (pence → £ for money metrics)."""
    if value is None:
        return "—"
    return _gbp(value, locale) if metric in ("gross_sales", "aov") else _decimal(value / 100, 2, locale)


def _readme_statistic(locale: str, chart: dict, res: dict) -> list[str]:
    """README section for the chart's statistic: what it is, its assumption, where it lives, how to change it,
    and its exported values."""
    r = R[locale]
    spec = chart["spec"]
    statistic, metric = spec["statistic"], spec["metric"]
    if statistic == "none":
        return [r["stat_none"]]
    w = spec["window"]
    out = [f"#### {r['stat'].format(name=chart['overlay_label'])}", ""]
    out += [f"- {line.format(w=w, w1=w - 1)}" for line in r["stat_text"][statistic]] + [""]
    per = {"month": ("month", "ay"), "week": ("week", "hafta")}.get(spec["dimension"], ("", ""))[locale == "tr"]
    head = r["stat_head"][statistic].format(per=per)
    out += [head, "|" + "|".join("---:" if i else "---" for i in range(head.count("|") - 1)) + "|"]
    limit = 24
    if statistic == "ci95":
        rows = res["chart_ci95"]
        for row in rows[:limit]:
            label = row["x"] if row["series"] == "all" else f"{row['x']} · {row['series']}"
            out.append(f"| {_md_escape(label)} | {_int(row['n'], locale)} | {_scaled_text(row['mean_pence'], 'aov', locale)} | "
                       f"{_scaled_text(row['lower_pence'], 'aov', locale)} | {_scaled_text(row['upper_pence'], 'aov', locale)} |")
    elif statistic == "trend":
        rows = [res["chart_trend"]]
        tr = res["chart_trend"]
        fraction = lambda v: "—" if v is None else _decimal(v / 1_000_000, 6, locale)  # noqa: E731
        out.append(f"| {tr['n']} | {_scaled_text(tr['slope_x100'], metric, locale)} | "
                   f"{_scaled_text(tr['intercept_x100'], metric, locale)} | {fraction(tr['r2_x1e6'])} | "
                   f"{fraction(tr['p_value_x1e6'])} | {tr['index_origin'] or '—'} |")
    elif statistic == "control_band":
        rows = [res["chart_control_band"]]
        band = res["chart_control_band"]
        out.append(f"| {band['n']} | " + " | ".join(_scaled_text(band[k], metric, locale) for k in
                                                     ("mean_x100", "sd_x100", "lower_x100", "upper_x100"))
                   + f" | {', '.join(band['outside']) or '—'} |")
    else:
        rows = res["chart_moving_average"]
        for row in rows[-limit:]:
            out.append(f"| {row['x']} | {_md_escape(row['series'])} | {_scaled_text(row['value_x100'], metric, locale)} |")
    if len(rows) > limit:
        out += ["", r["stat_more"].format(n=len(rows) - limit)]
    return out


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
        out += ["", f"### {r['chart']}", "", r["chart_text"].format(title=_md_text(chart["title"]), rows=len(res["chart"])), "",
                # Country names can come from uploaded data: a backtick is written as its JSON escape so it can
                # never close the fence.
                "```json", json.dumps(chart["spec"], ensure_ascii=False, indent=2).replace("`", "\\u0060"), "```", ""]
        out += _readme_statistic(locale, chart, res)
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


def _chart_sql(spec: dict, m: dict, locale: str, filters: dict | None = None, include_service: bool = False) -> dict:
    """SQL for an exported chart, shared verbatim by analysis.py and analysis.sql.

    ``scope`` sets the chart's date window from the dataset range, the --start/--end filters and the spec;
    ``view`` creates ``chart_buckets`` (one row per bucket; on a month/week axis every period is present and
    flagged ``partial`` as in Chart Studio); ``queries`` holds the chart rows and the statistic's query. Values
    come from the validated ChartSpec and catalog (allowlisted names, ISO dates) and are written as literals.
    """
    from analysis.chart_studio import _BUCKET, _BUCKET_NOTE, _BUCKET_NOTE_TR, _RANK

    v = L[locale]["v"]
    filters = filters or {}
    dim, metric, statistic = spec["dimension"], spec["metric"], spec["statistic"]
    time_axis = dim in ("month", "week")
    starts = [f"DATE {_literal(m['start'])}", "getvariable('start_date')::DATE"]
    ends = [f"DATE {_literal(m['end'])}", "getvariable('end_date')::DATE"]
    starts += [f"DATE {_literal(spec['start'])}"] if spec["start"] else []
    ends += [f"DATE {_literal(spec['end'])}"] if spec["end"] else []
    scope = (f"SET VARIABLE chart_start = greatest({', '.join(starts)});\n"
             f"SET VARIABLE chart_end = least({', '.join(ends)})")

    where = ["order_date BETWEEN getvariable('chart_start') AND getvariable('chart_end')"]
    if dim == "product" and not include_service:
        where.append(PRODUCTS_ONLY)
    groups_cte, source = "", "sales"
    if dim == "country_group":
        # Membership is fixed when the bundle is made (at the end of the exported scope, or today), and written
        # out as literals, so the script never needs the reference file.
        from analysis import reference

        end = min(d for d in [m["end"], filters.get("end"), spec["end"]] if d)
        unmatched = _literal(reference.bucket_label(spec["group"], "unmatched", locale))
        if spec["group_as_of"] == "transaction":
            # Membership by date (AW-22): each order takes the bucket valid on its own date.
            start = max(d for d in [m["start"], filters.get("start"), spec["start"]] if d)
            spans = reference.spans(spec["group"], m["countries"], start, end, locale)
            rows = ",\n        ".join(
                f"({_literal(c)}, {_literal(reference.bucket_label(spec['group'], b, locale))}, DATE {_literal(a)}, DATE {_literal(z)})"
                for c, b, a, z, _ in sorted(spans))
            groups_cte = (f"country_groups AS (\n    -- {spec['group']} membership on each order's date"
                          f" ({reference.card(spec['group'], locale)['source']})\n"
                          f"    SELECT * FROM (VALUES\n        {rows}\n    ) AS g(member_country, bucket, valid_from, valid_to)\n),\n")
            source = ("sales LEFT JOIN country_groups AS g\n"
                      "        ON g.member_country = country AND order_date BETWEEN g.valid_from AND g.valid_to")
        else:
            on = reference.resolve_as_of(spec["group_as_of"], end)
            mapping = reference.classify(spec["group"], m["countries"], on, locale)
            rows = ",\n        ".join(f"({_literal(c)}, {_literal(reference.bucket_label(spec['group'], mapping[c]['bucket'], locale))})"
                                       for c in sorted(mapping))
            groups_cte = (f"country_groups AS (\n    -- {spec['group']} membership on {on.isoformat()}"
                          f" ({reference.card(spec['group'], locale)['source']})\n"
                          f"    SELECT * FROM (VALUES\n        {rows}\n    ) AS g(country, bucket)\n),\n")
            source = "sales LEFT JOIN country_groups AS g USING (country)"
        bucket_sql = f"COALESCE(g.bucket, {unmatched})"
    if spec["countries"]:
        where.append("country IN (" + ", ".join(_literal(c) for c in spec["countries"]) + ")")
    if spec["exclude_countries"]:
        where.append("country NOT IN (" + ", ".join(_literal(c) for c in spec["exclude_countries"]) + ")")
    series = "country" if spec["split_by_country"] else "'all'"
    product = dim == "product"
    note = (_BUCKET_NOTE_TR if locale == "tr" else _BUCKET_NOTE)[dim]
    bucket = bucket_sql if dim == "country_group" else _BUCKET[dim]
    order_totals = (
        f"    -- {v['orders']}\n"
        "    SELECT\n"
        f"        {bucket} AS x,  -- {note}\n"
        f"        {series} AS series,\n"
        "        invoice,\n"
        + ("        MIN(product) AS label,\n" if product else "")
        + "        SUM(line_pence) AS order_pence,\n"
        "        SUM(quantity) AS order_units\n"
        f"    FROM {source}\n"
        "    WHERE " + "\n      AND ".join(where) + "\n"
        "    GROUP BY x, series, invoice"
    )
    value_note = f"  -- {v['value'].format(what=v['what'][metric])}"
    if time_axis:
        value = {"gross_sales": "COALESCE(t.pence, 0) / 100.0", "orders": "COALESCE(t.orders, 0)::DOUBLE",
                 "units": "COALESCE(t.units, 0)::DOUBLE", "aov": "t.pence / t.orders / 100.0"}[metric]
        label = "strftime(first_day, '%Y-%m')" if dim == "month" else "strftime(first_day, '%Y-%m-%d')"
        period_end = "last_day(first_day)::DATE" if dim == "month" else "(first_day + INTERVAL 6 DAY)::DATE"
        step = "INTERVAL 1 MONTH" if dim == "month" else "INTERVAL 7 DAY"
        names = spec["countries"] if spec["split_by_country"] else ["all"]
        series_rows = ", ".join(f"({i}, {_literal(name)})" for i, name in enumerate(names, 1))
        view = (
            "CREATE OR REPLACE TEMP VIEW chart_buckets AS\n"
            "WITH periods AS (\n"
            f"    -- {v['periods'].format(per=v['per'][dim])}\n"
            "    SELECT\n"
            "        row_number() OVER (ORDER BY first_day) - 1 AS period_index,\n"
            f"        {label} AS x,\n"
            "        first_day::DATE AS period_start,\n"
            f"        {period_end} AS period_end\n"
            "    FROM generate_series(\n"
            f"        date_trunc('{dim}', getvariable('chart_start')), getvariable('chart_end'), {step}\n"
            "    ) AS g(first_day)\n"
            "),\n"
            "series AS (\n"
            f"    -- {v['series_split'] if spec['split_by_country'] else v['series_all']}\n"
            f"    SELECT * FROM (VALUES {series_rows}) AS s(series_order, series)\n"
            "),\n"
            "order_totals AS (\n" + order_totals + "\n),\n"
            "totals AS (\n"
            f"    -- {v['totals']}\n"
            "    SELECT\n"
            "        x,\n"
            "        series,\n"
            "        SUM(order_pence)::BIGINT AS pence,\n"
            "        COUNT(*)::BIGINT AS orders,\n"
            "        SUM(order_units)::BIGINT AS units,\n"
            "        SUM(order_pence::HUGEINT * order_pence) AS pence_squared\n"
            "    FROM order_totals\n"
            "    GROUP BY x, series\n"
            ")\n"
            "SELECT\n"
            "    p.period_index,\n"
            "    s.series_order,\n"
            "    p.x,\n"
            "    s.series,\n"
            f"    -- {v['partial']}\n"
            "    (p.period_start < getvariable('chart_start') OR p.period_end > getvariable('chart_end')) AS partial,\n"
            "    COALESCE(t.pence, 0)::BIGINT AS pence,\n"
            "    COALESCE(t.orders, 0)::BIGINT AS orders,\n"
            "    COALESCE(t.units, 0)::BIGINT AS units,\n"
            "    COALESCE(t.pence_squared, 0)::HUGEINT AS pence_squared,\n"
            f"    {value} AS value{value_note}\n"
            "FROM periods AS p\n"
            "CROSS JOIN series AS s\n"
            "LEFT JOIN totals AS t ON t.x = p.x AND t.series = s.series"
        )
        order = "period_index, series_order"
        chart_sql = f"SELECT x, series, partial, pence, orders, units\nFROM chart_buckets\nORDER BY {order}"
    else:
        value = {"gross_sales": "SUM(order_pence) / 100.0", "orders": "COUNT(*)::DOUBLE",
                 "units": "SUM(order_units)::DOUBLE", "aov": "SUM(order_pence) / COUNT(*) / 100.0"}[metric]
        ranked = dim in ("country", "product", "country_group")
        rank = f"{_RANK[metric]} DESC, x" if ranked else "x"
        view = (
            "CREATE OR REPLACE TEMP VIEW chart_buckets AS\n"
            "WITH " + groups_cte + "order_totals AS (\n" + order_totals + "\n)\n"
            "SELECT\n"
            f"    row_number() OVER (ORDER BY {rank}) AS bucket_order,  -- "
            + (v["rank"].format(n=spec["top_n"]) if ranked else v["weekday"]) + "\n"
            "    x,\n"
            "    series,\n"
            + ("    MIN(label) AS label,\n" if product else "")
            + "    SUM(order_pence)::BIGINT AS pence,\n"
            "    COUNT(*)::BIGINT AS orders,\n"
            "    SUM(order_units)::BIGINT AS units,\n"
            "    SUM(order_pence::HUGEINT * order_pence) AS pence_squared,\n"
            f"    {value} AS value{value_note}\n"
            "FROM order_totals\n"
            "GROUP BY x, series"
            + (f"\nQUALIFY bucket_order <= {int(spec['top_n'])}" if dim in ("country", "product") else "")
        )
        order = "bucket_order"
        columns = "x, series, label, pence, orders, units" if product else "x, series, pence, orders, units"
        chart_sql = f"SELECT {columns}\nFROM chart_buckets\nORDER BY {order}"

    queries = {"chart": chart_sql}
    if statistic == "ci95":
        queries["chart_ci95"] = (
            "SELECT\n"
            "    x,\n"
            "    series,\n"
            "    orders AS n,\n"
            "    pence / NULLIF(orders, 0) AS mean_pence,\n"
            "    CASE WHEN orders >= 2\n"
            "         THEN sqrt((orders * pence_squared - pence::HUGEINT * pence)::DOUBLE / (orders * (orders - 1)))\n"
            "    END AS sd_pence\n"
            "FROM chart_buckets\n"
            f"ORDER BY {order}"
        )
    elif statistic == "trend":
        queries["chart_trend"] = (
            "SELECT\n"
            "    regr_count(value, period_index)::BIGINT AS n,\n"
            "    regr_slope(value, period_index) AS slope,\n"
            "    regr_intercept(value, period_index) AS intercept,\n"
            "    regr_r2(value, period_index) AS r2\n"
            "FROM chart_buckets\n"
            f"-- {v['complete']}; {v['no_value']}\n"
            "WHERE series = 'all' AND NOT partial AND value IS NOT NULL"
        )
    elif statistic == "control_band":
        queries["chart_control_band"] = (
            "WITH complete AS (\n"
            "    SELECT period_index, x, value\n"
            "    FROM chart_buckets\n"
            f"    WHERE series = 'all' AND NOT partial AND value IS NOT NULL  -- {v['complete']}\n"
            "),\n"
            "band AS (\n"
            "    SELECT COUNT(*)::BIGINT AS n, AVG(value) AS mean, STDDEV_SAMP(value) AS sd\n"
            "    FROM complete\n"
            ")\n"
            "SELECT\n"
            "    n,\n"
            "    mean,\n"
            "    sd,\n"
            "    mean - 2 * sd AS lower,\n"
            "    mean + 2 * sd AS upper,\n"
            "    (SELECT list(x ORDER BY period_index) FROM complete\n"
            "     WHERE value < band.mean - 2 * band.sd OR value > band.mean + 2 * band.sd) AS outside\n"
            "FROM band"
        )
    elif statistic == "moving_average":
        w = int(spec["window"])
        queries["chart_moving_average"] = (
            "SELECT\n"
            "    x,\n"
            "    series,\n"
            "    AVG(value) OVER recent AS value\n"
            "FROM chart_buckets\n"
            f"WHERE NOT partial  -- {v['complete']}\n"
            f"WINDOW recent AS (PARTITION BY series ORDER BY period_index ROWS BETWEEN {w - 1} PRECEDING AND CURRENT ROW)\n"
            f"QUALIFY COUNT(value) OVER recent = {w}\n"
            f"    AND period_index - MIN(period_index) OVER recent = {w - 1}\n"
            "ORDER BY series_order, period_index"
        )
    return {"scope": scope, "view": view, "queries": queries}


def _chart_bundle(spec_obj, m: dict, locale: str, filters: dict, include_service: bool = False) -> dict:
    from analysis.chart_studio import scope_text, validate_spec, _T as chart_text

    warnings: list[str] = []
    spec = validate_spec(spec_obj, m, locale=locale, warnings=warnings)
    if spec.pop("transform", None):
        # A money transform (AW-20) is not reproduced by the exported scripts yet: the bundle is the same chart in
        # GBP and says so, rather than a converted chart whose numbers the scripts could not recompute.
        warnings.append("Kod paketi dönüşümsüz (GBP) grafiği içerir; kur, enflasyon ve altın dönüşümü pakete henüz "
                        "aktarılmıyor." if locale == "tr" else
                        "The bundle contains the chart in GBP without the transform; currency, inflation and gold "
                        "transforms are not exported yet.")
    from analysis import reference

    group = reference.card(spec["group"], locale)["label"] if spec["dimension"] == "country_group" else ""
    title = chart_text[locale]["title"][spec["dimension"]].format(m=chart_text[locale]["metric"][spec["metric"]],
                                                                  n=spec["top_n"], g=group)
    title = title[:1].upper() + title[1:]
    if spec["countries"] or spec["exclude_countries"]:
        title += " · " + scope_text(spec, filters.get("country"), locale)
    overlay_label = L[locale]["overlay"][spec["statistic"]].format(w=spec["window"])
    return {"spec": spec, "title": title, "overlay_label": overlay_label, "warnings": warnings,
            **_chart_sql(spec, m, locale, filters, include_service)}


def export_code(request: dict) -> dict:
    """Worker action ``code_export`` (AW-16 §1)."""
    m = meta(request["dataset"])
    where, args, clean = filters_for(request, m)
    locale = "en" if request.get("locale") == "en" else "tr"
    kind = request.get("format", "bundle")
    if kind not in FORMATS:
        raise ValueError("Geçersiz dışa aktarım biçimi." if locale == "tr" else "Invalid export format.")
    from analysis.scope import include_service

    chart = (_chart_bundle(request["chart"], m, locale, clean, include_service(request))
             if request.get("chart") is not None else None)
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
        helpers = {"charts": charts_module}
        if _needs_stats(chart):
            helpers["stats"] = _load_module("stats", _stats_source(locale), "stats.py")
        script = _load_module("context_layer_export_analysis", analysis_py, "analysis.py", helpers)
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
            **({"stats.py": _stats_source(locale).encode("utf-8")} if _needs_stats(chart) else {}),
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
