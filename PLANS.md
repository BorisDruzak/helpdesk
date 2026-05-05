# Support Workspace SaaS Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans` or the project safe workflow when executing this plan. Keep this file current after each checkpoint. This plan replaces the old live-acceptance campaign plan and is now the active long-horizon plan for the `/app/tickets` redesign.

**Goal:** Redesign the operator support workspace around active `/app/tickets` routes into a production-ready modern SaaS service-desk workspace without breaking ticket business logic.

**Architecture:** Use the existing React/Vite webapp, shared UI primitives, typed `/api/web/support/*` boundary, ticket domain services, SLA/OLA/runtime services, playbook/tool APIs and passport APIs. Prefer an adaptation/view-model layer over replacing domain logic. Add backend DTO fields and typed aliases only where the current contract cannot support the reference workspace.

**Tech Stack:** React 19, Vite, TypeScript, Tailwind v4, TanStack Query, lucide-react, aiohttp typed web API, Pydantic DTOs, existing ticket/services/repos.

---

## Status

Created: 2026-05-05.

Current completion: 66%.

Current execution mode: Frontend workspace implementation is build-green against existing support APIs; Stage 2 backend expansion is deferred unless browser/live data proves a contract gap. Next checkpoint is workspace verification/browser signoff.

Working route: `/app/tickets` and `/app/tickets/:ticketId`.

Design reference: user-provided `image.png`. Treat it as the accepted visual target: dark SaaS operator workspace, 3 columns, calm topbar, left work slices/queues/tickets, central selected ticket/next action/timeline/composer, right context/SLA/tools/knowledge/passport.

## Source Of Truth And Constraints

- Work only in `C:\Users\admin-2\CodexProjects\pc_client`.
- Do not edit `\\192.168.100.17\NTFS_Share\pc_client` directly.
- Use active React routes under `/app/tickets`; `/app/support` is a compatibility redirect and must not become a second divergent workspace.
- Preserve existing business logic: statuses, assignment, queue/routing, priority, SLA/OLA, approval, diagnostics, playbooks, passport, observer, RBAC.
- Reuse existing shared components: `Button`, `Card`, `Tabs`, `Badge`, `SearchField`, `Select`, `Avatar` where they fit.
- Use Tailwind/Tailwind tokens and current React code style.
- Keep UI dense and operator-focused; no marketing landing layout.
- Browser verification must use `http://192.168.100.17:8666/admin` after deployment.
- Remote server must be stopped after verification unless the user explicitly asks to leave it running.

## Current Project Findings

### Active Frontend Surface

- `webapp/src/app/navigation.tsx`
  - `SUPPORT_HOME_PATH = "/app/tickets"`.
- `webapp/src/app/router.tsx`
  - `/app/support` redirects to `/app/tickets`.
  - `/app/tickets` renders `TicketListPage`.
  - `/app/tickets/:ticketId` renders `TicketDetailPage`.
- `webapp/src/pages/tickets/list-page.tsx`
  - Current ticket queue/list page.
- `webapp/src/pages/tickets/detail-page.tsx`
  - Current detailed ticket page with timeline, status actions, tools, playbooks, passport.
- `webapp/src/features/queues/support-workspace.tsx`
  - Existing support workspace implementation exists, but is not the canonical active route and should not be treated as the main page.
- `webapp/src/features/queues/api.ts`
  - Current typed support API client for queue, ticket detail, messages, status, tools, playbooks, passport, knowledge draft and tool/playbook run.

### Existing Backend Surface

- `GET /api/web/support/bootstrap`
- `GET /api/web/support/queue`
- `GET /api/web/support/tickets/{ticket_id}`
- `POST /api/web/support/tickets/{ticket_id}/messages`
- `POST /api/web/support/tickets/{ticket_id}/status`
- `GET /api/web/support/tickets/{ticket_id}/tools`
- `POST /api/web/support/tickets/{ticket_id}/tools/run`
- `GET /api/web/support/tickets/{ticket_id}/playbooks`
- `POST /api/web/support/tickets/{ticket_id}/playbooks/run`
- `GET /api/web/support/tickets/{ticket_id}/passport`
- `POST /api/web/support/tickets/{ticket_id}/passport/generate`
- `PATCH /api/web/support/tickets/{ticket_id}/passport`
- `GET/POST/PATCH /api/web/support/tickets/{ticket_id}/passport/evidence*`
- `POST /api/web/support/tickets/{ticket_id}/passport/knowledge-draft`

### Existing Domain Capabilities

- Smart views exist in `server/tickets/smart_views.py`.
- SLA and OLA logic exist in `server/tickets/sla_service.py` and `server/tickets/ola_service.py`.
- Ticket status/workflow logic exists in `server/tickets/workflow_service.py`.
- Assignment service exists in `server/tickets/assignment_service.py`.
- Routing service exists in `server/tickets/routing_service.py`.
- Playbook/tool launch exists in `server/web_api/support_handlers.py` and `server/app/services/playbook_engine.py`.
- Passport/evidence exists in `server/tickets/passport_service.py`, `server/tickets/evidence_service.py`, and `server/app/repos/ticket_passport_repo.py`.
- Registry/device context exists in `server/registry/*`, `RegistryRepo`, `DevicesRepo`.
- KB links exist at legacy ticket handler level, but full knowledge suggestions are not first-class yet.

## Backend Functionality Gap Estimate

Estimated missing backend functionality for the requested target: **35-40%**.

Already present:

- Ticket list and detail.
- Smart-view counts.
- Messages and internal notes.
- Status transitions and closure gates.
- Tools/playbooks, operation lifecycle, consent status.
- Passport and evidence management.
- Registry/device snapshot.
- Basic observer/timeline data.

Missing or incomplete for target:

- Workspace summary endpoint matching `GET /api/support/workspace/summary` semantics.
- Aggregated ticket workspace endpoint returning all center/right-panel data in one payload.
- First-class queue list/count DTO separate from smart views.
- SLA/OLA progress DTO with remaining/target/status/progress.
- Frontend view model matching `SupportWorkspaceViewModel`.
- Typed support aliases for assign, queue change, priority change and reroute.
- Filterable unified timeline endpoint or client mapper over all event types.
- Structured operation result mapper with steps, not raw preview text.
- Knowledge suggestions endpoint with similar tickets/articles/AI beta summary.
- Compact resolution passport readiness DTO for sidebar.
- Theme toggle/dark-mode workspace shell state.

## Design System Target

### Layout

- App fills `100vh`.
- Topbar height: 56-64px.
- Left column: 300-340px.
- Center column: flexible main workspace.
- Right sidebar: 360-420px.
- Each column scrolls independently.
- Topbar remains fixed/sticky.

### Visual Tokens

- Workspace dark app bg: `#07111f`.
- Panel bg: `#0d1828`.
- Card bg: `#111f33`.
- Elevated bg: `#13233a`.
- Border: `rgba(255,255,255,0.08)`.
- Text primary: `#e8edf5`.
- Text secondary: `#9aa8bd`.
- Primary: blue.
- Warning: orange.
- Danger: red.
- Success: green.
- Purple only as secondary accent.

### Interaction

- Selected ticket must be visually obvious.
- Next action is the central UX anchor.
- Public reply and internal note are visually distinct.
- Dangerous or unavailable actions must be disabled with visible reason.
- Agent offline disables agent-required tools.
- Operation running appears in timeline and right tools panel.

## Target Frontend Units

Prefer these focused units under `webapp/src/pages/tickets/` or `webapp/src/features/queues/`:

- `SupportWorkspacePage`
- `support-workspace-model.ts`
- `support-workspace-mappers.ts`
- `SupportTopbar` or route-aware `AppTopbar` dark variant
- `WorkSlicesPanel`
- `QueueList`
- `TicketWorklist`
- `TicketHeader`
- `NextActionPanel`
- `TicketActionBar`
- `TimelineTabs`
- `TicketTimeline`
- `TimelineEventItem`
- `OperationResultCard`
- `ReplyComposer`
- `TicketContextSidebar`
- `SlaOlaCard`
- `ToolsPlaybookCard`
- `KnowledgeSuggestionCard`
- `ResolutionPassportCard`

Do not split so aggressively that every component is one-use boilerplate; the final file layout should follow the existing repo style and testability.

## Target Backend Units

Modify these only as needed:

- `server/web_api/dto/support.py`
  - Add workspace DTOs, SLA/OLA DTOs, context DTOs, knowledge DTOs, action DTOs.
- `server/web_api/support_handlers.py`
  - Add or extend typed handlers and serializer helpers.
- `server/routes.py`
  - Register only missing typed routes.
- `server/tickets/smart_views.py`
  - Reuse existing smart-view ids and counts.
- `server/tickets/sla_service.py`, `server/tickets/ola_service.py`
  - Prefer read-only helper/serializer logic; do not change timer semantics unless a bug is proven.
- `server/docs/CODEMAP.md`, `docs/QUICK_LOOKUP.md`
  - Update if new routes or key entrypoints are added.

## Route And API Strategy

Use current typed `/api/web/support/*` routes as canonical React API. Add compatibility aliases only if needed for the requested names.

Preferred final API shape:

- Keep `GET /api/web/support/queue`.
- Add `GET /api/web/support/workspace/summary` if list page needs summary without ticket rows.
- Add `GET /api/web/support/tickets/{ticket_id}/workspace` to aggregate:
  - selected ticket;
  - timeline;
  - context;
  - SLA/OLA;
  - tools/playbooks;
  - knowledge;
  - passport readiness;
  - permissions/actions.
- Keep `POST /api/web/support/tickets/{ticket_id}/messages`.
- Keep `POST /api/web/support/tickets/{ticket_id}/status`.
- Add typed aliases if UI uses them:
  - `POST /api/web/support/tickets/{ticket_id}/assign`
  - `POST /api/web/support/tickets/{ticket_id}/queue`
  - `POST /api/web/support/tickets/{ticket_id}/priority`
  - `POST /api/web/support/tickets/{ticket_id}/reroute`
- Keep `GET /api/web/support/tickets/{ticket_id}/tools`.
- Keep `POST /api/web/support/tickets/{ticket_id}/tools/run`.
- Keep `GET /api/web/support/tickets/{ticket_id}/playbooks`.
- Keep `POST /api/web/support/tickets/{ticket_id}/playbooks/run`.
- Add `GET /api/web/support/tickets/{ticket_id}/knowledge-suggestions` as an honest low-risk stub if full KB backend is not ready.

## Execution Stages And Progress

Progress is tracked in 100 points:

- Stage 0: Plan and baseline, 8 points.
- Stage 1: Frontend view-model/mappers, 12 points.
- Stage 2: Backend DTO/serializer gaps, 18 points.
- Stage 3: Workspace shell and layout, 16 points.
- Stage 4: Left worklist, 10 points.
- Stage 5: Center ticket workspace, 16 points.
- Stage 6: Right sidebar, 10 points.
- Stage 7: Mutations, states and permissions, 5 points.
- Stage 8: Tests/docs/verification/browser, 5 points.

### Stage 0: Plan And Baseline (8 points)

- [x] Run UTF-8 shell bootstrap.
- [x] Run `python scripts/task_intake.py`.
- [x] Read workflow, quick lookup, boundaries and context index docs.
- [x] Rebuild context index.
- [x] Run `python scripts/bootstrap_web_toolchain.py`.
- [x] Identify active route ownership.
- [x] Replace `PLANS.md` with this plan.
- [x] Capture current `/app/tickets` and `/app/tickets/:ticketId` source structure in implementation notes.

Expected completion after Stage 0: 8%.

### Stage 1: View Model And Mappers (12 points)

Files:

- Create or modify `webapp/src/features/queues/support-workspace-model.ts`.
- Create or modify `webapp/src/features/queues/support-workspace-mappers.ts`.
- Modify `webapp/src/features/queues/api.ts`.
- Add tests near `webapp/src/features/queues/`.

Tasks:

- [x] Define `SupportWorkspaceViewModel`.
- [x] Define left-panel view models:
  - smart views;
  - queues;
  - ticket items.
- [x] Define selected ticket model:
  - header;
  - priority/status chips;
  - next action;
  - SLA/OLA summary;
  - requester/device/classification context.
- [x] Define timeline model:
  - messages;
  - internal notes;
  - diagnostics;
  - history.
- [x] Define sidebar models:
  - context;
  - SLA/OLA;
  - tools/playbooks;
  - knowledge;
  - passport.
- [x] Map current `SupportQueuePayload`, `SupportTicketDetailPayload`, `SupportTicketToolsPayload`, `SupportTicketPlaybooksPayload`, `SupportTicketPassportPayload` into the new view model.
- [x] Add mapper tests for:
  - next action by status/owner;
  - SLA risk countdown;
  - timeline filter classification;
  - passport readiness fallback.

Expected completion after Stage 1: 20%.

Stage 1 evidence:

- Added `webapp/src/features/queues/support-workspace-model.ts`.
- Added `webapp/src/features/queues/support-workspace-mappers.ts`.
- Added `webapp/src/features/queues/support-workspace-mappers.test.ts`.
- Ran `pnpm --dir webapp exec vitest run src/features/queues/support-workspace-mappers.test.ts`: 5 tests passed.

### Stage 2: Backend DTO And Serializer Gaps (18 points)

Files:

- Modify `server/web_api/dto/support.py`.
- Modify `server/web_api/support_handlers.py`.
- Modify `server/routes.py` only if new routes are added.
- Update `server/docs/CODEMAP.md` and `docs/QUICK_LOOKUP.md` if route surface changes.
- Add or extend `server/tests/test_web_support_api.py`.

Tasks:

- [ ] Add summary/queues DTO if existing queue payload is not enough.
- [ ] Add SLA/OLA card DTO serializer:
  - first response;
  - resolution;
  - OLA ack;
  - OLA processing.
- [ ] Add next-action serializer:
  - owner;
  - label;
  - hint;
  - due_at;
  - remaining_seconds;
  - timer_type.
- [ ] Add context serializer:
  - requester;
  - registry/location;
  - device;
  - classification.
- [ ] Add knowledge suggestions endpoint as honest empty/KB-link-backed payload if no full knowledge catalog exists.
- [ ] Add aggregated workspace endpoint if frontend complexity or round-trips justify it.
- [ ] Add typed aliases for assign/queue/priority/reroute only if used in visible action menu.
- [ ] Extend tests for DTO shape and RBAC denial payloads.

Expected completion after Stage 2: 38%.

Stage 2 note:

- No new backend route was added in the first implementation pass.
- The existing `GET /api/web/support/queue`, `GET /api/web/support/tickets/{ticket_id}`, tools/playbooks/passport and mutation endpoints are sufficient for the current UI with a frontend adapter.
- Updated frontend `SupportTicketDetailPayload.snapshot.registry` typing to match the existing backend DTO and handler.
- Remaining backend additions are still TODO if product requires fewer round trips or first-class knowledge/SLA-OLA workspace DTOs.

### Stage 3: Workspace Shell And Layout (16 points)

Files:

- Modify `webapp/src/pages/tickets/list-page.tsx`.
- Modify or replace portions of `webapp/src/pages/tickets/detail-page.tsx`.
- Possibly create `webapp/src/pages/tickets/workspace-page.tsx`.
- Modify `webapp/src/components/shell/app-topbar.tsx` only if route-specific dark topbar is needed.
- Modify `webapp/src/app/layouts/app-shell.tsx` only if the support workspace needs full-bleed mode.

Tasks:

- [x] Make `/app/tickets` the full 3-column workspace.
- [x] Keep `/app/tickets/:ticketId` deep-link behavior by selecting ticket in the same workspace.
- [x] Support no selected ticket state.
- [x] Add route-aware dark workspace mode without breaking admin/settings pages.
- [x] Implement fixed topbar and independent column scrolling.
- [x] Remove topbar KPI cards from the support workspace.
- [ ] Preserve sidebar navigation shell unless full-bleed support route requires a scoped exception.
- [ ] Ensure desktop width from 1366px works without overlap.

Expected completion after Stage 3: 54%.

Stage 3 evidence:

- Modified `webapp/src/pages/tickets/list-page.tsx` into the active 3-column dark support workspace.
- Modified `webapp/src/app/layouts/app-shell.tsx` with a route-scoped full-bleed exception for `/app/tickets` and `/app/tickets/:ticketId`.
- Modified `webapp/src/app/routes/lazy-pages.tsx` so `/app/tickets/:ticketId` uses the same workspace page.
- Ran focused route tests: `pnpm --dir webapp exec vitest run src/features/queues/support-workspace-mappers.test.ts src/pages/tickets/list-page.test.tsx src/app/router.test.tsx`: 11 tests passed.

### Stage 4: Left Worklist (10 points)

Files:

- New/modified component files under `webapp/src/pages/tickets/` or `webapp/src/features/queues/`.

Tasks:

- [x] Render work slices:
  - Нужен ответ;
  - SLA риск;
  - Без исполнителя;
  - Ответил пользователь.
- [ ] Render queues:
  - ServiceDesk L1;
  - Сети;
  - Серверы;
  - Оргтехника;
  - Системы;
  - ИБ.
- [x] Use existing smart-view and queue data where available; show zero/missing queues honestly.
- [x] Preserve extra saved/custom smart views after the four primary slices.
- [x] Render compact ticket rows:
  - number/code;
  - subject;
  - requester;
  - priority;
  - status;
  - SLA/risk;
  - unread dot;
  - assignee.
- [x] Implement selected state and filtering.
- [x] Add loading/error/empty states.

Expected completion after Stage 4: 64%.

Stage 4 evidence:

- Added canonical primary work-slice labels while preserving backend custom smart views.
- Updated `webapp/src/pages/tickets/list-page.test.tsx` to cover custom smart-view rendering and API filtering.
- Focused route/list/mapper tests passed: 11 tests.

### Stage 5: Center Ticket Workspace (16 points)

Files:

- New/modified component files under `webapp/src/pages/tickets/` or `webapp/src/features/queues/`.

Tasks:

- [x] Header:
  - breadcrumb/back;
  - ticket code and subject;
  - star/menu affordances;
  - metadata row.
- [x] Next action panel:
  - owner;
  - label;
  - hint;
  - remaining time;
  - SLA/OLA linkage.
- [x] Action bar:
  - Ответить;
  - Внутренняя заметка;
  - Запустить диагностику;
  - Ещё.
- [x] Timeline tabs:
  - Все;
  - Сообщения;
  - Внутреннее;
  - Диагностика;
  - История.
- [x] Timeline:
  - message/internal/system/operation/passport/approval styles;
  - structured operation result card;
  - attachments row where available.
- [x] Composer:
  - public/internal switch;
  - textarea;
  - attach/templates placeholders if backend is not ready;
  - explicit internal lock state;
  - send via current message mutation.

Expected completion after Stage 5: 80%.

Stage 5 evidence:

- Implemented selected ticket header, metadata chips, next-action panel, action bar, timeline tabs, timeline event cards and composer in `webapp/src/pages/tickets/list-page.tsx`.
- Public/internal composer uses the existing message mutation.
- Internal note tab/action is disabled when `can_send_internal_note` is false.

### Stage 6: Right Context Sidebar (10 points)

Files:

- New/modified component files under `webapp/src/pages/tickets/` or `webapp/src/features/queues/`.

Tasks:

- [x] Add tabs:
  - Контекст;
  - SLA;
  - Инструменты;
  - Знания;
  - Паспорт.
- [x] Context:
  - requester;
  - device;
  - category/service/classification.
- [x] SLA/OLA:
  - first response;
  - resolution;
  - OLA ack;
  - OLA processing;
  - ok/warning/danger/paused states.
- [x] Tools/playbooks:
  - available tools;
  - published playbooks;
  - disabled when offline/unavailable;
  - operation running summary.
- [x] Knowledge:
  - similar tickets/articles if available;
  - AI recommendation beta if backend returns it;
  - honest empty state if not available.
- [x] Passport:
  - readiness count;
  - checklist;
  - open passport action.

Expected completion after Stage 6: 90%.

Stage 6 evidence:

- Implemented right segmented sidebar for context, SLA, tools, knowledge and passport.
- Context reads requester/device/classification from the current ticket detail and registry snapshot.
- SLA cards are derived from first-response/resolution timers; detailed OLA DTO remains a backend TODO.
- Knowledge block is intentionally secondary and honest until a typed suggestions endpoint exists.

### Stage 7: Mutations, Permissions And States (5 points)

Files:

- `webapp/src/features/queues/api.ts`.
- Workspace component files.
- `server/web_api/support_handlers.py` only if new mutations are needed.

Tasks:

- [x] Public reply uses `postSupportTicketMessage(..., "public")`.
- [x] Internal note uses `postSupportTicketMessage(..., "internal")`.
- [x] Status action uses current typed status mutation.
- [x] Tool run uses current typed tool run mutation.
- [x] Playbook run uses current typed playbook run mutation.
- [x] Permission-denied states are shown, not silently ignored.
- [x] Agent offline disables agent-required tools.
- [x] Operation running invalidates detail/tools/playbooks/queue queries.

Expected completion after Stage 7: 95%.

Stage 7 evidence:

- Focused Vitest passed: `src/features/queues/support-workspace-mappers.test.ts`, `src/pages/tickets/list-page.test.tsx`, `src/app/router.test.tsx`.
- Production build passed: `pnpm --dir webapp run build`.

### Stage 8: Tests, Docs, Verification And Browser Signoff (5 points)

Files:

- Frontend tests for mappers and components.
- Server tests if API changes.
- `docs/QUICK_LOOKUP.md`, `server/docs/CODEMAP.md` if route/API structure changes.

Commands:

```powershell
.\scripts\bootstrap_shell_utf8.ps1
python scripts\verify_workspace.py
python scripts\bootstrap_web_toolchain.py
pnpm --dir webapp run build
pnpm --dir webapp test src\features\queues\support-workspace.test.tsx src\pages\tickets\list-page.test.tsx src\pages\tickets\detail-page.test.tsx
python -m pytest server\tests\test_web_support_api.py -q --tb=short
```

Remote/browser after local verification:

```powershell
python scripts\release_server_to_remote.py
python scripts\manage_remote_stack.py smoke server
```

Browser paths:

- `http://192.168.100.17:8666/admin`
- `http://192.168.100.17:8666/app/tickets`
- `http://192.168.100.17:8666/app/tickets/:ticketId`

Expected completion after Stage 8: 100%.

## Verification Matrix

### Local Functional Checks

- Queue loads with smart-view counts.
- Selecting a ticket opens center workspace.
- Deep link `/app/tickets/:ticketId` opens the same workspace with selected ticket.
- Public reply appears in timeline after mutation.
- Internal note is guarded by permission and visually distinct.
- Status transition uses server workflow guard.
- Tools show offline/unavailable/permission states.
- Playbooks show readiness and missing requirements.
- Passport readiness and open action work.

### Visual Checks

- Layout remains stable at 1366px desktop.
- Topbar is calm and has no KPI cards.
- Left, center and right columns scroll independently.
- Selected ticket and next action are the strongest focus.
- Timeline text does not overlap or clip.
- Buttons do not wrap awkwardly.
- Dark palette is not one-note; semantic colors remain readable.

### Backend Checks

- New DTOs validate with Pydantic.
- Existing support tests still pass.
- RBAC returns structured denial.
- No raw tokens or sensitive values appear in logs.
- Existing legacy routes remain unchanged.

## Open Risks

- The current active ticket detail page is large. Avoid a risky one-shot rewrite; migrate by composition and focused components.
- Existing `support-workspace.tsx` may tempt duplication. Prefer reusing ideas/mappers, not creating a second route.
- Knowledge backend is incomplete. Implement an honest stub or KB-link adapter rather than fake AI truth.
- SLA/OLA progress can be derived, but timer semantics must not be changed without dedicated tests.
- Deep-link behavior must not regress because operators may share ticket URLs.

## Current State

- Project context gathered.
- Active route ownership identified.
- Backend/API gap estimated at 35-40%.
- This plan is now the active long-horizon artifact.
- No code implementation has been started yet.

## Handoff

Recommended next step: Stage 1, create the frontend view model and mappers. This lets the UI be redesigned around existing backend payloads before adding backend fields. Add backend DTOs only for data the mapper cannot derive safely.
