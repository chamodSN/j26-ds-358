import os
from pathlib import Path
from threading import Lock
from time import time
from typing import Any

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

CLIENT_ID = os.getenv("EBAY_CLIENT_ID")
CLIENT_SECRET = os.getenv("EBAY_CLIENT_SECRET")
ENVIRONMENT = os.getenv("EBAY_ENVIRONMENT", "").upper()

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
BROWSE_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"

MARKETPLACE_ID = os.getenv("EBAY_MARKETPLACE_ID", "EBAY_US")

_token: str | None = None
_token_expiry = 0.0
_token_lock = Lock()


def _get_access_token() -> str:
    """Get and temporarily cache an eBay application access token."""
    global _token, _token_expiry

    if ENVIRONMENT != "PRODUCTION":
        raise RuntimeError(
            "Set EBAY_ENVIRONMENT=PRODUCTION in the root .env file."
        )

    if not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError(
            "Missing EBAY_CLIENT_ID or EBAY_CLIENT_SECRET in the root .env."
        )

    with _token_lock:
        if _token and time() < _token_expiry - 60:
            return _token

        response = requests.post(
            TOKEN_URL,
            auth=(CLIENT_ID, CLIENT_SECRET),
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
            timeout=20,
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"eBay OAuth failed (HTTP {response.status_code}). "
                "Check the backend logs and eBay application configuration."
            )

        data = response.json()
        _token = data["access_token"]
        _token_expiry = time() + int(data.get("expires_in", 7200))
        return _token


def search_ebay_products(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    Retrieve live eBay listings and normalize them for the frontend.

    Returns an empty list when eBay returns no matching listings.
    API/configuration errors raise an exception for the backend to handle.
    """
    token = _get_access_token()

    response = requests.get(
        BROWSE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": MARKETPLACE_ID,
            "Accept": "application/json",
        },
        params={
            "q": query,
            "limit": max(1, min(int(limit), 20)),
        },
        timeout=25,
    )

    if response.status_code != 200:
        # Don't return credentials or token information in the error.
        raise RuntimeError(
            f"eBay product search failed (HTTP {response.status_code})."
        )

    data = response.json()
    products = []

    for item in data.get("itemSummaries", []):
        price = item.get("price") or {}
        image = item.get("image") or {}
        shipping_options = item.get("shippingOptions") or []
        shipping = shipping_options[0] if shipping_options else {}

        aspects = item.get("localizedAspects") or []
        categories = item.get("categories") or []

        specifications = []
        for aspect in aspects:
            name = aspect.get("name")
            value = aspect.get("value")
            if name and value:
                specifications.append({
                    "name": name,
                    "value": value,
                })

        products.append({
            "product_id": item.get("itemId"),
            "title": item.get("title", "eBay product"),
            "platform": "ebay",
            "price": price.get("value"),
            "currency": price.get("currency"),
            "image_url": image.get("imageUrl"),
            "product_url": item.get("itemWebUrl"),
            "condition": item.get("condition"),
            "condition_id": item.get("conditionId"),
            "brand": None,
            "model": None,
            "shipping_cost": (
                (shipping.get("shippingCost") or {}).get("value")
            ),
            "shipping_currency": (
                (shipping.get("shippingCost") or {}).get("currency")
            ),
            "seller": (item.get("seller") or {}).get("username"),
            "category_ids": [
                category.get("categoryId")
                for category in categories
                if category.get("categoryId")
            ],
            "specifications": specifications,
            "item_location": item.get("itemLocation"),
        })

    return products