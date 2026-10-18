import hashlib

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

from app.core.config import settings

_model = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.SBERT_MODEL_NAME)
    return _model


def embed_texts(texts, batch_size: int = 64) -> np.ndarray:
    emb = get_model().encode(
        list(texts),
        batch_size=batch_size,
        normalize_embeddings=True,   # unit vectors: inner product == cosine
        convert_to_numpy=True,
        show_progress_bar=True,
    )
    return emb.astype("float32")


def _fingerprint(records: pd.DataFrame) -> str:
    h = hashlib.md5(settings.SBERT_MODEL_NAME.encode())
    for rid, text in zip(records["record_id"], records["text"]):
        h.update(rid.encode())
        h.update(text.encode())
    return h.hexdigest()


def embed_records_cached(records: pd.DataFrame, name: str) -> np.ndarray:
    """Cached on disk; re-computed automatically if texts or model change."""
    settings.DATA_INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    emb_path = settings.DATA_INTERIM_DIR / f"{name}_emb.npy"
    fp_path = settings.DATA_INTERIM_DIR / f"{name}_emb.fp"
    fp = _fingerprint(records)
    if emb_path.exists() and fp_path.exists() and fp_path.read_text() == fp:
        return np.load(emb_path)
    emb = embed_texts(records["text"].tolist())
    np.save(emb_path, emb)
    fp_path.write_text(fp)
    return emb


if __name__ == "__main__":
    from app.entity_resolution.datasets import load_records

    for name in ["abt_buy", "amazon_google", "wdc"]:
        recs = load_records(name)
        emb = embed_records_cached(recs, name)
        print(name, emb.shape, "norm of first vector:", round(float(np.linalg.norm(emb[0])), 4))