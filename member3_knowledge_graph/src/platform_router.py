import os
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer, util
from dotenv import load_dotenv

load_dotenv()

model = SentenceTransformer("all-MiniLM-L6-v2")

CATEGORY_LABELS = {
    "Electrical Items": [
        "laptop computer phone electronics gadget tablet",
        "smartphone mobile headphones smartwatch charger"
    ],
    "Fashion": [
        "dress shirt clothing shoes fashion wear outfit",
        "handbag jacket jeans accessories sunglasses"
    ]
}


# ── Map query to category ────────────────────────────────────────
def map_query_to_category(query: str) -> str:
    query_emb  = model.encode(query, convert_to_tensor=True)
    best_cat   = None
    best_score = -1

    for category, labels in CATEGORY_LABELS.items():
        for label in labels:
            label_emb = model.encode(label, convert_to_tensor=True)
            score     = util.cos_sim(query_emb, label_emb).item()
            if score > best_score:
                best_score = score
                best_cat   = category

    print(f"  Query: '{query}'")
    print(f"  Mapped to: {best_cat} (score: {round(best_score,3)})")
    return best_cat


# ── Get platforms from KG ────────────────────────────────────────
def get_platforms_for_category(category: str) -> list:
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER"),
              os.getenv("NEO4J_PASSWORD"))
    )

    with driver.session() as session:
        # Check freshness
        result = session.run("""
            MATCH (c:Category {name: $name})
            RETURN c.staleness_score AS score,
                   c.decay_rate      AS rate
        """, name=category).single()

        if result:
            score = result["score"]
            print(f"  Staleness score: {score}")
            if score > 0.7:
                print(f"  ⚠️  Data is stale — recommend refresh")

        # Get platforms
        platforms = [
            r["platform"] for r in session.run("""
                MATCH (c:Category {name: $name})
                      -[:CARRIED_BY]->(p:Platform)
                RETURN p.name AS platform
            """, name=category)
        ]

    driver.close()
    return platforms


# ── Main routing function ────────────────────────────────────────
def route_query(query: str) -> dict:
    print(f"\n🔍 Routing: '{query}'")
    category  = map_query_to_category(query)
    platforms = get_platforms_for_category(category)
    print(f"  ✅ Route to: {platforms}\n")

    return {
        "query"    : query,
        "category" : category,
        "platforms": platforms
    }


if __name__ == "__main__":
    test_queries = [
        "gaming laptop good battery",
        "summer dress for women",
        "wireless headphones",
        "leather handbag"
    ]
    for q in test_queries:
        route_query(q)