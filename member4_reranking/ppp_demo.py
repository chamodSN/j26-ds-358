"""
Novelty 2 demo: the final ranked list (order = Novelty 1) with, for the country of the user who searched,
the real price, the PPP-normalized price and the category tier vs THAT country's own market.

Run from the repo root (no server needed, uses the real /rerank code):
    python member4_reranking/ppp_demo.py member4_reranking/results/s11b_real_pilot.csv --query a01 --country LKA
    python member4_reranking/ppp_demo.py member4_reranking/results/s11b_real_pilot.csv --query a01 --country PAK

Uses the CSV columns: query_id, query, listing_id, title, brand, color, features, price_text.
Currency is read from price_text: 'US $..' -> USD, 'PKR' -> PKR, otherwise 'Rs'/'LKR'/'රු' -> LKR.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import pandas as pd
from fastapi.testclient import TestClient

from member4_reranking.api import app
from member4_reranking.src.ppp import COUNTRY_NAME, parse_price


def currency_of(text: str):
    t = str(text)
    if not re.search(r"\d", t):
        return None
    if "US" in t.upper() or "$" in t:
        return "USD"
    if "PKR" in t.upper():
        return "PKR"
    return "LKR"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--query", default=None)
    ap.add_argument("--country", default="LKA", choices=["LKA", "PAK"], help="country of the user who searches")
    a = ap.parse_args()

    d = pd.read_csv(a.csv, keep_default_na=False, dtype=str)
    d = d[d.title.str.strip() != ""]
    if a.query:
        d = d[d.query_id == a.query]
    client = TestClient(app)
    for qid, g in d.groupby("query_id", sort=True):
        products = []
        for r in g.itertuples():
            cur = currency_of(r.price_text)
            if cur is None:
                continue                                    # no price -> cannot show Novelty 2 for it
            attrs = {k: str(getattr(r, k)).strip() for k in ("brand", "color", "features") if str(getattr(r, k)).strip()}
            products.append({"canonical_id": r.listing_id, "canonical_title": r.title, "platforms": ["esci"],
                             "prices": [{"platform": "esci", "price": parse_price(r.price_text), "currency": cur}],
                             "harmonized_attributes": attrs, "retrieval_score": 0.5,
                             "source_product_ids": [r.listing_id]})
        req = {"query_id": qid, "query": g["query"].iloc[0], "products": products,
               "total_candidates_received": len(products), "max_results": len(products), "user_country": a.country}
        r = client.post("/rerank", json=req)
        if r.status_code != 200:
            print(qid, r.status_code, r.text[:300]); continue
        b = r.json()
        cur = (b["results"][0].get("user_view") or {}).get("currency", "?") if b["results"] else "?"
        print("=" * 112)
        print(f"{qid}  {COUNTRY_NAME[a.country]} user searches: {req['query']!r}")
        print(f"order = Novelty 1 (relevance) | price, PPP price, tier = Novelty 2 (display only) | rates as of {b.get('rates_as_of')}")
        print(f"{'#':>2} {'match':<6} {'title':<46} {'price (' + cur + ')':>15} {'PPP int$':>9}  tier ({COUNTRY_NAME[a.country]} market)")
        for x in b["results"]:
            u = x.get("user_view") or {}
            tier = u.get("price_tier") or ("-" if u.get("tier_category") else "- (not a phone)")
            print(f"{x['rank']:>2} {x['match_label']:<6} {x['canonical_title'][:46]:<46} "
                  f"{u.get('price', 0):>15,.0f} {u.get('ppp_intl_dollars', 0):>9,.0f}  {tier}")


if __name__ == "__main__":
    main()