"""
Member 4 - Cross-encoder re-ranker.

product_to_text() is the ONLY place that turns a product into model text.
When Member 2's harmonized fields are ready, change only this function.
rerank() is filled in at Step 9 (after the best model is chosen).
"""
import math

STYLES = ["title", "title_brand", "full", "full_bullets"]
MAX_LENGTH = {"title": 128, "title_brand": 128, "full": 128, "full_bullets": 256}


def _clean(x) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    return " ".join(str(x).split())


def product_to_text(p: dict, style: str = "full", bullet_chars: int = 200) -> str:
    """p uses generic keys: title, brand, color, bullets. Empty parts are skipped."""
    title, brand, color = _clean(p.get("title")), _clean(p.get("brand")), _clean(p.get("color"))
    if style == "title":
        parts = [title]
    elif style == "title_brand":
        parts = [title, brand]
    elif style == "full":
        parts = [title, brand, color]
    elif style == "full_bullets":
        parts = [title, brand, color, _clean(p.get("bullets"))[:bullet_chars]]
    else:
        raise ValueError(f"unknown style: {style}")
    return " | ".join(x for x in parts if x)


def esci_row_to_product(r) -> dict:
    """Maps ESCI column names to the generic keys."""
    return {"title": r["product_title"], "brand": r["product_brand"],
            "color": r["product_color"], "bullets": r["product_bullet_point"]}


def rerank(query: str, products: list[dict]) -> list[dict]:
    """TODO (Step 9): score each (query, product) pair and return products sorted by score."""
    raise NotImplementedError