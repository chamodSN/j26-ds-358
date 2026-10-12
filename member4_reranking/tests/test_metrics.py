"""Unit tests for member4_reranking/src/metrics.py.  Run: python -m pytest member4_reranking/tests -q"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from metrics import evaluate, mrr, ndcg_at_k, precision_at_k  # noqa: E402


def test_hand_example():
    ranked = np.array([0.0, 1.0, 0.1, 1.0])          # I, E, S, E
    assert mrr(ranked) == pytest.approx(0.5)
    assert precision_at_k(ranked, 5) == pytest.approx(2 / 5)
    dcg = 1 / np.log2(3) + 0.1 / np.log2(4) + 1 / np.log2(5)
    idcg = 1 + 1 / np.log2(3) + 0.1 / np.log2(4)
    assert ndcg_at_k(ranked, 10) == pytest.approx(dcg / idcg)


def _df(labels, scores, qid=1):
    return pd.DataFrame({"query_id": qid, "label": labels, "score": scores})


def test_oracle_scores_one():
    labels = [1.0, 0.1, 0.01, 0.0, 1.0]
    pq = evaluate(_df(labels, labels), "score")
    assert pq["mrr"].iloc[0] == 1.0 and pq["ndcg@10"].iloc[0] == pytest.approx(1.0)
    assert pq["p@5"].iloc[0] == pytest.approx(2 / 5)    # only 2 Exact exist


def test_queries_without_exact_skipped():
    d = pd.concat([_df([1.0, 0.0], [1, 0], 1), _df([0.1, 0.0], [1, 0], 2)])
    assert list(evaluate(d, "score").query_id) == [1]


def test_ties_do_not_use_row_order():
    # all scores equal: result must not depend on input order (seeded random tie-break)
    a = evaluate(_df([1.0] + [0.0] * 9, [0.5] * 10), "score", seed=1)
    b = evaluate(_df([0.0] * 9 + [1.0], [0.5] * 10), "score", seed=1)
    assert 0 < a["mrr"].iloc[0] <= 1 and 0 < b["mrr"].iloc[0] <= 1
    r = [evaluate(_df([1.0] + [0.0] * 9, [0.5] * 10), "score", seed=s)["mrr"].iloc[0]
         for s in range(20)]
    assert len(set(r)) > 1                               # not always rank 1