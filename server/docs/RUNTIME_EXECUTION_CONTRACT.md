# Runtime Execution Contract

Канон для agent runtime, server `run_tool` expectations и playbook execution.

## Canonical runtime payload

Wire-format `ToolResponse` сохраняется для совместимости, но канонический tool result живёт в `data.result`:

```json
{
  "status": "ok | error | partial | skipped",
  "output": {},
  "error": {
    "code": "TIMEOUT",
    "message": "human readable message",
    "retryable": true,
    "category": "runtime"
  },
  "artifacts": [],
  "metrics": {
    "duration_ms": 120,
    "attempt": 1,
    "request_id": "..."
  },
  "changed": false,
  "confidence": 1.0
}
```

## Runtime guarantees

- input validation через declared schema / params model
- dependency precheck до execution
- timeout support
- cancellation support
- artifact upload через общий artifact pipeline
- redaction перед сериализацией результата
- resource limits для runtime/artifact path

## Error taxonomy

Базовые коды:

- `VALIDATION_ERROR`
- `UNSUPPORTED_PLATFORM`
- `TIMEOUT`
- `ACCESS_DENIED`
- `CONSENT_REQUIRED`
- `DEPENDENCY_MISSING`
- `DNS_NXDOMAIN`
- `TCP_CONNECT_FAILED`
- `HTTP_407_PROXY_AUTH`
- `TLS_CERT_INVALID`

## Builtin vs managed

- Builtin modules являются first-class tool providers по тому же contract.
- Отличие только в доставке: builtin не требуют server ZIP install.
- Managed packs проходят install/reconcile path и preferred-version auto-update.
# Agent Recipe execution

`agent_recipe` is a first-class capability execution target for declarative endpoint diagnostics. It creates `operations.kind=agent_recipe` and enqueues a Protocol V3 `run_recipe` command in `device_outbox`.

`run_recipe` payload includes `operation_id`, `trace_id`, `ticket_id`, `capability_id`, `capability_version_id`, `recipe_version_id`, `runner_provider_id`, `min_runner_version`, `primitive_id`, `recipe`, `runtime_params`, `resource_limits` and `redaction`. The agent responds through the normal `command_result` envelope with a ToolResponse-compatible payload.

`ToolExecutionService.run_tool` remains the path for `agent_builtin` and `agent_managed_module`; it is not the recipe execution path. Terminal `agent_recipe` command results are projected into `diagnostic_evidence` by the command-result side-effect pipeline.
