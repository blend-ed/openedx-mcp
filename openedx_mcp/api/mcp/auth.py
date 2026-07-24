"""
Authentication + authorization for the MCP facade.

Two accepted credentials, in priority order:

  1. X-MCP-Key  — an openedx_mcp.MCPKey bearer token (the primary path; keys are
     minted from the Django admin). Resolves to the key's acting user.
  2. The host platform's own JwtAuthentication / SessionAuthentication — so the
     same endpoints can also be driven directly with an Open edX JWT that already
     carries is_staff/is_superuser (oauth_dispatch encodes both claims). This is
     what the key-management endpoints themselves use.

Whichever path authenticates, the authorization rule is identical and re-checked
LIVE on every request: the acting user must be is_staff or is_superuser right now.
A key does not cache privilege — demote the user and every key they hold dies on
the next call. `scopes` on a key only narrow, never widen.
"""
import logging

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import authentication, exceptions, permissions

from ...models import MCPKey, hash_key

log = logging.getLogger(__name__)
User = get_user_model()

MCP_KEY_HEADER = "X-MCP-Key"


class MCPKeyAuthentication(authentication.BaseAuthentication):
    """Authenticate by X-MCP-Key. Returns None (not an error) when absent, so it
    composes with JWT/Session authenticators on the same view."""

    def authenticate(self, request):
        raw = request.headers.get(MCP_KEY_HEADER)
        if not raw:
            return None

        key = MCPKey.objects.filter(key_hash=hash_key(raw)).select_related("user").first()
        if key is None:
            raise exceptions.AuthenticationFailed("Invalid MCP key.")
        if key.is_revoked:
            raise exceptions.AuthenticationFailed("This MCP key has been revoked.")
        if key.is_expired:
            raise exceptions.AuthenticationFailed("This MCP key has expired.")

        # Best-effort last-used telemetry; never blocks the request.
        MCPKey.objects.filter(pk=key.pk).update(last_used_at=timezone.now())
        return (key.user, key)

    def authenticate_header(self, request):
        return MCP_KEY_HEADER


def get_key(request):
    """The MCPKey backing this request, or None when authed by JWT/session."""
    auth = getattr(request, "auth", None)
    return auth if isinstance(auth, MCPKey) else None


def granted_scopes(request):
    """Scopes available on this request. A JWT/session admin (no key) has all
    scopes; a key is limited to its own granted set."""
    key = get_key(request)
    if key is None:
        from ...models import ALL_SCOPES
        return set(ALL_SCOPES)
    return key.granted_scopes()


class IsStaffOrSuperuser(permissions.BasePermission):
    """Live authority check — the acting user must currently be staff/superuser.
    This is the single gate; it runs on every request regardless of credential."""

    message = "This endpoint requires a staff or superuser account."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


def require_scopes(request, *needed):
    """Raise PermissionDenied unless the request's credential carries every scope.
    Superuser bypasses scope narrowing entirely."""
    if request.user.is_superuser:
        return
    have = granted_scopes(request)
    missing = set(needed) - have
    if missing:
        raise exceptions.PermissionDenied(
            {"error": "Missing scope(s).", "required": sorted(needed),
             "missing": sorted(missing)}
        )
