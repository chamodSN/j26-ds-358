
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

GRAPH_FILE = DATA_DIR / "electronics_kg_combined.json"
CROSSWALK_FILE = DATA_DIR / "category_crosswalk_candidates.json"


def main():
    with GRAPH_FILE.open("r", encoding="utf-8") as f:
        graph = json.load(f)

    with CROSSWALK_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        candidates = data
    else:
        candidates = data.get("candidates", data.get("crosswalk", []))

    nodes = {str(node["id"]): node for node in graph["nodes"]}

    # Back up the graph before changing it.
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_file = GRAPH_FILE.with_name(
        f"{GRAPH_FILE.stem}.backup_{timestamp}.json"
    )
    shutil.copy2(GRAPH_FILE, backup_file)

    # Remove previously generated candidate links so reruns are safe.
    edges = [
        edge for edge in graph["edges"]
        if edge.get("relationship") != "CANDIDATE_MAPPING"
    ]

    added = 0
    skipped = 0

    for item in candidates:
        amazon_id = str(item.get("amazon_id", ""))
        google_id = str(item.get("google_id", ""))

        amazon_node = nodes.get(amazon_id)
        google_node = nodes.get(google_id)

        if (
            not amazon_node
            or not google_node
            or amazon_node.get("source") != "Amazon"
            or google_node.get("source") != "Google Product Taxonomy"
        ):
            skipped += 1
            continue

        edges.append({
            "source": amazon_id,
            "target": google_id,
            "type": "CANDIDATE_MAPPING",
            "relationship": "CANDIDATE_MAPPING",
            "taxonomy": "Cross-taxonomy",
            "verified": item.get("verified") is True,
            "proposed_relationship": item.get("relationship"),
            "similarity_score": item.get("similarity_score"),
            "status": item.get("status"),
            "verification_method": (
                item.get("verification_method")
                if item.get("verified") is True
                else None
            ),
        })
        added += 1

    graph["edges"] = edges
    metadata = graph.setdefault("metadata", {})
    metadata["crosswalk_candidate_edges"] = added
    metadata["crosswalk_verified_candidates"] = sum(
        item.get("verified") is True for item in candidates
    )
    metadata["crosswalk_unverified_candidates"] = sum(
        item.get("verified") is not True for item in candidates
    )

    with GRAPH_FILE.open("w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)

    print("Crosswalk candidate integration complete.")
    print(f"Candidates in source: {len(candidates)}")
    print(f"Candidate links added: {added}")
    print(f"Invalid candidates skipped: {skipped}")
    print(f"Verified candidates: {metadata['crosswalk_verified_candidates']}")
    print(f"Unverified candidates: {metadata['crosswalk_unverified_candidates']}")
    print(f"Total graph nodes: {len(graph['nodes'])}")
    print(f"Total graph edges: {len(graph['edges'])}")
    print(f"Backup: {backup_file}")
    print(f"Updated graph: {GRAPH_FILE}")


if __name__ == "__main__":
    main()
