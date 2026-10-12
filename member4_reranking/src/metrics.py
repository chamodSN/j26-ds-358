"""
Member 4 - Ranking metrics for ESCI (MRR, NDCG@10, P@5).

Rules (master plan Section 7):
  - MRR and P@k count only Exact (label == 1.0) as relevant.
  - NDCG@k uses graded gains E=1.0, S=0.1, C=0.01, I=0.0 (linear gain, log2 discount).
    IDCG uses all candidates of the query.
  - Only queries with at least one Exact product are evaluated.
  - Ties in score are broken randomly with a fixed seed (no system gets lucky
    from the input row order).
  - P@5 can be below 1 for a perfect ranker when a query has fewer than 5 Exact products.
"""

import numpy as np
import pandas as pd

EXACT = 1.0


def rank_order(scores: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Indices sorted by score (desc); ties broken by a random key."""
    tie = rng.random(len(scores))
    return np.lexsort((tie, -np.asarray(scores, dtype=float)))


def dcg(gains: np.ndarray, k: int) -> float:
    g = np.asarray(gains, dtype=float)[:k]
    return float(np.sum(g / np.log2(np.arange(2, len(g) + 2))))


def ndcg_at_k(ranked_labels: np.ndarray, k: int = 10) -> float:
    ideal = dcg(np.sort(ranked_labels)[::-1], k)
    return dcg(ranked_labels, k) / ideal if ideal > 0 else 0.0


def mrr(ranked_labels: np.ndarray) -> float:
    hits = np.flatnonzero(np.asarray(ranked_labels) == EXACT)
    return 1.0 / (hits[0] + 1) if len(hits) else 0.0


def precision_at_k(ranked_labels: np.ndarray, k: int = 5) -> float:
    return float(np.sum(np.asarray(ranked_labels)[:k] == EXACT)) / k


def evaluate(df: pd.DataFrame, score_col: str, seed: int = 42) -> pd.DataFrame:
    """Per-query metrics. df needs columns query_id, label, <score_col>
    (optional: subcategory). Returns one row per evaluated query."""
    rng = np.random.default_rng(seed)
    rows = []
    for qid, g in df.groupby("query_id", sort=True):
        labels = g["label"].to_numpy(dtype=float)
        if not np.any(labels == EXACT):
            continue
        ranked = labels[rank_order(g[score_col].to_numpy(), rng)]
        row = {"query_id": qid, "mrr": mrr(ranked), "ndcg@10": ndcg_at_k(ranked, 10),
               "p@5": precision_at_k(ranked, 5), "n_candidates": len(g)}
        if "subcategory" in g:
            row["subcategory"] = g["subcategory"].iloc[0]
        rows.append(row)
    return pd.DataFrame(rows)


def summarize(per_query: pd.DataFrame) -> dict:
    return {"queries": int(len(per_query)),
            **{m: round(float(per_query[m].mean()), 4) for m in ["mrr", "ndcg@10", "p@5"]}}