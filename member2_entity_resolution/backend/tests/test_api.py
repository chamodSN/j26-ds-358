from fastapi.testclient import TestClient

from app.api import service
from app.api.demo_data import DEMO_LISTINGS
from app.api.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_resolve_without_llm_covers_every_listing_once():
    r = client.post("/resolve", json={"listings": DEMO_LISTINGS, "use_llm": False})
    assert r.status_code == 200
    body = r.json()
    ids = [m["id"] for c in body["clusters"] for m in c["members"]]
    assert sorted(ids) == sorted(l["id"] for l in DEMO_LISTINGS)
    assert body["stats"]["llm_pairs_sent"] == 0 and body["stats"]["llm_network_calls"] == 0


def test_single_listing_is_rejected():
    assert client.post("/resolve", json={"listings": DEMO_LISTINGS[:1]}).status_code == 422


def test_judge_that_says_no_keeps_capacity_siblings_apart():
    out = service.resolve(DEMO_LISTINGS, use_llm=True, judge=lambda a, b: 0)
    where = {m["id"]: c["entity_id"] for c in out["clusters"] for m in c["members"]}
    assert where["a1"] != where["a2"] and where["b1"] != where["b2"]