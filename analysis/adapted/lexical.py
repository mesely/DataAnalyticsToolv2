"""BM25 scoring extracted from adviSU; dataset documents are supplied by the caller."""
import math
from collections import Counter
class _BM25:
    def __init__(self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.docs = corpus
        self.N = len(corpus)
        self.doc_len = [len(d) for d in corpus]
        self.avgdl = (sum(self.doc_len) / self.N) if self.N else 0.0
        df: Counter[str] = Counter()
        for d in corpus:
            for term in set(d):
                df[term] += 1
        self.idf = {
            term: math.log(1 + (self.N - freq + 0.5) / (freq + 0.5))
            for term, freq in df.items()
        }
        self.tf = [Counter(d) for d in corpus]

    def scores(self, query_tokens: list[str]) -> list[float]:
        q = [t for t in query_tokens if t in self.idf]
        out = [0.0] * self.N
        for i in range(self.N):
            tf_i, dl = self.tf[i], self.doc_len[i]
            s = 0.0
            for term in q:
                f = tf_i.get(term, 0)
                if not f:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1))
                s += self.idf[term] * (f * (self.k1 + 1)) / denom
            out[i] = s
        return out
