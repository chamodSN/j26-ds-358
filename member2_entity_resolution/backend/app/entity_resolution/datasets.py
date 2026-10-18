import pandas as pd

from app.core.config import settings


def load_records(name: str) -> pd.DataFrame:
    path = settings.DATA_INTERIM_DIR / f"{name}_records.csv"
    return pd.read_csv(path, dtype=str).fillna("")


def load_pairs(name: str) -> pd.DataFrame:
    path = settings.DATA_PROCESSED_DIR / f"{name}_pairs.csv"
    return pd.read_csv(path, dtype={"left_id": str, "right_id": str})