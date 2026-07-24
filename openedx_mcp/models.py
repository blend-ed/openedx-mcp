"""
Data models for openedx-mcp.

Two tables, both managed by Django migrations and administered from the standard
Django admin (no external console, no Hasura):

  * MCPKey     — a bearer credential an admin hands to an MCP client. The raw
                 secret is shown ONCE at creation and only its SHA-256 hash is
                 stored. Each key belongs to a User; a key is only ever valid
                 while that User is still is_staff or is_superuser (checked live
                 on every request, so demotion revokes access immediately).
  * MCPAuditLog — append-only record of every state-changing tool call.

Authorization model is deliberately simple: the platform's own is_staff /
is_superuser flags are the authority. `scopes` on a key only ever *narrows* what
that already-privileged user may do through a given key (least privilege per
credential); it can never grant anything the user does not already have.
"""
import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

KEY_PREFIX = "mcpk_"


def generate_raw_key():
    """A fresh opaque secret. Shown to the admin once; never stored in the clear."""
    return KEY_PREFIX + secrets.token_urlsafe(32)


def hash_key(raw):
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class Scope(models.TextChoices):
    READ = "read", "Read (analytics, listings, whoami)"
    WRITE_ENROLLMENT = "write:enrollment", "Write enrollment (enroll/unenroll)"
    WRITE_USERS = "write:users", "Write users (create/roles)"
    WRITE_COURSES = "write:courses", "Write courses (authoring, settings)"
    DESTRUCTIVE = "destructive", "Destructive (delete course, deactivate user)"


ALL_SCOPES = [c.value for c in Scope]
DEFAULT_SCOPES = [Scope.READ.value]


class MCPKey(models.Model):
    """A per-admin bearer credential for the MCP facade."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mcp_keys",
        help_text="The staff/superuser this key acts as. The key is only valid "
                  "while this user still has is_staff or is_superuser.",
    )
    name = models.CharField(max_length=255, help_text="Human label, e.g. 'Ops laptop'.")
    key_hash = models.CharField(max_length=64, unique=True, db_index=True, editable=False)
    key_prefix = models.CharField(
        max_length=16, editable=False,
        help_text="First few chars of the raw key, for identifying it in this list.",
    )
    scopes = models.JSONField(
        default=list,
        help_text="Subset of scopes this key may use. Cannot exceed what the "
                  "user is already allowed. Empty = read only.",
    )
    is_revoked = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "MCP key"
        verbose_name_plural = "MCP keys"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.key_prefix}…) for {self.user}"

    @property
    def is_expired(self):
        return self.expires_at is not None and self.expires_at <= timezone.now()

    @property
    def is_active(self):
        return not self.is_revoked and not self.is_expired

    def set_raw_key(self, raw):
        self.key_hash = hash_key(raw)
        self.key_prefix = raw[: len(KEY_PREFIX) + 4]

    def granted_scopes(self):
        return set(self.scopes or DEFAULT_SCOPES)


class MCPAuditLog(models.Model):
    """Append-only audit of state-changing tool calls. Never updated after write."""

    OUTCOMES = [
        ("dry_run", "dry_run"),
        ("attempt", "attempt"),
        ("success", "success"),
        ("denied", "denied"),
        ("error", "error"),
    ]

    key = models.ForeignKey(
        MCPKey, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
    )
    tool = models.CharField(max_length=128, db_index=True)
    scope = models.CharField(max_length=64, blank=True)
    outcome = models.CharField(max_length=16, choices=OUTCOMES, db_index=True)
    request_summary = models.JSONField(default=dict)
    affected_count = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "MCP audit log"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.tool} {self.outcome}"
