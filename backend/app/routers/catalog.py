from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query

from app.api_schemas import FeaturedResponse, ItemDetailOut, ProductOut, Rail, Spec
from app.config import settings
from app.services.cache import cache_get, cache_set, make_key
from app.services.ebay import ebay
from app.services.fx import convert, get_rates
from app.services.mapping import raw_to_product, strip_html
from shared.ebay import EbayError, bigger_image, items_to_raw_products, shipping_text

router = APIRouter(prefix="/api", tags=["catalog"])

RAILS = [
    {"key": "phones", "title": "Smartphones to look at", "query": "smartphone unlocked", "category": "9355"},
    {"key": "laptops", "title": "Laptops worth a look", "query": "laptop", "category": "177"},
    {"key": "audio", "title": "Headphones and audio", "query": "wireless headphones", "category": "112529"},
    {"key": "watches", "title": "Smartwatches", "query": "smart watch", "category": "178893"},
]


def _http(e: EbayError) -> HTTPException:
    return HTTPException(status_code=e.status, detail=e.message)


async def _rail(spec: dict, rates: dict) -> dict:
    data = await ebay.search(spec["query"], limit=10, category_ids=spec["category"])
    raws = items_to_raw_products(data["items"])
    items = [raw_to_product(r, i + 1, rates).model_dump(mode="json") for i, r in enumerate(raws)]
    return {"key": spec["key"], "title": spec["title"], "category": spec["key"], "items": items}


@router.get("/featured", response_model=FeaturedResponse)
async def featured():
    key = make_key("featured", v=1)
    cached = await cache_get(key)
    if cached:
        return FeaturedResponse(**cached)

    if not ebay.configured:
        raise HTTPException(503, "eBay is not connected yet. Add EBAY_CLIENT_ID and EBAY_CLIENT_SECRET to .env.")

    rates = await get_rates()
    results = await asyncio.gather(*[_rail(s, rates) for s in RAILS], return_exceptions=True)
    rails = [r for r in results if isinstance(r, dict) and r["items"]]
    if not rails:
        first = next((r for r in results if isinstance(r, EbayError)), None)
        if first:
            raise _http(first)
        raise HTTPException(502, "Could not load featured products.")

    payload = {"rails": rails}
    await cache_set(key, payload, settings.cache_ttl_featured)
    return FeaturedResponse(**payload)


@router.get("/item", response_model=ItemDetailOut)
async def item_detail(id: str = Query(..., min_length=3, max_length=120)):
    key = make_key("item", id=id)
    cached = await cache_get(key)
    if cached:
        return ItemDetailOut(**cached)

    rates = await get_rates()
    try:
        raw = await ebay.get_item(id)
    except EbayError as e:
        raise _http(e) from e

    price_obj = raw.get("price") or {}
    try:
        price = float(price_obj.get("value"))
    except (TypeError, ValueError):
        raise HTTPException(502, "This listing has no price.") from None
    currency = price_obj.get("currency", "USD")

    main_image = (raw.get("image") or {}).get("imageUrl")
    images = [u for u in [main_image, *[(i or {}).get("imageUrl") for i in raw.get("additionalImages", [])]] if u]
    seller = raw.get("seller") or {}
    try:
        rating = float(seller["feedbackPercentage"]) if seller.get("feedbackPercentage") else None
    except (TypeError, ValueError):
        rating = None
    loc = raw.get("itemLocation") or {}
    location = ", ".join(x for x in (loc.get("city"), loc.get("country")) if x) or None

    specs = [
        Spec(name=a["name"], value=str(a["value"]))
        for a in raw.get("localizedAspects", [])
        if a.get("name") and a.get("value")
    ][:24]

    description = raw.get("shortDescription") or strip_html(raw.get("description", ""))

    # Related items: same eBay category, similar title words. Failure here must not break the page.
    related: list[ProductOut] = []
    try:
        words = " ".join(raw.get("title", "").split()[:4])
        data = await ebay.search(words, limit=9, category_ids=raw.get("categoryId"))
        for i, r in enumerate(items_to_raw_products(data["items"])):
            if r.product_id != raw.get("itemId") and len(related) < 6:
                related.append(raw_to_product(r, i + 1, rates))
    except EbayError:
        pass

    out = ItemDetailOut(
        id=raw.get("itemId", id),
        title=raw.get("title", "Untitled"),
        image_url=bigger_image(main_image),
        images=images,
        item_url=raw.get("itemWebUrl"),
        price=price,
        currency=currency,
        price_lkr=(lambda v: round(v, 2) if v is not None else None)(convert(price, currency, "LKR", rates)),
        condition=raw.get("condition"),
        seller=seller.get("username"),
        seller_rating=rating,
        location=location,
        shipping=shipping_text(raw),
        brand=raw.get("brand"),
        description=description,
        specs=specs,
        related=related,
    )
    await cache_set(key, out.model_dump(mode="json"), settings.cache_ttl_item)
    return out