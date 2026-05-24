# Registry Management Center

`/app/admin/registry` is the admin workspace for device ownership, people identities, account sessions and lightweight CMDB operations.

## Source Of Truth

- Active device-user relations live in `device_user_bindings`.
- `registry_assets.assigned_person_id` and `device_inventory_bindings.person_id/source_binding_id/registration_status` are derived state.
- Binding lifecycle operations must go through `RegistrationService`.
- Account sessions are revoked through `AccountSessionService` when bindings are revoked or transferred.
- Location, department, policy, merge and bulk admin actions write `registry_admin_events`.
- Person and identity admin mutations write `registry_admin_events` (`person_created`, `person_updated`, `identity_added`, `identity_verified`, `identity_deleted`).
- Dangerous admin operations expose read-only preview/dry-run endpoints before apply. Preview endpoints must not mutate state, write events or commit; the web UI requires preview before transfer/merge apply.

## Main API Surface

- `GET /api/web/admin/registry`
- Device binding actions:
  - `POST /api/web/admin/registry/devices/{device_id}/bind-person`
  - `POST /api/web/admin/registry/devices/{device_id}/transfer-owner/preview`
  - `POST /api/web/admin/registry/devices/{device_id}/transfer-owner`
  - `POST /api/web/admin/registry/devices/{device_id}/shared-users`
  - `POST /api/web/admin/registry/devices/{device_id}/responsible`
  - `POST /api/web/admin/registry/bindings/{binding_id}/revoke`
- People and identities:
  - `POST /api/web/admin/registry/people`
  - `PATCH /api/web/admin/registry/people/{person_id}`
  - `POST /api/web/admin/registry/people/{person_id}/identities`
  - `PATCH /api/web/admin/registry/identities/{identity_id}`
  - `DELETE /api/web/admin/registry/identities/{identity_id}`
  - `POST /api/web/admin/registry/people/merge/preview`
  - `POST /api/web/admin/registry/people/merge`
- CMDB:
  - `GET|POST /api/web/admin/registry/locations`
  - `PATCH /api/web/admin/registry/locations/{location_id}`
  - `POST /api/web/admin/registry/locations/{location_id}/archive`
  - `POST /api/web/admin/registry/locations/merge/preview`
  - `POST /api/web/admin/registry/locations/merge`
  - `GET|POST /api/web/admin/registry/departments`
  - `PATCH /api/web/admin/registry/departments/{department_id}`
  - `POST /api/web/admin/registry/departments/{department_id}/archive`
  - `POST /api/web/admin/registry/departments/merge/preview`
  - `POST /api/web/admin/registry/departments/merge`
- Policies:
  - `GET|PATCH /api/web/admin/registry/policies`
- Bulk/export/timeline:
  - `POST /api/web/admin/registry/bulk/preview`
  - `POST /api/web/admin/registry/bulk/devices/assign-location`
  - `POST /api/web/admin/registry/bulk/devices/assign-department`
  - `POST /api/web/admin/registry/bulk/devices/revoke-account-sessions`
  - `POST /api/web/admin/registry/bulk/people/assign-department`
  - `POST /api/web/admin/registry/bulk/account-sessions/revoke`
  - `GET /api/web/admin/registry/export?type=devices|people|bindings|sessions|locations|departments|quality&format=csv`
  - `POST /api/web/admin/registry/import/preview`
  - `POST /api/web/admin/registry/import/apply`
  - `GET /api/web/admin/registry/timeline/{object_type}/{object_id}`

Registry import is CSV-only and intentionally excludes direct binding import. Supported import types are `people`, `locations`, `departments` and `device_inventory_mapping`.

## Timeline Contract

`GET /api/web/admin/registry/timeline/{object_type}/{object_id}` is the drawer timeline source for `device`, `person`, `binding`, `account_session` and `claim`. It merges `registry_admin_events`, `device_registration_events` and `device_account_events` into a common item shape:

- `source`: `registry_admin`, `registration` or `account`.
- `event_type` plus `canonical_event_type` for UI labels such as `binding_created`, `shared_user_added`, `responsible_assigned`, `people_merged`, `policy_changed` and `bulk_action_applied`.
- `actor_id`, `actor_role`, `event_at`, `reason`.
- `summary` for a compact human-readable action line.
- `related` with affected ids (`device_id`, `person_id`, `binding_id`, `claim_id`, `session_id`, `ticket_id`, `identity_id`, `location_id`, `department_id` when known).
- `changes`, derived from explicit `payload.changes` or `before`/`after` payloads.

The drawer must render who changed what, when, why and which entities were affected. New registry admin actions should either write a domain event through `RegistrationService`/`AccountSessionService` or a `RegistryAdminEvent` through `RegistryAdminOperationsService.append_event`.

## Preview Contract

Preview responses use a shared shape:

```json
{
  "operation": "transfer_owner",
  "dry_run": true,
  "requires_confirmation": true,
  "counts": {"sessions_to_revoke": 2},
  "changes": [
    {"kind": "binding", "action": "update", "object_id": "...", "before": {}, "after": {}, "severity": "destructive"}
  ],
  "warnings": [],
  "blockers": []
}
```

Implemented preview operations:

- `transfer_owner`: shows old binding action, new primary binding creation, derived asset/inventory sync, account sessions that will be revoked and ticket references that stay preserved.
- `people_merge`: shows field winners, identity moves/conflicts, bindings, sessions, claims, tickets, asset owner and inventory rows that will move to the master person.
- `location_merge` and `department_merge`: show people/assets/inventory rows that will be moved plus duplicate object archival as `merged`.
- `bulk`: supports `devices.assign_location`, `devices.assign_department`, `devices.revoke_account_sessions`, `people.assign_department` and `account_sessions.revoke` with per-item results.

## Import Contract

Registry import is a two-step workflow:

1. `POST /api/web/admin/registry/import/preview`
2. `POST /api/web/admin/registry/import/apply`

Both endpoints accept JSON:

```json
{
  "type": "people",
  "format": "csv",
  "csv_text": "display_name,email\nIvan Ivanov,ivan@example.test\n",
  "reason": "required only for apply"
}
```

Preview parses and validates the file without mutating state. It returns row-level errors, duplicate keys, affected counts and a bounded change list. Apply reruns preview first and refuses to mutate if there are any row errors or duplicate keys, then applies all accepted rows in the request transaction and writes one `registry_import_applied` audit event with the import type, counts, reason and sample changes. Supported imports:

- `people`: create/update people by `person_id`, validate required display name, duplicate emails and location/department ids.
- `locations`: create/update locations and block exact duplicate building/floor/room keys.
- `departments`: create/update departments and block duplicate department codes.
- `device_inventory_mapping`: update registry asset location/department and non-binding lifecycle inventory card fields for existing devices. It does not import `device_user_bindings`, `assigned_person_id`, `person_id`, `source_binding_id` or account-session state.

## Smoke Checklist

For the full workflow smoke, deploy the current commit to the Linux stand and run:

```bash
python scripts/registry_workflow_smoke.py --base-url https://192.168.100.17:9443 --insecure-tls
```

The script issues short-lived admin/agent tokens through `AuthService`, drives admin and agent HTTP APIs, creates unique smoke objects, and verifies the database invariants below without printing raw tokens. It revokes smoke account sessions during cleanup and leaves audit/history records intact.

1. Create a user.
2. Add and verify an identity.
3. Bind the user to an unregistered device.
4. Confirm `registry_assets` and `device_inventory_bindings` sync.
5. Add a shared user.
6. Assign a responsible person.
7. Transfer owner.
8. Confirm old sessions are revoked.
9. Create an account session after transfer.
10. Revoke a binding.
11. Confirm account sessions become invalid.
12. Open the device drawer and check timeline/history.
13. Open the person drawer and check identities/devices/sessions.
14. Create/edit/archive/merge a location.
15. Create/edit/archive/merge a department.
16. Change a safe policy value and verify account-session TTL behavior.
17. Export devices, people, bindings, sessions, locations, departments and quality CSV.
18. Open Quality tab and use fix actions for missing user, stale binding, missing identity and duplicate person.

`scripts/registry_workflow_smoke.py` covers the high-risk operational scenarios:

- Scenario A: create person, add email/windows identities, verify identity, update person, confirm snapshot/drawer identity payload.
- Scenario B: bind person as `primary_user`, confirm `device_user_bindings`, `registry_assets`, `device_inventory_bindings`, registration event and confirmed account-session creation.
- Scenario C: add `shared_user` and `responsible`, confirm primary stays active and agent account-state exposes all relationships.
- Scenario D: transfer owner, confirm old binding status, new primary, derived asset/inventory state, old session revocation and denied ticket access with the old session.
- Scenario E: merge duplicate people and confirm identities, bindings, tickets, account sessions and derived owner state move to the master.
- Scenario F: create/assign/merge locations and departments and confirm people/assets/inventory are updated.

## Validation

Prefer Linux/test-DB for DB-backed pytest if the Windows DB harness stalls during Alembic/tunnel setup.

Focused backend:

```bash
python -m pytest server/tests/test_registry_admin_actions.py -q
python -m pytest server/tests/test_registry_people_admin.py -q
python -m pytest server/tests/test_registry_timeline_admin.py -q
python -m pytest server/tests/test_registry_admin_previews.py -q
python -m pytest server/tests/test_registry_people_merge.py -q
python -m pytest server/tests/test_registry_locations_admin.py -q
python -m pytest server/tests/test_registry_departments_admin.py -q
python -m pytest server/tests/test_registry_policies_admin.py -q
python -m pytest server/tests/test_registry_bulk_actions.py -q
python -m pytest server/tests/test_registry_import_export.py -q
```

Frontend:

```bash
pnpm --dir webapp test -- registry
pnpm --dir webapp run build
```
