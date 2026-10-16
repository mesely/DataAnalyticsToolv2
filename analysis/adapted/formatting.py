"""Pure extractive summaries from mesely/adviSU response_formatter.py.
Pinned e1e224134a3ce9a52c758c35ce517b1d42c9b75a; no model or academic side effects.
"""

import re

SUMMARY_HEADINGS = ("## Kısa Özet", "## Kisa Ozet", "## Short Summary")


def _plain_text(markdown: str) -> str:
    text = re.sub(r"```.*?```", " ", markdown or "", flags=re.DOTALL)
    text = re.sub(r"^\s*(?:#{1,6}|[-*+]|\d+\.)\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\|[-: |]+\|", " ", text)
    text = re.sub(r"[`*_>#]", "", text)
    text = re.sub(r"\[(.*?)\]\([^)]*\)", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def split_summary(answer: str) -> tuple[str, str]:
    """Return ``(body, summary)`` when the model already emitted a summary section."""
    for heading in SUMMARY_HEADINGS:
        index = answer.lower().find(heading.lower())
        if index >= 0:
            body = answer[:index].rstrip()
            summary = _plain_text(answer[index + len(heading) :])
            return body, summary
    return answer.rstrip(), ""


def compact_summary(answer: str, *, language: str = "tr", max_chars: int = 420) -> str:
    """Create a short extractive fallback when the model omitted its summary.

    This is intentionally conservative.  It reuses claims already present in the answer
    instead of asking a second model to generate another potentially inconsistent result.
    """
    _body, existing = split_summary(answer)
    if existing:
        return existing[:max_chars].rstrip()

    cleaned = _plain_text(
        re.sub(
            r"(?:^|\n)Sources?:.*$", "", answer or "", flags=re.DOTALL | re.IGNORECASE
        )
    )
    if not cleaned:
        return (
            "Bu cevap için kısa özet üretilemedi."
            if language == "tr"
            else "A short summary could not be generated for this answer."
        )
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    chosen: list[str] = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate = " ".join([*chosen, sentence])
        if len(candidate) > max_chars and chosen:
            break
        chosen.append(sentence)
        if len(chosen) >= 2:
            break
    summary = " ".join(chosen) or cleaned[:max_chars]
    if len(summary) > max_chars:
        summary = summary[: max_chars - 1].rstrip() + "…"
    return summary
