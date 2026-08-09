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

Service Catalog stays a Helpdesk-owned process layer. It no longer calls a local Knowledge service, publishes Knowledge bindings or exposes local Knowledge gap/deflection endpoints. Requester and agent catalog flows continue with the form and `other.unknown` fallback while Knowledge is unavailable.

PR-7 may let an external Knowledge Platform consume opaque `service_code`, `offering_code` and `request_template_key` values through [KNOWLEDGE_PLATFORM_API_V1.md](KNOWLEDGE_PLATFORM_API_V1.md). That integration must remain versioned and fail closed; it must not restore local content packs, routes or a database fallback.

P3 Quality Loop stores `service_code`, `offering_code`, `request_type` and `reporting_category` snapshots on feedback, reopen events, QA reviews, improvement actions and service-quality snapshots. `/app/admin/quality` uses those catalog dimensions for CSAT, reopen rate, SLA/quality review and improvement-action analytics without exposing queue ids, requester identifiers or raw catalog policy JSON to requester surfaces. Legacy tickets without catalog fields are bucketed as uncategorized/legacy rather than mutating the ticket contract.

P4/P4.1 Problem Management stores `service_code`, `offering_code`, `request_type` and `reporting_category` on problem candidates, problem records, affected objects and problem analytics. Candidate detection groups repeated incidents, low CSAT, reopens, SLA breaches and failed QA by service/offering where available. Problem SLO policies can also scope by service/offering, and `/app/admin/problems` shows service/offering candidate volume plus overdue problem milestones. Invalid service/offering codes are rejected when the catalog is present; legacy tickets remain bucketed as legacy/uncategorized. See [PROBLEM_MANAGEMENT.md](PROBLEM_MANAGEMENT.md).

The Helpdesk-owned catalog matrix is:

| Scenario | service_code | offering_code | request_template_key |
|---|---|---|---|
| VPN | `network` | `network.vpn_issue` | `network` |
| Internet | `network` | `network.internet_issue` | `network` |
| Password reset | `access` | `access.reset_password` | `access` |
| Grant access | `access` | `access.grant_access` | `access` |
| Mail | `mail` | `mail.mailbox_issue` | `mail_issue` |
| Printer | `workplace` | `workplace.printer_issue` | `printer` |
| Laptop | `workplace` | `workplace.laptop_broken` | `breakage` |
| Software | `workplace` | `workplace.software_install` | `software_install` |
| Other | `other` | `other.unknown` | `general_request` |

Do not restore retired local Knowledge pack validation or repair commands. External Knowledge owns any future content-to-catalog binding lifecycle.

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
- `GET /api/web/admin/request-studio/capabilities`
- `POST /api/web/admin/request-studio/validate-draft`
- `POST /api/web/admin/request-studio/publish-preview`
- `POST /api/web/admin/request-studio/publish`

Request Studio publish preview returns validation, publish steps, object diffs and a server-issued confirmation token bound to the canonical draft payload. Tokens use the `rs1.<payload>.<signature>` HMAC format, scope `request_studio.publish`, actor id/role binding, nonce, draft hash and a default 10 minute TTL from `REQUEST_STUDIO_CONFIRMATION_TTL_SECONDS`. Only `token_hash` and `nonce_hash` are stored in `request_studio_publish_tokens`; raw confirmation tokens are never persisted. Publish is admin-only, rejects missing/malformed/expired/used/wrong-actor/wrong-draft tokens, revalidates the draft and marks the token used only after successful guarded publication. Preview diffs show whether the form schema, request template, catalog offering and service will be created, updated, left unchanged or blocked, with field-level changes and overwrite warnings.

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

- `/app/admin/request-template-studio`: primary no-code request setup UX. It edits the basic draft inside Studio and uses Request Studio safe publish endpoints to validate, preview, confirm and publish the form schema, request template and catalog offering without opening expert pages for the normal path.
- `/app/admin/service-catalog`: expert service/offering dashboard, filters, structured service editor, structured offering editor, publication gates for service and selected offering, policy inheritance summary, Advanced JSON loader, publish/retire actions and runtime simulation.
- `/app/help`: requester chooses service and offering, fills the linked form, runs runtime-backed safe preview and submits `service_code`, `offering_code`, `offering_full_code` and `request_template_key`. It has no local Knowledge suggestions or deflection actions.
- Agent Qt GUI: `TicketApiClient.get_service_catalog_current()` caches the safe catalog. The create wizard explicitly shows `Раздел обращения -> Тип обращения -> dynamic form/details -> Preview -> Submit` and sends only the catalog references without changing Protocol V3.

## Reporting

`GET /api/web/reports/summary` includes `tickets_by_service` and `tickets_by_offering`. Queries use explicit indexed ticket columns and bucket legacy/null rows as `Без каталога / Legacy`.

P3 adds `GET /api/web/quality/service-quality` for quality analytics by service/offering. It is aggregate-only and complements the operational report summary: requester comments, requester ids and internal QA findings stay on ticket-level support/admin views, not in catalog analytics.

P5 Change Enablement stores `service_code` and `offering_code` on `changes` and `change_affected_objects`. Change metrics can therefore show upcoming, active, failed and rolled-back changes by service/offering without exposing requester data or internal rollback steps.

## Rollback

Migration `082` is additive. P1.1 has no schema migration. P3 migration `088` is additive and can be operationally rolled back by disabling quality prompts/triggers while leaving catalog dimensions read-only in existing quality rows. Rollback is operational: retire seeded catalog entries instead of deleting rows referenced by tickets, disable catalog-first UI by falling back to legacy forms, and keep legacy `form_key` / `request_template_key` create payloads intact.
