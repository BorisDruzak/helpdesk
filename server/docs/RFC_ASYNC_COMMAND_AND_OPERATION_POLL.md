# RFC: Async command execution + operation polling

## Status

Accepted (minimal contract, phase B1-a/B1-b).

## Problem

Long-running tool execution over WS can hold HTTP handlers while waiting for
`command_result`. Under load this creates too many long-lived coroutines and
degrades API responsiveness.

## Goals

- Keep `operation_id` as the single correlation key end-to-end.
- Support fire-and-forget command submit over HTTP with explicit polling.
- Preserve backward compatibility for existing sync/dev flows.

## Contract

### Submit command (async)

- Endpoint: existing run endpoints (for example `POST /api/tools/run`,
  `POST /api/admin/run_tool` with async mode).
- Behavior: enqueue/send command with `wait_for_result=False`.
- Response: `202 Accepted` with:
  - `operation_id` (required)
  - `poll_url` (required when `operation_id` exists), format:
    `/api/operations/{operation_id}`

Example:

```json
{
  "status": "accepted",
  "operation_id": "8af8b96c-0b2e-4fca-a64f-5ee2a0428d04",
  "poll_url": "/api/operations/8af8b96c-0b2e-4fca-a64f-5ee2a0428d04"
}
```

### Poll operation status

- Endpoint: `GET /api/operations/{operation_id}`
- Returns operation state and terminal result metadata.
- Canonical states:
  - non-terminal: `queued`, `sent`, `accepted`, `running`, `waiting_consent`,
    `cancel_requested`
  - terminal: `succeeded`, `failed`, `timed_out`, `canceled`, `denied`

## Compatibility

- Existing fields (`status`, `operation_id`, `ticket_id`, `device_id`) remain.
- Sync/dev mode (`wait=1` or equivalent) remains supported.
- Consent flow remains valid: `waiting_consent` may also return `202` and is
  still polled via the same `operation_id`.

## Constraints and guardrails

- Idempotency and lifecycle updates are driven by `operation_id`.
- HTTP submit must not block on final `command_result` in async mode.
- UI may poll `poll_url` or subscribe to websocket updates (`operation_updated`)
  where available.
- Timeouts and watchdog behavior are still enforced by operation lifecycle
  services; async submit does not bypass SLA rules.

## Alternative for further load reduction

Without changing public HTTP contract, queue pressure can also be reduced via:

- bounded semaphores in execution paths;
- worker pool limits for expensive pre/post-processing;
- backpressure/error responses when enqueue capacity is exhausted.
