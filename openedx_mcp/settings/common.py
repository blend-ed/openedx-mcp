"""Common plugin settings, merged into LMS+CMS by the Open edX plugin loader."""


def plugin_settings(settings):
    # Default lifetime for newly minted MCP keys (days); None = no expiry.
    settings.OPENEDX_MCP_DEFAULT_KEY_TTL_DAYS = getattr(
        settings, "OPENEDX_MCP_DEFAULT_KEY_TTL_DAYS", 90)
