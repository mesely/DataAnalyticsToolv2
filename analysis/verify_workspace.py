"""Repeatable HTTP acceptance for the loopback phase1 fixture, never production.

CONTEXTLAYER_FIXTURE_PASSWORD must contain the existing local IdP fixture password.
Run: .venv/bin/python -B -m analysis.verify_workspace --out <receipt.json>
Creates a public-data decision and a tiny synthetic owner dataset. No live model calls.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import http.cookiejar
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from analysis.fingerprint import fingerprint, ROOT
from analysis.narrative import packet, validate_statements

BASE = "http://127.0.0.1:8123"
B = "/v1/dashboard/workbench"
CSV = (ROOT / "analysis/data/preparation-example.csv").read_text()
MAP = dict(zip(
    ["invoice", "product_id", "product", "quantity", "unit_price", "order_date", "country"],
    ["order", "sku", "title", "qty", "price", "day", "market"],
))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def local_url(url):
    p = urllib.parse.urlsplit(url)
    if p.scheme != "http" or p.hostname != "127.0.0.1" or p.port not in {8123, 8188}:
        raise ValueError("Acceptance only permits the existing loopback fixture")
    return url


class Client:
    def __init__(self, username, password):
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), NoRedirect())
        self.csrf = None
        status, _, headers = self.request("GET", "/v1/auth/login")
        assert status == 302, "Fixture login did not redirect"
        authorize = urllib.parse.urlsplit(local_url(headers["Location"]))
        fields = urllib.parse.parse_qs(authorize.query)
        form = {k: v[0] for k, v in fields.items()}
        form.update(username=username, password=password)
        status, _, headers = self.request("POST", urllib.parse.urlunsplit(authorize._replace(query="")),
                                          raw=urllib.parse.urlencode(form).encode())
        assert status == 302, "Fixture IdP rejected login"
        status, _, _ = self.request("GET", local_url(headers["Location"]))
        assert status == 302, "Fixture callback failed"
        status, body, _ = self.request("GET", "/v1/auth/session")
        assert status == 200, "Fixture session unavailable"
        self.csrf = body["csrf_token"]

    def request(self, method, path, data=None, *, csrf=True, raw=None):
        headers = {"Accept": "application/json"}
        if data is not None:
            raw = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
        elif raw is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if csrf and self.csrf:
            headers["x-cl-csrf"] = self.csrf
        req = urllib.request.Request(local_url(path if path.startswith("http") else BASE + path),
                                     data=raw, headers=headers, method=method)
        try:
            r = self.opener.open(req, timeout=45)
        except urllib.error.HTTPError as e:
            r = e
        with r:
            body = r.read()
            return r.status, json.loads(body) if body and r.headers.get_content_type() == "application/json" else None, r.headers


def fixtures(directory):
    """Tiny synthetic UI uploads; Parquet generated with the same supported DuckDB dependency."""
    import duckdb
    import pandas as pd
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "retail.csv").write_text(CSV)
    path = directory / "retail.parquet"
    with duckdb.connect() as con:
        con.register("fixture", pd.read_csv(io.StringIO(CSV), dtype=str))
        con.execute("COPY fixture TO ? (FORMAT PARQUET)", [str(path)])
    localized = CSV.replace(",", ";").replace("5.25", "5,25").replace("2.10", "2,10")
    localized = localized.replace("2025-01-01", "01/02/2025").replace("2025-01-02", "02/02/2025").replace("Cup", "Çığlık")
    (directory / "retail-tr.csv").write_bytes(localized.encode("cp1254"))
    return base64.b64encode(path.read_bytes()).decode()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fixtures-dir", default=str(ROOT / "analysis/.local/phase11-qa"))
    args = ap.parse_args()
    password = os.environ.get("CONTEXTLAYER_FIXTURE_PASSWORD")
    if not password:
        raise SystemExit("Set CONTEXTLAYER_FIXTURE_PASSWORD for the existing local fixture; never use production credentials")
    checks = []
    def check(name, ok, detail=None):
        checks.append({"name": name, "ok": bool(ok), **({"detail": detail} if detail is not None else {})})
    alice, bob, viewer = (Client(u, password) for u in ("selman", "alper", "viewer"))
    check("login three local fixture identities", True)
    started = time.perf_counter()
    status, brief, _ = alice.request("POST", B + "/decisions", {
        "dataset": "uci", "locale": "tr", "use_llm": False,
        "scenario": {"volume_pct": 5, "price_pct": 0, "budget_gbp": 0}})
    check("UCI decision HTTP 200", status == 200, {"http_ms": round((time.perf_counter() - started) * 1000)})
    if status != 200:
        raise RuntimeError("UCI fixture is required; no success receipt written")
    f = brief["forecast"]
    check("nonnegative ordered forecast interval", 0 <= f["next"]["lower_pence"] <= f["next"]["pence"] <= f["next"]["upper_pence"])
    check("nominal is not empirical calibration", f["uncertainty"]["calibrated"] is False and any(d["code"] == "band_undercovers_final" for d in f["diagnostics"]))
    check("coverage with sharpness", all(v["final_mean_width_gbp"] >= 0 and v["development_mean_width_gbp"] >= 0 for v in f["uncertainty"]["levels"].values()), f["uncertainty"]["levels"])
    validated = validate_statements(json.dumps({"statements": brief["narrative"]["local"]}), packet(brief))
    check("all six local narrative types validate", len({s["type"] for s in validated}) == 6 and brief["narrative"]["model"] is None)
    root = ET.fromstring(brief["analysis_context_xml"])
    check("bounded XML ends with output contract", len(brief["analysis_context_xml"].encode()) <= 16000 and root[-1].tag == "output_contract")
    check("three country slices", len(f.get("slices", {}).get("countries", [])) == 3 if isinstance(f.get("slices"), dict) else len(f.get("slices", [])) == 3)
    status, reopened, _ = alice.request("GET", B + "/decisions/" + brief["decision_id"])
    check("owner reopens identical decision", status == 200 and reopened["output_sha256"] == brief["output_sha256"])
    check("other owner cannot read decision", bob.request("GET", B + "/decisions/" + brief["decision_id"])[0] == 404)
    check("viewer cannot create decision", viewer.request("POST", B + "/decisions", {"dataset": "demo"})[0] == 403)
    check("missing CSRF refused", alice.request("POST", B + "/decisions", {"dataset": "demo"}, csrf=False)[0] == 403)
    status, filtered, _ = alice.request("POST", B + "/decisions", {"dataset": "demo", "filters": {"country": "Germany"}})
    check("literal country omitted from both model packets", status == 200 and all("Germany" not in filtered[k] for k in ("context_xml", "analysis_context_xml")))
    encoded = fixtures(Path(args.fixtures_dir))
    status, profile, _ = alice.request("POST", B + "/prepare", {"parquet_base64": encoded})
    check("Parquet profiles without raw values", status == 200 and "Cup" not in json.dumps(profile))
    request = {"parquet_base64": encoded, "mapping": MAP, "options": {"drop_duplicates": True}}
    status, preview, _ = alice.request("POST", B + "/prepare", request)
    check("mapped Parquet exact monetary preview", status == 200 and preview["preview"]["gross_pence"] == 1260 and preview["preview"]["orders"] == 2)
    status, imported, _ = alice.request("POST", B + "/import", request | {"receipt": preview["receipt"], "title": "Phase11 acceptance"})
    check("preview-bound owner import", status == 200 and imported["rows"] == 2)
    check("other owner cannot read imported dataset", bob.request("POST", B + "/run", {"dataset": imported["id"]})[0] == 404)
    check("stale receipt refused", alice.request("POST", B + "/import", request | {"receipt": "stale"})[0] == 400)
    check("both sources refused", alice.request("POST", B + "/prepare", {"csv": CSV, "parquet_base64": encoded})[0] == 400)
    check("malformed Parquet refused", alice.request("POST", B + "/prepare", {"parquet_base64": "UEFSMQ=="})[0] == 400)
    status, csv_preview, _ = alice.request("POST", B + "/prepare", {"csv": CSV, "mapping": MAP, "options": {"drop_duplicates": True}})
    check("CSV/Parquet arithmetic parity", status == 200 and csv_preview["preview"] == preview["preview"])
    out = {
        "generated_utc": datetime.now(timezone.utc).isoformat(), "base": BASE,
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "build": fingerprint(),
        "web_sha256": {name: hashlib.sha256((ROOT / "core/web/dist" / name).read_bytes()).hexdigest() for name in ("app.js", "app.css")},
        "producer": "analysis.verify_workspace", "checks": checks,
        "summary": {"passed": sum(c["ok"] for c in checks), "failed": sum(not c["ok"] for c in checks),
                    "scope": "SERVER HTTP, actual loopback OIDC/CSRF/Postgres/Python. Public UCI and synthetic fixtures. Not browser/load/LLM accuracy."},
    }
    Path(args.out).write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out["summary"]))
    if out["summary"]["failed"]:
        print("Failed checks: " + ", ".join(c["name"] for c in checks if not c["ok"]))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
