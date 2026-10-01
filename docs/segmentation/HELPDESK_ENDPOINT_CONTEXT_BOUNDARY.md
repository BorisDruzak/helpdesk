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

## Authenticated browser BFF

Read roles: admin/support/auditor. Refresh roles: admin/support. Existing web
session authentication and same-origin CSRF middleware apply; service tokens
never cross this boundary. All responses are no-store.

- `GET /api/web/admin/endpoint/devices`: one provider fleet request and two
  Registry column-only queries for up to 250 exact mapped UUIDs. Unmapped
  devices remain visible; Registry failure is explicit and never alters
  Endpoint presence. Pagination uses the provider UUID cursor.
- `GET /api/web/admin/endpoint/devices/{device_id}`: exact provider UUID read;
  malformed UUID is 400, missing device is 404, no first-device substitution.
- `POST .../{device_id}/context/refresh`: one to five unique safe profiles;
  server-generated bounded idempotency key per profile. Returns individual
  collection/error outcomes and requested/partial/failed aggregate state.
  Request acceptance is not collection completion.
- `GET /api/web/admin/endpoint/context/collections/{collection_id}`: actual
  provider lifecycle projection. Browser polling must reread context after
  completed and preserve failed/expired outcomes.
- `GET .../{device_id}/context/history`: baseline/inventory, limit 1..100.
- `GET .../{device_id}/context/compare?before=UUID&after=UUID`: typed safe diff.

`registry/endpoint_device_overlay.py` joins only confirmed
RegistryEndpointDeviceMapping -> RegistryAsset and temporally active
DeviceUserBinding -> RegistryPerson -> department/location. It never guesses a
mapping by local UUID equality or hostname. Asset and person departments are
kept distinct. The first six deterministic active bindings are returned with
an explicit truncation flag; no historical presence or inventory table is read.
Canonical business edits remain in Registry preview/apply/audit flows.

## Browser devices workspace

`/app/admin/inventory` is the Devices fleet view. It uses one paginated BFF
read; page-level metrics/search/status/department filters are explicitly scoped
to that page. Unmapped Endpoint devices remain visible. Links contain the exact
Endpoint UUID. Loading and provider failure do not produce false offline counts.

`/app/admin/device?device=UUID` reads that exact device only; invalid/missing or
unknown UUID never selects the first fleet item or rewrites the URL. Tabs appear
only for actual safe observations: overview, system, network, baseline software,
health, session, supported history and Registry. Observed Endpoint login and
Registry person relationships are kept distinct. No Agent version, printers,
daily presence or module data is invented.

`endpoint-context-api.ts` is the same-origin client; `endpoint-context-types.ts`
mirrors bounded safe BFF DTOs. Read requests consume React Query AbortSignal.
Collection refresh is visible above profile content, allows at most five safe
profiles, sends no service token or provider idempotency key from the browser,
and preserves partial/failed requests. Polling is bounded to two minutes per
collection, stops at completed/failed/expired or read failure, and can be retried
explicitly. Completed rereads exact context, fleet and history. Historical diffs
are reset whenever the selected snapshot pair changes.

Legacy device workspace/panel and browser API methods for connections, tokens,
local inventory collection/bindings/policy/export, local archive and cleanup
have been removed. Registry edits use the existing canonical Registry page.
Unit/contract tests and production build do not replace final real staging
browser acceptance; the coordinated task remains active until that evidence and
runtime retirement are complete.


Admin Device cutover retirement: local inventory/presence services and admin routes
are removed. Ticket safe context uses EndpointDeviceContext + RegistryDeviceOverlay.
Registry business asset creation uses RegistryRepo.ensure_device_asset with no
telemetry ingestion. Registry links require exact RegistryEndpointDeviceMapping.
Observer/Tech legacy timestamp, policy, scheduler and baseline signals are retired.
Historical tables remain inert. See
`docs/segmentation/ADMIN_DEVICE_INVENTORY_RETIREMENT_V1.md` for counts, ownership,
removed reader/writer matrix, retention blockers and acceptance status.
