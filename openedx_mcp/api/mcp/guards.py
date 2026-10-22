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

The write runs in its own savepoint. The LMS sets ATOMIC_REQUESTS, so a re-raised
exception would roll back the whole request — audit rows included. Instead a
failed write rolls back only its savepoint, the error is audited, and the caller
gets a JSON error. Nothing half-written is committed.

The confirm-token store and rate-limit counter use the ambient Django cache. In
production that must be a shared backend (Redis/memcached); under LocMemCache
(dev) both are per-process.
"""
import functools
import logging

from django.db import transaction
from rest_framework import status
from rest_framework.response import Response

from ...models import MCPAuditLog, Scope
from ._rails import (
    CONFIRM_TOKEN_TTL_SECONDS,
    DEFAULT_RATE_LIMIT,
    RATE_LIMITS,
    check_rate_limit,
    consume_confirm_token,
    issue_confirm_token,
    redact,
)
from .auth import get_key, require_scopes
from .base import error_response

log = logging.getLogger(__name__)


def _redact(payload):
    return redact(payload)


def _unpack(result):
    if isinstance(result, tuple):
        return result[0], result[1]
    return result, 0


def _api_error(exc):
    """Render a DRF APIException here rather than re-raising it: DRF's handler
    marks the whole request for rollback, which would drop the audit rows."""
    detail = exc.detail if isinstance(exc.detail, dict) else {"error": exc.detail}
    return Response(detail, status=exc.status_code)


def audited_write(tool, scope="", destructive=False, require_confirm=True):
    """Wrap a DRF view method with the write rails.

    The wrapped method is called as `method(self, request, *args, confirmed=bool,
    **kwargs)` and must return a Response or `(Response, affected_count)`. When
    `confirmed` is False it MUST NOT write — return a preview of what *would*
    happen. With require_confirm=False the method is always called confirmed=True.
    """
    def decorator(view_method):
        @functools.wraps(view_method)
        def wrapper(self, request, *args, **kwargs):
            # `destructive` is ADDITIVE: a destructive tool needs its domain
            # scope AND the destructive scope, so a key cannot delete without
            # also holding the relevant write scope.
            needed = [s for s in (scope, Scope.DESTRUCTIVE.value if destructive else "") if s]
            if needed:
                require_scopes(request, *needed)  # raises PermissionDenied on miss

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

            def _run(confirmed):
                """Call the view in a savepoint. Returns (resp, affected, exc)."""
                try:
                    with transaction.atomic():
                        resp, affected = _unpack(view_method(
                            self, request, *args, confirmed=confirmed, **kwargs))
                        if resp.status_code >= 400:
                            # e.g. a bulk call that failed part-way: undo it all.
                            transaction.set_rollback(True)
                        return resp, affected, None
                except Exception as exc:  # noqa: BLE001 — savepoint already rolled back
                    return error_response(exc) or _api_error(exc), 0, exc

            if require_confirm:
                confirmed = consume_confirm_token(payload.get("confirm_token"),
                                                  tool, user_id, plan)
                if not confirmed:
                    _audit("dry_run")
                    resp, _, _ = _run(False)
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
            resp, affected, exc = _run(True)
            if exc is not None:
                _audit("error", error=f"{type(exc).__name__}: {exc}")
                return resp
            _audit("success" if resp.status_code < 400 else "error",
                   affected=affected,
                   error="" if resp.status_code < 400 else str(getattr(resp, "data", ""))[:500])
            return resp
        return wrapper
    return decorator
