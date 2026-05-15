# Service Catalog

P1 adds a managed service catalog process layer above the existing ticket engine:

`Catalog service -> Service offering -> Request template / form schema -> Effective policy bundle -> Ticket`.

This is not the CMDB registry service layer. `registry_services` remains inventory/CMDB data used for affected services and registry snapshots. Service Catalog services live in `helpdesk_services`, may link to `registry_services.service_id`, and own requester-facing catalog/process metadata.

## Model

- `helpdesk_services`: requester/admin catalog service with stable `code`, public title/description, lifecycle, visibility, owners, support/default queue, optional registry-service link, default policy refs and reporting tags.
- `helpdesk_service_offerings`: concrete request type under a service. It stores `service_id`, `code`, `full_code`, lifecycle, visibility, `request_type`, `request_template_key`, optional form/policy overrides and reporting tags.
- `helpdesk_service_catalog_audit`: append-only service/offering draft, publish and retire audit.
- `tickets`: explicit reporting fields `catalog_service_id`, `catalog_offering_id`, `service_code`, `offering_code`, `request_type`, `business_criticality`, `reporting_category`, `service_owner_actor_id`, `support_group_code`.

Tickets also store `custom_fields.service_catalog` with the selected service/offering, template version, effective policy refs/sources, reporting category, criticality and selection source.

## Runtime

`server/tickets/service_catalog_runtime.py` resolves create/preview input by:

1. `service_code + offering_code`;
2. `offering_full_code`;
3. legacy `request_template_key` / `form_key` when exactly one published offering maps to that template;
4. legacy create behavior when no unambiguous catalog mapping exists.

The resolver checks lifecycle/visibility for the actor and applies catalog defaults/overrides before ticket creation. Policy inheritance is:

`system -> ticket_type -> category -> service -> offering -> request_template`.

Request-template explicit refs remain strongest. Offering overrides beat service defaults. Policy Health and simulation expose catalog selection and effective policy sources without creating tickets.

P1.1 adds a real requester fallback. Safe catalog projection always exposes `other.unknown` (`Другое / Не знаю`) through `server/tickets/service_catalog_defaults.py`. Explicit invalid `service_code` / `offering_code` remains a validation error; the fallback is used only when the user selects it or when the catalog would otherwise be empty.

Requester-safe preview is `POST /api/service-catalog/preview`. It wraps the real catalog/form/policy runtime resolvers and returns only requester-safe labels, expected response/resolution text, approval/diagnostic summaries, next action, warnings and blockers. It does not insert tickets, events, approvals, diagnostics, notifications, public sessions or operations.

## Knowledge Integration

P2 Knowledge Platform binds published knowledge to `service_code`, `offering_code` and `request_template_key`. Requester `/app/help` and the local agent wizard call `POST /api/knowledge/suggest` after service/offering selection, show only requester-safe published suggestions, record helpful/not-helpful/deflected feedback, and include safe `knowledge_attempts` when ticket creation continues after failed self-service.

Policy Health includes a knowledge gap warning when a published public service/offering has no requester-safe published knowledge binding. Service Catalog remains the process layer; Knowledge Platform owns content lifecycle, versions, chunks/search, graph relations and deflection metrics. See [KNOWLEDGE_PLATFORM.md](KNOWLEDGE_PLATFORM.md).

P2.2 Knowledge Operations uses the same published public catalog as the gap source of truth. `GET /api/web/knowledge/gap-findings` and `POST /api/web/knowledge/gaps/recompute` combine missing requester-safe bindings, missing support runbooks, ticket counts and knowledge feedback (`ticket_created_after_view`, `not_helpful`) so admins can prioritize which service/offering needs content next. This does not change catalog runtime resolution or the `other.unknown` fallback.

## Publication Gates

`server/tickets/service_catalog_publication.py` validates service/offering publication:

- services need title, owner, active support/default queue unless informational/no-ticket, valid visibility and safe public description warnings;
- offerings need title, request type, active request template unless explicit no-form/no-ticket, valid parent and safe public description warnings;
- service default policy refs and offering policy override refs must point to active policies;
- required approval policies must declare a resolvable approver source before publication;
- offering validation runs a runtime dry-run simulation and blocks publication when routing cannot resolve or simulation fails;
- errors/critical issues block publication; warnings are surfaced for admin acknowledgement.

Publish/retire attempts are audited through `helpdesk_service_catalog_audit`.

## APIs

Admin/auditor:

- `GET /api/web/admin/service-catalog`
- `GET /api/web/admin/service-catalog/services/{service_code}`
- `POST /api/web/admin/service-catalog/services/save-draft`
- `POST /api/web/admin/service-catalog/services/{service_code}/validate|publish|retire`
- `GET /api/web/admin/service-catalog/services/{service_code}/offerings`
- `GET /api/web/admin/service-catalog/offerings/{full_code}`
- `POST /api/web/admin/service-catalog/offerings/save-draft`
- `POST /api/web/admin/service-catalog/offerings/{full_code}/validate|publish|retire`
- `POST /api/web/admin/service-catalog/simulate`

Requester/agent safe projection:

- `GET /api/service-catalog/current`
- `POST /api/service-catalog/preview`
- `GET /api/service-catalog/services/{service_code}`
- `GET /api/service-catalog/offerings/{full_code}`

Safe projection never includes queue ids, raw policy JSON, approver internals, requester ids, device ids, raw custom fields or trace/operation ids.

Seed/setup:

- `python scripts/seed_service_catalog.py --dry-run`
- `python scripts/seed_service_catalog.py`
- `python scripts/seed_service_catalog.py --force`

The seed is idempotent, creates baseline services (`workplace`, `access`, `network`, `mail`, `other`) and offerings, creates missing minimal request templates, reports missing dependencies and does not overwrite admin edits without `--force`.

## UX

- `/app/admin/service-catalog`: service/offering dashboard, filters, structured service editor, structured offering editor, publication gates for service and selected offering, policy inheritance summary, Advanced JSON loader, publish/retire actions and runtime simulation.
- `/app/help`: requester chooses service, offering, sees requester-safe knowledge suggestions/deflection actions, fills the linked form, runs runtime-backed safe preview before catalog submit, and submits `service_code`, `offering_code`, `offering_full_code`, `request_template_key` and safe `knowledge_attempts` when applicable. Legacy form-only submit remains available when the catalog is unavailable.
- Agent Qt GUI: `TicketApiClient.get_service_catalog_current()` caches the safe catalog. The create wizard explicitly shows `Раздел обращения -> Тип обращения -> dynamic form/details -> Preview -> Submit`; it fetches requester-safe knowledge suggestions after offering selection, records feedback, keeps the legacy form path as fallback and sends `service_code`, `offering_code`, `offering_full_code` and safe `knowledge_attempts` without changing Protocol V3.

## Reporting

`GET /api/web/reports/summary` includes `tickets_by_service` and `tickets_by_offering`. Queries use explicit indexed ticket columns and bucket legacy/null rows as `Без каталога / Legacy`.

## Rollback

Migration `082` is additive. P1.1 has no schema migration. Rollback is operational: retire seeded catalog entries instead of deleting rows referenced by tickets, disable catalog-first UI by falling back to legacy forms, and keep legacy `form_key` / `request_template_key` create payloads intact.
