# TODO

Backlog for `openedx-mcp` + `tutor-contrib-openedxmcp`. Held deliberately —
picked up on request.

## Feature tools (native APIs exist; not yet wired)

- [ ] **Cohorts** — list/create cohorts, assign learners
  (`openedx.core.djangoapps.course_groups`, instructor `AddUsersToCohorts`).
- [ ] **Course teams** — richer than instructor/staff; CMS `course_team_handler`.
- [ ] **Content libraries** — v2 library authoring / downstream links
  (`contentstore.rest_api.v2` downstreams).
- [ ] **Enable certificates for a course** — certificate configuration/activation.
- [ ] **Resend activation email / password reset** — `user_api` account flows.
- [ ] **Discussion / forum admin** — forum roles, cohorted discussions.
- [ ] **Enrollment-date / visibility quick toggles** — course schedule shortcuts.
- [ ] **Bulk course-team import** — CSV-style grant of staff across courses.
- [ ] **Grade override** — `grades.api.override_subsection_grade`.

## Hardening / ops

- [ ] Integration tests against a devstack (native wrappers, end-to-end).
- [ ] Metrics/observability on the MCP server (request counts, tool latency).
- [ ] Per-key audit view/export in Django admin (filter by key/tool/outcome).
- [ ] Optional per-scope rate-limit overrides via settings.

## Compatibility

- [ ] Track the next Open edX named release; add a compat matrix once >1 supported.
