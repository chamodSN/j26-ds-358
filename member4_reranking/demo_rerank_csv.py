"""
Demo: send YOUR OWN real product list to the running M4 service (POST /rerank) and show
the order BEFORE (as the shops listed them) vs AFTER (cross-encoder order), with your E/S/C/I labels.

Usage (ONE terminal, no server needed - runs /rerank inside this script):
    python member4_reranking/demo_rerank_csv.py member4_reranking/results/s11b_real_pilot.csv
    python member4_reranking/demo_rerank_csv.py member4_reranking/results/s11b_real_pilot.csv --query a01
Optional: --url http://localhost:8004  to call a running M4 service instead.

CSV columns used (same as s11b template): query_id, query, category_standin, platform, title, brand,
color, features, label, search_rank, price_text.  Rows with an empty title are skipped.
"""
import argparse
import math
import sys

import os
import httpx
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

GAIN = {"E": 1.0, "S": 0.1, "C": 0.01, "I": 0.0}
PLATFORMS = {"ebay": "ebay", "aliexpress": "aliexpress"}   # team Platform enum: ebay, aliexpress, esci


def ndcg10(labels):
    gains = [GAIN.get(l, 0.0) for l in labels]
    dcg = sum(g / math.log2(i + 2) for i, g in enumerate(gains[:10]))
    ideal = sum(g / math.log2(i + 2) for i, g in enumerate(sorted(gains, reverse=True)[:10]))
    return dcg / ideal if ideal > 0 else 0.0


def build_request(g: pd.DataFrame, use_category: bool) -> dict:
    products = []
    for i, r in enumerate(g.itertuples(), start=1):
        attrs = {"source": str(r.platform)}                       # metadata: ignored by the model
        if str(r.brand).strip():
            attrs["brand"] = str(r.brand).strip()
        if str(r.color).strip():
            attrs["color"] = str(r.color).strip()
        if str(r.features).strip():
            attrs["features"] = str(r.features).strip()
        plat = PLATFORMS.get(str(r.platform).lower().strip(), "esci")   # other shops -> 'esci' (enum stand-in)
        products.append({
            "canonical_id": str(r.listing_id), "canonical_title": str(r.title),
            "platforms": [plat], "prices": [{"platform": plat, "price": 0.0, "currency": "LKR"}],
            "harmonized_attributes": attrs, "retrieval_score": max(0.0, 1 - (i - 1) / len(g)),
            "source_product_ids": [str(r.listing_id)]})
    req = {"query_id": str(g.query_id.iloc[0]), "query": str(g["query"].iloc[0]), "products": products,
           "total_candidates_received": len(products), "max_results": len(products)}
    if use_category and str(g.category_standin.iloc[0]).strip():
        req["taxonomy_path"] = str(g.category_standin.iloc[0]).strip()
    return req


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--url", default=None, help="call a running M4 service instead of running it here")
    ap.add_argument("--query", default=None, help="only this query_id")
    ap.add_argument("--no-category", action="store_true", help="do not send the category (M3 not connected)")
    a = ap.parse_args()

    d = pd.read_csv(a.csv, keep_default_na=False, dtype=str)
    d = d[d.title.str.strip() != ""].copy()
    d["search_rank_n"] = pd.to_numeric(d.get("search_rank", ""), errors="coerce").fillna(99)
    if a.query:
        d = d[d.query_id == a.query]
    if d.empty:
        sys.exit("no rows to show")

    totals = []
    if a.url:
        client_cm = httpx.Client(timeout=120); base = a.url
    else:                                                          # run the real /rerank in-process
        from fastapi.testclient import TestClient
        from member4_reranking.api import app
        client_cm = TestClient(app); base = ""
    with client_cm as client:
        for qid, g in d.groupby("query_id", sort=True):
            g = g.sort_values(["search_rank_n", "listing_id"])        # BEFORE = order the shops showed
            req = build_request(g, use_category=not a.no_category)
            r = client.post(f"{base}/rerank", json=req)
            if r.status_code != 200:
                print(f"{qid}: HTTP {r.status_code} {r.text[:200]}"); continue
            body = r.json()
            lab = dict(zip(g.listing_id, g.label))
            before = list(g.label)
            after = [lab[x["canonical_id"]] for x in body["results"]]
            nb, na = ndcg10(before), ndcg10(after)
            if len(set(before)) > 1:
                totals.append((nb, na))
            print("=" * 100)
            print(f"{qid}  query: {req['query']!r}")
            print(f"     model read: {body['focused_query']!r}   |   M4 time {body.get('m4_latency_ms')} ms")
            print(f"     BEFORE (shop order): {' '.join(before)}   NDCG@10 {nb:.3f}")
            print(f"     AFTER  (M4 order)  : {' '.join(after)}   NDCG@10 {na:.3f}")
            print(f"     {'rank':>4} {'label':>5} {'score':>6} {'match':>6} {'lowconf':>7}  title")
            for x in body["results"]:
                print(f"     {x['rank']:>4} {lab[x['canonical_id']]:>5} {x['relevance_score']:>6.3f} "
                      f"{x['match_label']:>6} {str(x['low_confidence']):>7}  {x['canonical_title'][:60]}")
    if totals:
        print("=" * 100)
        print(f"Queries with mixed labels: {len(totals)} | mean NDCG@10 BEFORE {sum(t[0] for t in totals)/len(totals):.3f}"
              f" -> AFTER {sum(t[1] for t in totals)/len(totals):.3f}")


if __name__ == "__main__":
    main()