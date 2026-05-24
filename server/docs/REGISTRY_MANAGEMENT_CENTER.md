# Registry Management Center

`/app/admin/registry` is the admin workspace for device ownership, people identities, account sessions and lightweight CMDB operations.

## Source Of Truth

- Active device-user relations live in `device_user_bindings`.
- `registry_assets.assigned_person_id` and `device_inventory_bindings.person_id/source_binding_id/registration_status` are derived state.
- Binding lifecycle operations must go through `RegistrationService`.
- Account sessions are revoked through `AccountSessionService` when bindings are revoked or transferred.
- Location, department, policy, merge and bulk admin actions write `registry_admin_events`.

## Main API Surface

- `GET /api/web/admin/registry`
- Device binding actions:
  - `POST /api/web/admin/registry/devices/{device_id}/bind-person`
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
  - `POST /api/web/admin/registry/people/merge`
- CMDB:
  - `GET|POST /api/web/admin/registry/locations`
  - `PATCH /api/web/admin/registry/locations/{location_id}`
  - `POST /api/web/admin/registry/locations/{location_id}/archive`
  - `POST /api/web/admin/registry/locations/merge`
  - `GET|POST /api/web/admin/registry/departments`
  - `PATCH /api/web/admin/registry/departments/{department_id}`
  - `POST /api/web/admin/registry/departments/{department_id}/archive`
  - `POST /api/web/admin/registry/departments/merge`
- Policies:
  - `GET|PATCH /api/web/admin/registry/policies`
- Bulk/export/timeline:
  - `POST /api/web/admin/registry/bulk/devices/assign-location`
  - `POST /api/web/admin/registry/bulk/devices/assign-department`
  - `POST /api/web/admin/registry/bulk/devices/revoke-account-sessions`
  - `POST /api/web/admin/registry/bulk/people/assign-department`
  - `POST /api/web/admin/registry/bulk/account-sessions/revoke`
  - `GET /api/web/admin/registry/export?type=devices|people|bindings|sessions|locations|departments|quality&format=csv`
  - `GET /api/web/admin/registry/timeline/{object_type}/{object_id}`

## Smoke Checklist

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

## Validation

Prefer Linux/test-DB for DB-backed pytest if the Windows DB harness stalls during Alembic/tunnel setup.

Focused backend:

```bash
python -m pytest server/tests/test_registry_admin_actions.py -q
python -m pytest server/tests/test_registry_people_admin.py -q
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
