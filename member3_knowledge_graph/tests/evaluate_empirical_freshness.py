import csv
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

TESTS_DIR = Path("member3_knowledge_graph/tests")

INPUT_FILE = TESTS_DIR / "ebay_observations_labeled.csv"
OUTPUT_FILE = TESTS_DIR / "empirical_freshness_summary.csv"

# Match the default half-life used by the current freshness model.
HALF_LIFE_HOURS = 24.0


def parse_timestamp(value):
    """Parse an ISO timestamp and normalize it to UTC."""
    if not value:
        return None

    try:
        timestamp = datetime.fromisoformat(value.strip())

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        return timestamp.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def calculate_freshness(age_hours, half_life_hours):
    """Exponential observation-freshness decay."""
    return math.exp(
        -math.log(2) * age_hours / half_life_hours
    )


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Could not find input file: {INPUT_FILE}"
        )

    now = datetime.now(timezone.utc)
    grouped = defaultdict(list)

    with INPUT_FILE.open(
        "r", encoding="utf-8-sig", newline=""
    ) as file:
        reader = csv.DictReader(file)

        required = {
            "query",
            "platform",
            "observed_at_utc",
            "relevant",
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
            timestamp = parse_timestamp(row["observed_at_utc"])
            label = (row["relevant"] or "").strip()

            if not query or platform != "ebay" or timestamp is None:
                continue

            if label not in {"0", "1"}:
                continue

            age_hours = max(
                0.0, (now - timestamp).total_seconds() / 3600
            )

            freshness = calculate_freshness(
                age_hours, HALF_LIFE_HOURS
            )

            grouped[query].append({
                "query": query,
                "platform": platform,
                "observed_at_utc": timestamp.isoformat(),
                "age_hours": age_hours,
                "freshness_score": freshness,
                "relevant": int(label),
            })

    summary = []

    print("\n===== EMPIRICAL OBSERVATION FRESHNESS =====")
    print(f"Evaluation time (UTC): {now.isoformat()}")
    print(f"Freshness half-life: {HALF_LIFE_HOURS} hours")
    print("Note: this measures observation recency, not listing-update age.\n")

    for query, observations in sorted(grouped.items()):
        latest = max(
            observations,
            key=lambda item: item["observed_at_utc"],
        )

        relevant_count = sum(
            item["relevant"] for item in observations
        )

        precision = relevant_count / len(observations)

        summary.append({
            "query": query,
            "platform": "ebay",
            "observations": len(observations),
            "relevant_count": relevant_count,
            "precision": round(precision, 4),
            "latest_observation_utc": latest["observed_at_utc"],
            "latest_observation_age_hours": round(
                latest["age_hours"], 4
            ),
            "freshness_score": round(
                latest["freshness_score"], 6
            ),
            "half_life_hours": HALF_LIFE_HOURS,
        })

        print(
            f"{query}: "
            f"precision={precision * 100:.2f}%, "
            f"latest observation age={latest['age_hours']:.2f} h, "
            f"freshness={latest['freshness_score']:.6f}"
        )

    with OUTPUT_FILE.open(
        "w", encoding="utf-8", newline=""
    ) as file:
        fields = [
            "query",
            "platform",
            "observations",
            "relevant_count",
            "precision",
            "latest_observation_utc",
            "latest_observation_age_hours",
            "freshness_score",
            "half_life_hours",
        ]

        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary)

    print(f"\nSaved summary to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()