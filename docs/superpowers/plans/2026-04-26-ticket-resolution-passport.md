# Ticket Resolution Passport Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a verifiable "Паспорт решения" for each ticket: a generated, reviewable, printable resolution dossier assembled from ticket facts, actions, evidence, approvals, operations and final summaries.

**Architecture:** Add a dedicated passport domain under `server/tickets/` with normalized DB tables for passport snapshots, evidence, action log, approvals and related objects. The service assembles deterministic facts from existing ticket/timeline/operation/registry sources, stores versioned drafts, exposes typed web APIs, and renders a "Паспорт" tab in the ticket UI. AI/LLM is intentionally kept behind a future summarizer interface; v1 uses deterministic text so facts remain auditable.

**Tech Stack:** PostgreSQL + Alembic, SQLAlchemy models/repos, aiohttp typed web handlers, Pydantic DTOs, React/Vite/TanStack Query, Vitest, pytest, Playwright MCP live browser check.

---

## Product Scope

### v1 Must Ship

- A new ticket tab `Паспорт` in `/app/tickets/:ticketId`.
- Backend API to read, generate/refresh and update a passport draft.
- Passport facts built from:
  - ticket fields and requester profile;
  - registry context: person, department, location, asset, service;
  - status timeline and waits;
  - public/internal messages;
  - tool/module operations and result summaries;
  - worklogs;
  - KB links, ticket links and change/problem links where already present;
  - resolution fields: `resolution_code`, `resolution_summary`, `requester_resolution_summary`, `evidence_required`, `evidence_ref`.
- DB tables:
  - `ticket_resolution_passports`;
  - `ticket_evidence_items`;
  - `ticket_action_log`;
  - `ticket_approvals`;
  - `ticket_related_objects`.
- Buttons in UI:
  - `Собрать паспорт`;
  - `Обновить по последним действиям`;
  - `Печать / PDF`;
  - `Сохранить как черновик знания`.
- Closing guard: if `evidence_required=true`, ticket cannot move to `resolved` without at least one evidence item or `evidence_ref`.
- Printable view at `/app/tickets/:ticketId/passport/print` using browser print-to-PDF. This avoids introducing a server-side PDF dependency in v1 while still delivering PDF export through the browser.

### Explicitly Deferred

- LLM-generated prose. The schema and service should expose a clean `summary_source="deterministic"` now and allow `summary_source="llm_draft"` later.
- Full KB article publishing workflow. v1 creates a draft payload and UI confirmation, but does not introduce a full knowledge-base backend.
- Cryptographic signing. v1 stores immutable source references and `generated_at/generated_by`; signing can come after role/legal requirements are clarified.

---

## File Structure

### Server DB and Domain

- Create: `server/app/db/migrations/versions/20260426_1300_059_ticket_resolution_passport.py`
  - Adds passport/evidence/action/approval/object tables and indexes.
- Modify: `server/app/db/models.py`
  - Adds SQLAlchemy models for the five tables.
- Create: `server/app/repos/ticket_passport_repo.py`
  - CRUD/query layer for passport snapshots and detail rows.
- Create: `server/tickets/passport_service.py`
  - Deterministic assembler. Converts existing ticket facts into passport sections.
- Create: `server/tickets/passport_export.py`
  - Printable HTML renderer for the passport.
- Modify: `server/tickets/workflow_service.py`
  - Adds evidence guard for `resolved` transition.
- Modify: `server/web_api/dto/support.py`
  - Adds typed DTOs for passport payloads, actions, evidence and approvals.
- Modify: `server/web_api/support_handlers.py`
  - Adds passport endpoints and wires payload into support/ticket boundary.
- Modify: `server/routes.py`
  - Registers passport endpoints if handlers are not auto-mounted in existing support route registration.

### Webapp UI

- Modify: `webapp/src/features/queues/api.ts`
  - Adds passport types and API functions.
- Modify: `webapp/src/pages/tickets/detail-page.tsx`
  - Adds `Паспорт` tab, action buttons, evidence/action/approval sections and print navigation.
- Create: `webapp/src/pages/tickets/passport-print-page.tsx`
  - Printable passport view.
- Modify: `webapp/src/app/router.tsx`
  - Adds `/app/tickets/:ticketId/passport/print`.
- Modify or create tests:
  - `webapp/src/pages/tickets/detail-page.test.tsx`
  - `webapp/src/pages/tickets/passport-print-page.test.tsx`

### Tests and Docs

- Create: `server/tests/test_ticket_passport_schema.py`
- Create: `server/tests/test_ticket_passport_service.py`
- Create: `server/tests/test_ticket_passport_web_api.py`
- Modify: `server/tests/test_ticket_workflow_visibility.py`
- Modify: `server/docs/TICKET_SYSTEM.md`
- Modify: `server/docs/CODEMAP.md`
- Modify: `docs/QUICK_LOOKUP.md`
- Update: `PLANS.md`

---

## API Contract

### GET `/api/web/support/tickets/{ticket_id}/passport`

Returns current passport if stored; otherwise returns `status="missing"` with enough metadata for UI to show `Собрать паспорт`.

```json
{
  "ticket_id": "uuid",
  "passport": {
    "passport_id": 12,
    "version": 3,
    "status": "draft",
    "summary_source": "deterministic",
    "generated_at": "2026-04-26T14:00:00Z",
    "generated_by": "op1",
    "sections": {
      "requester": "Иванов И.И., Отдел...",
      "problem": "Пользователь сообщил...",
      "affected_object": "ПК sosn.alt.adm, кабинет 214",
      "automated_checks": "system.collect: успешно...",
      "operator_checks": "Проверены настройки...",
      "changes_made": "Перезапущена служба печати...",
      "approvals": "Согласование ИБ: approved",
      "evidence": "operation:abc, attachment:def",
      "user_result": "Пользователь должен увидеть...",
      "internal_result": "Причина: ..."
    },
    "source_event_ids": [101, 102],
    "source_operation_ids": ["operation-1"],
    "stale": false
  },
  "evidence": [],
  "actions": [],
  "approvals": [],
  "related_objects": []
}
```

### POST `/api/web/support/tickets/{ticket_id}/passport/generate`

Body:

```json
{
  "mode": "refresh",
  "include_internal_notes": true
}
```

Behavior:

- `mode="create"` creates version `1` if no passport exists.
- `mode="refresh"` creates `version + 1`, never overwrites old versions.
- Server returns the full payload from `GET`.
- RBAC: support/admin only.

### PATCH `/api/web/support/tickets/{ticket_id}/passport`

Body:

```json
{
  "operator_check_summary": "Проверил сетевую доступность и журнал ошибок.",
  "changes_made_summary": "Обновил драйвер принтера.",
  "repeat_guidance": "При повторе приложить скриншот ошибки и номер принтера."
}
```

Behavior:

- Updates editable fields on the current draft.
- Creates event `passport_updated`.
- RBAC: support/admin only.

### POST `/api/web/support/tickets/{ticket_id}/passport/evidence`

Body:

```json
{
  "evidence_type": "operation",
  "source_ref": "operation-id",
  "title": "Диагностика устройства",
  "summary": "Команда завершилась успешно.",
  "visibility": "internal"
}
```

Behavior:

- Appends evidence row.
- Also updates `tickets.evidence_ref` if empty.
- Creates event `passport_evidence_added`.

### POST `/api/web/support/tickets/{ticket_id}/passport/knowledge-draft`

Returns a deterministic draft object:

```json
{
  "title": "Повторяющаяся проблема печати HP LaserJet",
  "problem": "Что случилось...",
  "resolution": "Как решено...",
  "repeat_guidance": "Что делать при повторе...",
  "source_passport_id": 12
}
```

No KB record is published in v1.

---

## DB Shape

### `ticket_resolution_passports`

- `id BIGSERIAL PRIMARY KEY`
- `ticket_id VARCHAR(36) NOT NULL REFERENCES tickets(ticket_id) ON DELETE CASCADE`
- `version INTEGER NOT NULL`
- `status VARCHAR(30) NOT NULL DEFAULT 'draft'`
- `summary_source VARCHAR(30) NOT NULL DEFAULT 'deterministic'`
- `requester_summary TEXT`
- `problem_summary TEXT`
- `affected_object_summary TEXT`
- `automated_checks_summary TEXT`
- `operator_checks_summary TEXT`
- `changes_made_summary TEXT`
- `approvals_summary TEXT`
- `evidence_summary TEXT`
- `user_result_summary TEXT`
- `internal_result_summary TEXT`
- `repeat_guidance TEXT`
- `source_event_ids JSONB NOT NULL DEFAULT '[]'::jsonb`
- `source_operation_ids JSONB NOT NULL DEFAULT '[]'::jsonb`
- `source_payload JSONB NOT NULL DEFAULT '{}'::jsonb`
- `generated_by TEXT`
- `generated_at TIMESTAMPTZ NOT NULL`
- `updated_by TEXT`
- `updated_at TIMESTAMPTZ NOT NULL`
- unique index `(ticket_id, version)`
- index `(ticket_id, generated_at DESC)`

### `ticket_evidence_items`

- `id BIGSERIAL PRIMARY KEY`
- `ticket_id VARCHAR(36) NOT NULL REFERENCES tickets(ticket_id) ON DELETE CASCADE`
- `passport_id BIGINT REFERENCES ticket_resolution_passports(id) ON DELETE SET NULL`
- `evidence_type VARCHAR(30) NOT NULL`
- `source_ref TEXT`
- `title TEXT NOT NULL`
- `summary TEXT`
- `visibility VARCHAR(20) NOT NULL DEFAULT 'internal'`
- `created_by TEXT`
- `created_at TIMESTAMPTZ NOT NULL`
- index `(ticket_id, created_at DESC)`
- index `(passport_id)`

### `ticket_action_log`

- `id BIGSERIAL PRIMARY KEY`
- `ticket_id VARCHAR(36) NOT NULL REFERENCES tickets(ticket_id) ON DELETE CASCADE`
- `passport_id BIGINT REFERENCES ticket_resolution_passports(id) ON DELETE SET NULL`
- `action_type VARCHAR(40) NOT NULL`
- `actor_id TEXT`
- `source_event_id BIGINT`
- `operation_id VARCHAR(36)`
- `title TEXT NOT NULL`
- `summary TEXT`
- `started_at TIMESTAMPTZ`
- `finished_at TIMESTAMPTZ`
- `created_at TIMESTAMPTZ NOT NULL`
- index `(ticket_id, created_at DESC)`
- index `(operation_id)`

### `ticket_approvals`

- `id BIGSERIAL PRIMARY KEY`
- `ticket_id VARCHAR(36) NOT NULL REFERENCES tickets(ticket_id) ON DELETE CASCADE`
- `passport_id BIGINT REFERENCES ticket_resolution_passports(id) ON DELETE SET NULL`
- `approval_type VARCHAR(40) NOT NULL`
- `approver_id TEXT`
- `status VARCHAR(30) NOT NULL DEFAULT 'requested'`
- `reason TEXT`
- `requested_by TEXT`
- `requested_at TIMESTAMPTZ NOT NULL`
- `decided_at TIMESTAMPTZ`
- index `(ticket_id, status)`
- index `(approver_id, status)`

### `ticket_related_objects`

- `id BIGSERIAL PRIMARY KEY`
- `ticket_id VARCHAR(36) NOT NULL REFERENCES tickets(ticket_id) ON DELETE CASCADE`
- `passport_id BIGINT REFERENCES ticket_resolution_passports(id) ON DELETE SET NULL`
- `object_type VARCHAR(40) NOT NULL`
- `object_ref TEXT NOT NULL`
- `display_name TEXT`
- `relation_type VARCHAR(40) NOT NULL`
- `source VARCHAR(40) NOT NULL DEFAULT 'snapshot'`
- `created_at TIMESTAMPTZ NOT NULL`
- unique index `(ticket_id, object_type, object_ref, relation_type)`

---

## Task 1: Schema and Model Foundation

**Files:**
- Create: `server/app/db/migrations/versions/20260426_1300_059_ticket_resolution_passport.py`
- Modify: `server/app/db/models.py`
- Test: `server/tests/test_ticket_passport_schema.py`

- [ ] **Step 1: Write schema test**

Create `server/tests/test_ticket_passport_schema.py` with assertions that SQLAlchemy metadata contains:

```python
from __future__ import annotations

from app.db.base import Base


def test_ticket_passport_tables_are_registered():
    tables = Base.metadata.tables

    assert "ticket_resolution_passports" in tables
    assert "ticket_evidence_items" in tables
    assert "ticket_action_log" in tables
    assert "ticket_approvals" in tables
    assert "ticket_related_objects" in tables

    passport = tables["ticket_resolution_passports"]
    assert {"ticket_id", "version", "status", "summary_source", "source_event_ids", "source_operation_ids"}.issubset(
        passport.columns.keys()
    )

    evidence = tables["ticket_evidence_items"]
    assert {"ticket_id", "passport_id", "evidence_type", "source_ref", "visibility"}.issubset(evidence.columns.keys())
```

- [ ] **Step 2: Run failing test**

Run:

```powershell
python -m pytest server/tests/test_ticket_passport_schema.py -q
```

Expected: FAIL because the tables do not exist.

- [ ] **Step 3: Add models and migration**

Add the five SQLAlchemy models to `server/app/db/models.py` near the existing ticket-domain models. Use `JSONB`, `TIMESTAMP(timezone=True)`, `sa.ForeignKey`, `Index`, `UniqueConstraint`, and defaults consistent with `TicketWait`, `TicketWorklog` and `TicketLink`.

Create Alembic migration `059` with the exact table names and columns from "DB Shape".

- [ ] **Step 4: Run schema test**

Run:

```powershell
python -m pytest server/tests/test_ticket_passport_schema.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit schema foundation**

```powershell
git add server/app/db/models.py server/app/db/migrations/versions/20260426_1300_059_ticket_resolution_passport.py server/tests/test_ticket_passport_schema.py
git commit -m "server: add ticket resolution passport schema"
```

---

## Task 2: Passport Repository and Deterministic Assembler

**Files:**
- Create: `server/app/repos/ticket_passport_repo.py`
- Create: `server/tickets/passport_service.py`
- Test: `server/tests/test_ticket_passport_service.py`

- [ ] **Step 1: Write service tests**

Create tests for three cases:

```python
async def test_passport_service_builds_requester_problem_and_object_sections(db_session):
    ...

async def test_passport_service_collects_tool_events_as_automated_checks(db_session):
    ...

async def test_passport_refresh_creates_new_version_without_overwriting_previous(db_session):
    ...
```

The fixtures should create one `Ticket`, two `TicketEvent` rows (`chat_message`, `tool_call_result`) and one `Operation` row with `result_summary`.

- [ ] **Step 2: Run failing service tests**

```powershell
python -m pytest server/tests/test_ticket_passport_service.py -q
```

Expected: FAIL because repo/service modules do not exist.

- [ ] **Step 3: Implement repo**

`TicketPassportRepo` must provide:

```python
class TicketPassportRepo:
    async def get_latest_passport(self, ticket_id: str): ...
    async def create_passport_version(self, *, ticket_id: str, generated_by: str | None, sections: dict, source_payload: dict): ...
    async def list_evidence(self, ticket_id: str): ...
    async def add_evidence(self, *, ticket_id: str, passport_id: int | None, evidence_type: str, source_ref: str | None, title: str, summary: str | None, visibility: str, created_by: str | None): ...
    async def list_actions(self, ticket_id: str): ...
    async def replace_generated_actions(self, *, ticket_id: str, passport_id: int, actions: list[dict]): ...
    async def list_approvals(self, ticket_id: str): ...
    async def list_related_objects(self, ticket_id: str): ...
    async def replace_related_objects(self, *, ticket_id: str, passport_id: int, objects: list[dict]): ...
```

- [ ] **Step 4: Implement deterministic assembler**

`TicketPassportService.generate(ticket_id, actor_id, mode)` must:

1. Load ticket via existing `TicketEventsRepo` or direct `select(Ticket)`.
2. Load timeline events from `ticket_events`.
3. Load recent operations with `OperationsRepo.get_recent_operations(...)`.
4. Build sections:
   - requester: `requester_display_name`, requester profile, registry person/department/location if available;
   - problem: title + description + initial requester message;
   - affected object: device snapshot, registry asset/service, location;
   - automated checks: `tool_call_started`, `tool_call_result`, operation summaries;
   - operator checks: internal notes and worklog notes;
   - changes made: operation results and explicit support messages after `in_progress`;
   - approvals: rows from `ticket_approvals`;
   - evidence: `ticket_evidence_items`, `tickets.evidence_ref`, artifacts in message attachments;
   - user result: `requester_resolution_summary`;
   - internal result: `resolution_summary`, `root_cause`, `resolution_code`;
   - repeat guidance: deterministic fallback from category/request kind.
5. Store a new version on each refresh.
6. Create event `passport_generated` through `TicketEventsRepo.create_server_event`.

- [ ] **Step 5: Run service tests**

```powershell
python -m pytest server/tests/test_ticket_passport_service.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit service**

```powershell
git add server/app/repos/ticket_passport_repo.py server/tickets/passport_service.py server/tests/test_ticket_passport_service.py
git commit -m "server: assemble ticket resolution passports"
```

---

## Task 3: Typed Web API

**Files:**
- Modify: `server/web_api/dto/support.py`
- Modify: `server/web_api/support_handlers.py`
- Modify: `server/routes.py` if route registration is explicit there
- Test: `server/tests/test_ticket_passport_web_api.py`

- [ ] **Step 1: Write API contract tests**

Tests:

```python
async def test_get_passport_returns_missing_state_for_new_ticket(test_client, support_auth):
    ...

async def test_generate_passport_returns_sections_and_version(test_client, support_auth):
    ...

async def test_add_evidence_updates_passport_payload(test_client, support_auth):
    ...

async def test_requester_cannot_generate_passport(test_client, requester_auth):
    ...
```

- [ ] **Step 2: Run failing tests**

```powershell
python -m pytest server/tests/test_ticket_passport_web_api.py -q
```

Expected: FAIL with 404 or missing DTOs.

- [ ] **Step 3: Add DTOs**

Add Pydantic models:

```python
class SupportTicketPassportSectionPayload(BaseModel): ...
class SupportTicketPassportPayload(BaseModel): ...
class SupportTicketEvidenceItemPayload(BaseModel): ...
class SupportTicketActionLogPayload(BaseModel): ...
class SupportTicketApprovalPayload(BaseModel): ...
class SupportTicketRelatedObjectPayload(BaseModel): ...
class SupportTicketPassportDetailPayload(BaseModel): ...
class SupportTicketPassportGenerateRequest(BaseModel): ...
class SupportTicketPassportEvidenceRequest(BaseModel): ...
class SupportTicketKnowledgeDraftPayload(BaseModel): ...
```

- [ ] **Step 4: Add handlers**

Add handlers in `server/web_api/support_handlers.py`:

- `get_support_ticket_passport`
- `post_support_ticket_passport_generate`
- `patch_support_ticket_passport`
- `post_support_ticket_passport_evidence`
- `post_support_ticket_passport_knowledge_draft`

Use existing `AuthContext` and support/admin role checks already used by status/message/tool handlers.

- [ ] **Step 5: Run API tests**

```powershell
python -m pytest server/tests/test_ticket_passport_web_api.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit API**

```powershell
git add server/web_api/dto/support.py server/web_api/support_handlers.py server/routes.py server/tests/test_ticket_passport_web_api.py
git commit -m "server: expose ticket passport web api"
```

---

## Task 4: Resolution Evidence Guard

**Files:**
- Modify: `server/tickets/workflow_service.py`
- Modify: `server/web_api/support_handlers.py`
- Test: `server/tests/test_ticket_workflow_visibility.py`

- [ ] **Step 1: Add failing guard test**

Add:

```python
async def test_resolved_requires_evidence_when_ticket_requires_it(db_session):
    ...
```

Expected behavior:

- Ticket has `evidence_required=True`, no `evidence_ref`, no evidence rows.
- Transition `in_progress -> resolved` raises validation error.
- After inserting one `ticket_evidence_items` row, transition succeeds.

- [ ] **Step 2: Run failing test**

```powershell
python -m pytest server/tests/test_ticket_workflow_visibility.py::test_resolved_requires_evidence_when_ticket_requires_it -q
```

Expected: FAIL.

- [ ] **Step 3: Implement guard**

In `TicketWorkflowService.apply_status_transition(...)`, before applying `resolved`:

- if `ticket.evidence_required` is false, allow current behavior;
- if `ticket.evidence_ref` is set, allow;
- otherwise query `TicketPassportRepo.list_evidence(ticket.ticket_id)`;
- if empty, raise the same validation/error type used for invalid transitions, with a Russian message: `Для решения тикета требуется подтверждение: добавьте доказательство или ссылку evidence_ref`.

- [ ] **Step 4: Run guard test**

```powershell
python -m pytest server/tests/test_ticket_workflow_visibility.py::test_resolved_requires_evidence_when_ticket_requires_it -q
```

Expected: PASS.

- [ ] **Step 5: Commit guard**

```powershell
git add server/tickets/workflow_service.py server/web_api/support_handlers.py server/tests/test_ticket_workflow_visibility.py
git commit -m "server: require evidence for governed ticket resolution"
```

---

## Task 5: Ticket UI Passport Tab

**Files:**
- Modify: `webapp/src/features/queues/api.ts`
- Modify: `webapp/src/pages/tickets/detail-page.tsx`
- Test: `webapp/src/pages/tickets/detail-page.test.tsx`

- [ ] **Step 1: Write UI tests**

Add tests that render passport cards/components and assert:

- `Паспорт` tab label exists.
- Missing passport state shows `Собрать паспорт`.
- Existing passport state shows:
  - `Кто и откуда обратился`;
  - `Что произошло`;
  - `Что проверили автоматически`;
  - `Что изменили`;
  - `Чем подтверждено решение`.
- Buttons `Обновить по последним действиям`, `Печать / PDF`, `Сохранить как черновик знания` exist.

- [ ] **Step 2: Run failing UI test**

```powershell
pnpm -C webapp test -- --run src/pages/tickets/detail-page.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Add API types and functions**

Add to `webapp/src/features/queues/api.ts`:

```ts
export type SupportTicketPassportPayload = { ... };
export async function fetchSupportTicketPassport(ticketId: string): Promise<SupportTicketPassportDetailPayload> { ... }
export async function generateSupportTicketPassport(ticketId: string, mode: "create" | "refresh"): Promise<SupportTicketPassportDetailPayload> { ... }
export async function addSupportTicketPassportEvidence(ticketId: string, payload: SupportTicketPassportEvidenceRequest): Promise<SupportTicketPassportDetailPayload> { ... }
export async function createSupportTicketKnowledgeDraft(ticketId: string): Promise<SupportTicketKnowledgeDraftPayload> { ... }
```

- [ ] **Step 4: Add tab UI**

In `TicketDetailPage`:

- Add `{ value: "passport", label: "Паспорт" }` to `tabItems`.
- Add a `useQuery` for passport payload enabled when `ticketId` exists.
- Add mutations for generate/refresh/evidence/knowledge draft.
- Render sections as compact scan-friendly blocks.
- Keep cards at existing radii and density; no marketing hero or decorative cards.

- [ ] **Step 5: Run UI test**

```powershell
pnpm -C webapp test -- --run src/pages/tickets/detail-page.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit UI tab**

```powershell
git add webapp/src/features/queues/api.ts webapp/src/pages/tickets/detail-page.tsx webapp/src/pages/tickets/detail-page.test.tsx
git commit -m "webapp: add ticket resolution passport tab"
```

---

## Task 6: Printable Passport View

**Files:**
- Create: `webapp/src/pages/tickets/passport-print-page.tsx`
- Modify: `webapp/src/app/router.tsx`
- Test: `webapp/src/pages/tickets/passport-print-page.test.tsx`

- [ ] **Step 1: Write print view test**

Test:

```ts
it("renders official printable passport sections", async () => {
  ...
  expect(await screen.findByText("Паспорт решения")).toBeInTheDocument();
  expect(screen.getByText("Кто обратился")).toBeInTheDocument();
  expect(screen.getByText("Доказательства")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run failing print test**

```powershell
pnpm -C webapp test -- --run src/pages/tickets/passport-print-page.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement print page**

Page behavior:

- Uses `fetchSupportTicketPassport(ticketId)`.
- Shows official header: ticket code, generated timestamp, version.
- Shows sections in fixed order.
- Adds a `Печать / PDF` icon button that calls `window.print()`.
- CSS uses print-friendly white background, black text and no app shell decorations.

- [ ] **Step 4: Register route**

Add to `webapp/src/app/router.tsx`:

```tsx
{
  path: "tickets/:ticketId/passport/print",
  element: (
    <ProtectedRoute requiredWorkspace="support">
      <PassportPrintPage />
    </ProtectedRoute>
  ),
}
```

Use the exact local route guard pattern already present in the file.

- [ ] **Step 5: Run print test and build**

```powershell
pnpm -C webapp test -- --run src/pages/tickets/passport-print-page.test.tsx
pnpm -C webapp build
```

Expected: PASS and build succeeds.

- [ ] **Step 6: Commit print view**

```powershell
git add webapp/src/pages/tickets/passport-print-page.tsx webapp/src/pages/tickets/passport-print-page.test.tsx webapp/src/app/router.tsx
git commit -m "webapp: add printable ticket passport view"
```

---

## Task 7: Docs and Navigation

**Files:**
- Modify: `server/docs/TICKET_SYSTEM.md`
- Modify: `server/docs/CODEMAP.md`
- Modify: `docs/QUICK_LOOKUP.md`
- Modify: `PLANS.md`

- [ ] **Step 1: Update ticket docs**

Add a section `Паспорт решения` to `server/docs/TICKET_SYSTEM.md` with:

- purpose;
- data sources;
- DB tables;
- API endpoints;
- RBAC;
- evidence guard;
- print/PDF behavior;
- future LLM draft rules: "LLM suggests text only; facts come from DB/source refs".

- [ ] **Step 2: Update navigation docs**

In `server/docs/CODEMAP.md`, add passport files under:

- ticket flows;
- typed web boundary;
- DB/repositories.

In `docs/QUICK_LOOKUP.md`, update the `Ticket flows / helpdesk` row to include `server/tickets/passport_service.py` and passport API/UI notes.

- [ ] **Step 3: Update PLANS.md**

Add a short current-state block:

```markdown
## 2026-04-26 Ticket resolution passport

- Scope: DB-backed passport, evidence/action/approval/object records, typed API, ticket UI tab, print/PDF view, docs and live browser verification.
- Current State: implementation plan saved at `docs/superpowers/plans/2026-04-26-ticket-resolution-passport.md`.
- Verification target: schema/service/API pytest, webapp tests/build, `python scripts/verify_workspace.py`, remote release smoke and browser check at `http://192.168.100.17:8666/admin`.
```

- [ ] **Step 4: Commit docs**

```powershell
git add server/docs/TICKET_SYSTEM.md server/docs/CODEMAP.md docs/QUICK_LOOKUP.md PLANS.md
git commit -m "docs: document ticket resolution passports"
```

---

## Task 8: Full Verification and Live Test

**Files:**
- No new code unless verification finds a bug.

- [ ] **Step 1: Run targeted backend tests**

```powershell
python -m pytest server/tests/test_ticket_passport_schema.py server/tests/test_ticket_passport_service.py server/tests/test_ticket_passport_web_api.py server/tests/test_ticket_workflow_visibility.py -q
```

Expected: all pass.

- [ ] **Step 2: Run frontend tests and build**

```powershell
pnpm -C webapp test -- --run src/pages/tickets/detail-page.test.tsx src/pages/tickets/passport-print-page.test.tsx
pnpm -C webapp build
```

Expected: tests pass, build succeeds. Existing Vite chunk warning is acceptable if unchanged.

- [ ] **Step 3: Run workspace verification**

```powershell
python scripts/verify_workspace.py
```

Expected: `Verification passed`.

- [ ] **Step 4: Deploy to remote stand**

Only after commits:

```powershell
python scripts/release_server_to_remote.py --allow-local-dirty --skip-ci-check --skip-verify --leave-running
```

Expected:

- remote workspace fast-forwards to the latest commit;
- migration `059` runs;
- remote smoke `/api/health` returns `200`.

- [ ] **Step 5: Live browser verification**

Use MCP browser at `http://192.168.100.17:8666/admin`, then navigate to `/app/tickets/{ticket_id}`.

Check:

- `Паспорт` tab exists.
- `Собрать паспорт` creates a draft.
- Refresh increments version.
- Evidence item appears in passport.
- `Печать / PDF` opens print view.
- A ticket with `evidence_required=true` cannot be resolved until evidence is attached.
- No browser console errors.

- [ ] **Step 6: Stop remote server**

```powershell
python scripts/manage_remote_stack.py stop server
python scripts/manage_remote_stack.py status server
```

Expected: server stopped. Control plane may remain running.

- [ ] **Step 7: Final report**

Report:

- commit hashes;
- tests run;
- migration result;
- live browser result;
- any dirty pre-existing worktree files not related to the passport.

---

## Implementation Notes

- Treat `ticket_resolution_passports` as versioned generated snapshots. Do not mutate old versions.
- Treat `ticket_evidence_items` and `ticket_action_log` as factual source rows. Passport prose can be regenerated; source facts should stay queryable.
- Internal notes can feed `internal_result_summary`; requester-facing print should not expose internal-only notes unless support explicitly chooses an internal print mode later.
- For v1, `Сохранить как черновик знания` returns a draft payload and can show it in a modal. It must not silently publish into `/app/knowledge`.
- All new text stored by the app must be UTF-8. Avoid mojibake and keep Russian UI literals readable.
- Keep the ticket detail page dense and operational: no landing-page composition, no hero blocks, no decorative backgrounds.

---

## Self-Review

- Spec coverage:
  - Passport creation from ticket facts: Task 2.
  - DB tables requested by the user: Task 1.
  - UI tab/buttons/print: Tasks 5 and 6.
  - Evidence and approvals: Tasks 1, 2, 3 and 4.
  - Docs/testing/live testing: Tasks 7 and 8.
- Placeholder scan:
  - No implementation step depends on unnamed future work.
  - Deferred LLM/KB publishing is explicit and not required for v1 completion.
- Type consistency:
  - API, DTO, frontend type names use `SupportTicketPassport*`.
  - DB names are stable and match the requested domain names.
