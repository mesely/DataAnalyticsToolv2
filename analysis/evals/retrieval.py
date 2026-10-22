"""Retrieval benchmark (AW-23): which configuration finds the context cards a question needs.

    python -m analysis.evals.retrieval --split dev            # all configurations on the dev split
    python -m analysis.evals.retrieval --split val --out docs/evals/results/retrieval-val.json
    python -m analysis.evals.retrieval --split test --configs lexical,hybrid-rrf-rerank  # report only

Metrics on answerable cases: Hit@1, Recall@k (all relevant cards), MRR of the primary card, nDCG@5 (primary gain 2,
other relevant 1), Precision@5; on unanswerable cases: abstention (top score under the configuration's threshold,
chosen on dev). Latency is measured per query after the index is built; model load time is reported apart.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from analysis import retrieval as R
from analysis.evals import metrics as M

DATA = Path(__file__).resolve().parent / "data"
DENSE_MODELS = {
    "minilm": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "mpnet": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
}
RERANKER = "jinaai/jina-reranker-v2-base-multilingual"


def load(split: str) -> list[dict]:
    return json.loads((DATA / f"retrieval_{split}.json").read_text())["cases"]


def rrf(*rankings: list[str], k: int = 60) -> list[tuple[str, float]]:
    score: dict[str, float] = {}
    for ranking in rankings:
        for i, cid in enumerate(ranking):
            score[cid] = score.get(cid, 0.0) + 1.0 / (k + i + 1)
    return sorted(score.items(), key=lambda kv: (-kv[1], kv[0]))


def weighted(a: list[tuple[str, float]], b: list[tuple[str, float]], alpha: float) -> list[tuple[str, float]]:
    """alpha * minmax(a) + (1 - alpha) * minmax(b)."""
    def norm(xs):
        if not xs:
            return {}
        lo, hi = min(s for _, s in xs), max(s for _, s in xs)
        return {c: (s - lo) / (hi - lo) if hi > lo else 0.0 for c, s in xs}
    na, nb = norm(a), norm(b)
    ids = set(na) | set(nb)
    return sorted(((c, alpha * na.get(c, 0.0) + (1 - alpha) * nb.get(c, 0.0)) for c in ids), key=lambda kv: (-kv[1], kv[0]))


def mmr(ranked: list[tuple[str, float]], sim, lam: float = 0.7, k: int = 5) -> list[tuple[str, float]]:
    """Maximal marginal relevance over the first 20 candidates (sim: card-card similarity)."""
    pool = ranked[:20]
    top = max((s for _, s in pool), default=1.0) or 1.0
    chosen: list[tuple[str, float]] = []
    while pool and len(chosen) < k:
        best = max(pool, key=lambda cs: lam * cs[1] / top - (1 - lam) * max((sim(cs[0], c) for c, _ in chosen), default=0.0))
        chosen.append(best)
        pool.remove(best)
    return chosen + [x for x in ranked if x not in chosen]


class Bench:
    """Builds every configuration lazily so a run pays only for what it measures."""

    def __init__(self):
        self.cards = R.cards()
        self._dense: dict = {}
        self._rr = None
        self.loads: dict = {}

    def dense(self, key: str, granularity: str = "card"):
        k = (key, granularity)
        if k not in self._dense:
            from analysis.evals.dense import Dense

            d = Dense(DENSE_MODELS[key], self.cards, granularity)
            self._dense[k] = d
            self.loads[f"dense-{key}-{granularity}"] = {"load_s": round(d.load_s, 2), "index_s": round(d.index_s, 2)}
        return self._dense[k]

    def reranker(self):
        if self._rr is None:
            from analysis.evals.dense import Reranker

            self._rr = Reranker(RERANKER, self.cards)
            self.loads["reranker"] = {"load_s": round(self._rr.load_s, 2)}
        return self._rr

    def configs(self) -> dict:
        lex = R.Options()
        plain = R.Options(stem=None, title_weight=1.0, use_tags=False, expand=False, fuzzy=0)
        stem = R.Options(title_weight=1.0, use_tags=False, expand=False, fuzzy=0)
        fields = R.Options(use_tags=False, expand=False, fuzzy=0)
        tags = R.Options(expand=False, fuzzy=0)
        expand = R.Options(fuzzy=0)
        lang = R.Options(granularity="language")
        out = {
            "bm25-plain": lambda q: R.bm25(q, plain),
            "bm25-stem5": lambda q: R.bm25(q, stem),
            "bm25-stem4": lambda q: R.bm25(q, R.Options(stem=4, title_weight=1.0, use_tags=False, expand=False, fuzzy=0)),
            "bm25-stem6": lambda q: R.bm25(q, R.Options(stem=6, title_weight=1.0, use_tags=False, expand=False, fuzzy=0)),
            "bm25-fields": lambda q: R.bm25(q, fields),
            "bm25-fields-tags": lambda q: R.bm25(q, tags),
            "bm25-expand": lambda q: R.bm25(q, expand),
            "lexical": lambda q: R.bm25(q, lex),
            "lexical-language-docs": lambda q: R.bm25(q, lang),
            "dense-minilm": lambda q: self.dense("minilm").scores(q),
            "dense-minilm-language-docs": lambda q: self.dense("minilm", "language").scores(q),
            "dense-mpnet": lambda q: self.dense("mpnet").scores(q),
            "dense-mpnet-language-docs": lambda q: self.dense("mpnet", "language").scores(q),
            "hybrid-rrf": lambda q: rrf([c for c, _ in R.bm25(q, lex)], [c for c, _ in self.dense("mpnet").scores(q)]),
            "hybrid-rrf-minilm": lambda q: rrf([c for c, _ in R.bm25(q, lex)], [c for c, _ in self.dense("minilm").scores(q)]),
            "hybrid-weighted-0.5": lambda q: weighted(R.bm25(q, lex), self.dense("mpnet").scores(q), 0.5),
            "hybrid-weighted-0.7": lambda q: weighted(R.bm25(q, lex), self.dense("mpnet").scores(q), 0.7),
            "hybrid-weighted-0.3": lambda q: weighted(R.bm25(q, lex), self.dense("mpnet").scores(q), 0.3),
            "lexical-rerank": lambda q: self._rerank(q, R.bm25(q, lex)),
            "dense-rerank": lambda q: self._rerank(q, self.dense("mpnet").scores(q)),
            "hybrid-rrf-rerank": lambda q: self._rerank(q, rrf([c for c, _ in R.bm25(q, lex)],
                                                                [c for c, _ in self.dense("mpnet").scores(q)])),
            "hybrid-rrf-mmr": lambda q: mmr(rrf([c for c, _ in R.bm25(q, lex)], [c for c, _ in self.dense("mpnet").scores(q)]),
                                            self._card_sim),
        }
        return out

    def _rerank(self, q, first, depth: int = 10):
        head = [c for c, _ in first[:depth]]
        reranked = self.reranker().rerank(q, head)
        return reranked + [x for x in first[depth:]]

    def _card_sim(self, a, b):
        d = self.dense("mpnet")
        ia, ib = d.ids.index(a), d.ids.index(b)
        return float(d.docs[ia] @ d.docs[ib])


def abstention(rows: list[dict], threshold: float) -> dict:
    ans = [r for r in rows if r["answerable"]]
    un = [r for r in rows if not r["answerable"]]
    abst = [r for r in rows if r["top_score"] <= threshold]
    tp = sum(1 for r in abst if not r["answerable"])
    return {"threshold": threshold, "precision": tp / len(abst) if abst else float("nan"),
            "recall": tp / len(un) if un else float("nan"),
            "false_abstain_rate": sum(1 for r in abst if r["answerable"]) / len(ans) if ans else float("nan")}


def evaluate(fn, cases: list[dict], threshold: float | None = None) -> dict:
    rows, lat = [], []
    for c in cases:
        t0 = time.perf_counter()
        ranked_scores = fn(c["query"])
        lat.append((time.perf_counter() - t0) * 1000)
        ranked = [cid for cid, _ in ranked_scores]
        top = ranked_scores[0][1] if ranked_scores else float("-inf")
        rel = set(c["relevant"])
        row = {"id": c["id"], "category": c["category"], "lang": c["lang"], "answerable": c["answerable"],
               "top": ranked[:5], "top_score": round(top, 4)}
        if c["answerable"]:
            gains = {cid: 1.0 for cid in rel}
            if c.get("primary"):
                gains[c["primary"]] = 2.0
            row.update({"hit1": M.hit_at(ranked, rel, 1), "r1": M.recall_at(ranked, rel, 1), "r3": M.recall_at(ranked, rel, 3),
                        "r5": M.recall_at(ranked, rel, 5), "hit5": M.hit_at(ranked, rel, 5),
                        "rr": M.reciprocal_rank(ranked, c["primary"]) if c.get("primary") else M.reciprocal_rank(ranked, sorted(rel)[0]),
                        "ndcg5": M.ndcg_at(ranked, gains, 5), "p5": M.precision_at(ranked, rel, 5)})
        rows.append(row)
    ans = [r for r in rows if r["answerable"]]
    out = {"n": len(rows), "n_answerable": len(ans),
           "hit@1": M.mean(r["hit1"] for r in ans), "recall@1": M.mean(r["r1"] for r in ans),
           "recall@3": M.mean(r["r3"] for r in ans), "recall@5": M.mean(r["r5"] for r in ans),
           "hit@5": M.mean(r["hit5"] for r in ans), "mrr": M.mean(r["rr"] for r in ans),
           "ndcg@5": M.mean(r["ndcg5"] for r in ans), "precision@5": M.mean(r["p5"] for r in ans),
           "latency_ms": M.summary_ms(lat)}
    if threshold is not None:
        out["abstain"] = abstention(rows, threshold)
    out["by_category"] = {}
    for cat in sorted({r["category"] for r in ans}):
        sub = [r for r in ans if r["category"] == cat]
        out["by_category"][cat] = {"n": len(sub), "recall@5": M.mean(r["r5"] for r in sub), "mrr": M.mean(r["rr"] for r in sub)}
    out["by_lang"] = {lang: {"n": len(sub), "recall@5": M.mean(r["r5"] for r in sub), "mrr": M.mean(r["rr"] for r in sub)}
                      for lang in ("tr", "en", "mixed") if (sub := [r for r in ans if r["lang"] == lang])}
    out["rows"] = rows
    return out


def best_threshold(rows: list[dict]) -> float:
    """Abstention threshold maximising F1 of 'no card answers' while false abstentions stay <= 2 % (dev only)."""
    ans = [r for r in rows if r["answerable"]]
    un = [r for r in rows if not r["answerable"]]
    best, best_f1 = float("-inf"), -1.0
    for t in sorted({r["top_score"] for r in rows}):
        abst = [r for r in rows if r["top_score"] <= t]
        tp = sum(1 for r in abst if not r["answerable"])
        fp = len(abst) - tp
        if ans and fp / len(ans) > 0.02:
            continue
        p = tp / len(abst) if abst else 0.0
        rcl = tp / len(un) if un else 0.0
        f1 = 2 * p * rcl / (p + rcl) if p + rcl else 0.0
        if f1 > best_f1:
            best, best_f1 = t, f1
    return best


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev", choices=("dev", "val", "test"))
    ap.add_argument("--configs", default="", help="comma-separated configuration names (default: all)")
    ap.add_argument("--thresholds", default="", help="JSON file of dev thresholds per configuration")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    bench = Bench()
    configs = bench.configs()
    names = [n for n in args.configs.split(",") if n] or list(configs)
    thresholds = json.loads(Path(args.thresholds).read_text()) if args.thresholds else {}
    cases = load(args.split)
    results = {"split": args.split, "n": len(cases), "corpus_sha256": R.corpus()[1], "retrieval_version": R.VERSION,
               "configs": {}}
    for name in names:
        res = evaluate(configs[name], cases)  # one pass; the abstention threshold is read off the same rows
        thr = thresholds.get(name)
        if thr is None and args.split == "dev":
            thr = best_threshold(res["rows"])
        if thr is not None:
            res["abstain"] = abstention(res["rows"], thr)
        results["configs"][name] = res
        a = res.get("abstain") or {}
        print(f"{name:28} R@5 {res['recall@5']:.3f}  hit@1 {res['hit@1']:.3f}  MRR {res['mrr']:.3f}  nDCG@5 {res['ndcg@5']:.3f}"
              f"  abst P {a.get('precision', float('nan')):.2f} R {a.get('recall', float('nan')):.2f}"
              f"  p50 {res['latency_ms']['p50']:.1f} ms  p95 {res['latency_ms']['p95']:.1f} ms")
    results["model_loads"] = bench.loads
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(results, indent=1, ensure_ascii=False, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
