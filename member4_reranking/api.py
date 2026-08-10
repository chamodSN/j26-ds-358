"""
Member 4 - Cross-Encoder Re-ranking & PPP Price Normalization
Author: SANDEEPANI K.G.J

POST /rerank  - Takes Member 2's harmonized list, re-ranks using cross-encoder,
                applies PPP price normalization, returns final response.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi import FastAPI
from pydantic import BaseModel
from shared.schemas import HarmonizationResult, FinalResponse, RankedResult, QueryType

app = FastAPI(title="Member 4 - Re-ranking Service", version="0.1.0")


class RerankRequest(HarmonizationResult):
    max_results: int = 10


@app.get("/health")
def health():
    return {"status": "ok", "service": "member4-reranking"}


@app.post("/rerank", response_model=FinalResponse)
async def rerank(request: RerankRequest):
    """
    Cross-encoder re-ranking + PPP price normalization.
    Input:  HarmonizationResult from Member 2 + max_results
    Output: FinalResponse with PPP-adjusted ranked results
    """
    # TODO: Replace stub with actual implementation
    # 1. Score each product against query using cross-encoder
    # 2. Re-order by cross-encoder relevance score
    # 3. Fetch World Bank PPP conversion factor for each currency
    # 4. Apply PPP adjustment on top of exchange rate conversion
    # 5. Return top max_results products

    # STUB
    results = []
    for i, product in enumerate(request.products[:request.max_results]):
        best_price = product.prices[0] if product.prices else None
        results.append(
            RankedResult(
                rank=i + 1,
                canonical_id=product.canonical_id,
                canonical_title=product.canonical_title,
                platform=product.platforms[0],
                original_price=best_price.price if best_price else 0.0,
                currency=best_price.currency if best_price else "LKR",
                ppp_adjusted_price_usd=float((best_price.price if best_price else 0.0) / 300),
                relevance_score=float(1.0 - i * 0.08),
                harmonized_attributes=product.harmonized_attributes
            )
        )

    return FinalResponse(
        query_id=request.query_id,
        query=request.query,
        query_type=QueryType.SEMANTIC,
        hypothetical_spec="[From Member 1 — passed through pipeline]",
        results=results,
        total_candidates_retrieved=request.total_candidates_received,
        total_unique_products=len(request.products),
        platforms_queried=list({p for prod in request.products for p in prod.platforms})
    )