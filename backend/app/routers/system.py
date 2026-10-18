from __future__ import annotations

import asyncio

import httpx
from fastapi import APIRouter

from app.config import settings
from app.services.ebay import ebay
from shared.config import settings as shared

router = APIRouter(prefix="/api", tags=["system"])

MODULES = [
    ("m1", "Query intent and retrieval",
     lambda: shared.member1_url, lambda: settings.enable_m1),
    ("m2", "Entity resolution", lambda: shared.member2_url, lambda: settings.enable_m2),
    ("m3", "Knowledge graph routing",
     lambda: shared.member3_url, lambda: settings.enable_m3),
    ("m4", "Re-ranking and PPP pricing",
     lambda: shared.member4_url, lambda: settings.enable_m4),
]


@router.get("/health")
def health():
    return {
        "status": "ok",
        "ebay_configured": ebay.configured,
        "google_configured": bool(settings.google_client_id),
        "modules_enabled": {key: enabled() for key, _l, _u, enabled in MODULES},
    }


async def _ping(client: httpx.AsyncClient, key: str, label: str, url: str, enabled: bool):
    status = "off"
    if enabled:
        try:
            r = await client.get(f"{url}/health")
            status = "up" if r.status_code == 200 else f"error {r.status_code}"
        except httpx.HTTPError:
            status = "down"
    return {"key": key, "label": label, "url": url, "enabled": enabled, "status": status}


@router.get("/modules")
async def modules_status():
    async with httpx.AsyncClient(timeout=2.5) as client:
        rows = await asyncio.gather(
            *[_ping(client, k, label, url(), enabled()) for k, label, url, enabled in MODULES]
        )
    return {"modules": rows}
