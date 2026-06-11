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

Initial Phase 1 foundation lives in `server/ai/` and `server/web_api/knowledge_ai_handlers.py`: provider registry rows store only secret references, model profiles are task-scoped, policy rows keep AI opt-in gates disabled by default, and `ai_request_audit` is redacted by default. The OpenRouter client is transport-injectable for mocked tests and must not log raw keys, prompts or restricted content. Admin API routes under `/api/web/knowledge/ai/*` expose provider/profile/policy setup and provider health checks; health checks write redacted request audit rows and Observer-visible runtime audit events.

## Русская Локализация

Knowledge vNext является Russian-first для видимого продуктового поведения. Portal, support, admin, authoring, graph, AI settings, search/indexing/import/review pages, dialogs, empty states, validation messages, toasts и live-check notes должны использовать русский пользовательский текст.

Стабильные технические контракты остаются на английском: route paths, API field names, enum values, migration identifiers, observer event codes, metric names, model/profile task codes и log categories. Backend responses должны сохранять machine-readable error codes и давать безопасные русские display messages для web и GUI consumers.

UI tests для новых Knowledge vNext pages должны проверять репрезентативные русские labels и отсутствие mojibake в visible text.

## Observer v2

Knowledge vNext отправляет Observer v2 signals для provider health, policy blocks, AI request failures, search execution/fallback/zero-results, indexing lifecycle, graph proposals, import failures и RAG citation/safety outcomes. Observer events не должны включать raw prompts, secrets, tokens или restricted content.
