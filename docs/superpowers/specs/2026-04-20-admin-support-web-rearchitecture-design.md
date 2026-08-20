# Admin/Support Web Rearchitecture Design

**Date:** 2026-04-20

**Status:** Approved for planning

## Goal

Replace the legacy browser implementation for `/support` and `/admin` with a new typed web platform while keeping the existing Python server/runtime core (`aiohttp`, WebSocket/outbox, PostgreSQL, SQLAlchemy, agent protocol, observer) intact.

The first wave must produce:

- a new frontend foundation for internal operator workspaces;
- a new server-side web-facing API boundary for those workspaces;
- a migration path that allows old and new UIs to coexist;
- a release/deploy story that works on the current Linux host.

## Scope

### In Scope

- `/support` migration to the new web stack.
- `/admin` migration to the new web stack.
- New web-specific backend namespace and DTO contracts.
- New session/auth approach for the new UI.
- New frontend build/test/release pipeline.
- Parallel rollout with old and new routes.

### Explicitly Out of Scope

- `/ticket`
- public queue pages
- public browser ticket page
- agent desktop UI rewrite
- WebSocket protocol rewrite
- replacing `aiohttp`, `PostgreSQL`, or `SQLAlchemy`

## Current Problems

The current internal web surfaces are expensive to change because UI and backend are coupled through large manual JavaScript files and ad-hoc JSON contracts.

Observed hotspots:

- `server/admin.js` is a very large monolith with heavy DOM logic, many `fetch()` calls, and a wide implicit contract surface.
- `server/support.js` and `server/ticket.js` continue the same pattern.
- `server/static_pages/handlers.py` serves raw HTML/JS/CSS directly, with no build pipeline or typed integration layer.
- Server handlers such as `server/tickets/handlers.py`, `server/modules/handlers.py`, `server/tech/handlers.py`, and `server/tools/handlers.py` perform large amounts of manual request validation and response assembly tailored to legacy UI consumers.

The result is not primarily "old technology"; it is high contract drift risk and a high cost per feature change.

## Architectural Decisions

### 1. Frontend Stack

The new internal web layer will use:

- React
- TypeScript
- Vite
- React Router
- TanStack Query
- Vitest
- Playwright
- `pnpm` as the canonical package manager

This stack is selected because it directly addresses the current pain:

- React gives us component boundaries instead of page-long imperative DOM scripts.
- TypeScript gives us explicit UI-side contracts and catches response-shape drift early.
- Vite gives us a simple static build pipeline without forcing SSR or a second runtime framework.
- TanStack Query cleanly separates server-state from component-state.
- Playwright gives us stable browser verification for operator flows.

### 2. Frontend App Shape

We will use **one** frontend project, not two separate apps.

Reason:

- `/support` and `/admin` share auth, shell layout, routing patterns, typed client, realtime transport, and domain primitives such as tickets/devices/modules/tech.
- Splitting into two physical apps would duplicate infrastructure and create two divergent UI platforms too early.

Proposed structure:

```text
webapp/
  src/app/
    router/
    providers/
    layouts/
  src/pages/
    support/
    admin/
  src/features/
    auth/
    queues/
    tickets/
    devices/
    modules/
    agent-updates/
    tech/
    forms-builder/
  src/entities/
    ticket/
    device/
    module/
    operator/
  src/shared/
    api/
    realtime/
    session/
    ui/
    lib/
    config/
```

### 3. Backend Boundary

The current domain/runtime backend remains the system core. A new web-facing application layer is added on top.

Canonical namespace:

- `/api/web/session/*`
- `/api/web/support/*`
- `/api/web/admin/*`
- `/api/web/realtime/*`

This new boundary is responsible for:

- stable DTO contracts for the new UI;
- request validation through explicit models;
- aggregating existing domain services into workspace-oriented responses;
- hiding legacy response shapes from the new frontend;
- enforcing web auth/session rules cleanly.

Legacy endpoints remain during migration, but they are not the source of truth for the new UI.

### 4. Contracts and Schema

The new web boundary will use:

- `Pydantic v2` request/response models;
- explicit web DTO modules;
- OpenAPI for the new namespace;
- generated or strictly typed frontend API client.

New frontend code must not use scattered raw `fetch()` calls directly against arbitrary server routes. All web calls go through a single typed API layer.

### 5. Auth and Session

The new internal UI will move away from bearer tokens in `localStorage`.

Target model:

- login endpoint issues an `httpOnly` session cookie;
- frontend reads current identity from `/api/web/session/me`;
- backend resolves `AuthContext` from the session;
- logout invalidates the session server-side.

This is preferable because it reduces token exposure, simplifies client lifecycle logic, and gives the server a single source of truth for web auth state.

Legacy auth remains only for legacy routes during the coexistence window.

### 6. Realtime Layer

The React UI must not know transport details such as current `ws_ui` message shapes, catch-up semantics, or transport fallback rules.

We will introduce a client-side realtime adapter with domain methods such as:

- `subscribeSupportQueue(...)`
- `subscribeTicketStream(...)`
- `subscribeDeviceFeed(...)`
- `subscribeTechFeed(...)`

Server-side transport details remain behind `/api/web/realtime/*` and/or a dedicated web transport bridge.

This keeps React features stable even if transport internals evolve.

### 7. UI Foundation

We will create a minimal shared internal design system immediately, but we will not spend the first wave on cosmetic redesign for its own sake.

Required UI primitives:

- shell layout
- workspace sidebar/topbar
- filters and search bars
- data table primitives
- detail drawers/panels
- empty/loading/error states
- async action buttons
- confirm dialogs
- status badges/chips
- forms and validation feedback
- toasts/notifications

The objective is consistency and implementation speed, not branding polish.

### 8. Rollout Model

Rollout will use **parallel old/new routes**.

Recommended temporary route model:

- legacy `/support`, new `/app/support`
- legacy `/admin`, new `/app/admin`

After validation:

- default entry switches to the new routes;
- legacy routes remain as a rollback surface for one compatibility window;
- legacy UI code is removed only after workspace parity and stable release verification.

### 9. Migration Order

Migration order is fixed as:

1. platform foundation
2. `/support`
3. `/admin`
4. cutover and cleanup

Within `/support`, the recommended order is:

1. workspace shell and queue
2. ticket list and selection
3. ticket workspace
4. messaging/actions
5. tool launch surface
6. observer/trace surfaces

Within `/admin`, the recommended order is:

1. devices
2. agent updates
3. modules
4. tech panel
5. forms builder
6. users/RBAC

This sequence minimizes risk and validates the platform first on the more focused operator workspace.

## Build, Release, and Deploy Design

### Canonical Build Strategy

The new frontend will be built **before deploy**, not rendered ad hoc from raw source files on the Linux host at request time.

Target approach:

- local/CI frontend toolchain uses `Node.js 24 LTS + corepack + pnpm`;
- `pnpm` is canonical locally and in CI.
- CI/local build produces static frontend assets.
- release flow uploads or synchronizes the built assets as part of deploy.
- the Python server serves the built assets.

Why this is preferred:

- production runtime does not depend on a live Node toolchain;
- deploys become deterministic;
- asset verification can happen before server restart;
- the Linux host stays a runtime host, not the primary build host.

### Release Pipeline Changes Required

Current deploy flow is Git-only plus Python verification/restart. To support the new web layer, release automation must gain a web build artifact step.

Minimum required additions:

- bootstrap and validate the canonical local/CI web toolchain;
- install frontend dependencies in CI/local (`pnpm install --frozen-lockfile`);
- run web tests;
- build frontend bundle;
- store build artifact in the CI artifact layout;
- make `release_server_to_remote.py` aware of the web bundle artifact;
- unpack/copy built assets onto Linux before server start/smoke.

## Remote Linux Validation

Validation was run against `altserver@example.test:/var/chat_bot/pc_client` on 2026-04-20.

## Local Web Toolchain Validation

The canonical local/CI frontend toolchain was also validated on 2026-04-20.

### Local Facts Confirmed

- local Node.js: `v24.15.0`
- local npm: `11.12.1`
- local corepack: `0.34.6`
- local `pnpm`: `10.33.0` activated via `corepack`
- repo version files: `.node-version`, `.nvmrc`, `.npmrc`, `package.json`

### Remote Facts Confirmed

- remote branch: `master`
- remote commit: `c27e59e6e4e876c82da361b58c49606c90a42628`
- remote Python: `3.12.7`
- remote Node.js: `v22.13.1`
- remote npm: `10.9.2`
- remote `pnpm`: **not installed**
- remote `corepack`: **not installed**

### Service Check Results

- control-plane status: running
- server start: successful via `python scripts/manage_remote_stack.py start server`
- smoke: successful via `python scripts/manage_remote_stack.py smoke server`
- server stop: successful via `python scripts/manage_remote_stack.py stop server`

### Consequence for the Spec

The Linux host is capable of running the Python server and can host a future built frontend bundle. However, because `pnpm` and `corepack` are absent there today, the canonical plan should **not** assume a remote `pnpm` build as the primary release path.

This confirms the design decision to keep the frontend build canonical in local/CI release automation and make Linux consume built artifacts rather than become the authoritative frontend build machine. If the remote host ever needs npm-based frontend tasks, it should first be upgraded to the same `Node.js 24 LTS + corepack + pnpm` toolchain used locally and in CI.

## Risks

### Risk 1: React UI Built on Legacy Shapes

If new React code consumes current legacy response shapes directly, the team will recreate the same coupling problem inside a modern framework.

Mitigation:

- boundary-first rule;
- typed DTOs;
- no direct raw legacy endpoint use from new UI features.

### Risk 2: Over-Scope in Wave 1

Including `/ticket` and public pages would create a much larger migration surface and dilute the foundation work.

Mitigation:

- keep `/ticket`, public queue, and public browser ticket out of wave 1.

### Risk 3: Build/Deploy Drift

If frontend build output is not integrated into the verified release flow, Linux deploys will drift from what was tested.

Mitigation:

- extend CI artifacts and release scripts before first major UI cutover;
- treat web bundle presence as part of release completeness.

## Success Criteria

This design is considered successfully implemented when:

- `/app/support` is production-usable alongside legacy `/support`;
- `/app/admin` covers the agreed high-priority admin surfaces;
- new UI talks only to the new web-facing API boundary;
- legacy UI routes remain optional rollback paths, not primary surfaces;
- release pipeline builds, ships, and verifies frontend assets as part of the normal server release flow;
- future work on support/admin no longer requires edits to giant imperative JS monoliths.

## Approved Decisions Snapshot

- Stack: React + TypeScript + Vite
- Frontend toolchain: `Node.js 24 LTS + corepack + pnpm`
- One internal frontend project, two workspace route groups
- New backend namespace: `/api/web/*`
- New auth model: `httpOnly` session cookie
- New typed DTO/OpenAPI boundary
- New realtime adapter for web
- First migration targets: `/support`, then `/admin`
- Excluded from first wave: `/ticket`, public queue, public browser ticket pages
- Release model: build frontend before deploy, serve built assets from Python server
