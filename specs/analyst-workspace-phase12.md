# AW-16: Developer code export, Chart Studio, analyst avatars

2026-10-17 · User-authorized additive workbench amendment, written before the code. Same honesty rules as AW-14:
numbers are computed locally and never by a model; a model may only *plan*; live model accuracy stays BLOCKED
(HTTP 402) and is never claimed.

## 1. Developer code export (`code_export` worker action, `POST /v1/dashboard/workbench/export/code`)

Purpose: hand a developer the current analysis (dataset + filters, optionally a Chart Studio chart) as readable,
commented, runnable code they can change.

Request: `{dataset, filters, locale: tr|en, format: bundle|python|sql, chart?: ChartSpec}`.
Response: `{format, filename, content_type, base64, bytes, sha256, data_included, files: [{path, bytes, sha256}],
preview: {"README.md"?, "analysis.py"?, "analysis.sql"?}}`.

Bundle (`context-layer-<dataset>-analysis.zip`), deterministic (same input → byte-identical zip: sorted entries,
fixed 1980-01-01 timestamps, no wall-clock time anywhere):

| Path | Content |
|---|---|
| `README.md` | Purpose, quick start, file tree, data dictionary, metric definitions, applied filters, dataset provenance (source, licence, SHA-256), expected results table, embedded figures, "how to change it" recipes, limitations. Language = locale. |
| `analysis.sql` | DuckDB SQL. Parameters at the top via `SET VARIABLE`; one commented query per result (KPIs, monthly trend, top countries, top products, co-purchase pairs; plus the chart query when a chart is exported). Comments state grain and metric semantics. |
| `analysis.py` | Python 3.10+ script, only dependency `duckdb`. Typed, documented functions, one per result; `argparse` (`--data`, `--start`, `--end`, `--country`, `--out`, `--check`); writes CSVs and SVG figures to `--out`; `--check` compares against `expected.json` exactly and exits non-zero on any difference. |
| `charts.py` | Dependency-free SVG chart writer (line, bar) used by the script and to pre-render figures. |
| `expected.json` | Results at export time (integers in pence/counts, no floats that can drift), dataset SHA-256, filters, engine version. |
| `requirements.txt` | `duckdb==<engine version>` |
| `data/transactions.parquet` | Filtered rows; columns `invoice, product_id, product, quantity, unit_price, line_pence, order_date, country` (no customer identifier, same policy as the SQL lab); stable order. Omitted when larger than 6 MB (`data_included: false`; README explains `--data`). |
| `figures/*.svg` | Monthly gross sales, top countries, top products (+ `chart.svg` for an exported chart). |

`format: python|sql` returns the single file. Core may raise the worker output bound for this action only (≤ 12 MB).
Acceptance: the bundle's `analysis.py --check` and `analysis.sql` run against the bundled data reproduce
`expected.json` exactly, for the public, demo and a filtered scope; two exports are byte-identical.

## 2. Chart Studio (`chart` worker action, `POST /v1/dashboard/workbench/chart`)

Free-text chart requests and refinements ("son 6 ay", "Almanya ile Fransa'yı karşılaştır", "ortalama sepet +
%95 güven aralığı", "4 haftalık hareketli ortalama ekle"). A request produces a validated **ChartSpec**; the local
engine computes the data, statistics and commentary.

ChartSpec v1 (strict; unknown keys rejected):
`{version: 1, metric: gross_sales|orders|units|aov, dimension: month|week|weekday|country|product,
chart: line|area|bar, start?: ISO date, end?: ISO date, countries: [≤ 5 catalog names], split_by_country: bool,
top_n: 3..20, statistic: none|ci95|moving_average|trend|control_band, window: 2..12, sort: natural|value_desc|value_asc}`.
Rules: `line|area` and `moving_average|trend|control_band` need a time dimension (month, week); `split_by_country`
needs a time dimension and 2–5 countries; `ci95` is a t-based 95 % interval of a **mean** and is defined for `aov`
(mean of order totals per bucket); requested on a total it becomes `control_band` with a warning, never a fake
interval on an observed total. Dates are clamped to the dataset range with a warning.

Request: `{dataset, filters, locale, prompt (≤ 500 chars), base_spec?: ChartSpec, use_llm: bool}`.
Planner: with `use_llm` and a configured provider, Llama returns a ChartSpec-shaped JSON (schema, base spec and
catalog in the prompt; user text treated as untrusted data); invalid or unavailable → the deterministic local
planner (TR/EN lexicon: metrics, dimensions, chart types, relative/absolute periods, quarters, TR country exonyms,
top-N, statistics, comparison, removal). Refinement = base spec + only the fields the request mentions. A request
that changes nothing returns `planner.status = no_change` with suggestions, never a guess.

Response: `{spec, planner: {source: llama|local, status, changes: [{field, from, to}], note}, title, subtitle, unit,
data: [{x, series, value, lower?, upper?, n?, partial?}], overlays: {moving_average?, trend?: {slope, intercept, r2,
p_value, n}, control?: {mean, sd, lower, upper}}, statements: [{type: fact|calculation|inference|limitation, text}],
sql, params, warnings, output_sha256}`.
Statements are rendered from computed values only (peak/low bucket, first→last change on complete periods, top-k
share, trend slope with R²/p/n, interval width, out-of-band periods) plus limitations (partial periods, gross ≠ net,
interval assumptions, trend is descriptive not a forecast). Partial first/last periods are flagged.
Acceptance: statistics equal independent numpy/scipy computations; planner cases (TR/EN, refinements, rejections,
adversarial LLM output) are tested with an injected model; live LLM path stays BLOCKED.

## 3. Analyst avatars and product mark

Original Gemini (Nano Banana Pro) illustrations, consistent style, recoloured to the product palette (navy, cobalt,
brass, ivory): a core analytics mascot (also the new app mark next to "contextlayer") and business-domain analysts
(retail, banking, automotive, energy, telecom/network, logistics, health) as animals/creatures, plus human
analysts. No letter avatars. Selection persists server-side per subject (`workbench_profiles`, migration 0022;
`GET/PUT /v1/dashboard/workbench/profile`, allowlisted ids); the default is deterministic per subject. No browser
storage. Provenance and hashes in `PROVENANCE.md` / `ASSET_MANIFEST.json`.

## 4. Showcase

README presents the product with real screenshots/GIFs from the running app, the architecture and engineering
choices, and the analytics coverage (descriptive, diagnostic, predictive, prescriptive) with measured evidence and
explicit limits. No unmeasured claim.

## Results (2026-10-17, recorded after implementation)

- **Code export:** bundles for `demo`, full `uci` (3.2 MB zip, all 530,104 rows as Parquet) and filtered scopes run
  `analysis.py --check` green outside the repo (11 checks for a France scope with an exported chart); the SQL file
  reproduces the same KPIs through `read_parquet(getvariable('data_path'))`; repeated exports are byte-identical.
  Worker p50: Python file 104 ms, France bundle 404 ms, full bundle 742 ms
  (`docs/evidence/verification/phase12-aw16-performance.json`).
- **Chart Studio:** 79 tests (planner TR/EN cases, refinements, removals, adversarial model output, statistics against
  independent scipy.stats/numpy). The t quantile and the slope p-value use `scipy.special` (`stdtrit`, `stdtr`) and a
  closed-form OLS instead of importing `scipy.stats` (~1.4 s): interval/trend requests went from p50 1.51 s to 0.61 s
  with identical results. Interval whiskers below zero are cut at the axis in the UI (computed bounds unchanged in the
  data table and footnoted). The Llama path is exercised with an injected model only; live accuracy stays BLOCKED.
- **Portraits:** eight Gemini portraits plus the app mark; the human-analyst portraits were requested but not produced
  in this session. Profile choice persists per subject (`workbench_profiles`, migration 0022).
- **Design gates on the new surfaces:** audit 100 on every metric except Hick–Hyman (98, from the page behind the
  dialog), layout lint clean at 1280 and 390 px in both themes.
