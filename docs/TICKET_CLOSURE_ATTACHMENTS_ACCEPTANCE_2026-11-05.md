# Requester acceptance and ticket attachments — staging acceptance

Date: 2026-11-05. Branch: `codex/ui-support-001`.
Installed Helpdesk: `3865912ae94d8ccd720a8db27757e21681b2a643`.
Target: isolated staging `192.168.101.118`; production, Endpoint source/runtime
and the workstation agent were not changed. Staging remains running as requested.
Unrelated local changes remain unstaged. No push or production rollout performed.

## Result and causes

The active ordinary closure policy1.0.2 explicitly disabled requester acceptance.
Support also had a direct `resolved → closed` path without a confirmation guard.
Ordinary policy1.0.3 now requires requester acceptance and has no expiry-based
automatic closure. Support prepares the public result and leaves `resolved`;
the owner sees **Проверьте решение**, accepts to close, or returns it to work.
Staff/admin direct closure is rejected under the ticket lock. Optional rating
does not limit rejection of an outstanding acceptance.

An artifact's `device_id` was NOT NULL even for a legitimate browser ticket with
no linked computer. Migration154 permits ticket-bound NULL device artifacts,
with a CHECK requiring a ticket or device. Requester download identity now matches
the canonical identity used for upload. Scope checks remain enforced; errors no
longer expose SQL, bound parameters or internal paths.

## Verification

- Focused Python aggregate: **117 passed**. The attachment-only run was
  `python -m pytest server/tests/test_attachment_access_no_db.py server/tests/test_upload_handlers.py -q --tb=short`:
  **45 passed**. These counts overlap.
- Disposable PostgreSQL/HTTP attachment suite
  `python tmp/attachments-20261105/db_tests_corrected.py server/tests/test_ticket_attachment_upload_db.py`:
  **5 passed**. Covers requester/support upload without a device, file-only message,
  download, foreign-owner denial, wrong-ticket references, scope CHECK, legacy
  preservation, refused lossy downgrade and failure cleanup.
- Disposable owner acceptance/rejection API cases plus publication: **3 passed**.
  Subsequent publication plus legacy atomic opt-out API: **2 passed**.
  Latest publication fixture, including pending expiry/request preservation and
  explicit special-policy expiry: **1 passed**. Counts include repeated cases.
  Harness: `tmp/closure-confirmation-20261105/db_tests.py`.
- Frontend component run: **20 passed in4files**. `pnpm run build`,
  `python scripts/verify_workspace.py` and scoped `git diff --check` passed.
- Built-bundle browser fixture at1366px and390px: pending state is not closed;
  confirmation closes; rejection reopens the composer. No JavaScript errors or
  horizontal overflow. Playwright MCP transport was unavailable, so the fixture
  used the repository-pinned Playwright. Fixture results are separate from real
  PostgreSQL and installed-staging evidence.
- Independent final diff review found no remaining concrete blockers.

## Installed staging evidence

Two private verified backups were created: schema153 before release and schema154
before policy publication. Canonical committed-release installer built with a
frozen lockfile, installed the exact SHA and applied154. All30changed source/doc
hashes matched the committed archive. Strict TLS health returned200 for Helpdesk
and Endpoint; Helpdesk, Endpoint and its worker were active.

The audited registry published ordinary closure1.0.3. A fresh repeated apply was
idempotent. No resolved tickets needed reconciliation on this live snapshot.
All51previously closed ticket records and the special closure policy were unchanged
by publication. The2previously pending tickets retained their existing state.

Live browser acceptance:

- Opened the real T-000075 solution form: explicit employee-confirmation text,
  **Решить обращение**, no combined final-close action. Cancelled without submitting;
  the real ticket remains `in_progress`.
- Uploaded one generated, nonpersonal PNG to the existing synthetic own requester
  ticket T-000058, sent a file-only message and observed the file on the support
  side. Download succeeded; source/download SHA-256 matched
  `1b7f7c3e63a269a2e8addfa6dae2d8725ce80abdbbeddcd2c76ac1f2518b057e`.
  Persisted artifact has the correct ticket ID, original name and NULL device.
  Console errors:0 on both checked tabs.
- Controlled test side effect:1artifact and its file-only message on T-000058
  (2ticket events). No real-user message or status was submitted. Ticket/status
  counts were unchanged. Disposable test databases/roles and the known interrupted
  test resource were confirmed absent; local preview stopped.

Private evidence: `tmp/closure-confirmation-20261105/` and
`tmp/attachments-20261105/`. Screenshots: `upload-staging.png`,
`support-resolution-staging.png`, `requester-pending-desktop.png`,
`requester-reject-mobile.png`. The last2are synthetic browser fixtures.

## Limits and rollback

Already closed tickets were not reopened. Explicit special-policy opt-outs remain
configurable; ordinary requests require acceptance. Full CI was not requested or
run; this is focused staging acceptance. Existing Authlib deprecation warning
remains. Downgrade154 refuses while NULL-device attachments exist; preserve those
records/files and the compatible schema rather than delete data to force rollback.

Architecture/docs checked: canonical ticket workflow, requester identity and policy
runtime; `SUPPORT_WORKSPACE.md`, `ARTIFACTS_API.md`, `DATABASE.md`, server `CODEMAP.md`,
and live validation rules. No new route, dependency or cross-repository contract.

## Commits and included files

Implementation commits and exact file manifests follow.

`f65519dae504e1ed7cbae7d549a285e745ab3bd1` — fix(attachments): allow ticket uploads without a device

```text
server/app/db/migrations/versions/20261105_154_ticket_artifacts_optional_device.py
server/app/db/models.py
server/app/repos/artifacts_repo.py
server/app/services/artifact_service.py
server/docs/ARTIFACTS_API.md
server/docs/CODEMAP.md
server/docs/DATABASE.md
server/tests/test_attachment_access_no_db.py
server/tests/test_ticket_attachment_upload_db.py
server/uploads/handlers.py
```

`3865912ae94d8ccd720a8db27757e21681b2a643` — fix(tickets): require requester acceptance before ordinary closure

```text
PLANS.md
docs/SUPPORT_WORKSPACE.md
scripts/helpdesk_requester_confirmation.py
server/docs/CODEMAP.md
server/requester/ticket_handling.py
server/tests/test_phase1_completion_api.py
server/tests/test_phase1_completion_no_db.py
server/tests/test_requester_confirmation_publication_db.py
server/tests/test_requester_confirmation_publication_no_db.py
server/tests/test_requester_ticket_handling_no_db.py
server/tickets/requester_policy.py
server/tickets/workflow_service.py
server/web_api/dto/support.py
server/web_api/support_handlers.py
webapp/src/features/queues/api.ts
webapp/src/pages/requester/tickets-panels.test.tsx
webapp/src/pages/requester/tickets-panels.tsx
webapp/src/pages/tickets/components/simple-resolution-form.test.tsx
webapp/src/pages/tickets/components/simple-resolution-form.tsx
webapp/src/pages/tickets/components/simple-support-ticket.test.tsx
webapp/src/pages/tickets/components/simple-support-ticket.tsx
webapp/src/pages/tickets/list-page.tsx
```
