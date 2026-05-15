# P2.1 Knowledge Platform Acceptance Hardening

Status: implementation complete; local verification complete; remote/browser signoff pending. This is acceptance hardening for the already implemented P2 knowledge platform, not a scope expansion. P0/P0.1/P1/P1.1 contracts remain baseline and must not be weakened.

Classification: cross-cutting / release-control. Scope touches knowledge lifecycle/API, ACL and safe projection boundaries, DB migrations, React admin/support routes, passport publication governance, docs/CODEMAP and final verification.

## Discovery

- Admin publish flow has a real blocker: `webapp/src/features/knowledge/knowledge-admin-panel.tsx` publishes `selectedItem.current_version_id`, so a newly created draft item with a newly created version cannot be published from the UI because `current_version_id` is still null.
- `KnowledgeRepo.create_version()` returns the created version id, but the UI does not retain it as a publish target. There is no repo/API method to list versions or choose latest draft/current published/selected version.
- Web knowledge management endpoints currently call `KnowledgeRepo.list_items(include_archived=True)` and `get_item(...)` without role-aware visibility filtering, so direct-id/list access can leak `admin_internal` or `security_restricted` items to support/auditor paths.
- `actor_visible_visibilities()` currently treats auditor as all-visible. P2.1 policy will make auditor read-only and exclude `admin_internal` / `security_restricted` unless a future explicit security role policy says otherwise.
- Search and suggestions already use visibility filtering before requester-safe results, but shared contract constants need the same support/auditor policy and direct-id hardening.
- `KnowledgeGraphService.neighborhood()` filters edge visibility before checking the neighbor node visibility, which can leak an edge to an invisible node.
- Graph node list and ingestion job list handlers are admin/support authenticated, but need role-aware filtering/redaction and mutation visibility checks.
- Knowledge metrics backend returns nested `deflection` / `helpfulness`, while the web UI expects flat aliases such as `deflection_events`; both shapes must be supported.
- Passport draft service records stale warnings only as free-form metadata. `KnowledgeRepo.publish_item()` currently checks reviewer/version ownership only and can publish stale passport drafts without explicit acknowledgement.
- Migration `083` created the knowledge tables. Enum-like graph, feedback and ingestion fields still need DB CHECK constraints and matching SQLAlchemy model constraints.
- `/app/admin/knowledge` is the governance route. `/app/knowledge` must remain a real role-appropriate entry point, not a misleading placeholder or unrestricted admin surface.

## Design Decisions

- Add version listing and explicit publish target selection. Publishing always takes an explicit `version_id`; `current_version_id` is only the current published pointer.
- Support can read/requester-safe plus `support_internal` knowledge and can mutate only non-admin/non-security visibility items. Auditor is read-only and sees requester-safe/support/auditor-readable knowledge, not admin/security restricted items.
- Admin can manage normal knowledge, including `admin_internal`; `security_restricted` remains admin-accessible until a dedicated security role exists, and the docs will state this decision.
- Direct-id denial uses the project’s existing validation/404-style behavior without leaking item titles/snippets.
- Passport-derived items require lifecycle gates: reviewer, non-empty version, non-archived item, publishable visibility, and explicit stale acknowledgement when `passport_stale` / stale warnings are present.
- Metrics API returns canonical nested fields plus flat compatibility aliases. The UI prefers nested fields and falls back to aliases.
- DB constraints are added in a new Alembic revision `084`, with safe named CHECK constraints and downgrade drops.

## Implementation Plan

- [x] Read mandatory project docs and run intake/context commands.
- [x] Map acceptance blockers in `PLANS.md`.
- [x] Add/extend failing tests for publish version flow, ACL/direct-id hardening, metrics shape, passport stale gates, graph/ingestion visibility and DB constraints.
- [x] Implement role-aware visibility/mutation helpers and wire repo/API endpoints to them.
- [x] Add version list/latest APIs and fix React admin publish state.
- [x] Add publish gate validation and stale passport acknowledgement support.
- [x] Align metrics backend and UI DTO/display.
- [x] Add migration `084` and SQLAlchemy CHECK constraints for graph/feedback/ingestion enums.
- [x] Harden graph neighborhood/list and ingestion job visibility/redaction.
- [x] Ensure `/app/knowledge` is role-appropriate and docs match route behavior.
- [x] Update docs, CODEMAP, navigation/context index.
- [x] Run targeted tests, P0/P1 regressions, full server/agent suites, webapp build/typecheck and workspace verification.
- [ ] Run remote/browser signoff on the deployed stack.

## Verification Plan

- Targeted P2.1 tests: `test_knowledge_publish_flow.py`, `test_knowledge_acl_hardening.py`, `test_knowledge_db_constraints.py`, plus existing knowledge repo/API/metrics/graph/ingestion/passport tests.
- Regressions: P0/P0.1 ticket contract/public queue/workflow/policy health/create tests and P1/P1.1 service catalog fallback/preview/publication/API/create/reports tests.
- Agent: knowledge suggestions and service catalog wizard/helper suites.
- Static/UI: `compileall`, `git diff --check`, `verify_workspace.py`, `build_context_index.py --force`, `pnpm --dir webapp build`, typecheck/lint if present.
- Browser signoff on `https://192.168.100.17:9443/admin`: `/app/admin/knowledge`, `/app/knowledge`, `/app/help`, support ticket knowledge panel and direct-id/restricted visibility checks.

## Verification Results

- Targeted P2/P2.1 knowledge suite: `python -m pytest server\tests\test_knowledge_contract_no_db.py server\tests\test_knowledge_migration.py server\tests\test_knowledge_repo.py server\tests\test_knowledge_visibility.py server\tests\test_knowledge_acl_hardening.py server\tests\test_knowledge_search.py server\tests\test_knowledge_suggestions.py server\tests\test_knowledge_feedback.py server\tests\test_knowledge_graph.py server\tests\test_knowledge_ingestion.py server\tests\test_knowledge_passport_draft.py server\tests\test_knowledge_api.py server\tests\test_ticket_knowledge_links_compat.py server\tests\test_knowledge_metrics.py server\tests\test_knowledge_publish_flow.py server\tests\test_knowledge_db_constraints.py -q --tb=short` -> 33 passed.
- P0/P0.1 regression: `python -m pytest server\tests\test_ticket_status_usage_no_db.py server\tests\test_public_queue_privacy.py server\tests\test_workflow_side_effect_observability.py server\tests\test_policy_health_service.py server\tests\test_policy_health_api.py server\tests\test_ticket_create_contracts.py -q --tb=short` -> 32 passed, 1 existing shared-DB cleanup warning.
- P1/P1.1 service catalog regression: `python -m pytest server\tests\test_service_catalog_fallback.py server\tests\test_service_catalog_preview.py server\tests\test_service_catalog_repo.py server\tests\test_service_catalog_api.py server\tests\test_ticket_create_service_catalog.py server\tests\test_reports_service_catalog.py server\tests\test_policy_health_service_catalog.py -q --tb=short` -> 14 passed. The acceptance-list name `test_service_catalog_publication.py` is not present in this checkout; publication behavior is covered by `test_service_catalog_repo.py`.
- Form/process regression: `python -m pytest server\tests\test_form_process_preview.py server\tests\test_form_business_validation.py server\tests\test_helpdesk_policy_registry.py -q --tb=short` -> 44 passed.
- Agent focused regression: `python -m pytest pc_agent\tests\test_knowledge_suggestions.py pc_agent\tests\test_ticket_api_client_service_catalog.py pc_agent\tests\test_chat_panel_helpers.py pc_agent\tests\test_ticket_api_client_attachments.py -q --tb=short` -> 137 passed. The acceptance-list name `test_ticket_create_wizard_service_catalog.py` is not present in this checkout.
- Full agent suite: `python -m pytest pc_agent\tests -m "not manual" -q --tb=short` -> 309 passed, 4 deselected.
- Full server suite: `python -m pytest server\tests -m "not manual" -q --tb=short` -> 923 passed, 11 warnings in 0:57:36. Warnings are `NotAppKeyWarning` in `tests/test_web_session_api.py`.
- Static/build: `python -m compileall -q server pc_agent scripts`, `git diff --check`, `python scripts\verify_workspace.py`, `python scripts\build_context_index.py --force`, `python scripts\bootstrap_web_toolchain.py`, and `pnpm --dir webapp build` all completed successfully. `webapp/package.json` has no separate `typecheck` or `lint` script; build includes `tsc --noEmit`.
- A parallel DB pytest attempt hit transient `ConnectionDoesNotExistError` from simultaneous shared test database cleanup; the same tests passed when rerun sequentially.

## Rollback Notes

- Code rollback plus Alembic downgrade of revision `084` removes only new CHECK constraints; P2 schema/data remains intact.
- If publish governance blocks live content unexpectedly, admins can keep items in draft/in-review while correcting reviewer/version/stale acknowledgement metadata.
- ACL tightening may hide previously visible internal items from support/auditor; this is intentional P2.1 behavior and should be resolved by changing item visibility, not by bypassing filters.

# P2 Universal Knowledge Platform + Helpdesk Deflection

Status: implementation complete; verification in progress. P0/P0.1/P1/P1.1 remain baseline contracts and must not be weakened. This phase is cross-cutting / release-control because it adds schema, backend services, web/API surfaces, requester self-service, support workspace knowledge usage, agent GUI knowledge suggestions, docs and verification gates.

Goal: build a universal company knowledge platform, then use it for helpdesk self-service deflection and support knowledge workflows:

`Knowledge Space -> Knowledge Item -> Version -> Chunks/Search -> Bindings/Graph -> Feedback/Metrics -> Helpdesk Deflection`

## Discovery

- Existing helpdesk KB linkage is `ticket_kb_links` through `POST/GET/DELETE /api/tickets/{ticket_id}/kb_links`; it stores `article_ref`, title/source/creator and is used by support suggestions. It must remain compatible.
- Existing support suggestions are not a platform: `server/tickets/knowledge_provider.py` combines legacy ticket links, a JSON catalog file and similar-ticket search into a support-only payload.
- Existing support route `GET /api/web/support/tickets/{ticket_id}/knowledge-suggestions` returns articles/similar tickets/diagnostics for the support workspace. It can become a compatibility wrapper over the P2 suggestion service.
- Existing passport draft route `POST /api/web/support/tickets/{ticket_id}/passport/knowledge-draft` currently returns a draft payload only; it does not persist a knowledge item/version, lifecycle state, bindings or review requirement.
- Ticket resolution passports exist in `ticket_resolution_passports`; evidence and action logs already provide source material for draft-from-passport.
- Service Catalog is first-class: `helpdesk_services`, `helpdesk_service_offerings`, explicit ticket `service_code`, `offering_code`, `request_type`, `reporting_category` and `custom_fields.service_catalog`.
- Requester portal `/app/help` is catalog-first and runtime-preview-backed, but it does not call knowledge suggestions or record deflection/failed-article attempts.
- Agent GUI already has explicit Service -> Offering -> Dynamic form -> Preview -> Submit and HTTP create/preview boundaries, but no knowledge suggestion or feedback calls. No Protocol V3 change is needed.
- Support workspace `/app/tickets/:ticketId` already has a Knowledge right tab and a passport draft action, but it is tied to the legacy support suggestion payload.
- Admin webapp has an old `/app/knowledge` route/name in navigation, but there is no universal `/app/admin/knowledge` management surface for spaces/items/versions/graph/ingestion/metrics.
- No first-class knowledge tables exist yet: no spaces, universal items, item versions, chunks, bindings, graph nodes/edges, ingestion jobs or feedback events.
- Context index reported stale state for `PLANS.md`; rebuild after docs/code updates with `python scripts/build_context_index.py --force`.

## Design Decisions

- `knowledge_item` is the universal object. `article` is one `item_type`, not the whole model.
- PostgreSQL remains the foundation for P2. Add relational graph tables and chunk/search tables; do not add mandatory Neo4j, Elastic or OpenSearch.
- Search starts with PostgreSQL-compatible filters plus LIKE/ILIKE/full-text-ready chunk data. Vector/embedding fields remain nullable metadata/future-ready only if the project already supports them.
- ACL is enforced before search results, suggestions, graph expansion and any retrieval/RAG foundation. Requester/agent projections only return published requester-safe knowledge.
- Keep `ticket_kb_links` endpoints and events compatible. If normalized ticket-knowledge links are added, legacy endpoints remain wrappers.
- Imported/manual text and markdown ingestion creates draft items/versions/chunks and requires review. No imported document auto-publishes.
- Passport-to-knowledge creates a draft item/version with source refs, service/offering bindings and stale warnings; it never auto-publishes and must not invent facts outside passport/evidence data.
- Agent integration uses HTTP API methods on `TicketApiClient` for suggestions/feedback and sends `knowledge_attempts` in the existing create payload. Protocol V3 is unchanged.
- Requester/self-service deflection records feedback and can avoid ticket creation only after explicit user action. Urgent or fallback ticket creation remains unblocked.

## Implementation Phases

- [x] Run mandatory intake/context commands and read canonical docs.
- [x] Perform discovery of `kb_links`, passport draft, service catalog, requester help, support workspace and agent GUI boundaries.
- [x] Add TDD red tests for knowledge contracts, repo/lifecycle, visibility, search, suggestions, feedback, graph, ingestion, passport draft, API, metrics and compatibility.
- [x] Add Alembic revision `083` for knowledge spaces/items/versions/chunks/bindings/graph/feedback/ingestion and normalized ticket knowledge links.
- [x] Implement backend contracts, repository, visibility, serializers, search, suggestions, feedback, graph, ingestion, passport draft and metrics services.
- [x] Add admin/support/requester API endpoints and route registration with RBAC and safe projections.
- [x] Integrate requester `/app/help` suggestions, deflection, not-helpful continuation and `knowledge_attempts`.
- [x] Extend agent GUI/API client with safe suggestions, feedback and `knowledge_attempts` fallback behavior.
- [x] Add `/app/admin/knowledge` and strengthen support workspace Knowledge panel/passport draft flow.
- [x] Integrate Service Catalog/Policy Health knowledge gap indicators.
- [x] Update docs, CODEMAP, navigation catalog and context index.
- [ ] Run targeted tests, P0/P1 regressions, agent tests, webapp build/typecheck, workspace verification, full suite and browser signoff.

## API / UI Contracts

- Admin/support management:
  - `/api/web/knowledge/spaces*`
  - `/api/web/knowledge/items*`
  - `/api/web/knowledge/graph/*`
  - `/api/web/knowledge/ingestion/jobs*`
  - `/api/web/knowledge/metrics/*`
- Shared safe knowledge:
  - `POST /api/knowledge/search`
  - `POST /api/knowledge/suggest`
  - `POST /api/knowledge/feedback`
- Ticket integration:
  - Existing `/api/tickets/{ticket_id}/kb_links` stays compatible.
  - Support knowledge panel can use `/api/web/support/tickets/{ticket_id}/knowledge*` wrappers.
  - `POST /api/web/support/tickets/{ticket_id}/passport/knowledge-draft` creates a persisted draft item/version and returns item/version ids.
- Web routes:
  - Add `/app/admin/knowledge`.
  - Extend `/app/help` with requester-safe suggestions/deflection.
  - Extend `/app/tickets/:ticketId` Knowledge tab with user-tried, linked, suggested and draft actions.
- Agent:
  - Add `TicketApiClient.get_knowledge_suggestions(...)` and `record_knowledge_feedback(...)`.
  - Create/preview payloads may include `knowledge_attempts`.

## Security / Privacy

- Requester/agent endpoints must not return internal bodies, support/admin/security items, raw chunks for restricted items, source ticket/passport ids, requester/device ids, raw custom fields, internal graph edges, internal queue/policy ids, trace/operation ids or extraction/confidence internals unless explicitly safe.
- Support sees support-internal plus requester-safe knowledge. Admin sees all except any future security-restricted role split. Auditor is read-only.
- Validation errors and ingestion errors are redacted.
- Mutation endpoints audit actor/action where practical.

## Verification Plan

- Targeted server tests: `test_knowledge_contract_no_db.py`, `test_knowledge_migration.py`, `test_knowledge_repo.py`, `test_knowledge_visibility.py`, `test_knowledge_search.py`, `test_knowledge_suggestions.py`, `test_knowledge_feedback.py`, `test_knowledge_graph.py`, `test_knowledge_ingestion.py`, `test_knowledge_passport_draft.py`, `test_knowledge_api.py`, `test_ticket_knowledge_links_compat.py`, `test_knowledge_metrics.py`.
- Regressions: P0/P0.1 ticket contracts/public queue/side effects/policy health/create contracts and P1/P1.1 service catalog fallback/preview/publication/API/create/reports.
- Agent tests: new knowledge suggestion tests plus service catalog wizard/chat helper/attachment regressions.
- Static and workspace: compileall, `git diff --check`, `python scripts/verify_workspace.py`, `python scripts/build_context_index.py --force`.
- Webapp: `pnpm --dir webapp build`, typecheck/lint if configured.
- Browser signoff: `/app/admin/knowledge`, `/app/help`, `/app/tickets/:ticketId`, security direct-id denial, and agent GUI helper/manual limitation notes.

## Verification Log

- Targeted P2 backend tests passed during implementation: `python -m pytest server\tests\test_knowledge_contract_no_db.py server\tests\test_knowledge_migration.py server\tests\test_knowledge_repo.py server\tests\test_knowledge_visibility.py server\tests\test_knowledge_search.py server\tests\test_knowledge_suggestions.py server\tests\test_knowledge_feedback.py server\tests\test_knowledge_graph.py server\tests\test_knowledge_ingestion.py server\tests\test_knowledge_passport_draft.py server\tests\test_knowledge_api.py server\tests\test_ticket_knowledge_links_compat.py server\tests\test_knowledge_metrics.py -q --tb=short` -> 24 passed.
- Policy Health catalog knowledge gap focused test: `python -m pytest server\tests\test_policy_health_service_catalog.py -q --tb=short` -> 2 passed.
- Agent focused tests: `python -m pytest pc_agent\tests\test_chat_panel_helpers.py pc_agent\tests\test_knowledge_suggestions.py pc_agent\tests\test_ticket_api_client_service_catalog.py -q --tb=short` -> 126 passed.
- Webapp build passed during implementation: `pnpm --dir webapp build`.
- Pending final gate: fresh targeted regressions, compile/static checks, context index rebuild, full/non-manual suites where feasible, remote deploy/browser signoff.

## Rollback Notes

- Schema rollback should drop P2 knowledge tables only after ensuring no tickets depend on normalized ticket-knowledge links. Existing `ticket_kb_links` remains the compatibility fallback.
- Operational rollback can disable requester/agent suggestions and keep Service Catalog ticket creation intact.
- Knowledge items should be archived/retired rather than deleted once linked to tickets, feedback or passport drafts.

# P1.1 Catalog UX & Governance Hardening

Status: completed for release candidate. P0/P0.1 is the non-negotiable baseline and remains archived below; P1 Service Catalog is the foundation commit, not the final production UX.

Goal: harden the existing P1 Service Catalog so requesters, agents and admins can use it safely in production:

`Fallback catalog -> runtime-safe preview -> explicit requester/agent Service -> Offering flow -> structured admin governance -> publish simulation -> seed/setup`

Classification: cross-cutting / release-control. Scope touches requester-safe API, ticket create preview, publication gates, seed/setup scripts, React requester/admin UI, Qt agent wizard, docs/CODEMAP/context index and full verification. No Protocol V3 change is planned.

## Discovery

- `ServiceCatalogRuntimeResolver.current_catalog_for_requester()` currently returns `fallback: None`; there is no real default `other.unknown` service/offering in the safe response when the catalog is empty.
- `/api/service-catalog/current` is unauthenticated GET-only and safe-projected, but no requester-safe POST preview endpoint exists under service-catalog. Existing `/api/tickets/create/preview` requires an authenticated actor and returns internal preview fields such as target queue id/name and raw request-template context.
- `/app/help` is catalog-first and submits `service_code`, `offering_code`, `offering_full_code` and `request_template_key`, but its sidebar preview is static text; it does not call a runtime-backed safe preview before submit.
- The Qt agent already fetches and caches `/api/service-catalog/current`, but the wizard enriches forms by unique template mapping. There is no explicit Service -> Offering step; `CreateTicketTypeGrid` still renders request templates as the first choice.
- `TicketApiClient.preview_ticket_create(...)` and `create_ticket(...)` already accept service/offering fields, so the agent HTTP boundary does not need Protocol V3 changes.
- `/app/admin/service-catalog` has dashboard, validation, simulation, publish/retire and JSON draft save, but JSON is still the main edit surface. Structured service/offering fields and selector-style inputs need to become the normal path.
- `ServiceCatalogPublicationService` validates required fields and references, but offering publication is not yet blocked by a runtime-equivalent dry-run simulation.
- No idempotent seed/setup command exists for baseline services and offerings. Seed must be dry-run capable and must not overwrite admin edits without `--force`.
- Policy Health already includes catalog objects and simulation input, but P1.1 must keep its simulation result aligned with the new requester-safe preview and publication simulation.

## Design Decisions

- Add a shared fallback/default catalog definition in server code and use it for safe projection and seed. `other.unknown` is the only fallback and it maps to a general fallback request template/form.
- Invalid explicit service/offering selections remain validation errors. Fallback is used only when the user explicitly selects `other.unknown` or when safe catalog projection needs a non-blocking fallback card.
- Requester preview is a sanitized wrapper around real runtime resolvers. It may instantiate synthetic ticket/request context but must not insert tickets, events, approvals, diagnostics, notifications, public sessions or operations.
- Publication simulation will run through the same service-catalog preview/dry-run path with generated safe sample form payload. Critical/error simulation failures block offering publication and are written to catalog audit issues.
- Admin UI keeps JSON as an Advanced/debug path only. The primary editor uses typed service/offering fields and saves through existing draft endpoints.
- The agent wizard becomes catalog-aware without changing Protocol V3: Service selection, Offering selection, dynamic form/details, preview, submit/success. If catalog fetch fails, legacy form-pack selection remains available.
- Seed is an idempotent script first (`scripts/seed_service_catalog.py`) and may be exposed in admin UI as a setup action if the existing admin API pattern supports it cleanly.

## API / UI Contracts

- Requester-safe catalog:
  - `GET /api/service-catalog/current` always returns safe `services[]` and a real safe `fallback` object for `other.unknown`.
  - Safe projection must recursively exclude queue ids, raw policy refs/config, approver ids, registry ids, device/requester ids, raw custom fields and trace/operation ids.
- Requester-safe preview:
  - `POST /api/service-catalog/preview` accepts `service_code`, `offering_code`, `offering_full_code`, `request_template_key`, form payload and safe requester/device context.
  - Response includes only safe service/offering labels, request type label, public status after create, expected first response/resolution text, approval/diagnostic summaries, next action, warnings and blockers.
- Admin catalog:
  - Existing `/api/web/admin/service-catalog*` endpoints remain.
  - Add seed/setup endpoint only if needed by the structured admin panel; otherwise the canonical setup entrypoint is the script.
- Agent GUI:
  - `TicketApiClient` keeps existing methods backward-compatible and sends catalog fields for preview/create.
  - Wizard labels distinguish catalog service (`Раздел обращения`) from CMDB affected service (`Затронутая система/услуга`).

## Implementation Phases

- [x] Complete mandatory discovery/intake commands and classify as cross-cutting / release-control.
- [x] Archive P0/P0.1 as baseline and create this P1.1 working section.
- [x] Add red tests for fallback safe catalog, requester preview, publication simulation, seed idempotency and agent explicit catalog helper behavior.
- [x] Implement shared fallback/default catalog definitions and seed/setup script.
- [x] Add requester-safe preview service/handler/route and recursive forbidden-key coverage.
- [x] Extend publication gates to run runtime simulation and audit validation attempts.
- [x] Update `/app/help` to require runtime-safe preview before submit while preserving legacy form fallback.
- [x] Replace JSON-first admin editing with structured service/offering forms and keep JSON as Advanced.
- [x] Update Qt agent wizard to expose Service -> Offering -> Dynamic form -> Preview -> Submit and preserve legacy fallback.
- [x] Extend Policy Health linkage where needed so fallback and publish blockers remain visible.
- [x] Update docs, CODEMAP, navigation catalog and rebuild context index.
- [x] Run targeted tests, P0/P0.1 regressions, webapp build, agent tests, full/default gates and browser signoff on remote.

## Test Plan

- Server:
  - `server/tests/test_service_catalog_fallback.py`
  - `server/tests/test_service_catalog_preview.py`
  - `server/tests/test_service_catalog_publication.py`
  - `server/tests/test_service_catalog_api.py`
  - `server/tests/test_policy_health_service_catalog.py`
  - `server/tests/test_ticket_create_service_catalog.py`
  - `server/tests/test_service_catalog_seed.py`
- Agent:
  - `pc_agent/tests/test_ticket_api_client_service_catalog.py`
  - `pc_agent/tests/test_ticket_create_wizard_service_catalog.py`
  - `pc_agent/tests/test_chat_panel_helpers.py`
  - `pc_agent/tests/test_ticket_api_client_attachments.py`
- Regressions:
  - P0/P0.1 status/public queue/side-effect/policy-health/create contracts.
  - Form process/business validation and helpdesk policy registry.
- Static/UI:
  - `python -m compileall -q server pc_agent scripts`
  - `git diff --check`
  - `python scripts/verify_workspace.py`
  - `pnpm --dir webapp build`
  - Browser signoff at `https://192.168.100.17:9443/admin` for `/app/admin/service-catalog`, `/app/admin/policy-health` and `/app/help`.

## Verification Log

- Red-first checks:
  - `server/tests/test_service_catalog_fallback.py` initially failed because safe catalog returned `fallback: None`.
  - `server/tests/test_service_catalog_preview.py::test_requester_service_catalog_preview_returns_safe_validation_error` initially failed with 404.
  - `server/tests/test_service_catalog_seed.py` initially failed because `scripts.seed_service_catalog` did not exist.
  - `server/tests/test_service_catalog_repo.py::test_service_catalog_publication_blocks_offering_when_runtime_simulation_cannot_route` initially allowed publishing without a route.
  - Agent fallback helper test initially failed because normalized catalog did not promote the safe fallback.
- Green targeted checks so far:
  - `python -m pytest server/tests/test_service_catalog_fallback.py server/tests/test_service_catalog_preview.py server/tests/test_service_catalog_seed.py -q --tb=short` -> 7 passed.
  - `python -m pytest server/tests/test_service_catalog_repo.py::test_service_catalog_publication_blocks_offering_when_runtime_simulation_cannot_route server/tests/test_policy_health_service_catalog.py -q --tb=short` -> 2 passed.
  - `python -m pytest pc_agent/tests/test_chat_panel_helpers.py -q --tb=short` -> 119 passed.
  - `pnpm --dir webapp build` -> passed.
- Consolidated targeted verification:
  - `python -m pytest server/tests/test_service_catalog_fallback.py server/tests/test_service_catalog_preview.py server/tests/test_service_catalog_repo.py server/tests/test_service_catalog_api.py server/tests/test_policy_health_service_catalog.py server/tests/test_ticket_create_service_catalog.py server/tests/test_reports_service_catalog.py server/tests/test_service_catalog_seed.py -q --tb=short` -> 15 passed.
  - `python -m pytest server/tests/test_ticket_status_usage_no_db.py server/tests/test_public_queue_privacy.py server/tests/test_workflow_side_effect_observability.py -q --tb=short` -> 13 passed.
  - `python -m pytest server/tests/test_policy_health_service.py server/tests/test_policy_health_api.py -q --tb=short` -> 6 passed.
  - `python -m pytest server/tests/test_ticket_create_contracts.py -q --tb=short` -> 13 passed.
  - `python -m pytest server/tests/test_form_process_preview.py server/tests/test_form_business_validation.py -q --tb=short` -> 18 passed.
  - `python -m pytest server/tests/test_helpdesk_policy_registry.py -q --tb=short` -> 26 passed.
  - `python -m pytest server/tests/test_service_catalog_contract_no_db.py pc_agent/tests/test_ticket_api_client_service_catalog.py pc_agent/tests/test_ticket_api_client_attachments.py -q --tb=short` -> 18 passed.
  - `python -m pytest pc_agent/tests/test_ticket_api_client_service_catalog.py pc_agent/tests/test_ticket_api_client_attachments.py pc_agent/tests/test_chat_panel_helpers.py -q --tb=short` -> 133 passed.
  - `python -m pytest pc_agent/tests -m "not manual" -q --tb=short` -> 305 passed, 4 deselected.
  - `python -m pytest server/tests -m "not manual" -q --tb=short` -> 889 passed, 11 warnings.
- Static/build verification:
  - `pnpm --dir webapp build` -> passed.
  - `python -m compileall -q server pc_agent scripts` -> passed.
  - `git diff --check` -> passed with only line-ending warnings.
  - `python scripts/verify_workspace.py` -> passed.
  - `python scripts/build_context_index.py --force` -> passed.
- Full/default gate:
  - Initial `python scripts/run_ci_suite.py` attempt on the same commit timed out in `server_pytest_db_api` at the old 2700s per-step limit, with tests still progressing and no failure reported.
  - `python scripts/run_ci_suite.py --server-pytest-timeout 5400` -> green artifact: `verify_workspace` passed, webapp bundle built, server no-db 307 passed, server DB/API 552 passed, server agent_ws 30 passed, pc_agent 305 passed.
- Seed/setup:
  - Local `python scripts/seed_service_catalog.py --dry-run` exited 0 and printed offline baseline plan because local PostgreSQL was not running.
  - Remote `server/venv/bin/python scripts/seed_service_catalog.py --dry-run` against `/var/chat_bot/pc_client` reported five services and nine offerings would be created with no missing dependencies.
  - Remote `server/venv/bin/python scripts/seed_service_catalog.py` created baseline services `workplace`, `access`, `network`, `mail`, `other`, baseline offerings including `other.unknown`, and missing seed request templates; no `--force` updates were applied.
- Remote release/browser signoff:
  - `python scripts/release_server_to_remote.py --allow-local-dirty` used the green CI artifact, deployed committed state, ran remote Alembic `upgrade head`, uploaded the React bundle and passed remote smoke after one retry.
  - Browser MCP verified `https://192.168.100.17:9443/app/admin/service-catalog`: page loads, seeded services and fallback are visible, structured service/offering editors are visible, publication gates show blocking status, and runtime simulation runs from the admin panel.
  - Browser MCP verified `https://192.168.100.17:9443/app/admin/policy-health`: page loads and includes seeded fallback/template rows such as `general_request`.
  - Browser MCP verified `https://192.168.100.17:9443/app/help`: requester can select `Другое / Не знаю`, run a safe preview, and submit a ticket; test ticket access code `6WT8G22X` was created.
  - Browser-side recursive check of `/api/service-catalog/current` returned 200, five safe services, real fallback `other.unknown`, and no forbidden safe-projection keys.
  - Browser console check returned 0 errors/warnings; server logs showed ticket create/routing/SLA activity and expected unauthenticated public ticket WebSocket warnings, with no server error in the checked tail.
  - Remote server was stopped after signoff: `python scripts/manage_remote_stack.py stop server`; follow-up status reported inactive/dead.

## Rollback Notes

- Rollback is additive: retire seeded catalog services/offerings instead of deleting rows referenced by tickets.
- Disable catalog-first UI by falling back to the legacy request-form pack; do not remove legacy `form_key` / `request_template_key` create support.
- No schema migration is planned for P1.1 unless discovery exposes a hard blocker; seed data can be rolled back by retiring entries.

## Known Risks

- The biggest implementation risk is turning the Qt wizard into explicit catalog flow without destabilizing existing dynamic fields, attachments and diagnostic consent. Keep changes localized to selection helpers/widgets and preserve the old form path.
- Requester preview must avoid reusing internal `/api/tickets/create/preview` payload directly because that endpoint exposes internal routing details.
- Seeded offerings should not be published if dependencies cannot pass publication gates; the script must report draft/skipped status clearly.

# P1 Service Catalog + Runtime Process Governance

Goal: add a managed Service Catalog layer above the stabilized ticket engine:

`Service Catalog Service -> Service Offering -> Request Template / Form Schema -> Effective Policy Bundle -> Ticket`

Classification: cross-cutting / release-control. This touches DB migrations, ticket create/preview contracts, policy runtime, Policy Health, reporting, typed web API, React admin/requester UI, Qt agent GUI, docs and verification gates.

## Discovery

- CMDB/registry service already exists as `registry_services` via `RegistryService`, `RegistryRepo` and `RegistrySnapshotService`. It represents business/IT systems and inventory context, not requester-facing process catalog. Existing registry snapshots/options expose it to admin and picker fields.
- `tickets.service_id` and `request_templates.service_id` are legacy numeric category/service fields, not unambiguous CMDB or catalog service identifiers. Do not overload them for P1 reporting.
- Request-template/process model already exists: `ticket_types`, `form_schemas`, `request_templates`, versioned policy tables and `HelpdeskPolicyRepo.resolve_effective_request_template(...)`.
- Existing policy inheritance is `system -> ticket_type -> category -> request_template`. P1 must insert service/offering layers without weakening request-template explicit refs.
- Existing create paths are authenticated `/api/tickets/create`, `/api/tickets/create/preview`, unauthenticated `/public_api/tickets/create`, shared `create_ticket_with_side_effects(...)` and `resolve_create_form_submission(...)`.
- Policy Health simulation currently starts from `template_code` and uses real runtime routing/priority/SLA/OLA/approval/closure/visibility/diagnostic resolvers on a synthetic ticket. It needs catalog input resolution and source reporting.
- Requester web flow `/app/help` currently pulls `/public_api/ticket_forms/current?pack_key=request_forms`, picks a form directly and submits legacy form payload. It must become catalog-first while preserving direct forms fallback.
- Agent GUI currently uses `TicketApiClient.get_ticket_form_pack_current(...)`, `CreateTicketTypeGrid`, dynamic form widgets, server preview and create payloads with `request_template_key`. It needs service/offering steps and a fallback to the old form pack if catalog API is unavailable.
- Admin React route model already has `/app/admin/forms` and `/app/admin/policy-health`; new catalog UI should be another admin route, not a replacement for the form builder.

## Design Decisions

- Add first-class catalog entities `helpdesk_services` and `helpdesk_service_offerings`. They are process/catalog records, separate from CMDB `registry_services`.
- Link catalog service to CMDB with nullable `registry_service_id`. This keeps affected-system/service picker semantics separate from requester catalog choice.
- Add explicit ticket reporting/enrichment fields: `catalog_service_id`, `catalog_offering_id`, `service_code`, `offering_code`, `request_type`, `business_criticality`, `reporting_category`, `service_owner_actor_id`, `support_group_code`. Keep legacy `tickets.service_id` untouched.
- Store a requester-safe but support-auditable catalog snapshot in `custom_fields.service_catalog` including selected service/offering titles, template/version, ticket type, effective policy refs/sources, reporting tags and selected-by mode.
- Policy inheritance order for P1 is `system -> ticket_type -> category -> service -> offering -> request_template`. Request-template explicit refs remain strongest; offering overrides service.
- Public/requester/agent serializers must not expose internal queue IDs, raw policy JSON, approver internals, internal registry IDs, device/requester IDs or raw custom fields.
- Publication gates are required before `published`: missing owner/support queue/template/ticket type/SLA-required policy/approval approvers/unsafe visibility/invalid registry link block publication.
- Simulation must use the same catalog runtime resolver as create/preview and must not insert tickets, events, approvals, diagnostics, operations or sessions.

## Migration Plan

- Add Alembic revision `082_service_catalog_process_layer`.
- Create `helpdesk_services`, `helpdesk_service_offerings` and `helpdesk_service_catalog_audit`.
- Add ticket enrichment columns and indexes for reporting.
- Add constraints for lifecycle (`draft|published|retired`), visibility (`public|internal|restricted`), business criticality (`low|medium|high|critical`) and safe code shape.
- Avoid destructive cascade into tickets; catalog deletes should be blocked or detached through retire semantics.
- Downgrade drops P1 tables/columns where feasible without touching legacy request templates or registry rows.

## API Contract

- Admin/auditor endpoints under `/api/web/admin/service-catalog` for dashboard, service/offering draft save, validate, publish, retire, detail and simulation.
- Requester/agent safe catalog endpoints under `/api/service-catalog/current`, `/api/service-catalog/services/{service_code}` and `/api/service-catalog/offerings/{full_code}`; public aliases only if requester help needs anonymous catalog access.
- Create/preview accepts `service_code`, `offering_code`, `offering_full_code`, `request_template_key`, legacy `form_key` and form payload. Legacy form-only behavior remains valid.

## Implementation Phases

- [x] Add TDD contract tests for catalog constants, safe serializers and policy inheritance ordering.
- [x] Add migration/models/repo for services, offerings, ticket enrichment and catalog audit.
- [x] Add service catalog serializers, runtime resolver and publication service.
- [x] Extend policy runtime so service/offering policy refs participate in effective policy resolution with explainable sources.
- [x] Extend authenticated/public create and preview paths to resolve catalog input, validate visibility and store ticket fields/snapshot.
- [x] Extend Policy Health service/API/simulation to include catalog service/offering health and source reporting.
- [x] Add service/offering dimensions to reports.
- [x] Add admin API handlers and route registration.
- [x] Add React `/app/admin/service-catalog` UI with list/edit/publish/simulation/inheritance panels.
- [x] Update requester `/app/help` catalog-first UX with safe preview and legacy form fallback.
- [x] Update Qt agent `TicketApiClient` and create wizard to fetch catalog, select service/offering, preview and submit catalog payloads with legacy fallback.
- [x] Update docs/CODEMAP/navigation and rebuild context index.
- [ ] Run targeted server/agent/webapp tests, P0 regression tests, migrations, `verify_workspace.py`, full suites where feasible and browser checks.

## Test Plan

- Server no-db/domain: `server/tests/test_service_catalog_contract_no_db.py`.
- Server DB/API: `test_service_catalog_migration.py`, `test_service_catalog_repo.py`, `test_service_catalog_publication.py`, `test_service_catalog_runtime.py`, `test_service_catalog_api.py`, `test_ticket_create_service_catalog.py`, `test_policy_health_service_catalog.py`, `test_reports_service_catalog.py`.
- Agent: `pc_agent/tests/test_ticket_api_client_service_catalog.py`, `pc_agent/tests/test_ticket_create_wizard_service_catalog.py` plus existing chat panel and attachment tests.
- Regressions: P0/P0.1 status, public queue privacy, workflow side-effect observability, policy health and create contracts.

## Verification Plan

- Targeted server catalog tests first.
- P0 regression pack.
- `python -m compileall -q server pc_agent scripts`.
- Alembic upgrade head on clean/current test DB path where available.
- `python scripts/verify_workspace.py`.
- Webapp type/build after React changes.
- Browser check on `https://192.168.100.17:9443/admin` for `/app/admin/service-catalog`, `/app/admin/policy-health` and `/app/help`.
- Agent GUI changes verified by unit/helper tests; no Protocol V3 change planned.
- Full/default gate before production release claim.

## Verification Log

- Passed: `python -m pytest server/tests/test_service_catalog_contract_no_db.py -q`.
- Passed: `python -m pytest server/tests/test_service_catalog_repo.py server/tests/test_service_catalog_api.py -q --tb=short`.
- Passed: `python -m pytest server/tests/test_service_catalog_repo.py -q --tb=short` after adding policy-ref/approval publication gate coverage.
- Passed: `python -m pytest server/tests/test_reports_service_catalog.py -q --tb=short`.
- Passed: `python -m pytest server/tests/test_policy_health_service_catalog.py server/tests/test_policy_health_api.py -q --tb=short`.
- Passed: `python -m pytest server/tests/test_ticket_create_service_catalog.py -q --tb=short`.
- Passed: `python -m pytest pc_agent/tests/test_ticket_api_client_service_catalog.py -q`.
- Passed: `python -m pytest pc_agent/tests/test_chat_panel_helpers.py -q`.
- Passed: `python -m pytest server/tests/test_service_catalog_contract_no_db.py server/tests/test_service_catalog_repo.py server/tests/test_service_catalog_api.py server/tests/test_reports_service_catalog.py server/tests/test_policy_health_service_catalog.py server/tests/test_ticket_create_service_catalog.py -q --tb=short` (11 passed).
- Passed: `python -m pytest server/tests/test_ticket_status_usage_no_db.py server/tests/test_public_queue_privacy.py server/tests/test_workflow_side_effect_observability.py server/tests/test_policy_health_service.py server/tests/test_policy_health_api.py server/tests/test_ticket_create_contracts.py -q --tb=short` (32 passed).
- Passed: `python -m pytest server/tests/test_form_process_preview.py server/tests/test_form_business_validation.py server/tests/test_helpdesk_policy_registry.py -q --tb=short` (44 passed).
- Passed: `python -m pytest pc_agent/tests/test_ticket_api_client_service_catalog.py pc_agent/tests/test_chat_panel_helpers.py pc_agent/tests/test_ticket_api_client_attachments.py -q --tb=short` (131 passed).
- Passed: `python -m pytest pc_agent/tests -m "not manual" -q --tb=short` (303 passed, 4 deselected).
- Passed: `python -m pytest server/tests -m "not manual" -q --tb=short` (881 passed, 12 warnings).
- Passed: `pnpm --dir webapp build`.
- Passed: `python -m alembic heads` from `server` reports `082 (head)`.
- Passed: final `python -m compileall -q server pc_agent scripts`, `git diff --check`, `python scripts/verify_workspace.py` and `python scripts/build_context_index.py --force` after docs/navigation updates.
- Pending: remote/browser signoff after deploy.

## Rollback Notes

- Catalog rollout is additive. Rollback can retire catalog entries and keep legacy direct `request_template_key` / `form_key` create paths active.
- DB downgrade removes catalog tables and explicit ticket enrichment columns but does not touch registry services, request templates, ticket types or existing P0 invariants.
- If catalog API is unavailable, requester/agent flows must continue through the legacy request-form pack path.

## Known Risks

- The largest risk is semantic drift between CMDB service, legacy numeric `service_id` and new catalog service. The chosen mitigation is explicit P1 field names plus docs/tests around serializer boundaries.
- Public/requester safe projection must be guarded recursively to avoid leaking raw policy refs, queue IDs or registry internals.
- Policy inheritance source reporting must stay aligned between create, Policy Health simulation and admin UI.

# P0 Ticket System Contract Hardening

Status: completed and archived as the baseline for P1. Keep this section compact; P1 must not reopen or weaken these contracts.

- Canonical ticket status contract lives in `server/tickets/statuses.py`; `triaged` is legacy input/backfill compatibility only.
- Migration `081_ticket_contract_hardening` enforces canonical status, non-empty requester identity, SLA-safe priority invariant and deterministic event-order indexes.
- Public queue unauthenticated responses use a sanitized projection and reject numeric queue probing.
- Workflow side-effect failures are observable through structured log/audit/metric paths.
- Policy Health exists at `/api/web/admin/helpdesk/policy-health*` and `/app/admin/policy-health`; simulation is a dry-run over runtime resolvers.
- Last recorded P0 verification: targeted P0 suite `78 passed`, full server non-manual suite `863 passed, 12 warnings`, webapp type/build passed, `python scripts/verify_workspace.py` passed.

# Diagnostic Capabilities Full Implementation Plan

## Active Agent Recipe Runner Production Slice

Goal: add `agent_recipe` as a production execution target backed by a protected managed `agent_recipe_runner` module. Recipes are persisted DB records, not generated ZIP modules; execution uses a first-class `run_recipe` Protocol V3 command and produces operations plus diagnostic evidence.

### Ticket-bound Runner Auto-Install / Auto-Upgrade Slice

Goal: make `agent_recipe` runs able to install or upgrade the protected `agent_recipe_runner` as a runtime dependency without blocking the HTTP request and without bypassing module lifecycle.

- [x] Add `operation_dependencies` plus `operations.phase` for parent operation dependency state.
- [x] Select runner through preferred module assignment and version/platform/primitive compatibility checks.
- [x] Use `device_desired_modules` and `modules.reconcile.reconcile_device` for install/upgrade.
- [x] Return parent `operation_id` immediately in `waiting_dependency` / `installing_runner` state.
- [x] Resume parent recipe operation after dependency terminal result, `module_state_changed`, or `tools_changed`.
- [x] Keep resume idempotent and avoid duplicate `run_recipe` outbox commands.
- [x] Add timeout handling through operation watchdog and dependency timeout timestamps.
- [x] Update support diagnostics UI labels for install/upgrade runner actions and waiting dependency run results.
- [x] Add targeted tests for missing runner dependency creation and idempotent resume.

### Runner Fleet Rollout / Canary / Waves / Rollback Slice

Goal: add an admin-managed rollout workflow for the protected `agent_recipe_runner` module across multiple devices. This is separate from ticket-bound runtime dependency install: plans, waves and target state are persisted, but installs/upgrades still go through `device_desired_modules` and `modules.reconcile.reconcile_device`.

- [ ] Add persisted runner rollout plan, wave, target and event models plus migration.
- [ ] Add rollout service/repo with canary selection, wave promotion, pause/resume, refresh and rollback.
- [ ] Keep module delivery inside existing module lifecycle; never write module storage or install commands directly.
- [ ] Expose admin APIs for summary, create plan, start canary, promote wave, pause/resume, refresh and rollback.
- [ ] Extend Capability Studio provider card with Runner Rollout UI and actions.
- [ ] Add backend tests for canary desired-state writes, promotion guardrails, status refresh and rollback.
- [ ] Add frontend type/build coverage and browser-check `/app/admin/capabilities?tab=providers`.

Hard constraints for this slice:

- Runner rollout only targets `agent_recipe_runner`.
- No fake fleet rollout over the single-device dependency path.
- No remediation or arbitrary command execution.
- Rollback means setting desired module version back to the recorded rollback version and reconciling affected devices.
- Canary/waves may be admin-triggered in MVP; background scheduling can be added later without changing the persistence model.

Hard constraints for this slice:

- No arbitrary PowerShell/Bash/Python command runner.
- No remediation/side effects in the first release.
- No macOS support; only `win32` and `linux`.
- Do not break existing managed modules, `run_tool`, playbooks, observer, diagnostics or Capability Studio.
- Keep primitive execution inside the managed runner module; agent core only resolves and delegates.

Implementation plan:

- [ ] Add failing tests for `agent_recipe` target validation, recipe tables, readiness states, execution enqueue, agent bridge and basic primitives.
- [ ] Reuse `diagnostic_capabilities` / `diagnostic_capability_versions` for capability identity/version contracts; add recipe-specific tables and version contract fields.
- [ ] Add server recipe repo/service, admin recipe APIs and registry projection for published recipe capabilities.
- [ ] Extend readiness and execution router so `agent_recipe` routes to `RecipeExecutionService`, not `ToolExecutionService.run_tool`.
- [ ] Add `run_recipe` Protocol V3 command path and command-result evidence projection for `agent_recipe` operations.
- [ ] Add agent `RecipeRunnerBridge` and protected managed module package `agent_recipe_runner` with read-only primitives.
- [ ] Extend Capability Studio with Agent Recipe authoring MVP and runner provider visibility.
- [ ] Update docs/CODEMAP/navigation for the new tables, endpoints, command and agent module contract.
- [ ] Run targeted backend, agent and frontend checks; then deploy through the standard remote scripts and browser-check the admin UI.

## Goal

Build the full diagnostic capabilities model on top of the existing module/tool system:

`Provider / Module -> Capability / Tool -> Execution Target -> Operation / Session / Query -> Artifacts + Evidence -> Diagnostic Session / Finding / Passport`.

The current work completed the backward-compatible foundation. This plan tracks the remaining full implementation, including persistent evidence, real providers, UI integration, policy/readiness depth, playbook integration, and release/deploy verification.

## Hard Constraints

- Do not break existing `ToolExecutionService.run_tool`.
- Do not break managed ZIP modules, builtin modules, semantic tool ids, aliases, playbooks, observer traces, Protocol V3, DeviceOutbox, `command_result`, operations, passport/evidence, or remote assist.
- Do not move `server_connector`, `observer_query`, `remote_assist`, or `manual` capabilities onto the agent.
- Do not rename canonical ids unless a migration/alias strategy is explicit.
- Keep installation-on-agent as one deployment option, not a universal capability property.
- Work only in `C:\Users\admin-2\CodexProjects\pc_client`.

## Current State

Active slice for this task:

- Goal: add `/app/admin/capabilities` as a top-level Capability Studio MVP over the existing diagnostics capability registry, provider config APIs and Modules Workbench.
- Scope: admin React route/page, catalog/providers/evidence/readiness/SDK tabs, detail drawer, create wizard skeleton, typed admin aliases if needed.
- Non-goals: no ToolExecutionService changes, no playbook/runtime rewrites, no DB schema, no declarative recipe runner, no automation runner, no new Zabbix SDK.
- Current state: implemented route aliases, React Capability Studio page/components, navigation entry, Modules Workbench link and focused tests.
- Verification: backend alias tests pass; `pnpm --dir webapp exec vitest run src/app/router.test.tsx` passes; `pnpm --dir webapp run build` passes; Playwright MCP verified `/app/admin/capabilities` catalog, nav item, detail drawer, Providers tab, Evidence Mapping tab and create modal with mocked API payloads; `python scripts/docs_inventory.py --check-links` and `python scripts/verify_workspace.py` pass.

Stage 1 foundation is implemented:

- Manifest/tool contract accepts optional `execution`, `deployment`, `safety`, `evidence`, and `artifacts`.
- Old managed ZIP manifests default to `agent_managed_module`.
- Builtin agent tools default to `agent_builtin`.
- Validation covers target enum, `server_connector` integration requirements, agent install semantics, evidence requirements, perspective enum, and safety bool fields.
- Agent `@exposed_tool`, registry, `list_tools`, and `describe_tool` expose capability metadata for agent tools.
- `system.collect`, `screen.collect`, `screen.record`, and `diag.logs.collect` have `agent_builtin` metadata.
- `diag.logs.collect` is marked as `logs.bundle`, `domain=logs`, `perspective=endpoint`, `passport_eligible=true`, `artifacts.logs_zip`.
- Server capability projection exists in `server/diagnostics/`.
- Readiness foundation exists.
- Execution router foundation routes only `agent_builtin` / `agent_managed_module` to existing `ToolExecutionService.run_tool`; non-agent targets return unsupported placeholders and do not touch DeviceOutbox.
- Zabbix capabilities are implemented through a bounded server connector client; observer, remote assist, and manual providers are server-side routes.
- Endpoints exist:
  - `GET /api/diagnostics/capabilities`
  - `GET /api/tickets/{ticket_id}/diagnostics/capabilities`
- Support tool DTO can carry capability metadata.
- Docs, CODEMAP, navigation catalog and boundary docs are updated.

Active execution slice:

- [x] Extend manifest/tool metadata with explicit readiness flags for credentials, mapping and policy while keeping old manifests valid.
- [x] Replace placeholder readiness decisions with a real service context that can use device records, installed/desired module state, platform metadata, integration config, credentials, mapping, policy and permission checks.
- [x] Replace unsupported provider placeholders for `observer_query`, `remote_assist` and `manual` with real server-side provider routes built on existing observer, remote assist and passport/evidence services.
- [x] Keep Zabbix as a safe server connector implementation boundary: validate config/credentials/mapping, use persisted provider config at run time, and return bounded provider results through a JSON-RPC client without moving checks onto the agent.
- [x] Prove non-agent targets do not call `ToolExecutionService.run_tool` from the generic capability router.

Verified:

- `python scripts/verify_workspace.py`
- `python -m pytest server/tests/test_modules_manifest_no_db.py server/tests/test_diagnostic_capabilities_no_db.py server/tests/test_module_observer_contract_no_db.py server/tests/test_modules_workbench_api.py server/tests/test_ticket_diagnostic_policy.py server/tests/test_tool_service_builtin_modules.py server/tests/test_tool_service_auto_install_no_db.py -q --tb=short`
- `python -m pytest pc_agent/tests/test_registry_and_module_loading.py pc_agent/tests/test_diag_logs_module.py -q --tb=short`
- `python -m pytest server/tests/test_web_support_api.py -k "tools" -q --tb=short`
- Migration check: remote DB current is `073 (head)`; `run_remote_migrations.py upgrade head` is a no-op.
- `python -m pytest server/tests/test_modules_manifest_no_db.py server/tests/test_diagnostic_capabilities_no_db.py -q --tb=short`
- `python -m pytest pc_agent/tests/test_registry_and_module_loading.py pc_agent/tests/test_diag_logs_module.py -q --tb=short`
- `python -m compileall -q server\diagnostics server\utils\module_manifest.py server\utils\module_builder.py server\routes.py server\web_api\support_handlers.py server\web_api\dto\support.py pc_agent\core\registry.py pc_agent\core\orchestrator.py`
- `python -m pytest server/tests/test_diagnostic_layer.py server/tests/test_ticket_passport_service.py -q --tb=short`
- `python -m pytest server/tests/test_diagnostic_layer.py server/tests/test_ticket_passport_service.py server/tests/test_observer_diagnostics_api.py server/tests/test_ticket_diagnostic_policy.py server/tests/test_playbook_scenarios_no_db.py server/tests/test_remote_assist_no_db.py server/tests/test_agent_observer_events_repo.py pc_agent/tests/test_diag_logs_module.py -q --tb=short`
- `python -m compileall -q server\diagnostics server\app\repos\diagnostics_repo.py server\app\db\models.py server\routes.py`
- `pnpm --dir webapp build`
- `python -m alembic -c alembic.ini heads` from `server/` shows `074 (head)`.
- `git diff --cached --check`
- `python -m pytest server/tests/test_diagnostic_layer.py server/tests/test_diagnostic_capabilities_no_db.py -q --tb=short`
- `python -m pytest pc_agent/tests/test_registry_and_module_loading.py pc_agent/tests/test_diag_logs_module.py -q --tb=short`
- `python scripts/release_server_to_remote.py --allow-local-dirty --gate quick --skip-ci-check --leave-running`
- `python scripts/run_remote_migrations.py current` shows `074 (head)` on Linux.
- `python scripts/manage_remote_stack.py smoke server`
- Browser check at `https://192.168.100.17:9443/admin`: support ticket tools workspace opens the Diagnostics tab; overview loads evidence counts, perspectives, latest evidence and action buttons with no console warnings/errors.

## Active Diagnostic Layer MVP Slice

Goal: build the separate ticket diagnostic layer on top of existing tickets, operations, playbooks, observer, remote assist, artifacts, passport/evidence and capability metadata. Diagnostics must not become a ticket status and must not rewrite tool/module/playbook/observer execution.

Existing diagnostic data sources:

- `operations` plus `tool_call_started` / `tool_call_result` ticket events.
- `playbook_runs` and `playbook_step_runs`.
- observer root trace, compact summary, signatures and bundles.
- remote assist sessions/events.
- artifacts, especially `diag.logs.collect` / `logs_zip`.
- existing passport evidence and manual support context.
- capability readiness and execution metadata from the foundation phase.

Implementation plan:

- [x] Add failing tests for diagnostic overview, operation/artifact/remote evidence projection, session lifecycle, finding rules, evidence passport selection and bundle creation.
- [x] Add Alembic migration and ORM models for `diagnostic_sessions`, `diagnostic_steps`, `diagnostic_evidence`, `diagnostic_findings` and `diagnostic_bundles`.
- [x] Add `DiagnosticRepo` and services in `server/diagnostics/`:
  - `DiagnosticOverviewService`
  - `DiagnosticProjectionService`
  - `DiagnosticEvidenceService`
  - `DiagnosticSessionService`
  - `DiagnosticFindingService`
  - `DiagnosticBundleService`
  - profile registry skeleton.
- [x] Add endpoints:
  - `GET /api/tickets/{ticket_id}/diagnostics/overview`
  - `GET /api/web/support/tickets/{ticket_id}/diagnostics/overview`
  - session/evidence/finding/bundle/profile endpoints from the diagnostic layer spec.
- [x] Add frontend typed API in `webapp/src/features/diagnostics/api.ts`.
- [x] Add a unified Diagnostics panel/tab in the support workspace without removing existing tools/playbooks/observer/remote assist panels.
- [x] Update CODEMAP/navigation/docs for the new diagnostic layer and routes.
- [x] Run targeted backend tests, existing observer/playbook/remote/diag logs regressions, workspace verifier and targeted frontend checks.

Next execution slice:

- [x] Add passport bridge: selected `diagnostic_evidence` can be attached idempotently to existing `ticket_evidence_items` with provenance and artifact refs.
- [x] Add `POST /api/tickets/{ticket_id}/diagnostics/passport/attach-selected`.
- [x] Add `POST /api/tickets/{ticket_id}/diagnostics/run-profile` MVP: create diagnostic session, record recommended capability/playbook steps, project current ticket sources, evaluate findings and optionally auto-select passport-eligible evidence.
- [x] Add frontend actions in the Diagnostics tab: run profile, evaluate findings, build bundle and attach selected evidence to passport.
- [x] Deploy to Linux, apply migration `074`, smoke the remote stack and browser-check the Diagnostics tab.

Acceptance for this slice:

- Level 1 read-only overview works with empty and populated tickets.
- Level 2 persistent sessions/evidence/findings/bundles exists and can be exercised through services/API.
- Existing operations, remote assist sessions and diag logs artifacts can be projected into normalized diagnostic evidence.
- Observer summary appears in the overview without duplicating observer internals.
- Finding engine provides deterministic rule-based suspected findings.
- Evidence can be selected for passport later through `selected_for_passport`.
- Bundle MVP returns JSON summary plus evidence/artifact/observer/remote references.
- Existing tool, playbook, observer and remote assist flows continue to work unchanged.
- Selected diagnostic evidence can be promoted into passport evidence without duplicating existing rows.

## Full Implementation Phases

### Phase 2: Persistent Capability Registry and Config

- [x] Decide whether persisted capability registry is needed now or whether descriptors remain computed from providers plus manifests.
- [x] If persistence is needed, add DB tables:
  - `diagnostic_providers`
  - `diagnostic_capabilities`
  - `diagnostic_capability_versions`
  - `diagnostic_provider_configs`
  - `diagnostic_provider_credentials_refs` or references into an existing secret/config store.
- [x] Add Alembic migration and migration tests.
- [x] Define provider config lifecycle: disabled, configured, credentials_missing, ready, degraded.
- [x] Add admin-safe CRUD/service APIs for provider config without logging secrets.
- [x] Add web-session admin aliases for provider config APIs so the admin UI can use httpOnly session auth.
- [x] Add audit events for provider config changes.
- [x] Update `server/docs/DATABASE.md`, `server/docs/MODULES_API.md`, `server/docs/CODEMAP.md`, `docs/ARCHITECTURE_BOUNDARIES.md`.

Decision: capability descriptors remain computed from manifest/provider sources for now, because agent builtin/managed tools are dynamic and must keep backward-compatible `run_tool` semantics. Migration `075` adds persisted provider/config tables plus capability snapshot tables for admin/config workflows; it does not make the DB the source of truth for agent tool descriptors.

Verification:

- `python scripts/run_remote_migrations.py current`
- migration unit tests
- DB-backed provider config tests
- `python scripts/verify_workspace.py`
- `python -m pytest server/tests/test_diagnostic_provider_config.py -q --tb=short`
- `python -m pytest server/tests/test_diagnostic_provider_config.py server/tests/test_diagnostic_capabilities_no_db.py server/tests/test_diagnostic_layer.py -q --tb=short`
- `python -m compileall -q server\diagnostics server\app\repos\diagnostic_provider_config_repo.py server\app\db\models.py server\routes.py`
- `python -m alembic -c alembic.ini heads` from `server/` shows `075 (head)`.

### Phase 3: Real Readiness Model

- [x] Replace placeholder readiness heuristics with real data sources:
  - device exists / ticket bound to device
  - agent online state
  - platform compatibility from tool metadata, device OS and managed module manifest
  - installed module version and preferred version
  - desired/installing state
  - dependency/preflight state
  - consent requirements
  - RBAC permission checks
  - policy disabled states
  - integration config and credentials state
  - mapping requirements for server connectors
  - observer root trace availability
  - remote assist policy/user consent/device capability state
- [x] Return stable `reason_code` in addition to human-readable `reason`.
- [x] Return available actions with explicit action ids:
  - `install`
  - `run`
  - `configure_integration`
  - `add_credentials`
  - `request_consent`
  - `open_remote_assist`
  - `create_manual_evidence`
- [x] Add no-db and DB-backed tests for readiness statuses and provider-config transitions.
- [x] Ensure readiness cannot make support/admin UI leak devices or integration names outside caller permission.

Decision: readiness payloads keep the existing `readiness` status strings for backward compatibility, but `reason_code` is now a stable machine contract such as `DEVICE_REQUIRED`, `MODULE_INSTALL_REQUIRED`, `PREFLIGHT_FAILED`, `INTEGRATION_NOT_CONFIGURED`, `CREDENTIALS_MISSING`, `MAPPING_MISSING`, `CONSENT_REQUIRED`, `POLICY_DISABLED` or `PERMISSION_DENIED`. Human `reason` strings are generic for permissions/integrations, and callers should drive UI actions from `actions` ids instead of parsing text.

Verification:

- `python -m pytest server/tests/test_diagnostic_capabilities_no_db.py -q --tb=short`
- `python -m pytest server/tests/test_diagnostic_capabilities_no_db.py server/tests/test_diagnostic_provider_config.py -q --tb=short`
- targeted API tests for both global and ticket-scoped capability endpoints

### Phase 4: Execution Router Productionization

- [x] Add explicit operation/session/query model around capability runs without changing existing `run_tool`.
- [x] For `agent_builtin` and `agent_managed_module`, keep calling `ToolExecutionService.run_tool`.
- [x] For `server_builtin`, implement server-local command/query runner with operation records.
- [x] For `server_connector`, implement provider interface:
  - `list_capabilities()`
  - `get_readiness()`
  - `run_query()`
  - `normalize_result()`
  - `map_evidence()`
- [x] For `observer_query`, route to existing observer services for summary/bundle.
- [x] For `remote_assist`, route to existing remote assist request/session APIs rather than `run_tool`.
- [x] For `manual`, create manual evidence/finding flows.
- [x] Add idempotency and timeout semantics per target.
- [x] Add structured error codes:
  - `CAPABILITY_NOT_FOUND`
  - `CAPABILITY_NOT_READY`
  - `CAPABILITY_TARGET_UNSUPPORTED`
  - `INTEGRATION_NOT_CONFIGURED`
  - `CREDENTIALS_MISSING`
  - `MAPPING_MISSING`
  - `POLICY_DENIED`
  - `CONSENT_REQUIRED`
- [x] Ensure non-agent targets never write DeviceOutbox rows.

Decision: Phase 4 establishes the production routing contract without changing agent execution. `CapabilityExecutionRouter.run_capability()` now returns a target-specific envelope with `execution_target`, `execution_kind`, `provider_id`, `provider_type`, `idempotency_key` and `timeout_ms`. The ticket run endpoint computes current readiness and returns `409 CAPABILITY_NOT_READY` before invoking a provider/tool when the capability is blocked. `consent_required` stays executable for agent and remote-assist capabilities when the action is `request_consent`, preserving existing consent initiation flows. `agent_builtin` / `agent_managed_module` still call `ToolExecutionService.run_tool`; server connector, observer, remote assist and manual targets use provider boundaries. `server_builtin` now has a server-local runner for `server.dns.resolve` and `server.http.request`; it creates `operations` rows, transitions `queued -> running -> succeeded/failed`, supports idempotency keys and timeouts, maps evidence preview, and never writes `device_outbox`.

Verification:

- `python -m pytest server/tests/test_diagnostic_capabilities_no_db.py -q --tb=short`
- `python -m pytest server/tests/test_diagnostic_server_builtin_runner.py -q --tb=short`
- router tests proving each target goes to the correct backend
- operation lifecycle tests for `server_builtin` success/failure/idempotency
- negative tests proving server connector / observer / remote assist / manual do not call `ToolExecutionService.run_tool`

### Phase 5: Zabbix Server Connector

- [x] Define config schema:
  - endpoint URL
  - auth method
  - credentials reference
  - TLS options
  - host mapping strategy
  - timeout/retry policy
- [x] Implement Zabbix provider capabilities:
  - `zabbix.problems.lookup`
  - `zabbix.host.health`
  - `zabbix.item.history`
- [x] Add readiness:
  - integration_not_configured
  - credentials_missing
  - mapping_missing
  - available
  - unavailable/degraded
- [x] Implement safe API client with redaction and bounded responses.
- [x] Map Zabbix results to evidence:
  - `monitoring.problem`
  - `monitoring.host_health`
  - `monitoring.metric_history`
- [x] Add tests with fake HTTP server or mocked Zabbix API, not real external calls.
- [x] Add docs and admin config examples.

Decision: `diagnostics.providers.zabbix_provider.ZabbixProvider` is the first real `server_connector` implementation. It performs bounded Zabbix JSON-RPC calls for `problem.get`, `host.get` and `history.get`, accepts runtime config from persisted diagnostic provider config, uses credential references without returning/logging raw tokens, maps results to existing evidence metadata, and keeps all execution on the server side. Persisted provider config can supply URL, TLS/timeout options and mappings; a ready credential ref is passed internally to the provider run path. A full secret-vault resolver and admin UI for secret material are still separate work.

Verification:

- `python -m pytest server/tests/test_zabbix_provider_no_db.py -q --tb=short`
- `python -m pytest server/tests/test_diagnostic_provider_config.py -q --tb=short`
- provider unit tests
- readiness tests
- redaction tests
- no raw token/credential logging checks

### Phase 6: Observer Query Capabilities

- [x] Implement `observer.ticket.summary` using existing observer ticket summary/root trace services.
- [x] Implement `observer.trace.bundle` using existing diagnostics bundle/export path.
- [x] Define output contracts for observer capabilities.
- [x] Convert observer query results into evidence preview:
  - root trace health
  - latest error
  - top signature
  - related traces
  - degraded runtime signals
- [x] Ensure observer query capabilities are read-only and do not generate DeviceOutbox commands.
- [x] Add browser/API tests for support/admin deep links if UI consumes them.

Decision: `diagnostics.providers.observer_provider.ObserverCapabilityProvider` now dispatches `observer.ticket.summary` and `observer.trace.bundle` separately. Ticket summary returns a compact support-facing output with root trace health, latest error, top signature, trace counts, related traces and evidence preview. Trace bundle uses existing observer overlay trace search/detail/signature/degradation services to return a bounded bundle contract with primary trace, related traces, signatures, degradations, recommended next checks and evidence preview. Both capabilities stay `observer_query` / `execution_kind=query`; they do not call `ToolExecutionService.run_tool` and do not enqueue DeviceOutbox rows.

Verification:

- `python -m pytest server/tests/test_observer_capability_provider.py server/tests/test_diagnostic_capabilities_no_db.py -q --tb=short`
- `python -m pytest server/tests/test_observer_capability_provider.py server/tests/test_diagnostic_capabilities_no_db.py server/tests/test_observer_diagnostics_api.py -q --tb=short`
- `python -m pytest server/tests/test_web_support_api.py -k "observer" -q --tb=short`
- `python -m pytest server/tests/test_admin_tech_api.py::test_tech_diagnostics_bundle_collects_trace_context -q --tb=short`
- `python -m compileall -q server/diagnostics server/observer`
- `python scripts/verify_workspace.py`

### Phase 7: Remote Assist Capabilities

- [x] Model remote assist as session capability, not command/tool.
- [x] Add capabilities:
  - `remote_assist.request_view`
  - `remote_assist.request_control`
  - `remote_assist.session.summary`
  - optional later: file transfer, clipboard, elevated/admin as policy-gated sub-capabilities.
- [x] Readiness must use:
  - device online
  - support permission
  - remote assist policy
  - user consent state
  - session availability
- [x] Route execution to existing remote assist service/routes.
- [x] Map session summary to passport-eligible evidence where policy allows.
- [x] Preserve current Remote Assist consent/signaling flow.

Decision: Remote Assist remains a `session` capability target, not a regular tool command. `remote_assist.request_view` requests `view_only`; `remote_assist.request_control` requests `interactive_control` and is gated by `remote_assist.control` plus `remote_assist.interactive_control.enabled`; `remote_assist.session.summary` is a read-side ticket summary that does not require an online device. The provider uses `RemoteAssistService.request_session()` and `send_request_to_agent()` for real session/consent signaling, returns normalized session envelopes and maps both request/summary results to `remote_assist.session` evidence previews. Readiness now accounts for policy flags and active ticket/device sessions before routing.

Verification:

- `python -m pytest server/tests/test_remote_assist_capability_provider.py server/tests/test_remote_assist_no_db.py server/tests/test_diagnostic_capabilities_no_db.py -q --tb=short`
- `python -m compileall -q server/diagnostics server/remote_assist`

### Phase 8: Manual Capabilities

- [x] Add manual evidence creation capabilities:
  - `manual.visual_check`
  - `manual.vendor_response`
  - `manual.operator_note`
  - `manual.customer_confirmation`
- [x] Implement permission checks.
- [x] Add manual evidence DTOs and event payloads.
- [x] Link manual capabilities to ticket passport/evidence candidate flows.
- [x] Add audit trail and source attribution.

Decision: Manual capabilities now create `diagnostic_evidence` first and no longer bypass the Diagnostic Layer by writing directly to `ticket_evidence_items`. `manual.visual_check`, `manual.vendor_response`, `manual.operator_note` and `manual.customer_confirmation` use the `manual` execution target, require `diagnostics.create_manual_evidence`, produce `manual.evidence` output envelopes and write `diagnostic_manual_evidence_created` ticket events for audit/realtime projection. Passport linkage remains the existing selected-evidence bridge: evidence can be marked `selected_for_passport` and attached through `DiagnosticPassportBridgeService`, preserving current passport semantics.

Verification:

- `python -m pytest server/tests/test_manual_capability_provider.py server/tests/test_diagnostic_capabilities_no_db.py::test_capability_registry_projects_agent_and_skeleton_provider_capabilities server/tests/test_diagnostic_capabilities_no_db.py::test_readiness_returns_stable_reason_codes_and_action_ids server/tests/test_diagnostic_layer.py::test_manual_capability_run_creates_diagnostic_evidence_event_and_passport_candidate server/tests/test_diagnostic_layer.py::test_run_profile_and_attach_selected_api -q --tb=short`

### Phase 9: Evidence Persistence and Diagnostic Sessions

- [x] Add DB model if needed:
  - `diagnostic_sessions`
  - `diagnostic_session_capabilities`
  - `diagnostic_evidence`
  - `diagnostic_findings`
  - `diagnostic_artifact_links`
- [x] Define how an operation/session/query result becomes evidence:
  - raw operation result
  - normalized evidence preview
  - accepted evidence
  - passport-linked evidence
  - finding
- [x] Implement `normalize_tool_result_to_evidence_stub` as production mapper.
- [x] Preserve existing `TicketEvidenceService` and passport flows; extend them rather than replacing.
- [x] Add evidence provenance:
  - capability id/version
  - provider id/type
  - operation/session/query id
  - trace id
  - artifact refs
  - actor
  - redaction policy
- [x] Add cleanup/retention policy.

Implemented in phase 9:

- Migration `076` adds `diagnostic_session_capabilities` and `diagnostic_artifact_links`.
- `DiagnosticProjectionService.project_capability_result()` persists non-agent capability results into `diagnostic_evidence`, links artifacts, and writes session-scoped capability snapshots.
- `normalize_tool_result_to_evidence_values()` is the production mapper; the legacy preview helper delegates to it.
- Ticket capability run API now persists evidence for non-agent server/observer/remote capability results while keeping agent `run_tool` async behavior and manual evidence's existing provider-owned persistence.
- `DiagnosticEvidenceRetentionPolicy.cleanup_unselected_evidence()` removes old transient evidence while preserving selected passport evidence.

Verification:

- [x] migration/model tests
- [x] evidence service tests
- [x] passport linking tests
- [x] server_builtin operation/evidence lifecycle tests

### Phase 10: Playbook Integration

- [x] Allow playbooks to reference capability ids in addition to current tool ids.
- [x] Keep old playbooks working unchanged.
- [x] Add playbook step target resolution:
  - agent tool remains on the existing `run_tool` path.
  - server builtin / server connector query route through `CapabilityExecutionRouter`.
  - observer query routes through the observer capability provider.
  - manual checkpoint routes through the manual capability provider.
  - remote assist session request routes through the remote assist capability provider.
- [x] Add readiness preflight for capability-backed playbook steps.
- [x] Add output contracts for non-agent capability steps.
- [x] Add evidence attachment policy per step.
- [x] Add authoring UI/catalog updates for capabilities.

Verification:

- [x] existing playbook tests
- [x] new mixed-target playbook tests
- [x] no regression in auto-install before tool-backed steps

Notes:

- Completed in this phase: playbook drafts now persist `required_capabilities` alongside legacy `required_tools`; non-agent capability steps complete `playbook_step_run` synchronously with router output and do not enqueue DeviceOutbox commands; agent-backed steps still use the existing module install preflight and `run_tool` enqueue path.
- Evidence attachment is opportunistic and safe: playbook capability results with `evidence_preview` project into diagnostic evidence only when the ticket context points to an existing ticket, and projection failure does not fail the playbook step.
- Full policy/RBAC depth for capability playbooks remains part of Phase 12 hardening.

### Phase 11: Diagnostic Center UI

- [x] Add Diagnostic Center UI surfaces in the React webapp:
  - ticket-scoped capability list
  - readiness statuses and actions
  - filters by domain/perspective/provider/target
  - install/run/configure/request consent actions
  - evidence preview and attach-to-passport
  - session/finding view
- [x] Keep legacy support tool panel working.
- [x] Add admin/provider config UI for server connectors.
- [x] Add affordances for non-agent targets:
  - server connector configuration
  - observer summary/bundle
  - remote assist request
  - manual fact entry
- [x] Add browser checks at `http://192.168.100.17:8666/admin` per project browser canon after deploy.

Verification:

- [x] `python scripts/bootstrap_web_toolchain.py`
- [x] webapp type/build/tests
- [x] Playwright/browser checks
- [x] server API tests

Notes:

- Completed in this phase: `/app/tickets/:ticketId` now has a dedicated Diagnostic Center tab backed by `webapp/src/features/diagnostics/diagnostic-center-panel.tsx`. It loads ticket capabilities, readiness, evidence, sessions, findings and overview; filters by execution target/domain/perspective/provider; routes runnable capabilities through `POST /api/tickets/{ticket_id}/diagnostics/capabilities/{capability_id}/run`; supports manual evidence, finding evaluation, diagnostic bundle creation and selected evidence attachment to passport.
- `/app/admin/modules#diagnostic-provider-configs` now exposes `DiagnosticProviderConfigPanel` over the existing web-admin provider config aliases, so server connectors such as `zabbix_connector` can be configured without showing raw secret values from API responses.
- Legacy ticket tools and playbooks panels remain in the sidebar and still use their existing APIs.
- Browser signoff found and fixed a compact-layout drawer hit-testing regression: in ticket mode the right drawer stayed pointer-active over the center panel because Tailwind's `.flex` utility overrode the component-layer `display: none`. `webapp/src/styles.css` now hides the drawer with `display: none !important` for compact ticket mode.
- Follow-up signoff also found that the live `/app/tickets/:ticketId` route is backed by `TicketListPage`; the standalone `TicketDetailPage` route currently lazy-loads the same workspace page. `DiagnosticCenterPanel` is now wired directly into the live `Инструменты -> Диагностика` workspace tab so capability list/readiness/evidence/sessions/findings are visible in the actual support route.
- Follow-up signoff found that the Diagnostic Center was visible but its secondary queries used token-protected `/api/tickets/{ticket_id}/diagnostics/*` paths, which return `401` under the React httpOnly web session. The support workspace now uses `/api/web/support/tickets/{ticket_id}/diagnostics/*` aliases for capabilities, sessions, evidence, findings, bundle, profile-run and passport attach while the legacy `/api/tickets/*` contract remains available.

### Phase 12: Operations, Observer and Audit Hardening

- [x] Ensure every capability execution writes trace-visible lifecycle events.
- [x] Add observer root kinds/spans for:
  - capability run
  - server connector query
  - observer query
  - manual evidence
  - remote assist capability session
- [x] Add operation/session metrics:
  - duration
  - result status
  - readiness failure count
  - provider errors
  - evidence created/linked
- [x] Add audit events for high-risk or externally integrated capabilities.
- [x] Add redaction for integration config, credentials, query params and evidence payloads.
- [x] Update observer docs if new trace-visible API/flows are added.

Implemented in phase 12:

- `CapabilityExecutionRouter` now emits `capability_run_started` plus terminal lifecycle events through an observer sink without changing the old agent `run_tool` path.
- HTTP diagnostic capability runs and playbook non-agent capability steps use `RuntimeAuditCapabilityExecutionObserver`, which writes redacted `agent_runtime_audit` rows for trace projection.
- Observer runtime audit projection now recognizes diagnostic root kinds: `capability_run`, `server_connector_query`, `observer_query`, `manual_evidence` and `remote_assist`.
- Lifecycle audit details include bounded metrics (`duration_ms`, `result_status`, readiness failure count, provider error count and evidence linked count) and evidence metadata.
- Runtime params/result snapshots and persisted session capability snapshots redact integration config, credential refs, sensitive query fields and evidence output payloads.

Verification:

- [x] observer tests
- [x] dangerous-flow canary where applicable
- [x] redaction tests

### Phase 13: Release, Migration and Deployment

- [x] If DB schema changes were added, run migrations only through canonical scripts:
  - `python scripts/deploy_workspace_to_remote.py`
  - `python scripts/run_remote_migrations.py current`
  - `python scripts/run_remote_migrations.py upgrade head`
- [x] Run server release checks:
  - `python scripts/verify_workspace.py`
  - targeted pytest suites
  - remote smoke
  - browser checks for UI changes
- [x] Stop remote server after verification unless user asks to keep it running.
- [ ] Do not publish to GitHub until verified.

Implemented in phase 13:

- Released committed state `49f5775 diagnostics: add capability observability` to `/var/chat_bot/pc_client` through `python scripts/release_server_to_remote.py --allow-local-dirty --gate quick --leave-running`.
- Release flow ran local `verify_workspace.py`, built and uploaded the React bundle, deployed the committed branch to Linux, ran remote Alembic `upgrade head`, started control/server and passed remote server smoke after one retry.
- Confirmed remote Alembic state separately with `python scripts/run_remote_migrations.py current`: `076 (head)`.
- Confirmed remote server status and smoke with `python scripts/manage_remote_stack.py status server` and `python scripts/manage_remote_stack.py smoke server`.
- Browser-checked `http://192.168.100.17:8666/admin`: login page rendered, `admin/admin123` opened the Admin workspace and browser console had no warnings/errors.
- Stopped the remote server with `python scripts/manage_remote_stack.py stop server`; follow-up status reported `inactive/dead`.
- Follow-up live browser signoff on the support workspace opened `http://192.168.100.17:8666/admin`, switched to Support, opened a ticket, and found a compact-layout drawer hit-test issue that blocked the `Диагностика` tab. The UI CSS fix was built locally and is part of the next deploy/browser verification slice.

- Follow-up Phase 12 canary signoff ran `python scripts/run_observer_canary_suite.py --base-url http://192.168.100.17:8666 --ws-url ws://192.168.100.17:8666/ws --ui-ws-url ws://192.168.100.17:8666/ws_ui --report-path artifacts/observer_canaries/diagnostic_phase12_20260513_071408.json --markdown-report-path artifacts/observer_canaries/diagnostic_phase12_20260513_071408.md`. It passed module install/update/remove, consent approve/deny/timeout, retry exhaustion, WS nack/replay/rate-limit, UI replay, agent disconnect timeout, stable agent build registry checks and source coverage for `module_reconcile`, `playbook_run`, `web_auth`, `observer_runtime`, `capability_run`, `server_connector_query`, `observer_query`, `manual_evidence` and `remote_assist`.

Release note:

- This was a quick staging release gate because the local workspace has unrelated pre-existing dirty files and no full CI artifact was required for this iteration. Use the full gate before publishing to GitHub.

## Acceptance Criteria For Full Completion

- [x] Old module manifests still validate.
- [x] Old managed ZIP modules still auto-install and run through `ToolExecutionService.run_tool`.
- [x] Old builtin modules still run.
- [x] Old playbooks still run.
- [x] New manifest blocks are validated and surfaced.
- [x] Capability registry covers agent builtin, managed modules, server builtin/connector, observer, remote assist, manual and hybrid reserved target.
- [x] Readiness is accurate for device, online agent, install state, platform, dependencies, consent, RBAC, policy, integration config, credentials and mapping.
- [x] Non-agent targets never enqueue DeviceOutbox commands.
- [x] Server connector provider skeleton is replaced by at least one real connector implementation, starting with Zabbix.
- [x] Observer query capabilities return real observer data.
- [x] Remote assist capabilities route to existing remote assist service.
- [x] Manual capabilities create auditable manual evidence/facts.
- [x] Evidence is normalized, persisted where needed, traceable and passport-linkable.
- [x] Diagnostic sessions/findings can aggregate capability results.
- [x] UI can display capabilities, readiness, actions, evidence and findings.
- [x] Docs, CODEMAP, navigation catalog and architecture boundaries are current.
- [x] Targeted and cross-subsystem tests pass.
- [x] Migrations, if added, are linear, compile, apply on remote with `upgrade head`, and leave DB at head.

## Current Limitations / Handoff

- Zabbix has a bounded JSON-RPC provider and uses persisted config/mapping/ready credential refs in the ticket run route. Secret material is still expected through a runtime credential ref/resolver boundary; a full vault-backed secret-management UI is not implemented in this slice.
- `observer_query`, `remote_assist` and `manual` targets now route through server providers. Remote Assist uses the existing session service and may enqueue its existing `remote_assist.request` command; it does not use ordinary `ToolExecutionService.run_tool`.
- Diagnostic Center UI now exists in the React ticket detail and provider config UI exists under admin modules. Live browser signoff found and fixed a compact-layout drawer hit-testing issue and web-session diagnostics alias gaps. Remaining UI hardening is now implemented end-to-end: ticket-scoped capabilities return full descriptor metadata (`params_schema`, `output_schema`, `output_contract`, aliases, artifacts), arbitrary capability params render through a schema-driven editor and selected run params are sent to the capability router; blocked readiness states show RBAC/readiness-specific disabled copy with stable `reason_code` when available.
- Existing unrelated dirty worktree files predate this task and must not be reverted as part of this plan.

## Ticket System P0 Contract Hardening

Classification: cross-cutting / release-control. Scope touched ticket status contract, Alembic migrations, DB invariants, unauthenticated public queue API/UI, workflow side effects, policy health admin/auditor API/UI, docs and tests.

Discovery report:

- Legacy `triaged` appeared in status constants, workflow profile allowed statuses, public/admin/support/observer UI status labels, reports, docs, tests and historical migrations.
- Canonical status drift existed between `statuses.py`, model comments, migrations, docs and UI labels.
- Public queue ticket projection exposed internal identifiers and requester-sensitive fields through the same raw row shape used internally.
- Workflow transitions swallowed OLA/SLA/approval side-effect failures with broad exception handling.
- Status migrations existed historically, but no current canonical DB check/backfill enforced the final status set.
- `tickets.requester_id` was nullable in the model/DB, with legacy rows and tests creating tickets without a requester boundary value.
- Timeline/replay ordering relied on implicit ordering in some paths; the hardening migration adds explicit event indexes and docs pin `created_at, id`.
- Existing tests covered ticket creation/device binding/form policy flows, but lacked drift guards, recursive public privacy assertions, side-effect failure audit assertions and policy health API/service coverage.

Design decisions:

- `server/tickets/statuses.py` is the sole status contract module. Legacy aliases are accepted only at input boundaries; DB writes must call canonical assertion or rely on DB constraints.
- `triaged` backfills to `assigned` when `assignee_id` is nonblank; otherwise it backfills to `queued`.
- `requester_id` is required for new tickets. Legacy/model fallback order is explicit: preserve nonblank requester, then `device:<device_id>`, then `legacy:<ticket_id>`, with `legacy:unknown` only as a last insert-time guard.
- Public queue serializers are separate from internal/admin projections and return only ticket code, public position/status, public queue code, wait bucket and rounded update time.
- Side-effect failures are never silent. Non-critical OLA/notification-style failures audit/log/metric but allow transition; critical SLA integrity and required approval creation failures abort according to the documented decision matrix.
- Policy Health is a read-only admin/auditor governance surface. Simulation is dry-run only and returns `would_create_ticket: false`.

Implementation phases:

- Status contract: canonical sets, Russian labels, requester projection, legacy alias normalization metadata and canonical assertion.
- DB invariants: Alembic revision `081` (`20260513_1600_081_ticket_contract_hardening.py`) with requester/status backfill, NOT NULL/check constraints and ticket event ordering indexes.
- Public queue privacy: sanitized handlers and static public queue page/script.
- Workflow observability: `server/tickets/side_effects.py`, workflow transition wrappers, audit event `workflow_side_effect_failed`, redacted logging and metric counter.
- Policy health: backend service, admin/auditor API handlers, React admin page and dry-run panel.
- Docs/CODEMAP/navigation: ticket system, database, request form builder, security/auth, CODEMAP, quick lookup, architecture boundaries and navigation catalog updated.

Verification log:

- Targeted pytest: `python -m pytest server\tests\test_ticket_status_contract_no_db.py server\tests\test_ticket_status_usage_no_db.py server\tests\test_ticket_requester_boundary_no_db.py server\tests\test_ticket_create_contracts.py server\tests\test_ticket_device_binding.py server\tests\test_public_queue_privacy.py server\tests\test_workflow_side_effect_observability.py server\tests\test_policy_health_service.py server\tests\test_policy_health_api.py server\tests\test_form_process_preview.py server\tests\test_form_business_validation.py server\tests\test_helpdesk_policy_registry.py -q --tb=short` -> `78 passed`.
- Webapp verification: `pnpm --dir webapp exec tsc --noEmit` and `pnpm --dir webapp run build` passed.
- Workspace verification: `python scripts\verify_workspace.py` passed.
- Compile/static: `python -m compileall -q server\tickets server\web_api server\routes.py server\app\db\models.py scripts\navigation_catalog.py`, `python -m alembic -c alembic.ini heads`, `git diff --check`, `rg -n -U "except Exception:\s*\r?\n\s*pass" server\tickets`, and `rg -n "triaged" server webapp\src` passed with only allowed legacy/docs/test/migration occurrences.
- Full server suite after harness isolation fix: `python -m pytest server\tests -m "not manual" -q --tb=short` -> `863 passed, 12 warnings`.
- Remote deploy/migration: committed state `7fe3cda` pushed to `origin/codex/helpdesk-process-model`, deployed with quick gate, remote Alembic `upgrade head` applied revision `081`, and remote server smoke passed.
- Browser check: `https://192.168.100.17:9443/app/admin/policy-health` loaded the Policy Health dashboard, showed template rows/details, and dry-run returned a structured preview with `would_create_ticket: false`.
- Public queue browser/API check: `https://192.168.100.17:9443/queue` showed sanitized columns only; unauthenticated `/public_api/queues`, `/public_api/queue/tickets`, `/public_api/queue/stats` returned 200 with no recursive forbidden public keys; `/public_api/queue/tickets?ticket_code=T-000005` returned only `ticket_code`, `public_position`, `public_status`, `public_status_label`, `queue_code`, `wait_bucket`, `updated_at`.

Known risks / rollback notes:

- The release used the project quick gate because no current full CI artifact was available. Use the default/full release gate for final production promotion.
- The previous order-sensitive module workbench live-agent harness failures are resolved by restoring server modules after the in-process agent fixture clears agent-shadowed imports.
- Existing untracked `tmp/` remains untouched and is not part of this change.
- Rollback is a normal code rollback plus Alembic downgrade of revision `081` where feasible; data normalized from legacy aliases remains canonical by design.

### Follow-up: Production Contract Drift Closure

Current scope:

- Remove the remaining `Triaged` docs drift where it is still listed as a normal UI/API status.
- Add a guard that permits `triaged` only in legacy compatibility text, historical/backfill migrations and legacy-normalization tests.
- Close unauthenticated public queue probing by rejecting `queue_id`, accepting only `queue_code` / `public_queue_code`, and removing public `queue_name` exposure.
- Convert public ticket session revocation on close from warning-only handling into the same side-effect audit/log/metric path used for SLA/OLA/approval.
- Make Policy Health simulation runtime-equivalent: dry-run should use the same create/form policy overlay, routing, priority, SLA, OLA, approval, closure, visibility and diagnostic resolvers that ticket creation/lifecycle uses.

Design decisions:

- Public queue endpoints do not accept numeric queue ids at all. Numeric ids remain internal/admin-only.
- Public queue labels use `queue_code` only until a dedicated non-sensitive public alias/display field exists.
- Public session revocation after `closed` is non-critical for the status transition but must be observable as `workflow_side_effect_failed` plus metric when it fails.
- Policy Health simulation remains side-effect-free: it may instantiate an unsaved `Ticket` object and call resolver methods, but it must not insert tickets, approvals, events or operations.

Verification targets:

- Red run confirmed the expected failures in the new guards before implementation: old `Triaged` docs line, public `queue_id` probe/`queue_name`, warning-only public-session revoke and dashboard-only simulation.
- Implemented: public queue now rejects `queue_id` before DB access, accepts `queue_code` / `public_queue_code`, and exposes no internal queue names; close-time public-session revoke uses `run_workflow_side_effect(side_effect="public_session", action="revoke", critical=False)`; Policy Health simulation builds an unsaved ticket context and calls the real routing, priority, SLA, OLA, approval, closure, visibility and diagnostic runtime resolvers.
- Targeted green run: `python -m pytest server/tests/test_ticket_status_usage_no_db.py server/tests/test_public_queue_privacy.py server/tests/test_workflow_side_effect_observability.py server/tests/test_policy_health_api.py -q --tb=short` -> `16 passed`.
- Broader targeted green run: `python -m pytest server/tests/test_ticket_status_usage_no_db.py server/tests/test_public_queue_privacy.py server/tests/test_workflow_side_effect_observability.py server/tests/test_policy_health_service.py server/tests/test_policy_health_api.py -q --tb=short` -> `19 passed`.
- Neighbor regression green run: `python -m pytest server/tests/test_form_process_preview.py server/tests/test_form_business_validation.py server/tests/test_helpdesk_policy_registry.py server/tests/test_ticket_create_contracts.py -q --tb=short` -> `57 passed`.
- Static/compile: `python -m compileall -q server\tickets server\web_api server\routes.py server\app\db\models.py`, `python -m compileall -q scripts\navigation_catalog.py server\tickets\policy_health_service.py server\tickets\public_queue_handlers.py server\tickets\workflow_service.py`, `git diff --check`, `rg -n -i "triaged" server docs\QUICK_LOOKUP.md webapp\src`, `rg -n 'request\.query\.get\("queue_id"\)|"queue_name"|requester_display_name|urgency|importance|ticket_id|assignee_id|device_id|custom_fields' server\tickets\public_queue_handlers.py`, and `rg -n -U "except Exception:\s*\r?\n\s*pass" server\tickets` completed with no new blocking drift; `triaged` results are limited to legacy/docs/migration/tests.
- Context index refreshed: `python scripts\build_context_index.py --force`.
- Workspace verification: `python scripts\verify_workspace.py` -> passed after updating `scripts/navigation_catalog.py`.
- Browser check was not rerun for this follow-up because no web/static UI files changed; public queue and Policy Health behavior changes are backend/API contract changes covered by tests.
