
import json
import hashlib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

GOOGLE_FILE = DATA_DIR / "electronics_kg.json"
AMAZON_FILE = DATA_DIR / "amazon_electronics_categories.json"
OUTPUT_FILE = DATA_DIR / "electronics_kg_combined.json"


def stable_id(path):
    """Create a reproducible ID for an Amazon category path."""
    digest = hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]
    return f"amazon_{digest}"


def main():
    with GOOGLE_FILE.open("r", encoding="utf-8") as file:
        google_graph = json.load(file)

    with AMAZON_FILE.open("r", encoding="utf-8") as file:
        amazon_categories = json.load(file)

    # Normalize Google node metadata without changing IDs or paths.
    nodes = []
    for original in google_graph["nodes"]:
        node = dict(original)
        node["source"] = "Google Product Taxonomy"
        nodes.append(node)

    # Preserve Google edges and normalize their relationship metadata.
    edges = []
    for original in google_graph["edges"]:
        edge = dict(original)
        edge.setdefault(
            "relationship",
            edge.get("type", "HAS_SUBCATEGORY")
        )
        edges.append(edge)

    existing_ids = {node["id"] for node in nodes}
    amazon_nodes = {}
    amazon_edges = {}
    skipped = 0

    promotional_terms = (
        "financing",
        "bestselling",
        "best selling",
        "event",
        "promotion",
        "promotional",
        "deals",
        "savings",
        "discount",
        "off on ",
        "locker eligible",
    )

    for record in amazon_categories:
        path_parts = record.get("path", [])
        if not path_parts:
            continue

        full_path = " > ".join(path_parts)
        normalized_path = full_path.casefold()

        if any(term in normalized_path for term in promotional_terms):
            skipped += 1
            continue

        node_id = stable_id(full_path)

        if node_id not in existing_ids:
            amazon_nodes[node_id] = {
                "id": node_id,
                "name": path_parts[-1],
                "path": full_path,
                "depth": len(path_parts),
                "type": "Category",
                "source": "Amazon",
            }

        if len(path_parts) > 1:
            parent_path = " > ".join(path_parts[:-1])
            parent_id = stable_id(parent_path)

            edge_key = (parent_id, node_id)

            amazon_edges[edge_key] = {
                "source": parent_id,
                "target": node_id,
                "type": "PARENT_OF",
                "relationship": "HAS_SUBCATEGORY",
                "taxonomy": "Amazon",
            }

    nodes.extend(amazon_nodes.values())
    edges.extend(amazon_edges.values())

    combined_graph = {
        "metadata": {
            **google_graph.get("metadata", {}),
            "name": "Combined Electronics Taxonomy Knowledge Graph",
            "sources": ["Google Product Taxonomy", "Amazon"],
            "google_node_count": len(google_graph["nodes"]),
            "google_edge_count": len(google_graph["edges"]),
            "amazon_node_count": len(amazon_nodes),
            "amazon_edge_count": len(amazon_edges),
            "skipped_promotional_paths": skipped,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
        },
        "nodes": nodes,
        "edges": edges,
    }

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(combined_graph, file, indent=2, ensure_ascii=False)

    print("Amazon taxonomy integration complete.")
    print(f"Original Google nodes: {len(google_graph['nodes'])}")
    print(f"Original Google edges: {len(google_graph['edges'])}")
    print(f"Amazon nodes added: {len(amazon_nodes)}")
    print(f"Amazon hierarchy edges added: {len(amazon_edges)}")
    print(f"Promotional paths skipped: {skipped}")
    print(f"Combined nodes: {len(nodes)}")
    print(f"Combined edges: {len(edges)}")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
