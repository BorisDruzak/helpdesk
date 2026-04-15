# Module Authoring Rules

Канон для авторов модулей и tool-реализаций в текущем in-place runtime.

## Core model

- `module` — pack доставки, versioning, ownership и capability bundle.
- `tool` — атомарный исполняемый контракт.
- Публичный идентификатор tool всегда semantic-only: `dns.resolve`, `network.ping`, `screen.collect`.
- Alias допустим только как backward-compat bridge. UI, playbook, analytics и policy должны опираться на canonical id.

## Tool contract

Каждый tool обязан декларировать:

- `canonical_id`
- `contract_version`
- `method`
- `params_schema`
- `output_schema`
- `metadata`
- `dependencies`
- `lifecycle`
- `error_codes`
- `artifact_types`
- `redaction`
- `resources`

Минимальный metadata block:

- `domain`
- `platforms`
- `risk_level`
- `requires_consent`
- `idempotent`
- `side_effects`
- `timeout_sec`
- `allow_roles`
- `scopes`
- `origin`
- `tool_kind`

## Semantics

- Один tool = одно логическое действие.
- `stdout/stderr` не являются API-контрактом; это debug channel.
- Diagnostics по умолчанию должны быть `idempotent=true` и `side_effects=false`.
- Remediation должна быть явно помечена через `tool_kind=remediation` и `side_effects=true`.
- Import-time side effects запрещены: нельзя делать сеть, subprocess, запись на диск или сбор данных при импорте модуля.
- Секреты и чувствительные поля должны редактироваться по `redaction` policy.

## Naming and ownership

- Reserved core namespaces: `dns.*`, `network.*`, `tcp.*`, `http.*`, `tls.*`, `system.*`, `service.*`, `file.*`, `process.*`, `browser.*`.
- Reserved namespaces допускаются только для `owner_scope=core|platform|builtin`.
- Vendor/public tools должны жить в собственном namespace (`vendor_x.*`, `myorg.*`).

## Versioning

- `module_version`, `module_api_version`, `manifest_version` обязательны на уровне manifest.
- `contract_version` обязателен на уровне tool.
- Minor bump: backward-compatible additions.
- Major bump: incompatible schema change.
- Patch bump: implementation-only fix.

## Error and artifact rules

- `error_codes` должны быть стабильными и машиночитаемыми.
- Артефакты должны быть объявлены через `artifact_types`.
- Для screenshot/file/video path используются те же artifact descriptors, что и для обычных managed tools.
