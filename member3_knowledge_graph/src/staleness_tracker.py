import glob
import pandas as pd
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()


# ── Compute decay rates from historical CSVs ─────────────────────
def compute_decay_rates():
    files = sorted(glob.glob("data/ebay_*.csv"))

    if len(files) < 2:
        print("⚠️  Need at least 2 days of data to compute decay rates")
        print("    Run graph_builder.py daily and try again tomorrow")
        return {"Electrical Items": 0.8, "Fashion": 0.4}

    dfs = [pd.read_csv(f) for f in files]
    df  = pd.concat(dfs, ignore_index=True)
    df["price"] = pd.to_numeric(df["price"], errors="coerce")

    decay_rates = {}
    for category in df["category"].unique():
        cat_data       = df[df["category"] == category]
        price_changes  = (cat_data.groupby("title")["price"]
                                  .std().dropna())
        avg_volatility = price_changes.mean()
        decay_rates[category] = round(
            min(float(avg_volatility) / 100, 1.0), 4
        )
        print(f"  {category}: decay rate = {decay_rates[category]}")

    return decay_rates


# ── Update staleness scores in Neo4j ────────────────────────────
def update_staleness_scores(days_since_refresh=1):
    decay_rates = compute_decay_rates()

    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER"),
              os.getenv("NEO4J_PASSWORD"))
    )

    with driver.session() as session:
        for category, rate in decay_rates.items():
            new_score = round(
                min(rate * days_since_refresh, 1.0), 4
            )
            session.run("""
                MATCH (c:Category {name: $name})
                SET c.staleness_score = $score,
                    c.decay_rate      = $rate
            """, name=category, score=new_score, rate=rate)

            status = "⚠️  STALE" if new_score > 0.7 else "✅ Fresh"
            print(f"  {category}: score={new_score} {status}")

    driver.close()


if __name__ == "__main__":
    print("📊 Computing staleness scores...\n")
    update_staleness_scores(days_since_refresh=1)