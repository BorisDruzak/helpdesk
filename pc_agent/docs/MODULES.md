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
