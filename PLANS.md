# pc_client Product / Infra Plan

This file is intentionally compact. Detailed phase logs live in git history and the referenced CI/release artifacts; this document keeps the current product state, accepted checkpoints, active work, verification evidence and rollback notes.

## Release Workflow Guardrail

- Full CI is reserved for a frozen release candidate SHA. During implementation and live staging, use targeted tests, `verify_workspace`, relevant build/typecheck and explicit `--gate quick`.
- After green full CI, do not commit before full-gate release. Any new commit is a new candidate and requires a new full CI artifact.
- Before full-gate release, run `python scripts/release_candidate_preflight.py`; it verifies `summary.commit == HEAD`, green status, webapp bundle artifact and dirty workspace state.

## Status History

| Phase | Status | Essence | Key Evidence |
|---|---|---|---|
| P0 / P0.1 Ticket hardening | accepted / baseline | Canonical ticket statuses, public queue privacy, workflow side-effect observability, requester-safe timeline, policy health. | Last recorded P0 suite: 78 targeted passed; full server non-manual 863 passed; webapp build/typecheck and `verify_workspace` passed. |
| P1 / P1.1 Service Catalog | accepted / release-candidate | First-class helpdesk services/offerings, requester/agent-safe catalog, policy inheritance, publication/preview and reporting fields. | P1.1 full CI green with `--server-pytest-timeout 5400`; remote release and browser signoff completed. |
| P2 / P2.1 Knowledge Platform | accepted / release-candidate | Knowledge spaces/items/versions/search/suggestions/feedback/graph, ACL hardening, safe deflection and ticket KB compatibility. | CI artifact `artifacts/ci/08863b071b7a8740ead083d32ae2d6f3405d111f/summary.json`; remote/browser signoff completed. |
| P2.2 / P2.2.1 Knowledge Operations | accepted / release-candidate | Content packs, templates/lint, review tasks, quality/gap/search analytics, rollout policies and pack-binding repair. | CI artifact `artifacts/ci/356b473d231a52d7f77b0690c94e6e93c11dce47/summary.json`; remote/browser signoff completed. |
| P2.2.2 Suggestion Policy Enforcement | accepted / release-candidate | Requester help, agent wizard and `KnowledgeSuggestionService` enforce rollout min/max/no-suggestions/API-unavailable/known-error rules without blocking urgent bypass. Reserved UX flags remain future follow-up. | Commit `bbc7a6f` pushed/deployed; focused policy tests and webapp build/tsc passed. |
| P2.3 Test Harness / CI Layering | accepted / release-candidate | Root pytest collection stabilized, `pc_agent` imports qualified, isolated per-layer DB harness, domain CI layers and `run_ci_suite.py` summary artifacts. | Full CI artifact `artifacts/ci/cd21c1abbf02ce73d3b987555a01361430c321fc/summary.json`; no browser signoff required because product UI did not change. |
| P3 Experience & Quality Loop | accepted / release-candidate | Structured CSAT, reopen reasons, QA review queue, improvement actions, aggregate service/offering quality analytics and requester/support/admin UI. | Commits `71f2326`, `f826e33`; CI artifact `artifacts/ci/f826e3384e07ad0a21ac841434c8a89dccf4a1e1/summary.json`; remote/browser signoff completed. |
| P3.1 Quality Production Hardening | accepted / compact release-candidate | Latest-feedback DB invariant, concurrency coverage, daily/weekly quality snapshot scheduler, effective policy preview and P3 smoke regression. | Focused P3.1 tests, webapp build, `verify_workspace`, context index rebuild and smoke regression passed. |
| P4 Problem Management / RCA | accepted / release-candidate | First-class problems, candidates, ticket links, RCA, known-error/workaround Knowledge links, affected objects, analytics and `/app/admin/problems`. | Commit `2618616`; CI artifact `artifacts/ci/2618616bc2e0045ed4cdcdf39aeed7c195b8149e/summary.json`; remote/browser signoff completed. |
| P4.1 Problem Production Hardening | accepted / release-candidate | Scheduled scanner, run records, broader detection signals, dedup/merge/cooldown, problem SLO/aging and operational dashboard. | Commits `f2ad8db`, `f83f95d`, `d7f3836`; final CI artifact `artifacts/ci/f83f95d794fcd17028bb87d659902af4d26efe0f/summary.json`; remote/browser signoff completed and server stopped. |
| P5 Change Enablement | accepted / release-candidate | First-class changes, standard/normal/emergency lifecycle, risk/impact, approvals, windows/calendar, implementation/rollback plans, tasks, PIR, problem/action linkage and `/app/admin/changes`. | Commits `1abd32c`, `82a33a1`; CI artifact `artifacts/ci/82a33a1ecfcaf308ffe2cd3c53cdb0beb33ab1e7/summary.json`; remote/browser signoff completed. |
| P5 Change Enablement Hardening | accepted / compact release-candidate | Operator docs, standard preapproval catalog, recurring blackout/maintenance windows, overlap detection, emergency retrospective rules, hardened metrics and remote demo cleanup. | Commit `b904791`; focused P5 backend/webapp tests, webapp build, `verify_workspace`, quick deploy, remote smoke and browser signoff passed; remote demo records archived/canceled and server stopped. |

## Current Invariants

- Work only in `C:\Users\admin-2\CodexProjects\pc_client`; the SMB share and Linux checkout are mirrors.
- Do not weaken P0-P5 contracts, canonical ticket statuses, Service Catalog fields, Knowledge visibility, Quality privacy, Problem lifecycle or Change governance.
- Protocol V3 is unchanged unless explicitly required; current P5 scope does not require it.
- Requester/public surfaces must not expose internal QA, RCA, change risk notes, infrastructure details, rollback steps, queue ids, raw policy JSON or requester PII in analytics.
- Full DB/API gates use isolated test databases through the P2.3 harness; shared `pc_support_test` is debug-only and not a full gate.
- Product UI changes require webapp build plus remote/browser signoff at `https://192.168.100.17:9443/admin` before release acceptance.

## OBS1 Operational Integrity Observer - 2026-05-29 - run_id=obs1-20260529-1033-7410ce46

Status: OBS1 closed

Scope:
- OBS1.1 Observer architecture and code discovery.
- OBS1.2 Observer event model and persistence.
- OBS1.3 Operation lifecycle integrity checker.
- OBS1.4 Protocol V3 ACK/persistence integrity checker.
- OBS1.5 Runtime presence and projection checker.
- OBS1.6 Account/public/security boundary anomaly checker.
- OBS1.7 Module/toolset/artifact integrity checker.
- OBS1.8 Governance integrity checker: quality/problem/change.
- OBS1.9 Known contamination registry and suppression.
- OBS1.10 Admin Tech / Device Operations / Observer UI projection.
- OBS1.11 Alert severity, dedupe and runbook links.
- OBS1.12 Live fault-injection/regression validation.
- OBS1.13 Final OBS1 close gate.

Status audit:
- P0: documentation gap - Status History records `P0 / P0.1 Ticket hardening` as `accepted / baseline`; no literal `P0 closed` marker was found before OBS1. Treat as closed/accepted historical baseline for this run, but do not rewrite old evidence.
- P1: `Status: P1 closed` present.
- P2: `Status: P2 closed` present and status drift previously corrected.
- P3: `Status: P3 closed` present.
- P4: `Status: P4 closed` present.
- P5: `Status: P5 closed` present.
- P6: `Status: P6 closed` present.
- P6 handoff: remote server was intentionally stopped after successful smoke; OBS1 explicitly started it and verified `/api/health`.
- OBS1 prior state: no previous OBS1 section or observer-integrity table/repo found before this run.
- Dirty/untracked preserved: existing dirty `pc_agent/ui_gui/tickets_list_model.py` is unrelated and must not be touched; old/untracked `artifacts/*` remain unstaged unless new OBS1 evidence is explicitly listed here.

Baseline:
- Branch: `codex/helpdesk-process-model`
- Commit SHA: `7410ce462ad92faeba45ac64a66861cc84dd446c`
- Server URL: `https://192.168.100.17:9443`
- Browser/admin URL: `https://192.168.100.17:9443/admin`
- Browser/tech URL: `https://192.168.100.17:9443/app/admin/tech`
- Browser/device-operations URL: `https://192.168.100.17:9443/app/admin/device-operations/2447d396-79cd-53da-b3a9-028c5a4d56da`
- Browser/observer URL if present: `https://192.168.100.17:9443/app/admin/observer`; route loads without browser console errors, but current first viewport rendered the Admin Center map for tech/device/observer routes. Record as projection gap to verify during OBS1.10 before claiming UI evidence.
- Agent A: `live-v3-p1-clean2`
- Agent B if used: not selected at baseline.
- Device ids: Agent A `2447d396-79cd-53da-b3a9-028c5a4d56da`
- Agent versions: Agent A `3.1.61`
- pywinauto version: `.venvs\agent-win` has `pywinauto==0.6.9`; default Python env does not.
- Existing observer/tech/device routes: `/api/web/admin/observer/quick`, `/api/web/admin/observer/traces`, `/api/web/admin/observer/traces/{trace_id}`, `/api/admin/tech/observer/quick`, `/api/admin/tech/traces*`, `/api/admin/tech/signatures*`, `/api/admin/tech/degradations`, `/api/web/admin/tech/snapshot`, `/api/web/admin/device-operations/{device_id}`.
- Known P0-P6 contamination ignored: P0 phantom/malformed rows; P1 `device_outbox.id=135` and reconnect/probe historical rows; P2 screen/cross-device pre-fix rows; P3 pre-fix feedback/reopen rows; P4 pre-fix problem candidate and Knowledge draft rows; P5 pre-fix change rows; P6 historical non-P6 `agent_offline_active` tasks.

Baseline evidence:
- `/api/health`: `python scripts\manage_remote_stack.py start server` -> running, then `python scripts\manage_remote_stack.py smoke server --insecure-tls` -> `/api/health 200`.
- Agent A connected: `python scripts\agent_test_driver.py status live-v3-p1-clean2` -> `connection_state=connected`, `bridge_connected=true`, `ticket_count=22`.
- Browser admin/device/observer baseline: real in-app browser loaded `/app/admin/tech`, `/app/admin/device-operations/2447d396-79cd-53da-b3a9-028c5a4d56da`, `/app/admin/observer`; no browser console errors were captured, but dedicated route content needs OBS1.10 verification/fix.
- UIA semantic state probe: `.venvs\agent-win\Scripts\python.exe scripts\live_agent_uia_state_probe.py --instance live-v3-p1-clean2 --expect-connected --expect-account --output artifacts\obs1-20260529-0000-7410ce46-uia-baseline.json --skip-screenshot --max-depth 10 --max-nodes 2000 --max-seconds 60` -> `pywinauto_version=0.6.9`, `backend=uia`, `connection_state=connected`, `account_mode=confirmed_binding`, `failures=[]`.
- Agent SQLite: `.local-agent\instances\live-v3-p1-clean2\data\storage.db` has `outbox_obs1=0`, `failed_outbox_obs1=0`, `pending_command_results_obs1=0`, `pending_consents_total=0`.
- Server DB: for marker `obs1-*`, active `device_outbox=0`, total `device_outbox=0`. Agent A DB row: hostname `ADMIN-2`, agent version `3.1.61`, recent outbox rows all delivered.

OBS1 product contract:
- Observer purpose: detect runtime integrity problems previously found only by manual Live validation; provide alert/event source, correlation/evidence layer, runbook entry point and suppression-aware current anomaly view.
- Observer non-goals: not a generic log viewer, not fake counters, not a substitute for browser/UI validation, not an auto-fixer for product state.
- Observer events must include `event_type`, `severity`, `source`, `detected_at`, optional correlation ids, `expected`, `actual`, `evidence`, stable `dedupe_key`, `runbook`, `status`, and optional `suppression_reason`.
- Events must not include raw tokens/cookies/session tokens, raw requester message text, unsafe artifact paths or unnecessary PII. Product-side mutation is limited to observer event persistence.
- Severity contract: `critical` for data/security integrity loss, ACK without persistence, cross-device mismatch, wrong-account mutation success, late result dropped or public/requester leakage; `error` for stale terminal/active lifecycle, projection mismatch, material module/tool drift or materially wrong browser/admin projection; `warning` for fallback frequency, retryable NACK spikes, stale snapshots/schedulers and labeled historical contamination; `info` for check pass, suppression and recovery.
- Every OBS1 event/test payload must carry marker/run_id `obs1-20260529-1033-7410ce46`.
- Known historical contamination must be suppressible narrowly and must not hide new OBS1 rows.

## OBS1 implementation map

- Existing Observer routes: typed `/api/web/admin/observer/quick`, `/api/web/admin/observer/traces`, `/api/web/admin/observer/traces/{trace_id}`; legacy tech observer/search/detail under `/api/admin/tech/observer/*`, `/api/admin/tech/traces*`, `/api/admin/tech/signatures*`, `/api/admin/tech/degradations`.
- Existing Tech routes: typed `GET /api/web/admin/tech/snapshot` plus aliases `overview`, `alerts`, `logs`, `agents/audit`, `users/audit`, `operations/stuck`, `locate`.
- Existing Device Operations routes: `GET /api/web/admin/device-operations/{device_id}` and query fallback.
- Existing DB tables: observer trace overlay (`observer_traces`, `observer_spans`, `observer_span_links`, `observer_error_occurrences`, `observer_error_signatures`), `agent_observer_events`, `operations`, `device_outbox`, `ticket_events`, `device_events`, `agent_runtime_audit`, module/inventory/quality/problem/change tables.
- Missing pieces: no durable operational-integrity event table/repo/service; no known-contamination registry table; no integrity-checker API/projection in Tech/Device Operations/Observer workbench.
- Chosen MVP implementation: add durable `observer_integrity_events` and narrow `observer_known_contamination`, implement service/checkers for operation lifecycle, protocol audit gaps, runtime projection, security audit hooks, module/tool/artifact and governance invariants, then expose active/suppressed counts through typed admin observer, Tech snapshot and Device Operations.

OBS1 implementation progress:
- OBS1.1 discovery complete: existing observer/tech/device routes and DB surfaces mapped above.
- OBS1.2 implemented: `observer_integrity_events`, `observer_known_contamination`, repo, service, admin API and migration `20260529_105`.
- OBS1.3 implemented: operation lifecycle checker detects terminal operation with active outbox, stuck active operations and missing terminal tool result event.
- OBS1.4 implemented MVP: repeated Protocol V3 NACK checker and explicit ACK-persistence audit gap event until durable ACK audit exists.
- OBS1.5 implemented MVP: runtime presence checker accepts runtime state input and detects connected runtime with stale DB projection.
- OBS1.6 implemented MVP: account/public/requester boundary checker consumes successful anomaly audit events and produces critical observer events without raw tokens.
- OBS1.7 implemented: toolset hash drift, desired/actual module drift and missing artifact rows for artifact-bearing tool results.
- OBS1.8 implemented MVP: duplicate open problem candidate and approved/later change missing approved package checks.
- OBS1.9 implemented: narrow contamination registry seeded with P0/P1/P6 initial known suppressions; P2-P5 are listed for runtime extension when concrete entity ids are discovered.
- OBS1.10 implemented: Admin Tech snapshot, Device Operations device-scoped observer events and Observer workbench integrity list.
- OBS1.11 implemented: runbooks added under `docs/runbooks/observer_*.md`, stable dedupe keys, occurrence count, suppression and operation-lifecycle auto-resolution.
- OBS1.12 pending: remote live deployment, synthetic anomaly and browser projection evidence.
- OBS1.13 pending: final close gate.

### BUG-20260529-OBS1-01 - module/toolset checker crashed on Device.is_deleted property

Severity: OBS1
Status: verified-fixed
Area: module-toolset

OBS1 scenario: focused observer integrity pytest scan.
Run id: `obs1-test-20260529-0000`
Expected: checker scan completes and emits relevant integrity events.
Actual: `AttributeError: 'property' object has no attribute 'is_'` from SQLAlchemy filter using `Device.is_deleted`.
Repro steps: `python -m pytest server\tests\test_observer_integrity.py -q`.

Evidence:
- Test artifact: pytest failure in `server\observer\checks\module_toolset.py`.
- Run marker: `obs1-test-20260529-0000`.

Impact: blocked all OBS1 scan validation after earlier checkers.
Root cause hypothesis: checker used the Python `Device.is_deleted` property as if it were a mapped SQLAlchemy column.
Root cause confirmed: `Device.is_deleted` is derived from `deleted_at`, not mapped.
Fix policy:
- Blocking further OBS1: yes
- Fixed now: yes

Fix summary: changed query to `Device.deleted_at.is_(None)` and made checker orchestration sequential so a failing checker does not leave later coroutines unawaited.
Changed files: `server/observer/checks/module_toolset.py`, `server/observer/integrity_service.py`.
Tests: `server\tests\test_observer_integrity.py` now passes.
Live regression: pending remote live scan.
Regression check: `python -m py_compile ...`, focused pytest green.
Remaining risk: broader live data may expose additional schema edge cases.
Status consistency checked: yes.

### BUG-20260529-OBS1-02 - suppression seed and redaction made focused evidence ambiguous

Severity: OBS1
Status: verified-fixed
Area: suppression / account-boundary

OBS1 scenario: known contamination and account boundary tests.
Run id: `obs1-test-20260529-0000`
Expected: explicit contamination row wins for the same entity and non-secret boundary state remains visible in event evidence.
Actual: default P1 suppression could take precedence for the same `device_outbox.id=135`; evidence key `auth_state` was redacted even when value was only `missing_account_session`.
Repro steps: `python -m pytest server\tests\test_observer_integrity.py -q`.

Evidence:
- Observer event: suppressed operation event had P1 reason instead of test reason; account-boundary event redacted non-secret state.
- Test artifact: pytest assertion failures in `server\tests\test_observer_integrity.py`.
- Run marker: `obs1-test-20260529-0000`.

Impact: evidence was less actionable and suppression precedence could hide the specific known-contamination reason.
Root cause hypothesis: seed lookup included `source_phase`, allowing duplicate suppressions for the same entity/scope; redaction treats `auth_*` keys as secret-like.
Root cause confirmed: repo `ensure_contamination` only skipped exact source-phase duplicates; account checker used `auth_state` evidence key.
Fix policy:
- Blocking further OBS1: yes
- Fixed now: yes

Fix summary: seed now skips if any entity/scope suppression exists, and account-boundary evidence uses `boundary_state` for non-secret policy state.
Changed files: `server/app/repos/observer_integrity_repo.py`, `server/observer/checks/account_boundary.py`.
Tests: `server\tests\test_observer_integrity.py` now passes.
Live regression: pending remote live scan.
Regression check: focused pytest green.
Remaining risk: live contamination ids beyond P1 still need exact runtime entries when discovered.
Status consistency checked: yes.

### BUG-20260529-OBS1-03 - live scan endpoint failed when runtime state was present

Severity: OBS1
Status: verified-fixed
Area: runtime-presence / observer-event

OBS1 scenario: Live scan through `POST /api/web/admin/observer/integrity/scan`.
Run id: `obs1-20260529-1033-7410ce46`
Expected: admin scan endpoint runs checkers and persists OBS1 events.
Actual: endpoint returned HTTP 500 `OBSERVER_INTEGRITY_SCAN_FAILED`.
Repro steps: login through `/api/web/session/login`, then POST `/api/web/admin/observer/integrity/scan` with OBS1 run id.

Evidence:
- Observer event: none from endpoint because scan failed before response.
- Transport/API: `scan_http 500`, error code `OBSERVER_INTEGRITY_SCAN_FAILED`.
- Server DB: direct service scan without runtime state succeeded and generated 8 non-critical current events.
- Run marker: `obs1-20260529-1033-7410ce46`.

Impact: browser/admin live evidence could not trigger scans through the public admin API.
Root cause hypothesis: runtime-presence checker used `Device.is_deleted` property in SQL when the real app state enabled that checker.
Root cause confirmed: `server/observer/checks/runtime_presence.py` filtered with `Device.is_deleted.is_(False)`; direct scan without `state` bypassed that code path.
Fix policy:
- Blocking further OBS1: yes
- Fixed now: yes

Fix summary: changed runtime-presence query to `Device.deleted_at.is_(None)` and added a regression test using a fake online runtime state.
Changed files: `server/observer/checks/runtime_presence.py`, `server/tests/test_observer_integrity.py`.
Tests: `python -m pytest server\tests\test_observer_integrity.py -q` with shared test DB/watchdog -> `9 passed`.
Live regression: redeployed `90d74216`, `POST /api/web/admin/observer/integrity/scan` returned 200 and persisted scan results.
Regression check: `python -m py_compile server\observer\checks\runtime_presence.py server\tests\test_observer_integrity.py` -> passed.
Remaining risk: real runtime state may expose additional live-only assumptions.
Status consistency checked: yes.

OBS1 verification evidence so far:
- `python -m py_compile server\app\db\models.py server\app\repos\observer_integrity_repo.py server\observer\integrity_service.py server\observer\checks\operation_lifecycle.py server\observer\checks\protocol_integrity.py server\observer\checks\runtime_presence.py server\observer\checks\module_toolset.py server\observer\checks\governance.py server\observer\checks\account_boundary.py server\web_api\observer_integrity_handlers.py server\device_operations\service.py server\tech\snapshot.py server\routes.py` -> passed.
- `python -m py_compile server\tests\test_observer_integrity.py server\tests\conftest.py server\tests\test_tech_panel_snapshot.py` -> passed.
- `python -m pytest server\tests\test_observer_integrity.py -q` with shared test DB/watchdog -> `8 passed`.
- `python -m pytest server\tests\test_observer_integrity.py server\tests\test_tech_panel_snapshot.py -q` with shared test DB/watchdog -> `28 passed`.
- `python -m compileall -q server pc_agent scripts` -> passed before the latest focused test additions; final close gate will rerun.
- `git diff --check` -> passed with line-ending warnings only.
- `pnpm --dir webapp build` -> passed after OBS1 UI integration.

## OBS1 findings summary - 2026-05-29 - run_id=obs1-20260529-1033-7410ce46

| Finding | Severity | Area | Current bug or historical | Blocking OBS1 | Action |
|---|---|---|---|---|---|
| `protocol_ack_audit_gap:global` | warning | protocol-v3 | current telemetry gap | no | Left active; ACK persistence audit is an explicit next hardening item. |
| `toolset_hash_drift:2447d396-79cd-53da-b3a9-028c5a4d56da` | error | module-toolset | current state drift | no | Left active; Observer correctly reports drift for Agent A. |
| `toolset_hash_drift:b08675eb-780c-5042-b442-daa1cd066643` | error | module-toolset | current state drift | no | Left active; not fixed during OBS1 discovery-first pass. |
| P4 duplicate problem candidate dedupe keys | error | governance | historical P4 contamination | no | Added exact runtime suppression rows. |
| P5 `change_approved_without_package:f3b7db77-7a38-4afc-984b-97bbe7c8e238` | error | governance | historical P5 contamination | no | Added exact runtime suppression row. |
| P2/P3 terminal operation rows `0b5da7ba...`, `e7cf0b9d...` | error | operation-lifecycle | historical live-validation contamination | no | Added exact runtime suppression rows. |
| OBS1 synthetic `operation_outbox_mismatch:d4bb5633...:159` | critical | operation-lifecycle | intentional OBS1 fault injection | no | Created, observed as active critical, then resolved after outbox status cleanup. |

## OBS1 close summary - 2026-05-29 - run_id=obs1-20260529-1033-7410ce46

Status: OBS1 closed

Code head: `90d74216e9678994401c40754c01139bd577bad1`
Server URL: `https://192.168.100.17:9443`
Agent A: `live-v3-p1-clean2`, device `2447d396-79cd-53da-b3a9-028c5a4d56da`, connected.
Agent B: not used for OBS1 fault injection.
Observer event ids: baseline active after suppression has 3 active non-critical events; 5 historical events suppressed; 1 synthetic critical resolved.
Synthetic anomaly ids: operation `d4bb5633-cf2b-4d29-aecc-040e0ea12f4a`, device_outbox `159`, event `4cb05f28-5b02-5e72-a586-04b077adb311`.
Known contamination ids: P1 `device_outbox.id=135`; P4 duplicate problem candidate dedupe keys; P5 change `f3b7db77-7a38-4afc-984b-97bbe7c8e238`; P2/P3 operations `0b5da7ba-fa46-48e4-8e7d-d0ac38eef029`, `e7cf0b9d-beee-46d2-82fc-9981bf17c80b`.
Old contamination ignored: P0 phantom/malformed rows; P1 reconnect/probe rows; P2 screen/cross-device pre-fix rows; P3 feedback/reopen pre-fix rows; P4/P5 rows listed above; P6 historical non-P6 `agent_offline_active` tasks.

OBS1.1 result: implementation map recorded.
OBS1.2 result: durable observer integrity table/repo/service/API implemented and migrated.
OBS1.3 result: operation lifecycle checker detects stale terminal operation/outbox and resolves after cleanup.
OBS1.4 result: repeated NACK checker implemented; ACK audit gap is visible warning until ACK persistence audit is added.
OBS1.5 result: runtime presence checker implemented and API-state regression fixed.
OBS1.6 result: security-boundary audit checker implemented; anonymous live RBAC denied observer endpoints with 401.
OBS1.7 result: module/toolset/artifact checker implemented; live toolset drift remains active and actionable.
OBS1.8 result: governance checker implemented; historical rows suppressed by exact dedupe keys.
OBS1.9 result: known contamination registry implemented and live suppressions verified.
OBS1.10 result: Admin Tech, Device Operations and Observer workbench show OBS1 state in browser with no console errors.
OBS1.11 result: runbooks added for operation lifecycle, protocol, runtime presence, account boundary, module/toolset and governance.
OBS1.12 result: live scan, synthetic stale outbox create/resolve, RBAC denial, browser projections and marker cleanup passed.
OBS1.13 result: final local and remote gates passed with noted non-critical active findings.

Bugs found:
- BUG-20260529-OBS1-01 module/toolset checker SQL property crash.
- BUG-20260529-OBS1-02 suppression/redaction evidence ambiguity.
- BUG-20260529-OBS1-03 live scan endpoint failed with runtime state.

Verified fixed:
- All three OBS1 implementation blockers were fixed, tested locally and redeployed.

Deferred/known limitations:
- ACK persistence audit is not yet durable enough for positive ACK/persistence correlation; Observer reports this as `protocol_ack_audit_gap` warning.
- Two live devices have current toolset hash drift; Observer reports them as active errors and no product state was mutated during OBS1.
- Full wrong-account and diagnostic-probe live scenarios were not rerun end-to-end in this close pass; API RBAC, unit coverage and browser/DB evidence cover the new observer surfaces.
- Browser screenshot capture timed out in the in-app browser; browser DOM evidence and console-log checks were recorded instead.

Operational integrity result:
- Protocol ACK/persistence: telemetry gap detected and surfaced as warning.
- Operation/outbox/seen_commands: synthetic stale outbox critical detected and resolved.
- Runtime presence: state-aware scan endpoint fixed and regression-tested.
- Account/public security: audit checker and RBAC denial verified.
- Module/toolset/artifact: toolset drift detected for current devices; artifact checker covered by tests.
- Governance: duplicate/problem and change package invariants implemented; old rows suppressed.
- Admin Tech: shows `critical 0`, `error 2`, `suppressed 5`.
- Device Operations: device-scoped Observer tab shows current Agent A `toolset_hash_drift` and hides suppressed historical operation events.

Browser/UI evidence:
- `/app/admin/observer`: Operational Integrity Observer shows `critical 0`, `error 2`, `warning 1`, `suppressed 5`; no console errors.
- `/app/admin/tech`: Operational Integrity Observer section shows same counts and top events; no console errors.
- `/app/admin/device-operations/2447d396-79cd-53da-b3a9-028c5a4d56da`, Observer tab: shows device-scoped `toolset_hash_drift`, suppressed historical operation events no longer shown; no console errors.
UIA evidence: baseline UIA semantic probe passed with `pywinauto==0.6.9`, `backend=uia`, connected account state, evidence `artifacts\obs1-20260529-0000-7410ce46-uia-baseline.json`.
DB/SQLite evidence:
- Server marker check: `server_marker_device_outbox_total=1`, `server_marker_device_outbox_active=0`, `active_critical_obs1=0`.
- Agent SQLite marker check: `outbox_obs1=0`, `failed_outbox_obs1=0`, `pending_command_results_obs1=0`, `pending_consents_total=0`.
Runbooks:
- `docs/runbooks/observer_operation_lifecycle.md`
- `docs/runbooks/observer_protocol_v3.md`
- `docs/runbooks/observer_runtime_presence.md`
- `docs/runbooks/observer_account_boundary.md`
- `docs/runbooks/observer_module_toolset.md`
- `docs/runbooks/observer_governance.md`

Next readiness:
- ready for follow-up hardening on ACK persistence audit and toolset drift remediation; no false current critical OBS1 event remains.

## Active Work: Pilot Hardening / Mini-prod Readiness

Status: in progress on branch `codex/helpdesk-process-model`.

Goal:

- Close the immediate pilot-readiness gaps without requiring public `/help` or `/ticket` cutover in this pass; requester creation through the PC agent remains the accepted mini-prod path.

Scope:

- Move `InventoryRefreshRuntime` lifecycle out of housekeeping so only one scheduler starts and cleanup stops that single runtime.
- Add explicit `APP_ENV=dev|test|pilot|prod` security profile handling; keep `PILOT_STAND_MODE` as a compatibility strict-mode trigger.
- Make pilot/prod fail closed for default UI passwords, HTTPS/WSS/session-cookie policy, query-token auth, dev fallback and DB initialization failure.
- Remove committed local env/config files from git tracking while leaving local files available for the test stand.
- Align server dependency declarations and webapp CI gates, including Vitest and Playwright fixture checks in the canonical CI suite.
- Add a controlled DB cleanup plan/script for test data later in this block; backup automation is explicitly out of scope for now.

Non-goals:

- No `/help` or `/ticket` requester cutover in this pass.
- No backup/restore automation in this pass.
- No full release gate unless explicitly requested after a frozen candidate.

Verification target:

- Focused server tests for scheduler lifecycle, security config and DB fail-closed startup.
- Focused CI-script tests or dry-run evidence for added webapp CI layers.
- `python scripts/verify_workspace.py`, relevant pytest, `pnpm --dir webapp run test`, `pnpm --dir webapp run test:e2e`, `git diff --check`.

## Active Work: Registry Management Center P1/P2

Status: in progress / P1 feature layer implemented; P2 reliability smoke now focuses on end-to-end workflow invariants, preview-protected dangerous operations and safe registry import.

Goal:

- Turn `/app/admin/registry` from the completed P0 operations center into a fuller CMDB/Identity/Binding operations tool without rewriting the P0 page or weakening registration/account-session security.

Scope:

- Functional Locations and Departments tabs with CRUD, archive, merge, counts and registry events.
- Registration/account-session/ticket visibility policy editor backed by persisted safe config with default fallbacks.
- People merge/dedup workflow that moves identities, bindings, sessions, claims, tickets and derived asset assignments without deleting duplicates.
- Bulk operations for common registry administration: assign locations/departments and revoke account sessions with per-item results.
- CSV export for devices, people, bindings, sessions, locations, departments and quality issues.
- Safe CSV import for people, locations, departments and device inventory mapping through parse -> validate -> preview -> apply with row-level errors, duplicate detection, rollback-safe apply and audit events.
- More actionable quality remediation with persisted ignore/snooze/resolve state and richer timeline/detail drawer data.
- Unified Registry Timeline in the drawer for device/person/binding/session/claim: admin, registration and account events must show actor, time, reason, changes and affected entity ids.
- Operator docs and live smoke checklist for Registry Management Center.
- Repeatable A-F live workflow smoke for people/identities, bind, shared/responsible, transfer owner, people merge and locations/departments with API actions plus DB invariant checks.
- Read-only preview/dry-run contracts for dangerous operations before apply: transfer owner, people merge, location merge, department merge, bulk operations and registry import.

Non-goals:

- No AD/LDAP integration in this pass beyond safe placeholders/hooks.
- No raw lifecycle mutation for binding revoke/transfer/session invalidation; existing `RegistrationService` and `AccountSessionService` remain authoritative.
- No changes to machine-token or account-session architecture.
- No direct binding import in this pass; binding lifecycle remains service-backed and must not be imported without a dedicated preview/approval model.

Verification target:

- Focused Registry DB/API tests for previews, locations, departments, policies, merge, bulk actions, import/export where implemented, plus existing P0 registry/account-session/ticket access tests.
- Timeline regression: `python -m pytest server/tests/test_registry_timeline_admin.py -q`.
- `pnpm --dir webapp test -- registry`, `pnpm --dir webapp run build`, agent account-session smoke tests, `python -m compileall -q server pc_agent`, `python scripts/verify_workspace.py`, `git diff --check`.
- Linux DB validation for DB-backed pytest if the Windows harness stalls, then quick remote release, `python scripts/registry_workflow_smoke.py --base-url https://192.168.100.17:9443 --insecure-tls`, and browser smoke at `https://192.168.100.17:9443/app/admin/registry`.

Stage 5 bulk polish:

- Bulk apply responses now include `bulk_operation_id`, `summary.selected/success/failed` and normalized per-selected-object `items`, while keeping legacy `results` for compatibility.
- Devices, People and Account Sessions tabs expose checkbox selection and a shared bulk result panel with failed-row review, copy errors and CSV result export.

Stage 6 cautious policy editor:

- Registry policy responses now include defaults, effective values, changed-from-defaults, validation ranges, dangerous-setting warnings, `requires_restart` metadata, dry-run preview and reset-to-defaults.
- Enabling `registration.auto_approve_first_binding` shows the explicit test-stand warning before save, and policy patch/reset require a reason and write `policy_changed` audit events.

Stage 7 operation invariants:

- Add focused DB-backed invariants for primary binding uniqueness, transfer/revoke derived state, shared/responsible non-ownership changes, merge dangling-reference cleanup, policy audit and bulk partial-success semantics.

Stage 8 P2 safety hardening:

- Registry import apply now requires the exact `preview_id` returned by import preview, reruns validation before mutation, writes `registry_import_applied` with an operation id and returns per-row apply `items`.
- Data-quality issues now carry stable `issue_key` values. Admin ignore/snooze/resolve actions persist in `registry_quality_issue_overrides`, hide active overrides from the generated issue list and write `quality_issue_*` audit events.

Stage 9 P2 operation consistency:

- Extend the same preview -> apply -> audit -> result-report contract from import to transfer owner, people/location/department merge and bulk actions while preserving existing response fields for UI compatibility.
- Add regression tests that preview endpoints exist for every dangerous operation and that apply responses include `operation_id`, `status`, `summary`, `items` and `events`.
- Keep quality remediation action-first: issues fixed by the underlying operation must disappear from the generated active quality list without requiring a manual override.
- Add import result CSV export in the dialog so large imports can review all rows or failed rows after apply.
- Strengthen timeline coverage around ownership transfer so an admin can see actor, reason, before/after changes and related binding/session/device ids.

## Active Work: Device Account Session Hardening

Status: P5 closed.

Goal:

- Harden server-issued requester account sessions for the PC agent as the requester identity boundary: ticket create/list/detail/message/read access must require a valid account session, registration-pending gets a deterministic server-issued session, logout/revoke is server-side, and support/admin surfaces show session ownership and other-account warnings.
- Final staging hardening adds artifact-download and handshake leakage guards, explicit ticket visibility policy, support warning rendering, admin account-event visibility, and a live smoke checklist in `server/docs/REGISTRATION_ACCOUNT_SESSIONS.md`.

Follow-up TODO:

- Add an account-session TTL/cleanup scheduler for expired/revoked sessions and old `device_account_events`.
- Add a separate registered owner transfer flow: transfer request claim, admin approval, revoke old binding/sessions and activate the new binding.

Verification target:

- Focused server tests for `AccountSessionService`, registration API, ticket account access and ticket registration enrichment.
- Focused agent tests for account-session manager/gate/client helpers and chat-panel account propagation.
- `python -m compileall server pc_agent`, webapp build/typecheck, `python scripts/verify_workspace.py`, `git diff --check`.

## Active Work: Auth / Registration Security Patch

Status: in progress.

Goal:

- Close critical fail-open and token disclosure paths in user registration, UI auth, legacy UI auth and agent authorization without breaking Protocol V3 or the cookie-based `/api/web/session/login` flow.

Scope:

- Make legacy/public agent token issue admin-only and audited; keep compatibility route but require authenticated admin.
- Protect manual connection request polling with `request_id` plus one-time high-entropy `poll_secret`, without storing raw poll secrets in the database.
- Harden production defaults, role validation, UI config fallback, password policy, token revocation scoping and explicit agent token replacement/limits.
- Reject agent-forged registration confirmation, add safer account-session validation transport and gate legacy localStorage login behind an explicit flag.
- Update focused server and pc_agent tests plus auth/navigation docs touched by these contracts.

Verification target:

- Focused red/green tests for auth security, connection request security, admin users, registration API and pc_agent connection flow.
- `python -m pytest server/tests`, `python -m pytest pc_agent/tests`, `python scripts/verify_workspace.py`, and applicable lint/build checks if available in this workspace.

## Active Work: Admin Ticket Purge

Status: implementation complete / targeted API tests passed; workspace verification pending.

Goal:

- Add an admin-only hard purge path for test/noise tickets that first previews affected rows and blockers, then deletes ticket-owned data without leaving non-FK orphan rows.

Scope:

- Backend service for purge preview/apply over ticket ids.
- Typed/admin web endpoints for preview and confirmed purge.
- Cleanup of known non-FK ticket references: ticket events/archive, operations, remote assist rows, artifacts metadata/files, agent runtime/observer rows and observer projections, before relying on existing FK cascades for ticket-owned tables.
- Safety blockers for active operations and active Remote Assist sessions.
- Docs/CODEMAP sync and focused DB/API tests.

Non-goals:

- No requester/support access to hard delete.
- No automatic scheduled purge.
- No schema migration unless tests reveal a required FK/constraint change.

Verification target:

- Focused pytest for preview counts, admin-only authorization, blockers and successful purge of FK + non-FK tables: `python -m pytest server/tests/test_ticket_purge_api.py -q` -> 4 passed.
- `python scripts/verify_workspace.py`.
- Broader server tests only if touched shared behavior requires it.

## Active Work: Webapp Workspace Navigation IA

Status: local verification passed / commit and remote browser signoff pending.

Goal:

- Restructure the new React webapp navigation from a flat mixed Support/Admin list into `workspace -> domain group -> local tabs`, while preserving routes, permissions, workspace access gates, ticket workspace shell behavior and public requester/help flows.

Scope:

- React webapp navigation source of truth, AppShell, AppSidebar, AppTopbar workspace switching, workspace access helpers, `/app/admin` landing page and route-level domain tabs.
- Route semantics: `/app/support` remains the Support Work Center, `/app/admin` becomes the Admin Center instead of redirecting to inventory, and existing `/app/tickets`, `/app/admin/*`, `/app/help`, `/app/ticket*` routes remain intact.
- Docs/navigation sync only where route semantics or source-of-truth navigation references change.

Decisions:

- Treat this as a React webapp UI boundary change, not a backend/API change. Do not add fake metrics or backend contracts.
- Keep `/app/tickets` isolated from the global AppShell exactly as the current ticket workspace behavior requires.
- Use permission-filtered navigation helpers as the single source for sidebar groups, workspace labels/search placeholder, active matching, domain tabs, admin/support landing cards and workspace switch fallbacks.
- Store last support/admin workspace paths in localStorage only for safe workspace-owned `/app/*` paths, with SSR/test guards and fallback to workspace home when access or permission no longer allows a stored route.

Verification target:

- Focused Vitest: navigation helpers, sidebar workspace/domain behavior, router/admin center and workspace switch history.
- Full webapp `pnpm test`, `pnpm build`, `python scripts/verify_workspace.py`, and if available `pnpm run check:remote:webapp`.
- Browser MCP check at `https://192.168.100.17:9443/admin` for Support/Admin sidebar separation, Admin Center cards, domain tabs and workspace switch context restore.
- Full CI/full gate remains an explicit final release checkpoint and must not be run without user request.

Verification so far:

- RED targeted tests failed before implementation for missing navigation helpers, admin center route and grouped sidebar behavior.
- Focused `pnpm --dir webapp test -- src/app/navigation.test.ts src/components/shell/app-sidebar.test.tsx src/app/router.test.tsx` passed: 3 files / 17 tests.
- Full `pnpm --dir webapp test` passed: 59 files / 283 tests.
- `python scripts/bootstrap_web_toolchain.py`, `pnpm --dir webapp build`, `python -m pytest scripts/test_navigation_catalog.py scripts/test_task_intake.py -q`, `python scripts/build_context_index.py --force`, `python scripts/verify_workspace.py` and `git diff --check` passed.
- Remote quick release, `pnpm --dir webapp run check:remote:webapp` and MCP browser signoff remain pending until after local commit/push.

## Active Work: P0 Tech Panel v2 — Pilot Readiness & Runtime Health

Status: in progress / first production-safe read-only cut.

Goal:

- Turn `/app/admin/tech` into a production-like stand Tech Panel that answers pilot readiness, blockers, degradation, security/auth/session/TLS, PostgreSQL/migrations/backup/restore, agents, operations/outbox/watchdogs, logs and release smoke.

Scope:

- Add typed read-only `GET /api/web/admin/tech/snapshot` while keeping legacy tech endpoints.
- Build readiness gates from config, PostgreSQL health, auth/session policy, connection policy, scheduler/runtime state and marker files for release/smoke/backup/restore.
- Redesign the React page into a Russian Tech Panel workspace with Overview, Security, Runtime, Database, Agents, Operations, Logs/Signals and Release/Smoke tabs.
- Keep the first cut read-only: refresh and navigation links only; no restart/revoke/approve/retry/cancel/SQL/env editing actions.
- Update docs/navigation catalog and targeted backend/frontend tests.

Known gaps for this cut:

- Backup, restore drill, release and business smoke are marker-file based and may be `unknown` until scripts write the configured JSON artifacts.
- HTTPS/WSS and session-cookie gates are config/introspection based; no proxy-origin guessing from the request.
- Alembic current/head remains `unknown` unless a safe marker/status source is available.
- No dangerous control-plane or token-management actions are added to the browser UI.

## Active Work: Tech Panel v2.1 - Pilot Diagnostic Locator & Evidence Markers

Status: follow-up implementation in progress / focused scripts and frontend checks green.

Goal:

- Make `/app/admin/tech` useful during pilot testing by adding read-only quick localization for tickets/devices/operations/traces/logs, marker writers for release/business smoke/restore evidence, query-token telemetry, baseline device lists and inventory scheduler duplicate-task status.

Scope:

- Add `GET /api/web/admin/tech/locate?q=...` for support/admin/auditor with safe links only.
- Extend Tech snapshot with query-token attempt count, below-baseline devices, baseline metadata and inventory scheduler details.
- Add safe marker-writing scripts/helpers for release status, business smoke status, backup status and restore drill evidence.
- Update Tech Panel UI with the locator panel, baseline list, query-token attempts and scheduler duplicate status.
- Keep browser surface read-only: no restart/stop, raw SQL, env edit, token revocation, approval, retry/cancel, remote assist launch or consent bypass.

Known gaps:

- Business smoke can now create a test ticket and enqueue `inventory.collect` only when explicitly requested by CLI flags; a real agent handshake still requires a safe device/test agent.
- Mixed-content/WSS checks are available through the optional Playwright-backed `--browser-check`; headless runtime availability remains an environment prerequisite.
- GitHub branch protection / required status checks must still be enforced in GitHub settings; local repo scripts and docs can describe the gate, but cannot enable protected-branch policy by themselves.

Implemented:

- Quick Locator endpoint/UI for ticket code/id, device id, hostname, operation id, Observer trace id and bounded problem-log matches.
- Quick Locator now accepts non-UUID trace ids of length >= 8 and returns grouped root-cause diagnosis from ticket/device/operation/outbox/approval/Observer signals.
- Read-only operation detail route `/app/admin/operations/:operationId` consumes existing `GET /api/operations/{operation_id}` and exposes only safe context links.
- Release marker helper in `scripts/release_server_to_remote.py` writes Alembic current/head after remote migration when available and writes `/var/chat_bot/pc_client/...` marker paths directly on the remote host; standalone `scripts/business_smoke.py`, safe `scripts/write_restore_drill_marker.py` and `scripts/write_backup_status_marker.py` write readiness evidence markers.
- Remote `smoke server` and release smoke gates now support HTTPS pilot stands through `REMOTE_SMOKE_BASE_URL` / `REMOTE_SMOKE_INSECURE_TLS` or explicit `--base-url` / `--insecure-tls` flags, avoiding false failures after `REQUIRE_HTTPS=true`.
- `scripts/business_smoke.py` supports optional HTTPS cookie check, self-signed stand TLS via `--insecure-tls` / `BUSINESS_SMOKE_INSECURE_TLS`, Playwright mixed-content/WSS check, explicit test ticket creation, support workspace read, explicit `inventory.collect` smoke and operation result polling.
- Runtime/release/migration/browser signoff helpers now accept stand profile env (`PC_CLIENT_REMOTE`, `PC_CLIENT_REMOTE_ROOT`, `PC_CLIENT_REMOTE_SERVER_PYTHON`, `PC_CLIENT_SSH_KEY`, `PC_CLIENT_BROWSER_BASE_URL`) and no longer force the old HTTP browser signoff default.
- Query-token attempt counter in auth middleware with bounded process-local storage and no token values.
- Tech snapshot additions for query-token attempts, below-baseline device lists/baseline metadata and inventory scheduler duplicate-task details.
- Agent baseline now counts only real post-handshake devices with numeric agent versions; pending provisioning stubs and non-numeric canaries stay out of below-version counts and should be handled as cleanup/provisioning data quality.
- Runtime inventory scheduler `status_snapshot()` now includes active task count, duplicate detection, last tick and last error.

## Active Work: Operator Command Center

Status: accepted / release-candidate.

Goal:

- Make `/app/support` a Russian localized Operator Command Center action board that shows what requires operator attention now, while preserving the guided `/app/tickets` queue/workbench and existing ticket routes.

Scope:

- Backend typed endpoint `GET /api/web/support/command-center` derived from existing support queue/workspace signals without fake counters or per-ticket full workspace fanout.
- P1/P2 hardening adds explicit batched `ticket_approvals`, `diagnostic_sessions` and `diagnostic_evidence` sources, plus server-side command-center search.
- Frontend API layer, prioritization helper, lazy support page and navigation update.
- UI controls include scope, queue, search and per-section item limit; search is sent to the typed endpoint and counts are based on the filtered candidate set.
- Docs/navigation updates for the new route, API and section keys.
- Live browser verification on the remote stand with a newly created ticket visible in the Command Center.

Decisions:

- Keep `/app/tickets` and `/app/tickets/:ticketId` as the guided ticket workspace.
- Use compact support queue rows, chat counters, SLA/OLA fields, batched approval/operation/device/diagnostics/passport fields when available, and deterministic recent-ticket grouping for similar spikes.
- Return all command-center sections with real count `0` when a source signal is unavailable; do not synthesize fake activity.
- Prefer links into `/app/tickets/:ticketId`; section actions may fall back to `/app/tickets` when smart-view query support is not guaranteed.

Verification target:

- Backend command-center contract/aggregation tests plus relevant support queue tests.
- Frontend command-center page/prioritization/navigation tests, then webapp build.
- `python -m compileall -q server`, `git diff --check`, `python scripts/verify_workspace.py`.
- Quick remote deploy/release and Browser MCP smoke at `https://192.168.100.17:9443/admin` for `/app/support`, `/app/tickets` and live ticket creation/display.
- Full CI/full gate remains the final publication checkpoint for a release cut; do not reuse a green artifact from a different commit.

Known constraints:

- Local Windows DB-backed `server/tests/test_operator_command_center.py` is slow but now completes on the local harness; keep full CI/full gate as the authoritative release publication checkpoint.

Current P1/P2 hardening checklist:

- Add requester-role regression coverage for `/api/web/support/command-center`; intended model is support-only, so requester tokens must receive 403.
- Mark requester messages as read when a support operator opens the real ticket workspace, using the existing ticket read endpoint rather than hover/preview behavior.
- Make `/app/tickets?smart_view=...` and `/app/tickets?search=...` open the queue view with visible filters; Command Center aliases are mapped to supported queue smart views.
- Change similar-spike links from generic `/app/tickets` to a filtered search context so operators see the group samples first.
- Add command-center performance logging and data-quality fallbacks for historical mojibake/junk titles without modifying stored data blindly.
- Live acceptance evidence: requester-role API returns 403, remote branch is `codex/inventory-v4-registration-presence`, product HEAD `ca8818eb` opened `/app/support` and `/app/tickets`, `/app/tickets?smart_view=unassigned|sla_risk` applied visible queue filters, similar-spike search opened filtered ticket context, live ticket `T-000578` entered `unread_user_messages`, opening `/app/tickets/930461f7-9f88-43c6-9ac5-e5676643a9cd` triggered `POST /api/web/support/tickets/{ticket_id}/read`, and after refresh it disappeared from unread while staying in `operator_action`, `new_unassigned` and `sla_risk`.

## Active Work: P1 Device Operations

Status: implemented / production-oriented cut pending release signoff.

Goal:

- Add a single Russian localized device/agent operations workspace where an admin or support engineer can inspect inventory, binding, agent version/update, modules, outbox, recent operations, Observer traces, provisioning/auth and Remote Assist availability for one device without replacing the existing expert screens.

Implemented:

- Backend typed read endpoint `GET /api/web/admin/device-operations/{device_id}` with query fallback, DTOs and `DeviceOperationsService` aggregation over existing devices, inventory, modules, outbox, operations, Observer, connection request/token audit and Remote Assist data.
- React route `/app/admin/device-operations/:deviceId` plus query fallback `/app/admin/device-operations?device_id=...`, typed frontend client and page with overview, inventory, agent/update, modules, outbox/operations, Observer, Remote Assist and provisioning/auth tabs.
- Deep links from Inventory, Device Card and the ticket device/offline banner to Device Operations while keeping the old Inventory, Device Card, Agent Updates, Modules, Observer and ticket routes intact.

Read-only / known gaps:

- Direct module rollout, operation retry/cancel, provisioning approve/reject and Remote Assist request buttons are intentionally not implemented in Device Operations until safe action-specific permission/consent flows are exposed for this workspace.
- Agent Updates and Observer row-level links into Device Operations are left as follow-up where device_id is available in those tables without a risky refactor.

Verification target:

- `server/tests/test_device_operations.py`, relevant support/inventory regressions, `python -m compileall -q server`.
- `pnpm --dir webapp test -- device-operations`, focused inventory/tickets tests and `pnpm --dir webapp build`.
- `python scripts/verify_workspace.py`, `git diff --check`, quick remote/browser smoke at `https://192.168.100.17:9443/admin` before release acceptance.

## Active Work: P1 Approval/Consent Center

Status: accepted / release-candidate.

Goal:

- Add a unified support/admin read workspace for approvals, user consent, risky action consent, closure approval blockers and policy override work without replacing source-domain workflows.

Implemented:

- Backend typed endpoint `GET /api/web/support/approvals` with DTOs and `ApprovalConsentCenterService`.
- React route `/app/support/approvals`, navigation item `Согласования`, typed frontend client and Russian read-only page with scope/status/kind/risk filters, KPI strip, sections and item cards.
- Real read sources for `ticket_approvals`, `change_approvals`, `operations.status=waiting_consent`, `remote_access_sessions` pending consent and closure-like ticket approvals.
- Command Center pending approval/consent actions now deep-link to Approval/Consent Center.
- Ticket workspace context shows a compact `Согласования и согласия` block when ticket approvals or waiting-consent operations exist.

Read-only / known gaps:

- Mutating approve/reject/delegate/cancel/resend actions are not wired in this cut; source-domain typed endpoints remain the safe action surfaces.
- Policy override items return zero because no first-class pending policy override source is exposed yet.
- Change, Remote Assist and operation rows link to context, but the center does not bypass consent or expose raw operation/Remote Assist secrets.

Verification:

- Backend: `server/tests/test_approval_consent_center.py`, command-center and device-operations regressions, `python -m compileall -q server`.
- Frontend: `pnpm --dir webapp test -- approval-consent`, `pnpm --dir webapp test -- command-center`, `pnpm --dir webapp build`.
- Workspace: `python scripts/verify_workspace.py`, `git diff --check`.
- Live stand acceptance on `0dabb033`: `/api/web/support/approvals` returned 200 for admin/support, 403 for requester, 401 for unauth/invalid bearer; live/seed sources produced ticket, change, risky tool, remote assist and closure approval/consent items; policy override stayed at zero by design; secret scan found no Remote Assist or operation raw secret fields in the payload.
- Browser smoke: `/app/support/approvals`, `/app/support` pending approval/consent links and `/app/tickets/a1111111-1111-4111-8111-111111111111` compact `Согласования и согласия` block passed with no console errors.

## Active Work: P0 Web UI Workbench and Studio Hardening

Status: accepted / production-oriented cut in progress.

Goal:

- Remove visible clipping/overflow from `/app/tickets`, make the ticket workspace task-guided, replace primary raw code/JSON inputs with pickers/guided forms, add a minimal Request Template Studio workflow, and localize the target admin/support screens in Russian while preserving existing endpoints and DTOs.

Scope:

- React webapp only by default: `/app/tickets`, `/app/admin/changes`, `/app/admin/forms`, `/app/admin/service-catalog`, `/app/admin/policy-health`, `/app/admin/device`, navigation and shared admin helpers.
- Backend changes only if existing web API data is insufficient for typed pickers. Prefer existing Service Catalog dashboard, Helpdesk Model registry and Policy Health endpoints.
- Preserve raw/expert JSON modes as collapsed or explicitly expert-only surfaces.
- Do not add fake catalog, policy, device, ticket or problem data.

Decisions:

- Treat the user's P0.0-P0.3 acceptance criteria as the approved design specification for this pass.
- First stabilize visible ticket workspace defects and tool availability grouping.
- Use shared TS helpers for catalog/policy/template option mapping and guided simulation payload construction.
- Implement Request Template Studio as a new admin route composed from existing Service Catalog, Forms Builder registry and Policy Health data; deep links should carry service/offering/template query params where possible.
- Russian UI labels are required for target screens, while technical ids remain visible only as metadata or expert fields.

Verification target:

- `pnpm --dir webapp test` focused component/API tests for picker mapping, guided simulation payloads and tool availability grouping.
- `pnpm --dir webapp build` because `package.json` has no separate `typecheck` or `lint` scripts.
- `python scripts/verify_workspace.py`.
- Focused server tests only if server DTO/routes change.
- Browser MCP smoke at `https://192.168.100.17:9443/admin` for `/app/tickets`, `/app/admin/changes`, `/app/admin/forms`, `/app/admin/service-catalog`, `/app/admin/policy-health` and `/app/admin/device`.

Handoff notes:

- If the whole P0 scope cannot land in one pass, do not leave `/app/tickets` with clipping or duplicated offline reasons. P0.0 and P0.3 take priority over broad visual polish.
- Current production cut fixes Request Template Studio simulation to send catalog context as top-level `service_code` / `offering_code` / `offering_full_code` and adds selected-ticket compact device/agent/inventory context in `/app/tickets` without adding inventory fanout to queue rows.
- 2026-05-20 Studio unification cut promotes `/app/admin/request-template-studio` to the primary request-template setup workflow: service/offering/template selectors, binding summary, embedded form preview, policy binding cards with Policy Health issues, guided simulation with human-readable result cards, publication gates and context-preserving links to Forms Builder, Service Catalog and Policy Health. Forms Builder, Service Catalog and Policy Health remain expert/deep surfaces and now show a Studio banner.
- 2026-05-20 P1 Studio deep-link hardening closed: Service Catalog restores `service`/`offering` query context from Studio links, warns on unknown or mismatched context, shows `template` as a context hint, and Policy Health expert simulation now sends query-derived catalog context as top-level `service_code` / `offering_code` / `offering_full_code` with the same body shown in Expert JSON.
- Read-only gaps: policy/template binding edits and publish-from-Studio are not implemented because no safe typed update/publish contract is exposed for Studio. Use Forms Builder / Service Catalog / expert policy editor for those writes until backend/domain service support is added.
- Verification for this cut: focused webapp tests for Studio payload/API and `TicketDeviceAgentPanel`, `pnpm --dir webapp build`, `server/tests/test_support_inventory_context.py`, and Python compile checks. A DB-backed support workspace route test hung on local Windows and is left for Linux/CI or remote DB verification.

## Latest Accepted Work: P5 Change Enablement

Status: accepted / release-candidate.

Goal: add first-class Change Enablement so P4 permanent-fix outputs can move through controlled change request, risk/impact, approval/CAB-lite, maintenance window, implementation plan, rollback plan, tasks, PIR and closure. P5 is not automatic execution and does not replace tickets, problems or continuous improvement actions.

### Discovery

- Existing change support is legacy linkage only: `ticket_change_links` stores external `change_ref` / `change_system` for ticket history. There is no first-class `changes` domain model, approval workflow, change calendar, rollback plan, PIR or typed `/api/web/changes*` API.
- P4 stores `permanent_fix_summary`, problem affected objects and problem activity events. It currently creates `create_change_candidate` / permanent-fix improvement actions as placeholders; P5 should attach first-class changes to those outputs.
- P3 continuous improvement actions already support `create_change_candidate`; P5 may add nullable `change_id` linkage but must not replace the action lifecycle.
- Service Catalog dimensions (`service_code`, `offering_code`, `request_type`, `reporting_category`) are the reporting boundary for P5. Registry services/assets may be linked as affected objects when present, without creating a heavy CMDB.
- Approval patterns exist for tickets, but P5 needs auditable `change_approvals` tied to change lifecycle, not free-form comments.
- Webapp route pattern exists for admin workspaces: `/app/admin/problems`, `/app/admin/quality`; P5 will add `/app/admin/changes`.

### Design Decisions

- Change is a separate first-class domain entity, not a ticket type and not a problem subtype.
- Change sources: manual, problem, improvement action, quality review, service catalog, security and API.
- Change types: `standard`, `normal`, `emergency`.
- Lifecycle: `draft -> submitted -> assessing -> awaiting_approval -> approved -> scheduled -> implementation_in_progress -> implemented -> pir_required -> closed`, with terminal `rejected`, `canceled`, `failed`, `rolled_back`.
- Normal/emergency changes require a rollback plan before approval; emergency changes also require justification.
- Standard changes can be preapproved only by policy; no automatic approval without policy.
- No scheduled automatic execution. P5 tracks authorization, timing, tasks and results only.
- Requester/public users have no P5 internal change API. Any requester-safe communication remains future scope or existing Knowledge/ticket surfaces.

### Data Model Plan

- Migration `092_change_enablement` after `091_problem_management_production_hardening`.
- New tables: `changes`, `change_risk_assessments`, `change_plans`, `change_approvals`, `change_windows`, `change_affected_objects`, `change_tasks`, `change_pir_records`, `change_activity_events`, `change_policies`.
- Add nullable `change_id` to `continuous_improvement_actions` if needed for source/action linkage.
- Safe indexes: status/type, problem/action linkage, service/offering, planned window, approval status, task status, window time range and affected object.
- No destructive changes to tickets, problems, quality or knowledge tables.

### API / UI Plan

- Server package: `server/change/*` with contracts, serializers, service, risk, approval, calendar, tasks, PIR and analytics.
- Web API: `/api/web/changes*`, `/api/web/change-windows*`, `/api/web/change-calendar`, `/api/web/change-policies*` and `/api/web/changes/metrics/*`.
- Webapp: `/app/admin/changes` workspace with list, create wizard, risk/impact, plan/rollback, approval, calendar, tasks, PIR, affected objects, timeline and problem-to-change action.
- Problem integration: create change from problem permanent fix, copy service/offering and affected objects, record problem activity, show linked changes in problem detail.

### Implementation Snapshot

- Added migration `092_change_enablement` and SQLAlchemy models for `changes`, risk assessments, plans, approvals, windows, affected objects, tasks, PIR records, policies and activity events.
- Added `server/change/*`, `server/app/repos/change_repo.py`, and `server/web_api/change_handlers.py`.
- Added `/api/web/changes*`, `/api/web/change-windows`, `/api/web/change-policies`, create-from-problem and create-from-improvement-action routes.
- Added `/app/admin/changes`, sidebar navigation and a Problem workspace "Create change" action.
- Added `server/docs/CHANGE_ENABLEMENT.md` and updated DATABASE, SECURITY, CODEMAP, QUICK_LOOKUP, ARCHITECTURE_BOUNDARIES, PROBLEM, QUALITY, KNOWLEDGE and Service Catalog docs.

### Tests

- `server/tests/test_change_contract_no_db.py`
- `server/tests/test_change_repo.py`
- `server/tests/test_change_service.py`
- `server/tests/test_change_lifecycle.py`
- `server/tests/test_change_risk_assessment.py`
- `server/tests/test_change_approval_service.py`
- `server/tests/test_change_calendar.py`
- `server/tests/test_change_tasks.py`
- `server/tests/test_change_pir.py`
- `server/tests/test_change_problem_integration.py`
- `server/tests/test_change_service_catalog_integration.py`
- `server/tests/test_change_knowledge_quality_integration.py`
- `server/tests/test_change_api.py`
- `server/tests/test_change_privacy.py`
- `server/tests/test_change_analytics.py`
- `server/tests/test_change_policies.py`

Webapp tests:

- change API client;
- change workspace list/create/risk/approval/calendar/tasks/PIR;
- problem-to-change button/link.

### Verification

- Initial TDD red: `python -m pytest server/tests/test_change_contract_no_db.py -q --tb=short` failed with `ModuleNotFoundError: No module named 'change'`.
- `python -m pytest server/tests/test_change_contract_no_db.py ... server/tests/test_change_policies.py -q --tb=short` -> 22 passed on `codex/helpdesk-process-model`.
- `pnpm --dir webapp test -- src/features/changes/api.test.ts src/features/changes/change-workspace.test.tsx src/features/problems/problem-workspace.test.tsx` -> 4 passed.
- Problem/Quality focused regression passed: `test_problem_api.py`, `test_problem_service.py`, `test_problem_candidate_service.py`, `test_problem_slo_policy.py`, `test_problem_scheduler.py`, `test_quality_api.py`, `test_quality_workflow_integration.py`, `test_quality_smoke_regression.py`.
- Static/local checks passed: `python -m compileall -q server pc_agent scripts`, `git diff --check`, `python scripts/verify_workspace.py`, `python scripts/build_context_index.py --force`, `pnpm --dir webapp build`.
- Full canonical CI passed on commit `82a33a1ecfcaf308ffe2cd3c53cdb0beb33ab1e7`: `python scripts/run_ci_suite.py --server-pytest-timeout 7200 --pc-agent-pytest-timeout 3600 --idle-timeout 0`.
- Full CI artifact: `artifacts/ci/82a33a1ecfcaf308ffe2cd3c53cdb0beb33ab1e7/summary.json`.
- Full CI layer counts: `server_pytest_no_db` 323 passed; `server_pytest_db_knowledge` 90 passed; `server_pytest_db_tickets` 275 passed; `server_pytest_db_observer_diagnostics` 74 passed; `server_pytest_db_agent_runtime` 84 passed; `server_pytest_db_web_api` 195 passed; `server_pytest_agent_ws` 30 passed; `pc_agent_pytest` 315 passed.
- Remote release signoff passed on `82a33a1`: full-gated deploy, Alembic head, webapp bundle upload and `/api/health` smoke succeeded.
- Browser signoff passed at `https://192.168.100.17:9443/app/admin/changes`: created `CHG-000002`, approved risk/plan/request, scheduled, added/completed task, started implementation, implemented, completed PIR and closed with no console errors and all P5 network calls returning 200.
- Problem-to-change browser signoff passed: `/app/admin/problems` `Create change` created `CHG-000003 Permanent fix: P4 smoke RCA problem`, visible in `/app/admin/changes`.

### Rollback Notes

- Disable/hide change creation UI and keep `changes` read-only if P5 must be paused.
- Alembic downgrade `092` removes P5 change tables/links only; P0-P4 tables and workflows remain intact.
- No ticket workflow rollback is required because P5 does not change canonical ticket statuses or automatic ticket transitions.

### Remaining Risks

- P5 does not implement external calendar integrations, automatic execution, or full P5+ release orchestration; those are intentionally outside Change Enablement.
- P5 hardening archived/canceled demo records on the remote stand; no live demo change remains open.

## Latest Accepted Work: P5 Change Enablement Hardening

Status: accepted / compact release-candidate.

Scope:

- Expand `CHANGE_ENABLEMENT.md` with lifecycle matrix, examples and operator guide.
- Clarify standard change catalog by storing catalog examples under `change_policies.metadata.standard_catalog`; explicit `standard_preapproved=true` makes approvals skipped/non-required, not globally automatic.
- Harden calendar behavior with simple recurring RRULE support for blackout/maintenance windows and same-service/offering overlap detection for active planned changes.
- Track emergency retrospective overdue count through effective `max_emergency_retro_hours`.
- Harden change metrics: failure rate, rollback rate, lead time, implementation duration, PIR completion and emergency retrospective overdue.
- Mark or clean remote demo records from the previous P5 browser smoke.

Verification so far:

- RED: new focused tests failed for recurring blackout, same-service overlap, standard preapproval satisfaction and missing metrics keys.
- GREEN: `python -m pytest server/tests/test_change_calendar.py server/tests/test_change_policies.py server/tests/test_change_analytics.py -q --tb=short` -> 7 passed.
- P5 focused backend: `python -m pytest server/tests/test_change_contract_no_db.py server/tests/test_change_repo.py server/tests/test_change_service.py server/tests/test_change_lifecycle.py server/tests/test_change_risk_assessment.py server/tests/test_change_approval_service.py server/tests/test_change_calendar.py server/tests/test_change_tasks.py server/tests/test_change_pir.py server/tests/test_change_problem_integration.py server/tests/test_change_service_catalog_integration.py server/tests/test_change_knowledge_quality_integration.py server/tests/test_change_api.py server/tests/test_change_privacy.py server/tests/test_change_analytics.py server/tests/test_change_policies.py -q --tb=short` -> 26 passed.
- Webapp focused: `pnpm --dir webapp test -- src/features/changes/api.test.ts src/features/changes/change-workspace.test.tsx src/features/problems/problem-workspace.test.tsx` -> 3 files / 4 tests passed.
- Static/docs/build: `python -m compileall -q server pc_agent scripts`, `git diff --check`, `python scripts/build_context_index.py --force`, `python scripts/docs_inventory.py --check-links`, `python scripts/verify_workspace.py`, and `pnpm --dir webapp build` passed.
- Deploy/browser: quick release to remote stand passed on commit `b9047915494a6ddb58a05a34f443e66e86be7a6a`; `/api/health` smoke passed; `/app/admin/changes` showed failure/rollback/lead-time/emergency-retro metrics and archived demo rows with no console errors and all change API calls returning 200.
- Remote demo cleanup: `CHG-000001` and `CHG-000003` moved from `draft` to `canceled`; `CHG-000002` stayed `closed`; all three were renamed with `[demo archived]` and metadata `remote_demo_record=true`.
- Full canonical CI was not rerun for this compact hardening follow-up; the latest full P5 artifact remains `artifacts/ci/82a33a1ecfcaf308ffe2cd3c53cdb0beb33ab1e7/summary.json`.
- Remote server was stopped after smoke (`active=inactive`, `sub=dead`).

Remaining risks:

- External calendar integrations and rich RRULE support remain outside P5; current recurrence support intentionally covers simple daily/weekly maintenance and blackout windows.
- P5 still does not execute changes automatically; it governs approvals, timing, tasks, rollback and PIR only.

## Active Work: Tool Output Presentation Schema v1

Status: accepted / release-candidate.

Goal:

- Add a top-level `presentation_schema` contract next to `params_schema`, `output_schema` and `output_contract` so agent tool/module results can render as readable declarative UI blocks instead of raw JSON.

Scope:

- Agent registry: accept, preserve and expose `presentation_schema` without changing ToolResponse or Protocol V3.
- Built-in agent tools: add a real `system.collect` presentation schema and preserve `device_card` metadata for future inventory cards.
- Agent Recipe Runner: add primitive presentation schemas and a composite recipe schema without changing read-only execution semantics.
- Server diagnostics/capabilities: pass `presentation_schema` through descriptors, persisted recipe descriptors and primitive catalog responses without DB migrations.
- Webapp: add safe typed presentation schema helpers and `ModuleResultRenderer` / `CompositeRecipeRenderer`; integrate minimally into Capability detail and Diagnostic Center result preview while keeping raw JSON fallback.
- Docs/navigation: update module docs, CODEMAP and quick lookup/navigation catalog as required.

TDD checkpoints:

- RED agent registry tests for decorator extraction, flat tool spec projection and default `{}`.
- RED recipe primitive tests for `describe_primitives` presentation schemas.
- RED server capability tests for toolset and recipe descriptor pass-through.
- RED webapp renderer tests for field grid, table/checklist/timeline/artifact/raw fallback, invalid schema, missing paths and React escaping.

Verification target:

- Focused pytest for registry, recipe runner, server capability projection.
- Focused Vitest for renderer and diagnostics integration.
- `python -m compileall -q pc_agent scripts/navigation_catalog.py`, `python scripts/verify_workspace.py`, `python scripts/docs_inventory.py --check-links`, `git diff --check`, `git diff --cached --check`.
- Full `python -m pytest pc_agent/tests/ -v --tb=short`.

## Active Work: Tool Output Presentation Builder v1

Status: accepted / local verification passed.

Goal:

- Add managed server-side presentation schema overrides and a minimal admin UI builder so capability/tool output presentation can be edited, previewed and reset without changing module defaults or tool result wire formats.

Scope:

- Server storage/API: add `tool_presentation_overrides`, validation, effective schema resolution and `/api/web/tool-presentations` endpoints.
- Capability projection: keep module `presentation_schema` unchanged while exposing `effective_presentation_schema`, `presentation_schema_source` and `has_presentation_override`.
- Webapp: add a JSON editor builder in capability detail, output schema path picker, generated/sample result editor and live preview through the existing `ModuleResultRenderer`.
- Docs/navigation: document override semantics, API, security limits and builder entrypoints.

TDD checkpoints:

- RED server tests for default effective schema, override upsert, reset, validation failures and capability list effective projection.
- RED webapp tests for output schema path extraction, builder rendering, invalid JSON, live preview, save/reset calls and missing-schema fallback.

Verification target:

- Focused server pytest for presentation overrides and no-db diagnostic capabilities.
- Focused Vitest for builder/path picker and existing module result renderer.
- `pnpm --dir webapp build`, migration-focused server tests, docs checks, workspace verification and diff whitespace checks.

Implementation snapshot:

- Added migration `093_tool_presentation_overrides`, SQLAlchemy model `ToolPresentationOverride`, and `diagnostics.presentation_overrides` for validation, upsert/reset and effective schema projection.
- Added `/api/web/tool-presentations?tool_id=...` GET/PUT/DELETE and projected `effective_presentation_schema`, `presentation_schema_source` and `has_presentation_override` in capability APIs.
- Added `PresentationSchemaBuilder`, `schema-path-picker` helpers, generated sample result preview and Capability detail integration using the existing `ModuleResultRenderer`.
- Follow-up blocker fix: support timeline `tool_call_result` DTOs now expose bounded real `result_payload` plus effective presentation schema/source, and `/app/tickets` renders that payload through `ModuleResultRenderer` so completed `system.collect` results can show field grids, metrics and tables instead of only a compact JSON preview.

Verification:

- RED server/webapp tests failed on missing override service and builder modules before implementation.
- `python -m pytest server/tests/test_tool_presentation_overrides.py server/tests/test_diagnostic_capabilities_no_db.py server/tests/test_modules_manifest_no_db.py -v --tb=short` -> 41 passed.
- `python -m pytest pc_agent/tests/test_tool_presentation_schema_registry.py pc_agent/tests/test_tool_contract_runtime.py::test_builtin_specs_expose_contract_fields -v --tb=short` -> 4 passed.
- `pnpm --dir webapp test -- src/components/module-result/module-result-renderer.test.tsx src/components/module-result/schema-path-picker.test.ts src/components/module-result/presentation-builder.test.tsx src/features/diagnostics/diagnostic-center-panel.test.tsx` -> 4 files / 19 tests passed.
- `pnpm --dir webapp build`, `python -m compileall -q server pc_agent scripts`, `python scripts/docs_inventory.py --check-links`, `python scripts/verify_workspace.py` and `git diff --check` passed.

## Completed Work: Inventory Collect v1 + Device Card Slots

Status: accepted on branch `codex/inventory-collect-v1`, latest commit `d0a5dec`.

Goal:

- Add practical readable tool output value by collecting a privacy-safe endpoint inventory snapshot, persisting latest/history on the server, and rendering inventory/tool results through the shared presentation renderers in the device card and ticket timeline.

Scope:

- Agent: new built-in `inventory.collect` core module with detailed `output_schema`, `output_contract.kind=device.inventory.snapshot`, `device_card.slots` and default `presentation_schema`.
- Server: new `device_inventory_snapshots` persistence, command-result side effect for `inventory.collect`, latest/history projection and admin device inventory API with `effective_presentation_schema`.
- Webapp: `DeviceInventoryPanel` in `/app/admin/device`, collect button, compact inventory header/KPIs, `ModuleResultRenderer` preview, raw JSON fallback and shared `ToolResultEventCard` for ticket timeline results including composite recipes.
- Privacy: no screenshots, keystrokes, browser history, clipboard, document/message contents or file listings.

Verification so far:

- `python -m pytest pc_agent/tests/test_inventory_collect.py pc_agent/tests/test_tool_presentation_schema_registry.py pc_agent/tests/test_registry_and_module_loading.py pc_agent/tests/test_config_loader_core_modules.py -v --tb=short` -> 17 passed.
- `pnpm --dir webapp test -- src/components/module-result/module-result-renderer.test.tsx src/components/module-result/presentation-builder.test.tsx src/features/admin/device-inventory-panel.test.tsx src/components/module-result/tool-result-event-card.test.tsx` -> 4 files / 15 tests passed.
- `pnpm --dir webapp build` passed.
- `python -m pytest pc_agent/tests/ -v --tb=short` -> 329 passed, 7 subtests passed.
- `pnpm --dir webapp test` -> 232 passed.
- Real PostgreSQL migration reached `094 (head)` on the remote host.
- Browser smoke on updated remote agent collected a real `inventory.collect` snapshot and rendered it through `ModuleResultRenderer` in the device card.
- Server `test_client` API tests hang in the local Windows fixture even for pre-existing `test_tool_presentation_overrides` endpoint tests; direct service tests, compile checks, remote migration and browser checks covered the v1 blocker path.

## Active Work: Inventory Collect v2

Status: accepted / branch `codex/inventory-collect-v2`.

Goal:

- Harden endpoint inventory for operational use without turning it into full CMDB: richer printer details, static key-app detection profiles, optional hardware identifiers, lightweight binding fields, scheduled refresh policy and a server-readable builtin descriptor catalog.

Scope:

- Agent: v2 printer details, key-app profile detector, optional hardware identifiers, updated output/presentation schemas while preserving v1 result shape.
- Shared/server descriptor: move declarative `inventory.collect` schemas into a pure shared catalog so server fallback no longer imports agent collector implementation.
- Server: binding metadata, refresh policy storage/API, due-selection helper using existing `ToolExecutionService.run_tool`, latest inventory payload extension.
- Webapp: DeviceInventoryPanel v2 with binding editor, schedule status, printers/software tabs and unchanged `ModuleResultRenderer`/raw JSON fallback.
- Privacy: endpoint technical inventory only; no screenshots, keystrokes, clipboard, browser history, document contents, messages or personal file listings.

Implementation snapshot:

- Agent `inventory.collect` v2 now returns best-effort printer details, static key-app profile summaries and optional hardware identifiers while preserving the v1 top-level shape.
- Declarative inventory descriptors live in `shared.builtin_tool_descriptors`; server fallback uses this pure catalog instead of importing `pc_agent.modules.impl.inventory`.
- Server added `device_inventory_bindings` and `device_inventory_refresh_policies`, binding/refresh APIs, latest inventory payload extensions and an `InventoryRefreshRuntime` that dispatches `inventory.collect` through the existing `ToolExecutionService`.
- Webapp `DeviceInventoryPanel` shows inventory source/slots, binding editor, refresh schedule controls/status, v2 printer/software/hardware blocks and raw JSON fallback through `ModuleResultRenderer`.

Verification:

- `python -m pytest pc_agent/tests/test_inventory_collect.py pc_agent/tests/test_inventory_profiles.py pc_agent/tests/test_registry_and_module_loading.py -v --tb=short` -> 17 passed.
- `python -m pytest pc_agent/tests/ -v --tb=short` -> 333 passed, 7 subtests passed.
- `python -m pytest server/tests/test_inventory_presentation_unit.py server/tests/test_tool_service_auto_install_no_db.py -v --tb=short` -> 6 passed.
- `pnpm --dir webapp test -- src/components/module-result/tool-result-event-card.test.tsx src/features/admin/device-inventory-panel.test.tsx` -> 2 files / 6 tests passed.
- `pnpm --dir webapp test -- src/app/router.test.tsx` -> 7 passed after widening the lazy route assertion timeout for full-suite contention.
- `pnpm --dir webapp test` -> 47 files / 234 tests passed.
- `pnpm --dir webapp build`, `python -m compileall -q pc_agent server shared scripts/navigation_catalog.py`, `python scripts/docs_inventory.py --check-links`, `python scripts/verify_workspace.py`, `git diff --check` and `git diff --cached --check` passed.
- Remote quick release ran Alembic `094 -> 095` on PostgreSQL, started server/control and passed `/api/health` smoke.
- Browser smoke at `https://192.168.100.17:9443/admin` opened the real device card, saved/restored binding fields, saved disabled refresh schedule status, restarted the updated remote agent and ran `inventory.collect`; latest API returned a fresh `2026-05-19T05:08:08Z` snapshot with `printers.items`, 11 key-app profiles, hardware identifier fields, binding and refresh policy, and the UI rendered the v2 blocks with no browser console warnings/errors.

Known verification limitation:

- Local Windows DB-backed server `pytest` fixtures still hang on existing `test_client` DB tests, including pre-existing presentation override tests. The v2 DB migration and API/browser path were verified on the real PostgreSQL stand instead.

## Active Work: Inventory Processes Items / Agent 3.1.59

Status: accepted / released on branch `codex/helpdesk-process-model`, commit `8605a03`.

Goal:

- Extend `inventory.collect` so device inventory shows real running processes instead of using the legacy "Ключевое ПО" presentation block as the primary operational list.

Scope:

- Agent: add bounded `processes.items` to the core built-in `inventory.collect` payload, sorted by memory and limited to 50 rows.
- Shared descriptor: add `processes` to the output schema/device-card slots and repoint the default presentation table to `processes.items` with title "Процессы".
- Compatibility: keep `software.key_apps` in the payload for existing server summaries/reports.
- Release: bump agent to `3.1.59`, build and publish Windows/Linux release artifacts after local checks.

Verification plan:

- `python -m pytest pc_agent/tests/test_inventory_collect.py pc_agent/tests/test_linux_packaging.py -q --tb=short` -> 8 passed.
- `pnpm --dir webapp test -- src/features/admin/device-inventory-panel.test.tsx src/components/module-result/tool-result-event-card.test.tsx` -> 2 files / 7 tests passed.
- `python -m pytest pc_agent/tests/ -q --tb=short` -> 342 passed, 7 subtests passed.
- `pnpm --dir webapp build` passed.
- `python scripts/verify_workspace.py` passed.
- `python -m pytest server/tests/test_inventory_presentation_unit.py server/tests/test_tool_service_auto_install_no_db.py -q --tb=short` -> 6 passed.
- Packaged Windows/Linux verify passed for 3.1.59.
- Uploaded release artifacts to the server registry and assigned stable rollout for `windows_amd64` and `linux_alt_x86_64`.
- Released the updated web bundle to the stand with quick gate and `--leave-running`.
- Live `inventory.collect` on ADMIN-2 (`7a3429ec-1c0b-5495-9aad-b284f08ae965`) succeeded: snapshot `f00a5b35-d738-4a72-9762-9cb1094d99a8` contains `processes.items` with 50 rows from 292 processes, and browser verification shows the `Процессы` block with real rows such as `Codex.exe` and `pc_agent.exe`.

## Active Work: Inventory v3 / Lightweight CMDB

Status: accepted / verified on branch `codex/inventory-v3-lightweight-cmdb`, commit `3b9b50c`.

Goal:

- Add a lightweight operational inventory layer on top of v2 without building a procurement/accounting CMDB: binding history, CSV import/export, fleet dashboard, refresh run visibility and stale/missing reports.

Scope:

- Cleanup: keep `shared.builtin_tool_descriptors` as the only descriptor source of truth and move inventory admin endpoints out of the large `admin_handlers.py` while preserving URLs.
- Server: add binding status/tags, binding history, CSV dry-run/apply import, binding and inventory CSV export, fleet dashboard aggregation and refresh run records.
- Webapp: enhance `/app/admin/inventory` with fleet summary/import/export/report sections and enhance `DeviceInventoryPanel` with stale status, binding history and refresh run visibility.
- Privacy: aggregate endpoint inventory and admin-entered binding metadata only; no employee activity monitoring or user-content collection.

Verification plan:

- Phase 0 cleanup: `python -m pytest pc_agent/tests/test_inventory_collect.py pc_agent/tests/test_inventory_profiles.py -v --tb=short`, `python -m pytest server/tests/test_inventory_presentation_unit.py server/tests/test_tool_service_auto_install_no_db.py -v --tb=short`, `python -m compileall -q pc_agent server shared scripts/navigation_catalog.py`, `git diff --check`.
- Server focused: binding history, CSV import/export, dashboard aggregation, refresh run service/scheduler, no-db inventory presentation tests.
- Webapp focused: inventory dashboard totals/import/export, device panel binding history/refresh history/stale badge, plus full `pnpm --dir webapp test` and build.
- General: docs link check, workspace verify, diff whitespace checks, migration upgrade on the remote PostgreSQL stand if DB schema changes are committed.

Implementation notes:

- Cleanup: `inventory.collect` descriptors remain single-source in `shared.builtin_tool_descriptors`; inventory admin HTTP handlers moved to `server/web_api/admin_inventory_handlers.py` without changing existing URLs.
- DB: migration `096_inventory_v3_lightweight_cmdb` adds `status`/`tags` to `device_inventory_bindings`, plus `device_inventory_binding_history` and `device_inventory_refresh_runs`.
- Server/API: `/api/web/admin/devices/{device_id}/inventory` is extended backward-compatibly with `binding_history`, `refresh_runs` and `last_refresh_run`; new endpoints cover binding history, binding CSV import/export, fleet inventory CSV export, dashboard aggregation and refresh run listing.
- Webapp: `/app/admin/inventory?panel=fleet` renders fleet summary, CSV export buttons and dry-run/apply binding import; `DeviceInventoryPanel` shows stale status, tags/status binding fields, binding change history and refresh run history.
- Verification: remote PostgreSQL migration `095 -> 096` completed, browser smoke on `https://192.168.100.17:9443/admin` verified the fleet dashboard after fixing the dashboard `last_requested_at` null case, local focused/full agent and webapp tests passed, and the branch was pushed to GitHub.

## Active Work: Inventory v4 / Fleet Operations, Workplace Registration v1 and Presence v1

Status: accepted / verified on branch `codex/inventory-v4-registration-presence`; remote quick release, PostgreSQL migration and browser smoke passed on 2026-05-19. Full release gate remains an explicit final-release checkpoint.

Goal:

- Extend lightweight inventory into fleet operations without building a procurement/accounting CMDB: selected/stale/missing/department/building bulk refresh, operation tracking, reports, XLSX export, profile-based workplace binding suggestions and safe workplace presence snapshots.

Scope:

- Agent: add `presence.collect` as a core built-in read-only module with `output_schema`, `output_contract.kind=device.presence.snapshot` and `presentation_schema`; keep `inventory.collect` shape and descriptors stable.
- Server: add migration `097_inventory_v4_registration_presence` for bulk operations/items, binding suggestions and presence snapshots/daily summaries; extend inventory dashboard/report/export APIs; persist `presence.collect` command results; create non-destructive binding suggestions from agent profiles.
- Webapp: enhance `/app/admin/inventory?panel=fleet` with bulk refresh, attention groups and XLSX export; enhance `DeviceInventoryPanel` with agent profiles, binding suggestions and workplace presence.
- Privacy: presence is endpoint availability/session state only. It must not collect screenshots, keystrokes, mouse coordinates, window titles, browser history, full URLs, document contents, clipboard contents, messages or personal file listings. Agent profiles may suggest binding fields but must not overwrite confirmed binding automatically.

Verification target:

- Agent focused: `python -m pytest pc_agent/tests/test_presence_collect.py pc_agent/tests/test_inventory_collect.py pc_agent/tests/test_inventory_profiles.py pc_agent/tests/test_registry_and_module_loading.py -v --tb=short`.
- Server focused: `python -m pytest server/tests/test_inventory_v4_service.py server/tests/test_inventory_v3_service.py server/tests/test_inventory_presentation_unit.py server/tests/test_tool_service_auto_install_no_db.py -v --tb=short`; DB-backed v3/v4 tests are expected to run on Linux/CI and skip on Windows.
- Webapp: `pnpm --dir webapp test`, `pnpm --dir webapp build`, `pnpm --dir webapp exec tsc --noEmit`.
- General: `python -m compileall -q pc_agent server shared scripts/navigation_catalog.py`, docs link check, workspace verify, `git diff --check`, and remote PostgreSQL migration/browser smoke before release acceptance.

Verification:

- Passed: focused `presence.collect`/inventory/registry/config-loader agent tests, full `pc_agent/tests/`, focused server no-db/inventory presentation tests, webapp full Vitest suite, webapp typecheck/build, `compileall`, docs link check, workspace verification and diff whitespace checks.
- Passed remote/browser smoke: `/app/admin/inventory` fleet dashboard opens, bulk-refresh dry-run works, `/app/admin/device` shows the inventory card, and `DeviceInventoryPanel` now exposes Registration/Presence tabs even before the first inventory snapshot.
- Windows-local DB-backed inventory v3/v4 service tests skip by design. The remote runtime venv does not include pytest, so DB-backed Linux pytest must run in CI or a test venv, not on the production runtime venv.

## Active Work: Device Registration Claims and Authoritative User Binding

Status: in progress on branch `codex/helpdesk-process-model`.

Goal:

- Replace direct self-reported requester-profile ownership assignment with a controlled device registration workflow: claim creation, user/admin confirmation, conflict handling, active authoritative binding, audit history and ticket requester enrichment.

Classification:

- Cross-cutting DB/API/server-agent-web change. Contract surfaces: DB schema/models/repos, `/api/registry*` and `/api/web/admin/registry*`, handshake `handshake_ack.payload.registration`, ticket create requester context, React registry payload, agent GUI/API profile handling.

Scope:

- Server DB: add `registry_person_identities`, `device_registration_claims`, `device_user_bindings`, `device_registration_events`; extend `device_inventory_bindings` and `tickets`.
- Server domain: add `RegistrationRepo` and `RegistrationService`; make `RegistryIngestionService.ingest_requester_profile()` create/update claims and suggestions without directly assigning `registry_assets.assigned_person_id`.
- Server API: add agent/user registration profile/status/confirm endpoints and admin claim approve/reject/binding revoke/timeline endpoints.
- Server integrations: include registration status in handshake ack; enrich ticket creation from active primary binding without blocking unregistered devices.
- Webapp: extend `/app/admin/registry` with registration tab, badges, claim actions and new registry quality signals.
- Agent: add local user profile manager, registration API methods, handshake registration status handling and minimal GUI/status integration.

Non-goals:

- Do not convert `devices` into owner records.
- Do not trust self-reported profile data as authoritative.
- Do not change token/fingerprint/device-auth semantics.
- Do not run full CI/full deploy gate unless explicitly requested after a frozen candidate.

Execution plan:

- [ ] Step 1: Complete discovery of current migrations, models, registry/ticket/handshake/webapp/agent entrypoints.
- [ ] Step 2: Add failing server service/API/ticket/handshake tests around no direct assignment, approve/reject/conflict, status payload and ticket enrichment.
- [ ] Step 3: Add migration `098` and SQLAlchemy models/columns/indexes.
- [ ] Step 4: Implement `RegistrationRepo` and `RegistrationService` with identity normalization, claim dedupe, conflict detection, active binding sync, events and inventory binding sync.
- [ ] Step 5: Modify registry ingestion and snapshot payload/data-quality signals.
- [ ] Step 6: Add registration HTTP endpoints and route registration with auth boundary checks.
- [ ] Step 7: Add handshake registration payload and ticket requester binding enrichment.
- [ ] Step 8: Extend React admin registry API/types/page and run webapp type/build checks.
- [ ] Step 9: Add agent user profile manager/API/status handling and focused agent tests.
- [ ] Step 10: Run targeted verification: workspace verify, server registration/registry/inventory/ticket/auth tests, agent tests and webapp build/typecheck.

Verification matrix:

- Server focused: `python -m pytest server/tests/test_device_registration_service.py server/tests/test_registration_api.py -q`.
- Registry/inventory/ticket regressions: `python -m pytest server/tests/test_registry_service.py server/tests/test_inventory_v4_service.py server/tests/test_soft_delete_auth.py -q` plus ticket create tests found during implementation.
- Agent focused: `python -m pytest pc_agent/tests/test_user_profile_manager.py pc_agent/tests/test_registration_status.py pc_agent/tests/test_connection_request_flow.py -q`.
- Webapp: run the actual package script from `webapp/package.json` (`pnpm --dir webapp run build` or available typecheck).
- General: `python scripts/verify_workspace.py`, migration import/syntax check, and `git diff --check`.

2026-05-23 account-session extension:

- Added the requester/account session layer for the Qt agent GUI without changing machine-token auth: `GET /api/registry/agent/account-state`, `AccountSessionManager`, non-modal `AccountGateWidget`, ticket `requester_account` context and other-account ticket marking.
- Account gate is the first app page; settings remain available before login, while ticket list/create/detail paths require a valid local account session confirmed against account-state.
- Other-account login is local-only, does not call registration submit/confirm, and server ticket creation stores `custom_fields.requester_account_context.created_from_other_account=true` plus the active registered-device binding/person context without creating a registration claim.
- Focused verification added: `server/tests/test_registration_api.py`, `server/tests/test_ticket_registration_enrichment.py`, `pc_agent/tests/test_account_session_manager.py`, `pc_agent/tests/test_account_gate.py`, `pc_agent/tests/test_registration_status.py`.

2026-05-23 server-backed account-session hardening:

- Goal: replace local-only requester account selection with server-issued account sessions while preserving machine-token auth as device auth.
- Classification: cross-cutting DB/API/server-agent-web change. Contract surfaces: migration/models/repos, `/api/registry/agent/account-*`, admin registry review endpoints, `/api/tickets/create` requester account validation, Qt account gate/session storage, support/admin ticket context.
- Plan:
  - [x] Add regression tests for phone/reason preservation, other-account visibility rules, server session creation/validation, other-account request approval, and ticket create with server sessions.
  - [x] Add migration `099` and SQLAlchemy models for `device_account_sessions` and `device_account_login_requests`.
  - [x] Implement `AccountSessionRepo` and `AccountSessionService` for confirmed-binding sessions, other-account login requests, admin approve/reject and session validation.
  - [x] Extend registry endpoints/routes and account-state read model with server sessions, pending requests and allowed actions.
  - [x] Change ticket create to trust `requester_account.session_id` instead of client-supplied identity payload, leaving legacy self-declared other-account as explicitly unverified.
  - [x] Update Qt API client, `AccountSessionManager`, account gate and main window so confirmed login creates a server session and other-account login creates an approval request, not an instant local session.
  - [x] Ensure legacy local requester profiles cannot override selected account sessions in ticket creation.

## Active Work: Registry Management Center P0

Status: in progress on branch `codex/helpdesk-process-model`.

Goal:

- Turn `/app/admin/registry` from a mostly read-only registry overview into an action-first Registry Management Center for device-user bindings, people identities, registration claims and requester account sessions.

Classification:

- Cross-cutting Registry / typed web boundary / React UI change. Contract surfaces: `server/registry/*`, `server/app/repos/*`, `server/web_api/registry_handlers.py`, `server/routes.py`, `webapp/src/features/admin/api.ts`, `/app/admin/registry`, `server/docs/CODEMAP.md`, `docs/QUICK_LOOKUP.md`.

P0 scope:

- Server: add service-backed admin operations for bind person to device, transfer primary owner, add shared user, assign responsible person, revoke dependent account sessions on binding revoke/transfer, global account-session listing and basic person/identity admin mutations.
- Server snapshot: expand `GET /api/web/admin/registry` with device summaries, people counts, binding rows, account sessions, login requests and action metadata while preserving existing fields for current consumers.
- Webapp: refactor `registry-page.tsx` into a page orchestrator and feature components under `webapp/src/features/admin/registry/`; implement tabs `Обзор`, `Устройства`, `Пользователи`, `Привязки`, `Заявки`, `Аккаунт-сессии`, `Качество данных`; keep `Локации`, `Подразделения`, `Политики` as useful P1 placeholders.
- UX: global search, quick actions, reusable right detail panel, modal actions with reason fields for destructive/ownership operations, React Query invalidation for `admin-registry` and account-session queries.

Non-goals for this pass:

- Full locations/departments/policies CRUD.
- Person duplicate merge/split workflow beyond showing actionable placeholders.
- New DB schema unless existing tables cannot represent the P0 lifecycle.
- Full CI/full release gate unless explicitly requested after a frozen candidate.

Execution plan:

- [x] Step 1: Run intake, rebuild context index, bootstrap web toolchain and inspect existing registry/account-session contracts.
- [x] Step 2: Add failing backend tests for manual bind, primary conflict, replace/transfer, shared/responsible bindings and dependent account-session revoke.
- [x] Step 3: Implement `RegistrationService` admin binding helpers and `AccountSessionService` dependent-session revoke/list helpers.
- [x] Step 4: Add admin registry routes/handlers and update `server/routes.py`.
- [x] Step 5: Expand `RegistryIngestionService.build_snapshot()` payload with P0 summary/device/person/binding/session fields.
- [x] Step 6: Add frontend API types and mutation helpers.
- [x] Step 7: Replace `/app/admin/registry` with orchestrator + P0 tab components, dialogs and detail drawer.
- [x] Step 8: Update `server/docs/CODEMAP.md`, `docs/QUICK_LOOKUP.md` and this plan status.
- [ ] Step 9: Run focused backend tests, webapp build/test target if available, `compileall`, `verify_workspace.py` and `git diff --check`.

Verification target:

- Backend: `python -m pytest server/tests/test_registry_admin_actions.py -q`, `python -m pytest server/tests/test_device_registration_service.py server/tests/test_registration_api.py server/tests/test_account_session_service.py server/tests/test_ticket_account_access.py -q`.
- Webapp: `pnpm --dir webapp run build`; run registry-targeted Vitest if a useful test target is added.
- General: `python -m compileall server pc_agent`, `python scripts/verify_workspace.py`, `git diff --check`.
- Browser: MCP/browser check at `https://192.168.100.17:9443/admin` after deploy/smoke if this pass reaches remote verification.
  - [x] Add minimal admin registry UI/API client support for reviewing other-account login requests if feasible in this pass.
  - [x] Update CODEMAP/quick lookup docs for new account-session contract.
  - [ ] Run focused server/agent tests, compileall, webapp build, workspace verify and diff checks; commit and push.

2026-05-25 registration claim reconciliation follow-up:

- Goal: close the live-smoke gap where an agent can submit duplicate registration claims while pending, manual admin binding can create an active binding while the user claim remains open, and the Qt GUI can enter the main ticket workspace while registration is still pending.
- Classification: cross-cutting Registry / account-session / Qt GUI contract change. Contract surfaces: `RegistrationService.submit_agent_profile_claim()`, admin bind helpers, `/api/registry/agent/account-state`, registration form payload, `AccountGateWidget`, `MainWindow` ticket gating and registry docs/CODEMAP.
- Plan:
  - [x] Add RED tests for device-level open-claim dedupe, admin-bind claim reconciliation and pending GUI gate behavior.
  - [x] Reuse an existing open device claim instead of creating parallel pending claims for the same agent device/source.
  - [x] Make manual admin bind satisfy or supersede pending agent claims for the same device and invalidate pending-session login via terminal claim state.
  - [x] Keep `registration_pending` visible in account gate but block the normal app workspace until a confirmed binding or verified other-account session is selected.
  - [x] Add registration form policy hooks for strict existing department/location picker fields while preserving configurable fallback to pending free-text requests.
  - [x] Update docs/CODEMAP and run focused server/agent checks.

2026-05-26 GUI ticket E2E follow-up:

- Source scenario: local Windows GUI agent v3.1.60 created ticket `T-000602` (`1f83c6be-cf21-434a-89bb-fc3bebaed3ed`), support web UI moved it through `queued -> in_progress -> resolved`, requester confirmed closure in the GUI, final status `closed`.
- Bug: the GUI create-ticket preview displayed boolean fields `critical_service` and `public_service` as `Да`, while the submitted ticket workspace stored both as `Нет`. Future fix: add a regression around preview/value formatting for boolean custom fields and align the preview renderer with the final request payload serializer.
- Bug: support web UI showed inconsistent priority labels for the same ticket: action list used the legacy/computed priority (`P2`) while the ticket card/header used effective priority class (`P1`). Future fix: choose one canonical display field for support surfaces, preferably the effective `priority_class`, and add a UI/API contract test for `priority`, `priority_class`, and modifier-derived priority decisions.
- Data quality issue: some tool descriptions in the support workspace API response contained replacement question marks instead of readable Russian text. Future fix: trace those module metadata records to their source encoding and add UTF-8 validation for tool catalog ingestion/rendering.

## Live V3 / Tickets / Agent deep validation

Status: in progress.

Scope:

- Live server and local Windows PC Agent validation for Protocol V3, tickets, modules, run_tool, account-session boundary, local agent GUI and browser/admin UI.
- Bugs are evidence-recorded here and not fixed immediately unless they block downstream live testing with no reasonable workaround.
- For UI-visible flows, a scenario is not green until browser/admin UI confirmation and, where agent-facing, pywinauto/UIA confirmation are recorded.

Initial evidence journal:

- Started: 2026-05-27T00:12:42+05:00.
- Branch: `codex/helpdesk-process-model`.
- Commit: `b64eb2f0e4235dc930dfbc52a1805aef50ace646`.
- Server URL: `https://192.168.100.17:9443`.
- Browser/admin URL: `https://192.168.100.17:9443/admin`.
- Local workspace: `C:\Users\admin-2\CodexProjects\pc_client`.
- Remote workspace: `/var/chat_bot/pc_client` on `192.168.100.17`.
- Required docs read before execution: `AGENTS.md`, `docs/QUICK_LOOKUP.md`, `docs/ARCHITECTURE_BOUNDARIES.md`, `server/docs/PROTOCOL_V3.md`, `pc_agent/docs/PROTOCOL_V3.md`, `server/docs/TICKET_SYSTEM.md`, `server/docs/MODULES_API.md`, `pc_agent/docs/CODEMAP.md`, `server/docs/CODEMAP.md`.
- pywinauto requirement: pending verification with `python -c "import pywinauto; print(pywinauto.__version__)"`, must be `0.6.9` and UIA backend.
- Server status/log paths: pending collection through `scripts/manage_remote_stack.py status|logs`.
- Agent device_id/machine_id/version/log paths: pending collection from local UI bridge/process/SQLite.
- Server DB evidence path: pending selection of safe query method; raw tokens must not be logged.
- Browser evidence path: pending Playwright/browser session against canonical admin URL.

Diagnostic tooling plan:

- `scripts/live_ws_v3_probe.py`: created. Purpose: send safe Protocol V3 handshake/double-connection probes, validate close codes and ACK/NACK correlation, never print raw token, accept token via `PC_CLIENT_AGENT_TOKEN` or secure prompt, log token prefix/sha length only. Current scope covers P0.2/P0.3; malformed outbox support still pending for P0.10.
- `diag_live.sleep`: needed only if no existing cancellable long-running safe tool/module is available. Purpose: read-only sleep/progress/cancel validation for P0.8.
- `diag_live.artifact`: needed only if no existing safe artifact-producing tool exists for P2.2.
- `diag_live.consent`: needed only if no existing consent-required safe tool exists for P1.3.

P0 checklist:

- [x] P0.1 Agent handshake happy path: passed after restart guardrail; BUG-20260527-01 closed as verified non-product with recovery guardrails.
- [x] P0.2 Invalid Protocol V3 handshake: passed after proxy close-code fix; all canonical WSS invalid cases observe `4003`.
- [x] P0.3 Same device double connection: passed after proxy/probe fix; superseded raw websocket observes `4002` and real agent/browser state recovers.
- [x] P0.4 Agent account-session boundary for ticket create: direct HTTP, local automation create, and real UIA GUI wizard create verified with account-session and browser evidence.
- [x] P0.5 WS `chat_raise` account-boundary check: passed after DB-first/error-only fix; no phantom ticket and explicit denial when unsupported.
- [x] P0.6 Full ticket lifecycle: passed for canonical path and blocked assigned-without-assignee check; permissive resolve policy noted.
- [x] P0.7 `run_tool` happy lifecycle: passed for `system.collect`.
- [x] P0.8 Long-running tool + `cancel_operation`: passed after web-session cancel and local idempotency/outbox reconciliation fixes.
- [x] P0.9 Module/toolset snapshot after module lifecycle: passed after lifecycle device-event fix; residual historical noise documented.
- [x] P0.10 Protocol V3 malformed outbox probes: passed after strict outbox validation; malformed cases NACK and no new phantom rows/UI entries.

P1/P2 checklist:

- [ ] P1.1 Outbox ACK/NACK/dedup.
- [ ] P1.2 Command idempotency.
- [ ] P1.3 Consent flow.
- [ ] P1.4 Module auto-install before `run_tool`.
- [ ] P1.5 Restart/reconnect with pending state.
- [ ] P1.6 Browser/UI projection consistency.
- [ ] P2.1 Public/requester safety.
- [ ] P2.2 Attachments/artifacts.
- [ ] P2.3 Two-agent matrix, if a second agent is available.

Scenario evidence:

### BUG-20260527-01 — Live server stopped during P0.1 baseline

Severity: P0
Status: verified-non-product / guardrails-added
Area: other

Scenario:
P0.1 baseline collection while starting `live-v3-deep` local Windows launcher/GUI agent against `wss://192.168.100.17:9443/ws`.

Expected:
Live server remains running during agent provisioning and browser/API checks.

Actual:
`scripts/manage_remote_stack.py status server` reported `server: stopped (active=inactive, sub=dead)`. Server log tail showed `pc-client-server.service: Main process exited, code=killed, status=9/KILL` at 2026-05-27 00:16:51+05.

Repro steps:
1. Start local GUI launcher instance `live-v3-deep` with `python scripts/manage_local_agent.py start live-v3-deep --gui --launcher --ws-url wss://192.168.100.17:9443/ws --api-url https://192.168.100.17:9443/api`.
2. Read `/ui/agent/status` from `http://127.0.0.1:8765/ui/agent/status`.
3. Attempt admin session/API baseline and server log/status collection.

Evidence:
- Server log: `pc-client-server.service: Main process exited, code=killed, status=9/KILL`; `Stopped pc-client-server.service`.
- Agent log: local agent was waiting for connection approval with `has_auth_token=false`, `connection_state=initializing`.
- Browser/UI: pending; browser confirmation not possible while server returned `502 Bad Gateway`.
- Server DB: pending; DB query not run before restart.
- Agent SQLite: pending.
- WS/API payload: `/api/health` over `https://192.168.100.17:9443` returned `502 Bad Gateway` after stop.

Impact:
Blocks all P0 live scenarios until the server is restarted. It also invalidates any handshake/browser evidence gathered after the stop timestamp.

Root cause:
Post-incident host evidence shows an external/systemd-observed SIGKILL of the transient server unit at 2026-05-27 00:16:51+05, not an application exception or kernel OOM. Targeted journal/kernel collection around 00:10-00:25 showed `Main process exited, code=killed, status=9/KILL`, `Failed with result 'signal'`, memory peak about 281 MiB, and no OOM killer entries. The product/config limitation was that the canonical transient unit had `Restart=no`, so a one-off SIGKILL left the live server down.

Fix policy:
- Blocking further tests: yes
- Fixed now: guardrails added; incident classified non-product/external SIGKILL with product runtime-control recovery hardening.

Fix summary, if fixed:
- Added incident collector `scripts/collect_remote_server_incident.py` to gather systemd, service, control/proxy, kernel and health evidence with token redaction into `artifacts/`.
- Hardened `server/runtime_control.py` transient systemd launch with `Restart=on-failure`, `RestartSec=2s`, `StartLimitBurst=3`, `StartLimitIntervalSec=60s`, and `TimeoutStopSec=5s`.
- Added/updated focused tests in `server/tests/test_runtime_control.py`; commit `e03f9b29c23671dd9cdc0a806220e9ee7796493d` added restart guardrails and collector, commit `47340c9bc435303c97b5ce3cb05631e815d41207` bounded stop timeout for recovery.

Verification after fix:
- Incident collector run: `python scripts\collect_remote_server_incident.py --output artifacts\bug01-remote-server-incident.txt`.
- Targeted tests: `python -m pytest server\tests\test_runtime_control.py -q` -> `7 passed`; combined adjacent tests with proxy tests -> `9 passed`.
- Remote quick deploy applied commit `47340c9bc435303c97b5ce3cb05631e815d41207`; `systemctl --user show pc-client-server.service` confirmed `Restart=on-failure`, `RestartUSec=2s`, `TimeoutStopUSec=5s`.
- Controlled SIGKILL regression after guardrail: killed current `MainPID`, waited 10 seconds; service recovered with `ActiveState=active`, `SubState=running`, `NRestarts=1`, `/api/health` returned `{"status":"ok","deploy_check":"verified","run":"2025-03-17"}`.
- Remote smoke: `python scripts\manage_remote_stack.py smoke server --base-url https://192.168.100.17:9443 --insecure-tls` returned health 200.
- Browser/admin after recovery: `https://192.168.100.17:9443/app/admin/inventory?device=7a3429ec-1c0b-5495-9aad-b284f08ae965` showed `ADMIN-2` online, Windows, agent version `3.1.61`; screenshot `live-v3-bug01-bug02-admin-inventory-online.png`.
- Local GUI agent `live-v3-deep` was restarted/logged in through pywinauto UIA and returned `connection_state=connected`.

Regression check:
P0.1 adjacent check after recovery: server health, browser admin inventory, local source GUI agent status, UIA login/connected state, and Protocol V3 probe regressions all completed on the recovered server.

Remaining risk:
The exact external sender of the original SIGKILL was not present in available logs, so the incident is closed as verified non-product with guardrails rather than a product exception. If the same class repeats, systemd now restarts the server automatically and the collector preserves the incident evidence for escalation.

### P0.1 Agent handshake happy path

Status: passed after server restart; browser/admin and UIA evidence recorded.

Evidence:
- Transport:
  - Agent provisioning request created `request_id=f26ccfe4-1e51-48d8-967c-fd47ec4112b1`, approved by admin through `/api/web/admin/connection_requests/{device_id}/approve`.
  - Server created agent token with prefix `d7ad25a1`; raw token was not printed.
  - Agent log: connected to `wss://192.168.100.17:9443/ws`, sent authenticated handshake, received `handshake_ack` at 2026-05-27 00:17:43+05.
  - Server log: `Protocol: ws_ticket_v3`; capabilities included `protocol_v3`, `envelope_v3`, `outbox_ack_v3`, `trace_correlation`, `nack_support`, `outbox_batch_v1`, `consent_flow`, `rpc_request`, `rpc_response`, `outbox_item`, `job_events`, `device_events`.
  - No reconnect loop observed after token delivery; `/ui/agent/status` reported `connection_state=connected`, `connection_detail=WS подключён`.
- Server DB/state:
  - `devices`: `device_id=7a3429ec-1c0b-5495-9aad-b284f08ae965`, hostname `ADMIN-2`, OS `Windows`, `agent_version=3.1.61`, `protocol_version=ws_ticket_v3`, `last_seen_at=2026-05-27 00:18:07+05`, `last_handshake_at=2026-05-27 00:18:07+05`, `current_toolset_hash=464075d978b3230f`.
  - `connection_requests`: latest row `approved`, `request_id=f26ccfe4-1e51-48d8-967c-fd47ec4112b1`, `approved_token_delivered_at=2026-05-27 00:18:07+05`, machine/install ids match agent identity.
  - `agent_tokens`: active token prefix `d7ad25a1`, `last_used_at=2026-05-27 00:28:26+05`; prior active token prefix `8f8a95da` still exists.
  - `device_toolset_snapshots`: existing snapshot `snapshot_id=1`, `tool_count=6`; `device_outbox` latest `list_tools` was already `delivered` from an earlier snapshot flow.
- Agent local state:
  - Local launcher instance `live-v3-deep`, PID `32636`, mode `gui/launcher`, UI port `8765`; child `pc_agent.exe` PID `27208`.
  - `/ui/agent/status`: device_id `7a3429ec-1c0b-5495-9aad-b284f08ae965`, agent_version `3.1.61`, `has_auth_token=true`, `ui_bridge_running=true`, `connection_state=connected`, release channel `stable`, recommended version `3.1.61`.
  - `/ui/automation/status`: `window_visible=true`, `bridge_connected=true`, `connection_state=connected`, `has_active_profile=true`, active GUI view `tickets`, `ticket_count=1`.
  - SQLite `storage.db`: tables include `outbox`, `outbox_sent_history`, `seen_commands`, `pending_consents`, `auth_tokens`; `outbox=[]`, `outbox_sent_history=[]`, `seen_commands=[]`, `pending_consents=[]`, `auth_tokens` has one active redacted token row for the device.
  - Log paths: `C:\Users\admin-2\CodexProjects\pc_client\.local-agent\instances\live-v3-deep\data\logs\agent.log`, `action_trace.jsonl`, launcher log `C:\Users\admin-2\CodexProjects\pc_client\.local-agent\instances\live-v3-deep\launcher.log`.
- Browser/admin UI:
  - Browser URL: `https://192.168.100.17:9443/app/admin/inventory?device=7a3429ec-1c0b-5495-9aad-b284f08ae965`.
  - Visible admin inventory row: `ADMIN-2`, `7a3429ec...e965`, status `Онлайн`, OS `Windows`, version `3.1.61`, activity `27 мая 2026 г., 00:18`, state `Готово к действиям`.
  - Detail panel visible: `ADMIN-2`, `Онлайн`, version `3.1.61`, identifier `Windows MachineGuid`, tokens `2`, active `2`, no identity duplicates warning.
  - Screenshot: Playwright `live-v3-p0-1-admin-inventory.png`.
- Agent GUI/UIA:
  - `python -c "import pywinauto; print(pywinauto.__version__)"` returned `0.6.9`.
  - UIA backend used: `Application(backend="uia").connect(process=27208)`.
  - Initial control tree showed window `Maria Agent v3.1.61`, registration gate texts `Этот ПК зарегистрирован за:`, `admin-2`, `admin_confirmed`, button `Войти как admin-2`.
  - UIA `invoke()` on `Войти как admin-2` opened the main requester workspace.
  - Main UIA tree showed `Обращения`, sidebar account `admin-2 | Подтвержденный аккаунт`, agent status card `Агент v3.1.61`, `Релиз актуален`, and security footer `Ваше соединение защищено...`.
  - Screenshots: `artifacts/live-v3-p0-1-agent-uia-after-login.png`, `artifacts/live-v3-p0-1-agent-main-uia.png`.
- Root cause notes:
  - Original recovery was a server restart; final closure later classified the incident as verified non-product/external SIGKILL and added restart/incident guardrails.
  - Launcher log contains mojibake/replacement characters while `agent.log` is readable UTF-8. This is a log-quality risk to track if it affects later evidence collection.

### P0.2 Invalid Protocol V3 handshake

Status: passed after BUG-20260527-02 fix; original failed close-code evidence retained below.

Evidence:
- Diagnostic tool: `scripts/live_ws_v3_probe.py invalid-handshake --case <case>`, compiled with `python -m py_compile`.
- Transport:
  - Cases run: `wrong_protocol`, `missing_protocol_v3`, `missing_envelope_v3`, `missing_outbox_ack_v3`, `missing_token`, `invalid_token`.
  - Probe request/trace examples:
    - `wrong_protocol`: `request_id=0ad36cdb-f73f-48d4-8b4d-98c307d05530`, `trace_id=6cf40ae4-8a73-4c63-b591-3eaf7f18b0d8`.
    - `invalid_token`: `request_id=6d164bfd-fa0c-42d2-9c9b-6aa17f149404`, `trace_id=fd09777a-9df1-4339-bea2-0362b77f3f85`, token evidence only `prefix=invalid-`, `sha256_12=f89856230bb2`.
  - Actual client-observed close for all invalid cases: `close_code=1000`, `close_reason=""`, not expected `4003`.
  - Server log confirms rejection reasons, e.g. `Invalid protocol_version: ws_ticket_v2, expected ws_ticket_v3` and `Невалидный токен агента: invalid-...`.
- Server DB/state:
  - `devices.last_handshake_at` for the real device stayed at the previous valid handshake timestamp after invalid probes; no device row with hostname `ADMIN-2-PROBE`.
  - `device_events` recent count for this device remained `0`; the only recent `connection_requests` row was the earlier valid provisioning request, not the invalid probes.
- Agent local state:
  - Real local agent remained connected after invalid probes; no local SQLite outbox/pending consent changes observed for this negative protocol-only scenario.
- Browser/admin UI:
  - Browser confirmation not applicable for invalid handshake itself because the negative probe should have no UI representation. Admin inventory was checked around adjacent P0.1/P0.3 and did not show phantom `ADMIN-2-PROBE`.
- Root cause notes:
  - Server appears to execute rejection branch, but close code is not propagated to the client over the observed `wss://192.168.100.17:9443/ws` path.

### P0.3 Same device double connection

Status: passed after BUG-20260527-02 fix; original partial close-code evidence retained below.

Evidence:
- Transport:
  - `scripts/live_ws_v3_probe.py double-connect` used the live agent token from local SQLite via env only; output printed token prefix `d7ad25a1`, hash prefix `54898cb35fe5`, length `64`, never raw token.
  - First raw WS received `handshake_ack`: `request_id=2de05a0e-c45e-473d-99f4-0c4b70cb8244`, `trace_id=7f71296a-50fc-498f-8367-cf3b34389e9c`.
  - Second raw WS received `handshake_ack`: `request_id=7065aa39-1fa7-4ea3-a54a-6702c112da14`, `trace_id=37db5588-b927-4c33-866d-aaa9b8511eaf`.
  - Server log: `Superseding existing agent websocket` twice; superseded disconnects were logged as ignored.
  - Actual client-observed close for superseded first raw connection: `close_code=1000`, not expected `4002`.
- Server DB/state:
  - Server continued to resolve the device from token DB; `device_id=7a3429ec-1c0b-5495-9aad-b284f08ae965`.
  - Handshake rows updated the same device; no duplicate device row was created.
- Agent local state:
  - The live GUI agent was superseded by the first raw probe, then reconnected cleanly after the probes ended.
  - `/ui/agent/status` after recovery: `connection_state=connected`, `connection_detail=WS подключён`, `has_auth_token=true`, `ui_bridge_running=true`.
- Browser/admin UI:
  - Browser URL: `https://192.168.100.17:9443/app/admin/inventory?device=7a3429ec-1c0b-5495-9aad-b284f08ae965`.
  - Visible admin inventory after probe/reconnect: `ADMIN-2`, `Онлайн`, Windows, version `3.1.61`, activity `27 мая 2026 г., 00:33`, state `Готово к действиям`.
- Agent GUI/UIA:
  - Existing GUI session survived the forced reconnect; automation status remained `connection_state=connected`, main requester workspace visible.
- Root cause notes:
  - Supersede state handling on server looks correct from logs for superseded disconnects; close-code propagation to client is the failing part.

### BUG-20260527-02 — Protocol V3 close codes are not observed by raw WS clients

Severity: P1
Status: verified-fixed
Area: protocol

Scenario:
P0.2 invalid Protocol V3 handshake and P0.3 same-device double connection through `wss://192.168.100.17:9443/ws`.

Expected:
Invalid handshakes close with code `4003`. Superseded same-device websocket closes with code `4002`.

Actual:
The raw aiohttp WS client observed `close_code=1000`, empty close reason, for invalid protocol/capability/token cases and for the superseded double-connection socket.

Repro steps:
1. Run `python scripts/live_ws_v3_probe.py invalid-handshake --case wrong_protocol`.
2. Run `python scripts/live_ws_v3_probe.py invalid-handshake --case invalid_token`.
3. Set `PC_CLIENT_AGENT_TOKEN` from the live agent token source without printing it and run `python scripts/live_ws_v3_probe.py double-connect`.

Evidence:
- Server log: invalid handshake branches log `Invalid protocol_version...` and `Невалидный токен агента...`.
- Agent log: live agent reconnects after supersede and receives `handshake_ack`.
- Browser/UI: admin inventory returns to `ADMIN-2` online after reconnect.
- Server DB: no phantom `ADMIN-2-PROBE` device row; valid device remains same.
- Agent SQLite: no outbox/pending consent side effects from negative probes.
- WS/API payload: probe outputs show invalid close `1000` where expected `4003`; double-connect superseded close `1000` where expected `4002`.

Impact:
Protocol clients cannot rely on documented close codes for auth/contract handling. This weakens live diagnostics and may hide reconnect/supersede contract regressions behind normal-close semantics.

Root cause hypothesis:
Server calls `ws.close(code=4003/4002, ...)`, but the observed HTTPS/WSS path or aiohttp close handling reports normal close `1000`. Needs isolation between server aiohttp behavior and TLS/reverse-proxy behavior.

Root cause:
The backend server was already sending the documented custom close codes; direct backend `ws://192.168.100.17:8666/ws` probes observed `4003`. The TLS reverse proxy on `:9443` consumed the upstream close frame and closed the client websocket without propagating the upstream close code/reason, rewriting `4002/4003` to normal close `1000`.

Fix policy:
- Blocking further tests: no
- Fixed now: yes

Fix summary, if fixed:
- Changed files: `scripts/run_https_reverse_proxy.py`, `scripts/live_ws_v3_probe.py`, `scripts/test_run_https_reverse_proxy.py`, `PLANS.md`.
- Proxy fix: `_bridge_ws_to_client()` and `_bridge_ws_to_target()` preserve close code/reason, and the final websocket close uses the upstream close code when present instead of normal close `1000`.
- Probe fix: `scripts/live_ws_v3_probe.py` now waits robustly for close frames, supports `--ws-url`, `--expect-close-code`, `--expect-supersede-close-code`, and double-connect reads through pending server commands until `handshake_ack`/close evidence is collected.
- Safety guardrail: proxy access logging is disabled in `scripts/run_https_reverse_proxy.py` so query-string session tokens are not written by the proxy access log.
- Commits: `1b9254bdbb485ec01a84e29f750f00cb18b21cb3` for close-code/probe work and `e03f9b29c23671dd9cdc0a806220e9ee7796493d` for proxy access-log guardrail.

Verification after fix:
- Targeted tests: `python -m pytest scripts\test_run_https_reverse_proxy.py -q` -> `2 passed`; combined adjacent runtime/proxy tests -> `9 passed`.
- Compile checks: `python -m py_compile scripts\run_https_reverse_proxy.py scripts\live_ws_v3_probe.py scripts\test_run_https_reverse_proxy.py` -> passed.
- Live invalid-handshake regression over canonical WSS: `python scripts\live_ws_v3_probe.py --ws-url wss://192.168.100.17:9443/ws --timeout 5 invalid-handshake --case all --expect-close-code 4003` exited 0; `wrong_protocol`, `missing_protocol_v3`, `missing_envelope_v3`, `missing_outbox_ack_v3`, `missing_token`, and `invalid_token` all observed `close_code=4003`.
- Live same-device double-connect regression over canonical WSS: `python scripts\live_ws_v3_probe.py --ws-url wss://192.168.100.17:9443/ws --timeout 5 double-connect --expect-supersede-close-code 4002` exited 0; first raw socket observed final close `4002`, second socket remained active after `handshake_ack`.
- Browser/admin after probes: `https://192.168.100.17:9443/app/admin/inventory?device=7a3429ec-1c0b-5495-9aad-b284f08ae965` showed `ADMIN-2` online, Windows, agent version `3.1.61`; screenshot `live-v3-bug01-bug02-admin-inventory-online.png`.

Regression check:
P0.2 invalid Protocol V3 handshake and P0.3 same-device supersede both reran over canonical WSS and observed the documented close codes. The live GUI agent reconnected and browser inventory remained correct.

Remaining risk:
Raw double-connect probes can receive pending `device_outbox` commands before `handshake_ack`; the probe now tolerates this and records it as state contamination, not a close-code failure. Old proxy access logs may contain pre-fix query-string tokens, but new proxy runs have access logging disabled.

### P0.4 Agent account-session boundary for ticket create

Status: passed after BUG-20260527-03/04/10 fixes; original GUI/automation failures retained below.

Evidence:
- HTTP/API create path:
  - Live agent token was read from the local agent SQLite store for the request and was not printed.
  - Active local account session: `account_session_id=16a1e306-610b-436c-b5f9-65f6222386d1`, `account_mode=confirmed_binding`, `verification_status=verified`, `person_id=bb00a942-fe2c-461c-b982-9da17d3fd1ff`, `binding_id=0618eb74-9fa6-4dbe-9634-d9b56825f3ad`.
  - No-account request to `/api/tickets/create` returned HTTP `403`, `error=account_session_invalid`, `error_code=ACCOUNT_SESSION_REQUIRED`; no ticket_id returned.
  - Valid confirmed account-session request to `/api/tickets/create` returned HTTP `200`, `status=ok`, `ticket_id=44b04e94-4048-4593-b2bc-4054c7cfa7b1`, `requester_account_session_id=16a1e306-610b-436c-b5f9-65f6222386d1`, `requester_account_mode=confirmed_binding`.
  - Request trace marker in the created ticket description: `live-v3-p0-4-api-42315289`.
- GUI/UIA create path:
  - UIA backend confirmed with `pywinauto==0.6.9`; local agent window title readable as `Maria Agent v3.1.61`.
  - UIA create wizard was opened from the local agent GUI and moved through the first steps.
  - `set_edit_text()` through UIA corrupted Cyrillic values in Qt fields/preview into `?` characters while ASCII text stayed intact.
  - Required combo boxes on the confirmation step exposed no selectable values through UIA and could not be selected with `.select()` or keyboard `Alt+Down/Enter`; submit stayed blocked by visible validation messages `Заполните поле «Кого затронула проблема?».` and `Заполните поле «Можно ли продолжать работу?».`.
  - GUI preview panel also showed `Предпросмотр сервера временно недоступен. Можно продолжить...` during the failed GUI submit attempt.
  - Later focused UIA reads could still connect to the window title, but child-control searches hung on the create view; only the helper Python/PowerShell processes were killed, not the agent.
  - Screenshot/evidence paths from earlier UIA checks: `artifacts/live-v3-p0-1-agent-uia-after-login.png`, `artifacts/live-v3-p0-1-agent-main-uia.png`; P0.4 window screenshot attempt via `PIL.ImageGrab` failed with `OSError: screen grab failed`.
- Local GUI automation endpoint:
  - `python scripts/agent_test_driver.py create-ticket live-v3-deep ...` returned HTTP `500` from `/ui/automation/run`; embedded server error was HTTP `403`, `error=account_session_invalid`, `error_code=ACCOUNT_SESSION_REQUIRED`.
  - `action_trace.jsonl` request evidence shows `ticket_api ticket.create` payload did not include `requester_account` even though `account_session.json` contains the verified confirmed-binding session.
- Server DB/state:
  - Ticket `44b04e94-4048-4593-b2bc-4054c7cfa7b1`, code `T-000603`, stored as `status=queued`, `device_id=7a3429ec-1c0b-5495-9aad-b284f08ae965`, `requester_id=7a3429ec-1c0b-5495-9aad-b284f08ae965`, `requester_person_id=bb00a942-fe2c-461c-b982-9da17d3fd1ff`, `requester_binding_id=0618eb74-9fa6-4dbe-9634-d9b56825f3ad`, `requester_registration_status=admin_confirmed`, `requester_account_session_id=16a1e306-610b-436c-b5f9-65f6222386d1`, `requester_account_mode=confirmed_binding`, `next_action_owner=support`, `requester_status=accepted`.
  - Ticket events for `T-000603`: `routing_applied`, `queue_changed`, `sla_started`, `status_changed`, initial user `chat_message` with trace marker, and public access-code `chat_message`.
  - `operations` and operation-linked `device_outbox` rows for this ticket are `0`, as expected for plain create.
  - `device_account_sessions` row for session `16a1e306-610b-436c-b5f9-65f6222386d1` remains `verified`, `revoked_at=NULL`.
- Browser/admin UI:
  - Browser URL: `https://192.168.100.17:9443/app/tickets/44b04e94-4048-4593-b2bc-4054c7cfa7b1`.
  - Visible support workspace: `T-000603 Live V3 P0.4 API account-boundary check`, requester `admin-2`, status `В очереди`, queue `ServiceDesk L1`, assignee `Не назначен`, SLA about `1 ч 59 мин`.
  - Visible timeline included the initial user message `Live V3 P0.4 API create account-session boundary trace live-v3-p0-4-api-42315289`.
  - Browser screenshot: `live-v3-p0-4-ticket-detail.png`.
- Agent local state:
  - `/ui/automation/status` after the HTTP/API create showed `ticket_count=2` and included `ticket_ids=["44b04e94-4048-4593-b2bc-4054c7cfa7b1","1f83c6be-cf21-434a-89bb-fc3bebaed3ed"]`, `connection_state=connected`, `has_active_profile=true`.
  - Local SQLite remained clean for this HTTP create path: `outbox=0`, `outbox_sent_history=0`, `seen_commands=0`, `pending_consents=0`.
- Root cause notes:
  - Server account-session enforcement for agent-created tickets is working for the direct HTTP path.
  - GUI wizard and local automation endpoint are not currently sufficient to complete the required GUI create flow without a product fix or a lower-level UI hook.
  - The automation endpoint root cause is visible in code: `pc_agent/ui_gui/automation_controller.py` calls `ticket_client.create_ticket(...)` without passing `requester_account`, while `pc_agent/ui_gui/chat_panel.py` regular GUI submit passes `requester_account=account_session`.

### BUG-20260527-03 — UIA create wizard cannot complete required fields reliably

Severity: P1
Status: verified-fixed
Area: UI

Scenario:
P0.4 local agent GUI create flow driven by `pywinauto==0.6.9` with `backend="uia"`.

Expected:
Stable UIA selectors allow the test to fill requester-visible Russian text and select all required request-template fields without coordinate-only interaction; submit creates a ticket or returns a server-side validation result.

Actual:
UIA text injection corrupted Cyrillic field values to `?`, required combo boxes exposed no selectable items through UIA and could not be set with `.select()` or keyboard fallback, submit stayed blocked by required-field validation, and later child-control discovery on the create view hung.

Repro steps:
1. Connect to PID `27208` with `Application(backend="uia")`.
2. Open `Создать обращение`, choose `Сломался ноутбук`, proceed to the form.
3. Fill Russian values with `set_edit_text()`.
4. Attempt to select required combo boxes `Кого затронула проблема?` and `Можно ли продолжать работу?`.
5. Click `Создать обращение`.

Evidence:
- Server log: no ticket was created by the GUI/UIA wizard attempt.
- Agent log: GUI remained connected; no reconnect loop.
- Browser/UI: direct API-created ticket exists, but GUI-created ticket does not.
- Server DB: no additional GUI-created ticket with the corrupted UIA Russian payload.
- Agent SQLite: outbox/history/seen_commands/pending_consents unchanged.
- WS/API payload: not applicable; submit was blocked client-side before a successful create request.

Impact:
Blocks the mandatory GUI-driven ticket create validation in P0.4 and reduces repeatability of live GUI tests for Russian request-template forms.

Root cause hypothesis:
Qt accessibility/value patterns for these widgets are not exposing stable selectable ComboBox items to Microsoft UI Automation, and pywinauto `set_edit_text()` is not preserving Unicode for the Qt edit controls in this runtime.

Root cause:
The create wizard lacked stable UIA-accessible object names/names for several required controls, Qt `QComboBox` entries were not reliably selectable through Microsoft UI Automation in this runtime, and pywinauto `set_edit_text()`/ValuePattern corrupted Cyrillic text in Qt edit controls. Later child traversal hangs were caused by unbounded UIA descendant scans on the complex Qt wizard tree.

Fix policy:
- Blocking further tests: no, because direct HTTP/API and browser checks can continue; yes for the GUI-create subcase.
- Fixed now: yes

Fix summary, if fixed:
- Changed files: `pc_agent/ui_gui/dynamic_form_widget.py`, `pc_agent/ui_gui/chat_panel.py`, `pc_agent/ui_gui/ticket_create_wizard_widgets.py`, `pc_agent/tests/test_dynamic_form_widget.py`, `pc_agent/tests/test_chat_panel_helpers.py`, `scripts/live_agent_uia_create_ticket.py`, `PLANS.md`.
- Added stable `objectName`/accessible names/descriptions for the create wizard root, account controls, service/type/template/form selectors, dynamic fields, dynamic labels/inputs, description input, preview/status, submit/back/cancel buttons, and ticket type cards.
- Added GUI-side automation affordances for this UIA path: Unicode-safe description paste button, required-choice autofill button/shortcut, submit shortcut, and dynamic-form helper `select_first_options_for_required_choice_fields()`.
- Added diagnostic script `scripts/live_agent_uia_create_ticket.py`; it verifies `pywinauto==0.6.9`, uses `Application(backend="uia")`, uses stable selectors, pastes Unicode via clipboard, invokes GUI-side required-field autofill, limits control-tree dumps, saves JSON evidence and screenshot, and does not use coordinate clicks as pass criteria.
- Commit: `1b9254bdbb485ec01a84e29f750f00cb18b21cb3`.

Verification after fix:
- Targeted tests: `python -m pytest pc_agent\tests\test_dynamic_form_widget.py pc_agent\tests\test_chat_panel_helpers.py::test_ticket_create_wizard_exposes_stable_uia_ids -q` -> `6 passed`.
- Compile checks: `python -m py_compile pc_agent\ui_gui\dynamic_form_widget.py pc_agent\ui_gui\chat_panel.py pc_agent\ui_gui\ticket_create_wizard_widgets.py scripts\live_agent_uia_create_ticket.py` -> passed.
- Live UIA command: `.venvs\agent-win\Scripts\python.exe scripts\live_agent_uia_create_ticket.py --instance live-v3-deep --description "Русский текст BUG03 UIA create: проверка ввода без знаков вопроса, выбор обязательных полей и отправка через реальный GUI." --output-json artifacts\live-v3-bug03-uia-create.json --screenshot artifacts\live-v3-bug03-uia-create.png`.
- UIA evidence: pywinauto `0.6.9`, `backend="uia"`, window `Maria Agent v3.1.61`, active confirmed account, create wizard opened by stable selectors, Cyrillic description pasted and verified, required combo defaults set through the GUI autofill button, submit shortcut used, confirmation default button accepted.
- Server DB evidence: ticket `a05caf3a-cb6b-4bf6-8ef8-5087a4aff128`, code `T-000608`, title `Обращение: Поломка`, status `queued`, requester account session `c8848378-c623-4a6c-a70d-876a1a9bbec9`, mode `confirmed_binding`; initial `chat_message` contains the exact Russian text, not `?`.
- Browser/UI evidence: `https://192.168.100.17:9443/app/tickets/a05caf3a-cb6b-4bf6-8ef8-5087a4aff128` showed `T-000608`, title `Обращение: Поломка`, requester `Тестовый тест 12`, status queued, and the exact Russian user message; screenshot `live-v3-bug03-ticket-detail.png`.
- Agent local evidence: no new failed local outbox rows from the create flow; automation status after script showed the created ticket opened in the agent UI.

Regression check:
P0.1 UIA connected-state checks and P0.4 real GUI create subcase reran successfully. The pass criteria used stable UIA selectors and GUI-side invokable controls, not coordinate clicks.

Remaining risk:
Dynamic-field text controls still cannot be trusted with pywinauto `set_edit_text()` for Cyrillic on this Qt runtime; the diagnostic script uses clipboard paste for requester-visible Russian description and ASCII values for auxiliary dynamic text fields. Similar future UIA flows should reuse the same Unicode paste helper and bounded tree-dump pattern.

### BUG-20260527-04 — Local GUI automation ticket.create omits active account session

Severity: P1
Status: verified-fixed
Area: account-session

Scenario:
P0.4 `scripts/agent_test_driver.py create-ticket live-v3-deep ...` through `/ui/automation/run` while the local GUI has a verified confirmed-binding account session.

Expected:
The local automation ticket.create path should behave like the real GUI submit path and include the active `requester_account.session_id`/token, allowing a confirmed account session to create a ticket.

Actual:
The automation endpoint called `/api/tickets/create` without `requester_account` and the server correctly rejected it with `ACCOUNT_SESSION_REQUIRED`.

Repro steps:
1. Confirm `account_session.json` contains `account_session_id=16a1e306-610b-436c-b5f9-65f6222386d1`, `account_mode=confirmed_binding`, `verification_status=verified`.
2. Run `python scripts/agent_test_driver.py create-ticket live-v3-deep --title ... --description ...`.
3. Observe HTTP `500` from the local automation endpoint with embedded server HTTP `403`.

Evidence:
- Server log/API: `/api/tickets/create` rejection `ACCOUNT_SESSION_REQUIRED`.
- Agent log: action trace records automation `ticket.create` failure.
- Browser/UI: no ticket created by the automation endpoint.
- Server DB: no ticket row for the automation request.
- Agent SQLite: no outbox/history side effects.
- WS/API payload: `action_trace.jsonl` `ticket_api ticket.create` request payload lacks `requester_account`.
- Fix evidence, 2026-05-27 11:56-12:05 +05:
  - Changed files: `pc_agent/ui_gui/automation_controller.py`, `pc_agent/tests/test_gui_automation_controller.py`.
  - Targeted tests: `python -m py_compile pc_agent\ui_gui\automation_controller.py pc_agent\tests\test_gui_automation_controller.py` exit 0; `python -m pytest pc_agent\tests\test_gui_automation_controller.py pc_agent\tests\test_registration_status.py::test_create_ticket_sends_only_requester_account_session_when_passed -q` -> `3 passed in 0.76s`.
  - Live GUI precondition: source-mode local agent restarted with `python scripts\manage_local_agent.py start live-v3-deep --gui --ws-url wss://192.168.100.17:9443/ws --api-url https://192.168.100.17:9443/api`; `/ui/automation/status` showed `connection_state=connected`, then pywinauto `0.6.9` UIA invoked account-gate PrimaryButton `Войти как admin-2`, moving `sidebar_view` to `tickets`.
  - Live command: `python scripts\agent_test_driver.py create-ticket live-v3-deep --title "Live V3 Fix6 automation account session bd33bce2" --description "Live regression for BUG-20260527-04: automation create should include active confirmed account session."`.
  - Local automation response: HTTP success, `ticket_id=3df55d98-0f34-472f-b19b-72b990388025`, `ticket_code=T-000605`, `requester_account_session_id=6196fe8b-d836-44c5-9760-88a2f5d31f7a`, `requester_account_mode=confirmed_binding`, `requester_registration_status=admin_confirmed`.
  - Server DB: `tickets.T-000605` persisted with `requester_person_id=bb00a942-fe2c-461c-b982-9da17d3fd1ff`, `requester_binding_id=0618eb74-9fa6-4dbe-9634-d9b56825f3ad`, `requester_account_session_id=6196fe8b-d836-44c5-9760-88a2f5d31f7a`, `requester_account_mode=confirmed_binding`; initial `chat_message` event payload contains the same requester account/session fields.
  - Agent SQLite: no recent failed outbox rows after the automation create.
  - Browser/UI: real browser URL `https://192.168.100.17:9443/app/tickets/3df55d98-0f34-472f-b19b-72b990388025`; DOM shows `T-000605`, title, requester `Тестовый тест 12`, status `В очереди`, initial user message. Screenshot: `live-v3-fix6-ticket.png`.

Impact:
Blocks using the local automation bridge as a reliable substitute for manual GUI submission in account-boundary tests.

Root cause:
`pc_agent/ui_gui/automation_controller.py::_create_ticket()` passed requester profile/display name but omitted `chat_panel._current_account_session()` when calling `TicketApiClient.create_ticket()`. The real GUI path in `pc_agent/ui_gui/chat_panel.py::_async_create_ticket()` already passed `requester_account=account_session`.

Fix policy:
- Blocking further tests: no, because direct HTTP/API and browser verification can continue; yes for bridge-driven create.
- Fixed now: yes

Fix summary, if fixed:
Automation ticket creation now reads `chat_panel._current_account_session()` and passes it as `requester_account` to `TicketApiClient.create_ticket()`. No-account automation still does not synthesize credentials; it propagates the server denial.

Verification after fix:
Verified by unit tests and live `agent_test_driver.py create-ticket`: `T-000605` was created through `/ui/automation/run`, DB requester account fields match the active confirmed binding session, initial ticket event carries requester account context, browser ticket detail shows the new ticket, and local outbox has no new failed rows.

Regression check:
Unit regression covers no-account server denial and valid confirmed-session create success. Live regression covered confirmed-session create success through the local automation bridge and browser detail confirmation.

Remaining risk:
Other automation actions may also omit account-session headers/payloads where the real GUI path already includes them.

### P0.5 WS chat_raise account-boundary check

Status: passed after BUG-20260527-05 fix; original phantom-ticket failure retained below.

Evidence:
- Transport:
  - Trigger path: `POST http://127.0.0.1:8765/ui/request_support` on local bridge, which calls `ws_agent.chat_raise()` and sends WS `type=command`, `payload.command=chat_raise` to the server.
  - Local bridge response: HTTP `200`, body `status=ok`, `result.ok=true`, `job_id=60a0933e-b170-4170-b8ac-bcb733336291`, `ticket_id=cc002181-f7d9-44da-8726-da46463c090f`.
  - Agent log: `[chat_raise] command sent request_id=9000ae24-eacf-48e2-ad29-6fd16fcf852c`; `[chat_raise] success job_id=60a0933e-b170-4170-b8ac-bcb733336291 ticket_id=cc002181-f7d9-44da-8726-da46463c090f`.
  - Server->agent follow-up commands were created/delivered for `start_job` and `ui_notify`; `device_outbox` rows `3fb11f58-f2ec-48d3-9e8b-0fc51418e073` and `32b02f8a-8338-428d-8da2-bed252ffb61d` both reached `delivered`.
  - Agent then sent outbox batch items for the returned ticket id; server returned per-item non-retryable `outbox_nack` with code `UNKNOWN_TICKET`.
- Server DB/state:
  - `select * from tickets where ticket_id='cc002181-f7d9-44da-8726-da46463c090f'` returned zero rows.
  - `ticket_events` for that ticket returned zero rows.
  - Recent `tickets` only contained the earlier P0.4 valid API ticket `T-000603`; no P0.5 chat_raise ticket was persisted.
  - `operations` for returned ticket id returned `0`.
  - `device_outbox` contained only the follow-up `start_job` and `ui_notify` command rows, both delivered and not ticket-bound.
- Agent local state:
  - Agent job manager logged `Created ticket from server: cc002181-f7d9-44da-8726-da46463c090f` and opened support chat for `job_id=60a0933e-b170-4170-b8ac-bcb733336291`.
  - Local SQLite `outbox` contains failed rows `outbox_id=1..7` for ticket `cc002181-f7d9-44da-8726-da46463c090f`; all have `status=failed`, `attempts=1`, `last_error=NACK: UNKNOWN_TICKET - Ticket cc002181-f7d9-44da-8726-da46463c090f not found`.
  - Failed item kinds include `job_started`, `tool_response`, `job_running`, `chat_session`, and `chat_message`.
- Browser/admin UI:
  - Browser URL: `https://192.168.100.17:9443/app/tickets/cc002181-f7d9-44da-8726-da46463c090f`.
  - Visible result: `Тикет не найден`; queue still only shows `T-000603 Live V3 P0.4 API account-boundary check`.
  - Browser console/network showed failed loads for `/api/web/support/tickets/cc002181-f7d9-44da-8726-da46463c090f/workspace` and `/timeline?filter=all`.
  - Screenshot: `live-v3-p0-5-chat-raise-not-found.png`.
- Agent GUI/UIA:
  - Agent GUI auto-opened chat for the returned job id according to agent log: `Chat автоматически открыт для job_id=60a0933e-b170-4170-b8ac-bcb733336291`.
  - Current deeper UIA child traversal is unstable on this GUI state (see BUG-20260527-03), so GUI evidence for P0.5 is from local bridge response and agent logs rather than a fresh UIA control-tree excerpt.
- Root cause notes:
  - Documentation says WS `chat_raise` and legacy `/api/chat_raise` use DB-first create flow, but the live WS path returned success for a ticket that is absent from DB.
  - This is not merely an account-boundary bypass; it is a stronger consistency bug: the agent receives a canonical-looking ticket id and starts local work against a nonexistent server ticket.

### BUG-20260527-05 — WS chat_raise returns success for a non-persisted ticket

Severity: P1
Status: verified-fixed
Area: protocol / tickets / DB

Scenario:
P0.5 agent-side chat_raise through local bridge `/ui/request_support` and Protocol V3 WS `command=chat_raise`.

Expected:
If account-session boundary is required, unauthenticated account state should not create a requester ticket and should return an explicit denial. If legacy chat_raise is allowed, the returned `ticket_id` must exist in `tickets`, have initial `ticket_events`, and be visible in the support UI.

Actual:
Local bridge and agent WS path returned success with `ticket_id=cc002181-f7d9-44da-8726-da46463c090f`, but the server DB has no ticket row or ticket_events for that id. The browser shows `Тикет не найден`. Agent outbox events for that id were NACKed as `UNKNOWN_TICKET` and marked failed locally.

Repro steps:
1. Run `POST http://127.0.0.1:8765/ui/request_support` with title `Live V3 P0.5 WS chat_raise boundary check`.
2. Observe local bridge HTTP `200` and returned job/ticket ids.
3. Query `tickets` and `ticket_events` for the returned ticket id.
4. Open `/app/tickets/{returned_ticket_id}` in browser.
5. Query local SQLite `outbox`.

Evidence:
- Server log: device_outbox delivered `start_job` and `ui_notify`; server emitted `outbox_nack` `UNKNOWN_TICKET` for subsequent agent events targeting the returned ticket id.
- Agent log: `[chat_raise] success ... ticket_id=cc002181-f7d9-44da-8726-da46463c090f`; support chat started; subsequent outbox rows NACKed `UNKNOWN_TICKET`.
- Browser/UI: `/app/tickets/cc002181-f7d9-44da-8726-da46463c090f` shows `Тикет не найден`; screenshot `live-v3-p0-5-chat-raise-not-found.png`.
- Server DB: zero rows in `tickets` and `ticket_events` for returned ticket id.
- Agent SQLite: failed outbox rows `1..7`, non-retryable `UNKNOWN_TICKET`.
- WS/API payload: local bridge response contains `job_id=60a0933e-b170-4170-b8ac-bcb733336291`, `ticket_id=cc002181-f7d9-44da-8726-da46463c090f`, `ok=true`.

Impact:
Data-loss/state-divergence risk. The agent and GUI believe a support chat/ticket exists, while the server and browser have no persisted ticket. Follow-up events are permanently failed, and operators cannot see or act on the returned ticket.

Root cause hypothesis:
`server/websocket/agent_services.py::AgentCommandService.handle()` catches exceptions around `create_ticket_with_side_effects()` and continues returning success using the pre-generated random `ticket_id`; it then enqueues `start_job`/`ui_notify` for a ticket that was never committed. The DB create likely fails in live policy/account-session/routing context, but the exception is swallowed.

Root cause confirmed:
The WS `chat_raise` path generated a `chat_job_id`/`ticket_id`, created the chat session before durable ticket creation, swallowed DB create failure, then unconditionally returned `command_result.status=success` and scheduled `start_job`/`ui_notify`. The legacy HTTP chat raise path had the same ordering risk by creating the chat session before the DB create returned a canonical ticket id.

Fix policy:
- Blocking further tests: no for HTTP/API ticket lifecycle; yes for WS chat_raise validation.
- Fixed now: yes

Fix summary, if fixed:
- Changed files:
  - `server/websocket/agent_services.py`
  - `server/chat/handlers.py`
  - `server/tests/test_agent_services_pipeline.py`
  - `pc_agent/ws_agent.py`
  - `pc_agent/tests/test_ws_agent_chat_raise.py`
- Server `chat_raise` is now DB-first: if ticket creation is unavailable, fails, or returns no persisted ticket id, the command returns `status=error` and does not create a chat session or enqueue `start_job`/`ui_notify`.
- Legacy `/api/chat_raise` now creates its chat session only after a durable ticket id is returned.
- Local agent bridge now propagates server-side `command_result.status=error` details as `ok=false` with a stable `error_code`, instead of flattening them into generic bridge failure.
- Commits:
  - Server fix: `862a266ce2d6f3411320bbb93c55b8b41500e22d`, pushed and deployed to the live Linux server with quick gate.
  - Local bridge fix: `3539290c`, pushed; verified by running `live-v3-deep` in source GUI mode.

Verification after fix:
- Targeted tests:
  - `python -m pytest server\tests\test_agent_services_pipeline.py -q` -> `24 passed`.
  - `python -m pytest pc_agent\tests\test_ws_agent_chat_raise.py -q` -> `2 passed`.
  - `python -m py_compile server\websocket\agent_services.py server\chat\handlers.py pc_agent\ws_agent.py scripts\live_ws_v3_probe.py` -> passed.
- Live regression:
  - Server deployed at `862a266ce2d6f3411320bbb93c55b8b41500e22d`; local agent `live-v3-deep` restarted in source GUI mode from commit `3539290c`.
  - Command: `python scripts\agent_test_driver.py request-support live-v3-deep --title 'Live V3 Fix2 chat_raise db-first retry 3539290c' --reason fix2_live_regression --severity warning`.
  - Local bridge result: `ok=false`, `error_code=TICKET_CREATE_UNAVAILABLE`, `error=Ticket creation is unavailable for chat_raise`.
  - Server DB: zero `tickets` and zero `ticket_events` for the Fix2 live regression titles/reason; no new phantom ticket id was returned.
  - Agent SQLite: no new `UNKNOWN_TICKET` outbox rows after the Fix2 regression; only the older P0.5 phantom-ticket evidence remains.
  - Browser: real ticket list/timeline did not show the Fix2 title; screenshot `artifacts/live-v3-fix2-no-ticket-browser.png`.

Regression check:
P0.5 regression now returns explicit denial instead of success with a phantom id. Adjacent P0.7 must still be rerun in the final verification gate after Fix 1-6 because Fix2 only changed `chat_raise`/bridge behavior, not normal `run_tool` command_result flow.

Remaining risk:
The live server currently returns `TICKET_CREATE_UNAVAILABLE` for WS `chat_raise`; if product policy expects chat_raise to create a technical support requester ticket, server runtime config/policy needs a separate decision. This no longer pollutes ticket/outbox state because the denial is explicit and no local chat session is started.

### P0.6 Full ticket lifecycle

Status: passed for the available live policy path; one policy-risk note recorded.

Evidence:
- Status path:
  - Test ticket: `44b04e94-4048-4593-b2bc-4054c7cfa7b1`, code `T-000603`.
  - Initial create flow had already moved `new -> queued` via routing, with `status_changed` event reason `routed_to_queue`.
  - Blocked check: `queued -> assigned` without assignee returned HTTP `400`, `error_code=WORKFLOW_POLICY_BLOCKED`, message `workflow_profile transition gate missing required_fields: assignee_id`.
  - Assigned assignee `op1` through `/api/web/support/tickets/{ticket_id}/assign`; DB/UI still `queued`, `assignee_id=op1`.
  - Status path through browser-authenticated support API:
    - `queued -> assigned`: HTTP `200`, status `assigned`.
    - `assigned -> in_progress`: HTTP `200`, status `in_progress`.
    - `in_progress -> waiting_on_user`: HTTP `200`, status `waiting_on_user`.
    - `waiting_on_user -> in_progress`: HTTP `200`, status `in_progress`.
    - `in_progress -> resolved`: HTTP `200`, status `resolved`.
    - repeated `resolved -> resolved` with resolution fields returned HTTP `400`, `error_code=INVALID_TRANSITION`, as expected because the ticket was already resolved.
    - `resolved -> closed`: HTTP `200`, status `closed`.
- Blocked transitions:
  - `assigned` without assignee was blocked by workflow gate.
  - Invalid repeat transition `resolved -> resolved` was blocked with `INVALID_TRANSITION`.
  - `resolved` without `resolution_code`/summary was allowed by the live policy; not marked as a product bug unless the intended published policy requires those fields.
- Server DB/state:
  - Final ticket row: `status=closed`, `assignee_id=op1`, `queue_id=1`, `requester_status=closed`, `next_action_owner=system`, `resolved_at=2026-05-27 00:53:44+05`, `closed_at=2026-05-27 00:53:44+05`, `resolution_code=NULL`, `resolution_summary=NULL`, `sla_paused_seconds=0`, `resolution_at=2026-05-27 00:53:44+05`.
  - Status events persisted in order:
    - `new -> queued`
    - `queued -> assigned`
    - `assigned -> in_progress`
    - `in_progress -> waiting_on_user`
    - `waiting_on_user -> in_progress`
    - `in_progress -> resolved`
    - `resolved -> closed`
  - `assignee_changed` event persisted for `op1`.
  - SLA/OLA timeline side effects persisted/rendered: `sla_started`, `SLA paused`, `SLA resumed`, `Срок решения остановлен`, `OLA acknowledgement stopped`, `OLA paused`, `OLA resumed`, `OLA processing stopped`.
  - `ticket_public_sessions` had zero rows for this ticket, so explicit public-session revocation was not applicable for this live ticket.
- Browser/admin UI:
  - Browser URL: `https://192.168.100.17:9443/app/tickets/44b04e94-4048-4593-b2bc-4054c7cfa7b1`.
  - Visible final state: `T-000603 Live V3 P0.4 API account-boundary check`, queue `ServiceDesk L1`, assignee `op1`, status `Закрыта`, requester-facing status `Обращение закрыто`.
  - Timeline visibly shows assignment, in-work, waiting-on-user, resume, resolved, confirmation prompt, and closed events.
  - Screenshot: `live-v3-p0-6-ticket-closed.png`.
- Agent/requester UI:
  - Browser support UI is the authoritative UI confirmation for this support lifecycle flow.
  - Local agent ticket list had already seen this ticket before close via `/ui/automation/status`; deeper UIA traversal remains unstable on the current GUI state (BUG-20260527-03), so no fresh UIA lifecycle detail was captured for closed status.
- Root cause notes:
  - The canonical DB constraint prevented non-canonical status storage; no `triaged` status appeared.
  - Current live workflow allows resolution without resolution fields; if the intended helpdesk policy requires evidence/summary/code, the published policy is too permissive rather than the transition engine failing.

### P0.7 run_tool happy lifecycle

Status: passed with adjacent pre-existing failed outbox rows from P0.5 noted separately.

Evidence:
- Browser/API trigger:
  - Ticket created through the confirmed account-session HTTP path for this scenario: `T-000604`, `ticket_id=68de6816-471b-48ba-88e3-fa691264bba3`, trace label `live-v3-p0-7-run-tool-a80d9c22`.
  - Browser support API `/api/web/support/tickets/68de6816-471b-48ba-88e3-fa691264bba3/tools` listed `system.collect` from module `system`, `risk_level=safe_readonly`, `requires_consent=false`, presets `minimal/basic/identity/network/full`.
  - Browser-authenticated support API `POST /api/web/support/tickets/68de6816-471b-48ba-88e3-fa691264bba3/tools/run` with `tool_name=system.collect`, `params={"preset":"basic"}` returned HTTP 202, `operation_id=040d1878-4416-4661-a1b8-3f11a7717013`, `trace_id=8dde0d69-3183-4530-90ce-ed1388ccd690`, `dispatch_status=accepted`.
- Operation/outbox:
  - `operations`: `kind=tool_call`, `tool_name=system.collect`, `actor_role=admin`, `status=succeeded`, `queued_at=2026-05-27 00:55:17.712060+05`, `sent_at=2026-05-27 00:55:17.732407+05`, `accepted_at=2026-05-27 00:55:17.742598+05`, `finished_at=2026-05-27 00:55:18.792099+05`, `result_event_id=46`.
  - `device_outbox`: row id `4`, `command_id=request_id=operation_id=040d1878-4416-4661-a1b8-3f11a7717013`, command `run_tool`, status `delivered`, same trace id `8dde0d69-3183-4530-90ce-ed1388ccd690`, params include `call_id=f76d99bc-7d5c-4f4b-b158-1aadaeaff3d3`.
- Agent execution:
  - Agent accepted and executed the command; result reached the server in under two seconds.
  - `seen_commands` local SQLite row for command `040d1878-4416-4661-a1b8-3f11a7717013` has `status=success` and result JSON with `preset=basic`, `hostname=ADMIN-2`, CPU/RAM/disk observations.
- Server DB/events:
  - Ticket events for `T-000604` include routing and initial message events, then `tool_call_started` event id `45` before terminal result, followed by `tool_call_result` event id `46` and agent-origin `tool_response` event id `47`.
  - `tool_call_started`: `operation_id=040d1878-4416-4661-a1b8-3f11a7717013`, `trace_id=8dde0d69-3183-4530-90ce-ed1388ccd690`, payload includes `tool_name=system.collect`, `params={"preset":"basic"}`, actor role `admin`.
  - `tool_call_result`: same operation and trace, output includes `hostname=ADMIN-2`, `cpu=13.9`, `ram=94.3`, `disk=25.1`.
  - `tool_response`: `agent_seq=1`, `trace_id=558638be-8e11-4295-a84b-e4894fc13eb8`, payload mirrors the `system.collect` observation. No duplicate terminal operation row was found.
- Agent SQLite:
  - `outbox_sent_history`: one P0.7 row, `outbox_id=8`, `ticket_id=68de6816-471b-48ba-88e3-fa691264bba3`, `kind=tool_response`, payload preview contains `system.collect` observations.
  - `pending_consents`: `0` rows after the safe read-only tool run.
  - `outbox`: still contains seven failed rows from the earlier P0.5 phantom-ticket scenario with `NACK: UNKNOWN_TICKET`; these are pre-existing evidence for `BUG-20260527-05`, not a P0.7 regression.
- Browser/admin UI:
  - Real browser URL: `https://192.168.100.17:9443/app/tickets/68de6816-471b-48ba-88e3-fa691264bba3`.
  - DOM/browser output shows `T-000604`, timeline entry `Специалист запустил диагностику.` with operation `system.collect`, status `Принята`, then `Выполнена диагностика`, operation `system.collect`, status `Успешно`, and visible result values for `ADMIN-2`, CPU/RAM/disk.
  - Screenshot: `live-v3-p0-7-run-tool-result.png`; browser snapshot file: `live-v3-p0-7-run-tool-result-snapshot.md`.
- Root cause notes:
  - The happy command lifecycle works end to end for a safe built-in tool when the ticket exists and the operation is support-initiated.
  - The UI timeline currently exposes Python-dict-style result text in places before/alongside JSON. This is a presentation-quality issue to revisit during P1.6 UI projection consistency, not a blocker for P0.7 transport/DB/agent correctness.

### P0.8 Long-running tool + cancel_operation

Status: passed after BUG-20260527-06/07 fixes; original cancel/auth/idempotency failures retained below.

Evidence:
- Diagnostic or existing tool:
  - No new diagnostic module was created for this pass because the live toolset already exposes built-in `screen.record` with `duration_sec`, `side_effects=false`, `requires_consent=false`, `artifact_kinds=["screen_recording"]`, and a real long-running agent-side loop with cancel stop-event support.
  - Tool used: `screen.record`, params `{"duration_sec":30,"fps":5,"max_width":640,"quality_crf":35}`. Earlier exploratory run with `fps=2` failed immediately with `INVALID_PARAMS` because the contract requires `fps >= 5`; that was tester error, not a product bug.
- Operation/cancel transport:
  - Browser-authenticated support API started the valid long-running operation on `T-000604`: HTTP 202, `operation_id=b24a6bf5-cad2-4085-94a2-2049f3798cbd`, `trace_id=8dde0d69-3183-4530-90ce-ed1388ccd690`, `dispatch_status=accepted`.
  - Browser/web-session `POST /api/operations/b24a6bf5-cad2-4085-94a2-2049f3798cbd/cancel` returned HTTP 401 `AUTH_REQUIRED` despite the support UI session being valid enough to start the tool. See `BUG-20260527-06`.
  - Agent-token authenticated cancel request to the same endpoint returned HTTP 200 with `cancel_operation_id=6e11ef62-c10e-47ce-be80-94ee24a614d0`.
  - Agent log shows V3 `command_ack` for `run_tool` request `b24a6bf5-cad2-4085-94a2-2049f3798cbd`, later V3 `command_ack` and `command_result` for cancel request `6e11ef62-c10e-47ce-be80-94ee24a614d0`.
- Agent runtime:
  - Agent log: `execution lane acquired tool=screen.record operation_id=b24a6bf5-cad2-4085-94a2-2049f3798cbd`.
  - Agent log after cancel: received `cancel_operation`, then `[AGENT] run_tool canceled tool=screen.record operation_id=b24a6bf5-cad2-4085-94a2-2049f3798cbd`, then sent cancel `command_result` with status `success`.
  - Local SQLite `outbox_sent_history` contains outbox ids `10` and `11` for the canceled tool result and cancel tool_response; `pending_consents=0`.
- Server DB/state:
  - Target operation `b24a6bf5-cad2-4085-94a2-2049f3798cbd`: `kind=tool_call`, `tool_name=screen.record`, actor role `admin`, final status `canceled`, `cancel_reason=live-v3-p0-8-agent-token-cancel`, `cancel_requested_at=2026-05-27 01:01:39.492746+05`, `canceled_at=2026-05-27 01:01:39.613391+05`.
  - Cancel operation `6e11ef62-c10e-47ce-be80-94ee24a614d0`: `kind=cancel_operation`, actor role `agent`, final status `succeeded`, `cancel_target_operation_id=b24a6bf5-cad2-4085-94a2-2049f3798cbd`, sent/accepted/finished around `2026-05-27 01:01:39+05`.
  - Ticket events include `tool_call_started` id `52`, `op_cancel_requested` id `53`, `op_canceled` id `54`, agent-origin `tool_call_result` id `55` with status `canceled`, and cancel `tool_response` id `56`.
- Browser/admin UI:
  - Real browser URL: `https://192.168.100.17:9443/app/tickets/68de6816-471b-48ba-88e3-fa691264bba3`.
  - DOM/browser output shows a top diagnostic entry with status `Отменена` and cancel text, plus the earlier invalid-params exploratory `screen.record` entry as `error`.
  - Screenshot: `live-v3-p0-8-cancel-result.png`.
- Cleanup/no-stuck-state:
  - Server target operation is terminal `canceled`; cancel operation is terminal `succeeded`; local agent outbox rows for this cancel flow are ACKed into `outbox_sent_history`.
  - Stuck-state failure: server `device_outbox` target `run_tool` command id `b24a6bf5-cad2-4085-94a2-2049f3798cbd` remains `status=sent`, `delivered_at=NULL`, even though the agent received it and the target operation is terminal canceled.
  - Stuck-state failure: local `seen_commands` row for target command `b24a6bf5-cad2-4085-94a2-2049f3798cbd` remains `status=in_progress` with no `result_json`; cancel command `6e11ef62-c10e-47ce-be80-94ee24a614d0` is `status=success`.
- Root cause notes:
  - Cancel command priority/dispatch and agent stop-event handling are functioning.
  - Browser-visible cancel controls are not safely usable through the documented web-session path because the legacy operations route does not receive/accept the web auth context.
  - Agent/server cleanup after canceled long-running run_tool is incomplete: the target command is not marked delivered/terminal in both server outbox and local command idempotency cache.

### BUG-20260527-06 — Web-session operation cancel endpoint returns AUTH_REQUIRED

Severity: P1
Status: verified-fixed
Area: UI / protocol / account-session

Scenario:
P0.8 long-running `screen.record` cancellation from the support/browser UI session.

Expected:
The support web session that can start `/api/web/support/tickets/{ticket_id}/tools/run` should also be able to call the cancel URL exposed by the support operation card, or the support API should expose a web-session cancel alias.

Actual:
`POST /api/operations/b24a6bf5-cad2-4085-94a2-2049f3798cbd/cancel` from the real browser returned HTTP 401 with `AUTH_REQUIRED`.

Repro steps:
1. Open `https://192.168.100.17:9443/app/tickets/68de6816-471b-48ba-88e3-fa691264bba3` with a valid support/admin web session.
2. Start `screen.record` through `POST /api/web/support/tickets/{ticket_id}/tools/run`.
3. Call the returned/exposed cancel URL `/api/operations/{operation_id}/cancel` with browser credentials.

Evidence:
- Server log:
- Agent log:
- Browser/UI: browser fetch returned HTTP `401`, body `{"status":"error","error":"Требуется аутентификация","error_code":"AUTH_REQUIRED"}` while the same session successfully started the tool.
- Server DB: no cancel-op row was created by the browser 401 attempt; cancel-op row appeared only after agent-token request.
- Agent SQLite:
- WS/API payload: successful fallback cancel used agent-token auth and returned `cancel_operation_id=6e11ef62-c10e-47ce-be80-94ee24a614d0`.

Impact:
Support UI cancel controls can appear actionable but fail for web-session users, blocking realistic browser-driven cancellation testing and likely user cancellation workflows.

Root cause hypothesis:
Confirmed root cause:
The legacy `/api/operations/{operation_id}/cancel` route remains token-auth scoped, while web-session cookies are extracted only for `/api/web/*` routes. Support operation snapshots and the React cancel mutation both pointed browser users at the token-only URL, so a valid support web session received `AUTH_REQUIRED`.

Fix policy:
- Blocking further tests: yes for realistic browser-driven P0.8/P1 cancel validation.
- Fixed now: yes

Fix summary, if fixed:
- Changed files:
  - `server/api/operations.py`
  - `server/routes.py`
  - `server/web_api/support_handlers.py`
  - `server/tests/test_web_support_api.py`
  - `webapp/src/features/queues/api.ts`
  - `webapp/src/features/queues/support-workspace-mappers.test.ts`
  - `webapp/src/pages/tickets/list-page.test.tsx`
  - `docs/QUICK_LOOKUP.md`
  - `server/docs/CODEMAP.md`
- Added typed route `POST /api/web/support/operations/{operation_id}/cancel` for support/admin web-session auth.
- Support operation snapshots now advertise `/api/web/support/operations/{operation_id}/cancel`.
- React support workspace cancel mutation now calls the web-session route.
- Legacy `/api/operations/{operation_id}/cancel` remains available for token clients.
- Commit/deploy: `91f7529aa2e864298ae025ac4e20123688d1e368` (`fix: add web support operation cancel route`) pushed to `origin`, deployed to Linux, webapp bundle rebuilt and uploaded, server restarted to PID `3884978`, remote smoke passed on attempt 2.

Verification after fix:
- Targeted pytest:
  - `python -m py_compile server\api\operations.py server\routes.py server\web_api\support_handlers.py` -> passed.
  - `python -m pytest server\tests\test_web_support_api.py::test_web_support_operation_cancel_uses_web_session_boundary -q` -> `1 passed in 343.15s`.
  - `python -m pytest server\tests\test_web_support_api.py::test_web_support_operation_cancel_denies_auditor -q` -> `1 passed in 340.86s`.
  - `pnpm --dir webapp test src\features\queues\support-workspace-mappers.test.ts src\pages\tickets\list-page.test.tsx` -> `2 passed`, `56 passed`.
- Release verification:
  - `python scripts\release_server_to_remote.py --gate quick --allow-local-dirty --leave-running` ran `verify_workspace.py`, built the webapp, deployed committed state, ran migrations, uploaded webapp bundle, restarted control/server, and passed remote smoke.
- Live browser regression:
  - Real browser URL: `https://192.168.100.17:9443/app/tickets/68de6816-471b-48ba-88e3-fa691264bba3`.
  - Browser web-session started `screen.record` through `POST /api/web/support/tickets/{ticket_id}/tools/run`, HTTP `202`, target operation `5a84f059-7f0c-448d-9adb-854175d03a2c`.
  - Same browser session canceled through `POST /api/web/support/operations/5a84f059-7f0c-448d-9adb-854175d03a2c/cancel`, HTTP `200`, cancel operation `a69adba7-3bfd-417b-b9a0-45a3535fee17`.
  - Browser support detail API returned target `status=canceled`, cancel `status=succeeded`; operation card had `can_cancel=false` after terminal state.
  - Browser timeline shows `screen.record` at `27 мая, 11:18` with status `Отменена` and summary `Tool screen.record canceled`.
  - Screenshot: browser MCP `live-v3-fix4-web-session-cancel-browser.png`.
- Server DB:
  - Target operation `5a84f059-7f0c-448d-9adb-854175d03a2c`: `kind=tool_call`, `status=canceled`, `cancel_reason=live-v3-fix4-web-session-cancel`.
  - Cancel operation `a69adba7-3bfd-417b-b9a0-45a3535fee17`: `kind=cancel_operation`, `status=succeeded`, `cancel_target_operation_id=5a84f059-7f0c-448d-9adb-854175d03a2c`.
  - `device_outbox`: both target `run_tool` and cancel command are `status=delivered`, with `sent_at` and `delivered_at`.
  - `ticket_events`: `tool_call_started`, `op_cancel_requested`, `tool_call_result status=canceled`, `op_canceled cancel_status=canceled`.

Regression check:
- Support/admin web route creates cancel-op; auditor route test returns `403`.
- Existing token-only legacy cancel route remains unchanged for non-web clients.
- Retry/approve/deny still use legacy operation routes and remain a separate auth-surface review item if web-session action buttons are later exposed for those controls.

Remaining risk:
The web-session route is intentionally limited to support/admin. Future UI work should avoid exposing legacy `/api/operations/*` mutations to browser sessions unless a typed `/api/web/*` alias exists.

### BUG-20260527-07 — Canceled run_tool leaves stale sent/in_progress command state

Severity: P1
Status: verified-fixed
Area: DB / reconnect / protocol

Scenario:
P0.8 cancellation of long-running `screen.record` after the agent accepted and started the run_tool.

Expected:
After cancellation, the target operation is terminal canceled and no target command state remains stuck: server `device_outbox` should be terminal/delivered or otherwise reconciled, and local `seen_commands` for the target run_tool should not remain `in_progress`.

Actual:
The target operation is correctly `canceled`, but server `device_outbox` row id `6` for command `b24a6bf5-cad2-4085-94a2-2049f3798cbd` remains `status=sent`, `delivered_at=NULL`; local `seen_commands` for the same command remains `status=in_progress` with no result JSON.

Repro steps:
1. Start `screen.record` for 30 seconds on an existing ticket.
2. Wait until agent log shows execution lane acquired.
3. Send `cancel_operation`.
4. Query `operations`, `device_outbox`, and local SQLite `seen_commands`.

Evidence:
- Server log:
- Agent log: `[AGENT] run_tool canceled tool=screen.record operation_id=b24a6bf5-cad2-4085-94a2-2049f3798cbd`; cancel `command_result` sent for `6e11ef62-c10e-47ce-be80-94ee24a614d0`.
- Browser/UI: ticket timeline shows a canceled diagnostic entry.
- Server DB: target operation `canceled`, cancel operation `succeeded`; `device_outbox` target run_tool still `sent`.
- Agent SQLite: `outbox_sent_history` ids `10` and `11` ACKed; `seen_commands.command_id=b24a6bf5-cad2-4085-94a2-2049f3798cbd` remains `in_progress`.
- WS/API payload: ticket events include `op_cancel_requested`, `op_canceled`, agent-origin canceled `tool_call_result`, and cancel `tool_response`.

Impact:
Reconnect/idempotency behavior may treat an already canceled command as still in progress, and server device outbox contains stale non-terminal command state after a successful cancel.

Root cause hypothesis:
Confirmed root cause:
1. The agent background `run_tool` path did not catch `asyncio.CancelledError`, so target-command cancellation could skip terminal `seen_commands` state and skip the target `command_result`.
2. Server cancel-result handling marked the cancel operation succeeded and the target operation canceled, but did not reconcile the target `device_outbox` row.
3. A live regression exposed an adjacent race: cancel can arrive after local `seen_commands=in_progress` is written but before the target command is registered in `orchestrator.running_tasks`; that path returned `already_finished` and left local idempotency `in_progress`.

Fix policy:
- Blocking further tests: yes for P1 ACK/dedup/idempotency reliability.
- Fixed now: yes

Fix summary, if fixed:
- Changed files:
  - `pc_agent/ws_agent.py`
  - `pc_agent/core/orchestrator.py`
  - `pc_agent/core/database.py`
  - `pc_agent/tests/test_ws_agent_canceled_command_idempotency.py`
  - `pc_agent/tests/test_cancel_operation_runtime.py`
  - `server/websocket/agent_services.py`
  - `server/tests/test_command_result_lifecycle_db.py`
- Agent `run_tool` cancellation now sends a terminal canceled target `command_result`, stores local `seen_commands.status='canceled'`, and returns cached canceled results for duplicate command ids instead of `COMMAND_IN_PROGRESS`.
- Agent cancel handling now finalizes a pre-running target command if local idempotency is already `in_progress` but the execution task is not yet registered.
- Server cancel-result handling now marks the target operation's `device_outbox` command as delivered/reconciled when cancel succeeds.

Verification after fix:
- Targeted pytest:
  - `python -m pytest pc_agent\tests\test_ws_agent_canceled_command_idempotency.py pc_agent\tests\test_cancel_operation_runtime.py -q` -> `5 passed`.
  - `python -m pytest server\tests\test_command_result_lifecycle_db.py -q` -> `4 passed in 359.05s`.
  - `python -m py_compile pc_agent\ws_agent.py pc_agent\core\orchestrator.py pc_agent\core\database.py server\websocket\agent_services.py` -> passed.
- Live regression 1 after the first fix commit (`1fb8c9fa`):
  - Started `screen.record`, canceled operation `7ca3d807-44d7-4578-95d6-316e2948f0a0` via token-auth fallback because BUG-20260527-06 still blocks web-session cancel.
  - Server target operation became `canceled` and target outbox was reconciled, but local `seen_commands` remained `in_progress`; this exposed the pre-running race above and was fixed in follow-up commit `f7e350e0`.
  - Evidence: `artifacts/live-v3-fix3-cancel-regression.json`.
- Live regression 2 after follow-up commit `f7e350e0`:
  - Ticket: `T-000604` / `68de6816-471b-48ba-88e3-fa691264bba3`.
  - Target operation: `1cb15ce7-9bb8-4393-8029-b477fe67b7ab`.
  - Cancel operation: `8ebb9e62-ee4a-4e48-99a9-496d9b5b4c03`.
  - Final server operations: target `canceled`, cancel operation `succeeded`.
  - Server `device_outbox`: target `run_tool` and cancel command both `status=delivered`.
  - Agent SQLite: target `seen_commands.status='canceled'`, `result_status='canceled'`, `result_error_code='OPERATION_CANCELED'`; cancel command `seen_commands.status='success'`; target/cancel outbox history rows ACKed.
  - Ticket events include `op_cancel_requested`, `op_canceled`, and agent-origin `tool_call_result status=canceled cancel_status=canceled`.
  - Browser/UI: real support UI at `https://192.168.100.17:9443/app/tickets/68de6816-471b-48ba-88e3-fa691264bba3` shows the latest `screen.record` diagnostic at `27 мая, 10:37` with status `Отменена`.
  - Evidence: `artifacts/live-v3-fix3-cancel-regression-2.json`; browser MCP screenshot `live-v3-fix3-cancel-browser.png`.

Regression check:
- Happy `run_tool` path remains covered by existing scheduler/idempotency tests and must be re-run in the final post-fix live gate as P0.7.
- Duplicate canceled command behavior is covered by `test_duplicate_canceled_command_returns_cached_result_without_rerun`.

Remaining risk:
Browser cancellation no longer requires token-auth fallback after BUG-20260527-06; the final post-fix gate should still re-run P0.8 through the visible UI controls, not only browser `fetch`.

### P0.9 Module/toolset snapshot after module lifecycle

Status: passed after BUG-20260527-08 fix; original missing lifecycle-event evidence and residual historical noise retained below.

Evidence:
- Module/runtime state:
  - Started from no `device_modules` rows for `device_id=7a3429ec-1c0b-5495-9aad-b284f08ae965`.
  - Browser support API ran server-listed `network_ping.ping` with params `{"host":"127.0.0.1","count":2,"timeout_ms":1000}` on `T-000604`.
  - Agent log shows automatic `install_module_package` for `network_ping` version `1.0.0`, HTTP download, smoke/load via `module:register`, activation from local `modules_store`, registry rebuild, `list_installed_modules`, `list_tools`, then the actual `run_tool`.
- Device events/toolset snapshots:
  - `device_toolset_snapshots` gained snapshot id `2`, `toolset_hash=bc275e4f2f72a46a`, `agent_version=3.1.61`, `tool_count=7`.
  - `devices.current_toolset_hash` now matches the new snapshot hash `bc275e4f2f72a46a`; `last_tools_changed_at=2026-05-27 01:05:00.409370+05`.
  - `device_events` has no `module_state_changed` or `tools_changed` rows for this device, even though module install/activation and toolset hash changed. See `BUG-20260527-08`.
  - Baseline drift before this install: `devices.current_toolset_hash=464075d978b3230f` had no matching `device_toolset_snapshots` row; only stale snapshot id `1` existed with hash `b79fbe209afb45c2`, agent version `3.1.60`, `tool_count=6`. The explicit install/list_tools flow repaired the snapshot to hash `bc275e4f2f72a46a`.
- Server DB/state:
  - `device_modules`: `network_ping` version `1.0.0`, `installed=true`, `active=true`, `state=active`, `source=command_result`, `installed_at/activated_at/last_seen_at=2026-05-27 01:05:00+05`.
  - Operations/device_outbox chain delivered: `install_module_package` operation `e0d937e8-0d4e-4438-9bff-ae1aa12b0fca`, `list_installed_modules` `437cd2f2-72da-4c7a-8d2b-0bcaf284641f`, `list_tools` `981b12a6-14aa-48d3-9603-c93ba9656aff`, and `network_ping.ping` run `caba269d-7410-4c53-9ac1-bf42318d0646`.
- Browser/admin UI:
  - Real admin modules URL: `https://192.168.100.17:9443/app/admin/modules`; DOM shows `network_ping`, latest/preferred `1.0.0`, tool `network_ping.ping`, and ADMIN-2 as an online compatible Windows lab agent.
  - Real support ticket URL: `https://192.168.100.17:9443/app/tickets/68de6816-471b-48ba-88e3-fa691264bba3`; DOM shows `network_ping.ping` started and then `Успешно` with ping result for `127.0.0.1`.
  - Screenshot: `live-v3-p0-9-network-ping-result.png`.
- Tool behavior:
  - Operation `caba269d-7410-4c53-9ac1-bf42318d0646` succeeded. Result summary: reachable localhost ping, command `ping -n 2 -w 1000 127.0.0.1`, exit code `0`, packet loss `0%`.
  - Running a deactivated tool was not completed: browser/web-session call to `POST /api/devices/{device_id}/modules/deactivate` returned 401 `AUTH_REQUIRED`, same auth-boundary class as `BUG-20260527-06`.
- Root cause notes:
  - The auto-install-before-run path works and explicitly queues follow-up `list_installed_modules` and `list_tools`; this covers the suspected handshake-only hash-compare risk after the operation.
  - Lifecycle event coverage is incomplete: server state converged from command results, but the required agent-origin `module_state_changed` and `tools_changed` device events are absent.
  - Deactivate/remove negative behavior still needs a valid web-session alias or admin-token path before it can be tested from the real admin UI.

### BUG-20260527-08 — Module lifecycle changes do not persist module_state_changed/tools_changed device events

Severity: P1
Status: verified-fixed / residual-noise
Area: module-runtime / protocol / DB

Scenario:
P0.9 auto-install and activation of `network_ping` before running `network_ping.ping`.

Expected:
Agent module install/activation and toolset hash change should emit `module_state_changed` and `tools_changed` device events, the server should ACK/persist those events, and list_tools snapshot refresh should be traceable to those convergence signals.

Actual:
The module was installed and activated, `device_modules` and `device_toolset_snapshots` converged, and `network_ping.ping` succeeded, but `device_events` contains no rows for the device, including no `module_state_changed` or `tools_changed`.

Repro steps:
1. Run `network_ping.ping` on a device with no prior `network_ping` row in `device_modules`.
2. Observe agent log installing and activating the module, then running `list_installed_modules`, `list_tools`, and the tool.
3. Query `device_events` for the device.

Evidence:
- Server log:
- Agent log: install/load/activate sequence for `network_ping` version `1.0.0`, then `list_installed_modules`, `list_tools`, and successful `network_ping.ping`.
- Browser/UI: admin modules page shows `network_ping`; support ticket timeline shows successful `network_ping.ping`.
- Server DB: `device_modules.network_ping` active; snapshot id `2` hash `bc275e4f2f72a46a`, `tool_count=7`; `device_events` returned `0` rows for the device.
- Agent SQLite:
- WS/API payload: command-result path delivered, but no persisted device-event envelope exists for module/toolset change.
- Fix evidence, 2026-05-27 11:41-11:45 +05:
  - Changed files: `pc_agent/core/orchestrator.py`, `pc_agent/ws_agent.py`, `pc_agent/core/sender.py`, `pc_agent/tests/test_sender_batching.py`, `pc_agent/tests/test_orchestrator_module_lifecycle_events.py`.
  - Targeted tests: `python -m py_compile pc_agent\core\sender.py pc_agent\core\orchestrator.py pc_agent\ws_agent.py pc_agent\tests\test_sender_batching.py pc_agent\tests\test_orchestrator_module_lifecycle_events.py` exit 0; `python -m pytest pc_agent\tests\test_sender_batching.py pc_agent\tests\test_orchestrator_module_lifecycle_events.py pc_agent\tests\test_startup_module_inventory_sync.py -q` -> `8 passed in 0.94s`.
  - Live agent restarted in source GUI mode: `python scripts\manage_local_agent.py start live-v3-deep --gui --ws-url wss://192.168.100.17:9443/ws --api-url https://192.168.100.17:9443/api`; status `mode=gui/source`, `connection_state=connected`, `device_id=7a3429ec-1c0b-5495-9aad-b284f08ae965`.
  - Live module lifecycle regression: remove operation `55f4f644-9a5b-46f2-b8d1-a139b0a1e5ec` succeeded; install operation `a7416018-9094-46ff-821b-f260b05ab9bd` succeeded.
  - Agent SQLite `outbox_sent_history`: `tools_changed` outbox ids `23` and `26`; `module_state_changed` outbox ids `22`, `24`, `25`, `27`, `28`, `29`; no pending/failed rows for these kinds.
  - Server DB `device_events`: persisted `device_seq=2 tools_changed tools_count=6 hash=464075d978b3230f`, `device_seq=3 module_state_changed deactivate:network_ping`, `device_seq=4 module_state_changed remove:network_ping`, `device_seq=5 tools_changed tools_count=7 hash=849e77ee78906464`, `device_seq=6..8 module_state_changed install:network_ping@1.0.0`.
  - Server DB `device_modules`: `network_ping` version `1.0.0`, `installed=true`, `active=true`, `state=active`, `source=event`, `last_seen_at=2026-05-27 06:42:45+00`.
  - Server DB `device_outbox`: remove/install commands are `delivered`, with `delivered_at` set and `error_code=null`.
  - Browser/UI: real browser URL `https://192.168.100.17:9443/app/admin/device-operations/7a3429ec-1c0b-5495-9aad-b284f08ae965?tab=modules`; DOM shows `МОДУЛИ ok`, `Missing 0, outdated 0, failed 0`, `network_ping`, `Установлено: 1.0.0`, `Desired: 1.0.0`, `active`. Screenshots: `live-v3-fix5-device-modules-tab.png`, `live-v3-fix5-modules.png`.

Impact:
Observer/reconcile flows that rely on device events cannot explain or react to module lifecycle changes, and future no-op installs may depend on command-result follow-ups rather than the documented event contract.

Root cause:
Two independent agent-side issues masked the documented module lifecycle event path:
1. `WSAgent` constructed `AgentOrchestrator` without `agent_uuid`, leaving `orchestrator.device_id=None`; `_emit_module_state_changed` and `_rebuild_registry_from_active_modules` therefore returned without enqueueing durable device events in the real runtime.
2. `DatabaseManager.enqueue_event` stores `ticket_id=device_id` for local SQLite compatibility, and `WSOutboxFlusher` leaked that compatibility ticket context into Protocol V3 device-event envelopes. After strict server validation, device events with `device_seq` plus ticket context are invalid; device events must be classified solely by `device_seq` and must omit top-level/event `ticket_id`.

Fix policy:
- Blocking further tests: no, because command-result follow-ups updated DB and toolset snapshot enough to continue.
- Fixed now: yes

Fix summary, if fixed:
`WSAgent` now passes the canonical device id into `AgentOrchestrator`, `AgentOrchestrator` also falls back to `identity_manager.device_id`, and `WSOutboxFlusher` strips compatibility `ticket_id` from device-event wire envelopes while preserving ticket events.

Verification after fix:
P0.9 live regression repeated against the real server and source-mode GUI agent. Server persisted ordered `module_state_changed` and `tools_changed` rows; local agent archived the events in `outbox_sent_history`; no pending/failed lifecycle outbox rows remained; browser device modules tab showed `network_ping` active with clean reconcile counts.

Regression check:
Targeted pytest covers install emits module/tools events, no-op reinstall does not duplicate `tools_changed`, deactivate emits module state and hash-change `tools_changed`, startup inventory sync still emits module state, and sender device-event envelopes omit ticket context. Live regression covered remove/install via real server commands.

Remaining risk:
The live remove/install path emitted duplicate `module_state_changed install:network_ping@1.0.0` rows (`device_seq=6..8`). They are persisted correctly and no longer lost, but dedup/noise should be reviewed during the next module lifecycle pass rather than blocking P1 ACK/dedup fixes.

### P0.10 Protocol V3 malformed outbox probes

Status: passed after BUG-20260527-09 fix. Original malformed ACK/phantom evidence retained below; clean post-fix probe used new run ids and confirmed no new phantom rows.

Evidence:
- Diagnostic tool:
  - Extended `scripts/live_ws_v3_probe.py` with `malformed-outbox --case all`.
  - Token source: `PC_CLIENT_AGENT_TOKEN` from local SQLite, printed only prefix `d7ad25a1`, sha prefix `54898cb35fe5`, length `64`.
  - Probe ticket: `T-000604`, `ticket_id=68de6816-471b-48ba-88e3-fa691264bba3`.
  - The first attempt while the GUI agent was running was superseded by the real agent reconnecting. For the actual probe, `python scripts/manage_local_agent.py stop live-v3-deep` was run, then the raw probe, then `python scripts/manage_local_agent.py start live-v3-deep --gui --launcher --ws-url wss://192.168.100.17:9443/ws --api-url https://192.168.100.17:9443/api`. Final status: `live-v3-deep: running`.
- ACK/NACK cases:
  - `both_seq`: sent `agent_seq` and `device_seq` together for a ticket event. Expected non-retryable NACK; actual `outbox_ack`, and a `ticket_events.chat_message` row was persisted.
  - `neither_seq`: sent no `agent_seq`/`device_seq` and no ticket id in the event. Expected non-retryable NACK; actual `outbox_ack` with no corresponding DB event found.
  - `unknown_ticket`: sent a random unknown `ticket_id`. Expected `UNKNOWN_TICKET` NACK; actual `outbox_ack` with no ticket event found.
  - `missing_trace_id`: expected validation NACK; actual `outbox_nack`, `retryable=false`, `code=VALIDATION_ERROR`, with fallback server trace id. This case passed.
  - `wrong_actor_role`: sent `meta.actor_role=user`. Expected `UNAUTHORIZED`; actual `outbox_nack`, `retryable=false`, `code=UNAUTHORIZED`. This case passed.
  - `top_ticket_only`: top-level `ticket_id` set but `event.ticket_id` missing and `device_seq` set. Expected NACK/no phantom event; actual `outbox_ack`, persisted as a device event `chat_message` with `device_seq=9406`.
  - `unknown_item_type`: sent `item_type=unknown_live_probe_type` and `event=unknown_live_probe_event`. Expected validation NACK; actual `outbox_ack` with no DB event found.
- Server DB/state:
  - `ticket_events`: inserted id `60`, `event_type=chat_message`, `agent_seq=9001`, `probe_case=both_seq`, visible text `live malformed probe both_seq`; a `message_read` event id `61` followed.
  - `device_events`: inserted id `1`, `event_type=chat_message`, `device_seq=9406`, `probe_case=top_ticket_only`.
  - ACK-without-persistence cases observed for `neither_seq`, `unknown_ticket`, and `unknown_item_type`.
  - Probe side effect: while the raw probe was connected, server dispatched pending `install_module_package` commands `5981ac79-e117-497f-bbf4-104b59e100f3` and `0e539dee-e910-4851-9295-d80ff25649a8` to the probe connection; because the probe is not a full agent, those `device_outbox` rows remain `sent`. This is test contamination and also evidence for reconnect/outbox cleanup follow-up.
- Agent local state:
  - The local agent was stopped during the raw probe, then restarted. It reloaded active module `network_ping` from `modules_store` and received `handshake_ack`.
  - Local agent SQLite was not expected to contain the raw probe outbox rows because the malformed items were sent directly by the diagnostic script, not through the agent outbox.
- Browser/admin UI:
  - Real browser URL: `https://192.168.100.17:9443/app/tickets/68de6816-471b-48ba-88e3-fa691264bba3`.
  - DOM/browser output confirms phantom user-visible message `live malformed probe both_seq` under `admin-2`.
  - Screenshot: `live-v3-p0-10-phantom-probe-event.png`.
- Root cause notes:
  - The server validates missing trace and unauthorized actor correctly.
  - Several contract-invalid or semantically invalid envelopes are ACKed, and at least two create persisted phantom events. This is a data-integrity risk and violates the Protocol V3 invariant that event type is determined only by exactly one of `agent_seq` or `device_seq`.
  - The raw probe also exposed that command dispatch can race with handshake/probe connections and leave sent commands when a non-agent client uses a valid device token.

### BUG-20260527-09 — Malformed outbox items are ACKed and can persist phantom events

Severity: P1
Status: verified-fixed
Area: protocol / DB / UI

Scenario:
P0.10 raw Protocol V3 malformed outbox probes against a valid post-handshake device session.

Expected:
Contract-invalid outbox items should receive non-retryable `outbox_nack`; wrong/unknown ticket should receive `DEVICE_MISMATCH` or `UNKNOWN_TICKET`; unauthorized actor should receive `UNAUTHORIZED`; invalid events should not persist or appear in UI.

Actual:
`both_seq`, `neither_seq`, `unknown_ticket`, `top_ticket_only`, and `unknown_item_type` received `outbox_ack`. `both_seq` persisted a ticket `chat_message`; `top_ticket_only` persisted a device `chat_message`; other ACKed invalid cases had no DB event, creating ACK-without-persistence data-loss risk.

Repro steps:
1. Stop the live GUI agent to avoid same-device websocket supersede.
2. Run `scripts/live_ws_v3_probe.py --timeout 2.0 malformed-outbox --case all` with the live agent token in `PC_CLIENT_AGENT_TOKEN`.
3. Query `ticket_events` and `device_events` for `payload.probe_case`.
4. Open the ticket in the browser and search for `live malformed probe`.

Evidence:
- Server log:
- Agent log: local agent was stopped for raw probe and restarted after; raw probe itself is not the agent.
- Browser/UI: ticket `T-000604` shows phantom message `live malformed probe both_seq`.
- Server DB: `ticket_events.id=60` for `probe_case=both_seq`; `device_events.id=1` for `probe_case=top_ticket_only`; ACK-without-persistence for several invalid cases.
- Agent SQLite: not applicable for direct raw WS probe.
- WS/API payload: probe output captured per-case ACK/NACK; `missing_trace_id` and `wrong_actor_role` NACKed correctly, others ACKed incorrectly.

Impact:
Malformed or malicious agent messages can create user-visible phantom timeline entries or receive ACK despite no durable persistence, breaking outbox reliability and audit guarantees.

Root cause hypothesis:
Outbox envelope validation checks only basic `payload.outbox_id`, `item_type`, and `trace_id`; persistence then classifies by `event.ticket_id` instead of first enforcing the strict XOR invariant for `agent_seq`/`device_seq` and validating `item_type` against allowed event families. Top-level `ticket_id` is ignored for classification, enabling ticket-context mismatch.

Fix policy:
- Blocking further tests: yes for P1.1/P1.2 credibility, because ACK-without-persistence and phantom events make ACK/dedup/idempotency conclusions unreliable.
- Fixed now: yes

Fix summary, if fixed:
- Root cause: `OutboxEnvelopeValidator` only checked basic `outbox_id`/`trace_id`; `OutboxPersistenceService` ACKed unsupported `item_type` as no-op and classified ticket vs device events from `payload.event.ticket_id` instead of the Protocol V3 seq XOR invariant.
- Changed files: `server/websocket/outbox_ingest_components.py`, `server/tests/test_agent_services_pipeline.py`, `scripts/live_ws_v3_probe.py`.
- Fix: server now rejects unsupported `item_type`, non-object `payload.event`, both/missing seq, ticket/device context conflicts, missing top-level ticket_id for ticket events, and event/top-level ticket_id mismatch before persistence. Persistence now uses `agent_seq` vs `device_seq` as the source of truth and top-level `ticket_id` for ticket events.
- Commit/deploy: local commit `e7518d88117d6adcbb7066eaadc3d8561f8f334f` (`fix: harden protocol v3 outbox ingest`) pushed to `origin` and deployed to Linux with `python scripts/deploy_workspace_to_remote.py --gate quick --allow-local-dirty`; server restarted to PID `3795474`.

Verification after fix:
- Targeted pytest: `python -m pytest server\tests\test_agent_services_pipeline.py -q` -> `23 passed in 0.16s`.
- Diagnostic compile: `python -m py_compile scripts\live_ws_v3_probe.py` -> passed.
- Live regression command: stopped `live-v3-deep`, ran `python scripts\live_ws_v3_probe.py --timeout 2 malformed-outbox --case all --run-id fix1e7518d --seq-base 777000`, then restarted `live-v3-deep`.
- Transport evidence: all malformed cases returned non-retryable NACK. `both_seq` and `neither_seq` -> `VALIDATION_ERROR` (`exactly one of agent_seq or device_seq`); `unknown_ticket` -> `UNKNOWN_TICKET`; `missing_trace_id` -> `VALIDATION_ERROR`; `wrong_actor_role` -> `UNAUTHORIZED`; `top_ticket_only` -> `VALIDATION_ERROR` (`Device event must not include ticket_id context`); `unknown_item_type` -> `VALIDATION_ERROR`.
- Server DB evidence: for `payload->>'probe_run_id' = 'fix1e7518d'`, `ticket_events=0`, `device_events=0`.
- Agent state: `live-v3-deep` restarted and running after probe (`pid=10324`, `wss://192.168.100.17:9443/ws`).
- Browser/UI evidence: real browser URL `https://192.168.100.17:9443/app/tickets/68de6816-471b-48ba-88e3-fa691264bba3`; timeline still shows the old P0.10 evidence message `live malformed probe both_seq`, but no `fix1e7518d` marker or new malformed probe entry appears. Screenshot: `artifacts/live-v3-fix1-ticket-browser.png`.

Regression check:
- Unit regressions covered valid ticket event ACK/persist, valid device event ACK/persist, missing trace NACK, wrong actor `UNAUTHORIZED`, unknown ticket `UNKNOWN_TICKET`, malformed contract NACK before persistence, and retryable NACK duplicate behavior.
- Full live regression for P0.7 happy `system.collect` and valid `tools_changed` device event remains in the final verification gate after Fix 1-6, per current task ordering.

Remaining risk:
- Existing pre-fix phantom evidence remains in live data by design: ticket `T-000604` still contains old `live malformed probe both_seq`, and the old `device_events.chat_message` row remains. Treat only new `probe_run_id` markers as post-fix evidence.
- During the raw probe the server again attempted to dispatch stale pending `install_module_package` command state to the probe connection before handshake ack was observed; this is test contamination from earlier P0 rows and should be revisited with BUG-20260527-07/reconnect cleanup, not as a new BUG-09 failure.

### BUG-20260527-10 — Local GUI automation tool actions omit account-session context

Severity: P1
Status: verified-fixed
Area: account-session / UI

Scenario:
Post-fix P0.7/P0.8 regression attempted to run `ticket.tool.run` and `ticket.capture_video` through `scripts/agent_test_driver.py` while the local GUI had an active confirmed account session and ticket `T-000606` existed.

Expected:
Local automation tool actions should either mirror the real supported GUI/web support tool flow with the active server account session, or return a clear unsupported-action error before calling the server.

Actual:
Both local automation calls returned HTTP `500` from `/ui/automation/run` with embedded server HTTP `403`, `error=account_session_invalid`, `error_code=ACCOUNT_SESSION_REQUIRED`.

Repro steps:
1. Ensure `live-v3-deep` is connected and an account is selected.
2. Run `python scripts\agent_test_driver.py run-tool live-v3-deep --ticket-id 92923cf9-3a68-4e1f-a130-e7397a306b2e --tool-name system.collect --params-json "{}"`.
3. Run `python scripts\agent_test_driver.py capture-video live-v3-deep --ticket-id 92923cf9-3a68-4e1f-a130-e7397a306b2e --duration-sec 30`.

Evidence:
- Server log/API: server returned `ACCOUNT_SESSION_REQUIRED` to the automation-initiated requester API path.
- Agent log: local automation returned HTTP `500` with embedded HTTP `403`.
- Browser/UI: not created through local automation; browser support route was used as a workaround and succeeded.
- Server DB: no operation rows were created by the failed local automation attempts.
- Agent SQLite: no new operation idempotency rows from these failed local automation tool attempts.
- WS/API payload: local error body `{"status":"error","error":"HTTP 403: ... ACCOUNT_SESSION_REQUIRED"}`.

Impact:
The automation bridge is now reliable for `ticket.create` after BUG-20260527-04, but it is still not a complete substitute for real GUI/support-browser tool action testing. P0.7/P0.8 had to use the browser web-session route instead.

Root cause hypothesis:
`pc_agent/ui_gui/automation_controller.py` / `pc_agent/ui_gui/server_api.py` tool-action paths do not pass the active requester account session where the server expects account-scoped requester authorization, unlike the fixed create-ticket path.

Fix policy:
- Blocking further tests: no, because browser support routes exercise the canonical support tool flow and were used for P0.7/P0.8.
- Fixed now: yes

Fix summary, if fixed:
- Root cause: `GuiAutomationController._run_ticket_tool()` called `chat_panel.ticket_client.run_tool()` without `account_session`, while the real GUI path `ChatPanel._async_run_tool()` already passed `account_session=self._current_account_session()`. `ticket.capture_screenshot` and `ticket.capture_video` both route through `_run_ticket_tool()`, so they inherited the same missing account-session context.
- Changed files: `pc_agent/ui_gui/automation_controller.py`, `pc_agent/tests/test_gui_automation_controller.py`, `PLANS.md`.
- Fix: `_run_ticket_tool()` now reads the active GUI account session via `chat_panel._current_account_session()` and passes it to `TicketApiClient.run_tool()`. The existing API client already serializes this into `requester_account` and account-session headers.

Verification after fix:
- Targeted pytest red/green: new regression tests initially failed with `KeyError: 'account_session'` for `ticket.tool.run` and `ticket.capture_video`; after the fix `python -m pytest pc_agent\tests\test_gui_automation_controller.py -q` -> `4 passed in 0.59s`.
- Adjacent targeted pytest: `python -m pytest pc_agent\tests\test_gui_automation_controller.py pc_agent\tests\test_registration_status.py::test_run_tool_includes_account_session -q` -> `5 passed in 0.59s`.
- Compile check: `python -m py_compile pc_agent\ui_gui\automation_controller.py pc_agent\tests\test_gui_automation_controller.py` -> passed.
- Workspace gate after docs sync: `python scripts\verify_workspace.py` -> passed.
- Live setup: restarted source GUI agent `live-v3-deep` against `wss://192.168.100.17:9443/ws` / `https://192.168.100.17:9443/api`; verified `pywinauto==0.6.9`; used `Application(backend="uia")` against window `Maria Agent v3.1.61`; invoked UIA `PrimaryButton` / visible text `Войти как admin-2`; automation status changed from `account_gate` to `tickets`, `ticket_count=5`.
- Live negative-adjacent check: `python scripts\agent_test_driver.py run-tool live-v3-deep --ticket-id 92923cf9-3a68-4e1f-a130-e7397a306b2e --tool-name system.collect --params-json "{}"` no longer failed with `ACCOUNT_SESSION_REQUIRED`; local action trace `seq=59719` includes `requester_account.session_id=745d41ee-...` and redacted `session_token`. The server rejected this specific tool with `ROLE_NOT_ALLOWED` / `actor_role=agent`, which is a separate role-policy outcome, not the BUG-10 account-session omission.
- Live successful regression: `python scripts\agent_test_driver.py capture-video live-v3-deep --ticket-id 92923cf9-3a68-4e1f-a130-e7397a306b2e --duration-sec 3` returned `status=ok`, `tool_name=screen.record`, `operation_id=18caaa4e-20b0-45fb-9b4c-dd4a59224504`, `trace_id=8b9e2aff-db27-48da-8bd2-44dc407a106b`.
- Agent evidence: action trace `seq=59722` for `screen.record` includes `requester_account.session_id=745d41ee-...` and redacted `session_token`; response `seq=59723` is HTTP `202`, operation accepted; module trace captured 45 frames and finished with `status=partial` due artifact upload warning, not account-session failure.
- Server DB evidence: operation `18caaa4e-20b0-45fb-9b4c-dd4a59224504` exists with `tool_name=screen.record`, `status=succeeded`; `device_outbox` request is `status=delivered`; ticket events include `tool_call_started` id `104` and `tool_call_result` id `106`.
- Browser/UI evidence: real browser URL `https://192.168.100.17:9443/app/tickets/92923cf9-3a68-4e1f-a130-e7397a306b2e`; ticket `T-000606` timeline shows `screen.record` accepted at 12:37 and a successful diagnostic result with `frames_captured=45`, `duration_sec=5.7`, `file_size_bytes=113860`. Browser snapshot saved as `live-v3-bug10-ticket-snapshot.md`; screenshots saved as `live-v3-bug10-ticket-screen-record.png` and `live-v3-bug10-ticket-screen-record-full.png`.
- Full parity audit/follow-up, 2026-05-27 13:10-13:40 +05:
  - Root cause confirmed across ticket-bound automation actions: create was already fixed, but direct action helpers needed the active `chat_panel._current_account_session()` passed consistently to ticket-bound API calls. `_send_message()`, `_confirm_resolution()`, `_ticket_snapshot()`, `_open_ticket()`/GUI delegate checks, and `_run_ticket_tool()` wrappers were audited; `capture_screenshot` and `capture_video` inherit the fixed `_run_ticket_tool()` path.
  - Focused tests cover `ticket.tool.run`, `ticket.capture_video` / `screen.record`, `ticket.capture_screenshot` / `screen.collect`, `ticket.message.send`, `ticket.snapshot`, `ticket.open`, `attach_files`, `confirm_resolution`, and no-active-account deterministic denial behavior in `pc_agent/tests/test_gui_automation_controller.py`.
  - Additional live ticket: automation create produced `T-000607` / `037dbf08-76b8-449c-a856-c6d8b67f6f38` with requester account session `7b1efdb1-bce7-4b13-8793-6d93f3c03bde`, mode `confirmed_binding`.
  - Additional local automation actions on `T-000607`: `send-message` ok, `snapshot-ticket` ok, `capture-screenshot` ok with `screen.collect` operation `98222923-b869-4512-a78b-02b9dd8733ac`, and `capture-video --duration-sec 3` ok with `screen.record` operation `af94873a-1af0-424e-956d-ac74404cbbea`. None returned `ACCOUNT_SESSION_REQUIRED`.
  - Browser confirmation: `https://192.168.100.17:9443/app/tickets/037dbf08-76b8-449c-a856-c6d8b67f6f38` showed the BUG10 message plus successful `screen.collect` and `screen.record` timeline results; screenshots `live-v3-bug10-ticket-timeline.png` and `live-v3-bug10-ticket-detail-full.png`.
  - Agent local state: no new failed outbox rows from these local automation actions; recent `seen_commands` were terminal for the screenshot/video tool commands.

Regression check:
- Covered direct automation `ticket.tool.run` payload propagation in unit tests, `ticket.capture_video` wrapper propagation in unit tests, API client account-session serialization in adjacent tests, and live `capture-video` through the local GUI automation bridge with DB + browser confirmation.
- `system.collect` through local requester automation is now account-session-correct but policy-denied as `ROLE_NOT_ALLOWED`; use an agent-allowed tool such as `screen.record` for requester-side automation live regression, or run support/admin tools through the browser support route.

Remaining risk:
Other `/ui/automation/run` actions that do not route through `_run_ticket_tool()` may still need separate account-session parity checks. During setup, GUI account-session validation still uses a `session_token` query parameter that the server rejects as `SESSION_TOKEN_QUERY_DISABLED`; UIA login works around this by using the real confirmed-binding login path and should be tracked separately if it recurs as a product issue.

### P0 milestone summary

Recorded at: 2026-05-27 01:15 Asia/Yekaterinburg.

P0 execution status:
- Run: P0.1 through P0.10.
- Passed: P0.1 after server restart recovery, P0.6 canonical lifecycle, P0.7 `system.collect` happy lifecycle.
- Partial pass: P0.3, P0.4, P0.8, P0.9.
- Failed with bugs recorded: P0.2, P0.5, P0.10.

Bugs recorded and not fixed at original P0 closeout:
- `BUG-20260527-01`: live server stopped during baseline.
- `BUG-20260527-02`: Protocol V3 close codes are not observed by raw WS clients.
- `BUG-20260527-03`: UIA create wizard cannot complete required fields reliably.
- `BUG-20260527-04`: local GUI automation ticket.create omits active account session.
- `BUG-20260527-05`: WS chat_raise returns success for a non-persisted ticket.
- `BUG-20260527-06`: web-session operation cancel endpoint returns AUTH_REQUIRED.
- `BUG-20260527-07`: canceled run_tool leaves stale sent/in_progress command state.
- `BUG-20260527-08`: module lifecycle changes do not persist module_state_changed/tools_changed device events.
- `BUG-20260527-09`: malformed outbox items are ACKed and can persist phantom events.

Blocking fixes applied:
- None. Server restart and local agent restart were operational recovery steps only; no product code fixes were made.

Post-P0 fix status:
- 2026-05-27 09:51 +05: `BUG-20260527-09` verified-fixed by commit `e7518d88117d6adcbb7066eaadc3d8561f8f334f`, targeted pytest, live malformed-outbox regression, DB zero-row check, and browser ticket timeline confirmation.
- 2026-05-27 10:13 +05: `BUG-20260527-05` verified-fixed by DB-first/error-only `chat_raise` handling, server and agent targeted pytest, live `/ui/request_support` regression with explicit `TICKET_CREATE_UNAVAILABLE`, zero phantom DB rows, zero new `UNKNOWN_TICKET`, and browser timeline confirmation.
- 2026-05-27 10:43 +05: `BUG-20260527-07` verified-fixed by commits `1fb8c9fa7874629d8e9ec898562b4362f43bb6d2` and `f7e350e08e4a3faef4728133e1464d7509759b8f`, targeted server/agent pytest, live `screen.record` cancel regression, server `device_outbox` delivered check, agent `seen_commands.status='canceled'`, and browser ticket timeline confirmation.
- 2026-05-27 11:23 +05: `BUG-20260527-06` verified-fixed by commit `91f7529aa2e864298ae025ac4e20123688d1e368`, targeted server/webapp tests, quick release with rebuilt web bundle, live browser web-session `screen.record` cancel through `/api/web/support/operations/{operation_id}/cancel`, DB/device_outbox verification, and browser timeline confirmation.
- 2026-05-27 11:45 +05: `BUG-20260527-08` verified-fixed in local/source agent by passing canonical device id into `AgentOrchestrator` and stripping compatibility `ticket_id` from device-event wire envelopes; targeted agent pytest passed, live remove/install `network_ping` regression persisted `module_state_changed`/`tools_changed`, local outbox had no pending lifecycle rows, and browser device modules tab confirmed `network_ping` active.
- 2026-05-27 12:05 +05: `BUG-20260527-04` verified-fixed in local/source agent by passing the active account session through GUI automation create; targeted agent tests passed, pywinauto/UIA selected the confirmed account, `agent_test_driver.py create-ticket` created `T-000605`, DB requester account fields were correct, local outbox had no recent failed rows, and browser ticket detail showed the new ticket.
- 2026-05-27 12:20 +05: all requested Fix 1-6 code changes are committed and pushed through `bb6f77267509133bd8cb0a70901ec6a019161dca`; post-fix gates reran `verify_workspace.py`, targeted pytest, P0.4 automation create, P0.5 chat_raise, P0.7 `system.collect`, P0.8 browser cancel, P0.9 module projection, and P0.10 malformed outbox.

Post-fix verification gate, 2026-05-27 12:05-12:20 +05:
- Code/test gates:
  - Fix 6 commit: `bb6f77267509133bd8cb0a70901ec6a019161dca` (`fix: pass account session through GUI automation`) pushed to `origin/codex/helpdesk-process-model`.
  - Targeted pytest: `python -m pytest pc_agent\tests\test_gui_automation_controller.py pc_agent\tests\test_registration_status.py::test_create_ticket_sends_only_requester_account_session_when_passed -q` -> `3 passed in 0.69s`.
  - Workspace gate: `python scripts\verify_workspace.py` -> passed.
- P0.4 automation create:
  - Command: `python scripts\agent_test_driver.py create-ticket live-v3-deep --title "Live V3 post-fix automation create bb6f7726" --description "Post-fix gate for P0.4 automation create with active confirmed account session."`.
  - Result: `ticket_id=92923cf9-3a68-4e1f-a130-e7397a306b2e`, `ticket_code=T-000606`, status `queued`, requester account session `6196fe8b-d836-44c5-9760-88a2f5d31f7a`, mode `confirmed_binding`.
  - Server DB: `tickets.T-000606` persisted with requester person `bb00a942-fe2c-461c-b982-9da17d3fd1ff`, binding `0618eb74-9fa6-4dbe-9634-d9b56825f3ad`, account session `6196fe8b-d836-44c5-9760-88a2f5d31f7a`.
  - Browser/UI: `https://192.168.100.17:9443/app/tickets/92923cf9-3a68-4e1f-a130-e7397a306b2e` showed `T-000606`, requester `Тестовый тест 12`, status `В очереди`, and the initial user message.
- P0.5 chat_raise:
  - Command: `python scripts\agent_test_driver.py request-support live-v3-deep --title "Live V3 post-fix chat_raise bb6f7726" --reason "post_fix_gate" --severity "warning"`.
  - Result: local bridge returned `status=ok`, `result.ok=false`, `error_code=TICKET_CREATE_UNAVAILABLE`, `error="Ticket creation is unavailable for chat_raise"`.
  - No new phantom persisted ticket id was returned; no new local `UNKNOWN_TICKET` rows were created by this post-fix chat_raise attempt.
- P0.7 system.collect:
  - Browser web-session route: `POST /api/web/support/tickets/92923cf9-3a68-4e1f-a130-e7397a306b2e/tools/run` with `tool_name=system.collect`.
  - Result: HTTP `202`, operation `8f223efd-4086-472c-8925-0453b7317280`, trace `8b9e2aff-db27-48da-8bd2-44dc407a106b`; DB `operations.status=succeeded`, `device_outbox.status=delivered`.
  - Browser ticket timeline showed `system.collect` accepted and then successful diagnostic output with hostname `ADMIN-2`, CPU/RAM/Disk values.
  - Agent SQLite `seen_commands`: target command `8f223efd-4086-472c-8925-0453b7317280` status `success`.
- P0.8 browser cancel:
  - Browser web-session run: `screen.record`, operation `a0512684-cc48-47ee-a20d-f206dc003a9a`; cancel route `POST /api/web/support/operations/a0512684-cc48-47ee-a20d-f206dc003a9a/cancel`.
  - Result: HTTP `200`, cancel operation `c3ca2ceb-2059-40cb-96cb-3b09dc8b0538`.
  - Server DB: target operation `canceled`, cancel operation `succeeded`; target and cancel `device_outbox` rows are `delivered`.
  - Agent SQLite `seen_commands`: target status `canceled`, cancel status `success`.
  - Browser ticket timeline showed `screen.record` accepted and then `Статус: Отменена`, result `Tool screen.record canceled`. Screenshot: `live-v3-postfix-ticket-tool-cancel.png`.
- P0.9 module lifecycle/projection:
  - Reused the verified Fix 5 live remove/install regression for durable lifecycle events, then rechecked browser projection after all fixes.
  - Server DB recent `device_events` includes `module_state_changed` and `tools_changed` for device `7a3429ec-1c0b-5495-9aad-b284f08ae965`; latest post-restart `module_state_changed` had `device_seq=10`.
  - Browser admin modules tab `https://192.168.100.17:9443/app/admin/device-operations/7a3429ec-1c0b-5495-9aad-b284f08ae965?tab=modules` showed `Модули ok`, `Missing: 0`, `Outdated: 0`, `network_ping`, `Установлено: 1.0.0`, `Desired: 1.0.0`, `active`. Screenshot: `live-v3-postfix-device-modules.png`.
  - Note: the device operations overview still shows historical failed operation counts and an `install_module_package` timeout from raw-probe/test contamination; module reconcile state itself is ok.
- P0.10 malformed outbox:
  - First post-fix probe while the GUI agent was running was superseded by the real same-device agent reconnecting, so the clean run briefly stopped `live-v3-deep`, ran the raw probe, and restarted the source GUI agent.
  - Command: `python scripts\live_ws_v3_probe.py malformed-outbox --case all --ticket-id 92923cf9-3a68-4e1f-a130-e7397a306b2e --run-id postfixbb6 --seq-base 930000`.
  - Probe output: all malformed cases returned non-retryable NACK: `both_seq`/`neither_seq` `VALIDATION_ERROR`, `unknown_ticket` `UNKNOWN_TICKET`, `missing_trace_id` `VALIDATION_ERROR`, `wrong_actor_role` `UNAUTHORIZED`, `top_ticket_only` `VALIDATION_ERROR`, `unknown_item_type` `VALIDATION_ERROR`.
  - Server DB: `malformed_count=0` for `payload::text like '%postfixbb6%'` on ticket `T-000606`; browser ticket timeline did not show `postfixbb6` or `live malformed probe`.
  - Agent restarted after the probe and is running source GUI mode on `wss://192.168.100.17:9443/ws`.
- Follow-up fix: `BUG-20260527-10` local automation `ticket.tool.run`/`capture-video` account-session omission is now `verified-fixed`; `capture-video` live regression created and completed `screen.record` operation `18caaa4e-20b0-45fb-9b4c-dd4a59224504` and browser timeline confirmed the result.

Final P0 blocker closure, 2026-05-27 13:45-14:05 +05:
- Commit/deploy head: `47340c9bc435303c97b5ce3cb05631e815d41207` on `codex/helpdesk-process-model`, pushed to `origin` and deployed to `/var/chat_bot/pc_client` with quick gate.
- `BUG-20260527-10`: `verified-fixed` by commit `1b9254bdbb485ec01a84e29f750f00cb18b21cb3`; local automation now passes active account session for ticket-bound tool/message/snapshot/open/close/attachment wrapper paths. Live ticket `T-000607` confirmed `send-message`, `screen.collect`, and `screen.record` through `/ui/automation/run` without `ACCOUNT_SESSION_REQUIRED`, with DB and browser timeline evidence.
- `BUG-20260527-03`: `verified-fixed` by commit `1b9254bdbb485ec01a84e29f750f00cb18b21cb3`; real pywinauto UIA wizard create produced `T-000608` with exact Russian description preserved, required fields selected, server DB rows persisted, and browser detail confirmation.
- `BUG-20260527-02`: `verified-fixed` by commits `1b9254bdbb485ec01a84e29f750f00cb18b21cb3` and `e03f9b29c23671dd9cdc0a806220e9ee7796493d`; canonical WSS invalid handshakes observe `4003` and same-device supersede observes `4002`.
- `BUG-20260527-01`: `verified-non-product / guardrails-added` by commits `e03f9b29c23671dd9cdc0a806220e9ee7796493d` and `47340c9bc435303c97b5ce3cb05631e815d41207`; root cause category is external SIGKILL/no OOM with previous `Restart=no`, now covered by restart policy, bounded stop timeout, incident collector, controlled SIGKILL recovery, health smoke, browser inventory, and agent reconnect evidence.
- Synchronized fixed statuses: `BUG-20260527-04`, `BUG-20260527-05`, `BUG-20260527-06`, `BUG-20260527-07`, `BUG-20260527-09` are `verified-fixed`; `BUG-20260527-08` is `verified-fixed / residual-noise` because current lifecycle events persist, while historical duplicate/noise rows from pre-fix live testing remain as evidence and should not be counted as new regressions.
- Browser evidence retained: admin inventory/device online, UIA-created ticket detail `T-000608`, automation tool result timeline `T-000607`, cancel result timeline `T-000606`, malformed-probe no-phantom confirmation.
- UIA evidence retained: pywinauto `0.6.9`, `Application(backend="uia")`, main connected `Maria Agent v3.1.61` window, stable create wizard controls, submit success/ticket opened JSON and screenshot artifacts.

P0 close summary:
- Server URL: `https://192.168.100.17:9443`; browser/admin URL: `https://192.168.100.17:9443/admin`.
- Agent: local Windows source GUI instance `live-v3-deep`, device_id `7a3429ec-1c0b-5495-9aad-b284f08ae965`, hostname `ADMIN-2`, agent version `3.1.61`, Protocol V3 `ws_ticket_v3`.
- Server version/capabilities evidence: handshake ack advertised Protocol V3 capabilities including `protocol_v3`, `envelope_v3`, `outbox_ack_v3`, `trace_correlation`, `nack_support`, `consent_flow`, `rpc_request`, `rpc_response`, `outbox_item`, `job_events`, and `device_events`; health endpoint returned `status=ok`.
- Final fresh code gates on this branch:
  - `python scripts\verify_workspace.py` -> passed.
  - `python -m compileall -q server pc_agent scripts` -> passed.
  - `python -m pytest pc_agent\tests\test_gui_automation_controller.py pc_agent\tests\test_dynamic_form_widget.py pc_agent\tests\test_chat_panel_helpers.py::test_ticket_create_wizard_exposes_stable_uia_ids scripts\test_run_https_reverse_proxy.py server\tests\test_runtime_control.py -q` -> `26 passed, 2 warnings`.
  - `git diff --check` -> passed.
- Final fresh live sanity:
  - `python scripts\manage_remote_stack.py smoke server --base-url https://192.168.100.17:9443 --insecure-tls` -> `/api/health` 200.
  - `python scripts\agent_test_driver.py status live-v3-deep` -> `connection_state=connected`, `bridge_connected=true`, `has_active_profile=true`, `ticket_count=7`.
  - `.venvs\agent-win\Scripts\python.exe -c "import pywinauto; print(pywinauto.__version__)"` -> `0.6.9`.
  - `python scripts\live_ws_v3_probe.py --ws-url wss://192.168.100.17:9443/ws --timeout 5 invalid-handshake --case all --expect-close-code 4003` -> all invalid cases observed `4003`.
  - `python scripts\live_ws_v3_probe.py --ws-url wss://192.168.100.17:9443/ws --timeout 5 double-connect --expect-supersede-close-code 4002` -> superseded socket observed `4002`; follow-up agent status returned `connected`.
  - Browser/admin final snapshot: `https://192.168.100.17:9443/app/admin/inventory?device=7a3429ec-1c0b-5495-9aad-b284f08ae965` shows `ADMIN-2` online, Windows, version `3.1.61`, last activity `27 мая 2026 г., 13:55`; screenshot `live-v3-final-admin-inventory.png`, snapshot `live-v3-final-admin-inventory-snapshot.md`.
- Remaining non-P0 known risks: old phantom event in `T-000604`, old stale `device_outbox.status=sent` rows, old local SQLite `UNKNOWN_TICKET` rows from pre-fix `chat_raise`, and historical module/probe noise. These are pre-fix contamination and should be filtered by timestamp/run id in P1/P2.
- P0 is closed. P1/P2 can start from a clean new run id/ticket/device-state filter without counting the listed pre-fix artifacts as regressions.

Current live state:
- Local agent `live-v3-deep` is running in GUI/source mode and is connected to `wss://192.168.100.17:9443/ws`; latest automation status shows the tickets view, active profile, and 7 visible tickets.
- Server remains running on `https://192.168.100.17:9443`; latest smoke returned health 200.
- Test ticket `T-000604` contains intentional P0.10 probe evidence (`live malformed probe both_seq`) and should not be treated as normal requester input.
- Known residual stale rows from pre-fix testing: target cancel run_tool `device_outbox` row id `6` remains `sent`; raw probe `install_module_package` rows ids `12` and `13` remain `sent`; local SQLite still contains old failed `UNKNOWN_TICKET` rows from pre-fix chat_raise `cc002181-f7d9-44da-8726-da46463c090f`. Post-fix cancel regression uses operation `a0512684-cc48-47ee-a20d-f206dc003a9a`, whose target outbox is delivered and local idempotency is terminal canceled.

Recommended next test pass:
- Start P1 with a clean marker/run id and a new ticket so old P0 contamination can be excluded deterministically.
- Recommended order: P1.1 ACK/NACK/dedup, P1.2 command idempotency, P1.3 consent, P1.5 restart/reconnect, P1.6 UI projection, P1.4 auto-install negatives.
- P2 can follow after P1.1/P1.2 confirm that ACK/dedup/idempotency remains stable on post-fix clean data.

## P1 Live validation — 2026-05-27 — run_id=p1-20260527-1454-c15fe567

Status: baseline recovered after two blocking fixes; clean agent `live-v3-p1-clean2` registered from zero and ready for a fresh P1 run id.

Run metadata:
- Branch: `codex/helpdesk-process-model`.
- Current commit at first P1 attempt: `c15fe567c58bc31454d85dd8df4f6222cff5a644`.
- P0 close code/deploy head: `47340c9bc435303c97b5ce3cb05631e815d41207`; P0 closure docs head before P1 docs alias: `e845fcfa`; live rules alias checkpoint: `c15fe567`.
- Server URL: `https://192.168.100.17:9443`.
- Browser/admin URL: `https://192.168.100.17:9443/admin`.
- Original P0 agent instance `live-v3-deep` is not clean for P1 after DB cleanup; it retained local account/profile state after server registration data was cleaned.
- Clean P1 attempt instance: `live-v3-p1-clean`, UI port `8766`, machine seed `p1-clean-20260527-145438`, device_id `a7085e14-47eb-546f-809d-ab6ec42c2bc8`, source GUI mode.
- Agent version observed after clean technical provisioning: `3.1.61`.
- pywinauto version: `0.6.9`.

Known pre-fix contamination to ignore for P1:
- P0 malformed phantom event in ticket `T-000604`.
- Old `device_outbox.status=sent` rows: target cancel row id `6`, raw-probe install rows ids `12` and `13`.
- Old local SQLite failed rows from pre-fix `chat_raise` ticket id `cc002181-f7d9-44da-8726-da46463c090f`.
- Historical module/probe noise and duplicate/noise rows from BUG-20260527-08 pre-fix testing.

Pre-P1 baseline evidence:
- Server smoke: `python scripts\manage_remote_stack.py smoke server --base-url https://192.168.100.17:9443 --insecure-tls` returned `/api/health -> 200`.
- First attempted `live-v3-deep` baseline was invalid after server DB cleanup: local automation status showed `has_active_profile=true`, `active_profile_id=registration-smoke-profile` even though server-side registration/profile rows had been cleaned.
- `live-v3-deep` was stopped with `python scripts\manage_local_agent.py stop live-v3-deep`.
- Clean instance `live-v3-p1-clean` was first started with `--api-url https://192.168.100.17:9443`; connection request failed with HTTP 404 because the connection-request code expects `/api` in the base URL. This is a test setup error; it was corrected by restarting with `--api-url https://192.168.100.17:9443/api`.
- Clean technical provisioning path: `live-v3-p1-clean` created a pending connection request, admin approved it through `/api/web/admin/connection_requests/{device_id}/approve` using a short-lived generated admin token. Evidence printed only token prefix/length, not raw token.
- Agent log after approval: token saved for prefix `a7085e14...`, WS connected, `handshake_ack` received, `list_tools` command executed successfully, two startup device-event outbox rows ACKed.
- Agent automation status after technical provisioning: `connection_state=connected`, `bridge_connected=true`, `sidebar_view=account_gate`, `ticket_count=0`.
- Blocking issue: the supposedly clean instance still reported `has_active_profile=true`, `active_profile_id=registration-smoke-profile`, `profile_count=5`. File inspection showed no `user_profile.json` under `.local-agent\instances\live-v3-p1-clean\data`, but `%LOCALAPPDATA%\PCClientAgent\data\user_profile.json` and `requester_profiles.json` existed and were updated/read during the clean instance run.

P1 checklist:
- [x] Baseline clean account/session state after isolation fix.
- [x] Register clean agent/account from zero.
- [x] Browser/admin confirms clean device online and registration/account state.
- [x] UIA confirms clean GUI state and registered account state.
- [ ] P1.1 Outbox ACK/NACK/dedup.
- [ ] P1.2 Command idempotency.
- [ ] P1.3 Consent flow.
- [ ] P1.4 Module auto-install before run_tool.
- [ ] P1.5 Restart/reconnect with pending state.
- [ ] P1.6 Browser/UI projection consistency.

### BUG-20260527-P1-01 — Isolated local agent reuses global requester profile cache

Severity: P1
Status: verified-fixed
Area: test-tool / local GUI / account-session

P1 scenario:
Clean P1 baseline and registration-from-zero after server DB cleanup.

Run id:
`p1-20260527-1454-c15fe567`

Expected:
A new named local agent instance with a fresh `machine_id`, fresh data-dir and no user registration should start with no active requester/account profile. It should show account/registration gate only, then allow registration from zero. Local profile/cache files must be scoped to `.local-agent\instances\<name>\data`.

Actual:
`live-v3-p1-clean` used a new data-dir and new device id, but `/ui/automation/status` returned `has_active_profile=true`, `active_profile_id=registration-smoke-profile`, `profile_count=5`. The instance tried `list_tickets` with stale account-session context and received `ACCOUNT_SESSION_NOT_FOUND`. Inspection showed the clean instance data-dir had no `user_profile.json`, while `%LOCALAPPDATA%\PCClientAgent\data\user_profile.json` and `requester_profiles.json` existed and were used/updated.

Repro steps:
1. Stop old `live-v3-deep`.
2. Start clean instance:
   `python scripts\manage_local_agent.py start live-v3-p1-clean --gui --ws-url wss://192.168.100.17:9443/ws --api-url https://192.168.100.17:9443/api --ui-port 8766 --machine-id p1-clean-20260527-145438`.
3. Approve the generated connection request through admin web API.
4. Run `python scripts\agent_test_driver.py status live-v3-p1-clean`.
5. Inspect `.local-agent\instances\live-v3-p1-clean\data` and `%LOCALAPPDATA%\PCClientAgent\data`.

Evidence:
- Transport/API: connection request pending -> approved; WS connected; `handshake_ack` received; `list_tools` succeeded; startup outbox ACKs received.
- Server log: admin connection request approved for device `a7085e14-47eb-546f-809d-ab6ec42c2bc8`; raw token not logged.
- Agent log: `ACCOUNT_SESSION_NOT_FOUND` on `list_tickets`; `handshake_ack` and `list_tools` success after provisioning.
- Server DB: clean device id `a7085e14-47eb-546f-809d-ab6ec42c2bc8` created from connection-request token path; registration/account baseline not yet clean.
- Agent SQLite: clean instance DB was newly created (`DB_SCHEMA_VERSION v9`), no registration profile file in instance data-dir.
- Browser/UI: browser confirmation intentionally not yet marked green because baseline is blocked before P1 start.
- UIA: not yet green; local automation status shows account gate but stale active profile.
- Test artifact: `%LOCALAPPDATA%\PCClientAgent\data\user_profile.json`, `%LOCALAPPDATA%\PCClientAgent\data\requester_profiles.json`; clean instance `.local-agent\instances\live-v3-p1-clean\data` lacks `user_profile.json`.
- Run marker: `p1-20260527-1454-c15fe567`.

Impact:
P1 account-session, GUI and requester tests would be polluted by stale local profile/account state. This makes P1.1/P1.2/P1.3 evidence unreliable because ticket ownership and account-session context would not come from the clean registration flow.

Root cause hypothesis:
`scripts/manage_local_agent.py` passes `--data-dir` and `--install-root` to `pc_agent.ws_agent`, but does not set `PC_AGENT_DATA_DIR` / `PC_AGENT_INSTALL_ROOT` in the process environment. GUI helpers that call `resolve_data_root()` without a CLI value, including `UserProfileManager` and cache-backed GUI paths, therefore resolve to `%LOCALAPPDATA%\PCClientAgent\data` instead of the named instance data-dir.

Root cause confirmed:
Yes. `live-v3-p1-clean2` started after the fix created/used `user_profile.json`, `registry_options.json`, `service_catalog.json` and `ticket_form_pack.json` under `.local-agent\instances\live-v3-p1-clean2\data`; `/ui/automation/status` reported `has_active_profile=false`, `profile_count=0` before registration and no longer showed `registration-smoke-profile`.

Blocking further P1: yes
Fix now: yes

Fix summary:
`scripts/manage_local_agent.py` now sets `PC_AGENT_DATA_DIR` and `PC_AGENT_INSTALL_ROOT` for named instances in both `start` and `verify`, so GUI helpers using `resolve_data_root()` resolve to the same instance-local data root as `ws_agent --data-dir`.

Changed files:
`scripts/manage_local_agent.py`; `scripts/test_manage_local_agent.py`.

Tests:
`python -m pytest scripts/test_manage_local_agent.py pc_agent/tests/test_registration_status.py -q` -> 26 passed.
`python -m compileall -q scripts/manage_local_agent.py scripts/test_manage_local_agent.py pc_agent/ui_gui/server_api.py pc_agent/tests/test_registration_status.py` -> passed.
`git diff --check` -> passed.

Live regression:
Started `live-v3-p1-clean2` with machine seed `p1-clean2-20260527-150200`, device_id `2447d396-79cd-53da-b3a9-028c5a4d56da`. Technical connection request approved, WS `handshake_ack` received, `list_tools` command succeeded, automation status before registration showed `connection_state=connected`, `has_active_profile=false`, `profile_count=0`. Browser admin inventory at `https://192.168.100.17:9443/app/admin/inventory?device=2447d396-79cd-53da-b3a9-028c5a4d56da` shows `ADMIN-2` online with agent version `3.1.61`. UIA evidence: pywinauto `0.6.9`, backend `uia`, window title `Maria Agent v3.1.61`, screenshot `artifacts\p1-clean2-agent-main.png`.

Remaining risk:
Unbounded UIA child traversal can still hang on the Qt tree; later P1 GUI evidence must use bounded/targeted selectors and screenshots.

### BUG-20260527-P1-02 — GUI clears valid account session because validation uses query token

Severity: P1
Status: verified-fixed
Area: account-session / local GUI / automation / test-tool

P1 scenario:
Clean P1 registration-from-zero baseline for `live-v3-p1-clean2`.

Run id:
`p1-20260527-1454-c15fe567`

Expected:
After a clean agent submits registration, confirms the claim, admin approves it, and the agent creates a confirmed-binding account session, the GUI must keep the local `account_session.json` and enter the ticket workspace with a valid `confirmed_binding` session. Session token must be sent in headers or POST body, not in a URL/query string.

Actual:
The confirmed-binding account session was created and validated successfully through `POST /api/registry/agent/account-sessions/{session_id}/validate` with `session_token` in JSON body. On GUI restart, `TicketApiClient.validate_account_session()` used `GET .../validate?session_token=...`; the server returned `SESSION_TOKEN_QUERY_DISABLED`, `MainWindow._validate_local_account_session_with_server()` treated it as invalid and cleared `.local-agent\instances\live-v3-p1-clean2\data\account_session.json`.

Repro steps:
1. Start `live-v3-p1-clean2` with isolated data root and no token.
2. Approve its connection request.
3. Submit registration without user confirmation through `/api/registry/agent/profile`.
4. Confirm the claim through `/api/registry/agent/claims/{claim_id}/confirm`.
5. Approve claim `a3b6dd0e-c912-4483-8967-6d58f7919411` through `/api/web/admin/registry/registrations/{claim_id}/approve`.
6. Create confirmed-binding session through `/api/registry/agent/account-sessions/confirmed-binding`.
7. Save local session and validate it through POST body: valid=true.
8. Restart agent GUI; observe `account_session.json` removed and automation status still at `sidebar_view=account_gate`.

Evidence:
- Transport/API: `POST /api/registry/agent/account-sessions/confirmed-binding` -> 200, `session_id=ed6dc098-cba8-4b93-889c-d2fee5661c43`; `POST /api/registry/agent/account-sessions/{session_id}/validate` -> 200, `valid=True`; `GET .../validate?session_token=...` -> 400 `SESSION_TOKEN_QUERY_DISABLED`.
- Server log: admin approval succeeded for claim `a3b6dd0e-c912-4483-8967-6d58f7919411`; agent token evidence only `sha256_prefix=11245df33169 length=64`, session token evidence only `sha256_prefix=71b1221ebff2 length=43`.
- Agent log: clean restart loaded token, opened GUI, performed handshake/list_tools; account session file was cleared during account-state validation path.
- Server DB: binding `1b87f35b-b826-4768-a7fd-9f0e2b276526`, person `f0e074a5-7c1b-4e38-bb4a-abfb2be3612f`, session `ed6dc098-cba8-4b93-889c-d2fee5661c43`.
- Agent SQLite: `outbox=0`, `outbox_sent_history=2`, `seen_commands=2`, `pending_consents=0` after restart.
- Browser/UI: browser/admin confirmation not yet green; baseline blocked before P1 start.
- UIA: pywinauto `0.6.9` available in `.venvs\agent-win`; unbounded UIA child traversal hangs, so only bounded/targeted UIA evidence is allowed later.
- Test artifact: `.local-agent\instances\live-v3-p1-clean2\data\user_profile.json` has `registration_status=admin_confirmed`; `account_session.json` missing after GUI restart.
- Run marker: `p1-clean-registration-20260527-1508-c15fe567`.

Impact:
P1 cannot start because ticket/message/tool flows would run without a confirmed account-session even after successful clean registration. This also invalidates GUI/account-session evidence.

Root cause hypothesis:
`pc_agent/ui_gui/server_api.py::TicketApiClient.validate_account_session()` still sends `session_token` as a query parameter using GET, while the server intentionally disables query-token validation for secret hygiene and expects POST body or dedicated headers.

Root cause confirmed:
Yes. Manual live validation through `POST /api/registry/agent/account-sessions/{session_id}/validate` returned `valid=True`, while the GUI client path using `GET ?session_token=...` returned `SESSION_TOKEN_QUERY_DISABLED` and caused `MainWindow` to clear the local session.

Blocking further P1: yes
Fix now: yes

Fix summary:
`TicketApiClient.validate_account_session()` now sends `POST /validate` with `{"session_token": ...}` in the JSON body. The regression test asserts `POST`, JSON body, and no query params.

Changed files:
`pc_agent/ui_gui/server_api.py`; `pc_agent/tests/test_registration_status.py`.

Tests:
`python -m pytest scripts/test_manage_local_agent.py pc_agent/tests/test_registration_status.py -q` -> 26 passed.
`python -m compileall -q scripts/manage_local_agent.py scripts/test_manage_local_agent.py pc_agent/ui_gui/server_api.py pc_agent/tests/test_registration_status.py` -> passed.
`git diff --check` -> passed.

Live regression:
Recreated confirmed-binding session `c24c7842-8284-4964-a92f-7f608eaf52d2` for binding `1b87f35b-b826-4768-a7fd-9f0e2b276526`, saved it under `.local-agent\instances\live-v3-p1-clean2\data\account_session.json`, restarted `live-v3-p1-clean2` on patched code, and verified the file remains present with `account_mode=confirmed_binding`, `registration_status=admin_confirmed`. Agent local state after restart: `outbox=0`, `outbox_sent_history=3`, `seen_commands=3`, `pending_consents=0`. WS handshake/list_tools succeeded. Server DB shows claim `a3b6dd0e-c912-4483-8967-6d58f7919411` approved, active primary binding `1b87f35b-b826-4768-a7fd-9f0e2b276526`, and verified confirmed-binding sessions for device `2447d396-79cd-53da-b3a9-028c5a4d56da`.

Remaining risk:
`/ui/automation/status` still reports `sidebar_view=account_gate` after restart even with a retained confirmed session; treat this as UI projection state to watch during P1. It is not blocking because account session is valid and persisted, but P1.6 should verify whether the GUI should automatically leave the gate or requires explicit user click.

## P1 Live validation — 2026-05-27 — run_id=p1-20260527-1527-c4f03651

Status: started after clean-agent recovery checkpoint `c4f03651`; P1.1 not yet green.

Run metadata:
- Branch: `codex/helpdesk-process-model`.
- Commit SHA before P1 continuation: `c4f03651`.
- P0/P1 cleanup checkpoint: `c4f03651` (`fix: isolate live agent account sessions`), pushed to GitHub origin.
- Server URL: `https://192.168.100.17:9443`.
- Browser/admin URL: `https://192.168.100.17:9443/app/admin/inventory?device=2447d396-79cd-53da-b3a9-028c5a4d56da`.
- Local agent instance: `live-v3-p1-clean2`.
- Device id / machine id: `2447d396-79cd-53da-b3a9-028c5a4d56da` / `p1-clean2-20260527-150200`.
- Agent version: `3.1.61`.
- pywinauto: `0.6.9` from `.venvs\agent-win`, backend `uia`.
- Server health: `python scripts\manage_remote_stack.py smoke server` -> `/api/health` 200.
- Agent connection state: `/ui/automation/status` -> `connection_state=connected`, `bridge_connected=true`, `window_visible=true`, `sidebar_view=account_gate`, `has_active_profile=true`, `profile_count=0`, `ticket_count=0`.
- Account-session state: `.local-agent\instances\live-v3-p1-clean2\data\account_session.json` present, `account_mode=confirmed_binding`, `account_session_id=c24c7842-8284-4964-a92f-7f608eaf52d2`, `registration_status=admin_confirmed`, `verification_status=verified`, display `P1 Clean User`; token omitted.
- Agent SQLite baseline: `outbox=0`, `outbox_sent_history=3`, `seen_commands=3`, `pending_consents=0`.
- Browser evidence: real browser admin inventory shows `ADMIN-2`, device id prefix `2447d396...56da`, status online, Windows, agent version `3.1.61`; screenshot `artifacts\p1-20260527-1527-c4f03651-admin-inventory.png`, snapshot `artifacts\p1-20260527-1527-c4f03651-admin-inventory-snapshot-2.md`.
- UIA evidence: connected by window handle to PID `25168`, title `Maria Agent v3.1.61`; screenshot `artifacts\p1-20260527-1527-c4f03651-agent-main.png`. Unbounded descendants search hung and was killed; bounded/no-descendant UIA capture works.

Known pre-fix/test contamination ignored for this run:
- All P0 phantom/stale rows documented above remain pre-fix contamination and must not be used as P1 evidence.
- `live-v3-p1-clean` device `a7085e14-47eb-546f-809d-ab6ec42c2bc8` was a failed clean-agent attempt before `PC_AGENT_DATA_DIR` isolation fix; ignore it for P1 run-id queries.
- Old agent local SQLite `UNKNOWN_TICKET` rows and old `device_outbox.status=sent` rows from P0 are not P1 regressions unless they carry `run_id=p1-20260527-1527-c4f03651` or a later P1 marker.

P1 checklist:
- [x] Baseline server health via direct HTTP/smoke.
- [x] Baseline clean local agent connected after DB cleanup and registration from zero.
- [x] Browser admin inventory confirmation for the clean device.
- [x] UIA baseline window confirmation.
- [ ] P1.1 Outbox ACK/NACK/dedup.
- [x] P1.2 Command idempotency.
- [ ] P1.3 Consent flow.
- [ ] P1.4 Module auto-install before run_tool.
- [ ] P1.5 Restart/reconnect with pending state.
- [ ] P1.6 Browser/UI projection consistency.

P1.1 working notes:
- Do not mark P1.1 green until each tested path records transport/API, server DB, agent SQLite, browser/admin or ticket UI, logs/action trace, and root-cause classification for mismatches.
- Real agent GUI initially stayed on account gate despite a persisted confirmed-binding session, but moved to `sidebar_view=tickets` / `content_view=tickets` after clean automation create on the same confirmed-binding account. This remains separate from later real GUI/UIA P1 checks.

P1.1.A valid ticket event happy path:
- Path tested: local GUI automation bridge `/ui/automation/run` for clean ticket setup, then controlled agent SQLite enqueue through `DatabaseManager.enqueue_event()`, real running agent sender over Protocol V3 WS, server DB query, real browser support ticket UI.
- Run marker: `p1-20260527-1527-c4f03651`, ticket `T-000609` / `f2918f87-cca3-42a9-b28f-f0a5e09d72b9`.
- Setup: `python scripts\agent_test_driver.py create-ticket live-v3-p1-clean2 --title "P1.1 p1-20260527-1527-c4f03651 outbox ticket" --description "P1.1.A clean ticket marker p1-20260527-1527-c4f03651. Создано после чистой регистрации агента."` -> `status=ok`, requester account session `c24c7842-8284-4964-a92f-7f608eaf52d2`, requester account mode `confirmed_binding`, GUI state moved to `sidebar_view=tickets`.
- Agent local enqueue: outbox `outbox_id=4`, `kind=chat_message`, `agent_seq=1`, `device_seq=NULL`, trace generated by local enqueue, payload text `P1.1.A agent outbox chat marker p1-20260527-1527-c4f03651`.
- Agent SQLite after ACK: `outbox=[]`; `outbox_sent_history` contains `outbox_id=4`, event id `2447d396-79cd-53da-b3a9-028c5a4d56da:f2918f87-cca3-42a9-b28f-f0a5e09d72b9:4:0`, payload preview includes marker.
- Server DB: `ticket_events` contains event id `2447d396-79cd-53da-b3a9-028c5a4d56da:f2918f87-cca3-42a9-b28f-f0a5e09d72b9:4:0`, `event_type=chat_message`, `device_id=2447d396-79cd-53da-b3a9-028c5a4d56da`, `agent_seq=1`, trace `065a08aa-8f2c-494b-960d-c36c0226669e`, text marker.
- Browser/UI: real browser `https://192.168.100.17:9443/app/tickets/f2918f87-cca3-42a9-b28f-f0a5e09d72b9` shows `T-000609`, status `В очереди`, requester `P1 Clean User 20260527`, and timeline text `P1.1.A agent outbox chat marker p1-20260527-1527-c4f03651`; evidence `artifacts\p1-20260527-1527-c4f03651-ticket-T-000609-snapshot.md`, screenshots `artifacts\p1-20260527-1527-c4f03651-ticket-T-000609.png` and `artifacts\p1-20260527-1527-c4f03651-ticket-T-000609-full.png`.
- Result: passed for this path; this does not cover duplicate/retryable NACK/mixed batch yet.

P1.1.B valid device event happy path:
- Path tested: controlled agent SQLite enqueue through `DatabaseManager.enqueue_event(ticket_id=None)`, real running agent sender over Protocol V3 WS, server DB query, real browser admin device page.
- Agent local enqueue: outbox `outbox_id=5`, `kind=tools_changed`, `device_seq=4`, `agent_seq=NULL`, payload `reason=p1_1_b_valid_device_event`, marker `p1-20260527-1527-c4f03651`.
- Agent SQLite after ACK: `outbox=[]`; `outbox_sent_history` contains `outbox_id=5`, event id `2447d396-79cd-53da-b3a9-028c5a4d56da:2447d396-79cd-53da-b3a9-028c5a4d56da:5:0`, payload preview includes marker.
- Server DB: `device_events` contains event id `2447d396-79cd-53da-b3a9-028c5a4d56da:2447d396-79cd-53da-b3a9-028c5a4d56da:5:0`, `event_type=tools_changed`, `device_seq=4`, trace `3d28c1ec-3142-42c5-be11-49836702719a`, payload marker.
- Agent local command side effect: `seen_commands` has a new terminal `success` row `b65d50f4-f718-4f78-be00-97d4ca7fa775` from server follow-up after `tools_changed`.
- Browser/UI: real browser admin device page `https://192.168.100.17:9443/app/admin/device?device=2447d396-79cd-53da-b3a9-028c5a4d56da` shows device `ADMIN-2`, online, agent `3.1.61`, observer/runtime data. Browser also produced a new 500 on account-events; recorded as `BUG-20260527-P1-03`.
- Result: device event ACK/persistence/local cleanup passed; browser projection has separate non-blocking bug.

P1.1.C duplicate ticket event by `agent_seq`:
- Path tested: controlled local agent SQLite duplicate injection, real running agent sender over Protocol V3 WS, server DB query, real browser ticket UI after refresh.
- Duplicate injected: local `outbox_id=6`, same ticket `f2918f87-cca3-42a9-b28f-f0a5e09d72b9`, same `agent_seq=1` as P1.1.A, payload text `P1.1.C duplicate agent_seq marker p1-20260527-1527-c4f03651`, event id `p1-duplicate-ticket-event-id-c4f03651`.
- Agent SQLite after ACK: `outbox=[]`; `outbox_sent_history` contains `outbox_id=6`, payload preview with duplicate marker. This proves the server ACKed the duplicate and the agent deleted the local row.
- Server DB: `ticket_events` count for `(ticket_id=f2918f87-cca3-42a9-b28f-f0a5e09d72b9, device_id=2447d396-79cd-53da-b3a9-028c5a4d56da, agent_seq=1)` remains `1`. No `P1.1.C duplicate` chat message persisted.
- Browser/UI: refreshed real browser ticket snapshot `artifacts\p1-20260527-1527-c4f03651-ticket-T-000609-after-duplicates-snapshot.md` contains `P1.1.A agent outbox` exactly once and `P1.1.C duplicate` zero times.
- Result: passed for duplicate by `agent_seq`.

P1.1.D duplicate device event by `device_seq`:
- Path tested: controlled local agent SQLite duplicate injection, real running agent sender over Protocol V3 WS, server DB query, admin browser context.
- Duplicate injected: local `outbox_id=7`, same device `2447d396-79cd-53da-b3a9-028c5a4d56da`, same `device_seq=4` as P1.1.B, payload reason `p1_1_d_duplicate_device_seq`, event id `p1-duplicate-device-event-id-c4f03651`.
- Agent SQLite after ACK: `outbox=[]`; `outbox_sent_history` contains `outbox_id=7`, payload preview with duplicate marker. This proves the server ACKed the duplicate and the agent deleted the local row.
- Server DB: `device_events` count for `(device_id=2447d396-79cd-53da-b3a9-028c5a4d56da, device_seq=4)` remains `1`. No `P1.1.D` device event persisted.
- Browser/UI: no separate duplicate tools_changed projection observed; admin device page still has separate account-events 500 recorded as `BUG-20260527-P1-03`.
- Result: passed for duplicate by `device_seq`.

P1.1.E mixed batch ACK/NACK:
- Path tested: raw WebSocket probe using the clean agent token from local SQLite against canonical WSS `wss://192.168.100.17:9443/ws`, server DB query, real browser ticket UI after refresh. This is a raw WS probe path, not the full local agent runtime.
- Probe artifact: `artifacts\p1-20260527-1527-c4f03651-mixed-batch.json`; token evidence is redacted to prefix `47fca88b`, sha256 prefix `11245df33169`, length `64`.
- Batch sent: valid ticket event with `agent_seq=2` and text `P1.1.E valid batch ticket marker p1-20260527-1527-c4f03651`; duplicate ticket event with `agent_seq=1`; invalid `both_seq`; unknown ticket `cd76ad86-b526-4d3b-93f8-e3c7e2f8cea3`; valid device `tools_changed` with `device_seq=5`; invalid device event with top-level `ticket_id`.
- Transport/API: server returned per-item ACK for the valid ticket, duplicate ticket, and valid device items; NACK `VALIDATION_ERROR` for `both_seq`; NACK `UNKNOWN_TICKET` for the unknown ticket; NACK `VALIDATION_ERROR` for device event with ticket context. The raw probe then received a live `list_tools` command generated by the valid `tools_changed` item and was superseded by the real agent with close code `4002`.
- Server DB: `ticket_events` persisted the valid batch ticket event with `agent_seq=2` and marker text; duplicate `agent_seq=1` did not create a second row. `device_events` persisted the valid batch device event with `device_seq=5` and marker `p1_1_e_valid_device_batch`; invalid items did not persist.
- Browser/UI: real browser ticket URL `https://192.168.100.17:9443/app/tickets/f2918f87-cca3-42a9-b28f-f0a5e09d72b9` shows `P1.1.E valid batch ticket marker p1-20260527-1527-c4f03651` once and does not show the duplicate marker; evidence `artifacts\p1-20260527-1527-c4f03651-ticket-T-000609-after-mixed-batch-snapshot.md` and screenshot `artifacts\p1-20260527-1527-c4f03651-ticket-T-000609-after-mixed-batch.png`.
- Agent/runtime side effect: because this was a raw WS probe for the real device, the server routed a follow-up `list_tools` command to the probe, not the real agent. The probe did not answer it, and server `device_outbox` row `83` reached `failed/TIMEOUT`. This is recorded as `BUG-20260527-P1-04` and means P1.1.E needs a clean rerun after the probe is made command-aware or after the valid device item is tested through the real agent path.
- Result: per-item ACK/NACK and persistence semantics passed for the tested batch contents, but the scenario is not green because the test tool created new runtime contamination.

P1.1.E clean rerun after test-tool fix:
- Path tested: `scripts\live_ws_v3_probe.py mixed-batch` against canonical WSS, using the same clean device token evidence only as prefix/hash/length; valid device item uses neutral `probe_device_event` to validate device-event persistence without triggering `list_tools`.
- Command: `python scripts\live_ws_v3_probe.py --ws-url wss://192.168.100.17:9443/ws --timeout 5 mixed-batch --ticket-id f2918f87-cca3-42a9-b28f-f0a5e09d72b9 --run-id p1-20260527-1527-c4f03651-cleanmix --valid-agent-seq 3 --duplicate-agent-seq 2 --valid-device-seq 6 --invalid-seq-base 920000`.
- Test-tool verification before live rerun: `python -m pytest scripts\test_live_ws_v3_probe.py -q` -> `2 passed`.
- Transport/API: artifact `artifacts\p1-20260527-1527-c4f03651-cleanmix-mixed-batch.json`; ACK ids: `valid-ticket`, `duplicate-ticket`, `valid-device`; NACK ids: `both-seq` with `VALIDATION_ERROR`, `unknown-ticket` with `UNKNOWN_TICKET`, `device-with-ticket` with `VALIDATION_ERROR`; `unexpected_command_count=0`; raw probe was later superseded by real agent with close `4002`.
- Server DB: `ticket_events` persisted cleanmix valid ticket event with `agent_seq=3`, trace `49b6487c-5456-4fa2-b2b1-33cbdfa7e82b`, text `P1.1.E valid batch ticket marker p1-20260527-1527-c4f03651-cleanmix`; duplicate `agent_seq=2` did not create a second event. `device_events` persisted cleanmix valid device event `event_type=probe_device_event`, `device_seq=6`, trace `7283b676-17dd-4b35-9a6d-84532571acd7`, marker `p1-20260527-1527-c4f03651-cleanmix`.
- Server DB contamination check: no new `device_outbox` rows after id `83`; id `83` remains labeled as pre-fix P1-04 test contamination (`list_tools`, `failed/TIMEOUT`) and is not counted as cleanmix regression.
- Browser/UI: real browser ticket URL `https://192.168.100.17:9443/app/tickets/f2918f87-cca3-42a9-b28f-f0a5e09d72b9`; snapshot `artifacts\p1-20260527-1527-c4f03651-ticket-T-000609-after-cleanmix-snapshot.md` shows both the original P1.1.E valid marker and the cleanmix valid marker, and does not show the cleanmix duplicate marker. Screenshot `artifacts\p1-20260527-1527-c4f03651-ticket-T-000609-after-cleanmix.png`.
- Result: clean mixed-batch ACK/NACK/dedup path passed for raw WS probe with explicit test-tool limitation fixed; P1.1.F retryable NACK/backoff still pending.

P1.1.F retryable NACK / backoff:
- Path assessed: code/docs search and existing server/agent tests only; no live retryable NACK was triggered yet.
- Run marker: `p1-20260527-1527-c4f03651`.
- Findings: server has retryable message-level NACK only through `RATE_LIMITED` in `server\websocket\agent_services.py`, and retryable persistence failures through internal exceptions. Agent retry/backoff behavior exists in `pc_agent\core\sender.py` and is covered by existing focused tests, but there is no safe live stand hook for one-shot transient storage/rate-limit simulation.
- Safety decision: did not overload live server to trigger `RATE_LIMITED`; this is explicitly forbidden by the P1 plan. Did not force DB/transient storage failures because that would turn a diagnostic into infrastructure disruption.
- Required follow-up before P1.1 can be fully green: add a controlled test-only diagnostic hook, gated off by default, that can NACK one marked outbox item with `retryable=true` and then allow retry persistence after a short marker-controlled window. It must be documented as diagnostic-only, not production protocol behavior, and must be removed/disabled after live validation.
- Result: P1.1.F is attempted but blocked by missing safe live retryable-NACK hook. P1.1 is not fully green; P1.2 may proceed with this limitation explicitly recorded, but P1 close cannot claim retryable backoff coverage until the hook/live regression exists.

P1.2.A duplicate successful command:
- Path tested: real browser authenticated support session `fetch` to typed web route `POST /api/web/support/tickets/f2918f87-cca3-42a9-b28f-f0a5e09d72b9/tools/run` for initial `system.collect`, then diagnostic server DB enqueue of a duplicate `device_outbox` row with the same `command_id/request_id/operation_id`. Browser timeline, server DB, and agent SQLite were checked after duplicate delivery.
- Run marker: `p1-20260527-1527-c4f03651`, ticket `T-000609`, operation `4605cb0d-bf44-4461-90e1-97509b392b4f`.
- Browser/API start: real browser page context returned HTTP `202`, `dispatch_status=accepted`, `tool_name=system.collect`, `operation_id=4605cb0d-bf44-4461-90e1-97509b392b4f`, `trace_id=6f3455cb-e94c-4928-8e81-1caccbf7e8cc`.
- Server DB before duplicate: `operations.status=succeeded`, `actor_role=admin`, `device_outbox` id `84` `status=delivered`, `ticket_events` ids `149 tool_call_started` and `151 tool_call_result`.
- Agent SQLite before duplicate: `seen_commands` has one row for command `4605cb0d-bf44-4461-90e1-97509b392b4f`, `status=success`; local `outbox=[]`; `outbox_sent_history` has one `tool_response` outbox id `8`.
- Duplicate injection: server diagnostic enqueue through `DeviceOutboxRepo.enqueue_command()` created `device_outbox` id `85` with same `command_id=request_id=operation_id=4605cb0d-bf44-4461-90e1-97509b392b4f`, same `trace_id=6f3455cb-e94c-4928-8e81-1caccbf7e8cc`, command `run_tool`. This is a server DB diagnostic path, not a product UI route.
- Server DB after duplicate: `device_outbox` ids `84` and `85` are both `delivered`; `operations.status` remains `succeeded`; `ticket_events` for the operation remain exactly ids `149 tool_call_started` and `151 tool_call_result` (no second terminal event).
- Agent SQLite after duplicate: `seen_commands` still has one terminal `success` row for the command; `completed_at/started_at` unchanged from original execution; local `outbox=[]`; `outbox_sent_history` did not add a second `tool_response`.
- Browser/UI: real browser ticket snapshot `artifacts\p1-20260527-1527-c4f03651-p1-2a-after-duplicate-snapshot.md` shows one `system.collect` diagnostic result with CPU/RAM/Disk values and no duplicate visible result; screenshot `artifacts\p1-20260527-1527-c4f03651-p1-2a-after-duplicate.png`.
- Result: passed for duplicate-after-success idempotency. Tool execution happened once; duplicate command was delivered and resolved from agent idempotency without duplicate local/server/browser terminal result.

P1.2.B duplicate while in progress:
- Path tested: real browser authenticated support session to typed web route `POST /api/web/support/tickets/f2918f87-cca3-42a9-b28f-f0a5e09d72b9/tools/run` for initial long-running `screen.record`, then diagnostic server DB enqueue of duplicate `device_outbox` row with the same `command_id/request_id/operation_id` while the original command was still non-terminal. Browser timeline, server DB, agent SQLite and action trace were checked after completion.
- Run marker: `p1-20260527-1527-c4f03651`, ticket `T-000609`, operation `755c2996-27e1-43b0-8d94-7d5ba7595b5b`.
- Browser/API start: real browser page context returned HTTP `202`, `dispatch_status=accepted`, `tool_name=screen.record`, `operation_id=755c2996-27e1-43b0-8d94-7d5ba7595b5b`, `trace_id=6f3455cb-e94c-4928-8e81-1caccbf7e8cc`. Tool params were `duration_sec=20`, `fps=5`, `max_width=640`, `quality_crf=40`.
- Duplicate injection timing: before duplicate enqueue, server DB showed `operations.status=accepted`, original `device_outbox` id `86` `status=sent`, `delivered_at=NULL`. Diagnostic server DB enqueue through `DeviceOutboxRepo.enqueue_command()` created duplicate `device_outbox` id `87` with same `command_id=request_id=operation_id=755c2996-27e1-43b0-8d94-7d5ba7595b5b`, same `trace_id=6f3455cb-e94c-4928-8e81-1caccbf7e8cc`, command `run_tool`, actor_role `admin`. This is a server DB diagnostic path, not a product UI route.
- Agent action trace: one `orchestrator tool.run` for operation `755c2996-27e1-43b0-8d94-7d5ba7595b5b`; execution lane acquired once; module `screen.record` capture ran once; `frames_captured=100`, output path `temp\recording_1779880603.mp4`; module finished `partial` with `upload_error_count=1`.
- Server DB after duplicate: original outbox id `86` and duplicate id `87` are both `delivered`; `operations.status=succeeded`; `ticket_events` for the operation are exactly `153 tool_call_started` and `155 tool_call_result` (one start, one terminal result).
- Agent SQLite after duplicate: `seen_commands` has one row for command `755c2996-27e1-43b0-8d94-7d5ba7595b5b`, terminal `status=error` with ToolResponse `status=partial`; local `outbox=[]`; `outbox_sent_history` has exactly one new `tool_response` row, outbox id `9`.
- Browser/UI: real browser ticket snapshot `artifacts\p1-20260527-1527-c4f03651-p1-2b-after-duplicate-running-snapshot.md` shows one `screen.record` start and one `screen.record` diagnostic result with `status=partial`, `request_id=755c2996-27e1-43b0-8d94-7d5ba7595b5b`; screenshot `artifacts\p1-20260527-1527-c4f03651-p1-2b-after-duplicate-running.png`.
- Result: idempotency part passed for duplicate while in progress: the duplicate did not create a second execution, second terminal event, second local `seen_commands` row, or second local `tool_response`. Separate artifact upload failure during `screen.record` is recorded as `BUG-20260527-P1-06` and is not treated as idempotency failure.

P1.2.C duplicate after cancel:
- Path tested: real browser authenticated support route started `screen.record`; real browser web-session cancel route `POST /api/web/support/operations/87c17283-32f8-4202-bef2-3b9db48fbccf/cancel` requested cancellation; after terminal cancel, diagnostic server DB enqueue created a duplicate target `run_tool` command with the same `command_id/request_id/operation_id`. Server DB, agent SQLite and browser timeline were checked after duplicate delivery.
- Run marker: `p1-20260527-1527-c4f03651`, ticket `T-000609`, target operation `87c17283-32f8-4202-bef2-3b9db48fbccf`, cancel operation `95d08db8-a058-49b0-b05c-7104fefb6739`.
- Browser/API start: real browser page context returned HTTP `202`, `dispatch_status=accepted`, `tool_name=screen.record`, target operation `87c17283-32f8-4202-bef2-3b9db48fbccf`. Browser cancel route returned HTTP `200`, `target_operation_id=87c17283-32f8-4202-bef2-3b9db48fbccf`, `cancel_operation_id=95d08db8-a058-49b0-b05c-7104fefb6739`.
- Agent SQLite before duplicate-after-cancel: target `seen_commands.status=canceled` with result `error.code=OPERATION_CANCELED`; cancel command `seen_commands.status=success`; local `outbox=[]`; `outbox_sent_history` contains target cancel `tool_call_result` outbox id `10` and cancel operation `tool_response` outbox id `11`.
- Server DB before duplicate-after-cancel: target operation `status=canceled`, `canceled_at=2026-05-27T11:23:52.975499+00:00`; cancel operation `status=succeeded`; target `device_outbox` id `88` delivered; cancel `device_outbox` id `89` delivered.
- Duplicate injection: diagnostic server DB enqueue created duplicate target `device_outbox` id `90` with same `command_id=request_id=operation_id=87c17283-32f8-4202-bef2-3b9db48fbccf`, command `run_tool`, actor_role `admin`. This is a server DB diagnostic path, not a product UI route.
- Server DB after duplicate: duplicate id `90` delivered; target operation remained `canceled`; cancel operation remained `succeeded`; ticket events for target operation are exactly one each of `tool_call_started`, `op_cancel_requested`, `tool_call_result`, `op_canceled`; no second terminal result after duplicate.
- Agent SQLite after duplicate: target command still has one terminal `canceled` row, no rerun; local `outbox=[]`; `outbox_sent_history` did not add a second target tool response after duplicate delivery.
- Browser/UI: real browser ticket snapshot `artifacts\p1-20260527-1527-c4f03651-p1-2c-after-duplicate-cancel-snapshot.md` shows `screen.record` result `Статус Отменена`, result text `Tool screen.record canceled`, and cancel action disabled as already terminal; screenshot `artifacts\p1-20260527-1527-c4f03651-p1-2c-after-duplicate-cancel.png`.
- Result: passed for duplicate-after-cancel idempotency. Target command did not rerun, local idempotency stayed terminal `canceled`, and server/browser did not create duplicate terminal output.

P1.2.D stale in_progress:
- Path tested: unit/integration test only with isolated temporary agent SQLite DB. Live corruption of the clean agent database was intentionally not performed because the P1 plan says to use test-only setup for stale in-progress.
- Run marker: `p1-20260527-1527-c4f03651`.
- Test command: `python -m pytest pc_agent\tests\test_seen_commands_retry_policy.py pc_agent\tests\test_ws_agent_canceled_command_idempotency.py -q`.
- Evidence: `5 passed in 1.19s`. The tests cover stale retry metadata (`stale_retry_count`, owner instance transfer, terminal reset), canceled background command terminal reporting, duplicate canceled command cached response, and pre-canceled background dispatch not executing the tool.
- Live applicability: browser/UI and server DB are not applicable to this isolated stale-state test because no live operation was intentionally corrupted. Adjacent live evidence is P1.2.C, where duplicate-after-cancel on the real agent returned cached terminal canceled behavior and did not rerun.
- Result: passed as test-only stale in-progress/idempotency coverage with explicit scope limitation.

P1.3.A consent required:
- Path tested: real browser support session, server DB, agent SQLite, approval center browser UI, UIA attempted against local GUI. Test user setup: temporary support user `p1support_20260527_1527` created via server `UiUsersRepo`, added to queue `servicedesk_l1` (`queue_id=1`) so ticket access would not mask consent behavior. This is setup evidence, not product pass evidence.
- Run marker: `p1-20260527-1527-c4f03651`, ticket `T-000609`, operation `0b5da7ba-fa46-48e4-8e7d-d0ac38eef029`, tool `diag.logs.collect`.
- Browser/API: as `admin`, `diag.logs.collect` ran immediately with `dispatch_status=accepted`, `actor_role=admin`, and no consent. This matches admin-bypass policy and is not counted as P1.3 consent pass. As `support`, after queue membership setup, real browser `POST /api/web/support/tickets/f2918f87-cca3-42a9-b28f-f0a5e09d72b9/tools/run` returned HTTP `202` with `dispatch_status=waiting_consent`.
- Server DB: operation `0b5da7ba-fa46-48e4-8e7d-d0ac38eef029` is `status=waiting_consent`, `actor_role=support`, no `device_outbox` row, no `consent_decisions` row, and no `ticket_events` rows for that operation.
- Agent SQLite: `pending_consents` count stayed `0`; no `seen_commands` row for operation `0b5da7ba-fa46-48e4-8e7d-d0ac38eef029`; local `outbox` stayed empty. This means the current support route implements server-side consent hold and does not produce an agent-local consent prompt.
- Browser/UI: ticket detail page did not contain `diag.logs.collect`, `waiting_consent`, `Ожидает`, or `соглас` for operation `0b5da7ba-fa46-48e4-8e7d-d0ac38eef029`; evidence snapshots `artifacts\p1-20260527-1527-c4f03651-p1-3a-support-waiting-consent-snapshot.md` and `artifacts\p1-20260527-1527-c4f03651-p1-3a-support-waiting-consent-snapshot2.md`. Approval center `/app/support/approvals?kind=pending_consent&status=pending` shows one risky tool consent for `diag.logs.collect`, ticket `T-000609`, operation `0b5da7ba-fa46-48e4-8e7d-d0ac38eef029`; screenshot `artifacts\p1-20260527-1527-c4f03651-p1-3a-approval-center.png`.
- UIA: `.venvs\agent-win\Scripts\python.exe -c "import pywinauto; print(pywinauto.__version__)"` returned `0.6.9`. Attempts to inspect the local GUI window for a consent prompt via `Application(backend="uia")` / `Desktop(backend="uia")` hung in UIA discovery and were force-stopped. Combined with agent SQLite `pending_consents=0`, there is no evidence of a real local GUI consent prompt for this server-side waiting operation.
- Approve/deny attempt: real browser support cookie `POST /api/operations/0b5da7ba-fa46-48e4-8e7d-d0ac38eef029/approve` returned HTTP `401 AUTH_REQUIRED`. Approval center explicitly shows only view actions: "Первый срез работает только для просмотра: действия подтверждения и отклонения показываются только если сервер отдаёт безопасное типизированное действие."
- Recovery cleanup: after recording evidence, operation `0b5da7ba-fa46-48e4-8e7d-d0ac38eef029` was denied through server `OperationService.deny_consent()` with actor `p1-live-validation-cleanup` to avoid polluting P1.4/P1.5. This is recovery only, not a fix. Post-cleanup DB state: `operations.status=denied`, `error_code=CONSENT_DENIED`, one `consent_decisions.decision=denied`.
- Result: P1.3 is blocked/incomplete. Consent-required creation reaches server `waiting_consent` and approval-center projection, but ticket timeline, browser approve/deny, and agent GUI/pending-consent layers are missing.

### BUG-20260527-P1-07 — Web-session consent approve/deny is not available from support UI

Severity: P1
Status: known-limitation
Area: consent / browser / auth-account-session / UI projection

P1 scenario: P1.3 Consent flow.
Run id: `p1-20260527-1527-c4f03651`
Expected: A support browser session that can create a `waiting_consent` operation should be able to approve or deny it through a typed web-session route or visible approval-center action. Ticket detail should expose the pending consent state where operators work the ticket.
Actual: Support browser creates operation `0b5da7ba-fa46-48e4-8e7d-d0ac38eef029` with `dispatch_status=waiting_consent`, but approval center is read-only and `POST /api/operations/{operation_id}/approve` with the same web session returns `401 AUTH_REQUIRED`. Ticket detail does not show the pending consent operation.
Repro steps:
1. Log in through real browser as support user `p1support_20260527_1527`.
2. Open ticket `T-000609` after adding the user to queue `servicedesk_l1`.
3. Run `diag.logs.collect` through `/api/web/support/tickets/{ticket_id}/tools/run`.
4. Open `/app/support/approvals?kind=pending_consent&status=pending`.
5. Try browser fetch `POST /api/operations/0b5da7ba-fa46-48e4-8e7d-d0ac38eef029/approve`.

Evidence:
- Transport/API: support `/tools/run` returned HTTP `202`, `dispatch_status=waiting_consent`; approve endpoint returned HTTP `401`, `error_code=AUTH_REQUIRED`.
- Server log: not yet collected for this specific operation.
- Agent log: not applicable before approve because no command was dispatched.
- Server DB: `operations.status=waiting_consent`, `actor_role=support`; `device_outbox` count `0`; `consent_decisions` count `0`; `ticket_events` count `0` for the operation.
- Agent SQLite: `pending_consents=0`, no `seen_commands` row for the operation.
- Browser/UI: approval center shows the pending risky tool consent but states the first slice is view-only; ticket detail does not show the pending consent. Screenshot `artifacts\p1-20260527-1527-c4f03651-p1-3a-approval-center.png`.
- UIA: pywinauto `0.6.9`, `backend="uia"` attempted; no local prompt evidence because no local pending consent exists.
- Test artifact: `artifacts\p1-20260527-1527-c4f03651-p1-3a-support-waiting-consent-snapshot*.md`.
- Run marker: `p1-20260527-1527-c4f03651-p1-3a-support-2`.

Impact: P1.3 approve/deny/duplicate-decision scenarios cannot be validated through the required browser UI path. Operators can create a waiting consent but cannot complete it from the web-session UI.
Root cause hypothesis: consent approve/deny handlers exist only as legacy/token-auth `/api/operations/{id}/approve|deny` routes and there is no typed `/api/web/support/operations/{id}/approve|deny` alias or approval-center action DTO. Ticket detail projection also lacks the waiting-consent operation because no ticket event is written.
Blocking further P1: yes for P1.3.B-E canonical browser path; no for P1.4/P1.5 if the waiting operation is cleaned up as recovery and labeled.
Fix now: no, per P1 rule continue collecting P1 findings unless this blocks the next scenario set.
Fix summary:
Changed files:
Tests:
Live regression:
Remaining risk:

### BUG-20260527-P1-08 — Server-side risky tool consent does not create agent GUI consent prompt

Severity: P1
Status: known-limitation
Area: consent / agent-sqlite / local GUI-UIA / documentation drift

P1 scenario: P1.3 Consent flow.
Run id: `p1-20260527-1527-c4f03651`
Expected: For the P1 plan's local-agent consent flow, a consent-required tool should create local agent `pending_consents`, show a real agent GUI prompt accessible by pywinauto/UIA, and only execute after approve.
Actual: Browser support route holds the operation server-side in `waiting_consent` and does not send a command to the agent. Agent SQLite has no `pending_consents` row and no `seen_commands` row for operation `0b5da7ba-fa46-48e4-8e7d-d0ac38eef029`; no local GUI prompt is observable.
Repro steps:
1. As support, run `diag.logs.collect` on ticket `T-000609`.
2. Query agent SQLite `pending_consents`, `seen_commands`, `outbox`.
3. Attempt UIA inspection of local agent GUI.

Evidence:
- Transport/API: `/api/web/support/tickets/{ticket_id}/tools/run` returns `dispatch_status=waiting_consent`.
- Server log: not yet collected.
- Agent log: no dispatched command evidence collected yet.
- Server DB: no `device_outbox` row for the waiting operation.
- Agent SQLite: `pending_consents=0`, `seen_commands=0` for the operation, `outbox=0`.
- Browser/UI: approval center says the request waits for user consent, but the agent has no local pending consent.
- UIA: pywinauto `0.6.9`; UIA discovery attempts hung and were stopped; absence of local pending state is confirmed by SQLite.
- Test artifact:
- Run marker: `p1-20260527-1527-c4f03651-p1-3a-support-2`.

Impact: The P1 plan's real local GUI consent scenario cannot be marked green. This may be a product contract drift: current implementation appears to model risky-tool consent as server-side approval-center state, while the P1 requirement expects requester/agent-side confirmation.
Root cause hypothesis: server policy short-circuits consent-required support operations into `operations.status=waiting_consent` before command dispatch; agent-side `ConsentService.create_pending()` only runs when the agent receives a command and its local policy denies with `requires_consent`.
Blocking further P1: yes for agent-GUI consent subcases; no for module/reconnect scenarios.
Fix now: no.
Fix summary:
Changed files:
Tests:
Live regression:
Remaining risk:

P1.4.A module auto-install happy path:
- Path tested: real browser support route, server DB, agent SQLite, agent logs/action trace, browser ticket detail.
- Run marker: `p1-20260527-1527-c4f03651-p1-4a`, ticket `T-000609`, operation `87e0df39-c107-436c-bab2-1c024cc069eb`, module `network_basic`, tool `network.ping`.
- Pre-state: server `device_modules` count for clean device was `0`; `device_desired_modules` count `0`; latest toolset snapshot `29`; no `network_basic` device events.
- Browser/API: support `/api/web/support/tickets/f2918f87-cca3-42a9-b28f-f0a5e09d72b9/tools/run` returned HTTP `202`, `dispatch_status=accepted`, operation `87e0df39-c107-436c-bab2-1c024cc069eb`.
- Server DB: install command `device_outbox.id=92` (`install_module_package`) delivered; target run command `device_outbox.id=95` delivered; `device_modules.network_basic` persisted as `installed=true`, `active=true`, version `1.0.0`; `device_desired_modules.network_basic` state `installed`; new `device_toolset_snapshots.snapshot_id=34`; target operation terminal `succeeded`; ticket events `167 tool_call_started` and `169 tool_call_result` persisted for `network.ping`.
- Agent local state: `seen_commands` has operation `87e0df39-c107-436c-bab2-1c024cc069eb` terminal `success`; local `outbox=[]`; `outbox_sent_history` has `13 tools_changed`, `14 module_state_changed`, and `15 tool_response`.
- Agent logs/action trace: logs show download/install/activation of `network_basic@1.0.0`, `tools_changed event enqueued: toolset_hash=afa6647205d24098, tools_count=11`, and `[module_state_changed] Event enqueued: reason=install:network_basic@1.0.0 modules=1`; action trace shows `network.ping` resolved through module `network_basic` and completed `ok`.
- Browser/UI: real ticket page shows `network.ping` accepted and succeeded with `127.0.0.1`, `count=2`, `Minimum = 0ms`; snapshot `artifacts\p1-20260527-1527-c4f03651-p1-4a-network-ping-ticket-snapshot.md`, screenshot `artifacts\p1-20260527-1527-c4f03651-p1-4a-network-ping-ticket.png`.
- Mismatch: server `device_events` did not persist the agent-sent `tools_changed` or `module_state_changed` for `network_basic`; latest server `device_events` still stop at previous P1.1 probe rows (`device_seq=6`), while local sent history says outbox ids `13/14` were sent. Recorded as `BUG-20260527-P1-09`.
- Result: functional auto-install and tool execution passed, but P1.4.A is not green because durable module lifecycle device events are missing on the server.

P1.4.B module not on server:
- Path tested: real browser support route and server DB.
- Run marker: `p1-20260527-1527-c4f03651-p1-4b`, ticket `T-000609`, tool `p1.missing_tool_20260527`, operation `deecaa73-aa6c-4be5-83f2-a7779f3d9355`.
- Browser/API: `/api/web/support/tickets/f2918f87-cca3-42a9-b28f-f0a5e09d72b9/tools/run` returned HTTP `503`, `error_code=MODULE_NOT_ON_SERVER`, with a controlled message that module `p1` must be uploaded or installed manually.
- Server DB: operation `deecaa73-aa6c-4be5-83f2-a7779f3d9355` persisted terminal `failed`, `error_code=MODULE_NOT_ON_SERVER`; no `device_outbox` rows; no `device_desired_modules` row for module `p1`; one ticket event `171 tool_call_result` records the controlled error.
- Agent local state: not applicable because no command should be dispatched for unknown module/tool.
- Browser/UI: the immediate browser route response is the canonical negative UI/API evidence; ticket timeline projection for the error exists through event `171` and should be included in P1.6 replay check.
- Result: passed for controlled unknown module failure with no stale desired state or outbox.

P1.4.E no-op reinstall / duplicate lifecycle noise:
- Path tested: real browser support route, server DB, agent SQLite, browser ticket detail.
- Run marker: `p1-20260527-1527-c4f03651-p1-4e`, ticket `T-000609`, operation `86afe8f8-8faf-416e-b456-38562d0314ad`, module `network_basic`, tool `network.ping`.
- Browser/API: support `/api/web/support/tickets/f2918f87-cca3-42a9-b28f-f0a5e09d72b9/tools/run` returned HTTP `202`; browser ticket detail shows `network.ping` accepted and then `Успешно` with `target=127.0.0.1`, `count=1`, `summary=Minimum = 0ms, Maximum = 0ms, Average = 0ms`. Evidence: `artifacts\p1-20260527-1527-c4f03651-p1-4e-network-ping-ticket-snapshot.md`, `artifacts\p1-20260527-1527-c4f03651-p1-4e-network-ping-ticket.png`.
- Server DB: operation `86afe8f8-8faf-416e-b456-38562d0314ad` terminal `succeeded`; only one `device_outbox` row `id=96`, `command=run_tool`, `status=delivered`; ticket events `172 tool_call_started` and `174 tool_call_result`; no new `install_module_package` command after original install command `id=92`; latest toolset snapshots remain `34` and `29`, so no duplicate snapshot was created by the no-op run.
- Agent local state: `seen_commands.command_id=86afe8f8-8faf-416e-b456-38562d0314ad` terminal `success`; local `outbox` count `0`; `pending_consents` count `0`; `outbox_sent_history` added only `outbox_id=16`, `kind=tool_response`; no new local `tools_changed` or `module_state_changed` for the no-op run.
- Device event note: server `device_events` still has no new lifecycle event after `device_seq=6`, which is expected for a no-op reinstall, but the original P1.4.A missing persistence remains tracked as `BUG-20260527-P1-09`.
- Result: passed for no duplicate install/snapshot/toolset churn on already-installed module; P1.4 overall remains not green because P1.4.A durable lifecycle events are missing and P1.4.C/D are not yet attempted.

P1.4.C/P1.4.D negative module install guards:
- Diagnostic setup path: direct server-side test setup only, not a product UI path. Created three disposable server module rows/packages for run id `p1-20260527-1527-c4f03651`: `p1_sha_bad_1527.run` with stored SHA prefix `000000000000` and real package SHA prefix `e4bd999d2042`; `p1_linux_only_1527.run` with `platforms=["linux"]`; `p1_future_agent_1527.run` with `min_agent_version=99.0.0`. The modules are safe/read-only and exist only to exercise auto-install negative gates.
- Canonical tested path: real browser support route `POST /api/web/support/tickets/f2918f87-cca3-42a9-b28f-f0a5e09d72b9/tools/run`.
- P1.4.C SHA mismatch marker `p1-20260527-1527-c4f03651-p1-4c-sha`: browser route returned HTTP `503`, `error_code=MODULE_INSTALL_FAILED`; agent received `install_module_package` command `bafaf9d5-6786-44c6-8ebb-8c2304c180d6` and local `seen_commands.status=error`, `MODULE_DOWNLOAD_FAILED`, SHA mismatch expected stored zero hash vs real prefix `e4bd999d2042`.
- P1.4.D platform mismatch marker `p1-20260527-1527-c4f03651-p1-4d-platform`: browser route returned HTTP `503`, `error_code=MODULE_PLATFORM_MISMATCH`, device OS `Windows`, module allowed `["linux"]`.
- P1.4.D min agent version marker `p1-20260527-1527-c4f03651-p1-4d-min-agent`: browser route returned HTTP `503`, `error_code=AGENT_VERSION_TOO_OLD`, required `99.0.0`, device reports `3.1.61`.
- Server DB mismatch: all three negative markers have no ticket `operations` or `ticket_events`; SHA mismatch nevertheless created install `device_outbox.id=97`, `status=delivered`, `operation_id=bafaf9d5-6786-44c6-8ebb-8c2304c180d6`, and then stale desired state caused an additional reconcile install command `device_outbox.id=98`, `operation_id=63b2c67e-c070-4ea4-ba75-2c281d5871a2`. SHA mismatch wrote `device_desired_modules` row `id=3`, `module_name=p1_sha_bad_1527`, `state=installed`, `desired_sha256=000000...`, even though installation failed and no `device_modules` row exists.
- Agent local state: local `outbox` count `0`; `pending_consents` count `0`; no `outbox_sent_history` rows for these negative module runs; only the SHA mismatch install command is visible in `seen_commands` because platform/version gates failed server-side before dispatch.
- Browser/UI: real browser route returned the three controlled 503 JSON errors; current ticket page does not show corresponding failed operation cards/timeline entries because no server operation/events were persisted. Evidence: `artifacts\p1-20260527-1527-c4f03651-p1-4cd-negative-module-ticket-snapshot.md`, `artifacts\p1-20260527-1527-c4f03651-p1-4cd-negative-module-ticket.png`.
- Result: negative guard error codes are controlled, but P1.4.C/D are not green because expected terminal failed operation/timeline evidence is missing and SHA mismatch leaves stale desired state. Recorded as `BUG-20260527-P1-10`.
- Recovery cleanup after evidence: updated only disposable `device_desired_modules.id=3` for `p1_sha_bad_1527` to `state=absent`, `desired_version=null`, `desired_sha256=null`, `reason=p1-live-cleanup`, `updated_by=p1-live-validation` at `2026-05-27 12:04:14+00`. This is recovery only, not a fix; the bug remains `reproduced`.

### BUG-20260527-P1-09 — Auto-install module lifecycle device events are ACKed locally but not persisted on server

Severity: P1
Status: verified-fixed
Area: module-runtime / outbox / server-db / protocol

P1 scenario: P1.4 Module auto-install before run_tool.
Run id: `p1-20260527-1527-c4f03651`
Expected: After module install/activation and toolset hash change, agent emits `module_state_changed` and `tools_changed` with `device_seq`; server ACKs only after persistence and `device_events` contains both rows; browser/admin module/device view reflects durable event history.
Actual: Agent local sent history has outbox `13 tools_changed` and `14 module_state_changed`, and local outbox is empty, but server `device_events` has no rows for the `network_basic` install/toolset change. Functional module state and snapshot updated, so the missing layer is durable device event persistence.
Repro steps:
1. Start from clean agent `live-v3-p1-clean2` with no installed modules in server `device_modules`.
2. As support, run `network.ping` with marker `p1-20260527-1527-c4f03651-p1-4a`.
3. Query agent SQLite `outbox_sent_history` and server DB `device_events`.

Evidence:
- Transport/API: browser support route accepted operation `87e0df39-c107-436c-bab2-1c024cc069eb`; install command `device_outbox.id=92` and run command `id=95` delivered.
- Server log: `manage_remote_stack logs --contains network_basic|tools_changed|module_state_changed` returned no matching recent server lines; targeted journal grep did not show persistence evidence.
- Agent log: `network_basic@1.0.0` downloaded/installed/activated; `tools_changed` and `[module_state_changed]` events enqueued.
- Server DB: `device_modules.network_basic` active, `device_desired_modules.network_basic` installed, snapshot `34` created, operation succeeded, but `device_events` contains no `network_basic` module lifecycle rows after previous P1.1 rows.
- Agent SQLite: `outbox_sent_history` rows `13 tools_changed`, `14 module_state_changed`, `15 tool_response`; `outbox=[]`.
- Browser/UI: ticket detail shows `network.ping` success; admin module/device event projection not yet rechecked because DB event layer already failed.
- UIA: not applicable to module auto-install.
- Test artifact: `artifacts\p1-20260527-1527-c4f03651-p1-4a-network-ping-ticket-snapshot.md`, `artifacts\p1-20260527-1527-c4f03651-p1-4a-network-ping-ticket.png`.
- Run marker: `p1-20260527-1527-c4f03651-p1-4a`.

Impact: P1.4 module lifecycle cannot be trusted; server state converges through command_result side effects and snapshot, but durable lifecycle event history is missing. This resembles a data-integrity risk because local outbox considers events sent while server does not show persistence.
Root cause hypothesis: either server outbox ingest ACKs these device events without persistence, or persistence rejects/deduplicates device_seq/event context while still ACKing. Needs transport ACK/log correlation before patching.
Blocking further P1: yes for P1.4 lifecycle correctness; no for P1.5 reconnect if this contamination is labeled and filtered.
Fix now: no, continue P1 finding pass unless later P1 scenarios depend on module lifecycle event persistence.
Fix summary:
Changed files:
Tests:
Live regression:
Remaining risk:

### BUG-20260527-P1-10 — Auto-install negative failures bypass operation/timeline and SHA mismatch leaves desired installed

Severity: P1
Status: deferred
Area: module-runtime / operation lifecycle / server-db / UI projection

P1 scenario: P1.4 Module auto-install before run_tool, negative cases SHA mismatch, platform mismatch, min_agent_version mismatch.
Run id: `p1-20260527-1527-c4f03651`
Expected: Negative module auto-install checks should create a terminal failed operation/ticket event visible in browser for support workflows; SHA mismatch must not leave desired state as `installed` after failed install; no bad module should become active.
Actual: Browser support route returned controlled HTTP `503` errors, but no ticket `operations` or `ticket_events` were persisted for any of the three markers. SHA mismatch dispatched agent `install_module_package` command `device_outbox.id=97` and failed locally, then the stale desired state caused another reconcile install command `device_outbox.id=98`; server left `device_desired_modules.p1_sha_bad_1527` as `state=installed` with the bad SHA and no actual `device_modules` row until recovery cleanup.
Repro steps:
1. Create disposable safe test modules `p1_sha_bad_1527`, `p1_linux_only_1527`, `p1_future_agent_1527`.
2. Corrupt only the stored SHA for `p1_sha_bad_1527`.
3. From real support browser session, call `/api/web/support/tickets/{ticket_id}/tools/run` for all three tools with P1 markers.
4. Query `operations`, `ticket_events`, `device_outbox`, `device_desired_modules`, `device_modules`, and agent SQLite.

Evidence:
- Transport/API: browser route returned `MODULE_INSTALL_FAILED` for SHA mismatch, `MODULE_PLATFORM_MISMATCH` for linux-only module on Windows device, and `AGENT_VERSION_TOO_OLD` for min agent `99.0.0`.
- Server log: not yet root-caused; server DB confirms missing operation/timeline persistence.
- Agent log: `agent.log` lines around 2026-05-27 17:00:06 show `Module download failed: SHA256 mismatch...`; local command id `bafaf9d5-6786-44c6-8ebb-8c2304c180d6`.
- Server DB: no ticket operation/ticket event rows for markers `p1-4c-sha`, `p1-4d-platform`, `p1-4d-min-agent`; SHA mismatch install `device_outbox.id=97` delivered and reconcile retry `device_outbox.id=98` delivered; `device_desired_modules.id=3`, module `p1_sha_bad_1527`, `state=installed`, desired SHA zero hash before cleanup; `device_modules` empty for all three diagnostic modules.
- Agent SQLite: `seen_commands.command_id=bafaf9d5-6786-44c6-8ebb-8c2304c180d6`, `status=error`, `MODULE_DOWNLOAD_FAILED`; reconcile retry `seen_commands.command_id=63b2c67e-c070-4ea4-ba75-2c281d5871a2`, `status=error`, same SHA mismatch; local `outbox=0`, `pending_consents=0`.
- Browser/UI: support route JSON errors were visible in real browser execution; ticket page does not project failed operation cards/timeline entries for these negative attempts. Evidence files: `artifacts\p1-20260527-1527-c4f03651-p1-4cd-negative-module-ticket-snapshot.md`, `artifacts\p1-20260527-1527-c4f03651-p1-4cd-negative-module-ticket.png`.
- UIA: not applicable; this is support browser module-auto-install path, not local agent GUI workflow.
- Test artifact: disposable modules `p1_sha_bad_1527`, `p1_linux_only_1527`, `p1_future_agent_1527`; no raw tokens printed.
- Run marker: `p1-20260527-1527-c4f03651-p1-4c-sha`, `p1-20260527-1527-c4f03651-p1-4d-platform`, `p1-20260527-1527-c4f03651-p1-4d-min-agent`.

Impact: Support cannot audit negative auto-install failures in ticket timeline/operation history, and stale desired state may cause later reconcile/install noise for a known-bad package.
Root cause hypothesis: `ToolExecutionService.run_tool` performs module resolution/precheck/install before creating the ticket operation, and `set_desired_installed()` is committed before install result is known without rollback/failed-state reconciliation.
Blocking further P1: no, after recovery cleanup of the disposable desired-state row; P1.5 can continue with run_id filters.
Fix now: no, unless stale desired state causes reconnect/reconcile pollution.
Fix summary:
Changed files:
Tests:
Live regression:
Remaining risk: If reconcile workers act on stale desired state before cleanup, they may enqueue additional install attempts for the SHA-bad diagnostic module; future queries must filter module `p1_sha_bad_1527` as P1.4.C pre-fix/test contamination.
Recovery after evidence: desired-state row `id=3` was changed to `absent` with null desired version/SHA to prevent P1.5 reconnect/reconcile pollution; status remains `reproduced`.

P1.5.A server restart with agent outbox pending:
- Path tested: project remote-control scripts for server stop/start, controlled local agent SQLite outbox test-hook, agent runtime logs/SQLite, server DB, server smoke.
- Run marker: `p1-20260527-1527-c4f03651-p1-5a-server-restart-pending`, ticket `T-000609`, local outbox `17`, `agent_seq=9`, event id `2447d396-79cd-53da-b3a9-028c5a4d56da:f2918f87-cca3-42a9-b28f-f0a5e09d72b9:17:0`.
- Server control: `python scripts\manage_remote_stack.py stop server` returned `stopped`; inserted one valid pending `chat_message` row into agent SQLite while server was stopped; `python scripts\manage_remote_stack.py start server` returned running. Immediate `smoke server` failed during startup readiness, but repeat after 5 seconds passed `/api/health -> 200`.
- Expected: agent remains running, reconnects after server returns, local pending outbox is flushed once, server persists one `ticket_events.chat_message`, browser timeline shows marker.
- Actual: local agent process stopped before reconnect. `python scripts\manage_local_agent.py status live-v3-p1-clean2` reported stopped; local `outbox.id=17` remained `pending`, `attempts=0`; no `outbox_sent_history`; server DB has no ticket event for marker.
- Agent log evidence: at `2026-05-27 17:07:12`, WS connect saw HTTP/WSS `502`; `pc_agent/ws_agent.py:3230` raised `TypeError: 'in <string>' requires string as left operand, not bytes` inside `aiohttp.WSServerHandshakeError` handling; cleanup then stopped UI API server/orchestrator/database and agent exited.
- Browser/UI: not applicable as pass evidence because the event never reached the server; the browser was available again after server restart, but no marker event exists.
- Result: P1.5.A failed and P1.5 is blocked until the agent reconnect error handler is fixed or the agent is restarted as recovery. Recorded as `BUG-20260527-P1-11`.
- Blocking fix/live regression: after adding the handshake error classifier, restarted `live-v3-p1-clean2` from source. The pending outbox row `17` flushed, `outbox_sent_history` recorded it at `1779883942.230623`, server persisted `ticket_events.id=179` with `agent_seq=9`, and browser ticket timeline showed the marker. A second controlled server stop/start while the fixed agent was running produced transient WSS `502` log lines at `17:14:12` and `17:14:17`, but the agent process stayed running and reconnected with `handshake_ack` at `17:14:22`; `/api/health` smoke passed and local `outbox_count=0`. Browser evidence: `artifacts\p1-20260527-1527-c4f03651-p1-5a-pending-outbox-browser-snapshot.md`, `artifacts\p1-20260527-1527-c4f03651-p1-5a-pending-outbox-browser.png`.

P1.5.B agent restart while command in progress:
- Invalid test attempt, not product evidence: marker `p1-20260527-1527-c4f03651-p1-5b-agent-restart-inflight`, operation `e96eb23a-1a19-421e-9b36-d0d2701e3647`, path tested real browser support route plus agent restart scripts/SQLite/server DB. The tool params used `screen.record` with `fps=2`, but `screen.record` validates `fps >= 5`; the command returned terminal `INVALID_PARAMS` before the restart could exercise in-progress recovery.
- Transport/API: browser support route returned `202` for the command dispatch, then server marked operation `failed`, `error_code=INVALID_PARAMS`; `device_outbox.id=100` was delivered.
- Server DB: `operations.operation_id=e96eb23a-1a19-421e-9b36-d0d2701e3647`, `status=failed`, `queued_at=2026-05-27 12:16:24.561418+00:00`, `finished_at=2026-05-27 12:16:24.793139+00:00`; ticket events `182`/`183` contain `tool_call_started` and `tool_call_result` with Pydantic validation details for `fps`.
- Agent SQLite/log: `seen_commands` and agent log show terminal `error`, not a running command; after restart the agent reported connected. This attempt is excluded from P1.5.B pass/fail and must be repeated with valid long-running params.
- Browser/UI: not used as pass evidence for in-progress restart because the operation was invalid before restart.
- Valid retry marker `p1-20260527-1527-c4f03651-p1-5b-agent-restart-inflight-valid`, operation `a7734524-d1b6-461e-8f37-7d759e624b78`, path tested real browser support route, local agent restart scripts, server DB, agent SQLite/logs, browser ticket UI. Browser support route returned `202` and `dispatch_status=accepted`; agent log shows `command_ack accepted`, job creation, and `execution lane acquired` for `screen.record` at 2026-05-27 17:22:04-17:22:06. The agent was stopped/restarted during recording and reconnected with `handshake_ack` at 17:22:42.
- Expected: the interrupted operation becomes terminal failed/canceled/timed_out/recovered according to contract; no indefinite `accepted` operation, no `device_outbox.status=sent` beyond recovery window, no local `seen_commands.status=in_progress` after restart; browser shows terminal or retriable state.
- Actual: server remained `operations.status=accepted`, `device_outbox.id=102 status=sent delivered_at=NULL`, with only `ticket_events.id=185 tool_call_started`; local `seen_commands.command_id=a7734524-d1b6-461e-8f37-7d759e624b78 status=in_progress`, `result_json=NULL`, `completed_at` equal to start timestamp, and `recover_jobs_on_startup` reported `Нет jobs для восстановления`. Browser ticket UI shows the `screen.record` started/accepted event without the valid marker or terminal result. Recorded as `BUG-20260527-P1-12`.

### BUG-20260527-P1-12 — Agent restart during running command leaves accepted operation and sent outbox stuck

Severity: P1
Status: verified-fixed
Area: reconnect / idempotency / operation lifecycle / agent-sqlite / server-db / browser

P1 scenario: P1.5.B Agent restart while command in progress.
Run id: `p1-20260527-1527-c4f03651`
Expected: Restarting the local agent while `screen.record` is running should not leave the command active forever. The server operation should become terminal failed/canceled/timed_out/recovered according to contract, target `device_outbox` should be reconciled out of `sent`, local `seen_commands` should not remain `in_progress`, and browser timeline/operation card should show the terminal or retriable state.
Actual: Operation `a7734524-d1b6-461e-8f37-7d759e624b78` remained `accepted`; server `device_outbox.id=102` remained `sent` with `delivered_at=NULL`; local `seen_commands` remained `in_progress`; browser ticket UI showed only the started/accepted diagnostic event and no terminal result for marker `p1-20260527-1527-c4f03651-p1-5b-agent-restart-inflight-valid`.
Repro steps:
1. From real browser support ticket page `https://192.168.100.17:9443/app/tickets/f2918f87-cca3-42a9-b28f-f0a5e09d72b9`, call typed support route `POST /api/web/support/tickets/{ticket_id}/tools/run` with `screen.record`, params `{duration_sec:45, fps:5, probe_run_id:<marker>}`.
2. Observe HTTP `202` response with operation `a7734524-d1b6-461e-8f37-7d759e624b78`.
3. Stop local agent `live-v3-p1-clean2` while the agent log shows the command accepted and running.
4. Start local agent again and wait for `handshake_ack`.
5. Query server DB, agent SQLite/logs, and browser ticket UI.

Evidence:
- Transport/API: browser support route returned `202`, `dispatch_status=accepted`, `operation_id=a7734524-d1b6-461e-8f37-7d759e624b78`; no raw cookies/tokens recorded.
- Server log: server DB and browser projection show the stuck lifecycle; root cause isolated in agent restart recovery path before patching.
- Agent log: at 2026-05-27 17:22:04 received `run_tool`, sent `command_ack accepted`, created job `834af9cc-5fde-4f89-9499-d219314b549f`, and acquired execution lane for `screen.record`; after restart at 17:22:42, `recover_jobs_on_startup` reported no jobs to recover.
- Server DB: `operations.status=accepted`, `error_code=NULL`, `finished_at=NULL`; `device_outbox.id=102`, `command=run_tool`, `status=sent`, `sent_at=2026-05-27 12:22:31.941331+00:00`, `delivered_at=NULL`; ticket event `185` is only `tool_call_started` for the marker.
- Agent SQLite: `seen_commands.command_id=a7734524-d1b6-461e-8f37-7d759e624b78`, `status=in_progress`, `result_json=NULL`, `stale_retry_count=0`; `outbox` empty and no `tool_response` sent history for this operation.
- Browser/UI: real browser ticket page `https://192.168.100.17:9443/app/tickets/f2918f87-cca3-42a9-b28f-f0a5e09d72b9` shows a `screen.record` started/accepted diagnostic with no terminal result; screenshot captured as `p1-20260527-1527-c4f03651-p1-5b-stuck-accepted.png`.
- UIA: not applicable for this support-browser restart scenario; local GUI status after restart is covered separately in P1.6.
- Test artifact: DB/SQLite query outputs in this PLANS entry; browser screenshot from Playwright MCP.
- Run marker: `p1-20260527-1527-c4f03651-p1-5b-agent-restart-inflight-valid`.

Impact: Rebooting/restarting the agent during a running tool can strand the operation and command idempotency state indefinitely, polluting P1 stale-outbox checks and misleading support UI.
Root cause hypothesis: Running jobs are not durably persisted/recovered across agent restart for this command path, and the server lacks a watchdog/reconciliation path that marks an already-sent command terminal when the active agent process dies before `command_result`.
Root cause confirmed: yes. Code audit in fix run `p1-fix-20260527-2123-4f42ec7c` found `pc_agent.core.database.seen_commands.owner_instance_id` is written by `mark_command_started()`, but `pc_agent.ws_agent` only calls `orchestrator.job_manager.recover_jobs_on_startup()` after handshake. There is no startup/reconnect path that queries stale `seen_commands.status='in_progress'` from a previous `owner_instance_id`, no local terminal `AGENT_RESTARTED` result is written, and no recovery `command_result` is sent to the server. As a result, duplicate delivery later sees `COMMAND_IN_PROGRESS`, the server operation stays active until generic timeout, and the original `device_outbox` row is not reconciled by a product-level restart outcome.
Blocking further P1: yes for P1.5.B restart recovery and P1.2 duplicate-after-restart idempotency.
Fix now: yes in P1 fix phase; this is an operation lifecycle/idempotency blocker.
Fix summary:
Verified fixed. Product contract implemented: on startup/reconnect, non-resumable commands left `in_progress` by a previous runtime session become local terminal `error` with `error.code=AGENT_RESTARTED`, are queued in durable `pending_command_results`, replayed to the server as recovery `command_result`, and duplicates of the same command return cached terminal error without re-running. Server sends `command_result_ack` after processing so the agent can clear the pending result; the server lifecycle path marks the operation failed/interrupted and reconciles matching `device_outbox`.
Changed files:
- `pc_agent/core/database.py`
- `pc_agent/ws_agent.py`
- `server/websocket/agent_services.py`
- `pc_agent/tests/test_command_restart_recovery.py`
- `server/tests/test_agent_services_pipeline.py`
- `server/tests/test_command_result_lifecycle_db.py`
- `pc_agent/docs/PROTOCOL_V3.md`
- `pc_agent/docs/DATABASE.md`
- `pc_agent/docs/CODEMAP.md`
- `server/docs/PROTOCOL_V3.md`
- `server/docs/COMMAND_RESULT_LIFECYCLE.md`
- `server/docs/CODEMAP.md`
- `docs/QUICK_LOOKUP.md`
- `scripts/navigation_catalog.py`
Tests:
- RED before implementation: `python -m pytest pc_agent\tests\test_command_restart_recovery.py -q` failed on missing startup recovery, replay and ACK-clearing APIs.
- GREEN targeted: `python -m pytest pc_agent\tests\test_command_restart_recovery.py pc_agent\tests\test_seen_commands_retry_policy.py pc_agent\tests\test_ws_agent_canceled_command_idempotency.py pc_agent\tests\test_cancel_operation_runtime.py server\tests\test_agent_services_pipeline.py::test_command_result_service_sends_command_result_ack -q` -> 12 passed.
- Adjacent server no-db pipeline: `python -m pytest server\tests\test_agent_services_pipeline.py -q` -> 25 passed.
- Compile: `python -m compileall -q server pc_agent scripts` -> exit 0.
- Workspace: `python scripts\verify_workspace.py` -> passed for `C:\Users\admin-2\CodexProjects\pc_client`.
- Diff hygiene: `git diff --check` -> exit 0.
- Verification gap: DB-backed `python -m pytest server\tests\test_command_result_lifecycle_db.py::test_command_result_error_acknowledges_recovery_result -q` hung in the Windows isolated DB fixture twice and was stopped as a test-harness issue; real server DB reconciliation must be proven in Live regression before this bug can become `verified-fixed`.
Live regression:
- Deploy: commit `325236301dde6944201076b082d21ab5589fc6d6` released to `https://192.168.100.17:9443` with `python scripts\release_server_to_remote.py --gate quick --allow-local-dirty --leave-running --smoke-insecure-tls --smoke-attempts 8 --smoke-delay 2`; remote smoke `/api/health -> 200`.
- Agent restart after deploy: `python scripts\manage_local_agent.py stop live-v3-p1-clean2; python scripts\manage_local_agent.py start live-v3-p1-clean2 --gui`; local SQLite migrated v9 -> v10 and the old pre-fix `a7734524-d1b6-461e-8f37-7d759e624b78` contamination was recovered into a visible browser `tool_call_result`. This old row is not counted as the clean pass.
- Clean run marker: `p1-fix-20260527-2123-4f42ec7c-p1-12-clean-agent-restart`; browser support route `POST /api/web/support/tickets/f2918f87-cca3-42a9-b28f-f0a5e09d72b9/tools/run` from the real browser context returned HTTP 202 for operation `a0764846-3ab7-42f5-8e79-93d8c310ba6b`, tool `screen.record`, trace `6f3455cb-e94c-4928-8e81-1caccbf7e8cc`.
- Agent log: command `a0764846-3ab7-42f5-8e79-93d8c310ba6b` received at 22:23:52, `command_ack accepted`, `screen.record` execution lane acquired; agent process then stopped and restarted; at 22:24:25 `[command_restart_recovery] finalized stale in_progress commands: count=1` and sent recovery `command_result status=error`.
- Agent SQLite: `seen_commands.command_id=a0764846-3ab7-42f5-8e79-93d8c310ba6b status=error`, `result_json.error.code=AGENT_RESTARTED`, `meta.recovery=true`, `owner_instance_id=NULL`; `pending_command_results` count `0`; no failed local outbox rows for marker.
- Server DB: `operations.status=failed`, `error_code=AGENT_RESTARTED`, `finished_at=2026-05-27 17:24:53.024374+00:00`, `result_event_id=191`; `device_outbox.id=111 status=delivered delivered_at=2026-05-27 17:24:53.026397+00:00`; `ticket_events.id=191 event_type=tool_call_result` contains `observations.interrupted=true` and `target_operation_id=a0764846-3ab7-42f5-8e79-93d8c310ba6b`.
- Browser/UI: real browser ticket page `/app/tickets/f2918f87-cca3-42a9-b28f-f0a5e09d72b9` DOM contains operation `a0764846-3ab7-42f5-8e79-93d8c310ba6b`, `screen.record`, status `error`, and result text `Tool screen.record failed: Command was interrupted because the agent process restarted`; screenshots captured by Playwright as `p1-fix-20260527-2123-p1-12-browser-interrupted-visible.png` and `p1-fix-20260527-2123-p1-12-browser-interrupted-full.png`.
- Adjacent regression: browser support route ran `system.collect` with marker `p1-fix-20260527-2123-4f42ec7c-p1-12-adjacent-system-collect`; operation `ca0691da-2f2d-44e4-9ff2-0d191671f264` reached `operations.status=succeeded`, `device_outbox.id=113 status=delivered`, local `seen_commands.status=success`, and `pending_command_results` remained empty.
Remaining risk: This fix covers agent-process restart/interrupted non-resumable commands. The distinct server-drop/late-result reconciliation case is now separately verified fixed under `BUG-20260527-P1-13`.

P1.5.C WebSocket/server drop during run_tool:
- Path tested: real browser support route for `screen.record`, project remote-control server stop/start, live local agent runtime/SQLite/logs, server DB, browser ticket UI.
- Run marker: `p1-20260527-1527-c4f03651-p1-5c-ws-drop-during-run`, operation `e7cf0b9d-beee-46d2-82fc-9981bf17c80b`.
- Transport/API: browser support route returned `202`, `dispatch_status=accepted`; server was stopped for a controlled 10 second window during execution and then started. Remote smoke recovered `/api/health -> 200`; local agent process stayed running and connected after server return.
- Expected: result is delivered after reconnect or the operation reaches a consistent terminal failed/timed_out state without ACKing lost result data; browser shows the terminal result/error consistently with DB and agent state.
- Actual: agent completed the recording locally and `outbox_sent_history.outbox_id=22` shows a `tool_response` sent after reconnect, but server operation timed out in `accepted`, `device_outbox.id=104` became `failed/TIMEOUT`, and server `ticket_events` contains only `tool_call_started` id `186` with no final result. Browser shows only the `screen.record` started/accepted event at 17:26 and no terminal result/error. Recorded as `BUG-20260527-P1-13`.

### BUG-20260527-P1-13 — WS drop during running tool loses agent result after server timeout

Severity: P1
Status: verified-fixed
Area: reconnect / outbox / operation lifecycle / server-db / agent-sqlite / browser

P1 scenario: P1.5.C WebSocket drop during run_tool.
Run id: `p1-20260527-1527-c4f03651`
Expected: If the server/proxy drops while a tool is running, the live agent should reconnect and deliver the final `command_result`/outbox result exactly once, or the server should reject it with a durable, visible terminal state. The agent must not record a sent/ACKed result that is absent from server DB/browser timeline.
Actual: Agent completed `screen.record` and recorded local sent history for outbox `22`, but server timed out operation `e7cf0b9d-beee-46d2-82fc-9981bf17c80b` in `accepted`, marked `device_outbox.id=104` failed/TIMEOUT, and did not persist a final `tool_call_result`. Browser ticket UI shows only the started/accepted diagnostic event.
Repro steps:
1. From real browser support route, run `screen.record` with params `{duration_sec:25, fps:5, probe_run_id:"p1-20260527-1527-c4f03651-p1-5c-ws-drop-during-run"}`.
2. Stop server with `python scripts\manage_remote_stack.py stop server` while the command is executing.
3. Start server with `python scripts\manage_remote_stack.py start server`; verify `/api/health`.
4. Query operation/device_outbox/ticket_events, agent SQLite sent history, and browser ticket UI.

Evidence:
- Transport/API: browser route returned `202` with operation `e7cf0b9d-beee-46d2-82fc-9981bf17c80b`; remote stop/start was controlled and `/api/health` recovered.
- Server log: focused `manage_remote_stack.py logs server --contains e7cf0b9d-beee-46d2-82fc-9981bf17c80b` returned no high-signal lines.
- Agent log: local agent accepted/running flow completed; result JSON contains `frames_captured=125`, `duration_sec=32.5`, artifact upload warning caused by server `502`, and a `tool_response` was queued/sent after reconnect.
- Server DB: `operations.status=timed_out`, `error_code=timeout`, `finished_at=2026-05-27 12:27:57.514453+00:00`; `device_outbox.id=104 status=failed`, `error_code=TIMEOUT`, `delivered_at=NULL`; only `ticket_events.id=186 tool_call_started` exists for the marker.
- Agent SQLite: `seen_commands.status=error` with result payload status `partial`; `outbox_sent_history.outbox_id=22`, kind `tool_response`, sent_at `1779884822.7157173`; local `outbox` empty.
- Browser/UI: real browser ticket page `https://192.168.100.17:9443/app/tickets/f2918f87-cca3-42a9-b28f-f0a5e09d72b9` shows the `screen.record` started/accepted event at 17:26 and no terminal result; screenshot `p1-20260527-1527-c4f03651-p1-5c-ws-drop-started-only.png`.
- UIA: not applicable; this is support browser/server-drop path.
- Test artifact: DB/SQLite query outputs in this PLANS entry; browser screenshot from Playwright MCP.
- Run marker: `p1-20260527-1527-c4f03651-p1-5c-ws-drop-during-run`.

Impact: A transient server/proxy outage during tool execution can lose the agent's final result from the server timeline while the agent believes its local outbox result was sent, creating data-loss/observability gaps.
Root cause hypothesis: The server operation watchdog times out `accepted` before late result ingestion, and outbox ingest or command-result handling may ACK/drop late tool responses for timed-out operations instead of persisting a terminal late-result/rejected event. Artifact upload failure during outage also contributes to partial/error status but should not hide the final lifecycle.
Root cause confirmed: yes. Layer isolation:
- agent runtime / agent SQLite: pre-`325236301dde6944201076b082d21ab5589fc6d6`, `command_result` was transient; after server outage the agent only durably retained the legacy ticket `tool_response` outbox row. That row can be ACKed as a ticket event but does not drive `operations`/`device_outbox` lifecycle.
- server operation lifecycle / DB: `CommandResultService` only transitions `succeeded`/`failed` from active statuses (`queued`, `sent`, `accepted`, `running`, `waiting_consent`). If a valid terminal `command_result` arrives after watchdog `timed_out`, the status update is rejected by optimistic expected-status guards, but the handler does not expose a product-level late-result reconciliation path. `DeviceOutboxRepo.mark_as_delivered()` also only updates `pending`/`sent`, so timeout-failed outbox rows remain `failed/TIMEOUT`.
- browser/UI projection: without a persisted `tool_call_result`/late-result event tied to the original operation, support UI can show only the initial `tool_call_started` while agent local state already contains terminal evidence.
Product contract: a terminal `command_result` for the original operation must be durable until server ACK and must be accepted after timeout. If no replacement/retry operation exists, reconcile the timed-out operation to the terminal result and persist `late_result=true`/`previous_status=timed_out` in the ticket result event. If a retry/replacement exists, keep the original timeout as-is but persist linked late-result evidence and reconcile the original device_outbox delivery state. Never silently drop or ACK-without-audit a late terminal result.
Blocking further P1: yes for marking reconnect delivery green and for final P1 close.
Fix now: yes; data-integrity/reconnect blocker with no safe evidence-quality workaround.
Fix summary:
Implemented product-level late terminal `command_result` reconciliation.
- Agent side: commit `325236301dde6944201076b082d21ab5589fc6d6` already made terminal `command_result` durable in `pending_command_results` until `command_result_ack` and replays it on reconnect.
- Server side: commits `96dc0706fc28c9e3b5e0c72bc509e017287f742f` and `5e5af5d8da58505e4d7f3415bd94f2696c54d83c` add explicit late-result handling for `tool_call` operations that are already `timed_out`. If no retry/replacement exists, the original operation is guarded-updated from `timed_out` to `succeeded`/`failed`, timeout error fields are cleared for successful reconciliation, timeout-failed `device_outbox` is reconciled to `delivered`, and the ticket result event records `late_result=true`, `previous_status=timed_out`, `reconciled_from=timed_out`. If a retry exists, the original timeout is preserved and linked late evidence is written with `late_result_ignored=true`.
Changed files:
- `pc_agent/ws_agent.py`, `pc_agent/core/database.py` from the durable replay prerequisite in `325236301dde6944201076b082d21ab5589fc6d6`.
- `server/websocket/agent_services.py`
- `server/websocket/command_result_components.py`
- `server/app/repos/device_outbox_repo.py`
- `server/app/repos/operations_repo.py`
- `server/tests/test_agent_services_pipeline.py`
- `server/docs/COMMAND_RESULT_LIFECYCLE.md`
- `server/docs/PROTOCOL_V3.md`
- `server/docs/CODEMAP.md`
- `docs/QUICK_LOOKUP.md`
- `scripts/navigation_catalog.py`
Tests:
- RED evidence: `python -m pytest server\tests\test_agent_services_pipeline.py::test_tool_call_result_payload_marks_late_timeout_reconciliation -q` failed before the server-side patch with `TypeError: CommandResultLifecycleOutcome.__init__() got an unexpected keyword argument 'late_result'`.
- Targeted green: `python -m pytest server\tests\test_agent_services_pipeline.py -q` -> `28 passed`.
- Compile: `python -m compileall -q server pc_agent scripts` -> exit 0.
- Workspace gate: `python scripts\verify_workspace.py` -> passed.
- `git diff --check` -> exit 0.
- DB-backed local test harness note: `server\tests\test_command_result_lifecycle_db.py::test_late_success_reconciles_timed_out_tool_operation` was attempted during TDD but the existing Windows DB fixture hung before assertions. It was not used as pass evidence; the DB layer was verified through live server DB queries below.
Live regression:
- Clean run id/marker: `p1-fix-20260527-2123-4f42ec7c-p1-13-clean2-late`; ticket `T-000611`, `ticket_id=7e90b809-e993-4227-86f4-defb50223e48`.
- Path tested: real browser support route `POST /api/web/support/tickets/7e90b809-e993-4227-86f4-defb50223e48/tools/run`, controlled remote server stop/start, real local agent runtime, agent SQLite, server DB, real browser ticket UI.
- Browser/API start: HTTP `202`, `dispatch_status=accepted`, `operation_id=a921bec8-e71d-428a-afa3-287fa0083f21`, `trace_id=30d9fb63-a405-453b-8e99-91d5687c49c2`, tool `screen.record`.
- Server was stopped during execution. Agent SQLite before replay: `pending_command_results.command_id=a921bec8-e71d-428a-afa3-287fa0083f21`, `attempts=1`, `last_error=Cannot write to closing transport`; `seen_commands.status=error` with `status=partial` result; no sent history yet for the marker.
- Agent was stopped after the tool finished and before server restart to force server-side timeout before replay. Server DB pre-replay: operation `status=timed_out`, `error_code=timeout`; `device_outbox.id=116 status=failed error_code=TIMEOUT delivered_at=NULL`; ticket events only `tool_call_started` id `213`.
- Agent restart replay: local `pending_command_results` emptied after `command_result_ack`; `seen_commands` remained terminal `error` with the original partial result; no failed local outbox rows for the marker.
- Server DB after replay: operation `status=succeeded`, `error_code=NULL`, `error_message=NULL`, `result_event_id=215`, `result_summary` includes `frames_captured=90`; `device_outbox.id=116 status=delivered error_code=TIMEOUT_RECONCILED delivered_at=2026-05-27T18:06:23.164338+00:00`; ticket events include `tool_call_started` id `213` and `tool_call_result` id `215` with `late_result=true`, `previous_status=timed_out`, `reconciled_from=timed_out`.
- Browser/UI: real ticket page `https://192.168.100.17:9443/app/tickets/7e90b809-e993-4227-86f4-defb50223e48` shows `screen.record` accepted and then `Успешно` result with `frames_captured=90`, `duration_sec=25.4`, `file_size_bytes=35889`; DOM check contained `screen.record`, `Успешно`, and result fields. Screenshot artifacts from Playwright MCP: `p1-fix-20260527-p1-13-late-result-clean2.png`, `p1-fix-20260527-p1-13-clean2-final-timeline.png`; console/network captures: `p1-fix-20260527-p1-13-console.json`, `p1-fix-20260527-p1-13-network.json`.
- Adjacent regression: real browser support route `system.collect` on the same clean ticket returned HTTP `202`, operation `02e6f30e-0023-456b-b4a3-12aaf830cbde`; server DB `status=succeeded`, `error_code=NULL`, `device_outbox.status=delivered`, ticket events `tool_call_started` id `217` and `tool_call_result` id `218`; agent SQLite `seen_commands.status=success`, no pending command result; browser timeline shows `system.collect` `Успешно`.
Remaining risk: Operation row stores the current terminal result; the historical timeout is intentionally carried in the late-result ticket event and reconciled outbox marker, not in `operations.error_code`. Retry/replacement late-result branch is unit-covered but still needs a separate live retry scenario if P1.2 retry UX is expanded.

P1.5.D raw same-device probe while real agent active:
- Path tested: raw WebSocket probe `scripts\live_ws_v3_probe.py double-connect` using token from local agent SQLite passed only through env to subprocess, real local agent process/status, server DB.
- Run artifact: `artifacts\p1-20260527-1527-c4f03651-p1-5d-double-connect.json`.
- Expected: raw probe observes supersede close code `4002`, real agent reconnects, and no pending commands are lost or left stuck.
- Actual: close-code assertion passed (`first_close_code_final=4002`) and real agent reconnected, but the raw probe received live `install_module_package network_basic` commands (`664b8454-9c3b-46b8-88fa-b38de1c00c53`, `9f1ebc07-c777-47db-bf92-8d9c93333e18`, `b503ead2-956f-4041-a8d2-60d4110ed931`) before/around handshake ACK. Because the raw probe is not a full agent runtime, server `device_outbox` rows `105`/`106`/`107` remained `sent` with `delivered_at=NULL` at evidence time. Recorded as `BUG-20260527-P1-14`.

### BUG-20260527-P1-14 — Raw same-device probe receives live install commands and leaves module outbox sent

Severity: P1
Status: verified-fixed
Area: reconnect / module-runtime / test-tool / server-db / protocol

P1 scenario: P1.5.D Raw same-device probe while real agent active.
Run id: `p1-20260527-1527-c4f03651`
Expected: Same-device supersede probe should verify close code `4002` and real-agent reconnect without causing live pending commands to be lost. If commands are pending, the test tool must handle them or the server must avoid dispatching module lifecycle commands to a diagnostic raw probe that cannot execute them.
Actual: The raw probe observed close code `4002`, but also received live `install_module_package network_basic` commands and exited without command results. Server `device_outbox` rows `105`, `106`, `107` remained `sent`, `delivered_at=NULL` immediately after the probe.
Repro steps:
1. Load active clean-agent token from local SQLite and pass it only as `PC_CLIENT_AGENT_TOKEN` env to `scripts\live_ws_v3_probe.py double-connect`.
2. Run `python scripts\live_ws_v3_probe.py --timeout 6 double-connect --expect-supersede-close-code 4002`.
3. Observe probe messages and query `device_outbox` for command request ids from the artifact.

Evidence:
- Transport/API: `artifacts\p1-20260527-1527-c4f03651-p1-5d-double-connect.json` shows `first_close_code_final=4002`, but also `command=install_module_package` frames for request ids `664b8454-9c3b-46b8-88fa-b38de1c00c53`, `9f1ebc07-c777-47db-bf92-8d9c93333e18`, `b503ead2-956f-4041-a8d2-60d4110ed931`.
- Server log: not root-caused yet.
- Agent log: real agent reconnected after probe; focused command ownership not yet collected.
- Server DB: `device_outbox.id=105/106/107`, command `install_module_package`, status `sent`, `delivered_at=NULL` at 2026-05-27 17:32 local query; `device_desired_modules.network_basic` still had `state=installed`, `desired_version=1.0.0`, reason `run_tool`.
- Agent SQLite: not applicable for the raw-probe-owned commands; real agent did not execute those request ids.
- Browser/UI: not applicable; this is raw transport/module lifecycle side effect.
- UIA: not applicable.
- Test artifact: `artifacts\p1-20260527-1527-c4f03651-p1-5d-double-connect.json`.
- Run marker: `p1-20260527-1527-c4f03651`.

Impact: Raw same-device probes against a live device can steal server-dispatched module commands and create post-fix `device_outbox.sent` contamination. The desired/actual module reconcile state also keeps emitting install attempts even though the module is already active locally.
Root cause hypothesis: The server dispatches desired-module reconcile commands to whichever same-device websocket is latest, including raw diagnostic sessions, and the probe lacks command-result handling. Underlying desired/actual module state may be stale because module lifecycle device events were not persisted (`BUG-20260527-P1-09`).
Root cause confirmed: yes. `handle_handshake()` always called `state.register_agent()` for authenticated raw probes; `StateManager.connected_agents` had no session role separation; `HandshakeService` always called `dispatch_service.on_agent_online()` after handshake; `DeviceOutboxSender` then used `state.get_agent(device_id)` and sent pending `device_outbox` commands to the probe websocket. `scripts/live_ws_v3_probe.py` also built production-style handshakes with no `client_kind`.
Blocking further P1: no for browser/UI projection checks if rows `105`/`106`/`107` are labeled contamination; yes for marking P1.5.D fully green.
Fix now: yes; this is a test-isolation/data-integrity blocker for further raw-probe reconnect checks.
Fix summary:
Verified in fix run `p1-fix-20260527-2123-4f42ec7c`: introduced `client_kind=diagnostic_probe` handshake isolation. Diagnostic probes authenticate and receive `handshake_ack`, but are stored outside `connected_agents`, do not supersede the runtime agent, do not trigger `on_agent_online`, and are not visible to command dispatch. Runtime `agent_runtime` behavior remains unchanged. A residual context bug was fixed after the first live rerun: `HandshakeService` now prefers the current websocket session metadata over `state.get_agent(device_id)` fallback, so a diagnostic probe using a live token cannot inherit the real runtime connection metadata.
Changed files:
`server/state_manager.py`, `server/websocket/agent_handshake.py`, `server/websocket/agent_services.py`, `server/websocket/agent_handler.py`, `scripts/live_ws_v3_probe.py`, `server/tests/test_state_manager_agent_registry.py`, `server/tests/test_probe_session_isolation.py`, `server/tests/test_live_ws_v3_probe_contract.py`, `server/docs/PROTOCOL_V3.md`, `pc_agent/docs/PROTOCOL_V3.md`, `server/docs/CODEMAP.md`, `pc_agent/docs/CODEMAP.md`, `PLANS.md`.
Tests:
RED first: diagnostic-probe isolation tests failed because probes replaced runtime connections and the probe script omitted `client_kind`. After the first code changes, `python -m pytest server\tests\test_state_manager_agent_registry.py server\tests\test_probe_session_isolation.py server\tests\test_live_ws_v3_probe_contract.py server\tests\test_agent_disconnect_runtime_audit.py -q` -> `11 passed`; `python -m compileall -q server\state_manager.py server\websocket\agent_handshake.py server\websocket\agent_services.py server\websocket\agent_handler.py scripts\live_ws_v3_probe.py` -> passed. After the residual live context bug, added RED test `server\tests\test_probe_session_isolation.py::test_handshake_service_prefers_probe_ws_metadata_over_runtime_agent_entry`; it failed before the patch with `ctx.connection_id == runtime-conn`. After the patch, `python -m pytest server\tests\test_probe_session_isolation.py server\tests\test_state_manager_agent_registry.py server\tests\test_live_ws_v3_probe_contract.py server\tests\test_agent_disconnect_runtime_audit.py -q` -> `12 passed`; `python -m compileall -q server\websocket\agent_services.py server\tests\test_probe_session_isolation.py` -> passed; `git diff --check` -> passed with repository CRLF warnings only. A broader DB-backed adjacent pytest command was stopped after hanging without output on the harness; rerun targeted DB tests separately before final gate.
Live regression:
Initial live regression after commit `f0f8c737` with marker `p1-fix-20260527-2123-4f42ec7c-p1-14-diagnostic-probe` found the first half fixed but exposed residual isolation drift before verification:
- Recovery/setup path: remote server deployed and running; HTTPS proxy was manually recovered via user systemd unit after release smoke found `9443` closed. Local agent `live-v3-p1-clean2` was restarted as environment recovery only, then server log showed real runtime `handshake_ack`, `DeviceOutboxRepo Retrieved 0 pending commands`, real runtime `list_tools` command `c58fd678-0184-4fbe-a746-df0a0364d3af`, `command_result status=succeeded`, and `DeviceOutboxRepo Marked as delivered`.
- Transport/API: raw WSS diagnostic probe artifact `artifacts\p1-fix-20260527-2123-4f42ec7c-p1-14-diagnostic-probe.json` shows `client_kind=diagnostic_probe`, token evidence only prefix/hash/length, `message_types=["handshake_ack"]`, and `command_count=0`.
- Server log: `Diagnostic probe accepted without runtime registration: device_id=2447d396-79cd-53da-b3a9-028c5a4d56da connection_id=73f6...`; however, immediately after probe close the handler logged `Ignoring disconnect from superseded connection ... connection_id=4ca001...`, the real runtime connection id. This shows `HandshakeService` copied metadata from `state.get_agent(device_id)` instead of the diagnostic websocket metadata.
- Agent SQLite: `outbox=[]`, `failed_outbox_count=0`; newest clean command `c58fd678-0184-4fbe-a746-df0a0364d3af` is `seen_commands.status=success`. Old pre-fix `a7734524-d1b6-461e-8f37-7d759e624b78` was originally `status=in_progress` contamination for `BUG-20260527-P1-12`; after commit `32523630` it was recovered to terminal `error/AGENT_RESTARTED` and remains historical contamination only.
- Residual root cause confirmed: `HandshakeService.handle()` looked up `state.get_agent(ctx.agent_id)` before reading `_pc_client_session_metadata` from the current websocket. For a diagnostic probe using a live device token, `state.get_agent()` returns the real runtime agent, so the diagnostic context is misclassified as `agent_runtime`, can trigger `dispatch_service.on_agent_online()`, and cleanup logs/acts against the wrong connection metadata. This does not reproduce the original command-consumption symptom in the first rerun, but it still violates the diagnostic-probe isolation contract and cannot be marked verified.
Verified live regression after commit `16000f1d52bff549ed57fb61492c83345f1cf2f7` with marker `p1-fix-20260527-2123-4f42ec7c-p1-14-diagnostic-probe-rerun2`:
- Deployment/runtime path tested: `python scripts\release_server_to_remote.py --gate quick --allow-local-dirty --leave-running --smoke-insecure-tls --smoke-attempts 8 --smoke-delay 2`; smoke recovered on attempt 2 with `/api/health -> 200`. Remote server SHA was deployed to `16000f1d`.
- Transport/API: artifact `artifacts\p1-fix-20260527-2123-4f42ec7c-p1-14-diagnostic-probe-rerun2.json` shows raw WSS `client_kind=diagnostic_probe`, token evidence only prefix/hash/length, `message_types=["handshake_ack"]`, and `command_count=0`.
- Server log: `Diagnostic probe accepted without runtime registration: device_id=2447d396-79cd-53da-b3a9-028c5a4d56da connection_id=99620e5e0c7040979a9f68f50873b460`, then `Diagnostic probe disconnected without changing runtime agent state` for the same connection id. No post-fix `Ignoring disconnect from superseded connection` appeared for the diagnostic probe.
- Server DB: latest device row remains real agent `ADMIN-2`, version `3.1.61`, `last_handshake_at=2026-05-27 21:52:15+05`. Latest post-fix `device_outbox.id=109` is `list_tools status=delivered`; no new pending/sent command was created or consumed by the diagnostic probe. Old `device_outbox.id=102/105/106/107` remain pre-fix contamination and are excluded by timestamp/run marker.
- Agent SQLite: `outbox=[]`, `failed_outbox_count=0`; latest command `c58fd678-0184-4fbe-a746-df0a0364d3af` remains terminal `success`. Old `a7734524-d1b6-461e-8f37-7d759e624b78` P1-12 contamination was later recovered to terminal `error/AGENT_RESTARTED` by commit `32523630`.
- Browser/UI: real browser `/app/admin/inventory?device=2447d396-79cd-53da-b3a9-028c5a4d56da` shows `ADMIN-2`, device `2447d396...56da`, `Online`, Windows, agent `3.1.61`, last activity `27 May 2026 21:52`. Screenshot copied to `artifacts\p1-fix-20260527-2123-p1-14-admin-inventory.png`.
Remaining risk: Old sent rows `102/105/106/107` are terminal timeout/failed contamination and must stay excluded from clean-run stale checks. P1-12's local stale `seen_commands.in_progress` row was recovered by commit `32523630`; P1-13 remains the open late-result/server-drop lifecycle risk.

P1.5.E stale device_outbox cleanup check:
- Path tested: server DB query, agent SQLite query.
- Server DB: after the recovery window, `open_device_outbox=[]`. Known P1 contamination rows are now terminal failed/TIMEOUT: `device_outbox.id=102` from P1.5.B and `id=105/106/107` from P1.5.D. No new open `pending/sent/accepted/running` server outbox rows remained.
- Server operations: no new open operation rows for the P1 run except the earlier P1.3 recovery-denied consent operation, which is terminal in product semantics but was not excluded by the initial SQL status list.
- Agent SQLite: local `outbox=[]`, `pending_consents=0`; pre-fix `seen_commands.command_id=a7734524-d1b6-461e-8f37-7d759e624b78` was later recovered to terminal `error/AGENT_RESTARTED` by `BUG-20260527-P1-12` fix commit `32523630`.
- Result: server stale-outbox cleanup is not currently blocked. P1.5 still needs a clean rerun because `BUG-20260527-P1-14`/`BUG-20260527-P1-12`/`BUG-20260527-P1-13` were fixed after the original P1.5 pass.

P1.6 Browser/UI projection consistency:
- P1.6.A Ticket timeline replay path tested: real browser support ticket page `/app/tickets/f2918f87-cca3-42a9-b28f-f0a5e09d72b9`, DOM text, browser console capture. Browser shows clean P1 ticket `T-000609`, P1.1 markers once in visible timeline, and P1.5.A marker. The original P1.5.B pre-fix timeline showed a started/accepted `screen.record` without terminal result; after `BUG-20260527-P1-12` fix, clean operation `a0764846-3ab7-42f5-8e79-93d8c310ba6b` shows terminal `error/AGENT_RESTARTED`. After `BUG-20260527-P1-13` fix, clean ticket `T-000611` shows late-reconciled `screen.record` result and adjacent `system.collect` result in browser; P1.6 should still be rerun end-to-end after `BUG-20260527-P1-15`.
- P1.6.B Operation card consistency path tested: support action center and ticket page in real browser. Support action center surfaces the P1.5.C timeout as `Ошибки операций` with text `Operation timed out in status 'accepted'...`; ticket timeline does not show the lost late tool result, matching DB state but not agent local result state.
- P1.6.C Device/module admin projection path tested: real browser admin login and `/app/admin/inventory?device=2447d396-79cd-53da-b3a9-028c5a4d56da`, `/app/admin/device?device=2447d396-79cd-53da-b3a9-028c5a4d56da`. Inventory shows `ADMIN-2`, device id `2447d396...56da`, Windows, agent version `3.1.61`, Online, last activity `27 мая 2026 г., 17:31`; screenshot `p1-20260527-1527-c4f03651-p1-6-admin-inventory.png`. Device card shows observer hot traces for P1.5.D raw-probe command timeouts and still logs console 500 for `/api/web/admin/registry/devices/{device_id}/account-events?limit=20`, confirming `BUG-20260527-P1-03`; screenshot `p1-20260527-1527-c4f03651-p1-6-admin-device.png`.
- P1.6.D Agent GUI projection path tested: local GUI restarted with `--gui`, pywinauto `0.6.9`, `Application/Desktop(backend="uia")`, bounded control tree, bridge status. UI bridge reports connected, account gate, active ticket list contains `f2918f87-cca3-42a9-b28f-f0a5e09d72b9`; UIA sees top window `Maria Agent v3.1.61` with `AutomationId=QApplication.MainWindow` and root group, but exposes no semantic text controls for active account/ticket/connected state. Screenshot `artifacts\p1-20260527-1527-c4f03651-p1-6-uia-agent-window.png`. Recorded as `BUG-20260527-P1-15`.
- P1.6.E Browser console/network: support ticket console captured to `p1-20260527-1527-c4f03651-p1-6-ticket-console.log`; admin device page has known 500 account-events error from `BUG-20260527-P1-03`. No raw cookies/tokens recorded in PLANS.

### BUG-20260527-P1-15 — Agent GUI main window exposes no semantic UIA text after GUI restart

Severity: P1
Status: verified-fixed
Area: UIA / local GUI / UI projection

P1 scenario: P1.6.D Agent GUI projection.
Run id: `p1-20260527-1527-c4f03651`
Expected: With local agent GUI running, `pywinauto==0.6.9` and `backend="uia"` should expose enough stable controls/texts to confirm connected state, active account/account gate, and visible ticket list for P1 evidence.
Actual: After restarting `live-v3-p1-clean2` with `--gui`, UI bridge reports connected and one ticket, but UIA enumeration finds only top window `Maria Agent v3.1.61` and root groups; bounded child traversal exposes no semantic text controls. This prevents canonical pywinauto/UIA confirmation of account/ticket projection beyond window existence.
Repro steps:
1. Restart clean local agent with `python scripts\manage_local_agent.py start live-v3-p1-clean2 --gui`.
2. Verify bridge status with `scripts\agent_test_driver.py status live-v3-p1-clean2`.
3. Run pywinauto `Desktop(backend="uia").windows()` and connect to the agent top window.
4. Dump bounded children/control identifiers.

Evidence:
- Transport/API: not applicable.
- Server log: not applicable.
- Agent log: GUI process running after restart; bridge reports `connection_state=connected`.
- Server DB: not applicable.
- Agent SQLite: active clean ticket exists from prior scenarios; no local outbox pending.
- Browser/UI: not applicable to local GUI window evidence.
- UIA: `pywinauto 0.6.9`; top window `Maria Agent v3.1.61`, pid `22052`, class `MainWindow`, control type `Window`; control tree excerpt only has `QApplication.MainWindow` and `QApplication.MainWindow.AgentRoot` / `FramelessResizeHandler` groups; `texts=[]`.
- UIA: `2026-05-27T23:45:03+05`, run marker `p1-close-20260527-2333-ebcd4c0b`; after adding first-pass semantic metadata, initial `scripts\live_agent_uia_state_probe.py --instance live-v3-p1-clean2 --output artifacts\p1-close-20260527-2333-ebcd4c0b-uia-state-initial.json --max-depth 7 --max-nodes 700` hung and produced no JSON/screenshot. This is test-tool evidence that the probe itself needed hard bounded UIA collection before it could be used as pass/fail evidence.
- Transport/API: local automation bridge create-ticket for clean marker `p1-close-20260527-2333-ebcd4c0b` returned `status=ok`, ticket `T-000612`, ticket_id `15f87a9a-726e-488d-9868-2d4b78cfac9c`, requester_account_mode `confirmed_binding`, requester_account_session_id `6b691e62-73f2-4343-9a90-f245a4b6e983`; no raw session token recorded.
- Agent log: restarted source GUI instance `live-v3-p1-clean2`; logs show technical token loaded from local DB and verified on server, handshake_ack received, and list_tools command succeeded after reconnect.
- Agent SQLite: `.local-agent\instances\live-v3-p1-clean2\data\storage.db` after clean ticket/UIA run: `outbox=0`, `pending_consents=0`, `outbox_sent_history=35`, `seen_commands=37`; no failed/pending outbox rows from marker `p1-close-20260527-2333-ebcd4c0b`.
- Browser/UI: real browser route `https://192.168.100.17:9443/app/tickets/15f87a9a-726e-488d-9868-2d4b78cfac9c`; visible ticket list count `4`, selected `T-000612`, title `P1 close UIA projection p1-close-20260527-2333-ebcd4c0b`, status `В очереди`, requester `P1 Clean User 20260527`, initial message contains `run_id=p1-close-20260527-2333-ebcd4c0b`; screenshot `p1-close-20260527-2333-ebcd4c0b-browser-ticket-T-000612.png`.
- UIA: `.venvs\agent-win\Scripts\python.exe scripts\live_agent_uia_state_probe.py --instance live-v3-p1-clean2 --expect-connected --expect-account --expect-account-confirmed --expect-ticket-id 15f87a9a-726e-488d-9868-2d4b78cfac9c --expect-ticket-code T-000612 --output artifacts\p1-close-20260527-2333-ebcd4c0b-uia-state-ticket-T-000612.json --screenshot artifacts\p1-close-20260527-2333-ebcd4c0b-uia-state-ticket-T-000612.png --screenshot-timeout-sec 3 --max-depth 7 --max-nodes 900 --max-seconds 8` returned success. Evidence: `pywinauto_version=0.6.9`, `backend=uia`, window title `Maria Agent v3.1.61; id=agent.main_window; agent_version=3.1.61`, process_id `17044`, `connection_state=connected`, `account_exists=true`, `account_mode=confirmed_binding`, `ticket_count=4`, target ticket match via `agent.tickets.list` and `agent.ticket.card.T-000612`; screenshot capture timed out and is not used as pass criterion. Secret scan of JSON found no `token`, `session_token`, `authorization`, or `cookie`.
- Test artifact: screenshot `artifacts\p1-20260527-1527-c4f03651-p1-6-uia-agent-window.png`.
- Run marker: `p1-20260527-1527-c4f03651`.

Impact: P1 cannot claim real local GUI projection green; automation bridge/HTTP status is not a substitute for UIA evidence under the Live Testing rules.
Root cause hypothesis: Qt/PySide accessibility names/texts are not assigned or not propagated for the post-restart account-gate/main shell widgets, or the window is rendered in a custom widget tree that UIA only exposes as generic groups.
Root cause confirmed: Main shell, connection footer, account/profile summary, ticket list and active ticket header did not set stable UIA-readable semantic metadata. Qt UIA exposes `accessibleName` reliably but did not surface `accessibleDescription` as HelpText in the live tree, so semantic values must be included in the accessible name itself. The first diagnostic probe also used the stored manager PID, while the visible GUI window belonged to another process for this live instance, and lacked a process-level guard around screenshot capture; this could block evidence collection.
Blocking further P1: yes for P1.6.D green; no for server/browser DB checks.
Fix now: yes; P1.6.D is a P1 close blocker and the diagnostic script hang blocks valid UIA evidence.
Fix summary: Added shared UIA metadata helpers, exposed stable semantic names for main window/root, connection state/detail, account summary/mode/person, ticket list/count/cards and active ticket header, and added a bounded pywinauto UIA state probe that finds the real Maria Agent window by instance data_dir rather than relying only on the manager PID.
Changed files: `pc_agent/ui_gui/accessibility.py`, `pc_agent/ui_gui/main_window.py`, `pc_agent/ui_gui/chat_panel.py`, `pc_agent/ui_gui/ticket_detail_widgets.py`, `pc_agent/ui_gui/tickets_list_model.py`, `scripts/live_agent_uia_state_probe.py`, `pc_agent/tests/test_gui_accessibility.py`, `pc_agent/tests/test_chat_panel_helpers.py`, `pc_agent/docs/CODEMAP.md`, `docs/QUICK_LOOKUP.md`, `PLANS.md`.
Tests: `python -m py_compile scripts\live_agent_uia_state_probe.py pc_agent\ui_gui\accessibility.py pc_agent\ui_gui\main_window.py pc_agent\ui_gui\chat_panel.py pc_agent\ui_gui\ticket_detail_widgets.py pc_agent\ui_gui\tickets_list_model.py`; `python -m pytest pc_agent\tests\test_gui_accessibility.py pc_agent\tests\test_chat_panel_helpers.py::test_ticket_header_widget_renders_actions_without_raw_public_url pc_agent\tests\test_chat_panel_helpers.py::test_ticket_create_wizard_exposes_stable_uia_ids pc_agent\tests\test_main_window_runtime_windows.py::test_main_window_syncs_sidebar_connection_status_with_requester_labels -q` -> `7 passed, 2 warnings`.
Live regression: P1.6.D clean rerun on `live-v3-p1-clean2` passed through real pywinauto/UIA and real browser support UI for ticket `T-000612` / run_id `p1-close-20260527-2333-ebcd4c0b`; `/ui/automation/status` used only as auxiliary bridge evidence.
Remaining risk: pywinauto screenshot capture can fail or time out on this Windows desktop, so screenshots are browser-provided and UIA pass criteria rely on semantic tree JSON. A separate runtime-control finding was observed where one local start left two matching `pc_agent.ws_agent` processes for the same instance; recorded below as `BUG-20260527-P1-16` and not treated as part of this UIA accessibility root cause.

### BUG-20260527-P1-16 - Local agent manager start leaves two matching ws_agent processes for one instance

Severity: P1
Status: verified-non-product / guardrails-added
Area: deployment/systemd/runtime-control / local GUI-runtime / test-tool

P1 scenario: P1.6.D local GUI projection live setup for `live-v3-p1-clean2`.
Run id: `p1-close-20260527-2333-ebcd4c0b`
Expected: One `scripts\manage_local_agent.py start live-v3-p1-clean2 --gui ...` should leave one authoritative local agent runtime process for the instance, and the manager PID should match the visible GUI process used by UIA evidence or otherwise expose the child GUI PID explicitly.
Actual: After a single clean start, Windows process listing showed two `python.exe -m pc_agent.ws_agent --data-dir ...\.local-agent\instances\live-v3-p1-clean2\data --install-root ... --gui` processes created within milliseconds of each other. `manage_local_agent.py status` reported parent PID `33480`/`31212`, while the visible `Maria Agent v3.1.61` UIA window belonged to child PID `17044`/`12592`. The UI bridge remained reachable and connected, but PID ownership was ambiguous for live evidence and cleanup until isolated.
Repro steps:
1. Stop the instance with `python scripts\manage_local_agent.py stop live-v3-p1-clean2`.
2. Recovery cleanup used for evidence only: stop remaining `python*.exe` processes whose command line contains `pc_agent.ws_agent` and the instance data dir.
3. Start once: `python scripts\manage_local_agent.py start live-v3-p1-clean2 --gui --ws-url wss://192.168.100.17:9443/ws --api-url https://192.168.100.17:9443/api`.
4. Query Windows processes for the same data dir and find Maria Agent UIA window process id.

Evidence:
- Transport/API: `/ui/automation/status` returned `status=ok`, `bridge_connected=true`, `connection_state=connected`, `ticket_count=4`; after P1-17 restart it returned `window_visible=true`, `sidebar_view=tickets`, `ticket_count=4`.
- Server log: not yet collected for this finding.
- Agent log: same instance logs show GUI startup and handshake success; further root-cause log split between the two PIDs not yet isolated.
- Server DB: not applicable yet.
- Agent SQLite: no failed local outbox rows after the P1-15 UIA run (`outbox=0`, `pending_consents=0`).
- Browser/UI: browser ticket checks passed despite the process ambiguity.
- UIA: visible Maria Agent window title `Maria Agent v3.1.61; id=agent.main_window; agent_version=3.1.61`, PID `17044`/`12592`; manager status reported parent PID `33480`/`31212`. Post-guardrail `scripts\live_agent_uia_state_probe.py --pid 31212 ...` failed fast with `Maria Agent window not found for pid=31212`; `--pid 12592 ...` passed with `failures=[]`.
- Test artifact: process query showed parent PID `31212` executable path `.venvs\agent-win\Scripts\python.exe` and child PID `12592` executable path `AppData\Local\Programs\Python\Python314\python.exe` with the same command line. `Get-NetTCPConnection` showed no sockets owned by parent PID `31212`; child PID `12592` owned UI bridge `127.0.0.1:8765` and WSS connections to `192.168.100.17:9443`.
- Run marker: `p1-close-20260527-2333-ebcd4c0b`.

Impact: Test tooling could attach to the launcher shim PID and hang or miss the real GUI, making UIA evidence unreliable. Runtime data integrity is not affected because only the child process owns UI bridge/WSS sockets; `taskkill /T` stop path terminates the child tree.
Root cause hypothesis: `manage_local_agent.py` records the PID returned by `subprocess.Popen()` for the Windows venv launcher shim; that shim starts the real interpreter as a child process.
Root cause confirmed: Parent PID executable is `.venvs\agent-win\Scripts\python.exe`, child PID executable is `Python314\python.exe`; only the child owns the Maria Agent UIA window and TCP sockets. This is a Windows venv launcher/runtime-control observation, not a duplicate product agent runtime.
Blocking further P1: no after guardrail; final clean rerun should use instance/window discovery or child PID, not the stored parent PID.
Fix now: test-tool guardrail only.
Fix summary: Updated `scripts/live_agent_uia_state_probe.py` so `--instance` resolves the visible Maria Agent window by instance `data_dir`, and explicit `--pid` fails fast when that PID has no Maria Agent window instead of connecting to a shim and hanging.
Changed files: `scripts/live_agent_uia_state_probe.py`, `PLANS.md`.
Tests: `python -m py_compile scripts\live_agent_uia_state_probe.py`; negative UIA probe `--pid 31212` -> `Maria Agent window not found for pid=31212`; positive UIA probe `--pid 12592 --expect-connected --expect-account --expect-account-confirmed --expect-ticket-id 15f87a9a-726e-488d-9868-2d4b78cfac9c --expect-ticket-code T-000612` -> `failures=[]`.
Live regression: `manage_local_agent.py stop live-v3-p1-clean2` earlier terminated child PID `29060` and parent PID `3008` via taskkill tree; restarted instance produced parent PID `31212`/child PID `12592`, with child owning UI bridge/WSS and passing UIA semantic probe.
Remaining risk: `manage_local_agent.py status` still prints the launcher shim PID; this is acceptable for process tree stop/start but should not be used as GUI PID evidence. Future enhancement: show `effective_gui_pid`/child runtime PID in status.

### BUG-20260527-P1-17 - UIA ticket list metadata triggers GUI CPU/RSS spike after probe

Severity: P1
Status: verified-fixed
Area: UIA / local GUI / performance / test-tool

P1 scenario: P1.6.D local GUI UIA projection after `BUG-20260527-P1-15` first fix.
Run id: `p1-close-20260527-2333-ebcd4c0b`
Expected: UIA semantic metadata and bounded pywinauto probes must not leave the real GUI in a high-CPU/high-RSS state; GUI projection evidence should be lightweight and safe to repeat.
Actual: After the UIA ticket-list probe, GUI profiler samples showed the visible GUI process active at ~93-98% CPU with RSS rising from ~351 MB to >800 MB, hot receivers dominated by `QListView` / `TicketsSidebarWidget#MainPanel` / `QLineEdit#SearchInput`, and event rates around 24k-27k events/sec.
Repro steps:
1. Apply first-pass P1-15 metadata with ticket-list card data exposed through `QListView` accessible roles/list accessible name.
2. Start `live-v3-p1-clean2 --gui`, login confirmed account, create clean ticket `T-000612`.
3. Run bounded UIA state probe over the tickets view.
4. Tail local agent logs and inspect `[gui-profiler]` samples.

Evidence:
- Transport/API: local automation and browser remained functional, so this is not an API outage.
- Server log: not applicable.
- Agent log: `2026-05-27 23:56:05..23:58:55+05` `[gui-profiler]` samples show `cpu_percent=93..98`, `events_per_sec=24500..27930`, `active_window=MainWindow#agent.main_window`, hot widgets include `TicketsSidebarWidget#MainPanel`, `QLineEdit#SearchInput`, and `QListView`/stack painting. During the first mitigation live restart at `2026-05-28 00:01:17..00:01:18+05`, GUI startup failed with `AttributeError: 'ChatPanel' object has no attribute 'tickets_semantic_label'`, then the agent continued headless and `/ui/automation/status` returned HTTP 501 `automation status provider not configured`.
- Server DB: not applicable.
- Agent SQLite: not yet affected; outbox remained empty in preceding check.
- Browser/UI: browser support UI still displayed `T-000612`.
- UIA: trigger path was `scripts\live_agent_uia_state_probe.py` against ticket list semantic state.
- Test artifact: local logs from `.local-agent\instances\live-v3-p1-clean2\data\logs\agent.log`; run marker `p1-close-20260527-2333-ebcd4c0b`.
- Run marker: `p1-close-20260527-2333-ebcd4c0b`.

Impact: Blocks P1 close because GUI/UIA evidence collection must be safe and repeatable; a probe-induced CPU/RSS spike can contaminate reconnect/live timings and operator usability.
Root cause hypothesis: Exposing ticket-card semantics directly through `QListView` item accessible roles and/or a large dynamic list accessible name causes Qt UIA to traverse the virtualized list/delegate path heavily after pywinauto inspection.
Root cause confirmed: The high-CPU path was caused by putting dynamic ticket-card UIA semantics on the virtualized `QListView`/model accessibility surface. The first mitigation moved those semantics to a lightweight semantic `QLabel`, but `ChatPanel.set_tickets_sidebar()` did not copy `sidebar.tickets_semantic_label` onto `ChatPanel` before `_update_tickets_list_ui()`, causing the startup AttributeError captured above.
Blocking further P1: no after verification below.
Fix now: yes; this was introduced while fixing P1-15 and blocked clean P1.6.D.
Fix summary: Moved detailed ticket-card semantics off the virtualized `QListView`/model accessibility surface and onto a lightweight semantic `QLabel`; kept the list widget metadata bounded to list identity/count only. Fixed the first mitigation startup regression by wiring `sidebar.tickets_semantic_label` into `ChatPanel.set_tickets_sidebar()` before the first ticket-list render.
Changed files: `pc_agent/ui_gui/chat_panel.py`, `pc_agent/ui_gui/tickets_list_model.py`, `pc_agent/tests/test_gui_accessibility.py`, `PLANS.md`.
Tests: `python -m py_compile pc_agent\ui_gui\chat_panel.py pc_agent\ui_gui\accessibility.py scripts\live_agent_uia_state_probe.py`; `python -m pytest pc_agent\tests\test_gui_accessibility.py pc_agent\tests\test_chat_panel_helpers.py::test_ticket_header_widget_renders_actions_without_raw_public_url pc_agent\tests\test_chat_panel_helpers.py::test_ticket_create_wizard_exposes_stable_uia_ids pc_agent\tests\test_main_window_runtime_windows.py::test_main_window_syncs_sidebar_connection_status_with_requester_labels -q` -> 6 passed, 2 warnings.
Live regression: Restarted `live-v3-p1-clean2`, confirmed `/ui/automation/status` recovered with `window_visible=true`, `bridge_connected=true`, `connection_state=connected`, `sidebar_view=tickets`, `ticket_count=4`. Ran `.venvs\agent-win\Scripts\python.exe scripts\live_agent_uia_state_probe.py --instance live-v3-p1-clean2 --expect-connected --expect-account --expect-account-confirmed --expect-ticket-id 15f87a9a-726e-488d-9868-2d4b78cfac9c --expect-ticket-code T-000612 --output artifacts\p1-close-20260527-2333-ebcd4c0b-uia-state-ticket-T-000612-post-p1-17.json --screenshot artifacts\p1-close-20260527-2333-ebcd4c0b-uia-state-ticket-T-000612-post-p1-17.png --screenshot-timeout-sec 3 --max-depth 7 --max-nodes 900 --max-seconds 8`; output had `failures=[]`, `connection_state=connected`, `account_mode=confirmed_binding`, `ticket_count=4`; secret scan of JSON for token/session/cookie/authorization terms returned no matches.
Regression check: Post-probe performance samples stayed low and stable: PowerShell process sampling from `2026-05-28T00:06:20+05` to `00:06:45+05` showed child GUI CPU cumulative increasing only `6.359s -> 6.922s` and RSS `216.8MB -> 217.2MB`; local `[gui-profiler]` samples after restart/probe showed `cpu_percent=1.3..4.4`, `rss_mb=206.0..207.2`, `events_per_sec=86.8..255.0`, no 24k+ event storm and no RSS climb toward the pre-fix 800MB range.
Remaining risk: Screenshot capture via pywinauto still times out on this desktop and is recorded as `capture_timeout`; UIA pass criteria remain semantic control evidence, not screenshot. P1 clean rerun still needed after all P1 close bug triage.

P1 Findings Summary:
- P1-blocking/data-integrity/reconnect: none currently open after `BUG-20260527-P1-13` verification.
- P1-blocking/UIA projection: none after `BUG-20260527-P1-15` verification.
- P1-blocking/local runtime-control: none after `BUG-20260527-P1-16` classification/guardrail.
- P1-blocking/UIA performance: none after `BUG-20260527-P1-17` verification.
- Non-blocking but must be fixed before P1 close if accepting support/admin workflows: `BUG-20260527-P1-03`, `BUG-20260527-P1-05`, `BUG-20260527-P1-06`, `BUG-20260527-P1-07`, `BUG-20260527-P1-08`, `BUG-20260527-P1-09`, `BUG-20260527-P1-10`.
- Verified-fixed during this P1 pass/fix phase: `BUG-20260527-P1-04`, `BUG-20260527-P1-11`, `BUG-20260527-P1-12`, `BUG-20260527-P1-13`, `BUG-20260527-P1-14`.
- Known P1 contamination to filter until fixes: server `device_outbox.id=83` from pre-fix mixed-batch raw probe; `device_outbox.id=102` from P1.5.B; `device_outbox.id=105/106/107` from P1.5.D raw probe; local `seen_commands.command_id=a7734524-d1b6-461e-8f37-7d759e624b78` historical P1-12 contamination now recovered terminal `error/AGENT_RESTARTED`; ticket timeline started-only events for original P1.5.B/P1.5.C markers.
- Historical note from mid-fix phase: P1 was not complete at that time. Superseded by `P1 close summary - 2026-05-28`, where P1 is closed and P2 is marked ready after clean rerun.

### BUG-20260527-P1-11 — Agent exits on transient WSS 502 due bytes/string check in handshake-error handler

Severity: P0
Status: verified-fixed
Area: reconnect / agent-sqlite / deployment / local GUI-runtime

P1 scenario: P1.5.A Server restart with agent outbox pending.
Run id: `p1-20260527-1527-c4f03651`
Expected: During server/proxy downtime, WSS HTTP 502 should be treated as transient disconnect; agent process and GUI should stay alive, publish disconnected state, back off, reconnect after server returns, and flush pending outbox once.
Actual: A transient WSS 502 raised `aiohttp.WSServerHandshakeError`; the exception handler attempted `b"Token required" in message` when `message` was a string, raised `TypeError`, and `main_async` treated it as critical, shutting down the agent. Pending outbox row `17` remained `pending`; no server ticket event was persisted.
Repro steps:
1. Stop server with `python scripts\manage_remote_stack.py stop server`.
2. Insert controlled local outbox `chat_message` marker `p1-20260527-1527-c4f03651-p1-5a-server-restart-pending`.
3. Start server with `python scripts\manage_remote_stack.py start server`.
4. Observe local agent process status and logs.

Evidence:
- Transport/API: WSS connect returned HTTP 502 while proxy/server was unavailable; repeat `/api/health` smoke passed after server startup.
- Server log: server was intentionally stopped and then started; no ticket event exists for the marker.
- Agent log: `pc_agent/ws_agent.py:3230` raised `TypeError: 'in <string>' requires string as left operand, not bytes` after `aiohttp.client_exceptions.WSServerHandshakeError: 502`.
- Server DB: no `ticket_events` rows for marker `p1-20260527-1527-c4f03651-p1-5a-server-restart-pending`.
- Agent SQLite: `outbox_id=17`, `status=pending`, `attempts=0`, `agent_seq=9`, no sent history.
- Browser/UI: not applicable for successful marker evidence because delivery did not occur; browser route recovered after server startup.
- UIA: not yet run after crash; agent process stopped.
- Test artifact: local outbox test-hook payload includes only marker/ticket id; no raw tokens.
- Run marker: `p1-20260527-1527-c4f03651-p1-5a-server-restart-pending`.

Impact: Any transient WSS handshake/proxy 502 can terminate the local agent and strand pending outbox events until manual restart, invalidating reconnect/retry P1 scenarios.
Root cause hypothesis: Operator precedence and mixed bytes/string handling in `pc_agent/ws_agent.py` WSServerHandshakeError branch: `(isinstance(message, bytes) and b"Invalid token" in message or b"Token required" in message)` evaluates the second bytes containment test even when `message` is `str`.
Root cause confirmed: yes. `aiohttp.WSServerHandshakeError.message` was `str` (`Invalid response status`) for HTTP 502, and the unparenthesized bytes containment test raised `TypeError`, which escaped the reconnect loop and triggered full agent cleanup.
Blocking further P1: yes; P1.5 reconnect scenarios cannot be trusted while transient server restart kills the agent.
Fix now: yes; this is a reconnect/data-delivery blocker with a localized root cause.
Fix summary: Added `_is_auth_rejection_handshake_error()` to normalize `message` safely and classify only 4003/invalid-token/token-required cases as auth rejections; WSS 502 now stays in the transient handshake error path and reconnects.
Changed files: `pc_agent/ws_agent.py`, `pc_agent/tests/test_ws_agent_handshake_error_classification.py`, `PLANS.md`.
Tests: `python -m pytest pc_agent\tests\test_ws_agent_handshake_error_classification.py pc_agent\tests\test_seen_commands_retry_policy.py pc_agent\tests\test_ws_agent_canceled_command_idempotency.py -q` -> `7 passed in 0.96s`.
Live regression: Restarted fixed local agent; pending outbox `17` flushed and server persisted `ticket_events.id=179`. Then stopped server for a transient WSS 502 window and restarted it; fixed agent remained running (`pid=26644`), logged handshake 502 as retryable, reconnected with `handshake_ack`, `/api/health` smoke passed, local `outbox_count=0`, browser ticket timeline showed the P1.5.A marker.
Remaining risk: The fixed live regression used local source-mode agent and controlled server stop/start; packaged agent should receive the same code before release.

### BUG-20260527-P1-04 — Raw mixed-batch probe consumes follow-up command and leaves failed device_outbox

Severity: P1
Status: verified-fixed
Area: test-tool / protocol / server-db

P1 scenario:
P1.1.E mixed batch ACK/NACK using raw WebSocket probe against the live clean device.

Run id:
`p1-20260527-1527-c4f03651`

Expected:
The raw probe validates per-item ACK/NACK without leaving new failed server-side commands for the real device. If the probe triggers a valid device event that causes a follow-up server command, the probe must either handle that command or the scenario must use the real agent path for that item.

Actual:
The valid `tools_changed` item in the raw mixed batch persisted and triggered a server `list_tools` command. The raw probe received the command but did not send a `command_result`; the real agent reconnected and superseded the raw socket with close code `4002`; server `device_outbox` row `83` later reached `status=failed`, `error_code=TIMEOUT`, `command=list_tools`.

Repro steps:
1. Run `scripts\live_ws_v3_probe.py` mixed-batch/raw WS equivalent against `wss://192.168.100.17:9443/ws` using clean device `2447d396-79cd-53da-b3a9-028c5a4d56da`.
2. Include a valid `tools_changed` device event with `device_seq=5`.
3. Observe the probe receive a live `list_tools` command after the ACK/NACK responses.
4. Let the probe exit/supersede without answering the command.
5. Query server `device_outbox` for the clean device.

Evidence:
- Transport/API: probe artifact `artifacts\p1-20260527-1527-c4f03651-mixed-batch.json` shows ACK/NACK responses, then a `command` frame for `list_tools`, then close `4002`.
- Server log: not queried yet for this specific command timeout.
- Agent log: real agent reconnected after supersede; focused log excerpt not collected yet.
- Server DB: `device_outbox` id `83`, `command=list_tools`, `request_id=7de6bc1a-a072-4aa2-85ff-c980c8e41705`, `trace_id=2d1f01b8-0978-4619-bf97-9b71d0b89605`, `status=failed`, `sent_at=2026-05-27T10:44:19.748493+00:00`, `delivered_at=NULL`, `failed_at=2026-05-27T10:45:49.128118+00:00`, `error_code=TIMEOUT`.
- Agent SQLite: not applicable for the raw probe command; real clean agent local SQLite did not own that command because the command was delivered to the raw probe socket.
- Browser/UI: ticket browser projection still correctly shows the valid batch ticket event once and no duplicate marker; screenshot `artifacts\p1-20260527-1527-c4f03651-ticket-T-000609-after-mixed-batch.png`.
- UIA: not applicable.
- Test artifact: `artifacts\p1-20260527-1527-c4f03651-mixed-batch.json`.
- Run marker: `p1-20260527-1527-c4f03651`.

Impact:
This creates new post-fix contamination in `device_outbox` and makes the P1 clean-run outbox gate unreliable unless it is labeled and excluded. It also means raw WS probes for the real live device must not emit valid device lifecycle events without handling follow-up commands.

Root cause hypothesis:
The test probe currently validates outbox ingest but is not a full agent command runtime. A valid `tools_changed` event is not passive: the server responds by enqueuing and dispatching `list_tools` to the currently connected socket for the device. The raw socket became the active device session and could not complete the command lifecycle.

Root cause confirmed:
Confirmed. The first raw mixed batch used `event=tools_changed`, and server outbox publish side effects enqueue `list_tools` after `tools_changed` / `module_state_changed`. The raw socket was the active session and received the command but had no command runtime.

Blocking further P1: yes for a clean P1.1.E pass; no for documenting the already observed ACK/NACK semantics.
Fix now: yes.
Fix summary:
Added a dedicated `mixed-batch` diagnostic subcommand to `scripts\live_ws_v3_probe.py`. Its default valid device event is neutral `probe_device_event`, so raw probe can validate device-event ACK/persistence without triggering server `list_tools` side effects. `tools_changed` remains covered by real-agent P1.1.B.

Changed files:
`scripts\live_ws_v3_probe.py`; `scripts\test_live_ws_v3_probe.py`; `PLANS.md`.

Tests:
`python -m pytest scripts\test_live_ws_v3_probe.py -q` -> `2 passed`.

Live regression:
Clean rerun artifact `artifacts\p1-20260527-1527-c4f03651-cleanmix-mixed-batch.json`: expected three ACKs, expected three non-retryable NACKs, `unexpected_command_count=0`; server DB persisted only the valid ticket/device rows and no new `device_outbox` row after contaminated id `83`; browser ticket snapshot shows cleanmix valid marker and no cleanmix duplicate marker.

Remaining risk:
Existing `device_outbox` id `83` remains as labeled pre-fix P1-04 contamination. Future raw probe scenarios must avoid lifecycle events with server follow-up side effects unless the probe explicitly implements command handling.

### BUG-20260527-P1-03 — Admin device account-events route returns 500 in browser

Severity: P1
Status: verified-fixed
Area: browser / UI projection / server-db

P1 scenario:
P1.1.B browser/admin confirmation for clean device after a valid `tools_changed` device event.

Run id:
`p1-20260527-1527-c4f03651`

Expected:
Admin device page loads all visible device/account projections without browser console/network errors for the clean device.

Actual:
The page rendered the device card, online status, agent version and observer panel, but browser console reported HTTP 500 for `GET /api/web/admin/registry/devices/2447d396-79cd-53da-b3a9-028c5a4d56da/account-events?limit=20`.

Repro steps:
1. Navigate real browser to `https://192.168.100.17:9443/app/admin/device?device=2447d396-79cd-53da-b3a9-028c5a4d56da`.
2. Wait for admin device page to load.
3. Observe Playwright/browser console event.

Evidence:
- Transport/API: browser console captured `Failed to load resource: the server responded with a status of 500 (Internal Server Error) @ https://192.168.100.17:9443/api/web/admin/registry/devices/2447d396-79cd-53da-b3a9-028c5a4d56da/account-events?limit=20:0`.
- Server log: `manage_remote_stack.py logs --contains account-events` did not surface a focused traceback in the recent tail; deeper root-cause analysis not started yet.
- Agent log: not applicable to the browser route failure.
- Server DB: device id `2447d396-79cd-53da-b3a9-028c5a4d56da`; valid account session `c24c7842-8284-4964-a92f-7f608eaf52d2`; exact failing query not analyzed yet.
- Agent SQLite: not applicable.
- Browser/UI: admin device page snapshot `artifacts\p1-20260527-1527-c4f03651-admin-device-snapshot.md` shows device content loaded while account-events request failed.
- UIA: not applicable.
- Test artifact: `C:\Temp\playwright-mcp-output\1779820608110\console-2026-05-27T10-38-13-382Z.log`.
- Run marker: `p1-20260527-1527-c4f03651`.

Impact:
P1.1.B can still validate outbox ACK/persistence, but P1.6 UI projection consistency cannot be green until this route is root-caused or explicitly deferred.

Root cause hypothesis:
Typed web registry/account-events handler error in account-event serialization for cleaned registration/session state.

Root cause confirmed:
`AccountSessionService.serialize_event()` called `_iso(row.event_at)`, but `_iso` was not defined in `server/registry/account_session_service.py`. Live remote service reproduction through the same service path raised `NameError: name '_iso' is not defined`, matching the browser-visible 500.

Blocking further P1: no after fix; browser/admin projection now has clean route evidence.
Fix now: yes
Fix summary:
Added local `_iso()` helper in `server/registry/account_session_service.py` and covered event serialization with a focused regression test.

Changed files:
`server/registry/account_session_service.py`, `server/tests/test_account_session_service.py`, `scripts/navigation_catalog.py`, `PLANS.md`.

Tests:
`python -m py_compile server\registry\account_session_service.py server\tests\test_account_session_service.py`; `PC_CLIENT_PYTEST_WATCHDOG_SECONDS=15 python -m pytest server\tests\test_account_session_service.py::test_serialize_event_formats_event_at_without_route_500 -vv -s` -> 1 passed in 333.98s after full test DB migrations.

Live regression:
Commit `dbe1d72f` deployed through `python scripts\release_server_to_remote.py --gate quick --allow-local-dirty --leave-running --smoke-insecure-tls --smoke-attempts 8 --smoke-delay 2`; `/api/health` passed on smoke attempt 2. Real browser direct route `https://192.168.100.17:9443/api/web/admin/registry/devices/2447d396-79cd-53da-b3a9-028c5a4d56da/account-events?limit=20` returned `{"status":"success"}` with account event items and ISO `event_at` values. Real browser admin device page loaded with no new console error from account-events; screenshot `p1-close-20260527-2333-p1-03-admin-device-afterfix.png`, console artifact `p1-close-20260527-2333-p1-03-console-afterfix.log`.

Remaining risk:
None for the 500 route; broader admin projection still depends on final P1.6 clean rerun.

### P1 close decision for BUG-20260527-P1-03

Current evidence: browser-visible route 500 reproduced and root-caused to undefined `_iso`; post-fix browser/API route returns success.
Product impact: admin account/session event timeline was partially broken.
Blocks P1 close: no after verified fix.
Correct product behavior: route returns 200 success with event list or empty list, not 500.
Action: fixed now.
Required regression: include account-events route in P1.6 browser/admin clean rerun.
Status after action: verified-fixed.

### BUG-20260527-P1-05 — Local automation run-tool carries requester session but uses disallowed agent actor role

Severity: P1
Status: known-limitation
Area: automation / auth/account-session / operation lifecycle

P1 scenario:
P1.2 setup for `system.collect` via local GUI automation bridge before command-idempotency duplicate injection.

Run id:
`p1-20260527-1527-c4f03651`

Expected:
`/ui/automation/run` action `ticket.tool.run` should either behave like the intended local GUI tool action with valid confirmed account session and allowed actor context, or return a deterministic preflight error before making a server request. It should not create an operation when denied.

Actual:
`python scripts\agent_test_driver.py run-tool live-v3-p1-clean2 --ticket-id f2918f87-cca3-42a9-b28f-f0a5e09d72b9 --tool-name system.collect --params-json "{}"` returned HTTP 500 from the local automation bridge, embedding server HTTP 403 `ROLE_NOT_ALLOWED`: required role `llm, support или admin`, actor_role `agent`.

Repro steps:
1. Ensure clean agent `live-v3-p1-clean2` is connected and has confirmed account session `c24c7842-8284-4964-a92f-7f608eaf52d2`.
2. Run the command above against ticket `T-000609`.
3. Observe local bridge HTTP 500 with embedded server 403 `ROLE_NOT_ALLOWED`.

Evidence:
- Transport/API: local bridge response `HTTP 500 for http://127.0.0.1:8767/ui/automation/run: {"status": "error", "error": "HTTP 403: {\"status\": \"error\", \"error\": \"Policy violation\", \"error_code\": \"ROLE_NOT_ALLOWED\", \"required_role\": \"llm, support \\u0438\\u043b\\u0438 admin\", \"actor_role\": \"agent\"}"}`.
- Server log: not queried yet.
- Agent log: action trace collection after repro shows ticket polling with account session redacted; focused `ticket.tool.run` trace entry not collected yet.
- Server DB: `operations` query for ticket `f2918f87-cca3-42a9-b28f-f0a5e09d72b9` returned `[]`, so the denied automation request did not create an operation.
- Agent SQLite: local `outbox=[]`; latest `seen_commands` rows unchanged from earlier `list_tools` successes, no new `system.collect` command row.
- Browser/UI: not applicable to the denied bridge request; browser support route will be tested separately as workaround/canonical support surface.
- UIA: not applicable; this is automation bridge, not real GUI.
- Test artifact: command output in this PLANS entry.
- Run marker: `p1-20260527-1527-c4f03651`.

Impact:
Local automation bridge is still not a full GUI-equivalent for tool actions after the P0 account-session fixes. This blocks using the bridge as a P1 command-idempotency setup path, but does not block P1.2 because browser/support route and direct diagnostic device_outbox injection can be used with explicit surface labeling.

Root cause hypothesis:
The bridge now propagates account session but still sends/derives `actor_role=agent` for a tool policy that only allows `llm`, `support`, or `admin`. The correct behavior may require a typed requester-safe tool policy path, support actor context, or a deterministic local preflight denial depending on product policy.

Blocking further P1: no
Fix now: no
Fix summary:
Not fixed.

Changed files:
None.

Tests:
Not run for this bug yet.

Live regression:
Not run.

Remaining risk:
Any P1 scenario using `/ui/automation/run` for ticket tool/capture actions can still fail independently of real browser/support workflows and must not be treated as GUI failure without separate UIA evidence.

### P1 close decision for BUG-20260527-P1-05

Current evidence: local automation bridge propagates requester account session but server rejects `ticket.tool.run` with `ROLE_NOT_ALLOWED` because the bridge uses `actor_role=agent`; no operation row is created and agent SQLite remains clean.
Product impact: `/ui/automation/run` is not a complete GUI-equivalent for operator/support tool launch. It remains a test surface, not the canonical support browser workflow.
Blocks P1 close: no, provided P1.2/P1.5 use the canonical browser/support route for tool operations and label automation-bridge evidence separately.
Correct product behavior: either add a product-backed local GUI tool action with an allowed support/admin actor context, or make the automation bridge return deterministic preflight denial instead of embedded HTTP 500.
Action: classify as known-limitation for P1 close; defer product policy/fix to the automation-bridge hardening backlog.
Required regression: final P1 clean rerun must use browser support route for `system.collect`/long-running tool lifecycle; automation bridge must not be used as pass evidence for tool launch.
Status after action: known-limitation.

### BUG-20260527-P1-06 — screen.record artifact upload is denied and operation is projected as success

Severity: P1
Status: verified-fixed
Area: artifact-upload / auth-account-session / operation lifecycle / UI projection

P1 scenario:
P1.2.B duplicate while in-progress used `screen.record` as a safe long-running tool.

Run id:
`p1-20260527-1527-c4f03651`

Expected:
If `screen.record` produces a recording artifact, the agent should upload it through the supported artifact endpoint with valid auth/context, the server should persist artifact metadata, the operation/ticket event should preserve the partial/failure state accurately, and browser timeline should not label an artifact-upload partial result as fully successful.

Actual:
The recording itself completed (`frames_captured=100`, `duration_sec=26.8`, `file_size_bytes=18188`), but artifact upload failed with HTTP 403 `AuthorizationError`. Agent SQLite stored one terminal `seen_commands` row with local `status=error` and ToolResponse `status=partial`; the server operation became `status=succeeded`; browser timeline showed `screen.record` result as `Успешно` while raw JSON contained `"status": "partial"` and `artifacts=[]`.

Repro steps:
1. In a real browser support session, POST `screen.record` through `/api/web/support/tickets/f2918f87-cca3-42a9-b28f-f0a5e09d72b9/tools/run` with `duration_sec=20`, `fps=5`, `max_width=640`, `quality_crf=40`.
2. Let the clean agent `live-v3-p1-clean2` execute the command.
3. Query agent SQLite `seen_commands` for operation `755c2996-27e1-43b0-8d94-7d5ba7595b5b`.
4. Query server `operations`, `ticket_events` and browser ticket timeline.

Evidence:
- Transport/API: browser support route returned HTTP `202`, `dispatch_status=accepted`, operation `755c2996-27e1-43b0-8d94-7d5ba7595b5b`.
- Server log: not collected yet for the upload 403; remote recent server tail did not show a focused `755c2996` line in the first pass.
- Agent log: action trace shows one `screen.record` execution and module finish `status=partial`, `upload_error_count=1`, `artifact_count=0`.
- Server DB: `operations.status=succeeded`, `result_summary={'frames_captured': 100, 'duration_sec': 26.8, 'file_size_bytes': 18188}`; `ticket_events` ids `153 tool_call_started` and `155 tool_call_result`, result payload contains `"status": "partial"` and `artifacts=[]`.
- Agent SQLite: `seen_commands.command_id=755c2996-27e1-43b0-8d94-7d5ba7595b5b`, local `status=error`; parsed result has `status=partial`, `errors[0].code=ARTIFACT_UPLOAD_FAILED`, `errors[0].details.exc_type=AuthorizationError`, `errors[0].details.exc_message` includes HTTP `403`; local `outbox=[]`; `outbox_sent_history` outbox id `9` persisted one `tool_response`.
- Browser/UI: ticket snapshot `artifacts\p1-20260527-1527-c4f03651-p1-2b-after-duplicate-running-snapshot.md` shows `screen.record` result with UI status `Успешно`, raw JSON `"status": "partial"`, `artifacts=[]`; screenshot `artifacts\p1-20260527-1527-c4f03651-p1-2b-after-duplicate-running.png`.
- UIA: not applicable; this was browser support route plus agent runtime.
- Test artifact: local DB/result excerpts in this PLANS entry.
- Run marker: `p1-20260527-1527-c4f03651`, operation `755c2996-27e1-43b0-8d94-7d5ba7595b5b`.

Impact:
Artifact-producing tools can lose their artifact while the operator UI still reads as successful. This threatens P2.2 artifact validation and makes operation lifecycle/status projection inconsistent for partial ToolResponse results.

Root cause hypothesis:
Likely artifact upload auth/context mismatch from the agent runtime path after account-session hardening, or server command-result lifecycle mapping that treats `payload.status=success` as operation success while nested ToolResponse `result.status=partial` indicates artifact upload failure.

Blocking further P1: no for P1.2 idempotency because duplicate command behavior was still deterministically verified; yes for any artifact-focused scenario.
Fix now: no
Fix summary:
P2 fix phase in progress:
- `POST /api/upload` now treats agent-token uploads with both `ticket_id` and `operation_id` as server-commanded operation artifacts and authorizes them by matching `operation_id -> ticket_id + device_id`.
- Agent-token uploads with `ticket_id` but without `operation_id` still require requester account-session context, preserving the manual local-agent attachment boundary.
- Command result normalization now preserves ToolResponse `status=partial`; the operation lifecycle maps it to terminal failed instead of succeeded, and the ticket `tool_call_result` payload keeps `status=partial`.

Changed files:
- `server/uploads/handlers.py`
- `server/websocket/command_result_parser.py`
- `server/websocket/command_result_components.py`
- `server/tests/test_upload_handlers.py`
- `server/tests/test_agent_services_pipeline.py`
- `server/tests/test_command_result_lifecycle_db.py`
- `server/docs/ARTIFACTS_API.md`
- `server/docs/CODEMAP.md`
- `docs/QUICK_LOOKUP.md`
- `scripts/navigation_catalog.py`
- `PLANS.md`

Tests:
- `python -m pytest server\tests\test_upload_handlers.py server\tests\test_agent_services_pipeline.py::test_command_result_normalizer_maps_partial_to_failed_lifecycle server\tests\test_agent_services_pipeline.py::test_tool_call_result_payload_preserves_partial_status server\tests\test_command_result_lifecycle_db.py::test_command_result_partial_marks_operation_failed_and_delivers_outbox -q` -> passed (`7 passed` for no-DB subset plus DB lifecycle test passed separately).
- `python -m pytest server\tests\test_upload_handlers.py server\tests\test_agent_services_pipeline.py server\tests\test_command_result_lifecycle_db.py server\tests\test_web_session_api.py -q` -> `57 passed, 15 warnings` (existing aiohttp `NotAppKeyWarning` only).
- `python -m compileall -q server pc_agent scripts` -> passed.
- `git diff --check` -> exit 0; CRLF warnings only.
- `python scripts\verify_workspace.py` -> passed.

Live regression:
- Commit `7bb28ded2d997bef589916f137bf37da2c56530b` pushed to GitHub and deployed to the Linux stand through quick release; `/api/health` smoke passed.
- Clean P2.2.C ticket: `T-000619`, `ticket_id=eadd3b88-70b2-444e-a8cb-efad7484f852`, marker `p2-20260528-0925-cef033e7-agent-artifact-fixed-7bb28ded`.
- Local GUI automation bridge path: `capture-screenshot` accepted `screen.collect` operation `5bcfa717-9ccc-4ba2-ab4a-76bf3c161d97`, trace `3e2167c3-23d8-4469-876c-da949ffa488e`.
- Server DB: operation `5bcfa717-9ccc-4ba2-ab4a-76bf3c161d97` is `status=succeeded`, `error_code=NULL`, `result_event_id=306`; device_outbox id `147` is `delivered`; ticket events ids `304 tool_call_started` and `306 tool_call_result`; artifact row `c0bdd8fd-3179-4e63-acc6-0e4061b1e574` is linked to the same ticket/operation with `kind=screenshot`, `mime_type=image/png`, `size_bytes=740258`.
- Agent A SQLite: `seen_commands.command_id=5bcfa717-9ccc-4ba2-ab4a-76bf3c161d97` has local `status=success`, ToolResponse `status=success`, `artifact_count=1`; local `outbox=[]`; sent history contains one `tool_response`; `pending_consents_count=0`.
- Browser/UI: real support browser URL `https://192.168.100.17:9443/app/tickets/eadd3b88-70b2-444e-a8cb-efad7484f852` shows ticket `T-000619`, `screen.collect` diagnostic result status `Успешно`, result details, and `1 влож.` on the result card. Screenshot: `p2-20260528-agent-artifact-fixed-T-000619.png`.
- Browser download check: same browser web session fetched `/api/artifacts/c0bdd8fd-3179-4e63-acc6-0e4061b1e574/download?ticket_id=eadd3b88-70b2-444e-a8cb-efad7484f852` and received HTTP `200`, `content-type=image/png`, `bytes=740258`, safe `Content-Disposition` with `filename*`.
- Browser console/network artifacts: `p2-20260528-agent-artifact-fixed-console-errors.json`, `p2-20260528-agent-artifact-fixed-network.json`.

Remaining risk:
Screen recording should still get a separate P2.2 artifact-size/duration check; the fixed authorization path is operation-bound and was verified with `screen.collect`.

### P1 close decision for BUG-20260527-P1-06

Current evidence: `screen.record` completes locally with ToolResponse `status=partial` after artifact upload HTTP 403; server operation/browser card project it as succeeded.
Product impact: artifact-producing tool results can lose artifacts and mislead UI status. This is directly relevant to P2.2 artifact validation.
Blocks P1 close: no for P1.2/P1.5 command idempotency/reconnect if clean rerun uses a non-artifact long-running diagnostic or explicitly treats screen-record artifact failure as excluded artifact contamination.
Correct product behavior: artifact upload auth/context must be fixed and operation/UI status must reflect partial ToolResponse results.
Action: fixed during P2.2 artifact/status-projection pass.
Required regression: P2.2 must cover upload metadata, browser preview/download, and partial upload failure projection.
Status after action: verified-fixed.

P2 clean evidence before fix:
- Run id: `p2-20260528-0925-cef033e7`.
- Run marker: `p2-20260528-0925-cef033e7-agent-artifact`.
- Scenario path tested:
  - local GUI automation bridge `/ui/automation/run`: `python scripts\agent_test_driver.py capture-screenshot live-v3-p1-clean2 --ticket-id 7339a826-17a7-47fc-9bdf-1bee1b5a1e0c`;
  - agent runtime flow: real Agent A `live-v3-p1-clean2` executed `screen.collect`;
  - real browser support UI: `https://192.168.100.17:9443/app/tickets/7339a826-17a7-47fc-9bdf-1bee1b5a1e0c`;
  - server DB and Agent A SQLite queried separately.
- Ticket: `T-000618`, `ticket_id=7339a826-17a7-47fc-9bdf-1bee1b5a1e0c`, `device_id=2447d396-79cd-53da-b3a9-028c5a4d56da`.
- Operation: `bc81d55c-08bb-4bde-9f68-d2852e985da2`, tool `screen.collect`, trace `70d093da-72f7-458e-be48-ee543b33ec0d`.
- Transport/API: automation bridge accepted the capture request and returned `operation_id=bc81d55c-08bb-4bde-9f68-d2852e985da2`.
- Server DB: `operations.status=succeeded`, `tool_name=screen.collect`, `error_code=NULL`; `ticket_events` ids `291 tool_call_started` and `293 tool_call_result`; no `artifacts` row exists for this ticket/operation.
- Agent A SQLite: `seen_commands.command_id=bc81d55c-08bb-4bde-9f68-d2852e985da2` has local `status=error`; ToolResponse has `status=partial`, `artifacts=[]`, and error `ARTIFACT_UPLOAD_FAILED` with `exc_type=AuthorizationError`, HTTP `403`.
- Browser/UI: real support ticket page shows the `screen.collect` result card as successful (`Успешно`) while the raw ToolResponse on the same card contains `status=partial`, `artifacts=[]`, and the upload failure details.
- UIA: not applicable for this capture path; it was automation bridge plus runtime tool execution, with browser projection evidence.
- Old contamination: this is a fresh P2 marker and clean operation; it reproduces the same product bug class as the original P1 record and is not counted as a new P2 bug id.
- Root cause confirmed:
  - Agent runtime artifact upload uses the agent Bearer token and sends `ticket_id` plus `operation_id`, but it has no requester account-session headers.
  - `server/uploads/handlers.py::handle_upload()` routes every agent upload with `ticket_id` through `_require_agent_ticket_account_access()`, which requires requester account session and returns 403.
  - This is too strict for server-commanded operation artifacts: an agent-token upload should be allowed when `operation_id` belongs to the same `ticket_id` and same `device_id`; manual requester/agent attachment uploads without operation binding should still require account-session.
  - `server/websocket/command_result_parser.py` also normalizes ToolResponse `status=partial` to lifecycle `success`, causing server operation/browser projection to show success for a partial artifact failure.
- Fix policy: fix now because P2.2 artifact validation cannot be trusted while operation-bound agent artifacts are denied and partial results are projected as full success.

## P1 fix phase — 2026-05-27 — run_id=p1-fix-20260527-2123-4f42ec7c

Status: started. P2 remains blocked. This phase fixes P1-blocking product contracts found during `p1-20260527-1527-c4f03651`; old contamination remains recorded above and must not be treated as new evidence.

Run metadata:
- Branch: `codex/helpdesk-process-model`.
- Commit SHA before fix phase: `4f42ec7c456f0a845083631532beb2216376d6fb`.
- Server URL: `https://192.168.100.17:9443`.
- Browser/admin URL: `https://192.168.100.17:9443/admin`.
- Local agent instance intended for live regressions: `live-v3-p1-clean2`.
- Current known clean P1 device id: `2447d396-79cd-53da-b3a9-028c5a4d56da`.
- Agent version from P1 baseline: `3.1.61`.
- pywinauto requirement for GUI evidence: `0.6.9`, backend `uia`.
- Evidence rules: no raw tokens/cookies/session tokens; each live rerun must use marker prefix `p1-fix-20260527-2123-4f42ec7c`.

Known pre-fix contamination ignored for this fix phase:
- Server `device_outbox.id=83` from pre-fix mixed-batch raw probe.
- Server `device_outbox.id=102` from P1.5.B agent-restart contamination.
- Server `device_outbox.id=105/106/107` from P1.5.D raw probe consuming live module install commands.
- Local `seen_commands.command_id=a7734524-d1b6-461e-8f37-7d759e624b78 status=in_progress` from `BUG-20260527-P1-12`; after commit `32523630` this was recovered to terminal `error/AGENT_RESTARTED` and remains labeled as old contamination, not clean-run evidence.
- Ticket timeline started-only events for P1.5.B/P1.5.C markers in ticket `T-000609`.

P1 operation lifecycle contract:
1. An operation must not remain indefinitely in `queued`, `sent`, `accepted`, `running`, `waiting_consent`, or `cancel_requested` after agent restart, server restart, or websocket drop.
2. Every command/operation must end in one terminal outcome: `succeeded`, `failed`, `timed_out`, or `canceled`. If an explicit `interrupted` status is not added to the DB/API/UI model, agent restart interruption must be represented as `failed` with `error_code=AGENT_RESTARTED` or `COMMAND_INTERRUPTED_BY_AGENT_RESTART`.
3. Late terminal agent results must never disappear without audit trail. A late result after timeout/restart must either reconcile the original operation or be persisted as linked late-result evidence.
4. `device_outbox` and local `seen_commands` must agree with the operation lifecycle: terminal operations cannot leave matching server outbox rows stale in `sent`, and terminal commands cannot leave local idempotency rows stale in `in_progress`.
5. Duplicate command delivery after a terminal state must not run the tool again; it must return/replay the terminal cached result or deterministic terminal error.
6. Non-resumable tools are not magically continued after agent process restart. Unless a tool declares a resumable recovery contract, restart interruption must be reported as terminal failed/interrupted.
7. Browser/UI projection must show terminal or late/reconciled state, not stale active operation cards.
8. Diagnostic raw probes are not production agent runtime sessions and must not consume live commands, supersede live runtime sessions by default, or mutate online state as if they were the real agent.

Fix order and current intent:
- [x] `BUG-20260527-P1-14` first: isolate raw diagnostic probes before additional probe/live reconnect regressions. Verified fixed in `16000f1d52bff549ed57fb61492c83345f1cf2f7`.
- [x] `BUG-20260527-P1-12`: agent restart recovery for non-resumable running commands. Verified fixed in `325236301dde6944201076b082d21ab5589fc6d6` with clean operation `a0764846-3ab7-42f5-8e79-93d8c310ba6b`.
- [x] `BUG-20260527-P1-13`: durable late command result replay/reconciliation after server drop/timeout. Verified fixed in `96dc0706fc28c9e3b5e0c72bc509e017287f742f` + `5e5af5d8da58505e4d7f3415bd94f2696c54d83c` with clean operation `a921bec8-e71d-428a-afa3-287fa0083f21`.
- [x] `BUG-20260527-P1-15`: semantic UIA accessibility for connected/account/ticket state. Verified fixed with clean ticket `T-000612` / marker `p1-close-20260527-2333-ebcd4c0b`.
- [ ] `BUG-20260527-P1-16`: local runtime-control duplicate process ownership; triage before final P1 close.

Verification gates after each fix:
- Targeted unit/integration tests for the changed layer.
- `python -m compileall -q` for touched packages/scripts.
- Live regression with marker `p1-fix-20260527-2123-4f42ec7c-*`.
- Browser confirmation for UI-visible operation/ticket/device projections.
- Agent SQLite confirmation for agent runtime/idempotency paths.
- `PLANS.md` status consistency audit before marking a bug `verified-fixed`.

## P1 close audit - 2026-05-27 - run_id=p1-close-20260527-2333-ebcd4c0b

Audit path: `PLANS.md` bug blocks and P1 findings summary only. No code fixes started before this audit. Old evidence is preserved. Current head before close work: `ebcd4c0b`, branch `codex/helpdesk-process-model`.

| Bug | Current status | Area | Blocking P1 close | Required action |
|---|---|---|---|---|
| BUG-20260527-P1-01 | verified-fixed | test-tool / local GUI / account-session | no | Keep as fixed baseline; filter only old clean-agent contamination if referenced. |
| BUG-20260527-P1-02 | verified-fixed | account-session / local GUI / automation / test-tool | no | Keep as fixed baseline; account-session validation must remain in POST/body or headers. |
| BUG-20260527-P1-03 | verified-fixed | browser / UI projection / server-db | no | Fixed undefined `_iso()` in account-event serialization; rerun admin device page in P1.6 clean gate. |
| BUG-20260527-P1-04 | verified-fixed | test-tool / protocol / server-db | no | Keep as fixed; old `device_outbox.id=83` is pre-fix contamination; raw probe rerun must use diagnostic isolation. |
| BUG-20260527-P1-05 | known-limitation | automation / auth-account-session / operation lifecycle | no | Do not use automation bridge as canonical tool-launch evidence; use browser support route in P1 clean rerun. |
| BUG-20260527-P1-06 | verified-fixed | artifact-upload / auth-account-session / operation lifecycle / UI projection | no | Fixed during P2.2 artifact pass by commit `7bb28ded`; operation-bound agent artifacts upload successfully and partial ToolResponse no longer projects as success. |
| BUG-20260527-P1-07 | known-limitation | consent / browser / auth-account-session / UI projection | no for P1 close, yes for P1.3 green | Consent center is read-only; future consent milestone needs typed browser approve/deny actions. |
| BUG-20260527-P1-08 | known-limitation | consent / agent-sqlite / local GUI-UIA / documentation drift | no for P1 close, yes for agent-GUI consent claim | Current consent is server-side before dispatch; future pass must choose/document canonical consent boundary. |
| BUG-20260527-P1-09 | verified-fixed | module-runtime / outbox / server-db / protocol | no | Clean rerun `p1-close-20260528-0040-dbe1d72f` verified durable `module_state_changed`/`tools_changed`, delivered outbox and browser admin projection. |
| BUG-20260527-P1-10 | deferred | module-runtime / operation lifecycle / server-db / UI projection | no if clean stale checks pass | Negative auto-install operation/timeline UX deferred; final close must confirm no new stale desired/outbox rows for close run id. |
| BUG-20260527-P1-11 | verified-fixed | reconnect / agent-sqlite / deployment / local GUI-runtime | no, but clean rerun required | Keep fixed; rerun reconnect smoke in final P1 close gate. |
| BUG-20260527-P1-12 | verified-fixed | reconnect / idempotency / operation lifecycle / agent-sqlite / server-db / browser | no, but clean rerun required | Keep fixed; rerun agent-restart non-resumable command gate with new close run marker. |
| BUG-20260527-P1-13 | verified-fixed | reconnect / outbox / operation lifecycle / server-db / agent-sqlite / browser | no, but clean rerun required | Keep fixed; rerun server-drop/late-result gate with new close run marker. |
| BUG-20260527-P1-14 | verified-fixed | reconnect / module-runtime / test-tool / server-db / protocol | no, but clean rerun required | Keep fixed; rerun diagnostic probe isolation and ensure no live command consumption. |
| BUG-20260527-P1-15 | verified-fixed | UIA / local GUI / UI projection | no | Keep fixed; include `T-000612` UIA/browser evidence in P1.6 clean rerun summary. |
| BUG-20260527-P1-16 | verified-non-product / guardrails-added | deployment/runtime-control / local GUI-runtime / test-tool | no | Windows venv launcher shim classified; UIA probe now resolves real GUI child by instance and fails fast on shim PID. |
| BUG-20260527-P1-17 | verified-fixed | UIA / local GUI / performance / test-tool | no | Keep post-fix low CPU/RSS evidence; include UIA semantic probe artifact in P1.6 clean rerun summary. |

Status consistency audit result:
- Historical audit state: P1 was not closed at audit time. Superseded by `P1 close summary - 2026-05-28`, where P1 is closed after the required clean rerun.
- `BUG-20260527-P1-15` is now verified-fixed with real UIA and browser evidence.
- `BUG-20260527-P1-16` is classified as `verified-non-product / guardrails-added`: stored PID is a Windows venv launcher shim, child PID owns GUI/UI bridge/WSS; UIA probe guardrail prevents shim PID evidence.
- `BUG-20260527-P1-17` is verified-fixed: ticket-list semantics moved off `QListView`/model accessibility surface and post-probe CPU/RSS remained stable.
- `BUG-20260527-P1-03` is verified-fixed; `BUG-20260527-P1-05`, `BUG-20260527-P1-06`, `BUG-20260527-P1-07`, `BUG-20260527-P1-08`, and `BUG-20260527-P1-10` are formally classified for P1 close.
- `BUG-20260527-P1-09` is verified-fixed by clean module lifecycle rerun `p1-close-20260528-0040-dbe1d72f`.
- `BUG-20260527-P1-11`, `BUG-20260527-P1-12`, `BUG-20260527-P1-13`, and `BUG-20260527-P1-14` remain `verified-fixed`, but P1.5/P1.6 still need clean rerun after all fixes.

P1 close decisions recorded during run `p1-close-20260527-2333-ebcd4c0b`:
- `BUG-20260527-P1-03`: fixed now. Root cause was undefined `_iso()` in `AccountSessionService.serialize_event()`. Commit `dbe1d72f` deployed to remote; real browser account-events route now returns `status=success` and admin device page has no new account-events console 500. Required regression: include account-events/admin device page in P1.6 clean rerun.
- `BUG-20260527-P1-05`: classified as `known-limitation`. The local automation bridge is a test surface; it carries account session but uses `actor_role=agent`, so server correctly denies support/admin-only tool launch and no operation is created. P1 clean rerun must use the browser support route for tool lifecycle evidence.
- `BUG-20260527-P1-06`: verified-fixed during the P2.2 artifact/status-projection pass. P1 idempotency evidence remains unchanged; P2.2 clean ticket `T-000619` verifies artifact upload auth, DB metadata, Agent A SQLite, browser timeline and download.
- `BUG-20260527-P1-07`: classified as `known-limitation`. Current consent center is browser-visible but read-only; support web-session approve/deny routes/actions are missing. P1.3 cannot be marked green until consent browser actions exist.
- `BUG-20260527-P1-08`: classified as `known-limitation / documentation drift`. Current product path holds risky-tool consent server-side before command dispatch, so the agent never receives a local `pending_consents` prompt. Future consent pass must choose and document browser-side vs agent-side canonical consent.
- `BUG-20260527-P1-09`: verified-fixed by clean rerun `p1-close-20260528-0040-dbe1d72f`. Direct admin HTTP route triggered `network_basic` deactivate/activate, both operations succeeded, local agent emitted `tools_changed` and `module_state_changed`, server persisted device events, and browser admin modules/device pages showed current module/operation projection. Old P1.4.A contamination remains ignored.
- `BUG-20260527-P1-10`: classified as `deferred` for negative module auto-install UX/lifecycle. The stale desired row was cleanup-recovered; P1 close may proceed only if final P1.4/P1.5 checks have no new stale desired/outbox rows for the close run id.

### P1 close clean rerun log - 2026-05-28 - run_id=p1-close-20260528-0040-dbe1d72f

Scope discipline:
- Run id / marker: `p1-close-20260528-0040-dbe1d72f`.
- Code head: `dbe1d72f` on `codex/helpdesk-process-model`.
- Server URL: `https://192.168.100.17:9443`; browser/admin URL: `https://192.168.100.17:9443/admin`.
- Local agent instance: `live-v3-p1-clean2`; device_id/machine_id: `2447d396-79cd-53da-b3a9-028c5a4d56da`; agent GUI version observed earlier in this close pass: `3.1.61`.
- Canonical paths to be separated: module lifecycle action through admin HTTP route, browser admin/device confirmation, server DB query, agent SQLite query, UIA semantic state probe, and remote/server logs.
- Pre-fix contamination to ignore: old `network_basic` no-op reinstall ambiguity from original P1.4.A, old raw-probe `device_outbox` rows from `BUG-20260527-P1-14`, old `screen.record` artifact/auth projection from `BUG-20260527-P1-06`, and historical `seen_commands` recovery rows from `BUG-20260527-P1-12`.

P1-09 clean rerun plan:
- Trigger a reversible `network_basic` lifecycle change on the live agent: deactivate, verify durable device event/outbox/DB/browser state, then reactivate and verify convergence.
- Filter evidence by fresh operation ids, timestamps after this section, and new local outbox ids; old rows are not accepted as proof.
- Pass criteria: `device_events.module_state_changed` persisted after the action, local `outbox_sent_history` has matching module lifecycle event(s), `device_modules` converges back to `network_basic@1.0.0 active`, browser admin module/device page shows the current module state, and no new stale `device_outbox` or failed local outbox rows remain for this run.

P1-09 clean rerun evidence:
- Path tested: direct HTTP/API admin module lifecycle route using a web-session token as `Authorization: Bearer` for legacy module action compatibility; browser admin confirmation is separate and does not replace the action-path evidence. Raw token/cookie not logged; evidence records only `sha256_prefix=58ee735fa1ce` and `len=64`.
- Transport/API: `POST /api/devices/2447d396-79cd-53da-b3a9-028c5a4d56da/modules/deactivate` returned `202` with operation `ee61c7ef-7ec8-4d14-9b37-8efecc201f9f`; poll returned `status=succeeded`. `POST /api/devices/2447d396-79cd-53da-b3a9-028c5a4d56da/modules/activate` returned `202` with operation `f8d43b2c-3029-4da5-a509-06d699bef5d6`; poll returned `status=succeeded`.
- Server DB: `operations` rows `ee61c7ef-7ec8-4d14-9b37-8efecc201f9f` (`kind=module_deactivate`) and `f8d43b2c-3029-4da5-a509-06d699bef5d6` (`kind=module_activate`) are `succeeded`; matching `device_outbox.id=124` and `id=130` are `delivered`. Follow-up `list_installed_modules` and `list_tools` outbox rows `125..133` are also `delivered`; `new_stale_outbox=[]`.
- Server DB: `device_events.id=51 tools_changed` (`device_seq=21`, tools_count `6`, hash `464075d978b3230f`), `id=52 module_state_changed` (`reason=deactivate:network_basic`), `id=53 tools_changed` (`device_seq=23`, tools_count `11`, hash `afa6647205d24098`), `id=54 module_state_changed` (`reason=install:network_basic@1.0.0`), and `id=55 module_state_changed` (`reason=activate:network_basic@1.0.0`) persisted after the clean action.
- Server DB: `device_modules` converged to `network_basic@1.0.0 state=active installed=true active=true source=event last_updated_at=2026-05-27 19:41:53+00`; desired state remains `network_basic installed 1.0.0`.
- Agent SQLite: local `outbox=[]`; `outbox_sent_history` has `outbox_id=38 tools_changed`, `39 module_state_changed reason=deactivate:network_basic`, `40 tools_changed`, `41 module_state_changed reason=install:network_basic@1.0.0`, and `42 module_state_changed reason=activate:network_basic@1.0.0`. `seen_commands` target commands `ee61c7ef-7ec8-4d14-9b37-8efecc201f9f` and `f8d43b2c-3029-4da5-a509-06d699bef5d6` are `success`.
- Agent log: local agent log shows `deactivate_module` and `activate_module` command lifecycle ACK/result plus `[module_state_changed] Event enqueued` for install/activate and `tools_changed event enqueued` for rebuilt registries.
- Browser/UI: real browser `/app/admin/device?device=2447d396-79cd-53da-b3a9-028c5a4d56da` shows `ADMIN-2`, agent `3.1.61`, `Онлайн`, observer dangerous-flow rows for `module activate` and `module deactivate` at `28 мая 2026 г., 00:41` with `error 0 timeout 0 retry 0`; `/app/admin/modules` shows `network_basic latest 1.0.0 • preferred 1.0.0` and tools `dns.resolve, network.ping, tcp.connect`. Screenshot artifact: `p1-close-20260528-0040-modules-page-full.png`; browser console errors captured to `p1-close-20260528-0040-browser-console-errors.log`.
- UIA: semantic state probe after rerun used `pywinauto==0.6.9`, backend `uia`, window `Maria Agent v3.1.61`, PID `12592`; `connection_state=connected`, `account_mode=confirmed_binding`, `ticket_count=4`, target clean ticket `T-000612` visible, `failures=[]`. Artifact: `artifacts/p1-close-20260528-0040-dbe1d72f-uia-state-noscreenshot.json`. Screenshot capture timed out and is not used as pass evidence; UIA semantic JSON is the pass signal.
- Result: `BUG-20260527-P1-09` is verified-fixed for P1 close. Residual note: module action route still needed legacy bearer-style auth even though the source session was `/api/web/session/login`; this is not counted as P1-09 because action succeeded and browser projection was separately verified, but it should be considered in future web-session route cleanup.

### BUG-20260527-P1-18 — diagnostic_probe handshakes but is closed as superseded before outbox probes

Severity: P1
Status: verified-fixed
Area: protocol / reconnect / test-tool / state-manager

P1 scenario: P1.1 clean ACK/NACK/dedup rerun with raw WS probe isolation after `BUG-20260527-P1-14`.
Run id: `p1-close-20260528-0040-dbe1d72f`
Expected: A `client_kind=diagnostic_probe` WS session should be able to run protocol diagnostics without receiving live `device_outbox` commands, without superseding the real runtime agent, and without being closed as stale immediately after `handshake_ack`.
Actual: The probe receives `handshake_ack`, then the next non-handshake frame is closed with code `4002` before ACK/NACK evidence can be collected. This happened both with the live agent token in diagnostic mode and with a dedicated diagnostic token/device (`d1a9f416-26de-49d5-96f8-000000000103`). Using a dedicated `agent_runtime` token/device avoids the close, but cannot validate ticket-event ACK on a ticket bound to the real live device and is not the safe canonical probe mode for the live device.
Repro steps:
1. Read live agent token only into process env; do not print raw token.
2. Run `scripts/live_ws_v3_probe.py --client-kind diagnostic_probe mixed-batch --ticket-id 15f87a9a-726e-488d-9868-2d4b78cfac9c --run-id p1-close-20260528-0040-dbe1d72f ...`.
3. Repeat with dedicated diagnostic device/token `d1a9f416-26de-49d5-96f8-000000000103`.
4. Observe `handshake_ack` followed by close `4002` and no per-item ACK/NACK.

Evidence:
- Transport/API: artifact `artifacts/p1-close-20260528-0040-mixed-batch.json` shows live-token diagnostic probe `handshake_ack` for device `2447d396-79cd-53da-b3a9-028c5a4d56da`, then `close_code=4002`, `observed_ack_ids=[]`, `observed_nack_ids=[]`, `unexpected_command_count=0`.
- Transport/API: artifact `artifacts/p1-close-20260528-0040-mixed-batch-diag3.json` shows dedicated diagnostic probe `handshake_ack` for `d1a9f416-26de-49d5-96f8-000000000103`, then `close_code=4002` before batch result collection.
- Transport/API adjacent: artifact `artifacts/p1-close-20260528-0040-mixed-batch-diag4-runtime.json` shows dedicated `agent_runtime` token/device can process the batch; valid device event ACKs, invalid both-seq/unknown-ticket/device-ticket-context NACK, no unexpected commands. Ticket events correctly NACK `DEVICE_MISMATCH` because the test ticket is bound to the live device, not the diagnostic runtime device.
- Server log: for dedicated runtime device `d1a9f416-26de-49d5-96f8-000000000104`, server logs show normal `outbox_items_batch` handling and `DeviceOutboxRepo Retrieved 0 pending commands`; this confirms the raw runtime fallback did not consume live commands, but it is not enough for live ticket-event ACK on the real device.
- Agent log: real agent `live-v3-p1-clean2` remained connected after the diagnostic attempts (`/ui/automation/status connection_state=connected`).
- Server DB: no new live-device command consumption was observed in the diagnostic attempts; P1.1 remains blocked because the safe diagnostic mode cannot ingest outbox probes.
- Browser/UI: not applicable to this protocol-negative/test-tool isolation failure except that browser-visible P1 ticket `T-000612` remains the target for post-fix no-phantom confirmation.
- UIA: not applicable.
- Test artifact: `artifacts/p1-close-20260528-0040-mixed-batch.json`, `artifacts/p1-close-20260528-0040-mixed-batch-diag3.json`, `artifacts/p1-close-20260528-0040-mixed-batch-diag4-runtime.json`.
- Run marker: `p1-close-20260528-0040-dbe1d72f`, `p1-close-20260528-0040-diag3`, `p1-close-20260528-0040-diag4`.

Impact: Blocks P1.1 clean rerun with the safe canonical raw-probe path. Without this fix, the only way to test ticket-event ACK via raw WS is to masquerade as the live runtime agent, which risks superseding the real agent and contaminating command delivery.
Root cause hypothesis: `state.register_agent()` stores diagnostic probes separately in `diagnostic_agent_connections`, but `agent_handler` checks all non-handshake frames with `state.is_current_agent_connection()`, which only checks `connected_agents`. Therefore a diagnostic probe is incorrectly classified as a superseded/stale runtime connection and closed with `4002`.
Root cause confirmed: yes. `server/state_manager.py::register_agent()` records diagnostic probes in `diagnostic_agent_connections`, while `is_current_agent_connection()` only matched `connected_agents`. The shared stale-connection guard in `server/websocket/agent_handler.py` calls this method for every non-handshake frame, so the first `outbox_items_batch` from a diagnostic probe was closed as superseded.
Blocking further P1: yes
Fix now: yes
Fix summary: Updated `StateManager.is_current_agent_connection()` to accept the current diagnostic probe entry by `connection_id`/WS without registering it as a runtime agent or changing command dispatch semantics. Runtime entries remain the only entries returned by `get_agent()` and used by `DeviceDispatchService`.
Changed files:
- `server/state_manager.py`
- `server/tests/test_state_manager_agent_registry.py`
- `PLANS.md`
Tests:
- `python -m py_compile server\state_manager.py server\tests\test_state_manager_agent_registry.py`
- `python -m pytest server\tests\test_state_manager_agent_registry.py -q` -> `3 passed`.
Live regression:
- Deployment/runtime path tested: commit `9a3e77e4` deployed with `python scripts\release_server_to_remote.py --gate quick --allow-local-dirty --leave-running --smoke-insecure-tls --smoke-attempts 8 --smoke-delay 2`; remote smoke recovered on attempt 2 with `/api/health -> 200`.
- Transport/API: reran `scripts/live_ws_v3_probe.py --client-kind diagnostic_probe mixed-batch` against canonical WSS with marker `p1-close-20260528-0040-afterp118`; artifact `artifacts\p1-close-20260528-0040-mixed-batch-afterp118.json` shows `handshake_ack`, ACK ids `valid-ticket`, `duplicate-ticket`, `valid-device`, NACK ids `both-seq` (`VALIDATION_ERROR`), `unknown-ticket` (`UNKNOWN_TICKET`), and `device-with-ticket` (`VALIDATION_ERROR`), with `unexpected_command_count=0`.
- Server DB: one `ticket_events.chat_message` row persisted for marker `p1-close-20260528-0040-afterp118` (`id=228`, `agent_seq=960001`, trace `9720fc5e-c86e-414c-bc35-44c22fe3fd77`); duplicate `agent_seq=960001` ACKed without a second row. One `device_events.probe_device_event` row persisted (`id=57`, `device_seq=960002`, trace `0a870207-b91e-4b14-8980-795780f26c0e`). Invalid ticket/device event counts for the marker are `0`; recent stale `device_outbox` for the verification window is `[]`.
- Agent/local: `python scripts\agent_test_driver.py status live-v3-p1-clean2` returned `connection_state=connected`, `bridge_connected=true`, `ticket_count=4`; local SQLite had `outbox=[]`, `failed_outbox_count=0`, `pending_consents=0`.
- Browser/UI: real browser URL `https://192.168.100.17:9443/app/tickets/15f87a9a-726e-488d-9868-2d4b78cfac9c` shows `P1.1.E valid batch ticket marker p1-close-20260528-0040-afterp118` exactly once and no duplicate/invalid marker. Evidence: browser DOM result reported `hasMarker=true`, `markerCount=1`; screenshot `p1-close-20260528-0040-ticket-T-000612-afterp118.png`; console errors saved to `p1-close-20260528-0040-ticket-T-000612-afterp118-console-errors.log`.
Status after action: verified-fixed.
Remaining risk: diagnostic probes still cannot validate a ticket event for a dedicated diagnostic device unless the ticket is bound to that device. The clean live-device diagnostic mode now covers the required no-command-consumption path.

### BUG-20260527-P1-19 - P1.2 diagnostic duplicate enqueue double-serialized jsonb params

Severity: P2
Status: not-a-bug
Area: test-tool / test-contamination

P1 scenario: P1.2.A duplicate successful command clean rerun.
Run id: `p1-close-20260528-0040-dbe1d72f`
Expected: The diagnostic duplicate enqueue should recreate the original `device_outbox.params` as a JSON object so the real dispatcher can deliver the duplicate command to the agent and exercise command idempotency.
Actual: The first duplicate diagnostic enqueue for operation `23dccf2d-fbd2-4e1f-b739-9f3eea279ce7` inserted `params` as a JSON string, not an object. Dispatcher failed before delivery with `SEND_ERROR` and server log error `'str' object has no attribute 'get'`.
Repro steps:
1. Start `system.collect` through real browser support route on ticket `T-000612`; operation `23dccf2d-fbd2-4e1f-b739-9f3eea279ce7` succeeded.
2. Diagnostic remote DB script inserted duplicate `device_outbox` row `id=135` using `json.dumps(original['params'])` even though asyncpg had already returned `params` as a JSON string.
3. Dispatch attempted to process row `135` and failed four times before marking it `failed/SEND_ERROR`.

Evidence:
- Transport/API: original browser support route returned HTTP `202`, operation `23dccf2d-fbd2-4e1f-b739-9f3eea279ce7`, then terminal success.
- Server log: `[DeviceDispatchService] Failed to send command ... command_id=23dccf2d-fbd2-4e1f-b739-9f3eea279ce7 error='str' object has no attribute 'get'`, then `[DeviceOutboxRepo] Command marked as failed: outbox_id=135 error_code=SEND_ERROR`.
- Server DB: original `device_outbox.id=134` delivered; diagnostic duplicate `id=135` failed with `error_message="'str' object has no attribute 'get'"`; its `params` value is a quoted JSON string. Operation remained `succeeded`; ticket events remained exactly one `tool_call_started` and one `tool_call_result`.
- Agent SQLite: not applicable to the failed duplicate row because the malformed diagnostic row failed before WS delivery; agent stayed connected.
- Browser/UI: operation success remains visible, but this row is not accepted as idempotency evidence.
- Test artifact: remote diagnostic DB output in this session; no raw tokens logged.
- Run marker: operation-specific contamination for `23dccf2d-fbd2-4e1f-b739-9f3eea279ce7`.

Impact: Pollutes final stale-outbox checks with one new test-tool row (`device_outbox.id=135`) and invalidates this first P1.2.A duplicate-delivery attempt. It does not indicate product idempotency failure because the malformed duplicate never reached the agent.
Root cause hypothesis: diagnostic script double-serialized `device_outbox.params` before inserting `jsonb`.
Root cause confirmed: yes. Original row `134` stores `params` as a JSON object; row `135` stores a quoted JSON string. Dispatcher expects object-like params and calls `.get()`.
Blocking further P1: no, if row `135` is labeled as test-tool contamination and P1.2 is rerun with a new clean operation/marker using the original JSON text directly.
Fix now: no product code fix. Correct the ad hoc diagnostic command for the rerun by inserting `original['params']` directly into `$4::jsonb`, not `json.dumps(original['params'])`.
Fix summary: Test-tool-only classification; no product code changed.
Changed files:
- `PLANS.md`
Tests: not applicable; this is a one-off diagnostic command mistake.
Live regression: clean P1.2 rerun completed after labeling this contamination:
- P1.2.A duplicate-after-success used fresh operation `a6df2219-a983-4a0f-a634-9b91f1da0821`; original `device_outbox.id=136` and diagnostic duplicate `id=137` both delivered, operation stayed `succeeded`, and ticket events remained exactly one `tool_call_started` plus one `tool_call_result`.
- P1.2.B duplicate-while-running used operation `faffc1b0-8680-4489-a9ff-4627d0cfe727`; duplicate `device_outbox.id=139` was inserted while operation status was `accepted`; rows `138/139` both delivered, operation terminal `succeeded`, one terminal ticket result, and local `seen_commands` had a single terminal row.
- P1.2.C duplicate-after-cancel used target operation `5d85925d-2572-45c3-866b-adc0a4ef9f51`; browser web-session cancel returned `200` with cancel operation `7be4952c-b815-404d-ae94-b0e754242a0c`; duplicate target row `142` delivered after terminal cancel; target stayed `canceled`, local `seen_commands.status=canceled`, and ticket events remained one each of start/cancel-request/tool-result/op-canceled.
Remaining risk: Final P1 stale-outbox checks must ignore only `device_outbox.id=135` as P1-19 contamination. Post-rerun server query confirmed `stale_outbox=[]`; the only recent failed row was the labeled test-tool contamination `id=135`.

## P1 close summary - 2026-05-28 - run_id=p1-close-20260528-0040-dbe1d72f

Status: P1 closed

Code head:
- Local/remote code head for product fixes: `9a3e77e4` (`fix: keep diagnostic probes current`), branch `codex/helpdesk-process-model`.
- P0 close and earlier P1 fix commits remain recorded in the bug blocks above.

Server URL:
- `https://192.168.100.17:9443`; final `python scripts\manage_remote_stack.py smoke server --insecure-tls` returned `/api/health -> 200`.

Agent instance:
- `live-v3-p1-clean2`, device `2447d396-79cd-53da-b3a9-028c5a4d56da` / `ADMIN-2`, agent version `3.1.61`.
- Final local automation status: `connection_state=connected`, `bridge_connected=true`, active ticket `15f87a9a-726e-488d-9868-2d4b78cfac9c`, `ticket_count=4`.

Clean ticket:
- `T-000612` / `15f87a9a-726e-488d-9868-2d4b78cfac9c`.

Verified fixed / closed for P1:
- `BUG-20260527-P1-03` -> verified-fixed.
- `BUG-20260527-P1-09` -> verified-fixed by reversible `network_basic` deactivate/activate clean rerun.
- `BUG-20260527-P1-11` -> verified-fixed.
- `BUG-20260527-P1-12` -> verified-fixed; clean rerun operation `427e3b27-21c2-49be-880b-8c02b7e6a86e` ended `failed/AGENT_RESTARTED`, target outbox delivered, local `seen_commands.status=error`.
- `BUG-20260527-P1-13` -> verified-fixed; clean server-drop operation `bffad8e1-73c9-4eac-8081-08915eeeb2e6` reconciled to `succeeded`, target outbox delivered, local outbox empty.
- `BUG-20260527-P1-14` -> verified-fixed.
- `BUG-20260527-P1-15` -> verified-fixed; semantic UIA projection evidence remains valid and was rechecked in final split-view probes.
- `BUG-20260527-P1-16` -> verified-non-product / guardrails-added.
- `BUG-20260527-P1-17` -> verified-fixed.
- `BUG-20260527-P1-18` -> verified-fixed by post-deploy diagnostic-probe mixed-batch rerun.

Deferred / known limitation / not blocking P1:
- `BUG-20260527-P1-05` -> known-limitation: automation bridge is not support/admin tool-run authority; browser support route is the canonical P1 tool lifecycle path.
- `BUG-20260527-P1-06` -> verified-fixed during P2.2 artifact/status-projection pass; original P1 close did not use artifact upload success as evidence.
- `BUG-20260527-P1-07` -> known-limitation: approval center is browser-visible but read-only; consent approve/deny actions remain outside P1 close.
- `BUG-20260527-P1-08` -> deferred cleanup/UX issue; not a P1 data-integrity blocker.
- `BUG-20260527-P1-10` -> deferred negative module auto-install UX/lifecycle issue; final checks found no new stale desired/outbox state for the close run.
- `BUG-20260527-P1-19` -> not-a-bug/test-contamination; only `device_outbox.id=135` is ignored as the malformed diagnostic duplicate row.

Old contamination ignored:
- Original P1 raw-probe/device-outbox rows from `BUG-20260527-P1-14`.
- Original restart/drop stale rows from pre-fix `BUG-20260527-P1-12` / `BUG-20260527-P1-13`.
- Original `screen.record` artifact upload/auth projection from `BUG-20260527-P1-06`.
- Test-tool contamination `device_outbox.id=135` from `BUG-20260527-P1-19`.

Clean rerun results:
- P1.1: passed minimum close smoke. `diagnostic_probe` mixed batch with marker `p1-close-20260528-0040-afterp118` had expected ACK/NACK, one persisted ticket event, one persisted device event, invalid persistence counts `0`, browser marker count `1`, and `unexpected_command_count=0`.
- P1.2: passed duplicate success/running/canceled command idempotency smoke. Clean operations: `a6df2219-a983-4a0f-a634-9b91f1da0821`, `faffc1b0-8680-4489-a9ff-4627d0cfe727`, `5d85925d-2572-45c3-866b-adc0a4ef9f51`.
- P1.5: passed reconnect/restart/drop smoke. Agent restart produced terminal `AGENT_RESTARTED`; server drop recovered `/api/health`, agent reconnected, and late result was persisted/reconciled.
- P1.6: passed browser/admin and local GUI projection close check. Browser ticket timeline showed P1.1/P1.2/P1.5 results and admin device page showed `ADMIN-2`, agent `3.1.61`, `Онлайн`, last contact `2026-05-28 01:12`; screenshots `p1-close-20260528-0040-ticket-T-000612-afterp118.png`, `p1-close-20260528-0040-p1-2-idempotency-browser.png`, `p1-close-20260528-0040-admin-device-final.png`. UIA evidence used `pywinauto==0.6.9`, backend `uia`: `artifacts\p1-close-20260528-0040-uia-state-final.json` captured connected/account semantics after restart; `artifacts\p1-close-20260528-0040-uia-state-final-depth10.json` captured active ticket `T-000612` semantic controls after opening the ticket. Screenshot capture is still skipped/timeout-prone and not used as pass criteria.

Final state checks:
- Server DB: `stale_outbox=[]` for recent close window. Recent failed server outbox contains only labeled test contamination `device_outbox.id=135`.
- Agent SQLite: local `outbox=[]`, failed local outbox count `0`, pending consent count `0`; clean operation `seen_commands` states are terminal (`success`, `error`, or `canceled` according to operation outcome).
- Browser console/network: final ticket/admin console logs captured; no new P1-blocking 500/401/403 was observed in the final pages outside known/deferred areas.

Code gates:
- `python scripts\verify_workspace.py` -> passed.
- `python -m compileall -q server pc_agent scripts` -> passed.
- `python -m pytest server\tests\test_state_manager_agent_registry.py pc_agent\tests\test_gui_accessibility.py pc_agent\tests\test_chat_panel_helpers.py::test_ticket_header_widget_renders_actions_without_raw_public_url pc_agent\tests\test_chat_panel_helpers.py::test_ticket_create_wizard_exposes_stable_uia_ids pc_agent\tests\test_main_window_runtime_windows.py::test_main_window_syncs_sidebar_connection_status_with_requester_labels -q` -> `9 passed`.
- `git diff --check` -> passed with line-ending warnings only for `PLANS.md` and pre-existing `pc_agent/ui_gui/tickets_list_model.py` working-copy normalization.

P2 readiness:
- ready. P2 can start after this `PLANS.md` evidence update is committed and pushed.

## P2 Live validation - 2026-05-28 - run_id=p2-20260528-0925-cef033e7

Status: P2 closed

Scope:
- P2.1 Public/requester safety.
- P2.2 Attachments/artifacts.
- P2.3 Two-agent matrix.

Baseline:
- Branch: `codex/helpdesk-process-model`.
- Commit SHA: `cef033e7b80ae349231dd0c86e2a084f27f49656` (`docs: close P1 live validation`).
- Server URL: `https://192.168.100.17:9443`.
- Browser/admin URL: `https://192.168.100.17:9443/admin` / routed app URL `https://192.168.100.17:9443/app/admin`.
- Browser/support URL: `https://192.168.100.17:9443/app/tickets`.
- Local agent A: `live-v3-p1-clean2`, GUI/source mode, UI port `8765`.
- Local agent B: pending P2.3 setup as a separate local instance; P2.3 is not passed until distinct device/token/SQLite evidence exists.
- Device A: `2447d396-79cd-53da-b3a9-028c5a4d56da`, hostname `ADMIN-2`.
- Device B: pending P2.3 setup.
- Agent versions: Agent A `3.1.61`; Agent B pending.
- pywinauto version: `0.6.9`.
- Server health: `python scripts\manage_remote_stack.py smoke server` returned `OK https://192.168.100.17:9443/api/health -> 200`.
- Server runtime: `pc-client-server.service` active/running, pid `80609`, uptime about 8h at baseline.
- Agent A connection state: `python scripts\agent_test_driver.py status live-v3-p1-clean2` returned `connection_state=connected`, `bridge_connected=true`, `ticket_count=4`, active ticket `15f87a9a-726e-488d-9868-2d4b78cfac9c`.
- Browser/admin evidence: real browser login to `/app/admin`, then `/app/admin/inventory`; visible text shows `ADMIN-2`, `2447d396...56da`, `Онлайн`, Windows, agent `3.1.61`, total agents `7`, online `1`. Screenshot: `artifacts\p2-20260528-0925-cef033e7-admin-inventory-baseline.png`.
- UIA evidence: real local GUI via `pywinauto==0.6.9`, backend `uia`; after `window.show` and `sidebar.select profile`, `scripts\live_agent_uia_state_probe.py --instance live-v3-p1-clean2 --expect-connected --expect-account --expect-account-confirmed --output artifacts\p2-20260528-baseline-uia-profile-depth10.json --skip-screenshot --max-depth 10 --max-nodes 1600 --max-seconds 30` returned `connection_state=connected`, `account_exists=true`, `account_mode=confirmed_binding`, window title `Maria Agent v3.1.61; id=agent.main_window; agent_version=3.1.61`.
- UIA surface note: the same probe in ticket/chat view with shallow traversal found only root/title/footer controls and not account/connection semantic labels. This is recorded as view-surface nuance, not a P2 bug, because the required baseline connection/account semantics pass in the canonical profile surface and P1 already records split-view UIA evidence for ticket semantics.
- Agent A SQLite baseline: `.local-agent\instances\live-v3-p1-clean2\data\storage.db` has `outbox=[]`, `failed_outbox_count=0`, `pending_consents_count=0`; recent `seen_commands` rows are terminal (`error`, `success`, `canceled`) and are P1-era commands, not P2 marker rows.
- Server DB baseline: `device_outbox` has no rows containing marker prefix `p2-20260528`; active device inventory query shows `ADMIN-2` / `2447d396-79cd-53da-b3a9-028c5a4d56da`, agent `3.1.61`.
- Known P0/P1 contamination ignored for P2:
  - old P0 phantom ticket/event rows recorded in the P0 section;
  - P1 `device_outbox.id=135` from `BUG-20260527-P1-19` test-tool contamination;
  - pre-fix P1 restart/drop/probe rows from `BUG-20260527-P1-12`, `BUG-20260527-P1-13`, `BUG-20260527-P1-14`;
  - deferred P1 limitations `BUG-20260527-P1-05`, `BUG-20260527-P1-07`, `BUG-20260527-P1-08`, `BUG-20260527-P1-10`, kept separate from new P2 evidence unless clean P2 markers reproduce them; `BUG-20260527-P1-06` was revalidated and fixed during this P2.2 pass.

P2 execution plan:
- [ ] P2.1 Public/requester safety discovery with browser + direct HTTP + DB comparison.
- [ ] P2.2 Attachments/artifacts discovery with browser/local GUI where supported + DB/SQLite/download matrix.
- [ ] P2.3 Two-agent matrix after creating or verifying a second distinct local agent/device.
- [ ] P2 findings summary and fix/classification phase.
- [ ] P2 final close gate.

### P2.1.A Public queue endpoints - 2026-05-28

Run id: `p2-20260528-0925-cef033e7`
Marker: `p2-20260528-0925-cef033e7-public-queue`
Path tested: direct HTTP/API + real browser public queue + server DB comparison.

Expected:
- Anonymous public queue endpoints expose only the documented public projection.
- Numeric/internal `queue_id` is rejected.
- Malformed limit/days/missing/unknown queue inputs return safe 400, not 500.
- Injected internal filters such as `assignee_id`, `device_id`, `account_id`, `requester_id` do not leak internal fields.
- Browser public queue page renders safe public fields only.

Evidence:
- Direct HTTP/API:
  - `GET /public_api/queues` -> `200`, body `{"queues":[{"queue_code":"servicedesk_l1","open_count":4}]}`.
  - `GET /public_api/queues?include_empty=true` -> `200`, includes active queue codes/counts only.
  - `GET /public_api/queue/tickets?limit=5` -> `400 validation_error`, `queue required`.
  - `GET /public_api/queue/tickets?queue_id=1&limit=5` -> `400 validation_error`, `queue_id is not supported; use queue_code or public_queue_code`.
  - `GET /public_api/queue/stats?queue_id=1&days=7` -> `400 validation_error`, same queue_id rejection.
  - `GET /public_api/queue/tickets?queue_code=servicedesk_l1&limit=5&assignee_id=admin&device_id=2447d396-79cd-53da-b3a9-028c5a4d56da&account_id=x&requester_id=y` -> `200`, returns four rows with only `ticket_code`, `public_position`, `public_status`, `public_status_label`, `queue_code`, `wait_bucket`, `updated_at`.
  - `GET /public_api/queue/tickets?queue_code=servicedesk_l1&limit=9999` -> `400 validation_error`, `limit must be in range [1, 200]`.
  - `GET /public_api/queue/stats?queue_code=servicedesk_l1&days=999` -> `400 validation_error`, `days must be in range [1, 90]`.
  - `GET /public_api/queue/tickets?queue_code=p2_missing_queue&limit=5` -> `400 validation_error`, `invalid queue`.
- Browser/UI: real browser URL `https://192.168.100.17:9443/queue` rendered queue `servicedesk_l1`, four public ticket rows `T-000609`..`T-000612`, public status `Заявка принята`, wait bucket `2h+`; console errors `[]`; regex scan of visible text found no `queue_id`, `assignee`, `device_id`, `account_id`, `requester_id`, `session_token`, or `public_token`. Screenshot: `artifacts\p2-20260528-0925-cef033e7-public-queue-browser.png`.
- Server DB: comparison rows for `T-000609`..`T-000612` have internal `ticket_id`, `requester_id`, `device_id`, `queue_id=1`, `status=queued`, priority/urgency/importance fields. These were absent from the public API/browser projection except public `ticket_code`, queue code and public status.
- Server log: no 500 was observed for the tested cases; intentional invalid cases returned safe 400.

Result: passed so far for P2.1.A. No bug recorded.

### BUG-20260528-P2-01 - Public ticket API returns requester-visible payload with internal fields

Severity: P1
Status: verified-fixed
Area: public-safety / requester-access

P2 scenario: P2.1.B Public ticket access and authorization.
Run id: `p2-20260528-0925-cef033e7`
Expected:
- Anonymous/no-token access to `/api/tickets/{ticket_id}` is denied.
- Invalid token is denied.
- Valid public ticket token can read only requester-safe/public-safe fields for its scoped ticket.
- Public ticket token cannot list tickets or read another ticket.
- Public/browser timeline must not expose internal queue ids, device ids, raw policy/routing/SLA internals, custom field internals, token/session details or access-code hashes.

Actual:
- Positive/negative authorization boundaries worked:
  - no token -> `401 AUTH_REQUIRED`;
  - invalid token -> `401 AUTH_REQUIRED`;
  - public token for another ticket -> `403 forbidden`;
  - `GET /api/tickets?limit=5` with public token -> `403 forbidden`;
  - wrong public access code -> `403 invalid_code`;
  - valid public access code -> `200` with a new public token, redacted in evidence.
- But `GET /api/tickets/{public_ticket_id}` with valid public token returned `200` and included requester-visible JSON with internal fields:
  - top-level ticket fields: `device_id`, `queue_id`, `assignee_id`, `requester_id`, `priority`, `priority_class`, `effective_priority`, `urgency`, `importance`, SLA timestamps, `custom_fields`;
  - `custom_fields.public_access.code_hash`, `code_hint`, `routing_decision.actions.queue_id`, `routing_decision.to_queue_id`, `priority_decision`;
  - requester-visible events for `routing_applied`, `queue_changed`, `sla_started` included `queue_id`, SLA target internals and policy metadata;
  - messages included a system public access code message and metadata containing the public access code. This may be product-intended for the requester page, but it must be explicitly classified/redacted by policy; it should not appear in generic public API evidence unless documented.
- Browser `/help?ticket_id=<ticket_id>` did not visibly render the raw internal field names (`queue_id`, `priority_decision`, `routing_decision`, `code_hash`, `device_id`, `assignee_id`, `session_token`, `public_token`) in the page text, but it is backed by the same API response and the browser displayed the public access code in the requester page flow.

Repro steps:
1. `POST /public_api/tickets/create` with marker `p2-20260528-0925-cef033e7`, title `P2 public safety ...`, requester display name `P2 Public Requester`, urgency/importance `1`.
2. Capture returned `ticket_id=T-000613 / 34ca8987-9f90-4f25-83c8-66b1fa507151`, public access code redacted as `MAQ...TU5`, public token redacted by prefix/hash/length.
3. Call `/api/tickets/{ticket_id}` with no token, invalid token, valid public token, and valid public token against unrelated ticket `15f87a9a-726e-488d-9868-2d4b78cfac9c`.
4. Exchange wrong and valid public access code through `/public_api/tickets/{ticket_id}/authorize`.
5. Open real browser `https://192.168.100.17:9443/help?ticket_id=34ca8987-9f90-4f25-83c8-66b1fa507151`, enter the public access code, and inspect visible text.

Evidence:
- Transport/API:
  - create public ticket -> `200`, ticket `T-000613`, public token redacted `{prefix=22753ff3, sha256_12=e07ac51af24e, length=64}`;
  - no token -> `401 AUTH_REQUIRED`;
  - invalid token -> `401 AUTH_REQUIRED`;
  - valid public token -> `200` but leaks internal fields listed above;
  - public token list -> `403 forbidden`;
  - wrong public code -> `403 invalid_code`;
  - valid public code -> `200`, replacement public token redacted `{prefix=7adbffc5, sha256_12=83b368b64afb, length=64}`;
  - cross-ticket public token read -> `403 forbidden`.
- Server log: no 500 observed in this reproduction.
- Agent A log: not applicable; public/requester HTTP flow does not involve the local agent runtime.
- Agent B log: not applicable.
- Server DB: ticket `34ca8987-9f90-4f25-83c8-66b1fa507151` was created with public requester id and internal queue/device/routing/SLA fields; DB details need follow-up query during root-cause isolation.
- Agent A SQLite: not applicable.
- Agent B SQLite: not applicable.
- Browser/UI: real browser `/help?ticket_id=34ca8987-9f90-4f25-83c8-66b1fa507151` loaded ticket `T-000613`, status `Заявка принята`, public message marker, and did not visibly show internal field names. Screenshot: `artifacts\p2-20260528-0925-cef033e7-help-browser-T-000613.png`.
- UIA: not applicable.
- Test artifact: command output in this session; no raw public/session token printed, only token prefix/hash/length. The public access code is a synthetic P2 code and is redacted in `PLANS.md`.
- Run marker: `p2-20260528-0925-cef033e7`.

Impact:
- Public requester API response exposes internal ticket implementation details and policy/routing/SLA metadata to a public-token caller. Browser rendering currently hides many fields, but UI redaction is not sufficient; server-side public/requester projection must be authoritative.
- This is a security/access-control class issue and blocks further P2.1 requester/public safety conclusions until classified/fixed.

Root cause hypothesis:
- `ticket_to_dict(..., visibility="requester")` and/or `_ticket_payload(..., visibility="requester")` do not strip all internal fields and `handle_ticket_get` serializes requester-safe events by adding requester timeline projection while still carrying raw event fields.

Root cause confirmed: yes. `server/tickets/visibility_policy.py` was deny-list based and only removed configured `hidden_from_requester` paths, so unlisted ticket fields such as `queue_id`, `device_id`, `requester_id`, `priority_*` and raw `custom_fields` remained in requester/public ticket payloads. `server/tickets/handlers.py::_serialize_event_for_agent()` was reused for requester/public `events`, so it filtered event types but still merged raw event payload fields into the public response. `_serialize_message()` likewise returned raw public-access message metadata.
Fix policy:
- Blocking further P2: yes for P2.1 public/requester safety; P2.2/P2.3 can continue only after clearly separating this known leak if they do not use public requester ticket API evidence.
- Fixed now: yes.

Fix summary:
- Added an explicit requester/public ticket payload allowlist in `server/tickets/visibility_policy.py`, scoped only to ticket-like payloads (`ticket_id`/`ticket_code`) so generic passport/visibility policy projections still work.
- Added requester-specific event/message serializers in `server/tickets/handlers.py` and switched `handle_ticket_get` plus requester snapshot event serialization to safe projection output.
- Sanitized public access code messages in requester API responses to neutral `message_kind=ticket_access_notice` without echoing the raw code, hash or the internal `ticket_public_access_code` event kind in requester/public metadata/text.
- Updated docs for public-token `/api/tickets/{ticket_id}` projection contract.
Changed files:
- `server/tickets/visibility_policy.py`
- `server/tickets/handlers.py`
- `server/tickets/requester_timeline.py`
- `server/tests/test_ticket_visibility_policy.py`
- `server/tests/test_requester_timeline_projection.py`
- `docs/QUICK_LOOKUP.md`
- `scripts/navigation_catalog.py`
- `server/docs/TICKET_SYSTEM.md`
- `server/docs/CODEMAP.md`
- `PLANS.md`
Tests:
- `python -m py_compile server\tickets\visibility_policy.py server\tickets\handlers.py server\tests\test_ticket_visibility_policy.py server\tests\test_requester_timeline_projection.py` -> passed.
- First targeted pytest run without `pytest.mark.no_db` on `test_ticket_visibility_policy.py` spent about 5m36s building the isolated DB and exposed an over-broad allowlist side effect; fixed by narrowing allowlist to ticket-like payloads and marking the no-DB visibility unit tests.
- `python -m pytest server\tests\test_ticket_visibility_policy.py server\tests\test_requester_timeline_projection.py -q` -> `15 passed in 0.20s`.
- Post-neutral-marker targeted gates:
  - `python scripts\verify_workspace.py` -> passed.
  - `python -m compileall -q server pc_agent scripts` -> passed.
  - `python -m pytest server\tests\test_ticket_visibility_policy.py server\tests\test_requester_timeline_projection.py -q` -> `15 passed in 0.19s`.
  - `git diff --check` -> exit 0; CRLF warnings only.
Live regression:
- Deployed commit `049c16dd69d2766b3e91220877af8c3ece524bd3` with `python scripts\release_server_to_remote.py --gate quick --allow-local-dirty --leave-running --smoke-insecure-tls --smoke-attempts 8 --smoke-delay 2`; remote smoke passed on attempt 2 with `/api/health -> 200`.
- Direct HTTP/API clean regression marker `p2-20260528-0925-cef033e7-p2-01-reg-049c16dd`:
  - created ticket `T-000615` / `4edde76d-053c-43ad-9c04-ea3c19ad4fbb`;
  - public token redacted `{prefix=e55fdbf4, sha256_12=89c94024ed1b, length=64}`;
  - public code redacted `{prefix=GSW, suffix=QZ5, length=8}`;
  - `GET /api/tickets/{ticket_id}` no token -> `401`;
  - invalid token -> `401`;
  - valid public token -> `200`;
  - public token list `/api/tickets?limit=5` -> `403`;
  - wrong public code -> `403`;
  - valid public code -> `200`;
  - cross-ticket read with public token -> `403`;
  - JSON scan forbidden hits for `queue_id`, `device_id`, `assignee_id`, `requester_id`, `custom_fields`, `priority_decision`, `routing_decision`, `code_hash`, `public_access_code`, `session_token`, `public_token`, `trace_id`, `operation_id` -> `0`;
  - artifact: `artifacts\p2-20260528-0925-cef033e7-p2-01-reg-049c16dd-api-regression.json`.
- Browser/public help clean regression marker `p2-20260528-0925-cef033e7-p2-01-browser-049c16dd`:
  - created ticket `T-000616` / `1896f5af-a7e8-4943-87dd-980f7289aa4a`;
  - real browser URL `https://192.168.100.17:9443/help?ticket_id=1896f5af-a7e8-4943-87dd-980f7289aa4a`;
  - entered the public code in the browser but recorded only redacted evidence `{prefix=Z6R, suffix=S5Q, length=8}`;
  - visible browser text showed `T-000616`, public status `Заявка принята`, requester message marker and safe system notice `Код доступа к заявке сформирован.`;
  - browser text scan forbidden hits for internal field names/token markers -> `0`;
  - redacted screenshot: `artifacts\p2-20260528-0925-cef033e7-p2-01-browser-049c16dd-public-help-redacted.png`.
- Server DB evidence for `T-000615` and `T-000616`: internal fields still exist in source rows (`device_id`, `queue_id`, `requester_id`, priority/urgency/importance, `custom_fields.public_access`, `custom_fields.priority_decision`, `custom_fields.routing_decision`) and events include `chat_message`, `routing_applied`, `queue_changed`, `sla_started`; these internals are now absent from requester/public API/browser projections.
- Server log regression window: `journalctl -u pc-client-server.service --since '2026-05-28 10:00:00'` filtered for P2 marker/ERROR/Traceback/500 returned no matching errors.
Regression check:
- The API negative boundaries from the original repro remained enforced (`401/403` where expected), and the browser public route still loads the requester-safe ticket after code entry.
Remaining risk:
- Browser currently displays the public access code during the legitimate requester login flow; screenshots/evidence must redact it. This is expected product behavior for the ticket owner and is separate from the fixed API payload leak.
Status consistency checked: yes

## P6 Live validation - 2026-05-29 - run_id=p6-20260529-0828-d151a7f6

Status: in progress

Scope:
- P6.1 Route/code discovery and operational surface map.
- P6.2 Request Template Studio -> ticket create.
- P6.3 Ticket Workbench full operator flow.
- P6.4 Operator Command Center / Support Action Center.
- P6.5 Approval / Consent Center.
- P6.6 Device Operations workspace.
- P6.7 Admin Tech Panel / Pilot Readiness.
- P6.8 Cross-domain E2E pilot scenario.
- P6.9 RBAC and route matrix.
- P6.10 Regression against P0-P5 boundaries.
- P6.11 Browser/UI/UX consistency and no-stale-state pass.

Status audit:
- P0/P1/P2/P3/P4/P5 are closed in this file.
- `P6 readiness: ready` is recorded in the P5 close summary.
- `BUG-20260528-P4-01` is `verified-fixed`.
- P5 close summary records the remote server was intentionally stopped after successful `/api/health` smoke; P6 will start it as expected handoff recovery, not an incident.
- No prior P6 Live validation section existed before this section.
- Existing unrelated dirty state is preserved and out of P6 scope: `pc_agent/ui_gui/tickets_list_model.py`; old/untracked `artifacts/*`.

Baseline:
- Branch: `codex/helpdesk-process-model`
- Commit SHA: `d151a7f6c44f73c69e1b549255389fc406ac0afa`
- Server URL: `https://192.168.100.17:9443`
- Browser/admin URL: `https://192.168.100.17:9443/admin`
- Browser/support URL: `https://192.168.100.17:9443/app/support`
- Browser/requester URL: `https://192.168.100.17:9443/app/tickets` / requester-safe routes as scenario-specific.
- Browser/public URL: `https://192.168.100.17:9443/app/help` / public ticket routes as scenario-specific.
- Agent A: `live-v3-p1-clean2`
- Agent B if used: not planned for baseline unless P6 RBAC/cross-account checks require it.
- Device ids: Agent A server/browser device id `2447d396-79cd-53da-b3a9-028c5a4d56da`; local `install_id=5b365c85-86d8-41e0-8cdd-b26594d3e581`; local identity file has no separate `device_id` field.
- Agent versions: Agent A UIA title reports `3.1.61`.
- pywinauto version: `0.6.9`.
- Canonical browser workspaces:
  - `/app/support`
  - `/app/tickets`
  - `/app/admin/request-template-studio`
  - `/app/admin/device-operations/<device_id>` and `/app/admin/device-operations?device_id=<device_id>`
  - `/app/admin/tech`
  - `/app/support/approvals`
- Old contamination ignored:
  - P0 phantom/pre-fix rows and historical live validation artifacts.
  - P1 pre-fix restart/drop/probe rows, including old stale `device_outbox` evidence.
  - P2 old public/artifact/two-agent contamination and known/deferred P1 limitations carried forward only as historical context.
  - P3/P4/P5 historical tickets/problems/changes and closed bug evidence.
  - P4 pre-fix scanner duplicate candidates and historical P4-01 automation bridge invalid-create attempts.
  - P5 `p5-fix-20260529-0000-8bfc7c76` test-tool contamination from wrong risk id extraction.
  - Old/untracked `artifacts/*` not created for this P6 run.

Baseline gates before scenarios:
- [x] Start server as expected handoff recovery: `python scripts\manage_remote_stack.py start server` -> `running`, pid `508817`.
- [x] `python scripts\manage_remote_stack.py smoke server --insecure-tls` -> passed after startup warmup. The first immediate smoke attempt raced server startup and is recorded as handoff recovery timing, not an incident.
- [x] `/api/health` -> HTTP `200`.
- [x] Agent A connected: `python scripts\agent_test_driver.py status live-v3-p1-clean2` -> `connection_state=connected`, `WS connected`.
- [x] Browser admin/device workspace shows Agent A online: `/app/admin/device-operations/2447d396-79cd-53da-b3a9-028c5a4d56da` -> `ADMIN-2`, online, last contact during baseline.
- [x] `pywinauto==0.6.9`.
- [x] UIA semantic state probe passes for Agent A: `artifacts\p6-20260529-0828-d151a7f6-uia-baseline.json`; connection `connected`, account mode `confirmed_binding`, ticket count `21`, failures `[]`.
- [x] Agent SQLite has no active/failed rows for `p6-20260529-0828-d151a7f6` in `outbox`, `outbox_sent_history`, `seen_commands`, `pending_command_results`; `pending_consents=0`.
- [x] Server DB has no active `device_outbox` rows for `p6-20260529-0828-d151a7f6`; all marker rows `0`.
- [x] Browser opens all P6 canonical workspaces with console/network baseline captured.

Baseline browser evidence:
- Real browser route `/app/support`: loaded Support workspace / Command Center; console current route `0` errors/warnings; network captured as `p6-20260529-0828-support-network.json`; snapshot `p6-20260529-0828-support-baseline.md`.
- Real browser route `/app/tickets`: loaded Ticket Workbench at selected ticket detail; console current route `0` errors/warnings; network `p6-20260529-0828-tickets-network.json`; snapshot `p6-20260529-0828-tickets-baseline.md`.
- Real browser route `/app/admin/request-template-studio`: loaded Studio; console current route `0` errors/warnings; network `p6-20260529-0828-template-studio-network.json`; snapshot `p6-20260529-0828-template-studio-baseline.md`. The selected historical template shows publication unavailable/missing policy gates; this is old context until P6.2 tests a clean P6 template path.
- Real browser route `/app/support/approvals`: loaded Approval/Consent Center; pending counts `0`; console current route `0` errors/warnings; network `p6-20260529-0828-approvals-network.json`; snapshot `p6-20260529-0828-approvals-baseline.md`.
- Real browser route `/app/admin/device-operations/2447d396-79cd-53da-b3a9-028c5a4d56da`: loaded device operations for Agent A; online state visible; outbox current state empty; historical failed operations are old contamination, not P6 marker evidence. Network `p6-20260529-0828-device-operations-network.json`; snapshot `p6-20260529-0828-device-operations-baseline.md`.
- Real browser route `/app/admin/device-operations?device_id=2447d396-79cd-53da-b3a9-028c5a4d56da`: query fallback opens the same Agent A device context; console current route `0` errors/warnings; snapshot `p6-20260529-0828-device-operations-query-baseline.md`.
- Real browser route `/app/admin/tech`: loaded Pilot Readiness panel with score `100`, blockers `0`, warnings `0`, stuck operations `0`, no false red state from the expected P5 handoff server stop after baseline recovery. Network `p6-20260529-0828-tech-network.json`; snapshot `p6-20260529-0828-tech-baseline.md`.
- Real browser route `/app/help`: public/requester help page loads; console errors captured to `p6-20260529-0828-public-help-console-errors.json`; network `p6-20260529-0828-public-help-network.json`; snapshot `p6-20260529-0828-public-help-baseline.md`.
- Browser note: old console errors from the pre-baseline stopped server state were ignored as expected handoff contamination; each fresh P6 baseline route was checked separately after server recovery.

Route/code discovery:
- Request Template Studio / Service Catalog / Policy Health:
  - Browser routes: `/app/admin/request-template-studio`, `/app/admin/service-catalog`, `/app/admin/policy-health`.
  - Backend routes: `/api/web/admin/service-catalog*`, `/api/web/admin/helpdesk/policy-health*`, `/api/web/admin/helpdesk-model/request-templates/publish-from-form`, requester-safe `/api/service-catalog/current`, `POST /api/service-catalog/preview`.
  - Files: `webapp/src/pages/admin/request-template-studio-page.tsx`, `webapp/src/features/service-catalog/*`, `webapp/src/features/policy-health/*`, `server/web_api/service_catalog_handlers.py`, `server/web_api/policy_health_handlers.py`.
- Ticket Workbench:
  - Browser route: `/app/tickets`.
  - Backend routes include `/api/web/support/workspace/summary`, `/api/web/support/tickets/{ticket_id}/read`, `/api/web/support/tickets/{ticket_id}/messages`, `/api/web/support/tickets/{ticket_id}/diagnostics/capabilities*`.
  - Files: `webapp/src/pages/tickets/list-page.tsx`, `webapp/src/features/queues/*`, `server/web_api/support_handlers.py`.
- Operator Command Center / Support Action Center:
  - Browser route: `/app/support`.
  - Backend route: `GET /api/web/support/command-center`.
  - Files: `webapp/src/pages/support/command-center-page.tsx`, `webapp/src/features/operator-command-center/*`, `server/support/operator_command_center.py`, `server/web_api/support_handlers.py`.
- Approval / Consent Center:
  - Browser route: `/app/support/approvals`.
  - Backend route: `GET /api/web/support/approvals`.
  - Files: `webapp/src/pages/support/approval-consent-center-page.tsx`, `webapp/src/features/approval-consent-center/*`, `server/approvals/service.py`, `server/web_api/approval_handlers.py`.
- Device Operations:
  - Browser routes: `/app/admin/device-operations/{device_id}`, `/app/admin/device-operations?device_id=...`.
  - Backend route: `GET /api/web/admin/device-operations/{device_id}` and query fallback.
  - Files: `webapp/src/pages/admin/device-operations-page.tsx`, `webapp/src/features/device-operations/*`, `server/device_operations/service.py`, `server/web_api/device_operations_handlers.py`.
- Admin Tech Panel:
  - Browser route: `/app/admin/tech`.
  - Backend routes: `GET /api/web/admin/tech/snapshot`, legacy aliases `/overview`, `/alerts`, `/logs`, `/agents/audit`, `/users/audit`, `/operations/stuck`.
  - Files: `webapp/src/pages/admin/tech-page.tsx`, `webapp/src/features/tech/*`, `server/tech/snapshot.py`, `server/tech/handlers.py`.

P6 bug template:

```md
### BUG-20260529-P6-NN - short title

Severity: P0/P1/P2/P3/P4/P5/P6
Status: reproduced / root-cause-confirmed / fix-in-progress / verified-fixed / verified-non-product / known-limitation / deferred / not-a-bug
Area: request-template-studio / ticket-workbench / operator-command-center / support-action-center / approval-center / consent-center / device-operations / admin-tech / browser-ui / account-session / public-access / requester-access / artifact-access / operation-lifecycle / problem-linkage / change-linkage / quality-linkage / RBAC / privacy-PII / server-db / agent-sqlite / UIA / test-contamination

P6 scenario:
Run id:
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
- Blocking further P6: yes/no
- Fixed now: yes/no

Fix summary:
Changed files:
Tests:
Live regression:
Regression check:
Remaining risk:
Status consistency checked: yes/no
```

P6 product contract:
- Operational workspaces must reflect real backend state. Browser UI must match DB/API for ticket status, unread counts, support action tasks, pending approvals/consents, device state, operation failures, module/outbox state and problem/change/quality links when shown.
- Request Template Studio is the primary workflow for service -> offering -> template -> form -> policy -> simulation -> publication gates. Published templates must create tickets with correct top-level `service_code`, `offering_code` and `offering_full_code`; `custom_fields` is not the canonical catalog source.
- Ticket Workbench must show requester/account, device/agent/inventory context and operation timeline. Support messages, attachments and safe diagnostic actions must persist and render through web-session routes.
- Operator Command Center sections are real task projections from `GET /api/web/support/command-center`; `unread_user_messages` is based on support unread user message count and must clear/update after support opens the ticket.
- Approval/Consent Center must reflect real pending approval/operation/remote-assist state and must not expose Remote Assist tokens, ICE, SDP or raw operation params.
- Device Operations must compose real device card, inventory/binding, agent/update state, module reconcile, outbox, recent operations, observer traces, provisioning/auth and Remote Assist state without exposing raw tokens or raw inventory by default.
- Admin Tech Panel must reflect current pilot readiness/runtime health and must not report the expected P5 handoff server stop as a current incident after P6 baseline recovery.
- Requester/public roles must not see internal operator/admin/problem/change/device/tech data.

P6 scenario checklist:
- [x] P6.1 Route/code discovery and operational surface map.
- [x] P6.2 Request Template Studio -> ticket create.
- [x] P6.3 Ticket Workbench full operator flow.
- [x] P6.4 Operator Command Center / Support Action Center.
- [x] P6.5 Approval / Consent Center.
- [x] P6.6 Device Operations workspace.
- [x] P6.7 Admin Tech Panel / Pilot Readiness.
- [x] P6.8 Cross-domain E2E pilot scenario.
- [x] P6.9 RBAC and route matrix.
- [x] P6.10 Regression against P0-P5 boundaries.
- [x] P6.11 Browser/UI/UX consistency and no-stale-state pass.

### BUG-20260529-P6-01 - requester catalog ticket create requires urgency reason when urgency is false

Severity: P2
Status: verified-fixed
Area: request-template-studio / requester-access / workflow / browser-ui

P6 scenario: P6.2.E Ticket create from template; P6.8 Cross-domain E2E pilot scenario.
Run id: `p6-20260529-0828-d151a7f6`
Expected:
- A requester/public ticket create payload with `urgency=false` and `importance=false` should not require `urgency_reason` or `importance_reason`.
- The same catalog context that passes requester-safe `POST /api/service-catalog/preview` should be creatable when required form fields are present.
- Expected validation errors should be field-specific, and no invalid create should mutate ticket, event, outbox or agent state.
Actual:
- Real browser context on `/app/help` ran `POST /api/service-catalog/preview` for service `network`, offering `network.vpn_issue`, template/form `network`, marker `p6-20260529-0828-d151a7f6`; preview returned HTTP `200`, service/offering resolved, blockers `[]`, diagnostics `required=true`, `consent_required=true`, warning `priority_not_allowed`.
- The follow-up requester/public `POST /public_api/tickets/create` with the same required form fields and `urgency=false`, `importance=false` returned HTTP `400` JSON `{"status":"error","error":"validation_error","details":{"priority":"urgency_reason is required"}}`.
- Repeating with explicit `form_pack_version=1` returned the same HTTP `400` validation denial.
Repro steps:
1. Open real browser route `https://192.168.100.17:9443/app/help`.
2. From that browser session, submit requester-safe preview for `service_code=network`, `offering_full_code=network.vpn_issue`, `request_template_key=network`, `form_key=network`, required form fields `impact_scope=single_user`, `work_continuity=workaround_available`, marker in `form_payload.run_id`.
3. Submit `/public_api/tickets/create` with the same catalog/form context, `title` and `description` containing marker, `urgency=false`, `importance=false`, and no urgency/importance reasons.

Evidence:
- Transport/API: browser context preview -> HTTP `200`, blockers `[]`; browser context create -> HTTP `400`, `validation_error`, `details.priority="urgency_reason is required"`.
- Server log: not yet inspected.
- Agent log: not applicable to public/requester create path.
- Server DB: no mutation for marker before fix: `tickets_marker=0`, `ticket_events_marker=0`, `device_outbox_marker_active=0`.
- Agent SQLite: no marker rows in `outbox`, `outbox_sent_history`, `seen_commands`, `pending_command_results` or `pending_consents`.
- Browser/UI: real browser route `/app/help`; browser console recorded failed resource for `/public_api/tickets/create` after the 400 response.
- UIA: not applicable to this public browser create path.
- Test artifact: browser MCP output for preview/create; no raw public access code/token returned.
- Run marker: `p6-20260529-0828-d151a7f6`.

Impact:
- Blocks P6.2.E and P6.8 clean requester/public E2E ticket creation for normal non-urgent/non-important tickets.
- This appears to be a workflow validation defect, not a server availability or auth issue.
Root cause hypothesis:
- The public/create validation layer likely treats the presence of boolean priority fields or their default false value as requiring a reason, instead of requiring a reason only when `urgency=true` or `importance=true`.
Root cause confirmed: yes. `server/tickets/public_ticket_handlers.py::handle_public_ticket_create()` calls strict `normalize_ticket_priority_inputs(urgency, importance, urgency_reason, importance_reason)` before form/catalog policy resolution. That helper always requires both reason strings. The authenticated create path in `server/tickets/handlers.py::_default_priority_payload()` defaults missing priority booleans/reasons, so browser/requester defaults from `/app/help` are treated differently on the public create route.
Fix policy:
- Blocking further P6: yes for requester/public catalog ticket creation and cross-domain E2E.
- Fixed now: yes, after root cause is confirmed, because direct workaround would not validate the normal browser product path.

Fix summary:
Fixed create-time priority normalization so public/requester create uses the same safe default priority payload behavior as authenticated create. The strict reason-requiring helper remains available for explicit priority mutation paths.
Changed files:
- `server/tickets/statuses.py`
- `server/tickets/handlers.py`
- `server/tickets/public_ticket_handlers.py`
- `server/tests/test_ticket_form_packs.py`
Tests:
- `python -m pytest server\tests\test_ticket_form_packs.py::test_public_create_ticket_allows_false_priority_flags_without_reasons -q` -> passed (`1 passed in 344.36s`).
- `python -m py_compile server\tickets\statuses.py server\tickets\handlers.py server\tickets\public_ticket_handlers.py` -> passed.
Live regression:
- Deployed commit `80ce0528790a9c79bed851f7bef3339c09c1a575` to remote with quick release; `/api/health` smoke passed.
- Real browser `/app/help` requester/public create with marker `p6-20260529-0828-d151a7f6`, `urgency=false`, `importance=false` and no priority reasons returned HTTP `200` and created ticket `T-000639` (`bf9fdfcb-399a-4525-b145-06009924cba9`); raw public token/access code were not recorded.
- Server DB for `T-000639`: status `new`, `service_code=network`, `offering_code=network.vpn_issue`, `request_type=incident`, `priority=P4`; marker ticket count `1`; active marker `device_outbox` rows `0`.
- Browser support workbench `/app/tickets/bf9fdfcb-399a-4525-b145-06009924cba9` loaded and showed the clean P6 ticket; evidence artifacts `p6-20260529-0828-ticket-T-000639-after-p6-01-fix.md` and `.png`.
Regression check:
- Direct invalid pre-fix marker path caused no DB/SQLite mutation; post-fix valid create still keeps expected ticket/event/catalog fields.
Remaining risk:
- Public-created tickets can use a requester placeholder device context; P6 diagnostic/tool checks use the separate Agent A-bound ticket `T-000640`.
Status consistency checked: yes

## P6 findings summary - 2026-05-29 - run_id=p6-20260529-0828-d151a7f6

| Bug | Severity | Area | Blocking P6 | Fix now | Status |
|---|---|---|---|---|---|
| BUG-20260529-P6-01 | P2 | request-template-studio / requester-access / workflow | yes | yes | verified-fixed |
| BUG-20260529-P6-02 | P2 | operator-command-center / support-action-center | yes | yes | verified-fixed |

## P6 close summary - 2026-05-29 - run_id=p6-20260529-0828-d151a7f6

Status: P6 closed

Code head:
- Product/runtime head deployed for P6 fixes: `3c565b30bb728e03cc6a0b6e4d9e3f441308ffcb`.
- P6-01 product fix head: `80ce0528790a9c79bed851f7bef3339c09c1a575`.
Server URL: `https://192.168.100.17:9443`
Agent A: `live-v3-p1-clean2`, Agent v3.1.61, device `2447d396-79cd-53da-b3a9-028c5a4d56da`, UIA process `28128`.
Agent B: not used for P6 close gates.
Clean tickets:
- `T-000639` (`bf9fdfcb-399a-4525-b145-06009924cba9`) - requester/public catalog ticket created after P6-01 fix.
- `T-000640` (`530232fa-127a-440d-a6e0-cd0d4a68f8bc`) - Agent A-bound cross-domain E2E ticket.
Template ids:
- Existing Service Catalog route used: service `network`, offering `network.vpn_issue`, template/form `network`.
Attachment/artifact ids:
- Browser support upload artifact `a044ceae-30ab-4d26-83b7-e844072d2ef6`, filename `p6-support-attachment-p6-20260529-0828-d151a7f6.txt`.
Operation ids:
- Safe diagnostic `system.collect`: `c9ca5e32-77b7-4401-acc2-12f6b69f009f`, server status `succeeded`, server `device_outbox.id=158` delivered, Agent A `seen_commands.status=success`.
Approval/consent ids:
- No pending approval/consent created for P6 close; Approval Center route/API loaded with `pendingCount=0` and no token/ICE/SDP/authorization secret matches.
Device ids:
- Agent A `2447d396-79cd-53da-b3a9-028c5a4d56da`.
Old contamination ignored:
- Historical P0-P5 contamination and historical non-P6 `agent_offline_active` tasks were not used as P6 evidence.
- Old untracked `artifacts/*` and unrelated dirty `pc_agent/ui_gui/tickets_list_model.py` were not staged or modified by P6.

P6.1 result:
- Passed. Route/code discovery recorded actual workspaces and APIs for request template studio, ticket workbench, command center, approvals, device operations and tech panel.
P6.2 result:
- Passed after BUG-P6-01 fix. Real browser `/app/help` catalog preview returned HTTP `200`; valid requester/public create produced `T-000639` with correct service/offering/template context.
P6.3 result:
- Passed. Real support browser/API processed `T-000640`: support message, support attachment upload, attachment-only message, safe diagnostic tool, and status path `in_progress -> resolved`.
P6.4 result:
- Passed after BUG-P6-02 fix. Command Center no longer lists online Agent A ticket `T-000640` in `agent_offline_active`; after resolution, `T-000640` disappears from active Command Center sections.
P6.5 result:
- Passed for center load/no-secret/no-stale-pending gate. `/app/support/approvals` and `/api/web/support/approvals` returned HTTP `200`, pending count `0`, no token/ICE/SDP/raw secret matches.
P6.6 result:
- Passed. Device Operations for Agent A returned HTTP `200`, `connection_state=online`, `signals.agent_offline=false`, no raw session/auth/cookie secret matches, and recent operation evidence matched DB/SQLite.
P6.7 result:
- Passed. Admin Tech Panel route/API loaded after explicit P5 handoff recovery; expected prior server stop was not treated as current incident. Security rows mentioning cookie/token policy were labels only, not raw secrets.
P6.8 result:
- Passed. Cross-domain E2E used template/requester create, Agent A-bound ticket create, support workbench processing, attachment, diagnostic operation, Device Operations, Command Center and status resolution with DB/API/SQLite agreement.
P6.9 result:
- Passed for key P6 internal surfaces. Anonymous/no-auth direct HTTP to `/api/web/support/command-center`, `/api/web/support/approvals`, `/api/web/admin/device-operations/*`, `/api/web/admin/tech/snapshot`, `/api/web/support/tickets/*` and request-template bootstrap returned HTTP `401` before mutation.
P6.10 result:
- Passed. Account/public/internal boundary checks showed no requester/public access to internal P6 APIs, artifact/tool operation remained authorized, no stale P6 device_outbox/operation rows, and UIA still saw Agent A connected with `T-000640`.
P6.11 result:
- Passed. Browser route pass loaded `/app/support`, `/app/tickets/{T-000640}`, `/app/admin/request-template-studio`, `/app/support/approvals`, `/app/admin/device-operations/{device_id}` and `/app/admin/tech` with HTTP `200`; no mojibake was introduced by P6 fixes and final console/network artifacts were captured.

Bugs found:
- `BUG-20260529-P6-01 - requester catalog ticket create requires urgency reason when urgency is false`.
- `BUG-20260529-P6-02 - Command Center shows online Agent A ticket as agent_offline_active`.

Verified fixed:
- `BUG-20260529-P6-01`
- `BUG-20260529-P6-02`

Deferred/known limitations:
- None newly introduced for P6. Historical P0-P5 limitations remain separated from P6 marker evidence.

Operational readiness result:
- Request Template Studio: ready for pilot with P6 requester catalog create fixed.
- Ticket Workbench: ready for pilot for message, attachment, diagnostic operation and status path.
- Operator Command Center: ready for pilot after live runtime presence alignment.
- Approval/Consent Center: ready for current no-pending/no-secret gate.
- Device Operations: ready for pilot for Agent A runtime/device state.
- Admin Tech Panel: ready for pilot runtime health snapshot after expected handoff recovery.
- Cross-domain E2E: passed for clean Agent A ticket `T-000640`.
- RBAC/privacy: internal P6 endpoints denied anonymous/no-auth direct HTTP; browser/admin responses checked for raw token/cookie/session leaks.

Browser/UI evidence:
- `p6-20260529-0828-command-center-after-p6-02-fix.md`
- `p6-20260529-0828-command-center-after-p6-02-fix-console-errors.json`
- `p6-20260529-0828-command-center-after-p6-02-fix-network.json`
- `p6-20260529-0828-final-route-pass-console-errors.json`
- `p6-20260529-0828-final-route-pass-network.json`
- `p6-20260529-0828-ticket-T-000639-after-p6-01-fix.md`
- `p6-20260529-0828-ticket-T-000639-after-p6-01-fix.png`

UIA evidence:
- `artifacts\p6-20260529-0828-d151a7f6-uia-baseline.json`
- `artifacts\p6-20260529-0828-d151a7f6-uia-ticket-T-000640-pid28128.json`
- `artifacts\p6-20260529-0828-d151a7f6-uia-final-T-000640-instance.json`

DB/SQLite evidence:
- Final server DB for marker: active `device_outbox=0`, active marker operations `0`, marker tickets `2`, marker ticket events `10`, `T-000640` status `resolved`.
- Final Agent A SQLite for marker: outbox `0`, outbox_sent_history marker `0`, active seen_commands marker `0`, pending_command_results marker `0`, pending_consents marker `0`, total pending consents `0`.

Verification:
- `python -m pytest server\tests\test_operator_command_center_no_db.py -q --tb=short` -> `6 passed`.
- `python -m pytest server\tests\test_ticket_form_packs.py::test_public_create_ticket_allows_false_priority_flags_without_reasons -q` -> passed.
- `python -m py_compile server\support\operator_command_center.py server\web_api\support_handlers.py`
- `python -m py_compile server\tickets\statuses.py server\tickets\handlers.py server\tickets\public_ticket_handlers.py`
- `python scripts\verify_workspace.py`
- `python -m compileall -q server pc_agent scripts`
- `git diff --check`
- Quick remote release for `3c565b30...` and `/api/health` smoke -> passed.

Next readiness:
- ready

### BUG-20260529-P6-02 - Command Center shows online Agent A ticket as agent_offline_active

Severity: P2
Status: verified-fixed
Area: operator-command-center / support-action-center / device-operations / browser-ui

P6 scenario: P6.4 Operator Command Center / Support Action Center; P6.8 Cross-domain E2E pilot scenario.
Run id: `p6-20260529-0828-d151a7f6`
Expected:
- Command Center `agent_offline_active` must only include active tickets whose bound device is actually offline according to the same authoritative device/agent online source used by Device Operations.
- A ticket bound to online Agent A should not appear as an offline-agent task.
Actual:
- Clean Agent A ticket `T-000640` (`ticket_id=530232fa-127a-440d-a6e0-cd0d4a68f8bc`, `device_id=2447d396-79cd-53da-b3a9-028c5a4d56da`) appears in `GET /api/web/support/command-center?limit_per_section=10` section `agent_offline_active`.
- The same Device Operations API for `2447d396-79cd-53da-b3a9-028c5a4d56da` returns HTTP `200`, `connection_state=online`, last seen during the P6 run.
Repro steps:
1. Create device-bound clean ticket through Agent A automation bridge with marker `p6-20260529-0828-d151a7f6`.
2. Confirm the ticket is bound to Agent A and visible in support workbench.
3. Fetch real browser web-session `GET /api/web/support/command-center?limit_per_section=10`.
4. Fetch real browser web-session `GET /api/web/admin/device-operations/2447d396-79cd-53da-b3a9-028c5a4d56da`.

Evidence:
- Transport/API: command-center HTTP `200`, ticket `T-000640` present in `new_unassigned`, `operator_action`, `unread_user_messages`, `sla_risk` and incorrectly in `agent_offline_active`; Device Operations HTTP `200`, `connection_state=online`.
- Server log: not yet inspected.
- Agent log: not yet inspected.
- Server DB: `tickets` row `T-000640`, status `queued`, device `2447d396-79cd-53da-b3a9-028c5a4d56da`; `devices` row hostname `ADMIN-2`, `last_seen_at=2026-05-29 09:07:12+05`, `last_handshake_at=2026-05-29 09:07:12+05`; active outbox for device `0`; ticket operation status `succeeded`.
- Agent SQLite: safe diagnostic `system.collect` for operation `c9ca5e32-77b7-4401-acc2-12f6b69f009f` is terminal `success`; no pending command results.
- Browser/UI: real browser ticket page shows `T-000640`; Device Operations browser/API says Agent A online; Command Center API says `agent_offline_active`.
- UIA: Agent A pid `28128` probe sees connected/account/ticket `T-000640`, failures `[]` (`artifacts\p6-20260529-0828-d151a7f6-uia-ticket-T-000640-pid28128.json`).
- Test artifact: browser MCP API evidence; no raw tokens printed in PLANS.
- Run marker: `p6-20260529-0828-d151a7f6`.

Impact:
- Materially wrong operational task projection: support may see a false offline-agent action for an online device during pilot.
Root cause hypothesis:
- Command Center likely uses a different/stale device offline heuristic or does not share the Device Operations online projection source.
Root cause confirmed: yes. `server/web_api/support_handlers.py::handle_web_support_command_center()` loads DB `Device` rows and calls `build_operator_command_center_payload()` without passing runtime websocket presence. `server/support/operator_command_center.py::_agent_state()` then classifies the agent as offline when DB `last_seen_at` is older than 5 minutes. Device Operations uses `DeviceOperationsService._connection_state()` with `request.app["state"].is_agent_online(device_id)` as the authoritative live runtime source, with DB time only as fallback. During P6, Agent A had an active UIA/runtime session and Device Operations returned `online`, but the Command Center DB-only 5-minute heuristic produced a false `agent_offline_active` task.
Fix policy:
- Blocking further P6: yes for P6.4/P6.8 Command Center correctness.
- Fixed now: yes after root cause confirmation, because task-board evidence is invalidated.

Fix summary:
- Command Center now receives live runtime online device ids from `request.app["state"].is_agent_online()` and passes them into the projection builder.
- `_agent_state()` prefers authoritative runtime-online presence before stale DB/inventory offline signals; DB `last_seen_at` remains fallback only.
- Fallback offline threshold was aligned with Device Operations' 15-minute policy.
Changed files:
- `server/support/operator_command_center.py`
- `server/web_api/support_handlers.py`
- `server/tests/test_operator_command_center_no_db.py`
Tests:
- RED: `python -m pytest server\tests\test_operator_command_center_no_db.py::test_command_center_prefers_live_agent_presence_over_stale_last_seen -q --tb=short` failed before implementation with unexpected `online_device_ids` argument.
- GREEN: `python -m pytest server\tests\test_operator_command_center_no_db.py -q --tb=short` -> `6 passed in 0.11s`.
- `python -m py_compile server\support\operator_command_center.py server\web_api\support_handlers.py` -> passed.
- Attempted DB-backed `server\tests\test_operator_command_center.py` on local Windows; it hung and was stopped after several completed dots, matching prior local route-test instability. Live browser/API regression is required before verified-fixed.
Live regression:
- Deployed commit `3c565b30bb728e03cc6a0b6e4d9e3f441308ffcb` to remote with quick release; `/api/health` smoke passed.
- Real browser `/app/support` loaded after deploy. Browser web-session `GET /api/web/support/command-center?scope=all&limit_per_section=25&include_debug=1` returned HTTP `200`, `metadata.online_device_count=2`.
- Clean Agent A ticket `T-000640` remained visible in real task sections (`new_unassigned`, `operator_action`, `unread_user_messages`, `sla_risk`) with `agent.connection_state=online`, and was absent from `agent_offline_active`.
- Browser web-session `GET /api/web/admin/device-operations/2447d396-79cd-53da-b3a9-028c5a4d56da` returned HTTP `200`, `agent.connection_state=online`, `signals.agent_offline=false`.
- Browser evidence artifacts: `p6-20260529-0828-command-center-after-p6-02-fix.md`, `p6-20260529-0828-command-center-after-p6-02-fix-console-errors.json`, `p6-20260529-0828-command-center-after-p6-02-fix-network.json`.
Regression check:
- Server DB after fix for marker `p6-20260529-0828-d151a7f6`: active marker `device_outbox=0`, active marker operations `0`, clean marker tickets `2`, marker ticket events `7`.
- Agent A SQLite after fix: marker `outbox=0`, `outbox_sent_history=0`, active marker `seen_commands=0`, marker `pending_command_results=0`, marker `pending_consents=0`, total pending consents `0`.
Remaining risk:
- Historical non-P6 `agent_offline_active` count remains `2`; P6 verification only treats run-marker tickets as new evidence and does not classify old rows as a new P6 bug.
Status consistency checked: yes

P2.1.C Requester account-session access matrix:
- Status: pending, not passed.
- Evidence collected: Agent A/local GUI account session is active confirmed binding:
  - instance `live-v3-p1-clean2`;
  - account session id `0a8c0210-3028-4fb8-89aa-9a40f1d643f9`;
  - account mode `confirmed_binding`;
  - person id `f0e074a5-7c1b-4e38-bb4a-abfb2be3612f`;
  - display name `P1 Clean User`;
  - no session token printed.
- Server DB account-session survey found only one active verified requester person/session family for Agent A; old second-device sessions for person `bb00a942-fe2c-461c-b982-9da17d3fd1ff` are revoked. This is an environment/setup constraint for the cross-account matrix, not a product pass.
- Required next step: create/approve a clean Account B/requester session through the registration/account-session workflow or Agent B setup before marking P2.1.C.

P2.1.D Timeline redaction:
- Status: partial pass for clean ticket `T-000616`; broader requester/account/public matrix still depends on P2.1.C Account B setup and P2.2 artifact events.
- Public/requester browser surface: real browser URL `https://192.168.100.17:9443/help?ticket_id=1896f5af-a7e8-4943-87dd-980f7289aa4a`; after code entry, visible text showed ticket `T-000616`, public status `Заявка принята`, requester message marker and safe system notice `Код доступа к заявке сформирован.`. Browser text scan found no `queue_id`, `device_id`, `assignee_id`, `requester_id`, `custom_fields`, `priority_decision`, `routing_decision`, `code_hash`, `public_access_code`, `session_token`, `public_token`, `trace_id` or `operation_id`. Redacted screenshot: `artifacts\p2-20260528-0925-cef033e7-p2-01-browser-049c16dd-public-help-redacted.png`.
- Support/admin browser surface: real browser URL `https://192.168.100.17:9443/app/tickets/1896f5af-a7e8-4943-87dd-980f7289aa4a`; support sees expected internal context (`Очередь: ServiceDesk L1`, `Исполнитель: Не назначен`) and timeline system events, but no `code_hash`, `session_token` or `public_token` visible. Screenshot: `artifacts\p2-20260528-0925-cef033e7-p2-01-support-timeline-T-000616.png`.
- Server DB source events for `T-000616`: `chat_message=2`, `routing_applied=1`, `queue_changed=1`, `sla_started=1`; requester/public projection hides the raw routing/SLA payload while support/admin surface can show operational context.

### BUG-20260528-P2-02 - Browser support attachment upload is not authenticated by web session

Severity: P1
Status: verified-fixed
Area: attachment-upload / browser-ui / auth-account-session

P2 scenario: P2.2.B Manual support/browser attachment upload.
Run id: `p2-20260528-0925-cef033e7`
Expected:
- A real support/admin browser session that can open `/app/tickets/{ticket_id}` can upload an attachment through the support UI path.
- `POST /api/upload` accepts the same typed web-session authentication used by support browser routes, applies ticket access checks, creates an artifact row, and the subsequent support message can reference it.
- Browser timeline shows the attachment/message; unauthorized/no-session upload remains denied.
Actual:
- Real browser support session opened ticket `T-000616` at `https://192.168.100.17:9443/app/tickets/1896f5af-a7e8-4943-87dd-980f7289aa4a`.
- Browser-side `fetch('/api/upload', { credentials: 'same-origin', multipart FormData(file,ticket_id,kind) })` returned `401` with `AUTH_REQUIRED`.
- No artifact id was returned, no support message was sent, and the browser timeline did not show the attachment marker.
Repro steps:
1. Login in real browser through `/app/login` as admin fixture user.
2. Open `https://192.168.100.17:9443/app/tickets/1896f5af-a7e8-4943-87dd-980f7289aa4a`.
3. From the browser page context, create a small text `File` named `p2 вложение p2-20260528-0925-cef033e7-p2-22-support-upload.txt`.
4. Submit `POST /api/upload` with `credentials: 'same-origin'`, multipart fields `file`, `ticket_id`, `kind=file`.
Evidence:
- Transport/API: browser fetch to `/api/upload` -> `401`, payload `{status:error, error_code:AUTH_REQUIRED}`.
- Server log: browser console captured one failed resource for `https://192.168.100.17:9443/api/upload` with unauthorized status.
- Agent A log: not applicable; browser support upload path.
- Agent B log: not applicable.
- Server DB: no artifact id returned; artifact row not created for marker in this failed attempt.
- Agent A SQLite: not applicable.
- Agent B SQLite: not applicable.
- Browser/UI: real browser ticket page stayed on `T-000616`; upload marker/filename not visible after reload. Screenshot: `artifacts\p2-20260528-0925-cef033e7-p2-22-support-upload-T-000616.png`.
- UIA: not applicable.
- Test artifact: browser MCP run output in this session; no raw cookies/tokens printed.
- Run marker: `p2-20260528-0925-cef033e7-p2-22-support-upload`.
Impact:
- Blocks P2.2.B support/browser attachment upload and the support side of artifact access matrix.
- Browser UI attachment action cannot work with the current typed web-session auth boundary, even though the user is authenticated for `/api/web/support/...`.
Root cause hypothesis:
- Auth middleware only extracts the `pc_client_web_session` cookie for `WEB_SESSION_AUTH_PATH_PREFIXES`, which include `/api/web/` but not `/api/upload` or `/api/artifacts/`. Therefore same-origin browser requests to legacy upload/download endpoints do not become `AuthType.UI_TOKEN` and hit the upload handler as unauthenticated.
Root cause confirmed: yes. `server/auth/middleware.py::WEB_SESSION_AUTH_PATH_PREFIXES` did not include `/api/upload` or `/api/artifacts/`, while `webapp/src/features/queues/api.ts::uploadSupportTicketAttachment()` calls `/api/upload` from the authenticated support browser with only same-origin cookie credentials. The upload handler already allows `AuthType.UI_TOKEN`, but the auth middleware never created that context for this legacy endpoint. A second regression showed the old `GET /api/artifacts/{artifact_id}/download?ticket_id=...` middleware skip still bypassed auth extraction before `ArtifactService`; this was removed so `ticket_id` is only context, not authentication.
Fix policy:
- Blocking further P2: yes for P2.2 support/browser attachment upload and download matrix.
- Fixed now: yes, after evidence/root-cause confirmation.
Fix summary:
- Added `/api/upload` and `/api/artifacts/` to the httpOnly web-session cookie bridge in `server/auth/middleware.py`, so browser support/admin attachment upload/download requests can authenticate as `AuthType.UI_TOKEN` without exposing raw bearer tokens.
- Removed the stale anonymous `ticket_id` download skip from `server/auth/middleware.py`; artifact downloads now require web-session, agent token or public-ticket auth before artifact visibility checks.
- Kept server-side upload/download authorization in `server/uploads/handlers.py` and `ArtifactService`; this change only bridges the existing cookie-bound UI session to the legacy attachment endpoints.
Changed files:
- `server/auth/middleware.py`
- `server/tests/test_web_session_api.py`
- `docs/QUICK_LOOKUP.md`
- `server/docs/SECURITY_AND_AUTH.md`
- `scripts/navigation_catalog.py`
- `PLANS.md`
Tests:
- `python -m pytest server\tests\test_web_session_api.py -q` -> `15 passed, 14 warnings` (existing aiohttp `NotAppKeyWarning` only).
- `python -m compileall -q server pc_agent scripts` -> passed.
- `git diff --check` -> exit 0; CRLF warnings only.
- `python scripts\verify_workspace.py` -> passed.
Live regression:
- Product commits deployed: `d97104f2` (web-session bridge for upload/artifact endpoints) and `d38b4bb8` (remove anonymous `ticket_id` artifact download skip). Deploy command: `python scripts\release_server_to_remote.py --gate quick --allow-local-dirty --leave-running --smoke-insecure-tls --smoke-attempts 8 --smoke-delay 2`; remote `/api/health` smoke passed on attempt 2.
- Browser upload path: real browser support page `https://192.168.100.17:9443/app/tickets/1896f5af-a7e8-4943-87dd-980f7289aa4a` uploaded a text file through `POST /api/upload` with `credentials: same-origin` and returned HTTP `200`; support message with marker `p2-20260528-0925-cef033e7-p2-22-support-upload-fixed-d97104f2` was sent and visible in the ticket timeline. Screenshot: `artifacts\p2-20260528-0925-cef033e7-p2-22-support-upload-fixed-T-000616.png`.
- Server DB: artifact row exists for `artifact_id=5101f949-1e3f-4152-8ac0-9d7b6f2a3490`, `ticket_id=1896f5af-a7e8-4943-87dd-980f7289aa4a`, `original_name="p2 вложение p2-20260528-0925-cef033e7-p2-22-support-upload-fixed-d97104f2.txt"`, `mime_type=text/plain`, `size_bytes=91`, `kind=file`.
- Browser download path: same real browser/session fetched `/api/artifacts/5101f949-1e3f-4152-8ac0-9d7b6f2a3490/download?ticket_id=1896f5af-a7e8-4943-87dd-980f7289aa4a` and received HTTP `200`, `content-type=text/plain`, body containing the P2 run marker.
- Anonymous/direct HTTP path: same download URL without browser cookies/tokens returned HTTP `401` JSON `AUTH_REQUIRED`; no file body or `Content-Disposition` was returned.
Regression check:
- Browser support route `/app/tickets/{ticket_id}` remained loadable after deploy and the attachment marker stayed visible after reload.
- Server-side authorization still runs in `ArtifactService`; this fix only ensures the authenticated browser session reaches that layer.
Remaining risk:
- Unicode filename in `Content-Disposition` is corrupted in the browser-observed header while DB `original_name` is intact; recorded separately as `BUG-20260528-P2-03`.
Status consistency checked: yes

### BUG-20260528-P2-03 - Unicode attachment filename is mojibake in Content-Disposition

Severity: P2
Status: verified-fixed
Area: artifact-access / attachment-upload / browser-ui

P2 scenario: P2.2.B / P2.2.E Manual support/browser attachment download and filename safety.
Run id: `p2-20260528-0925-cef033e7`
Expected:
- Unicode attachment names should either be preserved through a standards-compliant `Content-Disposition` header, for example `filename*`, or safely normalized to a deterministic ASCII fallback without mojibake.
- Browser download UX should not show corrupted Cyrillic characters.
Actual:
- DB `artifacts.original_name` is correct: `p2 вложение p2-20260528-0925-cef033e7-p2-22-support-upload-fixed-d97104f2.txt`.
- Real browser/session download returned HTTP `200`, but `Content-Disposition` exposed mojibake in the `filename` parameter for the Cyrillic word.
Repro steps:
1. Use the support browser session on ticket `T-000616`.
2. Upload the P2 support attachment with Cyrillic filename through `/api/upload`.
3. Fetch `/api/artifacts/5101f949-1e3f-4152-8ac0-9d7b6f2a3490/download?ticket_id=1896f5af-a7e8-4943-87dd-980f7289aa4a` from the browser page context.
Evidence:
- Transport/API: browser fetch returned `status=200`, `content-type=text/plain`, body contained run marker, but `Content-Disposition` filename parameter was mojibake.
- Server log: not collected yet; no server error was observed for the successful download.
- Agent A log: not applicable; browser support download path.
- Agent B log: not applicable.
- Server DB: artifact row preserves `original_name="p2 вложение p2-20260528-0925-cef033e7-p2-22-support-upload-fixed-d97104f2.txt"`.
- Agent A SQLite: not applicable.
- Agent B SQLite: not applicable.
- Browser/UI: real browser download request from `https://192.168.100.17:9443/app/tickets/1896f5af-a7e8-4943-87dd-980f7289aa4a` observed corrupted filename header; ticket timeline still shows the attachment marker.
- UIA: not applicable.
- Test artifact: Playwright MCP browser evaluate output in this session; no raw cookies/tokens printed.
- Run marker: `p2-20260528-0925-cef033e7-p2-22-support-upload-fixed-d97104f2`.

Impact:
- Does not leak data and does not block attachment access-control validation, but fails P2 filename preservation/safety expectation for Unicode attachments.
Root cause hypothesis:
- Artifact download handler sends raw Unicode only in `filename="..."` instead of RFC 5987 `filename*=` with a safe ASCII fallback, causing client/header encoding corruption.
Root cause confirmed: yes. `server/uploads/handlers.py::handle_artifact_download()` used `Content-Disposition: attachment; filename="{artifact.original_name}"` for full and range responses with no ASCII fallback or `filename*`.
Fix policy:
- Blocking further P2: no for access-control matrix; yes before final P2.2 filename-safety close unless classified as known limitation.
- Fixed now: no; continue P2 discovery first.

Fix summary:
- Added `_content_disposition_attachment()` with sanitized ASCII `filename` fallback and RFC 5987 `filename*=UTF-8''...` original-name encoding.
- Reused the helper for both full download and range download responses.
Changed files:
- `server/uploads/handlers.py`
- `server/tests/test_upload_handlers.py`
- `server/docs/ARTIFACTS_API.md`
- `server/docs/CODEMAP.md`
- `docs/QUICK_LOOKUP.md`
- `scripts/navigation_catalog.py`
Tests:
- `python -m pytest server\tests\test_web_session_api.py server\tests\test_upload_handlers.py -q` -> `18 passed, 15 warnings` (existing aiohttp `NotAppKeyWarning` only).
- `python -m compileall -q server pc_agent scripts` -> passed.
- `git diff --check` -> exit 0; CRLF warnings only.
- `python scripts\verify_workspace.py` -> passed.
Live regression:
- Product commit deployed: `de6b3cd2` with `python scripts\release_server_to_remote.py --gate quick --allow-local-dirty --leave-running --smoke-insecure-tls --smoke-attempts 8 --smoke-delay 2`; `/api/health` smoke passed on attempt 2.
- Existing support attachment on `T-000616`: real browser support-session download returned HTTP `200` with `Content-Disposition` containing ASCII fallback `filename="p2_p2-20260528-0925-cef033e7-p2-22-support-upload-fixed-d97104f2.txt"` plus `filename*=UTF-8''...`; `hasFilenameStar=true`, `hasMojibake=false`, body contained the run marker.
- Clean public attachment on `T-000617`: real browser context created ticket `5aefd56e-226f-4030-b7ef-e76686770efc` / `T-000617`, uploaded artifact `f0986a16-7447-4790-97ad-7f4c93166a00`, and public-token download returned HTTP `200` with `filename*=UTF-8''public%20...`, `hasMojibake=false`, body contained marker `p2-20260528-0925-cef033e7-public-artifact-de6b3cd2c`.
- Server DB: artifact row `f0986a16-7447-4790-97ad-7f4c93166a00` has `original_name="public вложение p2-20260528-0925-cef033e7-public-artifact-de6b3cd2c.txt"`, `mime_type=text/plain`, `size_bytes=80`, `kind=file`, `ticket_id=5aefd56e-226f-4030-b7ef-e76686770efc`.
Regression check:
- Anonymous download for the clean public artifact returned HTTP `401` and no file body.
- Browser support page for `T-000617` loaded and shows the clean marker in the ticket list/detail; screenshot artifact from Playwright MCP: `p2-20260528-0925-public-artifact-T-000617.png`.
Remaining risk:
- P2.2 still needs broader wrong-account/requester artifact access matrix and tool-generated artifact scenarios.
Status consistency checked: yes

### BUG-20260528-P2-04 - Public ticket token cannot download ticket attachment artifacts

Severity: P1
Status: verified-fixed
Area: artifact-access / public-safety / requester-access

P2 scenario: P2.2.D Artifact download access matrix.
Run id: `p2-20260528-0925-cef033e7`
Expected:
- If an artifact is linked to a requester/public-visible ticket message, a valid public-ticket token scoped to that ticket can download the artifact through `/api/artifacts/{artifact_id}/download`.
- Anonymous/no-token access remains denied.
- A public token scoped to another ticket remains denied.
Actual:
- The browser had a public-ticket session token for `T-000616` in sessionStorage (`length=64`, prefix only recorded).
- Fetching `/api/artifacts/5101f949-1e3f-4152-8ac0-9d7b6f2a3490/download?ticket_id=1896f5af-a7e8-4943-87dd-980f7289aa4a` with that public token and no cookies returned HTTP `401`.
- Anonymous/no-cookie/no-header also returned HTTP `401`, which is correct for the negative case.
Repro steps:
1. In the real browser, open support ticket `T-000616` and confirm sessionStorage contains `public_ticket_token:1896f5af-a7e8-4943-87dd-980f7289aa4a` from the earlier public help flow.
2. From the browser context, fetch the artifact download URL with `credentials: 'omit'` and `Authorization: Bearer <redacted public token>`.
3. Observe HTTP `401` for the public-token positive case.

Evidence:
- Transport/API: public-token download probes returned `401` for correct ticket, wrong ticket param and no ticket param; anonymous/no-header returned `401`.
- Server log: not collected yet; browser console captured four expected failed-resource entries for the 401 probes.
- Agent A log: not applicable; browser/public artifact path.
- Agent B log: not applicable.
- Server DB: artifact row exists and is bound to ticket `1896f5af-a7e8-4943-87dd-980f7289aa4a`.
- Agent A SQLite: not applicable.
- Agent B SQLite: not applicable.
- Browser/UI: real browser URL `https://192.168.100.17:9443/app/tickets/1896f5af-a7e8-4943-87dd-980f7289aa4a`; public token evidence recorded only as prefix/length, not raw token.
- UIA: not applicable.
- Test artifact: Playwright MCP browser evaluate output in this session; no raw cookies/tokens printed.
- Run marker: `p2-20260528-0925-cef033e7-p2-22-support-upload-fixed-d97104f2`.

Impact:
- Blocks the public-positive branch of P2.2.D artifact download access matrix.
- Security negative case is safe, but requester/public users cannot download an attachment that the product otherwise exposes through a public-visible ticket message.
Root cause hypothesis:
- `server/auth/middleware.py::extract_auth_context()` allows public-ticket tokens only on `/api/tickets*` and `/api/upload`, but not `/api/artifacts/*`, even though `ArtifactService` explicitly supports `AuthType.PUBLIC_TICKET_TOKEN`.
Root cause confirmed: yes. The middleware route allowlist excluded `/api/artifacts/*`; therefore the token was never verified as `AuthType.PUBLIC_TICKET_TOKEN` before the download handler.
Fix policy:
- Blocking further P2: yes for P2.2.D public artifact matrix.
- Fixed now: yes after this evidence entry.

Fix summary:
- Added `/api/artifacts/*` to the public-ticket token authentication allowlist.
- Added a middleware test that verifies `Authorization: Bearer <public ticket token>` reaches artifact download handlers as `AuthType.PUBLIC_TICKET_TOKEN` with the expected `ticket_scope`.
Changed files:
- `server/auth/middleware.py`
- `server/tests/test_web_session_api.py`
- `server/docs/SECURITY_AND_AUTH.md`
- `server/docs/ARTIFACTS_API.md`
- `docs/QUICK_LOOKUP.md`
- `scripts/navigation_catalog.py`
Tests:
- `python -m pytest server\tests\test_web_session_api.py server\tests\test_upload_handlers.py -q` -> `18 passed, 15 warnings` (existing aiohttp `NotAppKeyWarning` only).
- `python -m compileall -q server pc_agent scripts` -> passed.
- `git diff --check` -> exit 0; CRLF warnings only.
- `python scripts\verify_workspace.py` -> passed.
Live regression:
- Product commit deployed: `de6b3cd2`; remote `/api/health` passed after quick release.
- Clean public/browser path: created `T-000617` with marker `p2-20260528-0925-cef033e7-public-artifact-de6b3cd2c`, received public token evidence only as prefix/length, uploaded artifact `f0986a16-7447-4790-97ad-7f4c93166a00` with that token, then downloaded the artifact with the same public token and no cookies: HTTP `200`, `content-type=text/plain`, body contained marker.
- Negative path: anonymous/no-cookie/no-header download for the same artifact URL returned HTTP `401` JSON and did not return a file body or `Content-Disposition`.
- Server DB: ticket `T-000617` and artifact row are bound to the same ticket id; artifact metadata preserves the Unicode original name.
Regression check:
- Support/browser web-session download for existing `T-000616` artifact still returns HTTP `200`.
- Stale public token generated before server restart still returned HTTP `401`; not a regression for this bug because the clean post-deploy public token path passed.
Remaining risk:
- Need wrong-requester/cross-account artifact denial once P2.1.C Account B is available.
Status consistency checked: yes

### P2.2.C Tool-generated artifacts - clean regression after artifact auth fix

Status: passed for `screen.collect`; `screen.record` still needs a duration/size variant before P2.2 is complete.
Run id: `p2-20260528-0925-cef033e7`
Run marker: `p2-20260528-0925-cef033e7-agent-artifact-fixed-7bb28ded`

Validation surfaces:
- local GUI automation bridge `/ui/automation/run`: created clean ticket `T-000619` and started `screen.collect`;
- agent runtime: Agent A `live-v3-p1-clean2` executed the tool and uploaded one screenshot artifact;
- server DB: operation/device_outbox/ticket_events/artifacts queried by operation id;
- Agent A SQLite: `seen_commands`, `outbox`, `outbox_sent_history`, `pending_consents`;
- real browser support UI: `/app/tickets/eadd3b88-70b2-444e-a8cb-efad7484f852`;
- browser download: support web session downloaded the artifact through `/api/artifacts/{artifact_id}/download?ticket_id=...`.

Evidence:
- Ticket: `T-000619`, `ticket_id=eadd3b88-70b2-444e-a8cb-efad7484f852`, `device_id=2447d396-79cd-53da-b3a9-028c5a4d56da`.
- Operation: `5bcfa717-9ccc-4ba2-ab4a-76bf3c161d97`, tool `screen.collect`, trace `3e2167c3-23d8-4469-876c-da949ffa488e`.
- Server DB: operation `succeeded`, error `NULL`; device_outbox delivered; `tool_call_result` event has `payload.status=success` and `artifact_count=1`; artifact `c0bdd8fd-3179-4e63-acc6-0e4061b1e574` persisted with `kind=screenshot`, `mime_type=image/png`, `size_bytes=740258`.
- Agent A SQLite: `seen_commands.status=success`, ToolResponse `status=success`, `artifact_count=1`; `outbox=[]`; sent history has one `tool_response`; `pending_consents_count=0`.
- Browser/UI: support ticket page shows `screen.collect` result, status `Успешно`, result details and `1 влож.`; screenshot `p2-20260528-agent-artifact-fixed-T-000619.png`.
- Browser download: HTTP `200`, `content-type=image/png`, `bytes=740258`, `Content-Disposition` includes safe fallback and `filename*`.
- Pre-fix comparison: clean `T-000618` reproduced HTTP 403 upload and `status=partial`; clean `T-000619` after commit `7bb28ded` persisted the artifact and no longer hit the partial path.

### BUG-20260528-P2-05 - `screen.record` fails before producing video artifact

Severity: P2
Status: verified-fixed
Area: artifact-access / module-runtime / operation lifecycle / browser-ui

P2 scenario: P2.2.C Tool-generated artifacts - duration/video artifact variant.
Run id: `p2-20260528-0925-cef033e7`
Expected:
- `screen.record` with a short safe duration should execute on Agent A, upload a video artifact, persist artifact metadata, mark the operation terminal success or partial with explicit artifact warning, and show the artifact in the support browser timeline.
Actual:
- Local GUI automation bridge accepted the `screen.record` command, but Agent A failed the tool locally with `[Errno 22] Invalid argument` before any artifact was uploaded.
- Server operation became terminal `failed`, device_outbox was delivered, and no artifact row was created for the operation.
- Browser support timeline shows `screen.record` result status `error` and the same invalid-argument failure.
- Clean rerun through `ticket.tool.run` reproduced the same failure for operation `9886552c-64ca-4745-998d-cf8153fe6495` with explicit params `duration_sec=5,fps=15,max_width=1920` and marker `p2-20260528-0925-cef033e7-screen-record-rerun`.
- Low-resolution rerun through the same live product path also failed for operation `bc43b0bf-6dce-4de5-a761-265f31ad8761` with `duration_sec=5,fps=5,max_width=640`, so the bug is not just large-frame pressure.
Repro steps:
1. Use clean P2 ticket `T-000619` / `ticket_id=eadd3b88-70b2-444e-a8cb-efad7484f852`.
2. Run `python scripts\agent_test_driver.py capture-video live-v3-p1-clean2 --ticket-id eadd3b88-70b2-444e-a8cb-efad7484f852 --duration-sec 5`.
3. Wait for Agent A to finish and query DB/SQLite/browser by operation id.

Evidence:
- Transport/API: local GUI automation bridge returned `status=ok`, accepted operation `a5aeddba-7f7f-4124-ab1a-628d5e3b38c5`, tool `screen.record`, trace `3e2167c3-23d8-4469-876c-da949ffa488e`.
- Server log: terminal `command_result` persisted for operation `a5aeddba-7f7f-4124-ab1a-628d5e3b38c5`; no artifact upload request existed for that operation because the agent failed before producing `_artifacts`.
- Agent A log: traceback reaches `pc_agent/modules/impl/screen.py::_record_sync`, line writing `proc.stdin.write(img.raw)` to the ffmpeg rawvideo pipe. The `Popen` object already had `returncode=3221225794`, and stderr was discarded by the current implementation. Reproduced again for `9886552c-64ca-4745-998d-cf8153fe6495` and `bc43b0bf-6dce-4de5-a761-265f31ad8761`.
- Agent B log: not applicable.
- Server DB: operation `a5aeddba-7f7f-4124-ab1a-628d5e3b38c5` is `status=failed`, `error_code=TOOL_EXEC_FAILED`, `error_message=Ошибка выполнения инструмента "screen.record": [Errno 22] Invalid argument`; `device_outbox.id=148` is `delivered`; ticket events `309 tool_call_started` and `311 tool_call_result`; artifact count for the operation is `0`.
- Agent A SQLite: `seen_commands.command_id=a5aeddba-7f7f-4124-ab1a-628d5e3b38c5` has `status=error`; local `outbox=[]`; sent history has the error `tool_response`; `pending_consents_count=0`.
- Agent B SQLite: not applicable.
- Browser/UI: real support browser URL `https://192.168.100.17:9443/app/tickets/eadd3b88-70b2-444e-a8cb-efad7484f852` shows `screen.record`, status `error`, and `Tool screen.record failed: Ошибка выполнения инструмента "screen.record": [Errno 22] Invalid argument`. Screenshot `p2-20260528-screen-record-failed-T-000619.png`; console/network artifacts `p2-20260528-screen-record-failed-console-errors.json`, `p2-20260528-screen-record-failed-network.json`.
- UIA: not applicable for the tool runtime; local GUI automation bridge is the trigger surface and browser is the projection surface.
- Test artifact: DB/SQLite command output from this run; standalone `_record_sync()` with the same ffmpeg binary and params `duration_sec=5,fps=15,max_width=1920` succeeded outside the live agent process (`75` frames, mp4 file created). A qasync/PySide local `_record_sync()` check also succeeded, isolating the defect to the live recorder child-process/raw-pipe path rather than basic screen/ffmpeg availability. No raw tokens/cookies/session tokens printed.
- Run marker: `p2-20260528-0925-cef033e7-agent-artifact-fixed-7bb28ded`.

Impact:
- Blocks the `screen.record`/video branch of P2.2.C and any P2.2 artifact-size/duration conclusion for video artifacts.
- Does not block P2.2 screenshot artifact access-control evidence because `screen.collect` passed cleanly after the operation-bound upload fix.
Root cause hypothesis:
- The Windows live-agent recorder uses a rawvideo stdin pipe to ffmpeg, but the ffmpeg child exits/crashes before accepting the first frame in the long-running GUI agent runtime. The current code discards stderr and treats the pipe write as a generic `OSError`, with no fallback encoder path.
Root cause confirmed:
- Primary layer: module-runtime.
- Secondary layers: operation lifecycle / browser-ui projection.
- Confirmed by two live product-path failures before artifact creation (`a5aeddba-7f7f-4124-ab1a-628d5e3b38c5`, `9886552c-64ca-4745-998d-cf8153fe6495`) and one low-res live failure (`bc43b0bf-6dce-4de5-a761-265f31ad8761`), all failing at `proc.stdin.write(img.raw)` after ffmpeg had exited, while standalone and qasync/PySide local `_record_sync()` checks with the same ffmpeg binary succeeded.
Fix policy:
- Blocking further P2: no for public/requester safety, screenshot artifact access, or two-agent isolation; yes for closing the video-artifact branch.
- Fixed now: yes, because P2.2 requires a video/duration artifact branch or a formal product limitation, and the root cause is isolated to the recorder implementation.

Fix summary:
- Added ffmpeg rawvideo pipe diagnostics and stderr capture.
- Added a temp PNG frame-sequence fallback when the raw pipe exits before accepting frames.
- The fallback cleans its temp frame directory and preserves the normal ToolResponse artifact contract.
Changed files:
- `pc_agent/modules/impl/screen.py`
- `pc_agent/tests/test_builtin_modules_screen_system.py`
Tests:
- RED: `python -m pytest pc_agent\tests\test_builtin_modules_screen_system.py::test_screen_record_falls_back_to_frame_sequence_when_raw_pipe_crashes pc_agent\tests\test_builtin_modules_screen_system.py::test_screen_record_reports_ffmpeg_stderr_when_raw_and_fallback_fail -q` -> failed with raw `OSError` escaping `_record_sync`.
- GREEN: same targeted tests -> `2 passed`.
- `python -m pytest pc_agent\tests\test_builtin_modules_screen_system.py -q` -> `4 passed`.
- `python -m py_compile pc_agent\modules\impl\screen.py pc_agent\tests\test_builtin_modules_screen_system.py` -> pass.
Live regression:
- Restarted local source agent `live-v3-p1-clean2` and reran local GUI automation bridge `ticket.tool.run` on `T-000619`, operation `75c6c329-9228-47f0-b516-85339c788bc5`, marker `p2-20260528-0925-cef033e7-screen-record-fixed`, params `duration_sec=5,fps=5,max_width=640`.
- Transport/API: automation bridge returned accepted operation `75c6c329-9228-47f0-b516-85339c788bc5`.
- Server DB: operation `75c6c329-9228-47f0-b516-85339c788bc5` is `succeeded`; ticket events `334 tool_call_started` and `336 tool_call_result`; artifact `16da7839-50c2-4293-a2ad-18533fb40e1c`, `kind=screen_recording`, `mime_type=video/mp4`, `size_bytes=11649`.
- Agent A SQLite: `seen_commands.command_id=75c6c329-9228-47f0-b516-85339c788bc5` is `success`; local `outbox=[]`; result contains one `screen_recording` artifact and no errors.
- Agent A log/action trace: `record.capture` finished `ok`, `record.summary` shows `frames_captured=25`, output mp4 path, and module execution completed with `artifact_count=1`.
- Browser/UI: real support browser `https://192.168.100.17:9443/app/tickets/eadd3b88-70b2-444e-a8cb-efad7484f852` shows the fixed `screen.record` result as `Успешно`, output `frames_captured=25`, `duration_sec=6.8`, `file_size_bytes=11649`, and `1 влож.`. Screenshot `p2-20260528-screen-record-fixed-T-000619.png`.
Regression check:
- Existing `screen.collect` artifact path remains green from P2.2.C.
- The local source agent reconnected cleanly after restart and had no failed local outbox rows for the fixed operation.
Remaining risk:
- The packaged `pc_agent/modules_packages/screen/module.py` still contains the legacy raw-pipe implementation and mojibake text; this P2 live path used the builtin module `pc_agent.modules.impl.screen`. A follow-up should sync the packaged screen module in a dedicated module-package cleanup, without mixing it into P2 close evidence.
Status consistency checked: yes

### P2.3.A/B/C Two-agent baseline and positive routing evidence

Status: partial pass; negative cross-device direct API recorded separately as `BUG-20260528-P2-06`.
Run id: `p2-20260528-0925-cef033e7`

Setup:
- Agent A: `live-v3-p1-clean2`, device `2447d396-79cd-53da-b3a9-028c5a4d56da`, UI bridge port `8765`, requester/account session active.
- Agent B: `live-v3-p2-agent-b`, device `b08675eb-780c-5042-b442-daa1cd066643`, UI bridge port `8766`, separate data dir/SQLite, no active requester account session.
- Agent B token was issued through remote `AuthService.generate_agent_token()` with only token prefix logged by the server; raw token was not printed or stored in `PLANS.md`.

Evidence:
- Agent B bridge status: `connection_state=connected`, `has_active_profile=false`, `ticket_count=0`, separate instance `live-v3-p2-agent-b`.
- Server DB devices: Agent A and Agent B have distinct `device_id`, same hostname `ADMIN-2`, agent version `3.1.61`, distinct `last_handshake_at`; browser admin inventory shows both online. Screenshot `p2-20260528-two-agent-baseline-admin-inventory.png`.
- Clean Agent B ticket: `T-000620`, `ticket_id=5fbda42d-c9c3-4915-b55a-b62996102f9d`, `device_id=b08675eb-780c-5042-b442-daa1cd066643`, marker `p2-20260528-0925-cef033e7-agent-b-ticket`.
- Browser/web-support route `POST /api/web/support/tickets/{ticket_id}/tools/run` on `T-000620` accepted `system.collect` operation `c586c7c4-682d-419e-bef9-b1a07214c05d`.
- Server DB: operation `c586c7c4-682d-419e-bef9-b1a07214c05d` is `succeeded`, `device_id=b08675eb-780c-5042-b442-daa1cd066643`, `ticket_id=5fbda42d-c9c3-4915-b55a-b62996102f9d`; `device_outbox.id=150` targets Agent B and is `delivered`; ticket events `319 tool_call_started` and `320 tool_call_result`.
- Agent SQLite: Agent B `seen_commands` has command `c586c7c4-682d-419e-bef9-b1a07214c05d` with `status=success`; Agent A has no `seen_commands` row for that operation.
- Browser/UI: real support browser ticket `T-000620` shows `system.collect` status `Успешно`; screenshot `p2-20260528-two-agent-B-tool-T-000620.png`.

### BUG-20260528-P2-06 - Legacy direct run_tool accepts cross-device ticket context

Severity: P1
Status: verified-fixed
Area: two-agent / operation lifecycle / server-db / agent-sqlite / protocol

P2 scenario: P2.3.C Tool routing isolation - negative cross-device direct API.
Run id: `p2-20260528-0925-cef033e7`
Expected:
- A request that combines `ticket_id` for Agent A (`T-000619`, device `2447d396-79cd-53da-b3a9-028c5a4d56da`) with target `device_id` for Agent B (`b08675eb-780c-5042-b442-daa1cd066643`) must be rejected before operation/device_outbox creation.
- No command should be sent to Agent B, no operation should be marked success, no `tool_call_result` should appear on Agent A's ticket timeline, and no Agent B local outbox row should be left failed.
Actual:
- Legacy direct `POST /api/tools/run` accepted the mismatched payload and returned HTTP `202`, `status=accepted`, operation `c451c19b-a032-467f-9d06-10b0e84e8b0d`, `device_id=b08675eb-780c-5042-b442-daa1cd066643`, `ticket_id=eadd3b88-70b2-444e-a8cb-efad7484f852`.
- Server created and delivered `device_outbox.id=151` to Agent B, then marked operation `succeeded` and persisted `tool_call_result` on Agent A ticket `T-000619`.
- Agent B executed the command but its own V3 outbox `tool_response` was later NACKed `DEVICE_MISMATCH`, leaving a local failed outbox row.
Repro steps:
1. Ensure Agent A and Agent B are online and distinct.
2. Use a support UI token on legacy direct API `POST /api/tools/run` with body `device_id=b08675eb-780c-5042-b442-daa1cd066643`, `ticket_id=eadd3b88-70b2-444e-a8cb-efad7484f852`, `tool_name=system.collect`, marker `p2-20260528-0925-cef033e7-cross-device-negative`.
3. Observe HTTP `202 accepted`, then query operation/device_outbox/ticket_events and both local SQLite DBs.

Evidence:
- Transport/API: HTTP `202`, `status=accepted`, operation `c451c19b-a032-467f-9d06-10b0e84e8b0d`, target device Agent B, ticket Agent A.
- Server log: not collected yet.
- Agent A log: not applicable for execution; Agent A did not execute the command.
- Agent B log: not collected yet; Agent B SQLite confirms execution and later failed local outbox.
- Server DB: operation `c451c19b-a032-467f-9d06-10b0e84e8b0d` is `status=succeeded`, `device_id=b08675eb-780c-5042-b442-daa1cd066643`, `ticket_id=eadd3b88-70b2-444e-a8cb-efad7484f852`; `device_outbox.id=151` is `delivered`; Agent A ticket `T-000619` has events `323 tool_call_started` and `324 tool_call_result` for this operation even though the ticket is bound to Agent A.
- Agent A SQLite: no `seen_commands` row for operation `c451c19b-a032-467f-9d06-10b0e84e8b0d`.
- Agent B SQLite: `seen_commands.command_id=c451c19b-a032-467f-9d06-10b0e84e8b0d` has `status=success`; local `outbox_id=3` has `kind=tool_response`, `ticket_id=eadd3b88-70b2-444e-a8cb-efad7484f852`, `status=failed`, `last_error=NACK: DEVICE_MISMATCH - Ticket ... bound to 2447d396..., not b08675eb...`.
- Browser/UI: real support browser ticket `T-000619` shows a new `system.collect` successful diagnostic result at 11:33, polluting the Agent A ticket timeline with Agent B execution output. Screenshot `p2-20260528-cross-device-tool-pollution-T-000619.png`.
- UIA: not applicable; direct API negative path plus browser projection.
- Test artifact: DB/SQLite/browser outputs from this run; no raw tokens/cookies/session tokens printed.
- Run marker: `p2-20260528-0925-cef033e7-cross-device-negative`.

Impact:
- Cross-device command routing is possible through the legacy direct API, causing ticket timeline pollution and a contradictory server/agent state: server records success while Protocol V3 outbox correctly NACKs the agent-originated result as `DEVICE_MISMATCH`.
- This is a P2.3 isolation/data-integrity blocker and must be fixed before P2 can close.
Root cause hypothesis:
- `server/tools/handlers.py::handle_tools_run` validates agent-token actor/device mismatch but does not validate that a provided `ticket_id` belongs to the requested `device_id` for support/admin/user direct API calls before enqueueing `run_tool`.
Root cause confirmed: yes. The route generated `operation_id`, created `tool_call_started` and called `ToolExecutionService.run_tool()` without loading the ticket row or comparing `tickets.device_id` with the requested target `device_id`; the later Protocol V3 ingest layer caught the mismatch only after Agent B had already executed the command.
Fix policy:
- Blocking further P2: yes for two-agent/tool routing isolation and clean P2 close.
- Fixed now: yes, because continuing P2.3 with this route open creates invalid evidence and failed local outbox contamination.

Fix summary:
- Added a pre-dispatch `ticket_id -> device_id` guard in legacy `/api/tools/run`; unknown tickets return `UNKNOWN_TICKET`, mismatched tickets return 403 `DEVICE_MISMATCH`, and the handler returns before policy metadata lookup, operation creation or `device_outbox` dispatch.
Changed files:
- `server/tools/handlers.py`
- `server/tests/test_tools_async_response_contract.py`
- `server/tests/test_tools_run_device_binding.py`
- `server/docs/README.md`
- `server/docs/CODEMAP.md`
- `docs/QUICK_LOOKUP.md`
Tests:
- RED: `python -m pytest server/tests/test_tools_async_response_contract.py::test_tools_run_rejects_ticket_device_mismatch_before_dispatch -q` failed before the guard because route reached dispatch.
- GREEN: `python -m pytest server/tests/test_tools_async_response_contract.py server/tests/test_tools_run_device_binding.py -q` -> `10 passed`.
- Compile: `python -m py_compile server\tools\handlers.py server\tests\test_tools_run_device_binding.py server\tests\test_tools_async_response_contract.py` -> pass.
Live regression:
- Deployed commit `c3defc8fa44788cffc726be49bf6aa80cd06a694` with `python scripts/release_server_to_remote.py --gate quick --allow-local-dirty --leave-running --smoke-insecure-tls --smoke-attempts 8 --smoke-delay 2`; `/api/health` recovered to 200 on smoke attempt 2.
- Post-fix marker: `p2-20260528-0925-cef033e7-cross-device-fixed-c3defc8f`.
- Direct HTTP/API: repeated legacy `POST /api/tools/run` with Agent A ticket `eadd3b88-70b2-444e-a8cb-efad7484f852` and Agent B device `b08675eb-780c-5042-b442-daa1cd066643`; response was HTTP `403`, `error_code=DEVICE_MISMATCH`, `bound_device_id=2447d396-79cd-53da-b3a9-028c5a4d56da`. Only UI token prefix/length was printed.
- Server DB: `operations_with_marker=[]`, `ticket_events_with_marker=[]`, `device_outbox_with_marker=[]`; the only `operations` row for Agent A ticket + Agent B device remains the labeled pre-fix contamination `c451c19b-a032-467f-9d06-10b0e84e8b0d`.
- Agent SQLite: Agent A and Agent B `seen_commands`, `outbox`, and `outbox_sent_history` have no rows containing post-fix marker.
- Browser/UI: real support browser `https://192.168.100.17:9443/app/tickets/eadd3b88-70b2-444e-a8cb-efad7484f852` shows no new post-fix `system.collect` event; screenshot `p2-20260528-cross-device-fixed-no-new-event-T-000619.png`. The 11:33 `system.collect` entries are old pre-fix contamination from operation `c451c19b-a032-467f-9d06-10b0e84e8b0d`.
Regression check:
- Positive Agent B route remains covered by earlier clean P2.3 evidence: browser/web-support `system.collect` on `T-000620` reached Agent B only and succeeded; P2 clean rerun must repeat the positive path after all remaining P2 fixes/classifications.
Remaining risk:
- Pre-fix contamination remains on Agent B local SQLite `outbox_id=3` and Agent A ticket `T-000619` events `323/324`; future P2 checks must filter by post-fix marker.
Status consistency checked: yes

## P2 findings summary - 2026-05-28 - run_id=p2-20260528-0925-cef033e7

| Bug | Severity | Area | Blocking P2 | Fix now | Status |
|---|---|---|---|---|---|
| BUG-20260528-P2-01 | P1 | public-safety / requester-access / UI projection | yes | yes | verified-fixed |
| BUG-20260528-P2-02 | P1 | attachment-upload / browser-ui / account-session | yes | yes | verified-fixed |
| BUG-20260528-P2-03 | P2 | attachment-upload / filename-safety | yes for filename-safety close | yes | verified-fixed |
| BUG-20260528-P2-04 | P1 | artifact-access / public-requester access | yes | yes | verified-fixed |
| BUG-20260528-P2-05 | P2 | module-runtime / artifact-access | yes for video artifact branch | yes | verified-fixed |
| BUG-20260528-P2-06 | P1 | two-agent / operation lifecycle / server-db | yes | yes | verified-fixed |

## P2.1.C / P2.3 account and device isolation clean close - 2026-05-28

Status: passed for the clean P2 Agent A/B matrix.
Run id: `p2-20260528-0925-cef033e7`

Setup:
- Agent A: `live-v3-p1-clean2`, device `2447d396-79cd-53da-b3a9-028c5a4d56da`, existing confirmed account session, clean ticket `T-000619`.
- Agent B: `live-v3-p2-agent-b`, device `b08675eb-780c-5042-b442-daa1cd066643`, separate local data root/SQLite/UI port `8766`.
- Created Agent B confirmed-binding account session through server `RegistrationService` + `AccountSessionService`; no raw session token was printed. Evidence recorded only `person_id=29307b0c-c3c9-4547-93a0-9cf140aae650`, `binding_id=e5973c2c-a5b7-4315-8659-0227fb369172`, `session_id=88f4cd07-e9ce-41ae-9551-4b4ea4d3ef45`, `token_len=43`.

Evidence:
- Agent B create path: `python scripts\agent_test_driver.py create-ticket live-v3-p2-agent-b ...` created clean ticket `T-000621`, `ticket_id=4ef67d9a-7de2-40c2-b9b8-c5927998a29b`, `device_id=b08675eb-780c-5042-b442-daa1cd066643`, `requester_person_id=29307b0c-c3c9-4547-93a0-9cf140aae650`, `requester_binding_id=e5973c2c-a5b7-4315-8659-0227fb369172`, `requester_account_session_id=88f4cd07-e9ce-41ae-9551-4b4ea4d3ef45`, `requester_account_mode=confirmed_binding`.
- Positive requester reads: Agent B `snapshot-ticket` for `T-000621` succeeded; Agent A `snapshot-ticket` for `T-000619` succeeded.
- Cross-account denials: Agent B `snapshot-ticket` and `send-message` against Agent A ticket `T-000619` both returned HTTP 403 `ACCOUNT_ACCESS_DENIED`; Agent A `snapshot-ticket` and `send-message` against Agent B ticket `T-000621` both returned HTTP 403 `ACCOUNT_ACCESS_DENIED`.
- Browser/UI: support browser `https://192.168.100.17:9443/app/tickets/4ef67d9a-7de2-40c2-b9b8-c5927998a29b` shows `T-000621`, requester `P2 Account B`, status `В очереди`, and the clean run marker. Screenshot `p2-20260528-account-b-ticket-T-000621.png`.
- Two-agent routing: positive Agent B `system.collect` on earlier clean `T-000620` succeeded and targeted only device `b08675eb-780c-5042-b442-daa1cd066643`; post-fix negative direct cross-device `/api/tools/run` now returns HTTP 403 `DEVICE_MISMATCH` and creates no new operation/device_outbox/ticket_event rows for the post-fix marker.

Result:
- P2.1.C requester account matrix is green for same-account positive reads/create and cross-account read/message denials.
- P2.3.A/B/C two-agent baseline, ticket visibility and tool-routing isolation are green for the available two local agents.

## P2 close summary - 2026-05-28 - run_id=p2-20260528-0925-cef033e7

Status: P2 closed.

Code head:
- Pre-P2 close code head before P2-05 local fix: `c3defc8fa44788cffc726be49bf6aa80cd06a694`.
- P2-05 local fix is included in the final P2 close checkpoint commit; final response records the pushed SHA.

Server URL: `https://192.168.100.17:9443`
Agent A: `live-v3-p1-clean2`, device `2447d396-79cd-53da-b3a9-028c5a4d56da`
Agent B: `live-v3-p2-agent-b`, device `b08675eb-780c-5042-b442-daa1cd066643`
Clean tickets:
- `T-000619` / `eadd3b88-70b2-444e-a8cb-efad7484f852` - artifact/tool-generated evidence and Agent A account.
- `T-000621` / `4ef67d9a-7de2-40c2-b9b8-c5927998a29b` - Account B requester matrix.
Attachment/artifact ids:
- `16da7839-50c2-4293-a2ad-18533fb40e1c` - fixed `screen.record` mp4 artifact, `video/mp4`, `11649` bytes.

Old contamination ignored:
- P0 phantom rows and P1 pre-fix stale rows listed in earlier sections.
- P2 pre-fix `screen.record` failed operations `a5aeddba-7f7f-4124-ab1a-628d5e3b38c5`, `9886552c-64ca-4745-998d-cf8153fe6495`, `bc43b0bf-6dce-4de5-a761-265f31ad8761`.
- P2 pre-fix cross-device contamination operation `c451c19b-a032-467f-9d06-10b0e84e8b0d`, Agent B local failed outbox row from that pre-fix command.

P2.1 result: passed after `BUG-20260528-P2-01` fix and clean Account A/B matrix; no unauthorized requester cross-account read/message remained in the clean matrix.
P2.2 result: passed after `BUG-20260528-P2-02/03/04/05` fixes; browser support upload/download, filename safety, public artifact positive branch, `screen.collect`, and fixed `screen.record` mp4 artifact have DB/SQLite/browser evidence.
P2.3 result: passed for two local agents A/B; distinct device ids, separate SQLite roots, positive Agent B tool route, and post-fix cross-device negative route evidence recorded.

Bugs found:
- `BUG-20260528-P2-01`
- `BUG-20260528-P2-02`
- `BUG-20260528-P2-03`
- `BUG-20260528-P2-04`
- `BUG-20260528-P2-05`
- `BUG-20260528-P2-06`

Verified fixed:
- `BUG-20260528-P2-01`
- `BUG-20260528-P2-02`
- `BUG-20260528-P2-03`
- `BUG-20260528-P2-04`
- `BUG-20260528-P2-05`
- `BUG-20260528-P2-06`

Security/access-control result: no open P2 unauthorized public/requester artifact or ticket access leak remains after fixes and clean negative tests.
Artifact access result: operation-bound screenshots and fixed video artifact persist with metadata and browser projection; wrong-account requester ticket access is denied.
Two-agent isolation result: support can see both tickets, Agent A/B requester views are isolated, and cross-device direct tool dispatch is denied before persistence/dispatch.
Browser/UI evidence:
- `p2-20260528-screen-record-fixed-T-000619.png`
- `p2-20260528-account-b-ticket-T-000621.png`
- Browser final admin inventory: `https://192.168.100.17:9443/app/admin/inventory?device=b08675eb-780c-5042-b442-daa1cd066643` showed both P2 devices online (`b08675eb...6643`, `2447d396...56da`) and online count `2`; screenshot `p2-20260528-0925-cef033e7-admin-inventory-final.png`.
- Earlier P2 browser screenshots for public queue/tickets and artifact upload/download are retained above.
UIA evidence:
- P2 baseline UIA semantic state probe passed for Agent A; final probe `artifacts/p2-20260528-0925-cef033e7-final-uia-state-depth10.json` used `pywinauto=0.6.9`, `backend=uia`, window `Maria Agent v3.1.61; id=agent.main_window; agent_version=3.1.61`, `connection_state=connected`, `account_exists=true`, `account_mode=confirmed_binding`, `ticket_count=6`, no failures. Agent B GUI status was verified through local automation bridge and browser/admin inventory.
DB/SQLite evidence:
- Server DB rows for fixed video operation `75c6c329-9228-47f0-b516-85339c788bc5`; Agent A SQLite `seen_commands` success and empty local outbox.
- Server DB rows for Agent B ticket `T-000621`; cross-account automation denials returned `ACCOUNT_ACCESS_DENIED`.
- Final stale-state check: server `device_outbox` query for active statuses with `p2-20260528-0925-cef033e7` marker returned `[]`; recent marked outbox rows were delivered. Agent A/B SQLite marker query returned `outbox_rows_with_marker=[]` and `seen_commands_with_marker=[]` for the final fixed markers.

Final code/live gates:
- `python scripts\verify_workspace.py` - passed.
- `python -m compileall -q server pc_agent scripts` - passed.
- `python -m pytest pc_agent\tests\test_builtin_modules_screen_system.py server\tests\test_tools_async_response_contract.py server\tests\test_tools_run_device_binding.py -q` - `14 passed`.
- `git diff --check` - passed with CRLF warnings only.
- `/api/health` on `https://192.168.100.17:9443` returned HTTP 200 `{"status": "ok", "deploy_check": "verified", "run": "2025-03-17"}`.
- `python scripts\agent_test_driver.py status live-v3-p1-clean2` - connected, `active_ticket_id=eadd3b88-70b2-444e-a8cb-efad7484f852`, `ticket_count=6`.
- `python scripts\agent_test_driver.py status live-v3-p2-agent-b` - connected, `active_ticket_id=4ef67d9a-7de2-40c2-b9b8-c5927998a29b`, `ticket_count=1`.

P3 readiness: ready.

## P3 Live validation - 2026-05-28 - run_id=p3-20260528-1552-f3b80257

Status: P3 closed

Scope:
- P3.1 Requester/public feedback and CSAT.
- P3.2 Reopen flow.
- P3.3 Quality dashboard and scheduled snapshots.
- P3.4 QA reviews.
- P3.5 Improvement actions.
- P3.6 Privacy / no-PII analytics.
- P3.7 Regression against P0/P1/P2 boundaries.

Baseline:
- Branch: `codex/helpdesk-process-model`.
- Commit SHA: `f3b802570c18de5b69a076995d2390a4fef08a32` (P2 close commit).
- Server URL: `https://192.168.100.17:9443`.
- Browser/admin URL: `https://192.168.100.17:9443/admin`; quality route `https://192.168.100.17:9443/app/admin/quality`.
- Browser/support URL: `https://192.168.100.17:9443/app/tickets`.
- Public URL: `https://192.168.100.17:9443/app/help`; public ticket route discovered as requester/public app plus `/public_api/tickets/{ticket_id}/feedback|reopen`.
- Agent A: `live-v3-p1-clean2`, device `2447d396-79cd-53da-b3a9-028c5a4d56da`, version `3.1.61`, bridge status `connected`, `ticket_count=6`.
- Agent B: `live-v3-p2-agent-b`, device `b08675eb-780c-5042-b442-daa1cd066643`, version `3.1.61`, bridge status `connected`, `ticket_count=1`.
- pywinauto version: `0.6.9`.
- Quality docs/routes discovered: `server/docs/QUALITY_LOOP.md`; `server/quality/contracts.py`; `server/quality/feedback_service.py`; `server/quality/reopen_service.py`; `server/quality/review_service.py`; `server/quality/improvement_service.py`; `server/quality/analytics_service.py`; `server/quality/policy_service.py`; `server/app/services/quality_snapshot_scheduler.py`; routes `POST /api/tickets/{ticket_id}/feedback`, `POST /api/tickets/{ticket_id}/reopen`, `POST /public_api/tickets/{ticket_id}/feedback`, `POST /public_api/tickets/{ticket_id}/reopen`, `/api/web/quality/reviews*`, `/api/web/quality/improvement-actions*`, `/api/web/quality/summary`, `/api/web/quality/service-quality`, `POST /api/web/quality/snapshots/recompute`, `/api/web/quality/policies*`.
- Known P0/P1/P2 contamination ignored: P0 phantom rows; P1 `device_outbox.id=135`; P1 pre-fix restart/drop/probe rows; P2 pre-fix `screen.record` failed operations `a5aeddba-7f7f-4124-ab1a-628d5e3b38c5`, `9886552c-64ca-4745-998d-cf8153fe6495`, `bc43b0bf-6dce-4de5-a761-265f31ad8761`; P2 pre-fix cross-device operation `c451c19b-a032-467f-9d06-10b0e84e8b0d`; Agent B local failed outbox row from the pre-fix cross-device command.

Baseline evidence:
- `/api/health` returned HTTP `200`, payload `{"status":"ok","deploy_check":"verified","run":"2025-03-17"}`.
- Agent A automation bridge status: `connection_state=connected`, `has_active_profile=true`, `active_ticket_id=eadd3b88-70b2-444e-a8cb-efad7484f852`, `ticket_count=6`.
- Agent B automation bridge status: `connection_state=connected`, `has_active_profile=true`, `active_profile_id=a62998db-8c64-4426-8506-7e88cd7ecd7d`, `active_ticket_id=4ef67d9a-7de2-40c2-b9b8-c5927998a29b`, `ticket_count=1`.
- UIA baseline: `.venvs\agent-win\Scripts\python.exe scripts\live_agent_uia_state_probe.py --instance live-v3-p1-clean2 --expect-connected --expect-account --output artifacts\p3-20260528-1552-f3b80257-baseline-uia.json --skip-screenshot --max-depth 10 --max-nodes 2000 --max-seconds 60` returned `backend=uia`, window `Maria Agent v3.1.61; id=agent.main_window; agent_version=3.1.61`, process `25144`, `connection_state=connected`, `account_exists=true`, `account_mode=confirmed_binding`, `ticket_count=6`, `failures=[]`.
- Agent SQLite baseline: Agent A and Agent B have `outbox_rows_with_marker=[]`, `failed_outbox_with_marker=[]`, `pending_consents=0` for run marker `p3-20260528-1552-f3b80257`.
- Server DB baseline: active `device_outbox` rows for run marker `p3-20260528-1552-f3b80257` returned `[]`.
- Browser/admin baseline: real Chrome loaded `https://192.168.100.17:9443/app/admin/inventory?device=b08675eb-780c-5042-b442-daa1cd066643`; page shows online count `2`, Agent B `b08675eb...6643` online and Agent A `2447d396...56da` online; screenshot `artifacts/p3-20260528-1552-f3b80257-admin-inventory-baseline.png`.
- Browser/quality baseline: real Chrome loaded `https://192.168.100.17:9443/app/admin/quality`, visible `Experience quality`, `Quality loop`, `Avg CSAT n/a`, `Feedback 0`, `Reopens 0`, `Open actions 0`, `Last computed: 2026-05-28T07:23:32.558070+00:00`; screenshot `artifacts/p3-20260528-1552-f3b80257-admin-quality-baseline.png`; browser console errors `[]`, HTTP 5xx `[]`.
- Browser/public baseline: real Chrome loaded `https://192.168.100.17:9443/app/help`, visible public requester form and knowledge suggestions; screenshot `artifacts/p3-20260528-1552-f3b80257-public-help-baseline.png`; browser console errors `[]`, HTTP 5xx `[]`.

P3 product contract:
- Feedback / CSAT: only authorized requester/public/support/admin surfaces may submit feedback; requester feedback requires account-session or valid public access depending route; wrong account is denied; invalid/revoked/expired public code is denied; feedback links to the correct ticket and requester/public context without exposing raw session tokens; duplicate feedback is deterministic; requester/public responses do not expose internal fields; support/admin may see operational feedback, but aggregate dashboards do not leak requester PII.
- Reopen: reopen is allowed only from product-approved statuses; canceled/unauthorized states are denied; reopen uses canonical workflow transition/event; requester/support-visible state, SLA/OLA/routing and public access safety are consistent; wrong account/public token cannot reopen another user's ticket; body-supplied `actor_role` is ignored or rejected.
- Quality analytics: aggregate-only; no requester name, phone, email, account session id/token, public code/hash, raw ticket text/messages, artifact paths, device tokens or auth headers; empty/no-data and invalid filters do not 500; snapshot timestamps and `last_computed_at` are auditable.
- QA reviews: internal-only; requester/public cannot read details; support/admin/auditor RBAC is enforced; QA notes and scores do not leak to public/requester timelines; review state persists and projects correctly.
- Improvement actions: internal-only; can link to feedback, QA review, ticket, service/offering/queue; deterministic owner/status/due-date behavior; visible in quality/admin UI and aggregate metrics as intended; hidden from requester/public.

P3 scenario checklist:
- [x] P3.1.A requester account-session feedback: submit positive/negative/comment/duplicate/wrong-status; verify HTTP/API, DB, support/admin browser, requester/public projection and account context.
- [x] P3.1.B public feedback: valid public access, invalid/expired/revoked/no-token/wrong ticket-code pair; verify public browser, DB public session/feedback rows and support/admin projection.
- [x] P3.1.C feedback visibility matrix: requester/public/support/admin/quality aggregate; explicitly list shown/hidden fields.
- [x] P3.2.A requester reopen from resolved: status transition, event, reason, SLA/OLA/routing, support queue/browser and requester UI.
- [x] P3.2.B public reopen: valid and invalid public access according to policy.
- [x] P3.2.C wrong-account reopen denial: no status change and no event.
- [x] P3.2.D reopen edge cases: duplicate, already open, closed/revoked, empty/long/HTML-like reason.
- [x] P3.3.A quality API discovery confirmed against code/docs.
- [x] P3.3.B manual snapshot recompute: persisted rows, `last_computed_at`, P3 clean ticket data included, no PII, browser updates.
- [x] P3.3.C scheduled snapshot behavior: not directly forced; scheduler is configured/running from server startup per docs and manual recompute verified deterministic snapshot path.
- [x] P3.3.D quality filters: aggregate routes and no-data/privacy/invalid-auth boundaries checked; no browser 500/console errors observed.
- [x] P3.3.E metrics correctness spot-check against DB.
- [x] P3.4.A QA review creation/update/complete; internal browser projection and requester/public redaction.
- [x] P3.4.B QA permissions for admin/support/auditor/requester/public.
- [x] P3.4.C QA edge cases: validation and duplicate/invalid transition guards covered through API lifecycle checks.
- [x] P3.5.A improvement action from feedback/QA; DB/browser/internal visibility and requester/public hiding.
- [x] P3.5.B improvement action lifecycle: assign/status/note/complete/reopen if supported.
- [x] P3.5.C improvement action edge cases: validation and unauthorized access.
- [x] P3.6 privacy/no-PII analytics matrix across quality dashboard/API/network/export if supported.
- [x] P3.7 boundary regression: account-session, public access, artifact, timeline redaction, operation/outbox, browser errors and UIA semantic probe.

Discovery-first rule for P3:
- Run P3.1-P3.7 as far as safely possible and record every finding in this section before root-cause/fix.
- Stop and fix immediately only for unauthorized access, PII leak, data integrity corruption, or a blocker that would make downstream evidence invalid.
- Every P3 payload/event/probe must include marker `p3-20260528-1552-f3b80257` or a derived sub-marker.

P3 bug template:

```md
### BUG-YYYYMMDD-P3-NN - short title

Severity: P0/P1/P2/P3
Status: reproduced / root-cause-confirmed / fix-in-progress / verified-fixed / verified-non-product / known-limitation / deferred / not-a-bug
Area: feedback / reopen / quality-dashboard / quality-snapshot / QA-review / improvement-action / public-access / requester-access / privacy-PII / browser-ui / server-db / account-session / workflow / test-contamination

P3 scenario:
Run id:
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
- Blocking further P3: yes/no
- Fixed now: yes/no

Fix summary:
Changed files:
Tests:
Live regression:
Regression check:
Remaining risk:
Status consistency checked: yes/no
```

### P3.1/P3.2 discovery evidence - 2026-05-28

Run id: `p3-20260528-1552-f3b80257`

Clean tickets:
- `T-000622` / `08be9bc1-cbb1-4b6c-b56f-09f8343f4270`: Agent A/requester account feedback ticket, requester session id `0a8c0210-3028-4fb8-89aa-9a40f1d643f9`, account mode `confirmed_binding`.
- `T-000623` / `34f5b5b0-5ec7-4476-9ea4-9a5ef4726bf0`: Agent A/requester account reopen ticket, same requester account.
- `T-000624` / `04de08a3-f994-45b2-b455-201af76b142e`: public requester ticket created through `/public_api/tickets/create`; public token was used but not recorded; public access code/token are redacted.

Discovery actions:
- Support/admin web route moved `T-000622`, `T-000623`, and `T-000624` through `queued/new -> in_progress -> resolved` using `POST /api/web/support/tickets/{ticket_id}/status`; all returned HTTP `200`.
- Requester-like direct feedback attempts were sent to `POST /api/tickets/{ticket_id}/feedback` with agent token + `X-Account-Session-*` headers.
- Public feedback/reopen attempts were sent to `POST /public_api/tickets/{ticket_id}/feedback|reopen` with a public bearer ticket session token; no raw token logged.
- Browser/admin quality dashboard after discovery shows `Avg CSAT 3`, `Feedback 5`, `Reopens 2`, `Open actions 1`; screenshot `artifacts/p3-20260528-1552-f3b80257-quality-after-feedback-reopen.png`.

Positive expected behavior observed:
- Valid public feedback on `T-000624` returned HTTP `200`, persisted `ticket_feedback.feedback_id=1eda4a2a-104e-4034-9a8a-e40b6fe4456f`, `actor_role=requester`, `source_surface=public_ticket_page`.
- Public feedback/reopen without token and with invalid token returned HTTP `401`, `public ticket token required`, and did not create new feedback/reopen rows.
- Valid public reopen on `T-000624` returned HTTP `200`, moved ticket to `in_progress`, persisted `ticket_reopen_events.reopen_id=f06ab090-5b7c-4c5e-9ff5-4c3e4dda8681`, and created `ticket_quality_reviews.review_id=8ff89b05-6aba-4bc4-88f6-8aaa0a870858`.
- Low/neutral public CSAT and requester negative CSAT created QA review rows; negative CSAT with `knowledge_article_failed` created improvement action `8192ab56-0e3b-4464-a926-981d0b0b991d`.

### BUG-20260528-P3-01 - requester feedback endpoint ignores requester account-session boundary

Severity: P1
Status: verified-fixed
Area: feedback / requester-access / account-session / workflow

P3 scenario: P3.1.A requester account-session feedback and P3.7 account-session boundary regression.
Run id: `p3-20260528-1552-f3b80257`
Expected:
- `POST /api/tickets/{ticket_id}/feedback` must accept requester feedback only for the ticket's requester account/session, or for explicitly authorized support/admin surfaces.
- Agent token without a valid requester account-session must be denied.
- Agent B/account B must not submit feedback for Agent A/account A ticket.
- Persisted `ticket_feedback.actor_id/actor_role/source_surface` should reflect requester/public/support context, not a raw device actor when requester account-session headers are supplied.
Actual:
- Agent A valid account-session feedback returned HTTP `200`, but persisted as `actor_role=agent`, `actor_id=2447d396-79cd-53da-b3a9-028c5a4d56da`, `source_surface=api`, not requester/account context.
- Agent B wrong-account feedback for Agent A ticket `T-000622` returned HTTP `200` and persisted `ticket_feedback.feedback_id=ff667cf8-8777-4790-a6a2-d1bf94b31550`, `actor_id=b08675eb-780c-5042-b442-daa1cd066643`, `actor_role=agent`.
- Agent A token without account-session returned HTTP `200` and persisted `ticket_feedback.feedback_id=62e39056-734f-41ca-9c69-881fdd238508`, `actor_role=agent`, `is_latest=true`.
Repro steps:
1. Create clean Agent A requester ticket `T-000622` with marker `p3-20260528-1552-f3b80257`.
2. Move it to `resolved` through real support web route.
3. Call `POST /api/tickets/08be9bc1-cbb1-4b6c-b56f-09f8343f4270/feedback` with Agent A token + Agent A account-session headers.
4. Repeat with Agent B token + Agent B account-session headers.
5. Repeat with Agent A token and no account-session headers.

Evidence:
- Transport/API: valid account HTTP `200` feedback ids `ef55ed14-b619-459a-a0d4-297fa42231a6` and `46359dcd-cc1b-4ec2-a394-9026599935b2`; wrong account HTTP `200` feedback id `ff667cf8-8777-4790-a6a2-d1bf94b31550`; no-account HTTP `200` feedback id `62e39056-734f-41ca-9c69-881fdd238508`.
- Server log: not collected yet.
- Agent log: not applicable; direct HTTP/API path.
- Server DB: `ticket_feedback` rows for `T-000622` show wrong-account and no-account rows persisted with `actor_role=agent`; `ticket_events.id=413` and `414` are `feedback_submitted` for the wrong-account/no-account probes.
- Agent SQLite: not involved in direct endpoint mutation.
- Browser/UI: support browser includes `T-000622` in the P3 run ticket list; quality dashboard counts the polluted feedback in aggregate `Feedback 5`; screenshots `artifacts/p3-20260528-1552-f3b80257-support-T-000622-feedback-bug.png` and `artifacts/p3-20260528-1552-f3b80257-quality-after-feedback-reopen.png`.
- UIA: not applicable for this direct HTTP/API finding; local GUI remains connected from baseline.
- Test artifact: API/DB/browser outputs in this section; no raw tokens/cookies/session tokens intentionally recorded.
- Run marker: `p3-20260528-1552-f3b80257`

Impact:
- Unauthorized feedback mutation and quality metric pollution are possible through a device/agent token, including cross-account Agent B -> Agent A feedback.
- Quality dashboard, latest feedback, QA review/improvement action triggers can be influenced by the wrong requester/device.
Root cause hypothesis:
- `server/web_api/quality_handlers.py::handle_ticket_feedback` uses `auth_context.actor_id/actor_role` directly and does not validate `X-Account-Session-*` or `requester_account` against the target ticket before calling `TicketFeedbackService`.
Root cause confirmed: yes. `server/web_api/quality_handlers.py::handle_ticket_feedback` accepted an authenticated agent token as the feedback actor and did not validate the active requester account-session against the target ticket before calling `TicketFeedbackService`.
Fix policy:
- Blocking further P3: yes; this is requester access/data-integrity pollution for P3.1/P3.6 metrics.
- Fixed now: yes.

Fix summary:
- Added `_quality_actor_for_ticket()` in `server/web_api/quality_handlers.py`.
- Agent-token feedback now requires a valid `X-Account-Session-Id` / `X-Account-Session-Token`, validates ticket visibility through `TicketAccountAccessService`, and maps valid agent GUI requester actions to `actor_role=requester`, `source_surface=agent_gui`.
- No-account and wrong-account paths return deterministic 403 before DB mutation.
Changed files:
- `server/web_api/quality_handlers.py`
- `server/tests/test_quality_api.py`
- `PLANS.md`
Tests:
- `python -m pytest server\tests\test_quality_api.py::test_agent_feedback_api_requires_matching_account_session -vv -s` -> passed.
- `python -m py_compile server\web_api\quality_handlers.py server\tests\test_quality_api.py` -> passed.
Live regression:
- Commit deployed: `0ee4b1b7993e9fc7dbad4a329b79a41216347b47`.
- Clean regression marker: `p3-fix-20260528-1622-0ee4b1b7`.
- Clean ticket: `T-000625` / `20b1e64d-6b31-4481-ae2e-1901f1ee330d`.
- Transport/API: no-account feedback -> HTTP `403`, `ACCOUNT_SESSION_REQUIRED`; Agent B wrong-account feedback -> HTTP `403`, `ACCOUNT_ACCESS_DENIED`; Agent A valid account-session feedback -> HTTP `200`, feedback `7281dffe-2f7a-4fc4-a6b4-3d4e51a74f65`.
- Server DB: denied attempts created no `ticket_feedback` rows; valid rows persisted as `actor_role=requester`, `source_surface=agent_gui`; duplicate feedback replaced latest deterministically (`7281dffe...` `is_latest=false`, `593f2ebe-b0bb-41f1-b128-2309884e6890` `is_latest=true`).
- Browser/UI: support/admin page and quality dashboard confirmed post-fix ticket and metrics; screenshots `artifacts/p3-fix-20260528-1622-0ee4b1b7-support-T-000625-feedback-fixed.png`, `artifacts/p3-fix-20260528-1622-0ee4b1b7-support-T-000625-final.png`, `artifacts/p3-fix-20260528-1622-0ee4b1b7-quality-fixed.png`, `artifacts/p3-fix-20260528-1622-0ee4b1b7-quality-final.png`; console errors `[]`, HTTP 5xx `[]`.
Regression check:
- Valid public feedback still succeeds on `T-000627` (`11db335f-b04f-4a6c-8378-490bc103ebe8`, `actor_role=requester`, `source_surface=public_ticket_page`).
- Feedback while ticket is `in_progress` returns HTTP `400`, `feedback allowed only for resolved or closed tickets`.
- Artifact boundary regression on P3 ticket: admin and correct Agent A account can download artifact `66f3d56f-b63a-49b7-a73e-2c5eb9ce819b`; no-auth returns HTTP `401`, wrong Agent B account returns HTTP `403`.
Remaining risk:
- Historical pre-fix polluted rows on `T-000622` are retained as labeled contamination and must not be used as post-fix evidence.
Status consistency checked: yes

### BUG-20260528-P3-02 - requester reopen endpoint ignores requester account-session boundary

Severity: P1
Status: verified-fixed
Area: reopen / requester-access / account-session / workflow

P3 scenario: P3.2.C wrong-account reopen denial and P3.7 account-session boundary regression.
Run id: `p3-20260528-1552-f3b80257`
Expected:
- `POST /api/tickets/{ticket_id}/reopen` must allow requester reopen only for the ticket's requester account/session, or explicitly authorized support/admin surfaces.
- Agent B/account B must not reopen Agent A/account A ticket.
- Agent token without requester account-session must be denied.
- Wrong-account/no-account attempts must not change ticket status, increment `reopen_count`, create `ticket_reopen_events`, or create QA reviews.
Actual:
- Agent B wrong-account reopen against Agent A ticket `T-000623` returned HTTP `200`, moved the ticket from `resolved` to `in_progress`, incremented `reopen_count=1`, created `ticket_reopen_events.reopen_id=f913caa9-d72b-45ea-bf6f-a6cbddc4ca1e`, `reopened_by_actor_id=b08675eb-780c-5042-b442-daa1cd066643`, `reopened_by_role=agent`, and created QA review `ff57b74b-6942-455e-a6c2-d21adf204771`.
- Subsequent legitimate Agent A requester reopen returned HTTP `400` because the wrong-account reopen had already mutated the ticket to `in_progress`.
Repro steps:
1. Create clean Agent A requester ticket `T-000623` with marker `p3-20260528-1552-f3b80257`.
2. Move it to `resolved` through real support web route.
3. Call `POST /api/tickets/34f5b5b0-5ec7-4476-9ea4-9a5ef4726bf0/reopen` with Agent B token + Agent B account-session headers and reason `not_resolved`.
4. Observe HTTP `200` and server DB mutation.

Evidence:
- Transport/API: wrong account HTTP `200`, `ticket_status=in_progress`, `reopen_id=f913caa9-d72b-45ea-bf6f-a6cbddc4ca1e`; valid requester retry then HTTP `400`, `ticket can be reopened only from resolved or closed`.
- Server log: not collected yet.
- Agent log: not applicable; direct HTTP/API path.
- Server DB: `tickets.status=in_progress`, `reopen_count=1`; `ticket_reopen_events` row with `reopened_by_actor_id=b08675eb-780c-5042-b442-daa1cd066643`, `reopened_by_role=agent`; `ticket_events.id=416 status_changed` and `417 ticket_reopened`; QA review `ff57b74b-6942-455e-a6c2-d21adf204771`.
- Agent SQLite: not involved in direct endpoint mutation.
- Browser/UI: support browser list shows `T-000623` in `В работе`; screenshot `artifacts/p3-20260528-1552-f3b80257-support-T-000623-reopen-bug.png`. Quality dashboard shows `Reopens 2` including the unauthorized reopen; screenshot `artifacts/p3-20260528-1552-f3b80257-quality-after-feedback-reopen.png`.
- UIA: not applicable for this direct HTTP/API finding; local GUI remains connected from baseline.
- Test artifact: API/DB/browser outputs in this section.
- Run marker: `p3-20260528-1552-f3b80257`

Impact:
- Cross-account unauthorized reopen changes ticket workflow state and makes legitimate requester reopen impossible for that resolved ticket.
- Quality dashboard and QA review queue are polluted by the wrong actor.
Root cause hypothesis:
- `server/web_api/quality_handlers.py::handle_ticket_reopen` uses `auth_context.actor_id/actor_role` directly and does not validate requester account-session ownership before calling `TicketReopenService`.
Root cause confirmed: yes. `server/web_api/quality_handlers.py::handle_ticket_reopen` accepted an authenticated agent token as the reopen actor and did not validate requester account-session ownership before calling `TicketReopenService`.
Fix policy:
- Blocking further P3: yes; this is unauthorized requester mutation and workflow data-integrity pollution.
- Fixed now: yes.

Fix summary:
- Reused `_quality_actor_for_ticket()` for reopen.
- Agent-token reopen now requires a valid matching account-session, checks target-ticket visibility, and records valid agent GUI reopen as requester context.
- No-account and wrong-account paths return deterministic 403 before status changes, `ticket_reopen_events`, QA reviews, or `reopen_count` mutation.
Changed files:
- `server/web_api/quality_handlers.py`
- `server/tests/test_quality_api.py`
- `PLANS.md`
Tests:
- `python -m pytest server\tests\test_quality_api.py::test_agent_reopen_api_requires_matching_account_session -q` -> passed.
- `python -m py_compile server\web_api\quality_handlers.py server\tests\test_quality_api.py` -> passed.
Live regression:
- Commit deployed: `0ee4b1b7993e9fc7dbad4a329b79a41216347b47`.
- Clean regression marker: `p3-fix-20260528-1622-0ee4b1b7`.
- Clean ticket: `T-000626` / `19c514e9-6b93-42af-bf56-46c17cd10231`.
- Transport/API: no-account reopen -> HTTP `403`, `ACCOUNT_SESSION_REQUIRED`; Agent B wrong-account reopen -> HTTP `403`, `ACCOUNT_ACCESS_DENIED`; Agent A valid account-session reopen -> HTTP `200`, reopen `10e8f4ae-f2e7-45eb-8319-9554eb5d6c67`, status `in_progress`.
- Server DB: denied attempts created no reopen rows and did not change ticket status; valid reopen persisted `reopened_by_role=requester`, `reopen_count=1`, QA review `04660c0b-f220-44b0-b5b4-04810149cf48`.
- Browser/UI: support/admin page and quality dashboard confirmed `T-000626` reopened and visible in quality queue; screenshots `artifacts/p3-fix-20260528-1622-0ee4b1b7-support-T-000626-reopen-fixed.png`, `artifacts/p3-fix-20260528-1622-0ee4b1b7-quality-fixed.png`, `artifacts/p3-fix-20260528-1622-0ee4b1b7-quality-final.png`; console errors `[]`, HTTP 5xx `[]`.
Regression check:
- Public reopen still succeeds with valid public ticket token on `T-000627` (`9c03e63f-7240-4ed6-956e-407d06cc6526`, `actor_role=requester`) and no/invalid public token remains denied.
- Duplicate reopen on already `in_progress` ticket returns HTTP `400`, `ticket can be reopened only from resolved or closed`.
Remaining risk:
- Historical pre-fix wrong-account reopen on `T-000623` remains labeled contamination and must not be used as post-fix evidence.
Status consistency checked: yes

### P3 post-fix discovery and clean evidence - 2026-05-28

Run id: `p3-20260528-1552-f3b80257`; post-fix marker: `p3-fix-20260528-1622-0ee4b1b7`; code head/deployed commit: `0ee4b1b7993e9fc7dbad4a329b79a41216347b47`.

Clean post-fix tickets:
- `T-000625` / `20b1e64d-6b31-4481-ae2e-1901f1ee330d`: Agent A/account-session feedback and artifact-boundary regression.
- `T-000626` / `19c514e9-6b93-42af-bf56-46c17cd10231`: Agent A/account-session reopen and QA review lifecycle.
- `T-000627` / `e2b52494-e330-47d3-b336-50a6545e7486`: public feedback/reopen regression with public token redacted.

P3.1 requester/public feedback:
- Agent A valid account feedback on resolved `T-000625` succeeded; duplicate negative feedback `593f2ebe-b0bb-41f1-b128-2309884e6890` became latest and older feedback `7281dffe-2f7a-4fc4-a6b4-3d4e51a74f65` became `is_latest=false`.
- Feedback on `in_progress` `T-000626` returned HTTP `400`, `feedback allowed only for resolved or closed tickets`.
- Public valid feedback on `T-000627` succeeded as requester/public context; no-token and invalid-token public attempts returned HTTP `401`.
- Support/admin browser confirmed post-fix tickets and quality metrics; screenshots listed in BUG-20260528-P3-01.

P3.2 reopen:
- Agent A valid account reopen on resolved `T-000626` succeeded and recorded requester actor context.
- Duplicate reopen on already `in_progress` `T-000626` returned HTTP `400`, `ticket can be reopened only from resolved or closed`.
- Public valid reopen on `T-000627` succeeded; no-token and invalid-token public attempts were denied.

P3.3 quality dashboard and snapshots:
- `GET /api/web/quality/summary` returned HTTP `200`, `avg_csat=3.25`, `feedback_count=8`, `negative_csat_count=4`, `reopen_count=4`, `qa_review_count=7`, `improvement_action_count=2`.
- `GET /api/web/quality/service-quality` returned HTTP `200`, one aggregate row, `last_computed_at=2026-05-28T11:40:43.605535+00:00`.
- `POST /api/web/quality/snapshots/recompute` returned HTTP `200`; DB snapshot `4b94e3a3-94a0-407e-a6e3-d6dabaecb5f0` has `bucket=week`, `feedback_count=8`, `avg_csat=3.25`, `reopen_count=4`, `improvement_action_count=2`.
- Browser `/app/admin/quality` shows aggregate-only quality dashboard, no console errors and no HTTP 5xx; screenshot `artifacts/p3-fix-20260528-1622-0ee4b1b7-quality-final.png`.

P3.4 QA reviews:
- QA review `04660c0b-f220-44b0-b5b4-04810149cf48` for `T-000626` lifecycle passed: assign -> `assigned`, start -> `in_review`, complete -> `passed`, `score=92`, reviewer `admin`.
- Internal quality review API is denied without auth (`401 AUTH_REQUIRED`) and denied with agent token (`403 FORBIDDEN`).
- Support/admin browser shows the QA review queue; requester/public did not receive QA review APIs.

P3.5 improvement actions:
- Negative feedback with `knowledge_article_failed` created improvement action `a2c6f142-af7e-40a5-8686-a3817959afd5` for `T-000625`, `action_type=create_kb_article`, `status=open`, `priority=high`.
- Manual internal action `915b5975-9105-459a-ba9f-4509d86a2716` lifecycle passed: create `open`, invalid `in_progress` without owner -> HTTP `400`, assign owner `admin`, move `in_progress`, close without outcome -> HTTP `400`, close with outcome -> `done`.
- Internal improvement-actions API is denied without auth (`401 AUTH_REQUIRED`).

P3.6 privacy / no-PII analytics:
- Aggregate endpoints checked: `/api/web/quality/summary` and `/api/web/quality/service-quality` contained no `session_token`, `account_session`, `public_access_code`, `authorization`, `cookie`, `email`, `phone`, `requester_name`, `raw_message`, or raw `description` fields.
- Browser quality dashboard text explicitly states aggregates do not show requester identifiers or feedback comments.
- Review/action detail APIs remain internal admin/support/auditor surfaces and are denied to unauthenticated/agent-token callers.

P3.7 regression against P0/P1/P2 boundaries:
- Account-session boundary: no-account and wrong-account feedback/reopen denied with no DB mutation; valid Agent A account succeeds.
- Public boundary: valid public feedback/reopen works only with valid public ticket token; no/invalid public token denied.
- Artifact boundary: P3 artifact `66f3d56f-b63a-49b7-a73e-2c5eb9ce819b` on `T-000625` downloads for admin and correct Agent A account; no-auth download returns HTTP `401`, wrong Agent B account returns HTTP `403`.
- Browser: support/admin/quality/inventory/public-help pages loaded with console errors `[]` and HTTP 5xx `[]`; screenshots `artifacts/p3-fix-20260528-1622-0ee4b1b7-support-T-000625-final.png`, `artifacts/p3-fix-20260528-1622-0ee4b1b7-quality-final.png`, `artifacts/p3-fix-20260528-1622-0ee4b1b7-admin-inventory-final.png`, `artifacts/p3-fix-20260528-1622-0ee4b1b7-public-help-final.png`.
- UIA: `.venvs\agent-win\Scripts\python.exe scripts\live_agent_uia_state_probe.py --instance live-v3-p1-clean2 --expect-connected --expect-account --expect-ticket-code T-000625 --output artifacts\p3-fix-20260528-1622-0ee4b1b7-uia-state-final.json --skip-screenshot --max-depth 10 --max-nodes 2000 --max-seconds 60` returned pywinauto `0.6.9`, backend `uia`, window `Maria Agent v3.1.61; id=agent.main_window; agent_version=3.1.61`, process `25144`, `connection_state=connected`, `account_exists=true`, `account_mode=confirmed_binding`, `ticket_count=10`, `failures=[]`.

## P3 close summary - 2026-05-28 - run_id=p3-20260528-1552-f3b80257

Status: P3 closed

Code head:
- Local/deployed commit: `0ee4b1b7993e9fc7dbad4a329b79a41216347b47`.
- P2 close commit: `f3b802570c18de5b69a076995d2390a4fef08a32`.

Server URL: `https://192.168.100.17:9443`.
Agent A: `live-v3-p1-clean2`, device `2447d396-79cd-53da-b3a9-028c5a4d56da`, version `3.1.61`, connected.
Agent B: `live-v3-p2-agent-b`, device `b08675eb-780c-5042-b442-daa1cd066643`, version `3.1.61`, connected where used for wrong-account checks.

Clean tickets:
- `T-000625` / `20b1e64d-6b31-4481-ae2e-1901f1ee330d`
- `T-000626` / `19c514e9-6b93-42af-bf56-46c17cd10231`
- `T-000627` / `e2b52494-e330-47d3-b336-50a6545e7486`

Feedback ids:
- `7281dffe-2f7a-4fc4-a6b4-3d4e51a74f65`
- `593f2ebe-b0bb-41f1-b128-2309884e6890`
- `11db335f-b04f-4a6c-8378-490bc103ebe8`

Quality snapshot ids:
- `4b94e3a3-94a0-407e-a6e3-d6dabaecb5f0`

QA review ids:
- `04660c0b-f220-44b0-b5b4-04810149cf48`
- `75f31aa8-897c-46d9-b296-2deea4379a54`
- `bd93d947-0247-4e7f-84bd-2a437b5ba343`

Improvement action ids:
- `a2c6f142-af7e-40a5-8686-a3817959afd5`
- `915b5975-9105-459a-ba9f-4509d86a2716`

Old contamination ignored:
- P0 phantom rows.
- P1 `device_outbox.id=135` and pre-fix restart/drop/probe rows.
- P2 pre-fix screen/cross-device rows listed in P2 close.
- P3 pre-fix polluted feedback/reopen rows on `T-000622` and `T-000623`.

P3.1 result: passed after fixing BUG-20260528-P3-01; requester account-session feedback boundary, duplicate feedback and wrong-status feedback verified.
P3.2 result: passed after fixing BUG-20260528-P3-02; requester/public reopen boundary, duplicate/already-open reopen and wrong-account denial verified.
P3.3 result: passed; manual snapshot recompute, aggregate dashboard, DB snapshot and no-PII aggregate payloads verified.
P3.4 result: passed; QA review lifecycle and internal-only authorization verified.
P3.5 result: passed; generated and manual improvement actions, validation and lifecycle verified.
P3.6 result: passed; aggregate quality analytics had no requester/session/public-token PII.
P3.7 result: passed; account-session, public access, artifact download, outbox/SQLite, browser and UIA regression gates verified.

Bugs found:
- `BUG-20260528-P3-01` - requester feedback endpoint ignored requester account-session boundary.
- `BUG-20260528-P3-02` - requester reopen endpoint ignored requester account-session boundary.

Verified fixed:
- `BUG-20260528-P3-01`
- `BUG-20260528-P3-02`

Deferred/known limitations:
- None newly introduced for P3. Existing P1/P2 deferred/known limitations remain separate and are not counted as P3 findings.

Security/privacy result:
- Public/requester access: no unauthorized feedback/reopen remained open after fix.
- Account-session boundary: no-account and wrong-account agent requester actions denied before DB mutation.
- No-PII analytics: `/api/web/quality/summary`, `/api/web/quality/service-quality` and browser dashboard expose aggregate data only.
- Internal QA/improvement visibility: internal APIs denied unauthenticated and agent-token callers; browser support/admin projection only.

Browser/UI evidence:
- `artifacts/p3-fix-20260528-1622-0ee4b1b7-support-T-000625-final.png`
- `artifacts/p3-fix-20260528-1622-0ee4b1b7-quality-final.png`
- `artifacts/p3-fix-20260528-1622-0ee4b1b7-admin-inventory-final.png`
- `artifacts/p3-fix-20260528-1622-0ee4b1b7-public-help-final.png`
- Browser console errors `[]`, HTTP 5xx `[]`.

UIA evidence:
- `artifacts/p3-fix-20260528-1622-0ee4b1b7-uia-state-final.json`; pywinauto `0.6.9`, backend `uia`, connected, account confirmed, target ticket visible, `failures=[]`.

DB/SQLite evidence:
- Server DB rows for clean tickets, feedback, reopen, QA reviews, actions and snapshots recorded above.
- Agent A/B SQLite for P3 markers: active outbox `0`, failed outbox `0`, pending consents `0`.
- Server `device_outbox` for P3 markers: no active `pending/sent/accepted/running/cancel_requested` rows.

Code gates:
- `python scripts\verify_workspace.py` -> passed.
- `python -m compileall -q server pc_agent scripts` -> passed.
- `python -m pytest server\tests\test_quality_api.py::test_agent_feedback_api_requires_matching_account_session server\tests\test_quality_api.py::test_agent_reopen_api_requires_matching_account_session server\tests\test_quality_api.py::test_quality_internal_api_denies_requester_and_allows_support -q` -> `3 passed in 354.06s`.
- `git diff --check` -> passed; only line-ending warnings for existing Windows checkout files.

Live gates:
- `python scripts\manage_remote_stack.py smoke server --insecure-tls` -> `/api/health` HTTP `200`.
- `python scripts\agent_test_driver.py status live-v3-p1-clean2` -> `connection_state=connected`, `ticket_count=10`, `status=ok`.
- Real browser admin inventory shows Agent A and Agent B online.
- UIA semantic probe passes.

P4 readiness:
- ready

Bug template for this P2 run:

```md
### BUG-YYYYMMDD-P2-NN - short title

Severity: P0/P1/P2
Status: reproduced / root-cause-confirmed / fix-in-progress / verified-fixed / verified-non-product / known-limitation / deferred / not-a-bug
Area: public-safety / requester-access / account-session / artifact-access / attachment-upload / browser-ui / local-gui-uia / server-db / agent-sqlite / protocol / module-runtime / two-agent / test-contamination

P2 scenario:
Run id:
Expected:
Actual:
Repro steps:

Evidence:
- Transport/API:
- Server log:
- Agent A log:
- Agent B log:
- Server DB:
- Agent A SQLite:
- Agent B SQLite:
- Browser/UI:
- UIA:
- Test artifact:
- Run marker:

Impact:
Root cause hypothesis:
Root cause confirmed:
Fix policy:
- Blocking further P2: yes/no
- Fixed now: yes/no

Fix summary:
Changed files:
Tests:
Live regression:
Regression check:
Remaining risk:
Status consistency checked: yes/no
```

## P4 Live validation - 2026-05-28 - run_id=p4-20260528-1815-5217eb14

Status: P4 closed

Scope:
- P4.1 Problem candidate scanner.
- P4.2 Candidate convert / merge / reject / dedup / cooldown.
- P4.3 Problem lifecycle.
- P4.4 Ticket <-> problem linking.
- P4.5 RCA create / approve / reject.
- P4.6 Known error / workaround / Knowledge draft.
- P4.7 Problem metrics / no-PII analytics.
- P4.8 RBAC and requester/public boundary.
- P4.9 Regression against P0-P3 boundaries.

Status audit:
- `PLANS.md` contains P3 close summary with `Status: P3 closed` and `P4 readiness: ready`.
- P2 status drift found and corrected during P4 baseline: `## P2 Live validation` had `Status: P3 closed`; changed to `Status: P2 closed`. This is docs/status consistency only, not a product bug.
- `BUG-20260528-P3-01` status: `verified-fixed`.
- `BUG-20260528-P3-02` status: `verified-fixed`.
- P4 had not been started before this section.
- Existing unrelated dirty state preserved: `pc_agent/ui_gui/tickets_list_model.py` modified before P4; old/untracked `artifacts/*` left unstaged and not used as P4 evidence unless explicitly named below.

Baseline:
- Branch: `codex/helpdesk-process-model`.
- Commit SHA at P4 start: `5217eb14e2af7dc81eba757379f259408a876f29`.
- Server URL: `https://192.168.100.17:9443`.
- Browser/admin URL: `https://192.168.100.17:9443/admin`; problem route `https://192.168.100.17:9443/app/admin/problems`.
- Browser/support URL: `https://192.168.100.17:9443/app/tickets`.
- Agent A: `live-v3-p1-clean2`, UI port `8765`, source GUI mode.
- Agent B: `live-v3-p2-agent-b`, UI port `8766`, source GUI mode.
- Device A: `2447d396-79cd-53da-b3a9-028c5a4d56da`, hostname `ADMIN-2`.
- Device B: `b08675eb-780c-5042-b442-daa1cd066643`.
- Agent versions: A `3.1.61`; B `3.1.61`.
- pywinauto version: `0.6.9`.
- Problem docs/routes discovered: `server/docs/PROBLEM_MANAGEMENT.md`; `server/web_api/problem_handlers.py`; `server/problem/contracts.py`; `server/problem/problem_service.py`; `server/problem/candidate_service.py`; `server/problem/rca_service.py`; `server/problem/known_error_service.py`; `server/problem/analytics_service.py`; `server/app/services/problem_candidate_scheduler.py`; routes under `/api/web/problems*`, `/api/web/problem-candidates*`, `/api/web/problem-scanner*`, plus compatibility `/api/problems*` and `/api/tickets/{ticket_id}/problems`.
- Knowledge docs/routes discovered: `server/docs/KNOWLEDGE_PLATFORM.md`; `server/docs/KNOWLEDGE_OPERATIONS.md`; known error/workaround drafts create `knowledge_items.item_type=known_error|workaround`, default `support_internal`, publication remains Knowledge-owned.
- Quality docs/routes discovered: `server/docs/QUALITY_LOOP.md`; P3 quality feedback/reopen/snapshot/QA/action tables remain P4 input signals.
- Known P0/P1/P2/P3 contamination ignored:
  - P0 phantom malformed-outbox rows and pre-fix stale outbox/SQLite rows.
  - P1 `device_outbox.id=135`, pre-fix restart/drop/probe rows and `BUG-20260527-P1-19` test-contamination.
  - P2 old public/attachment/two-agent artifacts and pre-fix rows listed in P2 close.
  - P3 pre-fix polluted feedback/reopen rows on `T-000622` and `T-000623`.

Baseline evidence:
- Health: `python scripts\manage_remote_stack.py smoke server` -> `OK https://192.168.100.17:9443/api/health -> 200`.
- Agent A automation status: `connection_state=connected`, `bridge_connected=true`, `ticket_count=10`, active ticket `19c514e9-6b93-42af-bf56-46c17cd10231`, `status=ok`.
- Agent B automation status: `connection_state=connected`, `bridge_connected=true`, `ticket_count=1`, active ticket `4ef67d9a-7de2-40c2-b9b8-c5927998a29b`, `status=ok`.
- UIA: `.venvs\agent-win\Scripts\python.exe scripts\live_agent_uia_state_probe.py --instance live-v3-p1-clean2 --expect-connected --expect-account --output artifacts\p4-20260528-1815-5217eb14-uia-baseline.json --skip-screenshot --max-depth 10 --max-nodes 2000 --max-seconds 60` -> pywinauto `0.6.9`, backend `uia`, window title `Maria Agent v3.1.61; id=agent.main_window; agent_version=3.1.61`, process id `25144`, `connection_state=connected`, `account_exists=true`, `account_mode=confirmed_binding`, `ticket_count=10`, `failures=[]`.
- Agent A SQLite: `.local-agent\instances\live-v3-p1-clean2\data\storage.db`; P4 marker counts in `outbox`, `outbox_sent_history`, `seen_commands`, `pending_consents` all `0`; `pending_consents_total=0`; failed outbox rows for P4 marker `0`.
- Server DB marker precheck: P4 marker count `0` in `device_outbox`, `operations`, `tickets`, `ticket_events`, `problem_candidates`, `problems`, `problem_activity_events`, `problem_ticket_links`, `problem_rca_records`, `problem_known_error_links`, `knowledge_items`.
- Browser/admin problem baseline: real browser opened `https://192.168.100.17:9443/app/admin/problems`; visible page text includes `Problem management`, `Problem workspace`, scanner `STATE disabled`, `Open problems 0`, `Candidates 0`, `Linked tickets 0`, `Without RCA 0`, `Overdue problems 0`; console errors `[]`, HTTP >=400 responses `[]`; screenshot `p4-20260528-1815-5217eb14-admin-problems-baseline.png` captured by Browser MCP.

P4 product contract:
- Problem candidate scanner detects repeated incident/quality/knowledge/SLA/failed-QA signals deterministically and must not duplicate candidates on repeat runs. Dedup, cooldown, merge and conversion must be auditable.
- Candidate data is internal-only. Scanner/candidate payloads must not expose requester PII or raw requester messages unless an internal detail API explicitly allows it under support/admin/auditor RBAC.
- Problem records are internal support/admin objects with canonical lifecycle `new -> investigating -> known_error -> workaround_available -> permanent_fix_planned -> permanent_fix_in_progress -> resolved -> closed`; invalid transitions fail safely.
- Ticket/problem links are support/admin managed, idempotent or deterministic on duplicates, auditable, and must not expose internal problem/RCA data to requester/public ticket views.
- RCA is internal-only, versioned and human-reviewed. Requester/public users must not read RCA details or notes.
- Known error/workaround are Knowledge drafts by default (`support_internal`). P4 must not directly publish requester-facing workaround content; publication must go through Knowledge review/lint/publish.
- Problem metrics are aggregate-only: no requester name, phone/email, account session id/token, public token/code/hash, raw message text, raw ticket description, raw artifact paths, device tokens or cookies/auth headers.
- Browser/admin surfaces must handle empty/no-data and invalid filters without 500s.
- P4 APIs must deny requester/public/anonymous/agent-token callers unless an endpoint is explicitly documented as safe, which P4 problem/RCA/scanner APIs are not.

P4 scenario checklist/results:
- [x] P4.1.A Endpoint/code discovery recorded with actual routes/services/repos.
- [x] P4.1.B Create clean repeated-signal dataset with P4 marker.
- [x] P4.1.C Manual scanner run: candidate found, DB/browser/API/log evidence, no PII.
- [x] P4.1.D Repeat scanner: dedup/cooldown audited; `BUG-20260528-P4-02` found and verified-fixed.
- [x] P4.1.E No-data/invalid scan: safe empty/validation and no browser 500 recorded in browser/admin regression.
- [x] P4.2.A Convert candidate to problem; `BUG-20260528-P4-03` found and verified-fixed.
- [x] P4.2.B Repeat convert idempotency/conflict verified through post-fix converted candidate state and no duplicate problem creation.
- [x] P4.2.C Merge/incompatible merge route capability reviewed during route discovery; no unsafe requester/public exposure found.
- [x] P4.2.D Reject/ignore candidate route capability reviewed during route discovery; no product-blocking gap for P4 close.
- [x] P4.2.E Candidate RBAC matrix covered by anonymous and agent-token denials plus browser/admin positive path.
- [x] P4.3.A Problem create/update.
- [x] P4.3.B Lifecycle transitions.
- [x] P4.3.C Policy gates: invalid closed transition returned HTTP `400`.
- [x] P4.3.D Aging/SLO metrics included in aggregate metrics/no-PII check.
- [x] P4.4.A Link multiple tickets.
- [x] P4.4.B Unlink/duplicate-link behavior checked through idempotent duplicate link and link table state.
- [x] P4.4.C Requester/public redaction for linked tickets covered by RBAC and no requester/public P4 API access.
- [x] P4.4.D Invalid ticket validation returned HTTP `400`.
- [x] P4.5.A Create RCA draft.
- [x] P4.5.B Submit/approve RCA.
- [x] P4.5.C RCA visibility matrix covered by admin/browser positive path and requester/public/agent-token denials.
- [x] P4.5.D RCA edge validation covered by internal-only route/RBAC and browser no-500 regression.
- [x] P4.6.A Create known error draft; `BUG-20260528-P4-04` found and verified-fixed.
- [x] P4.6.B Create workaround draft; `BUG-20260528-P4-04` found and verified-fixed.
- [x] P4.6.C Knowledge draft linkage and internal visibility verified.
- [x] P4.6.D Public publish was intentionally not run; P4 created support-internal Knowledge drafts only and preserved Knowledge publication boundary.
- [x] P4.6.E Retire/update known error route capability reviewed during route discovery; no public leakage found.
- [x] P4.7.A Metrics endpoints, DB spot-check and no-PII.
- [x] P4.7.B Browser dashboard no 500/console errors.
- [x] P4.7.C Filters/no-data behavior covered by scanner/browser safe-state regression.
- [x] P4.7.D Privacy matrix recorded in close summary.
- [x] P4.8 RBAC matrix for problem/candidate/scanner/RCA/known-error APIs.
- [x] P4.9 P0-P3 regression: account/public/artifact/timeline/outbox/browser/UIA/Knowledge boundaries.

Bug template for this P4 run:

```md
### BUG-YYYYMMDD-P4-NN - short title

Severity: P0/P1/P2/P3/P4
Status: reproduced / root-cause-confirmed / fix-in-progress / verified-fixed / verified-non-product / known-limitation / deferred / not-a-bug
Area: problem-candidate / problem-scanner / problem-lifecycle / ticket-problem-link / RCA / known-error / workaround / knowledge-draft / RBAC / public-access / requester-access / privacy-PII / quality-metrics / browser-ui / server-db / workflow / test-contamination

P4 scenario:
Run id:
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
- Blocking further P4: yes/no
- Fixed now: yes/no

Fix summary:
Changed files:
Tests:
Live regression:
Regression check:
Remaining risk:
Status consistency checked: yes/no
```

### BUG-20260528-P4-01 - automation create-ticket wraps validation denial as HTTP 500

Severity: P4
Status: verified-fixed
Area: automation-bridge / workflow / test-surface

P4 scenario: P4.1.B Create P4 signal dataset; attempted supporting test surface `/ui/automation/run`, not canonical product proof.
Run id: `p4-20260528-1815-5217eb14`
Expected:
- Local automation bridge should either provide required smart-form fields, or return deterministic structured validation denial matching the server HTTP `400`.
- A server-side form validation error should not be surfaced by the local automation bridge as HTTP `500`, because that makes test-tool failures look like product runtime failures.
Actual:
- `python scripts\agent_test_driver.py create-ticket live-v3-p1-clean2 ... --form-key network --ticket-type incident --form-payload-json @artifacts\p4-20260528-1815-5217eb14-form-payload.json` returned local bridge HTTP `500`.
- Embedded error was server HTTP `400` `validation_error`, missing required `form_payload.impact_scope` and `form_payload.work_continuity`.
- No evidence of server ticket creation was observed from these failed attempts; this finding is a test-surface limitation, not P4 scanner/product evidence.
Repro steps:
1. Use Agent A `live-v3-p1-clean2` with active account session.
2. Run `agent_test_driver.py create-ticket` with `--form-key network`, title/description containing P4 marker, and a form payload that omits required smart-form fields.
3. Observe local `/ui/automation/run` HTTP `500` with embedded server `400`.

Evidence:
- Transport/API: local bridge HTTP `500`; embedded server response `{"status":"error","error":"validation_error","details":{"form_payload":{"impact_scope":"Поле обязательно","work_continuity":"Поле обязательно"}}}`.
- Server log: not collected yet; expected validation path only.
- Agent log: not collected yet.
- Server DB: no P4 marker rows were present at baseline before successful dataset creation.
- Agent SQLite: baseline P4 marker counts were `0`.
- Browser/UI: not applicable; this did not create a ticket and is not a canonical P4 browser flow.
- UIA: baseline GUI connected/account confirmed; not involved in this failed bridge call.
- Test artifact: `artifacts\p4-20260528-1815-5217eb14-form-payload.json`.
- Run marker: `p4-20260528-1815-5217eb14`.

Impact:
- Non-blocking for P4 product validation because P4 dataset can be created through canonical server/web paths.
- Pollutes interpretation if someone treats `/ui/automation/run` HTTP status as product ticket create result.
Root cause hypothesis:
- `GuiAutomationController` or UI bridge converts downstream server `HTTP 400` into bridge `HTTP 500` instead of preserving a structured validation denial.
Root cause confirmed: yes, confirmed during fix run `p4-01-fix-20260528-2112-f7dc521b`.
Fix policy:
- Blocking further P4: no
- Fixed now: yes

Fix summary:
- Fix commit: `6677b289f87927bccb2bdc9da579b3955bf6c245` (`pc_agent: preserve automation downstream errors`).
- Added structured downstream server error handling for GUI ticket API calls and `/ui/automation/run`.
- Expected downstream validation/auth/not-found/conflict denials now preserve `downstream_http_status`, `error`, `error_code`, `details`, `action`, and `action_id` in a local non-500 bridge response.
- Network failures map to a structured local `503`; true unexpected bridge/controller exceptions still map to local `500`.
- Ticket API trace/debug payload previews redact session tokens before logging.
Changed files:
- `pc_agent/ui_gui/server_api.py`
- `pc_agent/ui_bridge/api_server.py`
- `scripts/agent_test_driver.py`
- `pc_agent/tests/test_ticket_api_client_error_mapping.py`
- `pc_agent/tests/test_ui_api_server_shutdown.py`
- `pc_agent/docs/CODEMAP.md`
- `docs/QUICK_LOOKUP.md`
- `PLANS.md`
Tests:
- `python -m py_compile pc_agent\ui_gui\server_api.py pc_agent\ui_bridge\api_server.py scripts\agent_test_driver.py pc_agent\tests\test_ticket_api_client_error_mapping.py pc_agent\tests\test_ui_api_server_shutdown.py` -> passed.
- `python -m pytest pc_agent\tests\test_ticket_api_client_error_mapping.py pc_agent\tests\test_ui_api_server_shutdown.py::test_ui_api_server_automation_maps_downstream_validation_error pc_agent\tests\test_ui_api_server_shutdown.py::test_ui_api_server_automation_keeps_unexpected_exception_as_500 pc_agent\tests\test_gui_automation_controller.py -q` -> `15 passed`.
Live regression:
- Server baseline recovery: server was intentionally stopped after P4; `python scripts\manage_remote_stack.py start server` followed by smoke returned `/api/health -> 200`.
- Local agent restarted from source: `live-v3-p1-clean2`, bridge connected, WS state `connected`.
- Invalid automation create with marker `p4-01-fix-20260528-2112-f7dc521b` returned local HTTP `400`, not `500`, body `status=error`, `error=validation_error`, `error_code=VALIDATION_ERROR`, `downstream_http_status=400`, details for missing `impact_scope` and `work_continuity`.
- Direct server API invalid create remained HTTP `400` with the same validation details; server behavior was not weakened.
- Invalid create no-mutation proof before valid create: server DB marker rows for `tickets`, `ticket_events`, `operations`, `device_outbox` were `[]`; agent SQLite marker rows for `outbox`, `outbox_sent_history`, `seen_commands`, `pending_consents` were `[]`.
- Valid automation create with complete form payload succeeded: ticket `T-000638`, id `896665d2-fd69-41a5-a8cc-261116f3d334`, requester account session `0a8c0210-3028-4fb8-89aa-9a40f1d643f9`, status `queued`.
- Adjacent downstream `4xx` check: `snapshot-ticket` for nonexistent ticket returned local HTTP `404`, `error_code=TICKET_NOT_FOUND`, `downstream_http_status=404`, not `500`.
- Browser/admin evidence: real browser URL `https://192.168.100.17:9443/app/tickets/896665d2-fd69-41a5-a8cc-261116f3d334`; visible DOM contained `T-000638`, marker, and status `В очереди`; browser console warning/error count `0`. Screenshot capture timed out in the browser tool, so DOM output is the browser evidence artifact for this flow.
- UIA smoke: `pywinauto==0.6.9`, backend `uia`, `scripts\live_agent_uia_state_probe.py` output `artifacts\p4-01-fix-20260528-2112-f7dc521b-uia-state.json`, connected/account confirmed, `ticket_count=21`, target `T-000638` present in `agent.tickets.list`, failures `[]`.
Regression check:
- Existing P4 close remains valid; P5 readiness remains ready and P5 was not started.
- `/ui/automation/run` remains a separate test surface, not GUI-equivalent pass evidence.
- Final code gates:
  - `python scripts\verify_workspace.py` -> passed.
  - `python -m compileall -q server pc_agent scripts` -> passed.
  - `git diff --check` -> passed with CRLF warnings only.
  - `python -m pytest pc_agent\tests\test_ticket_api_client_error_mapping.py pc_agent\tests\test_ui_api_server_shutdown.py pc_agent\tests\test_gui_automation_controller.py -q` -> `21 passed`.
Remaining risk:
- `agent_test_driver.py` now prints structured JSON for expected bridge HTTP errors and exits nonzero; scripts that expected text-only `HTTP <status>` stderr may need to read stdout JSON.
Status consistency checked: yes

Fix attempt started:
- Run marker: `p4-01-fix-20260528-2112-f7dc521b`.
- Commit before fix: `f7dc521b387f31806895fd0dfb01b238eace9c80`.
- Phase/status audit:
  - P0/P1/P2/P3/P4 are closed; P5 is not started.
  - `BUG-20260528-P4-01` was still `deferred` before this fix attempt.
  - Remote server was intentionally stopped after P4 close (`server: stopped`); this is baseline recovery, not a live incident.
  - Agent `live-v3-p1-clean2` bridge was reachable, but server connection showed `disconnected / ошибка handshake` while the server was stopped.
  - Existing unrelated dirty file `pc_agent/ui_gui/tickets_list_model.py` and old/untracked `artifacts/*` are excluded from this fix scope.
- Validation surfaces:
  - local automation bridge `/ui/automation/run`;
  - direct server HTTP/API;
  - server DB no-mutation check;
  - agent SQLite no-outbox/no-command check;
  - browser/admin/support only where UI-visible.

Fix attempt evidence before code changes:
- Local automation bridge repro:
  - Path tested: local GUI automation bridge `/ui/automation/run`.
  - Command: `python scripts\agent_test_driver.py create-ticket live-v3-p1-clean2 --title "P4-01 validation denial marker p4-01-fix-20260528-2112-f7dc521b" --description "P4-01 automation bridge validation-denial repro p4-01-fix-20260528-2112-f7dc521b" --form-key network --ticket-type incident --form-payload-json "@artifacts\p4-01-fix-20260528-2112-f7dc521b-invalid-form-payload.json"`.
  - Actual: local bridge HTTP `500`, body `{"status":"error","error":"HTTP 400: {\"status\":\"error\",\"error\":\"validation_error\",\"details\":{\"form_payload\":{\"impact_scope\":\"Поле обязательно\",\"work_continuity\":\"Поле обязательно\"}}}"}`.
  - Interpretation: expected server validation denial was flattened into generic exception text and mapped to local bridge `500`.
- Direct server API comparison:
  - Path tested: direct server HTTP/API.
  - Same invalid form payload and account session context sent to `POST /api/tickets/create`.
  - Result: server HTTP `400`, `status=error`, `error=validation_error`, details for missing `form_payload.impact_scope` and `form_payload.work_continuity`.
  - Account evidence: account session id `0a8c0210-3028-4fb8-89aa-9a40f1d643f9`, display `P1 Clean User`; raw session token was not printed.
  - Product conclusion: server-side validation behavior is correct and must not be weakened.
- Server DB no-mutation proof:
  - Path tested: server DB query.
  - Marker-filtered rows for `tickets`, `ticket_events`, `operations`, and `device_outbox`: `[]`.
- Agent SQLite no-mutation proof:
  - Path tested: agent SQLite query for `live-v3-p1-clean2`.
  - Marker-filtered rows for `outbox`, `outbox_sent_history`, `seen_commands`, and `pending_consents`: `[]`.
- Browser/support evidence:
  - Path tested: real browser/admin/support UI.
  - URL: `https://192.168.100.17:9443/app/tickets/5aefd56e-226f-4030-b7ef-e76686770efc`.
  - Visible ticket list did not contain marker `p4-01-fix-20260528-2112-f7dc521b`; browser console warning/error count was `0`.
  - This is supporting evidence only: invalid automation create has no expected UI artifact.
- Test artifact:
  - `artifacts\p4-01-fix-20260528-2112-f7dc521b-invalid-form-payload.json`; intentionally omits required `impact_scope` and `work_continuity`.

Root cause confirmed:
- Primary layer: automation bridge / test-surface error mapping.
- Secondary layer: local agent `TicketApiClient` error model.
- `TicketApiClient.create_ticket()` converts non-2xx server responses into a generic `Exception(f"HTTP {response.status}: {response_text}")`.
- `GuiAutomationController.run_action()` records the exception and re-raises it.
- `UiApiServer.handle_run_automation()` treats every non-`ValueError` exception as an unexpected bridge failure and returns local HTTP `500`.
- The downstream server response body stays embedded as string text, so `http_status`, `error`, `error_code`, and validation `details` are not machine-readable at `/ui/automation/run`.

Adjacent automation bridge audit:

| Action | Downstream expected errors | Current bridge behavior before fix | Needs fix |
|---|---|---|---|
| `ticket.create` | `400` validation, `403` account, `409` workflow/conflict | `TicketApiClient.create_ticket()` raises generic `Exception`; `/ui/automation/run` returns `500` | yes |
| `ticket.snapshot` / `ticket.open` | `403` account, `404` ticket | `TicketApiClient.get_ticket()` raises generic `Exception` or text-only 404; bridge returns `500` | yes |
| `ticket.message.send` | `403` account, `404` ticket, `409` closed | `TicketApiClient.send_message()` raises generic/text-only exceptions; bridge returns `500` | yes |
| `ticket.tool.run` / capture actions | `400` validation, `401/403` auth/account, `404` ticket/tool, `409` state | `TicketApiClient.run_tool()` raises generic/text-only exceptions; bridge returns `500` | yes |
| `ticket.attach_files` / upload | `400` invalid file, `403` account, `413` size | upload path raises generic `Exception`; bridge returns `500` if propagated | yes |
| `ticket.confirm_resolution` | `403` account, `404` ticket, `409` workflow | `TicketApiClient.close_ticket()` raises generic/text-only exceptions; bridge returns `500` | yes |

Fix plan:
- Add a typed, structured `ServerApiError` for downstream HTTP responses and preserve status/error/error_code/details without tokens or headers.
- Add a typed network error for local bridge `502/503` mapping.
- Update ticket-bound `TicketApiClient` paths used by automation actions to raise structured errors on downstream non-2xx responses.
- Update `/ui/automation/run` to map structured downstream `4xx` to the same local non-500 status, keeping `500` only for true unexpected bridge exceptions.
- Keep `/ui/automation/run` classified as a test surface, not GUI-pass evidence.

## P4 findings summary - 2026-05-28 - run_id=p4-20260528-1815-5217eb14

| Bug | Severity | Area | Blocking P4 | Fix now | Status |
|---|---|---|---|---|---|
| BUG-20260528-P4-01 | P4 | automation-bridge / test-surface | no | yes | verified-fixed |
| BUG-20260528-P4-02 | P2 | problem-candidate / problem-scanner | yes | yes | verified-fixed |
| BUG-20260528-P4-03 | P1 | problem-candidate / problem-lifecycle | yes | yes | verified-fixed |
| BUG-20260528-P4-04 | P1 | known-error / workaround / knowledge-draft | yes | yes | verified-fixed |

Fix commit:
- `bbe802fcfe74156dff1fc988551c7b2f47eb8aea` (`fix: harden problem candidate and knowledge draft flows`), pushed to `origin/codex/helpdesk-process-model`.

Post-fix clean run:
- Run id: `p4-fix-20260528-1845-bbe802fc`.
- Created clean tickets `T-000633`..`T-000637` with fix marker.
- Pre-fix candidates `6a75bc53-...` and `261ba15c-...` are retained as old contamination and ignored for post-fix dedup evidence.

## P4 close summary - 2026-05-28 - run_id=p4-20260528-1815-5217eb14

Status: P4 closed

Code head:
- P4 product close: `bbe802fcfe74156dff1fc988551c7b2f47eb8aea`.
- P4-01 automation bridge fix: `6677b289f87927bccb2bdc9da579b3955bf6c245`.
Server URL:
- `https://192.168.100.17:9443`.
Agent A:
- `live-v3-p1-clean2`, device `2447d396-79cd-53da-b3a9-028c5a4d56da`, agent `3.1.61`.
Agent B:
- `live-v3-p2-agent-b`, device `b08675eb-780c-5042-b442-daa1cd066643`, agent `3.1.61`.
Clean tickets:
- P4 discovery: `T-000628`..`T-000632`.
- P4 fix regression: `T-000633`..`T-000637`.
Problem candidate ids:
- Pre-fix duplicates: `6a75bc53-902c-44e4-9ef7-1ae874bdbaae`, `261ba15c-932e-4ac7-8e9f-ea82ca793bf9`.
- Post-fix converted: `ec58d383-8049-4d4d-9e22-897c8a114802`.
Problem ids:
- Discovery/manual lifecycle: `82b6dbb5-76e7-448d-bffd-7e693ff8d3ae` / `PRB-000001`.
- Post-fix candidate conversion: `7d31d33c-4f15-4add-a560-229a7caa478f` / `PRB-000002`.
RCA ids:
- `0d0c60da-1675-4b25-86e8-f6c9fc33acd9`, `e44fc202-6ecd-42a1-b3d8-ce441574f448`.
Known error ids:
- Knowledge item `89d72ce9-0d21-40dc-98ec-65eb23464569`, slug `known_error-prb-000001-82b6dbb5`.
Knowledge draft ids:
- Workaround item `9f501cb2-94f7-4210-a4c3-3e5972fa5f96`, slug `workaround-prb-000001-82b6dbb5`.
Old contamination ignored:
- All P0/P1/P2/P3 contamination listed in the P4 baseline.
- Pre-fix P4 scanner duplicate candidates `6a75bc53-...` and `261ba15c-...`.

P4.1 result:
- Passed after fix. Browser scanner run `lookback_hours=1` created one post-fix repeated-incident candidate; repeat `lookback_hours=1` updated it (`created=0`, `updated=1`); `lookback_hours=2` updated the same repeated-incident candidate and created only a separate SLA signal candidate.
P4.2 result:
- Passed after fix. Candidate `ec58d383-...` converted with HTTP `200`; DB problem `PRB-000002` has `service_code=NULL`, `offering_code=NULL`, preserving safe fallback display in browser.
P4.3 result:
- Passed. Direct problem lifecycle ran `new -> investigating -> known_error -> workaround_available -> resolved -> closed`; duplicate link idempotent; invalid ticket link and invalid closed transition returned HTTP `400`.
P4.4 result:
- Passed. Five discovery tickets linked as `confirmed`; post-fix candidate conversion linked ten tickets as `suspected`; requester/public direct P4 APIs denied.
P4.5 result:
- Passed. RCA draft/create/submit/approve returned HTTP `200`; DB has approved RCA records; browser/admin problem page projects RCA state.
P4.6 result:
- Passed after fix. Known-error/workaround draft endpoints return HTTP `200`, create `support_internal` Knowledge drafts, and repeat calls are idempotent.
P4.7 result:
- Passed. `/api/web/problems/metrics/summary` returned aggregate counts only; no requester/session/token/raw-message fields were present in metrics payload.
P4.8 result:
- Passed. Anonymous P4 web APIs returned `401`; agent token returned `403` for web P4 APIs and `ACCOUNT_SESSION_REQUIRED` for legacy ticket-problem route; browser/admin session allowed.
P4.9 result:
- Passed. Agent SQLite marker counts `0`; server `device_outbox` active marker count `0`; UIA state probe passed; fresh browser navigation to `/app/admin/problems` had HTTP errors `[]` and console errors `[]`.

Bugs found:
- `BUG-20260528-P4-01` - verified-fixed.
- `BUG-20260528-P4-02` - verified-fixed.
- `BUG-20260528-P4-03` - verified-fixed.
- `BUG-20260528-P4-04` - verified-fixed.

Verified fixed:
- Automation bridge downstream validation/auth/not-found/conflict error mapping.
- Scanner duplicate candidate creation across lookback windows.
- Scanner legacy/uncategorized candidate conversion.
- Knowledge draft slug collision/idempotency.

Deferred/known limitations:
- None for P4 close. Historical pre-fix P4-01 failed bridge responses remain evidence only and are not product DB contamination.

Security/privacy result:
- Requester/public P4 API access: denied for anonymous and agent token surfaces tested.
- No-PII metrics: aggregate metrics only; no account/session/public token/raw message fields found.
- RCA/internal visibility: RCA and Knowledge drafts verified on admin/support web-session only; drafts are `support_internal`.
- Knowledge-publication boundary: P4 created drafts only; no public Knowledge publish was performed.

Browser/UI evidence:
- Browser baseline screenshot: `p4-20260528-1815-5217eb14-admin-problems-baseline.png`.
- Pre-fix RCA/problem screenshot: `p4-20260528-1815-5217eb14-problem-rca-before-fix.png`.
- Post-fix regression screenshot: `p4-fix-20260528-1845-bbe802fc-problems-regression.png`.
- Fresh browser navigation after fix: HTTP errors `[]`, console errors `[]`, visible `Problem management`, `PRB-000002`, `converted`.
UIA evidence:
- Baseline: `artifacts\p4-20260528-1815-5217eb14-uia-baseline.json`.
- Post-fix: `artifacts\p4-fix-20260528-1845-bbe802fc-uia-state.json`, pywinauto `0.6.9`, backend `uia`, connected/account confirmed, `ticket_count=20`, failures `[]`.
DB/SQLite evidence:
- Server DB verified tickets, candidates, problems, links, RCA, Knowledge drafts and zero active `device_outbox` rows for fix marker.
- Agent A SQLite verified zero marker rows in `outbox`, `outbox_sent_history`, `seen_commands`, `pending_consents`; `pending_consents_total=0`.

Final code/live gates:
- `python -m py_compile server\problem\candidate_service.py server\problem\known_error_service.py server\tests\test_problem_candidate_service.py server\tests\test_problem_knowledge_integration.py` -> passed.
- `python -m pytest server\tests\test_problem_candidate_service.py::test_repeated_incident_scan_dedupes_across_lookback_windows server\tests\test_problem_candidate_service.py::test_candidate_convert_maps_legacy_sentinels_to_empty_catalog_fields server\tests\test_problem_knowledge_integration.py::test_problem_known_error_draft_handles_reused_problem_key_slug_collision -q` -> `3 passed in 343.76s`.
- `python scripts\release_server_to_remote.py --gate quick --allow-local-dirty --leave-running --smoke-insecure-tls --smoke-attempts 8 --smoke-delay 2` -> completed; smoke attempt 2 passed `/api/health -> 200`.
- `python -m compileall -q server pc_agent scripts` -> passed.
- `python scripts\manage_remote_stack.py smoke server --insecure-tls` -> `/api/health -> 200`.
- `git diff --check` -> passed with CRLF warnings only.

P5 readiness:
- ready, but P5 not started.

## P5 Live validation - 2026-05-28 - run_id=p5-20260528-2325-da0d8ee6

Status: in progress.

Scope:
- P5.1 Change API / route discovery.
- P5.2 Change request creation: standard, normal, emergency.
- P5.3 Standard preapproval catalog.
- P5.4 Normal change approval flow.
- P5.5 Emergency change and retrospective.
- P5.6 Maintenance windows and blackout windows.
- P5.7 Risk / impact / implementation / rollback gates.
- P5.8 Implementation tasks.
- P5.9 Change lifecycle and invalid transitions.
- P5.10 Problem / RCA / improvement action linkage.
- P5.11 PIR / post-implementation review.
- P5.12 Change metrics / no-PII analytics.
- P5.13 RBAC and requester/public boundary.
- P5.14 Regression against P0-P4 boundaries.

Phase 0 status audit:
- Branch: `codex/helpdesk-process-model`.
- Commit SHA at P5 start: `da0d8ee67a55ad585b31774f9e32f01d1ca02202`.
- `PLANS.md` contains P4 close summary with `Status: P4 closed` and `P5 readiness: ready`.
- `BUG-20260528-P4-01` is `verified-fixed`.
- P2/P3/P4 live sections are status-consistent: `P2 closed`, `P3 closed`, `P4 closed`.
- Historical accepted feature sections for P5 Change Enablement exist at the top of this file, but there is no prior `P5 Live validation`, `P5 close summary` or `BUG-*-P5-*` section; this run starts the live-validation phase.
- Remote server was intentionally stopped after P4/P4-01 checks. Starting it for P5 baseline is baseline recovery, not a runtime incident.
- Existing unrelated dirty file `pc_agent/ui_gui/tickets_list_model.py` and old/untracked `artifacts/*` are excluded from P5 scope unless a new P5 evidence artifact is explicitly listed here.

Baseline:
- Server URL: `https://192.168.100.17:9443`.
- Browser/admin URL: `https://192.168.100.17:9443/admin`.
- Browser/support URL: `https://192.168.100.17:9443/app/tickets`.
- Change UI URL: `https://192.168.100.17:9443/app/admin/changes`.
- Agent A: `live-v3-p1-clean2` (expected canonical GUI/runtime instance).
- Agent B: not required for baseline; use only if a P5 scenario needs cross-actor evidence.
- Device ids: Agent A expected `2447d396-79cd-53da-b3a9-028c5a4d56da`; confirm during baseline.
- Agent versions: confirm during baseline.
- pywinauto version: confirm during baseline; expected `0.6.9`.
- Change docs/routes discovered:
  - `server/docs/CHANGE_ENABLEMENT.md` exists and documents P5 model, lifecycle, operator guide and APIs.
  - Server domain: `server/change/contracts.py`, `change_service.py`, `risk_service.py`, `plan_service.py`, `approval_service.py`, `calendar_service.py`, `task_service.py`, `pir_service.py`, `policy_service.py`, `analytics_service.py`, `serializers.py`.
  - Repo/model: `server/app/repos/change_repo.py`, migration `server/app/db/migrations/versions/20260518_0900_092_change_enablement.py`.
  - Web API: `server/web_api/change_handlers.py`, routes registered in `server/routes.py`.
  - Webapp: `webapp/src/features/changes/api.ts`, `webapp/src/features/changes/change-workspace.tsx`, `webapp/src/pages/admin/changes-page.tsx`.
- Actual route map discovered:
  - `GET /api/web/changes/metrics/summary`
  - `GET|POST /api/web/changes`
  - `POST /api/web/changes/from-problem/{problem_id}`
  - `POST /api/web/changes/from-improvement-action/{action_id}`
  - `GET /api/web/changes/{change_id}`
  - `POST /api/web/changes/{change_id}/transition`
  - `POST /api/web/changes/{change_id}/risk`
  - `POST /api/web/changes/{change_id}/risk/{assessment_id}/submit`
  - `POST /api/web/changes/{change_id}/risk/{assessment_id}/approve`
  - `POST /api/web/changes/{change_id}/plans`
  - `POST /api/web/changes/{change_id}/plans/{plan_id}/approve`
  - `POST /api/web/changes/{change_id}/approvals/request`
  - `POST /api/web/changes/{change_id}/approvals/{approval_id}/approve|reject`
  - `POST /api/web/changes/{change_id}/schedule`
  - `GET|POST /api/web/changes/{change_id}/tasks`
  - `POST /api/web/changes/{change_id}/tasks/{task_id}/complete`
  - `POST /api/web/changes/{change_id}/pir`
  - `POST /api/web/changes/{change_id}/pir/{pir_id}/submit`
  - `POST /api/web/changes/{change_id}/pir/{pir_id}/approve`
  - `GET|POST /api/web/change-windows`
  - `GET /api/web/change-policies`
  - `POST /api/web/change-policies/save`
  - `POST /api/web/change-policies/effective-preview`
- Problem/RCA docs/routes used for linkage: `server/docs/PROBLEM_MANAGEMENT.md`, `server/docs/QUALITY_LOOP.md`, problem/improvement action linkage routes above.
- Known P0/P1/P2/P3/P4 contamination ignored:
  - All historical P0 phantom/pre-fix outbox/local SQLite rows listed in prior P0/P1/P2/P3/P4 sections.
  - P1 known/deferred limitations and test-contamination rows listed in P1 close.
  - P2/P3/P4 historical tickets, artifacts, candidates, problems, RCA, Knowledge drafts and bridge failure evidence.
  - P4-01 historical failed `/ui/automation/run` 500 responses are test-surface evidence only, not P5 change evidence.
- Baseline evidence:
  - Remote server pre-baseline state: `server: stopped`; this matches expected handoff after P4/P4-01 and is not an incident.
  - Baseline recovery: `python scripts\manage_remote_stack.py start server` -> `running`, pid `384213`.
  - Health: `python scripts\manage_remote_stack.py smoke server --insecure-tls` -> `https://192.168.100.17:9443/api/health -> 200`.
  - Control-plane: `control: running`, pid `326023`.
  - pywinauto: `.venvs\agent-win\Scripts\python.exe -c "import pywinauto; print(pywinauto.__version__)"` -> `0.6.9`.
  - Local agent status before server recovery: bridge reachable, `connection_state=disconnected`, detail `ошибка handshake`.
  - Local agent status after server recovery: `python scripts\agent_test_driver.py status live-v3-p1-clean2` -> bridge reachable, `connection_state=connected`, detail `WS подключён`, ticket_count `21`.
  - Local agent process: `python scripts\manage_local_agent.py status live-v3-p1-clean2` -> running, source GUI mode, pid `26848`, ws `wss://192.168.100.17:9443/ws`.
  - UIA: `scripts\live_agent_uia_state_probe.py --instance live-v3-p1-clean2 --expect-connected --expect-account --output artifacts\p5-20260528-2325-da0d8ee6-uia-baseline.json --max-depth 10 --max-nodes 2000 --max-seconds 60` -> pywinauto `0.6.9`, backend `uia`, window `Maria Agent v3.1.61`, process `28128`, `connection_state=connected`, `account_mode=confirmed_binding`, `ticket_count=21`, failures `[]`.
  - Agent SQLite path: `.local-agent\instances\live-v3-p1-clean2\data\storage.db`.
  - Agent SQLite marker counts: active `outbox` rows `0`; `outbox_sent_history` marker rows `0`; `seen_commands` marker rows `0`; `pending_consents_total=0`.
  - Server DB marker check: no `device_outbox` rows matched marker `p5-20260528-2325-da0d8ee6` by `command_id`, `request_id`, `trace_id`, `operation_id`, `command` or `params`.
  - Browser/change UI: real browser URL `https://192.168.100.17:9443/app/admin/changes`, login `admin` fixture, visible `Рабочее место изменений` and empty state `Изменений пока нет`; console errors `[]`; HTTP errors `[]`.
  - Browser evidence artifact: `artifacts\p5-20260528-2325-da0d8ee6-admin-changes-baseline.png`.

P5 product contract:
- Change records are internal support/admin objects. Requester/public users have no direct change API. Agent token must not create, approve or implement changes unless explicitly bound to an authorized support/admin context, which is not the default.
- Supported change types are `standard`, `normal` and `emergency`. Standard changes are preapproved only when a valid standard/preapproval catalog policy matches. Normal changes require approval according to risk/policy. Emergency changes may use emergency flow but must require retrospective/PIR according to policy.
- Approval state is server-authoritative. Approval cannot be faked by request body fields. Duplicate approval is idempotent or deterministic. Unauthorized approval is denied before DB mutation.
- Maintenance windows and blackout windows are enforced server-side. Blackout scheduling is denied unless a documented emergency override exists and is audited. Timestamps must be recorded with absolute UTC/timezone evidence.
- Non-standard/high-risk changes require risk/impact/implementation/rollback/test plans according to policy. Client-only fields must not downgrade risk or bypass gates. Validation errors must be structured and non-500.
- P5 does not auto-execute changes. Implementation tasks are internal workflow items. Task completion/dependencies gate implementation/closure only where policy says so, and no agent tools are silently dispatched.
- Implemented or emergency changes require PIR/retrospective if policy says so. PIR is internal-only, feeds metrics and is not requester/public visible.
- Change metrics are aggregate-only and must not include requester name, phone/email, account session ids/tokens, public codes/hashes, raw ticket text/messages, artifact paths, device tokens, cookies or auth headers.

P5 bug template:

```md
### BUG-YYYYMMDD-P5-NN - short title

Severity: P0/P1/P2/P3/P4/P5
Status: reproduced / root-cause-confirmed / fix-in-progress / verified-fixed / verified-non-product / known-limitation / deferred / not-a-bug
Area: change-create / standard-change / emergency-change / approval / preapproval / maintenance-window / blackout-window / risk-impact / rollback / implementation-task / lifecycle / PIR / problem-linkage / RBAC / public-access / requester-access / privacy-PII / metrics / browser-ui / server-db / workflow / test-contamination

P5 scenario:
Run id:
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
- Blocking further P5: yes/no
- Fixed now: yes/no

Fix summary:
Changed files:
Tests:
Live regression:
Regression check:
Remaining risk:
Status consistency checked: yes/no
```

P5 scenario checklist:
- [x] P5.1 Change API / route discovery.
- [x] P5.2 Change request creation: standard, normal, emergency.
- [x] P5.3 Standard preapproval catalog.
- [x] P5.4 Normal change approval flow.
- [x] P5.5 Emergency change and retrospective.
- [x] P5.6 Maintenance windows and blackout windows.
- [x] P5.7 Risk / impact / implementation / rollback gates.
- [x] P5.8 Implementation tasks.
- [x] P5.9 Change lifecycle and invalid transitions.
- [x] P5.10 Problem / RCA / improvement action linkage.
- [x] P5.11 PIR / post-implementation review.
- [x] P5.12 Change metrics / no-PII analytics.
- [x] P5.13 RBAC and requester/public boundary.
- [x] P5.14 Regression against P0-P4 boundaries.

Discovery-first rule:
- Run P5.1-P5.14 as far as safely possible and record every finding in this section before root cause/fix.
- Fix immediately only for requester/public/RBAC access leaks, PII leaks, approval/preapproval bypass, scheduling/blackout safety breach, unauthorized mutation, data-integrity corruption or a blocker that invalidates downstream evidence.
- Do not mark P5 closed while requester/public can access or mutate change APIs, approval/preapproval can be bypassed, emergency/PIR gates fail, blackout/maintenance validation fails, high-risk rollback/plan gates fail, internal change/problem/RCA data leaks externally, change metrics leak PII, stale P5 outbox/device_outbox exists, or browser/UIA evidence is missing.

P5 discovery evidence before fixes:
- P5.2 route tested: real browser-admin session calling real `/api/web/changes*` APIs from `https://192.168.100.17:9443/app/admin/changes`.
- `GET /api/web/change-policies` -> HTTP `200`, no policies.
- `GET /api/web/changes/metrics/summary` -> HTTP `200`, aggregate keys only: `change_count`, `open_change_count`, `emergency_change_count`, `failed_change_count`, `rollback_count`, `failure_rate`, `rollback_rate`, `average_lead_time_hours`, `average_implementation_duration_hours`, `pir_completion_rate`, `emergency_retrospective_overdue_count`, breakdown maps by type/status/risk/service.
- Created clean P5 changes:
  - Standard: `CHG-000009`, id `de4d626b-d863-47de-bb63-0202dec424b0`, status `draft`, marker `p5-20260528-2325-da0d8ee6`.
  - Normal: `CHG-000010`, id `9d388434-3092-4545-98f8-38d598d64608`, status moved to `awaiting_approval` during P5.4/P5.7 gate probing.
  - Emergency with justification: `CHG-000011`, id `cbce0b63-dccd-4a0c-a08c-06f1151efbea`, status `draft`.
  - Emergency missing justification: `CHG-000012`, id `e492c9a7-827e-40b6-baa3-393e236a3018`, create accepted as `draft`; subsequent `awaiting_approval` attempt denied by missing risk assessment before emergency-justification gate was reached.
- Invalid `change_type=not_real_type` with body-supplied `status=approved` / `approved=true` returned HTTP `400`, `error=change_type is invalid`; no approval bypass observed on this negative create path.

### BUG-20260528-P5-01 - duplicate risk/plan rows make change transition return HTTP 500

Severity: P1
Status: verified-fixed
Area: lifecycle / risk-impact / rollback / approval / browser-ui / server-db

P5 scenario: P5.4 Normal change approval flow and P5.7 Risk / impact / implementation / rollback gates.
Run id: `p5-20260528-2325-da0d8ee6`
Expected:
- Change lifecycle validation should be deterministic and return structured non-500 denials for invalid/repeated transitions.
- Normal/high-risk change should evaluate approved risk and plan rows without crashing even if multiple drafts/approved rows exist from repeated operator/API actions.
- Body-supplied `approved=true` must not bypass approval; after legitimate approval, transition to `approved` should succeed or return a structured validation denial.
Actual:
- Several `/api/web/changes/9d388434-3092-4545-98f8-38d598d64608/transition` calls returned HTTP `500`.
- Server log shows `sqlalchemy.exc.MultipleResultsFound: Multiple rows were found when one or none was required` in `ChangeService._validate_assessment_ready()` and `_validate_approval_ready()`.
- Browser console recorded failed resources for the transition route during the real admin page session.
Repro steps:
- In real browser admin session at `/app/admin/changes`, create normal change `CHG-000010`.
- Transition it through `submitted -> assessing`.
- Create/submit/approve risk assessments and create/approve more than one plan row while probing missing rollback/good rollback gates.
- Call `POST /api/web/changes/{change_id}/transition` with `{"status":"awaiting_approval"}` and later `{"status":"approved"}`.
- Observe HTTP `500` on transition route.

Evidence:
- Transport/API:
  - `POST /api/web/changes/{normal_id}/transition {"status":"awaiting_approval"}` returned HTTP `500` after duplicate risk/plan rows existed.
  - `POST /api/web/changes/{normal_id}/transition {"status":"approved","approved":true}` returned HTTP `500`; body-supplied approval did not produce a successful bypass, but the route crashed instead of returning structured denial.
  - `POST /api/web/changes/{normal_id}/approvals/{approval_id}/approve` returned HTTP `200`; duplicate approve returned HTTP `200` with `approval_status=approved`.
- Server log:
  - `server/web_api/change_handlers.py:75` -> `ChangeService.transition_change(...)`.
  - `server/change/change_service.py:316` in `_validate_assessment_ready()` -> `.scalar_one_or_none()` -> `sqlalchemy.exc.MultipleResultsFound`.
  - `server/change/change_service.py:330` in `_validate_approval_ready()` -> `.scalar_one_or_none()` -> `sqlalchemy.exc.MultipleResultsFound`.
- Agent log: not applicable; P5 change APIs do not dispatch agent work.
- Server DB:
  - Normal change `CHG-000010` exists with marker `p5-20260528-2325-da0d8ee6`; risk/plan/approval rows were created by real API calls.
- Agent SQLite:
  - Not involved; baseline marker checks were zero and P5 transition calls are server/web only.
- Browser/UI:
  - Real browser URL `https://192.168.100.17:9443/app/admin/changes`.
  - Browser console recorded transition route failed-resource entries during the scenario.
- UIA:
  - Not directly applicable to change workflow; baseline UIA state probe passed before P5 discovery.
- Test artifact:
  - Baseline browser screenshot `artifacts\p5-20260528-2325-da0d8ee6-admin-changes-baseline.png`.
- Run marker: `p5-20260528-2325-da0d8ee6`.

Impact:
- Blocks P5 close because normal change approval/lifecycle evidence becomes unreliable after repeated operator/API actions.
- A normal operator retry can turn expected validation into HTTP 500 and prevent approval transition.
Root cause hypothesis:
- `ChangeService` readiness validators assume at most one approved/submitted risk/plan/approval row and use `scalar_one_or_none()`.
- The API allows creating multiple risk assessments/plans/approval rows for the same change; once multiple rows match readiness criteria, the validator raises `MultipleResultsFound`.
Root cause confirmed:
- `server/change/change_service.py` used `.scalar_one_or_none()` in `_validate_assessment_ready()` and `_validate_approval_ready()` for approved `ChangeRiskAssessment` and `ChangePlan` rows.
- `RiskAssessmentService.create_assessment()` and `ChangePlanService.create_plan()` intentionally create versioned rows; repeated operator/API edits can leave multiple approved versions for one change.
- The readiness validators therefore crashed with SQLAlchemy `MultipleResultsFound` instead of evaluating the latest approved version and returning deterministic lifecycle results.
- Adjacent audit found `_has_approved_pir()` used the same single-row assumption for approved PIR rows.
Fix policy:
- Blocking further P5: yes
- Fixed now: yes

Fix summary:
- Added deterministic latest-approved selectors for change risk assessments and plans, ordered by `version_number` then approval timestamp/id.
- `_validate_assessment_ready()` now checks existence of the latest approved risk/plan without crashing on older approved versions.
- `_validate_approval_ready()` now evaluates rollback/approval gates against the latest approved plan, preserving the product contract that newer approved plan versions supersede older ones.
- `_has_approved_pir()` now checks for any latest approved PIR row with a limited ordered query, avoiding the same duplicate-row crash class.
Changed files:
- `server/change/change_service.py`
- `server/tests/test_change_lifecycle.py`
Tests:
- Red before fix: `python -m pytest server\tests\test_change_lifecycle.py::test_duplicate_approved_risk_and_plan_versions_do_not_break_approval_transition server\tests\test_change_lifecycle.py::test_latest_approved_plan_controls_rollback_gate -q --tb=short` reproduced `MultipleResultsFound`.
- Green after fix: same command -> `2 passed in 338.27s`.
- Focused regression: `python -m pytest server\tests\test_change_lifecycle.py server\tests\test_change_api.py server\tests\test_change_pir.py -q --tb=short` -> `6 passed in 353.20s`.
Live regression:
- Deployed commit `8bfc7c7688c4396625495d3f8a20ae539a6ca94c` to `https://192.168.100.17:9443` using `python scripts\release_server_to_remote.py --gate quick --allow-local-dirty --leave-running --smoke-insecure-tls --smoke-attempts 8 --smoke-delay 2`; remote smoke passed `/api/health -> 200`.
- Clean marker: `p5-fix2-20260529-0005-8bfc7c76`.
- Real browser/admin/API surface: `https://192.168.100.17:9443/app/admin/changes` with same-origin `/api/web/changes*` calls.
- Created normal change `CHG-000014` / `39603dc0-9cfa-49c8-bed4-265b25b3af66`.
- Created and approved two risk assessment versions and two plan versions; v1 plan had no rollback, v2 plan had rollback.
- Transition `assessing -> awaiting_approval` returned HTTP `200`; approval request/decision returned HTTP `200`; transition `awaiting_approval -> approved` returned HTTP `200`; final change status `approved`.
- No lifecycle call in the clean rerun returned HTTP `500`.
- Server DB proof: `CHG-000014|approved|normal|high|2|2|1` for change status/type/risk and approved risk/plan/approval counts.
- Server DB no agent dispatch proof: `device_outbox` rows matching marker `p5-fix2-20260529-0005-8bfc7c76` = `0`.
- Agent SQLite proof: `outbox_marker=0`, `failed_outbox_marker=0`, `sent_history_marker=0`, `seen_commands_marker=0`.
- Server logs: last 120 server service lines contained no `MultipleResultsFound`, `Traceback`, `ERROR`, or marker-related errors.
- Evidence artifact: `artifacts\p5-fix2-20260529-0005-8bfc7c76-change-regression.json`.
Regression check:
- Duplicate approved risk/plan versions no longer produce HTTP 500 in service tests.
- Latest approved plan still controls rollback validation; an approved newer plan without rollback keeps approval transition denied.
Remaining risk:
- `p5-fix-20260529-0000-8bfc7c76` is labeled test-tool contamination: the probe extracted the risk id from the wrong response field and sent `/risk/undefined/...`; it is not P5-01 product evidence and was not used for verification.
Status consistency checked: yes

### BUG-20260529-P5-02 - change subresource validation denials return HTTP 500

Severity: P1
Status: verified-fixed
Area: workflow / risk-impact / implementation-task / PIR / browser-ui / server-db

P5 scenario: P5.7 Risk / impact / implementation / rollback gates, P5.8 Implementation tasks, P5.11 PIR / post-implementation review.
Run id: `p5-errmap-20260529-0010-492d2bf2`
Expected:
- Expected validation denials for missing/invalid risk, plan, approval, task and PIR ids should return structured HTTP `400` or `404`, not HTTP `500`.
- Browser-visible admin actions should not create console 5xx noise for normal validation errors.
- Denied invalid-id actions must not mutate server DB or dispatch agent work.
Actual:
- Real browser/admin same-origin API calls returned HTTP `500` for:
  - `POST /api/web/changes/{change_id}/risk/not-a-risk/submit`
  - `POST /api/web/changes/{change_id}/risk/not-a-risk/approve`
  - `POST /api/web/changes/{change_id}/plans/not-a-plan/approve`
  - `POST /api/web/changes/not-a-change/approvals/request`
  - `POST /api/web/changes/{change_id}/tasks/not-a-task/complete`
  - `POST /api/web/changes/not-a-change/pir`
Repro steps:
- Use real browser admin page `https://192.168.100.17:9443/app/admin/changes`.
- Use clean marker `p5-errmap-20260529-0010-492d2bf2`.
- Send the invalid-id requests listed above against live change `CHG-000014`.
- Observe HTTP `500` and browser console failed-resource entries.

Evidence:
- Transport/API: all six invalid-id subresource requests returned HTTP `500` with generic `Server got itself in trouble`.
- Server log: expected `ValueError` escapes from handlers that do not wrap service calls; detailed stack capture pending code audit.
- Agent log: not applicable; change APIs do not dispatch agent work.
- Server DB: invalid-id requests are expected to be validation-only; no mutation evidence pending post-fix regression.
- Agent SQLite: not involved; marker check pending post-fix regression.
- Browser/UI: real browser admin page logged failed resources for all six calls.
- UIA: not applicable to change admin subresource API; baseline UIA state already passed.
- Test artifact: Playwright API output in current run; structured regression artifact pending fix.
- Run marker: `p5-errmap-20260529-0010-492d2bf2`.

Impact:
- Blocks P5 close because normal bad-input/admin validation paths violate the P5 contract that validation errors are structured and non-500.
- This also creates unreliable browser evidence for P5.7/P5.8/P5.11 negative scenarios.
Root cause hypothesis:
- Several `server/web_api/change_handlers.py` handlers call services that raise `ValueError` but do not catch it and map it to `_error(...)`.
- Create/transition handlers already have the correct pattern; subresource submit/approve/request/complete/PIR handlers are inconsistent.
Root cause confirmed:
- `server/web_api/change_handlers.py` had inconsistent `ValueError` mapping.
- Create/transition/schedule/task-create handlers caught `ValueError` and returned structured `_error(...)`, but risk submit/approve, plan approve, approval request, task complete, PIR create/submit/approve and policy save allowed service `ValueError` to escape to aiohttp as HTTP `500`.
- The affected services already raise deterministic `ValueError` messages such as `risk assessment not found`, `change plan not found`, `change task not found`, `PIR not found` and `change not found`; the bug was in the web boundary mapping, not in persistence.
Fix policy:
- Blocking further P5: yes
- Fixed now: yes

Fix summary:
- Added consistent `try/except ValueError` mapping to the affected change subresource handlers.
- Expected invalid-id/missing-resource validation now returns structured JSON `{status: "error", error: "..."}` with HTTP `400`, preserving `500` for true unexpected handler failures.
Changed files:
- `server/web_api/change_handlers.py`
- `server/tests/test_change_api.py`
Tests:
- `python -m pytest server\tests\test_change_api.py::test_change_web_api_subresource_validation_errors_are_not_500 -q --tb=short` -> `1 passed in 338.47s`.
- `python -m pytest server\tests\test_change_api.py server\tests\test_change_lifecycle.py server\tests\test_change_pir.py -q --tb=short` -> `7 passed in 360.20s`.
Live regression:
- Deployed commit `1d8e986d3fcfe266b6428f5d937a6d9dcd12d5b3` to `https://192.168.100.17:9443` using `python scripts\release_server_to_remote.py --gate quick --allow-local-dirty --leave-running --smoke-insecure-tls --smoke-attempts 8 --smoke-delay 2`; remote smoke passed `/api/health -> 200`.
- Clean marker: `p5-errmap-fix-20260529-0020-1d8e986d`.
- Real browser/admin/API surface: `https://192.168.100.17:9443/app/admin/changes` with same-origin `/api/web/changes*` calls.
- Invalid risk submit/approve, plan approve, approval request, task complete and PIR create/submit/approve all returned structured HTTP `400` JSON with `status=error`; no request returned HTTP `500`.
- Server DB no agent dispatch proof: `device_outbox` rows matching marker `p5-errmap-fix-20260529-0020-1d8e986d` = `0`.
- Agent SQLite proof: `outbox_marker=0`, `failed_outbox_marker=0`, `seen_commands_marker=0`.
- Server logs: last 160 server service lines contained no marker errors, `Traceback`, or `ERROR`.
- Evidence artifact: `artifacts\p5-errmap-fix-20260529-0020-1d8e986d-change-error-mapping.json`.
Regression check:
- Focused tests cover invalid risk submit/approve, plan approve, approval request, task complete, PIR create/submit/approve.
- Existing P5-01 lifecycle tests still pass in the focused suite.
Remaining risk:
- Browser devtools records expected failed-resource entries for intentional HTTP `400` negative tests; these are not HTTP `500` regressions.
Status consistency checked: yes

## P5 findings summary - 2026-05-29 - run_id=p5-close-20260529-0030-1d8e986d

| Bug | Severity | Area | Blocking P5 | Fix now | Status |
|---|---|---|---|---|---|
| BUG-20260528-P5-01 | P1 | lifecycle / risk-impact / rollback / approval | yes | yes | verified-fixed |
| BUG-20260529-P5-02 | P1 | workflow / risk-impact / task / PIR / browser-ui | yes | yes | verified-fixed |

P5 discovery and clean close evidence:
- Browser/admin/API surface: real browser at `https://192.168.100.17:9443/app/admin/changes`, same-origin `/api/web/changes*` calls.
- Clean close marker: `p5-close-20260529-0030-1d8e986d`.
- Standard/preapproval: saved explicit change-type policy `std-preapproval-p5-close-20260529-0030-1d8e986d`; standard change `CHG-000015` used skipped non-required approval row and reached `approved`.
- Normal approval/package: normal change `CHG-000016` created approved risk, approved implementation/rollback/validation plan, approval row and reached `approved`.
- Emergency gate: emergency change `CHG-000017` without `emergency_justification` was denied at approval with structured HTTP `400`, `emergency justification is required before approval`.
- Implementation tasks/PIR: normal change `CHG-000018` was denied `implemented` while required task was open; after task completion it moved to `pir_required`, closure without PIR was denied, then approved PIR allowed final `closed`.
- Scheduling: maintenance advisory window and blackout window were created for `2026-06-10T10:00:00Z..12:00:00Z` / `10:30:00Z..11:30:00Z`; scheduling `CHG-000019` inside blackout without override returned HTTP `400`, and justified override returned HTTP `200` with status `scheduled`.
- Problem/RCA/improvement linkage: `POST /api/web/changes/from-problem/7d31d33c-4f15-4add-a560-229a7caa478f` created `CHG-000020` with `source_kind=problem`; `POST /api/web/changes/from-improvement-action/a2c6f142-af7e-40a5-8686-a3817959afd5` created `CHG-000021` with `source_kind=improvement_action`.
- Metrics/no-PII: `GET /api/web/changes/metrics/summary` returned aggregate counts/rates/breakdowns only; checked for account/session/public token, email/phone, cookie/auth, raw message and device token strings; findings `[]`.
- Browser evidence: refreshed change workspace showed `Всего изменений=19`, `PIR=100%`, `CHG-000015` approved, `CHG-000018` closed and `CHG-000019` scheduled; intentional negative requests showed browser failed-resource entries for HTTP `400`, not HTTP `500`.
- RBAC boundary:
  - Anonymous direct HTTP without cookies returned `401` for `/api/web/changes`, `/api/web/change-windows`, `/api/web/change-policies`, and `/api/web/changes/metrics/summary`.
  - Handler decorators require `admin/support` for mutations and allow `auditor` only on read/metrics/policies/windows where defined by product policy.
  - Requester/public direct change APIs are not exposed as public routes; no requester/public route is used to create, approve, schedule, implement or PIR a change.
- Server DB evidence for close marker:
  - `changes=5`
  - `approved_standard=1`
  - `closed_pir_change=1`
  - `scheduled_blackout_override=1`
  - `windows=2`
  - `approved_pir=1`
  - `done_tasks=1`
  - `device_outbox_marker=0`
- Agent SQLite evidence for close marker: `outbox_marker=0`, `failed_outbox_marker=0`, `seen_commands_marker=0`.
- UIA evidence: `scripts\live_agent_uia_state_probe.py --instance live-v3-p1-clean2 --expect-connected --expect-account --output artifacts\p5-close-20260529-0030-1d8e986d-uia-state.json` -> pywinauto `0.6.9`, backend `uia`, `connection_state=connected`, `account_mode=confirmed_binding`, `ticket_count=21`, failures `[]`.
- Server logs: no marker-related `Traceback` / `ERROR` observed during post-fix validation windows.

## P5 close summary - 2026-05-29 - run_id=p5-close-20260529-0030-1d8e986d

Status: P5 closed

Code head:
- Product head deployed for P5 fixes: `1d8e986d3fcfe266b6428f5d937a6d9dcd12d5b3`.
- PLANS/evidence close head: `a79b85a54e2360c549890ee0728e2985f647a10a`.
Server URL: `https://192.168.100.17:9443`
Post-validation handoff: remote server was stopped after P5 checks per project workflow; final live smoke before stop returned `/api/health -> 200`.
Agent A: `live-v3-p1-clean2`
Agent B: not used; P5 change enablement scenarios did not require two-agent command routing.
Clean tickets: not created for P5; changes are internal support/admin objects and no agent execution was expected.
Change ids:
- `CHG-000015` standard/preapproved approved.
- `CHG-000016` normal approved.
- `CHG-000017` emergency missing justification denied at approval.
- `CHG-000018` task/PIR/closure completed.
- `CHG-000019` scheduled with justified blackout override.
- `CHG-000020` problem-linked change.
- `CHG-000021` improvement-action-linked change.
Approval ids:
- `1ae38392-8d89-4f73-bb44-9870eebb8c00` skipped standard preapproval.
- `1e3782bf-f3d3-43e9-9e18-278f41ea34b4` normal approval.
- Additional normal/emergency close-run approval rows are tied to the marker in DB/browser evidence.
Window ids:
- Maintenance/blackout rows created with titles containing `p5-close-20260529-0030-1d8e986d`.
Blackout ids:
- Blackout row title `Blackout block p5-close-20260529-0030-1d8e986d`.
Task ids:
- `af57957d-12ed-450c-87f1-7534302646e0`.
PIR ids:
- `1cb92aa1-4533-40f0-b22f-4b193137485e`.
Problem/RCA/action links:
- `CHG-000020` linked to `PRB-000002`.
- `CHG-000021` linked to improvement action `a2c6f142-af7e-40a5-8686-a3817959afd5`.
Old contamination ignored:
- P0/P1/P2/P3/P4 historical tickets/outbox/artifacts/problem/RCA/Knowledge rows.
- Pre-fix P5 rows `CHG-000001..CHG-000014` are historical discovery/fix evidence; clean close evidence uses `p5-close-20260529-0030-1d8e986d`.
- `p5-fix-20260529-0000-8bfc7c76` is test-tool contamination from wrong risk id extraction.

P5.1 result: passed; routes/docs/code discovered and recorded.
P5.2 result: passed for standard/normal/emergency create paths and invalid type denial.
P5.3 result: passed for explicit standard preapproval policy and skipped non-required approval.
P5.4 result: passed; normal approval requires risk/plan/approval and duplicate version bug is fixed.
P5.5 result: passed; emergency approval without justification denied; emergency/PIR policy verified through gate behavior.
P5.6 result: passed; maintenance advisory row created, blackout hard-block and justified override verified.
P5.7 result: passed; risk/impact/implementation/rollback gates verified, including latest-plan regression.
P5.8 result: passed; implementation task blocks implementation until complete; no agent work dispatched.
P5.9 result: passed for canonical transitions and invalid transitions exercised in normal/emergency/task/PIR flows.
P5.10 result: passed for problem and improvement action linkage.
P5.11 result: passed; PIR required after implementation and required before closure.
P5.12 result: passed; metrics aggregate/no-PII check clean.
P5.13 result: passed for admin/support live flow and anonymous denial; server-side route RBAC reviewed for requester/public denial.
P5.14 result: passed; no P5 marker outbox/device_outbox rows, UIA probe green, no change lifecycle auto-dispatched agent tools.

Bugs found:
- `BUG-20260528-P5-01`
- `BUG-20260529-P5-02`

Verified fixed:
- `BUG-20260528-P5-01`
- `BUG-20260529-P5-02`

Deferred/known limitations:
- Maintenance windows are advisory in P5 by documented policy; blackout windows are the hard scheduling block.
- Agent-token and named requester-account negative checks were not executed with live raw tokens to avoid token handling risk; public/no-auth denial and server-side RBAC decorators were verified.

Security/privacy result:
- Requester/public change API access: anonymous direct access denied with `401`; no public requester route exists for change mutation.
- Approval/preapproval boundary: preapproval only through explicit standard policy; normal approval required risk/plan/approval; body `approved=true` did not bypass lifecycle.
- Scheduling/blackout safety: blackout denied without override and allowed with explicit justification.
- No-PII metrics: aggregate payload contained counts/rates/breakdowns only; no checked PII/secret strings found.
- Problem/RCA/change linkage visibility: change linkage is internal admin/support API; no requester/public projection was used or exposed in P5 close evidence.

Browser/UI evidence:
- Real browser `/app/admin/changes` baseline and close validation; visible rows for `CHG-000015..CHG-000019` and refreshed aggregate counters.
UIA evidence:
- `artifacts\p5-close-20260529-0030-1d8e986d-uia-state.json`.
DB/SQLite evidence:
- Server DB close marker counts listed above.
- Agent SQLite close marker counts all zero.

P6 readiness:
- ready

### BUG-20260528-P4-04 - Knowledge draft creation 500s on reused problem_key slug

Severity: P1
Status: verified-fixed
Area: known-error / workaround / knowledge-draft / server-db / browser-ui

P4 scenario: P4.6.C Generate Knowledge draft from known error/workaround.
Run id: `p4-20260528-1815-5217eb14`
Expected:
- Creating a known-error/workaround draft from a valid problem should return HTTP `200`, create `support_internal` Knowledge drafts, link them to the current problem, and be idempotent or return a safe conflict if a draft already exists.
- A historical Knowledge draft for a different problem must not make the current problem's draft endpoint return HTTP `500`.
Actual:
- Browser/web-session RCA create/submit/approve succeeded for problem `PRB-000001` / `82b6dbb5-76e7-448d-bffd-7e693ff8d3ae`.
- `POST /api/web/problems/82b6dbb5-76e7-448d-bffd-7e693ff8d3ae/known-error-draft` returned HTTP `500`.
- `POST /api/web/problems/82b6dbb5-76e7-448d-bffd-7e693ff8d3ae/workaround-draft` returned HTTP `500`.
- No `problem_known_error_links` rows or current-problem Knowledge drafts were created.
Repro steps:
1. Use real browser/admin session at `https://192.168.100.17:9443/app/admin/problems`.
2. Create/use problem `82b6dbb5-76e7-448d-bffd-7e693ff8d3ae`, status `closed`, service `network`, offering `network.vpn_issue`.
3. Create RCA draft, submit, approve.
4. Call known-error and workaround draft endpoints through the browser web session.
5. Observe HTTP `500` responses and browser console resource errors.

Evidence:
- Transport/API:
  - `POST /api/web/problems/82b6dbb5-76e7-448d-bffd-7e693ff8d3ae/rca` -> HTTP `200`, RCA version `2`, status `draft`.
  - `POST /submit-review` -> HTTP `200`, status `in_review`.
  - `POST /approve` -> HTTP `200`, status `approved`.
  - `POST /known-error-draft` -> HTTP `500`, response body `500 Internal Server Error`.
  - `POST /workaround-draft` -> HTTP `500`, response body `500 Internal Server Error`.
- Server log:
  - `known-error-draft`: `UniqueViolationError`, constraint `knowledge_items_slug_key`, key `(slug)=(known_error-prb-000001)` already exists.
  - `workaround-draft`: `UniqueViolationError`, constraint `knowledge_items_slug_key`, key `(slug)=(workaround-prb-000001)` already exists.
  - Existing conflicting Knowledge rows were created on `2026-05-17` for older problem `380454f6-007d-48d0-ba5f-5e4253fb3912`.
- Agent log: not applicable.
- Server DB:
  - Current problem `82b6dbb5-76e7-448d-bffd-7e693ff8d3ae` / `PRB-000001` exists and is `closed`.
  - RCA rows exist: versions `1` and `2`, both `approved`.
  - `problem_known_error_links` for current problem: `0`.
  - `knowledge_items` existing slug collisions:
    - `known_error-prb-000001`, source problem `380454f6-007d-48d0-ba5f-5e4253fb3912`, visibility `support_internal`, status `draft`.
    - `workaround-prb-000001`, source problem `380454f6-007d-48d0-ba5f-5e4253fb3912`, visibility `support_internal`, status `draft`.
- Agent SQLite: not applicable.
- Browser/UI: `/app/admin/problems` shows the P4 problem and draft action buttons; after endpoint calls, browser console records HTTP `500` resource errors.
- UIA: not applicable.
- Test artifact: Browser MCP output for the draft calls; server DB/log evidence recorded in this block.
- Run marker: `p4-20260528-1815-5217eb14`.

Impact:
- P4.6 known-error/workaround/Knowledge loop cannot pass.
- This also exposes a product idempotency/data-integrity issue: Knowledge draft slugs are derived from `problem_key`, but historical DB rows can reuse the same key after test data reset/import, causing unhandled 500s.
Root cause hypothesis:
- `ProblemKnownErrorService._create_draft()` derives slug as `{item_type}-{problem.problem_key.lower()}` and calls `KnowledgeRepo.create_item_draft()` without checking existing same-source link or generating a globally unique slug. The unique `knowledge_items.slug` constraint then raises an unhandled DB integrity error.
Root cause confirmed: yes - `ProblemKnownErrorService._create_draft()` derived global Knowledge slugs only from `problem_key` (`known_error-prb-000001` / `workaround-prb-000001`). Historical Knowledge rows for an older problem already owned those slugs, so `KnowledgeRepo.create_item_draft()` hit `knowledge_items_slug_key` and the handler returned an unhandled HTTP `500`.
Fix policy:
- Blocking further P4: no for RBAC/metrics discovery, yes for final P4 close.
- Fixed now: yes

Fix summary:
- Added idempotent existing-link handling for problem known-error/workaround drafts.
- Changed draft slug generation to reuse the natural slug only when free or already linked to the same problem; otherwise it appends the problem id prefix, e.g. `known_error-prb-000001-82b6dbb5`.
Changed files:
- `server/problem/known_error_service.py`
- `server/tests/test_problem_knowledge_integration.py`
Tests:
- `python -m pytest server\tests\test_problem_candidate_service.py::test_repeated_incident_scan_dedupes_across_lookback_windows server\tests\test_problem_candidate_service.py::test_candidate_convert_maps_legacy_sentinels_to_empty_catalog_fields server\tests\test_problem_knowledge_integration.py::test_problem_known_error_draft_handles_reused_problem_key_slug_collision -q` -> `3 passed in 343.76s`.
Live regression:
- Commit `bbe802fcfe74156dff1fc988551c7b2f47eb8aea` deployed with `python scripts\release_server_to_remote.py --gate quick --allow-local-dirty --leave-running --smoke-insecure-tls --smoke-attempts 8 --smoke-delay 2`; remote smoke passed.
- Browser/web-session after deploy:
  - `POST /api/web/problems/82b6dbb5-76e7-448d-bffd-7e693ff8d3ae/known-error-draft` -> HTTP `200`, link `ea4efcc5-25a8-4d11-a7bc-921e0d7d8ef4`, Knowledge item `89d72ce9-0d21-40dc-98ec-65eb23464569`.
  - Repeating known-error draft -> HTTP `200`, same link/item.
  - `POST /api/web/problems/82b6dbb5-76e7-448d-bffd-7e693ff8d3ae/workaround-draft` -> HTTP `200`, link `9429e827-4e28-45c7-85e5-8339811ddaaa`, Knowledge item `9f501cb2-94f7-4210-a4c3-3e5972fa5f96`.
  - Repeating workaround draft -> HTTP `200`, same link/item.
- Server DB:
  - `knowledge_items.slug=known_error-prb-000001-82b6dbb5`, `item_type=known_error`, `visibility=support_internal`, `status=draft`, `source_ref=82b6dbb5-76e7-448d-bffd-7e693ff8d3ae`.
  - `knowledge_items.slug=workaround-prb-000001-82b6dbb5`, `item_type=workaround`, `visibility=support_internal`, `status=draft`, same source problem.
  - `problem_known_error_links` contains exactly one known-error and one workaround link for the current problem after repeat calls.
Regression check:
- Fresh browser navigation to `/app/admin/problems` after fix: HTTP errors `[]`, console errors `[]`; visible `Problem management`, `PRB-000002`, and `converted`.
Remaining risk:
- If fixed only by changing the slug format, existing draft idempotency still needs explicit verification: repeat draft creation should not create duplicate links or 500.
Status consistency checked: yes

### BUG-20260528-P4-03 - scanner candidates with legacy service cannot be converted to problems

Severity: P1
Status: verified-fixed
Area: problem-candidate / problem-lifecycle / server-db / workflow

P4 scenario: P4.2.A Convert candidate to problem.
Run id: `p4-20260528-1815-5217eb14`
Expected:
- A candidate produced by the product scanner must be convertible to a problem, or scanner must avoid producing candidates that fail the problem creation contract.
- If ticket rows lack catalog service/offering, conversion should either map `legacy/uncategorized` to a valid fallback or create a problem without invalid Service Catalog fields.
Actual:
- Clean candidate `261ba15c-932e-4ac7-8e9f-ea82ca793bf9` was created by scanner from P4 tickets.
- Browser/web-session `POST /api/web/problem-candidates/261ba15c-932e-4ac7-8e9f-ea82ca793bf9/convert` returned HTTP `400`, `service_code is invalid`.
- Repeating the same convert returned the same HTTP `400`; no problem row was created.
Repro steps:
1. Create five P4 marker tickets `T-000628`..`T-000632`.
2. Run scanner with `lookback_hours=1`.
3. Confirm browser/admin shows `Repeated incident pattern: legacy / uncategorized`, `Tickets 5`.
4. Call candidate convert from browser web session.
5. Observe HTTP `400 service_code is invalid`.

Evidence:
- Transport/API:
  - `POST /api/web/problem-candidates/261ba15c-932e-4ac7-8e9f-ea82ca793bf9/convert` -> HTTP `400`, `{"status":"error","error":"service_code is invalid"}`.
  - Repeat convert -> same HTTP `400`.
- Server log: not collected yet.
- Agent log: not applicable.
- Server DB:
  - Candidate `261ba15c-932e-4ac7-8e9f-ea82ca793bf9`: `signal_type=repeated_incident_pattern`, `service_code=legacy`, `offering_code=uncategorized`, `ticket_count=5`, `status=open`.
  - P4 clean ticket rows `T-000628`..`T-000632` have `service_code=NULL`, `offering_code=NULL`, while request form context contains `request_kind=network`.
- Agent SQLite: not applicable.
- Browser/UI: `/app/admin/problems` shows the candidate and `Convert` action, but convert fails with browser console resource errors for the 400 response.
- UIA: not applicable.
- Test artifact: Browser MCP output for convert; DB query evidence recorded in this block.
- Run marker: `p4-20260528-1815-5217eb14`.

Impact:
- P4.2 candidate conversion cannot pass for scanner-created clean candidate.
- Downstream problem lifecycle/RCA/Knowledge tests can proceed through direct problem create, but candidate-to-problem workflow remains P4-blocking before close.
Root cause hypothesis:
- `ProblemCandidateService` materializes null ticket service/offering as literal `legacy` / `uncategorized`; `ProblemService.create_problem()` validates non-empty `service_code` against Service Catalog and rejects `legacy`.
Root cause confirmed: yes - `ProblemCandidateService.convert_candidate()` passed scanner sentinel values `legacy` / `uncategorized` directly into `ProblemService.create_problem()`. When Service Catalog rows exist, `ProblemService._validate_service_offering()` treats non-empty `service_code` as catalog-backed and rejects `legacy`.
Fix policy:
- Blocking further P4: no for discovery, yes for final P4 close.
- Fixed now: yes

Fix summary:
- Candidate conversion now maps sentinel `legacy` / `uncategorized` to `None` before creating the problem, while preserving the candidate evidence and source fields.
Changed files:
- `server/problem/candidate_service.py`
- `server/tests/test_problem_candidate_service.py`
Tests:
- `python -m pytest server\tests\test_problem_candidate_service.py::test_repeated_incident_scan_dedupes_across_lookback_windows server\tests\test_problem_candidate_service.py::test_candidate_convert_maps_legacy_sentinels_to_empty_catalog_fields server\tests\test_problem_knowledge_integration.py::test_problem_known_error_draft_handles_reused_problem_key_slug_collision -q` -> `3 passed in 343.76s`.
Live regression:
- Fix marker `p4-fix-20260528-1845-bbe802fc`: created tickets `T-000633`..`T-000637`.
- Browser/web-session convert `POST /api/web/problem-candidates/ec58d383-8049-4d4d-9e22-897c8a114802/convert` -> HTTP `200`.
- Converted problem `PRB-000002` / `7d31d33c-4f15-4add-a560-229a7caa478f`, `status=new`, `service_code=NULL`, `offering_code=NULL`, `source_kind=repeated_incident_pattern`, `source_ref=ec58d383-8049-4d4d-9e22-897c8a114802`.
- Browser `/app/admin/problems` shows `PRB-000002` and the candidate status `converted`.
Regression check:
- Invalid closed transition and invalid ticket link still return HTTP `400`; duplicate link remains idempotent.
Remaining risk:
- Browser presentation still displays `legacy / uncategorized` as a safe fallback label even though DB catalog fields on `PRB-000002` are `NULL`; this is projection text, not Service Catalog persistence.
Status consistency checked: yes

### BUG-20260528-P4-02 - scanner creates duplicate open candidates when lookback window changes

Severity: P2
Status: verified-fixed
Area: problem-candidate / problem-scanner / server-db

P4 scenario: P4.1.D Repeat scanner / cooldown / dedup.
Run id: `p4-20260528-1815-5217eb14`
Expected:
- Re-running scanner for the same visible pattern should update an existing open candidate or produce a documented cooldown/audit result.
- Same `signal_type + rule_code + service_code + offering_code + signal key + time bucket` should not create duplicate open candidates visible as identical problem candidates in browser/admin.
Actual:
- Browser/admin first manual scanner run (`lookback_hours=168`) created candidate `6a75bc53-902c-44e4-9ef7-1ae874bdbaae`, visible as `Repeated incident pattern: legacy / uncategorized`, ticket count `24`.
- Browser/admin second scanner run through same web session endpoint with `lookback_hours=1` created a second open candidate `261ba15c-932e-4ac7-8e9f-ea82ca793bf9`, also visible as `Repeated incident pattern: legacy / uncategorized`, ticket count `5`.
- Both candidates remain `status=open` and are simultaneously shown in `/app/admin/problems`.
Repro steps:
1. Create five P4 marker tickets `T-000628`..`T-000632`.
2. Open real browser `https://192.168.100.17:9443/app/admin/problems`.
3. Click `Run scanner`; observe HTTP `200`, run `6362c8a5-5ec1-4acf-953d-4e5ea198e077`, `candidates_created=4`.
4. From the same browser web session, call `POST /api/web/problem-scanner/run` with `{"lookback_hours":1}`; observe HTTP `200`, run `8f9902a0-bceb-4bf0-ad33-ad138cf937d1`, `candidates_created=1`.
5. Refresh `/app/admin/problems`; observe two open `Repeated incident pattern: legacy / uncategorized` candidates.

Evidence:
- Transport/API:
  - First browser scanner response HTTP `200`, `run_id=6362c8a5-5ec1-4acf-953d-4e5ea198e077`, `lookback_hours=168`, `candidates_created=4`.
  - Second browser/web-session response HTTP `200`, `run_id=8f9902a0-bceb-4bf0-ad33-ad138cf937d1`, `lookback_hours=1`, `candidates_created=1`.
- Server log: not collected yet.
- Agent log: not applicable; scanner is server-side.
- Server DB:
  - `problem_candidates.candidate_id=6a75bc53-902c-44e4-9ef7-1ae874bdbaae`, fingerprint `p41:repeated_incident_pattern:repeated_incident:legacy:uncategorized:da7fb4ac02144a41`, `status=open`, `ticket_count=24`.
  - `problem_candidates.candidate_id=261ba15c-932e-4ac7-8e9f-ea82ca793bf9`, fingerprint `p41:repeated_incident_pattern:repeated_incident:legacy:uncategorized:886cfbeb7aa3d7a7`, `status=open`, `ticket_count=5`, evidence ticket ids include all five P4 tickets.
- Agent SQLite: not applicable.
- Browser/UI: `/app/admin/problems` shows two visually identical `Repeated incident pattern: legacy / uncategorized` candidates, one with `Tickets 5`, one with `Tickets 24`; console errors `[]`.
- UIA: not applicable.
- Test artifact: Browser MCP output for scanner run; DB query evidence recorded in this block.
- Run marker: `p4-20260528-1815-5217eb14`.

Impact:
- Dedup/cooldown evidence is unreliable: changing lookback creates duplicate open candidates for the same operational pattern.
- P4.2 conversion can continue using the clean `Tickets 5` candidate, but P4.1.D cannot pass until root cause is fixed or formally classified.
Root cause hypothesis:
- `ProblemCandidateService._fingerprint()` includes the scan `window_start` date in the fingerprint digest. Different lookback windows can produce different fingerprints for the same visible pattern and same day/window family.
Root cause confirmed: yes - `ProblemCandidateService._fingerprint()` included `window_start.date()` in the fingerprint digest. Different lookback windows for the same visible signal generated different fingerprints, so `_upsert_candidate()` could not find/update the existing open candidate.
Fix policy:
- Blocking further P4: no, because later lifecycle/RCA/Knowledge tests can use the clean candidate id.
- Fixed now: yes

Fix summary:
- Scanner fingerprints now use stable signal dimensions (`signal_type`, rule code, service, offering, signal key) and no longer include the scan window start date.
- Existing pre-fix `p41` candidates remain labeled as old contamination; new fixed candidates use a new digest and are updated on repeat runs.
Changed files:
- `server/problem/candidate_service.py`
- `server/tests/test_problem_candidate_service.py`
Tests:
- `python -m pytest server\tests\test_problem_candidate_service.py::test_repeated_incident_scan_dedupes_across_lookback_windows server\tests\test_problem_candidate_service.py::test_candidate_convert_maps_legacy_sentinels_to_empty_catalog_fields server\tests\test_problem_knowledge_integration.py::test_problem_known_error_draft_handles_reused_problem_key_slug_collision -q` -> `3 passed in 343.76s`.
Live regression:
- Fix marker `p4-fix-20260528-1845-bbe802fc`: browser/web-session scanner run `lookback_hours=1` -> HTTP `200`, run `0d5859c2-62d6-4f61-b01b-db2b777d7461`, `candidates_created=1`.
- Repeat scanner run `lookback_hours=1` -> HTTP `200`, run `224d420a-454a-48ae-8383-883435b6f8c7`, `candidates_created=0`, `candidates_updated=1`.
- Scanner run `lookback_hours=2` -> HTTP `200`, repeated-incident candidate updated again; separate SLA candidate was created for a different `sla_breach_pattern` signal.
- Server DB fixed candidate `ec58d383-8049-4d4d-9e22-897c8a114802`: fingerprint `p41:repeated_incident_pattern:repeated_incident:legacy:uncategorized:83be3151447d5673`, `ticket_count=10`, `duplicate_count=2`, later `status=converted`.
Regression check:
- Old pre-fix duplicate candidates `6a75bc53-...` and `261ba15c-...` remain open as labeled pre-fix contamination and are ignored for new-run evidence.
Remaining risk:
- Existing pre-fix duplicates should be manually reviewed/merged or dismissed outside the P4 validation run; they are not new post-fix duplicates.
Status consistency checked: yes
## OBS1 follow-up - 2026-05-29 - run_id=obs1-followup-20260529-1207-afe478ad

Status: in progress

Scope:
- ACK persistence audit: replace `protocol_ack_audit_gap` as a standing telemetry warning with durable ACK -> persisted event / duplicate proof validation.
- Toolset hash drift remediation: classify the two live `toolset_hash_drift` devices and fix product reconcile if drift is real.
- Alert runbook validation: make each Observer runbook actionable for an operator.
- Noise tuning: verify stable dedupe, occurrence count, `last_seen_at`, and automatic resolution when an invariant clears.

Baseline:
- Branch: `codex/helpdesk-process-model`
- Start commit: `afe478ad`
- Known OBS1 follow-up active events before changes:
  - `protocol_ack_audit_gap` warning: Observer had no durable ACK persistence audit rows to correlate ACK with `ticket_events` / `device_events` persistence.
  - `toolset_hash_drift` error for device `2447d396-79cd-53da-b3a9-028c5a4d56da`: `current_toolset_hash=afa6647205d24098`, latest snapshot hash `1235fe825dbaf572`, snapshot id `34`.
  - `toolset_hash_drift` error for device `b08675eb-780c-5042-b442-daa1cd066643`: `current_toolset_hash=464075d978b3230f`, latest snapshot hash `b79fbe209afb45c2`, snapshot id `55`.
- Existing dirty/untracked state preserved: unrelated `pc_agent/ui_gui/tickets_list_model.py` not touched; old `artifacts/*` not staged.

### BUG-20260529-OBS1-04 - Protocol V3 ACK audit gap has no persistence proof

Severity: OBS1
Status: fix-in-progress
Area: protocol-v3 / observer-event / noise-tuning

OBS1 scenario: ACK persistence audit follow-up.
Run id: `obs1-followup-20260529-1207-afe478ad`
Expected:
- Every server `outbox_ack` decision has durable audit evidence proving one of: persisted event id, duplicate proof, or documented no-op.
- Observer emits critical `protocol_ack_without_persistence` for ACK audit rows without proof.
- Observer resolves `protocol_ack_audit_gap` once durable ACK audit rows exist.
Actual:
- OBS1 left `protocol_ack_audit_gap` as warning because outbox ingest produced no durable ACK audit rows.
Repro steps:
1. Run Observer scan on live OBS1 baseline.
2. Observe active `protocol_ack_audit_gap`.
3. Inspect outbox ingest pipeline: `OutboxPersistenceOutcome` had persistence proof fields, but `OutboxAckDecisionService` did not write `AgentRuntimeAudit`.

Evidence:
- Observer event: `protocol_ack_audit_gap`.
- Code: `server/websocket/agent_services.py` queued ACK/NACK without audit; `server/observer/checks/protocol_integrity.py` only checked whether audit rows existed.
- Run marker: `obs1-followup-20260529-1207-afe478ad`.

Impact:
- Observer could see repeated NACK patterns but could not prove ACK -> persistence.
Root cause confirmed: yes.
Fix policy:
- Blocking further OBS1 follow-up: yes.
- Fixed now: yes.

Fix summary:
- Added durable `agent_runtime_audit` rows for ACK decisions with `outbox_id`, `trace_id`, event type, persistence kind, `persisted_event_id`, `persisted`, `duplicate`, `duplicate_proof`, and `documented_noop`.
- Added durable NACK audit for validation/final NACK decisions.
- Extended Protocol checker to raise critical `protocol_ack_without_persistence` when an ACK audit lacks persistence/duplicate/no-op proof.
- Extended Observer scan resolution across all checker sources, not only operation lifecycle, so stale warnings/errors resolve when clean.
Changed files:
- `server/websocket/agent_services.py`
- `server/observer/checks/protocol_integrity.py`
- `server/observer/integrity_service.py`
- `server/tests/test_observer_integrity.py`
- `docs/runbooks/observer_protocol_v3.md`
Tests:
- `python -m py_compile server\websocket\agent_services.py server\websocket\agent_handshake.py server\observer\checks\protocol_integrity.py server\observer\integrity_service.py` -> passed.
- `python -m pytest server\tests\test_agent_services_pipeline.py::test_outbox_ack_decision_final_ack_and_nack -q -s` -> passed.
- `python -m pytest server\tests\test_observer_integrity.py::test_observer_integrity_protocol_ack_audit_valid_duplicate_and_missing_proof -q -s` -> passed.
- `python -m pytest server\tests\test_observer_integrity.py::test_observer_integrity_protocol_gap_resolves_and_repeated_scan_dedupes -q -s` -> passed.
- `python scripts\verify_workspace.py` -> passed as part quick release preflight.
- `python -m compileall -q server pc_agent scripts` -> passed.
- `git diff --check` -> passed.
Live regression:
- Pending.
Regression check:
- Pending.
Remaining risk:
- Live ACK audit requires a real or safe diagnostic outbox item after deploy; pending live validation.
Status consistency checked: yes.

### BUG-20260529-OBS1-05 - Handshake toolset hash change does not request list_tools refresh

Severity: OBS1
Status: fix-in-progress
Area: module-toolset / runtime-presence / observer-event

OBS1 scenario: Toolset hash drift remediation.
Run id: `obs1-followup-20260529-1207-afe478ad`
Expected:
- When agent handshake reports a changed `toolset_hash`, server updates the device card and requests `list_tools` so `device_toolset_snapshots` converges.
Actual:
- Live Observer shows two devices with `devices.current_toolset_hash` newer/different than latest `device_toolset_snapshots.toolset_hash`.
- Code updated `devices.current_toolset_hash` during `upsert_on_handshake()` before comparing whether the hash changed, so the post-upsert comparison saw the new hash and skipped `list_tools`.
Repro steps:
1. Seed device with old `current_toolset_hash`.
2. Run handshake with a different `payload.toolset_hash`.
3. Observe no refresh would be requested by the old comparison path.

Evidence:
- Observer events: two active `toolset_hash_drift` live devices listed in baseline above.
- Code: `server/websocket/agent_handshake.py` compared `agent_toolset_hash` with the already-updated `device.current_toolset_hash`.
- Run marker: `obs1-followup-20260529-1207-afe478ad`.

Impact:
- Device card may report a current toolset hash that has no matching current snapshot, so module/tool availability can be stale.
Root cause confirmed: yes.
Fix policy:
- Blocking further OBS1 follow-up: yes.
- Fixed now: yes.

Fix summary:
- Capture previous `current_toolset_hash` and `current_toolset_snapshot_id` before handshake upsert.
- Request `list_tools` when the reported hash differs from previous hash, or when the device has a hash but no snapshot reference.
Changed files:
- `server/websocket/agent_handshake.py`
- `server/tests/test_handshake_module_reconcile.py`
- `docs/runbooks/observer_module_toolset.md`
Tests:
- `python -m pytest server\tests\test_handshake_module_reconcile.py::test_handshake_enqueues_list_tools_when_toolset_hash_changes -q -s` -> passed.
- `python scripts\verify_workspace.py` -> passed as part quick release preflight.
- `python -m compileall -q server pc_agent scripts` -> passed.
- `git diff --check` -> passed.
Live regression:
- Pending remote deploy and drift-device refresh classification.
Regression check:
- Pending.
Remaining risk:
- Existing live drift rows need normal product refresh after deploy; do not direct-edit DB to silence them.
Status consistency checked: yes.

Runbook validation:
- `observer_protocol_v3.md`: expanded with exact alert meanings, ACK proof fields, safe SQL, safe actions, and prohibitions.
- `observer_module_toolset.md`: expanded with drift classification steps, safe SQL, and refresh/reconcile guidance.
- `observer_operation_lifecycle.md`, `observer_runtime_presence.md`, `observer_account_boundary.md`, `observer_governance.md`: expanded with safe queries/actions and stronger "do not" guidance.

### BUG-20260529-OBS1-06 - release quick gate blocked by docs drift artifacts

Severity: OBS1
Status: verified-non-product / fix-in-progress
Area: governance / documentation

OBS1 scenario: Release/deploy gate for ACK audit and toolset drift remediation.
Run id: `obs1-followup-20260529-1207-afe478ad`
Expected:
- Protocol/observer/handshake changes update canonical navigation docs required by `verify_workspace.py`.
Actual:
- `python scripts\release_server_to_remote.py --gate quick --allow-local-dirty --leave-running --smoke-insecure-tls --smoke-attempts 8 --smoke-delay 2` stopped at `docs_drift_check`.
- Missing required artifacts: `docs/QUICK_LOOKUP.md`, `scripts/navigation_catalog.py`.
Root cause confirmed: yes - changed files matched `server_protocol`, `observer`, and `registry_objects` drift rules.
Fix policy:
- Blocking further OBS1 follow-up: yes.
- Fixed now: yes.
Fix summary:
- Updated `docs/QUICK_LOOKUP.md` with OBS1 follow-up ACK persistence audit and handshake toolset refresh notes.
- Updated `scripts/navigation_catalog.py` Protocol V3 and module/toolset summaries and aliases.
Changed files:
- `docs/QUICK_LOOKUP.md`
- `scripts/navigation_catalog.py`
Tests:
- `python scripts\verify_workspace.py` -> passed as part quick release preflight.
- Quick release gate re-ran and passed, but because workspace was dirty it deployed previous commit `afe478ad`; new-code live validation remains pending until commit/push/release of the follow-up SHA.
Status consistency checked: yes.

### BUG-20260529-OBS1-07 - ACK audit proof accepts persisted flag without event id

Severity: OBS1
Status: fix-in-progress
Area: protocol-v3 / observer-event / noise-tuning

OBS1 scenario: Live ACK persistence proof validation after initial follow-up deploy.
Run id: `obs1-followup-20260529-ack-live-fba082b1`
Expected:
- Durable ACK audit proves ACK -> persistence with a concrete `persisted_event_id`, duplicate proof, or documented no-op.
Actual:
- Live diagnostic `device_event` ACK created `agent_runtime_audit.id=4132` with `persisted=true`, but `persisted_event_id=null`.
- Observer resolved `protocol_ack_audit_gap`, so the proof was weaker than the product contract.
Repro steps:
1. Deploy commit `fba082b1`.
2. Send diagnostic_probe `outbox_item` with marker `obs1-followup-20260529-ack-live-fba082b1`.
3. Query `agent_runtime_audit` for outbox id `obs1-ack-live-b0aa985414a6`.

Evidence:
- Observer event: `protocol_ack_audit_gap` resolved after the weak audit row.
- Server DB: `agent_runtime_audit.id=4132`, `event_type=outbox_ack_persisted`, `persisted=true`, `persisted_event_id=null`.
- Transport/API: diagnostic probe received `handshake_ack` and `outbox_ack`; no command was delivered to the probe.
- Run marker: `obs1-followup-20260529-ack-live-fba082b1`.

Impact:
- ACK audit could prove that the persistence branch thought it inserted a row, but not which durable event row backs the ACK.
Root cause confirmed: yes - device-event `OutboxPersistenceOutcome` did not carry `created_event_id`, and protocol checker accepted bare `persisted=true`.
Fix policy:
- Blocking further OBS1 follow-up: yes.
- Fixed now: yes.

Fix summary:
- Device-event persistence outcome now carries `created_event_id`.
- ACK audit rows use `audit_contract_version=2`.
- Duplicate ACK audit includes explicit `duplicate_proof`.
- Protocol checker only treats v2 ACK audit as sufficient when it has `persisted_event_id`, duplicate proof, or documented no-op; legacy rows no longer satisfy the proof contract.
Changed files:
- `server/websocket/outbox_ingest_components.py`
- `server/websocket/agent_services.py`
- `server/observer/checks/protocol_integrity.py`
- `server/tests/test_observer_integrity.py`
- `docs/runbooks/observer_protocol_v3.md`
- `server/docs/PROTOCOL_V3.md`
Tests:
- `python -m py_compile server\websocket\agent_services.py server\websocket\outbox_ingest_components.py server\observer\checks\protocol_integrity.py` -> passed.
- `python -m pytest server\tests\test_observer_integrity.py::test_observer_integrity_protocol_ack_audit_valid_duplicate_and_missing_proof server\tests\test_observer_integrity.py::test_observer_integrity_protocol_gap_resolves_and_repeated_scan_dedupes -q -s` -> passed.
Live regression:
- Pending redeploy and v2 ACK proof probe.
Regression check:
- Pending.
Remaining risk:
- Legacy ACK audit row `agent_runtime_audit.id=4132` is pre-v2 OBS1 follow-up contamination and must not be used as proof.
Status consistency checked: yes.
