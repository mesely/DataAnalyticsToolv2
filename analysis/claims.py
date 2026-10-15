"""Resolve declared numeric facts against computed artifacts; not a free-text LLM verifier."""

from decimal import Decimal, InvalidOperation


def verify_numeric_claims(claims, result):
    if not isinstance(claims, list) or not 1 <= len(claims) <= 8:
        return False
    for claim in claims:
        if not isinstance(claim, dict):
            return False
        value = claim.get("value")
        metric = claim.get("metric")
        scope = claim.get("scope") or {}
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float, Decimal))
            or not isinstance(scope, dict)
        ):
            return False
        try:
            number = Decimal(str(value))
            if not number.is_finite():
                return False
            if not scope:
                if (
                    metric not in {"gross_sales", "orders", "units", "aov"}
                    or "rank" in claim
                ):
                    return False
                expected = result["summary"][metric]
            elif set(scope) == {"product_id"} or set(scope) == {"country"}:
                if metric != "gross_sales":
                    return False
                is_product = "product_id" in scope
                key = "product_id" if is_product else "label"
                dimension = "product_id" if is_product else "country"
                rows = result["products"] if is_product else result["countries"]
                row = next((r for r in rows if r[key] == scope[dimension]), None)
                if row is None:
                    return False
                expected = Decimal(row["pence"]) / 100
                if "rank" in claim and (
                    claim["rank"] != 1 or row["pence"] != max(r["pence"] for r in rows)
                ):
                    return False
            else:
                return False
            if claim.get("unit") not in (
                None,
                "GBP" if metric in {"gross_sales", "aov"} else "count",
            ):
                return False
            if number != Decimal(str(expected)):
                return False
        except (KeyError, TypeError, ValueError, InvalidOperation):
            return False
    return True
