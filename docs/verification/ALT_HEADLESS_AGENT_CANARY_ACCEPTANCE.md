# ALT Headless Agent Staging Canary acceptance — R3

**Status:** accepted after rollback
**Date and execution window:** 2026-08-23, 09:00:48–09:01:00 UTC
**Scope:** isolated Endpoint/Helpdesk staging and the dedicated ALT agent only

This is a redacted acceptance record. It excludes passwords, bearer tokens,
cookies, private keys, raw logs, raw agent result, complete environment files,
and database dumps.

## Revisions and release evidence

| Surface | Evidence |
| --- | --- |
| Endpoint provider | `1562af5c00e91f22ed9a7d8d120ce221fea82437` |
| Helpdesk before R3 | `1dbd5ea3bc096d94f1328a182410fc6fc58afd81` |
| Helpdesk lifecycle repair | PR [#12](https://github.com/BorisDruzak/helpdesk/pull/12), merge `eabf0cb58787da02e752bbfc09388ce5b79b41a6`; acceptance CI passed in 2m22s |
| Helpdesk staging release | immutable selector `helpdesk-eabf0cb58787` |
| Documentation acceptance | PR [#13](https://github.com/BorisDruzak/helpdesk/pull/13), merge `a5889ea2fa7e6a70eff9b0588db5acbcebe333d2`; acceptance CI passed in 1m44s |
| Database revisions | Helpdesk `137`; Endpoint `0014_endpoint_operations` |

The repair flushes a terminal diagnostic step before checking active steps and
has an idempotent recovery path for an already-terminal link. It does not call
Endpoint, change a ticket, create an operation, or create evidence.

## Agent and transport

| Criterion | Evidence |
| --- | --- |
| Platform and version | `linux_amd64`, `endpoint-agent-3.2.16-alt1.x86_64` |
| Agent source revision | `1562af5c00e91f22ed9a7d8d120ce221fea82437` |
| Active service | `endpoint-agent.service` active, MainPID recorded during the canary |
| Unit identity | `/usr/lib/systemd/system/endpoint-agent.service`, SHA-256 `79fa26755122d5eedd91210fe800e4d903dc63dba44212922d12df1322d527f9` |
| Immutable executable | installed RPM owns the launcher and unit; active artifact is version `3.2.16` |
| Transport | `gateway_wss` |
| HTTP migration fallback | packaged launcher includes `--no-migration-http-pull-fallback` |
| Strict TLS | Helpdesk and Endpoint health both returned `ok` with the staging CA and hostname validation |

## Exactly-once execution

| Item | Value |
| --- | --- |
| Safe device reference | `7ec6d3a4-b30b-43eb-944e-f81fe8933300` |
| Safe ticket reference | `33dea19e-4cce-4194-8d01-e9b532a3feb1` |
| Helpdesk diagnostic request | exactly one; HTTP `202` |
| Local operation | `6cc85394-e1f0-50d1-bbb9-fb95480e514f` |
| Remote operation | `d411cf09-8a25-4b41-8f39-48069c10297a` |
| Capability / duration | `context.diagnostic.collect`; 12 seconds |
| Gateway delivery / agent completion | one delivery, one result, marker `result-f176eeafdfbc49b5a29fbd040c98b96f`, digest present |
| Final states | local and remote operations `succeeded`; step and session `completed` |
| Safe evidence | exactly one `DiagnosticEvidence` |

The scoped service bearer had only `devices.read`, `operations.create`, and
`operations.read`. Verified ticket-device mapping created the required
`TicketAdminAudit` entry; a rejected preflight attempt remains separately
audited and did not create a mapping or operation.

## Invariants

- Ticket status was `queued` before and after the canary.
- The repeat reconciliation created no duplicate operation, link, or evidence.
- `DeviceOutbox` was 0 before and after (delta 0).
- The endpoint diagnostic path used no legacy Helpdesk WebSocket or ToolService
  dispatch; the deployed boundary guard and CI cover those imports.
- The Gateway command contained only the permitted `reason` parameter and no
  Helpdesk payload fields.
- No secret is present in the evidence package.

## Rollback and smoke

Approved snapshots were restored without database downgrade:

- `ENDPOINT_PORT_MODE=unavailable`;
- `ENDPOINT_DIAGNOSTIC_EXECUTION_MODE=legacy`;
- `ENDPOINT_OPERATIONS_API_ENABLED=false`.

The Endpoint Operations route returned HTTP 404 after rollback. Canary service
credentials were revoked through the Endpoint credential service and
append-only audit boundary; active canary credentials are 0. CA permissions
were restored to `0700 root:root` for its directory and `0600 root:root` for
the certificate. Endpoint and Helpdesk strict-TLS smoke both returned `ok`.

## Protected evidence hashes

The protected package is
`/var/lib/helpdesk-staging/canary-evidence/alt-headless-v1-r3-20260823`.
`SHA256SUMS` covers 26 files and passed verification with zero failures.

| File | SHA-256 |
| --- | --- |
| `SHA256SUMS` | `bd2987b8d7db122d324fe58d2c5e206fd66a21ff55adb12dac6e7570bc0b798e` |
| `manifest.json` | `f7fe8f8ccecceb68b58df609290f3efc95bc6b25fc9e27c0d5e864a3bcb71bd4` |
| `summary.json` | `2fc3763be04f2a299c0c464f039a785f2673dc86d51284e2c607238c2453bd1a` |
| `invariants.json` | `4e2bbf96335674c76dd6635f7623c49b36f219a90281a914e243b164df6a4089` |
| `rollback.json` | `34edd6ab52c1d30e846dc47ab61419a3ed7dfe855b22148a98128098f4c1b08c` |

## Boundary statement

No production deployment, migration, service configuration, or database was
modified. Staging services and the ALT agent remain active after the final
health checks for follow-up testing.
