# Admin/Support Web Rearchitecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the legacy `/support` and `/admin` browser surfaces with a new typed React-based internal web platform and a new server-side web API boundary, without rewriting the core Python runtime stack.

**Architecture:** A single `webapp/` frontend project serves new `/app/support` and `/app/admin` routes. The Python server grows a new `/api/web/*` application layer with `Pydantic v2` DTOs, session-based auth, and a workspace-oriented realtime bridge while the existing runtime/domain layers remain intact.

**Tech Stack:** Node.js 24 LTS, Corepack, `pnpm`, React, TypeScript, Vite, React Router, TanStack Query, Vitest, Playwright, `aiohttp`, `Pydantic v2`, PostgreSQL, SQLAlchemy, existing release/deploy scripts.

---

### Task 1: Create Web Platform Foundation

**Files:**
- Create: `package.json`
- Create: `.node-version`
- Create: `.nvmrc`
- Create: `.npmrc`
- Create: `scripts/bootstrap_web_toolchain.py`
- Create: `webapp/package.json`
- Create: `webapp/pnpm-lock.yaml`
- Create: `webapp/tsconfig.json`
- Create: `webapp/vite.config.ts`
- Create: `webapp/index.html`
- Create: `webapp/src/main.tsx`
- Create: `webapp/src/app/router.tsx`
- Create: `webapp/src/app/providers/query-provider.tsx`
- Create: `webapp/src/app/layouts/app-shell.tsx`
- Create: `webapp/src/pages/support/index.tsx`
- Create: `webapp/src/pages/admin/index.tsx`
- Create: `webapp/src/shared/ui/*`
- Test: `webapp/src/app/router.test.tsx`

- [x] **Step 1: Bootstrap the canonical frontend toolchain**

Run:

```powershell
python scripts/bootstrap_web_toolchain.py
```

Expected:
- local/CI frontend work uses the pinned `Node.js 24 LTS + corepack + pnpm` toolchain
- `pnpm` is available before the first `webapp/` install/build

- [x] **Step 2: Scaffold the Vite/React/TypeScript workspace**

Run:

```powershell
New-Item -ItemType Directory -Force webapp, webapp\src, webapp\src\app, webapp\src\pages, webapp\src\shared
```

Expected:
- `webapp/` exists under the repo root.
- The workspace is ready for `pnpm install` and `pnpm build`.

- [x] **Step 3: Add canonical frontend package scripts**

Add scripts for:
- `dev`
- `build`
- `preview`
- `test`
- `lint` if introduced in the same wave

Expected:
- `pnpm --dir webapp build` produces a distributable bundle.
- `pnpm --dir webapp run test` is executable in CI/local environments.

- [x] **Step 4: Add base app shell and router**

Implement route groups:
- `/app/support`
- `/app/admin`

Expected:
- The app shell can render placeholder pages for both route groups.
- No business logic is wired yet; only platform structure exists.

- [x] **Step 5: Add the first frontend unit test**

Run:

```powershell
pnpm --dir webapp run test
```

Expected:
- at least one router/shell test passes

- [ ] **Step 6: Commit the foundation scaffold**

```bash
git add webapp
git commit -m "feat: scaffold admin/support web platform"
```

### Task 2: Introduce Server-Side Web API Boundary

**Files:**
- Create: `server/web_api/__init__.py`
- Create: `server/web_api/session_handlers.py`
- Create: `server/web_api/support_handlers.py`
- Create: `server/web_api/admin_handlers.py`
- Create: `server/web_api/realtime_handlers.py`
- Create: `server/web_api/dto/common.py`
- Create: `server/web_api/dto/session.py`
- Create: `server/web_api/dto/support.py`
- Create: `server/web_api/dto/admin.py`
- Modify: `server/routes.py`
- Test: `server/tests/test_web_session_api.py`
- Test: `server/tests/test_web_support_api.py`
- Test: `server/tests/test_web_admin_api.py`

- [x] **Step 1: Define the namespace and route registration**

Add route groups for:
- `/api/web/session/*`
- `/api/web/support/*`
- `/api/web/admin/*`
- `/api/web/realtime/*`

Expected:
- the new namespace is reachable without disturbing legacy handlers

- [x] **Step 2: Add shared DTO envelopes**

Create DTO patterns for:
- success responses
- list responses
- detail responses
- validation errors
- action results

Expected:
- new handlers return explicit typed models instead of ad-hoc dict shapes

- [x] **Step 3: Add first contract tests**

Run:

```powershell
python -m pytest server/tests/test_web_session_api.py server/tests/test_web_support_api.py server/tests/test_web_admin_api.py -v --tb=short
```

Expected:
- tests fail before handlers are implemented
- tests pass after minimal boundary implementation

- [ ] **Step 4: Commit the boundary skeleton**

```bash
git add server/web_api server/routes.py server/tests/test_web_session_api.py server/tests/test_web_support_api.py server/tests/test_web_admin_api.py
git commit -m "feat: add web api boundary skeleton"
```

### Task 3: Replace Web Auth With Session-Based Flow For New UI

**Files:**
- Modify: `server/auth/handlers.py`
- Modify: `server/auth/middleware.py`
- Create: `server/web_api/session_handlers.py`
- Create: `server/tests/test_web_session_api.py`
- Create: `webapp/src/features/auth/api.ts`
- Create: `webapp/src/features/auth/session-provider.tsx`
- Create: `webapp/src/features/auth/login-page.tsx`
- Test: `webapp/src/features/auth/session-provider.test.tsx`

- [x] **Step 1: Add new web session endpoints**

Required endpoints:
- login
- logout
- current session/me

Expected:
- new UI can authenticate without storing bearer tokens in `localStorage`

- [x] **Step 2: Keep legacy auth untouched for legacy screens**

Expected:
- `/support` and `/admin` legacy routes keep working during migration
- new `/app/*` routes use the new session flow

- [x] **Step 3: Wire frontend session bootstrap**

Expected:
- app shell blocks or redirects when session is missing
- successful login hydrates the new UI session model

- [x] **Step 4: Verify session contract**

Run:

```powershell
python -m pytest server/tests/test_web_session_api.py -v --tb=short
pnpm --dir webapp run test
```

Expected:
- backend session tests pass
- frontend auth/session tests pass

- [ ] **Step 5: Commit session auth**

```bash
git add server/auth server/web_api/session_handlers.py server/tests/test_web_session_api.py webapp/src/features/auth
git commit -m "feat: add session auth for new web ui"
```

### Task 4: Add Frontend Build Artifacts To CI And Release Flow

**Files:**
- Modify: `scripts/run_ci_suite.py`
- Modify: `scripts/release_server_to_remote.py`
- Modify: `scripts/deploy_workspace_to_remote.py` if artifact transport is handled there
- Create: `scripts/build_webapp_bundle.py` or equivalent helper
- Modify: `scripts/ci_artifacts.py`
- Modify: `scripts/verify_workspace.py`
- Test: `scripts/test_run_ci_suite.py`
- Test: `server/tests/test_static_pages_handlers.py` or new web asset serving tests

- [x] **Step 1: Add web dependency install/build to CI**

Run target command:

```powershell
pnpm --dir webapp install --frozen-lockfile
pnpm --dir webapp build
```

Expected:
- CI artifacts include built web assets for the target commit

- [x] **Step 2: Decide and implement artifact shipping**

Canonical release behavior must become:
- verify workspace
- build frontend bundle
- produce CI artifact
- deploy code
- upload/unpack bundle on Linux
- start server
- smoke

Expected:
- Linux deploy no longer depends on raw source-only serving for new app routes

- [x] **Step 3: Keep Linux runtime free from mandatory `pnpm` dependency**

Expected:
- remote host can serve the built UI without requiring `pnpm`
- remote Node presence is optional for fallback diagnostics only

- [x] **Step 4: Verify release automation locally**

Run:

```powershell
python scripts/verify_workspace.py
python scripts/run_ci_suite.py
```

Expected:
- CI summary marks the web build as green

- [ ] **Step 5: Commit release-flow changes**

```bash
git add scripts server/tests
git commit -m "feat: add web bundle to ci and release flow"
```

### Task 5: Serve New Frontend Assets From The Python Server

**Files:**
- Modify: `server/static_pages/handlers.py`
- Create: `server/static_pages/webapp_assets.py`
- Modify: `server/routes.py`
- Test: `server/tests/test_static_pages_handlers.py`

- [x] **Step 1: Add built asset serving for the new app**

New routes must serve:
- `/app/support`
- `/app/admin`
- required JS/CSS/static assets from the built bundle

Expected:
- the server can return the built SPA entry and asset files cleanly

- [x] **Step 2: Preserve legacy route behavior**

Expected:
- existing `/support` and `/admin` handlers remain untouched during coexistence

- [x] **Step 3: Verify static asset responses**

Run:

```powershell
python -m pytest server/tests/test_static_pages_handlers.py -v --tb=short
```

Expected:
- built asset serving tests pass

- [ ] **Step 4: Commit static serving support**

```bash
git add server/static_pages server/routes.py server/tests/test_static_pages_handlers.py
git commit -m "feat: serve new app bundle from aiohttp"
```

### Task 6: Build Support Workspace Wave 1

**Files:**
- Create: `webapp/src/features/queues/*`
- Create: `webapp/src/features/tickets/*`
- Create: `webapp/src/pages/support/*`
- Create: `webapp/playwright.config.ts`
- Create: `webapp/tests/fixtures/support_fixture_server.py`
- Create: `server/web_api/support_handlers.py`
- Create: `server/web_api/dto/support.py`
- Test: `server/tests/test_web_support_api.py`
- Test: `webapp/src/features/queues/*.test.tsx`
- Test: `webapp/src/features/tickets/*.test.tsx`
- Test: `webapp/tests/support-workspace.spec.ts`

- [x] **Step 1: Ship support shell, queue, and selection model**

Include:
- queue list
- filters
- ticket selection
- basic detail loading

Expected:
- operators can navigate the new support workspace without using legacy `/support`

- [x] **Step 2: Add ticket workspace behaviors inside support**

Include:
- message timeline
- snapshot data
- operator actions relevant to support

Expected:
- support users can work inside `/app/support` without needing `/ticket`

- [x] **Step 3: Add tool launch and observer surfaces**

Expected:
- critical support workflows exist in the new workspace

- [x] **Step 4: Verify support E2E**

Run:

```powershell
pnpm --dir webapp run test
pnpm --dir webapp run test:e2e -- tests/support-workspace.spec.ts
```

Expected:
- core support flows pass end-to-end

- [ ] **Step 5: Commit support workspace**

```bash
git add webapp/src/pages/support webapp/src/features/queues webapp/src/features/tickets server/web_api/support_handlers.py server/web_api/dto/support.py server/tests/test_web_support_api.py webapp/tests/support-workspace.spec.ts
git commit -m "feat: migrate support workspace to new web platform"
```

### Task 7: Build Admin Workspace Wave 1

**Files:**
- Create: `webapp/src/features/devices/*`
- Create: `webapp/src/features/agent-updates/*`
- Create: `webapp/src/features/modules/*`
- Create: `webapp/src/features/tech/*`
- Create: `webapp/src/features/forms-builder/*`
- Create: `webapp/src/pages/admin/*`
- Create: `server/web_api/admin_handlers.py`
- Create: `server/web_api/dto/admin.py`
- Test: `server/tests/test_web_admin_api.py`
- Test: `webapp/tests/admin-workspace.spec.ts`

- [x] **Step 1: Build devices and agent-updates first**

Expected:
- the new admin workspace can list devices, open device detail, and trigger/view update actions

- [ ] **Step 2: Add modules and tech panel**

Expected:
- high-value admin operational surfaces are available in the new app

Current progress:
- typed observer quick slice for `/app/admin` is now part of this step via `GET /api/web/admin/observer/quick` and `webapp/src/features/tech/*`; modules/forms builder still remain for later slices

- [x] **Step 3: Add forms-builder**

Expected:
- the new admin workspace covers the agreed internal authoring surfaces

- [ ] **Step 4: Verify admin E2E**

Run:

```powershell
pnpm --dir webapp exec playwright test webapp/tests/admin-workspace.spec.ts
python -m pytest server/tests/test_web_admin_api.py -v --tb=short
```

Expected:
- admin flows pass end-to-end and contract tests pass

- [ ] **Step 5: Commit admin workspace**

```bash
git add webapp/src/pages/admin webapp/src/features/devices webapp/src/features/agent-updates webapp/src/features/modules webapp/src/features/tech webapp/src/features/forms-builder server/web_api/admin_handlers.py server/web_api/dto/admin.py server/tests/test_web_admin_api.py webapp/tests/admin-workspace.spec.ts
git commit -m "feat: migrate admin workspace to new web platform"
```

### Task 8: Add Web Realtime Bridge

**Files:**
- Create: `server/web_api/realtime_handlers.py`
- Create: `webapp/src/shared/realtime/client.ts`
- Create: `webapp/src/shared/realtime/adapters/*`
- Test: `server/tests/test_web_realtime_api.py`
- Test: `webapp/src/shared/realtime/*.test.ts`

- [x] **Step 1: Define realtime contract for the new app**

Expected:
- React features consume a stable transport abstraction rather than raw ws details

- [x] **Step 2: Bridge queue/ticket/device/tech feeds**

Expected:
- support/admin pages update live without embedding legacy transport logic

- [x] **Step 3: Verify realtime contract**

Run:

```powershell
python -m pytest server/tests/test_web_realtime_api.py -v --tb=short
pnpm --dir webapp run test
```

Expected:
- realtime contract tests pass

- [ ] **Step 4: Commit realtime bridge**

```bash
git add server/web_api/realtime_handlers.py webapp/src/shared/realtime server/tests/test_web_realtime_api.py
git commit -m "feat: add web realtime bridge"
```

### Task 9: Run Remote Linux Validation For The New Stack

**Files:**
- Modify: `scripts/release_server_to_remote.py`
- Modify: `scripts/manage_remote_stack.py` only if the new release flow requires machine-readable checks
- Create: `docs/superpowers/specs/2026-04-20-admin-support-web-rearchitecture-design.md`
- Test: remote runtime via canonical scripts

- [ ] **Step 1: Verify local workspace**

Run:

```powershell
python scripts/bootstrap_web_toolchain.py
python scripts/verify_workspace.py
python scripts/run_ci_suite.py
```

Expected:
- local Python and web checks are green

- [ ] **Step 2: Release to Linux using canonical scripts**

Run:

```powershell
python scripts/release_server_to_remote.py
```

Expected:
- remote control-plane starts
- remote server starts
- smoke succeeds

- [ ] **Step 3: Browser-check the new app routes**

Verify:
- `http://192.168.100.17:8666/app/support`
- `http://192.168.100.17:8666/app/admin`

Expected:
- pages load without JS/runtime boot failures

- [ ] **Step 4: Stop the remote server when checks are complete**

Run:

```powershell
python scripts/manage_remote_stack.py stop server
```

Expected:
- remote server is not left running unless explicitly requested

- [ ] **Step 5: Commit remote rollout support**

```bash
git add scripts docs
git commit -m "chore: validate new web stack on linux release flow"
```

### Task 10: Cutover and Legacy Cleanup

**Files:**
- Modify: `server/static_pages/handlers.py`
- Modify: `server/routes.py`
- Delete later: legacy UI-only scripts after parity is confirmed
- Update: `docs/QUICK_LOOKUP.md`
- Update: `server/docs/CODEMAP.md`
- Update: `PLANS.md`

- [ ] **Step 1: Keep old and new routes in parallel during validation**

Expected:
- rollback path exists while adoption is still proving out

- [ ] **Step 2: Switch default internal entrypoints to new routes**

Expected:
- operator traffic defaults to `/app/support` and `/app/admin`

- [ ] **Step 3: Remove legacy UI code only after parity**

Expected:
- deletions happen after browser verification and release validation, not before

- [ ] **Step 4: Sync docs**

Run:

```powershell
python scripts/verify_workspace.py
```

Expected:
- docs and codemap stay aligned with the new canonical web structure

- [ ] **Step 5: Commit cutover**

```bash
git add server docs PLANS.md
git commit -m "feat: cut over admin/support to new web platform"
```

## Execution Notes

- `/ticket`, public queue pages, and public browser ticket flows are intentionally excluded from this first migration wave.
- The Linux host was validated on 2026-04-20 and can run the Python server stack cleanly, but canonical frontend build should remain local/CI-driven rather than depend on remote `pnpm`.
- The long-horizon coordination artifact for this work remains the repo-root `PLANS.md`.
- `webapp/` intentionally stays a standalone package for now; the repo does not need a root `pnpm-workspace.yaml` until a second frontend package appears.
