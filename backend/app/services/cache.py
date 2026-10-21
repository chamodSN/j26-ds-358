from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import redis.asyncio as redis

from app.config import settings

log = logging.getLogger("vero.cache")
_client: redis.Redis | None = None


def _redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def make_key(prefix: str, **parts: Any) -> str:
    raw = json.dumps(parts, sort_keys=True, default=str)
    return f"vero:{prefix}:{hashlib.sha1(raw.encode()).hexdigest()}"


async def cache_get(key: str) -> Any | None:
    try:
        value = await _redis().get(key)
        return json.loads(value) if value else None
    except Exception as e:  # cache must never break the app
        log.warning("cache get failed: %s", e)
        return None


async def cache_set(key: str, value: Any, ttl: int) -> None:
    try:
        await _redis().set(key, json.dumps(value, default=str), ex=ttl)
    except Exception as e:
        log.warning("cache set failed: %s", e)