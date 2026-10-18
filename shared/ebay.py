"""
Small async client for the eBay Browse API (read only).

Used by the backend now, and by Member 1 later:

    from shared.ebay import EbayClient, items_to_raw_products
    client = EbayClient()
    data = await client.search("iphone 13", limit=50)
    candidates = items_to_raw_products(data["items"])   # list[RawProduct]
"""

from __future__ import annotations

import asyncio
import base64
import re
import time
from typing import Any, Optional
from urllib.parse import quote

import httpx

from shared.config import settings
from shared.schemas import Platform, RawProduct

HOSTS = {
    "SANDBOX": "https://api.sandbox.ebay.com",
    "PRODUCTION": "https://api.ebay.com",
}
SCOPE = "https://api.ebay.com/oauth/api_scope"


class EbayError(Exception):
    """An error we can show to the user. `status` is the HTTP code to send back."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.message = message
        self.status = status


class EbayClient:
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        environment: Optional[str] = None,
        marketplace: Optional[str] = None,
        timeout: float = 15.0,
    ):
        self.client_id = client_id or settings.ebay_client_id
        self.client_secret = client_secret or settings.ebay_client_secret
        env = (environment or settings.ebay_environment or "PRODUCTION").upper()
        self.base_url = HOSTS.get(env, HOSTS["PRODUCTION"])
        self.marketplace = marketplace or settings.ebay_marketplace or "EBAY_US"
        self._http = httpx.AsyncClient(timeout=timeout)
        self._token: Optional[str] = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    async def aclose(self) -> None:
        await self._http.aclose()

    # ---------------------------------------------------------------- auth
    async def _token_value(self, force: bool = False) -> str:
        if not self.configured:
            raise EbayError(
                "eBay is not connected yet. Add EBAY_CLIENT_ID and EBAY_CLIENT_SECRET to .env.",
                503,
            )
        async with self._lock:
            if not force and self._token and time.time() < self._expires_at - 60:
                return self._token
            basic = base64.b64encode(
                f"{self.client_id}:{self.client_secret}".encode()
            ).decode()
            try:
                r = await self._http.post(
                    f"{self.base_url}/identity/v1/oauth2/token",
                    headers={
                        "Authorization": f"Basic {basic}",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data={"grant_type": "client_credentials", "scope": SCOPE},
                )
            except httpx.HTTPError as e:
                raise EbayError(f"Could not reach eBay: {e}", 502) from e
            if r.status_code != 200:
                raise EbayError(
                    "eBay rejected the API keys. Check EBAY_CLIENT_ID, "
                    "EBAY_CLIENT_SECRET and EBAY_ENVIRONMENT.",
                    502,
                )
            data = r.json()
            self._token = data["access_token"]
            self._expires_at = time.time() + int(data.get("expires_in", 7200))
            return self._token

    async def _get(self, path: str, params: Optional[dict] = None) -> dict:
        r: Optional[httpx.Response] = None
        for attempt in (1, 2):
            token = await self._token_value(force=(attempt == 2))
            try:
                r = await self._http.get(
                    f"{self.base_url}{path}",
                    params=params,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "X-EBAY-C-MARKETPLACE-ID": self.marketplace,
                        "Accept": "application/json",
                    },
                )
            except httpx.HTTPError as e:
                raise EbayError(f"Could not reach eBay: {e}", 502) from e
            if r.status_code == 401 and attempt == 1:
                continue  # token expired early, get a new one and retry once
            break
        assert r is not None
        if r.status_code == 429:
            raise EbayError(
                "eBay rate limit reached. Please try again in a minute.", 429)
        if r.status_code == 404:
            raise EbayError(
                "That item was not found on eBay (it may have ended).", 404)
        if r.status_code >= 400:
            raise EbayError(f"eBay returned an error ({r.status_code}).", 502)
        return r.json()

    # ------------------------------------------------------------ endpoints
    async def search(
        self,
        q: str,
        *,
        limit: int = 24,
        offset: int = 0,
        category_ids: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        condition: Optional[str] = None,  # "new" | "used"
        currency: str = "USD",
    ) -> dict[str, Any]:
        """Returns {"items": [item summaries], "total": int}."""
        params: dict[str, str] = {
            "q": q, "limit": str(limit), "offset": str(offset)}
        if category_ids:
            params["category_ids"] = category_ids

        # stable prices, easier to compare
        filters = ["buyingOptions:{FIXED_PRICE}"]
        if min_price is not None and max_price is not None:
            filters.append(f"price:[{min_price:g}..{max_price:g}]")
        elif min_price is not None:
            filters.append(f"price:[{min_price:g}]")
        elif max_price is not None:
            filters.append(f"price:[..{max_price:g}]")
        if min_price is not None or max_price is not None:
            filters.append(f"priceCurrency:{currency}")
        if condition in ("new", "used"):
            filters.append(f"conditions:{{{condition.upper()}}}")
        params["filter"] = ",".join(filters)

        data = await self._get("/buy/browse/v1/item_summary/search", params)
        return {"items": data.get("itemSummaries", []), "total": int(data.get("total", 0))}

    async def get_item(self, item_id: str) -> dict[str, Any]:
        return await self._get(f"/buy/browse/v1/item/{quote(item_id, safe='')}")


# ---------------------------------------------------------------- helpers
def bigger_image(url: Optional[str]) -> Optional[str]:
    """eBay thumbnails look like .../s-l225.jpg. Ask for a sharper size."""
    if not url:
        return None
    return re.sub(r"s-l\d+(?=\.)", "s-l500", url)


def _price(obj: Optional[dict]) -> tuple[Optional[float], str]:
    if not obj or obj.get("value") is None:
        return None, "USD"
    try:
        return float(obj["value"]), obj.get("currency", "USD")
    except (TypeError, ValueError):
        return None, "USD"


def shipping_text(item: dict) -> Optional[str]:
    options = item.get("shippingOptions") or []
    if not options:
        return None
    cost, cur = _price(options[0].get("shippingCost"))
    if cost is None:
        return None
    if cost == 0:
        return "Free shipping"
    return f"{cur} {cost:,.2f} shipping"


def summary_to_raw_product(item: dict, rank: int, total: int) -> Optional[RawProduct]:
    """Turn one eBay item summary into the team's RawProduct schema."""
    item_id = item.get("itemId")
    price, currency = _price(item.get("price"))
    if not item_id or price is None:
        return None
    seller = item.get("seller") or {}
    try:
        rating = float(seller["feedbackPercentage"]) if seller.get(
            "feedbackPercentage") else None
    except (TypeError, ValueError):
        rating = None
    image = (item.get("image") or {}).get("imageUrl")
    return RawProduct(
        product_id=item_id,
        platform=Platform.EBAY,
        title=item.get("title", "Untitled"),
        price=price,
        currency=currency,
        retrieval_score=max(0.0, 1.0 - (rank - 1) / max(total, 1)),
        rank=rank,
        raw_attributes={
            "source": "ebay",
            "image_url": bigger_image(image),
            "item_url": item.get("itemWebUrl"),
            "condition": item.get("condition"),
            "seller": seller.get("username"),
            "seller_rating": rating,
            "location": (item.get("itemLocation") or {}).get("country"),
            "shipping": shipping_text(item),
            "categories": [c.get("categoryName") for c in item.get("categories", []) if c.get("categoryName")],
        },
    )


def items_to_raw_products(items: list[dict]) -> list[RawProduct]:
    out: list[RawProduct] = []
    for item in items:
        raw = summary_to_raw_product(item, len(out) + 1, len(items))
        if raw is not None:
            out.append(raw)
    return out
