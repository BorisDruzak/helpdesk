# Admin Device & Inventory cutover: retirement evidence

## Authority and remaining storage

Endpoint is the only technical provider. Registry owns business identity, assets,
locations, departments and temporally active person bindings. The six authenticated
same-origin BFF routes under `/api/web/admin/endpoint` expose bounded immutable
safe context; neither browser nor Helpdesk reads the Endpoint database.

The following historical Helpdesk tables remain unchanged. Their ORM definitions
and historical migrations remain solely for retention; no production runtime
reader or writer is permitted. Deletion requires a separate approved retention
and migration decision.

| Historical table | Production rows at 2026-10-01 07:21 UTC | Action |
| --- | ---: | --- |
| device_inventory_snapshots | 0 | retain inert |
| device_inventory_bindings | 1 | retain inert; exact canonical business references already exist |
| device_inventory_binding_history | 0 | retain inert |
| device_inventory_refresh_policies | 0 | retain inert |
| device_inventory_refresh_runs | 0 | retain inert |
| device_inventory_bulk_operations | 0 | retain inert |
| device_inventory_bulk_operation_items | 0 | retain inert |
| device_binding_suggestions | 0 | retain inert |
| device_presence_snapshots | 0 | retain inert |
| device_presence_daily_summaries | 0 | retain inert |

## Read-only production reconciliation

`scripts/audit_legacy_device_inventory.py` used the canonical SSH profile and only
`/etc/helpdesk/helpdesk.env`. The remote program ran from stdin, with a PostgreSQL
read-only repeatable-read transaction and 15-second statement timeout. No runtime
files, database rows, service state or configuration were modified. Production
Helpdesk was active before inspection. Deployed release remains
`helpdesk-e9c9bf37dc26af98e9da91b7d424bc4efcee7990-throttle-20260930`.

There were no foreign keys from or into the ten historical tables. The sole
binding has an exact Registry asset, exact Endpoint mapping and an exact current
person binding. There are zero inventory conflicts, zero missing destinations
for nonempty inventory numbers, zero unmatched person bindings, and zero location
or department rows requiring transfer. Inventory number, building, floor, room,
department, status, tags and notes are empty. One responsible-user string and the
person/asset/source-binding/registration-status fields are nonempty. The string
is retained in the historical row and private local metadata export; authority
comes from `DeviceUserBinding`, never this free text. No automatic copy or
canonical overwrite was performed.

Reports and private exports reside in ignored `.git/admin-cutover-retirement-audit`.
Possible credentials in notes/tags are redacted before local export. Only counts,
schema names and file hashes are printed. Raw metadata is never committed or
included in public CI artifacts. Tags/notes have no invented canonical destination.
The initial counts report SHA256 is
`fc2d7b3d5d35d60f55dfcba29056bdb784511e0215d5dd64259c5afac1efbe3a`.

## Removed production readers and writers

- Local inventory/presence services and `admin_inventory_handlers` are removed.
- Local `/api/web/admin/devices*` and `/api/web/admin/inventory*` routes are absent
  from the actual application, including cleanup/restore/binding/suggestion/export/
  refresh-policy/history APIs. New Endpoint routes are asserted present.
- Registry registration/transfer/revoke/possession no longer synchronizes or
  histories legacy bindings. Registry merge/bulk/import no longer reads or writes
  legacy bindings; the legacy inventory-mapping import type is retired.
- Registry quality no longer reads legacy presence or invents user-mismatch
  warnings. Unsupported OS/version/last-seen fields are removed from Registry UI.
- Registry asset creation stores business identity only and preserves richer
  existing rows atomically; local Agent telemetry is not ingested.
- Ticket context reads the exact verified ticket Endpoint reference, safe Context
  DTO and canonical Registry overlay. Missing mappings/provider failures remain
  UNKNOWN; no local telemetry fallback or Agent-version/update/scheduler display.
- Observer/Tech current technical state uses Endpoint or explicit UNKNOWN;
  local timestamps cannot create stale/offline signals. Local UUIDs cannot become
  Endpoint device-card links. Registry's link uses its exact verified mapping.
- Tech inventory scheduler, connection policy, Agent baseline/update/token signals
  are removed. One bounded Endpoint fleet read supplies page-scoped presence
  counts; failure produces null counts and UNKNOWN, retired devices are separate.
  Core authentication, backup, migrations and business-smoke gates remain.
- AI integration no longer shows retired Agent WS/connected-Agent counters.
- Legacy inventory scheduler environment settings are removed from active config.

`server/tests/test_device_cutover_boundary.py` permanently checks browser
production sources, legacy-model references across runtime, and registered route
parity. It runs in normal full CI and Endpoint contract acceptance CI. Historical
ORM definitions/migrations and explicit test fixtures are the only exceptions.
Audit privacy and transaction safety are covered separately.

## Acceptance status

Provider commit `38ddabe3c0badf09a033bb7523a89a7d2c5059a0` passed full
Linux/PostgreSQL CI 36825653896; merge CI 36827176730 also passed. Helpdesk
runtime candidate `35c67c4080979a2d583ba2b01e79db80b985304e` passed full CI
36848506139: all 18 canonical layers, isolated PostgreSQL/fresh migrations,
18 downloaded logs checked for no shared database fallback, and three real
provider/Gateway WSS/Helpdesk contract cases. Independent final review found
no actionable issues and executed 30 adapter/presence/retirement/audit checks.

Actual trusted HTTPS staging Chromium used no mocks or TLS bypass. Windows 3.2.75
was ONLINE with all five safe profiles; five refresh collections completed and
reread current Context. History exposed the actual semantic hash and compared
two saved baseline snapshots through the provider. Exact mapped/unmapped Registry
overlays, different local/Endpoint UUID navigation, temporal primary binding,
asset/person departments and canonical preview/apply/audit with preserved inventory
number were verified. Agent stop produced OFFLINE and restart produced ONLINE.
Endpoint outage produced 503 UNKNOWN with technical data hidden; missing, invalid
and unknown UUID URLs preserved exact identity. Normal console/page errors,
retired requests and direct browser-to-Endpoint calls were zero; intentional 404 /
503 resource messages were recorded separately. Three automation text-locator
assertions were corrected against visible content; they were not product defects.

Both original staging databases, release links, config hashes, principal scopes
and Windows enrollment were restored. All three staging units and Windows Agent
are stopped. Private receipts remain under `.git/admin-cutover-stage/phase2-35c`.
Draft Helpdesk PR39 uses frozen starting base c935a532 to exclude the pre-existing
Sonar changes. Production deployment, destructive cleanup and business metadata
migration remain excluded. A subsequent documentation-only freeze still requires
its own full exact-SHA CI and canonical staging revalidation before final delivery.
The installed Agent already emits replacement characters in session-login Context;
this upstream observation quality issue is reported without Registry substitution.

## Browser navigation verification

Fleet controls cover status, platform, Registry asset department/location,
mapping status, active user relationship, inventory observation age and retired
state. Search includes the exact Endpoint UUID. Counts and filters cover the
current bounded provider page; they do not imply global fleet totals. Inventory
age uses the visible operator-selected 24-hour, 7-day or 30-day window (7 days
initially). It never changes Endpoint ONLINE/OFFLINE. Missing inventory context
and unavailable Registry are distinguished from stale context and unmapped
records. Relationship-type filters retain truncated projections as explicitly
unconfirmed candidates when a requested type cannot be proved from the six
returned bindings; unconfirmed mapping never proves that an asset is absent.
History exposes each actual timestamp, semantic hash, warnings and
snapshot selection, with comparisons executed by the provider.

The admin domain, inventory navigation entry and page heading use «Устройства».
Fixture browser checks cover the exact Endpoint UUID card link, missing-UUID
validation, absence of retired device API requests and ticket context UNKNOWN
on provider failure. These fixture checks do not replace live staging acceptance.

Registry PostgreSQL regressions retain primary-owner, merge, preview, partial
failure and audit checks against canonical records. They also assert that legacy
inventory rows stay absent or unchanged and that the retired inventory import
fails closed without overwriting business metadata. The Endpoint integration
guard runs these suites in addition to the full Helpdesk CI.
