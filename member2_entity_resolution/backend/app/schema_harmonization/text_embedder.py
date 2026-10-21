"""SBERT embeddings for short texts (attribute name + sample values)."""
from functools import lru_cache

import numpy as np

from app.core.config import settings


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(settings.SBERT_MODEL_NAME)


def embed_texts(texts, batch_size=64):
    """L2-normalised embeddings, so a dot product is the cosine similarity."""
    vecs = _model().encode(list(texts), batch_size=batch_size,
                           normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(vecs, dtype=np.float32)