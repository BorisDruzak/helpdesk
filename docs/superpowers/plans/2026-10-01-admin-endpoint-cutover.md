# Admin Device & Inventory Endpoint Cutover v1 Implementation Plan

> Execute inline with superpowers:executing-plans. The user supplied the full architectural spec and explicitly requested execution.

**Goal:** Replace every active Helpdesk device telemetry surface with Endpoint technical projections and canonical Registry relationships.

**Architecture:** Browser → authenticated Helpdesk BFF → immutable EndpointPort → verified HTTPS Endpoint service API. Registry overlays resolve exact RegistryEndpointDeviceMapping; no hostname/UUID assumption, telemetry fallback, dual write or scheduler.

**Spec:** User attachment `pasted-text-1.txt`, Admin Device & Inventory Endpoint Cutover v1, sections 1–63.

**Starting revisions:** Helpdesk c935a532657786ae00ab9c9de1dbd34624b1b143; Endpoint 4a8258deace4fa09becdc8e27e4d344d1d1767a7. Helpdesk includes subsequent Sonar remediation; preserve it and unrelated untracked scanner files.

## Source ownership

| Fields | Authority | Current replacement boundary |
|---|---|---|
| identity, presence, last contact | Endpoint Device/DeviceSession | service device projection |
| OS, hardware, RAM, storage | Endpoint inventory_v1 | safe typed sections |
| software | Endpoint baseline_v1 | safe typed sections |
| network, health, session | Endpoint profiles | safe typed sections |
| profile freshness/history/collection | Endpoint Context | current/history/collection APIs |
| person, relationship, department, location, inventory number | Registry | exact mapping, asset, active binding, person |
| Helpdesk Device | compatibility identity only | tickets/Registry FK; no live telemetry authority |
| legacy inventory/presence/binding tables | inert historical storage | retention report; no automatic drop |
| Agent version | canonical provider only | omit unless exact provider contract supplies it |

## Constraints and review focus

- Production deployment and destructive migrations are prohibited by the supplied task.
- Preserve diagnostic consent/policy, possession flow, tickets and Registry relationships.
- Safe profiles: baseline_v1, inventory_v1, health_v1, network_v1, session_v1. History: baseline_v1/inventory_v1.
- Endpoint outage is UNKNOWN; unknown device URL never selects another device.
- Fleet uses bounded provider page and bulk Registry reads; expose pagination explicitly.
- Reject identity/profile mismatches, malformed sections, duplicate identities, oversize responses and redirected transport.
- Partial profiles and unmapped devices must remain visible.
- Per-profile collection failures remain visible; server creates idempotency keys.
- Existing active business values must never be overwritten from historical metadata.

## Execution tasks

- [x] A Provider: add paginated GET /api/v1/devices/context-summary under devices.read + context.read in endpoint_server/context/routes.py, with focused DTO/projection module. Bulk session/current/collection queries, deterministic UUID order, inventory_summary nullable. Tests in tests/context/test_service_api.py cover no context, partial context, online/offline/retired, scopes, bounds and raw exclusion. Generate canonical OpenAPI with existing tools; full exact-SHA CI before provider merge/pin.
- [x] B Adapter/domain: server/domain_ports/endpoint.py + focused context DTO module; server/endpoint_adapter/wire.py/http.py; unavailable port. Implement fleet, exact detail, refresh, collection, history and compare. Port returns typed failure; preserve HTTPS/size/timeout/redirect safeguards. Add adapter regressions including mismatch and no fallback.
- [x] C BFF: server/web_api/endpoint_device_handlers.py and server/routes.py; bulk Registry overlay service. Register fleet/detail/refresh/collection/history/compare. Read roles admin/support/auditor; mutation admin; existing CSRF/auth middleware. PostgreSQL overlay + route registration + refresh validation tests.
- [x] D UI: focused endpoint-devices API/types/components; replace inventory-page.tsx and device-page.tsx. Admin primary job: find a device and inspect exact authoritative context. List/detail archetype, primary refresh, secondary Registry/history. Metrics/filter/pagination, UNKNOWN errors, independent freshness and collection lifecycle; typed tabs without raw JSON. Replace legacy client callers/tests and navigation.
- [x] E Runtime retirement: remove legacy inventory/presence API registration/handlers/services and scheduler config where valid. Remove Registry side reads/writes of legacy binding/presence; preserve canonical business operations. Audit ticket/Tech/AI indicators. Permanent production-source boundary guard and actual BFF route parity tests, CI integration.
- [x] F Evidence/docs: retirement manifest with readers/writers/FKs/retention blockers and production read-only aggregates/reconciliation export. No table drop or automatic business overwrite. Update architecture/docs/CODEMAP and PLANS.
- [x] G Acceptance: focused tests then full suites, cross-contract pin/acceptance, exact-SHA CI, live staging browser with real Windows Endpoint device and outage/refresh/history/Registry. Restore staging state and stop test services; no production deploy. Review final full diff before publication; report exact receipts and every unverified gate honestly.

## Verification ledger

Discovery: GitNexus group status reports all members indexStale=false, contractsStale=false, commitsBehind=0, missingRepos=[]; source verifies existing support presence and absence of inventory fleet projection. Legacy Registry coupling exists in registration_service/admin_operations_service/service and must be removed explicitly. No implementation gate passed yet.

2026-10-01: A-F implementation and production read-only metadata audit complete; retirement review/tests ongoing. G full frozen-SHA CI and staging acceptance pending. No production deployment.


### Staging checkpoint after a61f0011

Exact-SHA full CI 36843043522 passed all 18 canonical layers, with isolated
PostgreSQL and no shared database fallback. Contract acceptance passed 269
integration guards and 3 real provider/Gateway/Helpdesk scenarios.
Trusted HTTPS browser acceptance rendered the actual Windows device ONLINE,
completed all five safe collections, compared two real baseline snapshots,
composed the exact Registry mapping and temporal primary-user overlay, and
applied a Registry department edit through preview/apply with audit evidence.
Stopping the Windows service produced OFFLINE; restarting and rereading produced
ONLINE. Stopping Endpoint produced HTTP 503 and UNKNOWN with no stale technical
panel. Normal scenarios recorded zero console/page errors, retired requests,
and direct browser-to-Endpoint requests. Controlled unknown-device 404 and
provider-outage 503 resource messages are recorded separately.

Acceptance found a Registry navigation defect: the snapshot queried verified
mappings but omitted them from asset rows. The bounded mapping projection now
exposes `endpoint_device_ref`; unmapped assets remain disabled without identity
inference. A PostgreSQL regression covers different local/Endpoint UUIDs and
an unmapped asset with the same business name. Final-SHA CI and browser
revalidation remain required before G is complete. The installed Windows agent
also emits replacement characters for the session login; the provider response
already contains them. This upstream observation quality issue must be reported
without substituting a Registry identity.


### Final runtime acceptance 35c67c40

Full CI 36848506139 passed all 18 canonical layers / 18 logs with no shared DB fallback;
real pinned-provider/Gateway WSS/Helpdesk acceptance: 3 passed, 0 skipped. Real trusted
staging Windows, expanded page controls, completed five collections, actual
history/hash/diff, exact Registry PC link and canonical preview/apply/audit,
OFFLINE / reconnect ONLINE and provider-outage UNKNOWN all verified. Normal errors/
retired/direct-provider requests: 0. Original both databases/releases / configs / scopes / Windows
enrollment restored, three units/Agent stopped. Final independent review clean;
30 focused checks passed. Draft PR39 base c935 excludes unrelated Sonar changes.
Final documentation and navigation labels frozen SHA full CI / staging revalidation and 63-item delivery
report remain; production untouched and no destructive migration.
