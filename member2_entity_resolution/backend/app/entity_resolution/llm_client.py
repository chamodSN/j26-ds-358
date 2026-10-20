"""Thin, provider-agnostic LLM client with a disk cache, retries, token accounting
and a hard call budget (so a bug can never burn your spend limit)."""
import hashlib
import json
import os
import time
from pathlib import Path

import requests

from app.core.config import settings


class BudgetExceeded(RuntimeError):
    pass


def _setting(name, default=None):
    value = getattr(settings, name, None)
    if value in (None, ""):
        value = os.environ.get(name)
    return default if value in (None, "") else value


class LLMClient:
    def __init__(self, max_calls=None, cache_path=None, session=None):
        self.provider = str(_setting("LLM_PROVIDER", "anthropic")).lower()   # anthropic | openai
        self.model = _setting("LLM_MODEL")
        self.api_key = _setting("LLM_API_KEY")
        self.base_url = _setting("LLM_BASE_URL", "https://api.openai.com/v1")
        self.max_output_tokens = int(_setting("LLM_MAX_OUTPUT_TOKENS", 16))
        self.max_calls = int(max_calls if max_calls is not None else _setting("LLM_MAX_CALLS", 1200))
        self.session = session or requests.Session()

        self.cache_path = Path(cache_path) if cache_path else Path(settings.DATA_INTERIM_DIR) / "llm_cache.jsonl"
        self.cache = {}
        if self.cache_path.exists():
            for line in self.cache_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    self.cache[rec["key"]] = rec
        self.network_calls = 0

    # ------------------------------------------------------------------
    def _key(self, system, user):
        raw = json.dumps([self.provider, self.model, system, user], ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _request(self, system, user):
        if not self.model or not self.api_key:
            raise RuntimeError("LLM_MODEL / LLM_API_KEY are not set (see .env and config.py).")
        if self.provider == "anthropic":
            r = self.session.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": self.model, "max_tokens": self.max_output_tokens, "temperature": 0,
                      "system": system, "messages": [{"role": "user", "content": user}]},
                timeout=60)
            if r.status_code == 200:
                d = r.json()
                text = "".join(b.get("text", "") for b in d["content"] if b.get("type") == "text")
                return text, d["usage"]["input_tokens"], d["usage"]["output_tokens"], r
            return None, 0, 0, r
        r = self.session.post(
            self.base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "content-type": "application/json"},
            json={"model": self.model, "temperature": 0, "max_tokens": self.max_output_tokens,
                  "messages": [{"role": "system", "content": system},
                               {"role": "user", "content": user}]},
            timeout=60)
        if r.status_code == 200:
            d = r.json()
            u = d.get("usage", {})
            return (d["choices"][0]["message"].get("content") or ""), \
                u.get("prompt_tokens", 0), u.get("completion_tokens", 0), r
        return None, 0, 0, r

    # ------------------------------------------------------------------
    def complete(self, system, user):
        """Returns dict(text, input_tokens, output_tokens, cached)."""
        key = self._key(system, user)
        if key in self.cache:
            rec = self.cache[key]
            return dict(text=rec["text"], input_tokens=rec["in"], output_tokens=rec["out"], cached=True)

        if self.network_calls >= self.max_calls:
            raise BudgetExceeded(f"Call budget of {self.max_calls} reached. Raise LLM_MAX_CALLS if intended.")

        last = None
        for attempt in range(5):
            self.network_calls += 1
            try:
                text, t_in, t_out, resp = self._request(system, user)
            except requests.RequestException as e:
                last = str(e)
                time.sleep(2 ** attempt)
                continue
            if text is not None:
                rec = dict(key=key, text=text, **{"in": t_in, "out": t_out})
                self.cache[key] = rec
                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.cache_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                return dict(text=text, input_tokens=t_in, output_tokens=t_out, cached=False)
            last = f"HTTP {resp.status_code}: {resp.text[:200]}"
            if resp.status_code in (400, 401, 403, 404):     # not retryable: fix config
                raise RuntimeError(f"LLM request rejected ({last})")
            time.sleep(2 ** attempt)
        raise RuntimeError(f"LLM request failed after retries: {last}")