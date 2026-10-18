import faiss
import numpy as np


def build_index(right_emb: np.ndarray) -> faiss.IndexFlatIP:
    # Exact search; inner product == cosine because vectors are normalised
    index = faiss.IndexFlatIP(right_emb.shape[1])
    index.add(right_emb)
    return index


def top_k_candidates(left_emb: np.ndarray, right_emb: np.ndarray, k: int):
    k = min(k, right_emb.shape[0])
    scores, idx = build_index(right_emb).search(left_emb, k)
    return scores, idx


def blocking_metrics(left_ids, right_ids, idx, true_pairs, ks=(1, 5, 10, 20, 50)):
    """Pair completeness (blocking recall) and reduction ratio for each K."""
    left_pos = {lid: i for i, lid in enumerate(left_ids)}
    right_pos = {rid: j for j, rid in enumerate(right_ids)}
    true = [(left_pos[l], right_pos[r]) for l, r in true_pairs]
    out = {}
    for k in ks:
        k = min(k, idx.shape[1])
        hits = sum(1 for i, j in true if j in idx[i, :k])
        out[k] = {
            "pair_completeness": round(hits / len(true), 4),
            "reduction_ratio": round(1 - k / len(right_ids), 4),
        }
    return out