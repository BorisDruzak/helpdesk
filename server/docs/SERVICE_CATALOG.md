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

## Publication Gates

`server/tickets/service_catalog_publication.py` validates service/offering publication:

- services need title, owner, active support/default queue unless informational/no-ticket, valid visibility and safe public description warnings;
- offerings need title, request type, active request template unless explicit no-form/no-ticket, valid parent and safe public description warnings;
- service default policy refs and offering policy override refs must point to active policies;
- required approval policies must declare a resolvable approver source before publication;
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
- `GET /api/service-catalog/services/{service_code}`
- `GET /api/service-catalog/offerings/{full_code}`

Safe projection never includes queue ids, raw policy JSON, approver internals, requester ids, device ids, raw custom fields or trace/operation ids.

## UX

- `/app/admin/service-catalog`: service/offering dashboard, filters, publication gates, policy inheritance summary, draft JSON editor, publish/retire actions and runtime simulation.
- `/app/help`: requester chooses service, offering, linked form, sees a safe process preview summary and submits catalog codes with the ticket create payload.
- Agent Qt GUI: `TicketApiClient.get_service_catalog_current()` caches the safe catalog. The create wizard keeps the legacy form path as fallback and sends `service_code`, `offering_code`, `offering_full_code` when a template maps to exactly one published offering.

## Reporting

`GET /api/web/reports/summary` includes `tickets_by_service` and `tickets_by_offering`. Queries use explicit indexed ticket columns and bucket legacy/null rows as `Без каталога / Legacy`.

## Rollback

Migration `082` is additive. Rolling back drops service catalog tables and ticket enrichment columns, leaving legacy `tickets.service_id`, request templates, form packs and registry services intact. Existing legacy create flows continue to work without catalog selection.
