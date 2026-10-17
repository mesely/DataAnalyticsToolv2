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

## AW-16 amendment (2026-10-17): exclusions, statement evidence keys, exported chart statistics

Additive, same version (ChartSpec stays `version: 1`, `chart-studio-v1`, `context-layer-analysis-expected/v1`).
Same honesty rules: every number is computed locally; a model may only plan.

### A1. `exclude_countries` (ChartSpec, optional additive key)

- `exclude_countries: [≤ 5 catalog names]`, default `[]`. A spec without the key stays valid: `validate_spec` fills
  the default (the response `spec` now always carries the key). Unknown names, non-lists and more than 5 entries are
  rejected like `countries`; duplicates are dropped.
- A country is never in both lists. **The later request wins**, with a warning: in the local planner an exclusion
  removes the country from `countries` and naming a country re-includes it (removes it from `exclude_countries`).
  `validate_spec(..., previous=base)` applies the same rule to a raw spec (the LLM plan is validated against its base);
  without a previous spec the exclusion wins (what `IN (...) AND NOT IN (...)` would compute anyway).
- Engine: `country NOT IN (?, …)` with bound parameters, in the chart query and in the scope totals of the top-k
  share. `split_by_country` series are `countries` only, so an excluded country never appears as a series. An app
  country filter that the chart excludes yields no data and the warning "excluded by the chart".
- Title/subtitle: when no `countries` are set the subtitle scope reads "Tüm ülkeler, Birleşik Krallık hariç" /
  "All countries except United Kingdom" (country labels localized as elsewhere in the subtitle; lists joined with
  "ve"/"and"). The exported figure title appends the same scope text when the spec has countries or exclusions.
  `scope.exclude_countries` is added to the response. Statement texts are unchanged; their numbers follow the scope.
- Local planner: an exclusion phrase attached to a country, or to a list of countries joined by `,`/`ve`/`and`/`ile`/
  `or`, is read before any other rule and consumed (so it is never re-read as a statistic removal or as a by-country
  axis). Turkish phrases follow the country, English ones precede it.
  - Exclusion words (always exclude): TR `hariç`, `hariç tut…`, `haricinde`, `dışında`, `dışındaki (ülkeler)`,
    `olmadan`; EN `except (for)`, `excluding`, `exclude`, `other than`, `without`, `but not`, `apart from`, `excluded`.
  - Removal words (context): TR `çıkar`, `kaldır`, `sil`, `gizle` (optionally after `karşılaştırmadan`/`grafikten`/
    `listeden`), EN `remove`, `drop`, `hide`, `delete`, `leave out`, `take out`. If the country is in `countries` it is
    dropped there (the existing "drop from the comparison" behaviour); otherwise it is added to `exclude_countries`.
  - Removal words not attached to a country keep their meaning ("güven aralığını kaldır" → statistic `none`).
  - "tüm ülkeler" / "all countries" clears both lists (then exclusions in the same request apply).
- LLM planner: the system prompt lists the key and its rules; a plan must contain every key except the additive one
  (the 12-key shape is still accepted); a plan with an unknown excluded country is `invalid_plan`.

### A2. Statement evidence keys

Every statement gains `evidence: [string, …]` (non-empty; `type` and `text` unchanged) naming the computed values it
rests on, so a UI can link statements that share them: `values:<series>` (`all` or a country), `trend`, `ci`, `band`,
`ma`, `partial`, `share`, `metric`.

| Statement | evidence |
|---|---|
| peak/low fact, first→last change | `["values:<s>"]` |
| no rows in scope; missing weekdays | `["values:<s>"…]` / `["values:all"]` |
| trend calculation · trend limitation | `["values:all","trend"]` · `["trend"]` |
| interval calculation; "fewer than 2 orders" fact · interval limitation | `["values:<s>"…,"ci"]` (`values:all` unless split) · `["ci"]` |
| band calculation, outside-band inference, all-inside fact | `["values:all","band"]` |
| moving-average calculation | `["values:<s>","ma"]` |
| partial-period limitation | `["values:<s>" for each affected series…, "partial"]` |
| top-k share | `["values:all","share"]` |
| gross ≠ net, distinct-order limitations | `["metric"]` |

### A3. The exported chart carries its statistic

With a chart, the bundle reproduces the chart exactly as Chart Studio shows it, statistic included.

- **Series.** `analysis.sql` (section 3) sets `chart_start`/`chart_end` = overlap of the dataset range, the
  `start_date`/`end_date` variables and the spec dates (`greatest`/`least`); section 4 creates the `chart_buckets`
  view. On a month/week axis a `generate_series` spine lists every period × series, so a period without rows is a zero
  (average order value: missing), and `partial` is set exactly as in Chart Studio. Exclusions and countries are
  written into the view as literals from the validated spec. `analysis.py` runs the same SQL text. The `chart` rows
  (`x, series, partial, pence, orders, units`; categorical axes without `partial`) equal Chart Studio's `data`.
- **Statistic results** in `expected.json` (integers only; `--check` compares exactly):
  - `chart_ci95` (per bucket): `n, mean_pence, sd_pence, lower_pence, upper_pence`. Mean and sd come from exact
    integer sums (`SUM(order_pence::HUGEINT * order_pence)`), so they do not depend on floating-point aggregation
    order; bounds = mean ± t(0.5 + `CI_LEVEL`/2, n − 1)·sd/√n with the t quantile from `stats.py`. The SQL returns
    n, mean and sd (DuckDB has no t quantile).
  - `chart_trend`: closed-form OLS on complete periods by period index → `index_origin, n, slope_x100,
    intercept_x100, r2_x1e6, p_value_x1e6` (p two-sided, t with n − 2 df via `stats.py`). SQL:
    `regr_count/regr_slope/regr_intercept/regr_r2` (verified in DuckDB 1.5.6; p-value in `analysis.py`).
  - `chart_control_band`: mean ± `CONTROL_SIGMAS`(2)·sample sd of complete periods → `n, mean_x100, sd_x100,
    lower_x100, upper_x100, outside`. SQL: `AVG`/`STDDEV_SAMP`.
  - `chart_moving_average`: trailing window of complete periods per series → `x, series, value_x100`. SQL:
    `AVG(value) OVER (PARTITION BY series ORDER BY period_index ROWS BETWEEN w−1 PRECEDING AND CURRENT ROW)`; the
    `WHERE NOT partial` filter runs before the window, so partial periods never enter an average, and
    `QUALIFY COUNT(value) … = w AND period_index − MIN(period_index) … = w−1` keeps only full windows of consecutive
    periods with a value.
  - Scales: `_x100` = pence for GBP metrics, hundredths for counts; `_x1e6` = millionths. Rounding: Python `round()`.
- **`stats.py`** (shipped when the statistic is `ci95` or `trend`): dependency-free Student-t CDF, two-sided p-value
  and quantile via the regularized incomplete beta function (continued fraction, modified Lentz as Numerical Recipes
  `betacf`, evaluated on the fast-converging side with 1 − x formed exactly); quantile by bracketing, bisection and
  Newton steps. Agrees with `scipy.special.stdtr/stdtrit/betainc` to 1e-9 relative over df 1…50 000.
- **Figure.** `charts.py` draws the overlay on `figures/chart.svg`: interval whiskers with caps (line and bar
  layouts), a dashed trend/moving-average line, a shaded control band with a dashed mean; missing values are gaps;
  values below zero are cut at the axis (data unchanged); a legend names the statistic.
- **README** chart section: what the statistic is, its assumption, where it lives (function, query), how to change it
  (`CI_LEVEL`, `CONTROL_SIGMAS`, window, partial periods) and its exported values.
- Generated comments and docstrings follow the locale; full-line comments are wrapped at 110 columns.

### Results (2026-10-17)

- Chart Studio + code-export tests 95 → 165 (+70); the whole analysis suite passes (474 at the time of writing).
  Chart Studio: 20 TR/EN exclusion-vs-removal planner cases, validation
  conflicts, engine vs pandas with exclusions (series, top-k share, split series, excluded app filter), LLM plans with
  `exclude_countries` accepted / unknown country rejected / legacy shape accepted / conflict resolved against base,
  evidence on every statement for 12 chart shapes plus the per-kind key mapping.
- Export: six uci bundles (ci95 monthly and by country with UK excluded, trend with UK excluded and a partial last
  month, trend on weekly AOV with empty weeks, control band under a Germany filter (TR), split weekly moving average)
  pass `analysis.py --check` in a temp dir; their `chart` rows equal Chart Studio's `data`; overlays equal Chart
  Studio's within rounding to pence (R² and p within 1e-6 of Chart Studio's own estimator); `analysis.sql` reproduces
  the same values with DuckDB aggregates. Moving-average points may differ from Chart Studio by one penny on exact
  half-penny ties (Chart Studio rounds with `round(x, 2)`, the export rounds whole pence); this is the only tolerance
  beyond half a penny.
- `output_sha256` of Chart Studio responses changes for every spec, because the hashed spec now contains the
  additive key; computed values are unchanged.
- Review fixes after the amendment landed (478 analysis tests):
  - "add the UK back" on an all-countries chart now lifts the exclusion; before, it narrowed the chart to the UK.
    It is covered by planner cases.
  - Chart SQL embedded in the generated `analysis.py` is escaped for a triple-quoted literal: backslashes are
    doubled and runs of three double quotes are escaped. Without this, an uploaded country name containing `"""`
    could close the literal, and one containing `\x41` would silently change the SQL text.
  - The README chart line escapes Markdown, and backticks in the JSON spec are written as ```.
  - A test exports a bundle that excludes a country named with quotes, backslashes, a newline and a code fence. It
    parses the script with warnings as errors, checks that the script imports nothing new, that its SQL equals the
    SQL file and that the README fences stay balanced, then runs `--check`.

## AW-16 continuation (2026-10-17): reasoning tree, focused dialogs, mascot poses

- **Reasoning tree** (`Reasoning.tsx`, used by Decision Studio and Chart Studio):
  - Statements are numbered per type: O/V/H/Ç/Ö/S in Turkish, F/A/C/I/R/L in English.
  - Each statement nests under the nearest lower-layer statements that share an evidence id. Limitations nest
    under the deepest step they share evidence with. Without shared evidence there is no link.
  - Five options were scored before choosing this one (`docs/phases/UX_DECISIONS.md`).
- **Focused dialogs:**
  - The SQL laboratory and "change over time" now open in their own modal dialogs instead of expanding inline.
  - Metric definitions moved into the evidence dialog, next to the SQL.
  - The overview keeps one starter question and the assistant keeps two.
  - Every main region and dialog has ≤ 15 commands, so the Hick–Hyman score is 100.
- **Mascot:**
  - Four poses of the Kontekst character, cut out to transparent PNGs: hanging, reading, waving and searching.
  - They are used in the sidebar brand, Chart Studio, the sign-in page (dev IdP `art` option), the signed-out
    screen, the getting-started dialog and empty states.
  - All are decorative (`alt=""`) and served at 2× resolution.
- **Signed-out screen:** Turkish by default, English for an English browser. The server's error code moved under
  "Technical detail".
