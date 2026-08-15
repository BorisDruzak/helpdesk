# Observer Profile Completion Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the Observer Web Cabinet check's direct local `RegistryPerson` read while preserving its profile-completion integrity invariant.

**Architecture:** Add one purpose-bound RegistryPort read operation that accepts an opaque `RequesterRef` and a fixed observer-only read context. It returns only profile-completion state and bounded missing field keys; it never returns a person profile, phone, metadata, identities, bindings, or a generic directory result. The observer passes local/unavailable/invalid outcomes through a typed integrity degradation path rather than treating them as clean.

**Tech Stack:** Python 3.12, aiohttp, SQLAlchemy async, Pydantic frozen DTOs, pytest, existing Registry local/HTTP/shadow adapters.

## Global Constraints

- Work only in `C:\Users\admin-2\CodexProjects\pc_client\.worktrees\helpdesk-segmentation-pr0-pr1-pr6`.
- Do not alter UI users, UI/web sessions, RBAC, tickets, consent, local Registry command/session/pairing behavior, or database schema/migrations.
- Use a dedicated observer context, not a forged `RegistryReadActor` from ticket/custom-field data.
- The persisted ticket requester/person reference is opaque data; client payload must never become observer authority.
- Preserve historical direct-read semantics for lifecycle state: existing inactive/archived/disabled/merged people remain evaluable; only an absent row is `RegistryNotFound`.
- External mode remains read-shadow/local-authoritative. Strict HTTP envelope/correlation validation is required before a local source marker is added.
- On unavailable/invalid result, the integrity checker must remain fail-closed and emit redacted degradation evidence; it must not auto-resolve the profile-completion invariant.
- Update port API docs, boundary/CODEMAP docs and import guard in the same change; no browser, deployment, remote DB or push.

---

### Task 1: Add observer-only profile-completion read and cut over Web Cabinet

**Files:**

- Modify: `server/domain_ports/registry_contracts.py`, `server/domain_ports/registry.py`, `server/domain_ports/unavailable.py`
- Modify: `server/registry_adapter/local.py`, `server/registry_adapter/http.py`, `server/registry_adapter/shadow.py`
- Modify: `server/observer/checks/web_cabinet.py`, `server/observer/integrity_service.py`, `scripts/check_domain_import_boundaries.py`
- Test: `server/tests/test_registry_port_rich_projections.py`, `server/tests/test_registry_http_adapter.py`, `server/tests/test_registry_shadow_read.py`, `server/tests/test_observer_web_cabinet.py`, `server/tests/test_observer_integrity_scan_scope.py`, `server/tests/test_domain_import_boundaries.py`
- Modify: `server/docs/REGISTRY_PLATFORM_API_V1.md`, `server/docs/SEGMENTATION_BOUNDARIES.md`, `server/docs/CODEMAP.md`, `docs/QUICK_LOOKUP.md`, `scripts/navigation_catalog.py`

**Interfaces:**

- Consumes: `RequesterRef` plus a frozen `RegistryObserverReadContext(source="observer.web_cabinet")` created by trusted observer composition only.
- Produces: `RequesterProfileCompletionProjection(person, complete, blocks, status, missing_field_keys, source)` or existing typed `RegistryNotFound`, `RegistryInvalidProjection`, `RegistryUnavailable` outcomes.
- Adds: `RegistryPort.requester_profile_completion(observer, person)` implemented by local, HTTP, shadow and unavailable adapters.

- [ ] **Step 1: Write the failing tests**

```python
async def test_web_cabinet_recomputes_completion_through_registry_port_when_snapshot_is_missing():
    result = await check_web_cabinet(session, registry_port=profile_completion_port)
    assert profile_completion_port.calls == [("observer.web_cabinet", "person-1")]

async def test_web_cabinet_emits_degradation_when_profile_completion_port_is_unavailable():
    events = await check_web_cabinet(session, registry_port=UnavailableRegistryPort())
    assert any(event.event_type == "profile_completion_registry_unavailable" for event in events)

async def test_local_profile_completion_keeps_archived_person_evaluable():
    result = await LocalRegistryAdapter(session).requester_profile_completion(observer_context, PersonRef(external_id="archived"))
    assert result.person.external_id == "archived"
```

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest server/tests/test_registry_port_rich_projections.py server/tests/test_observer_web_cabinet.py -q --tb=short
```

Expected: fail because the operation, observer context and port-injected check do not exist.

- [ ] **Step 3: Implement the narrow contract and adapters**

```python
@dataclass(frozen=True)
class RegistryObserverReadContext:
    source: Literal["observer.web_cabinet"]

class RegistryPort(Protocol):
    async def requester_profile_completion(
        self,
        observer: RegistryObserverReadContext,
        person: RequesterRef,
    ) -> RequesterProfileCompletionOutcome: ...
```

The local adapter opens its existing adapter-owned read scope, looks up only the requested person, obtains the existing requester-profile schema inside the adapter, and projects `complete`, `blocks`, safe status and a bounded/deduplicated list of missing field keys. It does not call or expose generic requester profile/directory operations. The HTTP adapter requires the exact outer correlation envelope and exact inner response keys; shadow returns authoritative local values and only records redacted mismatches. `UnavailableRegistryPort` returns its typed unavailable outcome without a database read.

- [ ] **Step 4: Cut the Observer checker over and guard it**

Inject/combine the RegistryPort in `ObserverIntegrityService` and allow direct unit injection in `check_web_cabinet`. Replace `_recompute_profile_completion`'s direct Registry ORM and local profile-schema imports with the purpose-bound port operation. For `RegistryNotFound`, preserve current no-evidence behavior. For unavailable or invalid outcomes, append a redacted `profile_completion_registry_unavailable` or `profile_completion_registry_invalid` integrity event and never treat the profile gate as complete. Add a narrow `observer` import-guard scope that rejects future direct Registry model imports in `server/observer/checks/web_cabinet.py`.

- [ ] **Step 5: Run GREEN and inspect contract boundaries**

Run:

```powershell
python -m pytest server/tests/test_registry_port_rich_projections.py server/tests/test_registry_http_adapter.py server/tests/test_registry_shadow_read.py server/tests/test_observer_web_cabinet.py server/tests/test_observer_integrity_scan_scope.py server/tests/test_domain_import_boundaries.py -q --tb=short
python scripts/check_domain_import_boundaries.py --workspace . --registry-scope observer
python scripts/verify_workspace.py --workspace .
```

Expected: all targeted tests and workspace verification pass; no direct `RegistryPerson` import remains in the observer check.

- [ ] **Step 6: Document and commit**

Document the observer-only endpoint/provenance, redacted output, local-shadow authority, and unavailable/invalid integrity behavior. Update navigation drift triggers for the adapter/observer changes. Commit only the scoped implementation, tests, and docs:

```powershell
git add server/domain_ports server/registry_adapter server/observer scripts/check_domain_import_boundaries.py server/tests server/docs/REGISTRY_PLATFORM_API_V1.md server/docs/SEGMENTATION_BOUNDARIES.md server/docs/CODEMAP.md docs/QUICK_LOOKUP.md scripts/navigation_catalog.py
git commit -m "server: route observer profile checks through RegistryPort"
```
