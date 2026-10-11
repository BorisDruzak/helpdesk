# Helpdesk ticket UI local verification — 2026-10-11

Initial local evidence was collected on `main`, based on
`b597583d893e325bb4cb67290839b971f64b51a0`.
Before publication the implementation was synchronized without conflicts with
`6948d45e73a31cd476f33ffe0a81b7512cd29231`. All 77 backend, 92 frontend and
16 browser checks below, build/typecheck, workspace verification and diff checks
passed again after that synchronization. Final independent review found no code blockers.
This evidence describes local source and browser fixtures, not a deployed release.

## Changes

- Shared ticket shell/header/sidebar: `webapp/src/app/layouts/app-shell.tsx`,
  `pages/tickets/list-page.tsx`, `styles.css`.
- Requester list/chat split: `pages/requester/tickets-page.tsx`,
  `ticket-chat-page.tsx`, `use-ticket-chat.ts`, `tickets-panels.tsx`, and router/lazy entrypoints.
- Russian quality text: `features/quality/{quality-dashboard,labels,api}.ts[x]`
  and the quality navigation description.
- SLA and bounded requester contacts: `server/web_api/support_handlers.py`,
  `dto/support.py`, `domain_ports/registry_contracts.py`, `registry_adapter/local.py`,
  and corresponding frontend API/model/mappers.
- Focused unit/browser regressions, `PLANS.md`, server CODEMAP and
  [behavior documentation](../HELPDESK_TICKET_UI.md).

## Executed checks

All shell commands below ran from the repository root, except pnpm commands,
which ran from `webapp`.

```powershell
python -m pytest server/tests/test_domain_ports.py server/tests/test_registry_http_adapter.py server/tests/test_registry_boundary.py server/tests/test_support_workspace_projection_no_db.py -q --tb=short
pnpm exec vitest run src/app/layouts/app-shell.test.tsx src/app/router.test.tsx src/pages/tickets/list-page.test.tsx src/pages/requester/tickets-page.test.tsx src/features/requester/live-refresh.test.tsx src/features/queues/support-workspace-mappers.test.ts src/features/quality/api.test.ts
$env:PC_CLIENT_WEBAPP_E2E_PORT='4175'
pnpm exec playwright test tests/support-workspace.spec.ts tests/ticket-ui.spec.ts tests/requester-workspace.spec.ts --grep 'operator|оператор|tickets workspace|shared tickets|quality dashboard|split routes|external operator|reply and confirmation|rating and reopen|waiting ticket|consent action'
pnpm build
python scripts/verify_workspace.py --workspace .
git diff --check
```

Results: 77 backend tests, 92 frontend tests, 16 browser scenarios passed;
typecheck/build, workspace verification and diff checks passed. The mapper
suite (20 tests) and quality browser scenario were also rerun after their final
small edits. Build retains the existing main-chunk size warning.

Browser coverage includes support shell/profile/completed SLA at 1366×768 and
1920×1080, dark/light switching at 1366/1440/1920, requester chat at 1366×768
and 390×844, separate list navigation, external updates, replies, consent,
confirmation, rating and reopening, and Russian quality labels with unchanged
mutation enum codes. Screenshots are in ignored `artifacts/ui/2026-10-11`.
New ticket/quality fixture scenarios and the latest MCP ticket check had no
browser console/page errors or failed requests. The older diagnostics fixture
explicitly expects its missing timeline/read endpoints to return 404.
The Windows fixture process logged connection-reset callbacks during page
teardown; all 16 browser assertions passed.

Independent read-only review found a device-owner contact fallback, corrected
with an explicit persisted-ticket-requester identity guard and a red/green
regression. Re-review found no remaining concrete issues. GitNexus impact
analysis covered the bounded profile projection and its adapters; source/tests
verified the boundary. Endpoint code/contracts and schema are unchanged.

## Open release checks

The DB-backed `server/tests/test_web_support_api.py` assertion was updated but
not executed: an isolated PostgreSQL test target was not validated in this run.
Production deployment, exact-SHA full CI, staging acceptance and the reviewed
production release gate have not run. Production files/services were not
changed for this implementation; the local fixture server was stopped after
verification. Unrelated scanner/Sonar and existing plan files were preserved.
