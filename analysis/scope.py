"""What a product analysis counts as a product (v3 G5).

Invoice lines in the retail data also carry postage, carriage, manual entries, fees and accounting adjustments under
their own stock codes. Gross sales (retail-v1) keeps them, and that stays the headline total. Product views — the
product ranking, the relationship network and the change-over-time network — leave them out by default, because
"which products sell the most?" answered with DOTCOM POSTAGE is a wrong answer, not a finding. The analyst can put
them back with `include_service`; the screen always says which way the view was computed and what was left out.
"""

# Stock codes (compared case-insensitively) that are not merchandise in the UCI Online Retail datasets, with the
# reason shown to the analyst. PADS ("PADS TO MATCH ALL CUSHIONS") is merchandise and deliberately absent.
SERVICE_CODES = {
    "POST": "shipping",
    "DOT": "shipping",
    "C2": "shipping",
    "M": "manual",
    "ADJUST": "adjustment",
    "B": "adjustment",
    "D": "discount",
    "CRUK": "fee",
    "BANK CHARGES": "fee",
    "AMAZONFEE": "fee",
    "S": "sample",
}

KIND_LABELS = {
    "shipping": ("Kargo ve posta", "Postage and carriage"),
    "manual": ("Elle girilmiş kalem", "Manual entry"),
    "adjustment": ("Muhasebe düzeltmesi", "Accounting adjustment"),
    "discount": ("İndirim", "Discount"),
    "fee": ("Ücret ve masraf", "Fees and charges"),
    "sample": ("Numune", "Samples"),
}


def _codes_sql():
    return ",".join("'" + c.replace("'", "''") + "'" for c in sorted(SERVICE_CODES))


def product_clause():
    """SQL predicate that keeps merchandise lines only (constant text; no user input)."""
    return f"UPPER(product_id) NOT IN ({_codes_sql()})"


def include_service(request):
    value = request.get("include_service", False)
    if not isinstance(value, bool):
        raise ValueError("include_service must be true or false.")
    return value


def with_products_only(where, request):
    """Extend a WHERE fragment (empty or starting with ' WHERE ') unless the request includes service lines."""
    if include_service(request):
        return where
    return where + (" AND " if where else " WHERE ") + product_clause()


def service_lines(con, where, args, locale="tr"):
    """Service lines inside the current filters, grouped by kind, for the scope disclosure."""
    rows = con.execute(
        f"SELECT UPPER(product_id) AS code,MIN(product) AS label,COUNT(*)::BIGINT AS lines,"
        f"COALESCE(SUM(line_pence),0)::BIGINT AS pence FROM transactions{where}"
        + (" AND " if where else " WHERE ")
        + f"UPPER(product_id) IN ({_codes_sql()}) GROUP BY 1 ORDER BY 4 DESC,1",
        args,
    ).fetchall()
    en = locale == "en"
    kinds = {}
    for code, label, lines, pence in rows:
        kind = SERVICE_CODES[code]
        k = kinds.setdefault(
            kind,
            {"kind": kind, "label": KIND_LABELS[kind][1 if en else 0], "lines": 0, "pence": 0, "codes": []},
        )
        k["lines"] += int(lines)
        k["pence"] += int(pence)
        k["codes"].append({"code": code, "label": label, "lines": int(lines), "pence": int(pence)})
    groups = sorted(kinds.values(), key=lambda k: (-k["pence"], k["kind"]))
    return {
        "lines": sum(k["lines"] for k in groups),
        "pence": sum(k["pence"] for k in groups),
        "groups": groups,
    }
