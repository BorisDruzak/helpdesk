# Helpdesk Live Bug Detection and Remediation Master Plan

> **For agentic workers:** execute this plan task-by-task. For implementation work use `superpowers:executing-plans` or `superpowers:subagent-driven-development`; keep this file updated after each meaningful checkpoint.

## Goal

Build a reliable bug-detection and remediation loop for the helpdesk system: live scenarios must execute real domain actions, every P0/P1 fix must have UI/API/DB/Observer/agent evidence where applicable, and release gates must reject shallow or stale proof.

## Current State

- **Status:** active planning reset on 2026-06-26.
- **Branch at plan creation:** `codex/helpdesk-process-model`.
- **HEAD at plan creation:** `489fe243db5c1845c7b8a2248e6fdff427728f0f`.
- **Scope classification:** cross-cutting. The plan spans webapp, server APIs, PostgreSQL, Observer, Protocol V3/agent runtime, live tooling, CI and release gates.
- **Plan source:** `PLANS.md` was intentionally cleared and rebuilt from the uploaded deep audit, live bug-detection plan and remediation plan.
- **Audit drift note:** the deep audit reviewed GitHub HEAD `a0b47ee1a28f8168c753c87aea913ab9287039e1`; this local plan was written at `489fe243db5c1845c7b8a2248e6fdff427728f0f`. Before changing code, verify each defect against the current local tree.
- **Release state:** not assumed green. Treat current release readiness as unknown until Phase 0 re-establishes exact commit, deployed commit, schema head, CI and live evidence.

## Sources Analyzed

- `C:\Users\admin-2\Downloads\helpdesk_deep_audit_2026-06-25.md`
- `C:\Users\admin-2\Downloads\helpdesk_live_bug_detection_plan_2026-06-25.md`
- `C:\Users\admin-2\Downloads\helpdesk_remediation_observer_test_plan_2026-06-25.md`
- `C:\Users\admin-2\Downloads\helpdesk_remediation_observer_test_plan_2026-06-25 (1).md`

The two remediation files are byte-identical by SHA-256, so they are counted as one unique source. The deep audit is the primary defect registry; the other two files translate it into live execution and remediation work.

## Decisions

- Live bug hunting must not start from broad manual clicking. First close the tooling gaps that can produce false `pass`.
- Fixture Playwright is useful for component and route regressions, but it is not live proof and must not publish `canonical_live_browser=true`.
- A scenario passes only when required evidence layers agree: browser/UI, API/transport, server DB, Observer trace/integrity, agent SQLite/logs when an agent participates, cleanup/contamination proof, and exact commit/schema/environment preflight.
- Observer is evidence and integrity monitoring, not the source of business truth and not an automatic business-state repair system.
- Every data-integrity fix must use a new `run_id`, fresh account/device/ticket markers and a clean post-fix rerun.
- `verified-fixed` is allowed only after canonical UI/API/DB/Observer/agent evidence, not after a single pytest.
- Release gates must fail on missing exact-context live summary, missing scenario manifests, mismatched commit/schema/environment, new critical/high Observer events, unexpected suppressions or open P0/P1 bugs.
- `device_link_code` validation during web registration is not itself a defect. The expected contract is account creation first and authenticated device-link confirmation later; the bug to test is any UI copy that falsely says the device is already connected.

## Non-Goals

- Do not run destructive cleanup against production-like data without an explicit backup/dry-run/survivor verification plan.
- Do not manually patch deployment mirrors.
- Do not treat `/ui/automation/run`, fixture mocks or direct HTTP calls as substitutes for browser-visible or native UIA proof.
- Do not enable self-registration broadly until the identity collision and verified-link audit is clean.
- Do not make Observer hide or auto-resolve real business defects.

## Key Findings From The Audits

| ID | Priority | Finding | Required Direction |
|---|---:|---|---|
| `LIVE-RUNNER-001` | P0 | Browser runner mostly loads pages and text markers, but does not execute domain actions. | Add action scenarios for ticket create, chat, status, assignment, consent, closure, reports and Observer drilldown. |
| `LIVE-RUNNER-002` | P0 | Manifest validator does not prove every `required_evidence` layer has a passing check. | Add `required_evidence`, `evidence_coverage` and per-layer pass enforcement. |
| `LIVE-RUNNER-003` | P0 | `surface=stand` for `canonical_stand_release_gate` is not scaffolded by evidence pack tooling. | Add `stand` support and a release-stand runner path. |
| `LIVE-RUNNER-004` | P0 | Operation lifecycle scenario is currently represented by malformed-outbox probe. | Build a real consent/operation lifecycle runner. |
| `LIVE-RUNNER-005` | P0 | Native agent scenario checks connected state only. | Add restart/reconnect/replay/update rollback evidence on Windows and Linux agents. |
| `LIVE-RUNNER-006` | P1 | Browser evidence lacks network/forensic linkage to backend outcome. | Capture HAR/network, target request/response digests, server request IDs, trace IDs and redaction report. |
| `LIVE-RUNNER-007` | P1 | Live runner has default credentials fallback. | Fail fast unless live credentials are explicitly provided through environment/config. |
| `LIVE-RUNNER-008` | P1 | Observer canary root-kind coverage is not scenario-specific enough for web-cabinet flows. | Require per-scenario root kinds such as `requester_web`, `ticket`, `tool_call`, `agent_auth`, `agent_runtime`, `agent_update`. |
| `LIVE-RUNNER-009` | P1 | Release summary is exact-context strict, but semantic depth depends on a weak validator. | Require pass assertions for every expected outcome from the behavior pack. |

## Primary Defect Registry From Deep Audit

The deep audit classifies findings as `static-confirmed`, `high-confidence`, `runtime-candidate`, `documented-risk` or repository evidence. Treat every item below as open until Phase 0 verifies whether it still exists at current local `HEAD`.

| Group | Defect IDs | Priority | Required first action |
|---|---|---:|---|
| Identity and Registry boundary | `ID-001`, `ID-002`, `AUTH-029`, `AUTH-030`, `ACCOUNT-033` | P0/P1/P2 | Verify web account to person resolution, case-insensitive login uniqueness, login length contract, lockout atomicity and unverified account behavior. |
| Public claim, public sessions and closure | `CLAIM-003`, `CLOSE-018`, `PUBLIC-AUTH-034` | P1 | Add pre-fix concurrent claim/public token evidence, then enforce CAS/row locks and deny-by-ticket-state. |
| Agent auth and pairing delivery | `AGENT-AUTH-004`, `PAIR-005`, `SESSION-006`, `TOKEN-031`, `PAIR-035` | P1/P2 | Prove handshake rebind/fingerprint atomicity and durable pairing/session delivery across restart and workers. |
| Ticket create and emergency/contact policy | `CREATE-011`, `CREATE-012`, `CREATE-013`, `CREATE-014` | P1/P2 | Add idempotency, typed degraded state, durable side effects and strict emergency contact validation. |
| Chat, events and timeline | `EVENT-007`, `EVENT-008`, `CHAT-009`, `CHAT-010` | P1/P2 | Replace mixed `agent_seq` UI ordering with cursor/keyset timeline, enforce event/message uniqueness and reject unknown visibility. |
| Workflow, assignment and queue/OLA | `WORKFLOW-015`, `WORKFLOW-016`, `WORKFLOW-017`, `ASSIGN-032` | P1/P2 | Add status CAS, assignment locks, invariant checks and queue/OLA reconciliation evidence. |
| Tools, modules, playbooks and consent | `TOOL-019`, `MODULE-020`, `CONSENT-021`, `PLAYBOOK-022`, `TOOL-038` | P1/P2 | Enforce start-event-before-dispatch, preserve initiating actor, require idempotency and close legacy execution gaps. |
| History and context | `HISTORY-023`, `HISTORY-024` | P1/P2 | Replace fixed latest-N scans with indexed direct relations and cursor pagination. |
| Support/admin degradation and query validation | `SUPPORT-025`, `SUPPORT-026` | P1/P2 | Distinguish DB outage from empty work, add degraded banners and typed query validation. |
| Agent install/update | `INSTALL-027`, `INSTALL-028` | P1 | Add atomic `current.json`, publish-failure DB restore and Windows installer/update VM proof. |
| Scaling/protocol risks | `SCALE-036`, `PROTOCOL-037` | P1 | Keep multi-instance blocked until process-local delivery/outbox/replay risks are resolved. |
| Test and release assurance | `TEST-039`, `TEST-040`, `RELEASE-041` | P0/P1 | Keep fixture UI separate from live proof, fix fixture drift and require fresh 17/17 exact-context live summary. |

Immediate guardrails from the deep audit:

- [ ] Keep `WEB_SELF_REGISTRATION_ENABLED=false` until `ID-001` and `ID-002` are fixed and migration audit is clean.
- [ ] Do not run multi-instance server deployment while process-local DeviceOutbox/session state remains an active risk.
- [ ] Treat release as blocked until all 17 critical scenarios have passing `pc_client.live_evidence.v2` manifests and exact release summary.
- [ ] Add a temporary fail-closed guard for unknown chat visibility before broader chat refactoring.
- [ ] Make public-session verification depend on ticket state as defense in depth.
- [ ] Reject high-risk dispatch when `tool_call_started`/outbox transaction is not persisted.
- [ ] Make support UI distinguish DB outage from an actually empty queue.
- [ ] Create bug records for the deep-audit IDs before changing implementation, with pre-fix evidence from `docs/LIVE_TESTING_DEBUG_RULES.md`.

## Execution Principles

1. Capture pre-fix evidence before changing code.
2. Keep P0/P1 auth, data-integrity, protocol and operation lifecycle fixes evidence-heavy.
3. Add negative permission tests for every auth/account/role boundary.
4. Prefer durable idempotency keys, explicit transaction boundaries and correlation IDs for mutating flows.
5. Keep all artifacts secret-free: no raw tokens, credentials, cookies, auth headers, public access codes, full private chat content or unredacted personal data.
6. If a live run hits a non-blocking issue, record it and continue. Stop only on the defined stop conditions.

## Phase 0 - Containment And Baseline

**Goal:** know whether the stand and data are safe enough for a bug hunt.

- [ ] Bootstrap shell UTF-8 and rebuild stale context index:
  `.\scripts\bootstrap_shell_utf8.ps1`
  `python scripts/build_context_index.py --force`
- [ ] Run task intake and focused context pack for the active slice:
  `python scripts/task_intake.py --task "live bug detection observer remediation"`
  `python scripts/build_context_pack.py --topic "live bug detection observer remediation"`
- [ ] Keep self-registration disabled until identity boundary audit is clean.
- [ ] Block multi-instance deployment in config/preflight until process-local outbox/session state is removed or explicitly proven safe.
- [ ] Record exact local commit, deployed commit, branch, expected schema head, actual schema head, environment and release run id.
- [ ] Collect a read-only DB report for:
  case-colliding UI logins, UI accounts without verified `ui_login`, ambiguous person-to-web-account links, closed tickets with active public sessions, consumed pairings without account session, approved login requests without deliverable secret, duplicate event/message IDs, `in_progress` without assignee, queue/OLA mismatch.
- [ ] Run baseline Observer integrity scan and record active/suppressed critical/high/error events.
- [ ] Dry-run the 17-scenario behavior pack and save command output.
- [ ] For every deep-audit defect ID that still reproduces on current `HEAD`, create a bug card with pre-fix evidence before code changes.

**Exit criteria:** collision/contamination state is known, rollback/cleanup approach is documented, and the team knows whether the stand is usable or blocked.

## Phase 1 - Live Tooling Must Stop False Green

**Goal:** make live evidence machine-verifiable before trusting scenario results.

**Likely files:**

- `scripts/run_live_behavior_suite.py`
- `scripts/live_evidence_pack.py`
- `scripts/validate_live_evidence.py`
- `scripts/build_live_release_summary.py`
- `webapp/scripts/live-browser-scenarios.mjs`
- New or refactored helpers for browser/API/DB/Observer/agent assertions, if the existing scripts cannot absorb the responsibility cleanly.
- `test_data_packs/critical_behavior_v1.json`
- `scripts/test_validate_live_evidence.py`
- `scripts/test_build_live_release_summary.py`
- `scripts/test_run_live_behavior_suite.py`
- `docs/LIVE_TESTING_DEBUG_RULES.md`

**Work:**

- [ ] Add `stand` surface support to evidence scaffold and release scenario handling.
- [ ] Add action-level browser runner support for form fill/select, ticket create, chat, internal/public support notes, status, assignment, queue changes, run tool/playbook, consent approve/deny, close/feedback/reopen, history/context/report/Observer pages.
- [ ] Add forensic browser output: screenshot, DOM assertion, console/page errors, failed network requests, target API request/response digests, server request IDs, idempotency keys, trace IDs and redaction summary.
- [ ] Add DB assertion output with redacted query digests for tickets, ticket events, operations, device outbox, registry bindings, account sessions, public sessions, SLA/OLA and history projections.
- [ ] Add Observer assertion output for trace list/detail, required root kinds, span/result consistency, integrity before/after and new critical/high/error deltas.
- [ ] Add agent assertion output for SQLite, action trace, logs, launcher/update files and UIA state.
- [ ] Extend manifests with `required_evidence`, `evidence_coverage`, `expected_outcomes` and `assertions[]`.
- [ ] Harden validator so a manifest fails when a required layer or expected outcome lacks a passing assertion or artifact.
- [ ] Remove live fallback credentials; live mode must fail unless credentials are explicitly configured.
- [ ] Ensure release summary rejects shallow manifests even when commit/environment/schema match.

**Exit criteria:** a shallow manifest for any critical scenario fails validation, and `canonical_stand_release_gate` can be scaffolded and summarized like the other scenarios.

## Phase 2 - First Live Bug Hunt

**Goal:** execute the behavior pack with real domain actions and create actionable bug cards.

**Canonical stand origin:** `https://192.168.100.17:9443`

**Before every run:**

- [ ] Create a unique `release_run_id`, for example `live-20260626-<commit7>-stand`.
- [ ] Create a unique scenario marker:
  `test_marker=<scenario_key>-<timestamp>-<short_uuid>`.
- [ ] Put the marker into safe ticket/message/custom-field/operation metadata and artifact names.
- [ ] Confirm target accounts/devices/forms: requester with completed profile and Windows primary agent, requester with Linux primary agent, incomplete-profile requester, no-primary-agent requester, support, admin, lab Windows agent and lab Linux agent.

**First 12 high-yield runs:**

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

**Bug card format:**

```yaml
bug_id: LIVE-YYYYMMDD-###
scenario_key:
surface:
priority: P0|P1|P2|P3
status: open|reproduced|root-cause-confirmed|fix-in-progress|verified-fixed|deferred
primary_layer:
secondary_layers:
expected:
actual:
repro_steps:
run_id:
ticket_id:
device_id:
operation_id:
trace_ids:
browser_evidence:
api_evidence:
server_db_evidence:
agent_sqlite_evidence:
logs_evidence:
observer_evidence:
contamination:
stop_condition_triggered: true|false
candidate_owner:
next_action:
```

**Pass/fail rules:**

- `fail` if a required layer is missing, browser/API/DB/Observer disagree, new critical/high/error Observer event appears, unexpected suppression appears, auth/account boundary is unclear, secrets leak into artifacts, cleanup is missing, replay creates duplicates, stale data lacks run marker, or commit/schema preflight mismatches.
- `blocked` if the stand is unreachable, deployed commit/schema head is unknown, required agent is offline, test account is missing, DB tunnel is unavailable, Observer scan is incomplete or contamination invalidates results.
- `pass` only if every required layer and expected outcome has a passing assertion, manifest validates, Observer canary passes, cleanup passes or is not applicable, no critical/high/error delta appears and exact release context matches.

## Phase 3 - Remediation A: Identity, Ownership, Pairing

**Goal:** close P0 account/person/device isolation and session delivery risks.

**Identity boundary:**

- [ ] Introduce `normalized_login` or a functional unique index on `lower(user_login)`.
- [ ] Normalize login before auth lookup and token subject creation.
- [ ] Remove fallback web-account resolution through email, Windows login or AD identity.
- [ ] Add durable verified web-account-to-person link.
- [ ] Route email/AD matches through claim/conflict flow.
- [ ] Align login max length across DTO, handler and DB.
- [ ] Make failed-attempt increments atomic.
- [ ] Migration must detect collisions, quarantine ambiguous accounts, backfill verified links and fail preflight on unresolved P0 collisions.

**Atomic ownership and public/session boundaries:**

- [ ] Use row locks or conditional updates for public ticket claim.
- [ ] Keep agent token, fingerprint and rebind checks in one transaction.
- [ ] Enforce device-scoped token max count with advisory lock or serializable transaction.
- [ ] Verify public sessions against revoked, expiry, ticket ownership and terminal-state policy.
- [ ] Make close/revoke atomic or enforce deny-by-closed-state defense in depth.

**Pairing/session delivery:**

- [ ] Model pairing states as `created -> browser_confirmed -> awaiting_approval -> approved_pending_delivery -> delivered -> consumed`.
- [ ] Do not consume before a deliverable session exists.
- [ ] Enforce one active pairing per device/purpose.
- [ ] Use a durable encrypted one-time token envelope.
- [ ] Make delivery claim atomic with `delivered_at IS NULL`.
- [ ] Prove polling works across workers and restarts.

**Exit criteria:** cross-account/profile/device/ticket/history matrix passes; two-worker pairing tests pass; self-registration can be enabled only after migration audit reports `0 unresolved critical collisions`.

## Phase 4 - Remediation B: Ticket Create, Timeline, Workflow

**Goal:** make ticket mutations idempotent, ordered and transactionally honest.

**Ticket create and event stream:**

- [ ] Add `Idempotency-Key` support for ticket create, messages, close/feedback/reopen, run tool/playbook, consent decision, assignment/status/queue mutation.
- [ ] Add durable idempotency storage with actor/scope, request hash, `in_progress/completed/failed`, response snapshot, TTL and unique scope/key.
- [ ] Add DB constraints for event/message IDs and agent event uniqueness.
- [ ] Use `ON CONFLICT` for server event insert paths.
- [ ] Separate agent replay ordering from UI timeline ordering.
- [ ] Add monotonic `timeline_seq` or robust keyset pagination.
- [ ] Add cursor pagination for ticket/event/history APIs.
- [ ] Convert routing/SLA/OLA side effects to durable outbox/reconciliation, not silent success.
- [ ] Ensure unverified accounts cannot receive `requester_person_id`.

**Workflow, assignment and closure:**

- [ ] Add or enforce `tickets.version`.
- [ ] Use CAS for status mutations.
- [ ] Row-lock assignment/load policy.
- [ ] Enforce `in_progress -> assignee required`.
- [ ] Keep queue/OLA changes transactional or visibly pending.
- [ ] Reject typed partial status for UI mutation unless explicitly designed.
- [ ] Give retryable side effects a durable execution ID.
- [ ] Make close, public-session revoke and closure event atomic.
- [ ] Use the same CAS model for auto-close, requester confirmation and reopen.

**Exit criteria:** real PostgreSQL concurrency suites pass; load dataset with more than 300 tickets, 1000 on-behalf links and 500 events passes API/UI assertions; mutation smoke kills CAS/lock/idempotency mutants.

## Phase 5 - Remediation C: Tools, Modules, Playbooks, Agent Update

**Goal:** prove the operation lifecycle from support click to agent result and update rollback.

**Operation lifecycle:**

- [ ] Canonical transaction order: `operation + tool_call_started + device_outbox + observer correlation -> commit -> sender dispatch`.
- [ ] High-risk tools fail closed.
- [ ] Preserve initiating actor attribution and store service principal separately.
- [ ] Require idempotency for tool/playbook runs and consent decisions.
- [ ] Add `approved_pending_dispatch` plus recovery worker for consent after dispatch outage.
- [ ] Show module owner conflict before run.
- [ ] Remove legacy execution paths or route them through the unified service.

**Agent installer/update:**

- [ ] Add update journal with phases and durable rollback marker.
- [ ] Use temp file, flush/fsync and atomic replace for `current.json`.
- [ ] Backup/restore DB for failures after verify/publish starts.
- [ ] Use SQLite online backup API.
- [ ] Add crash recovery for each intermediate phase.
- [ ] Formalize installer/portable deployment, signed artifacts, install/uninstall/repair contract and data directory ACL.

**Exit criteria:** every operation has an unbroken `operation_id -> command_id -> outbox_id -> trace_id -> result` chain; update success is confirmed only by new-version handshake, rollback only by previous-version handshake plus intact DB.

## Phase 6 - Support/Admin Truthfulness And UI Test Architecture

**Goal:** make UI states honest under backend failure and split fixture, real-backend, live and native-agent proof.

**Support/admin behavior:**

- [ ] DB outage returns explicit `503` or `200 degraded=true` with stale timestamp.
- [ ] UI shows a visible degraded/error banner and retry action.
- [ ] UI must not show zero counts as trustworthy when a source is incomplete.
- [ ] Query values are typed and bounded.
- [ ] Permission matrix is enforced for auditor/support/admin mutations.
- [ ] Invalid internal-note visibility fails closed and preserves draft text.
- [ ] Partial operation state is explicit if retained.
- [ ] Raw IDs remain secondary metadata.
- [ ] Console/network errors are captured for browser-visible checks.

**UI test projects:**

- `fixture-ui`: render, routing, component behavior, responsive and accessibility smoke; no release proof.
- `real-backend-e2e`: real PostgreSQL, Alembic migration, aiohttp server, React build, cookies/session/auth and real WS Protocol V3 simulator; API only for setup/cleanup.
- `live-stand-smoke`: canonical stand origin with unique marker, exact preflight, screenshots, network, DB and Observer evidence.
- `native-agent-uia`: launcher, tray, account gate, browser handoff, update progress, crash/rollback and native consent through UIA selectors.

**Exit criteria:** support UI cannot confuse backend failure with no work; P0/P1 UI scenarios have browser evidence plus backend/Observer proof.

## Phase 7 - Observer And Test Layer Expansion

**Goal:** make integrity gaps visible and prevent future shallow tests.

**New or expanded Observer checker sources:**

- `observer.identity_boundary`: `ui_login_case_collision`, `web_account_person_link_missing`, `web_account_person_link_ambiguous`, `external_identity_granted_without_verification`, `unverified_account_ticket_person_link`.
- `observer.registration_sessions`: `pairing_multiple_active`, `pairing_consumed_without_session`, `approved_login_request_secret_missing`, `account_session_delivery_duplicate`, `account_session_device_mismatch`.
- `observer.ticket_integrity`: `ticket_create_side_effect_incomplete`, `ticket_in_progress_without_assignee`, `ticket_queue_ola_mismatch`, `closed_ticket_active_public_session`, `ticket_multiple_terminal_events`, `ticket_event_duplicate_id`, `ticket_message_duplicate_id`, `ticket_timeline_non_monotonic`, `requester_history_projection_incomplete`.
- `observer.tool_lifecycle`: `tool_dispatched_without_started_event`, `operation_outbox_missing`, `tool_actor_attribution_mismatch`, `consent_approved_dispatch_missing`, `operation_terminal_result_missing`, `playbook_duplicate_execution_key`.
- `observer.agent_update_integrity`: `update_journal_incomplete`, `publish_failed_without_db_restore`, `current_pointer_invalid`, `handshake_version_not_confirmed`, `rollback_version_not_confirmed`.
- `observer.support_degradation`: `support_workspace_source_incomplete`, `support_empty_success_on_backend_error`, `support_summary_stale_without_banner`.

**Test layer expansion:**

- Unit/property: login canonicalization, profile field policy, FSM, idempotency request hashing, visibility enum, timeline cursor, update journal recovery.
- PostgreSQL integration: functional/partial indexes, row locks, CAS, two-session barriers, rollback, old-baseline migrations and partial migration retry.
- Multi-process: two server workers, approval on worker A and poll on worker B, outbox sender ownership, restart recovery.
- Protocol/agent: token validity, fingerprint mismatch, ACK after persistence/duplicate/no-op proof, malformed context NACK, terminal result replay, duplicate command handling and agent SQLite state.
- Fault injection: before/after DB write, after commit before HTTP/WS response, before outbox, after consent commit, during update pointer replace and during public token issuance.
- Load/boundary: 301 requester tickets, 1001 affected-person tickets, 501 mixed events, 2001 support tickets, 10k chat messages and malformed query values.
- Security: cross-account, cross-device, cross-queue, auditor mutation, support/admin permission matrix, self-registration abuse, public code throttling, CSRF/session cookie policy and redaction.
- Mutation smoke: login normalization, verified-link check, fingerprint check, CAS, public-session closed-state check, visibility validation, start-before-dispatch, event conflict handling and pairing one-time delivery CAS.

## Phase 8 - Release Gate

Release candidate is allowed only when:

- [ ] `python scripts/verify_workspace.py` is green.
- [ ] Plain full `python scripts/run_ci_suite.py` is green on the frozen commit.
- [ ] Fresh migration and supported old-baseline upgrade are green.
- [ ] Real-backend Playwright is green.
- [ ] Fixture drift audit is green.
- [ ] Windows installer/update VM matrix is green for agent release changes.
- [ ] Two-worker/restart suite is green.
- [ ] All 17 critical behavior scenarios have `status=pass`.
- [ ] Live summary matches commit, deployed commit, environment, release run ID and schema head.
- [ ] Observer baseline/delta/canary are green.
- [ ] No new active critical/high integrity events exist.
- [ ] No unexpected suppressions exist.
- [ ] Public token is revoked/denied after closure.
- [ ] No open P0/P1 bugs remain.
- [ ] TD-015 or equivalent multi-instance risk blocks horizontal scaling until actually resolved.

## Key Source Map

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
python scripts/task_intake.py --task "live bug detection observer remediation"
python scripts/build_context_pack.py --topic "live bug detection observer remediation"
python scripts/search_context_index.py "live evidence critical behavior observer remediation release summary" --profile contract
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

## Handoff

Next recommended execution slice:

1. Rebuild the context index because search reported stale entries.
2. Run Phase 0 as read-only baseline and record exact blockers.
3. Implement Phase 1 validator and evidence-pack hardening before accepting any live scenario as pass.
4. Execute the first 12 high-yield live runs and create bug cards.
5. Start remediation from P0 identity/account boundaries and operation lifecycle defects revealed by the live run.

Keep this file as the active source of truth. Do not append chat transcripts or raw logs here; store detailed evidence under `artifacts/live/<release_run_id>/` and link the concise result back into this plan.
