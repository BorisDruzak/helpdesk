# Legacy UI removal implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the Helpdesk legacy browser shells while preserving their entry URLs as React redirects.

**Architecture:** `server/static_pages/handlers.py` becomes a minimal
redirect layer for retired entry routes, while `/app` remains served by the
existing React bundle handler. `server/routes.py` stops exposing all
legacy-shell assets and embedded workbenches. Tests assert the HTTP contract
instead of implementation text, and browser signoff accepts only React route
mode.

**Tech Stack:** Python 3.14, aiohttp, pytest, Vite/React, Playwright.

**Spec:** `docs/superpowers/specs/2026-08-31-legacy-ui-removal-design.md`

## Global Constraints

- Preserve `/login`, `/admin`, `/support`, `/help`, `/ticket.html`, and
  `/ticket/{ticket_id}` as redirects into `/app/*`.
- Strip only the retired `legacy` and `_shell` query keys; preserve all other
  query keys and ticket identifiers.
- Do not alter ticket, queue, API, database, protocol, agent, or technical
  debug-page behaviour.
- Update route/auth/CODEMAP documentation in the same change.

---

### Task 1: Establish retired-route contract tests

**Files:**
- Modify: `server/tests/test_static_pages_handlers.py`
- Test: `server/tests/test_static_pages_handlers.py`

**Interfaces:**
- Consumes: existing `handle_login_page`, `handle_admin_page`,
  `handle_support_page`, `handle_help_page`, `handle_ticket_page`, and
  `handle_ticket_page_by_id` handlers.
- Produces: a test contract for permanent `/app/*` redirects and query
  normalization.

- [x] **Step 1: Write failing tests for a retired legacy escape.**

```python
with pytest.raises(web.HTTPPermanentRedirect) as exc_info:
    await handle_admin_page(make_mocked_request("GET", "/admin?legacy=1&_shell=old&tab=queue"))

assert exc_info.value.location == "/app/admin?tab=queue"
```

- [x] **Step 2: Run the focused test and verify it fails because the current
  handler serves the shell.**

Run: `python -m pytest server/tests/test_static_pages_handlers.py -q --tb=short`

Expected: failure showing a legacy-shell location or response rather than
`/app/admin?tab=queue`.

- [x] **Step 3: Add equivalent tests for login, support, help and both ticket
  routes.**

```python
assert exc_info.value.location == "/app/ticket/T-100?code=A1B2C3"
```

- [x] **Step 4: Run the file again and verify each new contract case fails.**

Run: `python -m pytest server/tests/test_static_pages_handlers.py -q --tb=short`

- [ ] **Step 5: Commit after the implementation task passes.**

### Task 2: Remove fallback implementation and static assets

**Files:**
- Modify: `server/static_pages/handlers.py`, `server/routes.py`,
  `server/config.py`, `server/static_pages/cutover.py`
- Delete: `server/admin.*`, `server/support.*`, `server/login.*`,
  `server/help.*`, `server/ticket.*`, `server/web_shared.js`,
  `server/admin_modules_workbench.*`, `server/admin_ticket_forms_builder.*`
- Test: `server/tests/test_static_pages_handlers.py`

**Interfaces:**
- Consumes: aiohttp `web.HTTPPermanentRedirect` and `request.rel_url`.
- Produces: a query-preserving redirect handler for every retired entry route;
  no registered handlers for legacy shell assets.

- [ ] **Step 1: Implement a minimal redirect helper that replaces the removed
  cutover and versioning helpers.**

```python
def _retired_shell_redirect(request: web.Request, target_path: str) -> web.HTTPPermanentRedirect:
    query = {key: value for key, value in request.query.items() if key not in {"legacy", "_shell"}}
    return web.HTTPPermanentRedirect(location=str(request.rel_url.with_path(target_path).with_query(query)))
```

- [x] **Step 2: Change each entry handler to raise the redirect and remove
  legacy asset handlers and route imports/registrations.**

- [x] **Step 3: Delete only the 20 assets named in the design scope.**

- [x] **Step 4: Run focused tests and verify green.**

Run: `python -m pytest server/tests/test_static_pages_handlers.py -q --tb=short`

- [ ] **Step 5: Commit after documentation and signoff updates.**

### Task 3: Make validation and documentation React-only

**Files:**
- Modify: `webapp/scripts/remote-browser-signoff.mjs`,
  `docs/WEBAPP_CUTOVER_CHECKLIST.md`, `docs/LOCAL_WORKFLOW.md`,
  `server/docs/SECURITY_AND_AUTH.md`, `server/docs/CODEMAP.md`,
  `docs/ARCHITECTURE_BOUNDARIES.md`, `server/docs/REQUEST_FORM_BUILDER.md`
- Test: `webapp/scripts/remote-browser-signoff.mjs`

**Interfaces:**
- Consumes: the unconditional redirects from Task 2.
- Produces: signoff that requires React redirects for legacy entry URLs,
  including legacy-query variants, and current documentation.

- [x] **Step 1: Make the remote signoff require `/app/*` for every former
  legacy URL; include a `?legacy=1` variant whose expected location has no
  retired query keys.**

```javascript
{ path: "/admin?legacy=1", expectedLocation: "/app/admin" }
```

- [x] **Step 2: Update the removal and fallback documentation to describe the
  unconditional redirect contract and remove obsolete asset ownership claims.**

- [ ] **Step 3: Run static-page tests, webapp tests/build, workspace verifier,
  and browser signoff.**

```powershell
python -m pytest server/tests/test_static_pages_handlers.py -q --tb=short
pnpm --dir webapp run test -- --run src/app/router.test.tsx
pnpm --dir webapp run build
python scripts/verify_workspace.py
```

- [ ] **Step 4: Inspect the complete diff, run `git diff --check`, and commit
  only the legacy-removal files.**
