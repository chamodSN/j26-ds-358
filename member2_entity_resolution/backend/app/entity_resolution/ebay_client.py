import base64
import time

import requests

from app.core.config import settings


class EbayClient:
    """Minimal eBay Browse API client (OAuth2 client-credentials flow)."""

    def __init__(self):
        self._token: str | None = None
        self._token_expiry: float = 0.0

    def _get_token(self) -> str:
        # Reuse the cached token until 60 seconds before it expires
        if self._token and time.time() < self._token_expiry - 60:
            return self._token

        credentials = f"{settings.EBAY_CLIENT_ID}:{settings.EBAY_CLIENT_SECRET}"
        b64_credentials = base64.b64encode(credentials.encode()).decode()

        resp = requests.post(
            settings.EBAY_TOKEN_URL,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {b64_credentials}",
            },
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_expiry = time.time() + data["expires_in"]
        return self._token

    def search_electronics(self, query: str, limit: int = 50) -> list[dict]:
        token = self._get_token()

        params = {"q": query, "limit": limit}
        # Category filter is optional: blank on SANDBOX, e.g. 293 on PRODUCTION
        if settings.EBAY_CATEGORY_ID:
            params["category_ids"] = settings.EBAY_CATEGORY_ID

        resp = requests.get(
            settings.EBAY_BROWSE_URL,
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=20,
        )
        resp.raise_for_status()
        items = resp.json().get("itemSummaries", [])

        return [
            {
                "source": "ebay",
                "item_id": it.get("itemId"),
                "title": it.get("title"),
                "price": it.get("price", {}).get("value"),
                "currency": it.get("price", {}).get("currency"),
                "condition": it.get("condition"),
                "seller_location": it.get("itemLocation", {}).get("country"),
                "category": settings.SCOPE_CATEGORY,
            }
            for it in items
        ]


if __name__ == "__main__":
    client = EbayClient()
    results = client.search_electronics("samsung", limit=10)
    print(f"Fetched {len(results)} {settings.SCOPE_CATEGORY} listings from {settings.EBAY_ENV}")
    for r in results[:3]:
        print(r)