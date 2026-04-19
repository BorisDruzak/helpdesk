# Modules in pc_agent

Агент использует единый contract как для builtin, так и для managed modules.

## Canonical model

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

Каждый tool spec должен нести:

- `contract_version`
- `params_schema`
- `output_schema`
- `metadata`
- `dependencies`
- `lifecycle`
- `error_codes`
- `artifact_types`
- `redaction`
- `resources`

Wire-format ответа сохраняет `ToolResponse`, но канонический structured result находится в `data.result`.
