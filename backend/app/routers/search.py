from __future__ import annotations

import time
import uuid
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from app.api_schemas import FxInfo, PipelineInfo, ProductOut, SearchResponse
from app.config import settings
from app.db import SessionLocal
from app.deps import get_optional_user
from app.models import SearchHistory, User
from app.services.cache import cache_get, cache_set, make_key
from app.services.fx import convert, get_rates
from app.services.mapping import CATEGORY_IDS, ranked_to_product
from app.services.pipeline import SearchParams, run_pipeline
from shared.ebay import EbayError

router = APIRouter(prefix="/api", tags=["search"])


def record_history(user_id: uuid.UUID, query: str, count: int) -> None:
    with SessionLocal() as db:
        db.add(SearchHistory(user_id=user_id, query=query, result_count=count))
        db.commit()


def _flags() -> str:
    return "".join("1" if f else "0" for f in (
        settings.enable_m1, settings.enable_m2, settings.enable_m3, settings.enable_m4))


@router.get("/search", response_model=SearchResponse)
async def search(
    background: BackgroundTasks,
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(24, ge=1, le=60),
    min_price: float | None = Query(None, ge=0, description="in LKR"),
    max_price: float | None = Query(None, ge=0, description="in LKR"),
    condition: Literal["new", "used"] | None = None,
    sort: Literal["best", "price_asc", "price_desc"] = "best",
    category: str | None = None,
    user: User | None = Depends(get_optional_user),
):
    q = q.strip()
    if not q:
        raise HTTPException(422, "Type something to search for.")

    rates = await get_rates()
    min_usd = convert(min_price, "LKR", "USD", rates) if min_price is not None else None
    max_usd = convert(max_price, "LKR", "USD", rates) if max_price is not None else None
    category_ids = CATEGORY_IDS.get(category or "")

    key = make_key(
        "search", q=q.lower(), limit=limit,
        lo=round(min_usd, 2) if min_usd is not None else None,
        hi=round(max_usd, 2) if max_usd is not None else None,
        cond=condition, cat=category_ids, flags=_flags(),
    )
    cached = await cache_get(key)
    was_cached = cached is not None

    if cached is None:
        started = time.perf_counter()
        try:
            result = await run_pipeline(
                SearchParams(
                    q=q, limit=limit, min_price_usd=min_usd, max_price_usd=max_usd,
                    condition=condition, category_ids=category_ids,
                ),
                rates,
            )
        except EbayError as e:
            raise HTTPException(status_code=e.status, detail=e.message) from e
        items = [ranked_to_product(r, result, rates) for r in result.final.results]
        cached = {
            "items": [i.model_dump(mode="json") for i in items],
            "total": result.total_available,
            "modules": result.modules_used,
            "degraded": result.degraded,
            "pricing_mode": result.pricing_mode,
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
        await cache_set(key, cached, settings.cache_ttl_search)

    items = [ProductOut(**i) for i in cached["items"]]

    # Filter by LKR price here too, so it also works when a team module made the list.
    if min_price is not None:
        items = [i for i in items if i.price_lkr is not None and i.price_lkr >= min_price]
    if max_price is not None:
        items = [i for i in items if i.price_lkr is not None and i.price_lkr <= max_price]

    if sort == "price_asc":
        items.sort(key=lambda i: i.price_lkr if i.price_lkr is not None else float("inf"))
    elif sort == "price_desc":
        items.sort(key=lambda i: i.price_lkr if i.price_lkr is not None else -1.0, reverse=True)

    if user is not None:
        background.add_task(record_history, user.id, q, len(items))

    return SearchResponse(
        query=q,
        total=cached["total"],
        count=len(items),
        items=items,
        pricing_mode=cached["pricing_mode"],
        pipeline=PipelineInfo(
            modules=cached["modules"],
            degraded=cached["degraded"],
            latency_ms=cached["latency_ms"],
            cached=was_cached,
        ),
        fx=FxInfo(
            usd_to_lkr=rates["rates"].get("LKR"),
            as_of=rates.get("as_of"),
            source=rates.get("source", "fallback"),
        ),
    )