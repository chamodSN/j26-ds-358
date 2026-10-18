import json
import re
from functools import lru_cache
from pathlib import Path
from turtle import title

from httpx2 import query


PROJECT_ROOT = Path(__file__).resolve().parent.parent

CATALOG_FILE = (
    PROJECT_ROOT
    / "member3_knowledge_graph"
    / "data"
    / "amazon_electronics_products.jsonl"
)

# Require the actual product type in the title.
PRODUCT_TYPES = {
    "headphones": {
        "headphones", "headphone", "headsets", "headset",
        "earbuds", "earphones", "earphones",
    },
    "keyboard": {"keyboard", "keyboards"},
    "mouse": {"mouse", "mice"},
    "router": {"router", "routers"},
    "camera": {"camera", "cameras", "camcorder", "camcorders"},
    "monitor": {"monitor", "monitors", "display", "displays"},
    "laptop": {"laptop", "laptops", "notebook", "notebooks"},
    "charger": {"charger", "chargers"},
    "speaker": {"speaker", "speakers"},
    "microphone": {"microphone", "microphones"},
    "webcam": {"webcam", "webcams"},
    "earbuds": {"earbuds", "earphones"},
    "tablet": {"tablet", "tablets"},
    "printer": {"printer", "printers"},
}

# Reject accessories when the user is searching for the main product.

ACCESSORY_TERMS = {
    "case", "cases", "cover", "covers", "protector",
    "protective", "replacement", "cable", "cord", "wire",
    "adapter", "adapters", "stand", "holder", "skin",
    "keychain", "carrying", "tips", "tip", "ear tips",
    "earbud tips", "foam tips", "ear cushions",
    "earpads", "ear pad", "ear pads", "cleaner",
    "cleaning", "cleaning kit", "repair", "spare",
    "accessory", "accessories", "storage", "pouch",
    "silicone case", "charging case",
}

IGNORED_QUERY_WORDS = {
    "under", "below", "less", "than", "over", "above",
    "more", "price", "maximum", "minimum", "max", "min",
    "usd", "lkr", "rs", "in", "for", "with", "and",
    "the", "a", "an", "wireless", "wired",
}


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


@lru_cache(maxsize=1)
def load_amazon_catalog() -> tuple[dict, ...]:
    """Load the local catalog once and reuse it across searches."""
    if not CATALOG_FILE.exists():
        return ()

    products = []

    with CATALOG_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue

            try:
                product = json.loads(line)
            except json.JSONDecodeError:
                continue

            if isinstance(product, dict):
                products.append(product)

    return tuple(products)


def identify_product_type(query_tokens: set[str]) -> set[str]:
    """Identify the product type requested by the user."""
    for aliases in PRODUCT_TYPES.values():
        if query_tokens & aliases:
            return aliases

    return set()

def matches_connection_type(title: str, query: str) -> bool:
    """Ensure wired and wireless searches return the requested type."""
    title_lower = title.lower()
    query_lower = query.lower()

    wants_wireless = "wireless" in query_lower
    wants_wired = bool(
        re.search(r"\bwired\b", query_lower)
    ) and not wants_wireless

    if wants_wireless:
        wired_indicators = [
            "wired", "3.5mm plug", "3.5 mm plug",
            "aux cable", "corded", "usb cable",
        ]
        if any(term in title_lower for term in wired_indicators):
            return False

    if wants_wired:
        wireless_indicators = [
            "wireless", "bluetooth", "true wireless",
            "tws", "cordless",
        ]
        if any(term in title_lower for term in wireless_indicators):
            return False

    return True


def search_amazon_products(
    query: str,
    limit: int = 10,
    attributes: dict | None = None,
) -> list[dict]:
    """
    Search historical Amazon metadata using title-first matching.

    These are dataset records, not verified live Amazon listings.
    """
    attributes = attributes or {}
    raw_tokens = tokenize(query)

    # Do not let price words dominate product matching.
    query_tokens = {
        token
        for token in raw_tokens
        if token not in IGNORED_QUERY_WORDS
        and not token.isdigit()
    }

    required_types = identify_product_type(query_tokens)

    # Treat an explicitly requested accessory as a valid target.
    accessory_requested = bool(
        query_tokens & ACCESSORY_TERMS
    )

    price_min = attributes.get("price_min")
    price_max = attributes.get("price_max")
    requested_currency = attributes.get("currency")

    results = []

    for product in load_amazon_catalog():
        title = str(product.get("title") or "").strip()
        if not title:
            continue

        title_tokens = tokenize(title)

        if not matches_connection_type(title, query):
            continue
        # When a main product type is clear, require it in the title.
        # This prevents a headphone case from matching headphones.
        if required_types and not (title_tokens & required_types):
            continue

        # Exclude accessory-like titles for main-product searches.
        # Reject accessory listings when the query asks for a main product.
        accessory_found = bool(title_tokens & ACCESSORY_TERMS)

        if required_types and not accessory_requested and accessory_found:
            continue
        # Score matches using the title, not the category path alone.
        relevant_query_tokens = query_tokens - required_types
        title_overlap = title_tokens & relevant_query_tokens

        if relevant_query_tokens:
            score = len(title_overlap) / len(relevant_query_tokens)
        else:
            score = 1.0 if required_types else 0.0

        # Require at least one meaningful title match.
        if relevant_query_tokens and not title_overlap:
            continue

        price = product.get("price")
        currency = product.get("currency")

        # Apply explicit price limits strictly.
        if price_min is not None or price_max is not None:
            try:
                price = float(price)
            except (TypeError, ValueError):
                continue

            if not currency:
                continue

            if requested_currency and (
                str(currency).upper()
                != str(requested_currency).upper()
            ):
                continue

            if price_min is not None and price < float(price_min):
                continue

            if price_max is not None and price > float(price_max):
                continue

        results.append({
            "product_id": product.get("product_id"),
            "title": title,
            "platform": "amazon",
            "price": price,
            "currency": currency,
            "image_url": product.get("image_url"),
            "product_url": None,
            "category": product.get("category", []),
            "seller": product.get("store"),
            "rating": product.get("rating"),
            "rating_count": product.get("rating_count"),
            "price_is_historical": True,
            "relevance_score": round(score, 4),
        })

    # Rank by title relevance, then prefer lower known prices.
    results.sort(
        key=lambda item: (
            -item["relevance_score"],
            (
                float(item["price"])
                if item["price"] is not None
                else float("inf")
            ),
        )
    )

    return results[:max(0, limit)]
