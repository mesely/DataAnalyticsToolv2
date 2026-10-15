"""Dataset-scoped lexical context search, using the actual adviSU BM25 kernel."""

import re, unicodedata
from analysis.adapted.lexical import _BM25


def tokens(text):
    text = unicodedata.normalize("NFKD", str(text).casefold().replace("ı", "i"))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9_]+", text)


def search_context(query, metadata, metrics):
    if not isinstance(query, str) or len(query) > 300:
        raise ValueError("Arama en fazla 300 karakter.")
    documents = [
        {
            "id": m["id"],
            "kind": "metric",
            "title": m["title"],
            "body": m["formula"] + " · " + m["note"],
            "terms": {
                "gross_sales": "gross sales revenue brut satis ciro",
                "orders": "orders siparis fatura invoice",
                "units": "units adet miktar quantity",
                "aov": "average order value ortalama siparis",
            }.get(m["id"], ""),
        }
        for m in metrics
    ]
    documents += [
        {
            "id": c["name"],
            "kind": "column",
            "title": c["name"],
            "body": c["type"] + " · transactions." + c["name"],
            "terms": "",
        }
        for c in metadata["schema"]
        if c["name"] != "customer_id"
    ]
    documents.append(
        {
            "id": "source",
            "kind": "source",
            "title": metadata["title"],
            "body": metadata["definition"]
            + " "
            + metadata["source"].get("description", ""),
            "terms": metadata["source"]["publisher"],
        }
    )
    scores = _BM25(
        [tokens(x["title"] + " " + x["body"] + " " + x["terms"]) for x in documents]
    ).scores(tokens(query))
    # Exact normalized titles get a small navigation boost over incidental mentions.
    scores = [
        score + 3 if tokens(query) == tokens(doc["title"]) else score
        for score, doc in zip(scores, documents)
    ]
    return [
        {
            "id": x["id"],
            "kind": x["kind"],
            "title": x["title"],
            "body": x["body"],
            "score": round(score, 5),
            "dataset_sha256": metadata["sha256"],
        }
        for score, x in sorted(zip(scores, documents), key=lambda p: -p[0])
        if score > 0
    ][:8]
