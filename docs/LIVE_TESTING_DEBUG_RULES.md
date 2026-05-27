# Live Testing and Debug Rules

These rules are mandatory for all Live validation, debugging and bug fixing work on this project.

They extend the general testing rules in `docs/TESTING_RULES.md`. When a task involves a live server, local agent, browser/admin UI, Protocol V3, account sessions, operation lifecycle, module runtime, deployment/runtime control or production-like debugging, this document is the canonical process contract.

## 0. Scope discipline

Do not mix validation modes.

Every finding must explicitly state which path was tested:

- real browser UI;
- real local agent GUI via pywinauto/UIA;
- local GUI automation bridge `/ui/automation/run`;
- direct HTTP/API;
- raw WebSocket probe;
- server DB query;
- agent SQLite query;
- unit/integration test only.

A scenario is not passed unless the required canonical path passes. A bridge/helper path may support evidence, but it cannot replace the canonical path unless the plan explicitly says so.

Examples:

- Browser support workflow must be verified in the real browser, not only via direct HTTP.
- Agent-facing GUI workflow must be verified through pywinauto/UIA when the plan requires GUI evidence.
- `/ui/automation/run` is not automatically equivalent to GUI until the same account/session/context behavior is verified.
- Raw WS probe is not equivalent to a full agent and must not receive live pending commands unless this is part of the test.

## 1. Evidence before fix

Do not fix a bug before recording the failure.

For every bug, first write or update the bug entry with:

- exact scenario;
- expected behavior;
- actual behavior;
- reproducible steps;
- server log evidence;
- agent log evidence;
- server DB evidence;
- agent SQLite evidence;
- browser/UI evidence when applicable;
- WS/API payload evidence when applicable;
- whether old pre-fix contamination may affect this result.

Only then start root-cause analysis and patching.

## 2. A fix is not a restart

Recovery is not a fix.

If a service is restarted, a queue is cleared, an agent is relaunched, or stale data is manually removed, record it as recovery only.

A bug can be marked fixed only when one of these is true:

- root cause was fixed in code/config;
- root cause was proven external/non-product and guardrails were added;
- root cause was proven test-tool-only and the test tool was corrected;
- root cause is intentionally accepted, documented, and no longer blocks the current milestone.

Allowed statuses:

- `open`
- `reproduced`
- `root-cause-confirmed`
- `fix-in-progress`
- `verified-fixed`
- `verified-non-product / guardrails-added`
- `known-limitation`
- `deferred`
- `not-a-bug`
- `needs-clean-rerun`

Do not use `fixed` without verification evidence.

## 3. Root cause must be isolated by layer

Every bug must be classified into one primary layer and optional secondary layers:

- protocol contract;
- transport/proxy;
- auth/account-session;
- server DB/transaction;
- agent SQLite/idempotency;
- operation lifecycle;
- UI projection;
- local GUI/UIA;
- automation bridge;
- module runtime;
- deployment/systemd/runtime-control;
- test contamination;
- documentation drift.

For ambiguous failures, isolate the layer before patching.

Examples:

- If WSS close code is wrong, test direct backend WS before changing server protocol code.
- If GUI automation fails, distinguish Qt/UIA accessibility from API/account-session behavior.
- If DB state is wrong after cancel, distinguish target operation, cancel operation, device_outbox and agent seen_commands.
- If browser shows stale state, compare DB, API response and DOM/browser UI separately.

## 4. No single-signal pass

Never mark a Live scenario passed from one successful signal.

For P0/P1 Live scenarios, check at least:

- transport/API response;
- server DB;
- agent local state when agent is involved;
- browser/UI state when visible to operators/requesters;
- logs/action trace.

A scenario can pass with a missing layer only if the layer is explicitly not applicable and the reason is written.

Example:

Protocol-negative invalid handshake may not need browser evidence, but it must state why browser is not applicable and confirm no phantom device/state was created.

## 5. Browser evidence is mandatory for UI-visible flows

If a result is visible to support/admin/requester, verify it in a real browser.

Required browser evidence:

- URL;
- visible status/text/result;
- screenshot or DOM-visible output;
- any browser console/network error relevant to the scenario.

Do not replace browser confirmation with DB/API success.

## 6. pywinauto/UIA evidence is mandatory for local GUI flows

For local Windows agent GUI scenarios:

- use `pywinauto==0.6.9`;
- use `Application(backend="uia")`;
- prefer stable selectors: AutomationId/objectName/accessibleName/control type;
- do not rely on coordinates as pass criteria;
- if using clipboard paste for Unicode, verify the value after paste;
- dump bounded control tree excerpts on failure;
- set timeouts for child traversal to avoid hangs;
- record window title, process id and control evidence.

A GUI scenario is not green if it passed only through `/ui/automation/run`.

## 7. Automation bridge is a test surface, not the product UI

The local automation bridge must be validated separately.

If `/ui/automation/run` fails, determine whether:

- product GUI is broken;
- automation bridge is missing context;
- server API denies correctly;
- account-session propagation is missing;
- the test sent unsupported payload.

Do not call a GUI feature broken just because automation bridge failed. Conversely, do not call a GUI feature fixed just because automation bridge passed.

## 8. Account-session boundary rule

Any agent/requester ticket action must explicitly verify account-session behavior.

For ticket create/message/tool/attachment/close/read/detail/list flows, record:

- account_session_id;
- account mode;
- person/binding if applicable;
- whether headers/body/query carried account session;
- server DB requester/account fields;
- cross-account denial if relevant.

If a route requires account-session and the test uses only agent token, the expected result is denial, not failure.

## 9. ACK requires persistence or documented no-op

For Protocol V3 outbox ingest:

- ACK is allowed only if the item was persisted, was a proven duplicate, or is an explicitly documented no-op.
- Unknown item types must NACK unless documented otherwise.
- Malformed event context must NACK.
- ACK-without-persistence is a data-integrity bug unless explicitly allowed by protocol docs.

For every ACK/NACK test, record:

- outbox_id;
- seq field;
- trace_id;
- event type;
- server DB row or duplicate proof;
- agent outbox state.

## 10. Clean-run IDs are mandatory after fixes

After any protocol/data-integrity fix, rerun with a new `run_id`, new marker and preferably a new ticket.

Do not use old contaminated rows as post-fix evidence.

Every probe/test payload should include a unique marker such as:

- `probe_run_id`;
- `live_run_id`;
- `test_marker`;
- timestamp/commit prefix.

When querying DB/browser, filter by that marker.

## 11. Pre-fix contamination must be labeled

If old bad rows remain by design, list them in `PLANS.md` as pre-fix contamination.

For each contaminated artifact, record:

- ticket_id/code;
- operation_id;
- device_outbox id;
- local outbox id;
- event id;
- why it is pre-fix;
- how future tests should filter it out.

Do not delete contamination unless the plan explicitly requires cleanup and cleanup is itself verified.

## 12. Blocking bug policy

Most bugs should be recorded and deferred until the current scenario set is complete.

A bug may be fixed immediately only if:

- it blocks multiple downstream scenarios;
- there is no reasonable workaround;
- continuing would produce invalid evidence;
- it is a data-integrity/protocol/auth boundary issue.

Before fixing a blocking bug:

1. Record the bug.
2. Capture evidence.
3. Explain why it blocks.
4. Confirm root cause.
5. Patch minimally but completely.
6. Add tests.
7. Run targeted checks.
8. Run Live regression.
9. Update `PLANS.md`.

## 13. No partial root-cause fixes

Do not patch only the observed symptom.

For each fix, state:

- root cause;
- why this code path caused the observed behavior;
- why the patch fixes that cause;
- what adjacent path could still fail;
- which regression covers the adjacent path.

Examples:

- If cancel fixes target operation but not target device_outbox/seen_commands, it is incomplete.
- If chat_raise stops phantom tickets but now always returns unavailable, data-integrity is fixed but product capability may still need a separate policy decision.
- If UIA script bypasses combo selection through an internal API, UIA wizard is not fixed.

## 14. Tests must match the bug layer

Use the right test type.

- Protocol bug -> raw WS/protocol tests + server unit/integration.
- DB lifecycle bug -> repository/service tests + Live DB verification.
- Agent idempotency bug -> agent SQLite tests + Live agent verification.
- Browser UI bug -> browser test/smoke + DOM/screenshot evidence.
- UIA bug -> pywinauto/UIA script and bounded control-tree evidence.
- Deployment bug -> service config tests + live recovery verification.

Do not claim a browser/UI bug fixed by unit tests only.

## 15. Test tools must be safe and documented

If a new diagnostic script/module is created, document:

- purpose;
- inputs;
- safety boundaries;
- token handling;
- output format;
- when it is allowed to run;
- cleanup behavior;
- whether it is a product tool or test-only tool.

Diagnostic tools must not leak tokens, collect sensitive user content, or mutate state outside their declared scope.

## 16. Token and secret hygiene

Never print raw tokens, cookies, session tokens or auth headers.

Allowed evidence:

- token prefix;
- sha256 prefix;
- length;
- redacted headers.

DB dumps must redact secrets.

Browser screenshots must not expose secrets or private user data beyond what the test requires.

## 17. Deployment and runtime-change rule

If a fix changes deployment/runtime/proxy/systemd behavior:

- record exact service/unit/config changed;
- run service status before/after;
- run `/api/health`;
- run one controlled recovery or restart test if safe;
- document whether the issue was product-code, config, proxy, systemd or external.

A server restart after deployment is not enough; prove the new behavior.

## 18. Status consistency rule

After each bug update, ensure the bug block has consistent status in all locations:

- bug heading status;
- checklist status;
- milestone summary;
- post-fix summary;
- recommended next steps.

No bug may appear as both `open` and `verified-fixed`.

At the end of a milestone, run a status audit:

- search `Status: open`;
- search bug ids in summary;
- ensure P0/P1 checklist matches individual bug blocks.

## 19. Final gate before moving to next phase

Before moving from P0 to P1 or P1 to P2:

- run workspace/code gates;
- run Live smoke;
- verify browser;
- verify local agent status;
- verify no new failed outbox rows;
- verify no stale unexpected operations/device_outbox rows for the new run_id;
- update `PLANS.md`;
- explicitly state what old contamination is ignored.

Do not start the next phase if status drift or unclassified blocking bugs remain.

## 20. Required bug template

Use this template for every bug:

```md
### BUG-YYYYMMDD-NN — short title

Severity: P0/P1/P2
Status: open / reproduced / root-cause-confirmed / verified-fixed / verified-non-product / deferred
Area: protocol / transport-proxy / account-session / DB / agent-sqlite / UI / UIA / automation / module-runtime / deployment / test-contamination

Scenario:
Expected:
Actual:
Repro steps:

Evidence:
- Transport/API:
- Server log:
- Agent log:
- Server DB:
- Agent SQLite:
- Browser/UI:
- UIA:
- Test artifact:
- Run marker:

Impact:
Root cause hypothesis:
Root cause confirmed:
Fix policy:
- Blocking further tests: yes/no
- Fixed now: yes/no

Fix summary:
Changed files:
Tests:
Live regression:
Regression check:
Remaining risk:
Status consistency checked: yes/no
```
