"""Tests for MCP key authentication + the live staff/superuser + scope gates."""
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import exceptions
from rest_framework.test import APIRequestFactory

from openedx_mcp.api.mcp.auth import (
    IsStaffOrSuperuser,
    MCPKeyAuthentication,
    granted_scopes,
    require_scopes,
)
from openedx_mcp.models import MCPKey, Scope, generate_raw_key

User = get_user_model()
factory = APIRequestFactory()


def _make_key(user, raw, **kw):
    key = MCPKey(user=user, name=kw.pop("name", "k"), scopes=kw.pop("scopes", []), **kw)
    key.set_raw_key(raw)
    key.save()
    return key


def _request_with_key(raw):
    # RequestFactory maps HTTP_X_MCP_KEY -> request.headers['X-MCP-Key'] (case-insensitive)
    return factory.get("/", HTTP_X_MCP_KEY=raw)


@pytest.mark.django_db
def test_authenticate_valid_key_returns_user_and_key():
    user = User.objects.create(username="a", is_staff=True)
    raw = generate_raw_key()
    key = _make_key(user, raw)
    got_user, got_key = MCPKeyAuthentication().authenticate(_request_with_key(raw))
    assert got_user == user
    assert got_key.pk == key.pk


@pytest.mark.django_db
def test_authenticate_absent_key_returns_none():
    assert MCPKeyAuthentication().authenticate(factory.get("/")) is None


@pytest.mark.django_db
def test_authenticate_invalid_revoked_expired():
    user = User.objects.create(username="b", is_staff=True)

    with pytest.raises(exceptions.AuthenticationFailed):
        MCPKeyAuthentication().authenticate(_request_with_key("mcpk_nope"))

    raw_r = generate_raw_key()
    _make_key(user, raw_r, is_revoked=True)
    with pytest.raises(exceptions.AuthenticationFailed):
        MCPKeyAuthentication().authenticate(_request_with_key(raw_r))

    raw_e = generate_raw_key()
    _make_key(user, raw_e, expires_at=timezone.now() - timedelta(minutes=1))
    with pytest.raises(exceptions.AuthenticationFailed):
        MCPKeyAuthentication().authenticate(_request_with_key(raw_e))


@pytest.mark.django_db
def test_is_staff_or_superuser_permission():
    perm = IsStaffOrSuperuser()
    staff = User.objects.create(username="s", is_staff=True)
    plain = User.objects.create(username="p")
    assert perm.has_permission(SimpleNamespace(user=staff), None) is True
    assert perm.has_permission(SimpleNamespace(user=plain), None) is False


@pytest.mark.django_db
def test_scopes_narrow_for_key_but_not_superuser():
    user = User.objects.create(username="c", is_staff=True)
    key = _make_key(user, generate_raw_key(), scopes=[Scope.READ.value])
    req = SimpleNamespace(user=user, auth=key)

    assert granted_scopes(req) == {Scope.READ.value}
    require_scopes(req, Scope.READ.value)  # allowed
    with pytest.raises(exceptions.PermissionDenied):
        require_scopes(req, Scope.WRITE_ENROLLMENT.value)  # missing


@pytest.mark.django_db
def test_superuser_bypasses_scope_narrowing():
    su = User.objects.create(username="root", is_staff=True, is_superuser=True)
    key = _make_key(su, generate_raw_key(), scopes=[Scope.READ.value])
    req = SimpleNamespace(user=su, auth=key)
    # superuser may use any scope regardless of the key's set
    require_scopes(req, Scope.DESTRUCTIVE.value)


@pytest.mark.django_db
def test_jwt_or_session_request_has_all_scopes():
    """No key on the request (auth is None) -> full scope set."""
    from openedx_mcp.models import ALL_SCOPES
    req = SimpleNamespace(user=User.objects.create(username="j", is_staff=True), auth=None)
    assert granted_scopes(req) == set(ALL_SCOPES)
