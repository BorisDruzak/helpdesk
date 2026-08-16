# Webapp Unification And API Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the new React web stack by reducing bundle risk, moving requester/ticket legacy pages into `/app/*`, and making React depend on typed `/api/web/*` contracts wherever practical.

**Architecture:** Keep the current Vite/React app as the canonical operator UI. Legacy pages remain available behind `?legacy=1` until browser signoff proves the React replacements cover the workflows. Server-side aiohttp keeps serving SPA assets through `server/static_pages/webapp_assets.py`, while `server/web_api/*` becomes the stable typed boundary for React.

**Tech Stack:** React 19, TypeScript, Vite 8, React Router 7, React Query, aiohttp, pytest, Vitest, Playwright.

---

## File Structure

- Modify `webapp/src/app/router.tsx`: add lazy route loading and new `/app/help` and requester ticket routes.
- Modify `webapp/src/app/navigation.tsx`: add navigation entries only where the role/session should expose them.
- Modify `webapp/src/main.tsx`: keep router bootstrap unchanged unless lazy route boundaries need a root fallback.
- Create `webapp/src/app/routes/lazy-pages.tsx`: central lazy imports for large workspace pages.
- Create `webapp/src/pages/help/index.tsx`: React requester ticket creation and ticket-code entry page.
- Create `webapp/src/pages/requester-ticket/index.tsx`: React requester ticket view/chat page.
- Create `webapp/src/features/requester/api.ts`: typed client for public/requester ticket APIs.
- Create `webapp/src/features/requester/types.ts`: narrow DTOs for requester pages.
- Modify `server/static_pages/handlers.py`: add optional cutover for `/help` and `/ticket/{ticket_id}` after React pages land.
- Modify `server/static_pages/cutover.py`: represent requester cutover state separately from admin/support/login.
- Modify `server/config.py`: add `WEBAPP_CUTOVER_HELP_ENABLED` and `WEBAPP_CUTOVER_TICKET_ENABLED`, default off until signoff.
- Modify `server/routes.py`: add any needed typed requester aliases and wire new cutover handlers.
- Modify `server/web_api/`: add requester-facing typed aliases only if public APIs are too raw for React.
- Modify `webapp/scripts/remote-browser-signoff.mjs`: add checks for lazy chunks and requester routes once cutover is enabled.
- Modify tests:
  - `webapp/src/app/router.test.tsx`
  - `webapp/src/pages/admin/index.test.tsx`
  - new `webapp/src/pages/help/index.test.tsx`
  - new `webapp/src/pages/requester-ticket/index.test.tsx`
  - `server/tests/test_static_pages_handlers.py`
  - targeted API tests for any new `server/web_api` requester handlers.
- Update docs:
  - `server/docs/CODEMAP.md`
  - `server/docs/SECURITY_AND_AUTH.md`
  - `docs/WEBAPP_CUTOVER_CHECKLIST.md`

---

## Phase 1: Split The React Bundle

### Task 1: Add Lazy Route Boundaries

**Files:**
- Modify: `webapp/src/app/router.tsx`
- Create: `webapp/src/app/routes/lazy-pages.tsx`
- Test: `webapp/src/app/router.test.tsx`

- [ ] **Step 1: Add a router test proving `/app/admin/playbooks` and `/app/admin/observer` still render through lazy pages**

Run: `pnpm --dir webapp exec vitest run src/app/router.test.tsx`

Expected before implementation: the test fails if the lazy route is not wired or fallback never resolves.

- [ ] **Step 2: Create lazy page exports**

Implementation shape:

```tsx
import { lazy } from "react";

export const TicketListPage = lazy(() =>
  import("../../pages/tickets/list-page").then((module) => ({ default: module.TicketListPage })),
);
export const TicketDetailPage = lazy(() =>
  import("../../pages/tickets/detail-page").then((module) => ({ default: module.TicketDetailPage })),
);
export const ReportsPage = lazy(() =>
  import("../../pages/reports").then((module) => ({ default: module.ReportsPage })),
);
export const SettingsPage = lazy(() =>
  import("../../pages/settings").then((module) => ({ default: module.SettingsPage })),
);
export const AdminInventoryPage = lazy(() =>
  import("../../pages/admin/inventory-page").then((module) => ({ default: module.AdminInventoryPage })),
);
export const AdminModulesPage = lazy(() =>
  import("../../pages/admin/modules-page").then((module) => ({ default: module.AdminModulesPage })),
);
export const AdminPlaybooksPage = lazy(() =>
  import("../../pages/admin/playbooks-page").then((module) => ({ default: module.AdminPlaybooksPage })),
);
export const AdminObserverPage = lazy(() =>
  import("../../pages/admin/observer-page").then((module) => ({ default: module.AdminObserverPage })),
);
```

- [ ] **Step 3: Wrap protected route outlet in `Suspense`**

Implementation shape in `ProtectedWorkspaceLayout`:

```tsx
import { Suspense } from "react";

function WorkspaceFallback() {
  return <SessionState title="Загружаем рабочую область" description="Подгружаем нужный раздел интерфейса." />;
}

return (
  <AppShell>
    <Suspense fallback={<WorkspaceFallback />}>
      <Outlet />
    </Suspense>
  </AppShell>
);
```

- [ ] **Step 4: Run focused and full frontend checks**

Run:

```powershell
pnpm --dir webapp exec vitest run src/app/router.test.tsx
pnpm --dir webapp run test
pnpm --dir webapp run build
```

Expected: tests pass and Vite build emits several route chunks instead of one dominant `index-*.js` bundle. If one chunk remains above 500 kB, split `modules`, `settings`, and `observer` panels next.

### Task 2: Split Heavy Feature Panels Inside Admin

**Files:**
- Modify: `webapp/src/pages/admin/index.tsx`
- Modify: `webapp/src/pages/admin/modules-page.tsx`
- Modify: `webapp/src/pages/admin/observer-page.tsx`
- Modify: `webapp/src/features/modules/modules-panel.tsx` only if route splitting is not enough.

- [ ] **Step 1: Measure bundle output after Task 1**

Run: `pnpm --dir webapp run build`

Expected: each chunk is small enough or the remaining warning identifies the heavy module.

- [ ] **Step 2: Lazy-load nested admin panels only when their tab/page is opened**

Implementation shape:

```tsx
const ModulesPanel = lazy(() =>
  import("../../features/modules/modules-panel").then((module) => ({ default: module.ModulesPanel })),
);
```

- [ ] **Step 3: Keep fallbacks operational, not decorative**

Fallback copy should be concrete:

```tsx
<div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-5 py-8 text-sm text-slate-500">
  Загружаем реестр модулей и проверки публикации.
</div>
```

- [ ] **Step 4: Verify**

Run:

```powershell
pnpm --dir webapp run test
pnpm --dir webapp run build
python scripts/check_webapp_cutover.py --json
```

Expected: frontend tests pass, cutover remains active, build warning is gone or documented with the exact remaining chunk and owner.

---

## Phase 2: Move `/help` And `/ticket` To React

### Task 3: Build Typed Requester API Client

**Files:**
- Create: `webapp/src/features/requester/types.ts`
- Create: `webapp/src/features/requester/api.ts`
- Test: `webapp/src/features/requester/api.test.ts`

- [ ] **Step 1: Define DTOs from existing public APIs**

Required DTOs:

```ts
export type RequestFormPack = {
  pack_key: string;
  version: string;
  forms: Array<{
    form_key: string;
    title: string;
    description?: string | null;
    fields: RequestFormField[];
  }>;
};

export type RequestFormField = {
  key: string;
  label: string;
  type: "text" | "textarea" | "select" | "checkbox" | "number" | "date";
  required?: boolean;
  placeholder?: string | null;
  options?: Array<{ value: string; label: string }>;
};

export type CreateTicketResponse = {
  ticket_id: string;
  public_code?: string | null;
  status: string;
};
```

- [ ] **Step 2: Implement API wrappers**

Use existing endpoints first:

```ts
export async function fetchPublicFormPack(): Promise<RequestFormPack> {
  const response = await fetch("/public_api/ticket_forms/current", { credentials: "same-origin" });
  return readJsonResponse<RequestFormPack>(response, "Не удалось загрузить форму заявки.");
}

export async function createPublicTicket(payload: unknown): Promise<CreateTicketResponse> {
  const response = await fetch("/public_api/tickets/create", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJsonResponse<CreateTicketResponse>(response, "Не удалось создать заявку.");
}
```

- [ ] **Step 3: Verify malformed responses fail predictably**

Run: `pnpm --dir webapp exec vitest run src/features/requester/api.test.ts`

Expected: API tests cover success, non-JSON, and server error payloads.

### Task 4: Implement React `/app/help`

**Files:**
- Create: `webapp/src/pages/help/index.tsx`
- Modify: `webapp/src/app/router.tsx`
- Test: `webapp/src/pages/help/index.test.tsx`

- [ ] **Step 1: Add tests for requester workflows**

Scenarios:
- form pack loads;
- required fields block submit;
- successful submit shows ticket code and link;
- existing ticket code entry navigates to requester ticket view.

- [ ] **Step 2: Build the page with real form pack data**

The page should not be a landing page. First screen is the actual request form plus compact ticket-code entry.

- [ ] **Step 3: Route `/app/help`**

Add a public route outside `ProtectedWorkspaceLayout` so requester pages do not require admin/support session.

- [ ] **Step 4: Verify**

Run:

```powershell
pnpm --dir webapp exec vitest run src/pages/help/index.test.tsx src/app/router.test.tsx
pnpm --dir webapp run test
```

### Task 5: Implement React Requester Ticket View

**Files:**
- Create: `webapp/src/pages/requester-ticket/index.tsx`
- Modify: `webapp/src/app/router.tsx`
- Test: `webapp/src/pages/requester-ticket/index.test.tsx`

- [ ] **Step 1: Map existing legacy `/ticket` behavior**

Use `server/ticket.js` as behavior source for:
- authorization by public code;
- message list;
- send message;
- attachments if already supported by API;
- resolution confirmation if available.

- [ ] **Step 2: Add React route**

Target routes:

```tsx
{ path: "ticket/:ticketId", element: <RequesterTicketPage /> }
{ path: "ticket", element: <RequesterTicketPage /> }
```

- [ ] **Step 3: Implement chat-first ticket view**

Keep the page focused: ticket status, latest messages, compose box, requester identity state, and resolution confirmation.

- [ ] **Step 4: Verify**

Run:

```powershell
pnpm --dir webapp exec vitest run src/pages/requester-ticket/index.test.tsx
pnpm --dir webapp run test
```

### Task 6: Add Controlled Cutover For `/help` And `/ticket`

**Files:**
- Modify: `server/config.py`
- Modify: `server/static_pages/cutover.py`
- Modify: `server/static_pages/handlers.py`
- Modify: `server/routes.py`
- Test: `server/tests/test_static_pages_handlers.py`

- [ ] **Step 1: Add cutover flags defaulting to false**

Implementation shape:

```python
WEBAPP_CUTOVER_HELP_ENABLED = os.getenv("WEBAPP_CUTOVER_HELP_ENABLED", "false").lower() == "true"
WEBAPP_CUTOVER_TICKET_ENABLED = os.getenv("WEBAPP_CUTOVER_TICKET_ENABLED", "false").lower() == "true"
```

- [ ] **Step 2: Extend cutover state**

Add `help` and `ticket` route states. `help` target is `/app/help`; ticket target preserves the ticket id as `/app/ticket/{ticket_id}`.

- [ ] **Step 3: Keep legacy escape**

`/help?legacy=1` and `/ticket/{ticket_id}?legacy=1` must still serve legacy HTML.

- [ ] **Step 4: Verify**

Run:

```powershell
python -m pytest server/tests/test_static_pages_handlers.py -q
python scripts/check_webapp_cutover.py --json
```

Expected: admin/support/login remain active; help/ticket report requested/active only when their flags are enabled.

---

## Phase 3: Normalize React API Boundary

### Task 7: Inventory Non-`/api/web/*` Calls From React

**Files:**
- Modify: `docs/WEBAPP_CUTOVER_CHECKLIST.md`

- [ ] **Step 1: Produce current API inventory**

Run:

```powershell
rg "fetch\\(" webapp/src -n
rg "\"/api/(?!web)" webapp/src -n
```

Classify each non-web endpoint as:
- `keep`: public endpoint intentionally shared with requester UI;
- `alias`: should get typed `/api/web/*` wrapper;
- `legacy`: should disappear after migration.

- [ ] **Step 2: Document the matrix**

Add a short table to `docs/WEBAPP_CUTOVER_CHECKLIST.md` with owner, endpoint, decision, and target route.

### Task 8: Add Typed Web Aliases For Observer And Notifications

**Files:**
- Modify: `server/web_api/admin_handlers.py`
- Modify: `server/web_api/settings_handlers.py` or create `server/web_api/notification_handlers.py`
- Modify: `server/routes.py`
- Modify: `webapp/src/features/tech/observer-workbench-api.ts`
- Modify: `webapp/src/components/shell/app-topbar.tsx`
- Test:
  - `server/tests/test_web_admin_api.py`
  - `webapp/src/features/tech/observer-workbench-api.test.ts`

- [ ] **Step 1: Add `/api/web/admin/observer/*` wrappers for all observer calls used by React**

Targets:
- trace detail;
- diagnostics bundle;
- runtime;
- settings;
- signatures;
- degradations;
- rebuild.

- [ ] **Step 2: Move React observer client to web endpoints**

For example:

```ts
const response = await fetch(`/api/web/admin/observer/traces/${encodeURIComponent(traceId)}${query}`, {
  credentials: "same-origin",
});
```

- [ ] **Step 3: Add typed notification aliases**

Targets:
- unread count;
- list notifications;
- preferences.

- [ ] **Step 4: Verify**

Run:

```powershell
python -m pytest server/tests/test_web_admin_api.py -q
pnpm --dir webapp exec vitest run src/features/tech/observer-workbench-api.test.ts
pnpm --dir webapp run test
```

### Task 9: Add Typed Web Aliases For Modules Workbench

**Files:**
- Modify: `server/web_api/admin_handlers.py`
- Modify: `server/routes.py`
- Modify: `webapp/src/features/modules/workbench-api.ts`
- Test:
  - `server/tests/test_web_admin_api.py`
  - module webapp tests if present.

- [ ] **Step 1: Add aliases under `/api/web/admin/modules/workbench/*`**

Map current endpoints without changing backend service behavior:
- `/api/modules/workbench`
- `/api/modules/workbench/{module_name}`
- `/api/modules/authoring/validate`
- `/api/modules/authoring/publish`
- `/api/modules/upload`
- live test candidate/run endpoints.

- [ ] **Step 2: Move React module workbench client to aliases**

Keep legacy endpoints working for compatibility.

- [ ] **Step 3: Verify**

Run:

```powershell
python -m pytest server/tests/test_web_admin_api.py server/tests/test_module_observer_contract_no_db.py -q
pnpm --dir webapp run test
```

---

## Phase 4: Live Signoff And Release

### Task 10: Browser Signoff

**Files:**
- Modify: `webapp/scripts/remote-browser-signoff.mjs`
- Test: `webapp/tests/admin-workspace.spec.ts`

- [ ] **Step 1: Add signoff checks**

Required checks:
- `/admin` redirects to `/app/admin/inventory`;
- `/support` redirects to `/app/tickets`;
- `/login` redirects to `/app/login`;
- `/app/admin/observer` opens trace detail;
- `/app/admin/playbooks` opens canvas;
- `/app/help` creates or validates a form flow in fixture mode;
- `/app/ticket/:ticketId` opens requester ticket fixture.

- [ ] **Step 2: Run local verification**

Run:

```powershell
python scripts/verify_workspace.py
pnpm --dir webapp run test
pnpm --dir webapp run build
python -m pytest server/tests/test_static_pages_handlers.py server/tests/test_web_admin_api.py -q
```

- [ ] **Step 3: Release to stand and live check**

Run:

```powershell
python scripts/release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running
pnpm --dir webapp run check:remote:webapp -- --base-url http://192.168.100.17:8666
python scripts/manage_remote_stack.py stop server
```

Expected: remote browser signoff passes; server is stopped after checks unless the user explicitly asks to leave it running.

---

## Commit Strategy

1. Commit Phase 1 separately: `perf(webapp): split workspace routes`.
2. Commit Phase 2 separately: `feat(webapp): add requester react pages`.
3. Commit Phase 3 separately: `refactor(webapp): route react clients through web api`.
4. Commit Phase 4/docs separately if needed: `docs: update webapp cutover plan`.

---

## Risks And Guards

- Public requester flows must not require web-session cookies.
- Legacy escape must remain for `/help` and `/ticket` until live signoff passes.
- Do not remove old `/api/admin/*`, `/api/modules/*`, or public APIs during this plan; add aliases first, then migrate callers.
- Bundle splitting must not hide runtime errors behind lazy fallbacks; tests must wait for loaded content.
- If React requester pages need an API shape that public endpoints cannot safely provide, add `/api/web/requester/*` aliases instead of contorting frontend code around raw legacy payloads.

---

## Current Execution State

- [x] Phase 1: route-level lazy imports are implemented in `webapp/src/app/routes/lazy-pages.tsx` and wired through `webapp/src/app/router.tsx`.
- [x] Phase 2: requester React pages are implemented at `/app/help`, `/app/ticket` and `/app/ticket/:ticketId`; `/help` and `/ticket` cutover flags default off.
- [x] Phase 3: React observer, notification, tech alert and module workbench clients use typed web aliases under `/api/web/*`; legacy backend endpoints remain available.
- [ ] Phase 4: remote browser signoff and release to Linux stand.

## Verification Checklist

- [ ] `python scripts/bootstrap_web_toolchain.py`
- [ ] `pnpm --dir webapp run test`
- [ ] `pnpm --dir webapp run build`
- [ ] `python -m pytest server/tests/test_static_pages_handlers.py -q`
- [ ] `python -m pytest server/tests/test_web_admin_api.py -q`
- [ ] `python scripts/check_webapp_cutover.py --json`
- [ ] `python scripts/verify_workspace.py`
- [ ] `pnpm --dir webapp run check:remote:webapp -- --base-url http://192.168.100.17:8666`
