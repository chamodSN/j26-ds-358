import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi.testclient import TestClient
from member4_reranking.api import app
from member4_reranking.src.cross_encoder import product_to_text


def test_health():
    r = TestClient(app).get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_product_to_text_skips_missing():
    assert product_to_text({"title": "Pixel 8", "brand": "Google", "color": None}) == "Pixel 8 | Google"
