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
- Modify: server/app/repos/tickets_repo.py, server/app/repos/user_consent_repo.py
- Test: server/tests/test_requester_reference_snapshot.py
- Test: server/tests/test_migration_schema_contract.py

**Interfaces:** produces PersonRef, DeviceRef, BindingRef, RequesterRef and RequesterSnapshot. Produces nullable requester_external_ref and requester_snapshot_json columns on tickets and user_consent_requests; legacy Registry fields remain read-only compatibility data.

- [ ] **Step 1: Write failing contracts**

~~~python
def test_snapshot_contains_only_safe_opaque_data() -> None:
    snapshot = RequesterSnapshot(person=PersonRef(external_id="person:p-1"), display_name="Иван")
    assert snapshot.model_dump(mode="json") == {
        "person": {"external_id": "person:p-1"},
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
git add server/domain_ports/registry.py server/app/db/models.py server/app/db/migrations/versions server/app/repos/tickets_repo.py server/app/repos/user_consent_repo.py server/tests/test_requester_reference_snapshot.py server/tests/test_migration_schema_contract.py
git commit -m "server: add neutral requester snapshots"
~~~

### Task 2: Persist and read snapshots in ticket and consent flows (PR-2)

**Files:**

- Modify: server/tickets/create_flow.py, server/tickets/ticket_context.py
- Modify: server/tickets/account_access_service.py, server/consent/service.py
- Modify: server/consent/operation_consent.py, server/requester/identity_service.py
- Test: server/tests/test_ticket_registration_enrichment.py
- Test: server/tests/test_ticket_account_access.py, server/tests/test_user_consent_api.py

**Interfaces:** consumes Task 1 snapshots. New ticket/consent records prefer neutral refs; legacy fields remain a read-only fallback only for pre-PR-2 rows.

- [ ] **Step 1: Write failing flow tests**

~~~python
async def test_ticket_create_persists_server_verified_snapshot(test_engine):
    ticket = await create_ticket_with_confirmed_binding(test_engine)
    assert ticket.requester_external_ref == "person:p-1"
    assert ticket.requester_snapshot_json == {
        "person": {"external_id": "person:p-1"},
        "display_name": "Иван",
    }

async def test_consent_authorizes_matching_external_ref(test_engine):
    consent = await create_consent_for_external_ref(test_engine, "person:p-1")
    assert await consent_service.get_for_requester(
        consent.consent_id, requester_external_ref="person:p-1"
    )
~~~

- [ ] **Step 2: Run RED**

Run: python -m pytest server/tests/test_ticket_registration_enrichment.py server/tests/test_ticket_account_access.py server/tests/test_user_consent_api.py -q --tb=short

Expected: FAIL because only Registry IDs decide persistence and authorization.

- [ ] **Step 3: Implement dual-read/dual-write**

Build snapshots only from verified server account/binding state, never from HTTP request fields. Prefer neutral values for new records; retain exact legacy authorization behavior for old rows. Pairing and registration decisions must not trust a snapshot.

- [ ] **Step 4: Run GREEN and commit**

Run: python -m pytest server/tests/test_ticket_registration_enrichment.py server/tests/test_ticket_account_access.py server/tests/test_user_consent_api.py server/tests/test_requester_workspace_api.py -q --tb=short

~~~powershell
git add server/tickets server/consent server/requester/identity_service.py server/tests/test_ticket_registration_enrichment.py server/tests/test_ticket_account_access.py server/tests/test_user_consent_api.py server/tests/test_requester_workspace_api.py
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
        DeviceRef(external_id="device:d-1")
    )
    assert result.binding.external_id.startswith("binding:")
    assert "person_id" not in result.model_dump(mode="json")

async def test_unavailable_command_fails_closed():
    result = await UnavailableRegistryPort().request_registration(
        RegistrationRequest(device=DeviceRef(external_id="device:d-1"))
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
- Modify: scripts/check_domain_import_boundaries.py, server/tests/test_domain_import_boundaries.py
- Test: server/tests/test_registry_boundary.py

**Interfaces:** Helpdesk reads call Task 3 port operations. server/registry_adapter, migrations and adapter tests are the only permitted local Registry imports.

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

Use DomainPortContainer.registry at composition boundaries. When unavailable, render immutable ticket history and a typed degraded current-state result; never add a direct local fallback outside the adapter.

- [ ] **Step 4: Run GREEN and commit**

Run: python -m pytest server/tests/test_domain_import_boundaries.py server/tests/test_registry_boundary.py server/tests/test_requester_workspace_api.py server/tests/test_web_support_api.py -q --tb=short; python scripts/check_domain_import_boundaries.py --workspace .

~~~powershell
git add server/requester server/tickets server/customer_history server/inventory server/web_api scripts/check_domain_import_boundaries.py server/tests
git commit -m "server: route Helpdesk reads through RegistryPort"
~~~

### Task 5: Add a versioned external HTTP adapter and shadow reads (PR-9)

**Files:**

- Create: server/registry_adapter/http.py, server/docs/REGISTRY_PLATFORM_API_V1.md
- Modify: server/config.py, server/domain_ports/container.py, server/registry_adapter/local.py
- Test: server/tests/test_registry_http_adapter.py, server/tests/test_registry_shadow_read.py

**Interfaces:** produces authenticated v1 read projections and redacted shadow-comparison evidence. Commands and auth stay local in this task.

- [ ] **Step 1: Write failing HTTP/shadow tests**

~~~python
async def test_http_adapter_returns_redacted_snapshot(mock_server):
    result = await adapter.requester_snapshot(PersonRef(external_id="person:p-1"))
    assert result.display_name == "Иван"
    assert "email" not in result.model_dump(mode="json")

async def test_shadow_mismatch_never_changes_authorization():
    result = await shadow_port.active_binding(DeviceRef(external_id="device:d-1"))
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

### Task 6: Cut over Registry commands and authentication eligibility (PR-9 acceptance)

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

### Task 7: Rehearse forward-only Knowledge/Registry schema retirement (PR-11)

**Files:**

- Create: server/app/db/migrations/versions/<next>_retire_local_registry_and_knowledge.py
- Create: scripts/rehearse_registry_retirement.py, server/tests/test_registry_retirement_migration.py
- Modify: scripts/audit_db_cleanup_schema.py, server/app/db/models.py
- Modify: server/docs/DATABASE.md, server/docs/RUNBOOK_BACKUP_RESTORE.md, server/docs/SEGMENTATION_BOUNDARIES.md

**Interfaces:** consumes PR-9 proof of no local Registry runtime and an approved backup. Produces a new Alembic head without approved target tables/FKs; rollback is a tested restore.

- [ ] **Step 1: Write failing clone-migration tests**

~~~python
async def test_retirement_drops_only_approved_tables(isolated_database):
    await upgrade_from_revision(isolated_database, "132")
    await upgrade_head(isolated_database)
    assert await catalog_has_no_tables(isolated_database, RETIRED_LOCAL_TABLES)
    assert await catalog_has_tables(
        isolated_database, {"ui_users", "tickets", "user_consent_requests"}
    )
~~~

- [ ] **Step 2: Run RED**

Run: python -m pytest server/tests/test_registry_retirement_migration.py -q --tb=short

Expected: FAIL before the retirement migration because target tables and FKs remain.

- [ ] **Step 3: Implement migration, rehearsal and runbook**

Require advisory lock, maintenance mode, counts and backup hash. Detach ticket and consent legacy FK columns first, then drop child tables in reverse FK order: account events/pairings, sessions/login requests, registration events/bindings/claims, identities/audiences/governance, assets/people/services and remaining roots. Drop approved Knowledge/AI tables in the same migration. Never drop ui_users, RBAC, tickets or user_consent_requests. The rehearsal script performs backup, clone migration, catalog/count audit and restore drill.

- [ ] **Step 4: Verify GREEN and commit**

Run: python scripts/rehearse_registry_retirement.py --workspace . --dry-run; python -m pytest server/tests/test_registry_retirement_migration.py server/tests/test_migration_schema_contract.py -q --tb=short; python scripts/audit_db_cleanup_schema.py --schema-from-models --strict

~~~powershell
git add server/app/db/migrations/versions scripts/rehearse_registry_retirement.py server/tests/test_registry_retirement_migration.py scripts/audit_db_cleanup_schema.py server/app/db/models.py server/docs/DATABASE.md server/docs/RUNBOOK_BACKUP_RESTORE.md server/docs/SEGMENTATION_BOUNDARIES.md
git commit -m "server: retire local Registry and Knowledge schema"
~~~

## Plan self-review

- Coverage: PR-2 is Tasks 1–2, PR-8 is Tasks 3–4, PR-9 is Tasks 5–6, PR-11 is Task 7.
- Safety: no schema deletion precedes external command/auth acceptance, clone rehearsal, backup and restore evidence.
- Consistency: all cross-domain values use opaque Task 1 refs; RegistryPort is the only Helpdesk interface after Task 4.
- Explicit exclusions: UI users/sessions/RBAC, tickets and consent tables remain; browser smoke is a later deployment gate.

