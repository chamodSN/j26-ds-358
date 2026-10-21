"""
Member 4 - S12: relevance re-ranking for one query (Novelty 1, relevance only).

Reranker.rerank(query, products) -> products sorted by cross-encoder relevance, each with:
    p          : relevance score = sigmoid(logit), 0..1
    p_exact    : calibrated probability the product is EXACT (isotonic, fitted on ESCI validation)
    match      : "great" (p_exact >= 0.90) / "good" (>= 0.50) / "fair"
    low_conf   : listing too incomplete to score reliably (title < 6 words, no brand, no features)

Rules (fixed in S12 Part A, notebook 18_s12_calibration):
  - model     = augplus seed 43, epoch 2 (highest val NDCG), copied to models/m4_final/
  - query     = query_to_text(query, price_span, category)   (useful parts only + M3 category)
  - product   = product_to_text(fields, "full_bullets")      (title | brand | color | features)
  - price, platform and seller fields are NEVER given to the model (handled later in Novelty 2).
"""
from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np

try:                                              # works both as a package and with src/ on sys.path
    from .cross_encoder import _clean, product_to_text, query_to_text
except ImportError:                               # pragma: no cover
    from cross_encoder import _clean, product_to_text, query_to_text

DEFAULT_MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models", "m4_final")

# Attribute keys that describe the PRODUCT (read-only from M2). Anything else is ignored.
BRAND_KEYS = ("brand", "Brand", "manufacturer", "Manufacturer")
COLOR_KEYS = ("color", "colour", "Color", "Colour")
FEATURE_KEYS = ("features", "bullets", "description", "product_bullet_point")
# Listing / seller / price metadata that must never reach the model (eBay fallback puts these in).
IGNORED_KEYS = {"source", "image_url", "item_url", "url", "listing_url", "condition", "seller",
                "seller_rating", "location", "shipping", "categories", "price", "currency"}


def _first(attrs: Dict[str, Any], keys: Sequence[str]) -> str:
    for k in keys:
        v = attrs.get(k)
        if isinstance(v, (str, int, float)) and _clean(v):
            return _clean(v)
    return ""


def product_fields(title: str, attributes: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """M2 product -> the generic keys used by product_to_text. Reads M2 data, never changes it."""
    attrs = {k: v for k, v in (attributes or {}).items() if k not in IGNORED_KEYS}
    return {"title": _clean(title), "brand": _first(attrs, BRAND_KEYS),
            "color": _first(attrs, COLOR_KEYS), "bullets": _first(attrs, FEATURE_KEYS)}


def is_low_confidence(fields: Dict[str, str]) -> bool:
    return len(fields["title"].split()) < 6 and not fields["brand"] and not fields["bullets"]


class Reranker:
    """Loads the deployment model once. `scorer` can be injected (tests) to avoid loading torch."""

    def __init__(self, model_dir: str = DEFAULT_MODEL_DIR,
                 scorer: Optional[Callable[[List[str], List[str]], Sequence[float]]] = None,
                 config: Optional[Dict[str, Any]] = None, device: Optional[str] = None,
                 batch_size: int = 32):
        self.model_dir = os.path.abspath(model_dir)
        self.cfg = config if config is not None else json.load(
            open(os.path.join(self.model_dir, "m4_config.json"), encoding="utf-8"))
        self.max_len = int(self.cfg.get("max_length", 256))
        self.cal_x = np.asarray(self.cfg["cal_x"], dtype=float)
        self.cal_y = np.asarray(self.cfg["cal_y"], dtype=float)
        self.great = float(self.cfg.get("great_if_p_exact_ge", 0.90))
        self.good = float(self.cfg.get("good_if_p_exact_ge", 0.50))
        self.batch_size = batch_size
        self._scorer = scorer or self._load_hf(device)

    # ---------------------------------------------------------------- model
    def _load_hf(self, device: Optional[str]):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        dev = device or ("cuda" if torch.cuda.is_available() else "cpu")
        tok = AutoTokenizer.from_pretrained(self.model_dir)
        model = AutoModelForSequenceClassification.from_pretrained(self.model_dir).to(dev).eval()

        def score(queries: List[str], texts: List[str]) -> List[float]:
            out: List[float] = []
            with torch.inference_mode():
                for i in range(0, len(texts), self.batch_size):
                    enc = tok(queries[i:i + self.batch_size], texts[i:i + self.batch_size], truncation=True,
                              max_length=self.max_len, padding=True, return_tensors="pt").to(dev)
                    out.extend(model(**enc).logits.view(-1).float().cpu().tolist())
            return out
        return score

    # ------------------------------------------------------------ scoring
    def p_exact(self, p: np.ndarray) -> np.ndarray:
        return np.interp(p, self.cal_x, self.cal_y)

    def match_label(self, pe: float) -> str:
        return "great" if pe >= self.great else ("good" if pe >= self.good else "fair")

    def rerank(self, query: str, products: List[Dict[str, Any]], price_span: Optional[str] = None,
               category: Optional[str] = None) -> Dict[str, Any]:
        """products: [{"id", "title", "attributes", "tie" (optional, e.g. retrieval_score)}].
        Returns {"focused_query", "items": [... sorted, best first]}."""
        q = query_to_text(query, price_span=price_span, category=category)
        if not products:
            return {"focused_query": q, "items": []}
        fields = [product_fields(p.get("title", ""), p.get("attributes")) for p in products]
        texts = [product_to_text(f, "full_bullets") for f in fields]
        logits = np.asarray(self._scorer([q] * len(texts), texts), dtype=float)
        p = 1.0 / (1.0 + np.exp(-logits))
        pe = self.p_exact(p)
        items = [{"id": prod.get("id"), "index": i, "p": float(p[i]), "p_exact": float(pe[i]),
                  "match": self.match_label(float(pe[i])), "low_conf": is_low_confidence(fields[i]),
                  "model_text": texts[i]}
                 for i, prod in enumerate(products)]
        # order: relevance first; ties -> upstream retrieval score, then original order (stable)
        ties = [float(prod.get("tie") or 0.0) for prod in products]
        items.sort(key=lambda it: (-it["p"], -ties[it["index"]], it["index"]))
        return {"focused_query": q, "items": items}