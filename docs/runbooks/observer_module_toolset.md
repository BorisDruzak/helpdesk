# Observer Runbook: Module Toolset Artifact Integrity

## Meaning

The Observer found drift between desired and actual modules, current and snapshot toolset hashes, or tool result artifact references and persisted artifact rows.

## Immediate Checks

- Open Device Operations for the affected `device_id`.
- Compare desired module rows with active `device_modules`.
- Compare `devices.current_toolset_hash` with latest `device_toolset_snapshots`.
- For artifact issues, check `ticket_events.tool_call_result` and linked `artifacts.operation_id`.

## Safe Queries

- Query by exact `device_id`, `module_name`, `operation_id`, or artifact id.
- Use compact artifact metadata only.

## What Not To Do

- Do not expose raw artifact paths or raw result payloads in observer/browser output.
- Do not run heavy screen recording solely to clear an alert.

## Escalation

Escalate as critical if product claims an artifact exists but the persisted artifact row is missing.

## Related Bugs

Inspired by P2/P6 module/toolset and artifact consistency checks.

## Cleanup and Suppression

Suppress only historical marked rows. New toolset or artifact drift should remain visible until reconciled.
