# Service Desk Core Completion / Request Studio UX Rebuild

Status: in progress

## Goal

Rebuild `/app/admin/request-template-studio` into `Студия обращений`: a guided no-code builder where a service desk administrator configures one user-facing request type without knowing the internal Service Catalog / Forms Builder / Policy Health model.

Primary user path:

1. Select or create a request type.
2. Review the user form.
3. Review processing rules as a processing profile.
4. Inspect routing, SLA, approval, execution, closure and notifications as fixed blocks.
5. Run a human-readable validation/simulation.
6. Open the safe publication path.

## Scope

- React webapp UX only unless a backend contract proves necessary.
- Keep route `/app/admin/request-template-studio`.
- Rename the visible page to `Студия обращений`.
- Use existing APIs first:
  - `fetchServiceCatalogDashboard`
  - `fetchHelpdeskModelRegistry`
  - `fetchPolicyHealthDashboard`
  - `fetchAdminFormsCatalog`
  - `simulatePolicyHealth`
- Build a frontend data model `RequestStudioItem` over the existing service/offering/template/form/policy data.
- Split the current page into feature-owned components under `webapp/src/features/request-template-studio/`.
- Update tests and docs for the new UX.

## Non-Goals

- Do not change Protocol V3.
- Do not weaken P0-P5 contracts.
- Do not add a registry/task universal constructor.
- Do not add a free drag-and-drop workflow canvas.
- Do not add a DB schema or backend endpoint unless frontend composition cannot meet the current UX.
- Do not remove expert surfaces. Service Catalog, Forms Builder and Policy Health remain available as expert tools.
- Do not show retired/test/smoke entries as the default working selection.

## Ownership And Boundary Classification

- Ownership zone: React webapp UI plus Service Catalog process layer documentation.
- Classification: local webapp UI change if no `/api/web/*` DTO shape changes are made.
- Boundary surfaces consumed but not changed:
  - `/api/web/admin/service-catalog`
  - `/api/web/admin/helpdesk-model/policies`
  - `/api/web/admin/helpdesk/policy-health`
  - `/api/web/admin/forms/current`
  - `/api/web/admin/helpdesk/policy-health/simulate`

## UX Decisions

- Main UI entity is `Тип обращения` / `Настраиваемое обращение`, not `service/offering/template/form/policy`.
- Basic mode hides raw policy refs, JSON, internal ids, route preview payloads and version/debug details.
- Advanced mode may show processing profile, inheritance, enabled policies, warnings and process mapping.
- Expert mode keeps JSON, raw policy refs and deep links to Service Catalog, Forms Builder and Policy Health.
- Publication button must not be a dead disabled control. If Studio cannot safely publish directly, show `Открыть экспертную публикацию` and explain the temporary limitation.
- Readiness must distinguish blockers, recommendations and ready items in human language.

## Component Plan

Create or update:

- `webapp/src/pages/admin/request-template-studio-page.tsx` - page entrypoint and data orchestration only.
- `webapp/src/features/request-template-studio/studio-model.ts` - frontend aggregate model, item selection, process block derivation, mode types and helper labels.
- `webapp/src/features/request-template-studio/readiness.ts` - readiness categories and human-readable blocker/recommendation mapping.
- `webapp/src/features/request-template-studio/request-studio-shell.tsx` - primary layout and header commands.
- `webapp/src/features/request-template-studio/request-item-list.tsx` - grouped request type list and test/retired filter.
- `webapp/src/features/request-template-studio/process-map.tsx` - fixed process map.
- `webapp/src/features/request-template-studio/process-block-card.tsx` - one block card with status/action.
- `webapp/src/features/request-template-studio/block-inspector.tsx` - selected block configuration in simple language.
- `webapp/src/features/request-template-studio/readiness-panel.tsx` - publication readiness sidebar.
- `webapp/src/features/request-template-studio/form-preview-panel.tsx` - user/executor preview.
- `webapp/src/features/request-template-studio/simulation-panel.tsx` - human-readable test run and expert JSON disclosure.
- `webapp/src/features/request-template-studio/options.ts` - keep existing picker/simulation helpers if useful.
- `webapp/src/pages/admin/request-template-studio-page.test.tsx` - update expectations to the new UX.
- `docs/QUICK_LOOKUP.md` and `server/docs/CODEMAP.md` - document Studio as the primary request setup path.

## Acceptance Criteria

- First screen reads as one request setup workflow, not four equal admin tools.
- `Студия обращений` is the visible page title.
- Basic mode has no raw JSON and no nine policy dropdowns.
- The selected request type shows user form, executor routing, SLA, approval, closure and publication readiness.
- Retired/test/smoke entries are excluded from default selection and appear only behind `Показать тестовые и выведенные`.
- Readiness messages use human language and group blockers, recommendations and ready items.
- Expert tools are reachable but do not dominate the basic flow.
- Existing Service Catalog, Forms Builder and Policy Health routes are not removed or renamed.
- Webapp tests and build pass.

## Execution Checkpoints

- [x] Read project workflow, boundaries, context index, testing rules and service catalog/ticket docs.
- [x] Rebuilt context index after stale `PLANS.md` warning.
- [x] Ran `python scripts/bootstrap_web_toolchain.py`.
- [x] Replace the current monolithic page with feature-owned components.
- [x] Update Request Studio tests.
- [x] Update docs/CODEMAP navigation notes.
- [x] Run required verification:
  - `python scripts/verify_workspace.py` -> passed.
  - `pnpm --dir webapp run test` -> 69 files / 325 tests passed.
  - `pnpm --dir webapp run build` -> TypeScript and Vite build passed.
  - `python scripts/build_context_index.py --force` -> rebuilt after docs/plan updates.
- [ ] Browser-check the canonical admin UI if remote/live verification is requested or after deploy.

## Known Constraints

- Direct safe save/publish from Studio may remain a follow-up if no safe endpoint exists for the composed Studio aggregate. In that case the UI must route to expert publication instead of showing a dead disabled button.
- Full CI and full release gate are not part of this iteration unless explicitly requested after a frozen candidate SHA.

## Handoff

Continue in Execute mode. Do not stage unrelated dirty files:

- `pc_agent/ui_gui/tickets_list_model.py`
- existing untracked `artifacts/*`
