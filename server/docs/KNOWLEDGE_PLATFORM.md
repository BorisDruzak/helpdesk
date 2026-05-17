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
- `knowledge_content_packs` / `knowledge_content_pack_items`: idempotent P2.2 install audit for versioned starter packs, dry-runs, unchanged skips, conflict detection, explicit force updates and retire/archive operations.
- `knowledge_rollout_policies`: admin-controlled self-service deflection rollout gates by surface, service, offering and request template, including gating, skip/bypass, max suggestion and fallback behavior.
- `knowledge_review_tasks` / `knowledge_review_comments`: first-class P2.2 review queue for drafts, scheduled reviews, stale content, negative feedback, gap candidates, passport drafts, ingestion review and unsafe visibility work.
- `knowledge_quality_snapshots`: optional persisted explainable quality score snapshots for reporting and low-quality queues.
- `knowledge_gap_findings`: persisted Service Catalog, ticket-volume and feedback-driven knowledge gap findings with accept/dismiss/create-draft workflow.
- `knowledge_search_events`: privacy-preserving search analytics with query hash and redacted query text for zero-result and ticket-after-search analysis.
- `ticket_knowledge_links`: normalized future link table. Existing `ticket_kb_links` and `/api/tickets/{id}/kb_links` remain compatible.

## Item Types

Supported item types are:

`article`, `faq`, `runbook`, `policy`, `document`, `known_error`, `workaround`, `troubleshooting_tree`, `glossary_term`, `service_description`, `external_source`, `resolution_draft`.

## Lifecycle

Item statuses are `draft`, `in_review`, `published`, `needs_review`, `archived`.

Published items must have a current version. The admin publish flow is explicit: create a draft item, create one or more `knowledge_item_versions`, select the latest draft or another version, then publish with that `version_id`. `knowledge_items.current_version_id` is only the current published pointer and is not required before the first publish.

Passport-generated and ingested items are drafts by default and require review before publication. Passport drafts carry `metadata.passport_stale`, `metadata.review_required` and structured `publish_blockers` when the source passport is stale. A stale passport draft cannot publish until an allowed actor supplies explicit stale acknowledgement and a review note. Operational rollback should archive or retire items rather than delete linked knowledge.

## Visibility And ACL

Visibility levels are `public`, `requester`, `agent_requester_safe`, `support_internal`, `admin_internal`, `security_restricted`, `auditor_read`.

Requester and local agent surfaces only receive published requester-safe knowledge. Support can see requester-safe plus `support_internal` knowledge. Auditor is read-only and can see requester-safe, `support_internal` and `auditor_read`, but not `admin_internal` or `security_restricted`. Admin can manage normal knowledge including `admin_internal`; `security_restricted` is admin-accessible until a dedicated security role exists. Search, suggestions, direct item/version reads, graph node lists, graph neighborhoods, ingestion job lists, metrics and future retrieval/RAG must filter by ACL before returning any result.

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

Content-pack baseline bindings must use the same canonical Service Catalog defaults as ticket create/preview: for example VPN is `network` + `network.vpn_issue` + template `network`, password reset is `access` + `access.reset_password` + template `access`, mail is `mail` + `mail.mailbox_issue` + template `mail_issue`, laptop is `workplace` + `workplace.laptop_broken` + template `breakage`, and fallback is `other` + `other.unknown` + template `general_request`. `scripts/validate_knowledge_pack_bindings.py --strict` enforces this against `server/tickets/service_catalog_defaults.py`.

## Helpdesk Deflection

The requester portal `/app/help` now inserts a knowledge step after service/offering selection. It calls `POST /api/knowledge/suggest`, shows safe suggestions, records helpful/not helpful/deflected feedback through `POST /api/knowledge/feedback`, and includes safe `knowledge_attempts` in ticket creation when the user continues after a failed article.

The local Qt agent wizard uses the same safe suggestion and feedback APIs through `TicketApiClient.get_knowledge_suggestions()` and `record_knowledge_feedback()`. It continues ticket creation if the knowledge API is unavailable. Protocol V3 is unchanged.

P2.2.1 rollout decisions are returned with suggestion responses and control whether suggestions are shown before or after the form, whether suggestions are required before submit, whether skip is allowed, urgent/high-impact bypass, `min_suggestions`, `max_suggestions`, deflection prompt visibility, known-error visibility, quality/freshness safe labels and no-suggestions/API-unavailable fallback. `max_suggestions=0` intentionally returns no suggestions. Defaults are non-blocking for requester and agent surfaces; admins must explicitly configure `block_submit`.

## Support Workspace

The support workspace knowledge panel keeps the existing `/api/web/support/tickets/{ticket_id}/knowledge-suggestions` shape while merging P2 platform suggestions. Existing `ticket_kb_links` endpoints and `kb_linked` / `kb_unlinked` ticket events remain compatible.

`POST /api/web/support/tickets/{ticket_id}/passport/knowledge-draft` now creates a persisted `knowledge_item` draft and first version from the ticket resolution passport. The draft inherits service/offering/request-template bindings from the ticket, stores source ticket/passport ids, marks stale-passport warnings and never publishes automatically.

## Ingestion

P2 supports manual text/markdown ingestion. Ingestion creates a job, draft item, first version and chunks, then moves the job to review-required/completed state. Errors are redacted. Uploaded/imported sources default to internal draft unless an admin explicitly changes visibility and publishes after review.

## P2.2 Knowledge Operations

P2.2 makes the platform operable day-to-day without replacing the P2/P2.1 contracts.

- Content packs live under `content_packs/knowledge/*.yaml` and are applied with `python scripts/seed_knowledge_content.py --dry-run|--force`. Packs are not migrations and not one-time SQL dumps: the service records source/content hashes, skips unchanged items, reports conflicts when admin-edited content would be overwritten, and requires explicit `--force` for overwrite. Pack binding drift is checked with `python scripts/validate_knowledge_pack_bindings.py --strict`; installed pack-managed binding drift is repaired with `python scripts/repair_knowledge_pack_bindings.py --dry-run --all` followed by the same command without `--dry-run`.
- Content templates are served by `GET /api/web/knowledge/templates` and cover article/how-to, FAQ, troubleshooting, support runbook, known error, workaround, policy/process and glossary structures.
- Review/curation is first-class through `GET /api/web/knowledge/review/tasks`, `POST /api/web/knowledge/review/generate` and task transition routes under `/api/web/knowledge/review/tasks/{task_id}/{assign|start|complete|dismiss}`. The older `GET /api/web/knowledge/review-queue` and item review-action route remain compatibility summaries.
- Quality score is deterministic and explainable. `KnowledgeQualityService` computes completeness, governance, safety, usefulness, freshness and coverage dimensions, while `GET /api/web/knowledge/quality` remains the dashboard summary.
- Gap detection is persisted through `GET /api/web/knowledge/gap-findings`, `POST /api/web/knowledge/gaps/recompute` and accept/dismiss/create-draft actions. It scans published public Service Catalog offerings, ticket counts and knowledge feedback, then reports missing requester articles, missing support runbooks, high-volume no-KB and high-not-helpful gaps.
- Rollout policy management is exposed by `GET|POST /api/web/knowledge/rollout-policies`, plus aliases `GET /api/web/knowledge/rollout`, `POST /api/web/knowledge/rollout/save` and `POST /api/web/knowledge/rollout/effective-preview`. Requester/agent suggestion calls honor the effective policy before search; support/admin/auditor and `support_workspace` remain visible so operations can continue during requester rollout pauses.
- Search analytics are recorded by `KnowledgeSearchAnalyticsService` during knowledge search with hashed/redacted query text; raw requester identifiers, device identifiers and raw custom fields are not stored.

Operational detail and rollback notes live in [KNOWLEDGE_OPERATIONS.md](KNOWLEDGE_OPERATIONS.md).

Requester-safe publication still runs lint checks before publishing. Public/requester content containing internal commands, queue/device/requester ids, raw custom fields, internal runbook language, secrets or security internals is blocked instead of relying on UI discipline.

## Graph

Bindings create service/offering graph edges. Knowledge attempts can create ticket-tried relations. Passport drafts create source relations. P2 exposes a practical neighborhood API with max depth 2 and visibility filtering.

Neighborhood responses are a fully visible subgraph. An edge is returned only when the edge visibility is allowed for the actor and both endpoint nodes are also visible and present in `nodes`; traversal never passes through hidden intermediate nodes, and orphan edges to missing or restricted endpoints are dropped before serialization.

## APIs

Requester/agent safe:

- `POST /api/knowledge/search`
- `POST /api/knowledge/suggest`
- `POST /api/knowledge/feedback`

Admin/support management:

- `GET|POST /api/web/knowledge/spaces`
- `GET|POST /api/web/knowledge/items`
- `GET /api/web/knowledge/items/{item_id_or_slug}`
- `GET|POST /api/web/knowledge/items/{item_id_or_slug}/versions`
- `POST /api/web/knowledge/items/{item_id_or_slug}/publish`
- `GET|POST /api/web/knowledge/graph/nodes`
- `GET /api/web/knowledge/graph/nodes/{node_id}/neighborhood`
- `POST /api/web/knowledge/graph/edges`
- `GET|POST /api/web/knowledge/ingestion/jobs`
- `GET /api/web/knowledge/metrics/summary`
- `GET /api/web/knowledge/content-packs`
- `POST /api/web/knowledge/content-packs/apply`
- `POST /api/web/knowledge/content-packs/{pack_code}/retire`
- `GET /api/web/knowledge/templates`
- `GET /api/web/knowledge/review-queue`
- `POST /api/web/knowledge/items/{item_id_or_slug}/review-action`
- `GET /api/web/knowledge/review/tasks`
- `GET /api/web/knowledge/review/tasks/{task_id}`
- `POST /api/web/knowledge/review/tasks/{task_id}/assign|start|complete|dismiss`
- `POST /api/web/knowledge/review/generate`
- `GET /api/web/knowledge/quality`
- `GET /api/web/knowledge/gaps`
- `GET /api/web/knowledge/gap-findings`
- `POST /api/web/knowledge/gaps/recompute`
- `POST /api/web/knowledge/gaps/{finding_id}/accept|dismiss|create-draft`
- `GET|POST /api/web/knowledge/rollout-policies`
- `GET /api/web/knowledge/rollout`
- `POST /api/web/knowledge/rollout/save`
- `POST /api/web/knowledge/rollout/effective-preview`

Ticket compatibility:

- `GET|POST|DELETE /api/tickets/{ticket_id}/kb_links`
- `GET /api/web/support/tickets/{ticket_id}/knowledge-suggestions`
- `POST /api/web/support/tickets/{ticket_id}/passport/knowledge-draft`

## UI

- `/app/admin/knowledge`: governance/editor route with spaces, item draft/version/publish workflow, selected-version publish controls, stale-passport acknowledgement, content pack operations, review queue, quality score, gap detection, rollout policies, metrics, graph/ingestion foundation and requester-safe preview context.
- `/app/knowledge`: support-facing knowledge entry using the same real backend data but without admin-first mutation controls. Support cannot create `admin_internal` / `security_restricted` content through this route.
- `/app/help`: service/offering suggestions, deflection feedback and failed-article attempts before ticket submit.
- `/app/tickets/:ticketId`: existing Knowledge tab receives platform-backed support suggestions and passport-to-draft results.

## Metrics

`KnowledgeMetricsService` exposes canonical nested metrics:

- `summary.deflection.deflected_count`
- `summary.deflection.ticket_created_after_view_count`
- `summary.deflection.deflection_rate`
- `summary.helpfulness.helpful_count`
- `summary.helpfulness.not_helpful_count`
- `summary.helpfulness.helpfulness_rate`
- `summary.totals.suggested_count`
- `summary.totals.viewed_count`
- `summary.totals.feedback_count`

Flat aliases remain for compatibility: `deflection_events`, `helpful_events`, `not_helpful_events`, `ticket_created_after_view_events`. Metrics must not include requester PII.

## P3 Quality Loop Integration

P3 consumes Knowledge Platform signals as quality inputs without changing article lifecycle or requester-safe filtering. `ticket_created_after_view`, `not_helpful` feedback and ticket `knowledge_attempts` can contribute to service-quality analytics, QA review triggers and continuous-improvement actions such as `update_kb_article`, `create_kb_article` or `create_known_error`.

Requester CSAT reason `knowledge_article_failed` is stored in `ticket_feedback.reason_codes` and may link to a knowledge item when the ticket context provides one. Aggregate quality APIs report failed knowledge attempt counts only by service/offering/period and must not include requester identifiers, raw comments or internal article metadata.

## Service Catalog Integration

Knowledge binds to service/offering/request-template. Policy Health and gap detection use canonical Service Catalog defaults, not stale content-pack aliases. Policy Health includes a warning when a published public service/offering has no requester-safe published knowledge binding. Service Catalog and requester preview may use knowledge counts/hints without exposing internal article names.

## Rollback

Migration `083` is additive. P2.1 migration `084` adds DB CHECK constraints for graph node/edge enums, entity mention states, feedback event/surface roles, ingestion source/status values and ticket-knowledge link enums. P2.2 migration `085` is additive for content-pack audit and rollout policy tables. P2.2 migration `086` adds review tasks/comments, quality snapshots, gap findings and search analytics. P2.2.1 migration `087` hardens rollout policies and content-pack binding repair audit status. P3 migration `088` adds ticket-quality tables that can reference knowledge failure signals operationally but do not own knowledge content. Operational rollback can disable requester/agent suggestions with a rollout policy and disable P3 quality triggers while leaving Service Catalog, support workspace and ticket creation intact; downgrade of `087` removes rollout hardening columns, downgrade of `086` removes only operations state and downgrade of `085` removes only pack/rollout audit state. Existing `ticket_kb_links` remains the compatibility fallback. Linked knowledge should be archived, not hard-deleted.
