# Changelog

All notable changes to `openedx-mcp`. Format based on
[Keep a Changelog](https://keepachangelog.com/). Ulmo release line.

## [0.1.3]

### Added
- Unauthenticated `/api/mcp/health/` liveness endpoint (for container/k8s probes).
- Platform-free unit tests for the safety rails (`tests/test_rails.py`) and a
  `ruff` lint config; both wired into CI.

### Changed
- Extracted the pure rails (confirm-token, rate-limit, fingerprint, redact) into
  `api/mcp/_rails.py` so they are unit-testable without the Open edX platform.
- Anchored `build/`/`dist/` in `.gitignore` to the repo root.

## [0.1.2]

### Added
- 9-scope model: `read`, `write:enrollment`, `write:users`, `write:roles`,
  `grant:admin`, `write:certificates`, `write:reports`, `write:courses`,
  `destructive`. Rendered as a checkbox list in Django admin.
- Key-creation banner now prints copy-paste Claude connect steps; new
  `OPENEDX_MCP_PUBLIC_URL` setting supplies the endpoint.

### Changed
- `destructive` is now **additive** (domain scope **and** `destructive`).
- `set_role` escalation gate: course roles need `write:roles`;
  `global_staff`/`superuser` need `grant:admin`. Certificates and reports moved
  off `write:users` to their own scopes.

## [0.1.1]

### Added
- Certificates, async reports (grade export), account retirement,
  `reset_student_attempts`, `create_block_tree`. Key auto-expiry; real
  bulk-enroll audience preview.

[0.1.3]: https://github.com/blend-ed/openedx-mcp/releases/tag/v0.1.3
[0.1.2]: https://github.com/blend-ed/openedx-mcp/releases/tag/v0.1.2
[0.1.1]: https://github.com/blend-ed/openedx-mcp/releases/tag/v0.1.1
