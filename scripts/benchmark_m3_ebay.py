
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from statistics import mean, median

import requests
from dotenv import load_dotenv


# =====================================================
# 1. Project setup
# =====================================================

PROJECT_DIR = Path(__file__).resolve().parents[1]
M3_SRC_DIR = PROJECT_DIR / "member3_knowledge_graph" / "src"

if str(M3_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(M3_SRC_DIR))

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
    raise ValueError("Missing eBay API credentials in .env")

if ENVIRONMENT != "PRODUCTION":
    raise ValueError("Set EBAY_ENVIRONMENT=PRODUCTION in .env")


# =====================================================
# 2. Reproducible benchmark configuration
# =====================================================

QUERIES = [
    "wireless headphones",
    "gaming keyboard",
    "wifi router",
    "digital camera",
    "phone charger",
]

RESULT_LIMIT = 5

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
BROWSE_URL = (
    "https://api.ebay.com/buy/browse/v1/item_summary/search"
)

MARKETPLACE_ID = "EBAY_US"


# =====================================================
# 3. Authentication
# =====================================================

def get_access_token():
    response = requests.post(
        TOKEN_URL,
        auth=(CLIENT_ID, CLIENT_SECRET),
        data={
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope",
        },
        timeout=30,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"eBay OAuth failed: HTTP {response.status_code}"
        )

    return response.json()["access_token"]


# =====================================================
# 4. Live retrieval
# =====================================================

def search_ebay(query, headers):
    started = time.perf_counter()

    response = requests.get(
        BROWSE_URL,
        headers=headers,
        params={
            "q": query,
            "limit": RESULT_LIMIT,
        },
        timeout=30,
    )

    latency_ms = (time.perf_counter() - started) * 1000

    if response.status_code != 200:
        return {
            "status": response.status_code,
            "latency_ms": latency_ms,
            "items": [],
            "observed_at": None,
        }

    # Record the response observation time, not listing-update time.
    observed_at = datetime.now(timezone.utc)

    # Keep the raw response in memory only.
    items = response.json().get("itemSummaries", [])

    return {
        "status": response.status_code,
        "latency_ms": latency_ms,
        "items": items,
        "observed_at": observed_at,
    }


# =====================================================
# 5. Manual relevance assessment
# =====================================================

def judge_results(query, items):
    """
    Ask the researcher to judge each returned title.
    Raw titles and labels are not written to disk.
    """
    judged = 0
    relevant = 0

    print("\nMANUAL RELEVANCE ASSESSMENT")
    print("Judge relevance to the original search query.")
    print("Enter y = relevant, n = not relevant, u = unsure.")

    for index, item in enumerate(items, start=1):
        title = item.get("title", "Unknown title")

        print(f"\nResult {index}: {title}")

        while True:
            answer = input(
                "Relevant to this query? [y/n/u]: "
            ).strip().lower()

            if answer in {"y", "n", "u"}:
                break

            print("Please enter y, n, or u.")

        if answer == "u":
            continue

        judged += 1

        if answer == "y":
            relevant += 1

    precision = relevant / judged if judged else None

    return {
        "judged_count": judged,
        "relevant_count": relevant,
        "precision_at_judged": precision,
    }


# =====================================================
# 6. Run benchmark
# =====================================================

def run_benchmark():
    print("\nM3 REAL-QUERY eBAY BENCHMARK")
    print("=" * 72)
    print("Marketplace:", MARKETPLACE_ID)
    print("Queries:", len(QUERIES))
    print("Maximum results per query:", RESULT_LIMIT)
    print("Raw listing data will not be saved to disk.")

    print("\nLoading M3 taxonomy and crosswalk...")
    categories = load_graph_categories()
    crosswalk = load_crosswalk()

    token = get_access_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": MARKETPLACE_ID,
        "Accept": "application/json",
    }

    print("eBay authentication successful.")

    # Keep observation timestamps in memory only.
    observation_times = {}

    # Aggregate metrics only; no product titles or IDs.
    summaries = []

    for number, query in enumerate(QUERIES, start=1):
        print("\n" + "=" * 72)
        print(f"QUERY {number}/{len(QUERIES)}: {query}")
        print("=" * 72)

        route_started = time.perf_counter()

        routing = route_query(
            query=query,
            categories=categories,
            crosswalk=crosswalk,
            observation_times=observation_times,
            # No arbitrary score threshold is applied.
        )

        routing_latency_ms = (
            time.perf_counter() - route_started
        ) * 1000

        matched = routing.get("matched_category")
        selected = routing.get("selected_platforms", [])
        ready = routing.get("retrieval_ready_platforms", [])

        print(
            "Matched category:",
            matched["category_name"] if matched else "No match",
        )
        print(
            "Category path:",
            matched["category_path"] if matched else "N/A",
        )
        print("Selected platforms:", selected)
        print("Live-ready platforms:", ready)
        print(f"Routing latency: {routing_latency_ms:.3f} ms")

        # Do not imply that Amazon has live retrieval.
        if "ebay" not in ready:
            print("eBay not selected as live-ready; retrieval skipped.")

            summaries.append({
                "query": query,
                "category_matched": matched is not None,
                "routing_latency_ms": routing_latency_ms,
                "api_status": None,
                "api_latency_ms": None,
                "result_count": 0,
                "judged_count": 0,
                "relevant_count": 0,
                "precision_at_judged": None,
            })
            continue

        live = search_ebay(query, headers)

        print("eBay API status:", live["status"])
        print(f"eBay API latency: {live['latency_ms']:.2f} ms")

        if live["status"] != 200:
            print("Retrieval failed; no relevance assessment performed.")

            summaries.append({
                "query": query,
                "category_matched": matched is not None,
                "routing_latency_ms": routing_latency_ms,
                "api_status": live["status"],
                "api_latency_ms": live["latency_ms"],
                "result_count": 0,
                "judged_count": 0,
                "relevant_count": 0,
                "precision_at_judged": None,
            })
            continue

        # Update freshness only after a successful observation.
        observation_times["ebay"] = live["observed_at"]

        items = live["items"]
        print("Results returned:", len(items))

        judgments = judge_results(query, items)

        precision = judgments["precision_at_judged"]

        print("\nQuery summary:")
        print("  Results returned:", len(items))
        print("  Manually judged:", judgments["judged_count"])
        print("  Relevant among judged:", judgments["relevant_count"])

        if precision is not None:
            print(f"  Precision among judged: {precision:.2%}")
        else:
            print("  Precision among judged: unavailable")

        summaries.append({
            "query": query,
            "category_matched": matched is not None,
            "routing_latency_ms": routing_latency_ms,
            "api_status": live["status"],
            "api_latency_ms": live["latency_ms"],
            "result_count": len(items),
            "judged_count": judgments["judged_count"],
            "relevant_count": judgments["relevant_count"],
            "precision_at_judged": precision,
        })

        # Drop references to listing records before continuing.
        del items
        del live

    # =================================================
    # 7. Aggregate report
    # =================================================

    print("\n\nM3 BENCHMARK SUMMARY")
    print("=" * 100)
    print(
        f"{'Query':22} {'Category':>9} {'HTTP':>6} "
        f"{'Results':>7} {'Judged':>7} {'Relevant':>9} "
        f"{'Precision':>11} {'Route ms':>10} {'API ms':>10}"
    )
    print("-" * 100)

    for row in summaries:
        precision_text = (
            f"{row['precision_at_judged']:.1%}"
            if row["precision_at_judged"] is not None
            else "N/A"
        )

        print(
            f"{row['query'][:22]:22} "
            f"{str(row['category_matched']):>9} "
            f"{str(row['api_status'] or '-'):>6} "
            f"{row['result_count']:7d} "
            f"{row['judged_count']:7d} "
            f"{row['relevant_count']:9d} "
            f"{precision_text:>11} "
            f"{row['routing_latency_ms']:10.3f} "
            f"{row['api_latency_ms'] if row['api_latency_ms'] is not None else 0:10.2f}"
        )

    valid_routes = summaries
    successful_api = [
        row for row in summaries if row["api_status"] == 200
    ]
    judged_rows = [
        row for row in summaries if row["judged_count"] > 0
    ]

    print("\nAGGREGATE METRICS")
    print("-" * 50)

    if valid_routes:
        print(
            "Category match rate: "
            f"{sum(row['category_matched'] for row in valid_routes) / len(valid_routes):.1%}"
        )
        print(
            "Median routing latency: "
            f"{median(row['routing_latency_ms'] for row in valid_routes):.3f} ms"
        )

    if successful_api:
        print(
            "Successful eBay API requests: "
            f"{len(successful_api)}/{len(QUERIES)}"
        )
        print(
            "Median eBay API latency: "
            f"{median(row['api_latency_ms'] for row in successful_api):.2f} ms"
        )
        print(
            "Mean results per successful query: "
            f"{mean(row['result_count'] for row in successful_api):.2f}"
        )

    total_judged = sum(row["judged_count"] for row in judged_rows)
    total_relevant = sum(row["relevant_count"] for row in judged_rows)

    if total_judged:
        print(
            "Micro-averaged precision among manually judged results: "
            f"{total_relevant / total_judged:.2%}"
        )
        print(f"Total manually judged results: {total_judged}")
    else:
        print("No results were manually judged.")

    print("\nLIMITATIONS")
    print("- This benchmark evaluates M3 category matching and eBay retrieval.")
    print("- It does not measure cross-platform recall or search reduction.")
    print("- Precision is based on your manual judgments of returned results.")
    print("- Five queries are a pilot benchmark, not a statistically broad evaluation.")
    print("- Observation freshness is not actual listing freshness.")
    print("- Raw listings and individual relevance labels are not saved.")
    print("- Aggregate output is printed only; rerun to reproduce the experiment.")

    return summaries


if __name__ == "__main__":
    run_benchmark()
