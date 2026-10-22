"""Grounded answers to knowledge questions (AW-23): definitions, exclusions, reference data, methods, limits.

    answer("retail-v2 nedir?", locale="tr") -> {"status": "answered", "text": ..., "citations": [...], ...}

The answer is assembled from the retrieved context cards only: the most relevant card's sentences (ranked against
the question, in the question's language), then the titles of other cards that also apply. Nothing is generated,
so every sentence is a sentence of a cited card (faithful by construction); a model may rephrase only through
`answer(..., model=...)`, whose reply is checked: every number it states must appear in the cited cards, or the
extractive answer is shown instead. When no card scores above the abstention threshold the answer says so and
names the kinds of questions the product can answer.
"""
from __future__ import annotations

import re

from analysis import retrieval as R

VERSION = "knowledge-qa-v1"
# Chosen on the dev split of the retrieval benchmark (docs/evals/RETRIEVAL.md); see analysis/evals/retrieval.py.
ABSTAIN_SCORE = 4.2923  # dev split: highest top score with <= 2 % false abstentions (analysis/evals/retrieval.py)
MAX_SENTENCES = 4
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÇĞİÖŞÜ'\"(£$€₺0-9])")
_NUM = re.compile(r"\d[\d.,]*")


def _lang(question: str, locale: str) -> int:
    from analysis.adapted.language import detect_language

    try:
        return 1 if detect_language(question) == "en" else 0
    except Exception:  # noqa: BLE001 - language detection must never break an answer
        return 1 if locale == "en" else 0


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split(text) if s.strip()]


def _extract(question: str, card: dict, i: int, opt: R.Options, mode: str = "ranked") -> list[str]:
    """The card's sentences most related to the question, in reading order (always including the first). A
    limitation card is given whole: its last sentence names the closest analysis that does work."""
    sents = sentences(card["body"][i])
    if mode == "all" or card.get("kind") == "limitation":
        return sents
    q = set(R.query_terms(question, opt))
    scored = [(len(q & set(R.tokens(s, opt.stem))), -n) for n, s in enumerate(sents)]
    keep = {0} | {-n for _, n in sorted(scored, reverse=True)[:MAX_SENTENCES - 1] if _ > 0}
    return [s for n, s in enumerate(sents) if n in keep][:MAX_SENTENCES]


# A second card's body is quoted too when it scores within this share of the first (the question likely needs both);
# chosen on the dev split (docs/evals/RETRIEVAL.md).
SECOND_BODY = 0.6


def answer(question: str, locale: str = "tr", *, k: int = 3, opt: R.Options | None = None,
           threshold: float = ABSTAIN_SCORE, retriever=None, mode: str = "all", second: float = SECOND_BODY) -> dict:
    """Retrieve, then answer extractively with citations. `retriever(question) -> [(card_id, score), ...]` overrides
    the default lexical retriever (used by the benchmark to compare configurations end to end)."""
    opt = opt or R.Options()
    i = _lang(question, locale)
    ranked = retriever(question) if retriever else R.bm25(question, opt)
    by_id = {c["id"]: c for c in R.cards()}
    if not ranked or ranked[0][1] <= threshold:
        return {"status": "no_card", "version": VERSION, "citations": [], "retrieved": [c for c, _ in ranked[:k]],
                "text": ("I have no reference card that answers this. I can explain the measures and their definitions, "
                         "what is excluded and why, where exchange rates, inflation, gold and country memberships come "
                         "from, how the statistics are computed, and what the data cannot answer.") if i else
                        ("Bunu cevaplayan bir bilgi kartım yok. Ölçülerin tanımlarını, neyin neden dışarıda kaldığını, "
                         "kur, enflasyon, altın ve ülke üyeliği verisinin kaynağını, istatistiklerin nasıl hesaplandığını "
                         "ve verinin neyi cevaplayamadığını açıklayabilirim.")}
    top_id, top_score = ranked[0]
    top = by_id[top_id]
    body = _extract(question, top, i, opt, mode)
    quoted = [top]
    if len(ranked) > 1 and second and ranked[1][1] >= second * top_score:
        nxt = by_id[ranked[1][0]]
        body += [""] + _extract(question, nxt, i, opt, mode)
        quoted.append(nxt)
    # Other cards that also apply: within 60 % of the top score, at most k-1 of them, named by title.
    also = [by_id[c] for c, s in ranked[1:k] if s >= 0.6 * top_score and by_id[c] not in quoted]
    text = " ".join(body).replace("  ", "\n\n")
    if also:
        text += ("\n\nSee also: " if i else "\n\nAyrıca: ") + "; ".join(c["title"][i] for c in also) + "."
    cited = quoted + also
    return {"status": "answered", "version": VERSION, "text": text,
            "citations": [{"id": c["id"], "title": c["title"][i], "source": c.get("source")} for c in cited],
            "retrieved": [c for c, _ in ranked[:k]], "score": round(top_score, 4), "corpus_sha256": R.corpus()[1]}


def unsupported_numbers(text: str, cited: list[dict]) -> list[str]:
    """Numbers in `text` that appear in none of the cited cards (either language). Used to validate model prose."""
    pool = " ".join(c["body"][0] + " " + c["body"][1] + " " + c["title"][0] + " " + c["title"][1] for c in cited)
    canon = lambda s: re.sub(r"[^\d]", "", s)  # noqa: E731 - "10.641.696,39" and "10,641,696.39" compare equal
    known = {canon(n) for n in _NUM.findall(pool)}
    return [n for n in _NUM.findall(text) if canon(n) and canon(n) not in known]
