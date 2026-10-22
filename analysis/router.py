"""Which studio a request belongs to (v3 G8): one ask box, two studios.

The Chart studio draws and reshapes a chart; the Decision studio answers questions, explains, projects and recommends.
This local router decides from the wording alone, deterministically; it never refuses — the destination studio applies
its own validation and abstention. An explicit drawing word ("grafik", "chart", "çiz", "plot") wins; otherwise a
question or decision word sends the request to the Decision studio, and chart-shaping vocabulary (periods, splits,
statistics, normalisation) to the Chart studio. With no signal at all the Decision studio takes it, because its
assistant can ask for clarification.
"""

import re

ROUTER_VERSION = "studio-router-v1"

# Words that name a chart or the act of drawing one.
_DRAW = re.compile(
    r"\b(grafi[kğ]\w*|chart\w*|plot\w*|çiz\w*|draw\w*|görselleştir\w*|visuali[sz]\w*|diagram\w*|pasta grafi\w*|pie|histogram\w*)",
    re.I,
)
# Questions, explanations, projections and recommendations.
_DECIDE = re.compile(
    r"\b(öner\w*|recommend\w*|karar\w*|decid\w*|decision\w*|ne yapmal\w*|what should|tahmin\w*|forecast\w*|projeksiyon\w*|"
    r"project(ion|ed)?\b|senaryo\w*|scenario\w*|neden\w*|niçin|why|açıkla\w*|explain\w*|özetle\w*|summar\w*|"
    r"hangi\w*|which|kaç\b|how many|ne kadar|how much|en çok|en az|most|least|best|worst|kâr\w*|kar\b|profit\w*|marj\w*|margin\w*|"
    r"risk\w*|fırsat\w*|opportunit\w*|bütçe\w*|budget\w*)",
    re.I,
)
# Chart-shaping vocabulary: periods, grouping, comparisons, statistics, overlays, units.
_SHAPE = re.compile(
    r"\b(trend\w*|karşılaştır\w*|compare\w*|versus|\bvs\b|hareketli ortalama|moving average|güven aralığı|confidence interval|"
    r"interval|kontrol bandı|control band|son \d+ (ay|hafta|gün)|last \d+ (months?|weeks?|days?)|aylık|monthly|haftalık|weekly|"
    r"günlük|daily|çeyrek|quarter\w*|ülkelere göre|by country|ürünlere göre|by product|ilk \d+|top \d+|hariç|except|excluding|"
    r"çubuk|bar|çizgi|line|alan|area|eksen|axis|normalize\w*|endeks\w*|index(ed)?|TL\b|lira|dolar|usd|euro|eur\b|enflasyon\w*|"
    r"inflation|altın\w*|gold|kur\b|exchange rate)",
    re.I,
)


def route(text, locale="tr", method="rules"):
    """Return {"studio": "chart"|"decision", "signal": ..., "version": ...} for a request text.

    method "rules" is the v1 lexicon below; "learned" the linear classifier trained on the benchmark's dev split
    (analysis/models/studio-router.json, AW-24); "auto" is what the product uses (see llm_routing.json)."""
    if not isinstance(text, str):
        raise ValueError("İstek metin olmalı.")
    t = text.strip()
    if len(t) > 8000:
        raise ValueError("İstek 8.000 karakteri aşamaz.")
    if method in ("learned", "auto"):
        from analysis import textclf

        studio, p = textclf.predict("studio-router", t)
        return {"studio": studio, "signal": "learned", "confidence": round(p, 4),
                "version": "studio-router-v2" if method == "auto" else "studio-router-learned-v1"}
    if _DRAW.search(t):
        studio, signal = "chart", "draw"
    elif _DECIDE.search(t):
        studio, signal = "decision", "question"
    elif _SHAPE.search(t):
        studio, signal = "chart", "shape"
    else:
        studio, signal = "decision", "default"
    return {"studio": studio, "signal": signal, "version": ROUTER_VERSION}
