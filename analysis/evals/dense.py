"""Dense embeddings and cross-encoder reranking for the retrieval benchmark (optional: needs `fastembed`).

Models are downloaded once into analysis/.local/models (ignored by Git, regenerable). Nothing here runs in the
product unless the benchmark shows it wins (docs/evals/RETRIEVAL.md).
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np

CACHE = Path(__file__).resolve().parents[1] / ".local" / "models"
# Models whose authors trained them with instruction prefixes.
PREFIXES = {"intfloat/multilingual-e5-large": ("query: ", "passage: ")}


def _cache() -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    return str(CACHE)


class Dense:
    """Cosine similarity between a question and each card (one vector per card or per card language)."""

    def __init__(self, model: str, cards: list[dict], granularity: str = "card"):
        from fastembed import TextEmbedding

        t0 = time.perf_counter()
        self.name, self.granularity = model, granularity
        self.model = TextEmbedding(model, cache_dir=_cache(), threads=max(1, (os.cpu_count() or 2) // 2))
        self.load_s = time.perf_counter() - t0
        q_prefix, d_prefix = PREFIXES.get(model, ("", ""))
        self.q_prefix = q_prefix
        texts, self.ids = [], []
        for c in cards:
            if granularity == "language":
                for i in (0, 1):
                    texts.append(d_prefix + c["title"][i] + ". " + c["body"][i])
                    self.ids.append(c["id"])
            else:
                texts.append(d_prefix + c["title"][0] + " / " + c["title"][1] + ". " + c["body"][0] + " " + c["body"][1])
                self.ids.append(c["id"])
        t0 = time.perf_counter()
        self.docs = self._norm(np.array(list(self.model.embed(texts))))
        self.index_s = time.perf_counter() - t0

    @staticmethod
    def _norm(m):
        return m / np.linalg.norm(m, axis=1, keepdims=True)

    def scores(self, question: str) -> list[tuple[str, float]]:
        q = self._norm(np.array(list(self.model.embed([self.q_prefix + question]))))[0]
        sims = self.docs @ q
        best: dict[str, float] = {}
        for cid, s in zip(self.ids, sims):
            best[cid] = max(best.get(cid, -1.0), float(s))
        return sorted(best.items(), key=lambda kv: (-kv[1], kv[0]))


class Reranker:
    """Cross-encoder relevance of (question, card) pairs, for the top candidates of a first stage."""

    def __init__(self, model: str, cards: list[dict]):
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        t0 = time.perf_counter()
        self.name = model
        self.model = TextCrossEncoder(model, cache_dir=_cache(), threads=max(1, (os.cpu_count() or 2) // 2))
        self.load_s = time.perf_counter() - t0
        self.text = {c["id"]: c["title"][0] + " / " + c["title"][1] + ". " + c["body"][0] + " " + c["body"][1] for c in cards}

    def rerank(self, question: str, ids: list[str]) -> list[tuple[str, float]]:
        scores = list(self.model.rerank(question, [self.text[i] for i in ids]))
        return sorted(zip(ids, map(float, scores)), key=lambda kv: (-kv[1], kv[0]))
