# PLANS.md

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
