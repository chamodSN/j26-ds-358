"""
M3 Platform Routing Evaluation
------------------------------
Separates a synthetic routing experiment from validation of CSV observations.
Blank CSV values are treated as unknown, never as zero.
"""

import csv
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timezone

from click import group

PROJECT_DIR = Path(__file__).resolve().parents[2]
M3_SRC_DIR = PROJECT_DIR / "member3_knowledge_graph" / "src"
GROUND_TRUTH_FILE = (
    Path(__file__).resolve().parent
    / "routing_ground_truth_empirical.csv"
)

if str(M3_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(M3_SRC_DIR))

from platform_router import (
    PLATFORMS,
    CATEGORY_ROUTING_POLICY,
    rank_by_freshness,
    calculate_routing_score,
    load_graph_categories,
    load_crosswalk,
    route_query,
)

THRESHOLDS = [0.90, 0.93, 0.95]
RELEVANCE_WEIGHT = 0.7
FRESHNESS_WEIGHT = 0.3
LATENCY_REPETITIONS = 5
OPERATIONS_PER_REPETITION = 2000

# Synthetic scenarios only: not real marketplace ground truth.
SCENARIOS = [
    {
        "query": "wireless headphones",
        "category_group": "audio",
        "relevant_platforms": {"ebay", "amazon"},
        "freshness": {"ebay": 0.95, "amazon": 0.70},
    },
    {
        "query": "gaming keyboard",
        "category_group": "computing",
        "relevant_platforms": {"ebay", "amazon"},
        "freshness": {"ebay": 0.60, "amazon": 0.90},
    },
    {
        "query": "wifi router",
        "category_group": "networking",
        "relevant_platforms": {"ebay", "amazon"},
        "freshness": {"ebay": 0.80, "amazon": 0.75},
    },
    {
        "query": "digital camera",
        "category_group": "camera",
        "relevant_platforms": {"ebay", "amazon"},
        "freshness": {"ebay": 0.50, "amazon": 0.85},
    },
    {
        "query": "phone charger",
        "category_group": "power_accessories",
        "relevant_platforms": {"ebay", "amazon"},
        "freshness": {"ebay": 0.90, "amazon": 0.65},
    },
]

REQUIRED_COLUMNS = {
    "query",
    "platform",
    "category_eligible",
    "retrieval_available",
    "relevant_results_found",
    "observation_timestamp",
}


def parse_bool(value, field_name, row_number):
    """Parse a CSV boolean; blank means unknown."""
    if value is None or not value.strip():
        return None

    value = value.strip().lower()

    if value in {"true", "1", "yes", "y"}:
        return True

    if value in {"false", "0", "no", "n"}:
        return False

    raise ValueError(
        f"Invalid {field_name} value on CSV row "
        f"{row_number}: {value!r}"
    )


def load_ground_truth():
    """Load and validate CSV observations without filling in missing data."""
    if not GROUND_TRUTH_FILE.exists():
        print(f"Ground-truth CSV not found: {GROUND_TRUTH_FILE}")
        return []

    with GROUND_TRUTH_FILE.open(
        "r", newline="", encoding="utf-8-sig"
    ) as file:

        reader = csv.DictReader(file)

        if not REQUIRED_COLUMNS.issubset(reader.fieldnames or []):
            missing = sorted(
                REQUIRED_COLUMNS - set(reader.fieldnames or [])
            )

            raise ValueError(
                "Ground-truth CSV is missing required columns: "
                + ", ".join(missing)
            )

        rows = []

        for row_number, raw in enumerate(reader, start=2):
            query = (raw.get("query") or "").strip()
            platform = (raw.get("platform") or "").strip().lower()

            if not query or not platform:
                raise ValueError(
                    f"CSV row {row_number} must include query and platform."
                )

            if platform not in PLATFORMS:
                raise ValueError(
                    f"Unknown platform {platform!r} "
                    f"on CSV row {row_number}."
                )

            count_raw = (
                raw.get("relevant_results_found") or ""
            ).strip()

            count = None

            if count_raw:
                try:
                    count = int(count_raw)
                except ValueError as exc:
                    raise ValueError(
                        "relevant_results_found must be a "
                        "non-negative integer or blank "
                        f"(CSV row {row_number})."
                    ) from exc

                if count < 0:
                    raise ValueError(
                        "relevant_results_found cannot be negative "
                        f"(CSV row {row_number})."
                    )

            rows.append(
                {
                    "query": query,
                    "platform": platform,
                    "category_eligible": parse_bool(
                        raw.get("category_eligible"),
                        "category_eligible",
                        row_number,
                    ),
                    "retrieval_available": parse_bool(
                        raw.get("retrieval_available"),
                        "retrieval_available",
                        row_number,
                    ),
                    "relevant_results_found": count,
                    "observation_timestamp": (
                        (raw.get("observation_timestamp") or "").strip()
                        or None
                    ),
                    "csv_row": row_number,
                }
            )

    return rows


def eligible_platforms(category_group):
    """Return enabled platforms permitted by the category policy."""
    policy = CATEGORY_ROUTING_POLICY.get(
        category_group,
        CATEGORY_ROUTING_POLICY.get("general_electronics", []),
    )

    return [
        platform
        for platform in policy
        if platform in PLATFORMS
        and PLATFORMS[platform].get("enabled", False)
        and "electronics"
        in PLATFORMS[platform].get("supported_categories", [])
    ]


def calculate_simulated_recall(selected, relevant):
    """Synthetic relevant-platform coverage, not product-level recall."""
    relevant = set(relevant)

    if not relevant:
        return None

    return len(set(selected) & relevant) / len(relevant)


def calculate_reduction(selected, eligible):
    """Fraction of eligible platform candidates excluded by routing."""
    eligible = set(eligible)

    if not eligible:
        return None

    return 1.0 - len(set(selected) & eligible) / len(eligible)


def adaptive_route(eligible, freshness, threshold):
    """
    Synthetic threshold experiment using fixed category relevance of 1.0.
    """
    scores = {
        platform: calculate_routing_score(
            category_relevance=1.0,
            freshness_score=freshness.get(platform),
            relevance_weight=RELEVANCE_WEIGHT,
            freshness_weight=FRESHNESS_WEIGHT,
        )
        for platform in eligible
    }

    selected = [
        platform
        for platform in eligible
        if scores[platform] >= threshold
    ]

    return sorted(
        selected,
        key=lambda platform: scores[platform],
        reverse=True,
    )


def select_for_strategy(
    strategy, eligible, freshness, threshold=None
):
    """Run one routing strategy for a synthetic scenario."""
    if strategy in {"all_platforms", "static_kg"}:
        return list(eligible)

    if strategy == "freshness_only":
        return rank_by_freshness(eligible, freshness)

    if strategy == "proposed_adaptive":
        if threshold is None:
            raise ValueError(
                "Adaptive strategy requires a threshold."
            )

        return adaptive_route(eligible, freshness, threshold)

    raise ValueError(f"Unknown strategy: {strategy}")


def measure_latency(
    strategy, eligible, freshness, threshold=None
):
    """
    Measure median local routing computation time per operation,
    in milliseconds.
    """
    timings = []

    for _ in range(LATENCY_REPETITIONS):
        start = time.perf_counter_ns()

        for _ in range(OPERATIONS_PER_REPETITION):
            select_for_strategy(
                strategy,
                eligible,
                freshness,
                threshold,
            )

        elapsed = time.perf_counter_ns() - start

        timings.append(
            elapsed
            / OPERATIONS_PER_REPETITION
            / 1_000_000
        )

    return statistics.median(timings)


def print_synthetic_evaluation():
    """Run and print the synthetic baseline experiment."""
    results = []

    for scenario in SCENARIOS:
        query = scenario["query"]

        eligible = eligible_platforms(
            scenario["category_group"]
        )

        relevant = scenario["relevant_platforms"]
        freshness = scenario["freshness"]

        # Baseline strategies
        for strategy in (
            "all_platforms",
            "static_kg",
            "freshness_only",
        ):
            selected = select_for_strategy(
                strategy,
                eligible,
                freshness,
            )

            results.append(
                {
                    "query": query,
                    "strategy": strategy,
                    "threshold": None,
                    "selected": selected,
                    "recall": calculate_simulated_recall(
                        selected, relevant
                    ),
                    "reduction": calculate_reduction(
                        selected, eligible
                    ),
                    "latency_ms": measure_latency(
                        strategy, eligible, freshness
                    ),
                }
            )

        # Proposed adaptive strategy at each threshold
        for threshold in THRESHOLDS:
            selected = select_for_strategy(
                "proposed_adaptive",
                eligible,
                freshness,
                threshold,
            )

            results.append(
                {
                    "query": query,
                    "strategy": "proposed_adaptive",
                    "threshold": threshold,
                    "selected": selected,
                    "recall": calculate_simulated_recall(
                        selected, relevant
                    ),
                    "reduction": calculate_reduction(
                        selected, eligible
                    ),
                    "latency_ms": measure_latency(
                        "proposed_adaptive",
                        eligible,
                        freshness,
                        threshold,
                    ),
                }
            )

    print("\nSYNTHETIC M3 ROUTING EVALUATION")
    print("=" * 105)

    print(
        f"{'Query':22} {'Strategy':20} {'Threshold':>9} "
        f"{'Recall*':>8} {'Reduction':>10} {'Latency(ms)':>12}"
    )

    print("-" * 105)

    for row in results:
        threshold = (
            f"{row['threshold']:.2f}"
            if row["threshold"] is not None
            else "-"
        )

        recall = (
            f"{row['recall']:.2f}"
            if row["recall"] is not None
            else "N/A"
        )

        reduction = (
            f"{row['reduction']:.0%}"
            if row["reduction"] is not None
            else "N/A"
        )

        print(
            f"{row['query'][:22]:22} "
            f"{row['strategy']:20} "
            f"{threshold:>9} "
            f"{recall:>8} "
            f"{reduction:>10} "
            f"{row['latency_ms']:12.6f}"
        )

        print(
            f"  Selected: "
            f"{', '.join(row['selected']) or '(none)'}"
        )

    # Aggregate results
    groups = defaultdict(list)

    for row in results:
        key = (row["strategy"], row["threshold"])
        groups[key].append(row)

    print("\nSYNTHETIC AGGREGATE RESULTS")
    print("=" * 90)

    print(
        f"{'Strategy':20} {'Threshold':>9} "
        f"{'Mean recall*':>13} {'Mean reduction':>15} "
        f"{'No-candidate rate':>18} "
        f"{'Median latency(ms)':>19}"
)
    print("-" * 90)

    for (strategy, threshold), group in groups.items():
        recalls = [
            row["recall"]
            for row in group
            if row["recall"] is not None
        ]

        reductions = [
            row["reduction"]
            for row in group
            if row["reduction"] is not None
        ]

        empty_selections = sum(
             not row["selected"] for row in group
        )

        no_candidate_rate = empty_selections / len(group)

        latencies = [
            row["latency_ms"]
            for row in group
        ]

        threshold_text = (
            f"{threshold:.2f}"
            if threshold is not None
            else "-"
        )

        recall_text = (
            f"{statistics.mean(recalls):.2f}"
            if recalls
            else "N/A"
        )

        reduction_text = (
            f"{statistics.mean(reductions):.0%}"
            if reductions
            else "N/A"
        )

        print(
            f"{strategy:20} "
            f"{threshold_text:>9} "
            f"{recall_text:>13} "
            f"{reduction_text:>15} "
            f"{no_candidate_rate:17.0%} "
            f"{statistics.median(latencies):19.6f}"
        )

    print("\nSYNTHETIC EVALUATION LIMITATIONS")
    print(
        "- Scenarios, freshness values, and relevance labels are synthetic."
    )
    print(
        "- Both platforms are labelled relevant for every scenario."
    )
    print(
        "- Category relevance is fixed at 1.0, not measured marketplace relevance."
    )
    print(
        "- Threshold results illustrate a simulated trade-off, "
        "not an optimal threshold."
    )
    print(
        "- Amazon is taxonomy-only and has no live product retrieval integration."
    )
    print(
        "- Reduction is simulated candidate reduction, "
        "not measured API-call savings."
    )
    print(
        "- Latency is local routing computation, not end-to-end search latency."
    )
    print(
        "- Recall* is synthetic relevant-platform coverage, "
        "not product-level recall."
    )


def print_ground_truth_validation(rows):
    """Report CSV completeness without fabricating empirical metrics."""
    print("\nCSV GROUND-TRUTH VALIDATION")
    print("=" * 90)

    if not rows:
        print("No CSV observations were available for validation.")
        return

    print(f"CSV rows: {len(rows)}")
    print(
        f"Unique queries: {len({row['query'] for row in rows})}"
    )

    observed_counts = sum(
        row["relevant_results_found"] is not None
        for row in rows
    )

    observed_timestamps = sum(
        row["observation_timestamp"] is not None
        for row in rows
    )

    print(
        f"Rows with relevant-result counts: "
        f"{observed_counts}/{len(rows)}"
    )

    print(
        f"Rows with observation timestamps: "
        f"{observed_timestamps}/{len(rows)}"
    )

    print("\nPer-query observations:")

    print(
        f"{'Query':24} {'Platform':10} {'Eligible':>10} "
        f"{'Retrieval':>11} {'Relevant count':>15} "
        f"{'Timestamp':>22}"
    )

    print("-" * 100)

    for row in rows:
        eligible = (
            "Unknown"
            if row["category_eligible"] is None
            else str(row["category_eligible"])
        )

        retrieval = (
            "Unknown"
            if row["retrieval_available"] is None
            else str(row["retrieval_available"])
        )

        count = (
            "Unknown"
            if row["relevant_results_found"] is None
            else str(row["relevant_results_found"])
        )

        timestamp = (
            row["observation_timestamp"] or "Unknown"
        )

        print(
            f"{row['query'][:24]:24} "
            f"{row['platform']:10} "
            f"{eligible:>10} "
            f"{retrieval:>11} "
            f"{count:>15} "
            f"{timestamp:>22}"
        )

    print("\nEmpirical metric readiness:")

    if observed_counts == 0:
        print(
            "- Empirical relevance metrics cannot be calculated yet: "
            "relevant_results_found is blank for every row."
        )
    else:
        print(
            "- Some result counts are recorded, but counts alone do not "
            "establish product-level recall. A judged relevant-product set "
            "and retrieved product IDs are needed for recall."
        )

    if observed_timestamps == 0:
        print(
            "- Freshness analysis is unavailable because timestamps are blank."
        )
    else:
        print(
            "- Timestamps exist; confirm they represent observation time "
            "before using them in a freshness analysis."
        )

    print(
        "- CSV validation is separate from the synthetic experiment; "
        "the CSV does not silently replace the synthetic scenario labels."
    )


def print_empirical_router_evaluation():
    """Evaluate the real M3 router using empirical eBay observations."""
    import csv
    import statistics
    import time

    empirical_file = (
        Path(__file__).resolve().parent
        / "routing_ground_truth_empirical.csv"
    )
    output_file = (
        Path(__file__).resolve().parent
        / "empirical_router_evaluation.csv"
    )

    if not empirical_file.exists():
        print(f"Empirical dataset not found: {empirical_file}")
        return

    categories = load_graph_categories()
    crosswalk = load_crosswalk()

    with empirical_file.open(
        "r", newline="", encoding="utf-8-sig"
    ) as file:
        observations = list(csv.DictReader(file))

    results = []

    for observation in observations:
        query = observation["query"].strip()
        platform = observation["platform"].strip().lower()
        timestamp_text = observation.get(
            "observation_timestamp", ""
        ).strip()

        observation_times = {}

        if timestamp_text:
            observed_at = datetime.fromisoformat(timestamp_text)
            observation_times[platform] = observed_at

        start = time.perf_counter()

        result = route_query(
            query=query,
            categories=categories,
            crosswalk=crosswalk,
            observation_times=observation_times,
        )

        latency_ms = (time.perf_counter() - start) * 1000

        matched = result.get("matched_category") or {}
        freshness = result.get("observation_freshness", {})
        platform_freshness = freshness.get(platform, {})
        routing_scores = result.get("platform_routing_scores", {})

        results.append({
            "query": query,
            "observed_platform": platform,
            "matched_category": matched.get("category_name", ""),
            "category_source": matched.get("source", ""),
            "routing_status": result.get("routing_status", ""),
            "selected_platforms": ";".join(
                result.get("selected_platforms", [])
            ),
            "retrieval_ready_platforms": ";".join(
                result.get("retrieval_ready_platforms", [])
            ),
            "observed_platform_freshness": platform_freshness.get(
                "freshness_score"
            ),
            "observed_platform_freshness_status": platform_freshness.get(
                "status", "unknown"
            ),
            "observed_platform_routing_score": routing_scores.get(
                platform
            ),
            "relevant_results_found": observation.get(
                "relevant_results_found", ""
            ),
            "total_products_observed": observation.get(
                "total_products_observed", ""
            ),
            "observation_timestamp": timestamp_text,
            "routing_latency_ms": round(latency_ms, 4),
        })

    if not results:
        print("No empirical observations available.")
        return

    fieldnames = list(results[0].keys())

    with output_file.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print("\nEMPIRICAL M3 ROUTER EVALUATION")
    print("=" * 100)

    for row in results:
        print(f"\nQuery: {row['query']}")
        print(f"Matched category: {row['matched_category']}")
        print(f"Category source: {row['category_source']}")
        print(f"Routing status: {row['routing_status']}")
        print(f"Selected platforms: {row['selected_platforms'] or '(none)'}")
        print(
            "Retrieval-ready platforms: "
            f"{row['retrieval_ready_platforms'] or '(none)'}"
        )
        print(
            "Observation freshness: "
            f"{row['observed_platform_freshness']} "
            f"({row['observed_platform_freshness_status']})"
        )
        print(
            "Observed platform routing score: "
            f"{row['observed_platform_routing_score']}"
        )
        print(f"Routing latency: {row['routing_latency_ms']:.4f} ms")

    valid_counts = [
        (int(row["relevant_results_found"]),
         int(row["total_products_observed"]))
        for row in results
        if row["relevant_results_found"] != ""
        and row["total_products_observed"] != ""
        and int(row["total_products_observed"]) > 0
    ]

    if valid_counts:
        relevant_total = sum(item[0] for item in valid_counts)
        product_total = sum(item[1] for item in valid_counts)

        print(
            "\nObserved retrieval precision: "
            f"{relevant_total / product_total:.2%} "
            f"({relevant_total}/{product_total})"
        )

    print(
        "Median route_query latency: "
        f"{statistics.median(row['routing_latency_ms'] for row in results):.4f} ms"
    )
    print(f"Detailed results saved to: {output_file}")
    print(
        "Limitations: one live retrieval-ready platform; "
        "routing scores may be unknown when platform relevance is not supplied. "
        "Precision describes observed products, not routing superiority."
    )

def run_controlled_router_experiment():
    """Test actual route_query threshold behaviour with illustrative inputs."""
    from platform_router import load_graph_categories, load_crosswalk

    categories = load_graph_categories()
    crosswalk = load_crosswalk()

    # Both platforms receive a recent observation timestamp.
    now = datetime.now(timezone.utc)
    observation_times = {
        "ebay": now,
        "amazon": now,
    }

    # Illustrative scores only; these are not empirically measured.
    relevance_scores = {
        "ebay": 0.95,
        "amazon": 0.80,
    }

    query = "wireless headphones"

    print("\nCONTROLLED ROUTER EXPERIMENT")
    print("=" * 85)
    print("Illustrative relevance inputs:", relevance_scores)
    print("Freshness timestamps: recent, generated at runtime")
    print("These results test routing behaviour, not marketplace performance.")

    for threshold in (None, 0.90, 0.93, 0.95):
        result = route_query(
            query=query,
            categories=categories,
            crosswalk=crosswalk,
            observation_times=observation_times,
            platform_relevance_scores=relevance_scores,
            min_routing_score=threshold,
        )

        print(f"\nThreshold: {threshold if threshold is not None else 'None'}")
        print("Matched category:", (result.get("matched_category") or {}).get("category_name"))
        print("Selected:", result["selected_platforms"])
        print("Retrieval-ready:", result["retrieval_ready_platforms"])
        print("Scores:", result["platform_routing_scores"])

def run_router_latency_benchmark(repeats=20):
    """Benchmark local route_query execution across five product queries."""
    from platform_router import load_graph_categories, load_crosswalk

    categories = load_graph_categories()
    crosswalk = load_crosswalk()

    queries = [
        "wireless headphones",
        "gaming keyboards",
        "wifi routers",
        "digital cameras",
        "phone chargers",
    ]

    output_file = (
        Path(__file__).resolve().parent
        / "router_latency_benchmark.csv"
    )

    rows = []

    print("\nREPEATED ROUTER LATENCY BENCHMARK")
    print("=" * 70)
    print(f"Timed repetitions per query: {repeats}")
    print("First run is excluded as a warm-up.")
    print("Measurements cover local routing, not marketplace API latency.")

    for query in queries:
        # Warm-up: excluded from measurements.
        route_query(
            query=query,
            categories=categories,
            crosswalk=crosswalk,
        )

        timings_ms = []

        for _ in range(repeats):
            start = time.perf_counter()

            route_query(
                query=query,
                categories=categories,
                crosswalk=crosswalk,
            )

            elapsed_ms = (time.perf_counter() - start) * 1000
            timings_ms.append(elapsed_ms)

        ordered = sorted(timings_ms)
        p95_index = max(0, int(0.95 * len(ordered)) - 1)

        result = {
            "query": query,
            "runs": len(timings_ms),
            "mean_ms": round(statistics.mean(timings_ms), 3),
            "median_ms": round(statistics.median(timings_ms), 3),
            "p95_ms": round(ordered[p95_index], 3),
            "min_ms": round(min(timings_ms), 3),
            "max_ms": round(max(timings_ms), 3),
        }

        rows.append(result)

        print(
            f"{query:<22} "
            f"median={result['median_ms']:>8.3f} ms | "
            f"mean={result['mean_ms']:>8.3f} ms | "
            f"p95={result['p95_ms']:>8.3f} ms"
        )

    with output_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    all_medians = [row["median_ms"] for row in rows]

    print("-" * 70)
    print(f"Overall median of query medians: "
          f"{statistics.median(all_medians):.3f} ms")
    print(f"Results saved to: {output_file}")

def main():
    ground_truth_rows = load_ground_truth()

    print(
        f"Ground-truth CSV loaded: {len(ground_truth_rows)} rows"
    )

    print_synthetic_evaluation()
    print_ground_truth_validation(ground_truth_rows)
    print_empirical_router_evaluation()
    run_controlled_router_experiment()
    run_router_latency_benchmark()

if __name__ == "__main__":
    main()