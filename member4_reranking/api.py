"""
Member 4 - Cross-Encoder Re-ranking (Novelty 1) & PPP Price Normalization (Novelty 2, later)
Author: SANDEEPANI K.G.J (IT23295438)

POST /rerank  - input : M2's HarmonizationResult + max_results (exactly what backend/app/services/pipeline.py sends)
                        + optional taxonomy_path (M3) and price_constraint_text (M1) when the team adds them
                output: the team's FinalResponse (+ extra M4 fields that older callers simply ignore)

S12 = relevance only. Price fields are placeholders until Novelty 2:
  - best offer = first listed price, ppp_adjusted_price_usd = exchange-rate placeholder (USD as is, LKR / M4_LKR_PER_USD).
"""
import os
import sys
import time
from typing import List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException
from shared.schemas import FinalResponse, HarmonizationResult, Platform, QueryType, RankedResult

from member4_reranking.src.reranker import DEFAULT_MODEL_DIR, Reranker

app = FastAPI(title="Member 4 - Re-ranking Service", version="0.2.0")

MODEL_DIR = os.environ.get("M4_MODEL_DIR", DEFAULT_MODEL_DIR)
LKR_PER_USD = float(os.environ.get("M4_LKR_PER_USD", "300"))   # placeholder until Novelty 2
_state = {"reranker": None, "error": None}


def get_reranker() -> Reranker:
    if _state["reranker"] is None and _state["error"] is None:
        try:
            _state["reranker"] = Reranker(MODEL_DIR)
        except Exception as e:                     # model folder missing etc. -> backend falls back
            _state["error"] = f"{type(e).__name__}: {e}"
    if _state["reranker"] is None:
        raise HTTPException(status_code=503, detail=f"M4 model not loaded ({_state['error']})")
    return _state["reranker"]


class RerankRequest(HarmonizationResult):
    max_results: int = 10
    taxonomy_path: Optional[str] = None            # [ADD-M3] category context (optional for now)
    price_constraint_text: Optional[str] = None    # [ADD-M1] exact price span to remove (optional)


class M4RankedResult(RankedResult):
    p_exact: float                                 # calibrated P(product is Exact)
    match_label: str                               # great / good / fair
    low_confidence: bool                           # listing too incomplete to score reliably


class M4FinalResponse(FinalResponse):
    focused_query: str                             # what the cross-encoder actually read
    results: List[M4RankedResult]
    m4_latency_ms: float


@app.get("/health")
def health():
    loaded = _state["reranker"] is not None
    return {"status": "ok", "service": "member4-reranking", "model_loaded": loaded,
            "model_dir": os.path.abspath(MODEL_DIR), "error": _state["error"]}


def _usd_placeholder(price: float, currency: str) -> float:
    c = (currency or "").upper()
    if c == "USD":
        return round(price, 2)
    if c == "LKR":
        return round(price / LKR_PER_USD, 2)
    return round(price, 2)                         # unknown currency: unchanged until Novelty 2


@app.post("/rerank", response_model=M4FinalResponse)
def rerank(request: RerankRequest):
    t0 = time.perf_counter()
    rr = get_reranker()
    items = [{"id": p.canonical_id, "title": p.canonical_title,
              "attributes": p.harmonized_attributes, "tie": p.retrieval_score} for p in request.products]
    out = rr.rerank(request.query, items, price_span=request.price_constraint_text,
                    category=request.taxonomy_path)

    results = []
    for rank, it in enumerate(out["items"][: request.max_results], start=1):
        prod = request.products[it["index"]]
        price = prod.prices[0] if prod.prices else None
        platform = prod.platforms[0] if prod.platforms else (price.platform if price else Platform.EBAY)
        amount, currency = (price.price, price.currency) if price else (0.0, "USD")
        results.append(M4RankedResult(
            rank=rank, canonical_id=prod.canonical_id, canonical_title=prod.canonical_title,
            platform=platform, original_price=amount, currency=currency,
            ppp_adjusted_price_usd=_usd_placeholder(amount, currency),
            relevance_score=round(it["p"], 6), harmonized_attributes=prod.harmonized_attributes,
            p_exact=round(it["p_exact"], 4), match_label=it["match"], low_confidence=it["low_conf"]))

    return M4FinalResponse(
        query_id=request.query_id, query=request.query,
        query_type=QueryType.SEMANTIC,             # placeholder: M1's query_type is not sent to M4 yet
        hypothetical_spec="",
        results=results,
        total_candidates_retrieved=request.total_candidates_received,
        total_unique_products=len(request.products),
        platforms_queried=sorted({pl for prod in request.products for pl in prod.platforms}, key=lambda x: x.value),
        focused_query=out["focused_query"],
        m4_latency_ms=round((time.perf_counter() - t0) * 1000, 1))