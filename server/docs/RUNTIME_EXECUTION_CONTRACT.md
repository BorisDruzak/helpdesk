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
