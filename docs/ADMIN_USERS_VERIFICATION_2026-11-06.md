# Unified Users — local verification, 2026-11-06

Subsequent authorized staging deployment and live acceptance are recorded in
[staging acceptance](ADMIN_USERS_STAGING_ACCEPTANCE_2026-11-06.md).

Implemented `/app/admin/users` and separate `/app/admin/registry`; old access
and people-related registry links redirect to Users. Profile/account/permissions
share a person card. Access writes are atomic, with scoped audit and ownership
guards. No migration, new dependency, real employee grant, commit, push or
deployment was performed. Existing unrelated dirty work was preserved.

## Passing checks

- `python scripts/bootstrap_web_toolchain.py`: Node24.15.0, pnpm10.33.0.
- `python scripts/run_with_local_postgres.py -- python -m pytest server/tests/test_user_account_provider.py server/tests/test_access_control.py server/tests/test_ui_users_repo.py server/tests/test_admin_users_auth.py server/tests/test_registry_people_admin.py server/tests/test_unified_queue.py server/tests/test_sso_oidc.py server/tests/test_ticket_approval_policy.py -q --tb=short`: **83 passed**.
- `python scripts/run_with_local_postgres.py -- python -m pytest server/tests/test_web_support_api.py -q --tb=short -k saved_view`: **3 passed**.
- `python -m pytest server/tests/test_unified_queue_no_db.py server/tests/test_support_work_no_db.py server/tests/test_ticket_assignment_capacity_no_db.py -q --tb=short`: **48 passed**.
- `pnpm --dir webapp test src/pages/admin/users-page.test.tsx src/pages/admin/users-registry-roundtrip.test.tsx src/pages/admin/registry-page.test.tsx src/features/admin/registry src/pages/admin/access-page.test.tsx src/app/navigation.test.ts src/components/shell/app-sidebar.test.tsx --maxWorkers=2`: **80 passed / 11 files**.
- `pnpm --dir webapp run build --outDir C:/Users/admin-2/CodexProjects/pc_client/artifacts/browser_checks/unified-users/dist`: **passed**, including TypeScript. Bundle kept isolated from other active tasks.
- `pnpm --dir webapp exec playwright test tests/unified-users.spec.ts --timeout 20000 --output C:/Users/admin-2/CodexProjects/pc_client/artifacts/browser_checks/unified-users/e2e-results`: **5 passed**. Child environment sets `PC_CLIENT_WEBAPP_E2E_DIST` to that bundle and `PC_CLIENT_WEBAPP_E2E_PORT=4187`.
- `python scripts/verify_workspace.py`: **passed** after provider changes.
- Scoped `git diff --check`: **passed**; Git emits existing LF/CRLF conversion notices.

## Browser evidence

Synthetic admin/person data at `/app/admin/users?person=test-marina` exercises
account creation, Support role, ServiceDesk L1 assignment, single atomic write,
reload/readback, failed-save draft preservation and legacy routing. Widths:
1366x768,1920x1080,390x844. Assertions check no horizontal document scrolling,
primary save visibility at desktop sizes, unexpected API requests and JavaScript/
console errors. The expected409 failure is recorded as the error-path fixture.
Screenshots were visually inspected. Fixture server4187 stopped automatically.

Saved desktop preview:
`artifacts/browser_checks/unified-users/e2e-results/unified-users-unified-pers-be1b2-s-support-and-queue-at-1366/users-permissions-saved.png`.

These browser responses are controlled fixtures, not deployed backend/DB proof.
Persistence/rollback, actual password/OIDC session projections, alias isolation
and duplicate-free operator/approver enumeration are verified separately with
disposable PostgreSQL. Live IdP and concurrent-request acceptance were not run.

## Full frontend suite limitations

This subsection records the original task checkpoint. The subsequent Git
publication verification fixes the stale requester-shell expectation and the
missing public-message permission in attachment fixtures; the final combined
checks are recorded in `HELPDESK_GIT_PUBLICATION_2026-11-06.md`.

`pnpm --dir webapp test --maxWorkers=2`: **1061 passed / 5 failed / 171 files**.
Two failures were old Access sidebar assertions; they were corrected and the
final focused suite (including all sidebar tests) passed.

Three failures outside the touched frontend surfaces remain. A narrow rerun
confirmed all three; they were not suppressed or rewritten:

- `router.test.tsx`: `renders the requester shell with Russian navigation for a single-workspace user` — expects `Пользователь`, current shell displays `Сотрудник`.
- `pages/tickets/list-page.test.tsx`: `ignores an old upload failure while the next ticket is still uploading` — disabled-state assertion.
- Same file: `uploads attachments and sends them from the composer` — upload mock is not called.

No all-suite-green or production-ready claim is made. No remote services were
started/stopped, and Marina's actual account/rights were not changed. GitNexus
tools were unavailable; committed/local architecture was checked with bounded
source and tests. Scoped backend/frontend reviews found no remaining concrete
task findings.
