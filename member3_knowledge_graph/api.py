"""
Member 3 - Knowledge Graph & Platform Routing
Author: Prarthana W.C
POST /route  - Given a query category, returns which platforms to query
               and their staleness scores.
"""
from shared.schemas import RoutingDecision, PlatformRoute, Platform, Category
from typing import List
from pydantic import BaseModel
from fastapi import FastAPI
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from member3_knowledge_graph.src.platform_router import map_query_to_category, get_platforms_for_category
from member3_knowledge_graph.src.staleness_tracker import compute_decay_rates

app = FastAPI(title="Member 3 - Knowledge Graph Service", version="0.1.0")


class RouteRequest(BaseModel):
    query_id: str
    query: str
    categories: List[str]


@app.get("/health")
def health():
    return {"status": "ok", "service": "member3-kg"}


@app.post("/route", response_model=RoutingDecision)
async def route(request: RouteRequest):
    """
    Knowledge graph routing.
    Input:  Query + categories
    Output: Ordered list of platforms to query with relevance and staleness scores
    """

    # Step 1 — Map query to category using embedding similarity
    raw_category = map_query_to_category(request.query)

    # Step 2 — Convert to schema Category enum
    # KG uses "Electrical Items"/"Fashion", schema uses ELECTRONICS/FASHION
    category_map = {
        "Electrical Items": Category.ELECTRONICS,
        "Fashion"         : Category.FASHION
    }
    category = category_map.get(raw_category, Category.ELECTRONICS)

    # Step 3 — Get staleness scores from Neo4j
    decay_rates = compute_decay_rates()
    staleness_map = {
        "Electrical Items": decay_rates.get("Electrical Items", 0.8),
        "Fashion"         : decay_rates.get("Fashion", 0.4)
    }
    staleness = staleness_map.get(raw_category, 0.5)

    # Step 4 — Get platforms from KG and build PlatformRoute list
    platform_routes = []

    # eBay is always available
    platform_routes.append(
        PlatformRoute(
            platform=Platform.EBAY,
            category_relevance=0.9,
            staleness_score=round(staleness, 4)
        )
    )

    # AliExpress — lower relevance, slightly less stale
    platform_routes.append(
        PlatformRoute(
            platform=Platform.ALIEXPRESS,
            category_relevance=0.75,
            staleness_score=round(min(staleness + 0.1, 1.0), 4)
        )
    )

    # Step 5 — Return RoutingDecision matching shared/schemas.py
    return RoutingDecision(
        query_id=request.query_id,
        category=category,
        platforms_to_query=platform_routes
    )