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
    # TODO: Replace stub with actual knowledge graph implementation
    # 1. Map query to Google Product Taxonomy category
    # 2. Query the KG: which platforms carry this category?
    # 3. Compute staleness score for each platform-category pair
    # 4. Return ordered platform list (most relevant first)

    # STUB
    category = Category.ELECTRONICS
    if categories := request.categories:
        if "fashion" in categories:
            category = Category.FASHION

    return RoutingDecision(
        query_id=request.query_id,
        category=category,
        platforms_to_query=[
            PlatformRoute(platform=Platform.EBAY,
                          category_relevance=0.9, staleness_score=0.1),
            PlatformRoute(platform=Platform.ALIEXPRESS,
                          category_relevance=0.8, staleness_score=0.2),
        ]
    )
