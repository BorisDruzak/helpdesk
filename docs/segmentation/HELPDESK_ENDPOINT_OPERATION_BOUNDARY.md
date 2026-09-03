# Helpdesk Endpoint Operation Boundary

## Status

Approved and staging-accepted architectural boundary for the Helpdesk-side
counterpart of Endpoint Operations API v1. The bounded diagnostic slice has
real-agent acceptance evidence on ALT and Windows after rollback; this does
not enable any additional capability, change a route, run a migration, or
alter production state.

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
Endpoint response to echo it exactly, never places it in a JSON envelope,
remote Endpoint operation, or Gateway WSS command, and never uses it for authorization. The
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

## Release-gate evidence

The immutable provider lock names `BorisDruzak/endpoint_platform` at published
Endpoint mainline merge `54fe6b975b7e8c4dff067d01c847be1da4eb7a81`. Validation
requires that exact Git root and HEAD, a clean non-ignored checkout, a
provider-owned relative OpenAPI path, and a SHA-256 over the OpenAPI Git blob
bytes. It rejects alternate repositories, feature tips, dirty files, and
checkout line-ending differences that do not match the committed blob.

The Helpdesk endpoint-acceptance workflow runs on pull requests and pushes to
`codex/helpdesk-process-model`, and manually. It records the exact Helpdesk
and Endpoint commits, the OpenAPI digest, JUnit XML, and the fact that it uses
a real provider app, real Gateway WSS, and a protocol-compatible Gateway WSS
test client without production changes.

The vertical acceptance protects the following invariants: Helpdesk keeps the
original ticket status; terminal reconciliation creates one safe evidence row
from one remote operation; the local operation, diagnostic step and last
active diagnostic session complete; and no Helpdesk `DeviceOutbox`, legacy
WebSocket, or `ToolService` dispatch is used. The Gateway payload excludes
Helpdesk-private data. The forward-only migration rehearsal starts at revision
134, preserves representative local data through revision 137, verifies the
new local constraints/indexes and a clean `head` upgrade, and writes its
machine-readable report under `artifacts/migration/`.

## Cross-platform real-agent acceptance

The bounded `endpoint.context.diagnostic.collect` operation is accepted on the
dedicated ALT and Windows staging agents. Both runs used the Endpoint
Operations API and Gateway WSS as the only command transport and confirmed no
Helpdesk legacy agent, `DeviceOutbox`, or `ToolService` dispatch. The
redacted records are
`docs/verification/ALT_HEADLESS_AGENT_CANARY_ACCEPTANCE.md` and
`docs/verification/WINDOWS_HEADLESS_AGENT_CANARY_ACCEPTANCE.md`.

This acceptance is limited to the existing diagnostic capability and does not
authorize broad command migration. The next package is typed read-only Endpoint
capabilities, with its own contract and acceptance evidence.

## Local facade and lifecycle

For a browser request Helpdesk authorizes ticket/diagnostic access locally,
creates a deterministic local `Operation`, `DiagnosticSession` and
`DiagnosticStep`, and adds an `EndpointOperationLink` in one local database
transaction. The link owns its stable idempotency key, correlation, external
reference once bound, last safe status, retry/lease data, and evidence marker.
No HTTP call occurs inside that transaction.

A worker then creates or reads the Endpoint operation with the same idempotency
key. The local opaque correlation reference never crosses the HTTP boundary. It
may safely recover a crash after remote creation but before local binding.
Endpoint state projects to the existing Helpdesk lifecycle:

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

## Cutover boundary

Helpdesk has no legacy agent runtime, agent WebSocket, device outbox, local
command dispatch, browser pairing, or device account-session authority. Those
responsibilities belong to Endpoint Platform. Helpdesk retains only the
Endpoint operation facade, ticket workflow, web authentication/RBAC and
`/ws_ui` browser notifications.
