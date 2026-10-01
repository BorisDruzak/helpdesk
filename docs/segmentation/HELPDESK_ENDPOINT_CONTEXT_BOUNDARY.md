# Safe Endpoint Context port

Endpoint Platform owns technical identity, presence and all normalized device
observations. Registry owns business assets, exact verified device mappings and
active person bindings. Helpdesk consumes technical data only through
`domain_ports.endpoint.EndpointPort` and `endpoint_adapter` using verified HTTPS.
It does not import provider source at runtime, use the provider database or fall
back to Helpdesk telemetry.

## Contract

The immutable lock is `integration/endpoint_contract.lock.json`: provider
38ddabe3c0badf09a033bb7523a89a7d2c5059a0, published and merged via Endpoint PR 40.
Canonical OpenAPI SHA256:
27425c76c95874606330ad282c66689b25e3bb95666d657cfe712e8e0d1ac137.
The fleet route is `GET /api/v1/devices/context-summary`, bounded to 250,
UUID keyset paginated, with no device-detail fanout. Detail is an exact UUID read.

The port exposes `list_device_fleet`, `read_device_context`,
`request_context_collection`, `read_context_collection`, `list_context_history`
and `compare_context_snapshots`. Frozen DTOs contain bounded tuple collections;
section variants match the five safe profiles. Diagnostic/activity profiles and
raw transport payloads are excluded. History permits baseline/inventory only.

Required service scopes are `devices.read`, `context.read`, `context.collect`,
plus existing independently accepted binding/operation scopes. Service credential
rotation must preserve existing scopes, be audited, support rollback, and revoke
the obsolete credential only after acceptance. Never expose credentials to the
browser or evidence.

HTTP failures remain typed unavailable/unauthorized/forbidden/not-found/invalid
projections. An unavailable projection is UNKNOWN; OFFLINE is only a valid
provider boolean. Redirects are rejected, timeouts and streamed response bytes
are bounded. Context GET accepts only 200, creation accepts 200/201.

## Verification

Focused adapter tests exercise transport, immutable projections, identity
mismatch, response bounds, unsafe profiles and errors. The true cross-repository
acceptance workflow checks the pinned clean provider and exact OpenAPI bytes,
starts its real routes with isolated migrated PostgreSQL, and exercises fleet,
detail, collection idempotency/read, history and compare. These fixtures are
contract evidence; they do not substitute for real Windows/browser staging
acceptance of the full cutover.

The implementation plan is
`docs/superpowers/plans/2026-10-01-admin-endpoint-cutover.md`. Legacy runtime
retirement, UI cutover, production read-only metadata audit and staging evidence
must finish before the coordinated task can be called complete. Production
deployment and automatic table deletion are excluded.
