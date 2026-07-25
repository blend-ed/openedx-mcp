"""DB-backed tests for the MCPKey / MCPAuditLog models."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from openedx_mcp.models import (
    KEY_PREFIX,
    MCPAuditLog,
    MCPKey,
    Scope,
    generate_raw_key,
    hash_key,
)

User = get_user_model()


def test_generate_raw_key_shape():
    raw = generate_raw_key()
    assert raw.startswith(KEY_PREFIX)
    assert len(raw) > len(KEY_PREFIX) + 20
    # unique each time
    assert generate_raw_key() != generate_raw_key()


def test_hash_is_stable_and_not_reversible():
    raw = generate_raw_key()
    assert hash_key(raw) == hash_key(raw)
    assert raw not in hash_key(raw)
    assert len(hash_key(raw)) == 64  # sha256 hex


@pytest.mark.django_db
def test_set_raw_key_stores_hash_and_prefix():
    user = User.objects.create(username="admin", is_staff=True)
    raw = generate_raw_key()
    key = MCPKey(user=user, name="laptop")
    key.set_raw_key(raw)
    key.save()

    assert key.key_hash == hash_key(raw)
    assert key.key_prefix == raw[: len(KEY_PREFIX) + 4]
    # the raw secret is never persisted
    assert raw not in key.key_hash


@pytest.mark.django_db
def test_expiry_and_active_flags():
    user = User.objects.create(username="u", is_staff=True)
    key = MCPKey(user=user, name="k")
    key.set_raw_key(generate_raw_key())
    key.expires_at = timezone.now() - timedelta(minutes=1)
    key.save()
    assert key.is_expired is True
    assert key.is_active is False

    key.expires_at = timezone.now() + timedelta(days=1)
    assert key.is_expired is False
    assert key.is_active is True

    key.is_revoked = True
    assert key.is_active is False


@pytest.mark.django_db
def test_granted_scopes_defaults_to_read():
    user = User.objects.create(username="u2", is_staff=True)
    key = MCPKey(user=user, name="k", scopes=[])
    key.set_raw_key(generate_raw_key())
    key.save()
    assert key.granted_scopes() == {Scope.READ.value}

    key.scopes = [Scope.WRITE_ENROLLMENT.value, Scope.READ.value]
    assert key.granted_scopes() == {"write:enrollment", "read"}


@pytest.mark.django_db
def test_audit_log_row():
    user = User.objects.create(username="u3", is_staff=True)
    row = MCPAuditLog.objects.create(
        user=user, tool="enroll_user", scope="write:enrollment",
        outcome="success", request_summary={"course_id": "c"}, affected_count=1,
    )
    assert row.pk is not None
    assert str(row).endswith("enroll_user success")
