from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: str = "development"
    secret_key: str = "dev-only-change-me"
    cookie_secure: bool = False
    session_days: int = 7
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Data stores
    database_url: str = "postgresql+psycopg://vero:vero@localhost:5433/vero"
    redis_url: str = "redis://localhost:6380/0"

    # Google login (public client id only)
    google_client_id: str | None = None

    # Team modules. Each one is OFF until the member finishes it.
    enable_m1: bool = False
    enable_m2: bool = False
    enable_m3: bool = False
    enable_m4: bool = False

    # Cache lifetimes (seconds)
    cache_ttl_search: int = 600
    cache_ttl_item: int = 1800
    cache_ttl_featured: int = 3600
    cache_ttl_fx: int = 3600

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


settings = Settings()
