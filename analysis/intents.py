"""The assistant's first decision (AW-24): what kind of question is this?

    classify("retail-v2 nedir?") -> {"intent": "knowledge", "method": "learned", "confidence": 0.93, ...}

Intents (v2): summary, products, countries, network, temporal, knowledge, unsupported, clarify, refuse. The local
guard (analysis/adapted/guardrails.py) decides `refuse` first and is final; then a small linear classifier trained
offline on the benchmark's dev split (analysis/models/intent-router.json, `python -m analysis.evals.train --task
intent`) labels the rest. Whether the model is asked instead is the routing table's decision (llm_routing.json),
from the held-out measurement — never a checkbox.
"""
from __future__ import annotations

import re

from analysis.adapted.guardrails import assess_input
from analysis.retrieval import fold

VERSION = "intent-router-v2"
INTENTS = ("summary", "products", "countries", "network", "temporal", "knowledge", "unsupported", "clarify", "refuse")
ANSWERS = {"summary", "products", "countries", "network", "temporal", "knowledge"}


def behavior(intent: str) -> str:
    return "answers" if intent in ANSWERS else intent


_P = lambda s: re.compile(s)  # noqa: E731 - patterns run on folded text (lower case, no diacritics, ı -> i)
# What the data cannot answer (contract: profit, causes, customers, next year, competitors, quantity rankings).
# Requests for instructions, prompts or secrets that the guard's patterns miss (the guard stays first and final).
REFUSE = _P(r"(?:sistem prompt\w*|system prompt\w*|talimat\w* (?:yok say|goster|yaz|unut|ifsa)\w*|ignore (?:all|any|previous|prior|your)|"
            r"disregard (?:all|your|previous)|api (?:key|anahtar)\w*|anahtari\w* (?:goster|yaz|ver)|secret\w*|gizli (?:kural|talimat|anahtar)\w*|"
            r"developer mode|gelistirici modu|jailbreak|kurallar\w* (?:unut|yok say|bosver|cigne)\w*)")
UNSUPPORTED = _P(r"(?<![a-z])(?:kar(?:li\w*|lar\w*|i|in|imiz\w*|ini)?(?![a-z])|profit\w*|marj\w*|margin\w*|net (?:gelir|ciro|satis|kar|sales|revenue|income)|"
                 r"roi|yatirim getiri\w*|maliyet\w*|costs?|churn\w*|kayip oran\w*|musteri kaybi\w*|memnun\w*|satisf\w*|happy|"
                 r"sadakat\w*|loyal\w*|lifetime value|yasam boyu deger\w*|donusum oran\w*|conversion\w*|rakip\w*|competitor\w*|"
                 r"pazar pay\w*|market share|gelecek yil\w*|next year\w*|onumuzdeki yil\w*|2012|predict\w*|"
                 r"stok seviye\w*|stock level\w*|inventory|envanter\w*|kampanya etkisi|campaign effect\w*|reklam\w*|advert\w*|"
                 r"(?:neden|niye|nicin|why)\b.{0,40}(?:dus|azal|art|yuksel|fell|fall|drop|declin|decreas|increas|ris|grow|go(?:es)? (?:up|down))|"
                 r"(?:dus|azal|art|fell|drop|declin)\w*.{0,30}(?:nedeni|sebeb|reason|cause)|"
                 r"adet (?:bazinda|olarak|e gore) (?:sirala|en)|en cok adet|most units|units sold the most|by quantity|miktar(?:a|ca) gore sirala)")
# Questions about definitions, methods, provenance and exclusions (answered from the context cards).
KNOWLEDGE = _P(r"(?:nasil hesaplan\w*|nasil bulun\w*|nasil tanimlan\w*|nasil cevril\w*|nasil uygulan\w*|ne demek|ne anlama|"
               r"neyi ifade|tanim\w*|definition\w*|define\w*|formul\w*|formula|"
               r"how (?:is|are|do you|does|was|were) .{0,60}(?:computed|calculated|defined|measured|converted|handled|chosen|built|derived|treated|counted)|"
               r"what (?:does|do) .{0,40}mean|what is (?:the )?(?:retail|aov|gross|merchandise|a |an )|what are (?:the )?(?:limits|rules)|"
               r"kaynag\w*|kaynak\w*|\bsource\w*|nereden (?:geliyor|alin\w*|geli\w*)|"
               r"where (?:do|does|did) (?:the |these |our |your )?(?:rates?|exchange rates?|numbers?|data|cpi|figures?|memberships?|prices?|gold|inflation|reference)\w* .{0,30}come from|"
               r"hangi (?:seri|kur\w*|tufe|endeks|yontem|standart|tarih\w* uyelik)|which (?:series|cpi|rate|exchange rate|method|standard|index)|"
               r"(?:neden|niye|nicin|why)\b.{0,50}(?:disla|haric|cikar|dusul|sayilm|yok|gorunm|excluded|left out|removed|not (?:counted|included|shown))|"
               r"lisans\w*|licen[cs]e\w*|yontem\w*|methodolog\w*|gizlilik\w*|privacy|retail-?v[12]|merchandise|guven aralig\w*|"
               r"confidence interval|kontrol band\w*|control band|hareketli ortalama nedir|moving average mean)")
NETWORK = _P(r"(?:birlikte|beraber|ayni (?:sepet|fatura|siparis)\w*|same (?:order|invoice|basket)s?|together|co-?purchase\w*|basket affinit\w*|bundle\w*|sepet\w* (?:analiz|iliski)\w*|"
             r"yaninda (?:ne|hangi)|iliski ag\w*|relationship network|urun ciftleri|product pairs?|pairs?)")
TEMPORAL = _P(r"(?:ay ay|aydan aya|aylara gore|aylik\w*|monthly|month (?:over|by|to) month|over time|zaman(?:la| icinde)\w*|trend\w*|"
              r"egilim\w*|gidisat\w*|yukseliyor|artiyor mu|dusuyor mu|going (?:up|down)|rising|seasonal\w*|mevsim\w*|"
              r"hangi ay\w*|which month\w*|en yuksek ay|peak month|nasil degisti|how did .{0,30}change|degisim\w*|"
              r"(?:rise|rose|fall|fell|grow|grew|increase|decrease|drop)(?:d|s)? (?:during|over|in|across|through)|yil boyunca|boyunca (?:art|dus)\w*)")
PRODUCTS = _P(r"(?:urun\w*|product\w*|items?\b|sku\w*|best.?sell\w*|en cok satan|en iyi satan|top seller\w*|stok kod\w*)")
COUNTRIES = _P(r"(?:ulke\w*|countr\w*|pazar\w*|market\w*|nerede (?:sat|en)|where (?:do we|does it) sell|where .{0,20}(?:sales|revenue) come from|"
               r"bolge\w*|region\w*|hangi (?:ulke|pazar))")
SUMMARY = _P(r"(?:toplam\w*|total\w*|genel (?:tablo|durum|bakis)|ozet\w*|overview|big picture|kac (?:siparis|fatura|adet)|how many (?:orders|invoices|units)|"
             r"ciro\w* ne kadar|revenue (?:is|so far)|ortalama sepet|average order|aov)")
CLARIFY = _P(r"(?:^|\b)(?:bunu|sunu|onu|bunun|sunun|orayi|oradaki\w*|surayi|that one|this one|the other one|compare it|compare this|show (?:me )?there|"
             r"just there|it with|ayni sey\w*|bu ne kadar)|(?:filtre\w*|tarih\w*|donem\w*|date|period).{0,20}(?:degistir|change|set|ayarla|gec)|"
             r"sadece \w+(?:'[a-z]+)? (?:goster|olsun)|show (?:only )?\w+ only|only show \w+|switch to \w+")


def rules(question: str) -> str | None:
    """High-precision cue rules (v2). None when no rule fires (the classifier decides)."""
    t = fold(question)
    if REFUSE.search(t):
        return "refuse"
    if UNSUPPORTED.search(t):
        return "unsupported"
    if KNOWLEDGE.search(t):
        return "knowledge"
    if CLARIFY.search(t) and not (PRODUCTS.search(t) or SUMMARY.search(t) or NETWORK.search(t)):
        return "clarify"
    if NETWORK.search(t):
        return "network"
    if TEMPORAL.search(t):
        return "temporal"
    hits = [name for name, pattern in (("products", PRODUCTS), ("countries", COUNTRIES), ("summary", SUMMARY)) if pattern.search(t)]
    return hits[0] if len(hits) == 1 else None


def classify(question: str, method: str = "auto") -> dict:
    """Local intent. `method`: "learned" (classifier only, after the guard), "rules" (cue rules, classifier when no
    rule fires) or "auto" (the product's choice, measured on the val split: see docs/evals/ROUTING.md)."""
    q = str(question or "").strip()
    if not q:
        return {"intent": "clarify", "method": "empty", "confidence": 1.0, "version": VERSION}
    check = assess_input(q)
    if not check.allowed:
        return {"intent": "refuse", "method": "guard", "confidence": 1.0, "reason": check.category, "version": VERSION}
    if method in ("rules", "auto"):
        hit = rules(q)
        if hit:
            return {"intent": hit, "method": "rules", "confidence": 1.0, "version": VERSION}
    from analysis import textclf

    label, p = textclf.predict("intent-router", q)
    return {"intent": label, "method": "learned", "confidence": round(p, 4), "version": VERSION}
