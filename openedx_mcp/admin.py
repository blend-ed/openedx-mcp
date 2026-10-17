"""
Django admin for MCP keys — this IS the "console" for key creation.

No custom MFE, no GraphQL. An is_staff user goes to /admin/openedx_mcp/mcpkey/,
clicks Add, picks the acting user + scopes, and saves. The raw key is generated
server-side and surfaced ONCE on the connect page rendered as the save response
(it is never stored in the clear, so it cannot be shown again). Thereafter the
row shows only a prefix. The same page, reached via "Connect a client" on the
key list, lets an admin paste an existing key to build client snippets in the
browser.
"""
from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone

from .models import MCPAuditLog, MCPKey, Scope, generate_raw_key


def _mcp_url():
    """Public MCP endpoint, if the deployment set it (the Tutor plugin injects
    OPENEDX_MCP_PUBLIC_URL into LMS/CMS settings). Falls back to a placeholder."""
    return getattr(settings, "OPENEDX_MCP_PUBLIC_URL", "") or "https://mcp.<LMS_HOST>/mcp"


CONNECT_DOCS_URL = "https://docs.blend-ed.com/openedx-mcp/connect/"
CONNECT_TEMPLATE = "admin/openedx_mcp/mcpkey/connect.html"


class MCPKeyForm(forms.ModelForm):
    """Render the scopes JSONField as a checkbox list of every available scope,
    instead of a raw JSON textbox. Selected boxes are stored as a JSON array."""

    scopes = forms.MultipleChoiceField(
        choices=Scope.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Least-privilege subset for this key. Cannot exceed what the "
                  "acting user is already allowed. None selected = read only.",
    )

    class Meta:
        model = MCPKey
        fields = "__all__"


@admin.register(MCPKey)
class MCPKeyAdmin(admin.ModelAdmin):
    form = MCPKeyForm
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
            obj._raw_key = raw  # in-memory only, for response_add
        else:
            super().save_model(request, obj, form, change)

    def response_add(self, request, obj, post_url_continue=None):
        # Render the connect page directly as the POST response instead of
        # redirecting, so the raw key never has to be parked in the session.
        raw = getattr(obj, "_raw_key", None)
        if raw is None:
            return super().response_add(request, obj, post_url_continue)
        return self._render_connect(request, raw_key=raw, key_name=obj.name)

    def get_urls(self):
        info = self.opts.app_label, self.opts.model_name
        return [
            path("connect/", self.admin_site.admin_view(self.connect_view),
                 name="%s_%s_connect" % info),
        ] + super().get_urls()

    def connect_view(self, request):
        """Connect page without a fresh key: the admin pastes one client-side."""
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        return self._render_connect(request)

    def _render_connect(self, request, raw_key=None, key_name=None):
        context = {
            **self.admin_site.each_context(request),
            "opts": self.opts,
            "title": "Connect an MCP client",
            "mcp_url": _mcp_url(),
            "docs_url": CONNECT_DOCS_URL,
            "raw_key": raw_key,
            "key_name": key_name,
        }
        response = TemplateResponse(request, CONNECT_TEMPLATE, context)
        response["Cache-Control"] = "no-store"  # page may carry the raw key
        return response

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
