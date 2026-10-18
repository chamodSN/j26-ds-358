
import json
import re
from pathlib import Path
from difflib import SequenceMatcher

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

GRAPH_FILE = DATA_DIR / "electronics_kg_combined.json"
OUTPUT_FILE = DATA_DIR / "category_crosswalk_candidates.json"

MIN_SCORE = 0.55
MAX_CANDIDATES_PER_CATEGORY = 3

ACCESSORY_TERMS = {
    "accessory", "accessories", "adapter", "adapters",
    "cable", "cables", "case", "cases", "cover", "covers",
    "mount", "mounts", "stand", "stands", "protector",
    "protectors", "replacement", "replacements"
}

IGNORED_TOKENS = {
    "electronics", "and", "the", "for", "with",
    "other", "amazon", "google"
}


def normalize(text):
    text = text.casefold().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def tokens(text):
    return {
        token for token in normalize(text).split()
        if token not in IGNORED_TOKENS
    }


def jaccard(left, right):
    a, b = tokens(left), tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def path_parts(node):
    return [
        normalize(part)
        for part in node.get("path", "").split(">")
        if normalize(part)
    ]


def leaf_name(node):
    parts = path_parts(node)
    return parts[-1] if parts else normalize(node.get("name", ""))


def category_scope(amazon, google):
    """Estimate whether matching categories have different scope."""
    a = tokens(amazon["name"])
    g = tokens(google["name"])

    if a == g:
        return "possible_equivalent"

    # A category explicitly including accessories should not be
    # equated with one that only describes the core product, or vice versa.
    a_accessory = bool(a & ACCESSORY_TERMS)
    g_accessory = bool(g & ACCESSORY_TERMS)

    if a_accessory != g_accessory:
        return "manual_review"

    # If one name's meaningful terms are contained in the other,
    # the categories may have a broader/narrower relationship.
    if a and g and (a < g or g < a):
        return "possible_broader_or_narrower"

    return "manual_review"


def similarity(amazon, google):
    a_name = leaf_name(amazon)
    g_name = leaf_name(google)

    if a_name and a_name == g_name:
        name_score = 1.0
    else:
        name_score = (
            0.65 * jaccard(amazon["name"], google["name"])
            + 0.35 * SequenceMatcher(
                None, a_name, g_name
            ).ratio()
        )

    path_score = jaccard(
        amazon.get("path", ""),
        google.get("path", "")
    )

    score = 0.8 * name_score + 0.2 * path_score

    return round(score, 3)


def main():
    with GRAPH_FILE.open("r", encoding="utf-8") as file:
        graph = json.load(file)

    amazon_nodes = [
        node for node in graph["nodes"]
        if node.get("source") == "Amazon"
    ]

    google_nodes = [
        node for node in graph["nodes"]
        if node.get("source", "Google Product Taxonomy")
        == "Google Product Taxonomy"
    ]

    candidates = []

    for amazon in amazon_nodes:
        ranked = []

        for google in google_nodes:
            relationship = category_scope(amazon, google)

            # Exclude obvious scope mismatches from automatic proposals.
            if relationship == "manual_review":
                # Keep potentially useful text matches for human review,
                # but require a higher score for uncertain relationships.
                score = similarity(amazon, google)
                if score < 0.65:
                    continue
            else:
                score = similarity(amazon, google)
                if score < MIN_SCORE:
                    continue

            ranked.append((score, google, relationship))

        ranked.sort(key=lambda item: item[0], reverse=True)

        for score, google, relationship in ranked[
            :MAX_CANDIDATES_PER_CATEGORY
        ]:
            exact = leaf_name(amazon) == leaf_name(google)

            if exact:
                status = "exact_name_candidate"
            elif score >= 0.75:
                status = "strong_candidate"
            else:
                status = "manual_review"

            candidates.append({
                "amazon_id": amazon["id"],
                "amazon_path": amazon["path"],
                "google_id": google["id"],
                "google_path": google["path"],
                "similarity_score": score,
                "status": status,
                "relationship": relationship,
                "verified": False
            })

    candidates.sort(
        key=lambda item: item["similarity_score"],
        reverse=True
    )

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(candidates, file, indent=2, ensure_ascii=False)

    print("Crosswalk candidate generation complete.")
    print(f"Amazon categories: {len(amazon_nodes)}")
    print(f"Google categories: {len(google_nodes)}")
    print(f"Candidate pairs: {len(candidates)}")

    print("\nCandidates by status:")
    for status in (
        "exact_name_candidate",
        "strong_candidate",
        "manual_review"
    ):
        count = sum(item["status"] == status for item in candidates)
        print(f"{status}: {count}")

    print("\nCandidates by proposed relationship:")
    relationships = {}
    for item in candidates:
        relationship = item["relationship"]
        relationships[relationship] = relationships.get(relationship, 0) + 1

    for relationship, count in sorted(relationships.items()):
        print(f"{relationship}: {count}")

    print("\nTop 15 candidates:")
    for item in candidates[:15]:
        print(
            f"\nScore: {item['similarity_score']}"
            f"\nStatus: {item['status']}"
            f"\nRelationship: {item['relationship']}"
            f"\nAmazon: {item['amazon_path']}"
            f"\nGoogle: {item['google_path']}"
        )

    print(f"\nOutput saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
