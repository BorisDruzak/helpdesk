# Forms Builder UI Refactor Plan

## Goal

Make `/app/admin/forms` understandable for an administrator by separating catalog overview, template editing, policy editing, smart views, versions/publication, and process preview into distinct UI modes while preserving the existing backend APIs, legacy compatibility, and `request_forms` pack format.

## Scope

- Work only in `C:\Users\admin-2\CodexProjects\pc_client`.
- Change the React webapp UI and shell behavior for the forms builder route.
- Keep current endpoints:
  - `GET /api/web/admin/forms/current`
  - `POST /api/web/admin/forms/save`
  - `POST /api/web/admin/forms/save-draft`
  - `POST /api/web/admin/forms/validate`
  - `POST /api/web/admin/forms/publish`
  - `PATCH /api/web/admin/forms/preferred`
  - `POST /api/web/admin/forms/route-preview`
  - `POST /api/web/admin/forms/process-preview`
- Do not change backend DTOs, legacy pack behavior, `/help`, agent create wizard, or ticket creation runtime.

## Constraints

- The global app sidebar must default to collapsed on `/app/admin/forms`, with an explicit expand/collapse control.
- Other app routes must keep their existing sidebar behavior.
- Overview must not show all editors at once.
- Publication should be a release-management action in Versions/Publication mode, not a primary CTA on every editor section.
- Raw JSON and low-level refs stay available only in expert/advanced sections.
- Existing functions and compatibility paths remain in place unless they are only reorganized visually.

## Current State

- Current primary files:
  - `webapp/src/app/layouts/app-shell.tsx`
  - `webapp/src/components/shell/app-sidebar.tsx`
  - `webapp/src/pages/admin/forms-page.tsx`
  - `webapp/src/features/forms-builder/forms-builder-panel.tsx`
  - `webapp/src/features/forms-builder/api.ts`
- Backend already exposes draft, validation, publish, preferred, route preview, and process preview APIs.
- `forms-builder-panel.tsx` currently combines overview metrics, registry controls, policy editors, smart views, versions, template fields, advanced JSON, route preview, process preview, and publish controls in one screen.

## Decisions

- Treat the change as a frontend-local React webapp change; no backend contract changes are planned.
- Add route-aware collapse behavior to `AppShell`/`AppSidebar` instead of changing global navigation defaults.
- Implement internal mode navigation with query params, using:
  - `mode=overview`
  - `mode=template`
  - `mode=policy`
  - `mode=smart-views`
  - `mode=versions`
  - `mode=preview`
- Keep the existing single-page route and state model to avoid router churn.
- Keep existing API calls and mutations, but expose them through clearer screen-level CTAs.

## Implementation Steps

- [x] Run project intake and web toolchain bootstrap.
- [x] Rebuild stale context index.
- [x] Replace `PLANS.md` with this scoped UI refactor plan.
- [x] Add forms-builder route sidebar collapse support in the app shell/sidebar.
- [x] Add builder mode and complexity mode state synced with query params.
- [x] Replace the overloaded first screen with a catalog overview.
- [x] Move template editing into a focused editor layout with stepper, central editor, and right preview/context.
- [x] Group field process roles by priority, routing, diagnostics, approvals, closure, reporting/passport, and other.
- [x] Move policy editing into a focused policy mode and hide raw JSON under expert/advanced controls.
- [x] Move smart views into a focused smart-view mode with list, editor, preview, and checks.
- [x] Move versions and publication into a release-management mode.
- [x] Move process preview into a separate process simulation mode using the existing process-preview endpoint.
- [x] Ensure status chips, validation counts, draft state, and warning/error panels are visible in editor headers.
- [x] Run TypeScript/build and focused tests where practical.
- [ ] Verify `/app/admin/forms` manually in browser at `https://192.168.100.17:9443/app/admin/forms` after deploy/release if live verification is requested or feasible.

## Verification Plan

- [x] `python scripts/verify_workspace.py`
- [x] `pnpm --dir webapp run build`
- [x] `pnpm --dir webapp run test`
- [x] Focused Vitest checks during timeout triage:
  - `pnpm --dir webapp exec vitest run src/features/forms-builder/forms-builder-panel.test.tsx --reporter=dot`
  - `pnpm --dir webapp exec vitest run src/pages/admin/index.test.tsx --reporter=dot`
- [x] Browser check through MCP against local Vite with mocked admin/session/forms API:
  - opened `/app/admin/forms?mode=overview`
  - verified overview, template, policy, smart views, versions, and process preview modes render separately
  - verified process preview calls the existing preview client and renders computed queue/process details
- [ ] Browser check on `https://192.168.100.17:9443/app/admin/forms` after deploy/release if live verification is requested or feasible.

## Handoff

- Keep unrelated dirty worktree files unstaged and untouched.
- The remote server was not started or changed for this UI pass.
- The local Vite dev server used for browser QA was stopped after checks.
