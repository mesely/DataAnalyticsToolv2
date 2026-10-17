<p align="center"><img src="core/web/src/workbench/assets/avatars/app-mark.jpg" width="96" alt=""></p>
<h1 align="center">Context Layer</h1>
<p align="center">An analytics workspace for retail sales data. Every number is computed by a local engine; a language model may only propose a plan, which is validated before anything runs.</p>
<p align="center"><a href="https://github.com/mesely/DataAnalyticsToolv2/actions/workflows/tests.yml"><img src="https://github.com/mesely/DataAnalyticsToolv2/actions/workflows/tests.yml/badge.svg" alt="CI"></a></p>

<p align="center"><img src="docs/showcase/chart-studio.gif" width="880" alt="Chart Studio: a chart refined step by step"></p>

The workspace covers data preparation, KPIs, a free-text chart builder, governed SQL, product networks, a backtested
weekly forecast, decision briefs, bounded machine-learning experiments and a code hand-off. It runs behind an OIDC
session with per-user ownership and an audit log. It extends Alper Çamlı's metadata and governance platform
([AlperCamli/DataAnalyticsTool](https://github.com/AlperCamli/DataAnalyticsTool)).

Contents: [Screens](#screens) · [How it works](#how-it-works) · [Reproduce it](#reproduce-it) ·
[Optional Llama planner](#optional-llama-planner) · [Tests and measurements](#tests-and-measurements) ·
[Limits](#limits) · [Sources](#sources)

---

## Screens

### Overview

<img src="docs/showcase/01-overview-dark.jpg" width="880" alt="Sales overview, dark appearance">

Dataset and filters in one scope card, four KPIs, the monthly trend and country rankings. Turkish and English,
command search (⌘K), dark and light appearances.

<details><summary>Light appearance</summary>
<img src="docs/showcase/02-overview-light.jpg" width="880" alt="Sales overview, light appearance">
</details>

### Chart Studio

Each request changes the current chart; the screen shows what changed, which planner produced the plan, the data,
the SQL and a commentary built from the computed values.

<img src="docs/showcase/03-chart-studio-compare.jpg" width="880" alt="Germany and France, monthly gross sales">
<img src="docs/showcase/04-chart-studio-interval.jpg" width="880" alt="Average order value by country with 95% t-intervals">
<img src="docs/showcase/05-chart-studio-exclusion.jpg" width="880" alt="Gross sales by country, United Kingdom excluded">

<details><summary>Linear trend with R², p-value and its limitation</summary>
<img src="docs/showcase/06-chart-studio-trend.jpg" width="880" alt="Monthly gross sales with an OLS trend">
</details>

### Decision brief and reasoning tree

Statements are numbered per type (F1, C1, I1, R1, L1; in Turkish O, H, Ç, Ö, S) and nested under the statements
they rest on. Limitations sit under the step they qualify.

<img src="docs/showcase/07-reasoning-tree.jpg" width="880" alt="Decision brief: facts, calculations, inferences and recommendations as a numbered tree">

<details><summary>Backtested weekly forecast</summary>
<img src="docs/showcase/08-decision-forecast.jpg" width="880" alt="Weekly projection with final-window error against naive">
</details>

### Code hand-off

<img src="docs/showcase/09-code-export-readme.jpg" width="880" alt="Code export dialog with the bundle README">

<details><summary>Generated Python</summary>
<img src="docs/showcase/10-code-export-python.jpg" width="880" alt="analysis.py preview">
</details>

### Analysis assistant, networks, expert tools

<img src="docs/showcase/11-analysis-assistant.jpg" width="880" alt="Assistant answer with its computed evidence">
<img src="docs/showcase/12-network.jpg" width="880" alt="Same-invoice co-purchase network">

<details><summary>Change over time, SQL laboratory, data preparation, model studio</summary>
<img src="docs/showcase/13-temporal.jpg" width="880" alt="Network and sales change around a pivot month">
<img src="docs/showcase/14-sql-lab.jpg" width="880" alt="Read-only SQL laboratory">
<img src="docs/showcase/15-data-preparation.jpg" width="880" alt="CSV preparation with explicit mapping">
<img src="docs/showcase/16-model-studio.jpg" width="880" alt="Model studio experiment">
</details>

<details><summary>Phone (390 px)</summary>
<img src="docs/showcase/17-mobile-overview.jpg" width="280" alt="Mobile overview"> <img src="docs/showcase/18-mobile-chart-studio.jpg" width="280" alt="Mobile Chart Studio">
</details>

### Sign-in and empty states

<img src="docs/showcase/19-sign-in.jpg" width="430" alt="Local sign-in page"> <img src="docs/showcase/20-empty-findings.jpg" width="430" alt="Empty findings list">

### Mascot and profile portraits

<p>
<img src="core/web/src/workbench/assets/mascot/mascot-hanging.png" width="88" alt="">
<img src="core/web/src/workbench/assets/mascot/mascot-reading.png" width="88" alt="">
<img src="core/web/src/workbench/assets/mascot/mascot-waving.png" width="88" alt="">
<img src="core/web/src/workbench/assets/mascot/mascot-searching.png" width="88" alt="">
</p>
<p>
<img src="core/web/src/workbench/assets/avatars/analyst-core.jpg" width="72" alt="">
<img src="core/web/src/workbench/assets/avatars/analyst-analyst.jpg" width="72" alt="">
<img src="core/web/src/workbench/assets/avatars/analyst-strategist.jpg" width="72" alt="">
<img src="core/web/src/workbench/assets/avatars/analyst-retail.jpg" width="72" alt="">
<img src="core/web/src/workbench/assets/avatars/analyst-banking.jpg" width="72" alt="">
<img src="core/web/src/workbench/assets/avatars/analyst-automotive.jpg" width="72" alt="">
<img src="core/web/src/workbench/assets/avatars/analyst-energy.jpg" width="72" alt="">
<img src="core/web/src/workbench/assets/avatars/analyst-telecom.jpg" width="72" alt="">
<img src="core/web/src/workbench/assets/avatars/analyst-logistics.jpg" width="72" alt="">
<img src="core/web/src/workbench/assets/avatars/analyst-health.jpg" width="72" alt="">
</p>

---

## How it works

```mermaid
flowchart LR
  B["Browser<br/>React SPA"] -- "cookie session + x-cl-csrf" --> C["Core service<br/>TypeScript, Fastify"]
  C -- "sessions, ownership,<br/>admission, audit" --> P[(PostgreSQL 16)]
  C -- "JSON on stdin/stdout<br/>45 s, bounded output" --> W["Analysis worker<br/>Python 3.12"]
  W --> D[("DuckDB file per dataset<br/>read-only")]
  W -. "optional: plan only,<br/>validated JSON" .-> L["Llama<br/>self-hosted or HF router"]
```

A request goes from the browser to the core service, which checks the session, the CSRF header, the role and the
ownership of every referenced object, takes an admission slot and starts one Python worker process. The worker reads
JSON from stdin, runs parameterised DuckDB queries against the prepared dataset, computes statistics in Python and
prints one JSON result. The core stores runs, findings and decisions in PostgreSQL under the caller's subject and
writes an audit record. No result is stored in the browser.

### Pipeline, stage by stage

| # | Stage | What happens | Methods and parameters | Code |
|---|---|---|---|---|
| 1 | Download | UCI Online Retail (2010-12-01 to 2011-12-09) is downloaded from the official archive. Online Retail II is optional. | `curl` of `archive.ics.uci.edu/static/public/352/online+retail.zip`; the archive's SHA-256 is recorded in the dataset metadata. | `deploy/phase1/start.sh` |
| 2 | Clean and normalise | Excel rows become one table of eligible invoice lines. | Kept only if quantity is an integer in (0, 1 000 000], unit price in (0, 1 000 000], the date parses, the invoice does not start with `C` and the identifiers are present. Duplicates are counted, not removed. `line_pence = round_half_up(quantity × price × 100)` with `Decimal`, per line. Customer ids are replaced by the first 12 hex digits of their SHA-256. | `analysis/prepare.py` `normalize` |
| 3 | Store | One DuckDB file and one metadata file per dataset. | Table `transactions(invoice, product_id, product, quantity BIGINT, unit_price DECIMAL(18,4), order_date DATE, country, customer_id, line_pence BIGINT)`; metadata holds row/order/product/country counts, date range, quality counters and the SHA-256 of the normalised table. | `prepare.py` `store` |
| 4 | Your own data | CSV or Parquet uploads are profiled, mapped column by column and stored per owner. | ≤ 2 MB, ≤ 10 000 rows, ≤ 60 columns; dialect sniffed from `, ; \t`; options `trim`, `drop_duplicates`, `decimal_comma`, `date_format` (`iso`, `dmy_slash`, `mdy_slash`, `dmy_dot`); nothing is guessed. Parquet is read by DuckDB with external access disabled, 64 MB, 1 thread. A receipt (SHA-256 of mapping, options and source hash) must match at import. | `analysis/preparation.py` |
| 5 | Scope | Dataset, country and period are applied to every query. | Dataset ids are allowlisted (`demo`, `uci`, `uci2`, `usr_<owner>_<receipt>`); `order_date >= ?::DATE`, `<= ?::DATE`, `country = ?` as bound parameters; the country must exist in the dataset metadata. | `analysis/worker.py` `filters_for` |
| 6 | KPIs and overview | Gross sales, orders, units, average order value, monthly series, top countries and products. | `SUM(line_pence)/100`, `COUNT(DISTINCT invoice)`, `SUM(quantity)`, gross ÷ orders; top 10 countries, top 12 products, ties broken by id. Every numeric claim in a text answer is matched exactly against these results. | `worker.py` `overview`, `analysis/claims.py` |
| 7 | Co-purchase network | Which of the top products are bought on the same invoice. | Nodes: top 24 products by gross sales. Edge weight: number of invoices containing both (self-join on invoice), kept at ≥ 2 shared invoices, at most 150 edges. Communities: greedy modularity on positive edges. Centrality: degree and unweighted betweenness. Layout: spring layout (seed 47, 150 iterations) then 220 separation passes to ≥ 72 px. | `worker.py` `graph`, `analysis/layout.py` |
| 8 | Change over time | Sales, concentration and the same product network before, around and after a pivot month. | Windows of 1–3 months; fixed universe of 24 products; product HHI; bootstrap interval of average order value (200 resamples, seed 47); edge Jaccard overlap, new and lost links, the 15 largest changes. Partial windows are flagged. | `analysis/temporal.py` |
| 9 | Expert SQL | Read-only SQL against the scoped data. | Validator plus AST walk (≤ 500 nodes): one table, no joins, no recursive CTEs, 29 allowed functions, `customer_id` hidden. DuckDB opened read-only with 128 MB, 1 thread, external access off, 5 s interrupt, ≤ 500 rows returned. | `analysis/sql_lab.py` |
| 10 | Chart Studio | A sentence becomes a validated chart specification, then a chart. | ChartSpec v1: metric (`gross_sales`, `orders`, `units`, `aov`), dimension (`month`, `week`, `weekday`, `country`, `product`), chart (`line`, `area`, `bar`), period, up to 5 countries, up to 5 excluded countries, top N 3–20, statistic, window 2–12, sort. The local planner parses Turkish and English (relative periods, quarters, month names, Turkish country names, "hariç"/"except", comparisons, removals). One CTE per request with bound parameters; identifiers only from allowlists. | `analysis/chart_studio.py` |
| 11 | Chart statistics | Statistics that are valid for the chosen chart, each with its stated assumption. | 95 % interval: mean ± t₀.₉₇₅,ₙ₋₁ · s/√n over invoice totals (average order value only). Trend: OLS over complete periods, R² and two-sided slope p-value from the t distribution. Control band: mean ± 2 s over complete periods. Moving average over complete periods. Partial periods are flagged and excluded from these. An interval asked for on a total becomes a control band with a warning. | `chart_studio.py` `render` |
| 12 | Forecast | A one-week projection of weekly gross sales, selected by backtest. | 11 registered methods: naive, seasonal naive (52), drift, means of 2/4/8, simple exponential smoothing (α 0.2/0.5/0.8), damped Holt (two settings). One-step rolling origin; the last `min(12, max(4, n/5))` origins are a final window that never takes part in selection. Metrics: MAE, RMSE, WAPE, sMAPE, MASE, bias. Band: split-conformal residual quantile at 90 %, absolute or relative scaling chosen on development coverage. | `analysis/forecast.py` |
| 13 | Decision brief | Ranked next steps, price/volume scenarios and a typed narrative. | Candidates scored by a published checklist (traceability 40, descriptive sufficiency 20, temporal validation 20, business validation 0); not a probability. Statements typed fact, assumption, calculation, inference, recommendation, limitation, each citing evidence ids. A model narrative is accepted only if every number matches a cited value and every id exists. | `analysis/decisions.py`, `analysis/narrative.py` |
| 14 | Reasoning tree | The typed statements shown as the chain they form. | A statement rests on the nearest lower-layer statements that share an evidence id (fact/assumption → calculation → inference → recommendation); limitations attach to the deepest statement they share evidence with. No shared evidence, no link. | `core/web/src/workbench/Reasoning.tsx` |
| 15 | Model studio | Bounded comparison of a baseline and two models on an uploaded table. | 100–3 000 rows; dummy, random forest (64 trees, depth 8) and logistic or ridge regression; random, group or time split (seed 47) with 3-fold CV; selection on CV only; holdout metrics (macro F1, balanced accuracy, calibration error, or MAE/RMSE/R²). Only the model card is stored. | `analysis/ml.py` |
| 16 | Optional model planner | A model may propose a plan in place of the local planner. | System prompt treats the user text as data; temperature 0; JSON only; strict key and enum validation; anything else falls back to the local planner and the screen says so. | `analysis/llm.py`, `chart_studio.py` `llm_plan` |
| 17 | Evidence | Every result can be checked. | Executed SQL and parameters, dataset SHA-256, output SHA-256 over canonical JSON, recipe version, build fingerprint (SHA-256 over source and lock files). | `worker.py`, `analysis/fingerprint.py` |
| 18 | Code export | The current analysis or chart as a runnable project. | `README.md`, `analysis.py` (only dependency `duckdb`), `analysis.sql`, `charts.py` (SVG, no dependencies), `expected.json`, figures, filtered rows as Parquet (zstd, fixed order, ≤ 6 MiB). Chart overlays (interval, trend, band, moving average) are recomputed by the script. `expected.json` comes from running the generated script; it must match the workspace before the bundle is returned. Zip entries are sorted and timestamped 1980-01-01, so the same scope gives the same bytes. | `analysis/code_export.py` |
| 19 | Access and audit | Who may run what, and a record of it. | OIDC authorization code with PKCE; HttpOnly cookie whose SHA-256 is stored server-side; CSRF header compared in constant time; roles `analyst` or `ops`; every dataset, run, query, experiment and decision checked against the caller's subject; at most 1 running job per user and 3 in total (also across processes via advisory locks); audit record per action. CSV cells starting with `= + - @` are neutralised. | `core/src/workbench.ts`, `core/src/session.ts` |
| 20 | Interface | One React application, built with esbuild. | Turkish and English strings side by side (`t(tr, en)`); design tokens on a 4 px grid, type scale 12–32 px, 44 px targets; one original glyph family; measured with `tools/design/audit.js` and `layout_lint.js`. | `core/web/src/workbench/` |

### Data definitions

- **Gross sales** are invoice-line sales after excluding cancellations, returns and non-positive prices, rounded to
  pence per line. They are not net revenue, margin or profit. Postage and service lines are kept and disclosed.
- **UCI Online Retail**: 541 909 raw lines → 530 104 eligible lines, 19 960 invoices, 3 922 products, 38 countries,
  **£10 666 684.54**. 11 805 lines excluded (9 288 cancellations); 5 268 duplicate lines kept.
- **UCI Online Retail II** (optional): two sheets; the overlapping 2010-12-01..09 rows are verified to be identical
  and kept once. 1 019 654 eligible lines, 40 077 invoices, **£20 533 741.90**.
- **Retail sample**: 180 synthetic invoices (seed 47) with an independent `Decimal` oracle, £21 405.00.
- Boundary months can be partial; charts flag them and keep them out of trends, bands and averages.

---

## Reproduce it

### Requirements

| | Version | Notes |
|---|---|---|
| Python | 3.12 | packages pinned in `constraints.txt` and `analysis/requirements.txt` (DuckDB 1.5.6, pandas 3.0.6, NumPy 2.5.4, NetworkX 3.7, scikit-learn 1.9.1) |
| Node.js | 22 or newer | tested with 24 |
| PostgreSQL | 16 | the launcher uses the Homebrew build at `/opt/homebrew/opt/postgresql@16`; override with `CONTEXT_PG_BIN` |
| Disk | about 1 GB | virtual environment, `node_modules`, prepared datasets |

Docker is needed only for the TypeScript integration tests.

### One command

```bash
./deploy/phase1/start.sh
```

Then open `http://127.0.0.1:8123/app/` and sign in with the local fixture account `selman` (or `alper`), password
`analiz-demo`. These accounts exist only in the local development identity provider.

### What the launcher does, step by step

If you are not on macOS or want to run the steps yourself:

```bash
# 1. PostgreSQL 16 on 127.0.0.1:5549, data under analysis/.local/postgres
printf '%s\n' phase1-local-only > analysis/.local/postgres-password && chmod 600 analysis/.local/postgres-password
initdb -D analysis/.local/postgres --username=postgres --auth-host=scram-sha-256 --auth-local=scram-sha-256 \
  --pwfile=analysis/.local/postgres-password --encoding=UTF8 --locale=C
pg_ctl -D analysis/.local/postgres -o '-h 127.0.0.1 -p 5549 -k /tmp -c timezone=UTC' start
PGPASSWORD=phase1-local-only createdb -h 127.0.0.1 -p 5549 -U postgres contextlayer_phase1

# 2. Python environment
python3.12 -m venv .venv
.venv/bin/pip install -c constraints.txt -e '.[dev]'
.venv/bin/pip install -r analysis/requirements.txt

# 3. Data: download, clean, store (writes analysis/.local/{demo,uci}.duckdb and .json)
curl --fail -L 'https://archive.ics.uci.edu/static/public/352/online+retail.zip' -o /tmp/online-retail.zip
.venv/bin/python -m analysis.prepare

# 4. Interface and core service
npm --prefix core ci --ignore-scripts
npm --prefix core run build

# 5. Start: local identity provider on 8188, migrations, core on 8123
node deploy/phase1/start.mjs
```

Check the preparation before anything else: `analysis/.local/uci.json` must report `rows` 530104, `orders` 19960
and the gross total above. The analysis tests assert the same numbers.

Optional second season:

```bash
curl --fail -L 'https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip' -o /tmp/online-retail-ii.zip
.venv/bin/python -m analysis.prepare --online-retail-ii /tmp/online-retail-ii.zip
```

### Run the worker without the interface

The worker is a plain JSON program, so every stage above can be called directly:

```bash
echo '{"action":"chart","dataset":"uci","prompt":"gross sales by country except United Kingdom","locale":"en"}' \
  | .venv/bin/python -m analysis.worker | python3 -m json.tool | head -40

echo '{"action":"forecast","dataset":"uci"}' | .venv/bin/python -m analysis.worker | python3 -m json.tool | head -40
```

### Use the exported code

```bash
unzip context-layer-uci-analysis.zip -d analysis-export && cd analysis-export
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python analysis.py --check          # recomputes every value and compares it with expected.json
.venv/bin/python analysis.py --country France --start 2011-01-01 --out out
```

---

## Optional Llama planner

Without a model the local planner handles every request. With a model configured and "Plan with Llama" ticked, the
model proposes the plan instead; the plan is validated exactly like the local one and the screen names which
planner was used.

Two providers are supported. A self-hosted OpenAI-compatible server takes precedence over Hugging Face.

**Self-hosted** (llama.cpp, Ollama, vLLM). The model name must contain `llama`.

```bash
# llama.cpp, from a GGUF file
llama-server -m Llama-3.1-8B-Instruct-Q4_K_M.gguf --port 8080
.venv/bin/python -m analysis.llm_setup --endpoint http://127.0.0.1:8080/v1 --model llama-3.1-8b-instruct

# Ollama
ollama pull llama3.1:8b
.venv/bin/python -m analysis.llm_setup --endpoint http://127.0.0.1:11434/v1 --model llama3.1:8b

# vLLM, from a local Hugging Face-format folder (for example a Google Drive copy mounted in Colab)
vllm serve /content/drive/MyDrive/llama/llama31_8b_instruct --served-model-name llama-3.1-8b-instruct --port 8000
.venv/bin/python -m analysis.llm_setup --endpoint http://<host>:8000/v1 --model llama-3.1-8b-instruct
```

`llm_setup` sends one two-token request, reports whether the server answered and saves
`analysis/.local/llama-endpoint.json` with mode 0600 (ignored by Git). The same settings can be given as
`LLAMA_BASE_URL`, `LLAMA_MODEL` and `LLAMA_API_KEY`. An 8B model needs roughly 6 GB of memory in 4-bit form and
16 GB in 16-bit form.

**Hugging Face router.** `.venv/bin/python -m analysis.llm_setup` asks for a token without echoing it, checks the
account and one completion, and saves `analysis/.local/hf-provider.json` (mode 0600). `HF_TOKEN` and `HF_MODEL`
work as well. HTTP 402 from the router means the account has no Inference Provider credits.

**Measuring it.** Once `llm_setup` reports the provider as ready:

```bash
.venv/bin/python -m analysis.llm_eval --providers local,hf --out docs/evidence/verification/llm-eval-live.json
```

The evaluation scores intent plans, decision citations, narrative validation and 24 Chart Studio requests
(Turkish and English, including exclusions and refinements). The live provider is probed once; if it cannot answer,
its row is reported as blocked and no accuracy is computed.

---

## Tests and measurements

```bash
.venv/bin/python -m pytest analysis/tests -q        # analytics: planners, statistics, forecast, export, security cases
.venv/bin/python -m pytest -q                       # platform: snapshots, generator, connectors, design system
npm --prefix core run typecheck
npm --prefix core test                              # core service; starts a disposable postgres:16 container
```

The analytics tests check statistics against independent SciPy and NumPy computations, run exported bundles end to
end with `--check`, feed adversarial model output (SQL, unknown keys, invented countries, prose) to every validator,
and run the planner on Turkish and English requests. The core tests cover sign-in, CSRF, owner isolation, exports,
chart and profile routes.

Worker latency, measured as a full subprocess per request (interpreter start, imports, DuckDB, JSON) on the UCI data,
one thread, seven samples each. Not a service-level figure.
[Receipt](docs/evidence/verification/phase12-aw16-performance.json).

| Request | p50 |
|---|---:|
| Python file export | 104 ms |
| Chart, monthly or two-country comparison | about 350 ms |
| Code bundle, France scope | 404 ms |
| Chart with 95 % intervals or OLS trend | about 610 ms |
| Overview run (KPIs, trend, rankings, network) | 703 ms |
| Code bundle, all 530 104 rows | 742 ms |

The interface is measured in the browser with `tools/design/audit.js` (target size, text and icon contrast, 4 px
spacing, type scale, alignment, Hick–Hyman command count) and `tools/design/layout_lint.js` (overflow, clipping,
icon alignment, narrow controls, horizontal scroll) on every screen and dialog, at 1440, 1024, 768 and 390 px, in
both appearances. In the last pass, 160 measurements across 19 screens and dialogs scored 100 on every rule, with no
lint findings
([receipt](docs/evidence/verification/phase12-aw16-design-sweep.json)). Formulas, the defects found on the way and
their limits are in the [design scorecard](docs/phases/DESIGN_SCORECARD.md). These are DOM heuristics, not a user
study.

---

## Limits

- The metrics are gross sales from invoice lines. There is no cost, margin, causal inference or market data.
- The forecast is one week ahead and is reported against naive even when it loses.
- The decision checklist is a traceability score, not a probability of success.
- Live accuracy of a Llama planner has not been measured: the Hugging Face account used here returned HTTP 402, and
  no self-hosted server was reachable from this machine. The self-hosted path is tested against a stand-in server.
- There has been no task-based user study.
- Native date and month fields take their format from the operating system's language, so the English screenshots
  show `gg.aa.yyyy` and Turkish month names.

---

## Sources

- Platform: [AlperCamli/DataAnalyticsTool](https://github.com/AlperCamli/DataAnalyticsTool).
- Retrieval, safety and export components adapted from [mesely/adviSU](https://github.com/mesely/adviSU); signed
  network methods from [mesely/PoliEcoTRNetSci](https://github.com/mesely/PoliEcoTRNetSci); train-only preprocessing
  from [Influencer stacking/SMOTE/RF](https://github.com/mesely/Influencer-Category-and-Like-Prediction-Stacking-SMOTE-RF).
  Pinned commits and hashes: [source ledger](docs/phases/REUSE_LEDGER.md).
- Data: UCI Online Retail, Daqing Chen, [10.24432/C5BW33](https://doi.org/10.24432/C5BW33); UCI Online Retail II,
  [10.24432/C5CG6D](https://doi.org/10.24432/C5CG6D); both CC BY 4.0, downloaded at setup, not committed.
- Illustrations, portraits, mascot poses and glyphs: generated with Gemini for this project
  ([provenance](core/web/src/workbench/assets/PROVENANCE.md)).
- Further reading: [AW-16 specification](specs/analyst-workspace-phase12.md), [test walkthrough](docs/phases/TEST_GUIDE.md),
  [architecture](docs/PLATFORM_OVERVIEW.md), [core service](core/README.md), [specifications](specs/spec-index.md),
  [security](SECURITY.md), [handoff](progress.md).
