# Agent Recipe Runner

Agent Recipe Runner adds a production path for read-only declarative endpoint diagnostics without generating a ZIP module per check.

## Model

`agent_recipe_runner` is a protected managed module. It is installed, preferred, rolled out and rolled back through the existing module lifecycle, but recipe capabilities are persisted in the server database:

- `diagnostic_capabilities` and `diagnostic_capability_versions` store capability identity and immutable/published contracts.
- `agent_recipe_versions` stores the concrete declarative recipe for a capability version.
- `agent_recipe_primitives` stores primitives supported by runner versions.
- `agent_recipe_test_runs` stores validation/live-test audit results.

The capability execution target is `agent_recipe`. It is distinct from `agent_managed_module`: the recipe is not a ZIP package, and execution requires an active `agent_recipe_runner`.

## Execution

1. Capability Studio or a playbook selects a published `agent_recipe` capability.
2. `RecipeExecutionService` resolves the current recipe version and checks readiness.
3. If the runner is ready, the service creates an `operations` row with `kind=agent_recipe` and enqueues a Protocol V3 `run_recipe` command in `device_outbox`.
4. If readiness reports `runner_not_installed`, `runner_outdated` or `primitive_not_supported`, the service creates the parent recipe operation in `phase=waiting_dependency`, records an `operation_dependencies` row, selects the compatible preferred `agent_recipe_runner` version, writes `device_desired_modules`, and invokes the existing module reconcile/install path.
5. The HTTP request returns immediately with the parent `operation_id` and dependency state. It does not wait for install/upgrade completion.
6. When `install_module_package` completes or the agent emits `module_state_changed` / `tools_changed`, the server re-checks readiness and resumes the parent operation by enqueuing `run_recipe` exactly once.
7. The agent core `RecipeRunnerBridge` locates the active protected runner module and delegates `validate_recipe` / `run_recipe`.
8. The normal `command_result` pipeline completes the operation.
9. Terminal `agent_recipe` operations are projected into `diagnostic_evidence`.

`ToolExecutionService.run_tool` remains unchanged and is not used for recipe execution.

## Runtime Dependency Auto-Install

Ticket-bound auto-install/auto-upgrade is intentionally narrower than fleet rollout:

- Dependency linkage is persisted in `operation_dependencies`.
- Parent operations keep the existing status lifecycle and use `operations.phase` for `waiting_dependency`, `installing_dependency`, `sending_run_recipe`, `running_recipe`, `completed` and `failed`.
- The runner version resolver uses the module preferred assignment from `ModuleRolloutRepo`; it does not install an arbitrary latest version.
- Target runner versions must satisfy the recipe `min_runner_version` / `runner_version_constraint`, support the device platform, advertise the requested primitive, and be a protected/core-platform module.
- Auto-install/upgrade is policy gated by role, read-only diagnostic tool kind, side-effect flag and risk level.
- Install/upgrade uses `device_desired_modules` plus `modules.reconcile.reconcile_device`; new code must not download or write module ZIPs directly.
- Resume is idempotent: if the parent operation already has a `run_recipe` outbox command, subsequent resume attempts do not enqueue another one.
- Timeout is handled by the operation watchdog through the dependency timeout timestamp and fails the parent operation with a clear runner dependency error.

## Readiness

`agent_recipe` readiness can return:

- `available`
- `agent_offline`
- `unsupported_platform`
- `runner_not_installed`
- `runner_install_required`
- `runner_installing`
- `runner_outdated`
- `primitive_not_supported`
- `recipe_not_published`
- existing policy/permission/consent states

Windows and Linux are the only supported platforms. macOS values (`darwin`, `mac`, `macos`) are rejected by recipe validation.

## Security

First release primitives are read-only. The runner does not expose a shell, arbitrary PowerShell/Bash/Python execution, file writes, registry writes, service restarts, process kills, package installs or remediation. Network primitives are bounded by timeout and output limits. Secrets such as auth headers/cookies are redacted or rejected by primitive-specific handling.

Remediation recipes are intentionally out of scope and require a separate approvals/governance phase.
