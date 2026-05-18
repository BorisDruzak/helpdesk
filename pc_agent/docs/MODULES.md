# Modules in pc_agent

Агент использует единый contract как для builtin, так и для managed modules.

## Canonical model

The server now projects agent tools as diagnostic capabilities, but the agent runtime still executes only local tools:

- `capability` is the server-side universal projection of an agent tool, server connector, observer query, remote assist session action or manual check.
- `execution target` declares where a capability runs.
- Agent-side registry exposes `execution`, `deployment`, `safety`, `readiness`, `evidence` and `artifacts` for executable agent tools.
- The agent must not execute `server_connector`, `observer_query`, `remote_assist` or `manual` targets through ordinary `run_tool`.

- builtin module: first-class provider, доставка встроенная
- managed module: ZIP pack из server registry
- tool: атомарный semantic contract

Примеры canonical ids:

- `system.collect`
- `screen.collect`
- `dns.resolve`

Legacy aliases остаются только для compat resolution в registry.

## Runtime path

- загрузка builtin modules через `ModuleFactory`
- загрузка managed modules через `ModuleManager` + `DynamicModuleLoader`
- регистрация всех tools через `ModuleRegistry`
- execution через `AgentOrchestrator._handle_run_tool`

## Observer instrumentation

- Каждый tool method должен оставлять observer trail через `BaseCollector.trace_span(...)` и `BaseCollector.trace_event(...)`.
- Минимальный обязательный каркас:
  - `with self.trace_span("tool.entry", details={"tool_name": "my.tool"}):`
  - дополнительные шаги на опасных местах: subprocess, network, retries, timeouts, artifact write/upload, consent-sensitive branch.
- Это не рекомендация, а CI-инвариант: `python scripts/verify_workspace.py` и module ZIP preflight теперь валят сборку, если `@exposed_tool` в `BaseCollector`-модуле не обёрнут в `self.trace_span("tool.entry", ...)`.
- `AgentOrchestrator` автоматически bind-ит `ticket_id`, `operation_id`, `trace_id`, `request_id` и `parent_action_id`, поэтому модулю достаточно вызывать SDK-хелперы из `BaseCollector`.
- Любые `details` должны быть JSON-совместимыми и безопасными для redaction; сырые секреты в trace/event payload запрещены.

## Contract guarantees

Additional capability metadata carried by `list_tools` and `describe_tool`:

- `execution`
- `deployment`
- `safety`
- `readiness`
- `evidence`
- `artifacts`

Agent builtin defaults:

- `execution.target=agent_builtin`
- `execution.requires_device=true`
- `execution.requires_agent_online=true`
- `execution.supports_auto_install=false`
- `deployment.install_required_on_agent=false`
- `deployment.package_type=builtin`
- `readiness.requires_credentials=false`
- `readiness.requires_mapping=false`
- `readiness.requires_policy=false`

Managed ZIP packages may pass explicit `agent_managed_module` metadata through `@exposed_tool`; old packages remain executable and are still owned by server-side manifest/default projection.

Builtin evidence markings:

- `system.collect` produces endpoint system snapshot evidence.
- `screen.collect` produces endpoint screenshot evidence and screenshot artifacts.
- `screen.record` produces endpoint screen recording evidence and recording artifacts.
- `diag.logs.collect` produces `logs.bundle` evidence from endpoint perspective, is passport-eligible and may produce `logs_zip` artifacts.
- `diag.logs.collect` app preset resolves the agent runtime logs directory from the current runtime data root (`PC_AGENT_DATA_DIR` or OS default), so diagnostic log collection does not depend on a stale config-loader singleton.

Каждый tool spec должен нести:

- `contract_version`
- `params_schema`
- `output_schema`
- `output_contract` when the tool is intended for predictable playbook branching
- `presentation_schema` when the UI should render structured results as readable blocks
- `metadata`
- `dependencies`
- `lifecycle`
- `error_codes`
- `artifact_types`
- `redaction`
- `resources`

Wire-format ответа сохраняет `ToolResponse`, но канонический structured result находится в `data.result`.

## Tool Output Presentation Schema v1

`presentation_schema` is a top-level tool/capability field next to `params_schema`, `output_schema` and `output_contract`.

- `output_schema` describes the complete structured result shape.
- `output_contract` describes deterministic semantics for playbooks, evidence and backend decisions.
- `presentation_schema` describes declarative UI rendering hints for that result.

The v1 schema is declarative only. It supports `version`, `kind`, `title`, optional `summary`, `blocks` and `fallback`. Supported block types are:

- `field_grid`
- `metric_cards`
- `table`
- `checklist`
- `timeline`
- `artifact_list`
- `raw_json`

Fields and columns may use safe dotted `path` lookups, `label`, `unit`, `format`, `empty_text`, `copyable` and bounded `tone_rules`. String templates support only path substitution with `{{path.to.value}}`; no JavaScript expressions, eval, HTML, CSS injection or remote URLs are allowed. UI renderers must rely on React text escaping and must not use `dangerouslySetInnerHTML`.

If a schema is missing, invalid or references missing paths, the UI falls back to a defensive generic rendering: top-level scalar values as a `field_grid`, arrays of objects as tables where practical, and a collapsed raw JSON view. Unsupported blocks are ignored and raw JSON remains available for debugging.

Recipe results use `kind=composite_recipe`. The recipe summary is rendered separately, `steps[]` are rendered as timeline/checklist items, and each step result is rendered with the `presentation_schema` for `step.tool_id` or `step.primitive_id`. If no matching schema exists, the step falls back to the same generic renderer/raw JSON path.

Tools may additionally declare future inventory hints in `output_contract.device_card` or `evidence.device_card`, for example:

```json
{
  "device_card": {
    "eligible": true,
    "slots": ["identity", "health", "network", "platform"],
    "priority": 100
  }
}
```

`system.collect` declares a v1 presentation schema for identity, resource metrics and network interfaces, plus `output_contract.device_card` hints. Agent recipe primitives declare simple v1 schemas for their read-only result payloads.

# Agent Recipe Runner

`agent_recipe_runner` is a protected managed module. It can be updated independently from Maria Agent through the normal managed-module lifecycle, but it is not a support-visible tool module.

Agent core handles only the stable bridge:

- locate the active `agent_recipe_runner`;
- verify `min_runner_version`;
- call `describe_primitives`, `validate_recipe` and `run_recipe`;
- return a ToolResponse-compatible `command_result`.

The runner module contains the read-only primitive implementations. It does not provide arbitrary shell, PowerShell, Bash or Python command execution and does not implement remediation in the first release. Supported platforms are `win32` and `linux`; macOS is unsupported.
