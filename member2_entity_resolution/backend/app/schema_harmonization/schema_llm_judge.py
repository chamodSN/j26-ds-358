"""LLM judge for the MIDDLE band of schema growth (same idea as the Novelty-1 cascade):

   similarity >= high  -> decided automatically (same attribute)
   low <= sim < high   -> THIS JUDGE decides   (embeddings cannot tell 'upload speed' from 'download speed')
   similarity <  low   -> decided automatically (different attribute)

One question, two uses:
   * does a NEW name belong to an existing candidate cluster?
   * is an AMBIGUOUS name just another name for a canonical (seed) attribute?
Every answer is cached on disk (llm_cache.jsonl) and logged, so a run can be audited and repeated for free."""
from collections import Counter

from app.entity_resolution.llm_client import BudgetExceeded
from app.entity_resolution.llm_matcher import parse_answer

SYSTEM = (
    "You compare two product-attribute names taken from different online shops. Answer MATCH only if a value "
    "stored under A could be stored under B WITHOUT changing its meaning: same property, same scope, same kind "
    "of value. Answer NON_MATCH if they differ in any qualifier that changes the meaning (minimum / maximum / "
    "average / peak / installed / package versus product / read versus write / input versus output / front "
    "versus rear), if one is a more specific or more general version of the other, if they measure different "
    "things even when the unit is the same, if the example values are a different kind of thing (for example a "
    "web address versus a name), or if you are unsure. The same attribute written in another language, or with "
    "different spelling or spacing, is a MATCH. Examples: 'Colour' and 'Couleur' -> MATCH; 'Battery life' and "
    "'Max battery life' -> NON_MATCH; 'Input voltage' and 'Output voltage' -> NON_MATCH; 'Front USB ports' and "
    "'Rear USB ports' -> NON_MATCH. Answer with exactly one word: MATCH or NON_MATCH."
)
# NOTE: the examples above must never be pairs that were audited (schema_cluster_audit.SHOULD_* and the rows of
# llm_decision_audit*.csv), otherwise the answers leak into the prompt.


def _fmt(name, samples):
    vals = [str(s)[:40] for s in list(samples)[:3]]
    return f"{name}" + (f"   (example values: {' | '.join(vals)})" if vals else "")


def build_prompt(name_a, samples_a, name_b, samples_b):
    return SYSTEM, f"Attribute A: {_fmt(name_a, samples_a)}\nAttribute B: {_fmt(name_b, samples_b)}"


class LLMAttributeJudge:
    """Callable: judge(name_a, samples_a, name_b, samples_b) -> 1 (same) | 0 (different) | None (no answer).

    strict=True: a MATCH must be CONFIRMED with A and B swapped (removes order bias).
    A wrong MATCH corrupts data silently; a wrong NON_MATCH only leaves two synonyms apart - so the
    two errors are not equally expensive and MATCH needs more evidence."""

    def __init__(self, client, strict=True):
        self.client = client
        self.strict = strict
        self.stats = Counter()
        self.log = []

    def _ask(self, na, sa, nb, sb):
        system, user = build_prompt(na, sa, nb, sb)
        try:
            res = self.client.complete(system, user)
        except BudgetExceeded:
            self.stats["budget_stop"] += 1
            return None
        self.stats["cached" if res["cached"] else "network_calls"] += 1
        self.stats["tokens_in"] += 0 if res["cached"] else res["input_tokens"]
        v = parse_answer(res["text"])
        self.stats["unparsed"] += v is None
        return v

    def __call__(self, name_a, samples_a, name_b, samples_b):
        first = self._ask(name_a, samples_a, name_b, samples_b)
        verdict, second = first, ""
        if self.strict and first == 1:
            swapped = self._ask(name_b, samples_b, name_a, samples_a)
            second = {1: "MATCH", 0: "NON_MATCH", None: "?"}[swapped]
            if swapped != 1:
                self.stats["match_not_confirmed"] += 1
                verdict = 0 if swapped == 0 else None
        self.log.append(dict(a=name_a, b=name_b, verdict={1: "MATCH", 0: "NON_MATCH", None: "?"}[verdict],
                             first={1: "MATCH", 0: "NON_MATCH", None: "?"}[first], swapped=second))
        return verdict