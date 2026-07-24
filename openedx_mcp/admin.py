"""
Django admin for MCP keys — this IS the "console" for key creation.

No custom MFE, no GraphQL. An is_staff user goes to /admin/openedx_mcp/mcpkey/,
clicks Add, picks the acting user + scopes, and saves. The raw key is generated
server-side and surfaced ONCE via a success message (it is never stored in the
clear, so it cannot be shown again). Thereafter the row shows only a prefix.
"""
from datetime import timedelta

from django.conf import settings
from django.contrib import admin, messages
from django.utils import timezone

from .models import MCPAuditLog, MCPKey, generate_raw_key


@admin.register(MCPKey)
class MCPKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "key_prefix", "scopes", "is_revoked", "expires_at",
                    "last_used_at", "created_at")
    list_filter = ("is_revoked", "created_at")
    search_fields = ("name", "user__username", "user__email", "key_prefix")
    readonly_fields = ("key_prefix", "key_hash", "last_used_at", "created_at")
    actions = ["revoke_keys"]

    def get_fields(self, request, obj=None):
        if obj is None:  # add form
            return ("user", "name", "scopes", "expires_at")
        return ("user", "name", "scopes", "is_revoked", "expires_at",
                "key_prefix", "last_used_at", "created_at")

    def save_model(self, request, obj, form, change):
        if not change:  # creating: mint the secret now, show it once
            raw = generate_raw_key()
            obj.set_raw_key(raw)
            # Auto-set expiry from the configured default TTL when left blank.
            if obj.expires_at is None:
                ttl_days = getattr(settings, "OPENEDX_MCP_DEFAULT_KEY_TTL_DAYS", None)
                if ttl_days:
                    obj.expires_at = timezone.now() + timedelta(days=ttl_days)
            super().save_model(request, obj, form, change)
            messages.warning(
                request,
                "MCP key created. Copy it now — it will not be shown again:\n%s" % raw,
            )
        else:
            super().save_model(request, obj, form, change)

    @admin.action(description="Revoke selected keys")
    def revoke_keys(self, request, queryset):
        n = queryset.update(is_revoked=True)
        self.message_user(request, f"Revoked {n} key(s).", messages.SUCCESS)


@admin.register(MCPAuditLog)
class MCPAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "tool", "outcome", "user", "affected_count")
    list_filter = ("outcome", "tool", "created_at")
    search_fields = ("tool", "user__username", "error")
    readonly_fields = [f.name for f in MCPAuditLog._meta.fields]

    def has_add_permission(self, request):
        return False  # append-only, written by the facade

    def has_change_permission(self, request, obj=None):
        return False
