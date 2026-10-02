# Post-Cutover Legacy Cleanup Implementation Plan

> Implement inline with the project verification/review skills; keep edits bounded to the approved cleanup.

**Goal:** Remove misleading fleet UNKNOWN controls and proven-dead Helpdesk Agent/inventory artifacts.

**Architecture:** Endpoint owns current technical presence/context; Registry owns business data. Preserve BFF routes and historical schema/operation compatibility. No production deployment or provider change.

**Tech Stack:** Python/aiohttp, React 19.2.5, TanStack Query 5.99.2, Vitest/Playwright.

**Spec:** User attachment `pasted-text-1.txt`, Post-Cutover Legacy Cleanup, baseline `1818f1988306061e806aa5668347f4389a5b91ca`.

## Tasks

- [x] Inspect baseline, GitNexus committed context, direct/string/dynamic imports, config access, packaging/release/startup/test consumers.
- [x] Reproduce new boundary and fleet UI checks before removal.
- [x] Remove UNKNOWN row option/zero metric; retain degraded page and refetch failure behavior.
- [x] Remove scheduler env entry, unused Agent module switch and unused shared descriptor module.
- [x] Remove discovered command-center local timestamp/historical offline fallback; preserve field/section names and workflow.
- [x] Extend existing boundary guard; test recent/stale local timestamps without technical authority.
- [x] Update canonical boundary documentation and CODEMAP.
- [x] Run focused tests, typecheck, Vitest, production build, browser evidence at 1366x768/1920x1080, workspace verifier and diff check.
- [ ] Independently review, freeze candidate commit, run full canonical CI with isolated PostgreSQL/fresh migrations and locked real Endpoint acceptance.
- [ ] Report exact candidate SHA, results and residual terminology debt. Do not deploy.

## Discovery classification

Tracked repository-wide symbol search found one active scheduler example (`server/.env.example`, ENABLED only), no runtime scheduler/config reader, and no tracked interval references. `AGENT_BUILTIN_MODULES` appeared only in its definition/env lookup, with no direct/dynamic/startup/packaging/test consumer. Shared package exports no descriptors; no descriptor imports or dedicated descriptor tests remain. The deleted module registered only inventory/presence descriptors.

Untracked `.superpowers/sdd/2026-10-01-admin-endpoint-cutover` scripts contain historical cleanup references; ignored old worktrees/temp checkouts contain prior runtime implementations. These are historical work artifacts, outside the current repository runtime, and remain untouched.

Remaining retired tool literals belong to historical DB model defaults, migration 094, historical Observer/locator/operation tests, the legacy migration matrix, and immutable browser evidence. `scripts/test_docs_inventory.py` uses the unrelated Python method `docs_inventory.collect_docs`, not a retired tool ID. Boundary tests permit historical schema/migrations/test/evidence and reject current server/shared registration or dispatch.

## Review focus

Outage must not render cached rows as current offline devices; successful boolean rows must offer only ONLINE/OFFLINE. Retained model defaults are historical storage, not dispatch authority. Local timestamp ages and stored offline signals must not supply current presence. No route, provider contract, schema, permission or production runtime change is authorized.
