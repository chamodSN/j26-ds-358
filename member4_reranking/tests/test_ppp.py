"""Novelty 2 (PPP part) tests - no internet, small fixed snapshot and reference lists."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from fastapi.testclient import TestClient

import member4_reranking.api as api
from member4_reranking.src import ppp as P
from member4_reranking.src.reranker import Reranker
from member4_reranking.tests.test_rerank_api import CFG, ebay_like_request, fake_scorer

SNAP = {"fx_as_of": "TEST",
        "countries": {"LKA": {"ppp_updated": 80.0, "fx_per_usd_now": 320.0, "currency": "LKR"},
                      "PAK": {"ppp_updated": 64.0, "fx_per_usd_now": 280.0, "currency": "PKR"}}}
# each country's OWN phone market (local currency): thirds at 40k / 80k (LK) and 30k / 50k (PK)
REF = {("LKA", "phones"): {"q1": 40000.0, "q2": 80000.0, "n": 10},
       ("PAK", "phones"): {"q1": 30000.0, "q2": 50000.0, "n": 8},
       ("LKA", "laptops"): {"q1": 1.0, "q2": 2.0, "n": 3}}               # too few -> no tier


def test_parse_price_and_country():
    assert P.parse_price("Rs. 111,999") == 111999.0
    assert P.parse_price("LKR 1,958.58") == 1958.58
    assert P.country_from_url("https://www.daraz.pk/products/x.html") == "PAK"
    with pytest.raises(ValueError):
        P.parse_price("call for price")


def test_price_view_exchange_then_ppp():
    v = P.price_view(100.0, "USD", "LKA", SNAP)               # eBay $100 for a Sri Lankan user
    assert v["price"] == 32000.0                               # real price: exchange rate
    assert v["ppp_intl_dollars"] == 400.0                      # PPP-normalized: 32,000 / 80
    assert P.price_view(32000.0, "LKR", "LKA", SNAP)["price"] == 32000.0   # LKR price stays as it is
    assert P.price_view(10.0, "EUR", "LKA", SNAP) is None       # unknown currency -> no PPP fields


def test_tier_uses_the_users_own_market():
    # eBay phone $200: LK user pays Rs 64,000 -> Mid-range in LK ; PK user pays PKR 56,000 -> Premium in PK
    lk = P.price_view(200.0, "USD", "LKA", SNAP, REF, "phones")
    pk = P.price_view(200.0, "USD", "PAK", SNAP, REF, "phones")
    assert (lk["tier"], pk["tier"]) == ("Mid-range", "Premium")


def test_no_tier_without_enough_reference_or_category():
    assert P.price_view(1.5, "LKR", "LKA", SNAP, REF, "laptops")["tier"] is None
    assert P.price_view(100.0, "USD", "LKA", SNAP, REF, None)["tier"] is None


def test_tier_category_stand_in():
    assert P.tier_category("Xiaomi Redmi Note 13 8GB 256GB", {}) == "phones"
    assert P.tier_category("xiaomi note 13", {}) == "phones"
    assert P.tier_category("Clear case for Redmi Note 13", {}) is None
    assert P.tier_category("anything", {"category": "Cell Phones & Smartphones"}) == "phones"


def test_load_reference(tmp_path):
    f = tmp_path / "ref.csv"
    f.write_text("country,category,title,price,currency\n" +
                 "".join(f"LKA,phones,p{i},{p},LKR\n" for i, p in enumerate([10, 20, 30, 40, 50, 60])))
    r = P.load_reference(str(f))[("LKA", "phones")]
    assert r["n"] == 6 and 20 < r["q1"] < r["q2"] < 50


@pytest.fixture
def client():
    api._state.update(reranker=Reranker(scorer=fake_scorer, config=CFG), error=None)
    api._rates.update(snap=SNAP, error=None, ref=REF)
    yield TestClient(api.app)
    api._state.update(reranker=None, error=None)
    api._rates.update(snap=None, error=None, ref=None)


def test_api_display_only_and_per_country(client):
    req = ebay_like_request()
    lk = client.post("/rerank", json=req).json()
    req["user_country"] = "PAK"
    pk = client.post("/rerank", json=req).json()
    assert [x["canonical_id"] for x in lk["results"]] == [x["canonical_id"] for x in pk["results"]]   # order unchanged
    phone_lk = next(x for x in lk["results"] if x["canonical_id"] == "p2")     # $199 Redmi Note 13
    phone_pk = next(x for x in pk["results"] if x["canonical_id"] == "p2")
    assert phone_lk["user_view"]["currency"] == "LKR" and phone_pk["user_view"]["currency"] == "PKR"
    assert phone_lk["user_view"]["price_tier"] == "Mid-range" and phone_pk["user_view"]["price_tier"] == "Premium"
    assert phone_lk["ppp_adjusted_price_usd"] == phone_lk["user_view"]["ppp_intl_dollars"]
    case = next(x for x in lk["results"] if x["canonical_id"] == "p1")         # phone case: not a phone
    assert case["user_view"]["price_tier"] is None


def test_api_works_without_snapshot():
    api._state.update(reranker=Reranker(scorer=fake_scorer, config=CFG), error=None)
    api._rates.update(snap=None, error="FileNotFoundError", ref={})
    body = TestClient(api.app).post("/rerank", json=ebay_like_request()).json()
    assert body["results"][0]["user_view"] is None                       # ranking still works
    api._state.update(reranker=None, error=None); api._rates.update(snap=None, error=None, ref=None)