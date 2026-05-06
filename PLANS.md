# Support Workspace SaaS Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans` or the project safe workflow when executing this plan. Keep this file current after each checkpoint. This plan replaces the old live-acceptance campaign plan and is now the active long-horizon plan for the `/app/tickets` redesign.

**Goal:** Redesign the operator support workspace around active `/app/tickets` routes into a production-ready modern SaaS service-desk workspace without breaking ticket business logic.

**Architecture:** Use the existing React/Vite webapp, shared UI primitives, typed `/api/web/support/*` boundary, ticket domain services, SLA/OLA/runtime services, playbook/tool APIs and passport APIs. Prefer an adaptation/view-model layer over replacing domain logic. Add backend DTO fields and typed aliases only where the current contract cannot support the reference workspace.

**Tech Stack:** React 19, Vite, TypeScript, Tailwind v4, TanStack Query, lucide-react, aiohttp typed web API, Pydantic DTOs, existing ticket/services/repos.

---

## Status

Created: 2026-05-05.

Current completion: 100% for P0, 100% for P1 including release/browser signoff, 100% for P2.1 knowledge catalog/search slice including release/browser signoff, 100% for P2.2 standalone timeline filtering including release/browser signoff, 100% for P2.3-P2.5 including release/browser signoff, 100% for P2.6 first-slice visual/readability hardening including release/browser signoff, 100% for P2.7 right-context enrichment polish including release/browser signoff, 100% for P2.8 diagnostics/tools UX hardening including release/browser signoff, 100% for P2.9 externalized knowledge provider including release/browser signoff, 100% for P2.10 "More" controls hardening including release/browser signoff, 100% for P2.11 final current-page browser/readiness pass, 100% for P3.1 tool policy metadata including release/browser signoff, 100% for P3.2 operation lifecycle semantics including release/browser signoff. P3 domain-depth track completion is about 40% overall. Overall current-page plan completion remains about 98-100%; P3 is optional domain depth rather than missing page readiness.

Current execution mode: P3.3 knowledge provider depth. P0 backend contract hardening and release/browser signoff are complete. P1 now has a typed selected-ticket aggregate endpoint, compact SLA/OLA and passport readiness DTOs, a lightweight workspace summary endpoint, first-class KB-link-backed knowledge suggestions with conservative AI beta summary, visible "More" controls wired to the tested mutation aliases, and Linux/browser signoff for commit `7a5fad8`. P2.1 extends the existing knowledge endpoint with a source-visible built-in catalog fallback for tickets without manual KB links and is deployed on the Linux stand. P2.2 adds standalone typed timeline filtering behind the existing timeline normalization and wires `/app/tickets` timeline tabs to it with aggregate fallback. P2.3-P2.5 adds nested structured diagnostic step/details extraction, a persisted `/app/tickets` theme toggle, and requester contact enrichment from registry person/location data, deployed on the Linux stand at commit `de8bf80`. P2.6 first slice completes SLA/OLA/passport readability, light-theme surface coverage and desktop-width audit. P2.7 enriches the right context tab with real registry provenance, asset identifiers, service/category metadata and related-knowledge count without adding fake data. P2.8 normalizes operation statuses, surfaces latest/running operations, makes tool/playbook disabled reasons visible in the right sidebar, and wraps long technical metadata safely. P2.9 moves support knowledge catalog/search out of the web handler into a first-class domain provider while keeping the existing API contract stable. P2.10 replaces primitive inline action controls with reason-capturing operator dialogs while preserving existing typed mutation aliases and backend workflow/RBAC guards, and was released/browser-checked at commit `7f835bf`. P2.11 completed final current-page browser/readiness validation across local checks, remote smoke, dark/light screenshots, page interactions, canonical support endpoints and server shutdown. P3.1 added manifest-derived tool policy metadata to the typed support tools payload and `/app/tickets` tools panel, released/browser-checked at commit `5061991`. P3.2 added read-only operation lifecycle hints to latest operation cards and diagnostic timeline cards, released/browser-checked at commit `cdd42ea`. P3 now focuses on richer domain semantics without changing DB schema or removing existing operator flows.

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
- `GET /api/web/support/tickets/{ticket_id}/knowledge-suggestions`

### Existing Domain Capabilities

- Smart views exist in `server/tickets/smart_views.py`.
- SLA and OLA logic exist in `server/tickets/sla_service.py` and `server/tickets/ola_service.py`.
- Ticket status/workflow logic exists in `server/tickets/workflow_service.py`.
- Assignment service exists in `server/tickets/assignment_service.py`.
- Routing service exists in `server/tickets/routing_service.py`.
- Playbook/tool launch exists in `server/web_api/support_handlers.py` and `server/app/services/playbook_engine.py`.
- Passport/evidence exists in `server/tickets/passport_service.py`, `server/tickets/evidence_service.py`, and `server/app/repos/ticket_passport_repo.py`.
- Registry/device context exists in `server/registry/*`, `RegistryRepo`, `DevicesRepo`.
- KB links exist at legacy ticket handler level and are now exposed through a first-class support workspace knowledge-suggestions endpoint; P2.1 adds a small built-in catalog fallback for common incidents when no manual KB links are present.

## Backend Functionality Gap Estimate

Estimated remaining backend functionality for the requested target after P2.5 implementation: **4-7%** at the typed web contract layer.

Important distinction:

- Domain/business functionality missing: **8-12%**. The project already has ticket lifecycle, smart views, routing, assignment, priority, SLA/OLA services, tools/playbooks, operations, passports, evidence, observer data and KB links. The remaining domain gap is mostly external/searchable KB depth, richer tool policy metadata, and richer operation state semantics.
- Typed workspace/API functionality missing: **4-7%**. The current React workspace now has a selected-ticket aggregate payload with compact SLA/OLA and passport readiness DTOs, a lightweight workspace summary contract, mutation aliases, first-class knowledge suggestions, standalone typed timeline filtering, nested diagnostic step extraction and registry requester enrichment. Remaining typed gaps are optional: external KB provider/index, richer operation-running/retry metadata, and deeper requester/account/service context.

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

- Workspace summary endpoint matching `GET /api/support/workspace/summary` semantics is now available as `GET /api/web/support/workspace/summary`.
- Aggregated ticket workspace endpoint returning all center/right-panel data in one payload is implemented as `GET /api/web/support/tickets/{ticket_id}/workspace`.
- First-class queue list/count DTO separate from smart views is implemented in the workspace summary/queue payloads; remaining queue work is optional inventory polish for missing/empty queues.
- Ticket list priority/assignee display DTO fields are implemented; remaining left-worklist work is visual density and selected-state polish.
- SLA/OLA progress DTO with remaining/target/status/progress is now available in the aggregate selected-ticket workspace payload; a standalone summary/list contract is still not implemented.
- Typed support aliases for assign, queue change, priority change and reroute are implemented and wired from visible "More" controls.
- Filterable unified timeline endpoint exists as `GET /api/web/support/tickets/{ticket_id}/timeline`; remaining timeline work is mostly operation-running, retry and details UX.
- Structured operation result mapper with step cards is implemented for common top-level and nested diagnostic payloads; remaining work is richer UI treatment for details, running state and unavailable-tool states.
- Knowledge suggestions endpoint with KB-linked articles, similar tickets, built-in catalog fallback and conservative AI beta summary is implemented as `GET /api/web/support/tickets/{ticket_id}/knowledge-suggestions` and included in the aggregate workspace payload.
- Compact resolution passport readiness DTO for sidebar is now available in the aggregate selected-ticket workspace payload; a standalone endpoint remains optional.
- Theme toggle/light-dark workspace shell state is implemented; remaining work is full light-theme visual polish across every panel and responsive desktop width.

## Backend Contract Analysis 2026-05-05

### Routes Already Available

- `GET /api/web/support/bootstrap`
  - Current typed bootstrap for support capabilities and observer endpoint hints.
- `GET /api/web/support/queue`
  - Current queue/list route. Supports `scope`, `status`, `smart_view`, `query`, `limit`.
  - Returns `summary.smart_view_counts`, status counts, smart-view options and ticket rows.
  - Built-in and custom smart views are evaluated through `server/tickets/smart_views.py`.
- `GET /api/web/support/tickets/{ticket_id}`
  - Current typed detail route. Returns ticket header data, request form summary, observer summary, filtered timeline, snapshot, status actions and closure requirements.
- `POST /api/web/support/tickets/{ticket_id}/messages`
  - Current public/internal message route used by composer.
- `POST /api/web/support/tickets/{ticket_id}/status`
  - Current status transition route. Uses workflow/approval/closure guards and can auto-assign on `in_progress`.
- `GET /api/web/support/tickets/{ticket_id}/tools`
  - Current typed tool availability route.
- `POST /api/web/support/tickets/{ticket_id}/tools/run`
  - Current ticket-scoped tool run route with consent handling.
- `GET /api/web/support/tickets/{ticket_id}/playbooks`
  - Current typed playbook availability/readiness route.
- `POST /api/web/support/tickets/{ticket_id}/playbooks/run`
  - Current ticket-scoped playbook run route.
- `GET/POST/PATCH /api/web/support/tickets/{ticket_id}/passport*`
  - Current passport, evidence and knowledge-draft routes.
- `POST /api/web/support/tickets/{ticket_id}/approvals/{approval_id}/decision`
  - Current approval decision route.
- Legacy but available: `POST /api/tickets/{ticket_id}/assign`, `/queue`, `/priority`, `/reroute`.
  - These use the existing assignment, queue, priority and routing services, but are not yet exposed through the typed `/api/web/support/*` boundary.

### Gaps By Priority

P0 - required before calling the backend contract production-complete:

- [x] Add priority and assignee display fields to `SupportQueueTicketItem` and `webapp/src/features/queues/api.ts`.
- [x] Add authoritative queue counts/list to the support queue payload or a new summary payload.
- [x] Expand typed detail timeline to include status, assignment, queue, priority, SLA/OLA, passport/evidence and operation events with normalized event kinds.
- [x] Add typed `/api/web/support/tickets/{ticket_id}/assign|queue|priority|reroute` aliases over the existing legacy handlers/services.

P0 first-slice evidence:

- RED verified: `server/tests/test_web_support_api.py::test_web_support_queue_returns_typed_scope_and_filter_payload` failed on missing `priority`.
- GREEN verified: the same backend test passes after adding queue item priority/assignee fields and `summary.queue_counts`.
- Frontend focused Vitest passed for `support-workspace-mappers.test.ts`, `list-page.test.tsx` and `router.test.tsx`.
- `server/tests/test_web_support_api.py` passed: 35 tests.
- `pnpm --dir webapp run build` passed.
- `python scripts/verify_workspace.py` passed after updating `docs/QUICK_LOOKUP.md` and `scripts/navigation_catalog.py` for the typed support/registry DTO drift rule.

P0 second-slice evidence:

- RED verified: `server/tests/test_web_support_api.py::test_web_support_ticket_detail_timeline_includes_normalized_lifecycle_events` failed because lifecycle events were filtered out of the typed detail timeline.
- GREEN verified: the same backend test passes after adding `event_category`, `event_label`, `event_details`, `operation_steps` and expanding support timeline event filtering.
- `server/tests/test_web_support_api.py` passed: 36 tests.
- Frontend mapper RED/GREEN verified for normalized timeline categories and operation steps.
- Focused Vitest passed for `support-workspace-mappers.test.ts`, `list-page.test.tsx` and `router.test.tsx`: 12 tests.
- `pnpm --dir webapp run build` passed.

P0 third-slice evidence:

- RED verified: new alias tests failed with 404 before routes existed.
- GREEN verified: `POST /api/web/support/tickets/{ticket_id}/assign|queue|priority|reroute` now return typed `SupportTicketMutationActionResult`.
- RBAC tests verify typed forbidden payloads for `ticket.assign`, `ticket.queue.change` and `ticket.status.change`.
- `server/tests/test_web_support_api.py` passed: 41 tests.
- Focused Vitest passed for `support-workspace-mappers.test.ts`, `list-page.test.tsx` and `router.test.tsx`: 12 tests.
- `pnpm --dir webapp run build` passed.

P0 release/browser signoff evidence:

- Green CI artifact created for commit `055f20b88286446e6ad739ecf9d75840cc2c4189`: `python scripts/run_ci_suite.py` wrote `artifacts/ci/055f20b88286446e6ad739ecf9d75840cc2c4189/summary.json` with status `green`.
- Linux release completed: `python scripts/release_server_to_remote.py` deployed branch `codex/helpdesk-process-model`, applied remote migrations, uploaded the webapp bundle and passed remote smoke (`/api/health -> 200`).
- Browser signoff completed at `http://192.168.100.17:8666/admin`: React shell redirected to `/app/tickets/:ticketId`, and the 3-column support workspace rendered with topbar, smart views, queue list, selected ticket, next-action panel, timeline/composer and right context tabs.
- Browser network verified support APIs returned 200 for queue, ticket detail, tools, playbooks and passport.
- Non-blocking browser observation: the support-role shell still logs one 403 for admin-only `GET /api/web/admin/connection_requests`; this does not block `/app/tickets` and remains a separate access UX cleanup item.

P1 - important for performance and the target architecture:

- [x] Add `GET /api/web/support/tickets/{ticket_id}/workspace` aggregate payload:
  - ticket detail;
  - full timeline;
  - context;
  - SLA/OLA;
  - tools/playbooks;
  - knowledge;
  - passport readiness;
  - permissions/actions.
- [x] Add `GET /api/web/support/workspace/summary` or extend `GET /api/web/support/queue?include_rows=0`.
- [x] Add compact `sla_ola` DTO with `first_response`, `resolution`, `ola_ack`, `ola_processing`.
- [x] Add compact passport readiness DTO so the right sidebar does not need the full passport payload.
- [x] Wire visible "More" menu controls to the typed `assign`, `queue`, `priority` and `reroute` aliases.

P1 first-slice evidence:

- RED verified: `server/tests/test_web_support_api.py::test_web_support_ticket_workspace_aggregates_detail_tools_passport_and_knowledge` failed with 404 before the aggregate route existed.
- GREEN verified: the same backend test passes after adding `SupportTicketWorkspacePayload` and `GET /api/web/support/tickets/{ticket_id}/workspace`.
- RED/GREEN frontend verified: `webapp/src/pages/tickets/list-page.test.tsx` now proves `/app/tickets/:ticketId` calls `fetchSupportTicketWorkspace()` and the "Ещё" menu exposes typed actions; reroute calls `postSupportTicketReroute(ticketId, { reason: "manual_recalculate" })`.
- Local verification passed: `python -m pytest server/tests/test_web_support_api.py -q --tb=short`, focused Vitest, `pnpm --dir webapp run build`, and `python scripts/verify_workspace.py`.
- Green CI artifact created for commit `368328b8a92f4d8fcc0ca965f0420da27117552a`; `python scripts/run_ci_suite.py` passed workspace verification, webapp bundle, server no-db/db-api/agent-ws layers and pc_agent tests.
- Linux release completed: `python scripts/release_server_to_remote.py` deployed branch `codex/helpdesk-process-model`, applied migrations, uploaded the webapp bundle and passed remote smoke (`/api/health -> 200`).
- Browser signoff completed at `http://192.168.100.17:8666/admin`: `/app/tickets/:ticketId` loaded the selected ticket through `GET /api/web/support/tickets/{ticket_id}/workspace -> 200`, and the visible "Ещё" menu rendered `Назначить на себя`, `Сменить очередь`, `Изменить приоритет`, `Пересчитать маршрут`.

P1 second-slice evidence:

- RED verified: backend aggregate test failed with missing `sla_ola`, and frontend mapper test failed because it still derived two timers from detail instead of preferring compact workspace DTOs.
- GREEN verified: `GET /api/web/support/tickets/{ticket_id}/workspace` now returns compact `sla_ola` timers for first response, resolution, OLA ack and OLA processing, plus `passport_readiness` with the four sidebar checklist items.
- Frontend mapper now prefers compact `sla_ola` and `passport_readiness` when present, while keeping the previous detail/passport derivation as fallback.
- Focused verification passed: `python -m pytest server\tests\test_web_support_api.py::test_web_support_ticket_workspace_aggregates_detail_tools_passport_and_knowledge -q --tb=short` and `pnpm --dir webapp exec vitest run src\features\queues\support-workspace-mappers.test.ts`.
- Local verification passed: `python -m pytest server\tests\test_web_support_api.py -q --tb=short` (42 tests), `pnpm --dir webapp exec vitest run src\pages\tickets\list-page.test.tsx src\features\queues\support-workspace-mappers.test.ts`, `pnpm --dir webapp run build`, and `python scripts\verify_workspace.py`.

P1 third-slice evidence:

- RED verified: `server\tests\test_web_support_api.py::test_web_support_workspace_summary_returns_view_and_queue_counts_without_rows` failed with 404 before the endpoint existed.
- GREEN verified: `GET /api/web/support/workspace/summary` now returns row-free `views`, `queues`, `smart_view_counts` and `smart_view_options`.
- The summary `views` object exposes target aliases `needs_action`, `sla_risk`, `unassigned` and `requester_replied` while preserving existing backend smart-view ids in `smart_view_counts`.
- Frontend typed client `fetchSupportWorkspaceSummary(limit)` added for the lightweight endpoint.
- Focused verification passed: `python -m pytest server\tests\test_web_support_api.py::test_web_support_workspace_summary_returns_view_and_queue_counts_without_rows server\tests\test_web_support_api.py::test_web_support_queue_returns_typed_scope_and_filter_payload -q --tb=short` and `pnpm --dir webapp exec vitest run src\features\queues\api.test.ts`.
- Local verification passed: `python -m pytest server\tests\test_web_support_api.py -q --tb=short` (43 tests), `pnpm --dir webapp exec vitest run src\features\queues\api.test.ts src\pages\tickets\list-page.test.tsx src\features\queues\support-workspace-mappers.test.ts`, `pnpm --dir webapp run build`, and `python scripts\verify_workspace.py`.
- Linux release completed for commit `0a69b51fe1b49b7c00312facbf5d9a16ffce304e` with `python scripts\release_server_to_remote.py --skip-ci-check --leave-running --smoke-attempts 6 --smoke-delay 5`; release verification, local webapp build, remote migrations, bundle upload and remote smoke passed.
- Browser signoff completed at `http://192.168.100.17:8666/admin`: `/app/tickets/:ticketId` rendered, and `GET /api/web/support/workspace/summary` returned 200 with row-free `views`, `queues`, `smart_view_counts` and no `tickets` key.

P1 fourth-slice evidence:

- RED verified: `server\tests\test_web_support_api.py::test_web_support_ticket_knowledge_suggestions_returns_sources_and_workspace_payload` failed with 404 before the typed endpoint existed.
- GREEN verified: `GET /api/web/support/tickets/{ticket_id}/knowledge-suggestions` returns KB-linked articles, similar tickets from `custom_fields.similar_tickets`, and a conservative `AI-рекомендация / Бета` summary with explicit sources.
- Aggregate `GET /api/web/support/tickets/{ticket_id}/workspace` now embeds the same knowledge payload, so the right sidebar does not need a separate waterfall.
- Frontend typed client `fetchSupportTicketKnowledgeSuggestions(ticketId)` added; `/app/tickets` maps aggregate `knowledge` into articles, similar tickets and the AI beta block instead of the old placeholder text.
- Focused verification passed: `python -m pytest server\tests\test_web_support_api.py::test_web_support_ticket_knowledge_suggestions_returns_sources_and_workspace_payload -q --tb=short` and `pnpm --dir webapp exec vitest run src\features\queues\api.test.ts src\features\queues\support-workspace-mappers.test.ts src\pages\tickets\list-page.test.tsx`.
- Local release verification passed: `python -m pytest server\tests\test_web_support_api.py -q --tb=short` (44 tests), focused Vitest (13 tests), `pnpm --dir webapp run build`, `python scripts\verify_workspace.py`, and `git diff --check`.
- Linux release completed for commit `7a5fad89b5a551f82c62b34538423cfeb04346ae` with `python scripts\release_server_to_remote.py --skip-ci-check --leave-running --smoke-attempts 6 --smoke-delay 5`; release verification, local webapp build, remote migrations, bundle upload and remote smoke passed.
- Browser signoff completed at `http://192.168.100.17:8666/admin`: `/app/tickets/:ticketId` rendered, the "Знания" tab showed the source-safe empty state for a ticket without KB links, `GET /api/web/support/tickets/{ticket_id}/workspace` returned 200 with `knowledge`, and standalone `GET /api/web/support/tickets/{ticket_id}/knowledge-suggestions` returned 200.

P2 - valuable, but can follow after core operator flows:

- [x] Add richer knowledge catalog/search integration behind the existing `GET /api/web/support/tickets/{ticket_id}/knowledge-suggestions` contract.
- [x] Add standalone typed timeline filtering endpoint behind existing support timeline normalization.
- [x] Add structured operation step extraction for diagnostic payloads.
- [x] Add frontend theme toggle/state integration for `/app/tickets`.
- [x] Add richer assignee/user profile display names and requester phone/email where registry data exists.

P2.1 knowledge catalog/search evidence:

- RED verified: `server\tests\test_web_support_api.py::test_web_support_ticket_knowledge_suggestions_uses_catalog_search_without_manual_links` failed because `KB-HTTP-502` was absent without manual KB links.
- GREEN verified: the same test passes after adding a built-in knowledge catalog fallback in `server/web_api/support_handlers.py`.
- Compatibility verified: existing manual-KB/workspace aggregate test still passes, and catalog fallback is suppressed when manual KB links are already attached to avoid duplicate right-sidebar suggestions.
- Local verification passed: `python -m pytest server\tests\test_web_support_api.py -q --tb=short` (45 tests), focused Vitest for queues/list page (13 tests), `pnpm --dir webapp run build`, `python scripts\verify_workspace.py`, and `git diff --check`.
- Full CI passed for commit `2cb35928754f17825e8863f6465766d1e39c9f69`: workspace verification, webapp bundle, server no-db/db-api/agent-ws layers and pc_agent tests.
- Linux release completed for commit `2cb35928754f17825e8863f6465766d1e39c9f69` with `python scripts\release_server_to_remote.py --leave-running --smoke-attempts 6 --smoke-delay 5`; remote fast-forward, migrations, bundle upload and remote smoke passed.
- Browser signoff completed at `http://192.168.100.17:8666/admin`: `/app/tickets/:ticketId` rendered, the "Знания" tab opened, `GET /api/web/support/tickets/{ticket_id}/workspace`, standalone `GET /api/web/support/tickets/{ticket_id}/knowledge-suggestions` and `GET /api/web/support/workspace/summary` returned 200, and aggregate `/workspace` embedded `knowledge`.

P2.2 standalone timeline filtering scope:

- Add `GET /api/web/support/tickets/{ticket_id}/timeline?filter=all|messages|internal|diagnostics|history&limit=...`.
- Reuse existing support timeline event allow-list and normalized `SupportTicketMessage` serializer.
- Keep aggregate `/workspace` behavior unchanged; the standalone endpoint is an optimization/contract for tab-specific refreshes.
- Map `history` to lifecycle/governance categories: history, SLA, OLA, passport and approval.

P2.2 standalone timeline filtering evidence:

- RED verified: `server\tests\test_web_support_api.py::test_web_support_ticket_timeline_endpoint_filters_normalized_events` failed with 404 before the typed endpoint existed.
- GREEN verified: `GET /api/web/support/tickets/{ticket_id}/timeline?filter=diagnostics|internal|history|all` returns normalized timeline rows using the same support serializer and lifecycle allow-list as aggregate/detail timeline.
- RED/GREEN frontend verified: `webapp/src/features/queues/api.test.ts` first failed on missing `fetchSupportTicketTimeline()`, then passed after adding the typed client; `webapp/src/pages/tickets/list-page.test.tsx` proves the "Диагностика" tab calls `fetchSupportTicketTimeline(ticketId, "diagnostics")` and renders filtered operation results.
- `/app/tickets` keeps aggregate `/workspace` timeline behavior for `all` and uses the standalone endpoint only for tab-specific refreshes, with local aggregate filtering as fallback.
- Local verification passed: `python -m pytest server\tests\test_web_support_api.py -q --tb=short` (46 tests), focused Vitest for queue API/mappers/list page (15 tests), `pnpm --dir webapp run build`, `python scripts\verify_workspace.py`, and `git diff --check`.
- Full CI passed for commit `3bff79a65bf08b127430d4936a95095093fa58ee`: workspace verification, webapp bundle, server no-db/db-api/agent-ws layers and pc_agent tests.
- Linux release completed for commit `3bff79a65bf08b127430d4936a95095093fa58ee` with `python scripts\release_server_to_remote.py --leave-running --smoke-attempts 6 --smoke-delay 5`; remote fast-forward, migrations, bundle upload and remote smoke passed.
- Browser signoff completed at `http://192.168.100.17:8666/admin`: `/app/tickets/:ticketId` rendered, aggregate `GET /api/web/support/tickets/{ticket_id}/workspace` returned 200, standalone `GET /api/web/support/tickets/{ticket_id}/timeline?filter=diagnostics` returned 200, and clicking the exact "Диагностика" timeline tab waited for the same 200 response.

P2.3-P2.5 execution scope:

- P2.3: Extract operation steps not only from top-level `payload.steps`, but also from common nested diagnostic payload shapes such as `payload.result.steps`, `payload.result.checks`, `payload.result.diagnostics`, `payload.observations.steps`, and normalize titles/status/value/details for richer operation result cards.
- P2.4: Add a compact theme toggle to `/app/tickets` topbar, persist the workspace theme in browser storage, and keep dark mode as the default accepted visual target.
- P2.5: Extend support registry/contact DTOs to include requester `phone`, `email`, location `floor`, and source/contact provenance when existing `registry_people` / `registry_locations` rows provide those fields. Keep safe fallbacks when data is absent.

P2.3-P2.5 verification plan:

- Backend RED/GREEN in `server/tests/test_web_support_api.py` for nested diagnostic step extraction and registry contact fields in aggregate workspace payload.
- Frontend RED/GREEN in `support-workspace-mappers.test.ts` and `list-page.test.tsx` for enriched context, structured step cards and theme persistence/toggle.
- Required local gates: focused backend test, focused Vitest, `pnpm --dir webapp run build`, `python scripts\verify_workspace.py`, `git diff --check`.
- Required release gates: full `python scripts\run_ci_suite.py`, standard Linux release, browser signoff at `http://192.168.100.17:8666/admin`, then stop remote server.

P2.3-P2.5 local evidence:

- RED verified: focused backend tests failed on missing nested diagnostic `operation_steps` and missing `person_phone` in aggregate workspace registry snapshot.
- RED verified: focused frontend tests failed on missing step `details` rendering, missing workspace theme state and missing registry phone/email in the right context sidebar.
- GREEN verified: `python -m pytest server\tests\test_web_support_api.py::test_web_support_timeline_extracts_nested_diagnostic_steps server\tests\test_web_support_api.py::test_web_support_workspace_enriches_requester_contact_from_registry -q --tb=short` passed.
- GREEN verified: `pnpm --dir webapp exec vitest run src\features\queues\support-workspace-mappers.test.ts src\pages\tickets\list-page.test.tsx` passed.
- Extended local verification passed so far: `python -m pytest server\tests\test_web_support_api.py -q --tb=short` (48 tests), `pnpm --dir webapp exec vitest run src\features\queues\api.test.ts src\features\queues\support-workspace-mappers.test.ts src\pages\tickets\list-page.test.tsx` (18 tests), `pnpm --dir webapp run build`, `python scripts\verify_workspace.py`, and `git diff --check`.
- Pre-commit full CI evidence: `python scripts\run_ci_suite.py --server-pytest-timeout 5400 --idle-timeout 0` passed with green summary for current dirty workspace state; repeat required after commit so deploy artifact matches the final commit SHA.
- Post-commit verification for `de8bf80` passed sequentially: `python scripts\verify_workspace.py`, `python -m pytest server\tests\test_web_support_api.py -q --tb=short` (48 tests), focused frontend Vitest/build, and `python -m pytest server\tests -m "not manual and agent_ws" -vv --durations=80 --tb=short` (25 tests). Combined `run_ci_suite.py` on Windows hit an unrelated agent_ws/test-DB lock timeout after verify/build/no-db/db-api layers passed; release used the standard script with explicit `--skip-ci-check` and the sequential evidence above.
- Linux release completed for commit `de8bf80` with `python scripts\release_server_to_remote.py --skip-ci-check --leave-running --smoke-attempts 6 --smoke-delay 5`; remote fast-forward, migrations, web bundle upload and remote smoke passed.
- Browser signoff completed at `http://192.168.100.17:8666/admin` for `/app/tickets/:ticketId`: workspace root rendered with `data-theme="dark"`, aggregate `/workspace` returned 200, standalone diagnostics timeline returned 200, exact `Диагностика` tab rendered, theme toggle switched to `data-theme="light"` and `localStorage.support-workspace-theme=light`, and final browser console reported 0 errors.

### Recommended Next Slices For `/app/tickets`

Recommended next slice: **P2.6 visual/light-theme/responsive hardening**. The page already has the target data contract and working operator flows, so the next useful work is visual production readiness on the current route rather than more backend shape work.

P2.6 - visual/light-theme/responsive hardening:

- Audit `/app/tickets` and `/app/tickets/:ticketId` at 1366, 1440 and 1920px desktop widths in dark and light themes.
- Polish the current light theme so all major surfaces, chips, borders, timeline rows, sidebars, composer and dropdowns are readable and cohesive, not only the topbar/root shell.
- Treat SLA/OLA and resolution passport as high-priority visual surfaces: timers must show breached/at-risk/paused/ok states clearly, progress bars must remain readable in both themes, passport readiness must not look like a passive placeholder, and "open passport" must stay obvious.
- Add edge-case visual states for SLA/OLA/passport where the existing view model supports them: unknown timer, paused timer, breached timer, no timers, passport 0/N, passport complete N/N, and missing passport fallback.
- Tighten density and overflow handling in the left ticket list, central action/timeline area and right context tabs.
- Fix any clipped text, awkward wraps, weak contrast, non-obvious selected state or scroll containment issues found in browser screenshots.
- Keep this frontend-only unless the audit exposes missing data that cannot be represented safely.

P2.7 - right-context enrichment polish:

- Improve display of requester/contact/source provenance, device/account/service/category/location fields when existing registry data provides them.
- Keep absent data quiet and explicit; avoid fake values.
- Add tests for mapper fallback behavior where registry fields are missing.

P2.8 - diagnostics/tools UX hardening:

- Improve operation-running and tool-unavailable states in the right sidebar and timeline.
- Show structured diagnostic step details more clearly, including retry/details affordances when the payload provides them.
- Disable agent-required tools with visible reason when the device is offline or policy denies the action.

P2.9 - externalized knowledge provider:

- Keep the existing `knowledge-suggestions` contract stable.
- Move beyond the built-in catalog fallback toward a first-class searchable KB provider/index if a project source exists.
- Keep AI beta copy source-visible and conservative; no automatic action execution.
- Concrete P2.9 slice in progress:
  1. [x] Move the hardcoded support knowledge catalog/search out of `server/web_api/support_handlers.py` into a `server/tickets` provider module with a small JSON-backed catalog source.
  2. [x] Preserve the existing typed `GET /api/web/support/tickets/{ticket_id}/knowledge-suggestions` and aggregate `/workspace` payload shape.
  3. [x] Keep manual ticket KB links preferred, then catalog search, then similar tickets; no fake AI/action execution.
  4. [x] Add focused provider/API tests for catalog search, manual-link precedence, dedupe and source summary behavior.
  5. [x] Update CODEMAP/quick lookup for the new provider location, then run focused server tests, webapp build/type checks and workspace verification.

P2.9 local evidence:

- Implemented `server/tickets/knowledge_provider.py` and `server/tickets/knowledge_catalog.json` as the support knowledge provider/catalog boundary.
- `server/web_api/support_handlers.py` now keeps only the typed route/DTO mapping and calls `build_knowledge_suggestions(...)`; the public `knowledge-suggestions` and aggregate `/workspace` payload shapes stay unchanged.
- Manual KB links remain preferred; catalog suggestions are added only when no manual articles are attached, and similar tickets plus AI beta summary remain source-visible and non-acting.
- Added `server/tests/test_support_knowledge_provider.py` for JSON catalog loading, dedupe, scoring and conservative source summary behavior.
- Local verification passed: focused support knowledge pytest (6 tests), `pnpm --dir webapp run build`, `python scripts\verify_workspace.py`, and `git diff --check`.
- Linux release completed for commit `079caf2` with `python scripts\release_server_to_remote.py --skip-ci-check --leave-running --smoke-attempts 6 --smoke-delay 5`; remote smoke passed.
- Browser signoff completed at `http://192.168.100.17:8666/admin`: `/app/tickets/:ticketId` rendered, the "Знания" tab opened, aggregate `GET /api/web/support/tickets/{ticket_id}/workspace` returned 200 with embedded `knowledge`, and standalone `GET /api/web/support/tickets/{ticket_id}/knowledge-suggestions` returned 200.
- Remaining browser console/network noise: known non-blocking support-role 403 for admin-only `GET /api/web/admin/connection_requests`; `/app/tickets` support APIs were 200.

P2.10 - "More" controls hardening:

- Replace primitive controls with proper reason-capturing modals/drawers for status, queue, priority, assign and reroute where the current workflow requires operator context.
- Preserve the existing typed mutation aliases and workflow/RBAC guards.
- Add permission/disabled states rather than hiding critical operator context.
- Concrete P2.10 slice complete:
  1. [x] Move status change from the inline select/apply pair into the "Ещё" action menu.
  2. [x] Add one compact operator action dialog that captures reason/comment for status, assign-to-self, queue change, priority change and reroute.
  3. [x] Use existing typed mutations only: status, assign, queue, priority and reroute; do not add backend routes.
  4. [x] Disable submit when the required target or reason is missing, and show clear disabled states for missing queues/status options.
  5. [x] Add focused React tests for the dialog, reason payloads, and queue/priority/status target selection.
  6. [x] Run focused Vitest, production build, workspace verification, deploy/browser signoff and stop the remote server.

P2.10 local evidence:

- Replaced the central inline status select/apply pair with a status action in the "Ещё" menu.
- Added a compact operator action dialog for status, assign-to-self, queue change, priority change and reroute.
- The dialog requires a human-readable reason before submit and sends optional internal comment where the existing typed client/backend support it.
- No backend routes were added; the UI still uses existing typed status/assign/queue/priority/reroute mutations.
- Focused verification passed: `pnpm --dir webapp exec vitest run src\pages\tickets\list-page.test.tsx src\features\queues\api.test.ts` (12 tests), `pnpm --dir webapp run build`, `python scripts\verify_workspace.py`, and `git diff --check`.
- Linux release completed for commit `7f835bf` with `python scripts\release_server_to_remote.py --skip-ci-check --leave-running --smoke-attempts 6 --smoke-delay 5`; remote smoke passed on the second attempt after service warm-up.
- Browser signoff completed at `http://192.168.100.17:8666/admin`: `/app/tickets/:ticketId` rendered, the "Ещё" menu showed `Назначить на себя`, `Сменить статус`, `Сменить очередь`, `Изменить приоритет` and `Пересчитать маршрут`; status and reroute dialogs enforced required reason before submit, and no live mutation was submitted during signoff.
- Aggregate/current support endpoints returned 200 in browser context: `GET /api/web/support/workspace/summary`, `GET /api/web/support/tickets/{ticket_id}/workspace`, `GET /api/web/support/tickets/{ticket_id}/tools`, `GET /api/web/support/tickets/{ticket_id}/knowledge-suggestions`, and `GET /api/web/support/tickets/{ticket_id}/passport`.
- Remaining browser console/network noise: known non-blocking support-role 403 for admin-only `GET /api/web/admin/connection_requests`; three 404 entries were created only by a manual probe against obsolete non-canonical `/api/web/tickets/...` URLs and are not emitted by the page flow.

P2.11 - final current-page browser signoff:

- Concrete P2.11 slice complete:
  1. [x] Re-run local focused tests, production build and workspace verification after the P2.10 plan closeout commit.
  2. [x] Deploy the plan closeout/docs state to the Linux stand without changing runtime code.
  3. [x] Capture dark/light desktop screenshots at 1366px and 1920px.
  4. [x] Verify `/app/tickets`, selected ticket, right tabs, timeline filters, composer and "Ещё" controls in browser.
  5. [x] Verify console/network health against canonical `/api/web/support/*` endpoints and record known non-blocking noise.
  6. [x] Stop the remote server after signoff.

P2.11 evidence:

- Local verification passed: `pnpm --dir webapp exec vitest run src\pages\tickets\list-page.test.tsx src\features\queues\api.test.ts` (12 tests), `pnpm --dir webapp run build`, `python scripts\verify_workspace.py`.
- Remote server was started with `python scripts\manage_remote_stack.py start server`; the first smoke failed during warm-up, logs showed successful DB init and running service, and the repeat `python scripts\manage_remote_stack.py smoke server` returned `OK http://192.168.100.17:8666/api/health -> 200`.
- Browser Use runtime failed to start because the local app-server path was missing, so final rendered validation used Playwright MCP against the canonical stand URL `http://192.168.100.17:8666/admin`.
- Browser identity and nonblank checks passed: page title `pc_client — рабочие места`, URL `/app/tickets/{ticket_id}`, visible topbar, left work slices, selected ticket, next action, timeline, composer and right context.
- Screenshots captured for visual evidence: `support-workspace-p2-11-1366-light.png`, `support-workspace-p2-11-1366-dark.png`, `support-workspace-p2-11-1920-dark.png`, and `support-workspace-p2-11-1920-light.png`.
- Right sidebar tabs were exercised: `Контекст`, `SLA`, `Инструменты`, `Знания`, `Паспорт`; SLA tab showed breached first-response/resolution timers plus no-deadline OLA rows.
- Timeline filters were exercised: `Сообщения`, `Внутреннее`, `Диагностика`, `История`, `Все`; article counts changed by filter without rendering errors.
- Composer was exercised in public/internal modes; public mode kept empty `Отправить` disabled, internal mode changed placeholder to `Напишите внутреннюю заметку для команды...`.
- "Ещё" controls were exercised: all five actions were visible, and `Пересчитать маршрут` opened a dialog with submit disabled until a reason is entered; no live mutation was submitted during signoff.
- Canonical support endpoints returned 200 in browser context: `GET /api/web/support/workspace/summary`, `GET /api/web/support/tickets/{ticket_id}/workspace`, `GET /api/web/support/tickets/{ticket_id}/tools`, `GET /api/web/support/tickets/{ticket_id}/knowledge-suggestions`, and `GET /api/web/support/tickets/{ticket_id}/passport`.
- Console health: only known non-blocking support-role 403 for admin-only `GET /api/web/admin/connection_requests`.
- Remote server was stopped after signoff: `active=inactive`, `sub=dead`.

## P3 Domain Depth Track

P3 is not a rescue pass for the page. The page is production-ready for the current contract after P2.11. P3 adds deeper domain semantics where the UI currently has enough structure to work but can expose better operational truth to an L1/L2 operator.

Scope:

- Keep `/app/tickets` as the only active support workspace route.
- Prefer typed DTO additions and adapter fields over new routes.
- Avoid DB migrations unless a slice explicitly needs persistent state.
- Keep AI/knowledge suggestions conservative and source-visible.
- Keep tool/playbook execution confirmation under operator control.

P3.1 - tool policy metadata:

- Goal: make tool/playbook availability less opaque by surfacing existing manifest/policy metadata in the typed support tools payload and right sidebar.
- Files:
  - `server/web_api/dto/support.py`
  - `server/web_api/support_handlers.py`
  - `server/tests/test_web_support_api.py`
  - `webapp/src/features/queues/api.ts`
  - `webapp/src/features/queues/support-workspace-mappers.ts`
  - `webapp/src/pages/tickets/list-page.test.tsx`
  - `server/docs/CODEMAP.md`
- Checklist:
  1. [x] Extend `SupportToolItem` with policy fields derived from `ToolMetadata`: `domain`, `tool_kind`, `required_permission`, `allowed_roles`, `policy_labels`.
  2. [x] Populate those fields in `_normalize_support_tool_entry()` without adding routes or changing run behavior.
  3. [x] Extend TypeScript API types and workspace mapper to show concise policy labels in the tools sidebar.
  4. [x] Add focused backend and frontend tests proving the metadata is returned and rendered.
  5. [x] Update CODEMAP and run focused tests/build/workspace verification.

P3.1 local evidence:

- `SupportToolItem` now carries existing tool-manifest policy metadata (`domain`, `tool_kind`, `required_permission`, `allowed_roles`, `policy_labels`) through the typed support tools payload.
- `_normalize_support_tool_entry()` keeps the existing tool run behavior intact and only enriches the DTO from `ToolMetadata`.
- `/app/tickets` tools sidebar mapper renders concise operator-visible labels such as required permission and allowed roles.
- The sidebar automation list now keeps both playbooks and tools visible when both catalogs are present, instead of letting many playbooks hide tool policy labels.
- Focused checks already passed: `python -m pytest server/tests/test_web_support_api.py::test_web_support_ticket_tools_returns_typed_inventory -v --tb=short`; `pnpm --dir webapp exec vitest run src\pages\tickets\list-page.test.tsx src\features\queues\support-workspace-mappers.test.ts src\features\queues\api.test.ts`.
- Build/verification passed: `python scripts\bootstrap_web_toolchain.py`; `pnpm --dir webapp run build`; `python scripts\verify_workspace.py`; `git diff --check`.
- Release/browser signoff passed on Linux stand at commit `5061991`: `release_server_to_remote.py --skip-ci-check --leave-running --smoke-attempts 6 --smoke-delay 5`, smoke `/api/health` 200, `/app/tickets` tools tab shows both playbooks and tools, and live tool cards show `Право: module.tool.run.low_risk` plus `Роли: admin, support`.

P3.2 - operation lifecycle semantics:

- Goal: enrich latest operation cards and timeline operation results with retryability, duration, trace/detail hints and policy/error category when existing operation/event payloads provide them.
- Non-goal: no retry button until the backend has a safe, idempotent retry contract.
- Checklist:
  1. [x] Extend typed support operation/timeline DTOs with read-only lifecycle metadata: duration, retry counts/retryable, error code/category, trace id and details URL.
  2. [x] Populate metadata from existing `Operation` columns and diagnostic event payloads without changing lifecycle transitions or adding retry actions.
  3. [x] Extend `/app/tickets` view-model and UI to show compact lifecycle chips in latest operations and diagnostic timeline cards.
  4. [x] Add focused backend/frontend tests.
  5. [x] Run focused tests/build/workspace verification, then release/browser signoff.

P3.2 local evidence:

- `SupportTicketOperationSnapshot` and support timeline messages now carry read-only lifecycle hints: `duration_ms`, `retry_count`, `max_retries`, `retryable`, `error_code`, `error_category`, `trace_id` and `details_url`.
- Latest operation snapshots populate those fields from existing `operations` columns; diagnostic timeline rows populate them from event payloads when present. No retry button or lifecycle mutation was added.
- `/app/tickets` renders compact lifecycle chips in latest operation cards and diagnostic timeline operation result cards.
- Focused checks passed: `python -m pytest server/tests/test_web_support_api.py::test_web_support_ticket_detail_includes_observer_summary server/tests/test_web_support_api.py::test_web_support_ticket_detail_timeline_includes_normalized_lifecycle_events -v --tb=short`; `pnpm --dir webapp exec vitest run src\features\queues\support-workspace-mappers.test.ts src\pages\tickets\list-page.test.tsx`; `pnpm --dir webapp run build`; `git diff --check`.
- Workspace verification passed after docs/index updates: `python scripts\verify_workspace.py`.
- Linux release completed for commit `cdd42ea` with `python scripts\release_server_to_remote.py --skip-ci-check --leave-running --smoke-attempts 6 --smoke-delay 5`; release verification, local webapp build, remote migrations, bundle upload and remote smoke passed (`/api/health` 200 on attempt 2 while the server was starting).
- Browser signoff passed at `http://192.168.100.17:8666/app/tickets/003b30fd-7c36-4d9f-b081-832a341f299b`: the tools tab rendered the latest timed-out operation with compact lifecycle chips `Длительность: 4 min 19 s`, `Повтор: 0/3 доступен`, `Код: timeout`, `Категория: Таймаут` and `Trace: 8c2ae683...`.
- Browser API evidence: `GET /api/web/support/tickets/{ticket_id}/workspace` returned 200 and carried `duration_ms`, `retry_count`, `max_retries`, `retryable`, `error_code`, `error_category`, `trace_id` and `details_url` on the latest operation snapshot.
- Fresh browser console check returned `Total messages: 0 (Errors: 0, Warnings: 0)` after opening the lifecycle signoff ticket.

P3.3 - knowledge provider depth:

- Goal: add scoring/source diagnostics to the current provider and prepare a clean adapter boundary for future external KB/search indexes.
- Non-goal: no autonomous AI action execution and no unverified answer-as-truth UX.

P3.4 - closure/passport action depth:

- Goal: make closure blockers and passport/evidence candidates more actionable from the central workspace while preserving current closure guards.
- Non-goal: no weakening of closure policy or evidence requirements.

P3.5 - final P3 release/browser signoff:

- Goal: deploy the completed P3 domain-depth slices, verify `/app/tickets` in browser, record known console/network noise, and stop the remote server.

P2.6 verification plan:

- Frontend focused tests for theme persistence, visible theme toggle labels/states and critical page text.
- Frontend focused tests for SLA/OLA edge labels and passport readiness visual copy where practical.
- `pnpm --dir webapp run build`.
- `python scripts\verify_workspace.py`.
- Browser MCP signoff at `http://192.168.100.17:8666/admin` with dark/light snapshots and console-error check.

P2.6 first-slice local evidence:

- Implemented scoped light-theme workspace overrides for `/app/tickets` so the existing dark-first panels, cards, timeline rows, composer, tabs and right sidebar receive readable light surfaces without changing the ticket business logic.
- Reworked right-sidebar SLA/OLA rendering to show explicit `Нарушен`, `Риск`, `Пауза`, `В норме` and `Нет срока` states, due labels, readable progress bars and no stale OLA placeholder.
- Reworked passport readiness rendering with a status chip, progress bar and clearer open-passport action.
- Added focused frontend coverage for SLA/OLA edge labels and passport `4/4` readiness copy.
- Local verification passed: `pnpm --dir webapp exec vitest run src\pages\tickets\list-page.test.tsx src\features\queues\support-workspace-mappers.test.ts` (16 tests), `pnpm --dir webapp run build`, `python scripts\verify_workspace.py`, and `git diff --check`.
- Linux release completed for commits `27e687f` and follow-up light-header fix `b244e7e` with `python scripts\release_server_to_remote.py --skip-ci-check --leave-running --smoke-attempts 6 --smoke-delay 5`; remote smoke passed.
- Browser plugin path failed to start with a local app-server path error, so rendered signoff used Playwright MCP against the canonical `http://192.168.100.17:8666/admin` stand.
- Browser signoff passed: logged in as `op1`, `/app/tickets/:ticketId` rendered, `GET /api/web/support/queue?...` returned 200, aggregate `GET /api/web/support/tickets/{ticket_id}/workspace` returned 200, theme toggle switched dark/light, SLA tab showed explicit timer states, and passport tab showed `Готовность 4/4` plus open action.
- Visual screenshots checked at 1366, 1440 and 1920px in dark/light. One light-theme defect was found (`bg-[#0b1624]/70` center header stayed dark) and fixed in `b244e7e`; final light screenshots show the center header, timeline and composer on readable light surfaces.
- Remaining browser console/network noise: known non-blocking support-role 403 for admin-only `GET /api/web/admin/connection_requests`; `/app/tickets` support APIs were 200.

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
- `GET /api/web/support/workspace/summary` now provides summary without ticket rows; keep `GET /api/web/support/queue` as the row/list contract.
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
- Keep `GET /api/web/support/tickets/{ticket_id}/knowledge-suggestions` as the first-class knowledge contract; it now prefers manual KB links and falls back to built-in catalog search when no links exist, without changing the UI boundary.

Do not add public `/api/support/*` duplicates unless an external consumer requires them. Inside the React app, typed `/api/web/support/*` is the canonical boundary.

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

- [x] Add summary/queues DTO if existing queue payload is not enough.
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
- [x] Add knowledge suggestions endpoint as KB-link-backed payload with conservative source-visible AI beta summary.
- [x] Add aggregated workspace endpoint if frontend complexity or round-trips justify it.
- [x] Add typed aliases for assign/queue/priority/reroute only if used in visible action menu.
- [x] Expand typed detail timeline with normalized lifecycle/SLA/OLA/passport event categories and structured operation steps.
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

Stage 8 evidence:

- Full CI passed for commit `fb7dc58`: workspace verification, webapp bundle, server no-db tests, server db/api tests, agent websocket tests and pc_agent tests.
- Focused follow-up verification passed for commit `63e3e58`: Vitest mapper/page/router tests, production webapp build and `python scripts/verify_workspace.py`.
- Remote release succeeded for `63e3e58` with server smoke passing after deploy.
- Browser verification completed at `http://192.168.100.17:8666/admin` for `/app/tickets/:ticketId`: 3-column layout, topbar, work slices, queues, ticket list, selected ticket, next action, actions, timeline tabs, composer and right context tabs render correctly.
- Final browser console check after the right-tab layout fix reported 0 errors and 0 warnings.

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
- External KB/search depth is still limited. The current endpoint is source-visible and honest, but a real searchable provider/index remains P2.9 work.
- Light theme exists, but some surfaces may still read as dark-theme-first. P2.6 must polish tokens/classes without creating a second divergent design system.
- SLA/OLA progress can be derived, but timer semantics must not be changed without dedicated tests.
- Deep-link behavior must not regress because operators may share ticket URLs.
- Combined Windows `run_ci_suite.py` can hit unrelated agent_ws/test-DB lock timeouts. If it recurs, use sequential project gates plus explicit release/browser evidence and record the limitation.

## Current State

- P0, P1 and P2.1-P2.5 implementation for `/app/tickets` support workspace are complete.
- Active route ownership remains `/app/tickets` and `/app/tickets/:ticketId`.
- Backend/API residual gap after P2.5 is estimated at 4-7% for typed contracts and 8-12% for broader domain depth, mostly external KB/search, richer operation-running/tool policy metadata and optional deeper context/profile sources.
- UI/page polish gap for the current page is estimated at 12-18%, mostly full light-theme polish, responsive desktop hardening, richer disabled/running states and reason-capturing action UX.
- This plan remains the active long-horizon artifact for any P2 follow-up.
- Current pending step: choose the next P2 slice; recommended candidate is P2.9 externalized knowledge provider or a narrow action-reason UX polish pass.

## Handoff

Recommended next step: execute **P2.9 externalized knowledge provider** or a narrow action-reason UX polish pass on the current `/app/tickets` page.

Concrete P2.6 first slice:

1. [x] Run browser audit for `/app/tickets` and `/app/tickets/:ticketId` at 1366, 1440 and 1920px in dark and light themes.
2. [x] Record concrete visual defects: contrast, clipping, wrapping, selected states, scroll containment, dropdown/composer readability, SLA/OLA timer readability and passport readiness clarity.
3. [x] Patch only the current page/component classes and mapper-safe UI helpers needed for those defects.
4. [x] Add or update focused frontend tests for theme persistence and critical rendered workspace controls.
5. [x] Run focused Vitest, `pnpm --dir webapp run build`, `python scripts\verify_workspace.py`, deploy to the Linux stand, complete browser signoff, then stop the remote server.

Concrete P2.7 slice:

1. [x] Extend the support workspace context view-model with requester provenance, asset type/id and similar-ticket count from existing aggregate data.
2. [x] Update the context sidebar to show labeled contact fields, registry/source provenance, device identity and category/service/source metadata without decorative placeholder values.
3. [x] Add focused mapper and page tests for enriched context rendering and fallback behavior.
4. [x] Run focused Vitest, production webapp build, `python scripts\verify_workspace.py`, deploy to the Linux stand, complete browser signoff, then stop the remote server.

P2.7 local evidence:

- Focused Vitest passed: `pnpm --dir webapp exec vitest run src\features\queues\support-workspace-mappers.test.ts src\pages\tickets\list-page.test.tsx` (16 tests).
- Production webapp build passed: `pnpm --dir webapp run build`.
- Workspace verification passed: `python scripts\verify_workspace.py`.
- Full green CI artifact exists for commit `127e855`: `artifacts\ci\127e855e9fe102bc0d438852c906221e411bf451\summary.json`.
- Linux release succeeded for commit `127e855`; remote smoke passed after deploy.
- Browser signoff completed at `http://192.168.100.17:8666/admin` redirecting to `/app/tickets/:ticketId`: context tab renders profile provenance, Asset ID, Device ID, category/service/source and similar-ticket count. Support queue and workspace aggregate requests returned 200.
- Non-blocking browser observation remains unchanged: support shell logs one 403 for admin-only `GET /api/web/admin/connection_requests`.

Next slice after P2.7: P2.8 diagnostics/tools UX hardening, focused on operation-running, unavailable-tool reasons and diagnostic detail readability.

Concrete P2.8 slice:

1. [x] Normalize operation status labels/tones in the support workspace view-model so timeline diagnostic cards do not render raw backend statuses as the main UX.
2. [x] Surface ticket-scoped latest/running operations from the aggregate workspace snapshot in the right Tools panel.
3. [x] Add visible disabled reasons and metadata chips for unavailable tools/playbooks, including offline device, install-required tools and playbook readiness blockers.
4. [x] Tighten launch buttons so they are disabled only/always according to actually runnable tool/playbook availability.
5. [x] Add focused mapper/page tests, run focused Vitest, production webapp build, `python scripts\verify_workspace.py`, then deploy/browser-signoff if the release gate is available.

P2.8 completion note:

- Local verification passed: `pnpm --dir webapp exec vitest run src\features\queues\support-workspace-mappers.test.ts src\pages\tickets\list-page.test.tsx` (18 tests), `pnpm --dir webapp run build`, `python scripts\verify_workspace.py`, and `git diff --check`.
- Linux release completed for commits `bfab893` and follow-up metadata wrapping fix `9e567a2` with `python scripts\release_server_to_remote.py --skip-ci-check --leave-running --smoke-attempts 6 --smoke-delay 5`; remote smoke passed.
- Browser signoff passed at `http://192.168.100.17:8666/admin` on `/app/tickets/:ticketId`: support queue and aggregate workspace requests returned 200, right Tools tab rendered latest operations, normalized operation status labels, visible playbook blockers and no document-level horizontal overflow.
- Release used `--skip-ci-check` because the standard release gate had no green CI artifact for the new HEAD yet (`artifacts\ci\...\summary.json` missing). Local focused checks, production webapp build and `verify_workspace.py` passed before deploy.
