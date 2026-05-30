# Service Desk Core Completion / Request Studio No-Code MVP

Status: implementation complete, verification in progress

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
8. See clear publication status; publication remains expert-only unless a safe Studio publish contract is added.

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
- Publication button must not be a dead disabled control. Until a safe Studio publish contract exists, show `Открыть экспертную публикацию` and explain the limitation.
- Readiness must distinguish blockers, recommendations and ready items in human language.
- Draft state must visibly distinguish saved, unsaved, saved draft, validation required and publication blocked/available states.

## Implementation Decisions For This Pass

- Use existing `saveAdminFormsDraft()` for durable form draft persistence. The Studio payload updates or creates one form in the `request_forms` pack, preserving other forms from the loaded catalog.
- Use existing `saveOfferingDraft()` for durable catalog draft persistence of title, description, visibility and selected policy refs.
- Treat policy selection as choosing existing active policies only. Presets and auto-fix may map to found active policies; if none exist, Studio must say expert setup is required.
- Keep direct publish out of scope for this pass because there is no dedicated safe Studio publish contract. The UI must expose this honestly and preserve context in the expert link.
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
- [x] Update docs/CODEMAP navigation notes.
- [ ] Run required verification:
  - `python scripts/verify_workspace.py`
  - `pnpm --dir webapp run test`
  - `pnpm --dir webapp run build`
- [ ] Browser-check the canonical admin UI after deploy or live release.

## Known Constraints

- Direct publish from Studio remains a follow-up unless a safe request-studio publish endpoint is added.
- Existing Forms Builder draft API saves the form pack draft, not a separately named Studio aggregate object. The UI must explain that Studio saves a draft using the existing form/catalog draft contracts.
- Full CI and full release gate are not part of this iteration unless explicitly requested after a frozen candidate SHA.

## Handoff

Continue in Execute mode. Do not stage unrelated dirty files:

- `pc_agent/ui_gui/tickets_list_model.py`
- existing untracked `artifacts/*`
