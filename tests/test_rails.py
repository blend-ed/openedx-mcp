"""Unit tests for the pure safety-rail primitives (no platform needed)."""
from django.core.cache import cache

from openedx_mcp.api.mcp import _rails


def setup_function(_):
    cache.clear()


# --- fingerprint ---

def test_fingerprint_is_order_insensitive():
    a = _rails.fingerprint("t", 1, {"x": 1, "y": 2})
    b = _rails.fingerprint("t", 1, {"y": 2, "x": 1})
    assert a == b


def test_fingerprint_binds_tool_user_payload():
    base = _rails.fingerprint("t", 1, {"x": 1})
    assert _rails.fingerprint("other", 1, {"x": 1}) != base
    assert _rails.fingerprint("t", 2, {"x": 1}) != base
    assert _rails.fingerprint("t", 1, {"x": 2}) != base


# --- confirm token ---

def test_confirm_token_roundtrip_and_single_use():
    payload = {"course_id": "c", "n": 5}
    token = _rails.issue_confirm_token("bulk_enroll", 7, payload)
    # first use succeeds
    assert _rails.consume_confirm_token(token, "bulk_enroll", 7, payload) is True
    # second use fails — single use
    assert _rails.consume_confirm_token(token, "bulk_enroll", 7, payload) is False


def test_confirm_token_rejects_changed_payload():
    token = _rails.issue_confirm_token("bulk_enroll", 7, {"n": 5})
    # preview said 5, apply tries 50 -> invalid
    assert _rails.consume_confirm_token(token, "bulk_enroll", 7, {"n": 50}) is False


def test_confirm_token_empty_is_false():
    assert _rails.consume_confirm_token("", "t", 1, {}) is False


# --- rate limit ---

def test_rate_limit_blocks_after_budget():
    # bulk_enroll budget is (5, 300)
    limit = _rails.RATE_LIMITS["bulk_enroll"][0]
    key = "key-A"
    for _ in range(limit):
        allowed, _win = _rails.check_rate_limit("bulk_enroll", key)
        assert allowed is True
    allowed, _win = _rails.check_rate_limit("bulk_enroll", key)
    assert allowed is False


def test_rate_limit_is_per_key():
    for _ in range(_rails.RATE_LIMITS["bulk_enroll"][0]):
        _rails.check_rate_limit("bulk_enroll", "key-1")
    # different key still has a fresh budget
    allowed, _ = _rails.check_rate_limit("bulk_enroll", "key-2")
    assert allowed is True


def test_unknown_tool_uses_default_limit():
    limit = _rails.DEFAULT_RATE_LIMIT[0]
    key = "key-D"
    for _ in range(limit):
        assert _rails.check_rate_limit("nonexistent_tool", key)[0] is True
    assert _rails.check_rate_limit("nonexistent_tool", key)[0] is False


# --- redact ---

def test_redact_hides_secrets():
    out = _rails.redact({"password": "hunter2", "confirm_token": "abc", "name": "ok"})
    assert out["password"] == "[redacted]"
    assert out["confirm_token"] == "[redacted]"
    assert out["name"] == "ok"


def test_redact_summarises_long_lists():
    out = _rails.redact({"emails": [f"u{i}@x.com" for i in range(50)]})
    assert out["emails"]["count"] == 50
    assert out["emails"]["truncated"] is True
    assert len(out["emails"]["sample"]) == _rails._MAX_LIST_SAMPLE


def test_redact_recurses_into_dicts():
    out = _rails.redact({"outer": {"password": "x", "ok": 1}})
    assert out["outer"]["password"] == "[redacted]"
    assert out["outer"]["ok"] == 1
