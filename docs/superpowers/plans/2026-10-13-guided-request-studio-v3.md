# Guided Request Studio v3 Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans. Work continuously within the approved specification.

**Goal:** One scenario map with multiple catalog entrances, a contextual visual editor, and canonical Helpdesk execution and policies.

**Architecture:** Add bounded entry_points and editor_layout to existing versioned JSON definitions; published graph and entrances are one immutable snapshot. Session start accepts an entrance key, resolves it server-side, and pins it alongside the version. Existing scenario runtime, processing, approval lifecycle, publication guards and Service/Offering remain canonical.

**Tech Stack:** Python/Pydantic/SQLAlchemy/PostgreSQL; React 19, TypeScript, React Flow 12, TanStack Query.

**Spec:** User-supplied Helpdesk Guided Request Studio v3 specification, copied to `docs/superpowers/specs/2026-10-13-guided-request-studio-v3.md`; visual reference `http://127.0.0.1:4173/#builder`.

## Global Constraints

- Main baseline bb8c521faaf76eea01119f314f68fecdeb34cefb matches origin/main at start.
- One functional branch; preserve unrelated untracked work and prototype.
- No production mutation, actual scenario publication, real tickets or real diagnostics during simulation.
- Preserve canonical Service -> Offering -> RequestTemplate/FormSchema -> Policy Runtime -> Ticket.
- Preserve legacy entry_block_id, pinned old sessions, strict DTO limits, positive resolution requirement, no automatic graph cycles, existing ACL/audit/publication guards.
- Additive storage only; use actual Alembic head if a migration is required.
- No added dependencies, separate SLA engine or runtime executor.
- Admin primary job: author/publish one map. Archetype: workbench with explorer, canvas and inspector. Secondary jobs: preview/version history; rare jobs: destructive edits in inspector with dependency explanation.
- Exactly three primary sections: Каталог, Карта сценария, Согласования. Testing and publication are contextual panels/actions.

## Review Focus

- Specialized entrances bypassing required fields or positive resolution checks: reject publication and actual submission.
- Hidden entrance/category/service/offering visibility: fail closed and omit from requester catalog.
- Old sessions after graph replacement: retain version and entrance context.
- Multi-step graph edits: preserve original conditions and unrelated routes, atomic undo/redo.
- Save conflicts and rapid edits while save pending: preserve newer local work; never imply publication.

### Task 1: Versioned entrances and canonical runtime

**Files:** Existing request_scenario DTO, repo, runtime, readiness, publication, session, catalog, related handlers/models; additive migration only if needed; server scenario tests.

**Interfaces:** ScenarioDraftDefinition.entry_points list of {key, title, description, category_id, synonyms, visibility, enabled, target_block_id, reported_symptom}; editor_layout.positions keyed by block ID with {x,y}. SessionStart.entry_point_key optional; SimulationInput.entry_point_key optional. Entrances never supply verified facts or policy authority. Legacy omission uses entry_block_id.

- [x] Add regression tests proving entrance validation, safe reported context, start authorization and pinned versions, every-entrance readiness, old-definition compatibility.
- [x] Run regression tests RED, implement additive contracts/storage/publication/runtime/catalog, and run focused tests GREEN.
- [x] Expose published requester catalog entrances within existing offering projection; retain legacy forms and fallback.
- [x] Run applicable persistence/API checks and report exact executed checks and outstanding database evidence.

### Task 2: Map workbench

**Files:** request-template-studio feature components/contracts/editor hook, admin Studio page, existing styles, graph model/component tests and fixture browser flows.

**Interfaces:** Consume Task 1 DTO fields; mutate canonical transitions. Seven visual palette types map to existing eight runtime kinds. System Начало represents map metadata only.

- [x] Add model/component regressions for movement, single-route reconnect, insertion retaining condition, entrance-safe deletion, fresh IDs on copy, cycle rejection, atomic undo/redo.
- [x] Implement full canvas with persistent geometry, ports/edges, search, zoom/pan/fit, contextual node/edge inspector, embedded question/condition/policy/entrance editing.
- [x] Replace primary navigation with three sections. Reuse approval backend, simulation, publication and version-history components in contextual surfaces.
- [x] Add selected-entrance simulation, current/path highlighting and safe result-policy preview; preserve explicit publication confirmation.
- [x] Implement draft saving state/autosave and safe conflicts without losing unsaved changes.
- [x] Run targeted frontend tests and build.

### Task 3: Requester integration and delivery verification

**Files:** Requester catalog/session API and UI, guided fixture browser tests, relevant docs and server CODEMAP, PLANS.md.

- [x] Render searchable published entrances and start selected server-resolved entrance; preserve ordinary forms and legacy single entrance.
- [x] Verify fixture/browser authoring and requester routes at 1366x768 and 1920x1080, no horizontal body scroll, visible actions, loading/empty/error states, console/network status.
- [x] Run scoped workspace sanity, affected backend/frontend suites, current build, applicable canonical CI checks; inspect full diff and diff --check.
- [x] Perform one independent final review and resolve concrete findings. Prepare atomic verified commits on functional branch; report contracts, limitations, tests and no-production boundary.

## Execution state

- Plan/spec originate from explicit approved user specification; no additional design gates per its section 13.
- GitNexus queried before source exploration; helpdesk index is on older codex/helpdesk-process-model baseline, so current source/tests govern new scenario contracts.
- Unrelated untracked files present before work; excluded from staging.

## Verification receipt

Implemented and independently reviewed all three tasks. Latest changed frontend suite: 30 files, 129 tests passed; TypeScript/Vite build passed. Full fixture browser suite: 118 passed; final viewport, pointer-editing, geometry and confirmation subset: 10 passed. Screenshots inspected at 1366 and 1920. Full server no-DB suite: 1375 passed, 1 skipped; latest affected server subset: 208 passed, 1 skipped. Isolated Linux PostgreSQL/API suite: 36 passed against current task server overlays, fresh migrations through head 148, temporary role/database cleanup confirmed. Scripts suite: 275 passed; six strict audits passed; mutation smoke killed 4/4 mutants; scoped workspace verification passed.

Functional branch commit and draft PR are the remaining delivery operations. Canonical PR CI will be tracked on the draft PR; local evidence does not substitute for its result. Dynamic group membership expansion is not implemented by the existing approval backend; authoring exposes trusted manager/owner/lead sources and active Registry accounts. No production services, real scenarios, real tickets or device operations changed.
