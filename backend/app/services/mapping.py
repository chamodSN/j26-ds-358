from __future__ import annotations

import html
import re
from typing import Any

from app.api_schemas import ProductOut
from app.services.fx import convert
from app.services.pipeline import PipelineResult
from shared.schemas import RankedResult, RawProduct

# Category ids for eBay (US). You can check ids with eBay's Taxonomy API.
CATEGORY_IDS = {
    "phones": "9355",
    "laptops": "177",
    "tablets": "171485",
    "watches": "178893",
    "audio": "112529",
    "cameras": "31388",
}

_KNOWN_KEYS = {
    "source", "image_url", "item_url", "condition", "seller",
    "seller_rating", "location", "shipping", "categories",
}


def _num(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _round(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def _extra(attrs: dict) -> dict:
    return {k: v for k, v in attrs.items() if k not in _KNOWN_KEYS}


def ranked_to_product(r: RankedResult, res: PipelineResult, rates: dict) -> ProductOut:
    """Final pipeline result -> what the UI needs. Pulls image and links from the raw eBay data."""
    sources = res.canon_sources.get(r.canonical_id) or [r.canonical_id]
    raw = next((res.raw_by_id[s] for s in sources if s in res.raw_by_id), None)
    merged = {**(raw.raw_attributes if raw else {}), **(r.harmonized_attributes or {})}
    uses_m4 = "m4" in res.modules_used
    return ProductOut(
        id=raw.product_id if raw else sources[0],
        rank=r.rank,
        title=r.canonical_title,
        image_url=merged.get("image_url"),
        item_url=merged.get("item_url"),
        platform=r.platform.value,
        price=r.original_price,
        currency=r.currency,
        price_lkr=_round(convert(r.original_price, r.currency, "LKR", rates)),
        ppp_adjusted_price_usd=r.ppp_adjusted_price_usd if uses_m4 else None,
        relevance_score=r.relevance_score if uses_m4 else None,
        condition=merged.get("condition"),
        seller=merged.get("seller"),
        seller_rating=_num(merged.get("seller_rating")),
        location=merged.get("location"),
        shipping=merged.get("shipping"),
        attributes=_extra(merged),
    )


def raw_to_product(raw: RawProduct, rank: int, rates: dict) -> ProductOut:
    a = raw.raw_attributes
    return ProductOut(
        id=raw.product_id,
        rank=rank,
        title=raw.title,
        image_url=a.get("image_url"),
        item_url=a.get("item_url"),
        platform=raw.platform.value,
        price=raw.price,
        currency=raw.currency,
        price_lkr=_round(convert(raw.price, raw.currency, "LKR", rates)),
        condition=a.get("condition"),
        seller=a.get("seller"),
        seller_rating=_num(a.get("seller_rating")),
        location=a.get("location"),
        shipping=a.get("shipping"),
        attributes=_extra(a),
    )


def strip_html(text: str, limit: int = 1500) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return text[:limit]