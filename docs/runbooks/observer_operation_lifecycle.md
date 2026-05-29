# Observer Runbook: Operation Lifecycle

## Meaning

The Observer found a mismatch between `operations`, `device_outbox`, and terminal ticket events. Typical cases are a terminal operation with an active outbox row, a stuck active operation, or a terminal tool operation without a `tool_call_result`.

## Immediate Checks

- Open `/app/admin/observer` and filter by operation or device.
- Open `/app/admin/device-operations/{device_id}` and inspect operations, outbox and OBS1 integrity events.
- Check `operations.status`, `device_outbox.status`, `ticket_events.event_type`, and timestamps for the reported identifiers.

## Safe Queries

- Query by exact `operation_id` or `device_outbox.id`; do not broad-update rows.
- Confirm whether the row is listed in `observer_known_contamination`.

```sql
SELECT operation_id, device_id, ticket_id, command, status,
       queued_at, sent_at, finished_at, error_code
FROM operations
WHERE operation_id = :operation_id;
```

```sql
SELECT id, command_id, device_id, operation_id, command, status,
       created_at, sent_at, delivered_at, failed_at, error_code
FROM device_outbox
WHERE operation_id = :operation_id OR id = :device_outbox_id
ORDER BY id DESC;
```

## Safe Actions

- If the operation is terminal and outbox is still active, preserve evidence and verify whether a late result or timeout reconciliation should have closed it.
- If the row is synthetic test data, clean it through the documented test cleanup path and re-run Observer scan.
- If the row is historical contamination, add a narrow `observer_known_contamination` entry by exact entity id.

## What Not To Do

- Do not manually delete outbox or operation rows to clear the alert.
- Do not mark an operation successful without checking command result persistence.
- Do not enqueue a replacement command until the original operation/outbox lifecycle is understood.

## Escalation

Escalate as data integrity if a command can still be delivered after its operation is terminal or if a terminal result was lost.

## Related Bugs

Inspired by P0-P2/P6 operation, outbox and projection failures.

## Cleanup and Suppression

Suppress only known historical rows by exact entity id. New rows with new marker/run_id must not be hidden by broad suppression.
