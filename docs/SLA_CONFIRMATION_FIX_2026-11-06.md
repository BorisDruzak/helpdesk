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

Exact runtime SHA, backup, browser results, SQL rollback proof and repaired-ticket
acceptance are appended after canonical staging installation. Private evidence:
`tmp/sla-confirmation-fix-20261106`; original diagnosis remains in
`tmp/t75-sla-audit-20261106`.

Freeze on top of `7b1d541d652c9e8975861f1479c642d755626cbc` with a private index and
own branch; preserve the shared checkout/index and previous requester/search fixes.
