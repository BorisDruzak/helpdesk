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

Provider changes and immutable contract pin have exact-SHA full CI and real
cross-repository PostgreSQL acceptance. UI unit/build checks and retirement guards
are separate evidence. Final frozen-SHA full Helpdesk CI and live staging browser/
Windows Endpoint online-offline-outage/collection/history/Registry acceptance are
still required. This document does not authorize production deployment or mark
the full cutover accepted.
