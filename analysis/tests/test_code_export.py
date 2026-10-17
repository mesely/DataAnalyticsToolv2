"""Developer code export (AW-16 §1): the bundle runs, its SQL and script reproduce expected.json exactly,
exports are byte-identical, and no customer identifier leaves the workbench."""

import base64
import io
import json
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
