# openedx-mcp

[![PyPI](https://img.shields.io/pypi/v/openedx-mcp.svg)](https://pypi.org/project/openedx-mcp/)
[![CI](https://github.com/blend-ed/openedx-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/blend-ed/openedx-mcp/actions/workflows/ci.yml)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](LICENSE)

An Open edX plugin that exposes **staff / superuser admin operations** as a REST
facade for an MCP (Model Context Protocol) server — so an AI agent (Claude, etc.)
can run course, user, role, enrollment, certificate, report and authoring tasks
against your LMS.

Pure Open edX: every operation calls **native `openedx-platform` Python APIs**.
No Hasura, no external identity, no multi-tenant org model. Authorization is the
platform's own `is_staff` / `is_superuser`, re-checked live on every request. MCP
keys are Django models administered from the **standard Django admin**.

> **Release:** Ulmo. Pairs with
> [`tutor-contrib-openedxmcp`](https://pypi.org/project/tutor-contrib-openedxmcp/),
> which runs the MCP server and installs this app into the LMS/CMS.

## Install

Installs via the standard Open edX djangoapp plugin entry points — no core fork:

```
lms.djangoapp: openedx_mcp = openedx_mcp.apps:MCPLmsConfig   -> ^api/mcp/
cms.djangoapp: openedx_mcp = openedx_mcp.apps:MCPCmsConfig   -> ^api/mcp/cms/
```

Two mounts because course-authoring writes the **modulestore** (CMS-only) while
people/access/analytics run in the **LMS**. One app, one `MCPKey` table, shared.

With Tutor:

```bash
tutor config save --set OPENEDXMCP_PIP_REQUIREMENT=openedx-mcp
tutor images build openedx
tutor local launch
tutor local do init          # runs migrations -> creates MCPKey tables
```

Or plain pip into the openedx venv, then `manage.py migrate openedx_mcp`.

## Create a key

Django admin → **Open edX Admin MCP → MCP keys → Add**. Pick the acting user
(must be `is_staff`/`is_superuser`), a name, tick the scopes, save. The raw key is
shown **once** in the success banner — copy it — with ready-to-paste connect steps.
Revoke any time via the row action.

## Connect an AI client

Streamable-http at `https://mcp.<LMS_HOST>/mcp`; authenticate with the raw key as
a Bearer token.

**Claude Code (CLI):**

```bash
claude mcp add --transport http openedx https://mcp.<LMS_HOST>/mcp \
  --header "Authorization: Bearer <YOUR_MCP_KEY>"
```

**Claude Desktop** (`claude_desktop_config.json`) — needs the `mcp-remote` bridge;
put the header value in `env` (mcp-remote splits args on spaces):

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

First call the `whoami` tool — confirms identity + granted scopes.

## Security model

- **Authentication**: an `X-MCP-Key` (an `MCPKey` row) or the platform's own JWT
  bearer / session (an Open edX JWT already encodes `is_staff`/`is_superuser`).
- **Authorization**: one live gate — the acting user must be `is_staff` or
  `is_superuser` **right now**, re-checked every request. Demote them and every
  key they hold dies on the next call.
- **Scopes** only ever *narrow* per key (least privilege); a superuser bypasses
  narrowing. See the table below.
- **Write rails** (`guards.audited_write`): per-tool rate limit, dry-run/confirm-
  token handshake for high-blast-radius/destructive tools, and an append-only
  `MCPAuditLog` written before the mutation. `destructive` is **additive** — a
  destructive tool needs its domain scope **and** `destructive`.

> **Production:** the confirm-token store and rate-limit counter use the ambient
> Django cache — point it at a **shared backend (Redis/memcached)**. Under
> LocMemCache the limits multiply per worker and tokens are per-process.

### Scopes

| Scope | Gates |
|---|---|
| `read` | whoami, analytics, listings, roles, grades, cert/report status |
| `write:enrollment` | enroll, unenroll, bulk_enroll |
| `write:users` | create_user, reset_student_attempts |
| `write:roles` | set_role (course roles), instructor_access |
| `grant:admin` | set_role for `global_staff` / `superuser` (escalation) |
| `write:certificates` | generate / regenerate certificates |
| `write:reports` | submit async reports (grade export, …) |
| `write:courses` | block CRUD, create_block_tree, update_course_settings |
| `destructive` | **additive** — deactivate_user, request_retirement, invalidate_certificate, delete block |

## Tool catalog

| Tool | Process | Scope | Native API |
|---|---|---|---|
| `whoami` | LMS | read | request.user |
| `analytics_overview` | LMS | read | `CourseOverview` + `enrollment_counts` |
| `list_courses` / `course_detail` | LMS | read | `course_overviews` |
| `list_users` / `user_roles` / `course_team` | LMS | read | `auth.User`, `CourseAccessRole`, course roles |
| `user_grade` | LMS | read | `grades.api.CourseGradeFactory` |
| `enroll` / `unenroll` / `bulk_enroll` | LMS | write:enrollment | `enrollments.api`, `instructor.enrollment` |
| `create_user` | LMS | write:users | `student.helpers.do_create_account` |
| `reset_student_attempts` | LMS | write:users | `instructor.enrollment.reset_student_attempts` |
| `set_role` | LMS | write:roles / grant:admin | `student.roles`, `GlobalStaff` |
| `instructor_access` | LMS | write:roles | `instructor.access.allow/revoke_access` |
| `deactivate_user` | LMS | write:users + destructive | `User.is_active` |
| `generate_certificate` / `regenerate_certificates` | LMS | write:certificates | `certificates.api`, `instructor_task.api` |
| `invalidate_certificate` | LMS | write:certificates + destructive | `certificates.api.invalidate_certificate` |
| `list_course_certificates` / `user_certificates` | LMS | read | `GeneratedCertificate` |
| `submit_report` / `report_tasks` / `report_downloads` | LMS | write:reports / read | `instructor_task.api`, `ReportStore` |
| `retirement_status` / `request_retirement` | LMS | read / write:users + destructive | `UserRetirementStatus`, retirement utils |
| `read_course_outline` | CMS | read | `modulestore` + `create_xblock_info` |
| `create_block` / `create_block_tree` / `update_block` | CMS | write:courses | `xblock_storage_handlers` |
| `publish_block` / `delete_block` | CMS | write:courses (+destructive) | `modulestore().publish`, `_delete_item` |
| `update_course_settings` | CMS | write:courses | `CourseDetails` / `CourseGradingModel` / `CourseMetadata` |

## Layout

```
openedx_mcp/
├── models.py        # MCPKey, MCPAuditLog, Scope
├── admin.py         # key console (checkbox scopes, connect banner)
├── apps.py          # lms.djangoapp + cms.djangoapp configs
├── native/          # thin wrappers over native openedx APIs (LMS + CMS)
└── api/mcp/
    ├── auth.py      # X-MCP-Key + JWT/session, live is_staff/superuser gate
    ├── _rails.py    # pure rails: confirm-token, rate-limit, redact (unit-tested)
    ├── guards.py    # audited_write decorator (rails + audit)
    ├── views.py / tool_views.py / ops_views.py / authoring_views.py
    └── urls.py (LMS) / cms_urls.py (CMS)
```

## Config

| Setting | Default | Meaning |
|---|---|---|
| `OPENEDX_MCP_DEFAULT_KEY_TTL_DAYS` | `90` | Auto-expiry for new keys (blank expiry). `None` = no expiry. |
| `OPENEDX_MCP_PUBLIC_URL` | `""` | Public MCP endpoint shown in the admin connect banner (the Tutor plugin sets it). |

## Develop

```bash
pip install ruff pytest "django>=4.2,<5"
ruff check openedx_mcp tests
pytest            # platform-free unit tests (rails)
```

Native wrappers need a running platform (devstack) to exercise end-to-end.

See [CHANGELOG.md](CHANGELOG.md) · [CONTRIBUTING.md](CONTRIBUTING.md) ·
[TODO.md](TODO.md).
