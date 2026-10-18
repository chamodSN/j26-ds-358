
import json
from pathlib import Path
from collections import Counter

BASE_DIR = Path(__file__).resolve().parents[1]
GRAPH_FILE = BASE_DIR / "data" / "electronics_kg_combined.json"

with GRAPH_FILE.open("r", encoding="utf-8") as file:
    graph = json.load(file)

nodes = graph["nodes"]
edges = graph["edges"]

node_ids = [node["id"] for node in nodes]
node_id_set = set(node_ids)

duplicate_ids = [
    node_id
    for node_id, count in Counter(node_ids).items()
    if count > 1
]

missing_endpoints = [
    edge
    for edge in edges
    if edge.get("source") not in node_id_set
    or edge.get("target") not in node_id_set
]

google_nodes = [
    node for node in nodes
    if node.get("source", "Google Product Taxonomy")
    == "Google Product Taxonomy"
]

amazon_nodes = [
    node for node in nodes
    if node.get("source") == "Amazon"
]

amazon_edges = [
    edge for edge in edges
    if edge.get("taxonomy") == "Amazon"
]

print("=== Combined Knowledge Graph Validation ===")
print(f"Total nodes: {len(nodes)}")
print(f"Total edges: {len(edges)}")
print(f"Google nodes: {len(google_nodes)}")
print(f"Amazon nodes: {len(amazon_nodes)}")
print(f"Amazon hierarchy edges: {len(amazon_edges)}")
print(f"Duplicate node IDs: {len(duplicate_ids)}")
print(f"Edges with missing endpoints: {len(missing_endpoints)}")

if duplicate_ids:
    print("\nDuplicate ID examples:", duplicate_ids[:5])

if missing_endpoints:
    print("\nInvalid edge examples:", missing_endpoints[:5])

print("\nValidation result:")
if not duplicate_ids and not missing_endpoints:
    print("PASS: Node IDs are unique and all edge endpoints exist.")
else:
    print("FAIL: Review the reported graph integrity issues.")
