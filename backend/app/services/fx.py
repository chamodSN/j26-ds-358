from __future__ import annotations

import httpx

from app.config import settings
from app.services.cache import cache_get, cache_set

# Used only if the live exchange-rate service is down and the cache is empty.
FALLBACK = {
    "rates": {"USD": 1.0, "LKR": 300.0, "EUR": 0.92, "GBP": 0.79, "AUD": 1.5, "CAD": 1.37, "INR": 84.0},
    "as_of": None,
    "source": "fallback",
}
_last_good: dict = dict(FALLBACK)


async def get_rates() -> dict:
    """Returns {"rates": {"LKR": ..}, "as_of": str|None, "source": "live"|"fallback"}. Base is USD."""
    cached = await cache_get("vero:fx:usd")
    if cached:
        return cached
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get("https://open.er-api.com/v6/latest/USD")
            r.raise_for_status()
            data = r.json()
        if data.get("result") == "success":
            payload = {
                "rates": data["rates"],
                "as_of": data.get("time_last_update_utc"),
                "source": "live",
            }
            _last_good.update(payload)
            await cache_set("vero:fx:usd", payload, settings.cache_ttl_fx)
            return payload
    except Exception:
        pass
    return dict(_last_good)


def convert(amount: float, from_cur: str, to_cur: str, rates: dict) -> float | None:
    table = rates["rates"]
    if from_cur not in table or to_cur not in table or not table[from_cur]:
        return None
    return amount / table[from_cur] * table[to_cur]