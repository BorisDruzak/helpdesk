# Playbook Tools Contract

Playbook engine больше не должен опираться на физические `module.tool` имена как на source of truth.

## Canonical reference

Playbook steps должны ссылаться на canonical semantic tool ids:

- `dns.resolve`
- `network.ping`
- `tcp.connect`
- `screen.collect`

Alias допустим только для compatibility resolution.

## Expected step contract

Каждый tool-backed шаг должен быть валидируемым через:

- `params_schema`
- `output_schema`
- `contract_version`
- `required_tool_version` / `required_contract_range` при необходимости

## Runtime result

Для playbook decisions канонический результат читается из `data.result` execution envelope, а не из произвольного `stdout` или ad-hoc fields.

## Risk and lifecycle

Playbook compiler/runtime должны учитывать:

- `risk_level`
- `requires_consent`
- `tool_kind`
- `lifecycle`

Deprecated tools допустимы только как migration bridge и должны подсвечиваться предупреждением.
