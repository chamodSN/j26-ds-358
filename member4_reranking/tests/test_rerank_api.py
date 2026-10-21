"""S12 tests: /rerank contract + reranker logic, with a FAKE scorer (no torch / no model download)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from fastapi.testclient import TestClient

import member4_reranking.api as api
from member4_reranking.src.reranker import Reranker, is_low_confidence, product_fields
from shared.schemas import FinalResponse

CFG = {"max_length": 256, "cal_x": [0.0, 1.0], "cal_y": [0.0, 1.0],      # identity calibration
       "great_if_p_exact_ge": 0.90, "good_if_p_exact_ge": 0.50}


def fake_scorer(queries, texts):
    """logit = 4 * (share of query words found in the product text) - 2  ->  p in (0.12, 0.88)."""
    out = []
    for q, t in zip(queries, texts):
        qw = set(q.lower().replace("[", " ").replace("]", " ").split())
        tw = set(t.lower().split())
        out.append(4 * len(qw & tw) / max(len(qw), 1) - 2)
    return out


def ebay_like_request(n_extra=0):
    def prod(pid, title, price, attrs=None, score=0.5):
        a = {"source": "ebay", "seller": "best_seller_99", "item_url": "https://ebay.com/itm/1",
             "shipping": "free", "image_url": "https://i.ebayimg.com/x.jpg", "condition": "New"}
        a.update(attrs or {})
        return {"canonical_id": pid, "canonical_title": title, "platforms": ["ebay"],
                "prices": [{"platform": "ebay", "price": price, "currency": "USD"}],
                "harmonized_attributes": a, "retrieval_score": score, "source_product_ids": [pid]}
    products = [
        prod("p1", "Phone case for Redmi Note 13 shockproof clear cover", 5.0, score=0.9),
        prod("p2", "Xiaomi Redmi Note 13 8GB 256GB Midnight Black Global Version", 199.0, {"brand": "Xiaomi"}, 0.8),
        prod("p3", "Redmi Note 13", 189.0, score=0.7),
        prod("p4", "Samsung 43 inch smart TV", 299.0, score=0.95),
    ] + [prod(f"x{i}", f"usb cable {i}", 3.0, score=0.1) for i in range(n_extra)]
    return {"query_id": "q1", "query": "redmi note 13 8gb 256gb under 60000", "products": products,
            "total_candidates_received": 50, "max_results": 10}


@pytest.fixture
def client():
    api._state.update(reranker=Reranker(scorer=fake_scorer, config=CFG), error=None)
    yield TestClient(api.app)
    api._state.update(reranker=None, error=None)


def test_rerank_returns_valid_team_final_response(client):
    r = client.post("/rerank", json=ebay_like_request())
    assert r.status_code == 200, r.text
    body = r.json()
    FinalResponse(**body)                                   # the backend can parse it (extra fields ignored)
    assert [x["rank"] for x in body["results"]] == [1, 2, 3, 4]
    assert all(0.0 <= x["relevance_score"] <= 1.0 for x in body["results"])


def test_order_is_by_relevance_not_by_retrieval(client):
    body = client.post("/rerank", json=ebay_like_request()).json()
    ids = [x["canonical_id"] for x in body["results"]]
    assert ids[0] == "p2"                                   # full match first, although M1 ranked p4 highest
    assert ids[-1] == "p4"                                  # TV last
    scores = [x["relevance_score"] for x in body["results"]]
    assert scores == sorted(scores, reverse=True)


def test_price_words_removed_from_model_query(client):
    body = client.post("/rerank", json=ebay_like_request()).json()
    assert body["focused_query"] == "redmi note 13 8gb 256gb"


def test_category_from_m3_is_added_when_given(client):
    req = ebay_like_request(); req["taxonomy_path"] = "Mobile & Computing"
    assert client.post("/rerank", json=req).json()["focused_query"] == "[Mobile & Computing] redmi note 13 8gb 256gb"


def test_max_results_and_match_labels(client):
    req = ebay_like_request(n_extra=12); req["max_results"] = 5
    body = client.post("/rerank", json=req).json()
    assert len(body["results"]) == 5 and body["total_unique_products"] == 16
    assert {x["match_label"] for x in body["results"]} <= {"great", "good", "fair"}


def test_low_confidence_flag(client):
    body = client.post("/rerank", json=ebay_like_request()).json()
    flags = {x["canonical_id"]: x["low_confidence"] for x in body["results"]}
    assert flags["p3"] is True                              # "Redmi Note 13": 3 words, no brand, no features
    assert flags["p2"] is False


def test_empty_product_list(client):
    req = ebay_like_request(); req["products"] = []
    body = client.post("/rerank", json=req).json()
    assert body["results"] == []


def test_seller_url_shipping_never_reach_the_model():
    f = product_fields("Redmi Note 13", {"seller": "abc", "item_url": "http://x", "shipping": "free",
                                         "brand": "Xiaomi", "color": "Black"})
    assert f == {"title": "Redmi Note 13", "brand": "Xiaomi", "color": "Black", "bullets": ""}
    assert not is_low_confidence(f)                         # has a brand


def test_503_when_model_missing():
    api._state.update(reranker=None, error="FileNotFoundError: no model")
    r = TestClient(api.app).post("/rerank", json=ebay_like_request())
    assert r.status_code == 503                             # backend then falls back to retrieval order
    api._state.update(reranker=None, error=None)