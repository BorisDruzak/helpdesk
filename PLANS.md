# Helpdesk Bug Remediation and Live Detection Master Plan

## 2026-08-26 Endpoint Module Platform v1

- **Status:** Phase 0 audit/documentation is complete. Endpoint PR-EP1 has
  typed contracts, both policy foundations, bounded agent primitives and a
  closed runtime registry; server feature flags and capability projection are
  still in progress. Runtime flags and production state are unchanged.
- **Goal:** move declarative module ownership/execution to Endpoint while
  retaining the legacy Workbench/runtime until explicitly migrated.
- **Constraints:** no Endpoint direct browser call, shared DB/FK, DeviceOutbox,
  ToolService, legacy WebSocket, dual dispatch, automatic fallback, arbitrary
  code, or production deployment.
- **Decisions:** Endpoint is canonical for recipe/module lifecycle and commands;
  Helpdesk is canonical for actors/tickets/facade/evidence. The exact boundary
  is `docs/segmentation/MODULE_PLATFORM_BOUNDARY.md`; legacy classifications
  live in `docs/segmentation/LEGACY_MODULE_MIGRATION_MATRIX.csv`.
- **Next steps:** finish PR-EP1 server feature flags/capability projection and
  cross-platform coverage, merge its Endpoint contract, then implement the
  typed Helpdesk port before any endpoint-native BFF execution path.
- **Verification:** Helpdesk Windows acceptance is already in mainline at
  `62b734ddf5b65a9978524c1c0af31bdf9ad53d2d`. Endpoint contracts and server
  policy foundations passed `tests/contracts tests/operations` (335 passed,
  4 skipped) before Gateway contract expansion; the refreshed Gateway contract
  suite passed (280 passed), and the later focused contracts/operations/agent
  gate passed (98 passed). No Module Platform runtime or canary verification
  has run yet.

> For agentic workers: execute this plan task-by-task. Keep this file as the active source of truth, update it after each meaningful checkpoint, and store detailed proof under `artifacts/live/<run_id>/`.

## 2026-08-26 Endpoint Operations cross-platform real-agent acceptance

- **Status:** ALT and Windows real-agent staging canaries are accepted after
  rollback; the canonical Windows record is
  `docs/verification/WINDOWS_HEADLESS_AGENT_CANARY_ACCEPTANCE.md`.
- **Accepted transport boundary:** Endpoint Operations transport is accepted
  cross-platform for the bounded `context.diagnostic.collect` slice. The
  command reached agents only through the Endpoint Gateway WSS path; Helpdesk
  performed no legacy agent, `DeviceOutbox`, or `ToolService` dispatch.
- **Runtime facts:** the successful Windows diagnostic ran against Helpdesk
  `80ed96e79fad1fad80093c8107b44a9ba0addfe1`; post-canary strict-CA tooling is
  `b338b5886b1069bffc92edf4990b090fda5987c3`. Both canaries are staging-only
  evidence and do not authorize a production change.
- **Retained components:** the legacy agent runtime, legacy `/ws`,
  `DeviceOutbox`, and agent account-session paths remain. Their deletion is
  explicitly deferred until their individual cutover prerequisites are met.
- **Not completed:** consent migration, Remote Assist migration, legacy agent
  `/ws` deletion, `DeviceOutbox` deletion, and agent account-session deletion.
- **Next package:** typed read-only Endpoint capabilities; do not expand the
  operation/command scope before its separate contract and acceptance evidence.
- **Operator action:** encrypted off-host archive of the Windows protected
  evidence is pending. Record its archive SHA-256 outside Git before claiming
  evidence archival complete.

## 2026-08-20 Helpdesk co-hosting on Endpoint Platform production host

- **Status:** clean Helpdesk baseline deployed and running on 2026-08-20.
- **Goal:** deploy Helpdesk as an independent production service on
  `osn_admin@192.168.100.19`, next to (but isolated from) Endpoint Platform.
- **Confirmed decisions:** create a fresh Helpdesk PostgreSQL database and only
  a new administrator; migrate no Helpdesk data; do not register or preserve
  legacy agents; agents will use a future replacement auth/connection method.
  Keep Helpdesk and Endpoint as separate repositories, databases, service
  users, systemd units, release trees, runtime directories, and Nginx vhosts.
- **Endpoint contract:** use only the existing HTTPS Endpoint Operations API
  with an explicitly enabled feature and a separate scoped service identity.
  No direct Endpoint import or database access is permitted.
- **Bootstrap constraint:** the initial IP-only access is temporary and
  network-restricted. The final production gate requires a DNS name, trusted
  TLS certificate, `REQUIRE_HTTPS=true`, and `REQUIRE_WSS=true`; insecure
  transport is never the steady-state design.
- **Deployment record:** immutable release
  `fb203b6026dde49a2673f0126a7a727d597aebe4` is active at
  `/opt/helpdesk/current`; Alembic revision is `136`. The dedicated
  `helpdesk-server.service` and `helpdesk-control.service` are enabled and
  active, bind only to loopback, and are exposed through the restricted
  temporary IP bootstrap at `http://192.168.100.19:8080`. The fresh database
  has no UI users or devices; no legacy Helpdesk data or agents were copied.
- **Verification record:** focused deployment tests (19 passed), documentation
  link check, Helpdesk API/Nginx smoke (200), Nginx syntax, service enablement
  and Endpoint service health passed. `verify_workspace.py` did not complete
  in the available local run and is not counted as a passing gate.
- **Remaining gates:** create the initial administrator, obtain the separate
  Endpoint service credential and acceptance, then complete FQDN/TLS/secure
  cookie cutover and the new agent connection/auth rollout.

## 2026-08-17 Helpdesk Endpoint Integration v1

- **Status:** implementation completed locally and merged into
  `codex/helpdesk-process-model`. Focused endpoint, standard PostgreSQL and
  workspace-verifier gates passed; no deployment or production migration ran.
  The full CI baseline remains blocked by four pre-existing non-Endpoint
  DB-cleanup-profile audit gaps.
- **Goal:** implement exactly one external vertical slice,
  `endpoint.context.diagnostic.collect` → Endpoint
  `context.diagnostic.collect`, without Helpdesk WebSocket/DeviceOutbox agent
  dispatch.
- **Starting baseline:** `062703ab291645123e01d3732939c1dfebe43339` on
  `codex/helpdesk-process-model`; current Alembic head at planning time is
  `134`.
- **Decisions:** Endpoint Platform owns endpoint-agent operations/control
  plane; Helpdesk owns tickets, diagnostics, UI, local facade `Operation`, and
  safe evidence. Endpoint refs/correlation are opaque and non-authorizing; no
  cross-service imports, DB FK, automatic fallback, or dual dispatch.
- **Default state:** Endpoint unavailable and diagnostic execution `legacy`.
  `endpoint` mode is explicit, fail-closed, asynchronous, and reconciles
  external operations into safe local diagnostics.
- **Constraints:** legacy agent `/ws`, `DeviceOutbox`, runtime/tables and
  `/ws_ui` remain. No production deployment/migration, service credential
  change, test-agent action or agent rollout is in scope.
- **Next steps:** before any deployment, rehearse migrations on the release
  candidate and validate the four allowed HTTPS Endpoint API routes against an
  integration fixture or approved Endpoint Platform environment. Keep
  `docs/segmentation/HELPDESK_ENDPOINT_RESIDUAL_INVENTORY.md` current whenever
  a residual component's ownership changes.
- **Verification gate:** Endpoint contract/adapter/device/link/reconciler/
  provider/cutover guard tests; affected diagnostics/operations/ticket/API/
  `/ws_ui`/migration suites; workspace verifier and diff check; browser
  evidence plus webapp build only if the UI changes.
- **Handoff:** accepted boundary:
  `docs/segmentation/HELPDESK_ENDPOINT_OPERATION_BOUNDARY.md`; approved design:
  `docs/superpowers/specs/2026-08-17-helpdesk-endpoint-integration-design.md`.

## 2026-08-09 Helpdesk segmentation milestone (PR-0 / PR-1 / PR-6)

- **Completed locally:** ownership ADR/API target, neutral domain ports, AST import guard, ticket/support/problem/Registry detachment, and removal of the in-process Knowledge runtime, routes, UI, agent client, local AI runtime, content packs and active ORM mappings.
- **Current behavior:** `KnowledgePort` is explicitly unavailable (`knowledge_unavailable`) with no local DB/HTTP fallback; removed local Knowledge paths return normal `404`; ticket creation, routing, support work and closure remain available.
- **Retained history:** all old Alembic migrations and physical Knowledge/AI tables, `ticket_kb_links` rows and sanitized legacy `knowledge_attempts` remain untouched and read-only. No schema migration, data deletion, deploy or remote mutation was run for this milestone.
- **Evidence:** focused port/import-boundary/ticket/support/problem/Registry/removed-route tests, Python compilation, default collection and webapp build are recorded in the task reports under `.superpowers/sdd/2026-08-09-helpdesk-segmentation-pr0-pr1-pr6/`. DB-backed subsets have a documented local timeout and are not claimed green.
- **Next gates:** PR-7 may add a versioned external Knowledge API adapter only after service/auth/scope/redaction acceptance. PR-11 may delete retained schema only after acceptance, with a separately reviewed forward-only migration, backup/rollback plan and no local fallback restoration.

## 2026-08-10 Registry retirement decision

- **Confirmed ownership:** `ui_users`, Helpdesk web sessions and RBAC remain
  Helpdesk-owned. Local `registry_*`, device-registration, account/pairing
  data and Registry-linked ticket/consent FKs are retirement targets only
  after a RegistryPort external cutover.
- **Required sequence:** PR-2 immutable refs/snapshots; PR-8 local adapter and
  import boundary; PR-9 external Registry API with shadow-read acceptance;
  PR-11 forward-only schema deletion with clone rehearsal, backup/restore
  rollback and a maintenance window. Alembic downgrade is explicitly excluded.
- **Design record:**
  `docs/superpowers/specs/2026-08-10-registry-retirement-design.md`.

## Goal

Build a reliable bug remediation and live detection loop for the helpdesk system. Already-known P0/P1 defects from the deep audit must be verified against current `HEAD`, fixed with regression coverage and real evidence, then the stabilized system can be used for broader live bug hunting.

The intended release state is:

- all known P0/P1 bugs are verified-fixed, verified-non-product, or explicitly accepted as release-blocking known limitations;
- every live bug found later is recorded, triaged, deduplicated and routed into a remediation wave before any fix work starts;
- all 17 critical behavior scenarios pass with exact-context live evidence;
- release gates reject shallow, stale, mismatched or missing proof.

## Current State

- **Status:** active master plan reset on 2026-06-26 after user review of the previous `PLANS.md` structure.
- **Branch at plan update:** `codex/helpdesk-process-model`.
- **Scope classification:** cross-cutting. The plan spans webapp, server APIs, PostgreSQL, Observer, Protocol V3/agent runtime, live tooling, CI and release gates.
- **Plan source:** rebuilt from the uploaded deep audit, live bug-detection plan, remediation/observer plan and the latest restructuring request.
- **Primary rule change:** broad live bug hunt is deferred until static-confirmed known P0/P1 defects are remediated or explicitly dispositioned.
- **Audit drift note:** the deep audit reviewed an older GitHub `HEAD`; Phase 0 must verify every deep-audit ID on the current local tree before code changes.
- **Release state:** not assumed green. Treat current release readiness as unknown until Phase 0 records exact commit, deployed commit, schema head, CI state, Observer baseline and live evidence readiness.
- **Latest remediation checkpoint, 2026-06-26:** Phase 1 code slices fixed `ID-001`, `ID-002`, `CLAIM-003`, `AGENT-AUTH-004`, `PAIR-005`, `SESSION-006`, `EVENT-007`, `EVENT-008`, `CHAT-009`, `CHAT-010`, `CLOSE-018`, `PUBLIC-AUTH-034`, `AUTH-029`, `ACCOUNT-033` and adjacent `AUTH-030` locally. Focused automated/no-DB regression checks and direct helper assertions are green where runnable, migration `132` is the Alembic head, and `known_bug_registry.current_head.json` records all 41 IDs. P0/P1 release disposition remains blocked until live/stand evidence is collected where required.

## Stop Conditions

Stop implementation or live execution and update this plan before continuing when any of these occurs:

- Broad live bug hunt is requested while any static-confirmed P0/P1 known bug is neither verified-fixed, verified-non-product, nor explicitly accepted as a release-blocking known limitation.
- Exact context is unknown: local commit, deployed commit, branch, schema head, environment or release run id cannot be proven.
- A run exposes cross-account access, cross-device access, public-token bypass, auth/session confusion, role confusion or unredacted secret leakage.
- A required evidence layer is missing for a P0/P1 fix or release-gate scenario.
- Browser/API/DB/Observer/agent evidence disagree on the same outcome.
- New active critical/high Observer events appear during a fix or live run.
- Data contamination invalidates a run marker, ticket marker, device marker or cleanup proof.
- Stand/deployment state is manually patched outside project release/deploy/runtime scripts.
- Multi-instance deployment is requested while process-local outbox/session delivery risks remain unresolved.

## Known Defect Registry

The deep audit IDs below are the initial known-defect registry. Current `HEAD` status is intentionally conservative until Phase 0 writes `known_bug_registry.current_head.json` with one of: `open`, `reproduced`, `not-reproduced`, `already-fixed`, `blocked`.

| Bug ID | Priority | Group | Current HEAD status | Fix status | Regression test | Verification | Release blocker |
|---|---:|---|---|---|---|---|---|
| `ID-001` | P0 | identity/account boundary | reproduced on current HEAD | fixed-local, live-evidence-pending | `test_requester_identity_does_not_link_by_unverified_email_alias`; `test_effective_identity_does_not_link_by_email_alias_without_ui_login` | focused pytest green; live/API/DB evidence missing | yes, until live evidence |
| `ID-002` | P0 | identity/account boundary | reproduced on current HEAD | fixed-local, live-evidence-pending | `test_ui_users_repo_rejects_case_variant_login` | focused pytest green; Alembic `130 -> 131` green; live evidence missing | yes, until live evidence |
| `CLAIM-003` | P1 | public claim/session | reproduced on current HEAD | fixed-local, focused-tests-green | `test_requester_public_ticket_claim_is_single_winner_under_race` | focused pytest green; live/stand evidence missing | yes, until live evidence |
| `AGENT-AUTH-004` | P1 | pairing/session delivery | reproduced on current HEAD | fixed-local, focused-tests-green | `test_handshake_rebind_keeps_token_on_original_device_when_fingerprint_mismatches`; `test_handshake_rebind_uses_expected_original_token_binding` | no-DB handshake pytest green; live/stand evidence missing | yes, until live evidence |
| `PAIR-005` | P1 | pairing/session delivery | reproduced on current HEAD | fixed-local, focused-tests-green | `test_registration_pairing_pickup_waits_for_deliverable_session_before_consuming`; API contract updated in `test_registration_pairing_approval_surfaces_confirmed_binding_to_agent`; agent gate compatibility tests updated | no-DB pairing FSM pytest green; focused pc_agent pytest green; DB API pytest attempted but fixture hung locally; live/stand evidence missing | yes, until live evidence |
| `SESSION-006` | P1 | pairing/session delivery | reproduced on current HEAD | fixed-local, focused-tests-partial | `test_approved_login_request_session_token_survives_worker_restart_until_first_poll`; `test_account_session_delivery_no_db.py` | direct helper assertions green; compile green; local pytest runner hung before result; live/stand evidence missing | yes, until live evidence |
| `EVENT-007` | P1 | chat/timeline | reproduced on current HEAD | fixed-local, focused-tests-green | `test_ticket_events_repo_no_db.py::test_get_events_orders_timeline_by_created_at_before_agent_seq` | no-DB pytest/direct regression green; compile green; live/stand evidence missing | yes, until live evidence |
| `EVENT-008` | P1 | chat/timeline | reproduced on current HEAD | fixed-local, focused-tests-green | `test_ticket_events_server_idempotency_unique_indexes_are_migrated`; `test_add_event_treats_server_idempotency_unique_conflicts_as_duplicates` | no-DB pytest green; Alembic head/history green; DB-backed migration contract hung locally | yes, until live evidence |
| `CHAT-009` | P1 | chat/timeline | reproduced on current HEAD | fixed-local, focused-tests-green | `test_web_support_send_message_rejects_unknown_visibility_before_db`; `test_chat_message_unknown_visibility_is_hidden_from_requester_timeline` | no-DB API/projection pytest green; DB-backed endpoint pytest hung locally; live/stand evidence missing | yes, until live evidence |
| `CHAT-010` | P2 | chat/timeline | reproduced on current HEAD | fixed-local, focused-tests-green | `test_web_support_send_message_rejects_long_message_id_before_db`; `test_web_support_message_retry_rejects_same_message_id_with_different_payload`; `test_requester_ticket_message_rejects_long_message_id_before_db`; `test_requester_ticket_message_retry_rejects_same_message_id_with_different_payload` | no-DB endpoint pytest green; DB-backed retry happy-path pytest hung locally | no, unless release-impacting |
| `CREATE-011` | P1 | ticket create/workflow | open, verify in Phase 0 | not-started | required | missing | yes |
| `CREATE-012` | P1 | ticket create/workflow | open, verify in Phase 0 | not-started | required | missing | yes |
| `CREATE-013` | P1 | ticket create/workflow | open, verify in Phase 0 | not-started | required | missing | yes |
| `CREATE-014` | P2 | ticket create/workflow | open, verify in Phase 0 | not-started | required | missing | no, unless release-impacting |
| `WORKFLOW-015` | P1 | ticket create/workflow | open, verify in Phase 0 | not-started | required | missing | yes |
| `WORKFLOW-016` | P1 | ticket create/workflow | open, verify in Phase 0 | not-started | required | missing | yes |
| `WORKFLOW-017` | P1 | ticket create/workflow | open, verify in Phase 0 | not-started | required | missing | yes |
| `CLOSE-018` | P1 | public claim/session | reproduced on current HEAD | fixed-local, focused-tests-green | `test_public_ticket_session_rejects_terminal_ticket_even_if_not_revoked` | focused pytest green; live/stand evidence missing | yes, until live evidence |
| `TOOL-019` | P1 | tool/operation lifecycle | open, verify in Phase 0 | not-started | required | missing | yes |
| `MODULE-020` | P1 | tool/operation lifecycle | open, verify in Phase 0 | not-started | required | missing | yes |
| `CONSENT-021` | P1 | tool/operation lifecycle | open, verify in Phase 0 | not-started | required | missing | yes |
| `PLAYBOOK-022` | P2 | tool/operation lifecycle | open, verify in Phase 0 | not-started | required | missing | no, unless release-impacting |
| `HISTORY-023` | P1 | history/context | open, verify in Phase 0 | not-started | required | missing | yes |
| `HISTORY-024` | P2 | history/context | open, verify in Phase 0 | not-started | required | missing | no, unless release-impacting |
| `SUPPORT-025` | P1 | support/admin truthfulness | open, verify in Phase 0 | not-started | required | missing | yes |
| `SUPPORT-026` | P2 | support/admin truthfulness | open, verify in Phase 0 | not-started | required | missing | no, unless release-impacting |
| `INSTALL-027` | P1 | installer/update | open, verify in Phase 0 | not-started | required | missing | yes |
| `INSTALL-028` | P1 | installer/update | open, verify in Phase 0 | not-started | required | missing | yes |
| `AUTH-029` | P1 | identity/account boundary | reproduced on current HEAD | fixed-local, focused-tests-green | `test_ui_users_repo_failed_attempts_are_atomic_across_stale_sessions` | focused pytest green; live/stand evidence missing | yes, until live evidence |
| `AUTH-030` | P2 | identity/account boundary | reproduced on current HEAD | fixed-local, focused-tests-green | `test_web_session_register_rejects_login_longer_than_db_limit` | no-DB registration pytest green | no, unless release-impacting |
| `TOKEN-031` | P2 | pairing/session delivery | open, verify in Phase 0 | not-started | required | missing | no, unless release-impacting |
| `ASSIGN-032` | P2 | ticket create/workflow | open, verify in Phase 0 | not-started | required | missing | no, unless release-impacting |
| `ACCOUNT-033` | P1 | identity/account boundary | reproduced on current HEAD | fixed-local, focused-tests-green | `test_unverified_other_account_does_not_resolve_declared_person` | focused pytest green; live/stand evidence missing | yes, until live evidence |
| `PUBLIC-AUTH-034` | P1 | public claim/session | reproduced on current HEAD | fixed-local, focused-tests-green | `test_public_ticket_authorize_rate_limits_invalid_code_attempts` | no-DB handler pytest green; live/stand evidence missing | yes, until live evidence |
| `PAIR-035` | P2 | pairing/session delivery | open, verify in Phase 0 | not-started | required | missing | no, unless release-impacting |
| `SCALE-036` | P1 | scaling/protocol risk | open, verify in Phase 0 | not-started | required | missing | yes |
| `PROTOCOL-037` | P1 | scaling/protocol risk | open, verify in Phase 0 | not-started | required | missing | yes |
| `TOOL-038` | P1 | tool/operation lifecycle | open, verify in Phase 0 | not-started | required | missing | yes |
| `TEST-039` | P0 | test/release assurance | open, verify in Phase 0 | not-started | required | missing | yes |
| `TEST-040` | P1 | test/release assurance | open, verify in Phase 0 | not-started | required | missing | yes |
| `RELEASE-041` | P0 | test/release assurance | open, verify in Phase 0 | not-started | required | missing | yes |

## Current Implementation Mismatch

These gaps must stay visible so existing scripts are not mistaken for completed live-proof infrastructure:

- browser runner = probe-only;
- operation lifecycle = malformed-outbox placeholder;
- native agent = connected-state placeholder;
- evidence pack lacks `stand`;
- validator is structural, not a full semantic pack validator;
- fallback live credentials still exist in browser script.

## Immediate Guardrails

- Keep `WEB_SELF_REGISTRATION_ENABLED=false` until `ID-001` and `ID-002` have live evidence and migration audit is clean.
- Do not run broad live bug hunts until Phase 2 is green.
- Do not run multi-instance server deployment while process-local DeviceOutbox/session state remains an active risk.
- Treat release as blocked until all 17 critical scenarios have passing `pc_client.live_evidence.v2` manifests and exact release summary.
- Maintain the fail-closed guard for unknown chat visibility before broader chat refactoring.
- Make public-session verification depend on ticket state as defense in depth.
- Reject high-risk dispatch when `tool_call_started`/outbox transaction is not persisted.
- Make support UI distinguish DB outage from an actually empty queue.
- Create or update bug records for all deep-audit IDs before changing implementation.

## Done Criteria For Already Known Bugs

For each known bug, `verified-fixed` requires all applicable evidence below:

1. Pre-fix proof on current `HEAD` or a documented `not-reproduced` / `already-fixed` disposition.
2. Regression test that fails before the fix or a documented reason why red-first proof is impossible.
3. Small code fix with no unrelated behavior change.
4. Focused green tests for the touched layer.
5. Negative and concurrency tests for auth, account, workflow, idempotency, ticket state, public-token, operation or session-delivery bugs.
6. Observer checker update or Observer assertion where the defect affects integrity, security, lifecycle or release evidence.
7. Real UI/API/DB evidence and agent evidence when the agent participates.
8. Clean run marker, cleanup proof and no cross-test contamination.

## Known Bug Remediation Waves

Phase 1 fixes follow this order. P2 items in the same area may be fixed in the wave when they are cheap, directly adjacent or needed for a clean P0/P1 proof, but they do not block starting the next P0/P1 slice unless Phase 0 promotes them.

| Wave | Area | IDs |
|---|---|---|
| A | identity/account/session/public access | `ID-001`, `ID-002`, `AUTH-029`, `AUTH-030`, `ACCOUNT-033`, `CLAIM-003`, `CLOSE-018`, `PUBLIC-AUTH-034`, `AGENT-AUTH-004`, `PAIR-005`, `SESSION-006`, `TOKEN-031`, `PAIR-035` |
| B | ticket create/event/timeline/workflow | `EVENT-007`, `EVENT-008`, `CHAT-009`, `CHAT-010`, `CREATE-011`, `CREATE-012`, `CREATE-013`, `CREATE-014`, `WORKFLOW-015`, `WORKFLOW-016`, `WORKFLOW-017`, `ASSIGN-032` |
| C | tool/operation/consent/module | `TOOL-019`, `MODULE-020`, `CONSENT-021`, `PLAYBOOK-022`, `TOOL-038` |
| D | history/support/admin | `HISTORY-023`, `HISTORY-024`, `SUPPORT-025`, `SUPPORT-026` |
| E | installer/update | `INSTALL-027`, `INSTALL-028` |
| F | scale/protocol/test/release assurance | `SCALE-036`, `PROTOCOL-037`, `TEST-039`, `TEST-040`, `RELEASE-041` |

## Phase 0 - Baseline and Current-HEAD Verification

**Goal:** verify the known audit findings against current local `HEAD`, record release context and determine whether stand/data are safe enough for remediation.

**Work:**

- Bootstrap UTF-8 and rebuild stale context:
  `.\scripts\bootstrap_shell_utf8.ps1`
- Run intake and focused context:
- Record exact local commit, deployed commit, branch, expected schema head, actual schema head, environment and release run id.
- Collect a read-only DB report for:
  case-colliding UI logins, UI accounts without verified `ui_login`, ambiguous person-to-web-account links, closed tickets with active public sessions, consumed pairings without account session, approved login requests without deliverable secret, duplicate event/message IDs, `in_progress` without assignee, queue/OLA mismatch.
- Run baseline Observer integrity scan and record active/suppressed critical/high/error events.
- For every deep-audit ID, verify current `HEAD` and write a row to `known_bug_registry.current_head.json`.
- Assign each ID status: `open`, `reproduced`, `not-reproduced`, `already-fixed`, or `blocked`.
- Sort P0/P1 IDs by fix order and copy that order back into this plan.
- Create or update bug cards for IDs that reproduce or remain open.

**Exit criteria:**

- `known_bug_registry.current_head.json` exists.
- All 41 IDs have a current `HEAD` status.
- P0/P1 bugs are sorted in implementation order.
- False positives and blocked-by-stand/data items are explicitly marked.
- The stand is either cleared for remediation evidence or marked blocked with exact blocker reason.

## Phase 1 - Remediate Already Known P0/P1 Bugs

**Goal:** close already-known P0/P1 defects before searching broadly for new live defects.

Broad live bug hunt starts only after all static-confirmed P0/P1 known bugs are either verified-fixed, verified-non-product, or explicitly accepted as release-blocking known limitations.

For every bug in this phase:

`pre-fix evidence -> regression test -> fix -> focused tests -> DB/API/UI verification -> Observer assertion -> status verified-fixed`

### Wave A - Identity / Account / Registry

Minimum order:

1. `ID-001` - fixed locally, live evidence pending
2. `ID-002` - fixed locally, live evidence pending
3. `AUTH-029` - fixed locally, live evidence pending
4. `AUTH-030` - fixed locally by adjacent login-length alignment
5. `ACCOUNT-033` - fixed locally, live evidence pending

Required direction:

- Introduce `normalized_login` or a functional unique index on `lower(user_login)`.
- Normalize login before auth lookup and token subject creation.
- Remove fallback web-account resolution through email, Windows login or AD identity.
- Add durable verified web-account-to-person link.
- Route email/AD matches through claim/conflict flow.
- Align login max length across DTO, handler and DB.
- Make failed-attempt increments atomic.
- Migration must detect collisions, quarantine ambiguous accounts, backfill verified links and fail preflight on unresolved P0 collisions.

### Wave B - Claim / Public Session / Pairing

Minimum order:

1. `CLAIM-003` - fixed locally; live evidence pending
2. `CLOSE-018` - fixed locally; live evidence pending
3. `PUBLIC-AUTH-034` - fixed locally; live evidence pending
4. `AGENT-AUTH-004` - fixed locally; live evidence pending
5. `PAIR-005` - fixed locally; live evidence pending
6. `SESSION-006` - fixed locally; pytest fixture/runner evidence pending
7. `TOKEN-031`
8. `PAIR-035`

Required direction:

- Use row locks or conditional updates for public ticket claim.
- Keep agent token, fingerprint and rebind checks in one transaction.
- Enforce device-scoped token max count with advisory lock or serializable transaction.
- Verify public sessions against revoked, expiry, ticket ownership and terminal-state policy.
- Make close/revoke atomic or enforce deny-by-closed-state defense in depth.
- Model pairing states as `created -> browser_confirmed -> awaiting_approval -> approved_pending_delivery -> delivered -> consumed`.
- Do not consume before a deliverable session exists.
- Enforce one active pairing per device/purpose.
- Use a durable encrypted one-time token envelope.
- Make delivery claim atomic with `delivered_at IS NULL`.
- Prove polling works across workers and restarts.

### Wave C - Create / Chat / Timeline / Workflow

Minimum order:

1. `EVENT-007` - fixed locally; live evidence pending
2. `EVENT-008` - fixed locally; DB-backed migration/live evidence pending
3. `CHAT-009` - fixed locally; DB-backed endpoint/live evidence pending
4. `CHAT-010` - fixed locally; DB-backed retry/live evidence pending
5. `CREATE-011`
6. `CREATE-012`
7. `CREATE-013`
8. `WORKFLOW-015`
9. `WORKFLOW-016`
10. `WORKFLOW-017`

Required direction:

- Add `Idempotency-Key` support for ticket create, messages, close/feedback/reopen, run tool/playbook, consent decision, assignment/status/queue mutation.
- Add durable idempotency storage with actor/scope, request hash, `in_progress/completed/failed`, response snapshot, TTL and unique scope/key.
- Add DB constraints for event/message IDs and agent event uniqueness.
- Use `ON CONFLICT` for server event insert paths.
- Separate agent replay ordering from UI timeline ordering.
- Add monotonic `timeline_seq` or robust keyset pagination.
- Add cursor pagination for ticket/event/history APIs.
- Convert routing/SLA/OLA side effects to durable outbox/reconciliation, not silent success.
- Ensure unverified accounts cannot receive `requester_person_id`.
- Add or enforce `tickets.version`.
- Use CAS for status mutations.
- Row-lock assignment/load policy.
- Enforce `in_progress -> assignee required`.
- Keep queue/OLA changes transactional or visibly pending.

### Wave D - Tool / Operation / Consent / Module

Minimum order:

1. `TOOL-019`
2. `MODULE-020`
3. `CONSENT-021`

Required direction:

- Canonical transaction order: `operation + tool_call_started + device_outbox + observer correlation -> commit -> sender dispatch`.
- High-risk tools fail closed.
- Preserve initiating actor attribution and store service principal separately.
- Require idempotency for tool/playbook runs and consent decisions.
- Add `approved_pending_dispatch` plus recovery worker for consent after dispatch outage.
- Show module owner conflict before run.
- Remove legacy execution paths or route them through the unified service.

### Wave E - Support/Admin Degradation

Minimum order:

1. `SUPPORT-025`
2. `SUPPORT-026`

Required direction:

- DB outage returns explicit `503` or `200 degraded=true` with stale timestamp.
- UI shows a visible degraded/error banner and retry action.
- UI must not show zero counts as trustworthy when a source is incomplete.
- Query values are typed and bounded.
- Permission matrix is enforced for auditor/support/admin mutations.
- Invalid internal-note visibility fails closed and preserves draft text.
- Partial operation state is explicit if retained.
- Raw IDs remain secondary metadata.

### Wave F - Agent Installer/Update

Minimum order:

1. `INSTALL-027`
2. `INSTALL-028`

Required direction:

- Add update journal with phases and durable rollback marker.
- Use temp file, flush/fsync and atomic replace for `current.json`.
- Backup/restore DB for failures after verify/publish starts.
- Use SQLite online backup API.
- Add crash recovery for each intermediate phase.
- Formalize installer/portable deployment, signed artifacts, install/uninstall/repair contract and data directory ACL.

**Exit criteria:**

- Every static-confirmed P0/P1 ID in Phase 1 has status `verified-fixed`, `verified-non-product`, or `accepted-release-blocking-limitation`.
- Regression tests and evidence links are recorded in the defect registry.
- No new high/critical Observer event remains active after remediation.
- No release-blocking known bug is hidden behind a live-tooling gap.

## Phase 2 - Verify Known-Bug Fixes End-to-End

**Goal:** prove the system still works after known P0/P1 remediation and before new-bug discovery begins.

Required smokes:

- requester registration/profile/device-link smoke;
- requester create/chat/close smoke;
- support queue/status/message smoke;
- tool/consent smoke;
- admin registry/observer smoke;
- no P0/P1 regressions;
- no new high/critical Observer events.

**Output:**

- `known_bug_fix_verification_summary.md`;
- P0/P1 fixed bugs verified;
- system smoke green;
- list of skipped checks with explicit reason, if any.

## Phase 3 - Harden Live Bug-Hunt Tooling

**Goal:** make live evidence machine-verifiable before trusting broad scenario results.

Likely files:

- `scripts/run_live_behavior_suite.py`
- `scripts/live_evidence_pack.py`
- `scripts/validate_live_evidence.py`
- `scripts/build_live_release_summary.py`
- `webapp/scripts/live-browser-scenarios.mjs`
- `test_data_packs/critical_behavior_v1.json`
- `scripts/test_validate_live_evidence.py`
- `scripts/test_build_live_release_summary.py`
- `scripts/test_run_live_behavior_suite.py`
- `docs/LIVE_TESTING_DEBUG_RULES.md`

Work:

- Add `stand` surface support to evidence scaffold and release scenario handling.
- Add action-level browser runner support for form fill/select, ticket create, chat, internal/public support notes, status, assignment, queue changes, run tool/playbook, consent approve/deny, close/feedback/reopen, history/context/report/Observer pages.
- Add forensic browser output: screenshot, DOM assertion, console/page errors, failed network requests, target API request/response digests, server request IDs, idempotency keys, trace IDs and redaction summary.
- Add DB assertion output with redacted query digests for tickets, ticket events, operations, device outbox, registry bindings, account sessions, public sessions, SLA/OLA and history projections.
- Add Observer assertion output for trace list/detail, required root kinds, span/result consistency, integrity before/after and new critical/high/error deltas.
- Add agent assertion output for SQLite, action trace, logs, launcher/update files and UIA state.
- Extend manifests with `required_evidence`, `evidence_coverage`, `expected_outcomes` and `assertions[]`.
- Harden validator so a manifest fails when a required layer or expected outcome lacks a passing assertion or artifact.
- Remove live fallback credentials; live mode must fail unless credentials are explicitly configured.
- Ensure release summary rejects shallow manifests even when commit/environment/schema match.

**Exit criteria:** a shallow manifest for any critical scenario fails validation, and `canonical_stand_release_gate` can be scaffolded and summarized like the other scenarios.

## Phase 4 - Live Bug Hunt Execution

**Goal:** execute real domain actions to discover new bugs after known P0/P1 remediation and live-tooling hardening.

**Historical stand origin for this archived phase:** `https://example.test:9443`

Rule: new bugs found in this phase are not fixed immediately inside the bug-hunt wave. First create or update a bug card, assign priority/layer, link it from this plan or a registry, then route it into the next remediation wave.

Before every run:

- Create a unique `release_run_id`, for example `live-20260626-<commit7>-stand`.
- Create a unique scenario marker: `test_marker=<scenario_key>-<timestamp>-<short_uuid>`.
- Put the marker into safe ticket/message/custom-field/operation metadata and artifact names.
- Confirm target accounts/devices/forms: requester with completed profile and Windows primary agent, requester with Linux primary agent, incomplete-profile requester, no-primary-agent requester, support, admin, lab Windows agent and lab Linux agent.

First high-yield runs:

1. `requester_support_admin_session_switch` with session revocation and role switch.
2. Self-registration hijack attempt using a login equal to an existing Registry email.
3. Case collision: `Alice` vs `alice`.
4. `real_account_device_linking` with delayed admin approval and server restart.
5. `requester_support_chat_roundtrip` with message retry and internal-note typo.
6. `admin_publish_requester_create` with double-click create and network retry.
7. `support_queue_status_after_routing` with concurrent status/assignment.
8. `tool_run_approve_deny_timeout` with late approve after timeout.
9. `module_playbook_canary` with duplicate playbook idempotency key.
10. `windows_linux_vm_agent_runtime` with restart/replay pending command.
11. Closure flow: resolve, public token, requester confirm close, old public token denied.
12. History cutoff: requester 301st ticket and old affected-person history.

Pass/fail rules:

- `fail` if a required layer is missing, browser/API/DB/Observer disagree, new critical/high/error Observer event appears, unexpected suppression appears, auth/account boundary is unclear, secrets leak into artifacts, cleanup is missing, replay creates duplicates, stale data lacks run marker, or commit/schema preflight mismatches.
- `blocked` if the stand is unreachable, deployed commit/schema head is unknown, required agent is offline, test account is missing, DB tunnel is unavailable, Observer scan is incomplete or contamination invalidates results.
- `pass` only if every required layer and expected outcome has a passing assertion, manifest validates, Observer canary passes, cleanup passes or is not applicable, no critical/high/error delta appears and exact release context matches.

## Phase 5 - New Bug Intake, Triage and Plan Update

**Goal:** convert live-findings into an ordered remediation backlog instead of mixing discovery and fixing.

Every live bug creates or updates:

- `artifacts/live/<run_id>/bugs/<bug_id>.md`;
- `quality/active_risks.json` if P0/P1 or release-blocking;
- this plan's bug registry row or a linked registry row;
- test refs once a regression exists.

Bug intake format:

```yaml
bug_id:
source_live_run:
scenario_key:
priority:
primary_layer:
status:
release_blocker:
regression_test_required:
observer_checker_required:
fix_phase:
```

Triage work:

- classify new bugs;
- deduplicate against known IDs and prior live cards;
- assign priority and owner/candidate owner;
- list impacted scenarios;
- define required evidence;
- decide stop/release blocker status;
- add to remediation backlog;
- route to Phase 6 or defer with explicit reason.

## Phase 6 - Remediate Live-Found Bugs

**Goal:** fix the live-found backlog created in Phase 5.

Work:

- Pull the next P0/P1 or release-blocking item from the triaged backlog.
- Capture pre-fix evidence from the source live run.
- Add regression coverage and Observer checker/assertion where required.
- Fix with the smallest correct change.
- Run focused tests, negative tests and live/API/DB/Observer verification.
- Update `quality/active_risks.json`, bug cards and this plan.

**Exit criteria:** all Phase 5 release-blocking live bugs are verified-fixed, verified-non-product, deferred with explicit release limitation, or still blocking release.

## Phase 7 - Repeat Live Hunt and Regression Matrix

**Goal:** rerun fixed scenarios and add exploratory coverage without losing exact-context discipline.

Work:

- Rerun all scenarios that produced Phase 5/6 bugs.
- Rerun the 17 critical behavior scenarios.
- Add exploratory variants for identity/session, cross-role search, public links, concurrent workflow, tool consent timing, agent restart/replay and report/history boundaries.
- Confirm all new bugs follow Phase 5 intake before any fix work starts.
- Update regression matrix with scenario, bug id, test ref, evidence ref and current status.

## Phase 8 - Observer/Test Layer Expansion

**Goal:** make integrity gaps visible and prevent future shallow tests.

New or expanded Observer checker sources:

- `observer.identity_boundary`: `ui_login_case_collision`, `web_account_person_link_missing`, `web_account_person_link_ambiguous`, `external_identity_granted_without_verification`, `unverified_account_ticket_person_link`.
- `observer.registration_sessions`: `pairing_multiple_active`, `pairing_consumed_without_session`, `approved_login_request_secret_missing`, `account_session_delivery_duplicate`, `account_session_device_mismatch`.
- `observer.ticket_integrity`: `ticket_create_side_effect_incomplete`, `ticket_in_progress_without_assignee`, `ticket_queue_ola_mismatch`, `closed_ticket_active_public_session`, `ticket_multiple_terminal_events`, `ticket_event_duplicate_id`, `ticket_message_duplicate_id`, `ticket_timeline_non_monotonic`, `requester_history_projection_incomplete`.
- `observer.tool_lifecycle`: `tool_dispatched_without_started_event`, `operation_outbox_missing`, `tool_actor_attribution_mismatch`, `consent_approved_dispatch_missing`, `operation_terminal_result_missing`, `playbook_duplicate_execution_key`.
- `observer.agent_update_integrity`: `update_journal_incomplete`, `publish_failed_without_db_restore`, `current_pointer_invalid`, `handshake_version_not_confirmed`, `rollback_version_not_confirmed`.
- `observer.support_degradation`: `support_workspace_source_incomplete`, `support_empty_success_on_backend_error`, `support_summary_stale_without_banner`.

Test layer expansion:

- Unit/property: login canonicalization, profile field policy, FSM, idempotency request hashing, visibility enum, timeline cursor, update journal recovery.
- PostgreSQL integration: functional/partial indexes, row locks, CAS, two-session barriers, rollback, old-baseline migrations and partial migration retry.
- Multi-process: two server workers, approval on worker A and poll on worker B, outbox sender ownership, restart recovery.
- Protocol/agent: token validity, fingerprint mismatch, ACK after persistence/duplicate/no-op proof, malformed context NACK, terminal result replay, duplicate command handling and agent SQLite state.
- Fault injection: before/after DB write, after commit before HTTP/WS response, before outbox, after consent commit, during update pointer replace and during public token issuance.
- Load/boundary: 301 requester tickets, 1001 affected-person tickets, 501 mixed events, 2001 support tickets, 10k chat messages and malformed query values.
- Security: cross-account, cross-device, cross-queue, auditor mutation, support/admin permission matrix, self-registration abuse, public code throttling, CSRF/session cookie policy and redaction.
- Mutation smoke: login normalization, verified-link check, fingerprint check, CAS, public-session closed-state check, visibility validation, start-before-dispatch, event conflict handling and pairing one-time delivery CAS.

## Phase 9 - Release Gate

Release candidate is allowed only when:

- known bugs are fixed, verified-non-product or explicitly accepted as release-blocking limitations;
- new live bugs are triaged;
- no open P0/P1 bugs remain outside accepted release-blocking limitations;
- all 17 critical behavior scenarios have `status=pass`;
- exact-context live summary passes;
- `python scripts/verify_workspace.py` is green;
- plain full `python scripts/run_ci_suite.py` is green on the frozen commit;
- fresh migration and supported old-baseline upgrade are green;
- real-backend Playwright is green;
- fixture drift audit is green;
- Windows installer/update VM matrix is green for agent release changes;
- two-worker/restart suite is green;
- live summary matches commit, deployed commit, environment, release run id and schema head;
- Observer baseline/delta/canary are green;
- no new active critical/high integrity events exist;
- no unexpected suppressions exist;
- public token is revoked/denied after closure;
- `TD-015` or equivalent multi-instance risk blocks horizontal scaling until actually resolved.

## 17 Critical Behavior Scenarios

| Scenario | Surface | Required live action |
|---|---|---|
| `requester_support_admin_session_switch` | requester | Login as requester/support/admin, switch sessions, verify no prior account data, revoke session and deny access. |
| `real_account_device_linking` | admin | Create/lookup pairing, confirm registration, approve binding, verify requester device view and agent state. |
| `requester_support_chat_roundtrip` | support | Create ticket, send requester/support messages, retry message, verify DB/timeline/no duplicates. |
| `admin_publish_requester_create` | requester | Admin publish form, requester select form, create ticket, verify form version/policy snapshot. |
| `support_queue_status_after_routing` | support | Create routed ticket, verify queue/status/SLA/OLA in UI/API/DB. |
| `requester_support_admin_search_visibility` | requester | Search as requester/support/admin, verify ACL and no support-only leak. |
| `requester_feedback_support_qa` | support | Resolve ticket, submit feedback, reopen, verify QA view privacy. |
| `admin_problem_support_link` | admin | Create similar tickets, generate problem candidate, link evidence, verify restricted field redaction. |
| `admin_change_approval_workflow` | admin | Create change, override risk with reason, approve/reject, rollback/PIR evidence. |
| `bounded_provider_canary` | support | Run diagnostic provider, verify evidence chain, versioned output and redaction. |
| `module_playbook_canary` | admin | Install module, live-test, set preferred, run playbook, verify step order and rollback evidence. |
| `tool_run_approve_deny_timeout` | operation_lifecycle | Real consent-required tool approve/deny/timeout/late decision/cancel. |
| `windows_linux_vm_agent_runtime` | native_agent | Restart/reconnect/replay/update rollback on Windows and Linux agents. |
| `non_production_remote_assist_session` | support | Request Remote Assist, requester consent, session start/end, artifact access and audit. |
| `admin_support_trace_drilldown` | admin | Trigger known traces, verify spans/redaction/integrity no business mutation. |
| `browser_totals_against_seeded_pack` | reports | Compare browser report totals with API and DB aggregates. |
| `canonical_stand_release_gate` | stand | Verify deployed commit/schema/service health/rollback markers/exact live summary. |

## Commands

Use these as the default command set, narrowing by phase where appropriate.

```powershell
.\scripts\bootstrap_shell_utf8.ps1
python scripts/verify_workspace.py
```

Dry-run browser scenarios:

```powershell
python scripts/run_live_behavior_suite.py `
  --pack test_data_packs/critical_behavior_v1.json `
  --surfaces requester,support,admin,reports `
  --dry-run `
  --json
```

Dry-run agent/operation scenarios:

```powershell
python scripts/run_live_behavior_suite.py `
  --pack test_data_packs/critical_behavior_v1.json `
  --mode agent-operation `
  --surfaces native_agent,operation_lifecycle,protocol_v3 `
  --dry-run `
  --json
```

Validate one manifest:

```powershell
python scripts/validate_live_evidence.py `
  --manifest artifacts/live/<run-id>/manifest.json
```

Build exact release summary:

```powershell
python scripts/build_live_release_summary.py `
  --pack test_data_packs/critical_behavior_v1.json `
  --live-root artifacts/live `
  --commit <release-commit> `
  --environment stand `
  --release-run-id <release-run-id> `
  --expected-schema-head <schema-head> `
  --output artifacts/live/release-summary.json `
  --markdown-output artifacts/live/release-summary.md
```

Preflight release candidate:

```powershell
python scripts/release_candidate_preflight.py `
  --workspace . `
  --commit <release-commit> `
  --environment stand `
  --expected-schema-head <schema-head>
```

## Source Map

Sources analyzed:

- `C:\Users\admin-2\Downloads\helpdesk_deep_audit_2026-06-25.md`
- `C:\Users\admin-2\Downloads\helpdesk_live_bug_detection_plan_2026-06-25.md`
- `C:\Users\admin-2\Downloads\helpdesk_remediation_observer_test_plan_2026-06-25.md`
- `C:\Users\admin-2\Downloads\helpdesk_remediation_observer_test_plan_2026-06-25 (1).md`
- `C:\Users\admin-2\.codex\attachments\47589abc-25dd-491b-a1e2-521ee6a533c3\pasted-text.txt`

The two remediation files are byte-identical by SHA-256, so they are counted as one unique remediation source.

Start from these files when implementing or verifying the deep-audit defect groups:

- Identity/session: `server/requester/identity_service.py`, `server/web_api/session_handlers.py`, `server/app/repos/ui_users_repo.py`.
- Registration and pairing: `server/app/repos/registration_repo.py`, `server/registry/browser_pairing_service.py`, `server/registry/account_session_service.py`.
- Agent auth and tokens: `server/websocket/agent_handshake.py`, `server/app/repos/auth_tokens_repo.py`.
- Ticket create/events/workflow: `server/tickets/create_flow.py`, `server/app/repos/ticket_events_repo.py`, `server/tickets/workflow_service.py`, `server/tickets/side_effects.py`.
- Public access: `server/tickets/public_access.py`, `server/tickets/public_ticket_handlers.py`.
- Web requester/support APIs: `server/web_api/requester_handlers.py`, `server/web_api/support_handlers.py`.
- Tools and operations: `server/tools/service.py`.
- Customer history: `server/customer_history/projection_service.py`.
- Agent update and packaging: `pc_agent/launcher/installer.py`, `pc_agent/build_windows_release.py`, `pc_agent/build_windows_release_v2.py`.
- UI tests and fixture drift: `webapp/playwright.config.ts`, `webapp/tests/fixtures/support_fixture_server.py`, `webapp/tests/requester-workspace.spec.ts`.
- Quality/live contracts: `quality/active_risks.json`, `test_data_packs/critical_behavior_v1.json`, `docs/TESTING_RULES.md`, `docs/LIVE_TESTING_DEBUG_RULES.md`, `docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md`, `server/docs/OBSERVER_LAYER.md`.

## Handoff

Next recommended execution slice:

1. Run Phase 0 as read-only baseline and create `known_bug_registry.current_head.json`.
2. Update the per-bug lifecycle table with Phase 0 statuses and sorted P0/P1 order.
3. Start Phase 1 Wave A from `ID-001` / `ID-002`; do not run broad live bug hunt yet.
4. After known P0/P1 fixes, produce `known_bug_fix_verification_summary.md`.
5. Only then harden live tooling and execute broad live bug hunt.

Do not append chat transcripts or raw logs here. Store detailed evidence under `artifacts/live/<release_run_id>/` and link concise results back into this plan.
