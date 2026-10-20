import numpy as np

from app.entity_resolution.router_v2 import cascade_any

LO, HI = 0.5, 0.9


def run(cos, v, b=1, s="C"):
    p, l = cascade_any([cos], [v], [b], LO, HI, s)
    return int(p[0]), bool(l[0])


def test_rule_accept_trusted_at_any_cosine():
    assert run(0.2, 1) == (1, False) and run(0.7, 1) == (1, False) and run(0.97, 1) == (1, False)


def test_high_cosine_without_rule_agreement_goes_to_llm():
    assert run(0.97, -1) == (0, True) and run(0.97, 0) == (0, True)


def test_middle_band():
    assert run(0.7, -1) == (0, True) and run(0.7, 0) == (0, False)


def test_low_band_rejected_without_llm():
    assert run(0.2, -1) == (0, False) and run(0.2, 0) == (0, False)


def test_unblocked_never_predicted_or_routed():
    assert run(0.97, 1, b=0) == (0, False) and run(0.97, -1, b=0) == (0, False)


def test_c_matches_b_outside_the_two_changed_cells():
    cos = np.array([0.7, 0.7, 0.7, 0.2, 0.2, 0.97, 0.97])
    v = np.array([1, -1, 0, -1, 0, 1, 0])
    b = np.ones(7, dtype=int)
    pb, lb = cascade_any(cos, v, b, LO, HI, "B")
    pc, lc = cascade_any(cos, v, b, LO, HI, "C")
    assert (pb == pc).all() and (lb == lc).all()