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


# Metric definitions (v3, AW-21). retail-v1 is every positive, non-cancelled invoice line and stays the default, so
# earlier results, digests and saved findings keep their meaning. retail-v2 ("customer sales") leaves out lines that
# are not something a customer bought or was billed for: accounting adjustments ("Adjust bad debt") and marketplace or
# bank fees ("AMAZON FEE", "Bank Charges", "CRUK Commission"). Postage, carriage and manual lines are billed to
# customers and stay in retail-v2; product views leave them out separately (merchandise only, above).
DEFINITIONS = ("retail-v1", "retail-v2")
DEFAULT_DEFINITION = "retail-v1"
V2_EXCLUDED_KINDS = ("adjustment", "fee")


def _codes_sql(kinds=None):
    codes = sorted(c for c, k in SERVICE_CODES.items() if kinds is None or k in kinds)
    return ",".join("'" + c.replace("'", "''") + "'" for c in codes)


def definition(value):
    """Validated metric definition (None or "" means the default)."""
    if value in (None, ""):
        return DEFAULT_DEFINITION
    if value not in DEFINITIONS:
        raise ValueError("Bilinmeyen ölçü tanımı.")
    return value


def definition_clause(value):
    """SQL predicate a definition adds to every query (constant text; no user input), or None for retail-v1."""
    if definition(value) == "retail-v2":
        return f"UPPER(product_id) NOT IN ({_codes_sql(V2_EXCLUDED_KINDS)})"
    return None


def reconciliation(con, where, args):
    """How the totals inside the current filters relate, line by line (v3, AW-21):

    retail-v1 = retail-v2 + adjustments + fees; retail-v2 = merchandise + postage/carriage + manual + samples.
    `where`/`args` must not already contain the definition clause. Cancellations and non-positive lines never
    reach the transactions table; their dataset-wide counts are in the dataset's quality block.
    """
    row = con.execute(
        "SELECT COUNT(*)::BIGINT, COALESCE(SUM(line_pence),0)::BIGINT FROM transactions" + where, args
    ).fetchone()
    kinds = {k: {"lines": 0, "pence": 0} for k in sorted(set(SERVICE_CODES.values()))}
    for code, lines, pence in con.execute(
        "SELECT UPPER(product_id), COUNT(*)::BIGINT, COALESCE(SUM(line_pence),0)::BIGINT FROM transactions" + where
        + (" AND " if where else " WHERE ") + f"UPPER(product_id) IN ({_codes_sql()}) GROUP BY 1",
        args,
    ).fetchall():
        kinds[SERVICE_CODES[code]]["lines"] += int(lines)
        kinds[SERVICE_CODES[code]]["pence"] += int(pence)
    v1 = {"lines": int(row[0]), "pence": int(row[1])}
    off_v2 = {k: sum(kinds[x][k] for x in V2_EXCLUDED_KINDS) for k in ("lines", "pence")}
    v2 = {k: v1[k] - off_v2[k] for k in v1}
    service_v2 = {k: sum(kinds[x][k] for x in kinds if x not in V2_EXCLUDED_KINDS) for k in ("lines", "pence")}
    merchandise = {k: v2[k] - service_v2[k] for k in v2}
    return {"retail_v1": v1, "retail_v2": v2, "merchandise": merchandise, "kinds": kinds,
            "v2_excluded_kinds": list(V2_EXCLUDED_KINDS)}


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
