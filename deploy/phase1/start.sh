#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
# PostgreSQL 16 on macOS aborts with "postmaster became multithreaded during startup" when the launching
# shell has no valid locale (seen 2026-10-16 from a non-interactive shell); the cluster is initdb'd with --locale=C.
export LC_ALL="${LC_ALL:-C}" LANG="${LANG:-C}"
NODE_BIN="${CONTEXT_NODE_BIN:-/Users/selmanyilmaz/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin}"
if [ -x "$NODE_BIN/node" ]; then export PATH="$NODE_BIN:$PATH"; fi
node -e 'if(Number(process.versions.node.split(".")[0])<22)throw Error("Node.js 22+ required")'
if curl -fsS --max-time 2 http://127.0.0.1:8123/healthz >/dev/null 2>&1; then echo 'Already running: http://127.0.0.1:8123/app/'; exit 0; fi
PG_BIN="${CONTEXT_PG_BIN:-/opt/homebrew/opt/postgresql@16/bin}"
if [ ! -x "$PG_BIN/pg_ctl" ]; then echo 'PostgreSQL 16 required. Install with: brew install postgresql@16';exit 1;fi
mkdir -p analysis/.local
if [ ! -f analysis/.local/postgres/PG_VERSION ]; then
 printf '%s\n' 'phase1-local-only' > analysis/.local/postgres-password;chmod 600 analysis/.local/postgres-password
 "$PG_BIN/initdb" -D analysis/.local/postgres --username=postgres --auth-host=scram-sha-256 --auth-local=scram-sha-256 --pwfile=analysis/.local/postgres-password --encoding=UTF8 --locale=C
fi
if ! "$PG_BIN/pg_ctl" -D analysis/.local/postgres status >/dev/null 2>&1; then "$PG_BIN/pg_ctl" -D analysis/.local/postgres -l /tmp/context-phase1-postgres.log -o '-h 127.0.0.1 -p 5549 -k /tmp -c timezone=UTC' start; fi
if ! PGPASSWORD=phase1-local-only "$PG_BIN/psql" -h127.0.0.1 -p5549 -Upostgres -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='contextlayer_phase1'" | grep -q 1; then PGPASSWORD=phase1-local-only "$PG_BIN/createdb" -h127.0.0.1 -p5549 -Upostgres contextlayer_phase1;fi
if [ ! -x .venv/bin/python ]; then python3.12 -m venv .venv; fi
if ! .venv/bin/python -c 'import duckdb,pandas,networkx,httpx,langchain_core,pytest,sqlglot' >/dev/null 2>&1; then .venv/bin/pip install -c constraints.txt -e '.[dev]';.venv/bin/pip install -r analysis/requirements.txt;fi
if [ ! -f analysis/.local/uci.duckdb ]; then curl --fail -L --max-time 120 'https://archive.ics.uci.edu/static/public/352/online+retail.zip' -o /tmp/online-retail.zip;.venv/bin/python -m analysis.prepare;fi
if [ ! -d core/node_modules ]; then npm --prefix core ci --ignore-scripts;fi
npm --prefix core run build
exec node deploy/phase1/start.mjs
