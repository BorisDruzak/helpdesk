# PLANS.md

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
