# Unified service scenarios implementation plan

> For agentic workers: use superpowers:executing-plans inline. User requests sequential execution without additional approval stages.

**Goal:** One map-based creation flow with a canonical server projection and safe form conversion.
**Architecture:** Extend existing DTOs/drafts/versions and canonical validation. Reuse catalog bindings, policies, session pinning and confirmed publication.
**Tech Stack:** Python/Pydantic/aiohttp/SQLAlchemy; React 19/React Flow 12; PyYAML 6.
**Spec:** docs/superpowers/specs/2026-10-13-unified-service-scenarios-design.md

## Global constraints

- No new storage layer or policy engine; no production or Endpoint modifications.
- Preserve v1 snapshots, published versions and existing tickets/sessions.
- Preserve unrelated local guide edits and untracked artifacts.
- Every change has focused risk-based tests; real browser acceptance before completion.

## Review focus

- Hidden or backtracked answers must not contribute processing effects.
- Import must never change catalog identity, publish, or mutate on validation failure.
- Unsupported legacy features must block conversion, not disappear.
- Multiple entry routes must validate only their visited questions.
- Concurrent edits and replayed conversion requests must preserve revisions and data.

### Task 1: Versioned model and server projection

Files: server/web_api/dto/request_scenario.py; server/tickets/request_scenario_document.py;
server/tickets/request_scenario_submission.py; server/tickets/request_scenario_processing.py;
server/tickets/request_template_submission.py; canonical requester/preview callers.
Produces: parse_scenario_document(text, format), export_scenario_document(definition, format),
derive_scenario_form(definition, state), apply_scenario_processing_facts(validated, facts).
- [x] Add failing strict round-trip/projection/effects tests and observe RED.
- [x] Implement v2 additive fields, bounded interchange, server-generated validation schema and existing-policy adapter.
- [x] Run focused DTO/runtime/submission/processing tests; expected PASS.

### Task 2: Internal creation and safe conversion

Files: server/app/repos/request_scenario_repo.py; server/tickets/request_scenario_conversion.py;
server/web_api/request_scenario_admin_handlers.py; server/routes.py; admin DTOs.
Consumes Task 1 v2 definition. Produces create_service(definition), convert_offering(code),
document validation/export endpoints and explicit conversion report.
- [x] Add failing conversion/creation/API tests and observe RED.
- [x] Implement automatic catalog binding, idempotent conversion and guarded interchange without automatic publication.
- [x] Run focused repository/API/publication/session tests; expected PASS.

### Task 3: Single map authoring flow

Files: webapp/src/features/request-template-studio/{scenario-contract,use-scenario-editor,
scenario-map-canvas,scenario-map-workbench,scenario-entry-inspector,scenario-purpose,
scenario-field-editor,scenario-edge-inspector,catalog-services-workbench,scenario-api}.tsx/ts;
webapp/src/pages/admin/request-template-studio-page.tsx; new document/effects panels.
Consumes Task 1/2 contracts. Produces direct create, visible Start, named service edges,
minimal inspectors, five kinds, advanced JSON/YAML interchange and conversion action.
- [x] Add focused failing creation/map/inspector tests and observe RED.
- [x] Implement UI on current design system, preserving node layout and history.
- [x] Run focused frontend tests and build; expected PASS.

### Task 4: Acceptance and documentation

Files: docs/GUIDED_REQUEST_STUDIO_ADMIN.md; server/docs/CODEMAP.md; PLANS.md;
focused browser tests and staging evidence under tmp/.
- [x] Run workspace sanity, regression checks and diff check; expected PASS.
- [x] Review complete task diff once, fix material findings with regression tests.
- [ ] Commit task files only, deploy through reviewed staging procedure, verify browser creation/publication/interchange and conversion report.
- [ ] Update guide for the actual delivered flow and report exact SHA, tests and remaining unsupported conversions.
