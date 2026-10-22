"""Money transforms for a chart (v3 G9, AW-20): another currency, constant prices, gold, an index.

A transform never changes which rows are counted; it multiplies each order's GBP value by a factor fixed by the
order's date, then the chart aggregates as before. Factors come only from the downloaded reference tables in
`analysis/reference/` (ECB rates, OECD CPI, World Bank gold), never from a model or a contemporary value applied to
history unless the request says so ("at today's rate").

Definitions (every step is deterministic and named on screen):
- currency, fx="transaction": value_C = value_GBP × (C per EUR) / (GBP per EUR) on the order's date; a date
  without an ECB fixing (weekend, TARGET holiday) uses the last fixing before it, at most 7 days back.
- currency, fx="latest": value_C = value_GBP × the same cross rate on the latest fixing in the table. Only on an
  explicit "today's rate" request; it cannot be combined with constant prices.
- real=<base>: value × CPI_C(base) / CPI_C(order month), with the CPI of the currency shown (GBP → UK,
  TRY → Türkiye, USD → United States, EUR → euro area). The base is a month (YYYY-MM), a year (YYYY: the mean of its
  twelve monthly values) or "latest" (the series' last published month). A month the CPI series does not cover is
  refused, never extrapolated.
- unit="gold_g" | "gold_oz": value in gold = value_USD on the order's date / gold USD per troy ounce (World Bank
  monthly average of the order's month), × 31.1034768 for grams. Gold is its own unit: it does not combine with a
  currency or constant prices.
- index: each series divided by its first non-zero period and × 100 (time axes only), after the steps above.
- compare: draw the nominal series next to the constant-price one (needs `real`, a time axis, one series).
"""
from __future__ import annotations

import functools
import hashlib
import json
import re
from datetime import date, timedelta

from analysis.reference import REF

CURRENCIES = ("GBP", "TRY", "USD", "EUR")
FX_RULES = ("transaction", "latest")
UNITS = ("money", "gold_g", "gold_oz")
KEYS = ("currency", "fx", "real", "unit", "index", "compare")
GRAMS_PER_TROY_OUNCE = 31.1034768
MAX_CARRY_DAYS = 7
SYMBOL = {"GBP": "£", "TRY": "₺", "USD": "$", "EUR": "€"}
CPI_AREA = {"GBP": ["Birleşik Krallık", "United Kingdom"], "TRY": ["Türkiye", "Türkiye"],
            "USD": ["ABD", "United States"], "EUR": ["Euro bölgesi", "euro area"]}

_T = {
    "tr": {
        "object": "transform bir nesne olmalı.",
        "keys": "transform içinde bilinmeyen alan: {keys}.",
        "enum": "transform.{field} geçersiz: {value}.",
        "bool": "transform.{field} doğru/yanlış olmalı.",
        "base": "Sabit fiyat bazı YYYY-AA (ör. 2011-01), YYYY (yıl ortalaması) ya da 'latest' olmalı.",
        "money_only": "Dönüşüm yalnız tutar ölçülerine uygulanır (brüt satış, ortalama sipariş); {metric} için kaldırıldı.",
        "gold_mix": "Altın kendi birimidir; para birimi ve sabit fiyat seçimi altınla birlikte uygulanmaz, kaldırıldı.",
        "latest_real": "Bugünkü kurla çevirme ile enflasyon düzeltmesi birlikte uygulanmaz; işlem günü kuru kullanıldı.",
        "fx_gbp": "Sterlin kaynak birim; kur kuralı yok sayıldı.",
        "index_time": "Endeks (ilk dönem = 100) yalnız zaman ekseninde uygulanır; kaldırıldı.",
        "compare_need": "Nominal–reel karşılaştırma sabit fiyat seçimi, zaman ekseni ve tek seri gerektirir; kaldırıldı.",
        "cpi_gap": "{area} TÜFE serisi {first} – {last} aylarını kapsıyor; {month} için değer yok. Tarih aralığını daraltın veya baz ayını değiştirin.",
        "fx_gap": "{day} için {n} gün içinde ECB kuru yok; dönüşüm yapılamadı.",
        "gold_gap": "Altın serisi {first} – {last} aylarını kapsıyor; {month} için değer yok.",
    },
    "en": {
        "object": "transform must be an object.",
        "keys": "Unknown field in transform: {keys}.",
        "enum": "Invalid transform.{field}: {value}.",
        "bool": "transform.{field} must be true or false.",
        "base": "The constant-price base must be YYYY-MM (e.g. 2011-01), YYYY (annual mean) or 'latest'.",
        "money_only": "Transforms apply to money measures only (gross sales, average order value); removed for {metric}.",
        "gold_mix": "Gold is a unit of its own; a currency or constant-price choice does not combine with gold and was removed.",
        "latest_real": "Converting at today's rate does not combine with inflation adjustment; the rate of each order's date was used.",
        "fx_gbp": "Sterling is the source currency; the rate rule was ignored.",
        "index_time": "An index (first period = 100) needs a time axis; removed.",
        "compare_need": "Nominal vs real needs a constant-price choice, a time axis and a single series; removed.",
        "cpi_gap": "The {area} CPI series covers {first} – {last}; there is no value for {month}. Narrow the dates or change the base month.",
        "fx_gap": "No ECB rate within {n} days of {day}; the conversion cannot be made.",
        "gold_gap": "The gold series covers {first} – {last}; there is no value for {month}.",
    },
}


def _loc(locale):
    return "en" if locale == "en" else "tr"


# ------------------------------------------------------------------------------------------- tables

@functools.lru_cache(maxsize=None)
def table(name: str) -> tuple[dict, str]:
    raw = (REF / name).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def fx_table():
    return table("fx_ecb.json")


def cpi_table():
    return table("cpi_oecd.json")


def gold_table():
    return table("gold_worldbank.json")


@functools.lru_cache(maxsize=1)
def _fx_index():
    """{fixing day: {currency: units per EUR}} from the table's rows (columns: date, GBP, USD, TRY)."""
    data, _ = fx_table()
    names = data["columns"][1:]
    return {row[0]: dict(zip(names, row[1:])) for row in data["rows"]}


def fixing(day: date) -> str | None:
    """The ECB fixing date used for `day`: that day or the last one before it, at most MAX_CARRY_DAYS back."""
    index = _fx_index()
    for back in range(MAX_CARRY_DAYS + 1):
        key = (day - timedelta(days=back)).isoformat()
        if key in index:
            return key
    return None


def cross_rate(currency: str, fixing_day: str) -> float:
    """Units of `currency` per 1 GBP on an ECB fixing day."""
    if currency == "GBP":
        return 1.0
    day = _fx_index()[fixing_day]
    target = 1.0 if currency == "EUR" else day[currency]
    return target / day["GBP"]


def latest_fixing() -> str:
    return fx_table()[0]["rows"][-1][0]


def cpi(currency: str) -> dict[str, float]:
    return cpi_table()[0]["months"][currency]


def gold_usd() -> dict[str, float]:
    return gold_table()[0]["months"]


# ------------------------------------------------------------------------------------------- spec

def default() -> dict:
    return {"currency": "GBP", "fx": "transaction", "real": None, "unit": "money", "index": False, "compare": False}


def is_identity(tr: dict | None) -> bool:
    return not tr or tr == default()


def validate(obj, *, metric: str, time_axis: bool, single_series: bool, money_metrics, locale="tr",
             warnings: list | None = None) -> dict | None:
    """Normalized transform or None (no transform). Unknown keys and values are rejected; combinations without a
    safe reading are dropped with a warning (gold + currency, today's rate + constant prices, ...)."""
    t = _T[_loc(locale)]
    out = warnings if warnings is not None else []
    if obj is None:
        return None
    if not isinstance(obj, dict):
        raise ValueError(t["object"])
    unknown = sorted(str(k) for k in obj if k not in KEYS)
    if unknown:
        raise ValueError(t["keys"].format(keys=", ".join(unknown)[:120]))
    tr = default()
    for field, allowed in (("currency", CURRENCIES), ("fx", FX_RULES), ("unit", UNITS)):
        if field in obj and obj[field] is not None:
            if not isinstance(obj[field], str) or obj[field] not in allowed:
                raise ValueError(t["enum"].format(field=field, value=str(obj[field])[:40]))
            tr[field] = obj[field]
    for field in ("index", "compare"):
        if field in obj and obj[field] is not None:
            if not isinstance(obj[field], bool):
                raise ValueError(t["bool"].format(field=field))
            tr[field] = obj[field]
    real = obj.get("real")
    if real is not None:
        if not isinstance(real, str) or not (real == "latest" or re.fullmatch(r"(19|20)\d{2}(-(0[1-9]|1[0-2]))?", real)):
            raise ValueError(t["base"])
        tr["real"] = real
    if is_identity(tr):
        return None
    if metric not in money_metrics:
        out.append(t["money_only"].format(metric=metric))
        return None
    if tr["unit"] != "money" and (tr["currency"] != "GBP" or tr["real"]):
        tr["currency"], tr["real"] = "GBP", None
        out.append(t["gold_mix"])
    if tr["fx"] == "latest" and tr["real"]:
        tr["fx"] = "transaction"
        out.append(t["latest_real"])
    if tr["currency"] == "GBP" and tr["fx"] != "transaction":
        tr["fx"] = "transaction"
        if tr["unit"] == "money":
            out.append(t["fx_gbp"])
    if tr["index"] and not time_axis:
        tr["index"] = False
        out.append(t["index_time"])
    if tr["compare"] and not (tr["real"] and time_axis and single_series):
        tr["compare"] = False
        out.append(t["compare_need"])
    return None if is_identity(tr) else tr


def unit_of(tr: dict | None, metric_is_money: bool = True) -> str:
    """Display unit: GBP/TRY/USD/EUR, g or oz of gold, or 'index'."""
    if not metric_is_money:
        return "count"
    if not tr:
        return "GBP"
    if tr["index"]:
        return "index"
    return {"gold_g": "g", "gold_oz": "oz"}.get(tr["unit"], tr["currency"])


def base_month(tr: dict) -> str | None:
    """The constant-price base: a month (YYYY-MM) or a year (YYYY)."""
    if not tr or not tr["real"]:
        return None
    return max(cpi(tr["currency"])) if tr["real"] == "latest" else tr["real"]


def base_value(series: dict[str, float], base: str) -> float | None:
    """CPI of the base: the month's value, or the mean of a year's twelve months (None when not all published)."""
    if len(base) == 7:
        return series.get(base)
    months = [series.get(f"{base}-{m:02d}") for m in range(1, 13)]
    return None if any(v is None for v in months) else sum(months) / 12


# ------------------------------------------------------------------------------------------- factors

def factors(tr: dict, days, locale="tr") -> tuple[list[tuple[str, float, float]], dict]:
    """(day, factor, nominal_factor) for every order day in `days` (ISO dates), and the provenance of the numbers used.

    `factor` turns a GBP amount on that day into the chart's unit; `nominal_factor` is the same without the
    constant-price step (equal to `factor` when there is none). Raises ValueError (localized) when a reference
    series does not cover a needed day or month."""
    t = _T[_loc(locale)]
    currency, gold = tr["currency"], tr["unit"] != "money"
    base = base_month(tr)
    cpi_series = cpi(currency) if tr["real"] else None
    cpi_base = base_value(cpi_series, base) if cpi_series is not None else None
    if cpi_series is not None and cpi_base is None:
        months = sorted(cpi_series)
        raise ValueError(t["cpi_gap"].format(area=CPI_AREA[currency][1 if locale == "en" else 0],
                                             first=months[0], last=months[-1], month=base))
    gold_series = gold_usd() if gold else None
    latest = latest_fixing() if tr["fx"] == "latest" else None
    out, used_fixings, carried, rates, months_used = [], set(), 0, [], set()
    for key in sorted({str(d) for d in days}):
        day = date.fromisoformat(key)
        month = key[:7]
        if gold:
            fix = fixing(day)
            if fix is None:
                raise ValueError(t["fx_gap"].format(day=key, n=MAX_CARRY_DAYS))
            if month not in gold_series:
                months = sorted(gold_series)
                raise ValueError(t["gold_gap"].format(first=months[0], last=months[-1], month=month))
            usd = cross_rate("USD", fix)
            per_oz = usd / gold_series[month]
            f = per_oz * (GRAMS_PER_TROY_OUNCE if tr["unit"] == "gold_g" else 1.0)
            nominal = f
            rates.append(usd)
        else:
            fix = latest if latest else (fixing(day) if currency != "GBP" else None)
            if currency != "GBP" and fix is None:
                raise ValueError(t["fx_gap"].format(day=key, n=MAX_CARRY_DAYS))
            rate = cross_rate(currency, fix) if currency != "GBP" else 1.0
            nominal = rate
            if cpi_series is not None:
                if month not in cpi_series:
                    months = sorted(cpi_series)
                    raise ValueError(t["cpi_gap"].format(area=CPI_AREA[currency][1 if locale == "en" else 0],
                                                         first=months[0], last=months[-1], month=month))
                f = rate * cpi_base / cpi_series[month]
            else:
                f = rate
            if currency != "GBP":
                rates.append(rate)
        if fix and fix != key and not latest:
            carried += 1
        if fix:
            used_fixings.add(fix)
        months_used.add(month)
        out.append((key, f, nominal))
    return out, provenance(tr, sorted(used_fixings), carried, rates, sorted(months_used), base, locale)


def provenance(tr, fixings, carried, rates, months, base, locale="tr") -> dict:
    i = 1 if locale == "en" else 0
    sources = []
    p = {"currency": tr["currency"], "fx": tr["fx"], "real": tr["real"], "base_month": base, "unit": tr["unit"],
         "index": tr["index"], "compare": tr["compare"], "sources": sources}
    if tr["currency"] != "GBP" or tr["unit"] != "money":
        data, digest = fx_table()
        quote = "USD" if tr["unit"] != "money" else tr["currency"]
        sources.append({"id": data["id"], "title": data["title"][i], "publisher": data["publisher"], "url": data["url"],
                        "licence": data["licence"], "retrieved_at": data["retrieved_at"], "sha256": digest,
                        "series": [data["series_ids"]["GBP"]] + ([data["series_ids"][quote]] if quote != "EUR" else []),
                        "version": data["version"]})
        p["fx_rule"] = "latest" if tr["fx"] == "latest" else "transaction_day"
        p["fixings"] = {"first": fixings[0], "last": fixings[-1], "count": len(fixings)} if fixings else None
        p["days_carried_forward"] = carried
        if rates:
            p["rate"] = {"quote": quote, "per": "GBP", "min": round(min(rates), 6), "max": round(max(rates), 6),
                         "mean": round(sum(rates) / len(rates), 6)}
    if tr["real"]:
        data, digest = cpi_table()
        series = data["months"][tr["currency"]]
        sources.append({"id": data["id"], "title": data["title"][i], "publisher": data["publisher"], "url": data["url"],
                        "licence": data["licence"], "retrieved_at": data["retrieved_at"], "sha256": digest,
                        "series": [data["series_ids"][tr["currency"]]], "version": data["version"]})
        p["cpi"] = {"area": CPI_AREA[tr["currency"]][i], "base_month": base, "base_value": base_value(series, base),
                    "base_rule": "annual mean of 12 months" if len(base) == 4 else "month",
                    "first_month": months[0], "first_value": series.get(months[0]),
                    "last_month": months[-1], "last_value": series.get(months[-1]), "unit": data["unit"]}
    if tr["unit"] != "money":
        data, digest = gold_table()
        prices = [data["months"][m] for m in months if m in data["months"]]
        sources.append({"id": data["id"], "title": data["title"][i], "publisher": data["publisher"], "url": data["url"],
                        "licence": data["licence"], "retrieved_at": data["retrieved_at"], "sha256": digest,
                        "series": [data["series_ids"]["USD"]], "version": data["version"]})
        p["gold"] = {"unit": "g" if tr["unit"] == "gold_g" else "troy oz", "price_unit": data["unit"],
                     "min": min(prices), "max": max(prices), "months": len(prices),
                     "grams_per_troy_ounce": GRAMS_PER_TROY_OUNCE}
    return p


def _n(value: float, decimals: int, locale: str) -> str:
    text = f"{value:,.{decimals}f}"
    return text if locale == "en" else text.translate(str.maketrans(",.", ".,"))


CURRENCY_NAME = {"GBP": ["sterlin", "GBP"], "TRY": ["TL", "TRY"], "USD": ["ABD doları", "USD"], "EUR": ["avro", "EUR"]}


def describe(p: dict, locale="tr") -> str:
    """One sentence naming every reference value used (shown under the chart and in the statements)."""
    en = locale == "en"
    parts = []
    cur = CURRENCY_NAME[p["currency"]][1 if en else 0]
    if p["unit"] != "money":
        g = p["gold"]
        parts.append((("Amounts are expressed in {u} of gold: each order's value is converted to US dollars at the ECB "
                      "rate of its date and divided by the World Bank monthly average gold price of its month "
                      "(${lo}–${hi} per troy ounce; 1 oz = 31.1034768 g).") if en else
                     ("Tutarlar altın {u} cinsinden: her siparişin değeri kendi tarihindeki ECB kuruyla ABD dolarına "
                      "çevrildi ve kendi ayının Dünya Bankası aylık ortalama altın fiyatına bölündü "
                      "(ons başına {lo}–{hi} $; 1 ons = 31,1034768 g).")).format(
            u=("grams" if g["unit"] == "g" else "troy ounces") if en else ("gramı" if g["unit"] == "g" else "onsu"),
            lo=_n(g["min"], 0, locale), hi=_n(g["max"], 0, locale)))
    elif p["currency"] != "GBP":
        r = p.get("rate") or {}
        lo, hi, mean = (_n(r.get(k, 0), 4, locale) for k in ("min", "max", "mean"))
        carried = p["days_carried_forward"]
        if p["fx"] == "latest":
            parts.append((f"Converted to {cur} at the latest ECB rate ({p['fixings']['last']}: {mean} {cur} per GBP) — "
                          "today's rate applied to every date, not the rate of the order's date.") if en else
                         (f"Tutarlar en son ECB kuruyla ({p['fixings']['last']}: 1 GBP = {mean} {cur}) {cur} cinsine "
                          "çevrildi — her tarihe siparişin günündeki değil, bugünkü kur uygulandı."))
        else:
            parts.append((f"Converted to {cur} at the ECB reference rate of each order's date ({lo}–{hi} {cur} per GBP"
                          + (f"; {carried} order days without a fixing used the previous fixing" if carried else "")
                          + ").") if en else
                         (f"Tutarlar her siparişin tarihindeki ECB referans kuruyla {cur} cinsine çevrildi "
                          f"(1 GBP = {lo}–{hi} {cur}"
                          + (f"; kur yayımlanmayan {carried} sipariş gününde önceki iş günü kuru kullanıldı" if carried else "")
                          + ")."))
    if p.get("cpi"):
        c = p["cpi"]
        parts.append((f"Constant {c['base_month']} prices: × {c['area']} CPI ({c['base_month']} = "
                      f"{_n(c['base_value'], 2, locale)}) / CPI of the order's month (OECD, 2015 = 100).") if en else
                     (f"{c['base_month']} sabit fiyatları: × {c['area']} TÜFE ({c['base_month']} = "
                      f"{_n(c['base_value'], 2, locale)}) / siparişin ayının TÜFE'si (OECD, 2015 = 100)."))
    if p["index"]:
        parts.append("Each series is indexed to its first period = 100." if en else
                     "Her seri ilk dönemine göre endekslendi (ilk dönem = 100).")
    return " ".join(parts)


def label(tr: dict | None, locale="tr") -> str | None:
    """Short chip text, e.g. "TL · işlem günü kuru · 2025-12 fiyatlarıyla"."""
    if not tr:
        return None
    en = locale == "en"
    bits = []
    if tr["unit"] != "money":
        bits.append(("gold, grams" if tr["unit"] == "gold_g" else "gold, troy oz") if en else
                    ("altın, gram" if tr["unit"] == "gold_g" else "altın, ons"))
    elif tr["currency"] != "GBP":
        name = {"TRY": "TL", "USD": "USD", "EUR": "EUR"}[tr["currency"]]
        bits.append(name + (" · " + ("today's rate" if en else "bugünkü kur") if tr["fx"] == "latest" else
                            " · " + ("rate of the day" if en else "işlem günü kuru")))
    if tr["real"]:
        base = base_month(tr)
        bits.append(f"{base} prices" if en else f"{base} fiyatlarıyla")
    if tr["compare"]:
        bits.append("nominal vs real" if en else "nominal ve reel")
    if tr["index"]:
        bits.append("index = 100" if en else "endeks = 100")
    return " · ".join(bits)


def format_value(value: float, unit: str, locale: str, signed: bool = False, num=None) -> str:
    """Localized text of a transformed value: ₺1.234,56 / $1,234.56 / 12,345 g / 104.2."""
    sign = "-" if value < 0 and round(abs(value), 2) != 0 else ("+" if signed and value > 0 else "")
    body = num(abs(value), 2 if unit in SYMBOL or unit == "oz" else 1, locale)
    if unit in SYMBOL:
        return sign + SYMBOL[unit] + body
    if unit in ("g", "oz"):
        return f"{sign}{body} {unit}"
    return sign + body
