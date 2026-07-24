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
