# Windows Headless Agent Staging Canary — acceptance

**Status:** accepted after rollback
**Canary date:** 2026-08-25
**Report date:** 2026-08-26
**Scope:** isolated Helpdesk/Endpoint staging and the dedicated Windows agent
**Helpdesk diagnostic runtime:** `80ed96e79fad1fad80093c8107b44a9ba0addfe1`
**Post-canary tooling runtime:** `b338b5886b1069bffc92edf4990b090fda5987c3`

This is a redacted acceptance record. It does not contain passwords, bearer
tokens, cookies, private keys, raw command output, full diagnostic payloads,
or ticket/device identifiers. The earlier `blocked` and `failed` records are
historical results of preceding attempts; this record covers the subsequent
immutable Windows release and successful bounded run.

## Plan completion

| Stage | Result | Safe evidence |
| --- | --- | --- |
| Staging boundary and approved hosts | Complete | Only the isolated staging Helpdesk, Endpoint, and dedicated Windows VM were used; production was not changed. |
| Immutable Windows agent release | Complete | Endpoint revision `90261822b6abb77ec5ee4e9ed8a9c5178d39e9bb`; agent version `3.2.27`; MSI identity and SHA-256 were checked by the Windows preflight. |
| Installed-agent preflight | Complete | `EndpointAgent` and `EndpointAgentUpdater` identities, protected service state, strict TLS, Gateway WSS, and the bounded capability were accepted. |
| Mapping and one diagnostic request | Complete | One verified mapping and exactly one bounded `context.diagnostic.collect` request were performed. |
| End-to-end result | Complete | One local operation, one linked Endpoint operation, and one Helpdesk diagnostic evidence item reached the required succeeded/safe state. |
| Exactly-once and invariant checks | Complete | Repeat reconciliation produced no duplicate operation, link, or evidence; no legacy fallback was used. |
| Rollback and credential cleanup | Complete | Endpoint operations were disabled; Helpdesk returned to unavailable/legacy mode; temporary canary access was revoked and temporary environment data removed. |
| Evidence package | Complete | The protected redacted package contains 21 files; `SHA256SUMS` verification passed. |
| Post-canary TLS tooling repair | Complete | Helpdesk canary client revision `b338b5886b1069bffc92edf4990b090fda5987c3` trusts the configured internal CA while retaining certificate, hostname, and redirect protections. |

## Required safe acceptance values

| Field | Recorded value |
| --- | --- |
| Helpdesk revision during the successful diagnostic operation | `80ed96e79fad1fad80093c8107b44a9ba0addfe1` |
| Post-canary Helpdesk tooling revision | `b338b5886b1069bffc92edf4990b090fda5987c3` |
| Helpdesk database revision | `138` |
| Endpoint database revision | `0014_endpoint_operations` |
| Windows MSI version | `3.2.27` |
| Windows MSI SHA-256 | `805ccc722c925ab4dc4e97e08454dad1bf5b79f706e328d8f423bcc410582ef1` |
| `EndpointAgent` account / start mode | `NT AUTHORITY\\LocalService` / `Automatic` |
| `EndpointAgentUpdater` account / start mode | `LocalSystem` / `Manual` |
| Local operation count | `1` |
| Remote Endpoint operation count | `1` |
| Helpdesk evidence count | `1` |
| Initial `Ticket.status` | not present in the redacted acceptance record; retained in protected evidence |
| Final `Ticket.status` | not present in the redacted acceptance record; retained in protected evidence |
| `DeviceOutbox` delta | not present in the redacted acceptance record; retained in protected evidence |

## Agent, transport, and execution facts

- The Windows service preflight accepted the immutable `3.2.27` package and
  exact Endpoint source revision before any mutable stage.
- The diagnostic used the Endpoint Gateway WSS path and the bounded
  `context.diagnostic.collect` capability.
- The final verification found exactly one succeeded local operation, one
  succeeded Endpoint operation with a safe result, and one
  `endpoint_platform` Helpdesk evidence record.
- Ticket state was preserved. The execution did not use Helpdesk legacy agent
  dispatch, `DeviceOutbox`, or `ToolService` fallback.
- The redacted acceptance record does not retain initial/final `Ticket.status`
  or a numeric `DeviceOutbox` delta. These values are retained in the
  protected evidence and are not reconstructed here.
- The additional read-only TLS validation reached the Helpdesk HTTP
  authentication boundary using the internal CA. An unauthenticated response
  was expected; no new token, mapping, or operation was created for that
  validation.

## Rollback and current staging state

Rollback was completed without database downgrade. Temporary canary
credentials and local environment data were removed. The immutable evidence
package remains protected at
`/var/lib/helpdesk-staging/canary-evidence/windows-20260825/canary-report-windows-canary-20260825`.

| Evidence archival field | Status |
| --- | --- |
| Protected evidence path | `/var/lib/helpdesk-staging/canary-evidence/windows-20260825/canary-report-windows-canary-20260825` |
| Number of files | `21` |
| `SHA256SUMS` verification | verified, zero failures |
| Off-host encrypted backup | `pending` — not present in the redacted acceptance record; retained in protected evidence |
| Off-host archive SHA-256 | `pending` — not present in the redacted acceptance record; retained in protected evidence |

Evidence archival is not complete until the pending off-host encrypted backup
has been recorded with its archive SHA-256.

## Operator action item — evidence archival (pending)

Create an encrypted off-host copy of the protected evidence package, verify
its archive SHA-256 after transfer, and update this acceptance record with the
backup location class, completion status, and checksum. Do not copy evidence,
credentials, raw results, or the archive itself into Git.

The post-canary tooling release was deployed as immutable staging release
`helpdesk-b338b5886b1069bffc92edf4990b090fda5987c3`. Its strict internal-CA
validation was confirmed before the staging Helpdesk service was stopped at
the end of the remote validation window. The release and protected evidence
remain available; the service can be started through the approved staging
procedure for later work.

## Documentation and source checkpoints

| Commit | Purpose |
| --- | --- |
| `b338b5886b1069bffc92edf4990b090fda5987c3` | Canary client uses configured internal CA and rejects redirects. |
| `4cc365701a458aa01778181fe8e08b7321fa1ffc` | Runbook uses the working module invocation for the canary tool. |

No production deployment, production migration, production service
configuration, or production database was modified.
