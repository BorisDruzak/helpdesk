# Module Platform Canary Closure v1 — staging record

## Status

**Not accepted.** The closure was safely rolled back after the sole permitted
Helpdesk ticket run reached a terminal local failure before Endpoint created a
remote operation. No production target was touched.

## Delivered code and releases

- Endpoint `main`: `684dab261f995aa80f8c18e347d72878d0fe0edd`
  (`fix(auth): revoke helpdesk module credentials`). This follows the merged
  15 canary-fix commits and adds the root-only, audited `--revoke` lifecycle
  action for the staging Helpdesk module credential.
- Helpdesk mainline: `ab5687db0609b4a3298f4a387d5ef20cbfe1d4fd`
  (`chore(modules): integrate canary closure`), including the reconciler
  hardening and locked Endpoint provider revision.
- Both revisions were deployed only to the isolated staging host.
- Endpoint verification: `1971 passed, 36 skipped` (`python -m pytest -q`).

## Sole ticket-route attempt

- Ticket: `ef87193f-3824-4aba-a712-65a655cabe7b`
- Published recipe: `network.canary.check@1.0.0`
- Local operation: `a352f78b-00d1-59b3-b8b8-e2e17d967465`
- Ticket status before and after: `in_progress`

The operation was submitted once through the Helpdesk BFF route. It produced:

| Check | Observed result |
| --- | --- |
| Local `Operation` | 1 |
| `EndpointOperationLink` | 1 |
| `DeviceOutbox` linked to operation | 0 |
| Remote parent operation | 0 |
| Remote child steps | 0 |
| `DiagnosticEvidence` | 0 |
| Link status | `failed` |
| Safe failure code | `endpoint_module_invalid_projection` |

The immediate cause was the intentionally empty Endpoint network-probe target
allowlist after the preceding staging rollback. The reconciler therefore never
created a remote operation. A second ticket run was deliberately not submitted:
the acceptance requirement permits exactly one recipe execution.

## Rollback and credential closure

- Exact pre-run Helpdesk and Endpoint staging environment files were restored.
- Staging Endpoint API, Endpoint worker, and Helpdesk services were verified
  `active` after restart.
- The root-only Endpoint CLI revoked the active fixed staging module credentials
  for `helpdesk-module-staging`; no bearer token is recorded here.
- The ephemeral staging web-session cookie and module-token handoff file were
  removed.

## Evidence and next action

This document is the redacted off-host evidence record once committed and
pushed to the Helpdesk repository. A new acceptance attempt requires an
explicitly approved fresh run after the Endpoint and selected agent network
allowlists are restored, because the current operation is terminal and must not
be replayed by mutating its database state.
