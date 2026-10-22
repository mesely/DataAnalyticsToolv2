"""Ranking and classification metrics used by the benchmarks (plain Python, no dependencies)."""
from __future__ import annotations

import math
import statistics


def recall_at(ranked: list[str], relevant: set[str], k: int) -> float:
    return len(set(ranked[:k]) & relevant) / len(relevant) if relevant else float("nan")


def hit_at(ranked: list[str], relevant: set[str], k: int) -> float:
    return 1.0 if set(ranked[:k]) & relevant else 0.0


def precision_at(ranked: list[str], relevant: set[str], k: int) -> float:
    return len(set(ranked[:k]) & relevant) / k


def reciprocal_rank(ranked: list[str], target: str) -> float:
    return 1.0 / (ranked.index(target) + 1) if target in ranked else 0.0


def ndcg_at(ranked: list[str], gains: dict[str, float], k: int) -> float:
    dcg = sum(gains.get(d, 0.0) / math.log2(i + 2) for i, d in enumerate(ranked[:k]))
    ideal = sorted(gains.values(), reverse=True)[:k]
    idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg else float("nan")


def mean(values) -> float:
    vals = [v for v in values if not (isinstance(v, float) and math.isnan(v))]
    return sum(vals) / len(vals) if vals else float("nan")


def percentile(values, p: float) -> float:
    vals = sorted(values)
    if not vals:
        return float("nan")
    k = (len(vals) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95 % Wilson score interval of a proportion."""
    if n == 0:
        return float("nan"), float("nan")
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def mcnemar(a_only: int, b_only: int) -> float:
    """Exact two-sided McNemar p-value for paired correct/incorrect outcomes (binomial on the discordant pairs)."""
    n = a_only + b_only
    if n == 0:
        return 1.0
    k = min(a_only, b_only)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def summary_ms(values) -> dict:
    vals = list(values)
    return {"p50": round(percentile(vals, 0.5), 3), "p95": round(percentile(vals, 0.95), 3),
            "p99": round(percentile(vals, 0.99), 3), "mean": round(statistics.fmean(vals), 3) if vals else None}
