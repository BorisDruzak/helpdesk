# Helpdesk server code map

## Entry points

- `server/server.py` builds the Helpdesk aiohttp application.
- `server/web_api/` provides authenticated Helpdesk browser and support APIs.
- `server/tech/snapshot.py` builds the read-only Tech Panel readiness model;
  the `endpoint_platform` connection-policy state is valid after the legacy
  Helpdesk agent runtime is retired.
- `server/control_plane.py` controls the independent Helpdesk server lifecycle.
- `server/runtime_control.py` manages only the Helpdesk server and control
  plane units.

## Dynamic request forms

- `server/tickets/form_catalog.py` is the compatibility facade and catalog
  persistence/augmentation boundary. Existing import names and callable
  signatures are retained.
- `form_defaults.py` owns default packs, constant vocabularies and priority
  compatibility defaults. `form_field_values.py` owns codecs, visibility and
  submission validation; it depends on defaults. `form_schema_validation.py`
  owns field/schema/role/template normalization and imports the shared pattern
  validator from values. Neither module imports the facade.
- Checkbox values use explicit aliases; ordinary text conditions remain case
  sensitive. Hidden values/errors are excluded without masking invalid visible
  dependencies. Required numeric zero is valid subject to min/max. Invalid regex
  is rejected at publication and fails closed on submission of legacy packs.
- `webapp/src/features/requester/dynamic-form/index.tsx` mirrors these boundary
  cases. Invalid checkbox state remains editable but blocks submission; render
  helpers do not turn a bad string into true or crash the requester form.

## Compatibility ticket detail UI

- `webapp/src/pages/tickets/detail-page.tsx` composes
  `hooks/use-ticket-detail-controller.ts` and `detail-workspace.tsx`, retaining
  its exported component/label facade. `detail-formatting.tsx` contains shared
  display helpers; `sections/` owns the existing dialog, status, passport,
  automation, diagnostics, context and sidebar presentation.
- Controller state holds the message draft independently of fetched detail,
  preserving it across refetch. Query keys, invalidation and permission checks
  remain those of the original page.
- The active router's `lazy-pages.tsx` ticket-detail export renders
  `TicketListPage` from `list-page.tsx`. The split page is a compatibility surface,
  exercised directly by component tests and `tests/detail-compatibility.spec.ts`.
  Its Vite fixture is built automatically by Playwright before the Python fixture
  server starts; it is not a production route or asset bundle.

## Problem scheduler shutdown

- `server/app/services/problem_candidate_scheduler.py::stop` shields the
  cancelled child task while its cleanup runs and preserves cancellation of
  the calling task, including repeated cancellation. The child reference is
  cleared only after termination. Event-barrier regressions live in
  `test_scheduler_stop_cancellation_no_db.py`.

## UI-user creation conflicts

- `server/app/repos/ui_users_repo.py` rolls back failed user creation and emits
  a constant conflict message. The reported `ValueError` suppresses the SQL
  exception chain so password hashes cannot appear in its formatted traceback.
  Regression coverage lives in `server/tests/test_ui_users_repo_no_db.py`.
- `server/app/db/engine.py` hides bound SQL parameter values in runtime engine
  logs and statement errors. `server/tests/test_db_engine_pool_config.py`
  verifies this against the configured SQLAlchemy engine without a DB connection.

## Requester consent decisions

- `server/consent/service.py` requires the operation lifecycle transition to
  succeed before a browser consent decision can be committed. A failed
  compare-and-set raises `ConsentAccessError` with
  `OPERATION_STATE_CONFLICT`/409; the requester handler rolls back the decision
  and its ticket event. Missing or no-longer-waiting operation subjects also
  return this conflict. Endpoint dispatch remains outside this service.
- Approval also requires an `endpoint_operation` with a persisted, unsubmitted
  `EndpointOperationLink` for `context.diagnostic.collect`. Missing or retired
  delivery returns `OPERATION_DELIVERY_UNAVAILABLE`/409 and rolls back the
  decision and event; denial remains available for legacy subjects.
  `endpoint_operation_reconciler.py` claims only queued/sent/accepted/running
  operations and cancellation monitoring, never local consent holds.
  `test_consent_endpoint_delivery_persistence.py` covers the PostgreSQL hold,
  durable retry after a transport failure and orphan approval rollback.

## Ticket creation

- `server/tickets/create_flow.py` preserves the keyword-only public create
  adapter and groups internal inputs in `TicketCreateInput`. Trusted
  `VerifiedRequesterBinding` remains a separate argument. The identity helper
  retains the original claimed-binding flag even when verification rejects it,
  preventing fallback to an unrelated active binding. `TicketCreateContext`
  carries registry/requester snapshots into `_prepare_ticket_custom_fields`
  and `_persist_and_initialize_ticket`; the caller still owns the transaction.

- `server/tickets/create_flow.py` verifies `browser_no_device` requester identity
  against `RequesterIdentityResolver.resolve_person_for_web_user` before
  assigning any requester/person/context fields. A client account dictionary
  is not an authorization claim. Mismatch raises `RequesterIdentityMismatch`;
  both create handlers roll back and return `REQUESTER_IDENTITY_FORBIDDEN`/403.
  Resolver failure raises `TicketInitializationError("requester_identity")`
  and returns the existing safe 503 after rollback. Verified binding and
  public-create composition retain their existing boundaries.
  Authorized emergency/profile-optional forms also support authenticated actors
  with no Registry identity and no person claim; these tickets remain unlinked.

- `server/requester/create_idempotency.py` owns durable requester-create
  reservations. `POST /api/web/requester/tickets` requires an 8–128-character
  ASCII `Idempotency-Key`; actor/key/payload hashes and the ticket link live in
  `requester_ticket_create_requests` (forward migration 144). Reservation,
  ticket side effects and response construction share one transaction. A
  concurrent duplicate waits for the first commit or rollback; a changed body
  or deleted-ticket tombstone returns `CREATE_REQUEST_CONFLICT`/409.
- A replay uses `RequesterIdentityResolver.get_ticket` with current actor
  scope. It reads an existing public-access event only after authorization
  and returns its code only if it still matches the ticket's current hash.
  The ledger never stores response bodies or codes and does not reissue tokens.
- `webapp/src/features/requester/create-intent.ts` retains the pending key in
  actor/intent-scoped sessionStorage. The requester form reuses it after a
  failure or refresh and clears it after success. A conflict offers ticket
  review and an explicit separate intent; unavailable storage stops submission.

- `server/tickets/create_flow.py` initializes ticket routing, SLA and OLA in
  the caller's transaction. A required stage failure raises
  `TicketInitializationError`; requester and ticket-create HTTP handlers
  roll back before returning `TICKET_INITIALIZATION_UNAVAILABLE`/503.
  A policy service's normal no-policy result is not a failure.
- `server/tickets/public_ticket_handlers.py` keeps public ticket creation,
  required routing/SLA/OLA and public-session issuance in one transaction.
  It constructs the response before committing. `AuthService` accepts the
  caller's session; `AuthTokensRepo` flushes without committing in that mode.
  Standalone public authorization retains its owned transaction.
- `server/web_api/requester_handlers.py::_has_contact_for_emergency` is shared
  by preview/create. A display name alone does not satisfy `contact_required`;
  profile phone/e-mail and explicitly supplied contact fields remain accepted.

## Requester ticket authorization

- `server/requester/identity_service.py` shares one access predicate between
  recent-ticket lists and direct ticket lookup. `get_ticket` queries the exact
  ID or code rather than searching a bounded list of 300 recent tickets.
  Legacy actor/person/active-binding scopes and strict neutral requester
  reference/snapshot validation are preserved. Policy annotation runs only
  for the authorized result. Regression checks are in
  `server/tests/test_requester_ticket_lookup.py` and its no-DB companion.

## Workflow transaction failures

- `server/tickets/workflow_service.py` separates pure status/timestamp builders
  from waiting effects, gate actions and persistence/finalization. Timestamp
  resets retain their original precedence over explicit resolution metadata.
  All stages run under the same row lock and caller transaction; required
  effects still fail closed before commit.

- `server/tickets/workflow_service.py` locks and refreshes the ticket before
  policies or lifecycle side effects. A stale `from_status` raises
  `WorkflowTransitionConflict`; status/confirmation/reopen HTTP handlers return
  `WORKFLOW_CONFLICT`/409 after rollback. `TicketEventsRepo.get_ticket` keeps
  ordinary reads unchanged; `for_update=True` flushes pending writes before
  refreshing because production sessions disable autoflush. The caller owns
  commit/rollback and therefore the lifetime of the row lock.
- Automatic reply transitions choose their target under the same row lock.
  An unavailable or duplicate fallback is a no-op instead of restoring a stale
  status. Concurrency and pending-assignment checks live in
  `server/tests/test_workflow_concurrency.py` and its no-DB companion.
- Support take-in-work keeps the status transition and self-assignment in one
  transaction. Assignment rejection rolls back before `ASSIGNMENT_CONFLICT`/409;
  unexpected failures roll back through the session context and return 503.
- Legacy and support queue-change/reroute handlers require both OLA close and
  restart to succeed. Failure rolls back queue, timers and events before a safe
  503 response and before broadcasting. Mass queue changes retain per-item
  transactions: a failed item rolls back and reports an error, while previously
  committed successful items remain applied.
- `server/tests/test_workflow_atomicity_no_db.py` checks HTTP error/broadcast
  ordering; `server/tests/test_workflow_atomicity.py` checks persisted state,
  events and mixed-result mass actions with isolated PostgreSQL.

## Support reads

- `server/web_api/support_handlers.py` returns `DB_UNAVAILABLE`/503 when
  command-center or workspace-summary reads fail, without a successful empty
  payload or internal exception details. Queue and summary malformed `limit`
  values return `VALIDATION_ERROR`/400 before database access.
- `webapp/src/pages/support/command-center-page.tsx` shows explicit errors and
  unavailable summary counts on first-load failure. A refetch failure keeps
  previously loaded tasks visible together with the error warning.

## Ticket event retries

- `server/tests/test_ticket_event_idempotency_concurrency.py` checks real
  PostgreSQL server-event deduplication after two concurrent retries have both
  passed their preliminary SELECT, for both event IDs and message IDs.
  Migration `132` owns the partial unique indexes; the test does not substitute
  for actual browser/WSS acceptance.

## Endpoint operation facade

- `webapp/src/features/queues/api.ts::postSupportTicketToolRun` reuses
  `diagnostics/endpoint-run-intent.ts` for actor/ticket-scoped safe retries across
  queue, detail and support workspace launchers.
- Registry claim projections in `registration_service.py` and `service.py`
  include provenance for the administrator requests tab; possession conflicts
  remain subject to separate explicit ownership review.

- `server/web_api/session_handlers.py` projects only the public registration
  capability flag; registration never accepts a retired device-link field.
- `server/web_api/requester_handlers.py::handle_web_requester_device_link`
  resolves a complete authenticated RegistryPerson before typed Endpoint
  redemption through `server/endpoint_adapter/http.py` and `wire.py`.
  Before the adapter call, `auth.rate_limit` limits the verified actor + trusted
  client IP pair to 5 attempts / 600 seconds (`DEVICE_BINDING_THROTTLED`, 429,
  no-store). A different IP has a separate bucket; untrusted forwarded headers
  cannot change the client IP. This uses the existing single-process limiter.
- `server/registry/endpoint_possession_service.py` owns locked policy checks,
  idempotent primary activation and conflict claims. Migration `146` adds
  `registry_endpoint_device_mappings`; no mapping is inferred from legacy IDs,
  hostname or ticket diagnostic targets. `RegistryPort.bind_endpoint_possession`
  is composed locally; unsupported external commands fail closed.
- The requester wizard at `webapp/src/pages/requester/device-link-page.tsx`
  uses `device-link-state.ts` for memory-only fragment capture before auth routing.
- Requester preview/create carry explicit `device_scope: none` through
  `TicketContextBuilder`; optional device selection cannot silently fall back to
  the primary computer. Ticket Endpoint snapshots require an exact Registry
  mapping and a fresh provider projection. Canonical form availability defaults
  allow no-device requests while preserving explicit device-required policies.

- `server/diagnostics/` projects the Endpoint diagnostic capability, validates
  ticket access and stores reconciled evidence.
- `server/endpoint/` contains the HTTP adapter and versioned contract types.
- `server/endpoint_adapter/wire.py` validates the published multi-capability
  response and the bounded Context API device presence projection. Support
  snapshots consume `EndpointPort.read_device_presence` for Endpoint-backed
  tickets; unknown provider state never falls back to Helpdesk transport presence.
  The HTTP adapter projects only `context.diagnostic.collect`
  into Helpdesk; its read-only risk, consent and parameter schema remain exact.
  Other published descriptors never authorize additional Helpdesk operations.
- `server/app/repos/` persists ticket, operation and Endpoint facade state.
- `server/tests/test_endpoint_operation_persistence.py` checks PostgreSQL
  rollback before remote dispatch and persisted-key replay after a simulated
  worker exit/lease expiry. Its idempotent provider is a stub; real provider
  transport and Windows acceptance remain separate gates.
  It also checks complete diagnostic-session/link attribution for a supported
  100-character UI login. Revision `145` widens the diagnostic-session actor
  column to match `UiUser.user_login`, preserving nullable/UUID compatibility.
- `server/web_api/support_handlers.py` exposes the canonical support
  diagnostic route and its browser compatibility alias.
- `server/web_api/requester_handlers.py` derives a `VerifiedRequesterBinding`
  only after the authenticated requester-device ownership check;
  `server/tickets/create_flow.py` accepts that internal context only when its
  device, person, and binding identifiers match, preserving requester scope
  for shared devices without changing the public request payload.
- `server/web_api/admin_handlers.py` supplies the browser admin bootstrap;
  its active feature catalog is limited to inventory, forms and the Tech Panel
  and does not advertise retired agent rollout or module-workbench surfaces.
- `server/tickets/handlers.py` projects requester and support UI presence;
  the retired Helpdesk agent runtime is always reported as offline.
- `server/registry/primary_agent_resolver.py` resolves a person's primary
  Endpoint device and projects runtime presence when the supplied state
  provider is available; an unavailable provider remains `unknown`.
- `server/tickets/diagnostic_policy.py` uses the ticket-context target rather
  than the retired Helpdesk agent runtime; an explicitly offline Endpoint
  target records a `diagnostic_autorun_skipped` event instead of starting a
  diagnostic playbook.
- `server/web_api/registry_handlers.py` creates admin registry people with a
  server-generated UUID, so the identity and audit flows never accept a
  caller-supplied person identifier.
- `server/observer/integrity_service.py` scans and resolves findings only for
  its active checks; retired protocol and local-runtime sources are excluded
  from new scans and leave existing events unchanged. Browser authentication
  failures remain in the
  `UiUserAudit` trail rather than the retired agent-runtime audit stream.

Helpdesk has no agent WebSocket server, device outbox sender, tool execution
service, command-result pipeline or local agent operation fallback. `/ws_ui`
is retained solely for browser notification delivery. The legacy local
`run_tool` CLI, GUI-agent debug driver and `/ws_ui_test` page are not shipped.
This also includes the retired UIA create-ticket harness for the local agent.

## Contracts and verification

- [ENDPOINT_OPERATION_CONTRACT.md](ENDPOINT_OPERATION_CONTRACT.md) is the
  Helpdesk-facing diagnostic and cancel contract.
- `server/tests/test_helpdesk_endpoint_only_boundary.py` and
  `server/tests/test_no_legacy_endpoint_routes.py` protect the retired
  surfaces.
- `server/tests/test_endpoint_contract_lock.py` protects the consumed Endpoint
  API contract.
# Production security policy

- `shared/production_security.py`: shared dependency-free production transport,
  bind and proxy policy; called by runtime `config.validate_security_config()`.
- `scripts/validate_production_config.py`: safe deployment/systemd preflight;
  optionally reads a root-owned env file and emits key-only errors.
- `scripts/helpdesk_database_backup.py`: mandatory verified production
  pre-migration custom backup and isolated restore drill; called by
  `server/scripts/run_migrations.py`. Reuses Tech Panel backup/restore markers.

- Tech Panel Runtime includes a bounded Endpoint dependency signal: one typed read-only device request using a saved ticket mapping, two-second timeout, no raw DTO/credentials/identifiers in the snapshot. Configuration readiness alone is not live health; absent mapping is unknown. Dependency failure warns without changing core liveness.

## Safe Endpoint Context boundary

- `domain_ports/endpoint.py` declares the six safe Context port methods;
  `endpoint_context.py` and `endpoint_context_sections.py` own frozen bounded
  fleet/detail/collection/history/diff DTOs with tuple nesting.
- `endpoint_adapter/context_http.py` adds these operations through the verified,
  bounded HTTPS transport in `http.py`. `wire.py` exports the strict wire
  projections. Runtime code does not import Endpoint Platform.
- `integration/endpoint_contract.lock.json` pins exact published provider and
  canonical OpenAPI bytes; `test_endpoint_context_adapter.py` covers projections
  and transport. The Context case in the true cross-repository acceptance
  starts the actual pinned provider with isolated PostgreSQL.
- Boundary contract: `docs/segmentation/HELPDESK_ENDPOINT_CONTEXT_BOUNDARY.md`.

- `web_api/admin_endpoint_handlers.py` exposes authenticated safe Context fleet,
  exact detail, bounded refresh, collection, history and comparison BFF routes
  registered in `routes.py`. Existing auth/CSRF middleware remains authoritative.
- `registry/endpoint_device_overlay.py` projects only exact verified mappings,
  asset business fields and active bounded person relationships in two reads.
  `test_registry_endpoint_device_overlay.py` executes the populated projection
  against isolated PostgreSQL; route/handler checks use actual registration.

- `webapp/src/pages/admin/inventory-page.tsx` is the paginated Endpoint fleet
  with business overlay; `device-page.tsx` loads exact Endpoint UUID only.
  `features/admin/endpoint-context-api.ts` and `endpoint-context-types.ts` are
  their typed BFF client/projections; `endpoint-profile-content.tsx` renders
  safe observations; `endpoint-context-actions.tsx` owns bounded collection
  polling and baseline/inventory history/diff interaction.
- The old `features/admin/admin-workspace.tsx` and
  `device-inventory-panel.tsx` and their local telemetry client methods are
  retired. Admin Center remains in `pages/admin/index.tsx`.
