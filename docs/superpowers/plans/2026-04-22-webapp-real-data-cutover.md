# Webapp Real-Data Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace mock-backed `/app/*` surfaces with real support/admin/report/settings data while preserving the approved unified SaaS UI and keeping Knowledge Base as an in-development placeholder.

**Architecture:** Reuse the existing React shell and typed support/admin feature APIs where they already exist, and add two new typed web boundaries: one aggregate read endpoint for reports and one admin settings boundary that wraps the existing legacy admin-config domain. Keep the new page routes thin: page wrappers compose TanStack Query hooks, shared UI primitives, and existing feature panels instead of duplicating data logic.

**Tech Stack:** React 19, TypeScript, TanStack Query, Tailwind v4, aiohttp, Pydantic DTOs, existing ticket/admin repos and admin-config handlers.

---

### Task 1: Real support page wrappers

**Files:**
- Modify: `webapp/src/pages/tickets/list-page.tsx`
- Modify: `webapp/src/pages/tickets/detail-page.tsx`
- Modify: `webapp/src/features/queues/api.ts`
- Test: `webapp/tests/support-workspace.spec.ts`

- [ ] Replace mock ticket list state with real queue query, keeping the new list layout.
- [ ] Replace mock ticket detail state with real detail/tools/status/message actions.
- [ ] Keep input responsiveness with `useDeferredValue` / `startTransition` for queue filters and search.
- [ ] Extend or adjust support browser coverage for the new real wrappers.

### Task 2: Real admin page wrappers

**Files:**
- Modify: `webapp/src/pages/admin/inventory-page.tsx`
- Modify: `webapp/src/pages/admin/device-page.tsx`
- Modify: `webapp/src/pages/admin/modules-page.tsx`
- Modify: `webapp/src/pages/admin/forms-page.tsx`
- Modify: `webapp/src/pages/admin/observer-page.tsx`
- Modify: `webapp/src/features/admin/api.ts`
- Test: `webapp/tests/admin-workspace.spec.ts`

- [ ] Replace mock inventory/device pages with real data from the typed admin bootstrap/devices/update boundaries.
- [ ] Reuse `ModulesPanel`, `FormsBuilderPanel`, and `ObserverQuickPanel` instead of maintaining parallel mock UIs.
- [ ] Preserve the approved menu-first SaaS layout and align device/detail pages with real update and observer flows.
- [ ] Update browser coverage for the real admin wrappers.

### Task 3: Typed reports boundary and reports page

**Files:**
- Create: `server/web_api/dto/reports.py`
- Create: `server/web_api/reports_handlers.py`
- Modify: `server/routes.py`
- Modify: `server/docs/CODEMAP.md`
- Create: `webapp/src/features/reports/api.ts`
- Modify: `webapp/src/pages/reports/index.tsx`
- Test: `server/tests/test_web_reports_api.py`

- [ ] Add a typed web reports payload built from real ticket metrics repos/endpoints.
- [ ] Expose KPI, SLA, status, backlog, reopen and top-category/channel aggregates for the new reports page.
- [ ] Keep the frontend visual system intact while replacing all mock analytics data.
- [ ] Add focused server tests for the reports boundary.

### Task 4: Typed settings boundary and settings page

**Files:**
- Create: `server/web_api/dto/settings.py`
- Create: `server/web_api/settings_handlers.py`
- Modify: `server/routes.py`
- Modify: `server/docs/CODEMAP.md`
- Create: `webapp/src/features/settings/api.ts`
- Modify: `webapp/src/pages/settings/index.tsx`
- Modify: `webapp/src/app/navigation.tsx`
- Modify: `webapp/src/app/router.tsx`
- Modify: `webapp/src/features/auth/workspace-access.ts`
- Test: `server/tests/test_web_settings_api.py`

- [ ] Build a typed settings read/write boundary over queues, queue members, routing rules, SLA, calendars, OLA targets, resolution codes and audit.
- [ ] Use legacy `server/admin.js` settings sections as functional parity reference only.
- [ ] Align route access and navigation so the settings surface reflects real permissions instead of mock assumptions.
- [ ] Add focused server tests for the settings boundary.

### Task 5: Honest knowledge placeholder, verification, deploy

**Files:**
- Modify: `webapp/src/pages/knowledge/index.tsx`
- Modify: `PLANS.md`
- Modify: `server/docs/CODEMAP.md`
- Test: `python scripts/verify_workspace.py`, relevant `pytest`, `pnpm --dir webapp run test`, `pnpm --dir webapp run build`

- [ ] Replace the knowledge mock page with an explicit in-development state while keeping the nav item.
- [ ] Sync repo docs to the new reports/settings typed boundaries and real-backed route model.
- [ ] Run local verification, browser smoke, deploy to Linux, do live signoff, and stop the remote server unless the user asks to keep it running.
