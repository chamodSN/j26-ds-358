
from pathlib import Path
import csv
import json

# ==========================================
# 1. Define file paths
# ==========================================

# Locate the member3_knowledge_graph folder
project_dir = Path(__file__).resolve().parent.parent

# Input: Extracted Google Electronics taxonomy
input_file = project_dir / "data" / "electronics_taxonomy.csv"

# Output: Knowledge Graph JSON file
output_file = project_dir / "data" / "electronics_kg.json"


# ==========================================
# 2. Load the Electronics taxonomy
# ==========================================

categories = []

with open(input_file, "r", encoding="utf-8-sig", newline="") as file:
    reader = csv.DictReader(file)

    for row in reader:
        categories.append(row)

print(f"Loaded {len(categories)} Electronics categories.")


# ==========================================
# 3. Create Knowledge Graph nodes
# ==========================================

nodes = []
path_to_id = {}

for category in categories:

    category_id = category["category_id"].strip()
    category_path = category["category_path"].strip()
    category_name = category["category_name"].strip()
    depth = int(category["depth"])

    # Map category paths to their unique IDs
    path_to_id[category_path] = category_id

    # Create a node for each category
    node = {
        "id": category_id,
        "name": category_name,
        "path": category_path,
        "depth": depth,
        "type": "Category"
    }

    nodes.append(node)


# ==========================================
# 4. Create parent-child relationships
# ==========================================

edges = []

for category in categories:

    category_path = category["category_path"].strip()
    category_id = category["category_id"].strip()

    # Split the hierarchy into individual levels
    levels = [
        level.strip()
        for level in category_path.split(">")
    ]

    # Root category has no parent
    if len(levels) == 1:
        continue

    # Identify the full path of the parent category
    parent_path = " > ".join(levels[:-1])

    # Find the parent's category ID
    if parent_path not in path_to_id:
        raise ValueError(
            f"Parent category not found: {parent_path}"
        )

    parent_id = path_to_id[parent_path]

    # Create a relationship from parent to child
    edge = {
        "source": parent_id,
        "target": category_id,
        "relationship": "HAS_SUBCATEGORY"
    }

    edges.append(edge)


# ==========================================
# 5. Construct the Knowledge Graph
# ==========================================

knowledge_graph = {
    "metadata": {
        "name": "Electronics Taxonomy Knowledge Graph",
        "source": "Google Product Taxonomy",
        "domain": "Electronics",
        "total_categories": len(nodes),
        "total_relationships": len(edges)
    },
    "nodes": nodes,
    "edges": edges
}


# ==========================================
# 6. Save Knowledge Graph as JSON
# ==========================================

output_file.parent.mkdir(parents=True, exist_ok=True)

with open(output_file, "w", encoding="utf-8") as file:
    json.dump(
        knowledge_graph,
        file,
        indent=2,
        ensure_ascii=False
    )


# ==========================================
# 7. Display results
# ==========================================

print("\nKnowledge Graph created successfully!")
print(f"Category nodes: {len(nodes)}")
print(f"Relationships: {len(edges)}")
print(f"Saved to: {output_file}")
