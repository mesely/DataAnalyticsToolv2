"""Knowledge retrieval for the assistant (v3, AW-23): which context cards answer a question.

The corpus is `analysis/knowledge/context-cards.json` (definitions, exclusions, reference data, transforms,
methods, limitations, workspace). Every configuration below was measured on the retrieval benchmark
(`python -m analysis.evals.retrieval`, docs/evals/RETRIEVAL.md) and the default is the one that won on the
validation split; the frozen test split is reported, never tuned on.

Retrieval is lexical and deterministic by default: Turkish-aware folding, first-N-character stemming (a strong,
simple stemmer for Turkish IR), BM25 over separately indexed fields (titles weigh more than bodies), and a small
bilingual expansion lexicon. Dense and reranking stages live in the benchmark harness (they need a model download
and an ONNX runtime), and are used in production only if they win there.
"""
from __future__ import annotations

import functools
import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

CORPUS = Path(__file__).resolve().parent / "knowledge" / "context-cards.json"
VERSION = "retrieval-v1"

_FOLD = str.maketrans({"İ": "i", "ı": "i", "’": "'", "‘": "'", "`": "'", "₺": " tl ", "£": " gbp ", "$": " usd ", "€": " eur "})
_TOKEN = re.compile(r"[a-z0-9]+(?:[.,][0-9]+)*")
# Function words that carry no topic in either language (folded). Kept short on purpose: question words such as
# "neden"/"why" are topical here (they signal limitation and exclusion cards).
STOP = frozenset("""
a an and are as at be by bu da de do does for from has have how i ile in is it its mi mu mı mü ne nedir of on or our
the this to ve veya was we what which with bir icin gibi olan ki my me show tell bana ben biz bunu buna""".split())

# Bilingual expansion lexicon (folded, stemmed lookups happen after folding). Authored from the product's own
# vocabulary on the development split only; each entry maps a user word to card vocabulary in the other language.
EXPANSION = {
    "ciro": ["revenue", "gross", "sales", "brut", "satis"], "hasilat": ["revenue", "brut", "satis"],
    "revenue": ["ciro", "brut", "satis"], "turnover": ["ciro", "gross"], "sales": ["satis"], "satis": ["sales"],
    "kar": ["profit", "kar"], "profit": ["kar"], "marj": ["margin"], "margin": ["marj"],
    "kur": ["exchange", "rate", "ecb"], "doviz": ["exchange", "currency", "kur"], "exchange": ["kur", "doviz"],
    "enflasyon": ["inflation", "cpi", "tufe"], "inflation": ["enflasyon", "tufe", "cpi"], "tufe": ["cpi", "inflation"],
    "cpi": ["tufe", "enflasyon"], "altin": ["gold"], "gold": ["altin"], "lira": ["tl", "try"], "tl": ["try", "lira"],
    "dolar": ["usd", "dollar"], "dollar": ["usd", "dolar"], "euro": ["eur", "avro"], "avro": ["euro", "eur"],
    "iade": ["return", "cancel", "iptal"], "iptal": ["cancel", "cancelled"], "return": ["iade", "iptal"],
    "cancel": ["iptal"], "kargo": ["postage", "shipping", "posta"], "postage": ["kargo", "posta"],
    "shipping": ["kargo", "postage"], "musteri": ["customer"], "customer": ["musteri"],
    "sepet": ["basket", "order", "aov"], "basket": ["sepet", "aov"], "siparis": ["order", "orders", "invoice"],
    "order": ["siparis"], "fatura": ["invoice"], "invoice": ["fatura"], "adet": ["units", "quantity"],
    "tahmin": ["forecast", "projection"], "forecast": ["tahmin", "projeksiyon"], "gelecek": ["future", "next"],
    "neden": ["why"], "why": ["neden"], "ag": ["network", "graph"], "network": ["ag"], "uyelik": ["membership"],
    "membership": ["uyelik"], "kaynak": ["source"], "source": ["kaynak"], "gizlilik": ["privacy"], "privacy": ["gizlilik"],
    "tablo": ["table"], "table": ["tablo"], "kita": ["continent"], "continent": ["kita"],
}


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text).translate(_FOLD).casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def tokens(text: str, stem: int | None = 5, stop: bool = True) -> list[str]:
    out = []
    for t in _TOKEN.findall(fold(text)):
        if stop and t in STOP:
            continue
        out.append(t[:stem] if stem and len(t) > stem and not t[0].isdigit() else t)
    return out


@dataclass
class Options:
    """One retrieval configuration (every switch is a benchmark ablation)."""
    stem: int | None = 5            # first-N-character stemming; None = whole words
    title_weight: float = 2.0       # BM25F-style field weight of titles relative to bodies
    use_tags: bool = True           # include the cards' search tags
    expand: bool = True             # bilingual expansion lexicon
    expand_weight: float = 0.5      # weight of expansion terms relative to the user's own words
    k1: float = 1.2
    b: float = 0.75
    granularity: str = "card"       # "card" (one document per card) | "language" (tr and en documents, max-pooled)
    fuzzy: int = 1                  # a query word unknown to the corpus also matches vocabulary words this many edits away
    fuzzy_weight: float = 0.7


@dataclass
class _Index:
    ids: list
    docs: list
    df: Counter
    avgdl: float
    tf: list = field(default_factory=list)


@functools.lru_cache(maxsize=1)
def corpus() -> tuple[dict, str]:
    raw = CORPUS.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def cards() -> list[dict]:
    return corpus()[0]["cards"]


def _document(card: dict, opt: Options, lang: int | None) -> Counter:
    """Weighted term counts of one card (or one language of it)."""
    langs = (0, 1) if lang is None else (lang,)
    bag: Counter = Counter()
    for i in langs:
        for t in tokens(card["title"][i], opt.stem):
            bag[t] += opt.title_weight
        for t in tokens(card["body"][i], opt.stem):
            bag[t] += 1.0
    if opt.use_tags:
        for t in tokens(card.get("tags", ""), opt.stem):
            bag[t] += 1.0
    return bag


@functools.lru_cache(maxsize=32)
def _index(opt_key: tuple) -> _Index:
    opt = Options(*opt_key)
    ids, docs = [], []
    for card in cards():
        if opt.granularity == "language":
            for lang in (0, 1):
                ids.append(card["id"])
                docs.append(_document(card, opt, lang))
        else:
            ids.append(card["id"])
            docs.append(_document(card, opt, None))
    df: Counter = Counter()
    for d in docs:
        df.update(set(d))
    avgdl = sum(sum(d.values()) for d in docs) / len(docs)
    return _Index(ids, docs, df, avgdl)


def _key(opt: Options) -> tuple:
    return (opt.stem, opt.title_weight, opt.use_tags, opt.expand, opt.expand_weight, opt.k1, opt.b, opt.granularity,
            opt.fuzzy, opt.fuzzy_weight)


def _edits_le(a: str, b: str, limit: int) -> bool:
    """Damerau-Levenshtein distance(a, b) <= limit (adjacent transpositions count once), with early exit."""
    if abs(len(a) - len(b)) > limit:
        return False
    prev2, prev = None, list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            if prev2 is not None and i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        if min(cur) > limit:
            return False
        prev2, prev = prev, cur
    return prev[-1] <= limit


@functools.lru_cache(maxsize=32)
def _vocabulary(opt_key: tuple) -> tuple[frozenset, dict]:
    """Unstemmed folded words of the corpus, and their stems (for typo matching)."""
    opt = Options(*opt_key)
    words = set()
    for card in cards():
        for text in (*card["title"], *card["body"], card.get("tags", "")):
            words.update(t for t in _TOKEN.findall(fold(text)) if len(t) >= 4 and not t[0].isdigit())
    return frozenset(words), {w: (w[:opt.stem] if opt.stem and len(w) > opt.stem else w) for w in words}


def query_terms(question: str, opt: Options) -> Counter:
    own = tokens(question, opt.stem)
    q: Counter = Counter({t: 1.0 for t in own})
    if opt.fuzzy:
        words, stems = _vocabulary(_key(opt))
        idx = _index(_key(opt))
        for word in _TOKEN.findall(fold(question)):
            if len(word) < 5 or word in STOP or word in words or word[0].isdigit():
                continue
            stem = word[:opt.stem] if opt.stem and len(word) > opt.stem else word
            if stem in idx.df:
                continue  # the stem already matches the corpus
            for w in words:
                if w[0] == word[0] and _edits_le(word, w, opt.fuzzy) and stems[w] not in q:
                    q[stems[w]] = opt.fuzzy_weight
    if opt.expand:
        for word in _TOKEN.findall(fold(question)):
            for extra in EXPANSION.get(word, ()):
                for t in tokens(extra, opt.stem):
                    if t not in q:
                        q[t] = opt.expand_weight
    return q


def bm25(question: str, opt: Options | None = None) -> list[tuple[str, float]]:
    """(card id, score) for every card, best first (ties by id). Scores are BM25 with weighted term frequencies."""
    opt = opt or Options()
    idx = _index(_key(opt))
    q = query_terms(question, opt)
    n = len(idx.docs)
    best: dict[str, float] = {}
    for cid, d in zip(idx.ids, idx.docs):
        dl = sum(d.values())
        s = 0.0
        for term, w in q.items():
            f = d.get(term, 0.0)
            if not f:
                continue
            idf = math.log(1 + (n - idx.df[term] + 0.5) / (idx.df[term] + 0.5))
            s += w * idf * f * (opt.k1 + 1) / (f + opt.k1 * (1 - opt.b + opt.b * dl / idx.avgdl))
        best[cid] = max(best.get(cid, 0.0), s)
    return sorted(best.items(), key=lambda kv: (-kv[1], kv[0]))


def search(question: str, k: int = 5, opt: Options | None = None, min_score: float = 0.0) -> list[dict]:
    """Top-k cards for a question with their scores; cards scoring at or below `min_score` are dropped."""
    by_id = {c["id"]: c for c in cards()}
    return [{"id": cid, "score": round(s, 4), "card": by_id[cid]} for cid, s in bm25(question, opt)[:k] if s > min_score]
