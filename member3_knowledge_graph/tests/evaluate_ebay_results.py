import csv
from collections import defaultdict
from pathlib import Path

# File paths relative to the project root
INPUT_FILE = Path(
    "member3_knowledge_graph/tests/ebay_observations_labeled.csv"
)

OUTPUT_FILE = Path(
    "member3_knowledge_graph/tests/ebay_evaluation_summary.csv"
)


def main():
    # Check whether the input CSV exists
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"CSV not found: {INPUT_FILE}\n"
            "Check the filename and project directory."
        )

    results = defaultdict(
        lambda: {"total": 0, "relevant": 0}
    )

    total = 0
    relevant_total = 0
    missing_labels = 0
    invalid_labels = 0

    # Read the labeled observations
    with INPUT_FILE.open(
        "r", encoding="utf-8-sig", newline=""
    ) as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError("The CSV file is empty.")

        # Handle column names regardless of capitalization
        columns = {
            name.strip().lower(): name
            for name in reader.fieldnames
            if name
        }

        if "query" not in columns or "relevant" not in columns:
            raise ValueError(
                "The CSV must contain 'query' and 'relevant' columns.\n"
                f"Found columns: {reader.fieldnames}"
            )

        for row in reader:
            query = (row.get(columns["query"]) or "").strip()
            label = (row.get(columns["relevant"]) or "").strip()

            if not query:
                continue

            # Only 0 and 1 are accepted as valid relevance labels
            if label not in {"0", "1"}:
                if not label:
                    missing_labels += 1
                else:
                    invalid_labels += 1
                continue

            total += 1
            results[query]["total"] += 1

            if label == "1":
                relevant_total += 1
                results[query]["relevant"] += 1

    # Overall results
    print("\n===== REAL EBAY RETRIEVAL EVALUATION =====")
    print(f"Input dataset: {INPUT_FILE}")
    print(f"Valid labeled observations: {total}")
    print(f"Relevant products (1): {relevant_total}")
    print(f"Irrelevant products (0): {total - relevant_total}")
    print(f"Missing labels: {missing_labels}")
    print(f"Invalid labels: {invalid_labels}")

    if total > 0:
        overall_precision = relevant_total / total
        print(
            f"Overall precision: {overall_precision:.4f} "
            f"({overall_precision * 100:.2f}%)"
        )
    else:
        print("No valid labels found; precision cannot be calculated.")

    # Results for each query
    print("\n===== PRECISION BY QUERY =====")

    summary_rows = []

    for query, data in sorted(results.items()):
        count = data["total"]
        relevant = data["relevant"]
        precision = relevant / count if count else 0

        print(
            f"{query}: {relevant}/{count} relevant "
            f"({precision * 100:.2f}%)"
        )

        summary_rows.append({
            "query": query,
            "total_labeled": count,
            "relevant_count": relevant,
            "irrelevant_count": count - relevant,
            "precision": round(precision, 4),
            "precision_percent": round(precision * 100, 2),
        })

    # Save the summary to a new CSV
    with OUTPUT_FILE.open(
        "w", encoding="utf-8", newline=""
    ) as file:
        fieldnames = [
            "query",
            "total_labeled",
            "relevant_count",
            "irrelevant_count",
            "precision",
            "precision_percent",
        ]

        writer = csv.DictWriter(
            file, fieldnames=fieldnames
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"\nSummary saved to: {OUTPUT_FILE}")

    print("\nIMPORTANT:")
    print("These metrics evaluate retrieved-product relevance.")
    print("They do not independently prove routing superiority.")
    print("Review all labels before reporting the results.")


if __name__ == "__main__":
    main()