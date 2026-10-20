"""Zero-shot LLM judge for the uncertain pairs the cascade routes to Tier 3."""
import re

SYSTEM = "You are an expert at matching product listings from different online shops."
USER = (
    "Do the two listings below describe the exact same product (same brand and same model)?\n\n"
    "Listing A: {a}\n"
    "Listing B: {b}\n\n"
    "Answer with exactly one word: MATCH or NON_MATCH."
)
MAX_TITLE_CHARS = 200
_MATCH = {"MATCH", "YES"}
_NON_MATCH = {"NON_MATCH", "NONMATCH", "NON", "NOT", "NO"}


def parse_answer(text):
    """1 = match, 0 = non-match, None = unparseable."""
    t = str(text).strip().upper().replace("-", "_")
    first = re.split(r"[^A-Z_]", t)[0] if t else ""
    if first in _MATCH:
        return 1
    if first in _NON_MATCH:
        return 0
    return None


def build_prompt(left_title, right_title):
    return SYSTEM, USER.format(a=str(left_title)[:MAX_TITLE_CHARS], b=str(right_title)[:MAX_TITLE_CHARS])


def judge_pair(client, left_title, right_title):
    system, user = build_prompt(left_title, right_title)
    res = client.complete(system, user)
    return parse_answer(res["text"]), res