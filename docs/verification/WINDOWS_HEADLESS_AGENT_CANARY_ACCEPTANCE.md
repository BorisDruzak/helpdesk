# Windows Headless Agent Staging Canary — acceptance

**Status:** accepted after rollback
**Canary date:** 2026-08-25
**Report date:** 2026-08-26
**Scope:** isolated Helpdesk/Endpoint staging and the dedicated Windows agent

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
- The additional read-only TLS validation reached the Helpdesk HTTP
  authentication boundary using the internal CA. An unauthenticated response
  was expected; no new token, mapping, or operation was created for that
  validation.

## Rollback and current staging state

Rollback was completed without database downgrade. Temporary canary
credentials and local environment data were removed. The immutable evidence
package remains protected at
`/var/lib/helpdesk-staging/canary-evidence/windows-20260825/canary-report-windows-canary-20260825`.

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
