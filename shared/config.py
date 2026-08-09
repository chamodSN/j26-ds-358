"""
Shared configuration loaded from environment variables.
Import this in any module that needs config values.

Usage:
    from shared.config import settings
    print(settings.ebay_client_id)
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # eBay API
    ebay_client_id: Optional[str] = None
    ebay_client_secret: Optional[str] = None
    ebay_environment: str = "SANDBOX"

    # AliExpress Affiliate API
    aliexpress_app_key: Optional[str] = None
    aliexpress_app_secret: Optional[str] = None

    # Service URLs
    member1_url: str = "http://localhost:8001"
    member2_url: str = "http://localhost:8002"
    member3_url: str = "http://localhost:8003"
    member4_url: str = "http://localhost:8004"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()