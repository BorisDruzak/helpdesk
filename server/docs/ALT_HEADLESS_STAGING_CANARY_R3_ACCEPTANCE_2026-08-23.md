# Real ALT Headless Agent Staging Canary v1 — R3 acceptance

**Status:** accepted after rollback
**Environment:** isolated staging only
**Date:** 2026-08-23

This record is intentionally redacted. It contains no passwords, tokens,
cookies, private keys, raw agent result, full configuration, or database dump.

## Release and gate

- Endpoint provider revision: `1562af5c00e91f22ed9a7d8d120ce221fea82437`.
- Helpdesk session-lifecycle repair: merge
  `eabf0cb58787da02e752bbfc09388ce5b79b41a6` (PR #12).
- PR #12 `cross-repository-acceptance`: passed in 2m22s.
- The deployed Helpdesk staging selector was
  `helpdesk-eabf0cb58787`; no schema migration or dependency update was part
  of this release.

## Canary result

| Criterion | Result |
| --- | --- |
| Helpdesk diagnostic request | Exactly one R3 request; HTTP 202. |
| Local facade | One `Operation` and one `EndpointOperationLink`. |
| Endpoint execution | One operation, one Gateway command delivery, and one terminal result. |
| Command safety | `context.diagnostic.collect`; the Gateway command contained only the permitted `reason` parameter. |
| Reconciliation | Local and remote operations succeeded; linked `DiagnosticStep` and `DiagnosticSession` completed. |
| Evidence | Exactly one safe Endpoint diagnostic evidence record. |
| Repeat reconciliation | No second operation, link, or evidence record was created. |
| Ticket and legacy boundary | Ticket remained `queued`; `DeviceOutbox` delta was zero; no Helpdesk payload was present in the Gateway command. |

The lifecycle repair is deliberately local and idempotent: it requires an
already-succeeded Endpoint link, a stored safe result, existing succeeded
evidence, and no active diagnostic steps. It does not call Endpoint, create an
operation, change a ticket, or create evidence.

## Rollback and smoke

The approved pre-canary configuration snapshots were restored:

- `ENDPOINT_PORT_MODE=unavailable`;
- `ENDPOINT_DIAGNOSTIC_EXECUTION_MODE=legacy`;
- `ENDPOINT_OPERATIONS_API_ENABLED=false`.

The Endpoint Operations route returned HTTP 404 after rollback; strict-TLS
health checks for Helpdesk and Endpoint returned `ok`. Canary service
credentials were revoked through the Endpoint credential service and its
append-only audit boundary. CA directory/file permissions were restored to
`0700 root:root` and `0600 root:root`.

## Evidence package

The protected, staging-host-only evidence package is located at:

`/var/lib/helpdesk-staging/canary-evidence/alt-headless-v1-r3-20260823`

It includes redacted preflight, mapping, execution, repair deployment,
repeat-reconciliation, Gateway delivery, invariants, rollback and summary
records. `SHA256SUMS` covers 26 files and was verified with zero failures.

## Scope boundary

This acceptance covers only the named staging services, databases, and ALT
agent. It did not deploy to, migrate, or modify production services or
production databases.
