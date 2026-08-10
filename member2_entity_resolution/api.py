"""
Member 2 - Entity Resolution & Schema Harmonization
Author: Watareka W.A.M.Y

POST /harmonize  - Takes Member 1's candidate list, deduplicates,
                   returns harmonized products.
"""

from shared.schemas import RetrievalResult, HarmonizationResult, HarmonizedProduct, PlatformPrice
from fastapi import FastAPI
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


app = FastAPI(title="Member 2 - Entity Resolution Service", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok", "service": "member2-entity"}


@app.post("/harmonize", response_model=HarmonizationResult)
async def harmonize(candidates: RetrievalResult):
    """
    Entity resolution + schema harmonization.
    Input:  RetrievalResult from Member 1 (50-100 raw candidates)
    Output: HarmonizationResult (10-30 deduplicated, harmonized products)
    """
    # TODO: Replace stub with actual implementation
    # 1. Block candidates using embedding similarity
    # 2. Pairwise match within each block
    # 3. Group matched pairs into canonical products
    # 4. Harmonize attributes using schema mapping

    # STUB
    harmonized = []
    for i, candidate in enumerate(candidates.candidates[:5]):
        harmonized.append(
            HarmonizedProduct(
                canonical_id=f"canonical-{i:03d}",
                canonical_title=candidate.title,
                platforms=[candidate.platform],
                prices=[PlatformPrice(
                    platform=candidate.platform,
                    price=candidate.price,
                    currency=candidate.currency
                )],
                harmonized_attributes=candidate.raw_attributes,
                retrieval_score=candidate.retrieval_score,
                source_product_ids=[candidate.product_id]
            )
        )

    return HarmonizationResult(
        query_id=candidates.query_id,
        query=candidates.query,
        products=harmonized,
        total_candidates_received=len(candidates.candidates)
    )
