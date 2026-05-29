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

## What Not To Do

- Do not classify an online runtime as offline from stale DB `last_seen` alone.
- Do not mix browser, UIA, direct API and raw WS as equivalent evidence.

## Escalation

Escalate as error when browser/admin projection materially disagrees with runtime presence beyond grace period.

## Related Bugs

Inspired by P6 false offline Command Center/Device Operations projection.

## Cleanup and Suppression

P6 historical non-P6 `agent_offline_active` tasks are not current OBS1 evidence unless tied to the current run marker.
