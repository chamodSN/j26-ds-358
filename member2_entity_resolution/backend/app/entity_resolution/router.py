
import numpy as np


def cascade(
    cos,
    verdict,
    blocked,
    lo: float,
    hi: float,
    strategy: str,
):
    """
    Confidence-aware product matching router.

    Returns:
        pred:
            Automatic predictions (1=match, 0=non-match).
            LLM-routed pairs remain 0 until resolved.

        llm_mask:
            Boolean mask identifying pairs sent to the LLM.

    Strategies:
        A: Original proposal, LLM handles low similarity.
        B: Disagreement-aware, LLM handles uncertain
           middle pairs and high-similarity rule conflicts.
    """
    if not 0 <= lo < hi <= 1:
        raise ValueError("Require 0 <= lo < hi <= 1")

    cos = np.asarray(cos, dtype=float)
    verdict = np.asarray(verdict, dtype=int)
    blocked = np.asarray(blocked, dtype=int)

    if not (
        len(cos) == len(verdict) == len(blocked)
    ):
        raise ValueError("Input lengths must match")

    high = cos >= hi
    low = cos < lo
    mid = ~(high | low)
    retrieved = blocked == 1

    pred = np.zeros(len(cos), dtype=int)
    llm = np.zeros(len(cos), dtype=bool)

    if strategy == "A":
        # Original proposal: LLM for low-similarity pairs.
        pred[high] = 1
        pred[mid & (verdict == 1)] = 1
        llm = low.copy()

    elif strategy == "B":
        # Strong evidence and no rule rejection.
        pred[high & (verdict != 0)] = 1

        # Rule accepts in the middle tier.
        pred[mid & (verdict == 1)] = 1

        # Uncertain middle-tier pairs.
        llm = mid & (verdict == -1)

        # High similarity conflicts with rule rejection.
        llm |= high & (verdict == 0)

    else:
        raise ValueError(
            f"Unknown strategy: {strategy!r}"
        )

    # Unretrieved pairs cannot be matched or sent to LLM.
    pred[~retrieved] = 0
    llm &= retrieved

    # Routed pairs have no automatic prediction.
    pred[llm] = 0

    return pred, llm


def prf(y, p):
    """Calculate binary precision, recall and F1."""
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=int)

    tp = int(((y == 1) & (p == 1)).sum())
    fp = int(((y == 0) & (p == 1)).sum())
    fn = int(((y == 1) & (p == 0)).sum())

    precision = (
        tp / (tp + fp) if tp + fp else 0.0
    )
    recall = (
        tp / (tp + fn) if tp + fn else 0.0
    )
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall else 0.0
    )

    return precision, recall, f1
