import os
from pathlib import Path

from dotenv import load_dotenv

# Project root = member2_entity_resolution/ (the folder that holds .env)
# this file: backend/app/core/config.py -> parents[3] is the project root
ROOT_DIR = Path(__file__).resolve().parents[3]
load_dotenv(ROOT_DIR / ".env")


class Settings:
    # ---------------- eBay Browse API ----------------
    EBAY_CLIENT_ID: str = os.getenv("EBAY_CLIENT_ID", "")
    EBAY_CLIENT_SECRET: str = os.getenv("EBAY_CLIENT_SECRET", "")
    EBAY_ENV: str = os.getenv("EBAY_ENV", "PRODUCTION").upper()

    # Leave blank on SANDBOX (its category tree differs from production).
    # On PRODUCTION set e.g. EBAY_CATEGORY_ID=293 (Consumer Electronics).
    EBAY_CATEGORY_ID: str = os.getenv("EBAY_CATEGORY_ID", "")

    EBAY_TOKEN_URL: str = (
        "https://api.ebay.com/identity/v1/oauth2/token"
        if EBAY_ENV == "PRODUCTION"
        else "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
    )
    EBAY_BROWSE_URL: str = (
        "https://api.ebay.com/buy/browse/v1/item_summary/search"
        if EBAY_ENV == "PRODUCTION"
        else "https://api.sandbox.ebay.com/buy/browse/v1/item_summary/search"
    )

    # ---------------- Scope decision ----------------
    SCOPE_CATEGORY: str = "electronics"

    # ---------------- Novelty 1: 3-tier cascade thresholds ----------------
    # Starting values; Phase 3 tunes them on the validation set.
    HIGH_CONFIDENCE_THRESHOLD: float = 0.90   # >= this -> auto-accept
    LOW_CONFIDENCE_THRESHOLD: float = 0.65    # <  this -> LLM decides

    # ---------------- Embedding model ----------------
    SBERT_MODEL_NAME: str = "all-MiniLM-L6-v2"

    # ---------------- Paths ----------------
    DATA_RAW_DIR: Path = ROOT_DIR / "data" / "raw"
    DATA_INTERIM_DIR: Path = ROOT_DIR / "data" / "interim"
    DATA_PROCESSED_DIR: Path = ROOT_DIR / "data" / "processed"
    CANONICAL_SCHEMA_PATH: Path = ROOT_DIR / "schemas" / "canonical_schema.json"

    BLOCKING_TOP_K: int = 10
    RANDOM_SEED: int = 42
    RESULTS_DIR: Path = ROOT_DIR / "research" / "results"

    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = ""
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MAX_OUTPUT_TOKENS: int = 16
    LLM_MAX_CALLS: int = 1200


settings = Settings()