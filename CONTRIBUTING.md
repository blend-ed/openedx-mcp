# Contributing to openedx-mcp

Thanks for helping! This app exposes Open edX staff/superuser operations to an MCP
server, using **only native `openedx-platform` APIs**.

## Ground rules

- **Native only.** New tools must call importable `openedx-platform` functions —
  no core fork, no vendored logic, no third-party stack. Note LMS vs CMS (course
  authoring runs in the CMS; it touches the modulestore).
- **Least privilege.** Every write goes through `guards.audited_write` with the
  right scope. Destructive/irreversible actions use `destructive=True` (additive)
  and the dry-run/confirm-token handshake.
- **Authz is `is_staff`/`is_superuser`, live.** Never cache privilege; scopes only
  narrow.

## Dev setup

```bash
pip install ruff pytest "django>=4.2,<5"
ruff check openedx_mcp tests
pytest                      # platform-free rails tests
```

End-to-end testing of `native/` wrappers needs a running devstack.

## Adding a tool

1. Add a native wrapper in `native/<domain>.py` (lazy platform imports).
2. Add a DRF view in the matching `api/mcp/*_views.py`, decorated with
   `audited_write(tool, scope=..., destructive=?, require_confirm=?)`.
3. Route it in `urls.py` (LMS) or `cms_urls.py` (CMS).
4. Add the MCP tool wrapper in the `tutor-contrib-openedxmcp` server package.
5. Update the README tool catalog + scope table and `CHANGELOG.md`.

## PRs

- Keep `ruff` and `pytest` green.
- One logical change per PR; update docs in the same PR.
- Conventional-commit style subjects (`feat:`, `fix:`, `docs:`…).

## Releasing

Bump the version (`setup.py` + `openedx_mcp/__init__.py`), update `CHANGELOG.md`,
tag `vX.Y.Z`, push — CI publishes to PyPI via trusted publishing.
