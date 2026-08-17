# Helpdesk Endpoint Integration v1 Design

## Status

Approved. This design captures the supplied Helpdesk-side counterpart to
Endpoint Operations API v1. Endpoint Platform remains read-only for this work;
its DTOs, JSON Schemas and Operations API are contract sources only.

## Goal

Deliver one safe, asynchronous diagnostic vertical slice:

```text
Support Diagnostics → Helpdesk capability → EndpointPort → Endpoint Operations API v1
→ Endpoint Gateway WSS → headless Endpoint Agent → safe result
→ Helpdesk evidence → ticket workspace
```

The Helpdesk capability is `endpoint.context.diagnostic.collect`; the external
capability is exactly `context.diagnostic.collect`.

## Architecture decision

Helpdesk owns ITSM state and UI. Endpoint Platform owns all endpoint-agent
control-plane state and execution. Helpdesk stores one local facade operation,
an opaque remote reference, and a safe historical result snapshot. It invokes
only a versioned service API through the existing `EndpointPort`; it does not
dispatch an agent command by Helpdesk WebSocket or `device_outbox`.

Endpoint correlations are tracing/idempotency data, never authorization data.
Helpdesk authenticates and authorizes the user/ticket locally; Endpoint
authorizes its service bearer and its own device operation independently.

## Contract shape

`server/domain_ports/endpoint.py` gains frozen Pydantic DTOs with
`extra="forbid"`:

- `OpaqueEndpointRef` (strict 1–128 character opaque transport string),
  `SafeEndpointCode` (`^[a-z0-9][a-z0-9._-]*$`), and bounded stripped
  `SafeEndpointText`;
- `EndpointDeviceRef`, `EndpointOperationRef`, availability outcomes, exact
  safe device/capability projections, correlation/request/create/read
  operation contracts, and safe terminal result projections;
- fixed capability `context.diagnostic.collect`, transport `gateway_wss`, risk
  `read_only`, no consent, and parameter schema version
  `diagnostic_collection_parameters_v1`.

All timestamps are aware. Capability lists cap at 32, process items at 64,
warning codes at 16, log excerpts at 8192, summaries/results at documented
bounded sizes. Raw context, tokens, credentials, network addresses, WSS
metadata, raw HTTP bodies and arbitrary result fields are rejected.

`EndpointPort` exposes availability, exact device/capability reads, idempotent
operation creation, and exact operation read. The HTTP adapter remains
transport-only; persistence, ticket authorization and diagnostic policy stay in
Helpdesk services.

## Persistence and recovery

Tickets gain nullable `endpoint_device_ref` and
`endpoint_device_snapshot_json`. The server resolves and verifies an exact
external device reference, then persists only its immutable redacted snapshot.
No client input, hostname, IP or MAC lookup may set it. Ticket creation remains
independent of Endpoint availability.

`endpoint_operation_links` links local operation IDs to external operation
references and carries the deterministic idempotency key, safe correlation,
lease/retry state, last projection, and one-time evidence state. A worker
performs HTTP outside a DB transaction and recovers create/bind crashes by
reusing the stable key. The new forward-only migration follows revision 134;
historical migrations and legacy tables remain unchanged.

## Diagnostics and UI

`EndpointPlatformCapabilityProvider` is selected only for
`execution_target="endpoint_operation"`. It returns local `operation_id`,
`queued`, `endpoint_operation`, `endpoint_platform`, and HTTP `202`, without
waiting for the remote terminal result. Existing targets retain their current
semantics. Readiness returns only configured, unavailable, mapping-missing, or
policy-disabled states appropriate to the configured mode.

The workspace receives a small source/state presentation change only. It shows
safe Endpoint status and queue/degraded text, never transport/security detail.

## Failure, flags, and rollback

Default configuration is unavailable Endpoint plus legacy diagnostics. Unknown
mode/configuration errors fail closed. `legacy` retains legacy behaviour;
`endpoint` prohibits automatic fallback and dual dispatch. Roll back by
changing the flag, deploying normally, stopping new creates, and reconciling
already-created external operations to terminal state. This is an application
release rollback, not an Alembic downgrade.

## Validation strategy

Contract, HTTP transport, device-reference, bridge/reconciliation, provider,
and cutover guard test modules prove typed safe data, idempotency, no outbox or
WebSocket dispatch, unchanged ticket status, terminal evidence de-duplication,
and unchanged legacy mode. Run affected diagnostics, operations, tickets,
support/requester APIs, `/ws_ui`, RegistryPort and migration regressions. A
visible workspace change additionally needs the prescribed browser evidence,
webapp test, and build.

## Exclusions

No endpoint agent runtime deletion, generic executor, proxy/ESB, direct Endpoint
DB/import integration, production deploy/migration, credential mutation, agent
rollout, or unrelated Registry/Knowledge/Remote Assist/consent/module work is
authorized by this design.
