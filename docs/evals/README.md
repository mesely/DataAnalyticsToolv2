# Evaluation methodology (Context Layer v3, AW-23 – AW-25)

Every claim about quality, routing or speed in the v3 report rests on the receipts in `results/`, rendered to
[RESULTS.md](RESULTS.md) by `python -m analysis.evals.report`. This page says how they were produced and how to
reproduce them.

## Data: who wrote the cases, and how they were frozen

| Set | Cases | Author saw | Splits (dev / val / test) |
|---|---:|---|---|
| retrieval | 260 questions (55 % TR, 35 % EN, 10 % mixed; 11 categories incl. 20 unanswerable, 16 injection-flavoured) with relevant cards, a primary card and required facts | the knowledge corpus only | 106 / 53 / 101 |
| studio | 320 requests (chart vs decision; typos, fragments, chart-word questions) | the product contract only | 128 / 63 / 129 |
| intent | 240 questions over 9 intents | the product contract only | 97 / 46 / 97 |
| chart | 260 requests → expected ChartSpec fields (92 refine a base spec) | the product contract only | 104 / 52 / 104 |
| multiturn | 45 conversations, 218 turns, cumulative expected state | the product contract only | 18 / 9 / 18 |

The authors were separate agent instances that never opened the planner, router or retriever code (the contract
they received is quoted in the commit that sealed the splits). They are the same model family as the engineer,
so shared blind spots are possible; three product rules they did not know are listed below. `analysis/evals/split.py`
splits each set once, stratified by category, seed 20261022, and records every file's SHA-256 in
`analysis/evals/data/MANIFEST.json`; the splits were committed **before** any tuning (`2a9cea7`, `7248531`), and
`python -m analysis.evals.split --verify` fails if a file changes.

**Use of the splits.** dev: error analysis, rule changes, training the learned routers. val: choosing between
variants (regularisation C, legacy data or not, retriever, thresholds). test: reported once per method, never
inspected case by case. The 18 Oct held-out sets (llm-eval v3) are older and were used only as extra training data
for the intent router, never as evidence.

## Metrics

- Retrieval (answerable questions): Recall@k over all relevant cards, Hit@k, MRR of the primary card, nDCG@5
  (primary gain 2, other relevant 1), Precision@5; abstention on unanswerable questions (top score at or below a
  threshold chosen on dev so that at most 2 % of answerable questions abstain).
- Answers: correct = every required fact appears verbatim in the answer; faithful = every answer sentence is a
  sentence of a cited card and every number appears in a cited card; unsupported-claim rate = 1 − faithful.
- Routing: accuracy with 95 % Wilson intervals; model vs local compared on the same cases with an exact McNemar
  test on the discordant pairs.
- Chart planning: every field in the case's `expect` matches the planned spec (country lists as sets, transform
  fields compared with defaults filled in); multi-turn: per turn, and per conversation when every turn is right.
- Latency: per request, spawning `python -m analysis.worker` exactly as the server does (interpreter, imports,
  DuckDB, JSON), p50/p95/p99 over n runs after one warm-up; `--inproc` measures the handler alone.

## Decision rules (written before the test runs)

- Routing (per task): a model replaces the local method only when it beats it by ≥ 3 points **and** McNemar
  p < 0.05; "local first, model when unsure" when the model recovers ≥ 60 % of the local misses (n ≥ 3); otherwise
  local. A model blocked by a quota on any case is not compared. The routing table is generated, not edited
  (`python -m analysis.evals.routing_table`).
- Retrieval: the simplest configuration on the Pareto front of (Recall@5, MRR, latency, dependencies) on val; a
  heavier stage must buy a material gain (≥ 2 points of MRR or Recall@5) to be shipped.

## Reproduce

```
make ws-setup            # once
make ws-test             # unit/golden/contract tests, reference-data rebuild check, split integrity, typecheck
make ws-eval             # local methods on val and test (offline, deterministic)
make ws-eval-models      # hosted models (Groq key in analysis/.local; ~1,000 requests per model per day)
make ws-benchmark        # retrieval (downloads ~2.3 GB of ONNX models once) and latency
python -m analysis.evals.report
```

Model answers are cached per case under `results/cache/`, so `ws-eval-models` resumes after a quota stop and the
reported accuracy is always over the cases actually answered (BLOCKED rows are listed).

## Known disagreements between the authors and the product

The independent authors' labels follow the contract they were given, which did not state three product rules; the
affected cases count as failures (labels are never edited after sealing):

1. Converting at today's exchange rate together with constant prices: refused by design (AW-20), the case expects
   both.
2. A trend line or a control band on a country split: dropped by design (one series only, AW-16), the case expects
   it to persist.
3. A statistic carried into a comparison of several countries: same rule as 2.
