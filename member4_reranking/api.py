"""
Member 4 - Cross-Encoder Re-ranking (Novelty 1) & PPP Price Normalization (Novelty 2, later)
Author: SANDEEPANI K.G.J (IT23295438)

POST /rerank  - input : M2's HarmonizationResult + max_results (exactly what backend/app/services/pipeline.py sends)
                        + optional taxonomy_path (M3) and price_constraint_text (M1) when the team adds them
                output: the team's FinalResponse (+ extra M4 fields that older callers simply ignore)

Novelty 1 decides the ORDER (relevance). Novelty 2 (PPP part) is DISPLAY ONLY, it never changes the order:
  - for the country of the user who searched (user_country: LKA or PAK): real price (live exchange rate),
    PPP-normalized price (international $ = ppp_adjusted_price_usd) and category tier Budget/Mid-range/Premium
    compared with THAT country's own market (price_data/phone_reference_v1.csv; phones only for now).
  - Sri Lankan user: estimated PAYABLE price (item + shipping + import taxes if shipped from abroad;
    rates in price_data/lk_import_rates.json, phones only for now) with a breakdown; PPP price and tier use it.
  - rates from price_data/rates_snapshot.json; if a file is missing, PPP fields stay empty (ranking still works).
  - best offer = first listed price until the payable-price step (taxes, shipping) is added.
"""
import os
import sys
import time
from typing import List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from shared.schemas import FinalResponse, HarmonizationResult, Platform, QueryType, RankedResult

from member4_reranking.src.reranker import DEFAULT_MODEL_DIR, Reranker
from member4_reranking.src import ppp as P
from member4_reranking.src import payable as PY

app = FastAPI(title="Member 4 - Re-ranking Service", version="0.2.0")

MODEL_DIR = os.environ.get("M4_MODEL_DIR", DEFAULT_MODEL_DIR)
LKR_PER_USD = float(os.environ.get("M4_LKR_PER_USD", "300"))   # placeholder until Novelty 2
_state = {"reranker": None, "error": None}
SNAPSHOT_PATH = os.environ.get("M4_RATES_SNAPSHOT", P.DEFAULT_SNAPSHOT)
REFERENCE_PATH = os.environ.get("M4_TIER_REFERENCE", P.DEFAULT_REFERENCE)
IMPORT_RATES_PATH = os.environ.get("M4_IMPORT_RATES", PY.DEFAULT_RATES)
_rates = {"snap": None, "error": None, "ref": None, "lk": None}


def get_import_rates():
    if _rates["lk"] is None:
        try:
            _rates["lk"] = PY.load_rates(IMPORT_RATES_PATH)
        except Exception:                          # no tax table -> payable = price + shipping, flagged
            _rates["lk"] = {"categories": {}}
    return _rates["lk"]


FX_AUTO_REFRESH = os.environ.get("M4_FX_AUTO_REFRESH", "1") == "1"   # daily exchange-rate refresh (live)


def get_snapshot():
    if _rates["snap"] is None and _rates["error"] is None:
        try:
            _rates["snap"] = P.load_snapshot(SNAPSHOT_PATH)
        except Exception as e:                     # no snapshot -> ranking still works, PPP fields empty
            _rates["error"] = f"{type(e).__name__}: {e}"
    if _rates["snap"] is not None and FX_AUTO_REFRESH:
        P.refresh_fx(_rates["snap"], max_age_hours=24)      # cheap check; fetches at most once a day
    return _rates["snap"]


def get_reference():
    if _rates["ref"] is None:
        try:
            _rates["ref"] = P.load_reference(REFERENCE_PATH)
        except Exception:                          # no reference list -> prices shown, tiers empty
            _rates["ref"] = {}
    return _rates["ref"]


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
    user_country: str = "LKA"                      # country of the user who searched (World Bank code)


class CountryView(BaseModel):
    country: str
    currency: str
    price: float                                   # price the user pays: payable (LK) or listed price (other countries)
    ppp_intl_dollars: float                        # PPP-normalized price
    price_tier: Optional[str] = None               # Budget / Mid-range / Premium vs this country's market
    tier_category: Optional[str] = None            # category used for the tier (stand-in: phones)
    tier_reference_n: int = 0                      # how many reference prices the tier is based on
    listed_price: Optional[float] = None           # listing price in the user's currency (before shipping/taxes)
    payable_breakdown: Optional[dict] = None       # item, shipping, cid, pal, cess, sscl, vat, fees (LKR)
    price_flags: List[str] = []                    # shipping_unknown, origin_assumed, tax_rate_missing, ...


class M4RankedResult(RankedResult):
    p_exact: float                                 # calibrated P(product is Exact)
    match_label: str                               # great / good / fair
    low_confidence: bool                           # listing too incomplete to score reliably
    user_view: Optional[CountryView] = None        # Novelty 2 for the user's country (display only)


class M4FinalResponse(FinalResponse):
    focused_query: str                             # what the cross-encoder actually read
    results: List[M4RankedResult]
    m4_latency_ms: float
    rates_as_of: Optional[str] = None


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

    # ---- Novelty 2 (display only): price, PPP price and tier for the user's own country
    snap, ref = get_snapshot(), get_reference()
    country = request.user_country if (snap is not None and request.user_country in snap["countries"]) else None

    def cview(i):
        p = request.products[i]
        if country is None or not p.prices:
            return None
        cat = P.tier_category(p.canonical_title, p.harmonized_attributes)
        user_cur = snap["countries"][country]["currency"]
        listed = P.convert(p.prices[0].price, p.prices[0].currency, user_cur, snap)
        if listed is None:
            return None
        price, breakdown, flags = listed, None, []
        if country == "LKA":                       # payable price: Sri Lanka only (for now)
            a = p.harmonized_attributes or {}
            sh = PY.parse_shipping(a.get("shipping"))
            ship_lkr = (P.convert(sh["amount"], sh["currency"] or p.prices[0].currency, "LKR", snap)
                        if sh["amount"] is not None else None)
            platform = (p.prices[0].platform.value if hasattr(p.prices[0].platform, "value") else str(p.prices[0].platform))
            res = PY.payable_lkr(listed, platform, cat, get_import_rates(), shipping_lkr=ship_lkr,
                                 shipping_included=sh["included"], tax_included=bool(a.get("tax_included", False)),
                                 item_country=a.get("item_country") or a.get("location"))
            price, breakdown, flags = res["payable"], res["breakdown"], res["flags"]
        v = P.price_view(price, user_cur, country, snap, ref, cat)
        return CountryView(country=country, currency=v["currency"], price=round(v["price"], 2),
                           ppp_intl_dollars=round(v["ppp_intl_dollars"], 2), price_tier=v["tier"],
                           tier_category=cat, tier_reference_n=v["tier_reference_n"],
                           listed_price=round(listed, 2), payable_breakdown=breakdown, price_flags=flags)

    results = []
    for rank, it in enumerate(out["items"][: request.max_results], start=1):
        prod = request.products[it["index"]]
        price = prod.prices[0] if prod.prices else None
        platform = prod.platforms[0] if prod.platforms else (price.platform if price else Platform.EBAY)
        amount, currency = (price.price, price.currency) if price else (0.0, "USD")
        uv = cview(it["index"])
        results.append(M4RankedResult(
            rank=rank, canonical_id=prod.canonical_id, canonical_title=prod.canonical_title,
            platform=platform, original_price=amount, currency=currency,
            ppp_adjusted_price_usd=uv.ppp_intl_dollars if uv else _usd_placeholder(amount, currency),
            relevance_score=round(it["p"], 6),
            # M2's attributes are copied unchanged; M4 only ADDS its own keys (the UI reads product.attributes,
            # the same channel the frontend already reserves for M4's budget_tier). M2's object is not modified.
            harmonized_attributes={**prod.harmonized_attributes, "m4_match_label": it["match"],
                                   "m4_low_confidence": it["low_conf"], "m4_p_exact": round(it["p_exact"], 4),
                                   "m4_price_tier": uv.price_tier if uv else None},
            p_exact=round(it["p_exact"], 4), match_label=it["match"], low_confidence=it["low_conf"],
            user_view=uv))

    return M4FinalResponse(
        query_id=request.query_id, query=request.query,
        query_type=QueryType.SEMANTIC,             # placeholder: M1's query_type is not sent to M4 yet
        hypothetical_spec="",
        results=results,
        total_candidates_retrieved=request.total_candidates_received,
        total_unique_products=len(request.products),
        platforms_queried=sorted({pl for prod in request.products for pl in prod.platforms}, key=lambda x: x.value),
        focused_query=out["focused_query"],
        m4_latency_ms=round((time.perf_counter() - t0) * 1000, 1),
        rates_as_of=(snap or {}).get("fx_as_of"))
