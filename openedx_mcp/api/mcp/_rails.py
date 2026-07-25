"""
Pure safety-rail primitives: payload fingerprinting, single-use confirm tokens,
fixed-window rate limiting, and audit redaction.

Deliberately dependency-light — imports only the Django cache and the stdlib, no
models, no DRF, no Open edX. That keeps this unit-testable outside a running
platform (see tests/test_rails.py); `guards.py` composes these into the
`audited_write` decorator with the DRF/audit machinery.
"""
import hashlib
import json
import logging
import secrets
import time

from django.core.cache import cache

log = logging.getLogger(__name__)

CONFIRM_TOKEN_TTL_SECONDS = 300
_CONFIRM_PREFIX = "mcp:confirm:"
_RL_PREFIX = "mcp:rl:"

# Per-(key, tool) fixed-window limits: (max_calls, window_seconds). Tuned to the
# blast radius of one call — mass tools get the tightest budget.
RATE_LIMITS = {
    "enroll_user": (60, 60),
    "unenroll_user": (60, 60),
    "bulk_enroll": (5, 300),
    "create_user": (20, 300),
    "set_role": (30, 60),
    "instructor_access": (30, 60),
    "reset_attempts": (30, 60),
    "deactivate_user": (10, 300),
    "generate_certificate": (10, 300),
    "regenerate_certificates": (5, 600),
    "invalidate_certificate": (20, 300),
    "submit_report": (10, 300),
    "request_retirement": (5, 600),
    "create_xblock": (200, 60),
    "update_xblock": (200, 60),
    "publish_xblock": (100, 60),
    "delete_xblock": (60, 60),
    "update_course_settings": (60, 60),
}
DEFAULT_RATE_LIMIT = (30, 60)

_SENSITIVE = {"confirm_token", "password", "key", "secret", "token"}
_MAX_LIST_SAMPLE = 20


def fingerprint(tool, user_id, payload):
    """Stable hash of (tool, acting user, payload). Order-insensitive; a confirm
    token is bound to this so a preview of A cannot be applied as B."""
    blob = json.dumps({"tool": tool, "user": str(user_id), "payload": payload},
                      sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def issue_confirm_token(tool, user_id, payload):
    token = secrets.token_urlsafe(24)
    cache.set(f"{_CONFIRM_PREFIX}{token}", fingerprint(tool, user_id, payload),
              CONFIRM_TOKEN_TTL_SECONDS)
    return token


def consume_confirm_token(token, tool, user_id, payload):
    """True only if `token` was issued for this exact (tool, user, payload).
    Single-use: burned on first success so a retry cannot replay it."""
    if not token:
        return False
    ck = f"{_CONFIRM_PREFIX}{token}"
    stored = cache.get(ck)
    if not stored or stored != fingerprint(tool, user_id, payload):
        return False
    cache.delete(ck)  # single use
    return True


def check_rate_limit(tool, key_id):
    """Fixed-window counter per (key, tool). Returns (allowed, window). Fails
    OPEN on cache errors — the audit log is the real integrity guard."""
    limit, window = RATE_LIMITS.get(tool, DEFAULT_RATE_LIMIT)
    try:
        window_start = int(time.time()) // window
        ck = f"{_RL_PREFIX}{key_id}:{tool}:{window_start}"
        cache.add(ck, 0, window)
        try:
            count = cache.incr(ck)
        except ValueError:
            cache.set(ck, 1, window)
            count = 1
        return (count <= limit), window
    except Exception as exc:  # noqa: BLE001 — fail open, audit is the real guard
        log.warning("rate-limit check failed tool=%s key=%s: %s", tool, key_id, exc)
        return True, 0


def redact(payload):
    """Shrink + de-secret a request body for the audit trail. Long lists become
    a sample + count; sensitive keys become [redacted]."""
    out = {}
    for k, v in (payload or {}).items():
        if k.lower() in _SENSITIVE:
            out[k] = "[redacted]"
        elif isinstance(v, list):
            out[k] = {"count": len(v), "sample": [str(x)[:200] for x in v[:_MAX_LIST_SAMPLE]],
                      "truncated": len(v) > _MAX_LIST_SAMPLE}
        elif isinstance(v, dict):
            out[k] = redact(v)
        elif isinstance(v, str):
            out[k] = v[:500]
        else:
            out[k] = v
    return out
