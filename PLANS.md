# Request Form Builder Improvement Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` for inline execution or `superpowers:subagent-driven-development` when splitting backend, frontend and tests. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the request form builder safe for production administration by separating draft, validation, publication and preferred rollout, adding business preflight, formal policy references, stable-key rules, process preview and runtime audit snapshots.

**Architecture:** Keep backward compatibility with the existing `request_forms` pack registry and `/api/web/admin/forms/save`, but introduce explicit lifecycle endpoints and a reusable validation/preview service. Move the builder toward a clean contract: forms own fields, conditions and process mappings; policies live as referenced standalone registry records. Ticket creation must snapshot exactly which form/template/policies and computed runtime decisions were used.

**Tech Stack:** aiohttp server, SQLAlchemy/Alembic, Pydantic DTOs in `server/web_api/dto/admin.py`, React + TanStack Query in `webapp/src/features/forms-builder`, Vitest, pytest, project release scripts.

---

## Scope

- Improve the current `/app/admin/forms` constructor and its typed backend boundary.
- Preserve old clients that use `/api/ticket_forms/*`, `/public_api/ticket_forms/current`, `/api/tickets/create`, `/api/tickets/create/preview` and the local Qt agent.
- Keep `request_forms` as the compatibility pack key while introducing a safer lifecycle and clearer standalone registry integration.
- Treat this as a boundary/cross-cutting change: React webapp, typed web API, ticket form registry, helpdesk model registry, ticket creation runtime, docs and tests all need coordinated updates.

## Non-Goals

- Do not remove the legacy `/admin` form builder in the first pass.
- Do not rewrite the whole helpdesk policy registry.
- Do not force all existing legacy packs to migrate before the safer lifecycle is available.
- Do not change public/requester create semantics except to add better source snapshots and diagnostics.

## Current State

- Canonical docs: `server/docs/REQUEST_FORM_BUILDER.md`, `docs/QUICK_LOOKUP.md`, `server/docs/TICKET_SYSTEM.md`, `server/docs/CODEMAP.md`.
- React page: `webapp/src/pages/admin/forms-page.tsx` -> `webapp/src/features/forms-builder/forms-builder-panel.tsx`.
- Frontend API/types: `webapp/src/features/forms-builder/api.ts`.
- Typed backend endpoints:
  - `GET /api/web/admin/forms/current`
  - `POST /api/web/admin/forms/save`
  - `POST /api/web/admin/forms/route-preview`
- Legacy pack endpoints:
  - `GET /api/ticket_forms/current`
  - `GET /public_api/ticket_forms/current`
  - `GET /api/ticket_forms/packs`
  - `GET /api/ticket_forms/packs/{pack_key}/{version}`
  - `POST /api/ticket_forms/packs/save`
  - `PATCH /api/ticket_forms/packs/{pack_key}/{version}/preferred`
- Core backend files:
  - `server/web_api/admin_handlers.py`
  - `server/web_api/dto/admin.py`
  - `server/tickets/form_catalog.py`
  - `server/tickets/request_template_submission.py`
  - `server/tickets/routing_service.py`
  - `server/app/repos/ticket_form_packs_repo.py`
  - `server/app/repos/helpdesk_policy_repo.py`
- Current save path creates a new pack version and immediately makes it preferred. This is convenient but unsafe for unfinished admin edits.
- Current route preview validates one draft form plus example payload and reports matched route/fallback, but it is not a full business preflight or full ticket process preview.
- Current form JSON can embed many policies inline, which risks turning the form into a large monolithic object.
- Runtime already preserves some metadata in `custom_fields.request_template`, but source resolution and computed decisions should be more explicit and queryable.

## Design Decisions

- Add explicit lifecycle states: `draft`, `validated`, `published`, `preferred`, `archived`.
- Keep `/api/web/admin/forms/save` compatible for existing React/tests initially, but add `publish` and `make_preferred` flags and route it internally through the new service.
- Introduce new typed endpoints rather than overloading one save action:
  - `POST /api/web/admin/forms/save-draft`
  - `POST /api/web/admin/forms/validate`
  - `POST /api/web/admin/forms/publish`
  - `PATCH /api/web/admin/forms/preferred`
  - `POST /api/web/admin/forms/process-preview`
- Store drafts explicitly in a new server table instead of relying on browser state only.
- Business validation returns structured errors and warnings; schema validation remains a lower-level guard.
- Forms should reference policies by stable policy keys/codes. Inline policy JSON remains accepted for legacy compatibility, but the UI should guide admins toward refs.
- Stable keys are runtime identifiers. Titles are display-only. Key rename must be treated as migration/alias work, not a normal title edit.
- Field roles must be a server-validated enum. Unknown roles are rejected in new typed endpoints.
- Process preview should reuse the same server-side create-preview/runtime helpers as ticket creation where possible, not duplicate independent calculations in the UI.
- Ticket runtime snapshots must record both source resolution and computed outcomes.

## Target Data Contracts

### Form lifecycle

```json
{
  "draft_id": "uuid",
  "pack_key": "request_forms",
  "base_version": "12",
  "status": "draft",
  "schema_json": {},
  "validation_report": {},
  "published_version": null
}
```

### Save flags compatibility

```json
{
  "title": "Каталог заявок",
  "description": "",
  "forms": [],
  "publish": true,
  "make_preferred": true
}
```

Default behavior for old callers may stay `publish=true` and `make_preferred=true` during transition. New UI should use explicit draft/validate/publish/preferred actions.

### Policy references on a request template

```json
{
  "priority_policy_ref": "incident_priority_v2",
  "routing_policy_ref": "website_routing_v5",
  "sla_policy_ref": "incident_sla_v3",
  "ola_policy_ref": "default_queue_ola_v1",
  "approval_policy_ref": null,
  "diagnostic_policy_ref": "website_diagnostics_v2",
  "closure_policy_ref": "diagnostic_incident_closure_v1",
  "visibility_policy_ref": "default_requester_visibility_v1",
  "notification_policy_ref": "incident_notifications_v1",
  "reporting_policy_ref": "incident_passport_report_v1"
}
```

### Field roles enum

Initial strict role set:

- `routing_field`
- `priority_impact`
- `priority_urgency`
- `priority_importance`
- `diagnostic_input`
- `approval_subject`
- `closure_evidence`
- `reporting_dimension`
- `passport_fact`
- `visibility_public`
- `display_only`

### Runtime resolution snapshot

```json
{
  "request_form": {
    "source": "legacy_pack",
    "pack_key": "request_forms",
    "pack_version": "12",
    "form_key": "website_unavailable",
    "form_title": "Проблема с сайтом"
  },
  "request_template": {
    "key": "website_unavailable",
    "version": "4",
    "form_schema_id": "website_unavailable_form",
    "form_schema_version": "1.0.4"
  },
  "policies": {
    "priority_policy": "incident_priority_v2",
    "routing_policy": "website_routing_v5",
    "sla_policy": "incident_sla_v3",
    "ola_policy": "default_queue_ola_v1",
    "approval_policy": null,
    "diagnostic_policy": "website_diagnostics_v2",
    "closure_policy": "diagnostic_incident_closure_v1",
    "visibility_policy": "default_requester_visibility_v1",
    "notification_policy": "incident_notifications_v1",
    "reporting_policy": "incident_passport_report_v1"
  },
  "computed": {
    "priority": "P1",
    "queue": "networks",
    "matched_routing_rule": "dns_fail_to_networks",
    "approval_required": false,
    "suggested_diagnostics": ["diagnose.website"]
  }
}
```

## Files To Touch

### Backend contracts and lifecycle

- Modify: `server/web_api/dto/admin.py`
  - Add draft, validation report, process preview, preferred update and field-role DTOs.
- Modify: `server/web_api/admin_handlers.py`
  - Add explicit handlers and route-compatible wrappers.
- Modify: `server/routes.py`
  - Register new typed form lifecycle routes.
- Create: `server/tickets/form_lifecycle_service.py`
  - Own save-draft, validate, publish, preferred rollback/update orchestration.
- Create: `server/tickets/form_business_validation.py`
  - Own business preflight rules and report structure.
- Create: `server/tickets/form_process_preview.py`
  - Own full process preview using existing routing/priority/SLA/OLA/approval/diagnostic helpers.
- Modify: `server/tickets/form_catalog.py`
  - Add strict stable-key and role validation helpers while preserving legacy normalization.
- Modify: `server/tickets/request_template_submission.py`
  - Add explicit source resolution fields and snapshot output.
- Modify: `server/tickets/handlers.py`
  - Persist the richer snapshot in create and create-preview responses.
- Modify: `server/app/repos/ticket_form_packs_repo.py`
  - Keep published pack versioning; add helper methods if lifecycle service needs them.
- Create: `server/app/repos/form_drafts_repo.py`
  - Store and retrieve explicit drafts.
- Modify: `server/app/db/models.py`
  - Add `FormDraft` model or equivalent.
- Create: `server/app/db/migrations/versions/<timestamp>_form_builder_drafts.py`
  - Add `form_builder_drafts` table.

### Frontend

- Modify: `webapp/src/features/forms-builder/api.ts`
  - Add lifecycle endpoint clients and types.
- Modify: `webapp/src/features/forms-builder/forms-builder-panel.tsx`
  - Split admin actions into Save Draft, Validate, Publish, Make Preferred, Rollback Preferred and Check Process.
  - Show structured preflight and process-preview results.
  - Use policy refs as the primary UI path.
  - Validate field roles against server-provided enum.
- Modify: `webapp/src/pages/admin/forms-page.tsx`
  - Adjust heading/microcopy if the workflow changes.
- Modify: `webapp/tests/fixtures/support_fixture_server.py`
  - Add fixture responses for the new lifecycle/process-preview endpoints.

### Tests

- Modify: `server/tests/test_web_admin_api.py`
  - Add typed API lifecycle tests.
- Modify: `server/tests/test_ticket_form_packs.py`
  - Add compatibility tests for legacy save and old create flows.
- Modify: `server/tests/test_helpdesk_policy_registry.py`
  - Add policy-ref publication and snapshot tests.
- Add: `server/tests/test_form_business_validation.py`
  - Business preflight unit tests.
- Add: `server/tests/test_form_process_preview.py`
  - Full preview computation tests.
- Modify: `webapp/src/features/forms-builder/forms-builder-panel.test.tsx`
  - Add UI tests for draft/validate/publish/preferred/process preview.
- Modify: `webapp/src/pages/admin/index.test.tsx`
  - Keep route/workspace integration coverage.

### Docs

- Modify: `server/docs/REQUEST_FORM_BUILDER.md`
- Modify: `server/docs/TICKET_SYSTEM.md`
- Modify: `server/docs/CODEMAP.md`
- Modify: `docs/QUICK_LOOKUP.md`
- Modify: `docs/ARCHITECTURE_BOUNDARIES.md` only if the boundary definitions change.
- Modify: `pc_agent/docs/CODEMAP.md` if agent-facing create payload/snapshot behavior changes.

## Phase 0: Baseline And Safety

- [x] Run `python scripts/task_intake.py --task "forms builder lifecycle validation process preview policy refs runtime snapshot"`.
- [x] Run `python scripts/build_context_pack.py --topic "forms builder lifecycle validation process preview policy refs runtime snapshot"`.
- [x] Run `python scripts/search_context_index.py "forms builder lifecycle validation process preview policy refs runtime snapshot" --profile contract`.
- [x] Run `python scripts/bootstrap_web_toolchain.py` before frontend commands.
- [x] Capture `git status --short`; ignore unrelated dirty files and do not stage them.
- [x] Run current focused tests before edits/while establishing baseline:
  - `python -m pytest server/tests/test_web_admin_api.py::test_web_admin_forms_current_returns_typed_payload -v --tb=short`
  - `python -m pytest server/tests/test_ticket_form_packs.py -q`
  - `pnpm --dir webapp exec vitest run src/features/forms-builder/forms-builder-panel.test.tsx`

## Phase 1: Explicit Draft / Publish / Preferred Lifecycle

- [x] Add `form_builder_drafts` DB model and migration:
  - columns: `id`, `pack_key`, `base_version`, `status`, `schema_json`, `validation_report_json`, `published_version`, `created_by`, `updated_by`, `created_at`, `updated_at`, `published_at`.
  - indexes: `(pack_key, status)`, `updated_at`.
- [x] Add `FormDraftsRepo` with get/upsert/mark_published methods.
- [x] Add lifecycle DTOs:
  - `AdminFormsDraftSaveRequest`
  - `AdminFormsDraftSaveResult`
  - `AdminFormsValidateRequest`
  - `AdminFormsValidateResult`
  - `AdminFormsPublishRequest`
  - `AdminFormsPublishResult`
  - `AdminFormsPreferredUpdateRequest`
  - `AdminFormsPreferredUpdateResult`
- [x] Implement `server/tickets/form_lifecycle_service.py`.
  - Lifecycle orchestration is extracted from typed admin handlers; handlers keep thin compatibility wrappers for existing tests and monkeypatch contracts.
- [x] Register typed routes:
  - `POST /api/web/admin/forms/save-draft`
  - `POST /api/web/admin/forms/validate`
  - `POST /api/web/admin/forms/publish`
  - `PATCH /api/web/admin/forms/preferred`
- [x] Keep `POST /api/web/admin/forms/save` compatible:
  - old behavior remains publish + preferred unless flags say otherwise.
  - new flags: `publish`, `make_preferred`.
- [x] Add server tests:
  - draft save does not change preferred version.
  - validate does not publish.
  - publish creates a pack version but does not make it preferred when `make_preferred=false`.
  - preferred update can point to an existing published version.
  - old `/save` still creates and prefers a version.
- [x] Update React API clients and tests.
- [x] Update UI actions:
  - Save Draft
  - Validate
  - Publish
  - Make Preferred
  - Rollback Preferred through selecting a previous version in the version list.
- [x] Verification:
  - `python -m pytest server/tests/test_web_admin_api.py -k "forms" -v --tb=short`
  - `pnpm --dir webapp exec vitest run src/features/forms-builder/forms-builder-panel.test.tsx`

## Phase 2: Business Dry-Run Validation Report

- [x] Create `server/tickets/form_business_validation.py`.
- [x] Define report shape:
  - `errors[]` with `code`, `message`, `path`, `severity`, `blocking`.
  - `warnings[]` with `code`, `message`, `path`, `recommendation`.
  - `summary` with counts and `can_publish`.
- [x] Add blocking validations:
  - required field hidden by impossible or missing condition.
  - `visible_when.field` references a missing field.
  - routing policy references a missing queue.
  - SLA policy id/ref points to an inactive or unknown policy record.
  - OLA policy ref is missing or inactive when queue OLA is enabled.
  - diagnostic playbook key is missing.
  - diagnostic playbook key exists but is not diagnostic-safe.
  - approval policy has no approver source when `required=true`.
  - closure policy requires evidence but no field has `closure_evidence`.
  - policy refs point to inactive or unknown policy records.
- [x] Add warning validations:
  - no impact/urgency/importance fields.
  - required field has no help text.
  - public title/title is missing or too generic.
  - no route-preview/process-preview sample values saved.
  - field key changed compared with base version without alias/migration note.
- [x] Wire validation into:
  - `POST /api/web/admin/forms/validate`
  - `POST /api/web/admin/forms/publish`
  - legacy `/save` before publishing.
- [x] UI: show grouped preflight report before publish through the existing validation report panel; backend publish blocks on blocking errors.
- [x] Tests:
  - `server/tests/test_form_business_validation.py`
  - `server/tests/test_ticket_form_packs.py` integration coverage for `/validate` warnings and `/publish` blocking invalid queue refs.
  - Existing React tests cover validation report rendering; add blocked-publish-specific UI test in a later UI tightening pass if the frontend flow changes.
- [x] Verification completed in this phase:
  - `python -m pytest server/tests/test_form_business_validation.py -q --tb=short`
  - `python -m pytest server/tests/test_ticket_form_packs.py -k "business_preflight or missing_business_refs" -q --tb=short`
  - `python -m pytest server/tests/test_ticket_form_packs.py -k "preflight_metadata or business_preflight or missing_business_refs" -q --tb=short`
  - `python -m pytest server/tests/test_web_admin_api.py -k "forms" -v --tb=short`
- [x] Full Phase 2 verification after latest additions:
  - `python -m pytest server/tests/test_ticket_form_packs.py -q`
  - `pnpm --dir webapp exec vitest run src/features/forms-builder/forms-builder-panel.test.tsx`
  - `python scripts/verify_workspace.py`

## Phase 3: Policy References And De-Monolith Contract

- [x] Add canonical policy-ref fields in DTO and serializer:
  - `priority_policy_ref`
  - `routing_policy_ref`
  - `sla_policy_ref`
  - `ola_policy_ref`
  - `approval_policy_ref`
  - `diagnostic_policy_ref`
  - `closure_policy_ref`
  - `visibility_policy_ref`
  - `notification_policy_ref`
  - `reporting_policy_ref`
- [x] Keep existing inline policy JSON for legacy reads and compatibility.
- [x] Add backend normalization:
  - prefer explicit refs when both ref and inline JSON exist.
  - include source in validation report for missing/inactive `policy_ref` errors.
- [x] Update publish-from-form path so it can attach explicit refs to request templates and skip publishing inline legacy config for those kinds.
- [x] UI:
  - show policy refs as the primary mode.
  - keep advanced JSON/edit inline policies under an explicit advanced section.
  - show which templates will be affected by changing an active policy.
- [x] Tests:
  - [x] policy refs override inline legacy config.
  - [x] missing/inactive refs appear in validation report with `source=policy_ref`.
  - [x] publish-from-form writes expected refs.
  - [x] UI tests for primary policy-ref controls and affected-template hints.
- [x] Verification:
  - [x] `python -m pytest server/tests/test_helpdesk_policy_registry.py -k "prefers_policy_refs or publish_from_form" -q --tb=short`
  - [x] `python -m pytest server/tests/test_ticket_form_packs.py -k "canonical_policy_refs or policy_refs or request_template" -q --tb=short`
  - [x] `pnpm --dir webapp exec vitest run src/features/forms-builder/forms-builder-panel.test.tsx`
  - [x] `pnpm --dir webapp run build`
  - [x] `python scripts/verify_workspace.py`

## Phase 4: Stable Keys And Field Role Enum

- [x] Define server role enum in one place, preferably `server/tickets/form_catalog.py` or a new small module imported by DTO/business validation.
- [x] Extend typed capabilities payload with role options and descriptions.
- [x] Enforce stable keys on new lifecycle endpoints:
  - [x] form key uniqueness per pack.
  - [x] field key uniqueness per form.
  - [x] title can change freely.
  - [x] key change compared with base version requires explicit `alias_from` or migration note.
- [x] Add role validation:
  - [x] reject unknown roles.
  - [x] only one `priority_impact`, `priority_urgency`, `priority_importance` per template unless policy explicitly allows multiple.
  - [x] `diagnostic_input` requires mapping to a playbook parameter when diagnostic auto-run is configured.
  - [x] `approval_subject` must be compatible with user/service/role/group source.
  - [x] `closure_evidence` must be compatible with closure policy evidence requirements.
- [x] UI:
  - [x] replace free-form role strings with controlled options.
  - [x] show singleton priority role conflicts in preflight.
  - [x] add inline field-level role conflict hints near affected fields.
- [x] Tests:
  - [x] role enum accepts valid roles and rejects unknown roles.
  - [x] duplicate singleton priority roles block publish.
  - [x] old legacy packs with old `field_roles` still load.
- [x] Verification:
  - [x] `python -m pytest server/tests/test_ticket_form_packs.py -k "field_roles or form_pack_schema or public_ticket_forms_current" -v --tb=short`
  - [x] `python -m pytest server/tests/test_form_business_validation.py -q --tb=short`
  - [x] `python -m pytest server/tests/test_web_admin_api.py -k "forms" -v --tb=short`
  - [x] `pnpm --dir webapp exec vitest run src/features/forms-builder/forms-builder-panel.test.tsx`
  - [x] `pnpm --dir webapp run build`
  - [x] `python scripts/verify_workspace.py`

## Phase 5: Full Process Preview

- [x] Create `server/tickets/form_process_preview.py`.
- [x] Add `POST /api/web/admin/forms/process-preview`.
- [x] Input:
  - draft form/template
  - sample `form_payload`
  - optional requester/device context
  - optional source version/draft id
- [x] Output:
  - `ticket_type`
  - `request_kind`
  - computed priority and explanation
  - matched routing rule and queue
  - SLA policy and due-date preview
  - OLA policy and target preview
  - approval required/current approver source summary
  - suggested diagnostics and consent gates
  - closure policy checklist
  - visibility/public status preview
  - notification plan preview
  - warnings/errors from business validation that affect the preview.
- [x] Reuse existing runtime helpers where possible:
  - routing: `server/tickets/routing_service.py`
  - priority: `server/tickets/priority_policy.py`
  - SLA: `server/tickets/sla_service.py`
  - OLA: `server/tickets/ola_service.py`
  - approval: `server/tickets/approval_policy.py`
  - diagnostics: `server/tickets/diagnostic_policy.py`
  - closure: `server/tickets/closure_policy.py`
  - visibility: `server/tickets/visibility_policy.py`
  - notifications: `server/tickets/notification_service.py`
- [x] UI:
  - extend route preview with `Проверить процесс`.
  - keep route preview available as the existing `Проверить` action.
  - show an admin-readable summary: type, priority, queue, matched routing rule, SLA/OLA, approval, diagnostics, closure and notifications.
- [x] Tests:
  - process preview returns queue and matched routing rule.
  - process preview returns priority and SLA for sample answers.
  - process preview reports approval and diagnostic consent requirements.
  - process preview has no DB side effects.
  - React panel calls `/api/web/admin/forms/process-preview` and renders the process summary.
- [x] Verification:
  - `python -m pytest server/tests/test_form_process_preview.py -v --tb=short`
  - `python -m pytest server/tests/test_web_admin_api.py -k "process_preview or route_preview" -v --tb=short`
  - `pnpm --dir webapp exec vitest run src/features/forms-builder/forms-builder-panel.test.tsx`
  - `pnpm --dir webapp run build`

## Phase 6: Runtime Resolution Transparency And Audit Snapshot

- [x] Extend `server/tickets/request_template_submission.py` result with:
  - `resolved_from`
  - `resolved_pack_key`
  - `resolved_pack_version`
  - `resolved_template_key`
  - `resolved_template_version`
  - `resolved_form_schema_id`
  - `resolved_form_schema_version`
- [x] Extend ticket create/custom fields snapshot:
  - `custom_fields.request_form`
  - `custom_fields.request_template`
  - `custom_fields.request_template.policy_refs`
  - `custom_fields.request_template.effective_policy_sources`
  - `custom_fields.request_template.effective_policy_snapshots`
  - `custom_fields.request_template.computed`
- [x] Ensure create-preview returns the same source/computed explanation without creating a ticket.
- [x] Add support/detail exposure rules:
  - support/admin keep the internal `request_template` snapshot through existing `custom_fields`.
  - requester/public visibility hides `custom_fields.request_template` so inline policy JSON and effective policy snapshots are not leaked.
- [x] Logging:
  - no new raw form payload logging was added.
  - no token logging was added.
- [x] Tests:
  - legacy pack source snapshot.
  - standalone registry source snapshot.
  - computed priority/queue/rule snapshot.
  - requester/public payload does not leak internal policy JSON.
- [x] Verification:
  - `python -m pytest server/tests/test_ticket_form_packs.py -k "source_snapshot or computed_snapshot or request_template_key or create_preview" -v --tb=short`
  - `python -m pytest server/tests/test_ticket_priority_policy.py -k "create_preview or overlays_priority_policy or standalone_registry_sla" -v --tb=short`
  - `python -m pytest server/tests/test_helpdesk_policy_registry.py -k "request_template_policy_ref_snapshot or resolves_request_template_policy_refs_before_inline_config" -v --tb=short`

## Phase 7: Docs, Browser Verification And Release Gate

- [x] Update docs:
  - `server/docs/REQUEST_FORM_BUILDER.md`
  - `server/docs/TICKET_SYSTEM.md`
  - `server/docs/CODEMAP.md`
  - `docs/QUICK_LOOKUP.md`
  - `pc_agent/docs/CODEMAP.md` reviewed; no update needed because the agent-facing create payload did not change.
- [x] Run workspace verification:
  - `python scripts/verify_workspace.py`
- [x] Run focused server tests:
  - `python -m pytest server/tests/test_web_admin_api.py server/tests/test_ticket_form_packs.py server/tests/test_helpdesk_policy_registry.py server/tests/test_form_business_validation.py server/tests/test_form_process_preview.py -v --tb=short`
- [x] Run frontend tests/build:
  - `pnpm --dir webapp exec vitest run src/features/forms-builder/forms-builder-panel.test.tsx src/pages/admin/index.test.tsx`
  - `pnpm --dir webapp run build`
- [x] Run browser verification after deploy/release on the canonical stand:
  - opened `http://192.168.100.17:8666/admin` and navigated to `/app/admin/forms`;
  - confirmed the lifecycle UI separates `Сохранить черновик`, `Проверить публикацию`, `Опубликовать` and per-version `Сделать preferred`;
  - saved a draft without changing preferred; `/api/web/admin/forms/save-draft` returned `200 OK`;
  - validated the draft and saw the structured preflight report; `/api/web/admin/forms/validate` returned `200 OK` and reported blocking business validation instead of a server error;
  - ran process preview with sample answers and confirmed ticket type, priority, queue, routing rule, SLA/OLA, approval, diagnostics, closure, visibility and notification summary are visible; `/api/web/admin/forms/process-preview` returned `200 OK`;
  - checked browser console/network: no console warnings/errors and no failed lifecycle requests;
  - live publish, preferred switch and rollback were intentionally not executed on the canonical stand because they mutate the active `request_forms` catalog.
- [x] Stop remote server after verification unless explicitly asked to leave it running.

## Rollout Strategy

- Phase 1 keeps old `/save` behavior so the current UI and tests can continue while new lifecycle actions are added.
- Phase 2 adds preflight report but can initially warn-only for selected legacy gaps; make blocking rules strict for new draft/publish endpoints first.
- Phase 3 policy refs should support dual read/write until all active forms have refs.
- Phase 4 role enum should reject unknown roles for new saves but tolerate old packs on read with warnings.
- Phase 5 process preview is additive.
- Phase 6 runtime snapshots are additive and should not change ticket routing decisions by themselves.

## Risks

- DB migration risk: drafts table is new but should not mutate existing `ticket_form_packs`.
- UI complexity risk: split workflow can overwhelm admins. Keep primary actions obvious: Save Draft, Validate, Publish, Make Preferred.
- Compatibility risk: old agent/public clients must keep working with `request_forms`.
- Policy-ref migration risk: inline legacy policies and refs may disagree. The plan chooses refs as authoritative and reports the source.
- Runtime audit risk: snapshots can expose too much. Support views may show explanations, requester views must stay filtered.

## Current Handoff

- Phase 1 lifecycle is implemented and covered:
  - new draft table/model/migration and `FormDraftsRepo`;
  - typed `/api/web/admin/forms/save-draft`, `/validate`, `/publish`, `/preferred`;
  - compatible `/api/web/admin/forms/save` with `publish` and `make_preferred` defaults;
  - React API clients and UI buttons for saving draft, validating, publishing and setting preferred from version history.
- Focused verification already passed during Phase 1:
  - `python -m pytest server/tests/test_web_admin_api.py -k "forms" -v --tb=short`
  - `python -m pytest server/tests/test_ticket_form_packs.py -q`
  - `pnpm --dir webapp exec vitest run src/features/forms-builder/forms-builder-panel.test.tsx`
- Phase 2 business preflight is now attached to the lifecycle service:
  - `server/tickets/form_business_validation.py` emits structured errors, warnings and `can_publish`;
  - `/api/web/admin/forms/validate` returns DB-backed business warnings/errors;
  - `/api/web/admin/forms/publish` and compatible `/api/web/admin/forms/save` block publication on business errors before a pack version is created.
- Phase 2 latest additions:
  - OLA-enabled queues now require an OLA policy;
  - playbooks used by diagnostic triggers must exist and have a diagnostic domain;
  - process-aware forms warn when no route/process preview sample is saved;
  - base-version comparison warns when field keys disappear without alias or migration note.
- Phase 3 backend slice is implemented:
  - typed forms accept and preserve canonical `*_policy_ref` fields;
  - form-pack normalization mirrors refs into `policy_refs` and `*_policy_code` for existing runtime/registry surfaces;
  - business preflight validates both canonical refs and legacy `policy_refs` dict entries;
  - publish-from-form attaches explicit refs to request templates and does not republish inline JSON for those policy kinds.
- Phase 3 UI slice is implemented:
  - the visual template constructor shows `Policy refs` as the primary contract fields for priority/routing/SLA/OLA/approval/diagnostic/closure/visibility/notification/reporting;
  - inline policy JSON is explicitly labeled as `Advanced inline policy JSON`;
  - entered refs show active request templates already using the same policy code;
  - the UI test covers `Routing policy ref`, affected-template hint and draft payload serialization.
- Phase 3 final verification after the UI/doc update passed:
  - `pnpm --dir webapp exec vitest run src/features/forms-builder/forms-builder-panel.test.tsx`
  - `pnpm --dir webapp run build`
  - `python -m pytest server/tests/test_form_business_validation.py -q --tb=short`
  - `python -m pytest server/tests/test_helpdesk_policy_registry.py -k "prefers_policy_refs or publish_from_form" -q --tb=short`
  - `python -m pytest server/tests/test_ticket_form_packs.py -k "canonical_policy_refs or policy_refs or request_template" -q --tb=short`
  - `python -m pytest server/tests/test_web_admin_api.py -k "forms" -v --tb=short`
  - `python scripts/verify_workspace.py`
- Worktree already had unrelated dirty files before this plan update. Do not revert or stage unrelated files. Current task-owned files are the forms lifecycle backend/frontend/tests, draft repo/migration and this `PLANS.md`.
