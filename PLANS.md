# Service Desk Core Completion / Request Studio No-Code MVP

Status: Request Studio No-Code MVP verified; safe publish hardening completed

## Current Production Hardening Pass After `5f12a609`

Goal for this pass: replace the MVP deterministic Request Studio publish confirmation hash with a server-issued one-time HMAC/nonce token with TTL, and make publish preview show a real create/update/noop/blocked diff for the affected form schema, request template, catalog offering and service.

Status: completed locally.

Execution plan:

1. Add `request_studio_publish_tokens` with token hash, nonce hash, actor binding, draft hash, scope, TTL, used-at and preview metadata. Raw confirmation tokens must never be stored.
2. Replace the deterministic `confirmation_token` with `rs1.<payload>.<signature>` signed by `REQUEST_STUDIO_CONFIRMATION_SECRET`, bound to canonical draft hash, actor id/role and scope `request_studio.publish`.
3. Reject publish when the token is missing, malformed, invalid, expired, already used, actor/scope mismatched or bound to a different draft; re-run draft validation before mutation and mark the token used only after successful guarded publication.
4. Add typed preview diffs for `form_schema`, `request_template`, `offering` and `service`, including create/update/noop/blocked actions, field changes, warnings and summary counts.
5. Update the Studio preview UI to show diff summary/cards, token expiry state and disabled confirmation for blocked or expired previews while preserving the publish success banner.
6. Update backend/frontend tests and docs for the hardened publish contract.

Verification:

- `python scripts/verify_workspace.py` passed.
- `python scripts/bootstrap_web_toolchain.py` passed with Node.js 24.15.0 and pnpm 10.33.0.
- `pytest server/tests/test_request_studio_api.py -q` passed: 5 tests.
- `pnpm --dir webapp exec vitest run src/pages/admin/request-template-studio-page.test.tsx` passed: 9 tests.
- `pnpm --dir webapp run test` passed: 72 files, 343 tests.
- `pnpm --dir webapp run build` passed.

Constraints:

- Do not change Protocol V3.
- Do not add registry-builder, universal work tasks or free workflow canvas features.
- Do not auto-create missing route/SLA/closure/notification policies.
- Do not expose raw token, raw policy JSON or internal refs in basic Studio UI.
- Do not stage unrelated `pc_agent/ui_gui/tickets_list_model.py` or generated `artifacts/*`.

## Current Safe Publish Pass After `3d73f678`

Goal for this pass: complete a short cleanup/hardening sequence, then add a typed safe publish contract for `/app/admin/request-template-studio` so the primary no-code path can validate, simulate, preview and publish from Studio without requiring Forms Builder, Service Catalog or Policy Health for the basic publication flow.

Commit sequence:

1. Harden Service Catalog expert controls. Completed in `db301661`: filter labels are human-readable while values stay stable, and the expert JSON loader now shows an inline parse error without mutating the draft.
2. Record browser smoke evidence for the request setup pages. Completed in `cc39eb7d`.
3. Clarify Request Studio readiness/publication wording before backend safe publish work. Completed in `fe0603ba`.
4. Verify the small cleanup pass. Completed with fixture hardening in `10362c6e`.
5. Add request-studio backend validation/capabilities contract. Completed: typed DTO/handlers/routes validate draft and capabilities.
6. Add draft-aware request-studio simulation. Kept as existing saved-draft Policy Health simulation for this checkpoint; safe publish validation now uses the current Studio draft payload directly.
7. Add request-studio publish preview/diff plan. Completed: preview returns validation, publish steps and confirmation token.
8. Add safe publish execution. Completed: publish revalidates token/draft, blocks unsafe payloads and commits form schema, request template and catalog offering through existing repos in one guarded transaction.
9. Wire frontend API, publish confirmation flow, tests and docs. Completed: Studio publish button opens preview, confirms token-backed publish and invalidates Studio queries.
10. Clarify post-review UX/docs. Completed: Studio shows the backend publish success message after confirmed publish, and this plan now records token/diff hardening as follow-up instead of saying the safe publish contract is missing.

Browser smoke evidence:

- Stand URL: `https://192.168.100.17:9443/admin`.
- Pages opened in browser after quick release smoke:
  - `/app/admin/request-template-studio`
  - `/app/admin/service-catalog`
  - `/app/admin/forms`
  - `/app/admin/policy-health`
- Screenshot artifacts were written under `artifacts/catalog-requests-screenshots/` for local inspection but are intentionally not part of the committed source changes.
- The remote server was stopped after the browser check.

Cleanup verification:

- `python scripts/verify_workspace.py` passed.
- `python scripts/bootstrap_web_toolchain.py` passed with Node.js 24.15.0 and pnpm 10.33.0.
- `pnpm --dir webapp run test` passed: 72 files, 341 tests.
- `pnpm --dir webapp run build` passed after aligning Request Studio readiness test fixtures with the typed model.

Constraints for this pass:

- Do not stage `pc_agent/ui_gui/tickets_list_model.py`.
- Do not stage existing `artifacts/*`.
- Do not change Protocol V3.
- Do not add a DB schema unless existing form/catalog/helpdesk-model tables cannot safely support the contract.
- Safe publish must validate and preview before mutation, block unsafe drafts and avoid silent partial publication.
- Current confirmation token is a deterministic draft integrity hash, not a server-issued one-time nonce. That is acceptable for this MVP because publish is admin-only and revalidates the draft, but a future hardening pass should add HMAC/nonce+TTL server state.
- Current preview shows publish steps and blockers, not a field-level create/update diff. A future hardening pass should add form schema, request template and offering diffs plus overwrite warnings for existing template codes.

## Current Follow-Up Pass After `7f72a5c7`

Goal for this pass: stabilize the Request Studio no-code MVP with small commits, then make Service Catalog, Forms Builder and Policy Health read clearly as expert surfaces rather than competing primary setup pages.

Commit sequence:

1. Clean Request Studio profile detection and remove mojibake-specific production comparisons from the profile logic.
2. Resolve Studio visibility policies through the loaded policy registry instead of blindly writing `visibility_default`.
3. Clarify the save/check flow: saved draft, stale check, blocked simulation with unsaved changes.
4. Run the required web verification checkpoint and record the remaining publish limitation. Completed green with `verify_workspace.py`, `bootstrap_web_toolchain.py`, `pnpm --dir webapp run test` and `pnpm --dir webapp run build`.
5. Polish Service Catalog as an expert page with Studio CTA, default test/retired filtering and collapsed expert JSON.
6. Polish Forms Builder as an expert page with Studio CTA and template-context return path.
7. Polish Policy Health as expert diagnostics with Studio-first repair actions and hidden technical refs by default.
8. Clarify request setup navigation labels so Studio is the primary path and the other pages are expert tools.
9. Run final verification and update docs for the completed pass. Completed in the final docs/verification commit.

Constraints for this pass:

- Do not stage `pc_agent/ui_gui/tickets_list_model.py`.
- Do not stage existing `artifacts/*`.
- Keep Studio direct publish on the typed safe publish contract; Service Catalog, Forms Builder and Policy Health remain expert surfaces, not the primary publication path.
- Keep Service Catalog, Forms Builder and Policy Health available as expert surfaces.

Final follow-ups:

- Add a draft-aware simulation endpoint that can validate the unsaved Studio aggregate directly after explicit save.
- Add optional service-desk-ready presets for route/SLA/closure/notification.
- Keep registry-builder and universal work-task modules out of this MVP; they belong to later dedicated passes.

## Goal

Continue the `/app/admin/request-template-studio` rebuild after `de7ae78b` and make it a real no-code editing MVP. An administrator must be able to select or create a request type, edit the basic form and processing blocks inside Studio, save a durable draft, run validation/simulation, and see whether publication is possible without opening Forms Builder, Service Catalog or Policy Health for the basic setup path.

Primary user path:

1. Select an existing request type or create a draft through a wizard.
2. Edit display title, description and visibility.
3. Edit form fields inline.
4. Choose a processing profile and apply safe defaults.
5. Choose route, SLA, approval, closure and notification settings inside Studio.
6. Save the draft through existing safe draft APIs.
7. Run validation/simulation against the saved draft context.
8. See clear publication status and publish from Studio through the safe preview/confirmation contract.

## Scope

- React webapp UX first; no new DB schema in this pass.
- Keep route `/app/admin/request-template-studio`.
- Use existing APIs first:
  - `fetchServiceCatalogDashboard`
  - `fetchHelpdeskModelRegistry`
  - `fetchPolicyHealthDashboard`
  - `fetchAdminFormsCatalog`
  - `saveAdminFormsDraft`
  - `saveOfferingDraft`
  - `simulatePolicyHealth`
- Add a mutable Studio draft model over existing service/offering/template/form/policy data.
- Add inline no-code editors under `webapp/src/features/request-template-studio/`.
- Update tests and docs for the no-code MVP.

## Non-Goals

- Do not change Protocol V3.
- Do not weaken P0-P5 contracts.
- Do not add a registry/task universal constructor.
- Do not add a free BPMN/n8n canvas.
- Do not add a DB schema or backend endpoint unless existing draft APIs cannot persist the MVP safely.
- Do not remove expert surfaces. Service Catalog, Forms Builder and Policy Health remain available as expert tools.
- Do not show retired/test/smoke entries as the default working selection.
- Do not show raw JSON/policy refs in basic mode.

## Ownership And Boundary Classification

- Ownership zone: React webapp UI plus Service Catalog process layer documentation.
- Classification: boundary change if using existing draft APIs without changing DTO shape; cross-cutting only if new `/api/web/*` DTO/routes are added.
- Boundary surfaces consumed but not changed unless implementation proves otherwise:
  - `/api/web/admin/service-catalog`
  - `/api/web/admin/service-catalog/offerings/save-draft`
  - `/api/web/admin/helpdesk-model/policies`
  - `/api/web/admin/helpdesk/policy-health`
  - `/api/web/admin/forms/current`
  - `/api/web/admin/forms/save-draft`
  - `/api/web/admin/helpdesk/policy-health/simulate`

## UX Decisions

- Main UI entity is `Тип обращения`, not `service/offering/template/form/policy`.
- Basic mode hides raw policy refs, JSON, internal ids, route preview payloads and version/debug details.
- Advanced mode may show processing profile, inheritance, enabled policies, warnings and process mapping.
- Expert mode keeps JSON, raw policy refs and deep links to Service Catalog, Forms Builder and Policy Health.
- Publication button must not be a dead disabled control. Studio now uses the safe publish preview/confirmation contract; expert catalog publication remains available only as an expert surface.
- Readiness must distinguish blockers, recommendations and ready items in human language.
- Draft state must visibly distinguish saved, unsaved, saved draft, validation required and publication blocked/available states.

## Implementation Decisions For This Pass

- Use existing `saveAdminFormsDraft()` for durable form draft persistence. The Studio payload updates or creates one form in the `request_forms` pack, preserving other forms from the loaded catalog.
- Use existing `saveOfferingDraft()` for durable catalog draft persistence of title, description, visibility and selected policy refs.
- Compose a single working Studio item from `selectedItem + studioDraft` so the process map, block inspector, readiness, preview, simulation payload and newly created wizard drafts all read the same current state.
- Show the selected block editor in basic mode instead of the previous long tape of every editor; advanced/expert modes can still show broader processing details.
- Treat policy selection as choosing existing active policies only. Presets and auto-fix may map to found active policies; if none exist, Studio must say expert setup is required.
- Direct publish is in scope through the dedicated safe Studio publish contract. The UI must preserve context in expert links but not make expert publication the basic path.
- Do not mutate published live objects field-by-field. Local edits become a dirty Studio draft and persist only when `Сохранить черновик` is clicked.

## Component Plan

Create or update:

- `webapp/src/pages/admin/request-template-studio-page.tsx` - page entrypoint, data orchestration and save mutations.
- `webapp/src/features/request-template-studio/studio-model.ts` - aggregate item selection and process block derivation.
- `webapp/src/features/request-template-studio/draft-model.ts` - Studio draft, presets, auto-fix suggestions and save payload builders.
- `webapp/src/features/request-template-studio/create-request-wizard.tsx` - MVP request type wizard.
- `webapp/src/features/request-template-studio/form-field-editor.tsx` - inline basic form editor.
- `webapp/src/features/request-template-studio/process-editors.tsx` - inline route/SLA/approval/closure/notification/profile editors.
- `webapp/src/features/request-template-studio/request-studio-shell.tsx` - header commands, status chips and expert publication wording.
- `webapp/src/features/request-template-studio/block-inspector.tsx` - selected block configuration in simple language.
- `webapp/src/features/request-template-studio/readiness.ts` - readiness categories and draft-aware blockers/recommendations.
- `webapp/src/pages/admin/request-template-studio-page.test.tsx` - no-code MVP regression tests.
- `webapp/src/features/request-template-studio/studio-model.test.ts`, `draft-model.test.ts` - draft overlay/default-selection/save-payload unit tests.
- `docs/QUICK_LOOKUP.md`, `docs/ARCHITECTURE_BOUNDARIES.md` if needed, and `server/docs/CODEMAP.md` - document Studio as the primary request setup path.

## Acceptance Criteria

- First screen reads as one request setup workflow, not four equal admin tools.
- `Студия обращений` is the visible page title.
- Basic mode has no raw JSON and no policy refs.
- The selected request type shows editable user form, executor routing, SLA, approval, closure, notifications and publication readiness.
- `Создать обращение` opens a wizard and produces a dirty draft.
- `Исправить автоматически` opens safe suggestions and applies only found existing policies/presets.
- `Сохранить черновик` calls real draft APIs and survives backend persistence.
- Route/SLA/approval/closure/notifications can be edited inside Studio in basic mode.
- Simulation warns when unsaved changes exist and uses saved/draft context after save.
- Retired/test/smoke entries are excluded from default selection and appear only behind the technical-items toggle.
- Expert tools are reachable but do not dominate the basic flow.
- Existing Service Catalog, Forms Builder and Policy Health routes are not removed or renamed.
- Webapp tests and build pass.

## Execution Checkpoints

- [x] Read project workflow, boundaries, context index, testing rules and service catalog/ticket docs.
- [x] Ran `python scripts/bootstrap_web_toolchain.py`.
- [x] Confirmed `de7ae78b` is an ancestor of the current branch.
- [x] Add failing no-code MVP tests and verify RED.
- [x] Implement draft model, wizard, inline editors, auto-fix and save flow.
- [x] Stabilize Studio around one draft-aware `workingItem` and focused block editor UX.
- [x] Update docs/CODEMAP navigation notes.
- [x] Run required verification:
  - `python scripts/verify_workspace.py`
  - `pnpm --dir webapp run test`
  - `pnpm --dir webapp run build`
- [x] Confirmed Request Studio No-Code MVP is draft-aware and verified after profile detection, visibility resolver and save/check flow cleanup.
- [x] Direct Studio publish uses a safe publish preview/confirmation contract.
- [x] Browser-check the canonical admin UI after deploy or live release.

## Known Constraints

- Direct publish from Studio is available through the safe request-studio publish endpoint.
- Confirmation token is now a server-issued one-time HMAC/nonce token with TTL and hashed DB state, not a deterministic draft hash.
- Publish preview now includes field-level create/update/noop/blocked diffs for the form schema, request template, offering and service.
- Existing Forms Builder draft API saves the form pack draft, not a separately named Studio aggregate object. The UI must explain that Studio saves a draft using the existing form/catalog draft contracts.
- Full CI and full release gate are not part of this iteration unless explicitly requested after a frozen candidate SHA.

## Handoff

Continue in Execute mode. Do not stage unrelated dirty files:

- `pc_agent/ui_gui/tickets_list_model.py`
- existing untracked `artifacts/*`

## 2026-06-03 Product Design UI audit remediation

Goal: apply the Product Design audit fixes for `/app/tickets`, `/app/admin/device`, and `/app/admin/policy-health`, then repeat the browser audit and verify the web UI.

Mode: Plan / Execute. Ownership zone: React webapp UI. Classification: local UI change; no API, DB, Protocol V3, auth, observer, deploy script, or DTO contract change planned.

Scope:

- Variant 1 hygiene pass:
  - add explicit accessible labels for affected search/select/textarea/file controls;
  - increase the effective tickets column-resizer target size while preserving the slim visual affordance;
  - improve icon/technical control discoverability where the audit found small or implicit controls;
  - make Policy Health summary counters scannable metric cards;
  - add helper text/examples to the Policy Health dry-run form.
- Variant 2 focused layout refactor:
  - make ticket diagnostics/context less visually cramped by default and make the right pane easier to collapse/focus;
  - make Device Card identity/status the dominant first-screen content and reduce right-rail competition;
  - make Policy Health support a table-first comparison view and visually tie the detail pane to the selected row.

Primary files:

- `webapp/src/styles.css`
- `webapp/src/pages/tickets/list-page.tsx`
- `webapp/src/pages/tickets/list-page.test.tsx`
- `webapp/src/pages/admin/device-page.tsx`
- `webapp/src/features/policy-health/policy-health-panel.tsx`
- `webapp/src/features/policy-health/policy-health-panel.test.tsx`
- optional targeted admin/device test if existing test coverage requires it

Non-goals:

- no backend payload changes;
- no route renames;
- no mobile redesign beyond avoiding obvious overflow;
- no full Product Design image-to-code prototype pass in this iteration.

Verification matrix:

- `python scripts/bootstrap_web_toolchain.py`
- targeted Vitest for changed webapp tests;
- `pnpm --dir webapp run test`
- `pnpm --dir webapp run build`
- `python scripts/verify_workspace.py`
- deploy/release through project scripts, then remote smoke and browser check on `https://192.168.100.17:9443/admin`;
- repeat Product Design-style screenshot audit for the three requested URLs;
- stop remote server after checks.

Execution checkpoints:

- [x] Ran task intake, context pack, context-index rebuild, and web toolchain bootstrap.
- [x] Add RED tests for Policy Health summary/layout/accessibility and tickets resize/labels.
- [x] Implement Variant 1 hygiene fixes.
- [x] Implement Variant 2 layout refactor.
- [x] Run local test/build/verify gates.
- [ ] Deploy to Linux stand, smoke and browser-audit the three URLs.
- [ ] Commit and push only task files, leaving unrelated dirty files untouched.
