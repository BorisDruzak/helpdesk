# Preserve resolution SLA through requester confirmation — 2026-11-06

User-authorized staging fix of T-000075's false overdue indication. Investigation:
support stopped resolution SLA at 05 November 17:42 Asia/Yekaterinburg, before the
18:47 deadline, but confirmation at 06 November 09:56 replaced `resolution_at`
with `closed_at`. The requester projection correctly compared the wrong timestamp.

## Change and safeguards

`server/tickets/workflow_service.py` now preserves an existing `resolution_at`
when closing. `closed_at` still records closure/acceptance. If no SLA stop exists,
close-time fallback remains; no fallback to `resolved_at` is introduced because
a policy can intentionally stop SLA only on close. Reopen clears previous-cycle
timestamps. Genuine late solutions remain late. Auth, workflow gates, policies,
pause behavior and API fields are unchanged.

`scripts/helpdesk_repair_t75_sla.py` is an imported maintenance callable, not an
automatic startup migration or bulk command. It requires trusted admin context,
the exact diagnosed ticket and isolated staging DB. It verifies one start/stop/
resolved/confirmed-close cycle, unchanged due date, no pauses/reopens/breach and
an existing confirmed closure. A fresh full-input fingerprint is checked under
the canonical ticket row lock. Canonical repository update plus one internal audit
event share a transaction. The source stop timestamp is restored without changing
acceptance, rating, deadline, policy or old history; repeated apply is a no-op.

Run only via the approved protected staging transport: assert test-helpdesk and
the installed exact candidate, load staging environment in memory, create SYSTEM
admin AuthContext, call `repair(..., apply=False)`, inspect its fingerprint, take a
verified backup, then call `repair(..., apply=True, expected_fingerprint=...)`.
Never print environment/auth values. A stale fingerprint requires a fresh plan.

## Checks and acceptance

- Workflow/handling/atomicity/concurrency and maintenance-helper focused tests:
  51 passed; new late-confirmation regression observed failing before the fix.
- Helper cases cover identity/history guards, dry-plan no writes, stale/wrong-DB
  rejection, audit failure rollback, preservation of acceptance/rating and
  idempotence (transaction tests use mocks; live PostgreSQL evidence is separate).
- Workspace verification passed. Browser spec uses the real Python timestamp
  builder and requester timer after confirmation and checks absence of a false
  warning, retained decision controls/rejection flow and responsive overflow.
- GitNexus class impact shows requester/support/public/quality/auto-close callers
  of the shared workflow service. Dynamic timestamp builder and canonical SLA
  stop sequencing were verified in source. No Endpoint HTTP contract is affected.
- CODEMAP documents timestamp ownership and the explicit repair helper. No schema
  or dependency change. Full CI and production deployment are outside this task.

## Staging result

Installed `b765fd6362686a28209e2aa92839363f961f21bd` —
`fix(sla): preserve resolution time through requester confirmation` (8 files:
workflow helper/tests, maintenance helper/tests, browser spec, CODEMAP, this report
and PLANS). Branch `codex/sla-confirmation-fix`. Canonical immutable installer built
the exact Git archive and frozen-lockfile frontend bundle. All 5 source/test hashes
match committed files. Schema remains 155; no migration was introduced.

Verified backup before code: `db5452a31062ff793fb526f4c8386f6c7228a1a354801d4039d783906a8629b5`.
Fresh backup before data repair: `6a0c4b395151383a6b56631fb71e5ee19281ccc805a670edb92ab281608067d4`.

The real PostgreSQL failure check flushed the UPDATE, forced a missing audit
result, and verified a complete rollback: ticket, all prior events, feedback and
other tickets matched their pre-transaction hashes. It did not leave test records.
Dry-plan fingerprint was checked again under the ticket lock during the real apply.

T-000075 `resolution_at` now equals the verified SLA stop event 18122:
`2026-11-05T12:42:15.591013Z` (17:42 local). Resolution deadline remains
`2026-11-05T13:47:18.658097Z` (18:47 local), and requester projection reports
`status=completed`, `completed_within_target=true`. Closure remains
`2026-11-06T04:56:15.735511Z`; status closed, confirmation pending=false / confirm.
All protected ticket columns, 75 other ticket rows, 5 feedback rows and 21 old
ticket events are unchanged. One internal repair audit was appended. Fresh-plan
repeat apply was a no-op, including no updated_at or extra audit changes.

Counts before/after repair: 76 tickets, 6 artifacts, 160 users and 44 people remain;
events 18424→18425 (the repair audit). Strict hostname/CA health returns HTTP 200
for Helpdesk and Endpoint, and all three staging services are active. No production
deployment or mass historical repair was performed.

Browser regression passed 3/3 at 1366x768, 1920x1080 and 390x844. It feeds actual
Python workflow/projection output into the fixture after confirmation and verifies
completion at the original resolution time without the false warning. A runner
import-path failure was corrected before the successful run. Live support browser
inspection of T-000075 shows closed and SLA «Завершено» with no warning/error
console entries; no requester decision was submitted. The employee's requester
session was not impersonated; its exact timer is verified through stored state
and the requester projection plus browser fixture. A full-page screenshot API was
unavailable; a native viewport screenshot succeeded (`live-t75-sla.jpg`).

Checks: `python -m pytest scripts/test_helpdesk_repair_t75_sla.py server/tests/test_workflow_update_builder_no_db.py server/tests/test_requester_ticket_handling_no_db.py server/tests/test_workflow_atomicity_no_db.py server/tests/test_workflow_concurrency_no_db.py -q` (51 passed);
`python scripts/verify_workspace.py` (passed);
`PC_CLIENT_WEBAPP_E2E_PORT=4189 pnpm --dir webapp test:e2e tests/requester-resolution-actions.spec.ts --output=../tmp/sla-confirmation-fix-20261106/browser-green` (3 passed);
private-index diff check (passed). Existing Authlib deprecation and fixture chunk
warnings remain. Independent backend/repair/browser/docs review has no findings.
Full CI/full DB suite are outside the targeted staging scope; genuine late and
close-only-policy behavior have regression coverage. Staging remains active.

Private evidence: `tmp/sla-confirmation-fix-20261106` (`installed.json`, code/data
backup receipts, `repair-rollback.json`, `repair-plan.json`, `repair-apply.json`,
deploy log, browser screenshots). Original diagnosis remains in
`tmp/t75-sla-audit-20261106`.

Freeze on top of `7b1d541d652c9e8975861f1479c642d755626cbc` with a private index and
own branch; preserve the shared checkout/index and previous requester/search fixes.
