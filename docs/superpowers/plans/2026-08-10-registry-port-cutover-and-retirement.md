# RegistryPort Cutover and Schema Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Move Helpdesk off local Registry/device-registration persistence while retaining Helpdesk authentication, RBAC, tickets and consent, then retire approved local tables through a rehearsed forward-only migration.

**Architecture:** Tickets and consent records receive immutable redacted requester snapshots plus opaque external identifiers. RegistryPort owns every cross-domain operation: first through a local adapter, then through a versioned external HTTP adapter with shadow reads. PR-11 deletes only the accepted local schema after API cutover, clone rehearsal and backup/restore evidence.

**Tech Stack:** Python 3.14, Pydantic, SQLAlchemy/Alembic, aiohttp, pytest, PostgreSQL, React/TypeScript.

## Global Constraints

- Work only on codex/helpdesk-segmentation-pr0-pr1-pr6; do not deploy or mutate production data.
- Retain ui_users, UI/web sessions, tokens, RBAC, tickets, queues, workflow, Endpoint runtime and user_consent_requests.
- External Registry values are opaque strings; new Helpdesk schema must not contain a Registry FK.
- Never edit historical Alembic revisions or use alembic downgrade for this programme.
- Registry commands and auth eligibility are security-sensitive: no shadow-write and no local fallback after cutover.
- Browser smoke remains deferred until the stand is reachable.

---

### Task 1: Add immutable requester refs and snapshots (PR-2)

**Files:**

- Create: server/app/db/migrations/versions/<next>_requester_external_refs.py
- Modify: server/domain_ports/registry.py, server/app/db/models.py
- Modify: server/app/repos/ticket_events_repo.py, server/app/repos/user_consent_repo.py
- Test: server/tests/test_requester_reference_snapshot.py
- Test: server/tests/test_migration_schema_contract.py

**Interfaces:** produces PersonRef, DeviceRef, BindingRef, RequesterRef and RequesterSnapshot. Produces nullable requester_external_ref and requester_snapshot_json columns on tickets and user_consent_requests; legacy Registry fields remain read-only compatibility data.

- [ ] **Step 1: Write failing contracts**

~~~python
def test_snapshot_contains_only_safe_opaque_data() -> None:
    snapshot = RequesterSnapshot(person=PersonRef(external_id="registry-ref-opaque-1"), display_name="Иван")
    assert snapshot.model_dump(mode="json") == {
        "person": {"external_id": "registry-ref-opaque-1"},
        "display_name": "Иван",
    }
    assert "email" not in snapshot.model_dump(mode="json")
~~~

- [ ] **Step 2: Run RED**

Run: python -m pytest server/tests/test_requester_reference_snapshot.py -q --noconftest

Expected: FAIL because DTOs and columns do not exist.

- [ ] **Step 3: Add validated DTOs and additive schema**

Use frozen Pydantic models; reject local ORM payloads, secrets and mutable profile dictionaries. Persist only validated JSON dumps. Migration adds no FK, creates an external-ref index, and leaves all old Registry columns untouched.

- [ ] **Step 4: Run GREEN and commit**

Run: python -m pytest server/tests/test_requester_reference_snapshot.py server/tests/test_migration_schema_contract.py -q --tb=short

~~~powershell
git add server/domain_ports/registry.py server/app/db/models.py server/app/db/migrations/versions server/app/repos/ticket_events_repo.py server/app/repos/user_consent_repo.py server/tests/test_requester_reference_snapshot.py server/tests/test_migration_schema_contract.py
git commit -m "server: add neutral requester snapshots"
~~~

### Task 2: Persist and read snapshots in ticket and consent flows (PR-2)

**Files:**

- Modify: server/tickets/create_flow.py, server/tickets/ticket_context.py
- Modify: server/tickets/account_access_service.py, server/consent/service.py
- Modify: server/consent/operation_consent.py, server/requester/identity_service.py
- Modify: server/web_api/requester_handlers.py
- Modify: docs/QUICK_LOOKUP.md, server/docs/CODEMAP.md
- Test: server/tests/test_ticket_registration_enrichment.py
- Test: server/tests/test_ticket_account_access.py, server/tests/test_user_consent_api.py

**Interfaces:** consumes Task 1 snapshots. New ticket/consent records prefer neutral refs; legacy fields remain a read-only fallback only for pre-PR-2 rows.

- [ ] **Step 1: Write failing flow tests**

~~~python
async def test_ticket_create_persists_server_verified_snapshot(test_engine):
    ticket = await create_ticket_with_confirmed_binding(test_engine)
    assert ticket.requester_external_ref == "registry-ref-opaque-1"
    assert ticket.requester_snapshot_json == {
        "person": {"external_id": "registry-ref-opaque-1"},
        "display_name": "Иван",
    }

async def test_consent_authorizes_matching_external_ref(test_engine):
    consent = await create_consent_for_external_ref(test_engine, "registry-ref-opaque-1")
    assert await consent_service.get_for_requester(
        consent.consent_id, requester_external_ref="registry-ref-opaque-1"
    )
~~~

- [ ] **Step 2: Run RED**

Run: python -m pytest server/tests/test_ticket_registration_enrichment.py server/tests/test_ticket_account_access.py server/tests/test_user_consent_api.py -q --tb=short

Expected: FAIL because only Registry IDs decide persistence and authorization.

- [ ] **Step 3: Implement dual-read/dual-write**

Build snapshots only from verified server account/binding state, never from HTTP request fields. Prefer neutral values for new records; retain exact legacy authorization behavior for old rows. Pairing and registration decisions must not trust a snapshot.

- [ ] **Step 4: Run GREEN and commit**

Run: python -m pytest server/tests/test_ticket_registration_enrichment.py server/tests/test_ticket_account_access.py server/tests/test_user_consent_api.py server/tests/test_requester_workspace_api.py -q --tb=short; python scripts/docs_drift_check.py --base <task-base> --json

~~~powershell
git add server/tickets server/consent server/requester/identity_service.py server/tests/test_ticket_registration_enrichment.py server/tests/test_ticket_account_access.py server/tests/test_user_consent_api.py server/tests/test_requester_workspace_api.py docs/QUICK_LOOKUP.md server/docs/CODEMAP.md
git commit -m "server: persist requester references independently"
~~~

### Task 3: Expand RegistryPort and compose a local adapter (PR-8)

**Files:**

- Create: server/domain_ports/registry_contracts.py, server/registry_adapter/local.py
- Create: server/registry_adapter/__init__.py
- Modify: server/domain_ports/registry.py, server/domain_ports/container.py, server/config.py
- Test: server/tests/test_registry_port.py

**Interfaces:** produces requester_snapshot, active_binding, account_status, audience_projection, request_registration, approve_registration and revoke_binding. Only server/registry_adapter may import local Registry ORM/repositories.

- [ ] **Step 1: Write failing port tests**

~~~python
async def test_local_adapter_returns_opaque_binding(session):
    result = await LocalRegistryAdapter(session).active_binding(
        DeviceRef(external_id="registry-ref-opaque-device-1")
    )
    assert result.binding.external_id == "registry-ref-opaque-binding-1"
    assert "person_id" not in result.model_dump(mode="json")

async def test_unavailable_command_fails_closed():
    result = await UnavailableRegistryPort().request_registration(
        RegistrationRequest(device=DeviceRef(external_id="registry-ref-opaque-device-1"))
    )
    assert result.code == "registry_unavailable"
~~~

- [ ] **Step 2: Run RED**

Run: python -m pytest server/tests/test_registry_port.py -q --noconftest

Expected: FAIL because RegistryPort exposes availability only.

- [ ] **Step 3: Implement contract, local adapter and composition**

Serialize redacted DTOs only. Compose through REGISTRY_PORT_MODE=local|unavailable|external; default stays local until external acceptance. Commands require stable operation IDs and deterministic idempotency outcomes.

- [ ] **Step 4: Run GREEN and commit**

Run: python -m pytest server/tests/test_registry_port.py server/tests/test_domain_ports.py -q --tb=short; python -m compileall -q server/domain_ports server/registry_adapter

~~~powershell
git add server/domain_ports server/registry_adapter server/config.py server/tests/test_registry_port.py
git commit -m "server: compose local RegistryPort adapter"
~~~

### Task 4: Route Helpdesk reads through RegistryPort and add an import guard (PR-8)

**Files:**

- Modify: server/requester/identity_service.py, server/tickets/create_flow.py
- Modify: server/tickets/ticket_context.py, server/customer_history/sources.py, server/inventory/service.py
- Modify: server/web_api/requester_handlers.py, server/web_api/support_handlers.py
- Modify: server/web_api/dto/support.py
- Modify: scripts/check_domain_import_boundaries.py, server/tests/test_domain_import_boundaries.py
- Test: server/tests/test_registry_boundary.py

**Interfaces:** This first read slice calls only Task 3 operations that exist: requester snapshot, active binding and account status. It emits typed Registry availability/source data in the support DTO. Rich requester profile, on-behalf directory search, customer-history and inventory projections are deferred to Task 5, which expands the port contract. During this incremental Task 4 slice, the Registry import guard enforces only the precise migrated modules; repository-wide enforcement starts only after every remaining consumer has been cut over.

- [ ] **Step 1: Write failing boundary tests**

~~~python
def test_registry_guard_rejects_ticket_orm_import(tmp_path: Path) -> None:
    source = tmp_path / "server/tickets/bad.py"
    source.parent.mkdir(parents=True)
    source.write_text("from app.db.models import RegistryPerson\n", encoding="utf-8")
    assert run_check(tmp_path).returncode == 1

async def test_support_uses_ticket_snapshot_when_registry_unavailable(test_client):
    payload = await support_ticket_payload_with_unavailable_registry(test_client)
    assert payload["requester"]["source"] == "ticket_snapshot"
~~~

- [ ] **Step 2: Run RED**

Run: python -m pytest server/tests/test_domain_import_boundaries.py server/tests/test_registry_boundary.py -q --tb=short

Expected: FAIL while Helpdesk imports Registry ORM/services.

- [ ] **Step 3: Inject and consume the port**

Use DomainPortContainer.registry at composition boundaries for only the available Task 3 operations. When unavailable, render immutable ticket history and a typed degraded current-state result; never add a direct local fallback outside the adapter. Leave rich Registry consumers unchanged but enumerate them in the report rather than claiming they were migrated.

- [ ] **Step 4: Run GREEN and commit**

Run: python -m pytest server/tests/test_domain_import_boundaries.py server/tests/test_registry_boundary.py server/tests/test_requester_workspace_api.py server/tests/test_web_support_api.py -q --tb=short; python scripts/check_domain_import_boundaries.py --workspace . --registry-scope requester,tickets,customer_history,inventory,web_api

~~~powershell
git add server/requester server/tickets server/customer_history server/inventory server/web_api scripts/check_domain_import_boundaries.py server/tests
git commit -m "server: route Helpdesk reads through RegistryPort"
~~~

### Task 5: Expand RegistryPort for rich read projections (PR-8)

**Files:**

- Modify: server/domain_ports/registry_contracts.py, server/domain_ports/registry.py
- Modify: server/registry_adapter/local.py, server/registry_adapter/__init__.py
- Test: server/tests/test_registry_port_rich_projections.py

**Interfaces:** produces redacted, immutable requester profile, directory-person, device context and requester-history projections with typed unavailable/not-found/invalid outcomes. These contracts replace the local data needed by requester profile, on-behalf search, customer history and inventory without exposing ORM metadata or raw identities.

- [ ] **Step 1: Write failing rich-projection tests**

~~~python
async def test_local_port_directory_search_returns_only_safe_person_projection(session):
    result = await LocalRegistryAdapter(session).search_people("Иван")
    assert result.items[0].display_name == "Иван"
    assert "email" not in result.items[0].model_dump(mode="json")

async def test_device_context_is_typed_unavailable_without_local_fallback():
    result = await UnavailableRegistryPort().device_context(DeviceRef(external_id="registry-ref-opaque-device-1"))
    assert result.code == "registry_unavailable"
~~~

- [ ] **Step 2: Run RED**

Run: python -m pytest server/tests/test_registry_port_rich_projections.py -q --noconftest

Expected: FAIL because the rich projection operations do not exist.

- [ ] **Step 3: Add bounded redacted read contracts**

Require trusted actor context for audience or directory visibility, cap every collection, distinguish missing from invalid projections, and isolate local adapter read errors so a failed statement cannot leave a caller session aborted. Resolve the three Task 3 deferred review items here: actor-aware audience projection, savepoint/diagnostic handling, and invalid-versus-not-found outcomes.

- [ ] **Step 4: Run GREEN and commit**

Run: python -m pytest server/tests/test_registry_port.py server/tests/test_registry_port_rich_projections.py -q --tb=short; python -m compileall -q server/domain_ports server/registry_adapter

~~~powershell
git add server/domain_ports server/registry_adapter server/tests/test_registry_port.py server/tests/test_registry_port_rich_projections.py
git commit -m "server: expand RegistryPort read projections"
~~~

### Task 6: Add a versioned external HTTP adapter and shadow reads (PR-9)

**Files:**

- Create: server/registry_adapter/http.py, server/docs/REGISTRY_PLATFORM_API_V1.md
- Modify: server/config.py, server/domain_ports/container.py, server/registry_adapter/local.py
- Test: server/tests/test_registry_http_adapter.py, server/tests/test_registry_shadow_read.py

**Interfaces:** produces authenticated v1 read projections and redacted shadow-comparison evidence. Commands and auth stay local in this task.

- [ ] **Step 1: Write failing HTTP/shadow tests**

~~~python
async def test_http_adapter_returns_redacted_snapshot(mock_server):
    result = await adapter.requester_snapshot(PersonRef(external_id="registry-ref-opaque-1"))
    assert result.display_name == "Иван"
    assert "email" not in result.model_dump(mode="json")

async def test_shadow_mismatch_never_changes_authorization():
    result = await shadow_port.active_binding(DeviceRef(external_id="registry-ref-opaque-device-1"))
    assert result.source == "local_authoritative"
~~~

- [ ] **Step 2: Run RED**

Run: python -m pytest server/tests/test_registry_http_adapter.py server/tests/test_registry_shadow_read.py -q --noconftest

Expected: FAIL because HTTP/shadow implementation does not exist.

- [ ] **Step 3: Implement flags and secure comparisons**

Specify service auth scope, timeout, correlation ID, registry_unavailable mapping and no sensitive payload logging. Shadow reads compare only redacted fields after returning the local authoritative result. No command makes a shadow call.

- [ ] **Step 4: Run GREEN and commit**

Run: python -m pytest server/tests/test_registry_http_adapter.py server/tests/test_registry_shadow_read.py server/tests/test_registry_port.py -q --tb=short

~~~powershell
git add server/registry_adapter server/docs/REGISTRY_PLATFORM_API_V1.md server/config.py server/domain_ports/container.py server/tests/test_registry_http_adapter.py server/tests/test_registry_shadow_read.py
git commit -m "server: add RegistryPort shadow reads"
~~~

### Task 7: Specify Registry command and eligibility API acceptance contract (PR-9 prerequisite)

**Files:**

- Create: server/docs/REGISTRY_PLATFORM_COMMANDS_V1.md
- Modify: server/docs/REGISTRY_PLATFORM_API_V1.md, docs/QUICK_LOOKUP.md, server/docs/CODEMAP.md
- Test: server/tests/test_registry_commands_api_docs.py

**Interfaces:** documents the minimum external Registry command/eligibility surface required before any authority changes: UI-login eligibility, registration request/approve/reject/bind/revoke, session create/validate/logout/revoke and exactly-once delivery, browser pairing create/lookup/confirm/pickup, and other-account approval. Every command requires trusted actor context, an operation idempotency key, correlation ID, replay semantics, typed availability and authorization errors. No runtime feature flag changes; no external authority is enabled.

- [ ] **Step 1: Write failing API-contract tests**

Assert the document declares HTTPS service authentication, no raw token logging, idempotency/replay rules, authoritative actor authorization, fail-closed uncertainty, immutable ticket/consent reference rules, and the protected Helpdesk-owned `ui_users`/web-session/RBAC boundary.

- [ ] **Step 2: Run RED**

Run: python -m pytest server/tests/test_registry_commands_api_docs.py -q --noconftest

Expected: FAIL because the command API acceptance contract does not exist.

- [ ] **Step 3: Publish the minimal non-runtime contract**

Do not add a command transport implementation or enable any cutover flag. Add external service preflight probes and per-operation acceptance evidence that a later task must satisfy before it can change authority.

- [ ] **Step 4: Run GREEN and commit**

Run: python -m pytest server/tests/test_registry_commands_api_docs.py server/tests/test_segmentation_docs.py -q --noconftest

~~~powershell
git add server/docs/REGISTRY_PLATFORM_COMMANDS_V1.md server/docs/REGISTRY_PLATFORM_API_V1.md docs/QUICK_LOOKUP.md server/docs/CODEMAP.md server/tests/test_registry_commands_api_docs.py
git commit -m "docs: specify Registry command API acceptance"
~~~

### Task 8: Cut over Registry commands and authentication eligibility (PR-9 acceptance)

**Files:**

- Modify: server/auth/service.py, server/registry/account_state_service.py
- Modify: server/registry/registration_service.py, server/registry/browser_pairing_service.py
- Modify: server/consent/service.py, server/web_api/session_handlers.py, server/web_api/registry_handlers.py
- Test: server/tests/test_registry_command_cutover.py, server/tests/test_account_session_delivery_no_db.py

**Interfaces:** consumes idempotent external Registry command acknowledgements. Produces local-auth independence from RegistryPersonIdentity and no fallback after a command flag is enabled.

- [ ] **Step 1: Write failing security tests**

~~~python
async def test_login_uses_external_eligibility_not_local_identity(session):
    await retire_local_identity_row(session)
    assert await authenticate_ui_user("alice", "password")

async def test_registration_command_is_idempotent():
    first = await port.request_registration(request)
    second = await port.request_registration(request)
    assert first.operation_id == second.operation_id
~~~

- [ ] **Step 2: Run RED**

Run: python -m pytest server/tests/test_registry_command_cutover.py server/tests/test_account_session_delivery_no_db.py server/tests/test_ticket_account_access.py -q --tb=short

Expected: FAIL while auth/session/pairing commands use local Registry tables.

- [ ] **Step 3: Cut commands in acceptance order**

First externalize login eligibility or a Helpdesk-owned immutable status snapshot. Then move registration, binding, account-session and browser-pairing commands one operation at a time. Each operation uses an idempotency key and typed availability error; delete a local route only after replacement acceptance.

- [ ] **Step 4: Run GREEN and commit**

Run: python -m pytest server/tests/test_registry_command_cutover.py server/tests/test_account_session_delivery_no_db.py server/tests/test_ticket_account_access.py server/tests/test_registration_api.py -q --tb=short

~~~powershell
git add server/auth server/registry server/consent server/web_api server/tests
git commit -m "server: cut over Registry commands"
~~~

### Task 9: Build non-destructive Knowledge/Registry retirement preflight (PR-11 prerequisite)

**Files:**

- Create: scripts/registry_retirement_manifest.py, scripts/rehearse_registry_retirement.py
- Create: server/tests/test_registry_retirement_preflight.py
- Modify: scripts/audit_db_cleanup_schema.py
- Modify: server/docs/DATABASE.md, server/docs/RUNBOOK_BACKUP_RESTORE.md, server/docs/SEGMENTATION_BOUNDARIES.md

**Interfaces:** produces a declarative target/retain manifest and no-write verifier. It fails while local Registry command/auth/session/pairing runtime, routes, or consumers remain; it never runs DDL. The manifest explicitly retains `ui_users`, web sessions/RBAC, tickets, `user_consent_requests` and `ticket_kb_links`.

- [ ] **Step 1: Write failing preflight tests**

~~~python
def test_retirement_manifest_preserves_helpdesk_owned_tables():
    assert RETIREMENT_MANIFEST.retain_tables >= {
        "ui_users", "tickets", "user_consent_requests", "ticket_kb_links"
    }

def test_preflight_rejects_active_registry_runtime(tmp_path):
    assert run_preflight(tmp_path).ready is False
~~~

- [ ] **Step 2: Run RED**

Run: python -m pytest server/tests/test_registry_retirement_preflight.py -q --noconftest

Expected: FAIL because the manifest/verifier does not yet exist.

- [ ] **Step 3: Implement manifest, verifier and forward rollback runbook**

Require proof gates for no local Registry runtime/routes/writers, external command acceptance, maintenance/advisory-lock plan, counts and backup hash. Record the later reverse-FK drop order: account events/pairings, sessions/login requests, registration events/bindings/claims, identities/audiences/governance, assets/people/services and roots; detached ticket/consent legacy Registry columns; then approved Knowledge/AI tables. Never include `ui_users`, UI sessions/RBAC, tickets, `user_consent_requests` or `ticket_kb_links`. Rollback is application rollback plus a tested DB restore, never Alembic downgrade.

- [ ] **Step 4: Verify GREEN and commit**

Run: python scripts/rehearse_registry_retirement.py --workspace . --dry-run; python -m pytest server/tests/test_registry_retirement_preflight.py server/tests/test_migration_schema_contract.py -q --tb=short; python scripts/audit_db_cleanup_schema.py --schema-from-models --strict

~~~powershell
git add scripts/rehearse_registry_retirement.py scripts/registry_retirement_manifest.py server/tests/test_registry_retirement_preflight.py scripts/audit_db_cleanup_schema.py server/docs/DATABASE.md server/docs/RUNBOOK_BACKUP_RESTORE.md server/docs/SEGMENTATION_BOUNDARIES.md
git commit -m "scripts: add Registry retirement preflight"
~~~

### Task 10: Retire the already-dead local Knowledge/AI physical schema (PR-11a)

**Prerequisites:** Knowledge runtime/routes/ORM are absent; clone tests prove the migration removes only the static historical Knowledge/AI target graph. This task does not depend on the external Registry command gate.

**Interfaces:** produces Alembic revision 134 that drops only retired Knowledge/AI tables, `ticket_knowledge_links` and `problem_known_error_links`, in static historical reverse-FK order. It preserves `ticket_kb_links`, tickets, problems, ticket resolution passports, UI users/sessions/RBAC and every Registry table.

- [ ] **Step 1: Write clone migration tests from revision 133**
- [ ] **Step 2: Encode the historical Knowledge FK graph; do not derive it from deleted ORM models**
- [ ] **Step 3: Implement an upgrade-only migration; downgrade instructs verified backup restore**
- [ ] **Step 4: Prove fresh clone 133→134 and head idempotency; update audit/docs**

### Task 11: Apply forward-only Registry retirement (PR-11b)

**Prerequisites:** Task 8 has external command/auth/session/pairing acceptance evidence for every local writer; Task 9 returns ready against the release candidate; Task 10 has already removed Knowledge/AI targets; a fresh encrypted backup and restore drill have passed on an isolated clone; maintenance window and advisory lock are approved.

**Interfaces:** produces a new Alembic head without approved local Registry/registration tables/FKs. The migration never drops `ui_users`, web sessions/RBAC, tickets, `user_consent_requests` or `ticket_kb_links`.

- [ ] **Step 1: Write failing clone-migration contract tests**
- [ ] **Step 2: Implement a forward-only idempotent migration and rehearsal**
- [ ] **Step 3: Prove clone upgrade, catalog/FK/count audit and backup restore**
- [ ] **Step 4: Apply only after release acceptance; rollback by verified restore, never downgrade**

### Task 12: Route customer-history reads through RegistryPort (PR-8 completion)

**Files:**

- Modify: server/customer_history/sources.py, server/customer_history/projection_service.py
- Modify: scripts/check_domain_import_boundaries.py, server/tests/test_domain_import_boundaries.py
- Test: server/tests/test_customer_history_projection.py, server/tests/test_customer_history_context_builder.py, server/tests/test_registry_boundary.py
- Modify: docs/QUICK_LOOKUP.md, server/docs/CODEMAP.md, server/docs/SEGMENTATION_BOUNDARIES.md

**Interfaces:** consumes `RegistryPort.requester_history()` with a trusted server-side `RegistryReadActor`, then projects its redacted events to the existing customer-history API shape. `unavailable`, `not_found` and `invalid` become typed degraded source states; no direct Registry ORM/session fallback is allowed. This task does not change ticket history queries, auth/session/registration commands, or external authority.

- [ ] **Step 1: Write failing boundary and actor-spoofing tests**
- [ ] **Step 2: Replace `DeviceUserBinding`/`DeviceAccountSession` source reads with the port**
- [ ] **Step 3: Remove exact customer-history import allowances and prove the scoped guard**
- [ ] **Step 4: Run API regression, docs drift and commit**

### Task 13: Make ticket customer-history neutral-reference-first (PR-2/PR-11 prerequisite)

**Files:**

- Modify: server/customer_history/projection_service.py, server/customer_history/context_builder.py, server/customer_history/sources.py, server/customer_history/handlers.py
- Modify: server/tickets/ticket_context.py only if existing neutral/legacy scope helpers need reuse
- Test: server/tests/test_customer_history_projection.py, server/tests/test_customer_history_context_builder.py, server/tests/test_registry_boundary.py
- Modify: server/docs/TICKET_SYSTEM.md, server/docs/CODEMAP.md, server/docs/SEGMENTATION_BOUNDARIES.md, docs/QUICK_LOOKUP.md

**Interfaces:** treats a history subject as an opaque `RequesterRef.external_id`, not a local Registry primary key. Canonical tickets match only a valid neutral pair and exact `requester_external_ref`; legacy fallback matches only legacy-scoped `requester_person_id`. `Ticket.requester_id` is never a person-history alias. Requester-derived ref remains server verified; malformed neutral data matches neither path.

- [ ] **Step 1: Write failing canonical/legacy/anti-collision tests**
- [ ] **Step 2: Convert projection, handlers and context pack to opaque requester refs**
- [ ] **Step 3: Preserve legacy creator/affected aliases only for legacy rows; add typed absence/degradation where needed**
- [ ] **Step 4: Run DB/API regression, docs drift and commit**

### Task 14: Route tech inventory-quality aggregate through RegistryPort (PR-8 completion)

**Interfaces:** adds a redacted bounded `InventoryQualityProjection(active_pc_without_location_count)` to local/HTTP/shadow adapters, then replaces the one direct `RegistryAsset` aggregate in tech handlers. It must not approximate the aggregate with per-device lookups or expose asset/person identifiers.

### Task 15: Route ticket participant context reads through RegistryPort (PR-8 completion)

**Files:**

- Modify: `server/domain_ports/registry_contracts.py`, `server/domain_ports/registry.py`, `server/domain_ports/unavailable.py`
- Modify: `server/registry_adapter/local.py`, `server/registry_adapter/http.py`, `server/docs/REGISTRY_PLATFORM_API_V1.md`
- Modify: `server/tickets/ticket_context.py`, `scripts/check_domain_import_boundaries.py`
- Test: `server/tests/test_registry_port_rich_projections.py`, `server/tests/test_registry_http_adapter.py`, `server/tests/test_registry_shadow_read.py`, `server/tests/test_ticket_context_builder.py`, `server/tests/test_domain_import_boundaries.py`
- Modify only as needed for contract drift: `docs/QUICK_LOOKUP.md`, `server/docs/CODEMAP.md`, `server/docs/SEGMENTATION_BOUNDARIES.md`, `docs/ARCHITECTURE_BOUNDARIES.md`, `scripts/navigation_catalog.py`

**Interfaces:** adds an immutable, purpose-bound `TicketParticipantProjection` for an existing ticket-context snapshot. It returns exactly the already persisted participant fields: opaque person ref, display name, full name, email, and opaque department/location refs, plus local/external source; no local numeric IDs, identities, bindings, assets, sessions, or policy metadata. Local and HTTP/shadow adapters distinguish unavailable, missing and malformed outcomes. `TicketContextBuilder.build()` loads creator and affected participants only through the port, validates that returned opaque refs match requested refs, and fails closed on missing/unavailable/invalid projection; it preserves the existing `ticket_context_v1` and flat-field behavior. It removes the direct `RegistryPerson` import/allowance, but deliberately retains the separate `PrimaryAgentResolver` debt until its own richer diagnostic-target contract is accepted. The external HTTP endpoint is service-to-service only and must validate an exact envelope before Helpdesk adds its source marker.

- [ ] **Step 1: Write RED contract and ticket-context tests**

```python
async def test_ticket_participant_projection_preserves_existing_ticket_context_fields(session):
    result = await LocalRegistryAdapter(session).ticket_participant(PersonRef(external_id="person-1"))
    assert result.person.external_id == "person-1"
    assert result.email == "person-1@example.test"
    assert result.department.external_id == "department-1"

async def test_ticket_context_fails_closed_when_participant_ref_does_not_match():
    with pytest.raises(ValueError, match="ticket participant Registry projection is invalid"):
        await TicketContextBuilder(session, registry_port=mismatched_port).build(creator_person_id="person-1")
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest server/tests/test_registry_port_rich_projections.py server/tests/test_ticket_context_builder.py -q --tb=short`

Expected: FAIL because the ticket-participant operation and port-only builder path do not exist.

- [ ] **Step 3: Implement exact read projection and cutover**

Use frozen DTOs and existing opaque-ref validation. Keep all existing ticket-context participant fields; do not replace department/location refs with labels or omit email/full name. Validate HTTP payload keys before local provenance injection; never directly query Registry ORM from tickets. Leave `PrimaryAgentResolver` untouched and explicitly guarded as deferred debt.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest server/tests/test_registry_port.py server/tests/test_registry_port_rich_projections.py server/tests/test_registry_http_adapter.py server/tests/test_registry_shadow_read.py server/tests/test_ticket_context_builder.py server/tests/test_domain_import_boundaries.py -q --tb=short`; `python scripts/check_domain_import_boundaries.py --workspace . --registry-scope requester,tickets,customer_history,inventory,web_api,tech`; `python scripts/docs_drift_check.py --base <task-base> --json`

```powershell
git add server/domain_ports server/registry_adapter server/tickets/ticket_context.py scripts/check_domain_import_boundaries.py server/tests server/docs/REGISTRY_PLATFORM_API_V1.md docs/QUICK_LOOKUP.md server/docs/CODEMAP.md server/docs/SEGMENTATION_BOUNDARIES.md docs/ARCHITECTURE_BOUNDARIES.md scripts/navigation_catalog.py docs/superpowers/plans/2026-08-10-registry-port-cutover-and-retirement.md
git commit -m "server: route ticket participants through RegistryPort"
```

## Plan self-review

- Coverage: PR-2 is Tasks 1–2 and 13, PR-8 is Tasks 3–5 and 12–15, PR-9 is Tasks 6–8, PR-11 preflight is Task 9, Knowledge retirement is Task 10 and Registry retirement is Task 11.
- Safety: no schema deletion precedes external command/auth acceptance, clone rehearsal, backup and restore evidence.
- Consistency: all cross-domain values use opaque Task 1 refs; RegistryPort is the only Helpdesk interface after Task 4.
- Explicit exclusions: UI users/sessions/RBAC, tickets and consent tables remain; browser smoke is a later deployment gate.
