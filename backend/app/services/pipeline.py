from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

import httpx

from app.config import settings
from app.services.ebay import ebay
from app.services.fx import convert
from app.services.modules import post_json
from shared.config import settings as shared
from shared.ebay import items_to_raw_products
from shared.schemas import (
    Category,
    FinalResponse,
    HarmonizationResult,
    HarmonizedProduct,
    Platform,
    PlatformPrice,
    PlatformRoute,
    QueryType,
    RankedResult,
    RawProduct,
    RetrievalResult,
    RoutingDecision,
)

log = logging.getLogger("vero.pipeline")


@dataclass
class SearchParams:
    q: str
    limit: int = 24
    min_price_usd: float | None = None
    max_price_usd: float | None = None
    condition: str | None = None
    category_ids: str | None = None


@dataclass
class PipelineResult:
    final: FinalResponse
    raw_by_id: dict[str, RawProduct]
    canon_sources: dict[str, list[str]]
    modules_used: list[str] = field(default_factory=list)
    degraded: list[str] = field(default_factory=list)
    total_available: int = 0
    pricing_mode: str = "fx_only"


# ------------------------------------------------------------ fallbacks
def _default_routing(query_id: str) -> RoutingDecision:
    return RoutingDecision(
        query_id=query_id,
        category=Category.ELECTRONICS,
        platforms_to_query=[
            PlatformRoute(platform=Platform.EBAY, category_relevance=1.0, staleness_score=0.0)
        ],
    )


async def _ebay_retrieval(query_id: str, p: SearchParams) -> tuple[RetrievalResult, int]:
    data = await ebay.search(
        p.q,
        limit=p.limit,
        category_ids=p.category_ids,
        min_price=p.min_price_usd,
        max_price=p.max_price_usd,
        condition=p.condition,
    )
    candidates = items_to_raw_products(data["items"])
    result = RetrievalResult(
        query_id=query_id,
        query=p.q,
        query_type=QueryType.SEMANTIC,
        alpha=0.5,
        hypothetical_spec="",
        candidates=candidates,
    )
    return result, data["total"]


def _wrap_harmonized(r: RetrievalResult) -> HarmonizationResult:
    """No entity resolution yet: one listing becomes one product."""
    products = [
        HarmonizedProduct(
            canonical_id=c.product_id,
            canonical_title=c.title,
            platforms=[c.platform],
            prices=[PlatformPrice(platform=c.platform, price=c.price, currency=c.currency)],
            harmonized_attributes=dict(c.raw_attributes),
            retrieval_score=c.retrieval_score,
            source_product_ids=[c.product_id],
        )
        for c in r.candidates
    ]
    return HarmonizationResult(
        query_id=r.query_id,
        query=r.query,
        products=products,
        total_candidates_received=len(r.candidates),
    )


def _basic_rerank(
    h: HarmonizationResult, r: RetrievalResult, rates: dict, limit: int
) -> FinalResponse:
    """No re-ranking yet: keep the order, convert price to USD with the exchange rate only."""
    shown = h.products[:limit]
    results: list[RankedResult] = []
    for i, p in enumerate(shown):
        price = p.prices[0] if p.prices else None
        amount = price.price if price else 0.0
        currency = price.currency if price else "USD"
        usd = convert(amount, currency, "USD", rates)
        results.append(
            RankedResult(
                rank=i + 1,
                canonical_id=p.canonical_id,
                canonical_title=p.canonical_title,
                platform=p.platforms[0] if p.platforms else Platform.EBAY,
                original_price=amount,
                currency=currency,
                ppp_adjusted_price_usd=round(usd if usd is not None else amount, 2),
                relevance_score=max(0.0, 1.0 - i / max(len(shown), 1)),
                harmonized_attributes=p.harmonized_attributes,
            )
        )
    return FinalResponse(
        query_id=r.query_id,
        query=r.query,
        query_type=r.query_type,
        hypothetical_spec=r.hypothetical_spec,
        results=results,
        total_candidates_retrieved=len(r.candidates),
        total_unique_products=len(h.products),
        platforms_queried=[Platform.EBAY],
    )


# ------------------------------------------------------------- pipeline
async def run_pipeline(p: SearchParams, rates: dict) -> PipelineResult:
    query_id = str(uuid.uuid4())
    used: list[str] = []
    degraded: list[str] = []
    total_available = 0

    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        # Stage 1: M3 routing
        routing = _default_routing(query_id)
        if settings.enable_m3:
            try:
                routing = RoutingDecision(
                    **await post_json(
                        client,
                        shared.member3_url,
                        "/route",
                        {"query_id": query_id, "query": p.q, "categories": ["electronics"]},
                    )
                )
                used.append("m3")
            except Exception as e:
                log.warning("M3 failed, using default routing: %s", e)
                degraded.append("m3")

        # Stage 2: M1 retrieval (fallback: live eBay search)
        retrieval: RetrievalResult | None = None
        if settings.enable_m1:
            try:
                retrieval = RetrievalResult(
                    **await post_json(
                        client,
                        shared.member1_url,
                        "/retrieve",
                        {"query_id": query_id, "query": p.q, "routing": routing.model_dump(mode="json")},
                    )
                )
                total_available = len(retrieval.candidates)
                used.append("m1")
            except Exception as e:
                log.warning("M1 failed, using live eBay search: %s", e)
                degraded.append("m1")
        if retrieval is None:
            retrieval, total_available = await _ebay_retrieval(query_id, p)  # may raise EbayError
            used.append("ebay")

        # Stage 3: M2 entity resolution (fallback: 1 listing = 1 product)
        harmonized: HarmonizationResult | None = None
        if settings.enable_m2:
            try:
                harmonized = HarmonizationResult(
                    **await post_json(
                        client, shared.member2_url, "/harmonize", retrieval.model_dump(mode="json")
                    )
                )
                used.append("m2")
            except Exception as e:
                log.warning("M2 failed, skipping harmonization: %s", e)
                degraded.append("m2")
        if harmonized is None:
            harmonized = _wrap_harmonized(retrieval)

        # Stage 4: M4 re-ranking + PPP (fallback: keep order, exchange rate only)
        final: FinalResponse | None = None
        pricing_mode = "fx_only"
        if settings.enable_m4:
            try:
                final = FinalResponse(
                    **await post_json(
                        client,
                        shared.member4_url,
                        "/rerank",
                        {**harmonized.model_dump(mode="json"), "max_results": p.limit},
                    )
                )
                used.append("m4")
                pricing_mode = "ppp"
            except Exception as e:
                log.warning("M4 failed, keeping retrieval order: %s", e)
                degraded.append("m4")
        if final is None:
            final = _basic_rerank(harmonized, retrieval, rates, p.limit)

    return PipelineResult(
        final=final,
        raw_by_id={c.product_id: c for c in retrieval.candidates},
        canon_sources={x.canonical_id: x.source_product_ids for x in harmonized.products},
        modules_used=used,
        degraded=degraded,
        total_available=total_available,
        pricing_mode=pricing_mode,
    )