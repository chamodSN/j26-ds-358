"""Strategy C = Strategy B plus two fixes found by error analysis:
  1. a rule ACCEPT is trusted at ANY cosine (rule ACCEPT precision >= 0.98 on validation);
  2. a very high cosine alone is NOT trusted: without a rule ACCEPT the pair goes to the LLM.
Everything else is identical to Strategy B."""
import numpy as np

from app.entity_resolution.router import cascade as _cascade_ab


def cascade_c(cos, verdict, blocked, lo, hi):
    cos = np.asarray(cos, dtype=float)
    verdict = np.asarray(verdict, dtype=int)
    ok = np.asarray(blocked, dtype=int) == 1

    pred = np.zeros(len(cos), dtype=int)
    llm = np.zeros(len(cos), dtype=bool)

    pred[ok & (verdict == 1)] = 1                                  # rule ACCEPT: accept at any cosine
    rest = ok & (verdict != 1)
    llm |= rest & (cos >= hi)                                       # high cosine, no rule agreement
    llm |= rest & (cos >= lo) & (cos < hi) & (verdict == -1)       # middle band, rules undecided
    return pred, llm                                                # rule REJECT in middle band / low band: reject


def cascade_any(cos, verdict, blocked, lo, hi, strategy):
    if strategy == "C":
        return cascade_c(cos, verdict, blocked, lo, hi)
    return _cascade_ab(cos, verdict, blocked, lo=lo, hi=hi, strategy=strategy)