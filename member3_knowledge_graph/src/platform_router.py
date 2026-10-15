
from pathlib import Path
import csv


PROJECT_DIR = Path(__file__).resolve().parent.parent
TAXONOMY_FILE = PROJECT_DIR / "data" / "electronics_taxonomy.csv"


# Only enable a platform when its API access is configured and tested.
PLATFORMS = {
    "ebay": {
        "enabled": True,
        "supported_categories": ["electronics"],
    },
    "aliexpress": {
        "enabled": False,
        "supported_categories": ["electronics"],
    },
}


def load_taxonomy():
    """Load Google Electronics taxonomy categories."""
    with open(
        TAXONOMY_FILE,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:
        return list(csv.DictReader(file))


def classify_query(query, categories):
    """Find possible Google taxonomy categories from a search query."""
    query_lower = query.lower()
    matches = []

    for category in categories:
        name = category["category_name"].lower()

        if name in query_lower:
            matches.append(category)

    # Prefer more specific category paths.
    matches.sort(
        key=lambda row: int(row["depth"]),
        reverse=True
    )

    return matches


def route_query(query, categories):
    """Choose enabled marketplaces for an electronics query."""
    matches = classify_query(query, categories)

    selected_platforms = []

    for platform, config in PLATFORMS.items():
        if not config["enabled"]:
            continue

        # Initial prototype: enabled platforms support electronics.
        selected_platforms.append(platform)

    return {
        "query": query,
        "matched_categories": [
            {
                "category_id": row["category_id"],
                "category_path": row["category_path"],
            }
            for row in matches[:5]
        ],
        "selected_platforms": selected_platforms,
        "routing_method": "initial_rule_based",
    }


def main():
    categories = load_taxonomy()

    test_queries = [
        "wireless headphones",
        "bluetooth speakers",
        "gaming keyboards",
        "USB microphones",
    ]

    for query in test_queries:
        result = route_query(query, categories)

        print("\n" + "=" * 60)
        print(f"Query: {result['query']}")
        print(f"Platforms: {result['selected_platforms']}")
        print(f"Method: {result['routing_method']}")

        if result["matched_categories"]:
            print("Category candidates:")

            for category in result["matched_categories"]:
                print(
                    f"  {category['category_id']} | "
                    f"{category['category_path']}"
                )
        else:
            print("No exact category-name match found.")


if __name__ == "__main__":
    main()
