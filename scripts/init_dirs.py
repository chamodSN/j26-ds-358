"""
Creates all required data and model directories.
Run once after cloning: python scripts/init_dirs.py
Works on Windows, Mac, and Linux.
"""

import os

DIRS = [
    # Shared data
    "data/raw",
    "data/processed",

    # Member 1
    "member1_retrieval/data/esci",
    "member1_retrieval/data/ebay",
    "member1_retrieval/data/processed",
    "member1_retrieval/models/spec_generator",
    "member1_retrieval/models/classifier",
    "member1_retrieval/models/faiss_index",

    # Member 2
    "member2_entity_resolution/data/abt_buy",
    "member2_entity_resolution/data/amazon_google",
    "member2_entity_resolution/data/wdc",
    "member2_entity_resolution/data/processed",
    "member2_entity_resolution/models/matcher",

    # Member 3
    "member3_knowledge_graph/data/taxonomy",
    "member3_knowledge_graph/data/graph",

    # Member 4
    "member4_reranking/data/esci",
    "member4_reranking/data/ppp",
    "member4_reranking/data/processed",
    "member4_reranking/models/cross_encoder",
]

for d in DIRS:
    os.makedirs(d, exist_ok=True)
    gitkeep = os.path.join(d, ".gitkeep")
    if not os.path.exists(gitkeep):
        open(gitkeep, "w").close()

print(f"Created {len(DIRS)} directories.")
print("Now put your datasets in:")
print("  member1_retrieval/data/esci/       - ESCI parquet files")
print("  member2_entity_resolution/data/    - Abt-Buy, Amazon-Google, WDC")
print("  member4_reranking/data/ppp/        - World Bank PPP CSV")
