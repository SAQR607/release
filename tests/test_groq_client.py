"""Groq failover + JSON extraction tests (§25, §42)."""

import json

import pytest

from app.groq_client import GroqClient, GroqExhausted, GroqKeyPool, extract_json


def test_extract_json_plain():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_fenced():
    text = 'Sure! ```json\n{"title": "X"}\n``` done'
    assert extract_json(text) == {"title": "X"}


def test_extract_json_with_prose_around():
    text = 'Here you go: {"k": [1,2]} hope that helps'
    assert extract_json(text) == {"k": [1, 2]}


def test_extract_json_array():
    assert extract_json("[1, 2, 3]") == [1, 2, 3]


def test_extract_json_garbage_raises():
    with pytest.raises(ValueError):
        extract_json("no json here at all")


def test_key_pool_rotation_and_auth_exhaustion():
    pool = GroqKeyPool(["k1", "k2"])
    assert pool.current() == (0, "k1")
    pool.mark_auth_failed()
    pool.rotate()
    assert pool.current() == (1, "k2")
    pool.mark_auth_failed()
    with pytest.raises(GroqExhausted):
        pool.rotate()


def test_key_pool_single_slot():
    pool = GroqKeyPool(["only"])
    pool.rotate()  # wraps back to 0 (not disabled yet)
    assert pool.current() == (0, "only")
    pool.mark_auth_failed()
    with pytest.raises(GroqExhausted):
        pool.rotate()


class _FakeHTTP:
    """Scripted responses: list of (status, body_dict_or_str[, retry_after])."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def __call__(self, payload, key, timeout):
        self.calls += 1
        row = self.script.pop(0)
        status, body = row[0], row[1]
        retry_after = row[2] if len(row) > 2 else None
        if isinstance(body, dict):
            body = json.dumps(body)
        return status, body, retry_after


def _ok_body(content="hello"):
    return {"choices": [{"message": {"content": content}}]}


def test_client_success_first_try():
    from app import groq_client

    orig = groq_client._post_chat
    groq_client._post_chat = _FakeHTTP([(200, _ok_body("hi"))])
    try:
        client = GroqClient(["k1"], model="m", sleep=lambda s: None, max_attempts=3)
        out = client.chat([{"role": "user", "content": "x"}])
        assert out == "hi"
    finally:
        groq_client._post_chat = orig


def test_client_429_waits_same_slot():
    from app import groq_client

    orig = groq_client._post_chat
    fake = _FakeHTTP([(429, ""), (200, _ok_body("ok"))])
    groq_client._post_chat = fake
    try:
        client = GroqClient(["k1", "k2"], model="m", sleep=lambda s: None, max_attempts=4)
        assert client.chat([{"role": "user", "content": "x"}]) == "ok"
        assert fake.calls == 2
        # TPM is org-wide: rotating keys would not help, so we wait on the slot.
        assert client.pool.current()[0] == 0
    finally:
        groq_client._post_chat = orig


def test_client_auth_failure_exhausts_all_slots():
    from app import groq_client

    orig = groq_client._post_chat
    fake = _FakeHTTP([(401, ""), (401, "")])
    groq_client._post_chat = fake
    try:
        client = GroqClient(["k1", "k2"], model="m", sleep=lambda s: None, max_attempts=6)
        with pytest.raises(GroqExhausted):
            client.chat([{"role": "user", "content": "x"}])
        assert fake.calls == 2  # one auth attempt per slot, then stop
    finally:
        groq_client._post_chat = orig


def test_client_5xx_backoff_bounded_attempts():
    from app import groq_client

    orig = groq_client._post_chat
    fake = _FakeHTTP([(500, "")] * 3)
    groq_client._post_chat = fake
    try:
        client = GroqClient(["k1"], model="m", sleep=lambda s: None, max_attempts=3)
        with pytest.raises(GroqExhausted):
            client.chat([{"role": "user", "content": "x"}])
        assert fake.calls == 3  # never retries forever
    finally:
        groq_client._post_chat = orig


def test_client_429_honors_retry_after_header():
    from app import groq_client

    orig = groq_client._post_chat
    fake = _FakeHTTP([(429, "", 7), (200, _ok_body("ok"))])
    groq_client._post_chat = fake
    slept: list = []
    try:
        client = GroqClient(["k1"], model="m", sleep=slept.append, max_attempts=4)
        assert client.chat([{"role": "user", "content": "x"}]) == "ok"
        assert slept == [7.0]  # server said 7s — not the fixed 62s
        assert client.pool.current()[0] == 0  # org-wide limits: same slot
    finally:
        groq_client._post_chat = orig


def test_client_429_without_retry_after_waits_fixed_window():
    from app import groq_client

    orig = groq_client._post_chat
    fake = _FakeHTTP([(429, ""), (200, _ok_body("ok"))])
    groq_client._post_chat = fake
    slept: list = []
    try:
        client = GroqClient(["k1"], model="m", sleep=slept.append, max_attempts=4)
        assert client.chat([{"role": "user", "content": "x"}]) == "ok"
        assert slept == [62.0]
    finally:
        groq_client._post_chat = orig
