import requests
from app.core.config import settings
from app.entity_resolution.ebay_client import EbayClient

client = EbayClient()
token = client._get_token()
headers = {"Authorization": f"Bearer {token}"}

tests = [
    ("phone, no category", {"q": "phone", "limit": 5}),
    ("laptop, no category", {"q": "laptop", "limit": 5}),
    ("phone + category 293", {"q": "phone", "category_ids": "293", "limit": 5}),
    ("samsung, no category", {"q": "samsung", "limit": 5}),
]

print("Environment:", settings.EBAY_ENV)
for label, params in tests:
    r = requests.get(settings.EBAY_BROWSE_URL, headers=headers, params=params, timeout=20)
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    print(f"\n[{label}] status={r.status_code} total={body.get('total')} "
          f"items={len(body.get('itemSummaries', []))}")
    if r.status_code != 200 or not body.get("itemSummaries"):
        print("  raw:", r.text[:250])