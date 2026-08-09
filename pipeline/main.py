"""
Pipeline Orchestrator - J26-DS-358
Coordinates Member 1 → 2 → 3 → 4 in sequence.
"""

import uuid
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.schemas import (
    QueryRequest, FinalResponse,
    RoutingDecision, RetrievalResult, HarmonizationResult
)
from shared.config import settings

app = FastAPI(
    title="J26-DS-358 — Pipeline API",
    description="Cross-Platform Product Retrieval & Ranking System — Research Project",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["System"])
def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "pipeline-api"}


@app.get("/", tags=["System"])
def root():
    return {
        "project": "J26-DS-358",
        "title": "Adaptive Cross-Platform Product Retrieval & Ranking",
        "docs": "/docs",
        "services": {
            "member1_retrieval": settings.member1_url + "/docs",
            "member2_entity": settings.member2_url + "/docs",
            "member3_kg": settings.member3_url + "/docs",
            "member4_reranking": settings.member4_url + "/docs",
        }
    }


@app.post("/search", response_model=FinalResponse, tags=["Pipeline"])
async def search(request: QueryRequest):
    """
    Main pipeline endpoint.

    Calls modules in this order:
    1. Member 3 - Knowledge Graph → get platform routing
    2. Member 1 - Retrieval → get raw candidates
    3. Member 2 - Entity Resolution → deduplicate and harmonize
    4. Member 4 - Re-ranking → rank and PPP-normalize
    """
    query_id = str(uuid.uuid4())
    timeout = httpx.Timeout(60.0)

    async with httpx.AsyncClient(timeout=timeout) as client:

        # Step 1: Member 3 - Platform Routing
        try:
            m3_response = await client.post(
                f"{settings.member3_url}/route",
                json={
                    "query_id": query_id,
                    "query": request.query,
                    "categories": [c.value for c in request.categories]
                }
            )
            m3_response.raise_for_status()
            routing = RoutingDecision(**m3_response.json())
        except httpx.ConnectError:
            raise HTTPException(503, "Member 3 (Knowledge Graph) is not running.")
        except Exception as e:
            raise HTTPException(503, f"Member 3 error: {e}")

        # Step 2: Member 1 - Retrieve Candidates
        try:
            m1_response = await client.post(
                f"{settings.member1_url}/retrieve",
                json={
                    "query_id": query_id,
                    "query": request.query,
                    "routing": routing.model_dump()
                }
            )
            m1_response.raise_for_status()
            candidates = RetrievalResult(**m1_response.json())
        except httpx.ConnectError:
            raise HTTPException(503, "Member 1 (Retrieval) is not running.")
        except Exception as e:
            raise HTTPException(503, f"Member 1 error: {e}")

        # Step 3: Member 2 - Entity Resolution + Harmonization
        try:
            m2_response = await client.post(
                f"{settings.member2_url}/harmonize",
                json=candidates.model_dump()
            )
            m2_response.raise_for_status()
            harmonized = HarmonizationResult(**m2_response.json())
        except httpx.ConnectError:
            raise HTTPException(503, "Member 2 (Entity Resolution) is not running.")
        except Exception as e:
            raise HTTPException(503, f"Member 2 error: {e}")

        # Step 4: Member 4 - Re-rank + PPP Normalize
        try:
            m4_response = await client.post(
                f"{settings.member4_url}/rerank",
                json={**harmonized.model_dump(), "max_results": request.max_results}
            )
            m4_response.raise_for_status()
            final = FinalResponse(**m4_response.json())
        except httpx.ConnectError:
            raise HTTPException(503, "Member 4 (Reranking) is not running.")
        except Exception as e:
            raise HTTPException(503, f"Member 4 error: {e}")

    return final