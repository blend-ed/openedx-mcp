"""
Safety rails for state-changing MCP tools.

An MCP key is driven by an autonomous agent, not a human clicking a button. The
failure mode designed against is a *looping* agent — a retry storm that mass-
enrols or deletes. Four rails, applied by the `audited_write` decorator:

 1. Live authority re-check (the IsStaffOrSuperuser permission already does this
    per request; audited_write assumes it ran).
 2. Rate limit — per (key, tool) fixed window. Turns a runaway loop into ~N calls.
 3. Confirm token — a write with no token performs a DRY RUN and returns a preview
    plus a single-use token bound to a fingerprint of the exact payload. Re-send
    with the token to apply. Changing the payload invalidates the token.
 4. Append-only audit — intent recorded before the write; the write is refused if
    the record cannot be persisted.

The confirm-token store and rate-limit counter use the ambient Django cache. In
production that must be a shared backend (Redis/memcached); under LocMemCache
(dev) both are per-process.
"""
import functools
import hashlib
import json
import logging
import secrets
import time

from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response

from ...models import MCPAuditLog
from .auth import get_key, require_scopes

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
    "deactivate_user": (10, 300),
    "create_xblock": (200, 60),
    "update_xblock": (200, 60),
    "publish_xblock": (100, 60),
    "delete_xblock": (60, 60),
    "update_course_settings": (60, 60),
}
DEFAULT_RATE_LIMIT = (30, 60)

_SENSITIVE = {"confirm_token", "password", "key", "secret", "token"}
_MAX_LIST_SAMPLE = 20


def _fingerprint(tool, user_id, payload):
    blob = json.dumps({"tool": tool, "user": str(user_id), "payload": payload},
                      sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def issue_confirm_token(tool, user_id, payload):
    token = secrets.token_urlsafe(24)
    cache.set(f"{_CONFIRM_PREFIX}{token}", _fingerprint(tool, user_id, payload),
              CONFIRM_TOKEN_TTL_SECONDS)
    return token


def consume_confirm_token(token, tool, user_id, payload):
    if not token:
        return False
    ck = f"{_CONFIRM_PREFIX}{token}"
    stored = cache.get(ck)
    if not stored or stored != _fingerprint(tool, user_id, payload):
        return False
    cache.delete(ck)  # single use
    return True


def check_rate_limit(tool, key_id):
    """Fixed-window counter per (key, tool). Fails OPEN on cache errors."""
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


def _redact(payload):
    out = {}
    for k, v in (payload or {}).items():
        if k.lower() in _SENSITIVE:
            out[k] = "[redacted]"
        elif isinstance(v, list):
            out[k] = {"count": len(v), "sample": [str(x)[:200] for x in v[:_MAX_LIST_SAMPLE]],
                      "truncated": len(v) > _MAX_LIST_SAMPLE}
        elif isinstance(v, dict):
            out[k] = _redact(v)
        elif isinstance(v, str):
            out[k] = v[:500]
        else:
            out[k] = v
    return out


def _unpack(result):
    if isinstance(result, tuple):
        return result[0], result[1]
    return result, 0


def audited_write(tool, scope="", require_confirm=True):
    """Wrap a DRF view method with the write rails.

    The wrapped method is called as `method(self, request, *args, confirmed=bool,
    **kwargs)` and must return a Response or `(Response, affected_count)`. When
    `confirmed` is False it MUST NOT write — return a preview of what *would*
    happen. With require_confirm=False the method is always called confirmed=True.
    """
    def decorator(view_method):
        @functools.wraps(view_method)
        def wrapper(self, request, *args, **kwargs):
            if scope:
                require_scopes(request, scope)  # raises PermissionDenied on miss

            key = get_key(request)
            key_id = key.pk if key else None
            user_id = request.user.id
            payload = request.data if isinstance(request.data, dict) else {}
            plan = {k: v for k, v in payload.items() if k != "confirm_token"}
            summary = _redact(plan)

            def _audit(outcome, affected=0, error=""):
                MCPAuditLog.objects.create(
                    key=key, user=request.user, tool=tool, scope=scope,
                    outcome=outcome, request_summary=summary,
                    affected_count=affected, error=error[:2000],
                )

            allowed, window = check_rate_limit(tool, key_id or user_id)
            if not allowed:
                _audit("denied", error="rate limited")
                limit, _ = RATE_LIMITS.get(tool, DEFAULT_RATE_LIMIT)
                return Response(
                    {"error": "Rate limit exceeded for this tool.",
                     "limit": limit, "window_seconds": window},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

            if require_confirm:
                confirmed = consume_confirm_token(payload.get("confirm_token"),
                                                  tool, user_id, plan)
                if not confirmed:
                    _audit("dry_run")
                    resp, _ = _unpack(view_method(self, request, *args, confirmed=False, **kwargs))
                    if resp.status_code < 400 and isinstance(resp.data, dict):
                        resp.data["dry_run"] = True
                        resp.data["confirm_token"] = issue_confirm_token(tool, user_id, plan)
                        resp.data["confirm_expires_in_seconds"] = CONFIRM_TOKEN_TTL_SECONDS
                        resp.data["next_step"] = (
                            "Re-send the identical request with this confirm_token to apply. "
                            "Single-use, valid only for this exact payload."
                        )
                    return resp

            _audit("attempt")
            try:
                result = view_method(self, request, *args, confirmed=True, **kwargs)
            except Exception as exc:  # noqa: BLE001 — record then re-raise
                _audit("error", error=str(exc))
                raise
            resp, affected = _unpack(result)
            _audit("success" if resp.status_code < 400 else "error",
                   affected=affected,
                   error="" if resp.status_code < 400 else str(getattr(resp, "data", ""))[:500])
            return resp
        return wrapper
    return decorator
