"""Shapes of the JSON this API sends and receives. (Not the same as shared/schemas.py.)"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# auth
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    name: str = Field(default="", max_length=100)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class GoogleIn(BaseModel):
    credential: str = Field(min_length=10)


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    avatar_url: str | None = None
    has_password: bool = False
    google_linked: bool = False


# products
class ProductOut(BaseModel):
    id: str  # eBay item id, e.g. "v1|1234567890|0"
    rank: int
    title: str
    image_url: str | None = None
    item_url: str | None = None
    platform: str = "ebay"
    price: float
    currency: str
    price_lkr: float | None = None
    # These two stay empty until Member 4 (re-ranking + PPP) is enabled
    ppp_adjusted_price_usd: float | None = None
    relevance_score: float | None = None
    condition: str | None = None
    seller: str | None = None
    seller_rating: float | None = None
    location: str | None = None
    shipping: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class PipelineInfo(BaseModel):
    modules: list[str]  # e.g. ["ebay"] now, ["m3","m1","m2","m4"] later
    # enabled modules that failed
    degraded: list[str] = Field(default_factory=list)
    latency_ms: int = 0
    cached: bool = False


class FxInfo(BaseModel):
    usd_to_lkr: float | None = None
    as_of: str | None = None
    source: str = "fallback"  # "live" or "fallback"


class SearchResponse(BaseModel):
    query: str
    total: int  # how many listings eBay says match
    count: int  # how many we return
    items: list[ProductOut]
    pricing_mode: str  # "fx_only" or "ppp"
    pipeline: PipelineInfo
    fx: FxInfo


class Spec(BaseModel):
    name: str
    value: str


class ItemDetailOut(BaseModel):
    id: str
    title: str
    image_url: str | None = None
    images: list[str] = Field(default_factory=list)
    item_url: str | None = None
    price: float
    currency: str
    price_lkr: float | None = None
    condition: str | None = None
    seller: str | None = None
    seller_rating: float | None = None
    location: str | None = None
    shipping: str | None = None
    brand: str | None = None
    description: str = ""
    specs: list[Spec] = Field(default_factory=list)
    related: list[ProductOut] = Field(default_factory=list)


class Rail(BaseModel):
    key: str
    title: str
    category: str
    items: list[ProductOut]


class FeaturedResponse(BaseModel):
    rails: list[Rail]


# saved / history
class SavedIn(BaseModel):
    item_id: str = Field(min_length=1, max_length=120)
    title: str = Field(max_length=500)
    image_url: str | None = None
    item_url: str | None = None
    price: float = Field(ge=0)
    currency: str = Field(default="USD", max_length=8)
    price_lkr: float | None = None


class SavedOut(SavedIn):
    model_config = ConfigDict(from_attributes=True)
    created_at: datetime


class HistoryOut(BaseModel):
    query: str
    searched_at: datetime
