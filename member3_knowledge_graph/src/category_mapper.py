
from pathlib import Path
import csv
import re

# Project paths
PROJECT_DIR = Path(__file__).resolve().parent.parent
TAXONOMY_FILE = PROJECT_DIR / "data" / "electronics_taxonomy.csv"

# Initial keyword rules for the prototype.
# These generate candidates, not verified mappings.
CATEGORY_RULES = {
    "headphones": [
        "headphone", "headphones", "headset",
        "earbud", "earbuds", "earphone", "earphones"
    ],
    "speakers": [
        "speaker", "speakers", "soundbar"
    ],
    "microphones": [
        "microphone", "microphones", "mic"
    ],
    "audio_accessories": [
        "audio accessory", "headphone accessory",
        "headphone cushion", "ear pad", "earpads"
    ],
}


def load_taxonomy():
    """Load the canonical Google Electronics taxonomy."""
    categories = []

    with open(
        TAXONOMY_FILE,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:
        reader = csv.DictReader(file)

        for row in reader:
            categories.append({
                "category_id": row["category_id"],
                "category_name": row["category_name"],
                "category_path": row["category_path"],
                "depth": int(row["depth"])
            })

    return categories


def detect_product_type(title):
    """Identify possible product types from the title."""
    text = title.lower()
    detected = []

    for product_type, keywords in CATEGORY_RULES.items():
        for keyword in keywords:
            pattern = r"\b" + re.escape(keyword) + r"\b"

            if re.search(pattern, text):
                detected.append(product_type)
                break

    return detected



def suggest_categories(title, categories):
    """Rank likely product categories, excluding accessory false matches."""

    text = title.lower()
    accessory_terms = [
        "replacement", "replacement cushion", "ear pad",
        "ear pads", "ear tips", "cushion", "cushions",
        "accessory", "accessories", "replacement parts"
    ]

    is_accessory = any(term in text for term in accessory_terms)

    if is_accessory:
        product_type = "accessory"
    elif any(term in text for term in [
        "headphone", "headphones", "headset",
        "earbud", "earbuds", "earphone", "earphones"
    ]):
        product_type = "headphones"
    elif any(term in text for term in [
        "speaker", "speakers", "soundbar"
    ]):
        product_type = "speakers"
    elif any(term in text for term in [
        "microphone", "microphones"
    ]):
        product_type = "microphones"
    else:
        product_type = None

    if product_type is None:
        return []

    scored = []

    for category in categories:
        path = category["category_path"].lower()
        name = category["category_name"].lower()
        score = 0

        if product_type == "headphones":
            if "headphones & headsets" in path:
                score = 100
            elif name in ("headphones", "headsets", "earbuds"):
                score = 90

            # Do not map a complete headphone product to accessories
            if "accessories" in path or "accessory" in path:
                score = 0

        elif product_type == "accessory":
            if "headphone & headset accessories" in path:
                score = 100
            elif "headphone" in path and "accessor" in path:
                score = 80

        elif product_type == "speakers":
            if name == "speakers":
                score = 100
            elif "speaker" in name and "accessor" not in path:
                score = 70

        elif product_type == "microphones":
            if name == "microphones":
                score = 100
            elif "microphone" in name and "accessor" not in path:
                score = 70

        if score > 0:
            scored.append({
                **category,
                "score": score
            })

    # Highest score first; prefer more specific categories on ties
    scored.sort(
        key=lambda item: (item["score"], item["depth"]),
        reverse=True
    )

    return scored



def main():
    categories = load_taxonomy()

    # Example eBay API results from your earlier test.
    # These are examples only, not a persistent dataset.
    sample_products = [
        {
            "ebay_category_ids": ["112529"],
            "title": (
                "Sony WH-1000XM6 The Best Wireless "
                "Noise Canceling Bluetooth Headphones"
            )
        },
        {
            "ebay_category_ids": ["80077", "112529"],
            "title": (
                "Waterproof Bluetooth 5.0 Earbuds "
                "Stereo Sport Wireless Headphones"
            )
        }
    ]

    print("EBAY TO GOOGLE TAXONOMY CANDIDATES")
    print("=" * 70)

    for product in sample_products:
        print(f"\nProduct: {product['title']}")
        print(
            "eBay category IDs: "
            + ", ".join(product["ebay_category_ids"])
        )

        suggestions = suggest_categories(
            product["title"],
            categories
        )

        if not suggestions:
            print("No candidate categories found.")
            continue

        for suggestion in suggestions[:10]:
            print(
                f"Google ID: {suggestion['category_id']} | "
                f"{suggestion['category_path']}"
            )

        print("Status: Candidate suggestions; manual validation required.")

    print("\nMapping candidate generation completed.")


if __name__ == "__main__":
    main()
