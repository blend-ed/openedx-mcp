# openedx-mcp

Open edX plugin (LMS + CMS) exposing staff/superuser admin operations as a REST
facade for an MCP server. Native `openedx-platform` APIs only; authorization is
`is_staff` / `is_superuser`. Ulmo.

Installs via the standard Open edX djangoapp entry points:

```
lms.djangoapp: openedx_mcp = openedx_mcp.apps:MCPLmsConfig   -> ^api/mcp/
cms.djangoapp: openedx_mcp = openedx_mcp.apps:MCPCmsConfig   -> ^api/mcp/cms/
```

- `models.py` — `MCPKey` (SHA-256 hashed bearer, per-user, scope-narrowed),
  `MCPAuditLog` (append-only).
- `admin.py` — mint/revoke keys from Django admin; raw key shown once.
- `api/mcp/auth.py` — `X-MCP-Key` auth + JWT/session, live staff/superuser gate.
- `api/mcp/guards.py` — rate limit + dry-run/confirm-token + audit for writes.
- `native/` — thin wrappers over native platform APIs (LMS + CMS).

See `../README.md` for the full architecture, tool catalog, and install steps.

Migrations: ships `0001_initial`. Run `tutor local do init` (or `manage.py
migrate openedx_mcp`) to create the tables.

## Create a key

Django admin → **Open edX Admin MCP → MCP keys → Add**. Pick the acting user
(must be `is_staff`/`is_superuser`), a name, tick the scopes, save. The raw key
is shown **once** in the success banner — copy it — along with ready-to-paste
connect steps (below). Revoke any time via the row action.

## Connect an AI client

The MCP server is streamable-http at `https://mcp.<LMS_HOST>/mcp` (the Tutor
plugin injects the exact URL into the admin banner via `OPENEDX_MCP_PUBLIC_URL`).
Authenticate with the raw key as a Bearer token.

**Claude Code (CLI):**

```bash
claude mcp add --transport http openedx https://mcp.<LMS_HOST>/mcp \
  --header "Authorization: Bearer <YOUR_MCP_KEY>"
```

**Claude Desktop** (`claude_desktop_config.json`) — needs the `mcp-remote`
bridge; put the header value in `env` because `mcp-remote` splits args on spaces:

```json
{
  "mcpServers": {
    "openedx": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://mcp.<LMS_HOST>/mcp",
               "--header", "Authorization:${AUTH}"],
      "env": { "AUTH": "Bearer <YOUR_MCP_KEY>" }
    }
  }
}
```

Config path: macOS `~/Library/Application Support/Claude/claude_desktop_config.json`,
Windows `%APPDATA%\Claude\claude_desktop_config.json`. Restart Desktop after edit.

First call the `whoami` tool — confirms identity + granted scopes.
