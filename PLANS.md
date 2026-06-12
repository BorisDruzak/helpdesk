## Active Work: Knowledge Platform vNext — Product KB, RAG, AI Settings, Manual Markup, Graph Studio and Observer v2

Status: accepted / implementation plan.

Branch target:

* Work on a new branch, for example `codex/knowledge-platform-vnext-rag`.
* Keep all changes incremental, tested, documented and backward-compatible with the existing helpdesk Knowledge Platform contracts.

Goal:

* Turn the current Knowledge Platform from a helpdesk-adjacent admin module into a product-grade organization knowledge base.
* Preserve and extend the existing foundation: `knowledge_spaces`, `knowledge_items`, versions, chunks, bindings, graph, feedback, metrics, gap findings, review tasks and deflection.
* Add a standalone Knowledge Portal, a proper article editor, visual graph editor, AI/RAG settings, OpenRouter integration, manual/auto/AI article segmentation, hybrid search, AI-off fallback mode and Observer v2 integration.
* Ensure the system works without AI enabled. AI must be optional, configurable, observable and safe.

Non-negotiable principles:

* Do not replace the existing Knowledge Platform. Extend it.
* AI must never be required for baseline search, article viewing, manual article editing, manual markup, graph editing or helpdesk linking.
* AI-generated content must never be auto-published. It must create proposals, drafts, segments or review tasks.
* Retrieval and RAG must be ACL-first. Filter by actor role, visibility, space policy and item/version status before vector search, rerank or answer generation.
* No API keys in git, docs examples, tests, screenshots or browser logs.
* OpenRouter API testing is allowed only when the user provides a key through the intended secret/config location.
* The user must be able to disable embeddings, rerank, answer generation, rewrite, auto-markup and all AI features independently.
* Every new product path must have tests, docs and live/browser verification evidence when the UI becomes testable.
* Integrate with Observer v2 from the start: health, jobs, audit, degradations, policy blocks, indexing failures, search failures, AI provider failures and RAG answer quality signals must be visible as observer events/metrics.

Локализация и языковая политика:

* Knowledge vNext должен быть Russian-first для всех пользовательских поверхностей: портал, support workspace, админский Knowledge Ops, authoring, graph, AI settings, search/indexing/import/review pages, диалоги, empty states, validation messages, toasts и browser/live evidence notes.
* Стабильные технические контракты остаются на английском: route paths, API field names, enum values, migration identifiers, observer event codes, metric names, model/profile task codes и log categories.
* Backend errors должны сохранять machine-readable codes и возвращать безопасные русские пользовательские сообщения для web/GUI consumers.
* Docs и handoff notes для операторов должны быть на русском, когда описывают продуктовое поведение или ручные live checks. Низкоуровневые code comments могут оставаться на английском, если объясняют implementation details.
* Тесты для UI-фаз должны проверять репрезентативные русские labels и отсутствие mojibake в rendered visible text.
* Тексты настройки OpenRouter/AI должны быть на русском и явно объяснять, куда оператор вводит ключ, но никогда не показывать raw key.

Current baseline context:

* The repo already contains a Knowledge Platform with spaces, items, immutable versions, chunks, bindings, graph nodes/edges/entity mentions, feedback events, ingestion jobs, ticket knowledge links, review tasks, quality snapshots, gap findings and search events.
* Current search is PostgreSQL-compatible keyword matching over title/summary/slug/chunk text with basic scoring. It is not yet product-grade hybrid search or RAG.
* Current `/app/admin/knowledge` is an operations/admin panel. Current `/app/knowledge` reuses the same panel in support mode. This must be split into separate product surfaces.
* Current ingestion is closer to text/markdown draft ingestion. PDF/DOCX/HTML/Git/API ingestion contracts exist conceptually but need real product implementation.
* Current graph foundation exists on the backend, but the UI does not expose a real visual graph editor.

Target product surfaces:

* `/app/kb`

  * Organization Knowledge Portal for end users.
* `/app/kb/search`

  * Standalone search experience.
* `/app/kb/ask`

  * AI answer with citations, only when enabled.
* `/app/kb/articles/:slug`

  * Requester-safe article reader.
* `/app/knowledge`

  * Support Knowledge Workspace.
* `/app/knowledge/articles/:id`

  * Support article/runbook/known-error view.
* `/app/admin/knowledge`

  * Knowledge Ops dashboard.
* `/app/admin/knowledge/studio`

  * Product article editor / authoring studio.
* `/app/admin/knowledge/graph`

  * Visual graph editor.
* `/app/admin/knowledge/ai`

  * AI providers, model profiles, policies and health.
* `/app/admin/knowledge/search-settings`

  * Search/retrieval settings.
* `/app/admin/knowledge/indexing`

  * Chunk/embedding/indexing jobs.
* `/app/admin/knowledge/import`

  * Document ingestion wizard.
* `/app/admin/knowledge/review`

  * Review and curation queue.

Architecture boundaries:

* `Knowledge Core`

  * spaces, items, versions, chunks, segment markup, ACL, tags, taxonomy, bindings, graph.
* `Knowledge Search`

  * keyword/full-text search, vector search, hybrid retrieval, rerank, explainable score.
* `Knowledge AI`

  * providers, model profiles, policies, rewrite, summarize, classify, markup, embeddings, rerank, answer.
* `Knowledge Portal`

  * end-user reading, search, ask, feedback.
* `Knowledge Authoring`

  * article editor, manual markup, templates, version diff, comments, review.
* `Knowledge Graph`

  * graph nodes/edges, visual graph editor, AI-suggested links.
* `Knowledge Ops`

  * quality, gaps, review, rollout, indexing, provider health, Observer v2.
* `Helpdesk Adapter`

  * ticket suggestions, deflection, ticket links, passport-to-draft, known errors, support runbooks.

Do not let `Knowledge Core` depend on ticket-specific code. Ticket/helpdesk code may depend on Knowledge through adapter services.

---

## Phase 0 — Discovery, constraints and plan scaffolding

Goal:

* Prepare the codebase for a large but controlled Knowledge Platform vNext implementation.

Scope:

* Review current knowledge files, routes, tests and migrations.
* Map current backend and frontend ownership.
* Confirm current Alembic head and migration naming.
* Add this plan to `PLANS.md` as the active work section.
* Add/update docs placeholders for the new architecture.

Expected files to inspect:

* `server/docs/KNOWLEDGE_PLATFORM.md`
* `server/docs/KNOWLEDGE_OPERATIONS.md`
* `server/app/db/migrations/versions/*knowledge*.py`
* `server/app/repos/knowledge_repo.py`
* `server/knowledge/*.py`
* `server/web_api/knowledge_handlers.py`
* `webapp/src/features/knowledge/*`
* `webapp/src/pages/admin/knowledge-page.tsx`
* `webapp/src/pages/knowledge/index.tsx`
* `webapp/src/app/navigation.tsx`
* `PLANS.md`
* `docs/ARCHITECTURE_BOUNDARIES.md`
* `docs/QUICK_LOOKUP.md`
* `server/docs/CODEMAP.md`
* `webapp/src/app/router.tsx`

Implementation tasks:

* Document current baseline in `PLANS.md`.
* Add a short `server/docs/KNOWLEDGE_VNEXT_ARCHITECTURE.md`.
* Add a `docs/QUICK_LOOKUP.md` entry for Knowledge vNext.
* Зафиксировать Russian-first UI/docs localization как cross-phase acceptance invariant.
* Add no runtime behavior changes in this phase.

Tests:

* No new product tests required yet.
* Run existing focused knowledge tests if practical.

Verification:

* `git diff --check`
* `git diff --cached --check`
* `python -m compileall -q server shared scripts`
* Проверить docs/UI plan text на mojibake и случайные англоязычные пользовательские тексты на новых Knowledge vNext surfaces.
* Existing focused knowledge tests if available.

Exit criteria:

* Plan is recorded.
* Architecture docs identify boundaries and future routes.
* Ожидания русской локализации явно зафиксированы для каждой последующей UI/API-message phase.
* No runtime behavior changed.

Phase 0 current state, 2026-06-11:

* Active plan and Russian-first localization policy are recorded.
* `server/docs/KNOWLEDGE_VNEXT_ARCHITECTURE.md` exists and defines Knowledge vNext boundaries, AI/search safety, target product routes, localization and Observer v2 expectations.
* `server/docs/KNOWLEDGE_PLATFORM.md`, `server/docs/KNOWLEDGE_OPERATIONS.md`, `server/docs/CODEMAP.md`, `docs/ARCHITECTURE_BOUNDARIES.md` and `docs/QUICK_LOOKUP.md` include Knowledge vNext target-route and Russian-first scaffolding.
* Runtime route registration, DB migrations, API handlers and webapp pages are intentionally not changed in Phase 0.
* Next implementation step is Phase 1 backend-first AI provider settings with OpenRouter mocked tests and Russian UI/API display-message requirements.

---

## Phase 1 — AI provider settings, model profiles and safe OpenRouter integration

Goal:

* Add configurable AI provider infrastructure.
* Support OpenRouter first.
* Leave room for local/Ollama/OpenAI-compatible providers later.
* Ensure all AI features can be disabled.

Important user action:

* For live OpenRouter testing, the user must provide an API key through the approved local secret/config location.
* Do not commit the key.
* Do not print the key.
* Do not include the key in screenshots.
* Recommended initial location for local testing:

  * `.env.local` or server environment variable: `OPENROUTER_API_KEY`
  * Admin UI secret input: `/app/admin/knowledge/ai`
* Codex must implement the UI/config path and then ask the operator to enter the key there. Codex must not invent or hardcode a key.

Backend schema:

Add migrations for:

* `ai_providers`

  * `provider_id`
  * `code`
  * `title`
  * `provider_type`: `openrouter`, `openai_compatible`, `ollama`, `local_custom`
  * `base_url`
  * `auth_type`: `api_key`, `bearer`, `none`, `custom_header`
  * `api_key_secret_ref`
  * `default_headers_json`
  * `data_policy`: `local_only`, `cloud_allowed`, `no_sensitive`, `allow_public`
  * `enabled`
  * `health_status`
  * `last_health_check_at`
  * `last_error_redacted`
  * `metadata_json`
  * `created_at`, `updated_at`, `created_by`, `updated_by`

* `ai_model_profiles`

  * `profile_id`
  * `provider_id`
  * `code`
  * `title`
  * `task_type`: `chat`, `embedding`, `rerank`, `rewrite`, `summarize`, `classify`, `extract`, `answer`, `markup`, `moderation`
  * `model_name`
  * `context_window`
  * `embedding_dimensions`
  * `timeout_ms`
  * `max_retries`
  * `temperature`
  * `top_p`
  * `structured_output_supported`
  * `streaming_supported`
  * `enabled`
  * `is_default`
  * `fallback_profile_id`
  * `metadata_json`
  * timestamps/audit fields

* `ai_policy_profiles`

  * `policy_id`
  * `scope_type`: `global`, `space`, `visibility`, `task_type`
  * `space_id`
  * `visibility`
  * `task_type`
  * `enabled`
  * `ai_allowed`
  * `embedding_allowed`
  * `rerank_allowed`
  * `answer_allowed`
  * `rewrite_allowed`
  * `auto_markup_allowed`
  * `require_local_for_security_restricted`
  * `allow_cloud_for_requester_safe`
  * `redact_before_send`
  * `store_prompts`
  * `store_outputs`
  * `max_tokens_per_request`
  * `max_requests_per_day`
  * `max_cost_per_day`
  * `metadata_json`

* `ai_request_audit`

  * `request_id`
  * `provider_id`
  * `model_profile_id`
  * `task_type`
  * `actor_id`
  * `actor_role`
  * `source_surface`
  * `status`
  * `latency_ms`
  * `token_input`
  * `token_output`
  * `cost_estimate`
  * `prompt_hash`
  * `output_hash`
  * `error_redacted`
  * `created_at`
  * `metadata_json`

Secret handling:

* Implement a minimal safe secret abstraction.
* For v1, support env-backed secret refs:

  * `env:OPENROUTER_API_KEY`
* Optional encrypted DB secret storage may be added only if the project already has a safe pattern.
* Never return raw secrets from API.
* UI must show masked secret state only.

Backend services:

Add:

* `server/ai/contracts.py`
* `server/ai/provider_registry.py`
* `server/ai/openrouter_client.py`
* `server/ai/openai_compatible_client.py`
* `server/ai/policies.py`
* `server/ai/audit.py`
* `server/ai/health.py`
* `server/ai/tasks.py`

Required task methods:

* `chat_completion`
* `generate_embedding`
* `rerank`
* `rewrite_text`
* `summarize_text`
* `classify_text`
* `extract_json`
* `markup_article_segments`

OpenRouter endpoints to support:

```text
POST /api/v1/chat/completions
POST /api/v1/embeddings
POST /api/v1/rerank
```

Do not make network calls in normal unit tests. Use fake HTTP transport/mocks.

Admin APIs:

* `GET /api/web/knowledge/ai/providers`
* `POST /api/web/knowledge/ai/providers`
* `PATCH /api/web/knowledge/ai/providers/{provider_id}`
* `POST /api/web/knowledge/ai/providers/{provider_id}/health-check`
* `GET /api/web/knowledge/ai/model-profiles`
* `POST /api/web/knowledge/ai/model-profiles`
* `PATCH /api/web/knowledge/ai/model-profiles/{profile_id}`
* `GET /api/web/knowledge/ai/policies`
* `POST /api/web/knowledge/ai/policies`
* `GET /api/web/knowledge/ai/audit`

UI:

* Add `/app/admin/knowledge/ai`.
* Sections:

  * Providers.
  * Model profiles.
  * Task defaults.
  * AI policies.
  * OpenRouter key status.
  * Health check.
  * Recent audit/errors.
* Add toggles:

  * Global AI enabled.
  * Embeddings enabled.
  * Rerank enabled.
  * Ask/answer enabled.
  * Rewrite enabled.
  * AI markup enabled.
  * Cloud providers allowed.
* Add clear warning:

  * `security_restricted` content must not be sent to cloud providers unless an explicit admin policy allows it.
  * Все видимые тексты AI settings, disabled/fallback states, health-check results и safe secret-entry instructions должны быть на русском.

Observer v2:

* Emit observer events:

  * `knowledge.ai.provider_health_failed`
  * `knowledge.ai.provider_health_ok`
  * `knowledge.ai.policy_blocked`
  * `knowledge.ai.request_failed`
  * `knowledge.ai.secret_missing`
* Add observer metrics:

  * AI request count by task.
  * AI failure count by provider.
  * AI latency p95 if existing observer aggregation supports it.
* Add admin tech/observer visibility where current observer UI allows.

TDD checkpoints:

* RED tests for AI provider CRUD.
* RED tests for env secret masking and no raw key in responses.
* RED tests for OpenRouter client request construction using mocked HTTP.
* RED tests for health check success/failure.
* RED tests for policy blocking cloud use for `security_restricted`.
* RED tests for audit record creation.
* RED webapp tests for provider settings UI, toggles, masked secret state and health result.
* RED webapp tests для репрезентативных русских labels и mojibake-free visible AI settings text.
* RED observer tests for provider failure event emission if existing observer test patterns exist.

Verification:

* Focused pytest:

  * `server/tests/test_ai_provider_settings.py`
  * `server/tests/test_ai_openrouter_client.py`
  * `server/tests/test_ai_policy_profiles.py`
  * `server/tests/test_ai_observer_events.py`
* Focused Vitest:

  * `webapp/src/features/knowledge/ai-settings-page.test.tsx`
* Compile/build:

  * `python -m compileall -q server shared scripts`
  * `pnpm --dir webapp test -- src/features/knowledge/ai-settings-page.test.tsx`
  * `pnpm --dir webapp build`
  * `git diff --check`

Live checks:

* Start server and webapp.
* Open `/app/admin/knowledge/ai`.
* Add OpenRouter provider.
* User enters API key in the intended secret/config location.
* Run health check.
* Confirm:

  * success state if key is valid;
  * failure state if key is invalid/missing;
  * key is masked;
  * browser console has no secret leakage;
  * observer event is created for success/failure.
* Capture browser evidence/screenshots for:

  * provider configured;
  * masked key;
  * health check result;
  * observer/tech event.

Exit criteria:

* OpenRouter can be configured safely.
* All AI functionality is disabled by default unless explicitly enabled.
* No AI feature is required for baseline KB operation.
* Observer v2 records AI health/failure/policy-block events.

Phase 1 current state, 2026-06-11:

* Backend foundation is implemented for the first safe AI settings slice.
* Migration `110` adds `ai_providers`, `ai_model_profiles`, `ai_policy_profiles` and `ai_request_audit`.
* `server/ai/provider_registry.py` persists providers, model profiles, policy rows and redacted audit data without returning raw secret references.
* `server/ai/openrouter_client.py` supports mocked OpenRouter-compatible chat completion, embedding and rerank requests.
* Current backend user-visible `display_message` text is Russian; route paths, field names, enum values and task codes remain English technical contracts.
* Runtime API handlers are implemented for provider list/create/patch, model profile list/create/patch, policy list/upsert, provider health-check and AI audit list under `/api/web/knowledge/ai/*`.
* Provider health-check uses mocked transport in tests, never returns raw keys, records redacted `ai_request_audit` rows and emits Observer-visible runtime audit events `knowledge.ai.provider_health_ok` / `knowledge.ai.provider_health_failed`.
* React `/app/admin/knowledge/ai` is registered in the admin Knowledge domain and renders Russian-first provider/model/policy/audit controls with masked secret state and health-check action.
* Focused frontend tests cover typed AI settings API, navigation, Russian visible labels and mojibake/secret-leak checks.
* Next Phase 1 follow-up is live browser validation against the deployed admin shell when the server/webapp bundle is released and an operator supplies the OpenRouter key through the approved secret/config path.

---

## Phase 2 — Search settings and AI-off baseline search

Goal:

* Build a strong non-AI search foundation before embeddings/RAG.
* Ensure the KB is useful with AI disabled.

Backend:

Add `knowledge_search_settings` table:

* `settings_id`
* `scope_type`: `global`, `space`, `surface`, `actor_role`
* `space_id`
* `surface`
* `actor_role`
* `keyword_enabled`
* `full_text_enabled`
* `vector_enabled`
* `rerank_enabled`
* `ai_query_rewrite_enabled`
* `graph_boost_enabled`
* `binding_boost_enabled`
* `manual_segment_boost_enabled`
* `quality_boost_enabled`
* `freshness_boost_enabled`
* `feedback_boost_enabled`
* `title_weight`
* `summary_weight`
* `body_weight`
* `chunk_weight`
* `manual_segment_weight`
* `binding_weight`
* `graph_weight`
* `quality_weight`
* `freshness_weight`
* `helpfulness_weight`
* `max_results`
* `snippet_length`
* `highlight_enabled`
* `zero_result_logging_enabled`
* `metadata_json`
* timestamps/audit fields

Search modes:

* `keyword_only`
* `full_text`
* `hybrid_no_ai`
* `hybrid_vector`
* `hybrid_vector_rerank`
* `rag_answer`

Important:

* `keyword_only`, `full_text` and `hybrid_no_ai` must work without any AI provider, embedding or vector index.
* If AI is disabled or provider unavailable, search must gracefully fall back to non-AI search.

Phase 2 current state, 2026-06-12:

* Backend foundation is implemented for the first AI-off search settings slice.
* Migration `111` adds the global `knowledge_search_settings` table with mode flags, AI/vector/rerank/rewrite/RAG switches disabled by default, result/snippet limits, weights, metadata and audit fields.
* `server/knowledge/search_settings_service.py` returns Russian-safe API defaults without requiring a stored row and computes `effective_mode`/`ai_enabled` deterministically from settings.
* Admin-only web API routes are available:

  * `GET /api/web/knowledge/search-settings`
  * `POST /api/web/knowledge/search-settings`
* `POST /api/web/knowledge/search` is available for authenticated admin/support/auditor web consumers and reuses the existing ACL-filtered keyword search path.
* Existing `POST /api/knowledge/search` remains backward-compatible and now also returns `search_mode`, `effective_mode`, `ai_used` and a Russian `display_message`.
* Search still runs without AI providers or embeddings; unknown analytics `surface` values are normalized to `search` to avoid CHECK-constraint 500s.
* React `/app/admin/knowledge/search-settings` is registered in the admin Knowledge domain and renders Russian-first controls for search mode, keyword/full-text/vector/rerank/rewrite/RAG toggles, weights, `max_results`, `snippet_length` and a search preview panel backed by `POST /api/web/knowledge/search`.
* Focused frontend tests cover typed search-settings/search-preview API, navigation, Russian visible labels, AI-off state, preview result rendering and mojibake checks.
* Live browser validation on deployed commit `d27a6bb1` confirmed `/app/admin/knowledge/search-settings` loads in the admin shell, shows AI-off `keyword_only`, runs preview query `VPN`, returns results without AI, and has no browser console warnings/errors. Evidence screenshot: `artifacts/browser_live_validation/knowledge-search-preview-d27a6bb1.png`.
* Next implementation step is Phase 3 article segmentation and markup: backend schema/service slice first, with manual/auto segmentation working without AI before AI-assisted proposals.

Backend service changes:

* Replace or wrap current `KnowledgeSearchService` with:

  * `KnowledgeSearchSettingsService`
  * `KnowledgeKeywordSearchService`
  * `KnowledgeFullTextSearchService`
  * `KnowledgeHybridSearchService`
  * `KnowledgeSearchAnalyticsService` compatibility.
* Keep old `/api/knowledge/search` shape backward-compatible.

APIs:

* `GET /api/web/knowledge/search-settings`
* `POST /api/web/knowledge/search-settings`
* `POST /api/knowledge/search`
* `POST /api/web/knowledge/search`

UI:

* Add `/app/admin/knowledge/search-settings`.
* Controls:

  * search mode;
  * enable/disable keyword;
  * enable/disable full-text;
  * enable/disable vector;
  * enable/disable rerank;
  * enable/disable query rewrite;
  * scoring weights;
  * max results;
  * snippet length;
  * boost manual segments;
  * boost bindings;
  * boost graph;
  * boost quality/freshness/helpfulness.
* Add preview panel:

  * query input;
  * selected actor role;
  * selected surface;
  * explain score;
  * show fallback mode when vector/AI disabled.

Observer v2:

* Emit:

  * `knowledge.search.executed`
  * `knowledge.search.zero_results`
  * `knowledge.search.fallback_used`
  * `knowledge.search.failed`
* Include safe metadata only:

  * query hash;
  * redacted query;
  * result count;
  * mode;
  * actor role;
  * surface;
  * no requester/device raw identifiers.

TDD checkpoints:

* RED tests for default search settings.
* RED tests for disabling AI/vector and still returning keyword results.
* RED tests for scoring weights.
* RED tests for fallback mode.
* RED tests for ACL-first filtering.
* RED webapp tests for settings UI and search preview.

Verification:

* `python -m pytest server/tests/test_knowledge_search_settings.py server/tests/test_knowledge_search_fallback.py -v --tb=short`
* Existing knowledge search tests.
* `pnpm --dir webapp test -- src/features/knowledge/search-settings-page.test.tsx`
* `pnpm --dir webapp build`
* `python -m compileall -q server shared scripts`
* `git diff --check`

Live checks:

* Disable AI globally.
* Create/publish requester-safe article.
* Search by title.
* Search by body text.
* Search by service/offering binding.
* Confirm results work without embeddings.
* Confirm observer shows search events and zero-result events.
* Capture screenshots:

  * search settings with AI disabled;
  * search preview returning results;
  * observer event.

Exit criteria:

* KB search is useful without AI.
* Search behavior is configurable from UI.
* AI/vector failure does not break search.

---

## Phase 3 — Article segmentation and markup: manual, auto and AI-assisted

Goal:

* Add product-grade article segmentation for search and embeddings.
* Let editors control retrieval quality by marking semantic segments manually.
* Support three segmentation modes:

  * manual markup;
  * automatic structural/paragraph/length segmentation;
  * AI-assisted semantic markup.
* Do not require AI for segmentation.

Status 2026-06-12:

* Phase 3A backend slice is implemented without AI:

  * migration `112` adds `knowledge_article_segments`, `knowledge_segmentation_profiles` and `knowledge_segmentation_jobs`;
  * `KnowledgeSegmentationService` supports manual segment create/list/update/archive, segmentation profile create/list and heading/paragraph auto segmentation jobs;
  * routes are live for `GET|POST /api/web/knowledge/items/{item_id_or_slug}/segments`, `POST /api/web/knowledge/items/{item_id_or_slug}/segments/auto`, `PATCH|DELETE /api/web/knowledge/segments/{segment_id}` and `GET|POST /api/web/knowledge/segmentation-profiles`;
  * active segment title/text/keywords contribute to AI-off Knowledge search snippets/scoring;
  * tests: `server/tests/test_knowledge_segments.py` and `server/tests/test_knowledge_search_segments.py`.
* Phase 3B frontend slice is implemented on the current `/app/admin/knowledge` editor route:

  * `ArticleSegmentationPanel` lets an editor select text from the chosen immutable version body and create manual retrieval segments with title, keywords, visibility, boost and full-text/embedding flags;
  * the panel lists active segments for the selected version and supports archive actions;
  * auto segmentation can be started from available segmentation profiles without requiring AI;
  * typed webapp API helpers cover segment list/create/update/archive, auto segmentation and profile list/create endpoints;
  * tests: `webapp/src/features/knowledge/article-segmentation-panel.test.tsx` and the segmentation block in `webapp/src/features/knowledge/api.test.ts`.
* Phase 3C/3D/3E backend/API slice is implemented:

  * `POST /api/web/knowledge/items/{item_id_or_slug}/segments/revalidate` copies active/draft/stale segments from one immutable version to another, exact-remaps offsets when text still exists, and creates stale target-version copies when text no longer matches;
  * `KnowledgeSegmentationService` writes Observer-visible `agent_runtime_audit` rows for manual create/update/archive, auto segmentation, remap/revalidation, AI policy blocks and AI proposal approve/reject decisions;
  * `POST /api/web/knowledge/items/{item_id_or_slug}/segments/ai-proposals` is gated by enabled `ai_policy_profiles` with `ai_allowed=true` and `auto_markup_allowed=true` for `task_type=markup`;
  * AI proposals are created as `segment_type=ai_proposed`, `status=draft`, `source=ai_markup` and do not affect active search until an admin/support operator approves them;
  * `POST /api/web/knowledge/segments/{segment_id}/approve` promotes draft AI proposals to `ai_approved` + `active`, while `POST /api/web/knowledge/segments/{segment_id}/reject` marks them `rejected` with redacted metadata;
  * typed webapp API helpers cover segment revalidation, AI proposals and approve/reject actions;
  * tests: `server/tests/test_knowledge_segments.py` covers remap, stale copy, AI policy block audit, proposal approve and proposal reject flows.
* Phase 3F/3G route and index-sync slice is implemented:

  * dedicated React route `/app/admin/knowledge/studio` is registered in the Knowledge admin domain and reuses the current article editor/segmentation surface as the initial Authoring Studio;
  * `POST /api/web/knowledge/items/{item_id_or_slug}/segments/index-sync` rewrites version-scoped `knowledge_chunks` rows from active `full_text_enabled` retrieval segments with `metadata_json.source=article_segment`;
  * synced chunks preserve segment visibility/text/content hash, record `segment_id` metadata and mark embedding work as `embedding_status=pending` when the source segment has embeddings enabled;
  * index sync creates a completed `knowledge_segmentation_jobs` row and emits Observer-visible `knowledge.segmentation.index_synced` audit evidence;
  * typed webapp API helpers and focused tests cover the route, navigation, chunk write and audit contract.
* Phase 3 is complete enough for Phase 4 handoff. The next implementation step is Phase 4 embeddings/vector indexing: generate provider-backed or safely stubbed embedding refs for pending segment chunks without making AI mandatory.

Terminology:

* Use “segments” or “retrieval segments” in the product UI.
* Existing `knowledge_chunks` may remain as the low-level retrieval unit.
* Manual article markup should create explicit segment records that generate chunks and/or override chunk metadata.

Backend schema:

Add:

* `knowledge_article_segments`

  * `segment_id`
  * `item_id`
  * `version_id`
  * `segment_index`
  * `segment_type`: `manual`, `auto`, `ai_proposed`, `ai_approved`
  * `title`
  * `summary`
  * `text`
  * `start_offset`
  * `end_offset`
  * `heading_path_json`
  * `keywords_json`
  * `boost`
  * `visibility`
  * `embedding_enabled`
  * `full_text_enabled`
  * `status`: `draft`, `active`, `stale`, `archived`, `rejected`
  * `source`: `editor_selection`, `paragraph_split`, `length_split`, `heading_split`, `ai_markup`
  * `content_hash`
  * `created_by`
  * `updated_by`
  * timestamps
  * `metadata_json`

* `knowledge_segmentation_profiles`

  * `profile_id`
  * `code`
  * `title`
  * `mode`: `auto`, `manual_default`, `ai`
  * `split_by_headings`
  * `split_by_paragraphs`
  * `target_tokens`
  * `max_tokens`
  * `min_tokens`
  * `overlap_tokens`
  * `preserve_tables`
  * `preserve_code_blocks`
  * `default_segment_boost`
  * `ai_profile_id`
  * `enabled`
  * `metadata_json`

* `knowledge_segmentation_jobs`

  * `job_id`
  * `item_id`
  * `version_id`
  * `profile_id`
  * `mode`
  * `status`
  * `created_by`
  * `started_at`
  * `completed_at`
  * `stats_json`
  * `error_redacted`

Manual markup behavior:

* Editor selects text in the article editor.
* Editor creates a segment:

  * title;
  * optional summary;
  * keywords;
  * boost;
  * visibility;
  * embedding enabled yes/no;
  * full-text enabled yes/no.
* Segment text must remain tied to version content using offsets and content hash.
* If the version body changes, affected segments become `stale` and require review or remapping.
* Manual segments should boost retrieval and create clearer citations.

Auto segmentation behavior:

* Split by headings first.
* Then paragraphs.
* Then length/token target.
* Keep code blocks/tables together where possible.
* Generate segment title from heading path or first sentence.
* No AI required.

AI segmentation behavior:

* Send version text to AI only when:

  * global AI enabled;
  * AI markup enabled;
  * policy allows this visibility/content;
  * selected provider/profile exists;
  * user explicitly starts the job.
* AI returns proposed segments as JSON.
* Proposed segments must be reviewed and approved.
* AI proposals must not overwrite manual segments automatically.
* AI segmentation must support no-cloud policy for restricted content.

Backend services:

* `KnowledgeSegmentationService`
* `KnowledgeManualSegmentService`
* `KnowledgeAutoSegmentationService`
* `KnowledgeAiSegmentationService`
* Segment-to-chunk sync service.
* Stale segment detection service.

APIs:

* `GET /api/web/knowledge/items/{item_id}/segments`
* `POST /api/web/knowledge/items/{item_id}/segments`
* `PATCH /api/web/knowledge/segments/{segment_id}`
* `DELETE /api/web/knowledge/segments/{segment_id}`
* `POST /api/web/knowledge/items/{item_id}/segments/auto`
* `POST /api/web/knowledge/items/{item_id}/segments/ai-propose`
* `POST /api/web/knowledge/segments/{segment_id}/approve`
* `POST /api/web/knowledge/segments/{segment_id}/reject`
* `GET /api/web/knowledge/segmentation-profiles`
* `POST /api/web/knowledge/segmentation-profiles`

UI:

* Add segmentation panel to `/app/admin/knowledge/studio`.
* Editor must support text selection and “Create segment from selection”.
* Segment panel:

  * list of segments;
  * source: manual/auto/AI;
  * status;
  * title;
  * keywords;
  * boost;
  * embedding enabled;
  * stale warning;
  * preview exact text.
* Actions:

  * create manual segment;
  * run auto segmentation;
  * run AI segmentation proposal;
  * approve/reject AI segments;
  * reindex selected segment;
  * compare segments with current article text.

Search integration:

* Search must prefer manual active segments when `manual_segment_boost_enabled=true`.
* Manual segment title and keywords must contribute to keyword/full-text score.
* Segment title/summary/keywords must be included in the embedding input text when embeddings are enabled.
* Use a clear embedding text format:

```text
Title: <segment title>
Keywords: <keywords>
Article: <article title>
Section: <heading path>
Text:
<segment text>
```

This should improve retrieval quality without polluting the article body.

Observer v2:

* Emit:

  * `knowledge.segmentation.auto_completed`
  * `knowledge.segmentation.ai_proposed`
  * `knowledge.segmentation.ai_blocked`
  * `knowledge.segmentation.failed`
  * `knowledge.segment.stale_detected`
  * `knowledge.segment.approved`
* Include safe counts, no raw article body.

TDD checkpoints:

* RED tests for manual segment CRUD.
* RED tests for offset/content hash/stale detection.
* RED tests for auto segmentation by headings/paragraphs/length.
* RED tests for AI segmentation policy disabled.
* RED tests for AI segmentation mocked JSON response.
* RED tests that AI proposals are not active until approved.
* RED tests that manual segment title/keywords affect search score in AI-off mode.
* RED tests that requester cannot create/admin segments.
* RED webapp tests for selection-to-segment UI, auto segmentation, AI proposal disabled state and stale warnings.

Verification:

* `python -m pytest server/tests/test_knowledge_segments.py server/tests/test_knowledge_segmentation_auto.py server/tests/test_knowledge_segmentation_ai.py server/tests/test_knowledge_search_segments.py -v --tb=short`
* `pnpm --dir webapp test -- src/features/knowledge/article-segmentation-panel.test.tsx src/features/knowledge/knowledge-studio-page.test.tsx`
* `pnpm --dir webapp build`
* `python -m compileall -q server shared scripts`
* `git diff --check`

Live checks:

* Create article draft.
* Create version with several sections.
* Manually select text and create segment with title/keywords.
* Run search with AI disabled.
* Confirm segment title/keywords improve result visibility.
* Run auto segmentation.
* Enable AI markup only after OpenRouter key is configured.
* Run AI segmentation proposal on requester-safe test article.
* Approve one AI segment and reject another.
* Confirm observer events.
* Capture screenshots:

  * manual text selection;
  * segment list;
  * search result showing segment snippet;
  * auto segmentation result;
  * AI proposal result;
  * observer event.

Exit criteria:

* Manual segmentation is usable and improves non-AI retrieval.
* Auto segmentation works without AI.
* AI segmentation is optional, policy-gated and review-only.

---

## Phase 4 — Embeddings and vector indexing with AI-off controls

Goal:

* Add embeddings as an optional retrieval enhancement.
* Keep baseline search working without embeddings.
* Support OpenRouter embeddings first.
* Prepare for local embedding providers later.

Status 2026-06-12:

* Phase 4A backend/UI vertical slice is implemented:

  * migration `113` adds `knowledge_chunk_embeddings` and `knowledge_index_jobs` without requiring pgvector in local/test DB;
  * `KnowledgeEmbeddingService` builds safe embedding input from segment chunks and existing chunks, honors AI-off/vector-disabled search settings, gates cloud embeddings through `ai_policy_profiles`, and uses injected OpenRouter embedding transport for provider-backed indexing;
  * `POST /api/web/knowledge/indexing/reindex-item`, `GET /api/web/knowledge/indexing/status` and `GET|POST /api/web/knowledge/indexing/jobs` are live for admin/support indexing operations and auditor read;
  * disabled policy/vector settings create `disabled` embedding rows and `knowledge.embedding.policy_blocked` audit evidence instead of failing search;
  * missing provider/secret/transport fails jobs safely with redacted `embedding provider unavailable` state and `knowledge.embedding.provider_unavailable` audit evidence;
  * successful fake/OpenRouter-compatible embedding calls persist vectors only in DB, update chunk `embedding_ref`/`embedding_model`, return no raw vectors to web clients and emit `knowledge.embedding.index_completed`;
  * React route `/app/admin/knowledge/indexing` shows Russian-first indexing status, disabled warnings, jobs and item reindex controls.
* Phase 4B scope orchestration is implemented:

  * `POST /api/web/knowledge/indexing/reindex-segment`, `POST /api/web/knowledge/indexing/reindex-space` and `POST /api/web/knowledge/indexing/reindex-all` now execute observable index jobs for segment, space and bounded full-run scopes;
  * generic `POST /api/web/knowledge/indexing/jobs` dispatches `scope_type=item|segment|space|all` instead of item-only execution;
  * typed webapp API helpers cover item/segment/space/all reindex and generic job creation without exposing raw vectors;
  * focused verification: `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_embeddings.py -q --tb=short` passed with 5 tests and only existing aiohttp app-key warnings.
* Remaining Phase 4 work:

  * add vector similarity search service and retrieval integration; Phase 4A stores embeddings but Phase 5 still owns hybrid retrieval/rerank ranking;
  * add live OpenRouter signoff with a real operator-provided key and screenshots after deploy.

Backend schema:

Add:

* `knowledge_chunk_embeddings`

  * `embedding_id`
  * `chunk_id`
  * `segment_id`
  * `item_id`
  * `version_id`
  * `model_profile_id`
  * `embedding_model`
  * `embedding_dimensions`
  * `embedding_vector`
  * `content_hash`
  * `embedding_input_hash`
  * `visibility`
  * `status`: `pending`, `indexed`, `failed`, `stale`, `disabled`
  * `indexed_at`
  * `error_redacted`
  * `metadata_json`

* `knowledge_index_jobs`

  * `job_id`
  * `scope_type`: `item`, `version`, `space`, `all`, `segment`
  * `scope_ref`
  * `model_profile_id`
  * `status`: `queued`, `running`, `completed`, `failed`, `canceled`
  * `requested_by`
  * `started_at`
  * `completed_at`
  * `stats_json`
  * `error_redacted`
  * `metadata_json`

Storage:

* Prefer PostgreSQL pgvector if available.
* If pgvector is not available on the local dev/test DB, tests must support a deterministic fake vector store or skip vector index DDL behind capability detection.
* Do not break local test runs due to missing pgvector.

Feature flags/settings:

* Global embeddings enabled/disabled.
* Per-space embeddings enabled/disabled.
* Per-visibility embeddings enabled/disabled.
* Per-segment embedding enabled/disabled.
* Per-provider/model enabled/disabled.
* Indexing worker enabled/disabled.
* Reindex on publish enabled/disabled.
* Use vector search enabled/disabled.

Backend services:

* `KnowledgeEmbeddingService`
* `KnowledgeIndexJobService`
* `KnowledgeVectorStore`
* `KnowledgeVectorSearchService`
* `KnowledgeEmbeddingInputBuilder`
* `KnowledgeEmbeddingPolicyService`

Embedding input priority:

1. Active manual/approved segments.
2. Auto segments.
3. Existing chunks.
4. Fallback body chunks.

Embedding input must include safe metadata useful for retrieval:

* article title;
* segment title;
* segment summary;
* keywords;
* heading path;
* body text.

Do not include:

* raw requester ids;
* device ids;
* queue ids;
* trace ids;
* operation ids;
* internal evidence in requester-safe embeddings;
* any restricted content sent to cloud when policy blocks it.

APIs:

* `POST /api/web/knowledge/indexing/jobs`
* `GET /api/web/knowledge/indexing/jobs`
* `POST /api/web/knowledge/indexing/reindex-item`
* `POST /api/web/knowledge/indexing/reindex-space`
* `POST /api/web/knowledge/indexing/reindex-all`
* `POST /api/web/knowledge/indexing/reindex-segment`
* `GET /api/web/knowledge/indexing/status`

UI:

* Add `/app/admin/knowledge/indexing`.
* Show:

  * indexed chunks/segments;
  * stale embeddings;
  * failed embeddings;
  * disabled embeddings;
  * current embedding model;
  * queue state;
  * last errors;
  * reindex buttons;
  * AI disabled/vector disabled warnings.
* Add “Embedding preview”:

  * show embedding input text without raw vector;
  * show model;
  * show content hash;
  * show status.

Observer v2:

* Emit:

  * `knowledge.embedding.index_started`
  * `knowledge.embedding.index_completed`
  * `knowledge.embedding.index_failed`
  * `knowledge.embedding.policy_blocked`
  * `knowledge.embedding.stale_detected`
  * `knowledge.embedding.provider_unavailable`
* Metrics:

  * pending jobs;
  * failed jobs;
  * stale embeddings;
  * provider latency;
  * indexed segment count.

TDD checkpoints:

* RED tests for embedding input builder.
* RED tests for embeddings disabled.
* RED tests for provider missing/key missing.
* RED tests for policy blocked restricted content.
* RED tests for stale detection.
* RED tests for indexing job lifecycle.
* RED tests for vector search fallback.
* RED tests for no raw vector returned to requester.
* RED webapp tests for indexing dashboard and disabled states.

Verification:

* `python -m pytest server/tests/test_knowledge_embeddings.py server/tests/test_knowledge_index_jobs.py server/tests/test_knowledge_vector_search.py -v --tb=short`
* `pnpm --dir webapp test -- src/features/knowledge/indexing-page.test.tsx`
* `pnpm --dir webapp build`
* `python -m compileall -q server shared scripts`
* `git diff --check`

Live checks:

* With AI disabled:

  * publish article;
  * confirm no embedding job runs;
  * search still works.
* With OpenRouter configured and embeddings enabled:

  * publish requester-safe test article;
  * run reindex item;
  * confirm indexed status;
  * run vector search preview;
  * confirm observer events.
* With invalid/missing key:

  * job fails safely;
  * error redacted;
  * search falls back to non-vector.
* Capture screenshots:

  * AI disabled indexing page;
  * reindex job queued/running/completed;
  * failed provider event;
  * vector search preview.

Exit criteria:

* Embeddings are optional.
* Indexing is observable.
* Search falls back safely.
* OpenRouter embeddings can be tested when user provides API key.

---

## Phase 5 — Hybrid retrieval, rerank and configurable search explainability

Goal:

* Build product-grade retrieval that can combine keyword/full-text, vector, bindings, manual segments, graph and optional rerank.
* Make ranking explainable and configurable.

Backend:

Implement `KnowledgeRetrievalService`:

Pipeline:

1. Normalize query.
2. Apply actor role and ACL.
3. Apply search settings.
4. Run keyword/full-text retrieval if enabled.
5. Run vector retrieval if enabled and available.
6. Apply binding/service/offering boosts.
7. Apply manual segment boosts.
8. Apply graph boosts if enabled.
9. Apply quality/freshness/helpfulness boosts.
10. Merge candidates.
11. Optional AI query rewrite.
12. Optional OpenRouter rerank.
13. Return explainable score parts.
14. Record search event and observer event.

Rerank:

* Use OpenRouter rerank only when:

  * AI enabled;
  * rerank enabled;
  * provider/model configured;
  * policy allows;
  * candidate count > threshold.
* If rerank fails, return pre-rerank hybrid results and emit fallback observer event.

APIs:

* `POST /api/knowledge/search`
* `POST /api/web/knowledge/search`
* `POST /api/web/knowledge/search/preview`
* `POST /api/web/knowledge/retrieve`

Response must include:

* item;
* version;
* chunk/segment;
* snippet;
* score;
* score_parts;
* source mode;
* fallback mode;
* citations;
* safe debug/explain for admin/support only.

UI:

* Update `/app/kb/search`.
* Add admin search preview in `/app/admin/knowledge/search-settings`.
* Show:

  * result title;
  * snippet;
  * segment title;
  * badges;
  * why matched;
  * score breakdown for admin/support;
  * fallback indicator.

Observer v2:

* Emit:

  * `knowledge.retrieval.executed`
  * `knowledge.retrieval.rerank_used`
  * `knowledge.retrieval.rerank_failed_fallback`
  * `knowledge.retrieval.vector_failed_fallback`
  * `knowledge.retrieval.zero_results`
* Include safe metadata only.

TDD checkpoints:

* RED tests for hybrid merge.
* RED tests for manual segment boost.
* RED tests for binding boost.
* RED tests for vector disabled fallback.
* RED tests for rerank disabled.
* RED tests for rerank mocked success.
* RED tests for rerank failure fallback.
* RED tests for ACL-first retrieval.
* RED tests for score explanation.

Verification:

* `python -m pytest server/tests/test_knowledge_hybrid_retrieval.py server/tests/test_knowledge_rerank.py server/tests/test_knowledge_search_acl.py -v --tb=short`
* `pnpm --dir webapp test -- src/pages/kb/search-page.test.tsx src/features/knowledge/search-preview.test.tsx`
* `pnpm --dir webapp build`
* `python -m compileall -q server shared scripts`
* `git diff --check`

Live checks:

* Search in modes:

  * keyword only;
  * hybrid no AI;
  * vector enabled;
  * rerank enabled;
  * rerank provider failure fallback.
* Confirm:

  * same article can be found without AI;
  * manual segment title boosts results;
  * vector mode improves semantic query;
  * rerank changes ordering only when enabled;
  * observer records each mode.
* Capture screenshots:

  * each search mode;
  * score breakdown;
  * fallback banner;
  * observer events.

Exit criteria:

* Search is product-grade and configurable.
* AI improves search but is not required.
* Ranking is explainable.

---

## Phase 6 — RAG Ask with citations and AI-off fallback

Goal:

* Add AI answer generation with citations.
* Keep Ask disabled unless explicitly enabled.
* Provide useful fallback when AI is disabled.

Backend:

Add `KnowledgeAskService`:

Pipeline:

1. Validate AI Ask enabled.
2. Validate actor role and surface.
3. Retrieve candidates using `KnowledgeRetrievalService`.
4. If no sufficient evidence:

   * return no-answer response.
5. Build grounded prompt with citations.
6. Call configured answer model.
7. Validate answer:

   * cites only provided sources;
   * no restricted content;
   * no raw internal metadata;
   * no uncited critical claims.
8. Return answer, citations, confidence and suggested actions.
9. Record feedback/audit/observer events.

AI-off fallback:

* If Ask disabled:

  * `/app/kb/ask` should show “AI answers disabled” and route user to search results.
* If provider unavailable:

  * return top search results with a clear fallback message.
* If search has no evidence:

  * say no answer available from KB, suggest creating ticket or gap finding.

APIs:

* `POST /api/knowledge/ask`
* `POST /api/web/knowledge/ask`
* `POST /api/web/knowledge/ask/preview`

Response:

* `answer`
* `answer_status`: `answered`, `not_enough_evidence`, `ai_disabled`, `provider_unavailable`, `policy_blocked`
* `citations`
* `retrieval_results`
* `confidence`
* `suggested_actions`
* `observer_event_id`
* `audit_id`

UI:

* `/app/kb/ask`

  * question box;
  * answer panel;
  * citations panel;
  * fallback search results;
  * helpful/not helpful;
  * create ticket;
  * suggest correction.
* Admin/support debug view:

  * retrieval mode;
  * chunks used;
  * score breakdown;
  * policy decisions.

Observer v2:

* Emit:

  * `knowledge.rag.answer_generated`
  * `knowledge.rag.not_enough_evidence`
  * `knowledge.rag.ai_disabled`
  * `knowledge.rag.provider_unavailable`
  * `knowledge.rag.policy_blocked`
  * `knowledge.rag.citation_validation_failed`
* Metrics:

  * answer count;
  * no-answer count;
  * fallback count;
  * latency;
  * failed provider count.

TDD checkpoints:

* RED tests for AI disabled response.
* RED tests for provider unavailable fallback.
* RED tests for grounded answer with mocked model.
* RED tests for citations only from retrieved chunks.
* RED tests for no-answer when retrieval evidence insufficient.
* RED tests for requester ACL.
* RED tests for support/internal visibility.
* RED webapp tests for Ask UI disabled/enabled/fallback states.

Verification:

* `python -m pytest server/tests/test_knowledge_ask_service.py server/tests/test_knowledge_rag_acl.py server/tests/test_knowledge_rag_citations.py -v --tb=short`
* `pnpm --dir webapp test -- src/pages/kb/ask-page.test.tsx`
* `pnpm --dir webapp build`
* `python -m compileall -q server shared scripts`
* `git diff --check`

Live checks:

* AI disabled:

  * Ask page shows disabled state and search fallback.
* AI enabled with OpenRouter key:

  * Ask question about seeded requester-safe article.
  * Answer includes citations.
  * Open citation article.
  * Mark helpful.
* Restricted leakage test:

  * requester asks about support_internal runbook.
  * requester does not receive restricted content.
  * support user can retrieve support content if permitted.
* Provider failure:

  * disable/invalid key;
  * Ask returns fallback search results.
* Capture screenshots:

  * AI disabled fallback;
  * answer with citations;
  * citation opened;
  * requester restricted content blocked;
  * observer events.

Exit criteria:

* Ask works with citations when enabled.
* Ask degrades to search when disabled/unavailable.
* No ACL leakage.

---

## Phase 7 — Knowledge Portal product UI

Goal:

* Build a standalone organization knowledge base portal for employees, independent of ticket creation.

Routes:

* `/app/kb`
* `/app/kb/search`
* `/app/kb/ask`
* `/app/kb/articles/:slug`
* `/app/kb/spaces/:spaceCode`
* `/app/kb/tags/:tag`

Features:

* Global search.
* AI Ask if enabled.
* Spaces/categories.
* Popular articles.
* Recently updated.
* Recommended for selected service/department if context exists.
* Article reader:

  * title;
  * summary;
  * body;
  * table of contents;
  * segment/citation anchors;
  * related articles;
  * graph neighborhood summary;
  * tags;
  * owner/review freshness;
  * helpful/not helpful;
  * suggest correction;
  * create ticket from article.
* Zero-result actions:

  * create ticket;
  * request article;
  * report missing knowledge.

Backend:

Add optional tables:

* `knowledge_article_views`
* `knowledge_user_bookmarks`
* `knowledge_correction_requests`
* `knowledge_article_subscriptions`

APIs:

* `GET /api/knowledge/portal/home`
* `GET /api/knowledge/articles/{slug}`
* `POST /api/knowledge/articles/{slug}/feedback`
* `POST /api/knowledge/articles/{slug}/correction-request`
* `POST /api/knowledge/articles/{slug}/bookmark`
* `DELETE /api/knowledge/articles/{slug}/bookmark`

TDD checkpoints:

* RED API tests for article reader ACL.
* RED tests for portal home.
* RED tests for feedback/correction requests.
* RED webapp tests for portal, search, article reader and AI disabled state.

Verification:

* Focused server tests.
* Focused webapp tests.
* `pnpm --dir webapp build`
* `python -m compileall -q server shared scripts`
* `git diff --check`

Live checks:

* Open `/app/kb`.
* Search and open article.
* Use feedback.
* Use correction request.
* Use create ticket from article.
* Confirm observer/search/feedback events.
* Capture screenshots:

  * portal home;
  * search results;
  * article page;
  * correction request;
  * ticket CTA.

Exit criteria:

* KB is useful as a standalone product.
* User does not need to start with a ticket.

---

## Phase 8 — Authoring Studio: product article editor

Goal:

* Replace textarea-centric editing with a product authoring experience.

Route:

* `/app/admin/knowledge/studio`

Features:

* Spaces/collections/draft browser.
* Article metadata panel:

  * space;
  * type;
  * visibility;
  * owner;
  * reviewer;
  * tags;
  * service/offering bindings;
  * graph links;
  * review due.
* Editor:

  * markdown editing;
  * preview;
  * template insertion;
  * structured sections;
  * callouts;
  * tables;
  * code blocks;
  * checklists;
  * attachment placeholders if attachment support is implemented.
* Version tools:

  * create version;
  * compare draft vs published;
  * diff;
  * publish checklist;
  * rollback/archive/supersede flow.
* Review:

  * submit for review;
  * approve;
  * request changes;
  * comments;
  * complete review task.
* Segment markup:

  * manual selection;
  * auto segmentation;
  * AI proposal;
  * segment status/stale warnings.
* AI tools:

  * rewrite;
  * summarize;
  * create requester-safe version;
  * generate FAQ;
  * generate tags;
  * generate graph proposals.
* AI tools must be hidden/disabled when AI disabled.

Backend additions:

* `knowledge_review_comments` already exists; extend if needed.
* Add:

  * `knowledge_article_editor_events`
  * optional `knowledge_article_attachments`
  * optional `knowledge_version_diff_cache`

TDD checkpoints:

* RED tests for article editor load/save.
* RED tests for version diff.
* RED tests for publish checklist blockers.
* RED tests for AI disabled UI.
* RED tests for requester-safe preview.
* RED tests for segment panel integration.
* RED webapp tests for editing workflow.

Verification:

* Focused backend tests.
* Focused webapp tests.
* Full relevant knowledge tests.
* Build/compile/diff checks.

Live checks:

* Create draft.
* Insert template.
* Create manual segment.
* Create version.
* Preview as requester/support.
* Submit review.
* Publish.
* Open article in `/app/kb`.
* Capture screenshots for each step.

Exit criteria:

* Articles can be authored and governed without raw admin-table workflow.
* Editor supports segmentation and AI tools safely.

---

## Phase 9 — Visual Knowledge Graph Studio

Goal:

* Add a visual graph editor for knowledge nodes/edges and article relationships.

Route:

* `/app/admin/knowledge/graph`

Frontend:

* Use a dedicated graph canvas component.
* A library such as React Flow is acceptable if already compatible with the project stack.
* If adding a new dependency, document why and keep it isolated.

Graph UI:

* Left panel:

  * node search;
  * filters;
  * palette;
  * saved views.
* Canvas:

  * nodes;
  * edges;
  * drag/drop;
  * connect handles;
  * zoom/pan;
  * layout actions.
* Right panel:

  * selected node/edge properties;
  * relation type;
  * visibility;
  * linked item;
  * confidence;
  * status;
  * source;
  * AI suggested links.
* Bottom/side panel:

  * warnings;
  * orphan nodes;
  * contradictions;
  * duplicate/superseded chains.

Backend schema additions:

* `knowledge_graph_layouts`

  * `layout_id`
  * `scope_type`
  * `scope_ref`
  * `layout_json`
  * `created_by`
  * `updated_by`
  * timestamps

* `knowledge_graph_proposals`

  * `proposal_id`
  * `proposal_type`: `node`, `edge`, `merge`, `contradiction`, `duplicate`, `supersede`
  * `source_kind`: `manual`, `ai`, `import`, `article_extraction`
  * `status`: `proposed`, `approved`, `rejected`
  * `payload_json`
  * `reason`
  * `created_by`
  * timestamps

APIs:

* `GET /api/web/knowledge/graph/search`
* `GET /api/web/knowledge/graph/nodes`
* `POST /api/web/knowledge/graph/nodes`
* `PATCH /api/web/knowledge/graph/nodes/{node_id}`
* `DELETE /api/web/knowledge/graph/nodes/{node_id}`
* `GET /api/web/knowledge/graph/edges`
* `POST /api/web/knowledge/graph/edges`
* `PATCH /api/web/knowledge/graph/edges/{edge_id}`
* `DELETE /api/web/knowledge/graph/edges/{edge_id}`
* `GET /api/web/knowledge/graph/neighborhood`
* `GET /api/web/knowledge/graph/layouts/{scope}`
* `POST /api/web/knowledge/graph/layouts/{scope}`
* `POST /api/web/knowledge/graph/ai/suggest-links`
* `POST /api/web/knowledge/graph/proposals/{proposal_id}/approve`
* `POST /api/web/knowledge/graph/proposals/{proposal_id}/reject`

AI graph suggestions:

* Disabled unless AI enabled.
* Suggest:

  * related articles;
  * glossary terms;
  * service/offering links;
  * known error/workaround links;
  * duplicate articles;
  * contradictions.
* Must create proposals only.
* Admin/support must approve before graph mutation.

Observer v2:

* Emit:

  * `knowledge.graph.node_created`
  * `knowledge.graph.edge_created`
  * `knowledge.graph.proposal_created`
  * `knowledge.graph.proposal_approved`
  * `knowledge.graph.proposal_rejected`
  * `knowledge.graph.ai_suggest_failed`
* Include counts and ids, no raw sensitive body.

TDD checkpoints:

* RED tests for node/edge CRUD.
* RED tests for graph layout save/load.
* RED tests for ACL-filtered graph search.
* RED tests for AI proposal disabled/policy blocked.
* RED webapp tests for graph canvas, create node, create edge, edit properties, save layout.
* RED browser-oriented test if existing browser harness supports it.

Verification:

* `python -m pytest server/tests/test_knowledge_graph_editor.py server/tests/test_knowledge_graph_layouts.py server/tests/test_knowledge_graph_proposals.py -v --tb=short`
* `pnpm --dir webapp test -- src/features/knowledge/graph-studio.test.tsx`
* `pnpm --dir webapp build`
* `python -m compileall -q server shared scripts`
* `git diff --check`

Live checks:

* Open graph studio.
* Create concept node.
* Link it to article node.
* Create relation edge.
* Save layout.
* Reload page and confirm layout persists.
* Run AI link suggestion with OpenRouter if enabled.
* Approve one proposal.
* Confirm observer events.
* Capture screenshots:

  * graph canvas;
  * node editor;
  * edge editor;
  * saved layout;
  * AI proposal panel;
  * observer event.

Exit criteria:

* Knowledge graph is visually editable.
* Graph changes are governed and observable.
* AI proposals are optional and review-only.

---

## Phase 10 — Import/Ingestion wizard with AI-off and AI-assisted enrichment

Goal:

* Implement product-grade document import, not just text ingestion.

Route:

* `/app/admin/knowledge/import`

Supported sources for this phase:

* text;
* markdown;
* HTML if feasible;
* DOCX if project dependencies allow;
* PDF if project dependencies allow;
* external URL only if safe and explicitly enabled;
* Git repo docs only as later subphase if needed.

Wizard steps:

1. Source selection.
2. Parse preview.
3. Structure detection.
4. Space/type/visibility selection.
5. Segmentation profile selection.
6. Optional AI enrichment:

   * summary;
   * tags;
   * glossary terms;
   * graph proposals;
   * duplicate detection.
7. Create drafts.
8. Queue indexing if enabled.

Backend:

* Extend `KnowledgeIngestionService`.
* Add parser abstraction:

  * `TextParser`
  * `MarkdownParser`
  * `HtmlParser`
  * `DocxParser`
  * `PdfParser`
* Add import preview endpoint.
* Add safe error redaction.
* Add ingestion observer events.

APIs:

* `POST /api/web/knowledge/import/preview`
* `POST /api/web/knowledge/import/create-drafts`
* `GET /api/web/knowledge/import/jobs`
* `GET /api/web/knowledge/import/jobs/{job_id}`

Observer v2:

* Emit:

  * `knowledge.import.preview_created`
  * `knowledge.import.drafts_created`
  * `knowledge.import.failed`
  * `knowledge.import.ai_enrichment_blocked`
  * `knowledge.import.ai_enrichment_failed`

TDD checkpoints:

* RED tests for text/markdown import preview.
* RED tests for draft creation.
* RED tests for parser error redaction.
* RED tests for AI enrichment disabled.
* RED tests for AI enrichment mocked proposals.
* RED webapp tests for import wizard.

Verification:

* Focused import tests.
* Webapp import wizard tests.
* Build/compile/diff checks.

Live checks:

* Import markdown text without AI.
* Create draft.
* Open in studio.
* Segment automatically.
* Publish after review.
* With OpenRouter enabled, run AI enrichment on safe test text.
* Confirm proposals require review.
* Capture screenshots:

  * import source;
  * preview;
  * draft created;
  * AI enrichment proposal;
  * observer event.

Exit criteria:

* KB can be populated from documents.
* Import works without AI.
* AI enrichment is optional and governed.

---

## Phase 11 — Support Knowledge Workspace and deeper helpdesk integration

Goal:

* Make `/app/knowledge` a support workspace, not a clone of admin panel.

Route:

* `/app/knowledge`
* `/app/knowledge/articles/:id`

Features:

* Fast support search.
* Filters:

  * requester-safe;
  * support internal;
  * known errors;
  * workarounds;
  * runbooks;
  * service/offering;
  * article status/freshness.
* Open article/runbook.
* Link article to ticket.
* Copy requester-safe answer.
* Generate requester-safe reply if AI enabled.
* Create KB draft from ticket resolution/passport.
* See requester knowledge attempts.
* Mark support_used.
* Report weak article.
* Create known error/workaround draft.

Ticket integration:

* Improve ticket Knowledge tab:

  * requester attempts;
  * suggested requester-safe articles;
  * support runbooks;
  * known errors;
  * workarounds;
  * linked articles;
  * draft from resolution;
  * AI safe reply if enabled.
* Preserve existing ticket KB endpoints.

Observer v2:

* Emit:

  * `knowledge.support.article_used`
  * `knowledge.support.ticket_linked`
  * `knowledge.support.reply_draft_created`
  * `knowledge.support.passport_draft_created`
  * `knowledge.support.weak_article_reported`

TDD checkpoints:

* RED tests for support search visibility.
* RED tests for ticket link/unlink compatibility.
* RED tests for requester attempts display.
* RED tests for support_used feedback.
* RED webapp tests for support workspace and ticket knowledge tab.

Verification:

* Focused server tests.
* Focused webapp tests.
* Existing ticket/knowledge tests.
* Build/compile/diff checks.

Live checks:

* Create ticket.
* View knowledge suggestions.
* Link article.
* Mark support_used.
* Create draft from resolution.
* Open draft in studio.
* Capture screenshots:

  * support search;
  * ticket knowledge tab;
  * linked article;
  * draft from resolution;
  * observer event.

Exit criteria:

* Helpdesk integration remains strong.
* Standalone KB and support KB serve different workflows.

---

## Phase 12 — Knowledge Ops dashboard with Observer v2

Goal:

* Turn `/app/admin/knowledge` into a Knowledge Operations Center.

Dashboard sections:

* Coverage:

  * spaces;
  * published articles;
  * requester-safe coverage;
  * support runbook coverage;
  * services/offerings without KB.
* Quality:

  * average score;
  * low-quality count;
  * stale review count;
  * missing owner/reviewer;
  * unsafe requester-safe blockers.
* Search:

  * zero-result searches;
  * top queries;
  * fallback count;
  * AI disabled count;
  * vector/rerank usage.
* RAG:

  * answer count;
  * no-answer count;
  * provider failures;
  * citation validation failures.
* Indexing:

  * queued;
  * failed;
  * stale embeddings;
  * disabled.
* AI:

  * provider health;
  * model profile status;
  * policy blocks;
  * cost/usage if available.
* Graph:

  * orphan nodes;
  * pending proposals;
  * contradiction/duplicate findings.
* Review:

  * assigned/open/overdue tasks.

Observer v2 integration:

* Add knowledge observer category or source.
* All critical operations emit observer events.
* Admin dashboard surfaces observer-backed degradation states:

  * AI provider down;
  * indexing failing;
  * high zero-result searches;
  * stale embeddings;
  * RAG citation failures;
  * policy blocks;
  * ingestion failures.

TDD checkpoints:

* RED tests for ops summary aggregation.
* RED tests for observer event mapping.
* RED tests for dashboard API.
* RED webapp tests for dashboard cards and degraded state.

Verification:

* Focused server tests.
* Focused webapp tests.
* Browser smoke.

Live checks:

* Trigger:

  * search zero-result;
  * failed AI health;
  * failed indexing job;
  * successful segmentation;
  * successful ask.
* Confirm dashboard and observer show states.
* Capture screenshots.

Exit criteria:

* Knowledge health is observable.
* Observer v2 is a first-class integration, not an afterthought.

---

## Phase 13 — RAG/search evaluation and safety regression suite

Goal:

* Add automated evidence that search/RAG is useful and safe.

Backend test fixtures:

Create a controlled knowledge dataset:

* requester-safe article;
* support_internal runbook;
* admin_internal article;
* security_restricted article;
* known error;
* workaround;
* manual segments;
* auto segments;
* AI-approved segment;
* graph links;
* service/offering bindings.

Evaluation tests:

* Keyword search finds requester article.
* Manual segment title/keywords improve search.
* Full-text search finds body-only content.
* Vector search finds semantic query when enabled.
* Vector disabled fallback still finds keyword result.
* Rerank changes ordering only when enabled.
* Ask returns citations only from allowed chunks.
* Ask returns no-answer when evidence insufficient.
* Requester cannot retrieve support/admin/security chunks.
* Support cannot retrieve admin/security chunks.
* Stale embeddings are not preferred.
* Archived items are not returned.
* Old versions are not used unless explicitly requested.

Metrics to record:

* `top_k_recall`
* `citation_precision`
* `no_answer_correctness`
* `acl_leakage_count`
* `fallback_count`
* `latency_ms`
* `provider_failure_count`

TDD checkpoints:

* RED eval harness tests.
* RED ACL leakage tests.
* RED no-answer tests.
* RED stale embedding tests.
* RED observer event tests.

Verification:

* `python -m pytest server/tests/test_knowledge_rag_eval.py server/tests/test_knowledge_rag_acl.py server/tests/test_knowledge_search_eval.py -v --tb=short`
* `pnpm --dir webapp test`
* `pnpm --dir webapp build`
* `python -m compileall -q server shared scripts`
* `python scripts/docs_inventory.py --check-links`
* `python scripts/verify_workspace.py`
* `git diff --check`
* `git diff --cached --check`

Live acceptance checks:

* End-to-end article lifecycle:

  * create article;
  * manually segment;
  * search without AI;
  * enable OpenRouter;
  * index embeddings;
  * search semantic query;
  * ask with citations;
  * feedback;
  * observer events.

* End-to-end graph:

  * create node;
  * create edge;
  * open related article;
  * save layout;
  * observer events.

* End-to-end helpdesk:

  * requester starts ticket;
  * suggestions shown;
  * user views article;
  * ticket creation carries knowledge attempt;
  * support sees attempts;
  * support links runbook;
  * create draft from resolution.

* Failure mode:

  * disable AI;
  * search still works;
  * Ask shows fallback;
  * indexing disabled state visible.

* Provider failure:

  * invalid OpenRouter key or provider disabled;
  * health check fails;
  * observer event emitted;
  * search falls back safely;
  * no key leaked.

Required browser evidence:

* `/app/admin/knowledge/ai` provider setup and masked key state.
* `/app/admin/knowledge/search-settings` AI disabled search preview.
* `/app/admin/knowledge/studio` manual segment creation.
* `/app/admin/knowledge/indexing` reindex job.
* `/app/kb/search` keyword and hybrid results.
* `/app/kb/ask` answer with citations or disabled fallback.
* `/app/admin/knowledge/graph` visual graph editing.
* `/app/admin/knowledge` ops/observer-backed dashboard.
* Ticket Knowledge tab integration.

Exit criteria:

* Product KB works without AI.
* AI adds embeddings/rerank/ask/rewrite/markup when enabled.
* OpenRouter integration is testable with user-supplied key.
* Search/RAG is ACL-safe.
* Observer v2 captures health, failures and key workflow events.
* Browser evidence proves the main workflows.

---

## Documentation updates required across phases

Update:

* `server/docs/KNOWLEDGE_PLATFORM.md`
* `server/docs/KNOWLEDGE_OPERATIONS.md`
* `server/docs/KNOWLEDGE_VNEXT_ARCHITECTURE.md`
* `server/docs/DATABASE.md`
* `server/docs/CODEMAP.md`
* `docs/ARCHITECTURE_BOUNDARIES.md`
* `docs/QUICK_LOOKUP.md`
* `docs/TESTING_RULES.md` if needed.
* `webapp` route/navigation docs if present.
* Any observer documentation that lists event types/sources.

Docs must cover:

* AI provider setup.
* Where the user enters OpenRouter API key.
* AI disabled mode.
* Search settings.
* Manual/auto/AI segmentation.
* Embedding/indexing lifecycle.
* RAG Ask with citations.
* Graph editor.
* Observer v2 events.
* Safety/ACL rules.
* Live testing procedure.

---

## Final verification target before merge

Run as many as practical locally, and document any environment limitation explicitly:

* Focused backend tests for:

  * AI settings;
  * OpenRouter mocked client;
  * search settings;
  * segmentation;
  * embeddings/indexing;
  * hybrid retrieval;
  * RAG Ask;
  * graph editor;
  * import;
  * support integration;
  * observer events.

* Focused webapp tests for:

  * AI settings page;
  * search settings page;
  * Knowledge Portal;
  * article reader;
  * Ask page;
  * Authoring Studio;
  * segmentation panel;
  * indexing dashboard;
  * Graph Studio;
  * Support Knowledge Workspace;
  * Ops dashboard.

* General:

  * `python -m compileall -q server shared pc_agent scripts`
  * `pnpm --dir webapp test`
  * `pnpm --dir webapp build`
  * `python scripts/docs_inventory.py --check-links`
  * `python scripts/verify_workspace.py`
  * `git diff --check`
  * `git diff --cached --check`

* DB:

  * Apply Alembic migration on the real PostgreSQL stand.
  * Confirm `/api/health` after migration.
  * Confirm migration rollback plan is documented if rollback is supported by project convention.

* Browser/live:

  * Real server/webapp smoke.
  * Screenshots for all required UI workflows.
  * Browser console check: no warnings/errors relevant to new features.
  * No secret leakage in logs, screenshots, network response bodies or console.

Known risks:

* pgvector may not be available in all local test environments. Add capability detection and fallback tests.
* OpenRouter key is external and user-supplied; tests must mock network by default.
* AI outputs are nondeterministic; product tests must validate contract shape and safety, not exact prose.
* Manual segment offsets can become stale after edits; implement content hash and stale detection.
* Graph UI dependency can increase bundle size; isolate it and justify dependency.
* Observer v2 integration must not create noisy events for every normal keystroke; emit workflow-level events only.
* ACL leakage is the highest-risk area. Add regression tests before enabling RAG answers.
