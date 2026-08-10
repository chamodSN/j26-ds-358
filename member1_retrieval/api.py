"""
Member 1 - Query Intent Enrichment & Adaptive Retrieval
Author: Nethmina K.G.C.S

API Endpoints:
  GET  /health      - Health check
  POST /retrieve    - Main retrieval endpoint (called by pipeline)
  POST /classify    - Classify query type only (useful for debugging)
  POST /generate-spec - Generate hypothetical product spec only (HyDE debug)
"""

from shared.schemas import (
    RetrievalResult, RoutingDecision, RawProduct,
    QueryType, Platform, Category
)
from typing import List
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# TODO: Uncomment these as you implement each module
# from member1_retrieval.src.classifier import QueryClassifier
# from member1_retrieval.src.hyde_generator import HyDEGenerator
# from member1_retrieval.src.retriever import Retriever
# from member1_retrieval.src.router import ConfidenceWeightedRouter

app = FastAPI(
    title="Member 1 — Adaptive Retrieval Service",
    description="Query intent classification, HyDE spec generation, and confidence-weighted retrieval",
    version="0.1.0",
)


# Request model

class RetrievalRequest(BaseModel):
    query_id: str
    query: str
    routing: dict   # RoutingDecision — passed as dict to avoid circular import issues


class ClassifyRequest(BaseModel):
    query: str


class SpecRequest(BaseModel):
    query: str


# Endpoints

@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "service": "member1-retrieval"}


@app.post("/classify", tags=["Debug"])
def classify_query(request: ClassifyRequest):
    """
    Debug endpoint: classify a query without running retrieval.
    Useful for testing the classifier independently.
    """
    # TODO: Replace stub with actual classifier
    # classifier = QueryClassifier()
    # result = classifier.classify(request.query)
    # return result

    # STUB - replace this with implementation
    query = request.query.lower()
    if any(w in query for w in ["samsung", "apple", "iphone", "xiaomi"]):
        if any(c.isdigit() for c in query):
            return {"query": request.query, "type": "exact", "confidence": 0.9}
    if any(w in query for w in ["under", "below", "cheap", "budget", "price"]):
        return {"query": request.query, "type": "hybrid", "confidence": 0.7}
    return {"query": request.query, "type": "semantic", "confidence": 0.8}


@app.post("/generate-spec", tags=["Debug"])
def generate_spec(request: SpecRequest):
    """
    Debug endpoint: run HyDE spec generation without retrieval.
    Useful for evaluating the quality of generated specs.
    """
    # TODO: Replace stub with actual HyDE generator
    # generator = HyDEGenerator(model_path="member1_retrieval/models/spec_generator")
    # spec = generator.generate(request.query)
    # return {"query": request.query, "hypothetical_spec": spec}

    # STUB
    return {
        "query": request.query,
        "hypothetical_spec": f"[STUB] High-performance product matching: {request.query} | Brand: TBD | Key specs: TBD"
    }


@app.post("/retrieve", response_model=RetrievalResult, tags=["Retrieval"])
async def retrieve(request: RetrievalRequest):
    """
    Main retrieval endpoint.

    Pipeline:
    1. Classify query type → get alpha (BM25 confidence weight)
    2. Generate hypothetical product spec via HyDE (for semantic/hybrid queries)
    3. Run BM25 keyword search
    4. Run HyDE dense vector search
    5. Blend results using: score = alpha × BM25 + (1-alpha) × HyDE_dense
    6. Return top 50-100 candidates

    This is called by the pipeline-api after Member 3 provides routing.
    """
    # TODO: Replace stub with actual implementation
    # Step 1: Classify
    # classifier = QueryClassifier()
    # classification = classifier.classify(request.query)
    # alpha = classification.alpha

    # Step 2: Generate spec
    # generator = HyDEGenerator(model_path="member1_retrieval/models/spec_generator")
    # hyp_spec = generator.generate(request.query)

    # Step 3+4+5: Retrieve and blend
    # router = ConfidenceWeightedRouter()
    # candidates = router.retrieve(request.query, hyp_spec, alpha)

    # STUB returns mock data so the full pipeline can be tested
    # Replace this with real implementation progressively
    stub_candidates = [
        RawProduct(
            product_id=f"mock-{i:03d}",
            platform=Platform.EBAY,
            title=f"[STUB] Product {i} for query: {request.query}",
            price=float(50000 - i * 1000),
            currency="LKR",
            retrieval_score=float(1.0 - i * 0.05),
            rank=i + 1,
            raw_attributes={
                "brand": "Samsung",
                "storage": "256GB",
                "ram": "8GB",
                "battery": "5000mAh"
            }
        )
        for i in range(5)  # Return 5 stub products
    ]

    return RetrievalResult(
        query_id=request.query_id,
        query=request.query,
        query_type=QueryType.SEMANTIC,
        alpha=0.1,
        hypothetical_spec=f"[STUB] Hypothetical spec for: {request.query}",
        candidates=stub_candidates
    )
