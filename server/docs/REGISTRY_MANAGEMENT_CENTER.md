# Registry Management Center

`/app/admin/registry` is the admin workspace for device ownership, people identities, account sessions and lightweight CMDB operations.

Registry visibility, effective identity and audience groups are tracked in [REGISTRY_VISIBILITY_FOUNDATION.md](REGISTRY_VISIBILITY_FOUNDATION.md). That document keeps organization structure, RBAC/access groups and content audiences separate while extending this Management Center; Knowledge audience-rule enforcement remains a later phase.

## Source Of Truth

- Active device-user relations live in `device_user_bindings`.
- `registry_assets.assigned_person_id` and `device_inventory_bindings.person_id/source_binding_id/registration_status` are derived state.
- Binding lifecycle operations must go through `RegistrationService`.
- UI login to registry-person links are represented only as verified `registry_person_identities(provider='ui_login')`; `ui_users` rows are not duplicated into person records.
- Departments are organization structure. Access groups are RBAC/queue permissions. Audience groups are content/service targeting objects and must not grant permissions by themselves.
- Account sessions are revoked through `AccountSessionService` when bindings are revoked or transferred.
- Location, department, policy, merge and bulk admin actions write `registry_admin_events`.
- Person and identity admin mutations write `registry_admin_events` (`person_created`, `person_updated`, `identity_added`, `identity_verified`, `identity_deleted`).
- Dangerous admin operations expose read-only preview/dry-run endpoints before apply. Preview endpoints must not mutate state, write events or commit; the web UI requires preview before transfer/merge/import apply.
- Dangerous apply operations return a normalized `operation_id`/`status`/`summary`/`items`/`events` report in addition to legacy domain fields where callers still rely on them.
- Generated data-quality issues have stable `issue_key` values. Ignore, snooze and resolve are persisted in `registry_quality_issue_overrides` and audited through `registry_admin_events`.

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
  - `POST /api/web/admin/registry/ui-users/{user_login}/link-person`
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
  - `POST /api/web/admin/registry/policies/preview`
  - `POST /api/web/admin/registry/policies/reset`
- Audience groups:
  - `GET|POST /api/web/admin/registry/audience-groups`
  - `PATCH /api/web/admin/registry/audience-groups/{audience_group_id}`
  - `POST /api/web/admin/registry/audience-groups/{audience_group_id}/archive`
  - `GET|PUT /api/web/admin/registry/audience-groups/{audience_group_id}/members`
  - `POST /api/web/admin/registry/audience-groups/{audience_group_id}/preview-members`
- Bulk/export/timeline:
  - `POST /api/web/admin/registry/bulk/preview`
  - `POST /api/web/admin/registry/bulk/devices/assign-location`
  - `POST /api/web/admin/registry/bulk/devices/assign-department`
  - `POST /api/web/admin/registry/bulk/devices/revoke-account-sessions`
  - `POST /api/web/admin/registry/bulk/people/assign-department`
  - `POST /api/web/admin/registry/bulk/account-sessions/revoke`
  - `GET /api/web/admin/registry/export?type=devices|people|bindings|sessions|locations|departments|quality|audience_groups|audience_group_members|knowledge_audience_rules&format=csv`
  - `POST /api/web/admin/registry/import/preview`
  - `POST /api/web/admin/registry/import/apply`
  - `GET /api/web/admin/registry/timeline/{object_type}/{object_id}`
- Data quality:
  - `POST /api/web/admin/registry/quality/{issue_key}/ignore`
  - `POST /api/web/admin/registry/quality/{issue_key}/snooze`
  - `POST /api/web/admin/registry/quality/{issue_key}/resolve`

Registry import is CSV-only and intentionally excludes direct binding and account-session import. Supported import types are `people`, `locations`, `departments`, `device_inventory_mapping`, `audience_groups` and `audience_group_members`.

## Visibility Foundation Boundary

The Registry Visibility Foundation extends this management center without changing existing source-of-truth rules:

- effective identity is a read model over verified `ui_login` identities, registry people, primary department/location, active bindings, account sessions and access groups;
- Phase 1 admin explain/read APIs live under `/api/web/admin/registry/identity/*` and are read-only;
- agent machine identity remains technical device identity and must not identify the requester without a valid server account session;
- `registry_audience_groups` may include people, departments, department trees, locations, roles, access groups or services, but they do not grant RBAC permissions;
- `/app/admin/registry` exposes `Группы доступа · P1` as a read-only RBAC summary and deep link to `/app/admin/access`; access-group mutations stay in the canonical Access Control Center;
- `/app/admin/registry` exposes the first audience-group management UI in the `Аудитории · P1` tab and keeps member save behind preview plus required reason;
- normal bulk, quality and UI-login linking paths use dialogs with searchable pickers/reason/result reports instead of raw `window.prompt` flows;
- future Knowledge audience rules refine coarse Knowledge visibility and must never make `support_internal`, `admin_internal` or `security_restricted` content requester-visible;
- dangerous audience, visibility and bulk operations must follow the same preview/apply/audit pattern already used by Registry transfer, merge, bulk and import flows.

Normal operator UI must prefer names/codes and searchable pickers. Raw ids belong only in `Advanced / служебные поля`.

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
- `people_merge`: shows field winners, identity moves/conflicts, bindings, sessions, account login requests, claims, tickets, asset owner and inventory rows that will move to the master person.
- `location_merge` and `department_merge`: show people/assets/inventory rows that will be moved plus duplicate object archival as `merged`.
- `bulk`: supports `devices.assign_location`, `devices.assign_department`, `devices.revoke_account_sessions`, `people.assign_department` and `account_sessions.revoke` with per-item results.

## Dangerous Apply Result Contract

Transfer owner, people merge, location merge, department merge, bulk actions and import apply return the same report envelope:

```json
{
  "operation_id": "uuid",
  "operation": "transfer_owner",
  "status": "success",
  "summary": {"success": 4, "failed": 0, "warnings": 0},
  "items": [
    {"id": "binding-old", "entity_type": "binding", "status": "success", "message": "transferred"},
    {"id": "session-1", "entity_type": "account_session", "status": "success", "message": "revoked"}
  ],
  "events": ["binding_transferred"],
  "report_url": null
}
```

`status` is `success`, `partial_success` or `error`. `items` is the operational audit/report surface: transfer reports old/new bindings, derived asset/inventory sync and revoked sessions; merge reports moved/skipped entities; bulk and import report one row per selected object or CSV row. Domain-specific fields such as `binding`, `asset`, `master`, `duplicate`, `moved`, `bulk_operation_id` and legacy `results` are preserved for compatibility.

## Policy Safety Contract

`GET /api/web/admin/registry/policies`, `POST /api/web/admin/registry/policies/preview`, `PATCH /api/web/admin/registry/policies` and `POST /api/web/admin/registry/policies/reset` return the same cautious policy envelope:

- `defaults`: server defaults for every registration, account-session and ticket-visibility policy.
- `effective`: validated effective policy after applying defaults.
- `changed_from_defaults`: field-level default/effective drift.
- `warnings`: dangerous-setting warnings. Enabling `registration.auto_approve_first_binding` returns: `Это позволит автоматически подтверждать первую регистрацию устройства. Рекомендуется только для тестового стенда.`
- `validation`: numeric ranges and nullable flags for bounded policy fields.
- `requires_restart` and `restart_required_fields`: currently `false` / empty for registry policies because the services read effective values at runtime.
- `dry_run`: `true` only for preview.

Patch/reset require `reason` and write `registry_admin_events.event_type=policy_changed`. Preview validates and returns the effective envelope without mutating state, committing or writing audit events.

## Bulk Apply Contract

Bulk apply endpoints return both the legacy `results` list and a normalized operation report for the UI:

```json
{
  "operation_id": "uuid",
  "bulk_operation_id": "uuid",
  "operation": "devices.revoke_account_sessions",
  "status": "partial_success",
  "summary": {"selected": 47, "success": 42, "failed": 5},
  "items": [
    {"id": "device-1", "status": "success", "affected_sessions": 2},
    {"id": "device-2", "status": "error", "error_code": "NOT_FOUND"}
  ],
  "results": [],
  "events": ["bulk_action_applied"],
  "report_url": null
}
```

`items` is one row per selected object, not one row per affected child record. Device-level session revoke therefore reports selected devices and includes `affected_sessions`. The registry UI shows selected count, success/failed totals, failed rows, copyable errors and CSV export of the report. CSV report generation escapes formula-leading values (`=`, `+`, `-`, `@`) before download.

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
  "preview_id": "required only for apply",
  "reason": "required only for apply"
}
```

Preview parses and validates the file without mutating state. It returns `preview_id`, row-level errors, duplicate keys, affected counts and a bounded change list. Apply requires the matching `preview_id`, reruns preview first and refuses to mutate if there are any row errors or duplicate keys, then applies all accepted rows in the request transaction and writes one `registry_import_applied` audit event with the import type, operation id, counts, reason and sample changes. Apply responses include `operation_id`, `status`, `summary` and per-row `items` so the UI can show the result, copy failed rows and download all-row or failed-only CSV reports. Supported imports:

- `people`: create/update people by `person_id`, validate required display name, duplicate emails and location/department ids.
- `locations`: create/update locations and block exact duplicate building/floor/room keys.
- `departments`: create/update departments and block duplicate department codes.
- `device_inventory_mapping`: update registry asset location/department and non-binding lifecycle inventory card fields for existing devices. It does not import `device_user_bindings`, `assigned_person_id`, `person_id`, `source_binding_id` or account-session state.
- `audience_groups`: create/update audience group code, name, description, source and status with duplicate code detection.
- `audience_group_members`: create/update group members by group code/id, member type, member id and include-children flag. For `member_type=department`, `include_children=true` intentionally imports the same subtree/path targeting contract as `member_type=department_tree`; with `include_children=false` it targets only the direct primary department. It imports audience targeting membership only; it does not grant RBAC permissions or create Registry people/bindings.

## Quality Remediation Contract

`GET /api/web/admin/registry` returns generated `data_quality` items with a stable `issue_key` built from `kind`, `object_type`, `object_id` and optional related id. Active ignored, snoozed and resolved issues are hidden from the main list:

- `ignore` hides an accepted exception until the underlying issue key changes.
- `snooze` hides an issue for 1-365 days.
- `resolve` records an admin resolution for issues fixed outside the UI flow.

Every state change requires `reason`, stores actor/time in `registry_quality_issue_overrides`, and writes one of `quality_issue_ignored`, `quality_issue_snoozed` or `quality_issue_resolved` to the registry timeline.

Issues caused by current state disappear from the active list when the root cause is fixed and the registry snapshot is recomputed. For example, binding a primary user resolves `asset_missing_confirmed_user` without requiring a manual `resolve`; adding the missing identity removes `missing_identity`; approving/replacing the conflict removes `registration_conflict`. Overrides remain for explicit admin ignore/snooze/resolve decisions.

Registry Visibility Foundation quality issues also include `audience_group_empty`, `knowledge_audience_rule_invalid_target` and `knowledge_audience_zero_users`. These issues expose ids/counts/reason context only; Knowledge article bodies, hidden content, tokens, cookies and public access codes must not be included in quality payloads or exported CSV.

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
