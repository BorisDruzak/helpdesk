# Observer Runbook: Protocol V3 ACK Persistence

## Meaning

`protocol_ack_audit_gap` means the server has not produced recent durable v2 ACK audit rows, so Observer cannot prove ACK -> persistence. `protocol_ack_without_persistence` means a v2 ACK audit exists but has no `persisted_event_id`, no `duplicate=true` with `duplicate_proof`, and no `documented_noop=true`; treat this as possible event loss. `protocol_repeated_nack` means the same device is repeatedly rejected with validation/routing errors.

## Immediate Checks

- Open `/app/admin/observer` and filter by `event_type=protocol_ack_without_persistence` or the reported `device_id`.
- Correlate `trace_id`, `device_id`, `ticket_id`, `operation_id`, and `outbox_id` from Observer evidence.
- For ticket events, confirm `ticket_events` has the expected `(ticket_id, agent_seq/event_id, event_type, trace_id)` row.
- For device events, confirm `device_events` has the expected `(device_id, device_seq/event_id, event_type, trace_id)` row.
- Check `agent_runtime_audit.details_json` for `persisted_event_id`, `duplicate`, `duplicate_proof`, `documented_noop`, and `db_persistence_enabled`.
- Require `details_json.audit_contract_version >= 2`; a bare `persisted=true` flag is legacy telemetry and is not enough proof.

## Safe Queries

Use exact identifiers only:

```sql
SELECT id, device_id, event_type, severity, details_json, created_at
FROM agent_runtime_audit
WHERE event_type IN ('outbox_ack_persisted', 'protocol_ack_persisted', 'protocol_nack')
  AND device_id = :device_id
ORDER BY created_at DESC
LIMIT 50;
```

```sql
SELECT id, ticket_id, device_id, event_type, operation_id, trace_id, created_at
FROM ticket_events
WHERE ticket_id = :ticket_id
ORDER BY created_at DESC
LIMIT 50;
```

```sql
SELECT id, device_id, event_type, trace_id, created_at
FROM device_events
WHERE device_id = :device_id
ORDER BY created_at DESC
LIMIT 50;
```

## Safe Actions

- If audit is missing but events are persisted, deploy/fix ACK audit instrumentation, then run Observer scan again and verify the gap resolves.
- If ACK lacks persistence proof, preserve DB/log evidence first; then investigate outbox ingest persistence and duplicate handling.
- For repeated NACKs, fix the validation/routing source or agent payload generator; do not suppress fresh rows.

## What Not To Do

- Do not trust WebSocket `outbox_ack` transport alone as proof of persistence.
- Do not replay commands to diagnostic probes.
- Do not insert fake `ticket_events` or `device_events` to clear an alert.
- Do not paste raw payload text, tokens, cookies, or requester messages into evidence.

## Escalation

Escalate `protocol_ack_without_persistence` as critical data integrity risk. Escalate repeated `UNKNOWN_TICKET` or `DEVICE_MISMATCH` as error because they can indicate cross-ticket or cross-device routing drift.

## Related Bugs

Inspired by P0/P1 Protocol V3 ACK/NACK, malformed outbox, and persistence-order failures.

## Cleanup and Suppression

Historical malformed/probe rows may be suppressed only by exact row id or stable dedupe key. Never suppress by broad device or event type for current traffic.
