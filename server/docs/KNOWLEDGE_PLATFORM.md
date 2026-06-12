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
- `knowledge_ai_proposals`: governed AI-generated proposal review queue for summaries, tags, glossary, graph nodes/edges and duplicate candidates. Proposals stay pending until admin/support review; approval can apply graph node/edge payloads and writes Observer-visible audit rows.
- `knowledge_feedback_events`: suggested/viewed/helpful/not_helpful/deflected/support-used/draft-created events for usage and deflection metrics.
- `knowledge_ingestion_jobs`: manual text/markdown ingestion and document-source job tracking. Imported content creates drafts and never auto-publishes.
- `knowledge_content_packs` / `knowledge_content_pack_items`: idempotent P2.2 install audit for versioned starter packs, dry-runs, unchanged skips, conflict detection, explicit force updates and retire/archive operations.
- `knowledge_rollout_policies`: admin-controlled self-service deflection rollout gates by surface, service, offering and request template, including gating, skip/bypass, max suggestion and fallback behavior.
- `knowledge_review_tasks` / `knowledge_review_comments`: first-class P2.2 review queue for drafts, scheduled reviews, stale content, negative feedback, gap candidates, passport drafts, ingestion review and unsafe visibility work.
- `knowledge_quality_snapshots`: optional persisted explainable quality score snapshots for reporting and low-quality queues.
- `knowledge_gap_findings`: persisted Service Catalog, ticket-volume and feedback-driven knowledge gap findings with accept/dismiss/create-draft workflow.
- `knowledge_search_events`: privacy-preserving search analytics with query hash and redacted query text for zero-result and ticket-after-search analysis.
- `knowledge_segmentation_profiles` / `knowledge_article_segments` / `knowledge_segmentation_jobs`: Knowledge vNext article markup foundation. Manual and auto segments are tied to an immutable item version by offsets plus content hash, carry title/summary/keywords/boost/visibility flags, and can be used by AI-off search before vector/RAG features are enabled.
- `knowledge_taxonomy_terms`, `knowledge_property_definitions`, `knowledge_item_properties`, `knowledge_item_taxonomy_terms`, `knowledge_applicability_rules` and `knowledge_quality_models`: Phase 14 governed metadata model. Taxonomy and typed properties are scoped to a knowledge space; item metadata stores validated property values and taxonomy assignments; applicability rules state explicit include/exclude scope separate from search bindings; quality models add persisted weights and thresholds used by the explainable quality summary. Migration `119` DB-enforces global quality model code uniqueness plus one active default global/per-space model. Phase 14C exposes these rows through `/app/admin/knowledge/metadata` and the Studio item metadata tabs; organization categories/properties remain editable governed data, not frontend constants.
- `ticket_knowledge_links`: normalized future link table. Existing `ticket_kb_links` and `/api/tickets/{id}/kb_links` remain compatible.

## Item Types

Supported item types are:

`article`, `faq`, `runbook`, `policy`, `document`, `known_error`, `workaround`, `troubleshooting_tree`, `glossary_term`, `service_description`, `external_source`, `resolution_draft`.

P4 Problem Management creates and links `known_error` and `workaround` items as Knowledge drafts through the normal Knowledge Platform lifecycle. These drafts default to `support_internal`; requester-safe publication still requires the usual lint/review/publish path and graph/ACL visibility filtering. P4.1 extends the evidence path into the scheduled problem scanner: `not_helpful` and `ticket_created_after_view` feedback can create failed-KB candidates, and open/accepted `knowledge_gap_findings` combined with repeated tickets can create knowledge-gap candidates. Candidate list APIs redact raw requester comments and internal evidence; known-error/workaround requester visibility remains owned by Knowledge Platform review and lint.

## Lifecycle

Item statuses are `draft`, `in_review`, `published`, `needs_review`, `archived`.

Published items must have a current version. The admin publish flow is explicit: create a draft item, create one or more `knowledge_item_versions`, select the latest draft or another version, then publish with that `version_id`. `knowledge_items.current_version_id` is only the current published pointer and is not required before the first publish.

Passport-generated and ingested items are drafts by default and require review before publication. Passport drafts carry `metadata.passport_stale`, `metadata.review_required` and structured `publish_blockers` when the source passport is stale. A stale passport draft cannot publish until an allowed actor supplies explicit stale acknowledgement and a review note. Operational rollback should archive or retire items rather than delete linked knowledge.

## Visibility And ACL

Visibility levels are `public`, `requester`, `agent_requester_safe`, `support_internal`, `admin_internal`, `security_restricted`, `auditor_read`.

Requester and local agent surfaces only receive published requester-safe knowledge. Support can see requester-safe plus `support_internal` knowledge. Auditor is read-only and can see requester-safe, `support_internal` and `auditor_read`, but not `admin_internal` or `security_restricted`. Admin can manage normal knowledge including `admin_internal`; `security_restricted` is admin-accessible until a dedicated security role exists. Search, suggestions, direct item/version reads, graph node lists, graph neighborhoods, ingestion job lists, metrics and future retrieval/RAG must filter by ACL before returning any result.

Requester/agent projections must not expose internal body for restricted items, source ticket/passport ids, requester/device ids, raw custom fields, internal graph edges, queue/policy ids, trace ids, operation ids or raw chunks for restricted items.

## Search And Suggestions

`KnowledgeSearchService` uses PostgreSQL-compatible filtering and text matching over items, versions, chunks, bindings and active article segments. Ranking prefers exact title/slug matches, service/offering/request-template bindings, segment title/keyword matches, text matches, helpfulness and freshness. Segment matches return the owning article with a segment-derived snippet while preserving the same item ACL projection.

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

The requester portal `/app/help` and authenticated requester workspace `/app/requester` insert a knowledge step after service/offering selection. They call `POST /api/knowledge/suggest`, show safe suggestions, record helpful/not helpful/deflected feedback through `POST /api/knowledge/feedback`, and include safe `knowledge_attempts` in ticket creation when the user continues after a viewed or failed article. Authenticated requester tickets store those attempts through the `/api/web/requester/tickets` ownership boundary and also write `ticket_created_after_view` feedback metrics.

The local Qt agent wizard uses the same safe suggestion and feedback APIs through `TicketApiClient.get_knowledge_suggestions()` and `record_knowledge_feedback()`. It continues ticket creation if the knowledge API is unavailable. Protocol V3 is unchanged.

P2.2.1 rollout decisions are returned with suggestion responses and control whether suggestions are shown before or after the form, whether suggestions are required before submit, whether skip is allowed, urgent/high-impact bypass, `min_suggestions`, `max_suggestions`, deflection prompt visibility, known-error visibility, quality/freshness safe labels and no-suggestions/API-unavailable fallback. `max_suggestions=0` intentionally returns no suggestions. Defaults are non-blocking for requester and agent surfaces; admins must explicitly configure `block_submit`.

## Support Workspace

The support workspace knowledge panel keeps the existing `/api/web/support/tickets/{ticket_id}/knowledge-suggestions` shape while merging P2 platform suggestions. The payload also exposes safe `requester_attempts` from ticket `knowledge_attempts` for `surface=requester_portal`; only item/version/result/surface/time fields are returned, and arbitrary attempt metadata is not serialized. Existing `ticket_kb_links` endpoints and `kb_linked` / `kb_unlinked` ticket events remain compatible. The dedicated `/app/knowledge` workspace can also accept `ticket_id` query context, show requester self-service attempts and ticket-scoped suggestions, and use web-session alias `POST /api/web/support/tickets/{ticket_id}/kb_links`, backed by the existing compatibility KB link handler, with `source=knowledge_support_workspace` to emit the redacted Observer event `knowledge.support.ticket_linked`.

Support feedback from `/app/knowledge` reuses `POST /api/knowledge/feedback`: `event_type=support_used` and `surface=support_workspace` emits `knowledge.support.article_used`, while `event_type=not_helpful` plus `result=weak_article_reported` emits `knowledge.support.weak_article_reported`. Runtime audit details carry only safe item/version/ticket/link ids and action metadata, not article bodies or user-entered secret-bearing metadata.

`POST /api/web/support/tickets/{ticket_id}/passport/knowledge-draft` now creates a persisted `knowledge_item` draft and first version from the ticket resolution passport. `/app/knowledge` exposes this as a ticket-context action next to the requester attempts panel. The draft inherits service/offering/request-template bindings from the ticket, stores source ticket/passport ids, marks stale-passport warnings and never publishes automatically.

## Ingestion

P2 supports manual text/markdown ingestion. Ingestion creates a job, draft item, first version and chunks, then moves the job to review-required/completed state. Errors are redacted. Uploaded/imported sources default to internal draft unless an admin explicitly changes visibility and publishes after review.

Knowledge vNext Phase 10 adds the first `/app/admin/knowledge/import` slices. `POST /api/web/knowledge/import/preview` parses `text`, `markdown` and `html` source payloads without AI, detects the title/sections/word count and returns AI enrichment as `disabled` by default or `blocked_pending_policy` when requested. The backend preview path also supports base64 DOCX/PDF uploads with a 5 MiB safe upload limit; DOCX extraction uses stdlib ZIP/XML text extraction, and PDF extraction uses dependency-free literal text extraction for simple PDFs. `url` and `git` source kinds remain fail-closed by default with `remote_import_blocked`; when `KNOWLEDGE_REMOTE_IMPORT_ENABLED=true`, only exact or wildcard hosts from `KNOWLEDGE_REMOTE_IMPORT_ALLOWED_HOSTS` are accepted. URL import requires HTTPS, blocks credentials and redirects, enforces `KNOWLEDGE_REMOTE_IMPORT_MAX_BYTES`, and returns only safe `remote_source` metadata. Git import requires an allowlisted HTTPS repository, clones into a temporary directory with depth/no-tags limits, reads only markdown/text/html files up to configured file/byte limits, maps ingestion jobs to `git_repo`, and returns no query strings, credentials or raw secret-bearing source URLs. `POST /api/web/knowledge/import/create-drafts` reuses the ingestion service to create review-required drafts from the parsed preview payload, can run existing non-AI auto segmentation when `auto_segment_after_import=true` with `segmentation_profile_code` or `default-auto`, and returns `indexing` metadata. If global search settings have `vector_enabled=true`, the import path runs the existing observable item indexing job for the created `item_id` and `version_id`; otherwise the response marks indexing disabled. When `ai_enrichment_enabled=true`, the import path creates governed pending `summary`, `tags`, `glossary_term`, `graph_node` and `duplicate` proposals through `KnowledgeAiProposalService`; review/apply stays behind the existing AI proposal lifecycle and generated payloads do not echo raw import body text or source secrets. Import job read APIs are available at `GET /api/web/knowledge/import/jobs` and `GET /api/web/knowledge/import/jobs/{job_id}` with space-visibility ACL filtering; `GET|POST /api/web/knowledge/ingestion/jobs` remains the compatibility route. Preview, draft creation, remote/policy failures and AI preview policy blocks emit redacted Observer-visible events with source `knowledge_import`: `knowledge.import.preview_created`, `knowledge.import.drafts_created`, `knowledge.import.failed`, `knowledge.import.ai_enrichment_blocked` and `knowledge.import.ai_enrichment_failed`.

## P2.2 Knowledge Operations

P2.2 makes the platform operable day-to-day without replacing the P2/P2.1 contracts.

- Content packs live under `content_packs/knowledge/*.yaml` and are applied with `python scripts/seed_knowledge_content.py --dry-run|--force`. Packs are not migrations and not one-time SQL dumps: the service records source/content hashes, skips unchanged items, reports conflicts when admin-edited content would be overwritten, and requires explicit `--force` for overwrite. Pack binding drift is checked with `python scripts/validate_knowledge_pack_bindings.py --strict`; installed pack-managed binding drift is repaired with `python scripts/repair_knowledge_pack_bindings.py --dry-run --all` followed by the same command without `--dry-run`.
- Content templates are served by `GET /api/web/knowledge/templates` and cover article/how-to, FAQ, troubleshooting, support runbook, known error, workaround, policy/process and glossary structures.
- Review/curation is first-class through `GET /api/web/knowledge/review/tasks`, `POST /api/web/knowledge/review/generate` and task transition routes under `/api/web/knowledge/review/tasks/{task_id}/{assign|start|complete|dismiss}`. The older `GET /api/web/knowledge/review-queue` and item review-action route remain compatibility summaries.
- Quality score is deterministic and explainable. `KnowledgeQualityService` computes completeness, governance, safety, usefulness, freshness and coverage dimensions, while `GET /api/web/knowledge/quality` remains the dashboard summary.
- Gap detection is persisted through `GET /api/web/knowledge/gap-findings`, `POST /api/web/knowledge/gaps/recompute` and accept/dismiss/create-draft actions. It scans published public Service Catalog offerings, ticket counts and knowledge feedback, then reports missing requester articles, missing support runbooks, high-volume no-KB and high-not-helpful gaps.
- Rollout policy management is exposed by `GET|POST /api/web/knowledge/rollout-policies`, plus aliases `GET /api/web/knowledge/rollout`, `POST /api/web/knowledge/rollout/save` and `POST /api/web/knowledge/rollout/effective-preview`. Requester/agent suggestion calls honor the effective policy before search; support/admin/auditor and `support_workspace` remain visible so operations can continue during requester rollout pauses.
- Search analytics are recorded by `KnowledgeSearchAnalyticsService` during knowledge search with hashed/redacted query text; raw requester identifiers, device identifiers and raw custom fields are not stored.
- Phase 12 adds `KnowledgeOpsSummaryService` and `GET /api/web/knowledge/ops/summary` as the first Knowledge Operations Center snapshot. It aggregates existing coverage, quality, search/RAG, indexing, AI, graph, review and Observer v2 degradation signals without adding new tables. The endpoint is the dashboard contract for `/app/admin/knowledge`; deeper event emission and richer Observer mappings remain later Phase 12 slices.
- Phase 14 adds `KnowledgeMetadataService` and `GET /api/web/knowledge/metadata` for governed taxonomy, property definitions, item metadata, applicability rules and quality models. The bundle returns all visible management rows plus `summary` total/active counts; Knowledge Ops uses active counts so draft/archived taxonomy terms and properties do not count as active coverage. Mutations are admin/support only: `POST /api/web/knowledge/taxonomy`, `POST /api/web/knowledge/properties`, `PUT /api/web/knowledge/items/{item_id_or_slug}/metadata`, `POST /api/web/knowledge/items/{item_id_or_slug}/applicability` and `POST /api/web/knowledge/quality-models`. Taxonomy term upsert validates both the parent space visibility and the requested term visibility. Item metadata reads filter assigned taxonomy terms by the actor's visible visibilities, and updates reject taxonomy term assignment when the actor cannot mutate that term visibility. Auditor can read the bundle; requester/public APIs do not receive this admin metadata bundle or quality model diagnostics.
- Phase 14C adds the `/app/admin/knowledge/metadata` management editor and `scripts/seed_knowledge_metadata.py` with optional Russian-first seed data in `content_packs/knowledge/default_metadata.json`. The seed supports dry-run/apply, is idempotent, preserves admin edits unless `--force` is explicit and rejects requester-visible internal/security defaults.

Operational detail and rollback notes live in [KNOWLEDGE_OPERATIONS.md](KNOWLEDGE_OPERATIONS.md).

Requester-safe publication still runs lint checks before publishing. Public/requester content containing internal commands, queue/device/requester ids, raw custom fields, internal runbook language, secrets or security internals is blocked instead of relying on UI discipline.

## Graph

Bindings create service/offering graph edges. Knowledge attempts can create ticket-tried relations. Passport drafts create source relations. P2 exposes a practical neighborhood API with max depth 2 and visibility filtering. Phase 9 graph management adds ACL-filtered search, governed node/edge update/archive endpoints and review-gated AI proposal application; graph deletes archive records (`status=archived`) instead of hard-deleting so audit/history and downstream references remain intact.

Neighborhood responses are a fully visible subgraph. An edge is returned only when the edge visibility is allowed for the actor and both endpoint nodes are also visible and present in `nodes`; traversal never passes through hidden intermediate nodes, and orphan edges to missing or restricted endpoints are dropped before serialization.

## APIs

Requester/agent safe:

- `POST /api/knowledge/search`
- `POST /api/knowledge/suggest`
- `POST /api/knowledge/feedback`

`POST /api/knowledge/search` remains backward-compatible for requester/agent/public consumers and now also returns `search_mode`, `effective_mode`, `ai_used` and a Russian `display_message`. The default mode is AI-off keyword search and does not require configured providers, embeddings or vector indexes.

Admin/support management:

- `GET|POST /api/web/knowledge/search-settings`
- `POST /api/web/knowledge/search`
- `POST /api/web/knowledge/search/preview`
- `POST /api/web/knowledge/retrieve`
- `GET /api/web/knowledge/indexing/status`
- `GET|POST /api/web/knowledge/indexing/jobs`
- `POST /api/web/knowledge/indexing/reindex-item`
- `POST /api/web/knowledge/indexing/reindex-segment`
- `POST /api/web/knowledge/indexing/reindex-space`
- `POST /api/web/knowledge/indexing/reindex-all`
- `GET|POST /api/web/knowledge/spaces`
- `GET|POST /api/web/knowledge/items`
- `GET|POST /api/web/knowledge/segmentation-profiles`
- `PATCH|DELETE /api/web/knowledge/segments/{segment_id}`
- `POST /api/web/knowledge/segments/{segment_id}/approve`
- `POST /api/web/knowledge/segments/{segment_id}/reject`
- `GET /api/web/knowledge/items/{item_id_or_slug}`
- `GET|POST /api/web/knowledge/items/{item_id_or_slug}/segments`
- `POST /api/web/knowledge/items/{item_id_or_slug}/segments/auto`
- `POST /api/web/knowledge/items/{item_id_or_slug}/segments/revalidate`
- `POST /api/web/knowledge/items/{item_id_or_slug}/segments/ai-proposals`
- `POST /api/web/knowledge/items/{item_id_or_slug}/segments/index-sync`
- `GET|POST /api/web/knowledge/items/{item_id_or_slug}/versions`
- `POST /api/web/knowledge/items/{item_id_or_slug}/publish`
- `GET|POST /api/web/knowledge/graph/nodes`
- `GET|PATCH|DELETE /api/web/knowledge/graph/nodes/{node_id_or_stable_key}`
- `GET /api/web/knowledge/graph/search`
- `GET /api/web/knowledge/graph/nodes/{node_id}/neighborhood`
- `GET|POST /api/web/knowledge/graph/edges`
- `GET|PATCH|DELETE /api/web/knowledge/graph/edges/{edge_id}`
- `GET|POST /api/web/knowledge/ai/proposals`
- `POST /api/web/knowledge/ai/proposals/{proposal_id}/review`
- `POST /api/web/knowledge/import/preview`
- `POST /api/web/knowledge/import/create-drafts`
- `GET /api/web/knowledge/import/jobs`
- `GET /api/web/knowledge/import/jobs/{job_id}`
- `GET|POST /api/web/knowledge/ingestion/jobs`
- `GET /api/web/knowledge/ops/summary`
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
- `GET /api/web/knowledge/metadata`
- `POST /api/web/knowledge/taxonomy`
- `POST /api/web/knowledge/properties`
- `GET|PUT /api/web/knowledge/items/{item_id_or_slug}/metadata`
- `GET|POST /api/web/knowledge/items/{item_id_or_slug}/applicability`
- `POST /api/web/knowledge/quality-models`
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
- `POST /api/web/support/tickets/{ticket_id}/kb_links`
- `GET /api/web/support/tickets/{ticket_id}/knowledge-suggestions`
- `POST /api/web/support/tickets/{ticket_id}/passport/knowledge-draft`

## UI

- `/app/admin/knowledge`: Russian-first `Центр операций базы знаний` plus governance/editor route. The top dashboard reads `GET /api/web/knowledge/ops/summary` for coverage, quality, search/RAG, indexing, AI, graph, review and Observer-backed degradation cards, and `GET /api/web/knowledge/metadata` for taxonomy/property/applicability/quality-model counts plus active quality weights. Existing spaces, item draft/version/publish workflow, selected-version publish controls, article retrieval segment markup, stale-passport acknowledgement, content pack operations, review queue, quality score, gap detection, rollout policies, metrics, graph/ingestion foundation and requester-safe preview controls remain below it.
- `/app/admin/knowledge/metadata`: dedicated metadata management workbench for governed taxonomy terms, property definitions, applicability rules and quality models. Admin/support users can create, edit and archive metadata through typed Russian-first forms; auditor remains read-only through the backend, and requester navigation must not expose this route.
- `/app/admin/knowledge/studio`: dedicated Knowledge Authoring Studio route with draft/article browser, new draft creation, article main fields, item metadata tabs (`Таксономия`, `Свойства`, `Применимость`, `Качество`), Markdown editor, template insertion, structured Markdown block insertion, requester-safe preview, selected-version comparison, rollback by publishing an older immutable version, publish checklist, review lifecycle actions, persisted editor history/diff cache, AI-disabled state and embedded retrieval segment markup panel.
- `/app/admin/knowledge/graph`: dedicated Visual Graph Studio route with Russian-first node search, SVG neighborhood canvas, node inspector, selected-node label edit, manual node creation, edge creation, edge/node archive controls, pending graph AI proposal review and persisted canvas layout save/load over graph node/edge/layout/proposal APIs.
- `/app/admin/knowledge/import`: dedicated Import/Ingestion wizard for text, markdown and HTML preview plus AI-off review draft creation through the import preview/create-drafts APIs. The backend preview contract already accepts safe DOCX/PDF base64 uploads, fail-closed-by-default URL/Git source kinds with explicit host allowlist fetch/clone support, optional non-AI auto segmentation after draft creation, indexing metadata that runs the existing item indexing path when `vector_enabled=true`, governed summary/tag/glossary/graph/duplicate AI enrichment proposals behind review, ACL-filtered import job list/detail APIs and redacted Observer-visible `knowledge.import.*` audit events. The UI exposes text/markdown/html/DOCX/PDF/URL/Git source controls, file upload, remote policy messaging, auto-segmentation toggle and segmentation profile selection; richer indexing/proposal controls remain later Phase 10 slices.
- `/app/admin/knowledge/indexing`: Russian-first indexing dashboard for embedding status, disabled/failed/indexed counters, index jobs and item reindex controls. It shows model/status/error metadata but never raw vectors.
- `/app/knowledge`: dedicated support Knowledge Workspace over existing item/version APIs plus optional `ticket_id` query context. It provides fast search, requester-safe/support-internal/type filters, selected article/runbook detail, guarded requester-safe copy action, link-to-ticket, support-used and weak-article reporting actions without admin publish/governance controls.
- `/app/knowledge/articles/:id`: support article/runbook/known-error detail route rendered by the same support workspace and selected by item id or slug.
- `/app/help`: service/offering suggestions, deflection feedback and failed-article attempts before ticket submit.
- `/app/tickets/:ticketId`: existing Knowledge tab receives platform-backed support suggestions and passport-to-draft results.

Knowledge vNext product UI является Russian-first. Новые portal, support, admin, authoring, graph, AI/search/indexing/import/review surfaces должны использовать русские пользовательские labels, validation messages, empty states, toasts и safe error text. Route paths, API fields, enum values, observer event codes и metric names остаются стабильными английскими техническими контрактами. Tests для новых UI pages должны проверять репрезентативный русский copy и ловить mojibake в visible text.

Segment index sync writes active `full_text_enabled` article segments into version-scoped `knowledge_chunks` rows with `metadata_json.source=article_segment`. Chunks with segment embeddings enabled are marked `embedding_status=pending`; actual provider-backed embedding generation belongs to the Phase 4 indexing worker and must keep keyword/full-text search usable when AI is disabled.

Phase 4 indexing stores optional embeddings in `knowledge_chunk_embeddings` and observable jobs in `knowledge_index_jobs`. `KnowledgeEmbeddingService` builds provider input from article title, segment title/summary, keywords, heading path and chunk text; vector-disabled settings or AI policy blocks create `disabled` rows and audit evidence instead of breaking baseline search. Provider/key failures are redacted as safe job/embedding errors, while successful OpenRouter-compatible calls persist vectors only in DB and return no raw vector data through web APIs. Indexing can be scoped to one item, one segment, one space or a bounded full run through dedicated endpoints or `POST /api/web/knowledge/indexing/jobs` with `scope_type=item|segment|space|all`. Import `create-drafts` reuses the same item indexing path when vectors are enabled and returns only safe job/stats/embedding metadata.

`KnowledgeVectorSearchService` provides the Phase 4 JSONB-vector fallback for environments without pgvector. Web search merges vector hits only when `vector_enabled=true` and a safe numeric `query_vector` is supplied. ACL filters run before cosine scoring, requester-safe projection hides diagnostic vector fields, support/admin responses may include `retrieval_source=vector` and `vector_score`, and raw `embedding_vector` values remain DB-only.

Phase 5 retrieval introduces `KnowledgeRetrievalService` for explainable hybrid retrieval previews. It merges keyword, manual segment, binding and optional JSONB-vector candidates after ACL filtering, returns score parts/source modes/citations for admin/support, records search analytics, and writes safe `knowledge.retrieval.executed` / `knowledge.retrieval.zero_results` audit events. Optional OpenRouter-compatible rerank runs only when settings, provider, model profile, policy, secret and injected transport are all available; failures keep the pre-rerank order and emit `knowledge.retrieval.rerank_failed_fallback`. Existing public `POST /api/knowledge/search` remains backward-compatible; `/api/web/knowledge/retrieve` and `/api/web/knowledge/search/preview` expose the richer admin/support contract, `/app/admin/knowledge/search-settings` uses that preview to show source modes, citations and score breakdown, and `/app/kb/search` gives requesters a protected standalone product search over the public-compatible search contract without admin diagnostics.

Phase 6 Ask introduces `KnowledgeAskService` and the `/app/kb/ask` requester route. Ask is disabled unless search settings produce `effective_mode=rag_answer`; disabled/provider-unavailable/no-evidence states return Russian fallback messages plus requester-safe retrieval results. When enabled, Ask uses `KnowledgeRetrievalService` citations, an OpenRouter-compatible `answer` model profile, `ai_policy_profiles.answer_allowed`, env-backed secret refs and injected transport. Raw keys and raw vectors are never returned. AI calls write redacted `ai_request_audit` rows, and Observer-visible events use `knowledge.rag.ai_disabled`, `knowledge.rag.provider_unavailable`, `knowledge.rag.not_enough_evidence`, `knowledge.rag.policy_blocked` and `knowledge.rag.answer_generated`. Answer validation rejects unknown citation markers and critical operational claims that have no valid `[1]..[N]` source marker; rejected answers are stored only as blocked audit evidence and the user receives `not_enough_evidence` fallback. The requester Ask page exposes helpful/not-helpful feedback, correction request and create-ticket actions after answered and AI-off fallback results; feedback and correction reuse the existing article endpoints against the first requester-safe result slug. Ask feedback metadata includes source `knowledge_ask`, answer status, audit id, effective mode, primary item/version/chunk/segment, score and citation count. The create-ticket CTA links to `/app/requester/new` and stores safe Ask context in `pc_client.knowledge_ask.ticket_context`; requester ticket creation consumes it once to prefill title/description and submit existing `knowledge_attempts` with `ticket_created_after_view`, preserving the current requester ticket create backend contract. The support `/app/knowledge` workspace includes an Ask debug panel over `/api/web/knowledge/ask/preview` so support/admin can inspect answer status, effective mode, audit id, chunk/segment ids, source modes and score parts without exposing diagnostics in requester Ask.

Phase 13 starts a repeatable RAG/search evaluation harness. `KnowledgeEvalRecorder` is a lightweight test helper that records `top_k_recall`, `citation_precision`, `no_answer_correctness`, `acl_leakage_count`, `fallback_count`, `latency_ms` and `provider_failure_count` for controlled suites. The current suite seeds requester-safe, support, admin and security knowledge plus manual segments, bindings, JSONB vectors and rerank configuration, then verifies keyword/body recall, ACL-safe result projection, vector recall/fallback, rerank ordering, no-evidence/provider-unavailable Ask fallback, requester-safe citation ids, archived item exclusion and current-version-only search before RAG answers are broadened.

Phase 7 portal adds `KnowledgePortalService` and turns `/app/kb` into a standalone requester Knowledge Portal home. Public-compatible portal APIs force requester ACL even when an authenticated support/admin context exists: `GET /api/knowledge/portal/home`, `GET /api/knowledge/portal/spaces/{space_code}`, `GET /api/knowledge/portal/tags/{tag}`, `GET /api/knowledge/articles/{slug}`, `POST /api/knowledge/articles/{slug}/feedback`, `POST /api/knowledge/articles/{slug}/correction-request` and `POST|DELETE /api/knowledge/articles/{slug}/bookmark`. Article detail returns requester-safe item metadata, selected published body, active requester-visible segments and empty related-article placeholders without `source_refs`, raw metadata or admin diagnostics. Migration `114` adds persisted portal state tables: article reads write `knowledge_article_views`, bookmark add/remove upserts `knowledge_user_bookmarks`, correction requests write `knowledge_correction_requests` with the user-entered comment, and `knowledge_article_subscriptions` is reserved for later article-update notifications. Feedback still writes `knowledge_feedback_events`, and portal home ranks `popular_articles` / `featured_articles` from view, active bookmark, helpful feedback and open correction signals before falling back to recent articles. React routes now include `/app/kb`, `/app/kb/articles/:slug`, `/app/kb/spaces/:spaceCode` and `/app/kb/tags/:tag` alongside existing search and Ask; the article reader includes a correction comment form instead of a fixed correction request string.

Phase 8 authoring history adds `KnowledgeEditorHistoryService`, migration `115`, and `GET /api/web/knowledge/items/{item_id_or_slug}/editor-history` for admin/support/auditor users. Studio draft creation, version creation, publish/rollback and review actions now write `knowledge_article_editor_events`; version creation also upserts `knowledge_version_diff_cache` with safe line-count summaries and content hash. Review actions include submit, comment, approve, request changes and archive/supersede. The editor-history API returns event metadata and diff summaries only, not article body, raw metadata, source refs, ticket/device fields or secret material. React `/app/admin/knowledge/studio` renders `История редактора` with latest events and `Diff cache: +N / -N`, plus structured Markdown insertion controls for callout, table, code block and checklist blocks.

## Knowledge vNext Target Routes

Phase 0 фиксирует целевые границы, но не регистрирует недоделанные runtime routes. Реализация должна вводить эти поверхности по фазам:

| Route | Назначение | Фаза |
|---|---|---|
| `/app/kb` | Standalone requester Knowledge Portal home over `GET /api/knowledge/portal/home` | Portal |
| `/app/kb/search` | Реализованный самостоятельный поиск по базе знаний через `POST /api/knowledge/search` | Search |
| `/app/kb/ask` | Реализованный AI Ask с citations, AI-off/provider fallback и requester-safe результатами | RAG |
| `/app/kb/articles/:slug` | Requester-safe article reader | Portal |
| `/app/kb/spaces/:spaceCode` | Requester-safe space collection page | Portal |
| `/app/kb/tags/:tag` | Requester-safe tag collection page | Portal |
| `/app/knowledge` | Рабочая база знаний поддержки | Support workspace |
| `/app/knowledge/articles/:id` | Support article/runbook/known-error view | Support workspace |
| `/app/admin/knowledge` | Knowledge Ops dashboard | Ops |
| `/app/admin/knowledge/studio` | Authoring Studio для статей и версий | Authoring |
| `/app/admin/knowledge/graph` | Visual Graph Studio | Graph |
| `/app/admin/knowledge/ai` | AI providers, model profiles, policies, health | AI settings |
| `/app/admin/knowledge/search-settings` | Настройки search/retrieval, explainable preview and score breakdown | Search settings |
| `/app/admin/knowledge/indexing` | Indexing jobs, embeddings, stale state | Indexing |
| `/app/admin/knowledge/import` | Import/Ingestion wizard | Import |
| `/app/admin/knowledge/review` | Review and curation queue | Review |

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

## P5 Change Enablement Integration

Changes may reference known-error, workaround, runbook or documentation follow-up context through metadata and improvement actions. P5 does not publish requester-facing knowledge directly: successful changes and PIR lessons can create improvement actions for `update_kb_article` or `create_kb_article`, and requester-safe publication still goes through Knowledge Platform review/lint/publish.

## Service Catalog Integration

Knowledge binds to service/offering/request-template. Policy Health and gap detection use canonical Service Catalog defaults, not stale content-pack aliases. Policy Health includes a warning when a published public service/offering has no requester-safe published knowledge binding. Service Catalog and requester preview may use knowledge counts/hints without exposing internal article names.

## Rollback

Migration `083` is additive. P2.1 migration `084` adds DB CHECK constraints for graph node/edge enums, entity mention states, feedback event/surface roles, ingestion source/status values and ticket-knowledge link enums. P2.2 migration `085` is additive for content-pack audit and rollout policy tables. P2.2 migration `086` adds review tasks/comments, quality snapshots, gap findings and search analytics. P2.2.1 migration `087` hardens rollout policies and content-pack binding repair audit status. P3 migration `088` adds ticket-quality tables that can reference knowledge failure signals operationally but do not own knowledge content. Operational rollback can disable requester/agent suggestions with a rollout policy and disable P3 quality triggers while leaving Service Catalog, support workspace and ticket creation intact; downgrade of `087` removes rollout hardening columns, downgrade of `086` removes only operations state and downgrade of `085` removes only pack/rollout audit state. Existing `ticket_kb_links` remains the compatibility fallback. Linked knowledge should be archived, not hard-deleted.
