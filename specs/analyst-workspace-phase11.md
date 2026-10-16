# AW-14: Measured quality loop — interval validity, typed analyst narrative, broader ingestion, probabilistic ML metrics

2026-10-16 · User-authorized additive workbench amendment. Written before the code; data-dependent results are recorded afterwards in `docs/phases/PHASE_11_REPORT.md`.

## Forecast uncertainty (weekly-gross-v3 within the same /forecast contract)
The residual band keeps its empirical construction but gains a development-only validity check. For the selected method, two band scalings are registered: `absolute` (quantile of |error| in pence) and `relative` (quantile of |error| / |forecast|, radius = quantile × point forecast). The quantile is the finite-sample split-conformal index ⌈(n+1)·level⌉, truncated to the largest residual when it exceeds n. For every development origin after the first eight development residuals, the radius is the quantile of the *earlier* development residuals only (rolling, one-step), and coverage is the share of development origins whose actual lies inside the band. The scaling whose development rolling coverages at 80 % and 90 % are closest to nominal is selected; ties resolve to `absolute`. The final window never influences the scaling choice; its coverage is reported descriptively, as today. `calibrated` stays `false`. New diagnostics: `band_undercovers_development` when the 90 % band covers fewer than 80 % of evaluated development origins. UI text must state the final-window size dynamically (no "final four").

## Typed analyst narrative (decision-narrative-v1, inside /decisions)
Every decision brief carries a `narrative`: an ordered list of typed statements `fact | calculation | inference | assumption | recommendation | limitation`, each with `text` and `evidence` (existing reference IDs). A deterministic local renderer always produces it; no model is needed. When the user opts into Llama, the model receives an `analysis_context` XML evidence packet (task, dataset, filters, definitions, evidence with IDs/paths/units, assumptions, limitations, allowed and forbidden claims, output contract repeated last; ≤ 16 KB; no product/country/customer labels or raw rows) and must return the same typed-statement JSON. Validation is programmatic: unknown statement types, unknown evidence IDs, fact/calculation/recommendation statements without a citation, recommendations naming a non-candidate, and any number in a statement that does not match a cited evidence value (pence, GBP, count or percent rendering) reject the reply. Policy: reject → one repair attempt with the rejection reason → local narrative with `provider.status = rejected`. Model text never replaces local numbers; the local narrative is always present alongside. Evaluation cases for this contract join `analysis/llm_eval` (ideal, adversarial, local); the live row stays BLOCKED until HTTP 402 clears.

## Ingestion (csv-preparation-v2, same /prepare and /import routes)
Explicit, previewed, reversible options extend `trim`/`drop_duplicates`: `decimal_comma` (interpret `1.234,56` and `12,5` as numbers; applied to quantity/price only after mapping), `date_format` (`iso` default, `dmy_slash`, `mdy_slash`, `dmy_dot`; the user chooses, no guessing). The profile reports per-column `decimal_comma_candidates` and date-pattern counts (`iso`, `slash_ambiguous`, `dot`) so the user sees what each option would do before previewing. Parquet files are accepted through `parquet_base64` (≤ 2 MB encoded), read by DuckDB `read_parquet` with all columns cast to text, same row/column bounds, same receipt (hash of the bytes); no new dependency. Browser decoding falls back to Windows-1252 only when UTF-8 decoding fails, and says so. Identifiers and money are never mutated silently; every transform appears in the receipt recipe.

## Probabilistic ML metrics (ml-experiment-v1 card, additive field)
For classification, the holdout and baseline sections gain `probabilistic`: log loss, multiclass Brier score, expected calibration error (10 equal-width bins on the top probability), and average precision for binary targets. They are reported for the selected and baseline models only after selection; they never influence selection. Cards without `predict_proba` report `null`.

## Acceptance
Meaningful pytest for each contract (oracle arithmetic, final-window isolation of the scaling choice, validator rejections, Parquet/decimal/date round trips, probability metrics on the Wine fixture); core web build/tsc; browser desktop/mobile/light/dark checks of Decision Studio including the narrative and dynamic final-window text; evidence logs under `docs/evidence/verification/phase11-*`. Live model accuracy stays BLOCKED/null. Production RLS, retention, hard isolation, user pilot remain OPEN.

## AW-14 correctness amendment — 2026-10-16 continuation
Gross forecasts use the nonnegative sales domain consistently: every registered candidate is clipped at zero before development selection, final evaluation, slice evaluation and next-point construction. Relative scaling remains unavailable when a development prediction is zero; a later zero prediction has zero relative radius and is disclosed as a collapsed band. No final outcome changes method or scaling selection. Each level reports mean displayed width (GBP, lower bound clipped at zero) for rolling development and the final window, alongside coverage and sample size. Final 90% coverage below 80% raises a diagnostic; this is descriptive, never a tuning signal.

Narrative numeric checks preserve signed magnitude, decimal scale and explicit units. English and Turkish number separators are supported by exact syntax; ambiguous unmarked numbers are rejected unless their plausible interpretations all match cited evidence. Every integer is checked, including zero; local templates cite final-origin count and business-validation evidence explicitly. Currency cannot be supported by counts, percentages cannot be supported by money. Facts and calculations about unavailable evidence reject; negative disclosures belong in limitations. Country filter values never leave the local application: outbound context retains dates plus a boolean country-filter marker only.

Parquet source limit means 2 MB **decoded bytes** (base64 transport is larger). File-controlled identifiers are quoted as SQL identifiers, never SQL expressions. DuckDB is restricted to the single temporary upload, with extension installation/loading disabled, memory/thread limits and a decoded row-data budget. Field and aggregate text-byte limits are checked inside DuckDB before values are materialized in Python. Nested/binary types are rejected explicitly; this bounded retail importer does not flatten them.

Browser CSV decoding exposes UTF-8, Windows-1252 and Windows-1254 with a local text preview. A failed strict UTF-8 decode suggests Windows-1252 but requires explicit confirmation before sending the decoded table for profiling/import. Changing encoding invalidates mapping/preview/receipt. The normalized UTF-8 text remains the server source hash; original CSV byte encoding is a local decoding decision, not an asserted byte-for-byte upload receipt. Async reads from superseded file selections cannot overwrite the active selection.

## AW-14 binding amendment — measure and period binding for narrative numbers (2026-10-16, Opus continuation)
Problem: the narrative validator accepted any number equal to *some* cited evidence value, so a reply citing both
`forecast_mae` and `baseline_mae` could swap them ("naive MAE is £47,206.66"), and any packet date (for example a
final-window target) was accepted next to a measurement it does not belong to.

Contract (additive; decision-narrative-v1 statement schema unchanged, local narrative text unchanged):
1. Every evidence item in the packet carries a `measure` (plain-language name), a fixed list of **distinctive** EN/TR
   descriptor terms, and a `period` (`start..end`, ISO) or none. Periods: sales measures (gross, orders, leading-country
   share, basket support) = observed scope; quality counts and business validation = none (whole source dataset /
   checklist); complete weeks = first..last complete week; final-window errors and origin count = first..last final
   target week; next-week projection = that week; scenario values = the last complete week.
2. **Measure binding.** For each numeric token, the validator takes up to four words immediately before it in the same
   clause (clauses end at `;`, `:` or sentence end) and after the previous number. If those words contain a descriptor term of some evidence item and
   none of the descriptor terms of the item(s) whose value the number matched, the statement is rejected
   ("measure binding"). Descriptors written after a number are not bound, and an evidence id without registered
   descriptors is not bound (skipped, never guessed) — documented limitations.
3. **Period binding.** Every ISO date in a statement must lie within the period of at least one cited evidence item;
   a date with no period-bearing citation is rejected ("period binding").
4. The `<analysis_context>` evidence items expose `measure` and `period` attributes; the instructions ask the model to
   name the measure immediately before each number.
5. Labels: this is a mechanical lexical check, **not semantic entailment**. It closes value swaps and wrong-measure /
   wrong-period attachments that use the packet's own vocabulary; paraphrases outside the term lists are not detected.
   Live model accuracy stays BLOCKED (HTTP 402) and null.

Period slices (same amendment, additive `forecast.period_slices`): error and 90% band behaviour by calendar month of
the target week, per phase. Development bands are rolling from earlier residuals only; final bands use the fixed radius.
Computed after selection; never used for it. Diagnostic `final_month_worse_than_naive` when a final month with ≥ 2 weeks
has selected MAE ≥ naive (non-naive selection only). No tuning on the existing final window.

Acceptance: the local EN and TR narratives (including negative scenarios) validate unchanged; swapped-MAE,
wrong-measure and wrong-period counter-examples with valid IDs are rejected in unit tests and in two new
`llm_eval` narrate cases; existing narrative, decision, forecast and LLM-eval tests stay green.
