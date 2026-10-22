"""
Member 4 - Novelty 2 (part 2): estimated PAYABLE price for a Sri Lankan buyer (landed cost).

payable = item price + shipping (+ import taxes if the item ships from abroad and tax is not already included)

Rules (each charge is added only once):
  - item located in Sri Lanka, or tax_included = True   -> no import taxes (local price already includes them)
  - item located abroad                                  -> CIF = price + shipping, then CID, PAL, CESS, SSCL, VAT
                                                            (rates from price_data/lk_import_rates.json, per category)
  - shipping given                                       -> used
  - shipping included / free                             -> 0
  - shipping unknown                                     -> 0 and flagged "shipping_unknown" (never invented)
  - origin unknown                                       -> platform default (daraz = local, ebay/aliexpress = abroad),
                                                            flagged "origin_assumed"
  - no tax rates for the category                        -> taxes not estimated, flagged "tax_rate_missing"
Every result carries a breakdown so the user (and the panel) can see how the price was built.
DISPLAY ONLY: the payable price never changes the ranking.
"""
from __future__ import annotations

import json
import os
import re
from typing import Dict, Optional

DEFAULT_RATES = os.path.join(os.path.dirname(__file__), "..", "price_data", "lk_import_rates.json")
LOCAL_PLATFORMS = {"daraz"}
IMPORT_PLATFORMS = {"ebay", "aliexpress", "alibaba"}
SRI_LANKA = {"lk", "lka", "sri lanka"}


def load_rates(path: str = DEFAULT_RATES) -> Dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_shipping(value) -> Dict:
    """Shipping from M2/eBay attributes -> {"amount": float|None, "currency": str|None, "included": bool}.
    'Free shipping' -> included; 'USD 12.50 shipping' / 12.5 -> amount (+ currency if written); else unknown."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return {"amount": None, "currency": None, "included": False}
    if isinstance(value, (int, float)):
        return {"amount": float(value), "currency": None, "included": float(value) == 0.0}
    s = str(value)
    if "free" in s.lower():
        return {"amount": 0.0, "currency": None, "included": True}
    m = re.search(r"\d[\d,]*(?:\.\d+)?", s)
    cur = re.search(r"\b([A-Z]{3})\b", s)
    return {"amount": float(m.group().replace(",", "")) if m else None,
            "currency": cur.group(1) if cur else None, "included": False}


def is_local(item_country: Optional[str], platform: str, flags: list) -> bool:
    if item_country:
        return str(item_country).strip().lower() in SRI_LANKA
    p = (platform or "").lower()
    flags.append("origin_assumed")
    return p not in IMPORT_PLATFORMS              # daraz / local shops = local, ebay / aliexpress = abroad


def payable_lkr(price_lkr: float, platform: str, category: Optional[str], rates: Dict, *,
                shipping_lkr: Optional[float] = None, shipping_included: bool = False,
                tax_included: bool = False, item_country: Optional[str] = None) -> Dict:
    """All amounts already in LKR. Returns {"payable", "breakdown", "flags", "local"}."""
    flags: list = []
    if shipping_included:
        ship = 0.0
    elif shipping_lkr is None:
        ship = 0.0
        flags.append("shipping_unknown")
    else:
        ship = float(shipping_lkr)
    local = is_local(item_country, platform, flags)
    b = {"item": price_lkr, "shipping": ship, "cid": 0.0, "pal": 0.0, "cess": 0.0, "sscl": 0.0, "vat": 0.0, "fees": 0.0}
    if local or tax_included:
        if tax_included and not local:
            flags.append("tax_included_by_seller")
    else:
        r = (rates.get("categories") or {}).get(category or "")
        if r is None:
            flags.append("tax_rate_missing")
        else:
            cif = price_lkr + ship
            b["cid"], b["pal"], b["cess"] = cif * r["cid"], cif * r["pal"], cif * r["cess"]
            base_sscl = cif + b["cid"] + b["pal"] + b["cess"]
            b["sscl"] = base_sscl * r["sscl"]
            b["vat"] = (base_sscl + b["sscl"]) * r["vat"]
            b["fees"] = float(r.get("fixed_fee_lkr", 0.0))
    b = {k: round(v, 2) for k, v in b.items()}
    return {"payable": round(sum(b.values()), 2), "breakdown": b, "flags": flags, "local": local}
