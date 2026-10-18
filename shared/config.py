"""
Shared configuration loaded from environment variables.
Import this in any module that needs config values.

Usage:
    from shared.config import settings
    print(settings.ebay_client_id)
"""

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # "../.env" is for running from a sub-folder (like backend/). ".env" wins if both exist.
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # do not crash on keys this class does not know
    )

    # eBay API
    ebay_client_id: Optional[str] = None
    ebay_client_secret: Optional[str] = None
    ebay_environment: str = "PRODUCTION"
    ebay_marketplace: str = "EBAY_US"

    # AliExpress Affiliate API
    aliexpress_app_key: Optional[str] = None
    aliexpress_app_secret: Optional[str] = None

    # Service URLs of the team modules
    member1_url: str = "http://localhost:8001"
    member2_url: str = "http://localhost:8002"
    member3_url: str = "http://localhost:8003"
    member4_url: str = "http://localhost:8004"


settings = Settings()