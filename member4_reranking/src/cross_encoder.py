"""
Member 4 - Cross-encoder re-ranker: model input text.

product_to_text() : the ONLY place that turns a product into model text.
                    Reads upstream fields (M2), never changes them.
query_to_text()   : the ONLY place that turns the user query into model text.
                    Keeps the product need; removes the parts M1/M3 already used
                    (price limit, price words, "on <platform>", delivery words);
                    adds M3's category as context.
rerank()          : filled in later (S12).
"""
import math
import re

STYLES = ["title", "title_brand", "full", "full_bullets", "key_value"]
MAX_LENGTH = {"title": 128, "title_brand": 128, "full": 128, "full_bullets": 256, "key_value": 128}


def _clean(x) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    return " ".join(str(x).split())


# --------------------------------------------------------------------- product side
def product_to_text(p: dict, style: str = "full", bullet_chars: int = 200) -> str:
    """p uses generic keys: title, brand, color, bullets. Empty parts are skipped.
    key_value imitates M2's harmonized layout ("brand: X | color: Y") using the same fields."""
    title, brand, color = _clean(p.get("title")), _clean(p.get("brand")), _clean(p.get("color"))
    if style == "title":
        parts = [title]
    elif style == "title_brand":
        parts = [title, brand]
    elif style == "full":
        parts = [title, brand, color]
    elif style == "full_bullets":
        parts = [title, brand, color, _clean(p.get("bullets"))[:bullet_chars]]
    elif style == "key_value":
        parts = [title, f"brand: {brand}" if brand else "", f"color: {color}" if color else ""]
    else:
        raise ValueError(f"unknown style: {style}")
    return " | ".join(x for x in parts if x)


def esci_row_to_product(r) -> dict:
    """Maps ESCI column names to the generic keys (stand-in for M2 fields)."""
    return {"title": r["product_title"], "brand": r["product_brand"],
            "color": r["product_color"], "bullets": r["product_bullet_point"]}


# --------------------------------------------------------------------- query side
_CUR = r"(?:(?<![a-z])(?:rs\.?|lkr|inr|usd)(?![a-z])|us\$|\$|£|€|₹)"   # "rs" only as a word (not "chargeRS")
_NUM = r"\d[\d,]*(?:\.\d+)?(?:\s?k)?\b"   # \b: never stop in the middle of a number
# a number followed by a unit is a SPEC, not a price ("under 50 inch", "up to 2tb")
_UNIT = r"(?!\s?(?:inch(?:es)?|in\b|\"|ft|feet|cm|mm|m\b|gb|tb|mb|mah|hz|ghz|mhz|w\b|watts?|v\b|volts?|mp\b|lbs?|oz|ml|ah\b|ports?|pack|pcs|pieces|x\b|%))"
_PRICE_LIMIT = re.compile(
    rf"\b(?:under|below|less than|lower than|cheaper than|up ?to|upto|within|max(?:imum)?|around|about|budget of)\s*"
    rf"(?:{_CUR}\s?)?{_NUM}{_UNIT}(?:\s?(?:{_CUR}|dollars?|bucks|rupees?))?", re.I)
_PRICE_ALONE = re.compile(rf"(?:{_CUR}\s?{_NUM}|\b{_NUM}\s?(?:dollars?|bucks|rupees?|lkr|usd|inr)\b)", re.I)
_PRICE_WORDS = re.compile(r"\b(?:cheap(?:est)?|budget|affordable|inexpensive|low[- ]cost|low price|best price|on sale|discount(?:ed)?)\b", re.I)
_PLATFORM = re.compile(r"\b(?:on|from|at|in)\s+(?:daraz|ebay|aliexpress|alibaba|amazon|walmart)\b", re.I)
_DELIVERY = re.compile(r"\b(?:free (?:shipping|delivery)|fast (?:shipping|delivery)|cash on delivery|cod)\b", re.I)
_DANGLING = re.compile(r"(?:\s+\b(?:with|for|on|at|in|from|and|the)\b)+\s*$", re.I)   # left over after a removal


def query_to_text(query: str, price_span: str | None = None, category: str | None = None,
                  use_rules: bool = True) -> str:
    """Return the ranking-relevant part of the query.
    price_span : exact text M1 extracted (production). If given it is removed as-is.
    use_rules  : small regex rules = ESCI stand-in for M1's extraction (no M1 output yet).
    category   : M3's taxonomy path / category, added in front as context (never inferred here)."""
    q = _clean(query)
    if price_span:
        q = re.sub(re.escape(price_span.strip()), " ", q, flags=re.I)
    if use_rules:
        for rx in (_PRICE_LIMIT, _PRICE_ALONE, _PRICE_WORDS, _PLATFORM, _DELIVERY):
            q = rx.sub(" ", q)
    q = " ".join(q.split())
    if q != _clean(query):                       # only tidy queries we actually changed
        q = _DANGLING.sub("", q).strip(" ,-")
    if not q:                                    # never send an empty query
        q = _clean(query)
    return f"[{_clean(category)}] {q}" if _clean(category) else q


def rerank(query: str, products: list[dict]) -> list[dict]:
    """TODO (S12): score each (query, product) pair and return products sorted by score."""
    raise NotImplementedError