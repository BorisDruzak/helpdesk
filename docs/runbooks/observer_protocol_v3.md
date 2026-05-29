# Observer Runbook: Protocol V3 ACK Persistence

## Meaning

The Observer detected a Protocol V3 ACK/persistence telemetry gap or repeated NACK pattern. ACK without durable persistence is a critical integrity risk; repeated NACKs often indicate routing, validation or stale command state.

## Immediate Checks

- Correlate `trace_id`, `device_id`, `operation_id`, `command_id`, and `device_outbox_id`.
- Check `ticket_events` and `device_events` for persisted rows before accepting ACK evidence.
- Inspect server logs around `outbox_ack`, `command_result_ack`, and NACK error codes.

## Safe Queries

- Use exact identifiers from the observer event.
- Count recent NACKs by `device_id` and `error_code`.

## What Not To Do

- Do not trust a transport ACK as proof of persistence.
- Do not replay commands to diagnostic probes.

## Escalation

Escalate as critical if ACK was emitted without persisted event, duplicate proof, or documented no-op.

## Related Bugs

Inspired by P0/P1 Protocol V3 ACK/NACK and malformed outbox failures.

## Cleanup and Suppression

Historical malformed/probe rows may be suppressed only by exact row id or stable dedupe key.
