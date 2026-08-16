# Helpdesk Segmentation PR-0/PR-1/PR-6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (\`- [ ]\`) syntax for tracking.

**Goal:** Establish ports and architecture guards, then remove Helpdesk's local Knowledge implementation without blocking core ticket workflows.

**Architecture:** Helpdesk owns ticket/process data and depends only on dependency-injected versioned ports. KnowledgePort is initially an explicit unavailable implementation; it does not query local tables or provide fallback content. Existing Knowledge database tables remain untouched until the accepted forward-only deletion migration in PR-11, but no active model, route, service, UI or job may access them after PR-6.

**Tech Stack:** Python 3, aiohttp, Pydantic, SQLAlchemy/Alembic, React/TypeScript, pytest, pnpm.

## Global Constraints

- Work only in the isolated worktree on codex/helpdesk-segmentation-pr0-pr1-pr6.
- Do not change deployed services or delete remote data.
- Preserve ticket creation, routing, support work and closure while Knowledge is unavailable.
- External IDs are opaque; do not add cross-service database FKs or direct imports.
- Keep existing Knowledge tables and Alembic history intact until PR-11; never edit old migrations.
- Remove server/ai only after proving it has no non-Knowledge consumer.
- Retain existing ticket_kb_links and sanitized knowledge_attempts as read-only history; do not write new local Knowledge records.
- Default behaviour is fail-closed: the former Knowledge routes/UI disappear and the port returns a typed unavailable result.

---

### Task 1: Record PR-0 ownership boundaries and external API target

**Files:**
- Create: server/docs/SEGMENTATION_BOUNDARIES.md
- Create: server/docs/adr/0001-helpdesk-external-domain-ports.md
- Create: server/docs/KNOWLEDGE_PLATFORM_API_V1.md
- Modify: docs/ARCHITECTURE_BOUNDARIES.md
- Modify: server/docs/CODEMAP.md
- Test: server/tests/test_segmentation_docs.py

**Interfaces:**
- Consumes: accepted Endpoint ADR 0001/0002 and the approved design.
- Produces: normative Helpdesk ownership boundaries and the versioned external Knowledge API.

- [ ] **Step 1: Write the failing documentation-presence test**

~~~python
def test_segmentation_docs_define_no_local_knowledge_fallback() -> None:
    text = Path("server/docs/SEGMENTATION_BOUNDARIES.md").read_text(encoding="utf-8")
    assert "KnowledgePort" in text
    assert "no local fallback" in text
~~~

- [ ] **Step 2: Run the test to verify it fails**

Run: python -m pytest server/tests/test_segmentation_docs.py -q
Expected: FAIL because the boundary documents do not exist.

- [ ] **Step 3: Write the architecture and API documents**

Document Helpdesk, Endpoint, Knowledge and Registry ownership; forbid direct imports/FKs; state that legacy Knowledge has no fallback. Define external Knowledge search, suggestion, item/version projection, resolution draft and feedback operations, service authentication/scopes, opaque correlation, pagination, redaction and the knowledge_unavailable error. Mark every endpoint as a future external target, not a Helpdesk route.

- [ ] **Step 4: Run the test and commit**

Run: python -m pytest server/tests/test_segmentation_docs.py -q
Expected: PASS.

~~~powershell
git add server/docs/SEGMENTATION_BOUNDARIES.md server/docs/adr/0001-helpdesk-external-domain-ports.md server/docs/KNOWLEDGE_PLATFORM_API_V1.md docs/ARCHITECTURE_BOUNDARIES.md server/docs/CODEMAP.md server/tests/test_segmentation_docs.py
git commit -m "docs: define Helpdesk external domain boundaries"
~~~

### Task 2: Add neutral ports and unavailable adapters

**Files:**
- Create: server/domain_ports/__init__.py
- Create: server/domain_ports/knowledge.py
- Create: server/domain_ports/registry.py
- Create: server/domain_ports/endpoint.py
- Create: server/domain_ports/unavailable.py
- Create: server/domain_ports/container.py
- Modify: server/config.py
- Test: server/tests/test_domain_ports.py

**Interfaces:**
- Consumes: PR-0 API names.
- Produces: KnowledgePort, RegistryPort, EndpointPort, KnowledgeUnavailable and DomainPortContainer.

- [ ] **Step 1: Write a failing unavailable-port test**

~~~python
async def test_unavailable_knowledge_port_never_returns_content() -> None:
    result = await UnavailableKnowledgePort().suggest(KnowledgeSuggestionRequest(query="vpn"))
    assert result.status == "unavailable"
    assert result.code == "knowledge_unavailable"
    assert result.items == ()
~~~

- [ ] **Step 2: Run the test to verify it fails**

Run: python -m pytest server/tests/test_domain_ports.py -q
Expected: FAIL because domain_ports does not exist.

- [ ] **Step 3: Implement contracts and composition**

Use immutable, validated request/result DTOs. KnowledgePort exposes availability, search, suggest, record_feedback and create_resolution_draft. Results may carry only opaque item/version refs, safe title/summary/status and a stable error code. UnavailableKnowledgePort must make no DB/HTTP calls. DomainPortContainer constructs it as the default from one explicit configuration setting; no module-global singleton is permitted.

- [ ] **Step 4: Run checks and commit**

Run: python -m pytest server/tests/test_domain_ports.py -q; python -m compileall -q server/domain_ports
Expected: PASS.

~~~powershell
git add server/domain_ports server/config.py server/tests/test_domain_ports.py
git commit -m "server: add external domain port contracts"
~~~

### Task 3: Add PR-1 import guards

**Files:**
- Create: scripts/check_domain_import_boundaries.py
- Create: server/tests/test_domain_import_boundaries.py
- Modify: scripts/verify_workspace.py
- Test: server/tests/test_domain_import_boundaries.py

**Interfaces:**
- Consumes: server/domain_ports as the only active cross-domain dependency layer.
- Produces: AST-based guard rejecting local Knowledge imports in runtime code.

- [ ] **Step 1: Write a failing forbidden-import fixture test**

~~~python
def test_check_rejects_ticket_import_of_local_knowledge(tmp_path: Path) -> None:
    source = tmp_path / "server" / "tickets" / "bad.py"
    source.parent.mkdir(parents=True)
    source.write_text("from knowledge.search_service import KnowledgeSearchService\n", encoding="utf-8")
    assert run_check(tmp_path).returncode == 1
~~~

- [ ] **Step 2: Run the test to verify it fails**

Run: python -m pytest server/tests/test_domain_import_boundaries.py -q
Expected: FAIL because the checker does not exist.

- [ ] **Step 3: Implement the guard**

Parse Python AST and reject imports of knowledge, app.repos.knowledge_repo and Knowledge ORM models in active source. Permit historical Alembic migrations only. Print file/line/import diagnostics, add it to verify_workspace.py and do not match comments/docs.

- [ ] **Step 4: Run checks and commit**

Run: python -m pytest server/tests/test_domain_import_boundaries.py -q; python scripts/check_domain_import_boundaries.py
Expected: PASS only after Task 6.

~~~powershell
git add scripts/check_domain_import_boundaries.py scripts/verify_workspace.py server/tests/test_domain_import_boundaries.py
git commit -m "scripts: guard Helpdesk domain imports"
~~~

### Task 4: Detach ticket and requester flows from local Knowledge

**Files:**
- Modify: server/tickets/handlers.py
- Modify: server/tickets/public_ticket_handlers.py
- Modify: server/web_api/requester_handlers.py
- Modify: server/tickets/knowledge_provider.py
- Modify: server/tickets/policy_health_service.py
- Modify: server/customer_history/sources.py
- Modify: server/customer_history/redaction.py
- Modify: server/quality/analytics_service.py
- Test: server/tests/test_ticket_knowledge_boundary.py
- Test: server/tests/test_requester_workspace_api.py

**Interfaces:**
- Consumes: DomainPortContainer.knowledge.
- Produces: ticket/requester creation that permits Knowledge unavailability and stores no new local Knowledge state.

- [ ] **Step 1: Write failing unavailable-flow tests**

~~~python
async def test_requester_ticket_create_succeeds_when_knowledge_is_unavailable(test_client):
    response = await test_client.post("/api/web/requester/tickets", json=valid_request_payload())
    assert response.status == 201

def test_policy_health_does_not_query_local_knowledge_models() -> None:
    assert policy_health_summary().knowledge_coverage_status == "not_configured"
~~~

- [ ] **Step 2: Run tests to verify they fail**

Run: python -m pytest server/tests/test_ticket_knowledge_boundary.py server/tests/test_requester_workspace_api.py -q --tb=short
Expected: FAIL while handlers import knowledge.* or read local catalog/content models.

- [ ] **Step 3: Implement the ticket-side boundary**

Replace feedback service, attempts sanitizer and local article catalog calls with ticket-owned validation that preserves only already-sanitized legacy attempt JSON. Ignore client-supplied content/body/item data. Keep similar-ticket search local. Policy health must return not_configured rather than query Knowledge models. Customer History, Observer and quality may display opaque/redacted legacy attempt metadata only.

- [ ] **Step 4: Run focused regressions and commit**

Run: python -m pytest server/tests/test_ticket_knowledge_boundary.py server/tests/test_requester_workspace_api.py server/tests/test_customer_history_context_builder.py server/tests/test_quality_analytics.py -q --tb=short
Expected: PASS.

~~~powershell
git add server/tickets server/web_api/requester_handlers.py server/customer_history server/quality/analytics_service.py server/tests/test_ticket_knowledge_boundary.py server/tests/test_requester_workspace_api.py
git commit -m "server: detach ticket flows from local Knowledge"
~~~

### Task 5: Detach support, problem and Registry from Knowledge

**Files:**
- Modify: server/web_api/support_handlers.py
- Modify: server/problem/known_error_service.py
- Modify: server/problem/candidate_service.py
- Modify: server/registry/service.py
- Modify: server/registry/admin_operations_service.py
- Test: server/tests/test_support_knowledge_boundary.py
- Test: server/tests/test_problem_knowledge_boundary.py
- Test: server/tests/test_registry_knowledge_boundary.py

**Interfaces:**
- Consumes: unavailable KnowledgePort and opaque external refs.
- Produces: no support/problem/Registry ORM or service dependency on Knowledge.

- [ ] **Step 1: Write failing boundary tests**

~~~python
async def test_support_detail_marks_knowledge_unavailable_without_articles(test_client):
    payload = await get_support_ticket_detail(test_client)
    assert payload["knowledge"]["status"] == "unavailable"
    assert payload["knowledge"]["suggestions"] == []

async def test_problem_known_error_does_not_create_local_knowledge_item(session):
    result = await KnownErrorService(session).create_from_problem(problem_id="p-1")
    assert result.external_reference is None
~~~

- [ ] **Step 2: Run tests to verify they fail**

Run: python -m pytest server/tests/test_support_knowledge_boundary.py server/tests/test_problem_knowledge_boundary.py server/tests/test_registry_knowledge_boundary.py -q
Expected: FAIL because these modules import Knowledge services/models.

- [ ] **Step 3: Implement unavailable projections**

Remove support suggestion/passport-draft handlers and Knowledge panel assembly. Keep Helpdesk problem/known-error entities, but use only nullable opaque external references. Registry export/quality must no longer inspect Knowledge rules/items. Do not emit new knowledge_* events.

- [ ] **Step 4: Run focused regressions and commit**

Run: python -m pytest server/tests/test_support_knowledge_boundary.py server/tests/test_problem_knowledge_boundary.py server/tests/test_registry_knowledge_boundary.py server/tests/test_problem_known_error.py -q --tb=short
Expected: PASS.

~~~powershell
git add server/web_api/support_handlers.py server/problem server/registry server/tests/test_support_knowledge_boundary.py server/tests/test_problem_knowledge_boundary.py server/tests/test_registry_knowledge_boundary.py
git commit -m "server: remove local Knowledge cross-domain writes"
~~~

### Task 6: Delete Knowledge runtime, routes, AI runtime and web surfaces

**Files:**
- Delete: server/knowledge/
- Delete: server/app/repos/knowledge_repo.py
- Delete: server/web_api/knowledge_handlers.py
- Delete: server/web_api/knowledge_ai_handlers.py
- Delete: server/ai/
- Delete: content_packs/knowledge/
- Delete: webapp/src/features/knowledge/
- Delete: webapp/src/pages/knowledge/
- Delete: webapp/src/pages/kb/
- Delete: webapp/src/pages/admin/knowledge-*.tsx
- Modify: server/routes.py
- Modify: webapp/src/app/router.tsx
- Modify: webapp/src/app/routes/lazy-pages.tsx
- Modify: webapp/src/app/navigation.ts
- Modify: server/app/db/models.py
- Test: server/tests/test_knowledge_routes_removed.py
- Test: webapp/src/app/router.test.tsx

**Interfaces:**
- Consumes: Tasks 2-5 removing active dependencies.
- Produces: no registered Knowledge endpoint/page and no active Knowledge ORM model.

- [ ] **Step 1: Write failing route/UI absence tests**

~~~python
async def test_legacy_knowledge_route_is_not_registered(test_client):
    response = await test_client.post("/api/knowledge/suggest", json={"query": "vpn"})
    assert response.status == 404
~~~

~~~tsx
it("does not register a Knowledge page", () => {
  expect(appRoutes.map((route) => route.path)).not.toContain("/app/knowledge")
})
~~~

- [ ] **Step 2: Run tests to verify they fail**

Run: python -m pytest server/tests/test_knowledge_routes_removed.py -q; pnpm --dir webapp test -- --run router.test.tsx
Expected: FAIL while routes/pages exist.

- [ ] **Step 3: Delete runtime and composition imports**

Delete listed Knowledge/AI modules and their tests; remove all imports, routes, navigation and UI pages. Remove Knowledge ORM classes from active models but preserve physical tables and migration history. Do not delete ticket_kb_links yet; stop exposing mutations and retain rows as historical data until PR-11. Update conftest cleanup only where removed active models require it.

- [ ] **Step 4: Run removal checks and commit**

Run: python scripts/check_domain_import_boundaries.py; python -m pytest server/tests/test_knowledge_routes_removed.py server/tests/test_domain_import_boundaries.py -q; pnpm --dir webapp run build
Expected: PASS; rg -n '(^from knowledge\.|^from ai\.|knowledge_repo)' server --glob '*.py' has no active-code matches.

~~~powershell
git add -A server/knowledge server/ai server/app/repos/knowledge_repo.py server/web_api/knowledge_handlers.py server/web_api/knowledge_ai_handlers.py content_packs/knowledge webapp/src/features/knowledge webapp/src/pages/knowledge webapp/src/pages/kb webapp/src/pages/admin server/routes.py server/app/db/models.py server/tests webapp/src
git commit -m "server: remove local Knowledge platform runtime"
~~~

### Task 7: Complete documentation and verification handoff

**Files:**
- Delete: server/docs/KNOWLEDGE_PLATFORM.md
- Delete: server/docs/KNOWLEDGE_OPERATIONS.md
- Delete: server/docs/KNOWLEDGE_VNEXT_ARCHITECTURE.md
- Modify: server/docs/DATABASE.md
- Modify: server/docs/TICKET_SYSTEM.md
- Modify: server/docs/SERVICE_CATALOG.md
- Modify: server/docs/REGISTRY_VISIBILITY_FOUNDATION.md
- Modify: docs/ARCHITECTURE_BOUNDARIES.md
- Modify: server/docs/CODEMAP.md
- Modify: pc_agent/docs/CODEMAP.md
- Modify: PLANS.md
- Test: server/tests/test_segmentation_docs.py

**Interfaces:**
- Consumes: final deleted surfaces.
- Produces: a verified milestone and explicit PR-7/PR-11 gate.

- [ ] **Step 1: Add failing documentation drift coverage**

~~~python
def test_docs_reference_external_knowledge_contract_not_removed_runtime() -> None:
    docs = Path("docs/ARCHITECTURE_BOUNDARIES.md").read_text(encoding="utf-8")
    assert "external Knowledge Platform" in docs
    assert "server/knowledge/" not in docs
~~~

- [ ] **Step 2: Run it to verify it fails**

Run: python -m pytest server/tests/test_segmentation_docs.py -q
Expected: FAIL while legacy docs remain.

- [ ] **Step 3: Update docs, plan and tests**

Replace local Knowledge ownership claims with the external contract. Delete Knowledge-only tests and rewrite cross-feature tests for unavailable/external-reference semantics. In PLANS.md record the removed surface, retained tables, no-deploy status, evidence and the next gates: PR-7 external API implementation; PR-11 forward-only schema deletion after acceptance.

- [ ] **Step 4: Run final verification and commit**

Run: python scripts/verify_workspace.py; python -m pytest server/tests/test_domain_ports.py server/tests/test_domain_import_boundaries.py server/tests/test_ticket_knowledge_boundary.py server/tests/test_support_knowledge_boundary.py server/tests/test_problem_knowledge_boundary.py server/tests/test_registry_knowledge_boundary.py server/tests/test_knowledge_routes_removed.py server/tests/test_segmentation_docs.py -q --tb=short; pnpm --dir webapp run build
Expected: PASS.

~~~powershell
git diff --check
git add -A server/docs docs pc_agent/docs PLANS.md server/tests docs/superpowers/plans/2026-08-09-helpdesk-segmentation-pr0-pr1-pr6.md
git commit -m "docs: record Knowledge extraction verification"
~~~

## Plan self-review

- Spec coverage: PR-0 is Task 1; PR-1 is Tasks 2-3; PR-6 is Tasks 4-7.
- Safety: no table/migration deletion occurs before PR-11; legacy Knowledge APIs/UI are removed and never silently fall back.
- Type consistency: application code uses only KnowledgePort and its unavailable code knowledge_unavailable.
- Resolved decisions: ticket_kb_links and knowledge_attempts are history-only; server/ai is deleted because it is Knowledge-only; removed HTTP paths return normal 404.
