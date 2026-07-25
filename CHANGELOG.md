# Changelog

All notable changes to `openedx-mcp`. Format based on
[Keep a Changelog](https://keepachangelog.com/). Ulmo release line.

## [0.1.5]

### Added
- Open edX cookiecutter-style test scaffold: `test_settings.py` (sqlite),
  `Makefile`, `tox.ini`, `requirements/`. Runs standalone — no platform boot.
- DB-backed tests for models (key hashing/expiry/scopes, audit log) and for MCP
  key authentication + the live staff/superuser gate + scope narrowing. CI now
  runs a py3.11/3.12 matrix.

### Changed
- Guard the Open edX plugin imports in `apps.py` (`HAS_OPENEDX`) so the app loads
  under a plain Django test settings module. Dropped the deprecated
  `default_app_config`.

## [0.1.4]

### Fixed
- `bulk_enroll` crashed on the confirmed write with
  `too many values to unpack (expected 2)` — Ulmo's
  `instructor.enrollment.enroll_email` returns a 3-tuple
  `(previous_state, after_state, enrollment_obj)`, not two. Now indexed
  arity-tolerantly. The dry-run was unaffected (different code path), so the
  error only surfaced on confirm. Row results also now include `allowed` (the
  pending-invite state for unregistered addresses).

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

[0.1.5]: https://github.com/blend-ed/openedx-mcp/releases/tag/v0.1.5
[0.1.4]: https://github.com/blend-ed/openedx-mcp/releases/tag/v0.1.4
[0.1.3]: https://github.com/blend-ed/openedx-mcp/releases/tag/v0.1.3
[0.1.2]: https://github.com/blend-ed/openedx-mcp/releases/tag/v0.1.2
[0.1.1]: https://github.com/blend-ed/openedx-mcp/releases/tag/v0.1.1
