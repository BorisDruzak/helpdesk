# PLANS.md

## 2026-04-28 Admin Support SaaS Redesign And Playbook Module Entry

Status: in progress.

### Goal

Redesign the React support and admin workspaces into one dense SaaS-style operator UI, using the existing device inventory and playbook builder as the visual/functional baseline, without adding a new UI library.

### Constraints

- Work only in `C:\Users\admin-2\CodexProjects\pc_client`.
- Keep the existing React/Tailwind/component stack.
- Prefer typed `/api/web/*` contracts; add server aliases only when the current frontend cannot express a required workflow.
- Do not expose raw JSON as the normal operator configuration path. UI must use controlled fields and generate payloads for the existing JSON-backed APIs.
- Keep legacy `/admin?legacy=1` and `/support?legacy=1` as rollback escapes unless a separate cutover task explicitly removes them.

### Implementation Tracks

1. Add a shared schema-driven parameter editor for module/tool/playbook params:
   - render text, textarea, boolean, number, integer, select/radio-like enum and object/array fields from typed schema;
   - keep object/array JSON only as a bounded advanced field where the schema does not expose a safer shape;
   - expose generated params preview as read-only/debug context.
2. Make `/app/admin/playbooks` the true entry point for module command launch and setup:
   - group command catalog by module/source/platform/risk;
   - show install policy, preset, params, output contract and condition hints in one inspector;
   - replace `Params JSON` with controlled parameter controls from `params_schema`;
   - keep save payload compatible with `POST /api/web/admin/playbooks/save`.
3. Apply the same parameter editor to support ticket tool launches in `/app/tickets/:ticketId` and compatibility `/app/support`.
4. Replace settings JSON textareas with controlled builders where server payload already provides the catalog:
   - routing condition builder writes `condition_json`;
   - SLA business hours and calendars use day/time rows and holiday rows;
   - JSON remains only as read-only preview or advanced fallback if needed.
5. Tighten the shared SaaS shell:
   - compact topbar/sidebar, reduce decorative copy, keep accessible labels;
   - use existing `Button`, `Badge`, `Card`, `Tabs`, `Select`, `SearchField`;
   - no new UI library.
6. Verify:
   - focused Vitest for params editor/playbooks/support/settings;
   - `pnpm --dir webapp run build`;
   - focused server pytest if typed API changes;
   - `python scripts/verify_workspace.py`;
   - live remote smoke/browser check at `http://192.168.100.17:8666/admin`, then stop server.

### Current Notes

- Current live signoff shows `/app/admin/inventory` and `/app/tickets` working, but long tables and raw JSON fields need an operator-focused pass.
- Main raw JSON hotspots found in:
  - `webapp/src/features/playbooks/playbook-builder-panel.tsx`;
  - `webapp/src/features/modules/modules-panel.tsx`;
  - `webapp/src/pages/tickets/detail-page.tsx`;
  - `webapp/src/features/queues/support-workspace.tsx`;
  - `webapp/src/pages/settings/index.tsx`.
- First implementation slice starts with playbook/module command params because it directly supports fast launch and configuration of concrete modules.

### 2026-04-28 Second Wave: Ticket Control, Forms And Status Logic

Current focus:

1. Build one shared frontend presentation model for ticket statuses:
   - internal status stage and tone;
   - requester-facing status;
   - next-action owner;
   - waiting/evidence/terminal gates;
   - Russian labels without mojibake.
2. Apply that model in `/app/tickets`, ticket detail and compatibility support workspace so support sees the same status logic everywhere.
3. Improve ticket management controls:
   - make status transition intent clearer;
   - show who is expected to act next;
   - make evidence/resolution readiness visible before closure.
4. Improve `/app/admin/forms` as the request entry builder:
   - route preview stays functional;
   - playbook/module trigger readiness is visible;
   - no raw JSON as the normal operator path.
5. Align `/app/settings` ticket lifecycle display with the same status model and labels.
6. Verify with focused Vitest, webapp build, workspace verification and live browser checks on `http://192.168.100.17:8666/admin`.

Completed:

- Shared ticket status presentation helper now drives `/app/tickets`, ticket detail, support workspace and settings lifecycle badges.
- Ticket detail shows stage, next action owner, operator action and evidence gate.
- Forms builder shows playbook-trigger readiness and route preview no longer exposes condition JSON as the normal operator surface.

### 2026-04-28 Third Wave: Safer Ticket Status Actions

Current focus:

1. Replace immediate status mutation from the ticket detail select with a deliberate transition panel:
   - choose target status;
   - preview the target stage;
   - show evidence/passport guard before resolution;
   - apply through an explicit button.
2. Keep the server FSM/evidence validation authoritative; frontend only explains the next action.
3. Keep support/admin styling dense and operational.

Completed:

- Ticket detail now applies status transitions only through an explicit confirmation button.
- Forms builder shows the launch chain from request form to routing and playbook trigger.

### 2026-04-28 Fourth Wave: Ticket Automation Entry

Current focus:

1. Add typed support endpoints for ticket-bound playbook launch:
   - list published playbooks available from a ticket;
   - expose version id, required tools, blocks count and readiness;
   - start a selected playbook against the ticket device with `trigger_type=support_ticket`.
2. Add an `/app/tickets/:ticketId` automation panel:
   - show playbook readiness/preflight summary;
   - launch through an explicit `Запустить плейбук` action;
   - show recent operation context next to the launch surface.
3. Keep the existing module command launcher intact for typed params/presets while the new automation panel becomes the entry point for playbook runs.

Completed:

- Ticket-bound playbook launch is available from `/app/tickets/:ticketId` through typed support endpoints.
- Live staging check exposed a real lazy module install edge case: `network_basic@1.0.0` installed successfully, but the playbook failed before `run_tool` because the strict capability gate read a stale/no toolset snapshot.

### 2026-04-28 Fifth Wave: Live Playbook Run And Auto-Install Fix

Current focus:

1. Reproduce real playbook launch from a support ticket against an online Windows agent.
2. Verify module auto-install through server logs and observer trace/detail/bundle.
3. Fix stale snapshot gating after successful lazy install so the playbook proceeds to `run_tool`.
4. Re-deploy and repeat live playbook run with observer proof.

Completed:

- Added a regression test for successful lazy install with strict capability gate and stale/no snapshot.
- Updated playbook engine preflight so successful DB-backed module install/registry preflight is authoritative for the immediate command enqueue.

## 2026-04-27 Webapp Unification And API Boundary

Status: local implementation verified; remote/live signoff pending.

### Goal

Finish the new React web stack in three implementation tracks:

1. Split the current React bundle so large admin/support workspaces do not ship as one heavy chunk.
2. Move requester-facing `/help` and `/ticket` flows into React under `/app/help` and `/app/ticket/*`, keeping legacy escape routes during cutover.
3. Normalize React API calls behind typed `/api/web/*` boundaries where practical, starting with observer, notifications and module workbench calls.

### Plan

- Detailed implementation plan: `docs/superpowers/plans/2026-04-27-webapp-unification-and-api-boundary.md`.
- Phase 1: lazy route boundaries and nested admin panel splitting; verify `pnpm --dir webapp run test`, `pnpm --dir webapp run build`, and cutover preflight.
- Phase 2: requester API client, React `/app/help`, React requester ticket view, and controlled `/help`/`/ticket` cutover flags defaulting off.
- Phase 3: endpoint inventory and typed `/api/web/*` aliases for observer, notifications and modules workbench; migrate React clients without removing legacy endpoints.
- Phase 4: remote browser signoff and docs sync.

### 2026-04-27 Progress

- Done locally: React route-level lazy imports, public `/app/help`, public `/app/ticket` / `/app/ticket/:ticketId`, `/help` and `/ticket` cutover flags defaulting off, and typed web aliases for observer, notifications, module workbench and tech alerts.
- React no longer calls the migrated legacy admin/module/notification URLs directly; remaining non-`/api/web/*` calls are intentional public requester APIs or support/ticket runtime APIs that stay outside this pass.
- Verified locally with frontend tests/build, static-page handler tests, Python compile checks, and cutover preflight. Remote browser signoff and deploy remain next.

### Verification Target

- `python scripts/bootstrap_web_toolchain.py`
- `pnpm --dir webapp run test`
- `pnpm --dir webapp run build`
- `python -m pytest server/tests/test_static_pages_handlers.py -q`
- `python -m pytest server/tests/test_web_admin_api.py -q`
- `python scripts/check_webapp_cutover.py --json`
- `python scripts/verify_workspace.py`
- `pnpm --dir webapp run check:remote:webapp -- --base-url http://192.168.100.17:8666`

## 2026-04-27 Observer Coverage For Agent Auth, Update And Runtime

Status: in progress.

### Problem

- Agent authorization and runtime lifecycle already write `agent_runtime_audit` records, but the observer projection only picked those records up when they were linked to an operation or ticket.
- Manual provisioning, invalid-token handshakes and other auth-only failures have no operation, so `/api/admin/tech/observer/search`, diagnostics bundles and quick dangerous-flow summaries could miss the exact failing step.
- Agent updates are better covered because they have `operation.kind=agent_update`, but update runtime audit should stay attached to the same trace and visible in bundle/detail.

### Plan

1. Add first-class observer classification for runtime audit events:
   - `device_provisioning` for connection request create/approve/reject/token-delivery/token-limit/fingerprint issues;
   - `agent_auth` for invalid/revoked token and handshake auth failures;
   - `agent_runtime` for lifecycle/offline/superseded runtime events;
   - keep operation-backed `agent_update` traces authoritative for updates.
2. Project operation-less runtime audit records as synthetic observer traces so search, trace detail and diagnostics bundle can find them by event name, device id and root kind.
3. Treat warning-level auth/provisioning failures as observer signatures where they represent an actionable problem.
4. Include auth/provisioning/runtime trace kinds in hot-trace and dangerous-flow summaries.
5. Add regression tests for:
   - search by `connection_request` and `invalid_token`;
   - `root_kind=device_provisioning` trace search;
   - diagnostics bundle by auth/provisioning query;
   - quick dangerous-flow visibility.
6. Update observer docs, CODEMAP and QUICK_LOOKUP.

### Verification Target

- `python -m pytest server/tests/test_observer_diagnostics_api.py -q`
- `python -m pytest server/tests/test_observer_v2_api.py -q`
- `python -m pytest server/tests/test_connection_request_api.py -q`
- `python scripts/verify_workspace.py`
- Live Linux smoke + browser/API check at `http://192.168.100.17:8666/admin`.

## 2026-04-27 Observer Coverage Closure And Agent Telemetry Channel

Status: planned.

Detailed implementation and handoff plan:

- `docs/superpowers/plans/2026-04-27-observer-coverage-closure-agent-telemetry.md`

### Goal

Close the known observer blind spots so support operators and Codex can diagnose authorization, updates, module reconcile, playbook execution, web API failures and agent-side failures through one server-side observer surface.

### Core Decision

Add a narrow agent observer/telemetry channel, but do not create a second independent observer system inside the agent.

The agent may keep local `action_trace.jsonl` as its durable local black box, but important lifecycle/action events must be uploaded to the server as bounded, redacted telemetry and projected into the existing server observer tables. The server remains the canonical query surface for support UI, diagnostics bundles and Codex API access.

### Scope

Covered in this plan:

- server observer projection gaps;
- module reconcile and module auto-install failures;
- playbook run/step/preflight visibility;
- web auth/RBAC/API boundary failures;
- agent local black-box upload for crashes, startup, update launcher, WS reconnect and tool execution;
- observer runtime self-health.

Out of scope for this plan:

- replacing existing operations/ticket/device event contracts;
- making routing fully editable as arbitrary automation;
- streaming raw logs/tokens/screenshots without redaction and retention limits.

### Architecture

Use one canonical observer graph on the server:

- existing sources stay: `operations`, `ticket_events`, `device_events`, `agent_runtime_audit`;
- add server-side source rows for `playbook_step_run` and selected system flows;
- add bounded `agent_observer_events` or equivalent ingestion source for agent local telemetry;
- projector materializes all sources into `observer_traces`, `observer_spans`, signatures and degradations.

Agent-side telemetry should be batched, redacted, idempotent and best-effort:

- local append-only queue on agent;
- upload after successful auth/handshake or via existing WS/RPC channel;
- no raw token, password, cookie, consent token, or full command output by default;
- server accepts only known event schemas and applies retention/sampling.

### Implementation Plan

1. Inventory trace sources and define a coverage matrix:
   - rows: auth/provisioning, update, module reconcile, module live test, playbook, web auth, ticket routing, notification delivery, agent startup/crash, WS reconnect, tool execution;
   - columns: source table, root_kind, spans, signatures, UI entrypoint, Codex diagnostics bundle.
2. Add first-class projection for playbook runs:
   - `root_kind=playbook_run`;
   - spans for preflight, skipped decision/local steps, module install precheck, command dispatch, retry, result normalization and ticket fact attachment;
   - link each operation-backed step to its operation trace.
3. Make module reconcile observer-visible:
   - write `agent_runtime_audit` or a dedicated system audit record for desired-state install/remove failures before enqueue;
   - emit `root_kind=module_reconcile` or map to `module_install` / `module_remove` with `source=reconcile`;
   - produce signatures for missing package, platform mismatch, agent offline and enqueue failure.
4. Add web auth/API boundary observability:
   - record rate-limited audit events for repeated 401/403 on important `/api/web/*`, `/api/tickets*`, `/api/admin/*` paths;
   - group by route, actor role, error_code and session state;
   - expose in diagnostics bundle and admin observer.
5. Add agent observer telemetry ingestion:
   - define schema for `agent.startup`, `agent.shutdown`, `agent.crash_detected`, `agent.ws.reconnect`, `agent.update.launcher`, `agent.update.apply`, `agent.tool.step`, `agent.module.install_step`;
   - implement local agent queue using the existing action trace recorder as source;
   - upload compact batches with sequence/idempotency keys;
   - store server-side rows linked by `device_id`, `operation_id`, `trace_id`, `tool_name`, `module_name`.
6. Project agent telemetry into server observer:
   - attach telemetry events to operation traces when `operation_id`/`trace_id` exists;
   - create synthetic `agent_runtime` traces for startup/crash/reconnect events without an operation;
   - create signatures for repeated crash/update/reconnect/tool-step failures.
7. Add observer self-health:
   - expose projector backlog, last error and stale projection as a trace-visible system health event;
   - keep `/api/web/admin/observer/runtime` as quick status;
   - add diagnostics bundle recommendations when projection is lagging.
8. Update UI:
   - `/app/admin/observer` root_kind filters include playbook, module reconcile and web auth/API;
   - trace detail shows playbook step graph and agent telemetry spans;
   - ticket Automation overlay links to the exact failing playbook step trace.
9. Update API for Codex/support:
   - diagnostics bundle accepts `playbook_run_id`, `step_run_id`, `route`, `root_kind=web_auth`, `root_kind=module_reconcile`;
   - bundle includes recent server logs only as fallback, with a flag when no first-class trace exists.
10. Add tests and canaries:
   - unit tests for projection from every new source;
   - integration tests for playbook preflight fail, reconcile offline agent, repeated web auth failure, agent telemetry upload and projection;
   - live canary for Linux agent startup/tool/update telemetry;
   - Windows live agent telemetry canary when a Windows lab agent is available.

### Verification Target

- `python -m pytest server/tests/test_observer_diagnostics_api.py -q`
- `python -m pytest server/tests/test_observer_v2_api.py -q`
- `python -m pytest server/tests/test_playbook_scenarios_no_db.py -q`
- new tests for playbook observer projection, module reconcile observer projection, web auth observer audit and agent telemetry ingestion;
- targeted agent tests for telemetry queue/upload/redaction;
- `python scripts/verify_workspace.py`;
- browser check on `http://192.168.100.17:8666/app/admin/observer`;
- live Linux agent check for startup, reconnect and tool telemetry;
- optional Windows lab check before claiming Windows telemetry coverage.

### Handoff

Start from:

- `server/observer/service.py`
- `server/observer/runtime.py`
- `server/tech/handlers.py`
- `server/app/services/playbook_engine.py`
- `server/app/repos/playbook_repo.py`
- `server/modules/reconcile.py`
- `server/auth/middleware.py`
- `server/web_api/admin_handlers.py`
- `server/websocket/agent_handshake.py`
- `server/websocket/agent_handler.py`
- `pc_agent/core/action_trace.py`
- `pc_agent/core/orchestrator.py`
- `pc_agent/ws_agent.py`
- `pc_agent/ws_agent_runtime_helpers.py`
- `webapp/src/features/tech/*`
- `webapp/src/pages/admin/observer-page.tsx`
- `server/docs/OBSERVER_LAYER.md`
- `server/docs/OBSERVER_AUTHORING_RULES.md`
- `server/docs/CODEMAP.md`
- `pc_agent/docs/CODEMAP.md`
- `docs/QUICK_LOOKUP.md`

Design rule: every newly observed problem must answer three questions in the UI/API: what failed, at which exact step, and what source row/event proves it.

### 2026-04-28 Follow-up: Canary, Live Agent Checks And UX

Status: in progress.

Detailed follow-up plan:

- `docs/superpowers/plans/2026-04-28-observer-canary-live-agent-ux.md`

Current execution focus:

1. Extend the live observer canary suite so it verifies first-class traces for `module_reconcile`, `playbook_run`, `web_auth` and `observer_runtime`.
2. Add report-level coverage closure output in JSON and Markdown.
3. Verify the current agent release is present in the stable build registry for both `windows_amd64` and `linux_alt_x86_64`.
4. Improve `/app/admin/observer` trace detail UX with evidence-source and diagnostics-bundle counters.

## 2026-04-27 Connection Request Duplicate Approval Bug

Status: fixed locally; release verification in progress.

### Findings

- The observer layer did not expose this as a first-class provisioning trace; the useful facts came from `connection_requests`, `agent_tokens` and server runtime audit/logs.
- Real DB showed duplicate approved rows for the same `device_id` on `Sirius` and `AD-MAIN`.
- Root cause: while waiting for approval, the agent sends heartbeat `POST /api/connection_request`; if admin approval happens just before that heartbeat, the server no longer sees a `pending` row and created a fresh pending request.
- Secondary issue: old `set_approval_token` updated every approved row for the same device, so legacy duplicate approved rows could retain an undelivered approval token.

### Fix

- Manual provisioning now treats post-approval heartbeats as "already approved, waiting for token delivery" and does not create a second pending row.
- New approval tokens are stored only on the latest approved request.
- Status consumption marks all undelivered approved-token rows for the device as delivered, preventing legacy duplicate rows from returning a token more than once.

### Verification

- Added regression tests for the approval heartbeat race and legacy duplicate approval-token consumption.
- Ran focused server and agent connection-request tests successfully.

## 2026-04-27 Playbook Low-Code Canvas UI

Status: completed and verified on the Linux stand.

### Goal

Rebuild `/app/admin/playbooks` from a linear block list into a real low-code builder:

- module command palette on the left;
- draggable block canvas with a visible grid;
- module-like blocks that can be moved and edited;
- command selector inside each diagnostic block;
- selected-block inspector with presets, params, output contract and error handling;
- preview/result panel for the selected command contract;
- preserve the current server save contract and published playbook runtime.

### Implementation Notes

- Keep the existing typed API: `GET /api/web/admin/playbooks/catalog` and `POST /api/web/admin/playbooks/save`.
- Store canvas positions in client state for now; save order is derived by block position from top to bottom.
- Use native HTML drag/drop and pointer movement to avoid a new dependency.
- Keep remediation out of the builder; this pass is diagnostic-only.

### Verification

- Update the playbook panel unit test for drag/drop and command selection.
- Ran targeted playbook tests, webapp build, `verify_workspace.py`, release smoke, and a browser check on `http://192.168.100.17:8666/app/admin/playbooks`.
- Live browser check published smoke playbook `codex_canvas_smoke_1777297678971` after changing a block command, adding a decision block, dragging a block on the canvas, and saving successfully.

## 2026-04-27 Self-Healing Automation And Playbook Orchestration

Status: core implementation completed locally; observer drilldown and full ticket playbook runner remain next-stage work.

### Goal

Build self-healing automation around the existing module/tool runtime:

- modules remain installable containers;
- atomic playbook units are module commands/tools;
- playbooks orchestrate commands, conditions, install/preflight flows, retries and fact packages;
- support sees every step, including module install and infrastructure failures, with observer trace drilldown.

### Core Decisions

- Do not replace low-level system primitives with editable playbooks.
- Keep critical primitives in code: module preflight, module install, activate, sync toolset, verify tool, operation wait, agent online check, ticket fact attachment.
- Represent those primitives as protected/system playbook blocks in the UI so operators can see and tune allowed parameters without breaking bootstrap behavior.
- Playbook runtime should operate on tool/command manifests, not on module names directly.
- Module auto-install should happen at the module-owner level, but be visible as a step/sub-playbook result.
- Presets from tool manifests must be expanded into concrete params at save/run time; the agent should receive normal command params, not only `preset_id`.

### Target Model

1. A playbook step references an atomic command such as `system.collect` or `ip_address.get_ip`.
2. The server resolves the owning module for the command from the preferred server module registry.
3. Preflight reports:
   - command source: builtin, device snapshot, server registry;
   - owning module/version;
   - install state;
   - platform compatibility;
   - min agent version;
   - risk/consent requirements;
   - output schema and known error codes.
4. At execution time, the engine starts the next eligible step.
5. If the command owner module is missing on the agent, the engine runs a protected install flow before the command.
6. Install flow results become first-class step facts:
   - `already_installed`
   - `installed`
   - `module_not_on_server`
   - `platform_mismatch`
   - `agent_version_too_old`
   - `download_failed`
   - `activate_failed`
   - `toolset_sync_failed`
   - `install_timeout`
7. Decision blocks can branch on both command results and install/preflight results.
8. Final output is attached to the ticket as a structured fact package.

### UI Direction

- `/app/admin/playbooks` should use the real dynamic tool catalog, not a static list of three diagnostic blocks.
- Tool picker groups commands by module and shows:
  - tool name;
  - module/version;
  - source: agent/server/builtin;
  - install required;
  - supported platforms;
  - min agent version;
  - risk and consent;
  - presets and params schema;
  - output schema and error codes.
- Step inspector should provide:
  - preset selector;
  - generated params preview;
  - manual param overrides from `params_schema`;
  - retry/timeout/continue-on-error;
  - condition builder based on previous step output/error/status;
  - install policy: `lazy`, `preinstall`, `fail_if_missing`, `skip_if_missing`.
- Ticket UI should expose an Automation overlay/modal:
  - run one command;
  - run a playbook;
  - inspect preflight;
  - see progress by step;
  - open observer trace for the failed step.

### Observer Direction

Observer should be attached to playbook execution as a first-class execution graph:

- root trace: playbook run;
- spans:
  - preflight;
  - module install sub-flow;
  - command dispatch;
  - agent policy/consent;
  - module execution;
  - result normalization;
  - ticket fact attachment;
- every step has `playbook_run_id`, `step_key`, `operation_id`, `tool_name`, `module_name`, `trace_id`;
- UI can show exactly where the failure happened, not just "playbook failed".

### Routing Question

Ticket routing can be moved partly into this model, but not as fully free-form automation.

Recommended boundary:

- Keep the existing routing service as the authoritative deterministic engine.
- Add a visible protected routing playbook/view that shows routing as steps:
  - normalize form/request data;
  - match request kind;
  - match registry/service/location;
  - choose queue;
  - choose priority/SLA;
  - optional auto-assign;
  - write routing reason.
- Allow admins to edit routing rules through the existing safe rule model, while observer shows the step-by-step routing trace.
- Do not allow arbitrary remediation/action blocks inside routing until there is explicit approval/governance.

This gives transparency and observer drilldown without turning ticket routing into an unrestricted workflow engine.

### Implementation Plan

1. Add a playbook tool-catalog service that merges device snapshot tools and server registry tools.
2. Extend playbook manifest to v2 with required tools, install policy, output contract and preflight metadata.
3. Fix playbook runtime to use the existing module auto-install primitive before tool-backed steps.
4. Record install/preflight as explicit step runs or protected sub-step facts.
5. Fix actor role/auth context for playbook tool execution so diagnostic tools do not fail as `system`.
6. Expand presets into params for both command run and playbook step configuration.
7. Replace static diagnostic builder catalog with dynamic module-command blocks.
8. Add low-code condition builder for command output, error code and install errors.
9. Add ticket Automation overlay for running commands/playbooks with preflight preview.
10. Add observer trace links and step-level error drilldown.
11. Update docs/CODEMAP/QUICK_LOOKUP and add regression tests.

### Verification Target

- Server tests:
  - playbook manifest v2 normalization;
  - dynamic tool catalog from device/server registry;
  - module owner resolution for command;
  - playbook auto-install before command;
  - install failure branching;
  - actor role/policy regression;
  - preset expansion into params.
- Webapp tests:
  - playbook builder renders dynamic commands;
  - preset selector changes params preview;
  - condition builder can reference step status/output/error;
  - ticket Automation overlay can select command/playbook and show preflight.
- Live checks:
  - run playbook against Linux agent with builtin `system.collect`;
  - run playbook that requires server module auto-install, then command execution;
  - force install/preflight error and verify support-facing package plus observer step drilldown.

### Handoff

Start implementation from:

- `server/tools/service.py`
- `server/app/services/playbook_engine.py`
- `server/app/services/playbook_capability.py`
- `server/playbooks/catalog.py`
- `server/web_api/admin_handlers.py`
- `server/web_api/support_handlers.py`
- `webapp/src/features/playbooks/*`
- `webapp/src/features/queues/*`
- `webapp/src/pages/tickets/detail-page.tsx`
- `pc_agent/core/orchestrator.py`
- `pc_agent/core/registry.py`

Before frontend commands, run:

- `python scripts/bootstrap_web_toolchain.py`

Before any completion claim, run focused pytest/vitest/build plus `python scripts/verify_workspace.py`, then live browser check at `http://192.168.100.17:8666/admin`.

### 2026-04-27 Implementation Notes

Completed in this pass:

- Added `server/playbooks/tool_catalog.py` for normalized atomic command manifests.
- Playbook manifest is now saved as `pc_client.playbook.self_healing.v2` with `required_tools`, install policy, output schema, presets, platforms and min agent version.
- `/api/web/admin/playbooks/catalog` now merges the static diagnostic starter blocks with installable commands from the preferred server module registry.
- Playbook execution now runs the existing module auto-install preflight before tool-backed steps. Install/preflight failures become failed step runs with `stage=module_install` or `stage=capability_gate` and are not enqueued to the agent.
- Playbook tool dispatch now uses the support actor role for diagnostic commands instead of `system`.
- Support tool runs and playbook builder steps expand manifest presets into concrete params; the agent no longer depends on receiving only `preset_id`.
- `/app/admin/playbooks` shows module/source/install/platform/min-agent metadata and lets an operator select presets and inspect/edit params JSON per step.
- Ticket tool surfaces now carry preset params to the server, and the server still re-expands the preset before dispatch for consistency.

### 2026-04-27 Output Contract Tightening

Completed in this pass:

- Module manifest normalization now preserves a separate tool-level `output_contract` instead of relying on verbose `output_schema`.
- Declared `output_contract.status_values` must be explicit and unique; `success_values` / `error_values` are checked against the declared status set.
- `server/playbooks/tool_catalog.py` derives `condition_hints` from `output_contract` and known `error_codes` so the low-code builder can offer predictable condition templates.
- Saved playbook `required_tools` now carry `output_schema`, `output_contract` and `condition_hints` separately.
- `/app/admin/playbooks` displays status path, allowed status values, summary path and error codes for each command block, and decision blocks can insert a quick condition from previous command output.

Deferred to the observer stage:

- First-class observer spans for playbook root, preflight, install, command dispatch and ticket fact attachment.
- A dedicated ticket Automation modal for launching full playbooks with preflight preview and step progress.
- Editable protected routing visualization over the existing routing service.

### 2026-04-27 Module Authoring API/UI Notes

Completed in this pass:

- Added headless module authoring API:
  - `GET /api/modules/authoring/catalog`
  - `POST /api/modules/authoring/validate`
  - `POST /api/modules/authoring/publish`
- The headless endpoints reuse the existing workbench package builder, preflight, smoke check, ownership-conflict check and registry persistence path.
- Generated module packages now preserve explicit `output_contract` in `manifest.json`, `manifest_summary` and editable workbench previews.
- Agent-side `@exposed_tool` now accepts `output_contract` and includes it in registry/tool specs, so installed module commands can expose the same predictable contract.
- The module workbench UI now has a `Playbook decision contract` block in legacy guided/advanced editors and in the typed `/app/admin/modules` React editor, readiness chips/local validation for contract paths/status buckets, and API preview snippets pointing at the headless authoring endpoints.

Verification focus:

- Legacy module payloads without `output_contract` must stay valid.
- New playbook-ready module payloads should declare explicit `status_values`, `success_values`, `error_values`, `summary_path` and `error_code_path`.
- `/app/admin/playbooks` can consume these contracts through the existing module/tool catalog path.

### 2026-04-27 Module Test Harness And Windows Gate

Current plan:

1. [done] Make the existing server-side module smoke/runtime harness explicit and mandatory in authoring validation before publish.
2. [done] Store harness status in `validation_json.server_harness` for each module version.
3. [done] For Windows-targeted modules (`win32` / `windows*` platforms), show a warning that a Windows lab agent live test is still required before production/preferred rollout.
4. [done] Add a live-test API for a published module version that installs/runs the module command on a selected real agent and records the result back into `validation_json.live_tests`.
5. [done] Block setting a Windows-targeted module version as preferred unless `validation_json.live_tests` contains a passed Windows test on an agent whose version satisfies the module `min_agent_version`.
6. [done] Keep Linux/any modules publishable with server harness only; live lab testing stays optional unless the module targets Windows and is being promoted to preferred.

Verification target:

- Server tests for mandatory harness metadata, Windows warning, live-test recording and preferred gate.
- React test for the Windows lab warning in the module constructor.
- Live check on `/app/admin/modules` plus headless API validation on the Linux server.

### 2026-04-27 Module Lab Agent Selection And Observer Coverage

Goal:

- Let an operator choose the exact Linux or Windows lab agent used to live-test a published module version.
- Make module authoring and lab-test failures observer-visible now, so later UI can render a step-by-step problem map instead of a raw error message.

Current plan:

1. [done] Add a server API that returns compatible lab-agent candidates for a module version, including normalized platform, online state, agent version compatibility and warning reasons.
2. [done] Add a typed React lab-test panel on `/app/admin/modules` for the selected published version: platform filter, agent selector, tool selector and live-test run button.
3. [done] Wire the panel to the existing live-test endpoint using the chosen `device_id`; show the latest result and trace id.
4. [done] Add observer materialization for preferred gate and live-test steps: root trace, spans for candidate selection / install / run / gate, and error occurrence on terminal failures.
5. [done] Update docs/CODEMAP/observer docs and add automated tests for API candidates, UI selector and observer trace output.

Verification target:

- Server pytest for candidate filtering, explicit `device_id` live-test, preferred gate and observer trace rows.
- React test for selecting Linux/Windows lab agent and calling the live-test endpoint.
- `python scripts/verify_workspace.py`, webapp build/test and live browser/API check on `http://192.168.100.17:8666/app/admin/modules`.

### 2026-04-27 Observer Coverage Closure And Agent Telemetry

Current status:

1. [done] Added `agent_observer_events` source rows, websocket `agent_observer_batch` ingest, projection into observer spans/signatures and agent-side action-trace export/upload cursor.
2. [done] Added first-class `module_reconcile`, `playbook_run`, `web_auth` and `observer_runtime` root kinds for previously log-only gaps.
3. [done] Extended typed observer filters for `playbook_run_id`, `step_run_id` and `route`; React observer workbench serializes the new filters and shows source evidence from trace attrs.
4. [in progress] Verification/release: focused pytest and observer Vitest are green; full workspace verification, Linux/Windows agent release artifacts, deploy and live browser checks are next.

Verification target:

- `python scripts/verify_workspace.py`
- focused server/agent observer pytest
- `pnpm --dir webapp run test -- observer` and `pnpm --dir webapp run build`
- Windows release via `python pc_agent/build_windows_release_v2.py`
- Linux release on `/var/chat_bot/pc_client` via the documented PyInstaller specs, then upload both agent builds and verify `/app/admin/observer` live.

### 2026-04-28 Protocol/Outbox Review Fixes

Current plan:

1. [in progress] Add focused regressions for outbox retry NACK dedupe, sync waiter race, missing trace_id NACK, params immutability and protocol-version logging.
2. [pending] Fix server-side outbox ingest and command dispatch without touching unrelated worktree changes.
3. [pending] Bump/build the Windows agent release only for the `ws_agent.py` protocol-log change, upload it and promote it as the preferred version.
4. [pending] Run local verification, deploy server fixes to Linux with the project scripts, smoke the remote stack and stop the server afterwards unless a follow-up requires it online.

Verification target:

- `python -m pytest server/tests/test_agent_services_pipeline.py server/tests/test_protocol_waiters.py server/tests/test_tool_service_auto_install_no_db.py pc_agent/tests/test_ws_agent_protocol_logging.py -q`
- `python scripts/verify_workspace.py`
- `python pc_agent/build_windows_release_v2.py`
- remote deploy/release and agent-build promotion through the documented scripts/APIs.
