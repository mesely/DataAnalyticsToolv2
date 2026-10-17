"""Developer code export (AW-16 §1): the bundle runs, its SQL and script reproduce expected.json exactly,
exports are byte-identical, and no customer identifier leaves the workbench."""

import base64
import io
import json
import math
import os
import py_compile
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

import duckdb
import pytest

import analysis.code_export as code_export
from analysis.code_export import COLUMNS, export_code
from analysis.worker import handle, meta, overview

UCI_FILTERS = {"country": "France", "start": "2011-01-01", "end": "2011-09-30"}
CHART = {"metric": "aov", "dimension": "month", "countries": ["France"], "start": "2011-03-01"}


def unzip(result, target):
    archive = zipfile.ZipFile(io.BytesIO(base64.b64decode(result["base64"])))
    archive.extractall(target)
    return archive


def run_script(folder, *args):
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    return subprocess.run([sys.executable, "analysis.py", *args], cwd=folder, capture_output=True, text=True,
                          env=env, timeout=120)


@pytest.fixture(scope="module")
def uci_bundle(tmp_path_factory):
    result = export_code({"dataset": "uci", "locale": "en", "format": "bundle", "filters": UCI_FILTERS, "chart": CHART})
    folder = tmp_path_factory.mktemp("uci_bundle")
    archive = unzip(result, folder)
    return result, folder, archive


@pytest.fixture(scope="module")
def demo_bundle(tmp_path_factory):
    result = export_code({"dataset": "demo", "locale": "tr", "format": "bundle"})
    folder = tmp_path_factory.mktemp("demo_bundle")
    archive = unzip(result, folder)
    return result, folder, archive


def sql_blocks(text):
    """Split analysis.sql into its preamble and the `-- name:` query blocks."""
    parts = re.split(r"^-- name: (\w+)\n", text, flags=re.M)
    preamble, named = parts[0], dict(zip(parts[1::2], parts[2::2]))
    return preamble, {name: body.strip().rstrip(";") for name, body in named.items()}


def run_sql(folder, monkeypatch):
    monkeypatch.chdir(folder)  # data_path in the SQL file is relative, as for the duckdb CLI
    preamble, queries = sql_blocks((folder / "analysis.sql").read_text())
    con = duckdb.connect()
    con.execute(preamble)  # SET VARIABLE lines and the `sales` view, as a multi-statement script
    out = {}
    for name, body in queries.items():
        cursor = con.execute(body)
        names = [c[0] for c in cursor.description]
        out[name] = [dict(zip(names, row)) for row in cursor.fetchall()]
    con.close()
    return out


@pytest.mark.parametrize("bundle", ["demo_bundle", "uci_bundle"])
def test_script_check_reproduces_expected(bundle, request):
    result, folder, _ = request.getfixturevalue(bundle)
    proc = run_script(folder, "--check", "--out", "out")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    lines = [line for line in proc.stdout.splitlines() if line[:1] in "✓✗"]
    assert lines and all(line.startswith("✓") for line in lines)
    assert any(" kpis.gross_pence " in line for line in lines)
    for name in ["kpis.csv", "monthly_trend.csv", "top_countries.csv", "top_products.csv", "copurchase_pairs.csv"]:
        assert (folder / "out" / name).read_text(encoding="utf-8").count("\n") >= 2
    # the script regenerates byte-identical figures
    for svg in (folder / "figures").glob("*.svg"):
        assert (folder / "out" / "figures" / svg.name).read_bytes() == svg.read_bytes()


def test_check_fails_on_any_difference(demo_bundle, tmp_path):
    _, folder, _ = demo_bundle
    copy = tmp_path / "copy"
    shutil.copytree(folder, copy, ignore=shutil.ignore_patterns("out"))
    expected = json.loads((copy / "expected.json").read_text())
    expected["results"]["kpis"]["gross_pence"] += 1
    (copy / "expected.json").write_text(json.dumps(expected))
    proc = run_script(copy, "--check", "--out", "out")
    assert proc.returncode == 1 and "✗ kpis.gross_pence" in proc.stdout
    # a different scope is reported, never silently compared
    proc = run_script(folder, "--check", "--country", "France", "--out", str(tmp_path / "fr"))
    assert proc.returncode == 1 and "✗ scope" in proc.stdout
    proc = run_script(folder, "--data", str(tmp_path / "missing.parquet"))
    assert proc.returncode == 2


@pytest.mark.parametrize("bundle", ["demo_bundle", "uci_bundle"])
def test_sql_file_reproduces_expected(bundle, request, monkeypatch):
    _, folder, _ = request.getfixturevalue(bundle)
    expected = json.loads((folder / "expected.json").read_text())
    got = run_sql(folder, monkeypatch)
    assert got["kpis"] == [expected["results"]["kpis"]]
    for name in ["monthly_trend", "top_countries", "top_products", "copurchase_pairs"]:
        assert got[name] == expected["results"][name], name
    if "chart" in expected["results"]:
        assert got["chart"] == expected["results"]["chart"]


def test_expected_matches_workbench_and_is_integer_only(uci_bundle):
    result, folder, _ = uci_bundle
    expected = json.loads((folder / "expected.json").read_text())
    observed = overview({"dataset": "uci", "filters": UCI_FILTERS})
    k = expected["results"]["kpis"]
    assert (k["row_count"], k["orders"], k["gross_pence"]) == (
        observed["summary"]["rows"], observed["summary"]["orders"], observed["summary"]["gross_pence"])
    assert expected["filters"] == UCI_FILTERS
    assert expected["dataset"]["sha256"] == meta("uci")["sha256"]
    assert expected["engine"] == f"duckdb {duckdb.__version__}"
    assert expected["row_count"] == k["row_count"] and expected["data_file"]["included"] is True

    def walk(value):
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        else:
            assert not isinstance(value, float), value

    walk(expected)
    assert (folder / "requirements.txt").read_text() == f"duckdb=={duckdb.__version__}\n"
    # the chart block equals the Chart Studio numbers for the same spec and scope
    from analysis.chart_studio import chart

    studio = chart({"dataset": "uci", "filters": UCI_FILTERS, "base_spec": CHART, "locale": "en"})
    observed_rows = {d["x"]: d["value"] for d in studio["data"]}
    for row in expected["results"]["chart"]:
        assert observed_rows[row["x"]] == round(row["pence"] / row["orders"] / 100, 2)


def test_exports_are_byte_identical():
    for request in [{"dataset": "demo", "locale": "en"},
                    {"dataset": "uci", "locale": "tr", "filters": UCI_FILTERS, "chart": CHART}]:
        a, b = export_code(dict(request)), export_code(dict(request))
        assert a["base64"] == b["base64"] and a["sha256"] == b["sha256"]


def test_zip_layout_is_deterministic(uci_bundle):
    result, _, archive = uci_bundle
    infos = archive.infolist()
    names = [i.filename for i in infos]
    assert names == sorted(names)
    assert names == [f["path"] for f in result["files"]]
    assert set(names) == {"README.md", "analysis.py", "analysis.sql", "charts.py", "data/transactions.parquet",
                          "expected.json", "figures/chart.svg", "figures/monthly_gross_sales.svg",
                          "figures/top_countries.svg", "figures/top_products.svg", "requirements.txt"}
    assert all(i.date_time == (1980, 1, 1, 0, 0, 0) and i.compress_type == zipfile.ZIP_DEFLATED for i in infos)
    assert {i.filename: i.external_attr >> 16 for i in infos}["analysis.py"] == 0o100755
    assert result["filename"] == "context-layer-uci-analysis.zip" and result["content_type"] == "application/zip"
    assert result["bytes"] == len(base64.b64decode(result["base64"]))
    for f in result["files"]:
        import hashlib
        assert hashlib.sha256(archive.read(f["path"])).hexdigest() == f["sha256"]
    assert set(result["preview"]) == {"README.md", "analysis.py", "analysis.sql"}
    assert result["preview"]["analysis.py"] == archive.read("analysis.py").decode()


def test_no_customer_identifier_anywhere(uci_bundle, demo_bundle):
    for result, folder, archive in (uci_bundle, demo_bundle):
        with duckdb.connect() as con:
            columns = [r[0] for r in con.execute("DESCRIBE SELECT * FROM read_parquet(?)",
                                                 [str(folder / "data/transactions.parquet")]).fetchall()]
            rows = con.execute("SELECT order_date, invoice FROM read_parquet(?)",
                               [str(folder / "data/transactions.parquet")]).fetchall()
        assert tuple(columns) == COLUMNS and "customer_id" not in columns
        assert rows == sorted(rows)  # stable order
        for name in archive.namelist():
            if not name.endswith(".parquet"):
                text = archive.read(name).decode()
                assert "customer_id" not in text and "CustomerID" not in text, name


def test_readme_documents_scope_figures_and_attribution(uci_bundle, demo_bundle):
    _, folder, _ = uci_bundle
    readme = (folder / "README.md").read_text()
    src = meta("uci")["source"]
    for needle in ["## Quick start", "python -m venv .venv", "pip install -r requirements.txt",
                   "python analysis.py --check", "duckdb < analysis.sql", 'duckdb -c ".read analysis.sql"',
                   "## How to change it", "## Reproducibility", "## Limitations", "units_per_order",
                   "date_trunc('week', order_date)", "COPY (SELECT * FROM sales)", "not net revenue",
                   "POSTAGE", meta("uci")["sha256"], src["license"], src["doi"], src["url"],
                   "![Monthly gross sales](figures/monthly_gross_sales.svg)", "(figures/top_countries.svg)",
                   "(figures/top_products.svg)", "(figures/chart.svg)", "country = `France`"]:
        assert needle in readme, needle
    for metric in ["gross_sales", "orders", "units", "aov"]:
        assert f"(`{metric}`)" in readme
    for column in COLUMNS:
        assert f"| `{column}` |" in readme
    tr = (demo_bundle[1] / "README.md").read_text()
    assert "## Hızlı başlangıç" in tr and "## Nasıl değiştirilir" in tr and "sentetik" in tr


def test_generated_code_quality(uci_bundle, demo_bundle):
    for _, folder, _ in (uci_bundle, demo_bundle):
        for name in ["analysis.py", "charts.py"]:
            py_compile.compile(str(folder / name), doraise=True)
        source = (folder / "analysis.py").read_text()
        assert source.startswith("#!/usr/bin/env python3\n\"\"\"")
        assert "from __future__ import annotations" in source and "@dataclass(frozen=True)" in source
        for fn in ["def kpis(", "def monthly_trend(", "def top_countries(", "def top_products(",
                   "def copurchase_pairs(", "def write_csv(", "def check_against_expected(", "def main("]:
            assert fn in source
        imports = {line.split()[1] for line in source.splitlines() if line.startswith(("import ", "from "))}
        assert imports <= {"__future__", "argparse", "csv", "json", "sys", "dataclasses", "pathlib", "typing",
                           "duckdb", "charts"}
        charts_src = (folder / "charts.py").read_text()
        assert "#5264df" in charts_src and "#172238" in charts_src and "#b9905b" in charts_src
        assert "import duckdb" not in charts_src
        for svg in (folder / "figures").glob("*.svg"):
            root = ET.fromstring(svg.read_text())
            tags = [child.tag.split("}")[1] for child in root]
            assert tags[:2] == ["title", "desc"] and root.attrib["role"] == "img"
    assert "def chart(" in (uci_bundle[1] / "analysis.py").read_text()
    assert "Kapsam için tüm sorguları" in (demo_bundle[1] / "analysis.py").read_text()  # TR comments


def test_single_file_formats(uci_bundle):
    bundle = uci_bundle[0]
    for kind, filename, content_type in [("python", "context-layer-uci-analysis.py", "text/x-python"),
                                         ("sql", "context-layer-uci-analysis.sql", "application/sql")]:
        r = export_code({"dataset": "uci", "locale": "en", "format": kind, "filters": UCI_FILTERS, "chart": CHART})
        assert r["filename"] == filename and r["content_type"] == content_type and r["data_included"] is False
        text = base64.b64decode(r["base64"]).decode()
        name = "analysis.py" if kind == "python" else "analysis.sql"
        assert text == bundle["preview"][name] == r["preview"][name]
        assert r["files"] == [{"path": name, "bytes": r["bytes"], "sha256": r["sha256"]}]


def test_large_data_is_omitted_but_expected_kept(monkeypatch):
    monkeypatch.setattr(code_export, "MAX_DATA_BYTES", 1000)
    r = export_code({"dataset": "demo", "locale": "en"})
    paths = [f["path"] for f in r["files"]]
    assert r["data_included"] is False and "data/transactions.parquet" not in paths
    assert "expected.json" in paths and "--data" in r["preview"]["README.md"]
    archive = zipfile.ZipFile(io.BytesIO(base64.b64decode(r["base64"])))
    assert json.loads(archive.read("expected.json"))["data_file"]["included"] is False


def test_invalid_requests_raise():
    with pytest.raises(ValueError):
        export_code({"dataset": "demo", "format": "xlsx"})
    with pytest.raises(ValueError):
        export_code({"dataset": "../etc/passwd"})
    with pytest.raises(ValueError):
        export_code({"dataset": "demo", "chart": {"metric": "profit"}})
    with pytest.raises(ValueError):
        export_code({"dataset": "demo", "filters": {"country": "Atlantis"}})


def test_worker_dispatch():
    r = handle({"action": "code_export", "dataset": "demo", "format": "sql", "locale": "tr"})
    assert r["format"] == "sql" and "SET VARIABLE data_path" in r["preview"]["analysis.sql"]
    assert "-- name: kpis" in r["preview"]["analysis.sql"]


def test_uploaded_title_cannot_escape_a_sql_comment_or_heading(monkeypatch):
    """A dataset title is user text for uploads: a newline must not end the SQL header comment and add a statement."""
    import analysis.code_export as ce

    real_meta = ce.meta

    def hostile_meta(dataset):
        m = dict(real_meta(dataset))
        m["title"] = "Sales\nDROP TABLE x; -- \r\n# injected"
        return m

    monkeypatch.setattr(ce, "meta", hostile_meta)
    r = ce.export_code({"dataset": "demo", "format": "bundle", "locale": "en"})
    sql = r["preview"]["analysis.sql"]
    readme = r["preview"]["README.md"]
    assert not any(line.startswith("DROP TABLE") for line in sql.splitlines())
    assert not any(line.startswith("# injected") for line in readme.splitlines())
    assert "Sales DROP TABLE x; --" in sql.splitlines()[1]


# ----------------------------------------------------------------- chart statistics in the bundle (amendment)

STAT_CASES = {
    "ci95": ("en", {"start": "2011-01-01", "end": "2011-11-20"},
             {"metric": "aov", "statistic": "ci95", "exclude_countries": ["United Kingdom"]}),
    "ci95_by_country": ("en", {}, {"metric": "aov", "dimension": "country", "statistic": "ci95", "top_n": 5,
                                   "exclude_countries": ["United Kingdom"]}),
    "trend": ("en", {"start": "2011-01-01", "end": "2011-11-20"},
              {"statistic": "trend", "exclude_countries": ["United Kingdom"]}),
    "trend_aov_gaps": ("tr", {}, {"metric": "aov", "dimension": "week", "statistic": "trend", "countries": ["Norway"]}),
    "control_band": ("tr", {"country": "Germany"}, {"metric": "orders", "statistic": "control_band"}),
    "moving_average": ("en", {"end": "2011-06-30"},
                       {"dimension": "week", "statistic": "moving_average", "window": 4,
                        "countries": ["Germany", "France"], "split_by_country": True,
                        "exclude_countries": ["United Kingdom"]}),
}


@pytest.fixture(scope="module", params=sorted(STAT_CASES))
def stat_bundle(request, tmp_path_factory):
    from analysis.chart_studio import chart

    locale, filters, spec = STAT_CASES[request.param]
    result = export_code({"dataset": "uci", "locale": locale, "filters": filters, "chart": spec})
    folder = tmp_path_factory.mktemp(f"stat_{request.param}")
    unzip(result, folder)
    proc = run_script(folder, "--check", "--out", "out")
    studio = chart({"dataset": "uci", "filters": filters, "base_spec": spec, "locale": locale})
    expected = json.loads((folder / "expected.json").read_text())["results"]
    return {"name": request.param, "result": result, "folder": folder, "proc": proc, "studio": studio,
            "expected": expected, "statistic": studio["spec"]["statistic"]}


def _studio_value(row, metric):
    if metric == "gross_sales":
        return round(row["pence"] / 100, 2)
    if metric in ("orders", "units"):
        return row[metric]
    return round(row["pence"] / row["orders"] / 100, 2) if row["orders"] else None


def test_stat_bundle_check_passes(stat_bundle):
    proc = stat_bundle["proc"]
    assert proc.returncode == 0, proc.stdout + proc.stderr
    lines = [line for line in proc.stdout.splitlines() if line[:1] in "✓✗"]
    assert all(line.startswith("✓") for line in lines)
    assert any(f" chart_{stat_bundle['statistic']}" in line for line in lines)
    # the script regenerates the overlay figure byte for byte
    folder = stat_bundle["folder"]
    assert (folder / "out" / "figures" / "chart.svg").read_bytes() == (folder / "figures" / "chart.svg").read_bytes()


def test_stat_bundle_series_equals_chart_studio(stat_bundle):
    """Zero-filled periods (missing average order value), exclusions and partial flags exactly as Chart Studio."""
    studio, rows = stat_bundle["studio"], stat_bundle["expected"]["chart"]
    metric = studio["spec"]["metric"]
    assert len(rows) == len(studio["data"])
    exported = {(row["x"], row["series"]): (_studio_value(row, metric), row.get("partial")) for row in rows}
    shown = {(d.get("key", d["x"]), d["series"]): (d["value"], d.get("partial")) for d in studio["data"]}
    assert exported == shown
    if stat_bundle["name"] == "trend_aov_gaps":
        assert any(row["orders"] == 0 for row in rows)  # weeks without Norwegian orders: zero rows, missing value
    assert "United Kingdom" not in {row["x"] for row in rows}


def test_stat_bundle_overlay_equals_chart_studio(stat_bundle):
    from scipy import special

    from analysis.chart_studio import _ols

    studio, expected, statistic = stat_bundle["studio"], stat_bundle["expected"], stat_bundle["statistic"]
    overlays, metric = studio["overlays"], studio["spec"]["metric"]
    pence = 0.005 + 1e-9  # values are rounded to whole pence on one side and to 2 decimals on the other
    if statistic == "ci95":
        got = {(row["x"], row["series"]): row for row in expected["chart_ci95"]}
        for d in studio["data"]:
            row = got[(d.get("key", d["x"]), d["series"])]
            assert row["n"] == d["n"]
            if "lower" in d:
                assert abs(row["lower_pence"] / 100 - d["lower"]) <= pence
                assert abs(row["upper_pence"] / 100 - d["upper"]) <= pence
                assert abs(row["mean_pence"] / 100 - d["value"]) <= pence
            else:
                assert row["lower_pence"] is None and row["upper_pence"] is None
    elif statistic == "trend":
        trend, shown = expected["chart_trend"], overlays["trend"]
        assert (trend["n"], trend["index_origin"]) == (shown["n"], shown["index_origin"])
        assert abs(trend["slope_x100"] / 100 - shown["slope"]) <= pence + 5e-5
        assert abs(trend["intercept_x100"] / 100 - shown["intercept"]) <= pence + 5e-5
        # R² and p against Chart Studio's own estimator on the same periods, to 1e-6 (stored in millionths)
        rows = [row for row in expected["chart"] if row["series"] == "all"]
        points = [(i, v) for i, row in enumerate(rows)
                  if not row["partial"] and (v := (row["pence"] / row["orders"] / 100 if metric == "aov" and row["orders"]
                                                   else None if metric == "aov" else row["pence"] / 100)) is not None]
        fit = _ols([x for x, _ in points], [y for _, y in points], special)
        assert abs(trend["r2_x1e6"] / 1e6 - fit["r2"]) <= 5e-7 + 1e-12
        assert abs(trend["p_value_x1e6"] / 1e6 - fit["p_value"]) <= 5e-7 + 1e-12
        assert abs(trend["r2_x1e6"] / 1e6 - shown["r2"]) <= 5e-5 + 1e-6
        assert trend["p_value_x1e6"] / 1e6 == pytest.approx(shown["p_value"], abs=1e-6)
    elif statistic == "control_band":
        band, shown = expected["chart_control_band"], overlays["control"]
        assert band["n"] == shown["n"] and band["outside"] == shown["outside"]
        for key in ("mean", "sd", "lower", "upper"):
            assert abs(band[f"{key}_x100"] / 100 - shown[key]) <= pence + 5e-5, key
    else:
        got = [(p["x"], p["series"], p["value_x100"] / 100) for p in expected["chart_moving_average"]]
        shown = overlays["moving_average"]["points"]
        assert [(x, s) for x, s, _ in got] == [(p["x"], p["series"]) for p in shown]
        # An average of 4 pence values often ends in exactly half a penny; Chart Studio's round(x, 2) and the
        # export's whole-pence round() can then break the tie differently, so the bound here is one penny.
        assert all(abs(value - p["value"]) <= 0.01 + 1e-9 for (_, _, value), p in zip(got, shown))
        assert {s for _, s, _ in got} == {"Germany", "France"}


def test_stat_sql_file_reproduces_statistics(stat_bundle, monkeypatch):
    """analysis.sql (regr_*, AVG/STDDEV_SAMP, window functions) agrees with analysis.py's expected.json."""
    expected, statistic = stat_bundle["expected"], stat_bundle["statistic"]
    got = run_sql(stat_bundle["folder"], monkeypatch)
    assert got["chart"] == expected["chart"]
    near = lambda value, scaled, scale=100: abs(round(value * scale) - scaled) <= 1  # noqa: E731
    if statistic == "ci95":
        for sql_row, row in zip(got["chart_ci95"], expected["chart_ci95"]):
            assert (sql_row["x"], sql_row["series"], sql_row["n"]) == (row["x"], row["series"], row["n"])
            if row["mean_pence"] is not None:
                assert near(sql_row["mean_pence"], row["mean_pence"], 1)
            if row["sd_pence"] is not None:
                assert near(sql_row["sd_pence"], row["sd_pence"], 1)
    elif statistic == "trend":
        (sql_row,), trend = got["chart_trend"], expected["chart_trend"]
        assert sql_row["n"] == trend["n"]
        assert near(sql_row["slope"], trend["slope_x100"]) and near(sql_row["intercept"], trend["intercept_x100"])
        assert near(sql_row["r2"], trend["r2_x1e6"], 1_000_000)
    elif statistic == "control_band":
        (sql_row,), band = got["chart_control_band"], expected["chart_control_band"]
        assert sql_row["n"] == band["n"] and sql_row["outside"] == band["outside"]
        for key in ("mean", "sd", "lower", "upper"):
            assert near(sql_row[key], band[f"{key}_x100"]), key
    else:
        rows = expected["chart_moving_average"]
        assert [(r["x"], r["series"]) for r in got["chart_moving_average"]] == [(r["x"], r["series"]) for r in rows]
        assert all(near(a["value"], b["value_x100"]) for a, b in zip(got["chart_moving_average"], rows))


def test_stat_bundle_figure_readme_and_code(stat_bundle):
    folder, statistic, name = stat_bundle["folder"], stat_bundle["statistic"], stat_bundle["name"]
    tr = STAT_CASES[name][0] == "tr"
    svg = (folder / "figures" / "chart.svg").read_text()
    root = ET.fromstring(svg)
    desc = root.find("{http://www.w3.org/2000/svg}desc").text
    marks = {"ci95": 'stroke="#172238" stroke-width="1.2"', "trend": 'stroke-dasharray="6 4"',
             "moving_average": 'stroke-dasharray="6 4"', "control_band": 'fill-opacity="0.14"'}
    assert marks[statistic] in svg
    assert {"ci95": "güven aralığı" if tr else "confidence interval", "trend": "trend",
            "control_band": "Kontrol bandı" if tr else "Control band",
            "moving_average": "moving average"}[statistic] in desc
    if statistic == "ci95":
        whiskers = sum(1 for row in stat_bundle["expected"]["chart_ci95"] if row["lower_pence"] is not None)
        assert svg.count('stroke="#172238" stroke-width="1.2"') >= 3 * whiskers  # a bar and two caps each
    readme = (folder / "README.md").read_text()
    assert ("#### İstatistik:" if tr else "#### Statistic:") in readme
    for needle in (["**Varsayım:**", "**Nasıl değiştirilir:**"] if tr else ["**Assumption:**", "**How to change it:**"]):
        assert needle in readme
    source = (folder / "analysis.py").read_text()
    assert f"def chart_{statistic}(" in source and "def chart_overlay(" in source and "def write_chart_figure(" in source
    imports = {line.split()[1] for line in source.splitlines() if line.startswith(("import ", "from "))}
    assert imports <= {"__future__", "argparse", "csv", "json", "math", "sys", "dataclasses", "pathlib", "typing",
                       "duckdb", "charts", "stats"}
    needs_stats = statistic in ("ci95", "trend")
    assert (folder / "stats.py").exists() == needs_stats and ("import stats" in source) == needs_stats
    sql = (folder / "analysis.sql").read_text()
    for marker in {"trend": ["regr_slope(", "regr_intercept(", "regr_r2("], "control_band": ["AVG(value)", "STDDEV_SAMP(value)"],
                   "moving_average": ["ROWS BETWEEN 3 PRECEDING AND CURRENT ROW", "WHERE NOT partial"],
                   "ci95": ["pence_squared"]}[statistic]:
        assert marker in sql
    if STAT_CASES[name][2].get("exclude_countries"):
        assert "NOT IN ('United Kingdom')" in sql
    for path in [folder / "analysis.py", folder / "charts.py", *([folder / "stats.py"] if needs_stats else [])]:
        py_compile.compile(str(path), doraise=True)
        text = path.read_text()
        assert all(len(line) <= 120 or not line.lstrip().startswith(("#", "--")) for line in text.splitlines())
    if tr:  # comments of the generated chart code follow the locale
        assert "Kapsam için tüm sorguları" in source and "# series in chart order" not in source
        assert "uçlu bıyıklar" in (folder / "charts.py").read_text() and "whiskers with caps" not in (folder / "charts.py").read_text()


def _stats_module(locale="en"):
    return code_export._load_module("stats", code_export._stats_source(locale), "stats.py")


def test_stats_module_matches_scipy():
    """stats.py (dependency-free Student-t) against scipy.special.stdtr / stdtrit, to 1e-9 relative."""
    from scipy import special

    stats = _stats_module()
    for df in [1, 2, 3, 4, 5, 7, 10, 19, 30, 57, 100, 250, 1000, 2500, 10_000, 50_000]:
        for t in [-80, -30, -10, -5, -3, -2.5, -1.96, -1, -0.3, -0.01, 0, 0.01, 0.3, 1, 2, 4, 9, 40]:
            want = float(special.stdtr(df, t))
            if want > 1e-290:
                assert stats.t_cdf(t, df) == pytest.approx(want, rel=1e-9, abs=0), (df, t)
            two_sided = float(2 * special.stdtr(df, -abs(t)))
            if two_sided > 1e-290:
                assert stats.t_two_sided_p(t, df) == pytest.approx(two_sided, rel=1e-9, abs=0), (df, t)
        for p in [1e-12, 1e-6, 0.001, 0.025, 0.05, 0.1, 0.2, 0.8, 0.9, 0.95, 0.975, 0.99, 0.995, 0.999, 0.9999]:
            assert stats.t_quantile(p, df) == pytest.approx(float(special.stdtrit(df, p)), rel=1e-9, abs=0), (df, p)
    for x in [1e-8, 0.01, 0.3, 0.5, 0.7, 0.99, 1 - 1e-9]:
        for a in [0.5, 1, 2.5, 10, 300]:
            for b in [0.5, 1, 3, 40]:
                assert stats.regularized_incomplete_beta(x, a, b) == pytest.approx(
                    float(special.betainc(a, b, x)), rel=1e-9, abs=1e-300)
    # exact identities: Cauchy (df = 1) and the symmetry of the distribution
    assert stats.t_cdf(1.0, 1) == pytest.approx(0.75, rel=1e-14)
    assert stats.t_quantile(0.5, 7) == 0.0 and stats.t_quantile(0.025, 7) == -stats.t_quantile(0.975, 7)
    assert stats.t_cdf(1e-9, 1) == pytest.approx(0.5 + 1e-9 / math.pi, rel=1e-15)  # scipy rounds this to 0.5
    with pytest.raises(ValueError):
        stats.t_quantile(1.0, 5)
    tr = _stats_module("tr")
    assert tr.t_quantile(0.975, 12) == stats.t_quantile(0.975, 12) and "Bağımlılıksız" in tr.__doc__


def test_stat_exports_are_byte_identical():
    locale, filters, spec = STAT_CASES["trend"]
    request = {"dataset": "uci", "locale": locale, "filters": filters, "chart": spec}
    assert export_code(dict(request))["sha256"] == export_code(dict(request))["sha256"]


def test_hostile_country_name_stays_a_literal_in_exported_code(monkeypatch, tmp_path):
    """Uploaded data can name a country anything. An excluded country with quotes, backslashes and a newline must stay
    a string literal in analysis.py and analysis.sql: the bundle still parses, runs and passes its own check."""
    import analysis.chart_studio as cs
    import analysis.code_export as ce

    hostile = 'Nowhere"""); import os  # \\x41 \'\n-- DROP ```'
    real_meta = ce.meta

    def with_hostile(dataset):
        m = dict(real_meta(dataset))
        m["countries"] = [*m["countries"], hostile]
        return m

    monkeypatch.setattr(ce, "meta", with_hostile)
    monkeypatch.setattr(cs, "meta", with_hostile)
    result = ce.export_code({"dataset": "demo", "locale": "en", "format": "bundle",
                             "chart": {"dimension": "country", "exclude_countries": [hostile]}})
    unzip(result, tmp_path)
    source = (tmp_path / "analysis.py").read_text()
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")  # an unescaped backslash would be a SyntaxWarning and change the SQL text
        tree = compile(source, "analysis.py", "exec", flags=__import__("ast").PyCF_ONLY_AST)
    import ast

    # The script imports only what the template imports; the hostile text is data, not a statement.
    imported = {a.name for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)) for a in node.names}
    assert "os" not in imported
    # The SQL the script runs equals the SQL file's text: the name survived both files unchanged.
    view = next(ast.literal_eval(node.value) for node in tree.body
                if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "CHART_VIEW_SQL")
    assert view.strip() + ";" in (tmp_path / "analysis.sql").read_text()
    assert hostile.replace("'", "''") in view
    readme = (tmp_path / "README.md").read_text()
    assert not any(line.startswith("-- DROP") for line in readme.splitlines())
    assert sum(line.startswith("```") for line in readme.splitlines()) % 2 == 0 and "\\`\\`\\`" in readme and "DROP \\u0060\\u0060\\u0060" in readme
    proc = run_script(tmp_path, "--check", "--out", "out")
    assert proc.returncode == 0, proc.stdout + proc.stderr
