# Task 4 report: RegistryPort Helpdesk read cutover

## Status

Complete. The commit hash is supplied in the controller handoff because this
report is included in that commit.

## Implemented slice

- `TicketContextBuilder.requester_reference_snapshot()` reads the verified
  requester display snapshot through `RegistryPort.requester_snapshot()` and
  fails closed on not-found, unavailable or invalid projections.
- Every migrated consumer correlates the returned requester/device refs with
  the exact requested opaque ref. Cross-request/mismatched snapshots, account
  status and bindings fail closed as `registry_projection_invalid`; inventory
  omits the invalid projection and support returns typed unavailable state.
- Ticket creation reads redacted device/account state through
  `RegistryPort.account_status()`. Invalid projections fail before requester
  profile ingestion or ticket persistence. The same injected/composed port is
  reused for verified requester snapshots.
- `DeviceInventoryService.list_device_profiles()` reads the current active
  requester through `RegistryPort.active_binding()` and returns only the opaque
  requester ref, display name and typed source/status. Unrepresented rich fields
  are `None`.
- Support ticket current requester state uses `requester_snapshot()` or, for a
  legacy device-only ticket, `active_binding()`. The DTO exposes typed
  `status`, `source` and `code`. Unavailable/not-found current state may show
  only a validated immutable ticket snapshot with `source=ticket_snapshot`;
  malformed neutral identity never falls through to legacy Registry data.
- The AST guard accepts
  `--registry-scope requester,tickets,customer_history,inventory,web_api`.
  Selected migrated paths and every new ticket module reject Registry
  ORM/repository/service imports except the exact symbol debt below. The default
  invocation retains the existing Knowledge-only behavior, so this task does
  not make a false repository-wide Registry claim.

## Expected redaction changes

- Task-3 `ActiveBindingProjection` and `AccountStatusProjection` do not expose
  Registry asset or pending-claim identifiers. Active/account-status ticket
  reads therefore no longer populate `asset_id` or nested pending-claim ids.
  Exact validated binding/session paths and same-flow command results may still
  provide their existing values.
- Support and inventory no longer reconstruct current phone, email,
  department, location, asset or service fields from local Registry tables.
  Existing API fields remain nullable for compatibility.
- These deltas were made explicit in legacy enrichment/support tests; no local
  fallback or contract expansion was added.

## Exact direct-import debt

The scoped guard allows only these existing imports:

- `server/requester/identity_service.py`: `DeviceAccountSession`,
  `DeviceRegistrationClaim`, `DeviceUserBinding`, `RegistryAsset`,
  `RegistryPerson`, `RegistryPersonIdentity`, `RegistrationRepo`,
  `is_person_active`, `normalize_identifier`, `RegistryRepo`,
  `PrimaryAgentResolver`, `RequesterProfileSchemaService`.
- `server/tickets/create_flow.py`: `RegistrationRepo` for binding-specific
  shared-user/session revalidation, `AccountSessionService` for verified session
  checks, and `RegistryIngestionService` for the existing registration command.
- `server/tickets/account_access_service.py`: `AccountSessionService`.
- `server/tickets/ticket_context.py`: `RegistryPerson` and
  `PrimaryAgentResolver` for the still-rich ticket context builder.
- `server/customer_history/sources.py`: `DeviceAccountSession` and
  `DeviceUserBinding`.
- `server/web_api/requester_handlers.py`: `RegistryDepartment`,
  `RegistryLocation`, `RegistryPerson`, `PrimaryAgentResolver` and
  `RequesterProfileSchemaService`.

`server/inventory/service.py` and `server/web_api/support_handlers.py` retain no
direct Registry imports.

## Deferred operations

- Requester identity/profile/schema resolution, pending-claim discovery,
  directory/on-behalf search and rich department/location/person reads.
- Rich ticket context and primary diagnostic-target resolution, including
  reverse person-to-device selection.
- Customer-history binding/account-session event projections.
- Rich inventory/support contact, organisation, asset and service projections.
- Binding-specific lookup in the port, exact account-session authorization and
  caller-idempotent Registry commands. Until those contracts exist,
  `create_flow.py` keeps the exact shared-binding/session checks required by the
  Task-2 isolation tests.

## TDD and verification evidence

RED:

- Four scoped-guard tests failed because `--registry-scope` did not exist.
- The support legacy-device test initially returned no current requester before
  `active_binding()` projection was implemented.
- `test_ticket_registration_enrichment.py` exposed eight compatibility deltas;
  two were the invalid-projection fail-open regression, while six were expected
  Task-3 redactions. The fail-open path was fixed and the redactions made
  explicit.
- Six security tests failed before requested-ref correlation was added across
  ticket snapshots, account status, inventory and support projections.
- The scoped guard initially allowed broad `import app.db.models` and
  `from app import repos` namespace imports; the bypass regression failed before
  broad-module rejection was added.

GREEN:

- Final required Task-4 gate after requested-ref correlation hardening:
  `python -m pytest server/tests/test_domain_import_boundaries.py server/tests/test_registry_boundary.py server/tests/test_requester_workspace_api.py server/tests/test_web_support_api.py -q --tb=short`
  -> `156 passed`.
- Enrichment/boundary regression gate:
  `python -m pytest server/tests/test_registry_boundary.py server/tests/test_ticket_registration_enrichment.py -q --tb=short`
  -> `22 passed` before the final two additional fail-closed/guard tests.
- Final focused follow-up:
  `python -m pytest server/tests/test_domain_import_boundaries.py server/tests/test_registry_boundary.py server/tests/test_ticket_registration_enrichment.py::test_verified_requester_with_invalid_snapshot_does_not_create_legacy_only_ticket -q --tb=short`
  -> `27 passed`.
- Shared primary/secondary binding isolation:
  `python -m pytest server/tests/test_requester_workspace_api.py::test_requester_shared_device_tickets_stay_scoped_to_person_and_binding -q --tb=short`
  -> `1 passed`.
- Ticket context: `9 passed`; requester snapshot plus boundary tests:
  `26 passed`; support compatibility targets: `2 passed`.
- Task-2 account-access and consent regression gate:
  `python -m pytest server/tests/test_ticket_account_access.py server/tests/test_user_consent_api.py -q --tb=short`
  -> `27 passed`.
- Final Registry boundary no-DB run -> `16 passed`; domain import boundary run
  -> `16 passed`; segmentation/navigation docs -> `18 passed`.
- `python scripts/check_domain_import_boundaries.py --workspace . --registry-scope requester,tickets,customer_history,inventory,web_api` -> pass.
- `python -m compileall -q server/requester server/tickets server/customer_history server/inventory server/web_api scripts/check_domain_import_boundaries.py` -> pass.
- `python scripts/audit_test_inventory.py --strict` -> `files=391 issues=0`.
- `python scripts/docs_drift_check.py --base aa0841cc --json` -> `status=ok`.
- `python scripts/verify_workspace.py --workspace .` -> pass.
- `git diff --check` -> pass (only the repository's LF-to-CRLF warnings).

## Files

Updated implementation:

- `scripts/check_domain_import_boundaries.py`
- `server/inventory/service.py`
- `server/tickets/create_flow.py`
- `server/tickets/ticket_context.py`
- `server/web_api/dto/support.py`
- `server/web_api/support_handlers.py`

Updated/created tests:

- `server/tests/test_domain_import_boundaries.py`
- `server/tests/test_registry_boundary.py`
- `server/tests/test_requester_reference_snapshot.py`
- `server/tests/test_ticket_registration_enrichment.py`
- `server/tests/test_web_support_api.py`

Updated routing/docs:

- `docs/QUICK_LOOKUP.md`
- `docs/ARCHITECTURE_BOUNDARIES.md`
- `docs/README.md`
- `server/docs/CODEMAP.md`
- `server/docs/README.md`
- `server/docs/SEGMENTATION_BOUNDARIES.md`
- `server/docs/TICKET_SYSTEM.md`
- `scripts/navigation_catalog.py`

## Independent review disposition

- The P1 cross-request ref-correlation finding was reproduced with six RED
  tests, fixed in all migrated consumers and covered by the final 156-test gate.
- Broad Registry namespace import bypasses were reproduced and fixed in the
  scoped guard.
- The review objection to rich-field redaction conflicts with the controller's
  explicit approved Task-4 split. It is retained as documented deferred
  contract work; no forbidden fallback was restored.
- The TypeScript support model does not yet consume `status`/`source`/`code` or
  visually distinguish `ticket_snapshot` history. Frontend/browser acceptance
  is explicitly deferred with the rich Registry contract; no browser-visible
  files were changed in this task.
- The ordinary workspace verifier still runs the default Knowledge guard. The
  Registry boundary remains intentionally incremental and is invoked explicitly
  with `--registry-scope` in the Task-4 gate/navigation contract rather than
  being advertised as repository-wide enforcement.

No schema, migration, route removal, Registry command cutover, deploy, remote
operation or browser run was performed.
