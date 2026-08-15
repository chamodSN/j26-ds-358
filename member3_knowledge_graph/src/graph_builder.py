import os
import requests
import base64
import pandas as pd
from datetime import datetime
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

# ── eBay Token ───────────────────────────────────────────────────
def get_ebay_token():
    client_id     = os.getenv("EBAY_CLIENT_ID")
    client_secret = os.getenv("EBAY_CLIENT_SECRET")
    credentials   = base64.b64encode(
        f"{client_id}:{client_secret}".encode("ascii")
    ).decode("ascii")

    response = requests.post(
        "https://api.sandbox.ebay.com/identity/v1/oauth2/token",
        headers={
            "Authorization" : f"Basic {credentials}",
            "Content-Type"  : "application/x-www-form-urlencoded"
        },
        data=(
            "grant_type=client_credentials"
            "&scope=https://api.ebay.com/oauth/api_scope"
        )
    )
    print("✅ eBay token obtained")
    return response.json()["access_token"]


# ── Collect eBay Data ────────────────────────────────────────────
def collect_ebay_data(token, query, category_label, limit=50):
    response = requests.get(
        "https://api.sandbox.ebay.com/buy/browse/v1"
        f"/item_summary/search?q={query}&limit={limit}",
        headers={"Authorization": f"Bearer {token}"}
    )
    items   = response.json().get("itemSummaries", [])
    records = []

    for item in items:
        price_info = item.get("price", {})
        records.append({
            "item_id"  : item.get("itemId", ""),
            "title"    : item.get("title", ""),
            "category" : category_label,
            "platform" : "eBay",
            "price"    : price_info.get("value", None),
            "currency" : price_info.get("currency", "USD"),
            "condition": item.get("condition", ""),
            "timestamp": datetime.now().isoformat()
        })

    print(f"  ✅ {len(records)} items collected for '{query}'")
    return records


# ── Save Data to CSV ─────────────────────────────────────────────
def save_data():
    token       = get_ebay_token()
    all_records = []

    print("\n📱 Collecting Electrical Items...")
    for query in ["laptop", "smartphone", "smartwatch",
                  "headphones", "tablet"]:
        all_records.extend(
            collect_ebay_data(token, query, "Electrical Items")
        )

    print("\n👗 Collecting Fashion...")
    for query in ["dress", "sneakers", "handbag",
                  "jacket", "jeans"]:
        all_records.extend(
            collect_ebay_data(token, query, "Fashion")
        )

    os.makedirs("data", exist_ok=True)
    today    = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"data/ebay_{today}.csv"
    df       = pd.DataFrame(all_records)
    df.to_csv(filename, index=False)
    print(f"\n✅ Saved {len(all_records)} records → {filename}")
    return df


# ── Build Knowledge Graph in Neo4j ───────────────────────────────
def build_knowledge_graph(df):
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER"),
              os.getenv("NEO4J_PASSWORD"))
    )

    # Default decay rates (updated later by staleness_tracker.py)
    decay_rates = {
        "Electrical Items": 0.8,
        "Fashion"         : 0.4
    }

    with driver.session() as session:
        # Clear existing graph
        session.run("MATCH (n) DETACH DELETE n")
        print("\n🗑️  Cleared existing graph")

        # Create Platform node
        session.run("""
            MERGE (p:Platform {name: 'eBay'})
            SET p.region = 'Global'
        """)

        for category in df["category"].unique():
            cat_data  = df[df["category"] == category]
            avg_price = round(
                float(cat_data["price"].dropna().mean()), 2
            )
            decay_rate = decay_rates.get(category, 0.5)

            # Create Category node
            session.run("""
                MERGE (c:Category {name: $name})
                SET c.avg_price       = $avg_price,
                    c.decay_rate      = $decay_rate,
                    c.staleness_score = 0.0,
                    c.last_refreshed  = $now
            """, name=category, avg_price=avg_price,
                 decay_rate=decay_rate,
                 now=datetime.now().isoformat())

            # Link Category → Platform
            session.run("""
                MATCH (c:Category  {name: $cat})
                MATCH (p:Platform  {name: 'eBay'})
                MERGE (c)-[:CARRIED_BY]->(p)
            """, cat=category)

            print(f"  ✅ Created node: {category} "
                  f"(decay={decay_rate}, avg_price={avg_price})")

    driver.close()
    print("\n✅ Knowledge Graph built in Neo4j")


if __name__ == "__main__":
    df = save_data()
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    build_knowledge_graph(df)