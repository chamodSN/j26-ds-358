import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd
from member4_reranking.src.metrics import ndcg_at_k, mrr, precision_at_k, evaluate
from member4_reranking.src.cross_encoder import product_to_text


def test_hand_example():
    g = [0.0, 1.0, 0.1]
    assert round(ndcg_at_k(g, g), 4) == 0.6405
    assert mrr(g) == 0.5
    assert precision_at_k(g) == 0.2


def test_perfect_order_is_one():
    d = pd.DataFrame({"query_id": [1, 1, 1, 2, 2], "gain": [0.0, 1.0, 0.1, 1.0, 0.01]})
    d["score"] = d["gain"]
    m, _ = evaluate(d)
    assert m["ndcg@10"] == 1.0 and m["mrr"] == 1.0


def test_text_styles():
    p = {"title": "Pixel 8", "brand": "Google", "color": float("nan"), "bullets": "  6.2 inch\nscreen "}
    assert product_to_text(p, "title") == "Pixel 8"
    assert product_to_text(p, "full") == "Pixel 8 | Google"
    assert product_to_text(p, "full_bullets") == "Pixel 8 | Google | 6.2 inch screen"