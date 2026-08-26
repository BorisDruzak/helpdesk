# Windows Headless Agent Canary — failed

> Historical / superseded record.
>
> Canonical final result:
> `docs/verification/WINDOWS_HEADLESS_AGENT_CANARY_ACCEPTANCE.md`

Status: `WINDOWS_CANARY_FAILED`

Date: 2026-08-24

## Safe observed facts

- The dedicated Windows staging VM is reachable through the approved agent
  account and reports a supported 64-bit Windows edition.
- `EndpointAgent` is installed, automatic, running, and uses
  `NT AUTHORITY\LocalService`.
- `EndpointAgentUpdater` is installed, demand-start, stopped, and uses
  `LocalSystem`.
- A staging Endpoint diagnostic reached a succeeded safe result and Helpdesk
  retained one `endpoint_platform` diagnostic evidence record.
- Staging services were returned to fail-closed operation and all temporary
  canary service credentials were revoked.

## Acceptance failure

The immutable selector on the installed Windows agent did not contain a
source revision.  The installed MSI therefore cannot be proven to originate
from the required exact Endpoint merge SHA.

This violates the immutable-release precondition and prevents this run from
being recorded as `WINDOWS_CANARY_ACCEPTED`, regardless of the successful
diagnostic result.

## Required recovery

1. Build a new immutable Windows MSI from the exact merged Endpoint revision.
2. Verify that its selector records the same non-empty source revision.
3. Reinstall it on the dedicated staging VM and run the strict installed-agent
   preflight validator.
4. Use a fresh dedicated canary ticket, execute exactly one operation, collect
   the full protected evidence package, verify rollback, and only then publish
   an acceptance record.

No production system was changed.
