from __future__ import annotations

import httpx


class ModuleError(Exception):
    pass


async def post_json(client: httpx.AsyncClient, base_url: str, path: str, payload: dict) -> dict:
    """POST to a team module. Any problem becomes a ModuleError so the pipeline can fall back."""
    try:
        r = await client.post(f"{base_url}{path}", json=payload)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise ModuleError(f"{base_url}{path}: {e}") from e