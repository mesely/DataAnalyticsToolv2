"""Questions about the relationship network (v3 G2): a sentence becomes a network query, computed locally.

A planner (the deterministic one here, or the model when the routing table says so — AW-18; this task has no
measurement yet, so it is local) turns the question into one of a few queries over the network the analyst is
looking at: the strongest links, a product's neighbours, the communities, the bridge products, the most connected
products, or the links that appeared or disappeared between two months. The answer names its numbers, lists the
nodes and links it rests on (the interface lights them up), and says what the network cannot tell.
"""
from __future__ import annotations

import re
import unicodedata

VERSION = "network-qa-v1"
QUERIES = ("strongest_pairs", "neighbors", "communities", "bridges", "hubs", "changes", "unsupported", "clarify")
K_RANGE = (1, 15)

_FOLD = str.maketrans({"İ": "i", "ı": "i", "’": "'", "‘": "'"})


def fold(text):
    text = unicodedata.normalize("NFKD", str(text).translate(_FOLD).casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


_P = re.compile
RE_UNSUPPORTED = _P(r"(?<!\w)(?:neden|nicin|why|sebep|cause[sd]?|musteri[a-z']*|customer[s]?|kar(?:i|li|lilik)?(?![a-z])|profit|margin|marj|tahmin|forecast|predict)")
RE_CHANGES = _P(r"(?<!\w)(?:kop(?:tu|an|mus)[a-z]*|olus(?:tu|an|mus)[a-z]*|yeni bag[a-z]*|kaybol[a-z]*|degis(?:ti|en|im)[a-z]*|new link[s]?|lost|appeared|disappeared|changed|change[s]?)")
RE_COMMUNITIES = _P(r"(?<!\w)(?:topluluk[a-z']*|kume[a-z']*|grup(?:lar|lari)[a-z']*|communit(?:y|ies)|clusters?|groups?(?![a-z]))")
RE_BRIDGES = _P(r"(?<!\w)(?:kopru[a-z']*|arac[a-z']*|aradalik|bridg[a-z]*|broker[a-z]*|betweenness|connects? (?:the )?groups)")
RE_HUBS = _P(r"(?<!\w)(?:en (?:cok|fazla) bag(?:lanti|i)[a-z']*|merkez[a-z']*|most connected|hub[s]?|central[a-z]*|degree)")
RE_NEIGHBORS = _P(r"(?<!\w)(?:ile (?:en cok |birlikte |beraber )|yaninda|beraber|birlikte alin[a-z']*|bought with|purchased with|goes? with|paired with|together with|neighbou?rs?|komsu[a-z']*)")
RE_STRONG = _P(r"(?<!\w)(?:en guclu|strongest|en cok birlikte|most (?:often )?bought together|top pairs?|en sik|ciftler[a-z']*|pairs?(?![a-z]))")
RE_K = _P(r"(?<![\d.])(\d{1,2})(?![\d.])")
RE_MONTH_ISO = _P(r"(?<!\d)((?:19|20)\d{2})-(0[1-9]|1[0-2])(?!\d)")
_TR_MONTHS = ["ocak", "subat", "mart", "nisan", "mayis", "haziran", "temmuz", "agustos", "eylul", "ekim", "kasim", "aralik"]
_EN_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
RE_MONTH_WORD = _P(r"(?<!\w)(" + "|".join(_TR_MONTHS + _EN_MONTHS) + r")[a-z']*\s+((?:19|20)\d{2})")


def _month(text):
    m = RE_MONTH_ISO.search(text)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = RE_MONTH_WORD.search(text)
    if m:
        word = m.group(1)
        i = (_TR_MONTHS.index(word) if word in _TR_MONTHS else _EN_MONTHS.index(word)) + 1
        return f"{m.group(2)}-{i:02d}"
    return None


def match_product(text, nodes):
    """The node a question names: its stock code, or the longest label (or 2+ leading label words) found in it.
    Returns (node id, matched text) or (None, None)."""
    best = None
    for n in nodes:
        label, code = fold(n["label"]), fold(n["id"])
        words = label.split()
        candidates = [label] + [" ".join(words[:k]) for k in range(len(words) - 1, 1, -1)]
        hit = next((c for c in candidates if len(c) >= 6 and re.search(r"(?<!\w)" + re.escape(c) + r"(?!\w)", text)), None)
        if re.search(r"(?<!\w)" + re.escape(code) + r"(?!\w)", text):
            hit = hit or code
        if hit and (best is None or len(hit) > best[0]):
            best = (len(hit), n["id"], hit)
    return (best[1], best[2]) if best else (None, None)


def local_plan(question, nodes):
    text = fold(question or "")
    product, named = match_product(text, nodes)
    # Numbers inside a product name ("3 TIER") or a month are not "how many results".
    rest = text.replace(named, " ") if named else text
    k_hit = RE_K.search(RE_MONTH_ISO.sub(" ", RE_MONTH_WORD.sub(" ", rest)))
    k = min(max(int(k_hit.group(1)), K_RANGE[0]), K_RANGE[1]) if k_hit else 5
    month = _month(text)
    if RE_UNSUPPORTED.search(text):
        return {"query": "unsupported", "k": k, "product": product, "month": month}
    if RE_CHANGES.search(text) or (month and not product):
        return {"query": "changes", "k": k, "product": None, "month": month}
    if product and (RE_NEIGHBORS.search(text) or not (RE_COMMUNITIES.search(text) or RE_BRIDGES.search(text) or RE_HUBS.search(text))):
        return {"query": "neighbors", "k": k, "product": product, "month": None}
    if RE_NEIGHBORS.search(text) and not product:
        return {"query": "clarify", "k": k, "product": None, "month": None}
    for query, pattern in (("communities", RE_COMMUNITIES), ("bridges", RE_BRIDGES), ("hubs", RE_HUBS), ("strongest_pairs", RE_STRONG)):
        if pattern.search(text):
            return {"query": query, "k": k, "product": None, "month": None}
    return {"query": "clarify", "k": k, "product": None, "month": None}


def validate_plan(plan, nodes, months):
    """A planner's output (local or model) must name a known query, an existing node and a month in the data."""
    if not isinstance(plan, dict) or set(plan) - {"query", "k", "product", "month"} or plan.get("query") not in QUERIES:
        raise ValueError("Invalid network plan")
    k = plan.get("k", 5)
    if type(k) is not int or not K_RANGE[0] <= k <= K_RANGE[1]:
        raise ValueError("Invalid network plan")
    ids = {n["id"] for n in nodes}
    if plan.get("product") is not None and plan["product"] not in ids:
        raise ValueError("Invalid network plan")
    if plan.get("month") is not None and plan["month"] not in months:
        raise ValueError("Invalid network plan")
    if plan["query"] == "neighbors" and plan.get("product") is None:
        raise ValueError("Invalid network plan")
    return {"query": plan["query"], "k": k, "product": plan.get("product"), "month": plan.get("month")}


def _months(m):
    import pandas as pd

    return [str(p) for p in pd.period_range(m["start"][:7], m["end"][:7], freq="M")]


def answer(request):
    from analysis import llm_routing
    from analysis.worker import graph, meta

    question = request.get("question")
    if not isinstance(question, str) or not question.strip() or len(question) > 500:
        raise ValueError("Soru 1–500 karakter olmalı." if request.get("locale") != "en" else "The question must be 1–500 characters.")
    en = request.get("locale") == "en"
    g = graph(request)
    m = meta(request["dataset"])
    months = _months(m)
    from analysis.adapted.guardrails import assess_input

    if not assess_input(question).allowed:
        return _out(request, g, {"query": "unsupported", "k": 5, "product": None, "month": None}, "local",
                    "Bu istek güvenlik kontrolünde durduruldu." if not en else "This request was stopped by the safety check.", [], [],
                    status="refused")
    plan, used, fallback = local_plan(question, g["nodes"]), "local", None
    local_ok = plan["query"] not in ("clarify",)
    if llm_routing.use_model("network_question", local_ok=local_ok):
        from analysis.llm import plan_network

        reply = plan_network(question, g["nodes"], months)
        llm_routing.record_usage(reply.get("telemetry"))
        if reply.get("status") == "planned":
            try:
                plan, used = validate_plan(reply["plan"], g["nodes"], months), "model"
            except ValueError:
                fallback = "invalid_plan"
        else:
            fallback = reply.get("status")
    plan = validate_plan(plan, g["nodes"], months)
    text, node_ids, edges = _compute(plan, g, request, m, en)
    out = _out(request, g, plan, used, text, node_ids, edges)
    out["routing"] = llm_routing.receipt("network_question", used, fallback=fallback)
    return out


def _out(request, g, plan, used, text, node_ids, edges, status="answered"):
    return {"version": VERSION, "question": request.get("question"), "plan": plan, "planner": used, "status": status,
            "answer": text, "highlight": {"nodes": node_ids, "edges": edges}, "mode": g["mode"],
            "filters": g.get("filters", {})}


def _label(g):
    return {n["id"]: n["label"] for n in g["nodes"]}


def _w(e, mode, en):
    if mode == "similarity":
        return f"{'similarity' if en else 'benzerlik'} {e['weight']:.2f}"
    return f"{int(e['weight'])} {'shared invoices' if en else 'ortak fatura'}"


def _compute(plan, g, request, m, en):
    names, mode, q, k = _label(g), g["mode"], plan["query"], plan["k"]
    edges = sorted(g["edges"], key=lambda e: (-abs(e["weight"]), e["source"], e["target"]))
    pair = lambda e: f"{names.get(e['source'], e['source'])} ↔ {names.get(e['target'], e['target'])} ({_w(e, mode, en)})"  # noqa: E731
    if not g["nodes"]:
        return (("There are no products to relate under these filters." if en else "Bu filtrelerle ilişki kurulacak ürün yok."), [], [])
    if q == "strongest_pairs":
        top = edges[:k]
        if not top:
            return (("No links at this threshold." if en else "Bu eşikte bağ yok."), [], [])
        lead = f"The {len(top)} strongest links: " if en else f"En güçlü {len(top)} bağ: "
        return lead + "; ".join(pair(e) for e in top) + ".", sorted({x for e in top for x in (e["source"], e["target"])}), [[e["source"], e["target"]] for e in top]
    if q == "neighbors":
        p = plan["product"]
        mine = [e for e in edges if p in (e["source"], e["target"])][:k]
        if not mine:
            return ((f"{names[p]} has no visible links at this threshold." if en else f"{names[p]} bu eşikte görünür bir bağa sahip değil."), [p], [])
        other = lambda e: e["target"] if e["source"] == p else e["source"]  # noqa: E731
        items = "; ".join(f"{names.get(other(e), other(e))} ({_w(e, mode, en)})" for e in mine)
        lead = f"Most often with {names[p]}: " if en else f"{names[p]} ile en çok: "
        return lead + items + ".", [p] + [other(e) for e in mine], [[e["source"], e["target"]] for e in mine]
    if q == "communities":
        groups = {}
        for n in g["nodes"]:
            groups.setdefault(n["community"], []).append(n)
        parts = []
        for cid in sorted(groups, key=lambda c: (-len(groups[c]), c)):
            members = sorted(groups[cid], key=lambda n: (-n["pence"], n["id"]))
            parts.append((f"community {cid + 1}: {len(members)} products, led by {members[0]['label']}" if en
                          else f"topluluk {cid + 1}: {len(members)} ürün, öne çıkan {members[0]['label']}"))
        lead = f"{len(groups)} communities — " if en else f"{len(groups)} topluluk — "
        tail = (" Communities are groups of products linked more to each other than to the rest; they are not customer segments."
                if en else " Topluluk, birbirine diğerlerinden daha sıkı bağlı ürün grubudur; müşteri segmenti değildir.")
        return lead + "; ".join(parts) + "." + tail, [n["id"] for n in g["nodes"]], []
    if q in ("bridges", "hubs"):
        key = "brokerage" if q == "bridges" else "degree"
        top = sorted(g["nodes"], key=lambda n: (-n[key], n["id"]))[:k]
        if q == "bridges":
            lead = "Bridge products (betweenness): " if en else "Köprü ürünler (aradalık): "
            tail = (" A bridge sits on many shortest paths between other products in this visible network."
                    if en else " Köprü ürün, bu görünür ağda diğer ürünler arasındaki en kısa yolların çoğunun üzerindedir.")
            items = "; ".join(f"{n['label']} ({n['brokerage']:.3f})" for n in top)
        else:
            lead = "Most connected products: " if en else "En çok bağlantılı ürünler: "
            tail = ""
            items = "; ".join(f"{n['label']} ({n['degree']} {'links' if en else 'bağ'})" for n in top)
        return lead + items + "." + tail, [n["id"] for n in top], []
    if q == "changes":
        return _changes(plan, g, request, m, en)
    if q == "unsupported":
        return (("The network shows which products appear on the same invoices; it cannot say why, and it has no customer, profit or forecast information. Try: the strongest links, what sells with a product, the communities or the bridge products."
                 if en else "Ağ, ürünlerin aynı faturalarda birlikte görülmesini gösterir; nedenini söyleyemez ve müşteri, kâr ya da tahmin bilgisi içermez. Şunları sorabilirsiniz: en güçlü bağlar, bir ürünle birlikte alınanlar, topluluklar veya köprü ürünler."), [], [])
    return (("Which product or which kind of answer do you mean? For example: 'strongest 5 pairs', 'what is bought with REGENCY CAKESTAND 3 TIER', 'how many communities', 'bridge products', 'which links appeared in 2011-11'."
             if en else "Hangi ürünü veya ne tür bir cevabı kastediyorsunuz? Örneğin: 'en güçlü 5 çift', 'REGENCY CAKESTAND 3 TIER ile birlikte ne alınıyor', 'kaç topluluk var', 'köprü ürünler', '2011-11'de hangi bağlar oluştu'."), [], [])


def _changes(plan, g, request, m, en):
    from analysis.temporal import analyze_temporal, edge_comparison
    from analysis.worker import DATA, filters_for

    months = _months(m)
    month = plan.get("month") or months[-2]  # the last complete month by default
    where, args, _ = filters_for(request, m)
    t = analyze_temporal({**request, "month": month, "window": 1, "min_shared": int(request.get("min_shared", 2))}, m, where, args, DATA)
    stages = {s["stage"]: s for s in t["stages"]}
    if "pre" in stages and stages["pre"]["months"]:
        a, b, la, lb = stages["pre"]["edges"], stages["shock"]["edges"], stages["pre"]["months"][0], month
    else:
        a, b, la, lb = stages["shock"]["edges"], stages["post"]["edges"], month, stages["post"]["months"][0]
    cmp = edge_comparison(a, b)
    names = {p["product_id"]: p["label"] for p in t["selected_products"]}
    wa = {(e["source"], e["target"]): e["weight"] for e in a}
    wb = {(e["source"], e["target"]): e["weight"] for e in b}
    # From the full edge sets (edge_comparison keeps only its 15 largest changes), largest first.
    new = sorted(({"source": k[0], "target": k[1], "before": 0, "after": w} for k, w in wb.items() if k not in wa),
                 key=lambda c: (-c["after"], c["source"], c["target"]))[: plan["k"]]
    lost = sorted(({"source": k[0], "target": k[1], "before": w, "after": 0} for k, w in wa.items() if k not in wb),
                  key=lambda c: (-c["before"], c["source"], c["target"]))[: plan["k"]]
    fmt = lambda c: f"{names.get(c['source'], c['source'])} ↔ {names.get(c['target'], c['target'])} ({c['before']} → {c['after']})"  # noqa: E731
    if en:
        text = (f"From {la} to {lb} on the same 24 products: {cmp['new_edges']} links appeared, {cmp['lost_edges']} disappeared,"
                f" {cmp['shared_edges']} stayed. Largest new: {'; '.join(fmt(c) for c in new) or 'none'}. Largest lost: {'; '.join(fmt(c) for c in lost) or 'none'}."
                " Months differ in length and coverage; a change is a description, not a cause.")
    else:
        text = (f"{la} → {lb}, aynı 24 ürün üzerinde: {cmp['new_edges']} bağ oluştu, {cmp['lost_edges']} bağ koptu, {cmp['shared_edges']} bağ sürdü."
                f" En büyük yeni bağlar: {'; '.join(fmt(c) for c in new) or 'yok'}. En büyük kopan bağlar: {'; '.join(fmt(c) for c in lost) or 'yok'}."
                " Ayların uzunluğu ve kapsamı farklıdır; değişim bir betimlemedir, neden değildir.")
    visible = {n["id"] for n in g["nodes"]}
    nodes = sorted({x for c in new + lost for x in (c["source"], c["target"]) if x in visible})
    return text, nodes, [[c["source"], c["target"]] for c in new + lost if c["source"] in visible and c["target"] in visible]
