"""Reference knowledge the analyses can use (v3 G7/G9): versioned tables with their source, never free text.

A question that needs outside knowledge ("which countries are in NATO?") is answered from a table here, at a stated
date, with the countries that could not be matched listed — never from a model's memory. Each table carries its
source, version and SHA-256, and `catalog()` lists them as cards (what a planner may refer to).
"""
from __future__ import annotations

import functools
import hashlib
import json
from datetime import date
from pathlib import Path

REF = Path(__file__).resolve().parent
GROUP_IDS = ("nato", "eu", "eurozone", "g7", "oecd", "continent")
AS_OF = ("period_end", "today")


@functools.lru_cache(maxsize=1)
def _groups_raw():
    raw = (REF / "country_groups.json").read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def groups():
    return _groups_raw()[0]


def card(group, locale="tr"):
    data, digest = _groups_raw()
    i = 1 if locale == "en" else 0
    if group == "continent":
        label, source = data["continents"]["label"][i], "ISO 3166 / UN M49 continental regions"
    else:
        g = data["groups"][group]
        label, source = g["label"][i], g["source"]
    return {"id": "country-groups", "group": group, "label": label, "source": source, "version": data["version"],
            "sha256": digest, "kind": data["kind"]}


def catalog(locale="tr"):
    """Cards for every reference table a planner may use (the retrieval surface: ids, labels, sources only)."""
    return [card(g, locale) for g in GROUP_IDS]


def resolve_as_of(as_of, period_end):
    if as_of == "today":
        return date.today()
    return date.fromisoformat(str(period_end))


def classify(group, countries, on, locale="tr"):
    """Bucket per dataset country for `group` on date `on`.

    Binary groups give "member" / "outside" / "unmatched"; continents give the continent id or "unmatched".
    Returns {country: {"bucket", "iso3", "note"}}.
    """
    if group not in GROUP_IDS:
        raise ValueError("Unknown reference group.")
    data = groups()
    i = 1 if locale == "en" else 0
    out = {}
    for country in countries:
        info = data["dataset_countries"].get(country)
        if info is None:
            out[country] = {"bucket": "unmatched", "iso3": None,
                            "note": "Referans tabloda eşleme yok" if i == 0 else "No match in the reference table"}
            continue
        if group == "continent":
            bucket = info.get("continent") or "unmatched"
            note = info["unmatched"][i] if bucket == "unmatched" and info.get("unmatched") else None
            out[country] = {"bucket": bucket, "iso3": info.get("iso3"), "note": note}
            continue
        if not info.get("iso3"):
            out[country] = {"bucket": "unmatched", "iso3": None, "note": (info.get("unmatched") or [None, None])[i]}
            continue
        span = data["groups"][group]["members"].get(info["iso3"])
        member = bool(span) and date.fromisoformat(span[0]) <= on and (span[1] is None or on < date.fromisoformat(span[1]))
        note = None
        if span and not member:
            note = (f"Üyelik {span[0]} tarihinde başladı" if on < date.fromisoformat(span[0]) else f"Üyelik {span[1]} tarihinde bitti") if i == 0 else (
                f"Membership began on {span[0]}" if on < date.fromisoformat(span[0]) else f"Membership ended on {span[1]}")
        out[country] = {"bucket": "member" if member else "outside", "iso3": info["iso3"], "note": note}
    return out


def bucket_label(group, bucket, locale="tr"):
    data = groups()
    i = 1 if locale == "en" else 0
    if bucket == "unmatched":
        return "Eşleşmeyen" if i == 0 else "Unmatched"
    if group == "continent":
        return data["continents"]["names"][bucket][i]
    g = data["groups"][group]
    return g["label"][i] if bucket == "member" else g["outside"][i]
