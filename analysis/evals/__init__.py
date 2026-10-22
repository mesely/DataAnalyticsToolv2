"""Evaluation harness (v3, AW-23): frozen splits, retrieval and routing benchmarks, multi-turn and answer quality.

    python -m analysis.evals.split        # (once) split the authored sets into dev / val / test and seal test
    python -m analysis.evals.retrieval    # retrieval benchmark: lexical, dense, hybrid, fusion, reranking
    python -m analysis.evals.routing      # studio routing, question intents, chart plans, multi-turn
    python -m analysis.evals.answers      # grounded answers: correctness, faithfulness, unsupported claims

Rules: tune on dev, choose on val, report test. The test split's SHA-256 is recorded in
analysis/evals/data/MANIFEST.json when it is created; `split --verify` fails if a test file changes.
"""
