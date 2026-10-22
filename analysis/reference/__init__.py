"""Reference knowledge the analyses can use (v3 G7/G9): versioned tables with their source, never free text.

A question that needs outside knowledge ("which countries are in NATO?") is answered from a table here, at a stated
date, with the countries that could not be matched listed — never from a model's memory. Each table carries its
source, version and SHA-256, and `catalog()` lists them as cards (what a planner may refer to).
"""
from __future__ import annotations

import functools
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

REF = Path(__file__).resolve().parent
GROUP_IDS = ("nato", "eu", "eurozone", "g7", "oecd", "continent")
# transaction: each order is classified by the membership on its own date (the default since AW-22);
# period_end: one membership, at the end of the chart's period; today: today's membership.
AS_OF = ("transaction", "period_end", "today")
DEFAULT_AS_OF = "transaction"


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


def spans(group, countries, lo, hi, locale="tr"):
    """Membership by date for an order-date classification (AW-22): for each country, the consecutive date ranges
    inside [lo, hi] over which its bucket is constant, as (country, bucket, valid_from, valid_to, note) with ISO
    dates. A country whose membership began or ended inside the range gets two ranges; nothing is extrapolated."""
    lo, hi = date.fromisoformat(str(lo)), date.fromisoformat(str(hi))
    data = groups()
    out = []
    for country in countries:
        cuts = {lo}
        info = data["dataset_countries"].get(country) or {}
        if group != "continent" and info.get("iso3"):
            span = data["groups"][group]["members"].get(info["iso3"])
            for edge in (span or [])[:2]:
                if edge and lo < date.fromisoformat(edge) <= hi:
                    cuts.add(date.fromisoformat(edge))
        starts = sorted(cuts)
        for i, start in enumerate(starts):
            end = (starts[i + 1] - timedelta(days=1)) if i + 1 < len(starts) else hi
            c = classify(group, [country], start, locale)[country]
            out.append((country, c["bucket"], start.isoformat(), end.isoformat(), c["note"]))
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
