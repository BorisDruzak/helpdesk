# Module Authoring Rules

Канон для авторов модулей и tool-реализаций в текущем in-place runtime.

Практический пошаговый guide:

- `server/docs/MODULE_CREATION_GUIDE.md`

## Core model

### Provider / capability extension

The module contract now projects tools as diagnostic capabilities without renaming the existing runtime model:

- `Provider / Module` is the source of capabilities: agent builtin module, managed ZIP module, server connector, observer provider, remote assist provider or manual provider.
- `Capability / Tool` is the atomic executable contract with canonical id, schemas, safety, evidence and execution metadata.
- `Execution target` declares where the capability physically runs.
- `Operation` is a concrete run of a capability/tool.
- `Evidence` is normalized diagnostic fact metadata that can be shown in Diagnostic Center and later linked to passport evidence.

Installation on an agent is only one deployment mode. It is not a required property of every capability.

- `module` — pack доставки, versioning, ownership и capability bundle.
- `tool` — атомарный исполняемый контракт.
- Публичный идентификатор tool всегда semantic-only: `dns.resolve`, `network.ping`, `screen.collect`.
- Alias допустим только как backward-compat bridge. UI, playbook, analytics и policy должны опираться на canonical id.

## Tool contract

New optional contract blocks are backward-compatible:

- `execution`: `target`, `requires_device`, `requires_agent_online`, `supports_auto_install`, `requires_integration`, optional `integration_key`.
- `deployment`: `provider_id`, `install_required_on_agent`, `package_type`.
- `safety`: `side_effects`, `requires_consent`, `idempotent`.
- `readiness`: `requires_credentials`, `requires_mapping`, `requires_policy`, optional `required_permission`, `policy_key`, `mapping_key`.
- `evidence`: `produces_evidence`, `kind`, `domain`, `perspective`, `passport_eligible`.
- `artifacts`: `may_produce_artifacts`, `artifact_kinds`.

Supported `execution.target` values are `agent_builtin`, `agent_managed_module`, `server_builtin`, `server_connector`, `observer_query`, `remote_assist`, `manual` and `hybrid`.

Backward-compatible defaults:

- Old managed ZIP tools default to `agent_managed_module`, `requires_device=true`, `requires_agent_online=true`, `supports_auto_install=true`, `deployment.install_required_on_agent=true`, `deployment.package_type=zip`, `evidence.produces_evidence=false`.
- Builtin agent tools default to `agent_builtin`, `supports_auto_install=false`, `deployment.install_required_on_agent=false`, `deployment.package_type=builtin`.
- Old `params_schema`, `output_schema`, `output_contract`, `risk_level`, `tool_kind` and aliases remain valid.

Validation additions:

- `server_connector` requires `execution.requires_integration=true`, `execution.integration_key` and `deployment.install_required_on_agent=false`.
- `agent_builtin` requires `deployment.install_required_on_agent=false`.
- `agent_managed_module` requires device, online agent and install-required deployment semantics.
- `evidence.produces_evidence=true` requires `kind`, `domain` and `perspective`; perspective is one of `endpoint`, `server`, `monitoring`, `observer`, `remote_assist`, `manual`, `hybrid`.
- `safety.side_effects`, `safety.requires_consent` and `safety.idempotent` must be booleans when present.
- `readiness.requires_credentials`, `readiness.requires_mapping` and `readiness.requires_policy` must be booleans when present.
- `readiness.required_permission`, `readiness.policy_key` and `readiness.mapping_key` must be non-empty strings when present.
- If `readiness.requires_credentials=true`, the tool must also declare `execution.integration_key`.

Example `diag.logs.collect` metadata:

```json
{
  "execution": {"target": "agent_builtin", "requires_device": true, "requires_agent_online": true, "supports_auto_install": false, "requires_integration": false},
  "deployment": {"provider_id": "diag_logs", "install_required_on_agent": false, "package_type": "builtin"},
  "evidence": {"produces_evidence": true, "kind": "logs.bundle", "domain": "logs", "perspective": "endpoint", "passport_eligible": true},
  "artifacts": {"may_produce_artifacts": true, "artifact_kinds": ["logs_zip"]}
}
```

Example `zabbix.problems.lookup` placeholder:

```json
{
  "execution": {"target": "server_connector", "requires_device": false, "requires_agent_online": false, "supports_auto_install": false, "requires_integration": true, "integration_key": "zabbix"},
  "deployment": {"provider_id": "zabbix_connector", "install_required_on_agent": false, "package_type": "server_connector"},
  "readiness": {"requires_credentials": true, "requires_mapping": true, "requires_policy": true, "required_permission": "monitoring.zabbix.view", "policy_key": "monitoring.zabbix.enabled", "mapping_key": "zabbix.host"},
  "evidence": {"produces_evidence": true, "kind": "monitoring.problem", "domain": "monitoring", "perspective": "monitoring", "passport_eligible": true}
}
```

Non-agent capabilities now route through server-side providers:

- `observer.ticket.summary` and `observer.trace.bundle` call existing observer overlay services and return evidence previews.
- `manual.visual_check` and `manual.vendor_response` create auditable passport/evidence items through the existing evidence repository.
- Zabbix server connector capabilities validate integration/config/credential/mapping readiness and return a bounded unavailable response until a real external client is configured.

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

## Observer SDK is mandatory

- Endpoint-owned module tools are instrumented and executed by Endpoint Platform; Helpdesk records only safe ticket evidence.
- Минимальный обязательный слой:
  - один верхнеуровневый `with self.trace_span("tool.entry", details={"tool_name": "<canonical id>"})`
  - `self.trace_event(...)` или вложенные `self.trace_span(...)` на опасных шагах
- Обязательные dangerous checkpoints:
  - subprocess / shell execution
  - network I/O
  - retries / timeout boundaries
  - artifact creation or upload
  - consent-sensitive or state-changing branch
- Workbench/builder-generated scaffold с trace hooks считается частью канона и не должен удаляться без эквивалентной ручной инструментировки.
- В `details` нельзя класть сырой токен, cookie, password, secret, consent token или другие чувствительные данные.

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
