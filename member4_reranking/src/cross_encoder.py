"""
Member 4 - Cross-encoder re-ranker.

product_to_text() is the ONLY place that turns a product into model text.
When Member 2's harmonized fields are ready, change only this function.
rerank() is filled in at Step 9 (after the best model is chosen).
"""


def product_to_text(product: dict) -> str:
    """Temporary format: 'title | brand | color' (empty parts are skipped)."""
    parts = [product.get("title"), product.get("brand"), product.get("color")]
    return " | ".join(str(p).strip() for p in parts if p and str(p).strip())


def rerank(query: str, products: list[dict]) -> list[dict]:
    """TODO (Step 9): score each (query, product) pair and return products sorted by score."""
    raise NotImplementedError
