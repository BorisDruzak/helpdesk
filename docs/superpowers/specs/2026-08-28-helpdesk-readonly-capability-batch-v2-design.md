# Helpdesk Read-only Capability Batch v2 Design

**Status:** approved and implemented; the Endpoint v2 contract merge SHA and OpenAPI digest are pinned.

## Ownership and flow

Endpoint owns capabilities, parameter/result schemas, recipes, parent/child
operations, Gateway WSS and agent execution. Helpdesk owns web authorization,
actor audit, ticket-local facade operations, the operation link and one safe
diagnostic evidence item. The browser calls the Helpdesk BFF only; Helpdesk
never sends an agent command.

The allowed path is Endpoint registry → `GET /api/v1/module-capabilities` →
typed `EndpointModulePort` → Helpdesk BFF → dynamic Workbench → immutable
recipe → local facade → Endpoint operation → Gateway WSS → typed bounded
result → closed Helpdesk projector → one evidence item.

## HD1

`EndpointModulePort.list_recipe_capabilities()` returns an immutable,
fail-closed `endpoint_module_capability_catalog_v1` DTO. The HTTPS adapter may
call only `GET /api/v1/module-capabilities`; it validates exact IDs, parameters,
platforms, safe-read risk, `consent_required=false`, `secret=false`, bounds and
schema versions. It never exposes handler/source paths, commands, services,
policy internals or credentials.

A closed projector registry accepts only `dns.resolve`, `network.ping`,
`tcp.connect`, `route.get`, `adapter.list` and `system.service_status` with
their exact result schemas. It returns only approved summaries and writes new
`endpoint_module_result_snapshot_v2` records. V1 snapshots remain readable and
historical evidence is not rewritten.

## HD2 and HD3

HD2 removes the Workbench `CAPABILITIES` constant and renders parameter/input
bindings from BFF catalog DTOs. `adapter.list` has no controls;
`system.service_status` is a literal-only logical-service-key select. Templates
remain declarative, including six-step `endpoint.readiness.check@1.0.0`.

After real ALT/Windows canaries and rollback, HD3 updates the migration matrix,
adds the redacted usage report and applies `LEGACY_MODULE_FREEZE_KEYS` only to
new legacy version/preferred/rollout/new-install actions. Existing audit,
removal, deactivation and rollback remain; no legacy source, route, table or
installed package is removed.

## Gates

The Endpoint PR-EP1/EP2 merge SHA and OpenAPI digest must be locked before HD1
or HD2. Cross-repository acceptance uses the real provider, PostgreSQL, Gateway
WSS and compatible agent. Each staging canary proves exactly one local
operation, link, remote parent, six terminal children and evidence item, with
zero Ticket status, DeviceOutbox, ToolService or legacy-WebSocket delta.
