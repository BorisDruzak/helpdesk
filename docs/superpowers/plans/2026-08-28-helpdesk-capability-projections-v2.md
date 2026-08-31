# Helpdesk Capability Projections v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the typed Endpoint capability catalog port and closed v2 result projections.

**Architecture:** The HTTPS adapter validates the Endpoint catalog into immutable Helpdesk DTOs; BFF and Workbench consume those DTOs rather than a local capability authority. A closed result-projector registry creates only safe v2 snapshots while retaining v1 readers.

**Tech Stack:** Python 3.14, aiohttp, Pydantic v2, pytest.

**Spec:** `docs/superpowers/specs/2026-08-28-helpdesk-readonly-capability-batch-v2-design.md`

## Global Constraints

- Begin after recording the merged EP1/EP2 SHA and OpenAPI digest in the immutable provider lock.
- Use only `GET /api/v1/module-capabilities`; no generic proxy, browser-to-Endpoint path or agent dispatch.
- Reject unknown fields, IDs, parameters, values, schema versions and result shapes; retain default-off feature flags.
- Preserve v1 historical snapshots; never rewrite Alembic history or evidence.

---

### Task 1: Model the catalog boundary

**Files:**
- Modify: `server/domain_ports/endpoint_modules.py:60-280`
- Modify: `server/domain_ports/unavailable.py:245-310`
- Modify: `server/domain_ports/__init__.py`
- Test: `server/tests/test_endpoint_modules_port_contracts.py`

**Interfaces:** Produces `EndpointModuleCapabilityCatalogOutcome` and `EndpointModulePort.list_recipe_capabilities()`.

- [ ] **Step 1: Write failing contract tests**

```python
async def test_unavailable_port_rejects_catalog() -> None:
    assert (await UnavailableEndpointModulePort().list_recipe_capabilities()).status == "unavailable"
```

- [ ] **Step 2: Run the focused test**

Run: `python -m pytest server/tests/test_endpoint_modules_port_contracts.py -q --tb=short`

Expected: FAIL because the method and catalog DTOs are absent.

- [ ] **Step 3: Add immutable DTOs and protocol method**

```python
class EndpointModuleCapabilityCatalog(_ImmutableEndpointModuleDTO):
    schema_version: Literal["endpoint_module_capability_catalog_v1"]
    items: tuple[EndpointModuleCapabilityDescriptor, ...] = Field(max_length=6)
```

Descriptors permit only `string|integer|enum`, `input|literal`, exact bounds and `secret=False`.

- [ ] **Step 4: Implement unavailable outcome and exports**

```python
async def list_recipe_capabilities(self) -> EndpointModuleCapabilityCatalogOutcome:
    return self._unavailable
```

- [ ] **Step 5: Verify and commit**

Run: `python -m pytest server/tests/test_endpoint_modules_port_contracts.py -q --tb=short`

```powershell
git add server/domain_ports/endpoint_modules.py server/domain_ports/unavailable.py server/domain_ports/__init__.py server/tests/test_endpoint_modules_port_contracts.py
git commit -m "feat(modules): add capability catalog port contracts"
```

### Task 2: Validate the fixed external catalog route

**Files:**
- Create: `server/endpoint_adapter/modules_catalog_wire.py`
- Modify: `server/endpoint_adapter/modules_http.py:1-330`
- Test: `server/tests/test_endpoint_modules_http_adapter.py`

**Interfaces:** Consumes Task 1 DTOs; produces a validated catalog outcome.

- [ ] **Step 1: Write failing adapter tests**

```python
async def test_catalog_uses_only_fixed_get_route(client) -> None:
    await adapter.list_recipe_capabilities()
    assert client.requests == [("GET", "/api/v1/module-capabilities")]
```

- [ ] **Step 2: Run the focused test**

Run: `python -m pytest server/tests/test_endpoint_modules_http_adapter.py -q --tb=short`

Expected: FAIL because no catalog wire DTO exists.

- [ ] **Step 3: Add closed wire DTOs**

```python
class ModuleCapabilityCatalogWireV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["endpoint_module_capability_catalog_v1"]
```

- [ ] **Step 4: Map only the fixed GET response**

```python
payload = await self._request("GET", "/api/v1/module-capabilities", expected_statuses=frozenset({200}))
return _catalog_projection_from_wire(ModuleCapabilityCatalogWireV1.model_validate(payload))
```

- [ ] **Step 5: Verify and commit**

Run: `python -m pytest server/tests/test_endpoint_modules_http_adapter.py server/tests/test_endpoint_modules_port_contracts.py -q --tb=short`

```powershell
git add server/endpoint_adapter/modules_catalog_wire.py server/endpoint_adapter/modules_http.py server/tests/test_endpoint_modules_http_adapter.py
git commit -m "feat(modules): validate external capability catalog"
```

### Task 3: Expose the typed BFF catalog

**Files:**
- Modify: `server/web_api/endpoint_module_handlers.py:87-145`
- Modify: `server/routes.py:700-770`
- Test: `server/tests/test_endpoint_module_bff.py`

**Interfaces:** Consumes Task 1; produces one authenticated `data` envelope for authoring metadata.

- [ ] **Step 1: Write failing authorization/redaction tests**

```python
async def test_catalog_bff_requires_modules_read_permission(client) -> None:
    assert (await client.get("/api/web/admin/endpoint-modules/capabilities")).status == 403
```

- [ ] **Step 2: Run the BFF test**

Run: `python -m pytest server/tests/test_endpoint_module_bff.py -q --tb=short`

Expected: FAIL because the BFF route is absent.

- [ ] **Step 3: Add one GET BFF route**

```python
@require_auth("admin", "auditor")
async def handle_endpoint_module_capabilities(request: web.Request) -> web.Response:
    return _catalog_response_or_failure(await _port(request).list_recipe_capabilities())
```

- [ ] **Step 4: Return DTO-derived authoring fields only**

```python
return web.json_response({"data": catalog.model_dump(mode="json")})
```

- [ ] **Step 5: Verify and commit**

Run: `python -m pytest server/tests/test_endpoint_module_bff.py server/tests/test_endpoint_modules_port_contracts.py -q --tb=short`

```powershell
git add server/web_api/endpoint_module_handlers.py server/routes.py server/tests/test_endpoint_module_bff.py
git commit -m "feat(modules): expose capability catalog through bff"
```

### Task 4: Close result projection and snapshot v2

**Files:**
- Create: `server/app/services/endpoint_module_result_projector.py`
- Modify: `server/app/services/endpoint_module_operation_reconciler.py:72-300`
- Test: `server/tests/test_endpoint_module_operation_reconciler.py`

**Interfaces:** Consumes terminal typed child results; produces `endpoint_module_result_snapshot_v2` and v1 reader compatibility.

- [ ] **Step 1: Write failing schema/unknown-capability tests**

```python
def test_projector_rejects_unknown_capability_or_schema() -> None:
    with pytest.raises(EndpointModuleResultProjectionError):
        project_module_result("unknown", {"schema_version": "unknown_v1"})
```

- [ ] **Step 2: Run reconciler tests**

Run: `python -m pytest server/tests/test_endpoint_module_operation_reconciler.py -q --tb=short`

Expected: FAIL because the closed v2 projector is absent.

- [ ] **Step 3: Implement the explicit projector registry**

```python
PROJECTORS = {"route.get": _project_route_get, "adapter.list": _project_adapter_list, "system.service_status": _project_service_status}
```

- [ ] **Step 4: Save validated v2 snapshots and read v1/v2**

```python
snapshot = EndpointModuleResultSnapshotV2.model_validate(projected)
```

- [ ] **Step 5: Verify and commit**

Run: `python -m pytest server/tests/test_endpoint_module_operation_reconciler.py server/tests/test_endpoint_modules_port_contracts.py -q --tb=short`

```powershell
git add server/app/services/endpoint_module_result_projector.py server/app/services/endpoint_module_operation_reconciler.py server/tests/test_endpoint_module_operation_reconciler.py
git commit -m "feat(modules): project capability results into snapshot v2"
```

### Task 5: Run the HD1 gate and record the boundary

**Files:**
- Modify: `server/docs/CODEMAP.md`
- Modify: `PLANS.md`
- Test: `server/tests/test_endpoint_modules_http_adapter.py`
- Test: `server/tests/test_endpoint_modules_port_contracts.py`
- Test: `server/tests/test_endpoint_module_bff.py`
- Test: `server/tests/test_endpoint_module_operation_reconciler.py`

**Interfaces:** Produces a verified, documented PR-HD1 boundary.

- [ ] **Step 1: Add no-legacy-dispatch regression**

```python
def test_catalog_path_does_not_dispatch_legacy_stack(monkeypatch):
    monkeypatch.setattr("server.tools.service.ToolService", _fail)
```

- [ ] **Step 2: Run the required focused suite**

Run: `python -m pytest server/tests/test_endpoint_modules_http_adapter.py server/tests/test_endpoint_modules_port_contracts.py server/tests/test_endpoint_module_bff.py server/tests/test_endpoint_module_operation_reconciler.py -q --tb=short`

- [ ] **Step 3: Run workspace checks**

```powershell
python scripts/verify_workspace.py --workspace .
python -m compileall -q server scripts
git diff --check
```

- [ ] **Step 4: Update CODEMAP and handoff**

Document the fixed catalog route, fail-closed DTOs, v2/v1 snapshot handling and absence of direct browser/agent dispatch.

- [ ] **Step 5: Commit the documented gate**

```powershell
git add server/docs/CODEMAP.md PLANS.md
git commit -m "docs(modules): record capability catalog boundary"
```
