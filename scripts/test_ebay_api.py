
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

# =====================================
# 1. Load Production API credentials
# =====================================

project_dir = Path(__file__).resolve().parent.parent
load_dotenv(project_dir / ".env")

client_id = os.getenv("EBAY_CLIENT_ID")
client_secret = os.getenv("EBAY_CLIENT_SECRET")
environment = os.getenv("EBAY_ENVIRONMENT", "").upper()

if not client_id or not client_secret:
    raise ValueError("Missing eBay credentials in .env")

if environment != "PRODUCTION":
    raise ValueError(
        "Set EBAY_ENVIRONMENT=PRODUCTION in .env"
    )

print("Production credentials loaded successfully.")

# =====================================
# 2. Request OAuth application token
# =====================================

token_url = (
    "https://api.ebay.com/identity/v1/oauth2/token"
)

response = requests.post(
    token_url,
    auth=(client_id, client_secret),
    data={
        "grant_type": "client_credentials",
        "scope": (
            "https://api.ebay.com/oauth/api_scope"
        )
    },
    timeout=30
)

if response.status_code != 200:
    print("Authentication failed.")
    print("HTTP status:", response.status_code)
    print("Check your Production keys and API access.")
    raise SystemExit(1)

access_token = response.json()["access_token"]

print("OAuth authentication successful!")
print("Access token obtained (not displayed).")

# =====================================
# 3. Test eBay Browse API
# =====================================

browse_url = (
    "https://api.ebay.com/buy/browse/v1/item_summary/search"
)

headers = {
    "Authorization": f"Bearer {access_token}",
    "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
    "Accept": "application/json"
}

params = {
    "q": "wireless headphones",
    "limit": 5
}

print("\nSearching eBay for wireless headphones...")

browse_response = requests.get(
    browse_url,
    headers=headers,
    params=params,
    timeout=30
)

print("Browse API HTTP status:", browse_response.status_code)

if browse_response.status_code == 200:
    data = browse_response.json()
    items = data.get("itemSummaries", [])

    print(f"Products returned: {len(items)}")

    for index, item in enumerate(items, start=1):
        title = item.get("title", "Unknown")
        price = item.get("price", {})
        amount = price.get("value", "N/A")
        currency = price.get("currency", "")

        print(f"\n{index}. {title}")
        print(f"   Price: {amount} {currency}")
        print(f"   Category ID: {item.get('leafCategoryIds', [])}")

    print("\nAPI test completed successfully.")

else:
    print("Browse API request was not successful.")
    print("HTTP status:", browse_response.status_code)

    # Avoid displaying response bodies that might
    # contain sensitive diagnostic information.
    if browse_response.status_code in (401, 403):
        print("Possible authentication or API permission issue.")
    elif browse_response.status_code == 429:
        print("API rate limit reached.")
    else:
        print("Check marketplace access and request parameters.")
