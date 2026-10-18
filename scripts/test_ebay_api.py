
import os
import sys
import csv
from pathlib import Path
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

# -------------------------------------
# 1. Project setup
# -------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent.parent
M3_SRC_DIR = PROJECT_DIR / "member3_knowledge_graph" / "src"

if str(M3_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(M3_SRC_DIR))

from freshness_model import calculate_freshness
from platform_router import (
    load_graph_categories,
    load_crosswalk,
    route_query,
)

load_dotenv(PROJECT_DIR / ".env")

CLIENT_ID = os.getenv("EBAY_CLIENT_ID")
CLIENT_SECRET = os.getenv("EBAY_CLIENT_SECRET")
ENVIRONMENT = os.getenv("EBAY_ENVIRONMENT", "").upper()

if not CLIENT_ID or not CLIENT_SECRET:
    raise ValueError("Missing eBay credentials in root .env")

if ENVIRONMENT != "PRODUCTION":
    raise ValueError("Set EBAY_ENVIRONMENT=PRODUCTION in .env")

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
BROWSE_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"

HEADERS_BASE = {
    "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
    "Accept": "application/json",
}

QUERIES = [
    "wireless headphones",
    "gaming keyboards",
    "wifi routers",
    "digital cameras",
    "phone chargers",
]

OUTPUT_DIR = PROJECT_DIR / "member3_knowledge_graph" / "tests"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

timestamp_label = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
OUTPUT_CSV = OUTPUT_DIR / f"ebay_observations_{timestamp_label}.csv"


# -------------------------------------
# 2. Authenticate with eBay
# -------------------------------------

print("Requesting eBay OAuth token...")

token_response = requests.post(
    TOKEN_URL,
    auth=(CLIENT_ID, CLIENT_SECRET),
    data={
        "grant_type": "client_credentials",
        "scope": "https://api.ebay.com/oauth/api_scope",
    },
    timeout=30,
)

if token_response.status_code != 200:
    print("OAuth failed. HTTP status:", token_response.status_code)
    print("Response:", token_response.text[:500])
    raise SystemExit(1)

access_token = token_response.json()["access_token"]

headers = {
    **HEADERS_BASE,
    "Authorization": f"Bearer {access_token}",
}

print("OAuth authentication successful.")


# -------------------------------------
# 3. Load M3 resources once
# -------------------------------------

print("Loading M3 taxonomy and crosswalk...")

categories = load_graph_categories()
crosswalk = load_crosswalk()

rows = []
summary = []


# -------------------------------------
# 4. Search, route, and record
# -------------------------------------

for query in QUERIES:
    print(f"\n{'=' * 60}")
    print("QUERY:", query)
    print("=" * 60)



    try:
        response = requests.get(
            BROWSE_URL,
            headers=headers,
            params={"q": query, "limit": 10},
            timeout=30,
        )
    except requests.RequestException as exc:
        print("Request failed:", str(exc))
        summary.append({
            "query": query,
            "http_status": "REQUEST_ERROR",
            "products_returned": 0,
            "routing_platforms": "",
        })
        continue

    print("eBay HTTP status:", response.status_code)
    observed_at = datetime.now(timezone.utc)

    if response.status_code != 200:
        print("Search failed:", response.text[:300])
        summary.append({
            "query": query,
            "http_status": response.status_code,
            "products_returned": 0,
            "routing_platforms": "",
        })
        continue

    data = response.json()
    items = data.get("itemSummaries", [])

    freshness = calculate_freshness(
        last_observed_at=observed_at,
        half_life_hours=24.0,
        now=datetime.now(timezone.utc),
    )

    routing = route_query(
        query=query,
        categories=categories,
        crosswalk=crosswalk,
        observation_times={"ebay": observed_at},
        min_routing_score=0.75,
        platform_relevance_scores={
            "ebay": 1.0,
            "amazon": 0.5,
        },
    )

    best_category = routing.get("matched_category") or {}

    category_name = best_category.get("category_name", "")
    category_path = best_category.get("category_path", "")
    category_source = best_category.get("source", "")
    category_score = best_category.get("score")

    selected_platforms = routing.get("selected_platforms", [])
    ready_platforms = routing.get("retrieval_ready_platforms", [])

    routing_scores = routing.get("platform_routing_scores", {})
    ebay_scores = routing_scores.get("ebay", {})

    print("Best category:", category_name or "Not available")
    print("Selected platforms:", selected_platforms)
    print("Retrieval-ready platforms:", ready_platforms)
    print("Freshness score:", freshness["freshness_score"])
    print("Products returned:", len(items))

    for item in items:
        price = item.get("price") or {}

        rows.append({
            "query": query,
            "platform": "ebay",
            "observed_at_utc": observed_at.isoformat(),
            "observation_freshness_score": freshness["freshness_score"],
            "category_name": category_name,
            "category_path": category_path,
            "category_source": category_source,
            "category_score": category_score,
            "routing_score": ebay_scores.get("routing_score"),
            "selected_platforms": "|".join(selected_platforms),
            "retrieval_ready_platforms": "|".join(ready_platforms),
            "product_id": item.get("itemId", ""),
            "title": item.get("title", ""),
            "price": price.get("value", ""),
            "currency": price.get("currency", ""),
            "category_ids": "|".join(item.get("leafCategoryIds", [])),
            "product_url": item.get("itemWebUrl", ""),
        })

    summary.append({
        "query": query,
        "http_status": response.status_code,
        "products_returned": len(items),
        "routing_platforms": "|".join(ready_platforms),
    })


# -------------------------------------
# 5. Save observations and summary
# -------------------------------------

product_fields = [
    "query",
    "platform",
    "observed_at_utc",
    "observation_freshness_score",
    "category_name",
    "category_path",
    "category_source",
    "category_score",
    "routing_score",
    "selected_platforms",
    "retrieval_ready_platforms",
    "product_id",
    "title",
    "price",
    "currency",
    "category_ids",
    "product_url",
]

with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as file:
    writer = csv.DictWriter(file, fieldnames=product_fields)
    writer.writeheader()
    writer.writerows(rows)

summary_csv = OUTPUT_DIR / f"ebay_query_summary_{timestamp_label}.csv"

with summary_csv.open("w", newline="", encoding="utf-8-sig") as file:
    fields = [
        "query",
        "http_status",
        "products_returned",
        "routing_platforms",
    ]
    writer = csv.DictWriter(file, fieldnames=fields)
    writer.writeheader()
    writer.writerows(summary)

print("\n" + "=" * 60)
print("EVALUATION COLLECTION COMPLETE")
print("=" * 60)
print("Queries attempted:", len(QUERIES))
print("Product observations saved:", len(rows))
print("Successful product CSV:", OUTPUT_CSV)
print("Query summary CSV:", summary_csv)
print("\nNote: observation freshness measures collection recency,")
print("not the seller's actual listing update time.")
print("Product relevance has not yet been manually judged.")
