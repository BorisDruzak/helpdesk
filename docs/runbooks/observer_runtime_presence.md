# Observer Runbook: Runtime Presence

## Meaning

The Observer found a mismatch between runtime connection state, DB `last_seen`, and UI projections such as Command Center or Device Operations.

## Immediate Checks

- Verify `/api/health`.
- Open Admin Tech, Device Operations and Command Center in a real browser.
- Check local agent state with UIA when GUI state is part of the claim.

## Safe Queries

- Read `devices.last_seen_at` and recent `agent_runtime_audit` rows by exact `device_id`.
- Compare with runtime state manager output.

```sql
SELECT device_id, last_seen_at, last_handshake_at, agent_version, hostname
FROM devices
WHERE device_id = :device_id;
```

```sql
SELECT id, event_type, severity, details_json, created_at
FROM agent_runtime_audit
WHERE device_id = :device_id
ORDER BY created_at DESC
LIMIT 50;
```

## Safe Actions

- If runtime is online but UI says offline, capture browser evidence and inspect the projection path before changing data.
- If runtime is offline, verify it from more than one signal before opening an incident.
- After restart/reconnect, run Observer scan and confirm the event resolves instead of suppressing it.

## What Not To Do

- Do not classify an online runtime as offline from stale DB `last_seen` alone.
- Do not mix browser, UIA, direct API and raw WS as equivalent evidence.
- Do not stop the agent for validation unless the live test plan says it is safe.

## Escalation

Escalate as error when browser/admin projection materially disagrees with runtime presence beyond grace period.

## Related Bugs

Inspired by P6 false offline Command Center/Device Operations projection.

## Cleanup and Suppression

P6 historical non-P6 `agent_offline_active` tasks are not current OBS1 evidence unless tied to the current run marker.
