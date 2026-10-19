
import numpy as np

from app.entity_resolution.router import cascade


def test_strategy_a_sends_low_to_llm():
    cos = np.array([0.95, 0.80, 0.50])
    ver = np.array([-1, 1, -1])
    blk = np.array([1, 1, 1])

    pred, llm = cascade(
        cos, ver, blk,
        lo=0.65, hi=0.90, strategy="A"
    )

    assert pred.tolist() == [1, 1, 0]
    assert llm.tolist() == [False, False, True]


def test_strategy_b_disagreement_and_llm():
    cos = np.array([0.95, 0.80, 0.50])
    ver = np.array([0, -1, -1])
    blk = np.array([1, 1, 1])

    pred, llm = cascade(
        cos, ver, blk,
        lo=0.65, hi=0.90, strategy="B"
    )

    assert pred.tolist() == [0, 0, 0]
    assert llm.tolist() == [True, True, False]


def test_unblocked_never_predicted():
    pred, llm = cascade(
        np.array([0.99]),
        np.array([1]),
        np.array([0]),
        lo=0.65, hi=0.90, strategy="B"
    )

    assert pred.tolist() == [0]
    assert llm.tolist() == [False]
