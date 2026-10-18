"""
M3: Knowledge-Graph-Guided Platform Router
===========================================

Responsibilities:
1. Load the combined Google + Amazon electronics taxonomy.
2. Match queries to relevant taxonomy categories.
3. Rank categories using query relevance and specificity.
4. Select eligible platforms using configuration and constraints.
5. Use observation freshness when available.
6. Keep routing separate from retrieval and final reranking.

Current integration status:
- eBay: enabled for live retrieval.
- Amazon: taxonomy available; live retrieval not ready.
- AliExpress: disabled.

Run from the repository root:
    python3 member3_knowledge_graph/src/platform_router.py
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ============================================================
# 1. FILE PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

GRAPH_FILE = DATA_DIR / "electronics_kg_combined.json"
CROSSWALK_FILE = DATA_DIR / "category_crosswalk_candidates.json"


# ============================================================
# 2. PLATFORM CONFIGURATION
# ============================================================

PLATFORMS = {
    "ebay": {
        "enabled": True,
        "retrieval_ready": True,
        "supported_categories": ["electronics"],
        "integration_status": "api_available",
    },
    "amazon": {
        "enabled": True,
        "retrieval_ready": False,
        "supported_categories": ["electronics"],
        "integration_status": "taxonomy_only",
    },
    "aliexpress": {
        "enabled": False,
        "retrieval_ready": False,
        "supported_categories": [],
        "integration_status": "not_integrated",
    },
}

CATEGORY_GROUPS = {
    "audio": [
        "headphone", "speaker", "microphone",
        "earphone", "headset", "amplifier",
    ],
    "computing": [
        "laptop", "computer", "keyboard", "mouse",
        "monitor", "tablet", "printer",
    ],
    "networking": [
        "router", "network", "wifi", "wireless",
    ],
    "camera": [
        "camera", "photography", "lens",
    ],
    "power_accessories": [
        "charger", "adapter", "battery", "power supply",
    ],
    "television": [
        "television", "tv", "projector", "display",
    ],
}

# Platforms that can currently retrieve live product results.
RETRIEVAL_READY_PLATFORMS = {"ebay"}

# Platforms considered in routing experiments.
# This does not mean all can retrieve live products.
EXPERIMENTAL_PLATFORMS = {"ebay", "amazon"}

CATEGORY_ROUTING_POLICY = {
    "audio": ["ebay", "amazon"],
    "computing": ["ebay", "amazon"],
    "networking": ["ebay", "amazon"],
    "camera": ["ebay", "amazon"],
    "power_accessories": ["ebay", "amazon"],
    "television": ["ebay", "amazon"],
    "general_electronics": ["ebay", "amazon"],
    "unknown": ["ebay"],
}


# ============================================================
# 3. QUERY NORMALIZATION
# ============================================================

TOKEN_ALIASES = {
    "mice": "mouse",
    "keyboards": "keyboard",
    "cameras": "camera",
    "speakers": "speaker",
    "headphones": "headphone",
    "earphones": "earphone",
    "microphones": "microphone",
    "monitors": "monitor",
    "routers": "router",
    "chargers": "charger",
    "adapters": "adapter",
    "adaptors": "adapter",
    "laptops": "laptop",
    "computers": "computer",
    "tablets": "tablet",
    "printers": "printer",
    "scanners": "scanner",
    "projectors": "projector",
    "televisions": "television",
    "tvs": "tv",
    "displays": "display",
    "cables": "cable",
    "connectors": "connector",
    "accessories": "accessory",
    "batteries": "battery",
    "drives": "drive",
    "controllers": "controller",
    "headsets": "headset",
    "webcams": "webcam",
    "lamps": "lamp",
    "memories": "memory",
    "keypads": "keypad",
    "receivers": "receiver",
    "amplifiers": "amplifier",
    "recorders": "recorder",
}

QUERY_SYNONYMS = {
    "laptop chargers": [
        "laptop charger",
        "laptop power adapter",
        "laptop power supply",
    ],
    "digital cameras": [
        "digital camera",
        "camera photo digital camera",
    ],
    "gaming mice": [
        "gaming mouse",
        "computer mouse gaming",
    ],
    "gaming keyboards": [
        "gaming keyboard",
        "computer keyboard gaming",
    ],
    "wireless headphones": [
        "wireless headphone",
        "bluetooth headphone",
    ],
    "bluetooth speakers": [
        "bluetooth speaker",
        "wireless speaker",
    ],
    "computer monitors": [
        "computer monitor",
        "computer display",
    ],
    "wireless routers": [
        "wireless router",
        "wifi router",
        "wi fi router",
    ],
    "usb microphones": [
        "usb microphone",
        "computer microphone",
    ],
}

FEATURE_TOKENS = {
    "wireless", "bluetooth", "usb", "wired", "portable",
    "professional", "digital", "smart", "new", "latest",
    "best", "cheap", "budget", "gaming",
}

GENERIC_TOKENS = {
    "electronics", "electronic", "product", "products",
    "device", "devices", "equipment", "item", "items",
    "accessory", "accessories", "for", "and", "with",
    "the", "a", "an", "of", "to", "in", "on",
    "find", "search", "show", "looking", "want", "buy", "get",
}

EXCLUDED_PATH_PHRASES = {
    "free two day shipping",
    "free shipping",
    "new arrivals",
    "new products",
    "outlet",
    "product finder",
    "features us",
    "frustration free packaging",
    "back to school",
    "gifts for dad",
    "gifts for dads",
    "gifts for grad",
    "gifts for grads",
    "gift ideas",
    "holiday gifts",
    "deals and promotions",
    "deals",
    "clearance",
}

KNOWN_BRANDS = {
    "amazonbasics", "apple", "bose", "canon", "contour",
    "dell", "fujifilm", "hp", "lenovo", "logitech",
    "nikon", "razer", "samsung", "sony", "toshiba",
}


def normalize_text(text: str) -> str:
    """Lowercase text and replace punctuation with spaces."""
    text = str(text).lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_token(token: str) -> str:
    """Normalize common plurals and irregular forms."""
    token = token.lower().strip()

    if token in TOKEN_ALIASES:
        return TOKEN_ALIASES[token]

    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"

    if len(token) > 4 and token.endswith("sses"):
        return token[:-2]

    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]

    return token


def tokenize(text: str) -> list[str]:
    """Return normalized tokens."""
    normalized = normalize_text(text)

    if not normalized:
        return []

    return [normalize_token(token) for token in normalized.split()]


def meaningful_tokens(text: str) -> set[str]:
    """Return tokens useful for identifying product categories."""
    return {
        token for token in tokenize(text)
        if token not in GENERIC_TOKENS
    }


def query_core_tokens(query: str) -> set[str]:
    """Remove feature words to identify the core product type."""
    return meaningful_tokens(query) - FEATURE_TOKENS


def expand_query(query: str) -> list[str]:
    """Return the normalized query plus configured synonyms."""
    normalized = normalize_text(query)
    variants = [normalized]

    for key, synonyms in QUERY_SYNONYMS.items():
        if normalized == normalize_text(key):
            variants.extend(normalize_text(item) for item in synonyms)

    return list(dict.fromkeys(item for item in variants if item))


# ============================================================
# 3A. STRUCTURED QUERY UNDERSTANDING
# ============================================================

COLOUR_TERMS = {
    "black", "white", "silver", "gray", "grey", "red", "blue",
    "green", "pink", "purple", "gold", "beige", "brown", "orange",
}

CONNECTIVITY_TERMS = {
    "wireless": "wireless",
    "wired": "wired",
    "bluetooth": "bluetooth",
    "wifi": "wi_fi",
    "wi-fi": "wi_fi",
    "usb": "usb",
}

BRAND_ALIASES = {
    "amazon basics": "AmazonBasics",
    "apple": "Apple",
    "bose": "Bose",
    "canon": "Canon",
    "contour": "Contour",
    "dell": "Dell",
    "fujifilm": "Fujifilm",
    "hp": "HP",
    "lenovo": "Lenovo",
    "logitech": "Logitech",
    "nikon": "Nikon",
    "razer": "Razer",
    "samsung": "Samsung",
    "sony": "Sony",
    "toshiba": "Toshiba",
}

PRICE_NUMBER = r"(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d{1,2})?)"
PRICE_CURRENCY = r"(?:\$|USD\s*|US\$\s*|LKR\s*|Rs\.?\s*)"


def parse_structured_query(query: str) -> dict[str, Any]:
    """
    Extract common product attributes from a natural-language query.

    This is a conservative rule-based parser, not an NLP model. It keeps
    the original query and returns extracted values plus a category-focused
    query used for taxonomy matching. Unrecognised details are preserved.
    """
    original = str(query).strip()
    working = original
    attributes: dict[str, Any] = {}
    hard_constraints: list[str] = []
    matched_spans: list[tuple[int, int]] = []

    def capture(pattern: str, flags: int = re.IGNORECASE):
        match = re.search(pattern, working, flags)
        if match:
            matched_spans.append(match.span())
        return match

    # Price bounds. A currency symbol/code is optional; currency is only
    # reported when explicitly supplied, never inferred from user location.
    max_price = capture(
        rf"\b(?:under|below|less than|up to|at most|maximum|max)\s*"
        rf"({PRICE_CURRENCY})?({PRICE_NUMBER})\s*(USD|LKR|Rs\.?|dollars?)?\b"
    )
    if max_price:
        currency_prefix = (max_price.group(1) or "").strip().upper()
        number = float(max_price.group(2).replace(",", ""))
        currency_suffix = (max_price.group(3) or "").strip().upper()
        currency = "USD" if "$" in currency_prefix or "US$" in currency_prefix else (
            "LKR" if "LKR" in currency_prefix or "RS" in currency_prefix or
            currency_suffix in {"LKR", "RS.", "RS"} else (
                "USD" if currency_suffix in {"USD", "DOLLAR", "DOLLARS"} else None
            )
        )
        attributes["price_max"] = number
        if currency:
            attributes["currency"] = currency
        hard_constraints.append("price_max")

    min_price = capture(
        rf"\b(?:over|above|more than|at least|minimum|min)\s*"
        rf"({PRICE_CURRENCY})?({PRICE_NUMBER})\s*(USD|LKR|Rs\.?|dollars?)?\b"
    )
    if min_price:
        currency_prefix = (min_price.group(1) or "").strip().upper()
        number = float(min_price.group(2).replace(",", ""))
        currency_suffix = (min_price.group(3) or "").strip().upper()
        currency = "USD" if "$" in currency_prefix or "US$" in currency_prefix else (
            "LKR" if "LKR" in currency_prefix or "RS" in currency_prefix or
            currency_suffix in {"LKR", "RS.", "RS"} else (
                "USD" if currency_suffix in {"USD", "DOLLAR", "DOLLARS"} else None
            )
        )
        attributes["price_min"] = number
        if currency:
            attributes["currency"] = currency
        hard_constraints.append("price_min")

    # RAM and storage are distinct attributes.
    ram = capture(r"\b(\d{1,3})\s*GB\s*(?:of\s*)?RAM\b")
    if ram:
        attributes["ram_gb"] = int(ram.group(1))
        hard_constraints.append("ram_gb")

    storage = None
    for candidate in re.finditer(
        r"\b(\d+(?:\.\d+)?)\s*(TB|GB)\s*(?:storage|SSD|HDD|memory|drive)?\b",
        working,
        re.IGNORECASE,
    ):
        # Do not mistake the capacity in "8GB RAM" for storage.
        following_text = working[candidate.end():candidate.end() + 12].lower().lstrip()
        if re.match(r"ram\b", following_text):
            continue
        storage = candidate
        matched_spans.append(candidate.span())
        break
    if storage:
        value = float(storage.group(1))
        unit = storage.group(2).upper()
        attributes["storage_gb"] = int(value * (1000 if unit == "TB" else 1))
        hard_constraints.append("storage_gb")

    bluetooth = capture(r"\bBluetooth\s*(?:version\s*)?([0-9]+(?:\.[0-9]+)+)\b")
    if bluetooth:
        attributes["bluetooth_version"] = bluetooth.group(1)
        hard_constraints.append("bluetooth_version")

    # Explicit brand names from the current known-brand vocabulary.
    for brand_key in sorted(BRAND_ALIASES, key=len, reverse=True):
        match = re.search(rf"\b{re.escape(brand_key)}\b", working, re.IGNORECASE)
        if match:
            attributes["brand"] = BRAND_ALIASES[brand_key]
            matched_spans.append(match.span())
            break

    # Colour is treated as a requested attribute. Whether it is a hard
    # constraint is left to downstream policy/UI rather than assumed here.
    for colour in sorted(COLOUR_TERMS, key=len, reverse=True):
        match = re.search(rf"\b{re.escape(colour)}\b", working, re.IGNORECASE)
        if match:
            attributes["colour"] = "gray" if colour == "grey" else colour
            matched_spans.append(match.span())
            break

    # Connectivity features are attributes, not product categories.
    for term, normalized in CONNECTIVITY_TERMS.items():
        match = re.search(rf"\b{re.escape(term)}\b", working, re.IGNORECASE)
        if match:
            attributes.setdefault("connectivity", [])
            if normalized not in attributes["connectivity"]:
                attributes["connectivity"].append(normalized)
            matched_spans.append(match.span())

    # Remove only extracted spans to produce a category-oriented query.
    # Merge overlapping spans before deletion.
    merged: list[list[int]] = []
    for start, end in sorted(matched_spans):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)

    category_query = working
    for start, end in reversed(merged):
        category_query = category_query[:start] + " " + category_query[end:]
    category_query = re.sub(r"\s+", " ", category_query).strip(" ,.-")

    # Do not leave the category query empty when the input was only attributes.
    if not category_query:
        category_query = original

    return {
        "original_query": original,
        "category_query": category_query,
        "attributes": attributes,
        "hard_constraints": hard_constraints,
        "parser": "rule_based_v1",
    }



# ============================================================
# 4. LOAD KNOWLEDGE GRAPH CATEGORIES
# ============================================================

def is_excluded_path(path: str) -> bool:
    """Exclude promotional paths that are not product categories."""
    normalized = normalize_text(path)

    return any(
        normalize_text(phrase) in normalized
        for phrase in EXCLUDED_PATH_PHRASES
    )


def get_node_source(node: dict[str, Any]) -> str:
    """Determine the taxonomy source of a graph node."""
    source = node.get("source") or node.get("taxonomy") or ""

    if source:
        return str(source)

    node_id = str(node.get("id", "")).lower()

    if node_id.startswith("amazon_"):
        return "Amazon"

    return "Google Product Taxonomy"


def load_graph_categories() -> list[dict[str, Any]]:
    """Load category nodes from the combined knowledge graph."""
    if not GRAPH_FILE.exists():
        raise FileNotFoundError(
            f"Knowledge graph not found: {GRAPH_FILE}"
        )

    with GRAPH_FILE.open("r", encoding="utf-8") as file:
        graph = json.load(file)

    categories = []
    seen_ids = set()

    for node in graph.get("nodes", []):
        if not isinstance(node, dict):
            continue

        category_id = node.get("id")
        category_name = node.get("name")
        category_path = node.get("path") or category_name

        if category_id is None or not category_name or not category_path:
            continue

        category_id = str(category_id)
        category_name = str(category_name).strip()
        category_path = str(category_path).strip()

        if category_id in seen_ids:
            continue

        if is_excluded_path(category_path):
            continue

        seen_ids.add(category_id)

        try:
            depth = int(
                node.get("depth", len(category_path.split(">")))
            )
        except (TypeError, ValueError):
            depth = len(category_path.split(">"))

        path_parts = [
            part.strip()
            for part in category_path.split(">")
            if part.strip()
        ]

        categories.append({
            "category_id": category_id,
            "category_name": category_name,
            "category_path": category_path,
            "source": get_node_source(node),
            "depth": depth,
            "path_parts": path_parts,
        })

    if not categories:
        raise ValueError(
            "No categories loaded. Check the graph JSON structure."
        )

    return categories


# ============================================================
# 5. LOAD CATEGORY CROSSWALK
# ============================================================

def load_crosswalk() -> list[dict[str, Any]]:
    """Load candidate cross-taxonomy mappings."""
    if not CROSSWALK_FILE.exists():
        print(
            "Warning: crosswalk file not found; continuing without it:",
            CROSSWALK_FILE,
        )
        return []

    with CROSSWALK_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        candidates = data
    elif isinstance(data, dict):
        candidates = (
            data.get("candidates")
            or data.get("mappings")
            or data.get("crosswalk")
            or []
        )
    else:
        candidates = []

    return [
        item for item in candidates
        if isinstance(item, dict)
    ]


def find_crosswalk_candidates(
    category_id: str,
    category_source: str,
    crosswalk: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Find candidate mappings for a Google taxonomy category."""
    if "google" not in category_source.lower():
        return []

    return [
        candidate for candidate in crosswalk
        if (
            str(candidate.get("google_id", "")) == category_id
            or str(candidate.get("amazon_id", "")) == category_id
        )
    ]


# ============================================================
# 6. CATEGORY SCORING
# ============================================================

def contains_brand_path(category: dict[str, Any]) -> bool:
    """Check whether an ancestor path component names a known brand."""
    parts = category.get("path_parts", [])

    for part in parts[:-1]:
        normalized = normalize_text(part).replace(" ", "")

        if normalized in KNOWN_BRANDS:
            return True

    return False


def category_context_adjustment(query: str, category: dict) -> float:
    """Adjust category scores using query intent and taxonomy context."""
    q = normalize_text(query)
    name = normalize_text(category.get("category_name", ""))
    path = normalize_text(category.get("category_path", ""))

    query_tokens = set(tokenize(q))
    name_tokens = set(tokenize(name))
    path_tokens = set(tokenize(path))

    adjustment = 0.0

    # Digital cameras: prefer the main product category.
    if "camera" in query_tokens and "charger" not in query_tokens:
        if name in {"digital cameras", "digital camera"}:
            adjustment += 0.45

        if name == "camera" and (
            "battery charger" in path
            or "battery chargers" in path
        ):
            adjustment -= 0.90

        if "digital camera accessories" in name and "accessories" not in q:
            adjustment -= 0.30

    # Gaming keyboards: favour the specific gaming category.
    if "gaming" in query_tokens and "keyboard" in query_tokens:
        if "gaming keyboard" in name:
            adjustment += 0.45
        elif name in {"keyboard", "keyboards"}:
            adjustment -= 0.15

    # Wi-Fi routers: favour wireless-router categories.
    if (
        query_tokens & {"wifi", "wireless"}
        or {"wi", "fi"}.issubset(query_tokens)
    ) and "router" in query_tokens:
        if "wireless router" in name:
            adjustment += 0.50

    # Phone chargers: favour phone-related charging categories.
    if "phone" in query_tokens and "charger" in query_tokens:
        phone_context = bool(
            path_tokens
            & {"phone", "mobile", "cell", "android"}
        )
        charger_category = bool(
            name_tokens & {"charger", "charging"}
        )

        if phone_context and charger_category:
            adjustment += 0.65

        # Penalize charging categories for unrelated devices.
        if path_tokens & {"mp3", "mp4"}:
            adjustment -= 0.70

        if {"camera", "photo"}.issubset(path_tokens):
            if "charger" in name or "charging" in name:
                adjustment -= 0.60

        if "phone card" in name:
            adjustment -= 0.80

        if name in {
            "phone chargers",
            "cell phone chargers",
            "mobile phone chargers",
        }:
            adjustment += 0.50

    # Headphones: demote accessory and specialist categories
    # when the user is searching for headphones themselves.
    if (
        "headphone" in query_tokens
        and not query_tokens
        & {"accessory", "replacement", "cushion"}
    ):
        if "headphone and headset accessories" in name:
            adjustment -= 0.35

        if "car headphones" in name:
            adjustment -= 0.30

        if "headphone amplifiers" in name:
            adjustment -= 0.30

    return adjustment


def calculate_category_score(
    query: str,
    category: dict[str, Any],
) -> tuple[float, dict[str, Any]]:
    """Calculate a heuristic query/category relevance score."""
    variants = expand_query(query)

    category_name = category["category_name"]
    category_path = category["category_path"]

    category_tokens = meaningful_tokens(category_name)

    if not category_tokens:
        category_tokens = set(tokenize(category_name))

    best_score = 0.0
    best_details: dict[str, Any] = {}

    normalized_name = normalize_text(category_name)
    normalized_path = normalize_text(category_path)
    normalized_query = normalize_text(query)

    query_has_brand = any(
        normalize_text(brand) in normalized_query
        for brand in KNOWN_BRANDS
    )

    for variant in variants:
        query_tokens = query_core_tokens(variant)

        if not query_tokens:
            query_tokens = set(tokenize(variant))

        if not query_tokens:
            continue

        overlap = query_tokens & category_tokens

        query_coverage = len(overlap) / len(query_tokens)
        category_coverage = len(overlap) / max(len(category_tokens), 1)

        score = (
            0.70 * query_coverage
            + 0.30 * category_coverage
        )

        if normalized_name == variant:
            score += 0.65
        elif normalized_name and normalized_name in variant:
            score += 0.30

        if normalized_path and normalized_path in variant:
            score += 0.20

        path_tokens = meaningful_tokens(category_path)
        path_overlap = query_tokens & path_tokens

        if path_overlap:
            score += 0.10 * (
                len(path_overlap) / len(query_tokens)
            )

        if "gaming" in tokenize(variant):
            if "gaming" in tokenize(category_name):
                score += 0.15
            elif "mouse" in category_tokens:
                score -= 0.02

        if "laptop" in query_tokens and "charger" in query_tokens:
            if (
                "laptop" in normalized_path
                and any(term in normalized_path for term in (
                    "charger", "adapter", "power supply"
                ))
            ):
                score += 0.45

            if "mp3" in normalized_path or "mp4" in normalized_path:
                score -= 0.55

        if "digital" in tokenize(variant) and "camera" in query_tokens:
            if "digital camera" in normalized_name:
                score += 0.30

            if contains_brand_path(category) and not query_has_brand:
                score -= 0.40

        if contains_brand_path(category) and not query_has_brand:
            score -= 0.25

        if query_tokens & meaningful_tokens(category_name):
            score += 0.10

        # Adjust for product context, avoiding irrelevant specialist categories.
        score += category_context_adjustment(query, category)

        # Penalize specialist paths unless the query explicitly asks for them.
        query_tokens_set = set(tokenize(query))
        path_tokens_set = set(tokenize(category_path))
        category_name_tokens = set(tokenize(category_name))

        specialist_contexts = {
            "car": {"car", "vehicle", "automotive", "automotive"},
            "camera": {"camera", "photography"},
        }

        if "speaker" in query_tokens_set:
            if (
                path_tokens_set & {"car", "vehicle", "automotive"}
                and not query_tokens_set & {"car", "vehicle", "automotive"}
            ):
                score -= 0.45

        if "microphone" in query_tokens_set:
            if (
                path_tokens_set & {"camera", "photography"}
                and not query_tokens_set & {"camera", "photography"}
            ):
                score -= 0.45

        if {"laptop", "charger"}.issubset(query_tokens_set):
            # Network adapters are not laptop chargers.
            if (
                "network" in path_tokens_set
                or "networking" in path_tokens_set
            ):
                score -= 0.60

        # Exact product-name matches should remain more meaningful than
        # incidental matches in a long ancestor path.

        if category_name_tokens & query_tokens_set:
            score += 0.05

        # Penalize promotional categories when the query does not request
        # a gift, seasonal, or promotional shopping context.
        promotional_terms = {
            "gift", "gifts", "back", "school", "holiday",
            "holidays", "christmas", "father", "fathers",
            "dad", "dads", "mom", "moms", "graduation",
        }

        query_context_tokens = set(tokenize(query))
        path_context_tokens = set(tokenize(category_path))

        if (
            path_context_tokens & promotional_terms
            and not query_context_tokens & promotional_terms
        ):
            score -= 0.25


        # Phone charger: require charging-related category evidence.
        if {"phone", "charger"}.issubset(set(tokenize(query))):
            name_tokens = set(tokenize(category_name))
            path_tokens = set(tokenize(category_path))

            has_charger_context = bool(
                name_tokens & {"charger", "charging"}
                or path_tokens & {"charger", "charging", "chargers"}
            )

            has_phone_context = bool(
                name_tokens & {"phone", "mobile", "cell"}
                or path_tokens & {"phone", "mobile", "cell", "android"}
            )

            # Phone-only categories are not phone charger categories.
            if not has_charger_context:
                score -= 0.60

            # Prefer categories that indicate both phone and charging intent.
            elif has_phone_context:
                score += 0.20

        details = {
            "matched_tokens": sorted(overlap),
            "query_coverage": round(query_coverage, 3),
            "category_coverage": round(category_coverage, 3),
            "matched_variant": variant,
        }

        if score > best_score:
            best_score = score
            best_details = details

    normalized_score = best_score / (1.0 + max(best_score, 0.0))

    return round(normalized_score, 4), best_details


def classify_query(
    query: str,
    categories: list[dict[str, Any]],
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Rank taxonomy categories by heuristic relevance."""
    if not query or not query.strip():
        return []

    results = []

    for category in categories:
        score, details = calculate_category_score(query, category)

        if not details.get("matched_tokens"):
            continue

        results.append({
            **category,
            "score": score,
            "matched_tokens": details.get("matched_tokens", []),
            "query_coverage": details.get("query_coverage", 0.0),
            "category_coverage": details.get("category_coverage", 0.0),
            "matched_variant": details.get("matched_variant", ""),
        })

    results.sort(
        key=lambda item: (
            item["score"],
            item["query_coverage"],
            item["depth"],
            len(meaningful_tokens(item["category_name"])),
        ),
        reverse=True,
    )

    if not results:
        return []

    threshold = max(0.35, results[0]["score"] * 0.60)

    return [
        result for result in results
        if result["score"] >= threshold
    ][:top_k]


# ============================================================
# 7. PLATFORM CLASSIFICATION AND FRESHNESS-AWARE ROUTING
# ============================================================

def classify_category_group(category: dict[str, Any] | None) -> str:
    """Classify a category using its leaf name before its broader path."""
    if not category:
        return "unknown"

    name = normalize_text(category.get("category_name", ""))
    path = normalize_text(category.get("category_path", ""))
    leaf_tokens = set(tokenize(name))
    path_tokens = set(tokenize(path))

    # Use the product category itself first. Ancestor paths can be misleading.
    if leaf_tokens & {"router", "network", "networking"}:
        return "networking"

    if leaf_tokens & {
        "headphone", "speaker", "microphone", "earphone",
        "headset", "amplifier"
    }:
        return "audio"

    if leaf_tokens & {
        "keyboard", "mouse", "laptop", "computer", "monitor",
        "tablet", "printer", "scanner", "webcam"
    }:
        return "computing"

    if leaf_tokens & {"camera", "photography", "lens"}:
        return "camera"

    if leaf_tokens & {
        "television", "tv", "projector", "display"
    }:
        return "television"

    if leaf_tokens & {
        "charger", "adapter", "battery", "cable", "connector"
    }:
        return "power_accessories"

    # Fall back to the full path only when the leaf is inconclusive.
    if path_tokens & {"router", "network", "networking", "wifi"}:
        return "networking"

    if path_tokens & {"headphone", "speaker", "microphone", "earphone", "headset"}:
        return "audio"

    if path_tokens & {
        "keyboard", "mouse", "laptop", "computer", "monitor",
        "tablet", "printer", "scanner", "webcam"
    }:
        return "computing"

    if path_tokens & {"camera", "photography", "lens"}:
        return "camera"

    if path_tokens & {"television", "tv", "projector", "display"}:
        return "television"

    if path_tokens & {"charger", "adapter", "battery", "power"}:
        return "power_accessories"

    return "general_electronics"


def rank_by_freshness(
    candidates: list[str],
    freshness_scores: dict[str, float | None] | None = None,
) -> list[str]:
    """
    Rank candidates by known freshness score.

    Higher scores come first. Unknown scores remain eligible but are
    placed after candidates with known scores. Original order breaks ties.
    """
    freshness_scores = freshness_scores or {}
    original_order = {
        platform: index
        for index, platform in enumerate(candidates)
    }

    def sort_key(platform: str) -> tuple:
        score = freshness_scores.get(platform)

        if score is None:
            return (1, 0.0, original_order[platform])

        return (0, -float(score), original_order[platform])

    return sorted(candidates, key=sort_key)


def calculate_routing_score(
    category_relevance: float,
    freshness_score: float | None,
    relevance_weight: float = 0.7,
    freshness_weight: float = 0.3,
) -> float:
    """
    Calculate a routing score using category relevance and freshness.

    Unknown freshness is excluded from the calculation and the
    remaining weight is assigned to category relevance.
    """
    if not 0.0 <= category_relevance <= 1.0:
        raise ValueError("Category relevance must be between 0 and 1.")

    if not 0.0 <= relevance_weight <= 1.0:
        raise ValueError("Relevance weight must be between 0 and 1.")

    if not 0.0 <= freshness_weight <= 1.0:
        raise ValueError("Freshness weight must be between 0 and 1.")

    if abs(relevance_weight + freshness_weight - 1.0) > 1e-9:
        raise ValueError("Routing weights must sum to 1.")

    if freshness_score is not None and not 0.0 <= freshness_score <= 1.0:
        raise ValueError("Freshness score must be between 0 and 1.")

    if freshness_score is None:
        return round(category_relevance, 4)

    score = (
        relevance_weight * category_relevance
        + freshness_weight * freshness_score
    )

    return round(score, 4)


def select_platforms(
    category: dict[str, Any] | None,
    constraints: dict[str, Any] | None = None,
    freshness_scores: dict[str, float | None] | None = None,
    platform_relevance_scores: dict[str, float] | None = None,
    min_routing_score: float | None = None,
) -> dict[str, Any]:
    """
    Select platforms using category policy, constraints, freshness,
    optional platform-specific relevance, and an optional score threshold.

    Unknown platform relevance defaults to 1.0 for backward compatibility.
    This fallback is not evidence of actual marketplace relevance.
    Required platforms are not removed by the score threshold.
    """
    if min_routing_score is not None and not 0.0 <= min_routing_score <= 1.0:
        raise ValueError("Minimum routing score must be between 0 and 1.")

    if category is None:
        return {
            "category_group": "unknown",
            "routing_candidates": [],
            "retrieval_ready": [],
            "platform_routing_scores": {},
            "reasons": ["No category match was found."],
        }

    constraints = constraints or {}
    freshness_scores = freshness_scores or {}
    platform_relevance_scores = platform_relevance_scores or {}

    group = classify_category_group(category)

    required = {
        str(platform).lower()
        for platform in constraints.get("required_platforms", [])
    }
    excluded = {
        str(platform).lower()
        for platform in constraints.get("excluded_platforms", [])
    }

    policy_candidates = CATEGORY_ROUTING_POLICY.get(
        group,
        CATEGORY_ROUTING_POLICY["general_electronics"],
    )

    candidates = [
        platform for platform in policy_candidates
        if (
            platform in EXPERIMENTAL_PLATFORMS
            and platform in PLATFORMS
            and PLATFORMS[platform].get("enabled", False)
            and platform not in excluded
            and "electronics" in PLATFORMS[platform].get(
                "supported_categories", []
            )
        )
    ]

    if required and not required.issubset(set(candidates)):
        return {
            "category_group": group,
            "routing_candidates": [],
            "retrieval_ready": [],
            "platform_routing_scores": {},
            "reasons": [
                "A required platform is disabled, excluded, "
                "or not configured for this category."
            ],
        }

    # If platforms are explicitly required, preserve that selection.
    if required:
        candidates = [
            platform for platform in candidates
            if platform in required
        ]

    scores = {}



    for platform in candidates:
            relevance_provided = platform in platform_relevance_scores
            relevance = platform_relevance_scores.get(platform)
            freshness = freshness_scores.get(platform)

            if relevance is not None:
                score = calculate_routing_score(
                    category_relevance=relevance,
                    freshness_score=freshness,
                )
                score_status = "calculated"
            else:
                score = None
                score_status = "insufficient_relevance_data"

            scores[platform] = {
                "category_relevance": relevance,
                "category_relevance_source": (
                    "provided" if relevance_provided else "unknown"
                ),
                "freshness_score": freshness,
                "routing_score": score,
                "routing_score_status": score_status,
            }

            # Apply the threshold only when explicitly requested.
    # Required platforms are preserved.
    if min_routing_score is not None and not required:
        threshold_candidates = [
            platform
            for platform in candidates
            if (
                scores[platform]["routing_score"] is not None
                and scores[platform]["routing_score"] >= min_routing_score
            )
        ]

        if threshold_candidates:
            candidates = threshold_candidates
        else:
            # If no platform has a known score, do not treat missing
            # relevance data as proof that every platform is unsuitable.
            scored_candidates = [
                platform
                for platform in candidates
                if scores[platform]["routing_score"] is not None
            ]

            if scored_candidates:
                best_platform = max(
                    scored_candidates,
                    key=lambda platform: scores[platform]["routing_score"],
                )
                candidates = [best_platform]
            else:
                # Keep eligible candidates in their original order.
                # Their routing scores remain unknown.
                candidates = list(candidates)


    # Rank retained platforms by score; stable sorting preserves policy order
    # for ties.

    candidates = sorted(
        candidates,
        key=lambda platform: (
            scores[platform]["routing_score"] is not None,
            scores[platform]["routing_score"] or 0.0,
        ),
        reverse=True,
    )


    retrieval_ready = [
        platform for platform in candidates
        if (
            platform in RETRIEVAL_READY_PLATFORMS
            and PLATFORMS[platform].get("retrieval_ready", False)
        )
    ]

    reasons = [
        f"Category classified as '{group}'.",
        "Candidates were filtered by routing policy and platform constraints.",
    ]

    if min_routing_score is not None:
        reasons.append(
            f"Applied minimum routing score threshold: {min_routing_score:.2f}."
        )
    else:
        reasons.append("No score threshold was applied.")

    if required:
        reasons.append(
            "Required platforms were preserved; the score threshold "
            "was not used to remove them."
        )

    if any(freshness_scores.get(p) is not None for p in candidates):
        reasons.append("Available freshness scores contributed to ranking.")

    if any(
        scores[p]["routing_score"] is None
        for p in candidates
    ):
        reasons.append(
            "Routing scores are unknown because platform relevance "
            "data was not provided."
        )
    elif not any(freshness_scores.get(p) is not None for p in candidates):
        reasons.append(
            "Freshness is unknown; routing scores use category relevance only."
        )

    if "amazon" in candidates:
        reasons.append(
            "Amazon is a taxonomy-only candidate; live retrieval "
            "is not yet ready."
        )

    if "ebay" in candidates:
        reasons.append("eBay is configured for live retrieval.")

    return {
        "category_group": group,
        "routing_candidates": candidates,
        "retrieval_ready": retrieval_ready,
        "platform_routing_scores": {
            platform: scores[platform] for platform in candidates
        },
        "reasons": reasons,
    }


def calculate_platform_freshness(
    candidates: list[str],
    observation_times: dict[str, datetime] | None = None,
    now: datetime | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Calculate observation-age freshness for supplied platform timestamps.

    observation_times maps platform names to timezone-aware datetimes.
    Missing timestamps remain unknown. No data is persisted.
    """
    observation_times = observation_times or {}
    now = now or datetime.now(timezone.utc)

    freshness = {}

    if now.tzinfo is None:
        raise ValueError("'now' must be timezone-aware.")

    for platform in candidates:
        observed_at = observation_times.get(platform)

        if observed_at is None:
            freshness[platform] = {
                "status": "unknown",
                "freshness_score": None,
                "reason": "No observation timestamp is available.",
            }
            continue

        if observed_at.tzinfo is None:
            freshness[platform] = {
                "status": "invalid_timestamp",
                "freshness_score": None,
                "reason": "Observation timestamp must be timezone-aware.",
            }
            continue

        try:
            # Import from the existing M3 freshness model.
            from freshness_model import calculate_freshness

            result = calculate_freshness(
                last_observed_at=observed_at,
                now=now,
            )

            freshness[platform] = {
                "status": "calculated",
                **result,
            }

        except (ValueError, TypeError) as error:
            freshness[platform] = {
                "status": "invalid_timestamp",
                "freshness_score": None,
                "reason": str(error),
            }

    return freshness


def route_query(
    query: str,
    categories: list[dict[str, Any]],
    crosswalk: list[dict[str, Any]],
    constraints: dict[str, Any] | None = None,
    top_k: int = 5,
    observation_times: dict[str, datetime] | None = None,
    min_routing_score: float | None = None,
    platform_relevance_scores: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    Match a query, calculate observation freshness, and route platforms
    using category relevance, freshness, and an optional score threshold.

    Observation timestamps are used in memory and are not saved.
    """
    structured_query = parse_structured_query(query)
    category_query = structured_query["category_query"]

    # Match taxonomy categories against the product-focused portion of the
    # query so price/specification tokens do not dilute category relevance.
    matches = classify_query(category_query, categories, top_k=top_k)
    best_category = matches[0] if matches else None

    constraints = constraints or {}
    platform_relevance_scores = platform_relevance_scores or {}

    group = classify_category_group(best_category)

    policy = (
        CATEGORY_ROUTING_POLICY.get(
            group,
            CATEGORY_ROUTING_POLICY["general_electronics"],
        )
        if best_category
        else []
    )

    excluded = {
        str(platform).lower()
        for platform in constraints.get("excluded_platforms", [])
    }

    preliminary_candidates = [
        platform
        for platform in policy
        if (
            platform in PLATFORMS
            and PLATFORMS[platform].get("enabled", False)
            and platform not in excluded
        )
    ]

    freshness = calculate_platform_freshness(
        candidates=preliminary_candidates,
        observation_times=observation_times,
    )

    freshness_scores = {
        platform: details.get("freshness_score")
        for platform, details in freshness.items()
    }

    routing = select_platforms(
        category=best_category,
        constraints=constraints,
        freshness_scores=freshness_scores,
        platform_relevance_scores=platform_relevance_scores,
        min_routing_score=min_routing_score,
    )

    crosswalk_candidates = []

    if best_category:
        crosswalk_candidates = find_crosswalk_candidates(
            category_id=best_category["category_id"],
            category_source=best_category["source"],
            crosswalk=crosswalk,
        )

    return {
        "query": query,
        "structured_query": structured_query,
        "routing_constraints": {
            "hard_constraints": structured_query["hard_constraints"],
            "attributes": structured_query["attributes"],
            "listing_filtering_applied": False,
            "note": (
                "Constraints are extracted for downstream processing. "
                "M3 does not verify or filter individual product listings."
            ),
        },
        "matched_category": (
            {
                "category_id": best_category["category_id"],
                "category_name": best_category["category_name"],
                "category_path": best_category["category_path"],
                "source": best_category["source"],
                "score": best_category["score"],
            }
            if best_category
            else None
        ),
        "category_matches": matches,
        "category_group": routing["category_group"],
        "selected_platforms": routing["routing_candidates"],
        "retrieval_ready_platforms": routing["retrieval_ready"],
        "routing_reasons": routing["reasons"],
        "observation_freshness": freshness,
        "platform_routing_scores": routing["platform_routing_scores"],
        "crosswalk_candidates": crosswalk_candidates,
        "routing_status": (
            "matched" if best_category else "no_category_match"
        ),
        "note": (
            "Freshness represents time since observation, not actual "
            "listing age or confirmed inventory. Unspecified platform "
            "relevance defaults to 1.0 for backward compatibility; "
            "this is not measured marketplace relevance. Scoring weights "
            "are experimental prototype settings."
        ),
    }


# ============================================================
# 8. DISPLAY HELPERS
# ============================================================

def print_route_result(result: dict[str, Any]) -> None:
    """Print a readable routing result for manual testing."""
    print("\n" + "=" * 78)
    print(f"QUERY: {result['query']}")
    print("=" * 78)

    matched = result["matched_category"]

    if matched:
        print("\nBest category:")
        print(f"  Name:   {matched['category_name']}")
        print(f"  Path:   {matched['category_path']}")
        print(f"  Source: {matched['source']}")
        print(f"  Score:  {matched['score']}")
    else:
        print("\nNo relevant category found.")

    print("\nTop category matches:")

    if not result["category_matches"]:
        print("  No matches.")
    else:
        for index, category in enumerate(
            result["category_matches"], start=1
        ):
            print(
                f"  {index}. {category['category_name']} "
                f"(score={category['score']:.3f}, "
                f"source={category['source']})"
            )
            print(f"     Path: {category['category_path']}")

    print("\nSelected platforms (routing candidates):")
    print(
        "  " + ", ".join(result["selected_platforms"])
        if result["selected_platforms"] else "  None"
    )

    print("\nPlatforms ready for live retrieval:")
    print(
        "  " + ", ".join(result["retrieval_ready_platforms"])
        if result["retrieval_ready_platforms"] else "  None"
    )

    print("\nRouting reasons:")
    for reason in result.get("routing_reasons", []):
        print(f"  - {reason}")

    print("\nPlatform observation freshness:")
    freshness = result.get("observation_freshness", {})

    if not freshness:
        print("  Unknown — no platform candidates to evaluate.")
    else:
        for platform, details in freshness.items():
            if details.get("status") == "calculated":
                print(
                    f"  {platform}: "
                    f"score={details['freshness_score']:.4f}, "
                    f"age={details['age_hours']:.2f} hours"
                )
            else:
                print(
                    f"  {platform}: freshness unknown "
                    f"({details.get('reason', details.get('status'))})"
                )

    if result["crosswalk_candidates"]:
        print(
            "\nCrosswalk candidate records found: "
            f"{len(result['crosswalk_candidates'])}"
        )
        print("  Note: candidate mappings are not verified.")


# ============================================================
# 9. MAIN TEST RUN
# ============================================================

def main() -> None:
    print("Loading M3 electronics knowledge graph router...")

    categories = load_graph_categories()
    crosswalk = load_crosswalk()

    source_counts: dict[str, int] = {}

    for category in categories:
        source = category["source"]
        source_counts[source] = source_counts.get(source, 0) + 1

    print(f"\nCategories loaded: {len(categories)}")
    print(f"Crosswalk candidates loaded: {len(crosswalk)}")
    print("Category counts by source:")

    for source, count in sorted(source_counts.items()):
        print(f"  {source}: {count}")

    print("\nPlatform configuration:")

    for name, config in PLATFORMS.items():
        status = "ENABLED" if config["enabled"] else "DISABLED"
        print(f"  {name}: {status} ({config['integration_status']})")

    test_queries = [
        "wireless headphones",
        "bluetooth speakers",
        "gaming keyboards",
        "USB microphones",
        "laptop chargers",
        "computer monitors",
        "digital cameras",
        "wireless routers",
        "gaming mice",
        "TV replacement lamps",
    ]

    print("\nRunning test queries...")

    # No historical timestamps are available in this standalone run.
    # Freshness should therefore be reported as unknown.
    observation_times: dict[str, datetime] = {}

    for query in test_queries:
        result = route_query(
            query=query,
            categories=categories,
            crosswalk=crosswalk,
            observation_times=observation_times,
        )
        print_route_result(result)

    print("\n" + "=" * 78)
    print("Testing complete.")
    print(
        "Reminder: category matches are heuristic, freshness is based "
        "on observation timestamps when supplied, and Amazon is not "
        "ready for live retrieval."
    )


if __name__ == "__main__":
    main()