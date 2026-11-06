# Inline Studio Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Implement the approved complete Studio redesign with compatible legacy services and reliable draft saving.
**Architecture:** Preserve v1/v2/v3 definitions and pinned sessions. Add v4 with explicit execution semantics, manual navigation actions, automatic SLA nodes and safe rich documents. Reuse the existing React Flow editor, attachment authorization, publication and session lifecycle.
**Tech Stack:** Python/Pydantic 2/SQLAlchemy 2/PostgreSQL, React 19, React Flow 12.11, Tiptap 3.26, Vitest/pytest/Playwright.
**Spec:** `docs/superpowers/specs/2026-11-06-studio-inline-map-editor-design.md` (approved by user).

## Global Constraints

- Work in the current checkout, preserve the initial dirty diff captured in `tmp/studio-inline-20261106/baseline.diff`.
- Branch `codex/studio-inline-v4`; no production changes, history rewriting or automatic service publication.
- Existing v1/v2/v3 definitions and active sessions keep their behavior, including checkbox and screenshot-stage compatibility.
- No new dependencies, no weakened authentication/CSRF/authorization, no external image URLs or raw HTML.
- Manual navigation: 1–10 buttons, no mixed automatic/button edges within one interactive block; no answers fabricated for navigation.
- User has approved full implementation. Execute continuously; planning and technical implementation choices do not require another permission round.

## Review Focus

- Two buttons to one destination must retain distinct processing and replay correctly.
- Upgrading a legacy draft must preserve checkbox/missing-answer/processing semantics.
- Copying fragments must not grant access to source files or silently reuse conflicting field/policy keys.
- Expired session or CSRF refusal must retain local edits and never be retried as a successful write.
- Inputs in expanded map nodes must not drag/pan the map or lose edits on selection changes.

## Interface Decisions

- v4 `execution_semantics: 1|2|3` preserves source semantics; new v4 uses 3.
- `BlockBase.transition_mode?: "automatic"|"buttons"`; `Transition.button?: {key:string,label:string}`.
- Commands optionally carry `action_key`; the server validates it against the current block and durable route history.
- `navigation` is an interactive button-only block. `sla` is automatic with `processing_facts`, optional `sla_profile` or `policy_ref`; one ordinary continuation.
- `RichDocument` is a bounded Tiptap-style JSON doc with an allowlisted AST. Instruction `content.rich_document` and field `help_document` are optional v4 data; plain body/help_text are preserved as fallback. Asset nodes reference canonical scoped attachments by `asset_id`.
- Fragment APIs live below `/api/web/admin/request-scenarios`: GET/POST `/fragments`, GET/archive `/fragments/{id}`, POST `/scenarios/{id}/fragments/{fragment_id}/insert`. Source snapshot, selected block IDs and title create a fragment; insertion accepts expected revision and dependency mappings and returns ScenarioDetail.

### Task 1: Versioned execution, SLA, navigation and rich contracts

**Files:** backend DTO/runtime/validation/submission/session/projection/publication/assets, scenario models and new migration; frontend `scenario-contract.ts`; new focused `server/tests/test_request_scenario_v4*.py`.
**Consumes:** existing v1/v2/v3 engines and published-session authority.
**Produces:** interfaces above; v4 conversion helper with explicit preserved source semantics; regenerated JSON schema.
- [ ] Write tests for v4 1/10/11 buttons, invalid/stale action, required answers, equal targets with different processing, SLA/backtracking and legacy conversion equivalence.
- [ ] Run focused pytest and observe failures for unsupported v4.
- [ ] Implement schema/runtime, server-derived action trace, projected actions, v4 processing and rich AST validation without changing legacy definitions. Extend DB version constraint additively.
- [ ] Run new tests plus existing runtime/contract/v3/processing/optional-evidence tests; all must pass.

### Task 2: Diagnose and fix saving

**Files:** `use-scenario-editor.ts`, tests, API error handling and confirmed owning auth/deploy configuration only if evidence requires it.
**Consumes:** same-origin/session authorization and revision CAS.
**Produces:** distinguishable safe save failures and a verified fix for the observed refusal.
- [ ] Capture redacted live HTTP code/request-id on an isolated unpublished staging draft; preserve the user's current unsaved draft.
- [ ] Test stale callbacks, expired session, origin refusal and pending autosave across read-only/identity changes; run failing regressions.
- [ ] Correct the confirmed cause and expose the appropriate recovery action while retaining edits. No blind 401/403 retries.
- [ ] Run hook/API/auth regressions and repeat the isolated browser flow.

### Task 3: Server fragment library

**Files:** new fragment service/handlers/DTO, migration/model, scoped asset-copy reuse, route registration and tests.
**Consumes:** Task 1 definitions and existing author-material authorization/copy paths.
**Produces:** persistent revisioned fragment APIs from Interface Decisions.
- [ ] Add failing tests for selected-subgraph extraction, unique remapping, external dependencies, source/destination access, archived source and retained fragment attachments.
- [ ] Implement source snapshots, list/archive, atomic insertion and scoped material retention/copy. Conflicts require explicit mapping, never default substitution.
- [ ] Run focused service/API tests and existing asset-copy tests.

### Task 4: Catalog and inline map editor

**Files:** catalog workbench/geometry/CSS/tests; map workbench/canvas/model/edge/CSS/tests; new inline/context-menu/fragments components.
**Consumes:** Task 1 contracts, Task 3 APIs and existing editors.
**Produces:** two-zone catalog/map, double-click/keyboard editing, visible insertion and map context actions.
- [ ] Add failing component tests for double-click service opening, no permanent inspector, pan/zoom insertion, node double-click and keyboard/PCМ actions.
- [ ] Embed each editor in the expanded node; use nodrag/nopan/nowheel and dimension updates. Non-node operations open contextual overlays, not a permanent third panel.
- [ ] Add viewport-relative placement, source/edge insertion, context actions, atomic fragment insertion/undo and built-in fragments.
- [ ] Add dedicated navigation/SLA editors and legacy-effect projections; remove duplicated SLA/route panels from question/instruction editors.
- [ ] Run relevant Vitest tests, keyboard/disabled/legacy cases and build.

### Task 5: Visual block content and requester execution

**Files:** shared rich renderer/editor, field/block editors, author attachments, requester step/session and simulation components/tests.
**Consumes:** Task 1 rich AST/actions and existing attachment contexts.
**Produces:** safe matching author/requester rendering, formatted questions/instructions and button navigation.
- [ ] Add failing tests for permitted AST, rejected URLs/nodes, asset scope, manual actions with no fabricated answers and required question validation.
- [ ] Implement existing-Tiptap editing, explicit conversion, scoped inline images, full editor overlay and live form/option editing.
- [ ] Render actions in requester and simulator, pass action_key, support backtracking and preserve old text formatting unless explicitly converted.
- [ ] Run focused frontend/backend projection tests and build.

### Task 6: Integrate, review and verify

**Files:** docs/UNIFIED_SERVICE_SCENARIOS.md, server/docs/CODEMAP.md, PLANS.md, focused E2E fixtures and evidence.
**Consumes:** all prior tasks.
**Produces:** reviewed complete implementation and exact verification evidence.
- [ ] Review task diffs against baseline; address compatibility or security findings with failing regressions first.
- [ ] Run focused backend suites, all affected Studio/requester Vitest tests, build and `python scripts/verify_workspace.py`.
- [ ] Browser-check 1366×768 and 1920×1080, no horizontal scroll, visible actions, pan/zoom/PCМ, content, fragments, legacy services and failed/successful saves; inspect console/network.
- [ ] Update docs/CODEMAP/PLANS. Obtain fresh whole-change review under the review skill, fix important findings and record residual limitations honestly.
- [ ] Inspect complete diff/status and `git diff --check`; stage only task changes if committing. Do not publish or deploy production.

## Execution Ledger

- 2026-11-06: approved spec; baseline captured, branch created; existing checkout reused to preserve uncommitted prerequisite changes.
- Ruling: execute within the user's specified workspace and current dirty checkout; no extra worktree or repeated plan approval — preserves required local changes and obeys the instruction to proceed fully.
- Preflight: Task 1 contracts feed Tasks 3–5; stabilize names before parallel integration. Backend owner does not edit frontend; controller owns frontend contracts and integration.

### Integration progress — 2026-11-06

- Tasks 1–3: v4 execution, atomic explicit upgrade, safe save recovery and persistent fragments implemented. Backend focused265, isolated PostgreSQL API/runtime66 and schema8 passed; clusters stopped.
- Tasks 4–5: catalog/map inline editing, viewport placement, context actions, SLA/navigation controls, visual content and requester/simulator actions implemented. Studio225 passed; two later regressions (editor click bubbling and rich help duplication) reproduced and fixed with focused checks.
- Browser: `PC_CLIENT_WEBAPP_E2E_PORT=4216 pnpm --dir webapp exec playwright test tests/studio-inline-v4.spec.ts` — 2 passed at1366×768/1920×1080, `browser-inline3.log`; expected401 isolated from other console/network errors. No live staging service/data changes.
- Whole-change independent review found4 issues (legacy SLA prop assignment, insertion schema guard, rich-image attachment removal and automatic-edge precedence); final fix wave assigned, plus selected catalog detail visibility. Completion waits fixes and scoped re-review.
- Ruling: fragment endpoints use the existing `/api/web/admin/request-studio` prefix rather than the plan's mistaken `/request-scenarios` prefix — preserves the owning API boundary; all consumers use the same prefix.
- Ruling: atomic upgrade proves equality of normalized effective business definitions under preserved execution semantics, with legacy outcome regressions — arbitrary input/external-policy enumeration cannot be exhaustive; a mismatch fails before writing.
- Publication/deployment: no commit, push, production or staging deployment performed. Backend precedes frontend, migrations157/158 and reviewed deployment remain mandatory when releasing.

- Final wave: F1–F5 fixed with regression coverage; scoped independent re-review clean (no new P0/P1/P2). Browser final4/4 passed on final product source, including legacy SLA and rich-image upload/removal. Full frontend suite still running; final completion awaits exit result. `git diff --check` clean.

### Final local acceptance

- Full frontend:186 files /1126 tests passed, `frontend-final.log`.
- Browser:4/4 passed, `browser-final2.log`; no unexpected JS/network errors, expected401 recorded separately.
- Backend265 focused, isolated DB/API66, migration/schema8 passed; owned clusters and browser fixture stopped.
- Build passed (known chunk-size warning); verify_workspace and diff whitespace checks passed. Independent whole-change review + one fix wave + scoped re-review complete, no open P0/P1/P2 findings.
- Implementation scope complete locally. Release/deployment remains separate: no commits/push/staging or production installation,157/158 must precede the new frontend.
