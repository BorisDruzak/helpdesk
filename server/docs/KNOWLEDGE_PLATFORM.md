# Knowledge Platform

P2 adds a universal company knowledge layer and uses it for helpdesk self-service deflection. It is broader than a classic article table:

`Knowledge Space -> Knowledge Item -> Version -> Chunks -> Bindings -> Graph -> Feedback/Metrics -> Helpdesk Deflection`.

`article` is only one `knowledge_item.item_type`.

## Core Model

- `knowledge_spaces`: logical knowledge areas such as IT Support, Security, HR or Vendor Docs. Spaces define lifecycle, visibility, owner/reviewer defaults, ingestion/RAG flags and allowed item types.
- `knowledge_items`: universal objects with item type, lifecycle, visibility, owner/reviewer, source metadata, review dates and current published version.
- `knowledge_item_versions`: immutable versioned content. Publishing points `knowledge_items.current_version_id` at a reviewed version.
- `knowledge_chunks`: chunked text for search and future ACL-filtered retrieval/RAG. P2 does not add a mandatory external search or vector database.
- `knowledge_bindings`: operational links to `service_code`, `offering_code`, `request_template_key`, ticket type, symptoms, error codes and device/OS context.
- `knowledge_nodes` / `knowledge_edges` / `knowledge_entity_mentions`: PostgreSQL graph foundation for services, offerings, items, concepts, known errors, workarounds and ticket-derived relations.
- `knowledge_feedback_events`: suggested/viewed/helpful/not_helpful/deflected/support-used/draft-created events for usage and deflection metrics.
- `knowledge_ingestion_jobs`: manual text/markdown ingestion and document-source job tracking. Imported content creates drafts and never auto-publishes.
- `ticket_knowledge_links`: normalized future link table. Existing `ticket_kb_links` and `/api/tickets/{id}/kb_links` remain compatible.

## Item Types

Supported item types are:

`article`, `faq`, `runbook`, `policy`, `document`, `known_error`, `workaround`, `troubleshooting_tree`, `glossary_term`, `service_description`, `external_source`, `resolution_draft`.

## Lifecycle

Item statuses are `draft`, `in_review`, `published`, `needs_review`, `archived`.

Published items must have a current version. Passport-generated and ingested items are drafts by default and require review before publication. Operational rollback should archive or retire items rather than delete linked knowledge.

## Visibility And ACL

Visibility levels are `public`, `requester`, `agent_requester_safe`, `support_internal`, `admin_internal`, `security_restricted`, `auditor_read`.

Requester and local agent surfaces only receive published requester-safe knowledge. Support can see support-internal and requester-safe knowledge. Admin can manage spaces/items according to web-session RBAC. Search, suggestions, graph neighborhood and future retrieval/RAG must filter by ACL before returning any result.

Requester/agent projections must not expose internal body for restricted items, source ticket/passport ids, requester/device ids, raw custom fields, internal graph edges, queue/policy ids, trace ids, operation ids or raw chunks for restricted items.

## Search And Suggestions

`KnowledgeSearchService` uses PostgreSQL-compatible filtering and text matching over items, versions, chunks and bindings. Ranking prefers exact title/slug matches, service/offering/request-template bindings, text matches, helpfulness and freshness.

`KnowledgeSuggestionService` accepts helpdesk context:

- `service_code`
- `offering_code`
- `request_template_key`
- `ticket_type`
- query/form text
- device metadata
- surface (`requester_portal`, `agent_gui`, `support_workspace`)

The service returns visibility-filtered suggestions, known errors and workarounds.

## Helpdesk Deflection

The requester portal `/app/help` now inserts a knowledge step after service/offering selection. It calls `POST /api/knowledge/suggest`, shows safe suggestions, records helpful/not helpful/deflected feedback through `POST /api/knowledge/feedback`, and includes safe `knowledge_attempts` in ticket creation when the user continues after a failed article.

The local Qt agent wizard uses the same safe suggestion and feedback APIs through `TicketApiClient.get_knowledge_suggestions()` and `record_knowledge_feedback()`. It continues ticket creation if the knowledge API is unavailable. Protocol V3 is unchanged.

## Support Workspace

The support workspace knowledge panel keeps the existing `/api/web/support/tickets/{ticket_id}/knowledge-suggestions` shape while merging P2 platform suggestions. Existing `ticket_kb_links` endpoints and `kb_linked` / `kb_unlinked` ticket events remain compatible.

`POST /api/web/support/tickets/{ticket_id}/passport/knowledge-draft` now creates a persisted `knowledge_item` draft and first version from the ticket resolution passport. The draft inherits service/offering/request-template bindings from the ticket, stores source ticket/passport ids, marks stale-passport warnings and never publishes automatically.

## Ingestion

P2 supports manual text/markdown ingestion. Ingestion creates a job, draft item, first version and chunks, then moves the job to review-required/completed state. Errors are redacted. Uploaded/imported sources default to internal draft unless an admin explicitly changes visibility and publishes after review.

## Graph

Bindings create service/offering graph edges. Knowledge attempts can create ticket-tried relations. Passport drafts create source relations. P2 exposes a practical neighborhood API with max depth 2 and visibility filtering.

## APIs

Requester/agent safe:

- `POST /api/knowledge/search`
- `POST /api/knowledge/suggest`
- `POST /api/knowledge/feedback`

Admin/support management:

- `GET|POST /api/web/knowledge/spaces`
- `GET|POST /api/web/knowledge/items`
- `GET /api/web/knowledge/items/{item_id_or_slug}`
- `POST /api/web/knowledge/items/{item_id_or_slug}/versions`
- `POST /api/web/knowledge/items/{item_id_or_slug}/publish`
- `GET|POST /api/web/knowledge/graph/nodes`
- `GET /api/web/knowledge/graph/nodes/{node_id}/neighborhood`
- `POST /api/web/knowledge/graph/edges`
- `GET|POST /api/web/knowledge/ingestion/jobs`
- `GET /api/web/knowledge/metrics/summary`

Ticket compatibility:

- `GET|POST|DELETE /api/tickets/{ticket_id}/kb_links`
- `GET /api/web/support/tickets/{ticket_id}/knowledge-suggestions`
- `POST /api/web/support/tickets/{ticket_id}/passport/knowledge-draft`

## UI

- `/app/admin/knowledge`: spaces, item draft/version/publish workflow, metrics, graph/ingestion foundation and requester-safe preview context.
- `/app/knowledge`: support-facing knowledge entry, using the same real backend component.
- `/app/help`: service/offering suggestions, deflection feedback and failed-article attempts before ticket submit.
- `/app/tickets/:ticketId`: existing Knowledge tab receives platform-backed support suggestions and passport-to-draft results.

## Metrics

`KnowledgeMetricsService` exposes item totals, published count, deflection events, viewed/helpful/not_helpful counts, tickets created after failed knowledge and knowledge gaps by service/offering foundation. Metrics must not include requester PII.

## Service Catalog Integration

Knowledge binds to service/offering/request-template. Policy Health includes a warning when a published public service/offering has no requester-safe published knowledge binding. Service Catalog and requester preview may use knowledge counts/hints without exposing internal article names.

## Rollback

Migration `083` is additive. Operational rollback can disable requester/agent suggestions while leaving Service Catalog and ticket creation intact. Existing `ticket_kb_links` remains the compatibility fallback. Linked knowledge should be archived, not hard-deleted.
