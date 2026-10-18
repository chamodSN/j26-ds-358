
import json
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
GRAPH_FILE = BASE_DIR / "data" / "electronics_kg_combined.json"

with GRAPH_FILE.open("r", encoding="utf-8") as file:
    graph = json.load(file)

nodes = {node["id"]: node for node in graph["nodes"]}
edges = graph["edges"]

source_counts = Counter(
    node.get("source", "unspecified")
    for node in graph["nodes"]
)

relationship_counts = Counter(
    edge.get("relationship", "missing")
    for edge in edges
)

missing_endpoints = []
cross_taxonomy_edges = []

for edge in edges:
    source_id = edge.get("source")
    target_id = edge.get("target")

    if source_id not in nodes or target_id not in nodes:
        missing_endpoints.append((source_id, target_id))
        continue

    source_taxonomy = nodes[source_id].get("source")
    target_taxonomy = nodes[target_id].get("source")

    if source_taxonomy != target_taxonomy:
        cross_taxonomy_edges.append(edge)

print("NODE SOURCES:")
print(dict(source_counts))

print("\nEDGE RELATIONSHIPS:")
print(dict(relationship_counts))

print("\nTOTAL NODES:", len(nodes))
print("TOTAL EDGES:", len(edges))
print("EDGES WITH MISSING ENDPOINTS:", len(missing_endpoints))
print("CROSS-TAXONOMY EDGES:", len(cross_taxonomy_edges))

print("\nSAMPLE CROSS-TAXONOMY EDGES:")
for edge in cross_taxonomy_edges[:5]:
    print(edge)
