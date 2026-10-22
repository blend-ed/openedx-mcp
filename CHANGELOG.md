# Changelog

All notable changes to `openedx-mcp`. Format based on
[Keep a Changelog](https://keepachangelog.com/). Ulmo release line.

## [0.1.8]

### Fixed
- `courses/<course_id>/team/` always returned 500: the greedy `<path:course_id>`
  in the course-detail route swallowed `.../team`. The team route is now
  registered first.
- `users/<username>/roles/` returned 500 for any user with course roles
  (`CourseLocator` is not JSON serializable). `course_id` is now a string.
- The CMS course outline returned only the course root: `create_xblock_info`
  defaults `include_children_predicate` to `NEVER`. It now walks the whole tree
  and returns a compact projection per block (id, display_name, category,
  published, has_changes, visibility_state, graded, format, start, due,
  children) instead of Studio's full ~40-key xblock info.

## [0.1.7]

### Changed
- Redesigned the scope picker on the MCP key form. Scopes are now full-width
  rows grouped as Read / Write / Elevated, each showing a short name, the scope
  code and what it allows on one line. Grant admin is flagged "highest" and
  Destructive "add-on". Added Read only / All / Clear presets. Stored values
  are unchanged, so existing keys need no migration.

## [0.1.6]

### Changed
- Minting a key in the admin now opens a **Connect a client** page instead of a
  single flattened warning banner: the key with its own copy button, then
  tabbed snippets for Claude Code, Claude Desktop, Cursor and VS Code, each
  with a copy button. The page is the response to the save (not a redirect),
  so the raw key is still never stored anywhere.
- The same page is linked from the MCP key list. There, the admin pastes an
  existing key and the snippets are built in the browser; the key is never sent
  to the server.
- Added `MANIFEST.in` so the admin templates ship in the sdist.

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
