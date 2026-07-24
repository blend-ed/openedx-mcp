def plugin_settings(settings):
    settings.OPENEDX_MCP_DEFAULT_KEY_TTL_DAYS = settings.ENV_TOKENS.get(
        "OPENEDX_MCP_DEFAULT_KEY_TTL_DAYS",
        getattr(settings, "OPENEDX_MCP_DEFAULT_KEY_TTL_DAYS", 90),
    )
