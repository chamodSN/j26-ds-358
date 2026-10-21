from pathlib import Path
import re
import numpy as np
import pandas as pd

OUT = Path("../data/processed")
V = "v2.3"


def load_all():
    queries = pd.read_parquet(OUT / f"esci_electronics_{V}_queries.parquet")
    roles = pd.read_csv(OUT / f"query_roles_{V}.csv")
    queries = queries.merge(roles, on="query_id")
    judg = pd.read_parquet(OUT / f"esci_electronics_{V}_judgments.parquet")
    corpus = pd.read_parquet(
        OUT / f"esci_electronics_{V}_corpus_retrieval.parquet").reset_index(drop=True)
    return queries, judg, corpus


def build_qrels(judg):
    qrels = {}
    for qid, pid, g in zip(judg["query_id"], judg["product_id"], judg["gain"]):
        qrels.setdefault(qid, {})[pid] = g
    return qrels


def tokenize(text):
    return re.findall(r"\w+", str(text).lower())


def minmax(x):
    x = np.asarray(x, dtype=float)
    lo, hi = x.min(), x.max()
    return np.zeros_like(x) if hi == lo else (x - lo) / (hi - lo)


def _dcg(gains):
    gains = np.asarray(gains, dtype=float)
    return float((gains / np.log2(np.arange(2, len(gains) + 2))).sum())


def evaluate(ranked, qrels, k=10, mrr_relevant=1.0):
    """ranked: {query_id: [product_id, ...]} best first.
    Unjudged products count as gain 0 (ESCI convention).
    MRR counts a hit when gain >= mrr_relevant (1.0 = Exact only)."""
    rows = []
    for qid, pids in ranked.items():
        rel = qrels[qid]
        g = [rel.get(p, 0.0) for p in pids[:k]]
        idcg = _dcg(sorted(rel.values(), reverse=True)[:k])
        ndcg = _dcg(g) / idcg if idcg > 0 else 0.0
        rr = next((1.0 / (i + 1)
                  for i, x in enumerate(g) if x >= mrr_relevant), 0.0)
        rows.append((qid, ndcg, rr))
    return pd.DataFrame(rows, columns=["query_id", f"ndcg@{k}", f"mrr@{k}"]).set_index("query_id")
