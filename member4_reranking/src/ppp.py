"""
Member 4 - Novelty 2 (part 1): PPP-normalized prices and category affordability tiers.

DISPLAY ONLY: nothing here changes the ranking. The order comes from Novelty 1 (relevance).

For each product, for the country of the user who searched (user_country):
  1. real price  = listing price -> user's currency with the live exchange rate (what the user pays;
                   a price already in the user's currency stays as it is)
  2. PPP price   = real price / PPP factor of the user's country -> international dollars
                   (= the team schema's `ppp_adjusted_price_usd`, "USD-equivalent")
  3. tier        = Budget / Mid-range / Premium: the real price compared with THAT country's own market
                   for the SAME category (reference list -> thirds, 33rd/67th percentile)

Rates: price_data/rates_snapshot.json (notebook 19_n2_rates; source + date for every value).
Reference lists: price_data/phone_reference_v1.csv (stand-in: phones only, 10 LK / 8 PK listings).
Live prices are never inflation-adjusted.
"""
from __future__ import annotations

import csv
import json
import os
import re
from typing import Dict, Optional

import numpy as np

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "price_data")
DEFAULT_SNAPSHOT = os.path.join(DATA_DIR, "rates_snapshot.json")
DEFAULT_REFERENCE = os.path.join(DATA_DIR, "phone_reference_v1.csv")
DOMAIN_TO_COUNTRY = {"daraz.lk": "LKA", "daraz.pk": "PAK"}
COUNTRY_NAME = {"LKA": "Sri Lanka", "PAK": "Pakistan"}
MIN_REFERENCE = 6                  # fewer reference prices for a (country, category) -> no tier
TIERS = ("Budget", "Mid-range", "Premium")


# ------------------------------------------------------------------ data
def load_snapshot(path: str = DEFAULT_SNAPSHOT) -> Dict:
    with open(path, encoding="utf-8") as f:
        snap = json.load(f)
    for iso, c in snap["countries"].items():
        for key in ("ppp_updated", "fx_per_usd_now", "currency"):
            if key not in c:
                raise ValueError(f"snapshot: {iso} has no '{key}'")
    return snap


def load_reference(path: str = DEFAULT_REFERENCE) -> Dict:
    """CSV (country, category, title, price, currency, ...) -> {(country, category): {"q1", "q2", "n"}}.
    Prices are in the country's own currency. Cut-offs = 33rd / 67th percentile."""
    prices: Dict = {}
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            prices.setdefault((r["country"].strip(), r["category"].strip()), []).append(float(r["price"]))
    ref = {}
    for key, v in prices.items():
        q1, q2 = np.quantile(np.array(v), [1 / 3, 2 / 3])
        ref[key] = {"q1": float(q1), "q2": float(q2), "n": len(v)}
    return ref


def fx_table(snap: Dict) -> Dict[str, float]:
    t = {"USD": 1.0}
    for c in snap["countries"].values():
        t[c["currency"]] = float(c["fx_per_usd_now"])
    return t


# ------------------------------------------------------------------ helpers
def parse_price(text) -> float:
    """'Rs. 111,999' -> 111999.0 ; 'LKR 1,958.58' -> 1958.58 ; 41899 -> 41899.0"""
    if isinstance(text, (int, float)):
        return float(text)
    m = re.search(r"\d[\d,]*(?:\.\d+)?", str(text))
    if not m:
        raise ValueError(f"no number in price {text!r}")
    return float(m.group().replace(",", ""))


def country_from_url(url: str) -> Optional[str]:
    for domain, iso in DOMAIN_TO_COUNTRY.items():
        if domain in str(url).lower():
            return iso
    return None


def convert(amount: float, from_cur: str, to_cur: str, snap: Dict) -> Optional[float]:
    t = fx_table(snap)
    f, to = (from_cur or "").upper(), (to_cur or "").upper()
    if f not in t or to not in t:
        return None
    return amount / t[f] * t[to]


_PHONE = re.compile(r"\b(smart ?phone|mobile phone|iphone|galaxy [asmz]\d|redmi|poco|infinix|tecno|realme|"
                    r"vivo [a-z]?\d|oppo|pixel \d|nokia [a-z]?\d|note \d+)", re.I)
_NOT_PHONE = re.compile(r"\b(case|cover|charger|cable|protector|tempered|glass|holder|stand|strap|adapter|"
                        r"earbuds?|headphones?|watch|band|tablet|pad\b|laptop|notebook)", re.I)


def tier_category(title: str, attributes: Optional[Dict]) -> Optional[str]:
    """Stand-in until M2/M3 give product categories: 'phones' from the category field or the title, else None."""
    cat = str((attributes or {}).get("category", "")).lower()
    if cat in ("phones", "phone", "smartphones", "cell phones & smartphones"):
        return "phones"
    if _PHONE.search(title or "") and not _NOT_PHONE.search(title or ""):
        return "phones"
    return None


# ------------------------------------------------------------------ main function
def price_view(amount: float, currency: str, user_iso: str, snap: Dict, ref: Optional[Dict] = None,
               category: Optional[str] = None) -> Optional[Dict]:
    """What a user in `user_iso` sees for one product. None if the currency is unknown."""
    c = snap["countries"][user_iso]
    real = convert(amount, currency, c["currency"], snap)
    if real is None:
        return None
    out = {"country": user_iso, "currency": c["currency"], "price": real,
           "ppp_intl_dollars": real / c["ppp_updated"], "tier": None, "tier_reference_n": 0}
    r = (ref or {}).get((user_iso, category)) if category else None
    if r and r["n"] >= MIN_REFERENCE:
        out["tier"] = TIERS[0] if real <= r["q1"] else (TIERS[1] if real <= r["q2"] else TIERS[2])
        out["tier_reference_n"] = r["n"]
    return out


# ------------------------------------------------------------------ automatic exchange-rate refresh
FX_URL = "https://open.er-api.com/v6/latest/USD"     # same source as the team backend (backend/app/services/fx.py)


def refresh_fx(snap: Dict, max_age_hours: float = 24.0, timeout: float = 5.0) -> bool:
    """Update the exchange rates inside `snap` if they are older than max_age_hours.
    PPP / CPI / income stay from the World Bank snapshot (they change yearly; run refresh_rates.py monthly).
    Any network problem -> keep the old rates (returns False). Never raises."""
    import datetime
    import httpx
    now = datetime.datetime.now(datetime.timezone.utc)
    last = snap.get("fx_fetched_at") or snap.get("created_at")
    try:
        if last and (now - datetime.datetime.fromisoformat(last)).total_seconds() < max_age_hours * 3600:
            return False
        data = httpx.get(FX_URL, timeout=timeout).json()
        if data.get("result") != "success":
            return False
        for c in snap["countries"].values():
            new = data["rates"].get(c["currency"])
            if new:
                c["fx_per_usd_now"] = float(new)
                c["price_level_ratio"] = round(c["ppp_updated"] / float(new), 4)
        snap["fx_as_of"] = data.get("time_last_update_utc")
        snap["fx_fetched_at"] = now.isoformat(timespec="seconds")
        return True
    except Exception:
        return False
