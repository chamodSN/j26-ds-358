"""Novelty 2 (payable price, Sri Lanka) tests - no internet."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from fastapi.testclient import TestClient

import member4_reranking.api as api
from member4_reranking.src import payable as PY
from member4_reranking.src.reranker import Reranker
from member4_reranking.tests.test_ppp import REF, SNAP
from member4_reranking.tests.test_rerank_api import CFG, ebay_like_request, fake_scorer

RATES = {"categories": {"phones": {"cid": 0.0, "pal": 0.10, "cess": 0.25, "sscl": 0.025, "vat": 0.18, "fixed_fee_lkr": 236}}}


def test_parse_shipping():
    assert PY.parse_shipping("Free shipping") == {"amount": 0.0, "currency": None, "included": True}
    assert PY.parse_shipping("USD 12.50 shipping") == {"amount": 12.5, "currency": "USD", "included": False}
    assert PY.parse_shipping(None)["amount"] is None


def test_local_daraz_price_gets_no_import_tax():
    r = PY.payable_lkr(57900, "daraz", "phones", RATES, shipping_lkr=350, item_country="LK")
    assert r["payable"] == 58250 and r["breakdown"]["vat"] == 0 and r["local"] is True


def test_imported_phone_taxes_in_the_right_order():
    # CIF 100,000 -> CID 0, PAL 10,000, CESS 25,000 -> SSCL 2.5% of 135,000 = 3,375 -> VAT 18% of 138,375 = 24,907.5
    r = PY.payable_lkr(96000, "ebay", "phones", RATES, shipping_lkr=4000, item_country="US")
    b = r["breakdown"]
    assert (b["pal"], b["cess"], b["sscl"], b["vat"], b["fees"]) == (10000, 25000, 3375, 24907.5, 236)
    assert r["payable"] == 100000 + 10000 + 25000 + 3375 + 24907.5 + 236


def test_nothing_added_twice():
    inc = PY.payable_lkr(50000, "ebay", "phones", RATES, shipping_included=True, tax_included=True, item_country="US")
    assert inc["payable"] == 50000 and "tax_included_by_seller" in inc["flags"]


def test_unknowns_are_flagged_not_invented():
    r = PY.payable_lkr(30000, "aliexpress", "earbuds", RATES)        # no shipping, no origin, no earbud rates
    assert r["breakdown"]["shipping"] == 0
    assert {"shipping_unknown", "origin_assumed", "tax_rate_missing"} <= set(r["flags"])
    assert r["payable"] == 30000


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "FX_AUTO_REFRESH", False)
    api._state.update(reranker=Reranker(scorer=fake_scorer, config=CFG), error=None)
    api._rates.update(snap=SNAP, error=None, ref=REF, lk=RATES)
    yield TestClient(api.app)
    api._state.update(reranker=None, error=None)
    api._rates.update(snap=None, error=None, ref=None, lk=None)


def test_api_payable_for_sri_lanka_only(client):
    req = ebay_like_request()
    for p in req["products"]:
        p["harmonized_attributes"]["location"] = "US"
    lk = client.post("/rerank", json=req).json()
    phone = next(x for x in lk["results"] if x["canonical_id"] == "p2")       # $199 eBay phone, free shipping
    u = phone["user_view"]
    assert u["listed_price"] == 199 * 320 and u["price"] > u["listed_price"]   # taxes added
    assert u["payable_breakdown"]["vat"] > 0 and u["payable_breakdown"]["shipping"] == 0
    req["user_country"] = "PAK"
    pk = client.post("/rerank", json=req).json()
    up = next(x for x in pk["results"] if x["canonical_id"] == "p2")["user_view"]
    assert up["payable_breakdown"] is None and up["price"] == up["listed_price"]
