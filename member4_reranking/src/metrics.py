"""
Member 4 - Ranking metrics with ESCI gains (E=1.0, S=0.1, C=0.01, I=0.0).
NDCG@10 uses the gains; MRR and Precision@5 count only Exact (gain >= 1.0) as relevant.
Ties in the score are broken by a seeded random number, so the data's original order cannot help.
"""
import numpy as np
import pandas as pd

GAIN = {"E": 1.0, "S": 0.1, "C": 0.01, "I": 0.0}


def ndcg_at_k(ranked_gains, all_gains, k=10):
    g = np.asarray(ranked_gains, float)[:k]
    dcg = float((g / np.log2(np.arange(2, len(g) + 2))).sum())
    ideal = np.sort(np.asarray(all_gains, float))[::-1][:k]
    idcg = float((ideal / np.log2(np.arange(2, len(ideal) + 2))).sum())
    return dcg / idcg if idcg > 0 else 0.0


def mrr(ranked_gains):
    for i, g in enumerate(ranked_gains, 1):
        if g >= 1.0:
            return 1.0 / i
    return 0.0


def precision_at_k(ranked_gains, k=5):
    return float((np.asarray(list(ranked_gains)[:k]) >= 1.0).sum()) / k


def evaluate(d: pd.DataFrame, score_col="score", seed=0):
    """d needs query_id, gain and score_col. Returns (mean metrics dict, per-query DataFrame)."""
    d = d.copy()
    d["_tie"] = np.random.default_rng(seed).random(len(d))
    d = d.sort_values(["query_id", score_col, "_tie"], ascending=[True, False, True])
    rows = []
    for qid, grp in d.groupby("query_id", sort=False):
        g = grp["gain"].tolist()
        rows.append({"query_id": qid, "ndcg@10": ndcg_at_k(g, g, 10),
                     "mrr": mrr(g), "p@5": precision_at_k(g, 5)})
    per_q = pd.DataFrame(rows)
    return per_q[["ndcg@10", "mrr", "p@5"]].mean().round(4).to_dict(), per_q