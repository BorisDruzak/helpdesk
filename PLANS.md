# Web-First Product Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Status:** planning document, 2026-06-17.

**Goal:** stabilize the web-first requester model before broad live validation on Windows/Linux VM agents.

**Architecture:** `/app/requester` is the canonical requester workspace. The server resolves account -> Registry profile -> primary active agent/binding and stores immutable ticket context; browser host and local GUI agent are never implicit diagnostic targets. Customer History and Observer become separate role-safe projections over product and technical events, not replacements for ticket state.

**Tech Stack:** Python server/web API, Registry/tickets/Knowledge/Observer modules, React webapp, Qt/Windows/Linux agent surfaces, pytest, pnpm test suites, browser evidence for web flows, UIA evidence for native GUI flows.

This file intentionally replaces the previous active PA/agent release plan. Historical release evidence remains in artifacts and git history; the active plan below is the new web-first product contract, ticket context, customer history, Observer coverage, and preparation gate.

---

## Goal

Prepare the product for broad live validation after the architecture shift:

- from agent-first ticket creation to web-first requester cabinet;
- from device-centered context to person/profile/primary-agent context;
- from ticket-only context to LLM-ready Customer History;
- from execution-only Observer to web-cabinet plus execution Observer.

Broad live testing must not start until Phases A-D are implemented, documented, and focused automated checks are green.

---

## Scope

In scope:

- Freeze the web-first requester contract in docs and tests.
- Make ticket context mandatory for new web requester tickets.
- Add Customer History projections and LLM context preview without real LLM execution.
- Extend Observer with web-cabinet events and web-first integrity checks.
- Prepare the test data and entry gate for later VM live testing.

Out of scope for this plan:

- Real LLM execution or automatic AI answers.
- Full AD/SSO integration.
- Automatic self-service device rebinding.
- Generic CMDB/database constructor.
- Support workspace redesign.
- Production rollout.
- Broad Windows/Linux VM live matrix before this plan's preparation gate passes.

---

## Core Invariant

```text
Normal requester ticket:
creator_person_id == affected_person_id
diagnostic target = creator primary active agent, if available

On-behalf requester ticket:
creator_person_id != affected_person_id
diagnostic target = affected person's primary active agent, if available

Missing/offline/ambiguous primary agent:
record evidence and route/manual-triage as policy says
do not fall back to the creator's browser PC or current GUI agent
```

---

## Locked Product Terms

Use these user-facing Russian terms in normal requester/agent UI:

- `Аккаунт` - login/password/session.
- `Профиль` - Registry-backed person details.
- `Устройство` - PC/agent.
- `Привязка устройства` - relationship between person and device.
- `Основное устройство` - primary active agent/PC.
- `Кабинет пользователя` - main requester workspace.
- `Обращение` - ticket/request.
- `Сотрудник, у которого проблема` - affected person.
- `Устройство для диагностики` - server-resolved target device.

Forbidden in normal requester UI:

- `pairing`
- `binding`
- `claim`
- `session`
- `registry person`
- raw UUID
- `*_id`
- raw backend enum
- raw policy code
- raw trace id

Allowed only in admin/debug/test/server DTO surfaces.

---

## Locked Decisions

### Account, Profile, Device

- Account is login/password/session.
- Profile is RegistryPerson with name, department, location, contact and work context.
- Device is an agent-connected PC.
- Binding links profile/person to device.
- Primary agent is the server-resolved technical diagnostic target.

### Web Cabinet

- `/app/requester` is the primary requester workspace.
- It is account/person-centered, not browser-device-centered.
- The current browser host must not determine ticket diagnostic target.

### GUI Agent

GUI Agent may:

- show connection status;
- show pairing/link code;
- open web cabinet;
- confirm local bound-user login;
- provide local setup/status actions.

GUI Agent must not:

- own profile lifecycle;
- silently rebind device on login;
- create normal requester tickets as the preferred path;
- bypass web profile completion policy;
- run diagnostics for another person unless the server target resolver says so.

### Profile Completion

- `PROFILE_COMPLETION_REQUIRED=true` blocks normal requester ticket create and preview.
- Allowed while incomplete: profile setup, device-link status view, logout, emergency form only when availability policy allows it.
- Normal forms must return `REQUESTER_PROFILE_INCOMPLETE` until required fields are complete.
- First rollout required fields: `full_name`, `department_id`, `location_id`, `phone` or `internal_extension`.

### Device Linking

- Device link request from web cabinet creates a pending claim/request.
- Admin approval remains default.
- First-device auto-approval is out of scope unless explicitly added behind policy.
- Requester cannot self-rebind ownership.

### On-Behalf Tickets

- On-behalf is allowed only by request form policy.
- Requester sees affected-person selector only when the form allows it.
- Affected-person context may influence routing, diagnostics, and support context.
- Affected-person context must not expand requester Knowledge audience.

---

## Current State

- Target repository: `C:\Users\admin-2\CodexProjects\pc_client`.
- Current active commit at planning time: `0b2ed284871d9bee928c171ec4c9dd7d0f7405b1`.
- The requested active work supersedes the previous `Primary Agent, GUI Login and On-Behalf Ticket Context` plan.
- This is a preparation plan only. No broad live product validation is claimed by this document.
- The working tree may contain unrelated artifact/config changes from prior sessions; do not revert them while implementing this plan.
- Phase A contract freeze completed locally on 2026-06-17 at `0b2ed284871d9bee928c171ec4c9dd7d0f7405b1`.
- Phase B ticket-context slice is implemented and validated locally: canonical `ticket_context_v1` helpers, requester-safe preview context, nested diagnostic-target precedence and `ticket_context_resolved` event are in place.
- Phase C Customer History v1 slice is implemented and focused validation is green locally: role-safe ticket/person history endpoints, requester-safe ticket history, support ticket detail compact history, redacted deterministic LLM preview, on-behalf creator/affected projections, chat/ObserverTrace adapters, time-window filters, related-history context packs and focused tests are in place. Phase D web-cabinet Observer events remain open.

---

## File Map

### Documentation

- Modify: `docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md`
- Modify: `docs/TESTING_RULES.md`
- Modify: `docs/LIVE_TESTING_DEBUG_RULES.md`
- Modify: `docs/QUICK_LOOKUP.md`
- Modify: `PLANS.md`
- Modify: `server/docs/TICKET_SYSTEM.md`
- Modify: `server/docs/CODEMAP.md`
- Modify: `server/docs/OBSERVER_LAYER.md`
- Modify: `server/docs/REGISTRATION_ACCOUNT_SESSIONS.md`
- Modify: `server/docs/KNOWLEDGE_PLATFORM.md`

### Existing Server Areas

- Modify: `server/requester/identity_service.py`
- Modify: `server/web_api/requester_handlers.py`
- Modify: `server/web_api/support_handlers.py`
- Modify: `server/web_api/dto/support.py`
- Modify: `server/registry/primary_agent_resolver.py`
- Modify: `server/registry/account_session_service.py`
- Modify: `server/registry/browser_pairing_service.py`
- Modify: `server/registry/effective_identity_service.py`
- Modify: `server/tickets/ticket_context.py`
- Modify: `server/tickets/diagnostic_target.py`
- Modify: `server/tickets/create_flow.py`
- Modify: `server/tickets/form_catalog.py`
- Modify: `server/tickets/requester_timeline.py`
- Modify: `server/observer/service.py`
- Modify: `server/observer/runtime.py`
- Modify: `server/observer/checks/*`

### New Server Areas

- Create: `server/customer_history/__init__.py`
- Create: `server/customer_history/models.py`
- Create: `server/customer_history/sources.py`
- Create: `server/customer_history/projection_service.py`
- Create: `server/customer_history/redaction.py`
- Create: `server/customer_history/context_builder.py`
- Create: `server/customer_history/retention.py`
- Create: `server/customer_history/handlers.py`
- Create: `server/customer_history/dto.py`

**Status 2026-06-17:** module structure created locally.
- Create: `server/observer/web_event_writer.py`

### Webapp

- Modify: `webapp/src/pages/requester/index.tsx`
- Modify: `webapp/src/features/requester/api.ts`
- Modify: `webapp/src/features/requester/types.ts`
- Modify: `webapp/src/pages/device-pairing/index.tsx`
- Modify: `webapp/src/features/admin/registry/*`
- Modify: `webapp/src/pages/admin/registry-page.tsx`
- Modify: `webapp/src/features/queues/api.ts`
- Modify: `webapp/src/pages/tickets/detail-page.tsx`
- Modify: `webapp/src/pages/admin/observer/*`
- Modify: `webapp/src/features/admin/*`

### Agent

- Modify: `pc_agent/ui_gui/account_gate.py`
- Modify: `pc_agent/ui_gui/main_window.py`
- Modify: `pc_agent/ui_gui/server_api.py`

### Tests and Guards

- Modify: `scripts/test_web_first_registration_localization.py`
- Add or modify: `server/tests/test_ticket_context*.py`
- Add or modify: `server/tests/test_requester_workspace_api.py`
- Add or modify: `server/tests/test_web_support_api.py`
- Create: `server/tests/test_customer_history_projection.py`
- Create: `server/tests/test_customer_history_redaction.py`
- Create: `server/tests/test_customer_history_context_builder.py`
- Create: `server/tests/test_observer_web_cabinet*.py`

---

## Phase A: Freeze Web-First Contract

### Task A1: Documentation Contract

**Files:**

- Modify: `docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md`
- Modify: `server/docs/TICKET_SYSTEM.md`
- Modify: `docs/LIVE_TESTING_DEBUG_RULES.md`
- Modify: `docs/TESTING_RULES.md`
- Modify: `docs/QUICK_LOOKUP.md`
- Modify: `server/docs/CODEMAP.md`
- Modify: `PLANS.md`

**Steps:**

- [x] Document account/profile/device/binding/primary-agent as separate concepts.
- [x] Document `/app/requester` as canonical requester workspace.
- [x] Document browser host non-target rule.
- [x] Document GUI Agent limited role.
- [x] Document profile completion gate and emergency bypass boundary.
- [x] Document on-behalf visibility/access rule.
- [x] Link this contract from `PLANS.md` and `docs/QUICK_LOOKUP.md`.

### Task A2: Static UI Terminology Guard

**Files:**

- Modify: `scripts/test_web_first_registration_localization.py`

**Guard forbidden normal UI terms:**

- `affected_person_id`
- `target_device_id`
- `binding_id`
- `claim_id`
- `pairing_id`
- `registry person`
- `account_session_id`
- `diagnostic_target_source`
- `trace_id`
- `operation_id`

**Allowlist:**

- admin/debug/test files;
- server DTO/type files;
- Observer/debug surfaces.

**Steps:**

- [x] Add path-aware allowlist for admin/debug/test/server DTO areas.
- [x] Scan normal requester and agent UI source files.
- [x] Fail with file/line/term output.
- [x] Add at least one fixture/assertion proving normal requester UI is guarded.

### Task A3: Route Contract Map

Document each route with purpose, allowed roles, canonical proof surface, critical API calls, expected Observer/audit events, and forbidden sensitive data:

- `/app/register`
- `/app/login`
- `/app/requester`
- `/app/requester/profile/setup`
- `/app/requester/profile`
- `/app/requester/devices`
- `/app/device/pair`
- `/app/device/register`
- `/app/device/login`
- `/app/admin/registry`
- `/app/tickets`
- `/app/admin/observer`

Status: completed 2026-06-17 in `docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md`; guarded by `scripts/test_web_first_registration_localization.py::test_phase_a_route_contract_map_documents_required_fields`.

### Phase A Acceptance

- [x] Contract docs explicitly distinguish account/profile/device/binding/primary-agent.
- [x] `/app/requester` is documented as canonical requester workspace.
- [x] Browser host cannot be interpreted as diagnostic target in docs/tests.
- [x] GUI Agent is documented as local setup/status/linking tool.
- [x] Raw internal identifiers are forbidden in normal requester UI.
- [x] Live testing rules require browser evidence for web-first requester flows.
- [x] `docs/QUICK_LOOKUP.md` points future Codex sessions to the correct files.

### Phase A Validation

Run:

```powershell
python scripts/verify_workspace.py
python scripts/test_web_first_registration_localization.py
python -m pytest server/tests/test_config_feature_flags.py -vv
pnpm --dir webapp run test -- requester
```

Expected:

- docs and static guards are green;
- no runtime/product behavior is claimed live-validated.

Completed 2026-06-17:

- `python scripts/test_web_first_registration_localization.py -q --tb=short` -> 7 passed.
- `python -m pytest scripts/test_web_first_registration_localization.py -q --tb=short` -> 7 passed.
- `python -m pytest server/tests/test_config_feature_flags.py -vv --tb=short` -> 4 passed.
- `python scripts/bootstrap_web_toolchain.py` -> web toolchain ready.
- `pnpm --dir webapp run test -- requester` -> 4 files / 38 tests passed.
- `python -m pytest pc_agent/tests/test_main_window_update_status.py -q --tb=short` -> 3 passed.
- `python -m pytest pc_agent/tests/test_ui_api_server_shutdown.py pc_agent/tests/test_runtime_logging.py -q --tb=short` -> 13 passed.
- `python scripts/verify_workspace.py` -> passed after updating agent routing metadata.

Notes:

- No broad live product validation is claimed for Phase A.
- The only runtime-source cleanup in this phase is requester/agent UI terminology hygiene: agent update status keeps internal operation ids in state but no longer renders them in visible status text.

---

## Phase B: Make Ticket Context Mandatory

### Goal

Every ticket created through the web-first requester model carries a server-owned immutable `ticket_context_v1` snapshot.

### Required Context Shape

Canonical schema belongs in `server/tickets/ticket_context.py` and `server/docs/TICKET_SYSTEM.md`.

Required top-level sections:

- `schema`
- `created_at`
- `creator`
- `affected`
- `on_behalf`
- `requester_context`
- `diagnostic_target`
- `form`
- `policy_refs`
- `redaction`

Required flat aliases in `custom_fields`:

- `custom_fields.ticket_context.schema`
- `custom_fields.creator_person_id`
- `custom_fields.affected_person_id`
- `custom_fields.created_on_behalf`
- `custom_fields.target_device_id`
- `custom_fields.target_binding_id`
- `custom_fields.target_agent_status`
- `custom_fields.diagnostic_target_source`
- `custom_fields.requester_context_snapshot`
- `custom_fields.requester_department_id`
- `custom_fields.requester_location_id`
- `custom_fields.requester_device_id`
- `custom_fields.requester_asset_id`
- `custom_fields.requester_binding_id`
- `custom_fields.requester_account_mode`

### Task B1: Schema Helpers

**Files:**

- Modify: `server/tickets/ticket_context.py`
- Modify: `server/tickets/diagnostic_target.py`
- Modify: `server/tickets/create_flow.py`
- Modify: `server/web_api/requester_handlers.py`

**Required functions:**

- `build_ticket_context_v1` - accepts resolved creator, affected person, requester context, diagnostic target, form, and policy refs.
- `validate_ticket_context_v1` - accepts a context mapping and returns typed validation errors for missing/invalid required fields.
- `project_requester_ticket_context` - accepts a context mapping plus actor context and returns a requester-safe projection.
- `project_support_ticket_context` - accepts a context mapping plus actor context and returns support-visible context.
- `resolve_diagnostic_target_from_ticket_context` - accepts a ticket/custom_fields object and returns target device, source, status, and evidence.
- `redact_ticket_context_for_requester` - removes ids, policy refs, trace refs, and internal diagnostic source fields.
- `redact_ticket_context_for_history` - returns the compact support/LLM-safe fields needed by Customer History.

**Steps:**

- [x] Write failing tests for normal requester context creation.
- [x] Write failing tests for on-behalf context creation.
- [x] Add schema builder with strict required fields.
- [x] Add validation that rejects missing schema/creator/affected/diagnostic sections.
- [x] Add requester and support projection helpers.
- [x] Preserve legacy aliases for existing readers.

### Task B2: Requester Preview Contract

**Endpoint:** `POST /api/web/requester/tickets/preview`

**Requirements:**

- [x] Resolve web account to RegistryPerson.
- [x] Enforce profile completion unless availability policy bypasses it.
- [x] Resolve selected/primary binding when needed.
- [x] Resolve service catalog/request template/form schema.
- [x] Resolve on-behalf policy if selected.
- [x] Compute target device.
- [x] Return requester-safe context explanation.
- [x] Never trust browser-supplied person/device/binding ids as authoritative.
- [x] Never create DB ticket.

### Task B3: Requester Create Contract

**Endpoint:** `POST /api/web/requester/tickets`

**Requirements:**

- [x] Recompute everything server-side.
- [x] Reject stale/forged context hints.
- [x] Store immutable context snapshot.
- [x] Store request form snapshot.
- [x] Store policy source snapshot.
- [x] Write initial ticket event.
- [ ] Write Customer History event.
- [ ] Write Observer/audit event.
- [x] Trigger routing/SLA/diagnostic policy using the target from ticket context.

### Task B4: Legacy/Agent Compatibility

**Rules:**

- [ ] If account session is present, resolve person/context when possible.
- [ ] If only agent token is present, create compatibility ticket with limited context.
- [ ] Mark `requester_account_mode=agent_legacy_or_device_only`.
- [ ] Do not pretend profile is complete.

### Task B5: Diagnostic Target Resolver

**File:** `server/tickets/diagnostic_target.py`

Resolve target in this order:

1. `custom_fields.ticket_context.diagnostic_target.device_id`
2. `custom_fields.target_device_id`
3. legacy `ticket.device_id` only for old tickets without `ticket_context_v1`

If target is missing/offline/ambiguous:

- [x] Write `diagnostic_autorun_skipped` event.
- [x] Store manual triage evidence.
- [ ] Write Observer event.
- [x] Show support-visible target explanation.
- [x] Do not create `DeviceOutbox` command.

### Task B6: Support and Requester Projections

**Files:**

- Modify: `server/web_api/support_handlers.py`
- Modify: `server/web_api/dto/support.py`
- Modify: `webapp/src/features/queues/api.ts`
- Modify: `webapp/src/pages/tickets/detail-page.tsx`
- Modify: `webapp/src/pages/requester/index.tsx`

Requester-safe projection shows:

- request status;
- request form summary;
- selected service/offering;
- public chat;
- requester-visible timeline;
- primary device label only if safe;
- profile/context explanation in user terms.

Requester-safe projection must not show:

- `creator_person_id`
- `affected_person_id`
- `target_device_id`
- `binding_id`
- `trace_id`
- `operation_id`
- raw policy refs
- raw `diagnostic_target_source`

Support projection shows:

- creator;
- affected person;
- `created_on_behalf`;
- on-behalf reason;
- diagnostic target device;
- diagnostic source/status;
- missing/offline/ambiguous evidence;
- request form context;
- SLA/routing/policy explanation;
- Observer summary link.

### Task B7: Context Consistency Event

On ticket create write:

```text
event_type=ticket_context_resolved
visibility=internal/support
```

Payload includes:

- schema;
- `created_on_behalf`;
- `diagnostic_target_source`;
- `target_available`;
- evidence codes;
- policy sources.

Requester projection hides this raw event or converts it to a safe user-facing message.

**Status 2026-06-17:** implemented locally. `create_flow.py` writes `ticket_context_resolved` after storing the server-owned snapshot; requester preview receives only the safe projection, not this raw event.

### Phase B Acceptance

- [x] Every new web-created ticket has `ticket_context_v1`.
- [x] Normal requester ticket has creator=affected.
- [x] On-behalf ticket has creator!=affected and reason when required.
- [x] Diagnostics never target creator/current browser PC for on-behalf unless affected user is actually the creator.
- [x] Missing/offline/ambiguous primary agent creates evidence, not wrong dispatch.
- [x] Support UI exposes context clearly.
- [x] Requester UI does not expose raw ids/policy/trace fields.
- [x] Legacy tickets remain readable.

### Phase B Validation

Run:

```powershell
python scripts/verify_workspace.py
python -m pytest server/tests/test_requester_workspace_api.py -vv --durations=80
python -m pytest server/tests/test_web_support_api.py -vv --durations=80
python -m pytest server/tests/test_ticket_context*.py -vv --durations=80
pnpm --dir webapp run test -- requester
pnpm --dir webapp run test -- tickets
```

**Validation checkpoint 2026-06-17:**

- `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_ticket_context_builder.py -q --tb=short` - passed, 9 tests.
- `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_requester_workspace_api.py::test_requester_can_create_no_device_ticket_and_preview_without_device server/tests/test_requester_workspace_api.py::test_requester_preview_ticket_accepts_catalog_form_payload server/tests/test_requester_workspace_api.py::test_requester_on_behalf_create_stores_authorized_ticket_context -q --tb=short` - passed, 3 tests.
- `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_web_support_api.py::test_web_support_tool_action_uses_ticket_context_target_device server/tests/test_tools_run_device_binding.py::test_ticket_device_match_guard_uses_ticket_context_target -q --tb=short` - passed, 2 tests.
- `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_ticket_context_builder.py -vv --durations=80 --tb=short` - passed, 9 tests. The literal `server/tests/test_ticket_context*.py` command from this plan is not expanded by PowerShell, so the concrete file path was used.
- `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_requester_workspace_api.py -vv --durations=80 --tb=short` - passed, 31 tests.
- `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_web_support_api.py -vv --durations=80 --tb=short` - passed, 70 tests.
- `pnpm --dir webapp run test -- requester` - passed, 4 files / 38 tests.
- `pnpm --dir webapp run test -- tickets` - passed, 7 files / 69 tests.
- `python scripts/test_web_first_registration_localization.py -q --tb=short` - passed, 7 tests.
- Note: DB-backed pytest commands were run sequentially with `PC_CLIENT_ALLOW_SHARED_TEST_DB=1`; parallel shared-DB pytest runs intentionally conflict with the project cleanup fixture.

Required scenarios:

- [x] B-TC-01 normal requester preview builds server-owned context.
- [x] B-TC-02 normal requester create stores `ticket_context_v1`.
- [x] B-TC-03 incomplete profile blocks normal create.
- [x] B-TC-04 emergency form bypass stores manual-triage evidence.
- [x] B-TC-05 on-behalf allowed: affected primary agent selected.
- [x] B-TC-06 on-behalf forbidden: affected selection rejected.
- [x] B-TC-07 no primary agent: no `DeviceOutbox` command, evidence stored.
- [x] B-TC-08 forged `target_device_id` ignored.
- [x] B-TC-09 requester projection redacts internal ids.
- [x] B-TC-10 support projection shows creator/affected/target.

---

## Phase C: Unified Customer History

### Goal

Create a unified, role-safe Customer History read model that can later feed LLM context. It is not the ticket timeline and not Observer.

Customer History answers:

- What happened with this requester/person/device across the product?
- What did the user try before ticket creation?
- What Knowledge articles were suggested/viewed?
- What tickets did they create?
- What devices are bound to them?
- What diagnostics were run?
- What SLA/closure/reopen/feedback history exists?
- What should support know before answering?
- What context can safely be sent to LLM?

### Design Rules

- Customer History is a product read model.
- It may read tickets, ticket events, feedback, reopen events, Knowledge attempts, Registry, bindings, sessions, registration claims, operations, Observer summaries, SLA/OLA events and artifact metadata.
- It must not expose raw source rows directly.
- Every history item has visibility flags for requester/support/admin/LLM.
- Redaction is part of v1, not a future patch.
- Full support timeline is rich and filterable.
- LLM context pack is compact, bounded, redacted and deterministic.

### Task C1: Module Structure

**Files:**

- Create: `server/customer_history/__init__.py`
- Create: `server/customer_history/models.py`
- Create: `server/customer_history/sources.py`
- Create: `server/customer_history/projection_service.py`
- Create: `server/customer_history/redaction.py`
- Create: `server/customer_history/context_builder.py`
- Create: `server/customer_history/retention.py`
- Create: `server/customer_history/handlers.py`
- Create: `server/customer_history/dto.py`

### Task C2: Source Adapters

Implement adapters returning normalized `CustomerHistoryEvent`:

- [x] `TicketHistorySource`
- [x] `RegistryHistorySource`
- [x] `KnowledgeHistorySource`
- [x] `DiagnosticHistorySource`
- [x] `ObserverHistorySource`
- [x] `SlaHistorySource`
- [x] `ChatHistorySource`

V1 event groups:

- Registry/profile: account/profile/device-link/session events.
- Tickets: preview/create/context/status/routing/SLA/resolve/close/reopen/feedback.
- Chat: public requester/support messages, attachments, confirmations.
- Knowledge: suggested/viewed/helpful/not helpful/deflected/ask used/ticket created after view.
- Diagnostics/modules: autorun/tool/module/playbook compact summaries.
- Observer: compact trace/status/error summaries.
- SLA/OLA: started/paused/warning/breached/stopped.

### Task C3: Redaction Layer

Implement:

- `redact_for_requester(history_event)`
- `redact_for_support(history_event)`
- `redact_for_admin(history_event)`
- `redact_for_llm(history_event, mode)`

Must remove:

- password;
- token;
- cookie;
- session;
- authorization;
- raw headers;
- raw `metadata_json`;
- access code;
- pairing code/hash;
- private/internal notes by default;
- raw trace/span attrs;
- large attachments.

**Status 2026-06-17:** `server/customer_history/redaction.py` implements recursive requester/support/admin/LLM projection redaction and filters requester/LLM Knowledge attempts by both audience and visibility scope so affected-only on-behalf Knowledge does not enter creator LLM preview context.

### Task C4: Context Builder

Implement:

- `build_ticket_context_pack(ticket_id, actor_context, mode)`
- `build_person_history(person_id, actor_context, filters)`
- `build_requester_history(actor_context)`

Builder requirements:

- [x] Sort events by output mode.
- [x] Deduplicate same source events.
- [x] Limit by count and time window.
- [x] Include current ticket first.
- [x] Include related recent history second.
- [x] Include Knowledge and diagnostics compactly.
- [x] Include redaction report.
- [x] Do not call any LLM API.

**Status 2026-06-17:** `CustomerHistoryContextBuilder.build_ticket_context_pack()` returns deterministic `preview_only` packs with no LLM API call, keeps the current ticket first, appends related recent person history second and aggregates redaction/source metadata. Person/ticket history supports count and `since` / `window_days` filtering.

### Task C5: API Endpoints

Add support/admin endpoints first:

- `GET /api/web/support/people/{person_id}/history`
- `GET /api/web/support/tickets/{ticket_id}/history`
- `GET /api/web/support/tickets/{ticket_id}/context-pack`
- `POST /api/web/support/tickets/{ticket_id}/llm-context/preview`

Add requester-safe endpoints:

- `GET /api/web/requester/history`
- `GET /api/web/requester/tickets/{ticket_id}/history`

Add admin endpoint:

- `GET /api/web/admin/history/search`

**Status 2026-06-17:** all Phase C routes above are registered in `server/routes.py`; support ticket routes use existing support ticket access checks, requester ticket history uses `RequesterIdentityResolver.get_ticket()`.

### Task C6: Minimal UI Placeholder

**File:** `webapp/src/pages/tickets/detail-page.tsx`

Add support ticket detail sections:

- `История клиента` - compact latest 10 events.
- `Контекст для ассистента - preview` - compact redacted context pack.

Do not build a large new UI in this phase.

**Status 2026-06-17:** `/app/tickets/:ticketId` history tab renders compact `История клиента` and `Контекст для ассистента - preview` sections from support detail payload.

### Phase C Acceptance

- [x] Support can request customer history for a ticket/person.
- [x] LLM context preview returns compact redacted data.
- [x] Requester endpoint cannot see support-only/admin-only events.
- [x] Knowledge attempts respect audience/visibility scope.
- [x] On-behalf affected context does not leak restricted KB to creator.
- [x] Raw ids/secrets/session data are absent from LLM context preview.
- [x] History links to ticket/observer/operation only through safe refs.

### Phase C Validation

Run:

```powershell
python scripts/verify_workspace.py
python -m pytest server/tests/test_customer_history_projection.py -vv --durations=80
python -m pytest server/tests/test_customer_history_redaction.py -vv --durations=80
python -m pytest server/tests/test_customer_history_context_builder.py -vv --durations=80
python -m pytest server/tests/test_knowledge_feedback.py -vv --durations=80
python -m pytest server/tests/test_knowledge_suggestions.py -vv --durations=80
python -m pytest server/tests/test_web_support_api.py -vv --durations=80
```

Required scenarios:

- [x] C-HIST-01 normal ticket appears in creator history.
- [x] C-HIST-02 on-behalf ticket appears for creator and affected with different projections.
- [x] C-HIST-03 requester cannot see support-only/internal events.
- [x] C-HIST-04 support sees compact diagnostic/Observer summary.
- [x] C-HIST-05 Knowledge attempts included with visibility/audience scopes.
- [x] C-HIST-06 restricted KB does not leak into creator LLM context.
- [x] C-HIST-07 secrets/tokens/session/cookies are redacted.
- [x] C-HIST-08 raw trace/span attrs are excluded from LLM context.
- [x] C-HIST-09 context pack is bounded and deterministic.
- [x] C-HIST-10 no current LLM API call is made; preview only.

Partial validation checkpoint 2026-06-17:

- `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_customer_history_projection.py -q --tb=short; python -m pytest server/tests/test_customer_history_context_builder.py -q --tb=short; python -m pytest server/tests/test_customer_history_redaction.py -q --tb=short` - passed sequentially, 3 + 4 + 1 tests. Covers C-HIST-02, C-HIST-04, C-HIST-06, time-window filtering and related-history ordering.
- `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_feedback.py -q --tb=short; python -m pytest server/tests/test_knowledge_suggestions.py -q --tb=short; python -m pytest server/tests/test_web_support_api.py -vv --durations=20 --tb=short` - passed sequentially, 4 + 8 + 70 tests.
- `pnpm --dir webapp run test -- tickets` - passed, 7 files / 69 tests.
- `python scripts/test_web_first_registration_localization.py -q --tb=short` - passed, 7 tests.
- `python scripts/verify_workspace.py` - passed.
- `git diff --check` - passed with existing CRLF normalization warnings only.
- `python -m pytest server/tests/test_customer_history_redaction.py -q --tb=short` - passed, 1 test.
- `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_customer_history_context_builder.py -q --tb=short` - passed, 1 test.
- `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_customer_history_projection.py -q --tb=short` - passed, 1 test.
- `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_customer_history_redaction.py server/tests/test_customer_history_projection.py server/tests/test_customer_history_context_builder.py -q --tb=short` - passed, 3 tests.
- `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_feedback.py -q --tb=short` - passed, 4 tests.
- `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_suggestions.py -q --tb=short` - passed, 8 tests.
- `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_web_support_api.py -vv --durations=20 --tb=short` - passed, 70 tests in 7:43.
- `pnpm --dir webapp run test -- tickets` - passed, 7 files / 69 tests.
- `python scripts/test_web_first_registration_localization.py -q --tb=short` - passed, 7 tests.
- `python scripts/verify_workspace.py` - passed.
- `git diff --check` - passed with existing CRLF normalization warnings only.
- The earlier combined Phase C pytest without `PC_CLIENT_ALLOW_SHARED_TEST_DB=1` timed out during DB-backed setup and was replaced by the documented sequential shared-DB pattern.
- The first quiet `test_web_support_api.py -q` run timed out at 7 minutes; the verbose rerun with a 15 minute timeout completed successfully.

---

## Phase D: Extend Observer Layer for Web Cabinet

### Goal

Observer must cover web-first critical flows while remaining a technical trace/integrity overlay, not a business-state source of truth.

It must help answer:

- Why could the requester not create a ticket?
- Was profile completion blocking correctly?
- Was device linking created/approved/rejected?
- Which account/session/person/device was resolved?
- Was ticket preview computed correctly?
- Was diagnostic target resolved correctly?
- Did Knowledge suggestion fail because of access policy or search?
- Did SLA/routing run after web create?
- Was chat/closure confirmation delivered?

### Source and Root Kind Policy

Preferred balanced model:

- `root_kind=requester_web`
- `source=requester_ticket_create`, `requester_profile`, `requester_knowledge`, etc.

Standardize sources:

- `requester_web`
- `requester_profile`
- `requester_device_link`
- `requester_ticket_preview`
- `requester_ticket_create`
- `requester_knowledge`
- `requester_chat`
- `requester_closure`
- `web_form_runtime`
- `registry_binding`
- `account_session`

Use separate root kinds only when a flow needs independent trace search/debug.

### Task D1: Web Event Writer

**File:** `server/observer/web_event_writer.py`

Add `write_web_cabinet_observer_event` with these keyword arguments:

- `session`
- `source: str`
- `event_type: str`
- `severity: str`
- `route: str`
- `actor_context`
- `ticket_id: str | None = None`
- `device_id: str | None = None`
- `person_id: str | None = None`
- `result: str`
- `error_code: str | None = None`
- `payload: dict | None = None`

Writer rules:

- [ ] Reuse existing durable audit/event source if possible.
- [ ] Do not create a parallel Observer-only business table unless necessary.
- [ ] Redact sensitive payload fields before write.
- [ ] Include route/method/result/error/correlation fields.

### Task D2: Event Calls

Add Observer event calls to:

- `server/web_api/session_handlers.py`
- `server/web_api/requester_handlers.py`
- `server/web_api/registry_handlers.py`
- `server/registry/account_session_service.py`
- `server/registry/browser_pairing_service.py`
- `server/registry/registration_service.py`
- `server/tickets/create_flow.py`
- `server/tickets/ticket_context.py`
- `server/tickets/diagnostic_target.py`
- `server/knowledge/suggestion_service.py`
- `server/knowledge/ask_service.py`
- `server/tickets/workflow_service.py`
- `server/tickets/closure_policy.py`

Required event groups:

- Account/session: login/register/session/mismatch.
- Profile: bootstrap/incomplete/update/gate blocked.
- Device linking: lookup/request/approve/reject/transfer.
- Ticket preview/create: started/succeeded/blocked/created/failed/context/target.
- Knowledge: suggest/access/attempt/audience guard.
- SLA/routing/form runtime: form/routing/SLA/priority resolution.
- Chat/closure: message/support visibility/confirmation/reopen.

### Task D3: Integrity Checks

Add Observer checks for:

- [ ] `web_ticket_missing_ticket_context_v1:{ticket_id}` - critical.
- [ ] `diagnostic_target_creator_fallback_on_behalf:{ticket_id}` - critical.
- [ ] `forged_target_device_accepted:{ticket_id}` - critical.
- [ ] `profile_incomplete_normal_ticket_created:{ticket_id}` - high.
- [ ] `knowledge_audience_leak_on_behalf:{ticket_id}` - critical.
- [ ] `missing_customer_history_for_ticket:{ticket_id}` - medium.
- [ ] `missing_observer_event_for_web_ticket_create:{ticket_id}` - medium.

### Task D4: API and UI Projection

Extend:

- `GET /api/web/admin/observer/quick`
- `GET /api/web/admin/observer/integrity`
- `POST /api/web/admin/observer/integrity/scan`
- `GET /api/web/admin/observer/traces`
- `GET /api/web/admin/observer/traces/{trace_id}`
- `GET /api/web/support/tickets/{ticket_id}`

Support ticket detail must embed compact Observer status:

- health: `ok | warning | error | empty`;
- web flow: ticket create/profile gate/target resolution/Knowledge guard;
- latest error;
- integrity events;
- safe trace URL.

Admin Observer filters:

- `source=requester_ticket_create`
- `root_kind=requester_web`
- `ticket_id=<ticket-id>`
- `person_id=<person-id>`
- `device_id=<device-id>`
- `error_code=REQUESTER_PROFILE_INCOMPLETE`
- `event_type=diagnostic_target_missing`

### Task D5: Redaction

Observer writer must remove:

- `Authorization`
- `Cookie`
- `Set-Cookie`
- `password`
- `password_repeat`
- `token`
- `access_code`
- `pairing_code`
- `poll_secret`
- `session_token`
- raw request body
- raw response body
- email unless needed; prefer actor ref/hash
- phone unless explicitly support-safe

### Phase D Acceptance

- [ ] Web requester create/preview/profile/device-link actions generate Observer-visible events.
- [ ] Observer can search web-cabinet failures by route/error_code/ticket/person/device.
- [ ] Integrity scan detects missing ticket context.
- [ ] Integrity scan detects wrong diagnostic fallback.
- [ ] Integrity scan detects profile gate bypass.
- [ ] Integrity scan detects missing Customer History event.
- [ ] Support ticket detail shows compact Observer web-flow status.
- [ ] Observer does not leak tokens/secrets/raw payloads.
- [ ] Observer remains technical overlay, not ticket source of truth.

### Phase D Validation

Run:

```powershell
python scripts/verify_workspace.py
python -m pytest server/tests/test_observer_*.py -vv --durations=80
python -m pytest server/tests/test_requester_workspace_api.py -vv --durations=80
python -m pytest server/tests/test_web_support_api.py -vv --durations=80
python -m pytest server/tests/test_registration_api.py -vv --durations=80
pnpm --dir webapp run test -- observer
pnpm --dir webapp run test -- tickets
```

Required scenarios:

- [ ] D-OBS-01 profile incomplete block writes Observer event.
- [ ] D-OBS-02 ticket preview success writes Observer event.
- [ ] D-OBS-03 ticket create success writes Observer event.
- [ ] D-OBS-04 ticket context missing integrity checker raises critical event.
- [ ] D-OBS-05 on-behalf wrong-target checker detects invalid dispatch.
- [ ] D-OBS-06 Knowledge audience leak checker detects invalid item.
- [ ] D-OBS-07 Customer History missing checker raises event.
- [ ] D-OBS-08 support ticket detail embeds compact Observer status.
- [ ] D-OBS-09 admin Observer search filters requester web events.
- [ ] D-OBS-10 event payload redacts secrets/tokens/cookies/passwords.

---

## Phase E: Preparation Gate Before Broad Live Testing

### Goal

Create a strict entry gate before using two VM agents for broad live testing. This phase prepares environment and data; it does not execute the full live matrix.

### Target VM Agents

`lab-win-primary-agent`:

- OS: Windows.
- SSH available.
- Agent installed.
- Unique `device_id`.
- Bound to test requester A.
- Primary active binding.
- Module set snapshot collected.

`lab-lin-primary-agent`:

- OS: Linux.
- SSH available.
- Agent installed.
- Unique `device_id`.
- Bound to test requester B.
- Primary active binding.
- Module set snapshot collected.

### Required Test Users

- `admin_test`
- `support_test`
- `requester_a_completed_profile_windows_agent`
- `requester_b_completed_profile_linux_agent`
- `requester_c_incomplete_profile`
- `requester_d_no_primary_agent`
- `requester_e_same_department`
- `requester_f_restricted_department`

### Required KB Data

- public requester article;
- department-restricted article;
- support-only article;
- on-behalf help article;
- device-linking help article;
- PC offline/power failure article.

### Required Forms

- normal incident form;
- emergency no-profile/no-agent form;
- on-behalf-enabled form;
- on-behalf-disabled form;
- access/request form with approval if already supported;
- form with SLA policy;
- form with diagnostic policy.

### Broad Live Testing Entry Criteria

Do not start broad live testing until all are true:

- [ ] Contract docs updated and static guard green.
- [ ] Web-created tickets store `ticket_context_v1`.
- [ ] Customer History endpoints/context preview exist.
- [ ] Observer web-cabinet events exist.
- [ ] Observer integrity checks include web-first invariants.
- [ ] Support ticket detail shows creator/affected/target/Observer/history context.
- [ ] Requester UI does not show raw ids.
- [ ] Focused automated tests for Phases A-D are green.
- [ ] Test data pack exists.
- [ ] VM agents are uniquely registered and not contaminated by previous manual experiments.

### Later Broad Live Matrix

Run later only after the entry criteria are green:

- LIVE-0 Environment sanity: health, runtime snapshot, Observer status, agents online, bindings visible, no unexpected integrity events.
- LIVE-1 Web account/profile/device-link: register/login/profile/device-link/admin approve/history/Observer.
- LIVE-2 Ticket create and context: normal, emergency, on-behalf, no-primary-agent, forged target negative, support/requester projection.
- LIVE-3 Knowledge and history: suggestions, views, feedback, restricted KB negative, Customer History, LLM context preview.
- LIVE-4 SLA/routing/forms: preview, validation, routing, priority, SLA, queue display, Observer/history.
- LIVE-5 Diagnostics/modules: online/offline target, module available/missing, tool runs, DeviceOutbox target, Observer trace, history summary.
- LIVE-6 Chat/closure: requester/support messages, attachment if needed, resolve, confirmations, close, reopen, feedback, history/Observer.

### Live Bug Policy

For every bug discovered later:

- [ ] Record evidence before fix.
- [ ] Classify layer: contract, auth/account-session, requester web cabinet, registry/binding, ticket context, form/runtime policy, SLA/routing, Knowledge/access, diagnostics/module, Observer, history, browser UI, native GUI/UIA, or test contamination.
- [ ] Document root cause.
- [ ] Implement code/config fix.
- [ ] Add focused automated test.
- [ ] Rerun cleanly with new `run_id`.
- [ ] Label old contamination if relevant.

Use the template from `docs/LIVE_TESTING_DEBUG_RULES.md`.

---

## Recommended Commit Slices

### Commit 1: Contract Freeze

Message:

```text
docs: freeze web-first requester contract
```

Files:

- `docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md`
- `docs/TESTING_RULES.md`
- `docs/LIVE_TESTING_DEBUG_RULES.md`
- `docs/QUICK_LOOKUP.md`
- `server/docs/TICKET_SYSTEM.md`
- `server/docs/CODEMAP.md`
- `PLANS.md`
- `scripts/test_web_first_registration_localization.py`

### Commit 2: Ticket Context Hardening

Message:

```text
server: harden web requester ticket context contract
```

Files:

- `server/tickets/ticket_context.py`
- `server/tickets/diagnostic_target.py`
- `server/tickets/create_flow.py`
- `server/web_api/requester_handlers.py`
- `server/web_api/support_handlers.py`
- `server/web_api/dto/support.py`
- `server/tests/test_ticket_context*.py`
- `server/tests/test_requester_workspace_api.py`
- `webapp/src/pages/requester/index.tsx`
- `webapp/src/pages/tickets/detail-page.tsx`

### Commit 3: Customer History Projection

Message:

```text
server: add customer history context projection
```

Files:

- `server/customer_history/*`
- `server/web_api/history_handlers.py`
- `server/routes.py`
- `server/tests/test_customer_history_projection.py`
- `server/tests/test_customer_history_redaction.py`
- `server/tests/test_customer_history_context_builder.py`
- `webapp/src/pages/tickets/detail-page.tsx`

### Commit 4: Observer Web-Cabinet Coverage

Message:

```text
server: add observer coverage for web requester flows
```

Files:

- `server/observer/web_event_writer.py`
- `server/observer/service.py`
- `server/observer/runtime.py`
- `server/observer/checks/*`
- `server/web_api/requester_handlers.py`
- `server/web_api/registry_handlers.py`
- `server/web_api/session_handlers.py`
- `server/web_api/observer_handlers.py`
- `server/tests/test_observer_web_cabinet*.py`
- `webapp/src/pages/admin/observer/*`
- `webapp/src/pages/tickets/detail-page.tsx`

### Commit 5: Preparation Gate Docs

Message:

```text
docs: add web-first live validation preparation gate
```

Files:

- `PLANS.md`
- `docs/LIVE_TESTING_DEBUG_RULES.md`
- `docs/TESTING_RULES.md`
- `docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md`

---

## Final Definition of Ready for Broad Testing

Broad live testing may start only when all are true:

- [ ] Contract docs updated.
- [ ] Static UI terminology guard green.
- [ ] Web requester ticket create stores `ticket_context_v1`.
- [ ] Ticket context visible to support and redacted for requester.
- [ ] Diagnostic target resolver uses ticket_context before legacy `device_id`.
- [ ] Customer History projection exists.
- [ ] LLM context preview exists and is redacted.
- [ ] Observer web-cabinet event writer exists.
- [ ] Observer integrity checks cover web-first invariants.
- [ ] Support detail includes compact history, Observer, and context blocks.
- [ ] Test data pack for Windows/Linux VM agents is defined.
- [ ] Focused automated tests for Phases A-D are green.
- [ ] No broad live test has been marked green based only on API/DB without browser evidence.

---

## Handoff

- Phase A is complete locally.
- Phase B ticket context hardening is implemented and validation is green locally.
- Phase C Customer History is implemented and focused validation is green locally; continue with Phase D web-cabinet Observer event writing and integrity checks.
- Do not jump directly to broad live testing.
- Before implementation, verify current code and docs against `HEAD`; do not trust old completion text.
- Use browser evidence as canonical proof for requester web flows.
- Use UIA evidence only for native GUI flows.
- API tests support but do not replace browser evidence where the product surface is the browser.
- Keep `PLANS.md` as current state, not a chat log.
- After each major phase, update this file's checkboxes, validation commands, and any changed decisions.
