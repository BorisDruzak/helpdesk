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
3. The service creates an `operations` row with `kind=agent_recipe`.
4. The server enqueues a Protocol V3 `run_recipe` command in `device_outbox`.
5. The agent core `RecipeRunnerBridge` locates the active protected runner module and delegates `validate_recipe` / `run_recipe`.
6. The normal `command_result` pipeline completes the operation.
7. Terminal `agent_recipe` operations are projected into `diagnostic_evidence`.

`ToolExecutionService.run_tool` remains unchanged and is not used for recipe execution.

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
