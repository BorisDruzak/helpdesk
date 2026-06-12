# Knowledge vNext Architecture

Knowledge vNext расширяет существующую Knowledge Platform, а не заменяет её. Текущие spaces, items, versions, chunks, bindings, graph, feedback, metrics, review tasks и helpdesk deflection contracts остаются фундаментом.

## Product Surfaces

- `/app/kb` — requester-safe портал знаний организации.
- `/app/kb/search` — отдельный поиск по базе знаний.
- `/app/kb/ask` — optional RAG Ask с citations и безопасным fallback, когда AI отключён.
- `/app/kb/articles/:slug` — requester-safe просмотр статьи.
- `/app/knowledge` — support knowledge workspace.
- `/app/knowledge/articles/:id` — support view для article/runbook/known error.
- `/app/admin/knowledge` — Knowledge Ops dashboard.
- `/app/admin/knowledge/studio` — article authoring studio.
- `/app/admin/knowledge/graph` — visual graph editor.
- `/app/admin/knowledge/ai` — управление AI providers, model profiles, policies и health.
- `/app/admin/knowledge/search-settings` — настройки search/retrieval.
- `/app/admin/knowledge/indexing` — управление chunks, embeddings и indexing jobs.
- `/app/admin/knowledge/import` — мастер ingestion.
- `/app/admin/knowledge/review` — очередь curation/review.

## Boundaries

- Knowledge Core владеет spaces, items, versions, chunks, segment markup, ACL, taxonomy, bindings и graph.
- Knowledge Search владеет keyword/full-text search, optional vector search, hybrid retrieval, rerank и explainable scoring.
- Knowledge AI владеет provider registry, model profiles, policies, audit, OpenRouter integration и optional tasks: embeddings, rewrite, classify, markup, rerank, answer.
- Knowledge Portal владеет requester-facing reading, search, Ask и feedback.
- Knowledge Authoring владеет article editing, manual markup, templates, version diff, comments и review.
- Knowledge Graph владеет graph node/edge editing, saved layout и AI proposals.
- Knowledge Ops владеет quality, gaps, review, rollout, indexing, provider health и Observer v2 visibility.
- Helpdesk Adapter владеет ticket suggestions, deflection, ticket links, passport-to-draft и support runbook integration.

Knowledge Core не должен зависеть от ticket-specific code. Helpdesk code может потреблять Knowledge через adapter services.

## AI And Search Safety

AI является optional. Baseline article viewing, authoring, manual markup, graph editing, keyword/full-text search и helpdesk linking должны работать, когда все AI features отключены.

Retrieval и RAG работают по принципу ACL-first. Система должна фильтровать по actor role, visibility, space policy и item/version status до vectorization, rerank или answer generation. Контент `security_restricted` нельзя отправлять cloud provider без явной admin policy.

OpenRouter — первый external provider. API keys должны храниться только через approved secret/config path, не должны попадать в git, logs, API payloads или screenshots и должны отображаться только в masked state.

Initial Phase 1 foundation lives in `server/ai/`, `server/web_api/knowledge_ai_handlers.py` and `webapp/src/features/knowledge/ai-settings-page.tsx`: provider registry rows store only secret references, model profiles are task-scoped, policy rows keep AI opt-in gates disabled by default, and `ai_request_audit` is redacted by default. The OpenRouter client is transport-injectable for mocked tests and must not log raw keys, prompts or restricted content. Admin API routes under `/api/web/knowledge/ai/*` expose provider/profile/policy setup, model profile updates, provider health checks and redacted audit listing; health checks write redacted request audit rows and Observer-visible runtime audit events. React `/app/admin/knowledge/ai` shows Russian provider/model/policy/audit controls and masked secret state only.

Initial Phase 2 search foundation lives in `server/knowledge/search_settings_service.py`, `server/knowledge/search_service.py`, `server/web_api/knowledge_handlers.py` and `webapp/src/features/knowledge/search-settings-page.tsx`. Migration `111` adds global `knowledge_search_settings` with AI/vector/rerank/rewrite/RAG switches disabled by default. `GET|POST /api/web/knowledge/search-settings` is admin-configurable with Russian `display_message` responses, `POST /api/web/knowledge/search` gives authenticated web consumers the same ACL-filtered baseline search, and public `POST /api/knowledge/search` remains backward-compatible while exposing `search_mode`, `effective_mode` and `ai_used`. React `/app/admin/knowledge/search-settings` shows Russian controls for mode, AI-off toggles, weights and limits. The first implementation deliberately runs without AI providers, embeddings or vector indexes.

Initial Phase 3 segmentation foundation lives in `server/knowledge/segmentation_service.py`, `server/web_api/knowledge_handlers.py`, `webapp/src/features/knowledge/article-segmentation-panel.tsx` and `/app/admin/knowledge/studio`. Migration `112` adds article segments, segmentation profiles and segmentation jobs. Manual/auto segments improve AI-off search, revalidation remaps segment offsets across immutable versions, AI proposals remain draft until approve/reject, and segment index sync writes active retrieval segments into `knowledge_chunks`.

Initial Phase 4 indexing foundation lives in `server/knowledge/embedding_service.py`, `server/knowledge/vector_search_service.py`, migration `113`, `server/web_api/knowledge_handlers.py` and `webapp/src/features/knowledge/indexing-page.tsx`. `knowledge_chunk_embeddings` and `knowledge_index_jobs` store optional embedding state and observable jobs without requiring pgvector in local/test DB. `/app/admin/knowledge/indexing` exposes Russian status, disabled/failure counters, jobs and item reindex. Web APIs never return raw vectors; vector-disabled settings, AI policy blocks and provider failures fall back safely and emit Observer-visible audit rows. Indexing orchestration now supports item, segment, space and bounded full-run scopes through dedicated reindex endpoints plus generic `POST /api/web/knowledge/indexing/jobs`. Vector retrieval has an ACL-first JSONB cosine fallback for `vector_enabled` searches with a supplied numeric `query_vector`; pgvector acceleration and rerank remain later hybrid retrieval work.

Initial Phase 5 retrieval foundation lives in `server/knowledge/retrieval_service.py`. It keeps existing public search backward-compatible while adding admin/support `POST /api/web/knowledge/retrieve` and `POST /api/web/knowledge/search/preview` for explainable hybrid candidates. The service merges keyword, manual segment, binding and optional JSONB-vector score parts after ACL filtering, returns citations and safe score diagnostics, records analytics, and emits Observer-visible retrieval audit events. Optional OpenRouter-compatible rerank is injected/mocked in tests, requires explicit settings/profile/provider/policy/secret availability, and falls back to pre-rerank ordering on failure.

## Русская Локализация

Knowledge vNext является Russian-first для видимого продуктового поведения. Portal, support, admin, authoring, graph, AI settings, search/indexing/import/review pages, dialogs, empty states, validation messages, toasts и live-check notes должны использовать русский пользовательский текст.

Стабильные технические контракты остаются на английском: route paths, API field names, enum values, migration identifiers, observer event codes, metric names, model/profile task codes и log categories. Backend responses должны сохранять machine-readable error codes и давать безопасные русские display messages для web и GUI consumers.

UI tests для новых Knowledge vNext pages должны проверять репрезентативные русские labels и отсутствие mojibake в visible text.

## Observer v2

Knowledge vNext отправляет Observer v2 signals для provider health, policy blocks, AI request failures, search execution/fallback/zero-results, indexing lifecycle, graph proposals, import failures и RAG citation/safety outcomes. Observer events не должны включать raw prompts, secrets, tokens или restricted content.
