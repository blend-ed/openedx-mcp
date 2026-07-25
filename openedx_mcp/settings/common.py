"""Common plugin settings, merged into LMS+CMS by the Open edX plugin loader."""


def plugin_settings(settings):
    # Default lifetime for newly minted MCP keys (days); None = no expiry.
    settings.OPENEDX_MCP_DEFAULT_KEY_TTL_DAYS = getattr(
        settings, "OPENEDX_MCP_DEFAULT_KEY_TTL_DAYS", 90)
    # Public MCP endpoint shown in the key-creation banner as copy-paste connect
    # steps. The Tutor plugin sets this to https://<OPENEDXMCP_ENDPOINT>/mcp;
    # empty falls back to a placeholder host in the admin.
    settings.OPENEDX_MCP_PUBLIC_URL = getattr(settings, "OPENEDX_MCP_PUBLIC_URL", "")
