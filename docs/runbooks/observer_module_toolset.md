# Observer Runbook: Module Toolset Artifact Integrity

## Meaning

`toolset_hash_drift` means `devices.current_toolset_hash` no longer matches the latest `device_toolset_snapshots.toolset_hash` after the grace period. `module_desired_actual_drift` means desired module state has not converged to active actual state. `artifact_result_missing_rows` means a tool result references artifacts but no durable artifact row is linked.

## Immediate Checks

- Open `/app/admin/device-operations/{device_id}` and check Observer, Modules, Toolset, Outbox, and Recent Operations.
- Compare `devices.current_toolset_hash`, `current_toolset_snapshot_id`, `last_toolset_refresh_at`, and `last_handshake_at`.
- Compare the latest snapshot hash/time with the current device hash. A newer handshake hash with an older snapshot usually means `list_tools` did not run or did not finish.
- Check for pending or failed `list_tools` operations before enqueueing another refresh.
- For module drift, compare `device_desired_modules` to active `device_modules`.
- For artifact drift, check the `tool_call_result.operation_id` and the `artifacts.operation_id` rows.

## Safe Queries

```sql
SELECT device_id, current_toolset_hash, current_toolset_snapshot_id,
       last_toolset_refresh_at, last_tools_changed_at, last_handshake_at, last_seen_at
FROM devices
WHERE device_id = :device_id;
```

```sql
SELECT snapshot_id, toolset_hash, tool_count, captured_at, agent_version
FROM device_toolset_snapshots
WHERE device_id = :device_id
ORDER BY captured_at DESC
LIMIT 5;
```

```sql
SELECT operation_id, command, status, queued_at, sent_at, finished_at, error_code
FROM operations
WHERE device_id = :device_id
  AND command IN ('list_tools', 'list_installed_modules')
ORDER BY queued_at DESC
LIMIT 20;
```

## Safe Actions

- If the device is online and no `list_tools` is pending, use the normal admin/support tool refresh path or enqueue a safe `list_tools`; then re-run Observer scan.
- If the latest snapshot is stale but the current hash came from a recent handshake, investigate handshake refresh scheduling and command result persistence.
- If desired/actual module drift is real, let module reconcile run or use the documented Modules UI/API flow; keep Observer event active until convergence.

## What Not To Do

- Do not directly edit `devices.current_toolset_hash` or `device_toolset_snapshots` to silence drift.
- Do not expose raw artifact paths or raw result payloads in Observer/browser output.
- Do not run heavy screen recording solely to clear an alert.
- Do not suppress fresh drift for live devices unless it is proven legacy and narrowly scoped.

## Escalation

Escalate as error when tool availability may be stale or module desired/actual state does not converge. Escalate artifact missing rows as critical if the product claims an artifact exists but no durable artifact record exists.

## Related Bugs

Inspired by P0/P1 tool availability drift and P2/P6 module/toolset/artifact consistency checks.

## Cleanup and Suppression

Suppress only historical marked rows. New toolset, module, or artifact drift should remain visible until the normal refresh/reconcile path resolves it.
