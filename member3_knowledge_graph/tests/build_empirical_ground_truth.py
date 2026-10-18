import csv
from collections import defaultdict
from pathlib import Path

TESTS_DIR = Path("member3_knowledge_graph/tests")

INPUT_FILE = TESTS_DIR / "ebay_observations_labeled.csv"
OUTPUT_FILE = TESTS_DIR / "routing_ground_truth_empirical.csv"


def main():
    # Aggregate the actual eBay observations by query.
    query_data = defaultdict(
        lambda: {
            "total": 0,
            "relevant": 0,
            "timestamps": [],
        }
    )

    with INPUT_FILE.open(
        "r", encoding="utf-8-sig", newline=""
    ) as file:
        reader = csv.DictReader(file)

        required = {
            "query",
            "platform",
            "relevant",
            "observed_at_utc",
        }

        if not reader.fieldnames:
            raise ValueError("Input CSV has no headers.")

        missing = required - set(reader.fieldnames)

        if missing:
            raise ValueError(
                f"Missing required columns: {sorted(missing)}"
            )

        for row in reader:
            query = (row["query"] or "").strip()
            platform = (row["platform"] or "").strip().lower()
            label = (row["relevant"] or "").strip()
            timestamp = (row["observed_at_utc"] or "").strip()

            if not query or platform != "ebay":
                continue

            if label not in {"0", "1"}:
                continue

            query_data[query]["total"] += 1

            if label == "1":
                query_data[query]["relevant"] += 1

            if timestamp:
                query_data[query]["timestamps"].append(timestamp)

    # Keep the original ground-truth file unchanged.
    rows = []

    for query, data in sorted(query_data.items()):
        timestamps = data["timestamps"]

        rows.append({
            "query": query,
            "platform": "ebay",
            "category_eligible": "True",
            "retrieval_available": "True",
            "relevant_results_found": data["relevant"],
            "observation_timestamp": max(timestamps) if timestamps else "",
            "total_products_observed": data["total"],
        })

    with OUTPUT_FILE.open(
        "w", encoding="utf-8", newline=""
    ) as file:
        fields = [
            "query",
            "platform",
            "category_eligible",
            "retrieval_available",
            "relevant_results_found",
            "observation_timestamp",
            "total_products_observed",
        ]

        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Empirical eBay query rows: {len(rows)}")
    for row in rows:
        print(
            f"{row['query']}: "
            f"{row['relevant_results_found']}/"
            f"{row['total_products_observed']} relevant; "
            f"timestamp={row['observation_timestamp'] or 'Unknown'}"
        )

    print(f"\nSaved to: {OUTPUT_FILE}")
    print("Amazon was not included because live retrieval is unavailable.")


if __name__ == "__main__":
    main()