# Helpdesk Endpoint Operation Boundary

## Status

Approved architectural target for the Helpdesk-side counterpart of Endpoint
Operations API v1. This document defines the boundary before implementation;
it does not enable a remote adapter, change a route, run a migration, or alter
production state.

## Purpose

The first external Endpoint vertical slice is deliberately limited to:

`endpoint.context.diagnostic.collect` (Helpdesk) →
`context.diagnostic.collect` (Endpoint Platform).

It must reach the headless Endpoint Agent only through Endpoint Platform's
versioned Operations API and Gateway WSS. Helpdesk remains fully functional
when that service is unavailable.

## Ownership and data boundary

| Concern | Canonical owner | Helpdesk responsibility |
| --- | --- | --- |
| Ticket, diagnostic session/step/evidence, workflow, approval facade, UI, web auth/RBAC, `/ws_ui` | Helpdesk | Owns and persists it |
| Endpoint operation, Gateway WSS, command queue, ACK/result lifecycle, device credential, agent presence, raw device context, update lifecycle | Endpoint Platform | Consumes only a safe, versioned projection |
| Local `Operation` | Helpdesk | Ticket-facing facade and local lifecycle projection |
| Remote operation reference | Endpoint Platform | Opaque external reference retained in a Helpdesk link |

Helpdesk must not import Endpoint Python modules, query an Endpoint database,
create Endpoint credentials, parse an external reference, or use Endpoint
correlation for authorization. There is no cross-service database foreign key.
The Endpoint Agent must not receive `ticket_id` or any other Helpdesk entity.
`X-Correlation-ID` is a transport-only tracing header: Helpdesk requires the
Endpoint response to echo it exactly, never places it in a JSON envelope, and
never uses it for authorization. It never reaches a Gateway WSS command. The
durable Endpoint idempotency key is exactly
`helpdesk-endpoint-operation:<local-operation-id>`; the browser caller key is
stored only with the actor that supplied it and never leaves Helpdesk.

## Required integration surface

The existing `server/domain_ports/endpoint.py::EndpointPort` is the only
Helpdesk boundary. It is extended, never replaced by a second port, with typed
versioned operations for availability, device/capability projections, and
`create_operation` and `read_operation`. Reconciliation is driven from
Helpdesk's durable local links; it does not add an Endpoint operation-list API.

The concrete adapter is `ExternalEndpointHttpAdapter` under
`server/endpoint_adapter/`. It calls only HTTPS Endpoint Operations API v1 with
a service bearer, internal CA bundle, bounded timeout, redirects disabled, and
redacted structured telemetry. It returns typed outcomes only: `available`,
`unavailable`, `invalid_projection`, `unauthorized`, `forbidden`,
`not_found`, or `conflict`; raw HTTP bodies never escape the adapter.

Endpoint API integration targets are not Helpdesk routes:

| Method | Endpoint API v1 target | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/devices/{endpoint_device_ref}` | Exact device projection |
| `GET` | `/api/v1/devices/{endpoint_device_ref}/capabilities` | Capability projection |
| `POST` | `/api/v1/devices/{endpoint_device_ref}/operations` | Idempotent external creation |
| `GET` | `/api/v1/operations/{endpoint_operation_ref}` | Safe operation projection |

`EndpointPort.availability()` is a local configuration projection. It never
issues an Endpoint Operations API request and must not introduce a health or
availability route.

The actual adapter implementation must verify this route table against the
read-only Endpoint Platform contracts and committed schemas before coding.
It parses a strict provider-owned wire DTO (including the provider's canonical
diagnostic wording) and maps it to the localized internal port DTO; unknown
fields, mismatched IDs, correlation mismatch and an unaccompanied succeeded
result fail closed.

## Cross-repository acceptance database boundary

The special cross-repository acceptance test starts the real Endpoint factory
with a disposable loopback PostgreSQL database. It applies the Endpoint
Alembic head before seeding test-only credentials and drops that database after
the WSS/evidence flow. The Helpdesk side uses its independently migrated
temporary PostgreSQL database. SQLite is not an acceptance backend for either
side of this contract.

## Local facade and lifecycle

For a browser request Helpdesk authorizes ticket/diagnostic access locally,
creates a deterministic local `Operation`, `DiagnosticSession` and
`DiagnosticStep`, and adds an `EndpointOperationLink` in one local database
transaction. The link owns its stable idempotency key, correlation, external
reference once bound, last safe status, retry/lease data, and evidence marker.
No HTTP call occurs inside that transaction.

A worker then creates or reads the Endpoint operation with the same idempotency
key. It may safely recover a crash after remote creation but before local
binding. Endpoint state projects to the existing Helpdesk lifecycle:

| Endpoint state | Helpdesk `Operation` / diagnostic step |
| --- | --- |
| `queued` | `queued` |
| `delivered` | `sent` |
| `acknowledged` | `accepted` |
| `running` | `running` |
| `succeeded` | `succeeded` |
| `failed` | `failed` |
| `canceled` | `canceled` |
| `expired` | `timed_out` |

Terminal states are immutable. On terminal Endpoint success, Helpdesk applies
its own redaction to the already-safe response, bounds all fields, and writes
exactly one `DiagnosticEvidence` row keyed by
`(source_type="endpoint_platform", source_id=endpoint_operation_ref)`. It
does not change `Ticket.status` or close a ticket/session unless existing
session-completion rules permit the last active step to complete.

## Cutover and failure policy

`ENDPOINT_DIAGNOSTIC_EXECUTION_MODE=legacy` is the default. In that mode the
new capability is disabled and no Endpoint operation worker creates remote
operations. `endpoint` mode enables only the new capability and is fail-closed:
remote errors never call `ToolService`, Helpdesk agent WebSocket, or
`DeviceOutbox`; a user operation may never dispatch both legacy and Endpoint
commands. Rollback is an explicit configuration change followed by a normal,
verified Helpdesk deployment. Existing external operations remain
reconciliation/read-only work until terminal; they are never rewritten as
legacy commands.

Endpoint outage is represented as a typed degraded state and may prevent this
technical diagnostic from starting, but must not prevent ticket creation,
routing, correspondence, specialist work, closure, or any unrelated legacy
capability. Endpoint offline is not itself a readiness failure because an
external operation may remain queued until the agent reconnects.

## Security and UI rules

Browser input carries no Endpoint device reference, correlation, reason, or
arbitrary parameters. The capability has an empty object parameter schema.
Only the admin-only `PUT /api/admin/tickets/{ticket_id}/endpoint-device-mapping`
may persist `endpoint_device_ref`. It performs an exact Endpoint device read,
stores an immutable `endpoint_device_snapshot_v1`, and readiness calls the
same reference service before exposing the capability. There is no
hostname/IP/MAC matching, legacy `Ticket.device_id` fallback, or client
override. Revision `137` adds the partial unique
`(caller_actor_id, caller_idempotency_key)` constraint for caller idempotency.

The existing diagnostics workspace gains only source and state presentation:
Endpoint Platform; queued/delivered/accepted/running/terminal states; a safe
temporary-unavailable message; mapping-missing guidance; and offline queue
guidance. Service token, base URL, CA path, raw response/command, credential,
WSS session and stack traces are never shown. The opaque external operation
reference is available only in authorized advanced service details.

## Explicit non-goals

This slice neither migrates all `run_tool` paths nor removes the legacy agent
runtime. It does not move managed modules, recipes, scheduler, consent, Remote
Assist, agent update/build/rollout, Registry, Knowledge, device tables, browser
pairing, or `/ws_ui`; it does not deploy, run a production migration, change
service credentials, or roll out an agent.
