import json

import pytest

import app.entity_resolution.llm_client as llm_client_module
from app.entity_resolution.llm_client import BudgetExceeded, LLMClient
from app.entity_resolution.llm_matcher import judge_pair, parse_answer


class FakeResponse:
    def __init__(self, code, payload):
        self.status_code, self._p, self.text = code, payload, json.dumps(payload)

    def json(self):
        return self._p


class FakeSession:
    def __init__(self, answers):
        self.answers, self.calls = list(answers), 0

    def post(self, url, **kw):
        self.calls += 1
        a = self.answers.pop(0)
        if isinstance(a, int):
            return FakeResponse(a, {})
        return FakeResponse(200, {"content": [{"type": "text", "text": a}],
                                  "usage": {"input_tokens": 50, "output_tokens": 2}})


def make_client(tmp_path, answers, max_calls=5):
    c = LLMClient(max_calls=max_calls, cache_path=tmp_path / "cache.jsonl", session=FakeSession(answers))
    c.provider, c.model, c.api_key = "anthropic", "test-model", "test-key"
    return c


def test_parse_answer():
    assert parse_answer("MATCH") == 1 and parse_answer(" match.") == 1 and parse_answer("Yes") == 1
    assert parse_answer("NON_MATCH") == 0 and parse_answer("non-match") == 0
    assert parse_answer("Non match") == 0 and parse_answer("NOT a match") == 0 and parse_answer("No") == 0
    assert parse_answer("") is None and parse_answer("maybe") is None


def test_cache_tokens_and_budget(tmp_path):
    c = make_client(tmp_path, ["MATCH", "NON_MATCH"], max_calls=2)
    p, r = judge_pair(c, "Sony DSCW150", "Sony DSC-W150")
    assert p == 1 and r["input_tokens"] == 50 and not r["cached"]
    p, r = judge_pair(c, "Sony DSCW150", "Sony DSC-W150")          # same pair -> cache, no network
    assert p == 1 and r["cached"] and c.session.calls == 1
    judge_pair(c, "a1", "b2")
    with pytest.raises(BudgetExceeded):
        judge_pair(c, "x", "y")
    c2 = make_client(tmp_path, [], max_calls=0)                     # cache survives restart
    assert judge_pair(c2, "a1", "b2")[0] == 0


def test_retry_on_rate_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_client_module.time, "sleep", lambda s: None)
    c = make_client(tmp_path, [429, "MATCH"])
    assert judge_pair(c, "q1", "w2")[0] == 1 and c.session.calls == 2


def test_auth_error_is_not_retried(tmp_path):
    c = make_client(tmp_path, [401])
    with pytest.raises(RuntimeError, match="401"):
        judge_pair(c, "q1", "w2")
    assert c.session.calls == 1