## Active Work: Knowledge Platform vNext — Product KB, RAG, AI Settings, Manual Markup, Graph Studio and Observer v2

Status: active implementation / partial product signoff. Phases 0-14 contain implemented slices and verification evidence, but Knowledge vNext is not final-complete until the real-key OpenRouter signoff and dedicated semantic retrieval browser/live evidence are closed.

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

Current open gates before final Knowledge vNext signoff:

* Live OpenRouter answer signoff with a real operator-provided key remains pending. Mock/client/provider tests are valid regression evidence, but they are not product signoff for the external provider.
* Full Ask -> requester create-ticket -> `ticket_created_after_view` analytics is closed by the 2026-06-12 live no-device requester run recorded in Phase 6E correction below.
* Dedicated retrieval browser/live evidence after deploy must cover semantic search behavior, not only route load: requester-safe search, AI-off fallback, ACL-safe projection and diagnostics separation.
* Knowledge -> requester regressions must stay bundled with Knowledge changes: requester knowledge suggestions, Ask fallback -> requester ticket prefill, requester ticket create with `knowledge_attempts`, `ticket_created_after_view` analytics and public `/app/help` deflection.
* Evidence paths under `artifacts/` may be local/untracked operational artifacts; audit docs must say when evidence must be preserved outside git or regenerated.

2026-06-13 UI refactor note:

* `/app/admin/knowledge` переведён в Knowledge Operations Center: обзор здоровья и быстрые переходы вместо старой mega-form со всеми CRUD/rollout/content pack блоками.
* `/app/admin/knowledge/studio` получил единый TipTap/ProseMirror editor surface с визуальными состояниями ручной разметки, AI-предложений, автосегментов и изменённого текста; version/publish/review API остаются прежними.
* `/app/admin/knowledge/graph` получил React Flow canvas как основной editor surface: выбор узла, drag layout, connect edge и save layout связаны с текущими graph API.
* `/app/admin/knowledge/import`, `/search-settings`, `/ai`, `/indexing` приведены к сценарному контракту: wizard/action bar, AI-gated controls, secret refs и raw ids в Advanced, item picker для reindex.
* Проверено локально: `pnpm --dir webapp build`; `pnpm --dir webapp test -- --reporter=dot` — 91 файл, 428 тестов; `python scripts/verify_workspace.py`.
* Browser evidence собрано для всех семи admin Knowledge routes на 1366×768 и 1920×1080: `knowledge-ops-final-*`, `knowledge-studio-final-*`, `knowledge-graph-final-*`, `knowledge-import-final-*`, `knowledge-search-settings-final-*`, `knowledge-ai-final-*`, `knowledge-indexing-final-*`. Проверено: primary actions видны без прокрутки, horizontal scroll отсутствует, Studio показывает единый редактор и визуальные легенды разметки, Graph показывает React Flow editor canvas и inspector action.
* Осталось вне этого UI signoff: общий Knowledge vNext product signoff по live OpenRouter/retrieval остаётся в верхних open gates и не блокирует админский UI refactor.

2026-06-13 Knowledge Studio reference 01 follow-up:

* `/app/admin/knowledge/studio` дополнительно перестроен по приложенному reference 01: первый экран теперь `Article Explorer -> Unified Article Editor -> Inspector`, без нижней ленты независимых карточек.
* Постоянная форма `Новый черновик` убрана из левой колонки; создание открывается в drawer, а owner/reviewer/tags скрыты в `Advanced / служебные поля`.
* Основные поля, metadata model, preview, diff, history, validation, publish и segmentation перенесены внутрь шагов единого редактора; inspector держит версии, computed checklist и publish/review/rollback/archive действия без прокрутки.
* Разметка встроена в шаг `Разметка`: TipTap передаёт выделение текста в сегментацию, auto-markup и список сегментов версии находятся рядом с формой сегмента.
* Browser comment follow-up: template insertion in the TipTap toolbar is collapsed into one `Вставить шаблон` dropdown menu with selectable templates; individual `Вставить шаблон: ...` buttons are removed.
* Проверено локально: `pnpm --dir webapp exec tsc --noEmit --pretty false`; `pnpm --dir webapp exec vitest run src/pages/admin/knowledge-studio-page.test.tsx src/features/knowledge/article-segmentation-panel.test.tsx src/features/knowledge/article-metadata-panel.test.tsx --reporter=dot` — 3 файла, 8 тестов.
* Browser evidence обновлено на стенде `https://192.168.100.17:9443/app/admin/knowledge/studio`; артефакты локальные/untracked: `knowledge-studio-reference-1366x768.png`, `knowledge-studio-reference-1920x1080.png`, `knowledge-studio-reference-segments-form-1366x768.png`, `knowledge-studio-reference-new-draft-drawer-1366x768.png`, `knowledge-studio-reference-console.json`, `knowledge-studio-reference-network.json`.
* Browser checks: 1366×768 и 1920×1080 без horizontal body scroll; `Создать версию` видна без прокрутки; три зоны `Черновики и статьи`, `Единый редактор статьи`, `Инспектор и публикация` видны; старые bottom-card labels отсутствуют; drawer `Новый черновик` открывается как `role=dialog`; console warnings/errors = 0; network requests = 200.

2026-06-13 Knowledge Studio/Graph browser comments follow-up:

* `/app/admin/knowledge/studio`: удалён ложный дубль `Сохранить`, потому что он вызывал тот же `createVersion`; осталась одна primary action `Создать версию` с пояснением, что она фиксирует текущий текст и метаданные как новую версию.
* Inspector разделён по смыслу: lifecycle/publish/rollback/archive описаны как действия над статусом и выбранной версией, review comment/approve/request changes описаны как `review-action`, а не сохранение текста статьи.
* TipTap editor больше не перезаписывает документ через `textContent`; изменение идёт через TipTap `onUpdate`, поэтому заголовки, списки, bold/italic/code и highlight-разметка не должны сбрасываться в плоский текст.
* `Preview` убран из постоянной правой колонки шага `Текст`; предпросмотр открывается только через быструю вкладку `Preview`.
* Левый список статей ограничен прокручиваемой областью и выводит первые 10 результатов с подсказкой уточнить поиск/фильтр, если найдено больше.
* Admin sidebar теперь сворачивается для всего admin workspace: есть кнопка `Свернуть/Развернуть меню`, выбор пункта навигации сворачивает панель, а клик по значку в свёрнутом состоянии сначала раскрывает панель.
* `/app/admin/knowledge/graph`: React Flow canvas получил auto-fit после загрузки узлов, кнопку `Показать весь граф`, верхние действия `Авторазложить` и `Сохранить layout`; сохранение layout продолжает идти через существующий graph layout API.
* Browser-debug по graph canvas нашёл реальную причину пустого вида: React Flow создавал node, но держал его `visibility:hidden` до измерения. Узлам заданы явные `width/height/initial/measured` размеры и ограничение длинного label; полный label остаётся в inspector/sidebar.
* Проверено локально: `pnpm --dir webapp exec tsc --noEmit --pretty false`; `pnpm --dir webapp exec vitest run src/pages/admin/knowledge-studio-page.test.tsx src/features/knowledge/graph-studio.test.tsx src/components/shell/app-sidebar.test.tsx --reporter=dot` — 3 файла, 16 тестов.
* Проверено локально после graph fix: `pnpm --dir webapp build`; `python scripts/verify_workspace.py`; `git diff --check`.
* Remote/browser evidence на `https://192.168.100.17:9443`: Studio 1366×768 и 1920×1080 без horizontal scroll; `Создать версию` ровно одна, `Сохранить` отсутствует, preview скрыт до клика вкладки `Preview`, список показывает первые 10 из 45; sidebar collapse 260→64px, labels `sr-only`, клик по иконке раскрывает без navigation, второй клик по раскрытому пункту открывает `/graph` и снова сворачивает sidebar.
* Graph browser evidence: canvas содержит видимый React Flow node, toolbar `Авторазложить`, `Сохранить layout`, `Показать весь граф`; DOM node `visibility: visible`, внутри canvas top/bottom 244–412 из 609px; graph API network requests 200. Screenshots: `knowledge-studio-comments-followup-1366x768.png`, `knowledge-studio-comments-followup-1920x1080.png`, `knowledge-graph-comments-followup-visible-node-1366x768.png`, `knowledge-graph-comments-followup-visible-node-1920x1080.png`.

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
## Preserved Browser / Requester / Agent signoff

Status 2026-06-12: preserved and moved out of the rolling plan.

The completed Browser / Requester / Agent identity and consent model is now documented in `docs/completed/BROWSER_REQUESTER_AGENT_IDENTITY_MODEL.md`. That document records Stage 1, Stage 2A, Stage 2B and Stage 3 status, live evidence paths, regression commands, privacy boundaries and non-goals.

Knowledge vNext must continue treating these flows as non-regression boundaries:

* `/app/requester` and `/api/web/requester/*`;
* requester ticket create, preview, detail, message, attachment, close, feedback and reopen;
* requester no-device ticket creation;
* public ticket claim-to-account;
* requester knowledge suggestions, `knowledge_attempts`, `surface=requester_portal` and `ticket_created_after_view`;
* public `/app/help` and `/app/ticket/:ticketId` access-code flows;
* canonical `UserConsentRequest`;
* requester/agent consent APIs;
* Remote Assist browser consent and agent account-session consent boundary;
* cookie-auth same-origin protection for unsafe web-session requests;
* shared-device privacy.

Fresh regression run for the final Knowledge vNext signoff is tracked in the final verification section below.

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
* Phase 4C vector retrieval fallback is implemented:

  * `KnowledgeVectorSearchService` performs ACL-first cosine similarity over stored JSONB embeddings for environments without pgvector;
  * `KnowledgeSearchService` merges vector hits into search results only when vector search is enabled and a safe numeric `query_vector` is supplied;
  * requester-safe projection still hides diagnostic vector fields, support/admin responses may include `retrieval_source=vector` and `vector_score`, and no response includes raw `embedding_vector`;
  * focused verification: `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_vector_search.py server/tests/test_knowledge_embeddings.py server/tests/test_knowledge_segments.py server/tests/test_knowledge_search_segments.py server/tests/test_knowledge_search_settings.py server/tests/test_knowledge_search.py -q --tb=short` passed with 23 tests and only existing aiohttp app-key warnings.
* Remaining Phase 4 work:

  * pgvector-native acceleration and full hybrid/rerank ranking remain Phase 5 work; Phase 4C provides the safe JSONB fallback and retrieval contract;
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

Status 2026-06-12:

* Phase 5A backend/API retrieval slice is implemented:

  * `KnowledgeRetrievalService` normalizes search settings, applies ACL before scoring, merges keyword, manual segment, binding and optional JSONB-vector candidates, and returns explainable `score_parts`, `source_mode`, snippets and citations for admin/support;
  * requester-safe projection hides score diagnostics while preserving safe item payloads;
  * `POST /api/web/knowledge/retrieve` and `POST /api/web/knowledge/search/preview` are live for admin/support/auditor retrieval preview without changing the existing public search contract;
  * retrieval writes safe `knowledge.retrieval.executed` / `knowledge.retrieval.zero_results` audit events and records search analytics;
  * typed webapp helpers `retrieveKnowledge` and `previewKnowledgeRetrieval` cover the new endpoints.
* Phase 5B optional rerank slice is implemented:

  * `KnowledgeRetrievalService` uses OpenRouter-compatible rerank only when search settings enable rerank and a rerank model profile, provider, secret, policy and injected transport are available;
  * successful mocked rerank adds `score_parts.rerank`, tags `source_mode=rerank`, reorders candidates and emits `knowledge.retrieval.rerank_used`;
  * provider/config/request failures keep the pre-rerank candidate order, set safe fallback mode and emit `knowledge.retrieval.rerank_failed_fallback`;
  * no normal unit test performs network calls.
* Phase 5C admin score breakdown UI is implemented:

  * `/app/admin/knowledge/search-settings` preview now calls `POST /api/web/knowledge/search/preview` instead of legacy item-only search;
  * preview results render nested item data, snippets, source modes, score, citations count and per-source `score_parts` for admin/support diagnostics;
  * visible text remains Russian-first and no raw vectors/secrets are displayed.
* Phase 5D requester portal search UI is implemented:

  * `/app/kb` redirects to protected requester route `/app/kb/search`;
  * `/app/kb/search` renders a Russian-first standalone search experience over public-compatible `POST /api/knowledge/search`;
  * the portal request uses `actor_role=requester` and `surface=requester_portal`, shows AI-used/effective-mode state, safe summaries and no admin score diagnostics;
  * requester navigation now includes `База знаний`, and workspace detection treats `/app/kb/*` as requester-owned instead of support/admin.
* Focused verification:

  * `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_hybrid_retrieval.py -q --tb=short` passed with 3 tests;
  * `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_hybrid_retrieval.py server/tests/test_knowledge_vector_search.py server/tests/test_knowledge_embeddings.py server/tests/test_knowledge_segments.py server/tests/test_knowledge_search_segments.py server/tests/test_knowledge_search_settings.py server/tests/test_knowledge_search.py -q --tb=short` passed with 26 tests and only existing aiohttp app-key warnings;
  * `pnpm --dir webapp test -- src/features/knowledge/api.test.ts` passed with 11 tests.
  * After Phase 5B, `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_hybrid_retrieval.py -q --tb=short` passed with 5 tests.
  * After Phase 5C, `pnpm --dir webapp test -- src/features/knowledge/search-settings-page.test.tsx` passed with 1 test.
  * After Phase 5D, `pnpm --dir webapp test -- src/pages/kb/search-page.test.tsx src/app/navigation.test.ts src/features/knowledge/api.test.ts` passed with 3 files / 23 tests.
* Remaining Phase 5 work:

  * dedicated browser/live retrieval evidence after deploy remains pending for semantic hybrid/vector/rerank behavior, not just route load. The check must cover requester-safe search, AI-off fallback, ACL-safe projection, diagnostics separation and real-key rerank/OpenRouter behavior only when an operator supplies the approved key.

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

Status 2026-06-12:

* Phase 6A Ask foundation is implemented:

  * `KnowledgeAskService` validates global search settings and keeps Ask disabled unless `rag_answer_enabled=true` and `effective_mode=rag_answer`;
  * disabled Ask returns `answer_status=ai_disabled`, Russian `display_message`, citations/search fallback payloads and requester-safe retrieval results;
  * enabled Ask uses `KnowledgeRetrievalService` evidence, OpenRouter-compatible answer model profiles, `ai_policy_profiles.answer_allowed`, env-backed secret refs and injected transport for mocked tests;
  * provider/config/request failures return `answer_status=provider_unavailable` with top search results instead of breaking requester flow;
  * insufficient evidence returns `answer_status=not_enough_evidence`;
  * AI calls write redacted `ai_request_audit` rows, and workflow states emit Observer-visible `knowledge.rag.ai_disabled`, `knowledge.rag.provider_unavailable`, `knowledge.rag.not_enough_evidence`, `knowledge.rag.policy_blocked` and `knowledge.rag.answer_generated`.
* Ask APIs are implemented:

  * public-compatible requester-safe `POST /api/knowledge/ask`;
  * authenticated `POST /api/web/knowledge/ask`;
  * authenticated `POST /api/web/knowledge/ask/preview`.
* `/app/kb/ask` is implemented:

  * protected requester workspace route;
  * Russian-first question box, answer panel, citation panel and fallback search results;
  * requester navigation includes `AI-вопрос`.
* Focused verification:

  * `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_ask.py -q --tb=short` passed with 4 tests.
  * `pnpm --dir webapp test -- src/pages/kb/ask-page.test.tsx src/pages/kb/search-page.test.tsx src/app/navigation.test.ts src/features/knowledge/api.test.ts` passed with 4 files / 25 tests.
* Phase 6B Ask requester action hardening, 2026-06-12:

  * `/app/kb/ask` now exposes requester answer actions after a grounded/fallback answer: `Ответ полезен`, `Ответ не помог`, `Предложить исправление` and `Создать обращение`.
  * Feedback and correction reuse existing requester-safe article contracts `POST /api/knowledge/articles/{slug}/feedback` and `POST /api/knowledge/articles/{slug}/correction-request`; no new backend endpoint, table or API contract was added.
  * Actions target the first requester-safe retrieval result with a slug for both answered and AI-off fallback results, and the create-ticket CTA links to `/app/requester/new` even when a direct feedback target is unavailable.
  * RED test: `pnpm --dir webapp test -- src/pages/kb/ask-page.test.tsx` failed as expected before implementation because the `Создать обращение` link was absent.
  * GREEN test: `pnpm --dir webapp test -- src/pages/kb/ask-page.test.tsx` passed with 1 file / 2 tests after implementation.
  * Targeted regression: `pnpm --dir webapp test -- src/pages/kb/ask-page.test.tsx src/pages/kb/search-page.test.tsx src/app/navigation.test.ts src/features/knowledge/api.test.ts` passed with 4 files / 30 tests before and after the AI-off fallback action-row correction.
  * Build/docs sanity: `pnpm --dir webapp build`, `python scripts/docs_inventory.py --check-links`, `python scripts/verify_workspace.py` and `git diff --check -- PLANS.md docs/QUICK_LOOKUP.md server/docs/KNOWLEDGE_PLATFORM.md server/docs/CODEMAP.md webapp/src/pages/kb/ask-page.tsx webapp/src/pages/kb/ask-page.test.tsx` passed; diff check reported CRLF conversion warnings only.
  * Remote validation: `python scripts/release_server_to_remote.py --branch codex/helpdesk-process-model --allow-local-dirty --gate quick --skip-ci-check --leave-running --smoke-insecure-tls` deployed commit `db9d9ee0`; `/api/health` returned 200 on smoke attempt 2.
  * Browser/live evidence: in-app browser opened `https://192.168.100.17:9443/app/kb/ask`, submitted `VPN`, received AI-off fallback/search results and confirmed visible actions `Ответ полезен`, `Ответ не помог`, `Предложить исправление` and `Создать обращение`.
* Phase 6C citation validation hardening, 2026-06-12:

  * `KnowledgeAskService` now blocks AI answers that contain critical operational claims without any valid `[1]..[N]` source marker.
  * Out-of-range citation markers are blocked as `UNKNOWN_CITATION`; uncited critical claims are blocked as `UNCITED_CRITICAL_CLAIM`.
  * Blocked answers are not shown to requesters/support. Ask returns safe `answer_status=not_enough_evidence`, preserves retrieval fallback/citations, writes a blocked `ai_request_audit` row and emits `knowledge.rag.not_enough_evidence` with reason metadata.
  * RED test: `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_ask.py::test_knowledge_ask_blocks_uncited_critical_claims -q --tb=short` failed before implementation because the uncited critical answer was returned as `answered`.
  * GREEN tests: the same focused test passed with 1 test, and `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_ask.py -q --tb=short` passed with 5 tests.
  * Remote validation: `python scripts/release_server_to_remote.py --branch codex/helpdesk-process-model --allow-local-dirty --gate quick --skip-ci-check --leave-running --smoke-insecure-tls` deployed commit `661a7b43`; `/api/health` returned 200 on smoke attempt 2.
* Phase 6D support/admin Ask debug view, 2026-06-12:

  * `/app/knowledge` support Knowledge Workspace now includes an `Ask debug` panel that runs `POST /api/web/knowledge/ask/preview` through `previewKnowledgeAsk()`.
  * The panel submits `surface=support_ask_debug`, `limit=5`, and renders answer status, effective mode, AI fallback/used state, fallback mode, audit id, citation count and per-result retrieval diagnostics.
  * Debug result rows expose support/admin-safe score, `score_parts`, `source_mode`, `chunk_id` and `segment_id`; requester `/app/kb/ask` still hides admin diagnostics.
  * RED test: `pnpm --dir webapp test -- src/features/knowledge/support-workspace-page.test.tsx` failed before implementation because `Ask debug query` was absent.
  * GREEN test: the same focused test passed with 1 file / 2 tests after implementation.
  * Remote validation: `python scripts/release_server_to_remote.py --branch codex/helpdesk-process-model --allow-local-dirty --gate quick --skip-ci-check --leave-running --smoke-insecure-tls` deployed commit `165c4747`; `/api/health` returned 200 on smoke attempt 2.
  * Browser validation: Playwright/browser opened `https://192.168.100.17:9443/app/knowledge`, confirmed the `Ask debug` panel, filled `VPN`, ran `Проверить Ask`, and saw `ai_disabled`, `keyword_only`, `AI fallback`, 5 citations plus per-result `score`, `source_mode`, `chunk_id`, `segment_id` and `keyword_*` score parts.
* Phase 6E requester Ask feedback analytics and ticket prefill, 2026-06-12:

  * `/app/kb/ask` now adds Ask-specific feedback metadata when requester marks an answer useful/not useful: `source=knowledge_ask`, `answer_status`, `audit_id`, `ai_used`, `effective_mode`, fallback mode, query, primary item/version/chunk/segment, primary score and citation count.
  * The create-ticket CTA still routes to `/app/requester/new`, but now stores a safe `pc_client.knowledge_ask.ticket_context` session draft with query, Ask status, audit id, top retrieval result and citations.
  * `/app/requester/new` reads that draft once, replaces the default title with `Knowledge Ask: <query>`, pre-fills the description with Ask status/audit/top article context, and submits existing `knowledge_attempts` with `result=ticket_created_after_view` so the current requester ticket create API records the downstream `ticket_created_after_view` analytics event.
  * RED tests: `pnpm --dir webapp test -- src/pages/kb/ask-page.test.tsx src/pages/requester/index.test.tsx` failed before implementation because Ask context was absent and requester ticket draft stayed empty/default.
  * GREEN tests: `pnpm --dir webapp test -- src/pages/kb/ask-page.test.tsx src/pages/requester/index.test.tsx` passed with 2 files / 13 tests; expanded `pnpm --dir webapp test -- src/pages/kb/ask-page.test.tsx src/pages/requester/index.test.tsx src/features/requester/api.test.ts src/features/knowledge/api.test.ts src/app/navigation.test.ts` passed with 5 files / 54 tests.
  * Remote validation: `python scripts/release_server_to_remote.py --branch codex/helpdesk-process-model --allow-local-dirty --gate quick --skip-ci-check --leave-running --smoke-insecure-tls` deployed commit `ef5cf73b`; `/api/health` returned 200 on smoke attempt 2.
  * Browser validation: Playwright/browser opened `https://192.168.100.17:9443/app/kb/ask`, submitted `VPN`, saw AI-off fallback actions, clicked `Создать обращение`, and confirmed `/app/requester/new` was prefilled with `Knowledge Ask: VPN` plus Ask status/effective mode/top article context in the description. Live submit was not attempted because the current admin-backed requester session showed `Insufficient permissions` and a disabled create button for that account/device state.
* Phase 6E correction, 2026-06-12:

  * The Ask ticket draft is now a read-once `sessionStorage` value on `/app/requester/new`; it is removed immediately after the first read attempt and ignored after 30 minutes. This prevents stale Ask context from being replayed after page reloads or a logout/login in the same browser tab.
  * Targeted regression added this storage cleanup assertion to `webapp/src/pages/requester/index.test.tsx`.
  * Local verification: `pnpm --dir webapp test -- src/pages/kb/ask-page.test.tsx src/pages/requester/index.test.tsx src/features/requester/api.test.ts src/features/knowledge/api.test.ts src/app/navigation.test.ts` passed with 5 files / 59 tests; `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_requester_workspace_api.py server/tests/test_knowledge_feedback.py server/tests/test_knowledge_ask.py server/tests/test_ticket_knowledge_links_compat.py -q --tb=short` passed with 27 tests; `pnpm --dir webapp build`, `python scripts/docs_inventory.py --check-links`, `python scripts/verify_workspace.py` and `git diff --check -- PLANS.md docs/completed/BROWSER_REQUESTER_AGENT_IDENTITY_MODEL.md webapp/src/pages/requester/index.tsx webapp/src/pages/requester/index.test.tsx` passed.
  * Remote validation: `python scripts/release_server_to_remote.py --branch codex/helpdesk-process-model --allow-local-dirty --gate quick --skip-ci-check --leave-running --smoke-insecure-tls` deployed commit `f50279db`; `/api/health` returned 200 on smoke attempt 2.
  * Browser/live submit validation: Playwright browser used requester web user `knowledge-live-requester@example.test` with a linked `RegistryPerson` and no devices, opened `/app/kb/ask`, submitted `VPN`, clicked `Create ticket`, confirmed `/app/requester/new` prefill, confirmed `pc_client.knowledge_ask.ticket_context` was cleared from `sessionStorage`, filled the live required form fields, previewed the request and submitted the ticket.
  * Live result: ticket `bf968d13-ea5d-4c6e-8153-0dc612ec6a55` was created with `request_context=no_device`, `requester_account_mode=browser_no_device`, 4 stored `knowledge_attempts` all carrying `result=ticket_created_after_view`, and a `knowledge_feedback_events` row with `event_type=ticket_created_after_view`, `source_surface=requester_portal`, `actor_role=requester` and 4 metadata attempts.
  * Live evidence: `artifacts/browser_live_validation/ask-requester-submit-f50279db-1781286917167/report.json`, `01-requester-prefill.png`, `02-requester-created.png`, `network.json` and `console.json`. Console was empty; network/status evidence had no probe leaks for `sk-or-`, `sk-proj-`, `BEGIN PRIVATE KEY`, `secret-token` or `password=hidden`.
* Remaining Phase 6 work:

  * Browser/live evidence after deploy is complete for the AI-off/fallback requester prefill, full no-device requester ticket submit/analytics, and support debug flows.
  * Optional live OpenRouter answer signoff remains pending until an operator provides a key through the approved secret/config path.

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
* `GET /api/knowledge/portal/spaces/{spaceCode}`
* `GET /api/knowledge/portal/tags/{tag}`
* `GET /api/knowledge/articles/{slug}`
* `POST /api/knowledge/articles/{slug}/feedback`
* `POST /api/knowledge/articles/{slug}/correction-request`
* `POST /api/knowledge/articles/{slug}/bookmark`
* `DELETE /api/knowledge/articles/{slug}/bookmark`

Implemented in this iteration:

* Added requester-safe `KnowledgePortalService` over existing spaces/items/versions/segments, with public-compatible API routes:

  * `GET /api/knowledge/portal/home`;
  * `GET /api/knowledge/portal/spaces/{space_code}`;
  * `GET /api/knowledge/portal/tags/{tag}`;
  * `GET /api/knowledge/articles/{slug}`;
  * `POST /api/knowledge/articles/{slug}/feedback`;
  * `POST /api/knowledge/articles/{slug}/correction-request`;
  * `POST|DELETE /api/knowledge/articles/{slug}/bookmark`.

* Public portal APIs force requester ACL before returning data, so authenticated support/admin test contexts cannot read `support_internal` content through `/api/knowledge/*`.
* Added React routes:

  * `/app/kb` portal home;
  * `/app/kb/articles/:slug` article reader;
  * `/app/kb/spaces/:spaceCode` space collection;
  * `/app/kb/tags/:tag` tag collection.

* Portal home links to search, Ask, article reader, spaces and tags. Article reader shows title, summary, body, TOC from markdown headings, active segments, tags, owner/review freshness, helpful/not helpful, correction, bookmark and create-ticket CTA.
* Phase 7 hardening adds migration `114` with dedicated `knowledge_article_views`, `knowledge_user_bookmarks`, `knowledge_correction_requests` and `knowledge_article_subscriptions` tables. Feedback still writes `knowledge_feedback_events`; article views, bookmark state and correction requests now also have persisted portal-specific rows.
* Tests added:

  * `server/tests/test_knowledge_portal.py`;
  * `webapp/src/pages/kb/home-page.test.tsx`;
  * `webapp/src/pages/kb/article-page.test.tsx`;
  * `webapp/src/pages/kb/collection-page.test.tsx`;
  * portal helper coverage in `webapp/src/features/knowledge/api.test.ts`;
  * requester workspace route coverage in `webapp/src/app/navigation.test.ts`.

Remaining Phase 7 product hardening:

* Completed in the 2026-06-12 hardening slice: dedicated portal tables, signal-ranked popular/recommended articles, and a full article correction comment form.

Phase 7 live/browser result, deployed commit `7bb4ff91`, 2026-06-12:

* Deployed `codex/helpdesk-process-model` to `192.168.100.17` with quick release gate and remote smoke `GET /api/health -> 200`.
* Browser evidence captured under `artifacts/browser_live_validation/knowledge-portal-7bb4ff91/`.
* Verified requester web session (`actor_role=user`, workspace `requester`) can load `/api/knowledge/portal/home` through web-session cookie auth.
* Verified `/app/kb`, `/app/kb/search?q=VPN` and `/app/kb/ask` render Russian requester portal surfaces without console/page/network errors.
* Verified article reader `/app/kb/articles/codex-stage2b-requester-kb-20260608-2107`, helpful feedback, correction request, bookmark action, `/app/kb/spaces/glossary` and `/app/kb/tags/live` without console/page/network errors.
* Temporary live-check requester users were created for the browser run and deactivated after verification.

Remaining Phase 7 product hardening after live check:

* Completed locally in the 2026-06-12 hardening slice. Remote/browser validation is required after commit/deploy because the article reader and portal home UI changed.
* Subscription APIs/UI are not exposed yet; only the persisted table exists for the planned article update notification flow.

Phase 7 hardening local result, 2026-06-12:

* Added migration `114` and SQLAlchemy models for persisted portal article views, user bookmarks, correction requests and future article subscriptions.
* `GET /api/knowledge/articles/{slug}` records requester-safe article views after ACL-filtered lookup; correction/bookmark writes still reuse `knowledge_feedback_events` and now also persist dedicated portal rows.
* `GET /api/knowledge/portal/home` ranks `popular_articles` and `featured_articles` from persisted view, active bookmark, helpful feedback and open correction signals, falling back to recent articles only when no signals exist.
* `/app/kb/articles/:slug` now shows a correction comment textarea and sends the requester-entered comment to `/api/knowledge/articles/{slug}/correction-request`; `/app/kb` renders a `Популярные` section from `popular_articles`.
* RED checks failed before implementation as expected: focused backend dedicated-table test failed on missing `knowledge_article_views`; focused article-page test failed because the correction comment field was absent.
* GREEN checks: `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_portal.py -q --tb=short` passed with 9 tests; `pnpm --dir webapp test -- src/pages/kb/home-page.test.tsx src/pages/kb/article-page.test.tsx src/pages/kb/collection-page.test.tsx src/features/knowledge/api.test.ts` passed with 4 files / 20 tests.
* Sanity checks passed: `pnpm --dir webapp build`, `python -m compileall -q server shared scripts`, `python scripts/docs_inventory.py --check-links`, `python scripts/verify_workspace.py`, and focused `git diff --check`.

Phase 7 hardening remote/browser result, deployed commit `c88aba7b`, 2026-06-12:

* `python scripts/release_server_to_remote.py --branch codex/helpdesk-process-model --allow-local-dirty --gate quick --skip-ci-check --leave-running --smoke-insecure-tls` deployed commit `c88aba7b`; Alembic applied `113 -> 114`; `/api/health` returned 200 on smoke attempt 2.
* Browser opened `https://192.168.100.17:9443/app/kb` and confirmed the requester Knowledge Portal renders `Рекомендуемые статьи`, the new `Популярные` section and `Недавно обновленные`.
* Browser opened `https://192.168.100.17:9443/app/kb/articles/codex-stage2b-requester-kb-20260608-2107`, confirmed the article reader shows `Комментарий к исправлению`, filled `Live Phase 7 hardening check: уточнить шаг питания.`, submitted `Предложить исправление` and saw `Запрос на исправление отправлен.`.
* The same live page clicked `В закладки` and saw `Статья добавлена в закладки.`.
* Browser network evidence for the article run: `GET /api/knowledge/articles/codex-stage2b-requester-kb-20260608-2107 -> 200`, `POST /correction-request -> 200`, `POST /bookmark -> 200`; console errors after the article run: 0.

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

Phase 8 current state, 2026-06-12:

* `/app/admin/knowledge/studio` now renders a dedicated Russian-first Knowledge Authoring Studio instead of reusing the admin operations panel.
* Implemented first authoring slice in `webapp/src/features/knowledge/authoring-studio-page.tsx`: draft/article browser, metadata fields, Markdown editor, template insertion, requester-safe preview, lightweight diff counters, publish checklist, disabled AI tools panel and embedded `ArticleSegmentationPanel`.
* The first slice deliberately reuses existing item/version/template/publish/segment APIs and adds no new DB tables yet.
* RED/green webapp coverage lives in `webapp/src/pages/admin/knowledge-studio-page.test.tsx` and covers load/edit preview, template insertion, version creation, publish payload, Russian labels and mojibake guard.
* Verified locally:

  * `pnpm --dir webapp test -- src/pages/admin/knowledge-studio-page.test.tsx` -> 2 passed.
  * `pnpm --dir webapp test -- src/pages/admin/knowledge-studio-page.test.tsx src/features/knowledge/article-segmentation-panel.test.tsx src/features/knowledge/api.test.ts src/app/navigation.test.ts` -> 29 passed.
  * `pnpm --dir webapp build` -> passed.

Remaining Phase 8 product hardening before declaring the full phase complete:

* Persist `knowledge_article_editor_events` and optional attachment/diff cache tables if audit-grade editor history is required.
* Add review approve/comment workflow beyond the existing submit/request-changes/archive actions.
* Add richer structured block editing beyond Markdown plus template insertion.

Phase 8 hardening slice, 2026-06-12:

* Studio now includes a `Новый черновик` creation panel backed by existing `POST /api/web/knowledge/items`; the panel sends space, type, visibility, title, slug, summary, owner, reviewer and tags without leaving `/app/admin/knowledge/studio`.
* Studio now exposes `Ревью и жизненный цикл` actions backed by existing `POST /api/web/knowledge/items/{item_id_or_slug}/review-action`: `submit_review`, `request_changes` and `archive` for archive/supersede governance.
* Studio now exposes `Версия для сравнения` and `Откатить к выбранной версии`, reusing the selected-version publish API for rollback to an older immutable version.
* The selected version no longer snaps back to the current version after the user selects an older version for comparison or rollback.
* Studio default selection now prefers non-archived items with a current version, so archived live-check drafts without versions do not hide the manual segment controls on a fresh page load; archive/retire lifecycle actions also reset selection back to the preferred active item.
* Focused coverage in `webapp/src/pages/admin/knowledge-studio-page.test.tsx` now covers new draft creation payloads, review action payloads, rollback publish payloads, archive/supersede action and archived-first API ordering.
* Verified locally:

  * `pnpm --dir webapp test -- src/pages/admin/knowledge-studio-page.test.tsx` -> 3 passed.
  * `pnpm --dir webapp test -- src/pages/admin/knowledge-studio-page.test.tsx src/features/knowledge/article-segmentation-panel.test.tsx src/features/knowledge/api.test.ts src/app/navigation.test.ts` -> 30 passed.
  * `pnpm --dir webapp build` -> passed.
  * `python scripts/verify_workspace.py` -> passed.
  * `git diff --check` -> passed with only existing CRLF warnings.

Phase 8 live/browser result, deployed commit `ae402548`, 2026-06-12:

* Deployed `codex/helpdesk-process-model` to `192.168.100.17` with quick release gate and remote smoke `GET /api/health -> 200`.
* Browser evidence captured under `artifacts/browser_live_validation/knowledge-studio-ae402548/`.
* Verified admin web session can load `/app/admin/knowledge/studio` and `GET /api/web/knowledge/items` returns `200`.
* Verified visible Russian Studio surfaces: `Студия статей`, `Черновики и статьи`, `Метаданные статьи`, `Редактор`, `Предпросмотр`, `Проверка публикации`, `AI-инструменты отключены` and `Разметка статьи`.
* Verified no console/page/network errors and no visible mojibake markers during the live browser run.

Phase 8 hardened live/browser result, deployed commit `5b8930e4`, 2026-06-12:

* Deployed `codex/helpdesk-process-model` to `192.168.100.17` with quick release gate, migrations and remote smoke `GET /api/health -> 200`.
* Browser evidence captured under `artifacts/browser_live_validation/knowledge-studio-hardening-5b8930e4-1781234318001/`.
* Verified `/app/admin/knowledge/studio` with admin web session after archived no-version live draft existed first in `GET /api/web/knowledge/items` (`first_status=archived`); Studio still default-selected an active versioned item and showed `Разметка статьи` plus `Запустить авторазметку`.
* Verified visible hardened controls: `Версия для сравнения`, `Откатить к выбранной версии`, `Отправить на ревью`, `Запросить правки`, `Архивировать / supersede` and manual segment fields/actions.
* Verified manual segment lifecycle in browser: `POST /api/web/knowledge/items/{item_id}/segments -> 200`, created segment `3c66dabf-17ea-48a1-a81f-8ac4fc6f1007`, then `DELETE /api/web/knowledge/segments/{segment_id} -> 200`.
* Verified new draft/review lifecycle in browser: `POST /api/web/knowledge/items -> 200`, created item `1af4d555-eb0b-4b89-8060-07fb36140b5c`, then `submit_review -> 200` and `archive -> 200`.
* Verified rollback control visibility on the deployed route; no production rollback was executed against an existing published article during this cleanup-safe browser run.
* Browser console messages: none. Failed browser requests during the Studio run: none. All observed Knowledge API calls returned `200`.

Phase 8 editor-history hardening slice, 2026-06-12:

* Added migration `115` for persisted Authoring Studio audit history:

  * `knowledge_article_editor_events` records draft creation, version creation, publish/rollback and review lifecycle actions.
  * `knowledge_version_diff_cache` stores safe immutable-version diff summaries with added/removed/changed line counts, content hash and change summary.

* Added `KnowledgeEditorHistoryService` and authenticated `GET /api/web/knowledge/items/{item_id_or_slug}/editor-history` for admin/support/auditor roles.
* Existing Studio-backed flows now write editor history:

  * `POST /api/web/knowledge/items` writes `draft_created`;
  * `POST /api/web/knowledge/items/{item_id_or_slug}/versions` writes `version_created` and diff cache;
  * `POST /api/web/knowledge/items/{item_id_or_slug}/publish` writes `published` or `rollback_published`;
  * `POST /api/web/knowledge/items/{item_id_or_slug}/review-action` writes `review_submitted`, `changes_requested`, `archived`, `retired` or review fallback events.

* `/app/admin/knowledge/studio` now loads and renders `История редактора` with latest workflow events and `Diff cache: +N / -N`; the history query is invalidated after draft/version/publish/review actions.
* Safety contract: editor-history responses expose event metadata and diff counts only, not article body, raw metadata, source refs, ticket/device fields or secret material.
* TDD status:

  * RED backend `server/tests/test_knowledge_api.py::test_knowledge_authoring_studio_records_editor_history` failed on missing `/editor-history` route before implementation.
  * RED frontend expectation was added to `webapp/src/pages/admin/knowledge-studio-page.test.tsx` for `История редактора`, `version_created`, `Publish from Studio` and `Diff cache: +2 / -1`.
  * GREEN focused backend now passes, 1 test.
  * GREEN focused Studio test now passes, 3 tests.

* Phase 8 product hardening status after this slice:

  * Review approve/comment workflow is implemented through `approve` and `comment` review-action buttons plus persisted `approved` / `commented` editor history events.
  * Richer structured block editing is implemented as Markdown block insertion controls for callout, table, code block and checklist.
  * Optional attachment tables/UI remain deferred until an attachment-backed authoring requirement is selected; this is no longer a blocker for Phase 8 because the plan marked attachments as optional.

Phase 8 completion result, 2026-06-12:

* Phase 8 is now complete for the planned non-optional Authoring Studio scope.
* Additional TDD status:

  * RED backend for review comment failed with `400 unsupported review action`; GREEN after `KnowledgeOperationsService.review_action()` accepted `comment` without status mutation.
  * RED frontend for `Добавить комментарий` and `Одобрить` failed on missing buttons; GREEN after Studio added both actions.
  * RED frontend for structured blocks failed on missing `Вставить callout`; GREEN after Studio added callout/table/code/checklist insertion controls.

* Additional focused verification:

  * `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_api.py::test_knowledge_authoring_studio_records_editor_history -q --tb=short` -> passed, 1 test.
  * `pnpm --dir webapp test -- src/pages/admin/knowledge-studio-page.test.tsx -t "runs review comment"` -> passed, 1 selected test.
  * `pnpm --dir webapp test -- src/pages/admin/knowledge-studio-page.test.tsx -t "structured markdown"` -> passed, 1 selected test.

Phase 8 final remote/live validation, 2026-06-12:

* Deployed commit `4d5eff4e` to `192.168.100.17` with `python scripts/release_server_to_remote.py --branch codex/helpdesk-process-model --allow-local-dirty --gate quick --skip-ci-check --leave-running --smoke-insecure-tls`.
* Remote Alembic migration ran `114 -> 115` and health smoke returned `GET /api/health -> 200`.
* Browser route validated: `https://192.168.100.17:9443/app/admin/knowledge/studio`.
* Live Studio workflow created article `codex-phase8-history-20260612072045` (`item_id=a3c566b0-7d36-4879-831d-a38a5e9e86bf`, `version_id=f6b167a8-c232-4910-81e0-ffbb1a400a92`) and verified:

  * `POST /api/web/knowledge/items` -> 200;
  * `POST /api/web/knowledge/items/{item_id}/versions` -> 200;
  * `POST /api/web/knowledge/items/{item_id}/publish` -> 200;
  * `POST /api/web/knowledge/items/{item_id}/review-action` for `comment` and `approve` -> 200;
  * `GET /api/web/knowledge/items/{item_id}/editor-history` -> 200.

* Editor history returned and UI rendered `draft_created`, `version_created`, `published`, `commented`, `approved`; diff cache rendered `Diff cache: +4 / -0`.
* Safety scan found no forbidden raw-history fields in the editor-history API response.
* Browser evidence: screenshot `phase8-studio-history.png`; network requests for current Studio run returned 200 for session, spaces, items, versions, segments, segmentation profiles and editor-history.
* Browser console errors for the current Studio run: none.
* Remote `server` and `control` services were stopped after validation.

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

Phase 9 first slice, 2026-06-12:

* `/app/admin/knowledge/graph` now routes to a dedicated Russian-first Visual Graph Studio.
* Frontend uses no new graph dependency yet; `webapp/src/features/knowledge/graph-studio-page.tsx` renders an SVG graph canvas with deterministic layout, node search/list, clickable nodes, edge labels, right-side inspector, warning/coverage counters, manual node creation and manual edge creation.
* Typed webapp helpers in `webapp/src/features/knowledge/api.ts` cover the existing backend graph endpoints:

  * `GET /api/web/knowledge/graph/nodes`
  * `POST /api/web/knowledge/graph/nodes`
  * `GET /api/web/knowledge/graph/nodes/{node_id_or_stable_key}/neighborhood?depth=2`
  * `POST /api/web/knowledge/graph/edges`

* Navigation now exposes `Граф знаний` inside the admin Knowledge domain.
* Live validation after deploy:

  * Commits: `73130642` added the Visual Graph Studio first slice; `c7449acd` aligned relation type defaults with the existing DB constraint and added backend validation for unsupported relation types.
  * Artifact: `artifacts/browser_live_validation/knowledge-graph-c7449acd-1781236903632/report.json`
  * Screenshot: `artifacts/browser_live_validation/knowledge-graph-c7449acd-1781236903632/knowledge-graph-live.png`
  * Remote URL: `https://192.168.100.17:9443/app/admin/knowledge/graph`
  * Result: login 200, graph nodes GET 200, required UI text present, manual node create POST 200, manual edge create POST 200, neighborhood GET 200.
  * Created live test node: `concept:codex-live-graph-1781236903632`
  * Created live test edge: `9498e50e-80a3-48e0-84d4-0ab69fb3d75e`, relation type `mentions`.
  * Console messages: none. Failed requests: none. HTTP errors: none.
  * Live finding fixed during this phase: the first UI default used `related_to`, which violated `ck_knowledge_edges_relation_type` and produced a server 500. The studio now defaults to valid relation types and the backend returns 400 for unsupported relation types before DB flush.
* Focused coverage:

  * `webapp/src/features/knowledge/graph-studio.test.tsx` covers graph canvas load, neighborhood display, node creation payload and edge creation payload.
  * `webapp/src/features/knowledge/api.test.ts` covers graph helper endpoint/payload contracts.
  * `webapp/src/app/navigation.test.ts` covers Knowledge domain route exposure.
  * `server/tests/test_knowledge_api.py::test_knowledge_graph_edges_reject_unknown_relation_type` covers invalid relation type 400 and valid `mentions` edge creation.

Phase 9 persisted layout slice, 2026-06-12:

* Added migration `116` with `knowledge_graph_layouts` keyed by `(scope_type, scope_ref)` and storing sanitized `layout_json` for graph canvas coordinates.
* Added `KnowledgeGraphService.get_layout()` / `save_layout()` and authenticated `GET/POST /api/web/knowledge/graph/layouts/{scope}`:

  * admin/support/auditor can load layouts;
  * admin/support can save layouts;
  * auditor write attempts return `403`;
  * layout JSON is narrowed to node stable-key coordinates plus viewport values before persistence/response.

* `/app/admin/knowledge/graph` now loads `default` persisted layout, applies saved node positions to the SVG canvas and exposes `Сохранить layout`.
* TDD status:

  * RED backend `server/tests/test_knowledge_api.py::test_knowledge_graph_layouts_save_and_load` failed with `404` before route implementation.
  * RED frontend API test failed because `fetchKnowledgeGraphLayout` was missing.
  * RED Graph Studio test failed because the layout status/control was not rendered.
  * GREEN targeted backend/API/Graph Studio tests now pass.
* Remote/live validation:

  * Deployed commits `a7a19491` and responsive follow-up `19efe98d` to `192.168.100.17` with quick release gate; remote smoke returned `GET /api/health -> 200`.
  * Remote Alembic migration ran `115 -> 116`.
  * Browser route validated: `https://192.168.100.17:9443/app/admin/knowledge/graph`.
  * UI rendered `Сохранить layout` and `Layout сохранен для scope default`; final viewport evidence captured as `phase9-graph-layout-final.png` and `phase9-graph-layout-coverage-final.png`.
  * Live API flow verified `GET /api/web/knowledge/graph/layouts/default` -> 200, `POST /api/web/knowledge/graph/layouts/default` -> 200, repeated GET -> 200, sanitized unexpected layout keys, and persisted coordinates `x=111`, `y=222`.
  * Current Graph Studio Knowledge API requests returned 200 for nodes, layout and neighborhood. Browser console errors: none.

Phase 9 graph CRUD/search slice, 2026-06-12:

* Added full governed graph CRUD beyond initial upsert/create:

  * `GET /api/web/knowledge/graph/search?q=...` returns ACL-filtered active nodes plus matching/connected edges;
  * `GET/PATCH/DELETE /api/web/knowledge/graph/nodes/{node_id_or_stable_key}`;
  * `GET /api/web/knowledge/graph/edges`, `GET/PATCH/DELETE /api/web/knowledge/graph/edges/{edge_id}`;
  * DELETE archives nodes/edges instead of hard-deleting; node archive also archives connected active edges.

* Graph mutations remain admin/support only; auditor is read-only and receives `403` for PATCH/DELETE.
* Graph Studio now lets operators edit the selected node label and archive visible edges or the selected node from the inspector, then refreshes nodes/neighborhood queries.
* TDD status:

  * RED backend `server/tests/test_knowledge_api.py::test_knowledge_graph_crud_search_and_archive` failed with `404` on `/api/web/knowledge/graph/search`.
  * RED frontend API test failed with `searchKnowledgeGraph is not a function`.
  * RED Graph Studio test failed because `Метка выбранного узла` and archive controls were not rendered.
  * GREEN targeted backend/API/Graph Studio tests now pass.
* Remote/live validation:

  * Deployed commit `02f51240` to `192.168.100.17` with quick release gate; remote smoke returned `GET /api/health -> 200` on attempt 2.
  * Browser route validated: `https://192.168.100.17:9443/app/admin/knowledge/graph`.
  * UI rendered `Метка выбранного узла`, `Сохранить узел`, `Архивировать выбранный узел` and per-edge archive controls.
  * Live API flow verified `GET /api/web/knowledge/graph/search`, `PATCH /api/web/knowledge/graph/nodes/{stable_key}`, `GET/PATCH/DELETE /api/web/knowledge/graph/edges/{edge_id}` and `DELETE /api/web/knowledge/graph/nodes/{stable_key}` all returned `200`.
  * Temporary live node `concept:crud-live-1781262810209` was archived; post-delete search returned zero nodes for that stable key.
  * Safe response scan found no forbidden raw keys. Browser console warnings/errors: none. Evidence screenshot: `phase9-graph-crud-live.png`.

Phase 9 AI proposal lifecycle slice, 2026-06-12:

* Added governed AI proposal persistence/API/review workflow:

  * migration `117` adds `knowledge_ai_proposals`;
  * `GET|POST /api/web/knowledge/ai/proposals`;
  * `POST /api/web/knowledge/ai/proposals/{proposal_id}/review`;
  * proposal payloads are sanitized before storage/response;
  * approve/reject/comment review is admin/support-only while auditor remains read-only;
  * graph node/edge proposals can be applied to the governed graph APIs on approval;
  * create/review writes Observer-visible `agent_runtime_audit` rows with source `knowledge_ai_proposals`.

* Graph Studio now renders pending graph AI proposals and can approve/reject them from the graph route.
* TDD status:

  * RED backend `server/tests/test_knowledge_api.py::test_knowledge_ai_proposals_graph_review_lifecycle_and_observer_audit` failed with `404` on `/api/web/knowledge/ai/proposals`.
  * RED frontend API test failed with `fetchKnowledgeAiProposals is not a function`.
  * RED Graph Studio test failed because `AI proposals` was not rendered.
  * GREEN targeted backend/API/Graph Studio tests now pass.
* Remote/live validation:

  * Deployed commit `6583551d` to `192.168.100.17` with quick release gate; remote Alembic ran `116 -> 117`, and health smoke returned `GET /api/health -> 200` on attempt 2.
  * Browser route validated: `https://192.168.100.17:9443/app/admin/knowledge/graph`.
  * Live API flow verified `POST /api/web/knowledge/ai/proposals`, `GET /api/web/knowledge/ai/proposals?target_kind=graph&status=pending`, `POST /api/web/knowledge/ai/proposals/941e4fb1-2a0e-4d3b-b747-9b2ffc38b2e3/review`, `GET /api/web/knowledge/graph/search?q=concept:ai-proposal-live-1781264653569` and approved proposal listing all returned `200`.
  * Approval applied graph refs `10b7f870-133c-4cac-a2b4-8354cd6247c3`, `cd16a6a3-02f4-4bd9-aa66-3c87b60467c3` and edge `af4d8dac-0aaf-4b87-89aa-952a3cd20967`; graph search found the `similar_to` edge.
  * Safe response scan found no forbidden raw keys: `source_ticket_id`, `device_id`, `token`, `secret-token`. Browser console warnings/errors: none.
  * Evidence: `phase9-ai-proposals-live.png`, `phase9-ai-proposals-console.json`, `phase9-ai-proposals-network.json`.

Phase 9 live/test graph cleanup slice, 2026-06-12:

* Used the live governed graph DELETE workflow to archive only explicit `support_internal` test nodes matching `concept:crud-live-*`, `concept:ai-proposal-live-*`, `concept:ai-proposal-live-target-*` and `concept:codex-live-graph-*`.
* Archived nodes:

  * `concept:ai-proposal-live-1781264653569`;
  * `concept:ai-proposal-live-target-1781264653569`;
  * `concept:codex-live-graph-1781236521026`;
  * `concept:codex-live-graph-1781236903632`;
  * `concept:crud-live-target-1781262810209`.

* All archive calls returned `200` with `status=archived`; repeated live searches by cleanup prefixes returned no remaining active support_internal test graph nodes.

Phase 9 remaining work:

* None for the graph CRUD/layout/AI-proposal scope. Continue with the remaining Phase 10 ingestion hardening items.

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

Phase 10 first slice, 2026-06-12:

* Implemented `/app/admin/knowledge/import` as a Russian-first Import/Ingestion wizard route.
* Added backend APIs:

  * `POST /api/web/knowledge/import/preview`
  * `POST /api/web/knowledge/import/create-drafts`

* Supported source kinds in this slice: `text`, `markdown`, `html`.
* Preview parses markdown H1 as detected title, H2-H6 headings as sections, plain text paragraphs as sections and strips HTML tags before calculating word/section counts.
* Draft creation reuses the existing `KnowledgeIngestionService.ingest_text()` path, creates review-required drafts and keeps AI enrichment disabled by default.
* If `ai_enrichment_enabled=true`, preview returns `blocked_pending_policy` with no proposals; real AI enrichment/proposal review remains a later subphase.
* Navigation now includes `Импорт знаний`, and the route is lazy-loaded through the React app router.
* Local verification completed before docs/live follow-up:

  * `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_import_api.py -q --tb=short` -> 2 passed.
  * `pnpm --dir webapp test -- src/features/knowledge/import-wizard.test.tsx` -> 1 passed.
  * `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_import_api.py server/tests/test_knowledge_api.py::test_knowledge_api_admin_crud_and_requester_safe_suggest -q --tb=short` -> 3 passed.
  * `pnpm --dir webapp test -- src/features/knowledge/import-wizard.test.tsx src/features/knowledge/api.test.ts src/app/navigation.test.ts` -> 3 files, 28 tests passed.
  * `pnpm --dir webapp build` -> passed.

Phase 10 live validation, 2026-06-12:

* Commit `e5303524` was deployed to `https://192.168.100.17:9443` with quick release gate, remote migrations and webapp bundle upload.
* Remote smoke passed: `GET /api/health` -> 200.
* Browser route validated: `https://192.168.100.17:9443/app/admin/knowledge/import`.
* Live flow completed:

  * web session login -> 200;
  * import preview `POST /api/web/knowledge/import/preview` -> 200;
  * create draft `POST /api/web/knowledge/import/create-drafts` -> 200;
  * created live draft item `7041042b-3a27-45ee-b142-006c7b17a7ea`, slug `codex-import-1781238442868`;
  * AI enrichment status was `disabled`;
  * browser console warnings/errors, failed requests and HTTP errors were empty.

* Evidence:

  * report: `artifacts/browser_live_validation/knowledge-import-e5303524-1781238442868/report.json`;
  * screenshot: `artifacts/browser_live_validation/knowledge-import-e5303524-1781238442868/knowledge-import-live.png`.

Phase 10 parser/upload policy slice, 2026-06-12:

* Extended `KnowledgeIngestionService.preview_import()` beyond the first text/markdown/html slice:

  * DOCX previews now accept `file_content_base64`, enforce a 5 MiB safe upload limit, parse `word/document.xml` with stdlib zip/XML text extraction and return plain-text title/sections/counts;
  * PDF previews now accept `file_content_base64`, enforce the same safe upload limit, require a `%PDF` header and extract simple text literals without adding a new dependency;
  * URL and Git source kinds are recognized but blocked by the safe import policy until an explicit allowlist/fetch/clone policy is implemented;
  * blocked remote imports return `error=remote_import_blocked` with a safe Russian display message and do not echo raw URLs, tokens or passwords.

* TDD status:

  * RED `server/tests/test_knowledge_import_api.py` failed because DOCX/PDF preview returned `400` and URL/Git returned generic `validation_error`.
  * GREEN focused import API tests now pass with 4 tests.
* Remote/live validation:

  * Deployed commit `d8df7b62` to `192.168.100.17` with quick release gate; remote smoke returned `GET /api/health -> 200` on attempt 2.
  * Browser route loaded: `https://192.168.100.17:9443/app/admin/knowledge/import`.
  * Same-origin live API checks verified DOCX preview -> `200` with detected title `Live DOCX Import`, PDF preview -> `200` with detected title `Live PDF Import Reconnect client`, URL preview -> `400 remote_import_blocked`, and Git preview -> `400 remote_import_blocked`.
  * Safe response scan for URL/Git policy blocks found no leaked `secret-token`, `password=hidden` or remote private URL fragments. Browser console recorded expected failed-resource entries for the deliberate `400` policy-block responses.

Phase 10 import auto-segmentation contract slice, 2026-06-12:

* Extended `POST /api/web/knowledge/import/create-drafts` with explicit backend auto-segmentation controls:

  * `auto_segment_after_import=true` runs the existing non-AI `KnowledgeSegmentationService.auto_segment()` after draft/version creation;
  * `segmentation_profile_code` selects the profile, defaulting to `default-auto`;
  * the response includes `segmentation.enabled`, `segmentation.status`, `segmentation.profile_code`, `segmentation.job` and `segmentation.segments`;
  * frontend API typing now exposes the optional `segmentation` result for the import wizard follow-up UI.

* TDD status:

  * RED `server/tests/test_knowledge_import_api.py::test_knowledge_import_create_drafts_can_run_auto_segmentation_profile` failed because the create-drafts response had no `segmentation` field.
  * GREEN `server/tests/test_knowledge_import_api.py` now passes with 5 tests.

* Live validation:

  * Commit `730cf5e3` was pushed to `origin/codex/helpdesk-process-model` and deployed with `scripts/release_server_to_remote.py --gate quick --skip-ci-check --leave-running --smoke-insecure-tls`.
  * Remote smoke verified `https://192.168.100.17:9443/api/health -> 200`.
  * Browser same-origin API check on `/app/admin/knowledge/import` verified `POST /api/web/knowledge/import/create-drafts -> 200` with `auto_segment_after_import=true`, `segmentation.status=completed`, profile `default-auto`, and segment titles `Symptoms`, `Fix`.
  * Follow-up `GET /api/web/knowledge/items/<item_id>/segments -> 200` returned the same two live segments.

Phase 10 import indexing queue slice, 2026-06-12:

* Extended `POST /api/web/knowledge/import/create-drafts` with `indexing` response metadata:

  * when global search settings have `vector_enabled=false`, the response returns `indexing.enabled=false`, `status=disabled`, `reason=vector_indexing_disabled`;
  * when `vector_enabled=true`, import draft creation immediately runs the existing observable item indexing path for the created `item_id` and `version_id`;
  * the returned `indexing.job`, `indexing.stats` and safe `indexing.embeddings` reuse `KnowledgeEmbeddingService.reindex_item()` and never expose raw `embedding_vector`;
  * the web handler passes the configured embedding transport through to the ingestion service for provider-backed environments.

* TDD status:

  * RED `server/tests/test_knowledge_import_api.py::test_knowledge_import_create_drafts_queues_indexing_when_enabled` failed with `KeyError: 'indexing'`.
  * GREEN focused test passed after implementation.
  * Sequential `server/tests/test_knowledge_import_api.py` passed with 6 tests.
  * Sequential `server/tests/test_knowledge_embeddings.py` passed with 5 tests; the first parallel run of those two shared-DB files failed due `ConnectionDoesNotExistError` from shared test DB contention and was discarded.

* Live validation:

  * Commit `ea220d97` was pushed to `origin/codex/helpdesk-process-model` and deployed with `scripts/release_server_to_remote.py --gate quick --skip-ci-check --leave-running --smoke-insecure-tls`.
  * Remote smoke verified `https://192.168.100.17:9443/api/health -> 200`.
  * Browser same-origin API check on `/app/admin/knowledge/import` temporarily enabled `vector_enabled=true`, created draft `indexed-import-live-1781269338959`, and verified `indexing.enabled=true`, `indexing.status=completed`, `job.scope_type=item`, `job.metadata_json.version_id=<created version_id>`, `stats.chunks_seen=1`, `stats.disabled_embeddings=1`.
  * Follow-up `GET /api/web/knowledge/indexing/jobs -> 200` found the created indexing job, response scan confirmed no raw `embedding_vector`, and the previous search setting `vector_enabled=false` was restored.

Phase 10 governed AI enrichment proposal slice, 2026-06-12:

* Extended `POST /api/web/knowledge/import/create-drafts` so `ai_enrichment_enabled=true` creates governed pending proposals through the existing `KnowledgeAiProposalService`:

  * proposal types: `summary`, `tags`, `glossary_term`, `graph_node`, `duplicate`;
  * proposals target the created item/version or graph review path and reuse the existing `POST /api/web/knowledge/ai/proposals/{proposal_id}/review` approve/reject/comment lifecycle;
  * generated proposal payloads are structural review seeds, not raw LLM output, and do not echo import body text, uploaded file names or remote/source secrets;
  * graph node proposals can be approved through the existing graph apply path and return `applied_refs.node_ids`.

* TDD status:

  * RED `server/tests/test_knowledge_import_api.py::test_knowledge_import_create_drafts_creates_governed_ai_enrichment_proposals` failed because import responses still returned `blocked_pending_policy`.
  * GREEN focused test passed after implementation.
  * Sequential `server/tests/test_knowledge_import_api.py` plus `server/tests/test_knowledge_api.py::test_knowledge_ai_proposals_graph_review_lifecycle_and_observer_audit` passed with 8 tests.

* Remote/live validation:

  * Commit `85ee0934` was pushed to `origin/codex/helpdesk-process-model` and deployed with `scripts/release_server_to_remote.py --gate quick --skip-ci-check --leave-running --smoke-insecure-tls`.
  * Remote smoke verified `https://192.168.100.17:9443/api/health -> 200`.
  * Browser same-origin API check on `/app/admin/knowledge/import` created draft `ai-proposals-import-live-1781270022361` with `ai_enrichment_enabled=true`.
  * `POST /api/web/knowledge/import/create-drafts -> 200` returned `ai_enrichment.status=review_required`, five pending proposals, and proposal types `duplicate`, `glossary_term`, `graph_node`, `summary`, `tags`.
  * Safe response scan confirmed no `secret-token` source-name leak and no raw body phrase leak.
  * Approving the created graph proposal through `POST /api/web/knowledge/ai/proposals/0980d5a5-0d54-4414-b6c0-c9758a61ea8c/review -> 200` returned `status=approved` and one applied graph node.
  * Follow-up `GET /api/web/knowledge/ai/proposals?status=pending&target_kind=item -> 200` found the created item proposal review rows.

Phase 10 allowlisted remote import policy slice, 2026-06-12:

* Added explicit fail-closed URL/Git remote import support:

  * default behavior stays `remote_import_blocked` for `url` and `git`;
  * `KNOWLEDGE_REMOTE_IMPORT_ENABLED=true` plus exact/wildcard `KNOWLEDGE_REMOTE_IMPORT_ALLOWED_HOSTS` is required before remote fetch/clone can run;
  * URL import requires HTTPS, blocks URL credentials and redirects, enforces configured byte/time limits and returns only safe `remote_source` metadata;
  * Git import requires an allowlisted HTTPS repo, clones into a temp directory with depth/no-tags limits, reads only markdown/text/html files within configured file/byte limits, maps draft ingestion to `git_repo`, and returns no raw query strings or secret-bearing source URLs;
  * typed webapp API now exposes optional safe `remote_source` metadata for future import wizard controls.

* TDD and verification:

  * RED focused URL/Git allowlist tests first failed because `KnowledgeRemoteImportFetcher` and config policy did not exist.
  * GREEN focused URL/Git allowlist tests passed after implementation.
  * `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_import_api.py -q --tb=short` -> 10 passed.
  * `python -m compileall -q server/config.py server/knowledge/ingestion_service.py server/tests/test_knowledge_import_api.py scripts/navigation_catalog.py` -> passed.
  * `pnpm --dir webapp test -- src/features/knowledge/api.test.ts` -> 20 passed.
  * `pnpm --dir webapp build` -> passed.
  * `python scripts/docs_inventory.py --check-links` -> passed.
  * `python scripts/verify_workspace.py` -> passed.

* Remote/live validation:

  * Commit `84fad303` was pushed to `origin/codex/helpdesk-process-model` and deployed with `scripts/release_server_to_remote.py --gate quick --skip-ci-check --leave-running --smoke-insecure-tls`.
  * Remote smoke verified `https://192.168.100.17:9443/api/health -> 200`.
  * Browser route loaded: `https://192.168.100.17:9443/app/admin/knowledge/import`.
  * Same-origin browser API checks against deployed default config verified URL preview -> `400 remote_import_blocked` and Git preview -> `400 remote_import_blocked`.
  * Safe response scans found no leaked `secret-token`, `password=hidden` or `outside.example.test` host fragments.
  * Browser screenshot captured as `knowledge-import-remote-policy-84fad303.png`; console recorded expected failed-resource entries for the deliberate `400` policy-block responses.

Phase 10 import wizard UI controls slice, 2026-06-12:

* Extended `/app/admin/knowledge/import` controls:

  * format selector now includes `text`, `markdown`, `html`, `docx`, `pdf`, `url` and `git`;
  * DOCX/PDF upload reads selected file into `file_content_base64`, updates `source_name` and uses the existing preview API;
  * URL/Git modes expose dedicated URL/repo/ref fields plus a visible remote import policy message;
  * auto-segmentation can be enabled before draft creation and uses selectable profiles loaded from `/api/web/knowledge/segmentation-profiles`;
  * preview can display safe `remote_source` metadata and result can display segmentation status/profile.

* TDD status:

  * RED `pnpm --dir webapp test -- src/features/knowledge/import-wizard.test.tsx` initially failed after adding the new controls because the test contract and query payload expectations did not cover segmentation profile loading and remote controls.
  * GREEN focused import wizard test now passes with 2 tests.
  * `pnpm --dir webapp test -- src/features/knowledge/import-wizard.test.tsx src/features/knowledge/api.test.ts` -> 2 files, 22 tests passed.
  * `pnpm --dir webapp build` -> passed.
  * `python -m compileall -q scripts/navigation_catalog.py` -> passed.
  * `python scripts/docs_inventory.py --check-links` -> passed.
  * `python scripts/verify_workspace.py` -> passed.

* Remote/live validation:

  * Commit `2c2b651b` was pushed to `origin/codex/helpdesk-process-model` and deployed with `scripts/release_server_to_remote.py --gate quick --skip-ci-check --leave-running --smoke-insecure-tls`.
  * Remote smoke verified `https://192.168.100.17:9443/api/health -> 200`.
  * Browser route loaded: `https://192.168.100.17:9443/app/admin/knowledge/import`.
  * Live form evidence verified the `docx upload`, `pdf upload`, `external URL` and `Git repository` source modes, the visible URL source field, the fail-closed remote import policy message, the auto-segmentation checkbox and the active segmentation profile selector.
  * Browser screenshot captured as `knowledge-import-ui-controls-2c2b651b.png`.

Phase 10 remaining work:

Phase 10 import job detail and Observer events slice, 2026-06-12:

* Added ACL-filtered import job read APIs:

  * `GET /api/web/knowledge/import/jobs`;
  * `GET /api/web/knowledge/import/jobs/{job_id}`;
  * compatibility `GET /api/web/knowledge/ingestion/jobs/{job_id}`.

* Job detail returns safe ingestion job metadata, created item/version ids, stats, metadata and the visible knowledge space summary without import body content.
* Import preview/create/failure paths now emit redacted Observer-visible `agent_runtime_audit` rows with source `knowledge_import`:

  * `knowledge.import.preview_created`;
  * `knowledge.import.drafts_created`;
  * `knowledge.import.failed`;
  * `knowledge.import.ai_enrichment_blocked`;
  * `knowledge.import.ai_enrichment_failed`.

* Updated typed webapp import job helpers and docs/CODEMAP/navigation catalog.

* TDD status:

  * RED `python -m pytest server/tests/test_knowledge_import_api.py -q --tb=short` failed with `404` for `/api/web/knowledge/import/jobs` and empty `knowledge_import` audit feed.
  * GREEN `python -m pytest server/tests/test_knowledge_import_api.py -q --tb=short` -> 12 passed.
  * `pnpm --dir webapp test -- src/features/knowledge/api.test.ts` -> 1 file, 21 tests passed.
  * `python -m compileall -q server\knowledge\ingestion_service.py server\web_api\knowledge_handlers.py server\routes.py server\tests\test_knowledge_import_api.py scripts\navigation_catalog.py` -> passed.
  * `pnpm --dir webapp build` -> passed.
  * `python scripts/docs_inventory.py --check-links` -> passed.
  * `python scripts/verify_workspace.py` -> passed.

* Remote/live validation:

  * Commit `21fc7d9d` was pushed to `origin/codex/helpdesk-process-model` and deployed with `scripts/release_server_to_remote.py --gate quick --skip-ci-check --leave-running --smoke-insecure-tls`.
  * Remote smoke verified `https://192.168.100.17:9443/api/health -> 200`.
  * Browser same-origin API checks against deployed server verified:

    * `POST /api/web/knowledge/import/preview` -> `200`, AI preview status `blocked_pending_policy`;
    * `POST /api/web/knowledge/import/create-drafts` -> `200`, job `171fdb01-8037-4394-995d-06388dd75c6f`;
    * `GET /api/web/knowledge/import/jobs/{job_id}` -> `200`, status `review_required`, space `it-support`, response did not include import body text;
    * `GET /api/web/knowledge/import/jobs` -> `200` and included the created job;
    * blocked URL preview -> `400 remote_import_blocked` without leaking `secret-token`, `password=hidden` or `outside.example.test`.

  * Browser same-origin audit checks via `/api/web/admin/tech/agents/audit?event_type=...` verified deployed `knowledge_import` rows for `knowledge.import.preview_created`, `knowledge.import.ai_enrichment_blocked`, `knowledge.import.drafts_created` and `knowledge.import.failed`; audit details did not leak import body text or secret-bearing URL fragments.

Phase 10 remaining work:

* None for the import job detail / Observer events scope. Continue with Phase 11.

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

Phase 11 first slice, 2026-06-12:

* Replaced `/app/knowledge` support surface with a dedicated `KnowledgeSupportWorkspacePage` instead of reusing `KnowledgeAdminPanel mode="support"`.
* Added support article route `/app/knowledge/articles/:itemId` through the existing support workspace gate.
* First slice uses existing knowledge item/version APIs only; no backend contract changes yet.
* Implemented support-facing UX:

  * fast local search over title, slug, summary, type and visibility;
  * filters for requester-safe, support internal, article, runbook, known error and workaround;
  * selected article/runbook detail card with current version body;
  * requester-safe copy action guarded by visibility;
  * disabled placeholders for link-to-ticket and weak-article reporting until ticket context/backend endpoints are added.

* TDD status:

  * RED `webapp/src/features/knowledge/support-workspace-page.test.tsx` failed on missing component before implementation.
  * GREEN focused test now covers support search, runbook filtering, detail route and requester-safe copy guard.

* Local verification:

  * `pnpm --dir webapp test -- src/features/knowledge/support-workspace-page.test.tsx src/app/navigation.test.ts` passed, 11 tests.
  * `pnpm --dir webapp build` passed.
  * `python scripts/verify_workspace.py` passed.
  * `git diff --check -- PLANS.md docs/QUICK_LOOKUP.md server/docs/KNOWLEDGE_PLATFORM.md server/docs/CODEMAP.md scripts/navigation_catalog.py webapp/src/features/knowledge/support-workspace-page.tsx webapp/src/features/knowledge/support-workspace-page.test.tsx webapp/src/pages/knowledge/index.tsx webapp/src/app/router.tsx` passed with CRLF warnings only.

* Remote/live validation, 2026-06-12:

  * Deployed commit `9eb1f838` with `python scripts/release_server_to_remote.py --branch codex/helpdesk-process-model --allow-local-dirty --gate quick --skip-ci-check --leave-running --smoke-insecure-tls`; health smoke returned 200.
  * Playwright checked `https://192.168.100.17:9443/app/knowledge` and `/app/knowledge/articles/7041042b-3a27-45ee-b142-006c7b17a7ea`.
  * Verified support heading, search placeholder, type/visibility filters, deep-link article detail, and `support_internal` copy-safe guard.
  * `adminTitleCount=0`; the support workspace no longer shows the admin knowledge title.
  * Console warnings/errors, failed requests and HTTP errors were empty.
  * Evidence: `artifacts/browser_live_validation/knowledge-support-9eb1f838-1781239434437/report.json` and `artifacts/browser_live_validation/knowledge-support-9eb1f838-1781239434437/knowledge-support-live.png`.

Phase 11 support ticket actions slice, 2026-06-12:

* `/app/knowledge` and `/app/knowledge/articles/:itemId` now preserve optional `ticket_id` query context and show a ticket context banner when present.
* The selected support article card now enables:

  * `Link to ticket` through web-session alias `POST /api/web/support/tickets/{ticket_id}/kb_links`, backed by the existing compatibility KB link handler, with `source=knowledge_support_workspace`;
  * `Mark support used` through existing `POST /api/knowledge/feedback` with `event_type=support_used` and `surface=support_workspace`;
  * `Report weak article` through existing `POST /api/knowledge/feedback` with `event_type=not_helpful`, `result=weak_article_reported` and `surface=support_workspace`.

* Backend Observer-visible audit rows are emitted without new tables:

  * `knowledge.support.ticket_linked` from `server/tickets/handlers.py`;
  * `knowledge.support.article_used` from `server/web_api/knowledge_handlers.py`;
  * `knowledge.support.weak_article_reported` from `server/web_api/knowledge_handlers.py`.

* Safety contract: audit details include only article/item/version/ticket/link ids and safe action metadata; test metadata containing `secret-token` or `password=hidden` is not persisted into runtime audit details.
* TDD status:

  * RED backend tests failed before implementation because ticket link/support feedback did not emit Observer rows.
  * GREEN backend tests: `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_ticket_knowledge_links_compat.py server/tests/test_knowledge_feedback.py -q --tb=short` passed with 6 tests.
  * GREEN frontend tests: `pnpm --dir webapp test -- src/features/knowledge/support-workspace-page.test.tsx src/features/knowledge/api.test.ts` passed with 2 files / 24 tests.
* Remote/live validation, 2026-06-12:

  * First deployed commit `9a49a849` with quick release flow; smoke `/api/health` returned 200, and browser validation caught a real cookie-auth mismatch: direct browser `POST /api/tickets/{ticket_id}/kb_links` returned 401.
  * Follow-up commit `8f81c251` added web-session alias `POST /api/web/support/tickets/{ticket_id}/kb_links`; quick release flow deployed it and smoke `/api/health` returned 200 on attempt 2.
  * Browser route validated: `https://192.168.100.17:9443/app/knowledge/articles/a3c566b0-7d36-4879-831d-a38a5e9e86bf?ticket_id=9ec63696-5109-409f-9452-5dd403970100`.
  * Same-origin browser POSTs returned 200 for link-to-ticket, `support_used` and `weak_article_reported`.
  * Live audit confirmed events `knowledge.support.ticket_linked`, `knowledge.support.article_used` and `knowledge.support.weak_article_reported` with source `knowledge_support`; unsafe probe strings `secret-token` and `password=hidden` were absent from audit output.
  * Evidence screenshot: `knowledge-support-ticket-actions-8f81c251.png`.

Phase 11 requester attempts / passport draft slice, 2026-06-12:

* `GET /api/web/support/tickets/{ticket_id}/knowledge-suggestions` now includes safe `requester_attempts` from ticket `knowledge_attempts` where `surface=requester_portal`.
* Safety contract: requester attempts expose only `item_id`, `version_id`, `result`, `surface` and `occurred_at`; arbitrary attempt metadata is not serialized into the support payload.
* `/app/knowledge` with `ticket_id` now loads the support ticket knowledge payload and shows:

  * requester self-service attempts;
  * ticket-scoped suggested articles;
  * `Создать черновик из паспорта` action through existing `POST /api/web/support/tickets/{ticket_id}/passport/knowledge-draft`;
  * link to the created draft when the backend returns `edit_url`.

* `/app/tickets` Knowledge tab now renders the same requester attempts from the shared support workspace mapper.
* No database migration or new table was added; the slice reuses existing sanitized `knowledge_attempts`, support knowledge suggestions and passport-to-draft service contracts.
* TDD status:

  * RED backend test failed with `KeyError: 'requester_attempts'` before DTO/serializer changes.
  * RED frontend tests failed on missing `fetchSupportTicketKnowledgeSuggestions()` helper, missing `/app/knowledge` requester-attempts UI and missing queue mapper field.
  * GREEN after implementation.

* Local verification:

  * `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_web_support_api.py::test_web_support_ticket_knowledge_suggestions_returns_sources_and_workspace_payload -q --tb=short` passed, 1 test.
  * `pnpm --dir webapp test -- src/features/knowledge/support-workspace-page.test.tsx src/features/knowledge/api.test.ts src/features/queues/support-workspace-mappers.test.ts` passed, 44 tests.
  * `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_web_support_api.py::test_web_support_ticket_knowledge_suggestions_returns_sources_and_workspace_payload server/tests/test_web_support_api.py::test_web_support_ticket_knowledge_suggestions_uses_catalog_search_without_manual_links server/tests/test_ticket_knowledge_links_compat.py server/tests/test_knowledge_feedback.py server/tests/test_knowledge_passport_draft.py -q --tb=short` passed, 9 tests.
  * `pnpm --dir webapp test -- src/features/knowledge/support-workspace-page.test.tsx src/features/knowledge/api.test.ts src/features/queues/api.test.ts src/features/queues/support-workspace-mappers.test.ts src/pages/tickets/list-page.test.tsx` passed, 88 tests.
  * `python -m compileall -q server shared scripts` passed.
  * `pnpm --dir webapp build` passed.
  * `python -m pytest scripts/test_navigation_catalog.py scripts/test_task_intake.py -q` passed, 21 tests.
  * `python scripts/docs_inventory.py --check-links` passed.
  * `python scripts/verify_workspace.py` passed after updating `scripts/navigation_catalog.py`.
  * `git diff --check` passed with CRLF warnings only on existing dirty/generated files.

* Remote/live validation, 2026-06-12:

  * Deployed commit `1eac39b9c8f7d0f91869e1a9087d6de1142b7670` with `python scripts/release_server_to_remote.py --branch codex/helpdesk-process-model --allow-local-dirty --gate quick --skip-ci-check --leave-running --smoke-insecure-tls`.
  * Quick release gate passed: `verify_workspace.py` passed, webapp bundle built, migrations ran to head, and remote `/api/health` returned 200 on smoke attempt 2.
  * Created live public validation ticket `T-000689` (`d0132bf4-5a22-4cec-ba85-68593d13e447`) through `/public_api/tickets/create` with two requester-portal `knowledge_attempts` for article `a3c566b0-7d36-4879-831d-a38a5e9e86bf`.
  * `GET /api/web/support/tickets/d0132bf4-5a22-4cec-ba85-68593d13e447/knowledge-suggestions` returned 200 with two safe `requester_attempts`; probe metadata fields/values were absent from the response.
  * Browser route `/app/knowledge?ticket_id=d0132bf4-5a22-4cec-ba85-68593d13e447` rendered `Self-service попытки` with `Просмотрена` and `Не помогла`; the `Создать черновик из паспорта` UI action returned `Черновик знания подготовлен: Draft from T-000689...` and showed `Открыть черновик`.
  * Browser route `/app/tickets/d0132bf4-5a22-4cec-ba85-68593d13e447` rendered the same attempts in the Knowledge tab through the shared mapper.
  * Browser route `/app/knowledge?ticket_id=9ec63696-5109-409f-9452-5dd403970100` confirmed ticket-scoped suggested article rendering for `Codex Phase 8 history 20260612072045`.
  * Evidence: `knowledge-support-requester-attempts-1eac39b9.png`, `knowledge-support-requester-attempts-ticket-tab-1eac39b9.png`, `knowledge-support-requester-attempts-console-1eac39b9.log`, `knowledge-support-requester-attempts-network-1eac39b9.log`, `knowledge-support-ticket-suggestions-console-1eac39b9.log`, `knowledge-support-ticket-suggestions-network-1eac39b9.log`.
  * Console evidence for the final `/app/tickets` and ticket-suggestions browser checks had `Errors: 0`; non-static network requests returned 200.
  * Remote `server` and `control` services were stopped after validation.

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

Phase 12 first slice, 2026-06-12:

* Added `KnowledgeOpsSummaryService` as the first backend aggregation point for `/app/admin/knowledge` Operations Center.
* Added authenticated `GET /api/web/knowledge/ops/summary` for admin/support/auditor roles.
* First summary payload covers:

  * coverage: spaces, published articles, requester-safe items, support runbooks, Service Catalog offerings without requester-safe KB;
  * quality: average score, low-quality count, stale review, missing owner/reviewer, unsafe requester-safe blockers;
  * search/RAG: zero-result searches, top redacted queries, fallback count, AI disabled count, vector/rerank usage, answer/no-answer/provider/citation failure counters;
  * indexing: queued/failed jobs, stale/disabled embeddings and vector/model status;
  * AI, graph, review and Observer-backed active knowledge degradations.

* Added `KnowledgeOpsDashboardPanel` above the existing `/app/admin/knowledge` governance controls.
* TDD status:

  * RED `server/tests/test_knowledge_ops_summary.py` failed on missing `knowledge.ops_summary_service`.
  * RED `webapp/src/features/knowledge/ops-dashboard-panel.test.tsx` failed on missing `./ops-dashboard-panel`.
  * GREEN focused tests now cover backend aggregation/API and frontend dashboard/degraded state rendering.

* Local verification:

  * `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_ops_summary.py -q --tb=short` passed, 2 tests.
  * `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_ops_summary.py server/tests/test_knowledge_api.py::test_knowledge_api_admin_crud_and_requester_safe_suggest -q --tb=short` passed, 3 tests.
  * `pnpm --dir webapp test -- src/features/knowledge/ops-dashboard-panel.test.tsx` passed, 1 test.
  * `pnpm --dir webapp test -- src/features/knowledge/ops-dashboard-panel.test.tsx src/features/knowledge/api.test.ts src/app/navigation.test.ts` passed, 28 tests.
  * `pnpm --dir webapp build` passed.

* Remote/live validation, 2026-06-12:

  * Deployed commit `dd0b4ddb` with `python scripts/release_server_to_remote.py --branch codex/helpdesk-process-model --allow-local-dirty --gate quick --skip-ci-check --leave-running --smoke-insecure-tls`; health smoke returned 200.
  * Playwright checked `GET /api/web/knowledge/ops/summary` and `https://192.168.100.17:9443/app/admin/knowledge`.
  * API returned `status=ok`, `summary.status=degraded`, `generated_at=2026-06-12T04:59:14.841795+00:00`.
  * Dashboard rendered `Knowledge Operations Center`, requester-safe coverage, zero-result searches, RAG no-answer, failed indexing jobs and Observer-backed degradation cards.
  * Console warnings/errors, failed requests and HTTP errors were empty.
  * Evidence: `artifacts/browser_live_validation/knowledge-ops-dd0b4ddb-1781240295274/report.json` and `artifacts/browser_live_validation/knowledge-ops-dd0b4ddb-1781240295274/knowledge-ops-live.png`.

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

Phase 13 first slice, 2026-06-12:

* Added lightweight `KnowledgeEvalRecorder` for repeatable search/RAG evaluation metrics:

  * `top_k_recall`;
  * `citation_precision`;
  * `no_answer_correctness`;
  * `acl_leakage_count`;
  * `fallback_count`;
  * `latency_ms`;
  * `provider_failure_count`.

* Added `server/tests/test_knowledge_rag_eval.py` with a controlled dataset covering:

  * requester-safe article;
  * support_internal runbook;
  * admin_internal article;
  * security_restricted article;
  * known_error;
  * workaround;
  * manual requester segment with keyword recall;
  * Service Catalog binding.

* First evaluation assertions cover:

  * manual segment keyword search finds the requester article;
  * requester search does not leak support/admin/security content;
  * support search does not leak admin/security content;
  * Ask returns `not_enough_evidence` when retrieval has no evidence;
  * requester citations are restricted to allowed requester-safe item ids.

* TDD status:

  * RED `server/tests/test_knowledge_rag_eval.py` failed on missing `knowledge.evaluation`.
  * GREEN after adding `KnowledgeEvalRecorder` and correcting fixtures for known-error lint and RAG effective mode.

* Local verification:

  * `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_rag_eval.py -q --tb=short` passed, 1 test.
  * `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_rag_eval.py server/tests/test_knowledge_ask.py::test_knowledge_ask_ai_disabled_returns_search_fallback server/tests/test_knowledge_search.py::test_knowledge_search_filters_visibility_and_boosts_offering_binding -q --tb=short` passed, 3 tests.
  * `python scripts/verify_workspace.py` passed.
  * `git diff --check -- PLANS.md docs/QUICK_LOOKUP.md server/docs/CODEMAP.md server/docs/KNOWLEDGE_PLATFORM.md scripts/navigation_catalog.py server/knowledge/evaluation.py server/tests/test_knowledge_rag_eval.py` passed with CRLF conversion warnings only.

* Documentation/navigation:

  * Added Phase 13 routing notes to `docs/QUICK_LOOKUP.md`.
  * Added evaluation harness notes to `server/docs/KNOWLEDGE_PLATFORM.md`.
  * Added CODEMAP/navigation entries for `server/knowledge/evaluation.py` and `server/tests/test_knowledge_rag_eval.py`.

Phase 13 second slice, 2026-06-12:

* Extended `KnowledgeEvalRecorder` with `record_answer_status_case()` so provider-unavailable Ask/RAG statuses increment `fallback_count` and `provider_failure_count`.
* Extended the controlled eval suite to cover additional Phase 13 safety/usefulness cases:

  * body-only full-text recall;
  * JSONB-vector semantic recall when `vector_enabled=true`;
  * vector-disabled keyword fallback;
  * mocked OpenRouter-compatible rerank ordering;
  * archived item exclusion;
  * old-version exclusion with current-version recall.

* TDD status:

  * RED `server/tests/test_knowledge_rag_eval.py` failed on missing `KnowledgeEvalRecorder.record_answer_status_case()`.
  * GREEN after adding the recorder method, 2 eval tests passed.

* Local verification:

  * `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_rag_eval.py -q --tb=short` passed, 2 tests.
  * `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_rag_eval.py server/tests/test_knowledge_hybrid_retrieval.py::test_retrieval_rerank_reorders_candidates_with_mocked_openrouter server/tests/test_knowledge_vector_search.py::test_vector_search_merges_jsonb_embeddings_without_raw_vector server/tests/test_knowledge_ask.py::test_knowledge_ask_ai_disabled_returns_search_fallback server/tests/test_knowledge_search.py::test_knowledge_search_filters_visibility_and_boosts_offering_binding -q --tb=short` passed, 6 tests.
  * `python scripts/verify_workspace.py` passed.

Final Phase 13 verification, 2026-06-12:

* Focused backend Knowledge vNext gates were run sequentially because `PC_CLIENT_ALLOW_SHARED_TEST_DB=1` uses a destructive shared cleanup path. A parallel attempt was invalid and failed with shared-test-DB connection/cleanup contention, not with assertion regressions.
* Sequential backend results:

  * `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_ai_provider_settings.py server/tests/test_ai_openrouter_client.py server/tests/test_knowledge_ai_api.py server/tests/test_knowledge_search_settings.py -q --tb=short` passed, 15 tests.
  * `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_segments.py server/tests/test_knowledge_search_segments.py server/tests/test_knowledge_embeddings.py server/tests/test_knowledge_vector_search.py -q --tb=short` passed, 19 tests, with existing aiohttp app-state/config warnings in the embedding transport test.
  * `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_hybrid_retrieval.py server/tests/test_knowledge_ask.py server/tests/test_knowledge_portal.py server/tests/test_knowledge_import_api.py server/tests/test_knowledge_ops_summary.py server/tests/test_knowledge_rag_eval.py -q --tb=short` passed, 22 tests.

* General verification:

  * `pnpm --dir webapp test` passed, 89 files / 406 tests.
  * `pnpm --dir webapp build` passed.
  * `python -m compileall -q server shared scripts` passed.
  * `python scripts/docs_inventory.py --check-links` passed.
  * `python scripts/verify_workspace.py` passed.
  * `git diff --check; git diff --cached --check` passed with CRLF warnings only on pre-existing unrelated dirty files.

* Remote validation:

  * `python scripts/release_server_to_remote.py --branch codex/helpdesk-process-model --allow-local-dirty --gate quick --skip-ci-check --leave-running --smoke-insecure-tls` completed for commit `2937960e`; `/api/health` returned 200 on smoke attempt 2.
  * `python scripts/manage_remote_stack.py --remote altserver@192.168.100.17 stop server` stopped the server.
  * `python scripts/manage_remote_stack.py --remote altserver@192.168.100.17 stop control` stopped the control service.

* Browser/live note:

  * Phase 13 changes are backend test/evaluation harness and documentation only, with no new UI route or runtime API contract. Full browser workflow evidence from Phases 10-12 remains the current product evidence; no additional browser screenshots were captured for this test-only slice.

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

## Phase 14 - Knowledge taxonomy, properties, applicability and quality model

Status: implemented and live validated on commit `9941a454`, 2026-06-12; Phase 14 follow-up hardening active on 2026-06-13.

Scope:

* Add first-class taxonomy terms for Knowledge spaces so categories, products, audiences, topics and tags are governed data instead of only free-form `tags`.
* Add configurable property definitions and per-item property values, with validation by value type and item type applicability.
* Add explicit applicability rules for items, separate from existing search `knowledge_bindings`, so operators can state include/exclude scope for services, offerings, request templates, roles, device OS/family and custom scopes.
* Add a persisted quality model per space with weights and thresholds. The existing quality summary must expose the active model and apply metadata-driven scoring without breaking previous clients.
* Expose protected admin/support/auditor APIs for reading the model; only admin/support may mutate taxonomy, item metadata and applicability.
* Add admin Knowledge Ops UI evidence for taxonomy/properties/applicability/model status.
* Preserve requester/public projection safety: requester KB, public `/app/help`, Ask fallback and requester ticket creation must not receive admin-only taxonomy diagnostics or raw quality internals.

Implementation checkpoints:

* RED backend tests for taxonomy CRUD, property value validation, applicability include/exclude, quality model application and requester ACL projection.
* Migration adds additive tables only; no destructive schema changes.
* Backend service/API returns a single metadata bundle suitable for UI and live validation.
* Frontend API/types and `/app/admin/knowledge` panel render taxonomy, property definitions, applicability rules and model weights.
* Docs/CODEMAP/QUICK_LOOKUP explain the new model and audit boundaries.
* Local verification and live browser evidence after deploy.

Exit criteria:

* `GET /api/web/knowledge/metadata` returns spaces, taxonomy terms, property definitions, applicability rules, quality models and item metadata summary for admin/support/auditor.
* `POST /api/web/knowledge/taxonomy`, `POST /api/web/knowledge/properties`, `PUT /api/web/knowledge/items/{item_id}/metadata`, `POST /api/web/knowledge/items/{item_id}/applicability` and `POST /api/web/knowledge/quality-models` validate inputs and forbid unauthorized mutation.
* Quality summary includes `quality_model` and uses property/applicability requirements in scoring.
* `/app/admin/knowledge` shows the Russian-first metadata model card, active taxonomy/property/applicability counts and quality weights after deploy.
* Requester/public Knowledge paths remain backward-compatible and do not expose admin metadata diagnostics.

Implementation results, 2026-06-12:

* Added additive migration `118` and ORM models for `knowledge_taxonomy_terms`, `knowledge_property_definitions`, `knowledge_item_properties`, `knowledge_item_taxonomy_terms`, `knowledge_applicability_rules` and `knowledge_quality_models`.
* Added `KnowledgeMetadataService` and protected web APIs for metadata bundle reads, taxonomy/property upsert, item metadata update, applicability replacement and quality model upsert.
* Mutation is role and visibility constrained: requester cannot mutate, auditor is read-only, support cannot mutate `admin_internal` or other non-support-visible Knowledge spaces, and global quality models are admin-only.
* Extended quality scoring so an active persisted quality model can add weighted `properties`, `taxonomy` and `applicability` dimensions while preserving the built-in fallback model.
* Extended `/app/admin/knowledge` Knowledge Ops panel with the "Knowledge metadata model" card, counts and active model weights.
* Updated Knowledge docs, CODEMAP, `docs/QUICK_LOOKUP.md`, `docs/ARCHITECTURE_BOUNDARIES.md` and `scripts/navigation_catalog.py`.

Local verification, 2026-06-12:

* `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_metadata_model.py -q --tb=short` passed with 2 tests.
* `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_metadata_model.py server/tests/test_requester_workspace_api.py server/tests/test_knowledge_feedback.py server/tests/test_knowledge_ask.py server/tests/test_ticket_knowledge_links_compat.py server/tests/test_knowledge_rag_eval.py -q --tb=short` passed with 31 tests.
* `pnpm --dir webapp test -- src/features/knowledge/api.test.ts src/features/knowledge/ops-dashboard-panel.test.tsx` passed with 2 files / 24 tests.
* `pnpm --dir webapp test -- src/pages/kb/ask-page.test.tsx src/pages/requester/index.test.tsx src/features/requester/api.test.ts src/features/knowledge/api.test.ts src/features/knowledge/ops-dashboard-panel.test.tsx src/app/navigation.test.ts` passed with 6 files / 61 tests.
* `python -m compileall -q server shared scripts`, `python scripts/docs_inventory.py --check-links`, `pnpm --dir webapp build`, `python scripts/verify_workspace.py` and targeted `git diff --check` passed.

Remote/live verification, 2026-06-12:

* `python scripts/release_server_to_remote.py --branch codex/helpdesk-process-model --allow-local-dirty --gate quick --skip-ci-check --leave-running --smoke-insecure-tls` deployed commit `9941a454`, applied migration `117 -> 118`, started control/server and passed remote `/api/health` smoke with HTTP 200 on attempt 2.
* Browser MCP opened `https://192.168.100.17:9443/app/admin/knowledge` as admin and confirmed the deployed page renders `Knowledge metadata model`, `Taxonomy terms`, `Properties`, `Applicability rules`, `Item metadata` and active quality model `builtin-default`.
* Evidence artifacts are local/untracked and must be preserved outside git if needed for audit: `artifacts/browser_live_validation/phase14-knowledge-metadata-9941a454/report.json`, `snapshot.md` and `01-admin-knowledge-metadata-model.png`.
* Direct shell API probe with `test-ui-admin-token` returned 401 on the live stand; this is expected because live does not accept test bearer tokens. The browser evidence uses the authenticated admin session and rendered metadata payload.
* Evidence text scan found no `sk-or-`, `sk-proj-`, `BEGIN PRIVATE KEY`, `secret-token` or `password=hidden` markers.

Phase 14 follow-up hardening plan, 2026-06-13:

* Replace English Knowledge metadata model card labels and metadata API fallback errors with Russian-first text, and add webapp tests that assert the metadata panel is mojibake-free.
* Harden taxonomy term mutation so support can mutate only requested term visibilities allowed for support, not merely terms inside a support-visible space.
* Add DB-enforced quality model uniqueness with partial indexes for global model code, active default global model and active default model per space.
* Keep `/api/web/knowledge/metadata` as a full visible metadata bundle for admin/support/auditor management, and add `summary` total/active counts. Knowledge Ops dashboard must use active counts for model coverage so draft/archived taxonomy terms and property definitions are not counted as active coverage.
* Add local and live mutation evidence: create taxonomy/property/applicability/quality model through protected admin UI/API, verify `/app/admin/knowledge` updates, and verify requester/public Knowledge projections still hide admin metadata diagnostics.

Phase 14 follow-up hardening exit criteria:

* Phase 14 remains live-rendered.
* Metadata mutation rules are role-safe for requested taxonomy term visibility.
* Quality model uniqueness is DB-enforced.
* Ops counts are semantically correct and active-only.
* Visible metadata card text is Russian-first and mojibake-free.
* Requester/public Knowledge projections remain safe.

Phase 14 follow-up implementation results, 2026-06-13:

* Hardened `KnowledgeMetadataService.upsert_taxonomy_term()` so requested taxonomy term `visibility` is checked against the actor role in addition to the parent space visibility.
* Added migration `119` and ORM indexes for DB-enforced global quality model code uniqueness, one active default global model and one active default model per space. The migration normalizes any pre-existing duplicate global codes/defaults before creating indexes.
* Extended `GET /api/web/knowledge/metadata` with `summary` total/active counts while keeping the full visible management bundle for admin/support/auditor workflows.
* Updated `/app/admin/knowledge` metadata model card to Russian-first labels and active coverage counts; draft/archived taxonomy terms and properties no longer count as active model coverage.
* Updated Knowledge metadata API fallback errors to Russian-first strings.
* Updated docs, CODEMAP, quick lookup and navigation catalog for migration `119`, active summary counts and requested taxonomy visibility ACL.

Phase 14 follow-up local verification, 2026-06-13:

* RED checks failed before implementation for support admin-internal taxonomy mutation, support visibility escalation, missing metadata `summary`, duplicate global quality model code/defaults and English metadata UI/API text.
* `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_metadata_model.py -q --tb=short` passed with 9 tests.
* `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_metadata_model.py server/tests/test_knowledge_api.py::test_knowledge_api_admin_crud_and_requester_safe_suggest server/tests/test_knowledge_acl_hardening.py::test_web_acl_denies_support_restricted_mutation_and_auditor_publish server/tests/test_knowledge_rag_eval.py -q --tb=short` passed with 13 tests.
* `pnpm --dir webapp test -- src/features/knowledge/api.test.ts src/features/knowledge/ops-dashboard-panel.test.tsx` passed with 2 files / 25 tests.
* `pnpm --dir webapp test -- src/features/knowledge/api.test.ts src/features/knowledge/ops-dashboard-panel.test.tsx src/pages/kb/search-page.test.tsx src/app/navigation.test.ts` passed with 4 files / 36 tests.
* `python -m compileall -q server shared scripts`, `python scripts/docs_inventory.py --check-links`, `pnpm --dir webapp build`, `python scripts/verify_workspace.py` and targeted `git diff --check` passed.

Phase 14 follow-up remote/live verification, 2026-06-13:

* `python scripts/release_server_to_remote.py --branch codex/helpdesk-process-model --allow-local-dirty --gate quick --skip-ci-check --leave-running --smoke-insecure-tls` deployed commit `1214efcf`, applied migration `118 -> 119`, started control/server and passed remote `/api/health` smoke with HTTP 200 on attempt 2.
* Live API scenario authenticated as admin through web session, created Knowledge space `phase14-hardening-12201341`, item `phase14-hardening-item-12201341`, taxonomy term `phase14-term-12201341`, property `phase14-property-12201341`, one applicability rule and active default quality model `phase14-quality-12201341`.
* Live `GET /api/web/knowledge/metadata` verified the created taxonomy/property/item metadata/quality model are present and active `summary` counts incremented: taxonomy `0 -> 1`, properties `0 -> 1`, applicability `0 -> 1`, quality models `0 -> 1`, item metadata `38 -> 39`.
* Live public-compatible `POST /api/knowledge/search` with `surface=requester_portal` returned only safe top-level keys: `ai_used`, `display_message`, `effective_mode`, `results`, `search_mode`, `status`; recursive scan found no metadata bundle, quality model, weights, thresholds, applicability rules, property values, taxonomy terms, score parts or diagnostics.
* Browser MCP opened `https://192.168.100.17:9443/app/admin/knowledge?phase14=1214efcf` after deploy and confirmed the loaded card renders `Модель метаданных знаний`, `Термины таксономии`, `Свойства`, `Правила применимости`, `Метаданные статей`, `Активная модель качества:` and active model `phase14-quality-12201341`; scan found no old English metadata labels or mojibake patterns in the card snapshot.
* Browser MCP opened `https://192.168.100.17:9443/app/kb/search?phase14=1214efcf` and confirmed the requester Knowledge search route renders without admin metadata/model diagnostics.
* Evidence artifacts are local/untracked and must be preserved outside git if needed for audit: `artifacts/browser_live_validation/phase14-hardening-1214efcf-20260612201341/report.json`, `admin-knowledge-loaded-snapshot.md`, `admin-knowledge-loaded.png`, `kb-search-loaded-snapshot.md` and `kb-search-loaded.png`.
* Evidence text scan found no `password`, `secret`, `cookie`, `Authorization`, `sk-`, `BEGIN PRIVATE KEY` or `pc_client_web_session` markers.

Phase 14 follow-up hardening addendum, 2026-06-13:

Status: implemented and live validated on runtime commit `736972c6`, 2026-06-13. The item metadata visibility ACL and Knowledge Ops Russian-first addendum are closed; final Knowledge vNext product signoff still keeps the top-level real-key OpenRouter and dedicated semantic retrieval browser/live gates open.

Required fixes:

* Item metadata taxonomy ACL: `GET|PUT /api/web/knowledge/items/{item_id_or_slug}/metadata` must treat assigned taxonomy term visibility as part of the metadata contract. Read responses must hide assigned terms the actor cannot read, and metadata updates must reject terms whose visibility the actor cannot mutate even when the item and parent space are otherwise visible.
* Knowledge Ops Russian-first text: `/app/admin/knowledge` must replace remaining visible English Ops dashboard labels such as `Knowledge Operations Center`, `Search and RAG`, `Coverage and Review`, `AI, Indexing and Graph` and `Observer-backed degradation` with Russian-first labels, with regression tests for representative English-label absence and mojibake-free rendering.
* Verification must include backend regression tests for admin-assigned `admin_internal` taxonomy on requester/support-visible items, support/auditor read filtering, support assignment denial, admin assignment/read success, frontend label tests, local checks, deploy and live browser/API evidence.

Phase 14 follow-up addendum implementation results, 2026-06-13:

* Added item metadata ACL filtering in `KnowledgeMetadataService.item_metadata()`: assigned taxonomy terms are returned only when the actor can read the term visibility.
* Added item metadata assignment ACL in `KnowledgeMetadataService.update_item_metadata()`: support can no longer attach `admin_internal` or otherwise hidden taxonomy terms to a visible item by id, while admin/security can.
* Added backend regressions for admin-assigned `admin_internal` taxonomy on a requester-visible item, support/auditor read filtering, support assignment denial and admin assignment/read success.
* Replaced remaining visible English labels in `KnowledgeOpsDashboardPanel` with Russian-first dashboard text, including the dashboard heading, status badge, summary cards, section headings and Observer degradation card.
* Added webapp regression expectations for Russian Ops labels, old English label absence and mojibake-free rendered panel text.
* Updated Knowledge Platform docs, CODEMAP, quick lookup, architecture boundaries and navigation aliases for item metadata term-visibility ACL.

Phase 14 follow-up addendum local verification, 2026-06-13:

* RED: `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_metadata_model.py -q --tb=short` failed before implementation on taxonomy term leakage to support item metadata and support assignment of an `admin_internal` term.
* RED: `pnpm --dir webapp test -- src/features/knowledge/ops-dashboard-panel.test.tsx` failed before implementation because `/app/admin/knowledge` still rendered `Knowledge Operations Center` / `Degraded` and old English Ops labels.
* GREEN: `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_metadata_model.py -q --tb=short` passed with 11 tests.
* GREEN: `pnpm --dir webapp test -- src/features/knowledge/ops-dashboard-panel.test.tsx` passed with 1 test.
* `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_metadata_model.py server/tests/test_knowledge_api.py::test_knowledge_api_admin_crud_and_requester_safe_suggest server/tests/test_knowledge_acl_hardening.py::test_web_acl_denies_support_restricted_mutation_and_auditor_publish server/tests/test_knowledge_rag_eval.py -q --tb=short` passed with 15 tests.
* `pnpm --dir webapp test -- src/features/knowledge/api.test.ts src/features/knowledge/ops-dashboard-panel.test.tsx src/pages/kb/search-page.test.tsx src/app/navigation.test.ts` passed with 4 files / 36 tests.
* `python -m compileall -q server shared scripts`, `python scripts/docs_inventory.py --check-links`, `pnpm --dir webapp build`, `python scripts/verify_workspace.py`, targeted `git diff --check` and UTF-8 replacement-character scan over changed files passed.

Phase 14 follow-up addendum remote/live verification, 2026-06-13:

* `python scripts/release_server_to_remote.py --branch codex/helpdesk-process-model --allow-local-dirty --gate quick --skip-ci-check --leave-running --smoke-insecure-tls` deployed runtime commit `736972c6`, left services running for browser/API validation and passed remote `/api/health` smoke with HTTP 200 on attempt 2.
* Live API scenario authenticated through `POST /api/web/session/login`, created a temporary support user through the protected admin API using the web-session UI token as Bearer auth, then deactivated the user after validation.
* Live API scenario created Knowledge space `phase14-live-0df3499f`, item `phase14-live-0df3499f-article`, `admin_internal` taxonomy term `phase14-admin-term-0df3499f`, property `phase14-property-0df3499f`, one applicability rule and quality model `phase14-quality-0df3499f`.
* Admin successfully attached and read the `admin_internal` taxonomy term on a requester-visible item. Support live read filtered that term out of `GET /api/web/knowledge/items/{item_id}/metadata`, and support live assignment of the known hidden `term_id` was denied with HTTP 400.
* Live `GET /api/web/knowledge/metadata` verified the created taxonomy/property/applicability/quality model in the metadata bundle and reported active/total summary counts: taxonomy `2/2`, properties `2/2`, applicability `2/2`, quality models `2/2`, item metadata `40`.
* Live public-compatible `POST /api/knowledge/search` with `surface=requester_portal` recursively scanned response bodies and found no metadata bundle, quality model, weights, thresholds, applicability rules, property values, taxonomy terms, score parts or diagnostics.
* Browser evidence opened `https://192.168.100.17:9443/app/admin/knowledge?phase14=736972c6` and confirmed Russian-first labels `Центр операций базы знаний`, `Поиск и RAG`, `Покрытие и проверка`, `AI, индексация и граф`, `Деградации из Observer` and `Модель метаданных знаний`; old English labels were absent and mojibake scan was clean.
* Browser evidence opened `https://192.168.100.17:9443/app/kb/search?phase14=736972c6` and confirmed the requester Knowledge route rendered without admin metadata/model diagnostics and without mojibake.
* Evidence artifacts are local/untracked and must be preserved outside git if needed for audit: `artifacts/browser_live_validation/phase14-item-acl-736972c6-20260613-020442/phase14-live-evidence-summary.json`, `api-live-report.json`, `admin-knowledge-snapshot.md`, `admin-knowledge.png`, `kb-search-snapshot.md` and `kb-search.png`.
* Intermediate login snapshots were removed because the live login page displays local fixture credential hints. Secret scan over the final evidence directory found no known live credential, temporary support password or `pc_client_web_session` marker.
* Browser console evidence contained repeated existing `[webapp-realtime] websocket bridge reported an error` warnings from the shared realtime layer; no render failure, metadata projection leak or new Knowledge metadata diagnostics exposure was observed.

Phase 14B - Authoring Studio editor regression after metadata hardening, 2026-06-13:

Status: implemented and live validated on runtime commit `cf2f6af0`, 2026-06-13.

Scope:

* Re-validate `/app/admin/knowledge/studio` after Phase 14 metadata model and item-metadata ACL hardening.
* Keep editor API contracts unchanged while ensuring visible Authoring Studio copy is Russian-first and mojibake-free.
* Prove the editor still loads articles, creates drafts, inserts templates/structured Markdown blocks, creates versions, publishes/rolls back selected versions, writes review actions and renders persisted editor history/diff summaries.
* Live validation must create or mutate a disposable article through Studio/API, verify editor history and browser rendering, and confirm requester/public Knowledge projections still do not expose admin metadata diagnostics.

Implementation results:

* Replaced remaining English Authoring Studio visible labels with Russian-first text: heading eyebrow, item status/visibility badges, owner/reviewer labels, item type/visibility option labels, publish checklist copy, review comment/archive wording, requester-safe tag copy, editor-history diff cache copy and AI-disabled description.
* Live browser review found that embedded `ArticleSegmentationPanel` still exposed raw visibility/status/source labels; hardened that editor sub-panel with Russian-first visibility options, segment status/type/source badges, search weight/full-text/embedding copy and segment description text while preserving submitted enum values.
* Kept technical API values and event codes unchanged: `article`, `requester`, `submit_review`, `approve`, `archive`, `version_created` and editor-history payload contracts remain stable.
* Added webapp regression coverage for Russian Studio labels, Russian segment panel visibility/status/source labels, old English label absence and mojibake-free rendered panel text.

Local verification:

* RED: `pnpm --dir webapp test -- src/pages/admin/knowledge-studio-page.test.tsx` failed before implementation on missing Russian labels (`Владелец`, `Ревьюер`, `Назначен ревьюер`, `Комментарий ревью`) and old English Studio copy.
* GREEN: `pnpm --dir webapp test -- src/pages/admin/knowledge-studio-page.test.tsx` passed with 5 tests.
* RED: `pnpm --dir webapp test -- src/features/knowledge/article-segmentation-panel.test.tsx` failed before the follow-up fix because the embedded segment panel still rendered `requester`, `Boost`, `Full-text`, `Embeddings`, `active`, `manual`, `editor_selection` and `boost 2` as visible UI text.
* GREEN: `pnpm --dir webapp test -- src/features/knowledge/article-segmentation-panel.test.tsx` passed with 1 test.
* GREEN: `pnpm --dir webapp test -- src/pages/admin/knowledge-studio-page.test.tsx src/features/knowledge/article-segmentation-panel.test.tsx src/features/knowledge/api.test.ts src/app/navigation.test.ts` passed with 4 files / 40 tests.
* GREEN: `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_api.py::test_knowledge_authoring_studio_records_editor_history -q --tb=short` passed with 1 test.
* GREEN: `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_metadata_model.py server/tests/test_knowledge_api.py::test_knowledge_authoring_studio_records_editor_history -q --tb=short` passed with 12 tests.
* `python scripts/bootstrap_web_toolchain.py`, `pnpm --dir webapp build`, `python -m compileall -q server shared scripts`, `python scripts/docs_inventory.py --check-links`, `python scripts/verify_workspace.py`, targeted `git diff --check` and UTF-8 replacement-character scan over changed files passed.

Remote/live verification:

* `python scripts/release_server_to_remote.py --branch codex/helpdesk-process-model --allow-local-dirty --gate quick --skip-ci-check --leave-running --smoke-insecure-tls` deployed final runtime commit `cf2f6af0`, uploaded the rebuilt webapp bundle, left services running for validation and passed remote `/api/health` smoke with HTTP 200 on attempt 2.
* Live API scenario authenticated through web session with same-origin headers, created Knowledge space `phase14b-studio-final-20260613-033529-d95888`, item `phase14b-studio-final-article-20260613-033529-d95888`, immutable version `0902cb01-760c-404b-8415-9f1d24b09410` and manual segment `e3b8e258-3635-46bb-ad9d-f8962be54ae6`.
* Live API scenario published the created version, submitted review, added a comment, approved the article and verified `GET /api/web/knowledge/items/{item_id}/editor-history` returns `approved`, `commented`, `review_submitted`, `published`, `version_created`, `draft_created` plus diff cache `added_lines=4`.
* Live public-compatible `POST /api/knowledge/search` with `surface=requester_portal` returned only safe top-level keys: `ai_used`, `display_message`, `effective_mode`, `results`, `search_mode`, `status`; recursive scan found no metadata bundle, quality model, weights, thresholds, applicability rules, property values, taxonomy terms, score parts or diagnostics.
* Browser MCP opened `https://192.168.100.17:9443/app/admin/knowledge/studio?phase14b=cf2f6af0-033529`, filtered the final live article and verified Russian-first Studio/editor labels, segment panel labels, `Кэш различий`, `Вес поиска`, `Полнотекстовый поиск`, `Эмбеддинги`, `Активный`, `Ручной`, `Выделение редактора` and `вес 1.5`; old English labels such as `Knowledge Authoring`, `Requester-safe теги`, `Diff cache`, `Boost`, `Full-text`, `Embeddings`, `editor_selection` and mojibake markers were absent.
* Browser MCP checked `/app/admin/knowledge/studio` at 1366x768 and 1920x1080; both viewports had no horizontal overflow. Browser console warn/error logs for Studio were empty.
* Browser MCP opened `https://192.168.100.17:9443/app/kb/search?phase14b=cf2f6af0-033529`, searched for the final live slug and verified the requester route rendered a safe result/empty state without admin metadata/model diagnostics, mojibake or horizontal overflow. Browser console warn/error logs were empty.
* Evidence artifacts are local/untracked and must be preserved outside git if needed for audit: `artifacts/browser_live_validation/phase14b-studio-cf2f6af0-20260613-033529/api-live-report.json`, `created-item.safe.json`, `studio-1366-checks.json`, `studio-1366-snapshot.md`, `studio-1366.png`, `studio-1920-checks.json`, `studio-1920-snapshot.md`, `studio-1920.png`, `studio-console-warn-error.json`, `kb-search-1366-checks.json`, `kb-search-1366-snapshot.md`, `kb-search-1366.png` and `kb-search-console-warn-error.json`.
* Evidence text scan found no `password`, `secret`, `cookie`, `Authorization`, `pc_client_web_session`, `sk-` or `BEGIN PRIVATE KEY` markers.

Phase 14C - Knowledge metadata management editor, 2026-06-13:

Status: implemented and live validated on commit `ee6e31e1`, 2026-06-13; Phase 14C follow-up permission/UI hardening is active on 2026-06-13. Required follow-up after Phase 14 backend metadata foundation and Phase 14B Authoring Studio regression is closed; final Knowledge vNext product signoff still keeps the top-level real-key OpenRouter and dedicated semantic retrieval browser/live gates open.

Scope:

* Add `/app/admin/knowledge/metadata` as a first-class metadata workbench for admin and explicitly delegated knowledge-manager users, covering governed taxonomy terms, property definitions, applicability rules and quality models.
* Keep organization categories/properties as editable governed data. Frontend code must not hardcode business categories; default business taxonomy may exist only as optional seed content.
* Extend `/app/admin/knowledge/studio` with item-level metadata tabs: `Таксономия`, `Свойства`, `Применимость`, `Качество`.
* Add optional safe default metadata seed pack/script with Russian-first output, dry-run/apply modes and idempotent behavior without overriding admin changes unless `--force`.
* Preserve requester/public projection safety: requester KB, public-compatible search/Ask/article routes and requester navigation must not expose metadata management, admin/internal taxonomy, quality weights, applicability internals or support/security-only property values.

Implementation checkpoints:

* RED backend tests for editor API coverage, metadata ACL/read-only behavior, item metadata assignment, hidden taxonomy filtering, applicability replacement, quality model constraints and seed dry-run/apply idempotency.
* RED frontend tests for `/app/admin/knowledge/metadata`, item metadata tabs in Studio, Russian-first/mojibake-free labels and requester navigation hiding the admin metadata editor.
* Implement reusable frontend API helpers for item metadata reads plus the metadata editor workbench and Studio metadata panel over existing protected APIs.
* Add seed pack/script without making seeded categories immutable or hardcoded into UI.
* Update route/navigation docs, Knowledge docs, CODEMAP/quick lookup and this plan with local/live evidence.

Local implementation state:

* Added `/app/admin/knowledge/metadata` with Russian-first tabs for taxonomy, properties, applicability and quality models.
* Added Studio item metadata tabs for taxonomy assignment, property values, applicability rules and quality preview.
* Added `content_packs/knowledge/default_metadata.json` and `scripts/seed_knowledge_metadata.py`; seed defaults are editable governed data and remain idempotent unless `--force` is explicit.
* Added backend validation for required active property definitions during item metadata updates and reused Phase 14 ACL filtering for hidden taxonomy reads/assignments.
* Updated Knowledge docs, CODEMAP, quick lookup, architecture boundaries and navigation catalog for the new route and seed command.

Local verification:

* `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_metadata_model.py server/tests/test_knowledge_metadata_editor_api.py server/tests/test_knowledge_metadata_seed.py -q --tb=short` -> 17 passed.
* `pnpm --dir webapp test -- src/features/knowledge/api.test.ts src/features/knowledge/ops-dashboard-panel.test.tsx src/features/knowledge/metadata-page.test.tsx src/features/knowledge/article-metadata-panel.test.tsx src/pages/admin/knowledge-studio-page.test.tsx src/app/navigation.test.ts` -> 42 passed.
* `pnpm --dir webapp build` -> passed.
* `python -m compileall -q server shared scripts` -> passed.
* `python scripts/verify_workspace.py` -> passed.
* `python scripts/docs_inventory.py --check-links` -> passed.
* `python scripts/check_webapp_cutover.py --json` -> bundle ready, full switch ready.
* `git diff --check -- . ':(exclude)artifacts/**'` -> passed.
* `python scripts/seed_knowledge_metadata.py --help` -> Russian-first CLI help renders correctly. Direct local `--dry-run` needs a reachable database; DB-backed dry-run/apply remains part of deploy/live evidence.

Exit criteria:

* Admin and explicitly delegated knowledge-manager users can create/edit/archive taxonomy terms and property definitions, replace item applicability rules and create/update quality models without direct API calls.
* Support cannot create, assign or escalate `admin_internal`/`security_restricted` taxonomy terms; auditor can read the visible bundle but cannot mutate.
* Item metadata assignment validates required properties, allowed values and item type applicability, and filters hidden taxonomy terms in reads.
* Knowledge Ops active counts update after metadata mutations and still count only active taxonomy/property/model rows.
* `/app/admin/knowledge/metadata` and Studio metadata tabs are Russian-first, mojibake-free and browser-validated at 1366x768 and 1920x1080.
* Requester/public projections remain safe and backward-compatible after deploy.

Remote/live verification:

* `python scripts/release_server_to_remote.py --branch codex/helpdesk-process-model --allow-local-dirty --gate quick --skip-ci-check --leave-running --smoke-insecure-tls` deployed commit `ee6e31e1`; remote `/api/health` smoke returned HTTP 200.
* Live protected admin scenario created Knowledge space `phase14c-live-9ee748e7`, item `phase14c-live-9ee748e7-article`, taxonomy terms `phase14c-access-9ee748e7` / `phase14c-vpn-9ee748e7`, property `phase14c-audience-9ee748e7`, item metadata, one applicability rule and quality model `phase14c-quality-9ee748e7`.
* Playwright browser evidence verified `/app/admin/knowledge/metadata` at 1366x768 and 1920x1080, including the created taxonomy term; `/app/admin/knowledge/studio` rendered metadata tabs `Таксономия`, `Свойства`, `Применимость`, `Качество`; `/app/admin/knowledge` rendered the metadata/Ops card after mutation.
* Requester `/app/kb/search`, public-compatible `/api/knowledge/search` and support `/app/knowledge` kept safe projections. Public search returned only `ai_used`, `display_message`, `effective_mode`, `results`, `search_mode`, `status`; recursive scan found no forbidden metadata diagnostics.
* Browser run recorded `console_errors=0` and `page_errors=0`.
* Evidence artifacts are local/untracked and must be preserved outside git if needed for audit: `artifacts/knowledge-metadata-editor-live-20260612-234114/report.json`, `api/public-search.safe.json`, `screenshots/admin-knowledge-metadata-1366.png`, `admin-knowledge-metadata-1920.png`, `admin-knowledge-studio-metadata-tabs-1920.png`, `admin-knowledge-ops-after-metadata.png`, `requester-kb-search-safe.png` and `support-knowledge-safe.png`.
* Post-validation remote cleanup stopped both `server` and `control`; `python scripts/manage_remote_stack.py status server --json` and `status control --json` reported `display_state=stopped`, `active_state=inactive`, `sub_state=dead`.

Remaining Phase 14 work:

* Phase 14 metadata-model hardening is complete. Phase 14B editor regression and live validation are complete.
* Phase 14C metadata management editor is complete with local tests, deploy, live mutation evidence, browser evidence and requester/public projection checks.
* Final Knowledge vNext product signoff still keeps the top-level real-key OpenRouter and dedicated semantic retrieval browser/live gates open.

Phase 14C follow-up permission/UI hardening, 2026-06-13:

Status: implemented, deployed and live validated on commit `a1ec3053`, 2026-06-13. Support-without-permission live denial was attempted but could not be completed through a live support account because the deployed stand rejected the available canary support login/setup path; the same denial is covered by backend tests and the full local Knowledge CI layer.

Review findings:

* Backend metadata mutation was role-gated for admin/support while the editor route lived only in the admin workspace. The chosen model is explicit delegation: default support remains outside the editor, and support knowledge managers must receive both `workspace.admin.view` and `knowledge.metadata.manage` through access groups.
* The metadata editor still displayed raw enum values for taxonomy term type/status/visibility and property value type/status in visible lists.
* The item metadata panel rendered `multi_select` properties as `<select multiple>` while saving a string value, so multi-value saves were incomplete.
* This repository checkout has no `.github/workflows` directory and the Windows environment has no `gh` CLI, so GitHub Actions status cannot be produced for the current branch. Phase 14C verification uses project local CI/test/build/browser evidence instead of claiming a GitHub Actions gate.

Implementation results:

* Added high-risk permission `knowledge.metadata.manage`; admin receives it through catalog defaults, support does not receive it by default.
* Protected metadata write APIs now require `knowledge.metadata.manage` in addition to the existing authenticated role boundary. Reads remain available to admin/support/auditor according to the existing visibility model; auditor stays read-only.
* `/app/admin/knowledge/metadata` and the navigation item now require `knowledge.metadata.manage`; the route can be opened by a support knowledge-manager session only when the session also has admin workspace access.
* Localized taxonomy/property list badges and enum labels while keeping technical codes visible as secondary identifiers.
* Replaced item `multi_select` property editing with a newline/comma textarea path that feeds the existing structured value parser.
* Added backend and frontend regression tests for permission catalog defaults, support denial without manager permission, support knowledge-manager access, raw enum label hiding and multi-select save shape.

Verification:

* `pnpm --dir webapp test -- src/app/navigation.test.ts src/app/router.test.tsx src/features/knowledge/metadata-page.test.tsx src/features/knowledge/article-metadata-panel.test.tsx` -> 24 passed.
* `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_access_control.py::test_permission_catalog_has_stable_role_defaults server/tests/test_knowledge_metadata_editor_api.py -q --tb=short` -> 5 passed.
* `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_metadata_model.py -q --tb=short` -> 11 passed.
* `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_access_control.py server/tests/test_web_session_api.py server/tests/test_knowledge_metadata_model.py server/tests/test_knowledge_metadata_editor_api.py server/tests/test_knowledge_metadata_seed.py -q --tb=short` -> 44 passed, 18 existing aiohttp `NotAppKeyWarning` warnings.
* `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_api.py::test_knowledge_api_admin_crud_and_requester_safe_suggest server/tests/test_knowledge_acl_hardening.py::test_web_acl_denies_support_restricted_mutation_and_auditor_publish server/tests/test_knowledge_hybrid_retrieval.py server/tests/test_knowledge_ask.py -q --tb=short` -> 12 passed.
* `pnpm --dir webapp test -- src/features/knowledge/api.test.ts src/features/knowledge/ops-dashboard-panel.test.tsx src/features/knowledge/metadata-page.test.tsx src/features/knowledge/article-metadata-panel.test.tsx src/pages/admin/knowledge-studio-page.test.tsx src/app/navigation.test.ts src/app/router.test.tsx` -> 54 passed.
* `pnpm --dir webapp test -- src/pages/kb/search-page.test.tsx src/pages/kb/ask-page.test.tsx src/pages/requester/index.test.tsx src/features/knowledge/support-workspace-page.test.tsx` -> 17 passed.
* `pnpm --dir webapp build` -> passed.
* `python -m compileall -q server shared scripts` -> passed.
* `python scripts/verify_workspace.py` -> passed.
* `python scripts/docs_inventory.py --check-links` -> passed.
* `python scripts/check_webapp_cutover.py --json` -> bundle ready and full switch ready for active login/support/admin cutover flags.
* `git diff --check -- <Phase 14C hardening tracked files>` -> passed.
* `python scripts/run_ci_suite.py --layer server_pytest_db_knowledge --idle-timeout 0` -> 176 passed, 9 deselected, 2 existing warnings, returncode 0; artifact log is local/untracked under `artifacts/ci/42cd2a591afef323d97f261f1da514ec71e6ade4/logs/server_pytest_db_knowledge.log`.
* GitHub Actions status remains unavailable in this checkout: `.github/workflows` is absent and `gh` CLI is not installed. This follow-up uses the project local CI layer above as the CI evidence.

Remote/live verification:

* `python scripts/release_server_to_remote.py --branch codex/helpdesk-process-model --allow-local-dirty --gate quick --skip-ci-check --leave-running --smoke-insecure-tls` deployed commit `a1ec3053`; migrations ran and remote smoke returned `/api/health` HTTP 200 on retry 2.
* Browser opened `https://192.168.100.17:9443/app/admin/knowledge/metadata` as admin and confirmed the route/navigation item is visible under the new `knowledge.metadata.manage` gate.
* Live admin UI mutation created persisted taxonomy term `phase14c-hardening-a1ec3053-bn8a13` / `Phase 14C hardening persisted bn8a13`; after reload, the list rendered localized `Категория` and `Активно` labels, not raw `category`/`active`.
* Browser evidence captured `/app/admin/knowledge/metadata` at 1366x768 and 1920x1080 after data load: persisted term visible, no raw enum line, no mojibake marker, no horizontal overflow and console error count 0.
* Browser opened requester `/app/kb/search`; forbidden metadata diagnostics (`quality_model`, `taxonomy_terms`, `property_definitions`, `applicability_rules`, `admin_internal`, `security_restricted`, `score_parts`, `knowledge.metadata.manage`) and the created admin term were not visible, with console error count 0.
* Public-compatible `POST /api/knowledge/search` returned HTTP 200 with top-level keys `ai_used`, `display_message`, `effective_mode`, `results`, `search_mode`, `status`; recursive scan found no forbidden metadata diagnostics and did not expose the created admin term.
* Live support denial attempt: existing canary support login returned 401; legacy `/api/ui_login` returned 410 and web-session cookie bridge to legacy user-admin setup returned 401, so no live support account was created or mutated. Backend coverage remains `test_support_without_knowledge_manager_permission_cannot_mutate_metadata` plus the full `server_pytest_db_knowledge` layer.
* Evidence artifacts are local/untracked and must be preserved outside git if needed for audit: `artifacts/knowledge-metadata-hardening-live-20260613-a1ec3053/report.json`, `admin-knowledge-metadata-hardening-loaded-1366.png`, `admin-knowledge-metadata-hardening-loaded-1920.png`, `requester-kb-search-hardening-safe.png`, `public-knowledge-search-safe.json`, `support-without-metadata-manage-denied.safe.json`, and console error JSON files.
* Post-validation cleanup stopped both remote services: `server` and `control` reported `display_state=stopped`, `active_state=inactive`, `sub_state=dead`.

---

## Knowledge admin UI refactor design decision, 2026-06-13

Status: design spec recorded; implementation pending.

Design spec:

* `docs/superpowers/specs/2026-06-13-knowledge-admin-ui-refactor-design.md`

Decision:

* Refactor `/app/admin/knowledge` into a Knowledge Operations Center, not an editor or CRUD form.
* Refactor `/app/admin/knowledge/studio` into a real Authoring Workbench with one primary editor for article text, metadata support, manual markup, AI markup, auto segmentation, visual highlights, diff, validation and publication flow.
* Refactor `/app/admin/knowledge/graph` into a real Graph Workbench with a canvas-first graph editor, editable nodes/edges, searchable pickers, inspector, saved layout and proof that mutations update the visible graph.
* Use `TipTap` / `ProseMirror` for Studio. A textarea-based implementation is not acceptable for the final editor because the product requires robust selections, inline decorations, markup states, diff/validation marks and inspector-driven editing.
* Use React Flow (`@xyflow/react`) for Graph. A hand-rolled SVG/list implementation is not acceptable for the final graph editor because the product requires real canvas interactions, node/edge selection, connection editing, drag layout and visible mutation feedback.
* Keep `/app/admin/knowledge/import`, `/search-settings`, `/ai` and `/indexing` aligned with the Wizard, Settings and Ops Console archetypes from `webapp/AGENTS.md`.

Implementation notes:

* Add the dependencies deliberately in the implementation phase and document the bundle impact.
* Isolate TipTap/ProseMirror and React Flow behind Knowledge feature components rather than leaking their APIs into shared app primitives.
* Preserve existing backend contracts where practical; if an API gap blocks usable pickers or graph/editor state, add the smallest contract extension with tests and docs.
* Update browser evidence for all seven target routes at 1366x768 and 1920x1080.

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

Final verification run, 2026-06-12:

This run is the local and route-level deployed verification for the implemented slices. It does not close final Knowledge vNext product signoff: real-key OpenRouter answer signoff and dedicated semantic retrieval browser/live evidence remain open gates. Full Ask -> requester ticket submit -> `ticket_created_after_view` analytics was closed by the later Phase 6E correction run above.

* Local backend and contract checks:

  * `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_requester_workspace_api.py server/tests/test_requester_timeline_projection.py server/tests/test_user_consent_api.py server/tests/test_operation_retry.py server/tests/test_web_session_api.py server/tests/test_registration_api.py server/tests/test_tools_async_response_contract.py -q --tb=short` passed, 99 tests with existing aiohttp app-key warnings.
  * `python scripts/run_ci_suite.py --layer server_pytest_db_knowledge` passed, 158 tests, 9 deselected, 2 existing aiohttp warnings. Evidence log: `artifacts/ci/d88ab2500e26b7c49a08d5d8f91fb16e0b16bdf9/logs/server_pytest_db_knowledge.log`.
  * `python -m pytest server/tests/test_ai_openrouter_client.py -q --tb=short` passed, 3 tests.
  * `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_ai_provider_settings.py server/tests/test_ai_integration_api.py -q --tb=short` passed, 5 tests.
  * `python -m pytest server/tests/test_ticket_knowledge_links_compat.py -q --tb=short` passed, 2 tests.
  * A noncanonical broad manual shared-DB pytest run was rejected as evidence because it attempted `127.0.0.1:5432` where no local PostgreSQL is running; the canonical `run_ci_suite.py --layer server_pytest_db_knowledge` run above supersedes it.

* Local frontend and general checks:

  * `pnpm --dir webapp test -- src/features/forms-builder/forms-builder-panel.test.tsx -t "не отправляет route preview"` passed, 1 test.
  * `pnpm --dir webapp test -- src/features/forms-builder/forms-builder-panel.test.tsx` passed, 30 tests.
  * `pnpm --dir webapp run test` passed, 89 test files and 419 tests; jsdom printed the existing informational `Not implemented: navigation to another Document` message.
  * `pnpm --dir webapp run build` passed.
  * `python -m compileall -q server shared pc_agent scripts` passed.
  * `python scripts/docs_inventory.py --check-links` passed.
  * `python scripts/verify_workspace.py` passed.
  * `git diff --check`, `git diff --check -- PLANS.md docs/completed/BROWSER_REQUESTER_AGENT_IDENTITY_MODEL.md webapp/src/features/forms-builder/forms-builder-panel.tsx` and `git diff --cached --check` passed; Git reported CRLF normalization warnings only.

* Live/browser validation:

  * Commit `34b9236d` was pushed to `origin/codex/helpdesk-process-model` and deployed with `python scripts/release_server_to_remote.py --branch codex/helpdesk-process-model --allow-local-dirty --gate quick --leave-running --smoke-insecure-tls`.
  * Quick release flow passed `python scripts/verify_workspace.py`, rebuilt the webapp bundle, applied remote Alembic migrations to head and verified remote `/api/health -> 200` on smoke attempt 2.
  * Browser route evidence passed for `https://192.168.100.17:9443/app/admin/knowledge`, `/app/admin/knowledge/ai`, `/app/admin/knowledge/search-settings`, `/app/admin/knowledge/studio`, `/app/admin/knowledge/indexing`, `/app/admin/knowledge/graph`, `/app/kb/search`, `/app/kb/ask`, `/app/knowledge` and `/app/tickets/d0132bf4-5a22-4cec-ba85-68593d13e447`.
  * Browser report: `artifacts/browser_live_validation/knowledge-final-34b9236d-1781283207077/report.json`; screenshots are in the same directory.
  * Browser evidence found no route-level session gate, login redirect, expected-text miss, console warn/error or probe leak for `secret-token`, `password=hidden`, `sk-or-`, `sk-proj-` or `BEGIN PRIVATE KEY`.
  * Browser read-only evaluation did not expose `fetch` or `XMLHttpRequest`, so same-origin API body scan from that browser surface was not available. Product data loading was verified through rendered pages and `/api/health` was verified by release smoke.
  * Live OpenRouter health check with a real key was not run because no operator-provided key was supplied. Mocked OpenRouter/client/provider tests passed and the AI settings route loaded with masked provider controls.
  * Historical note: full Ask -> requester ticket submit was not run in this route-level pass, but was later closed by the Phase 6E correction live no-device requester run on commit `f50279db`.
  * Remote `server` and `control` services were stopped after validation; follow-up status showed both inactive/dead.

Known risks:

* pgvector may not be available in all local test environments. Add capability detection and fallback tests.
* OpenRouter key is external and user-supplied; tests must mock network by default.
* AI outputs are nondeterministic; product tests must validate contract shape and safety, not exact prose.
* Manual segment offsets can become stale after edits; implement content hash and stale detection.
* Graph UI dependency can increase bundle size; isolate it and justify dependency.
* Observer v2 integration must not create noisy events for every normal keystroke; emit workflow-level events only.
* ACL leakage is the highest-risk area. Add regression tests before enabling RAG answers.
* `/app/kb/*` remains a protected requester-owned route family; every browser/live gate must include unauthenticated redirect, requester-safe projection, support/admin diagnostics separation and public `/app/help` compatibility.
* AI/RAG provider secret leakage checks must include browser console/network evidence, server audit/log/error redaction paths and screenshots; route-only rendering is not sufficient when a real provider key is enabled.

---

## Knowledge Graph editor correction, 2026-06-13

Changed:

* `/app/admin/knowledge/graph` was moved from a mostly visual graph view to an explicit graph editor workflow with modes for selection, node creation and node linking.
* The graph inspector now edits selected node fields through the existing graph API, archives nodes/edges through API mutations, and opens linked articles in Studio.
* `/app/admin/knowledge/studio?item=...` now selects the requested article by `item_id` or slug after Knowledge items load, so graph-to-Studio navigation opens the intended article instead of the default item.

Scenarios checked locally:

* Graph mode controls render: selection, add node, link nodes.
* Add node submits `POST /api/web/knowledge/graph/nodes`.
* Link nodes submits `POST /api/web/knowledge/graph/edges`.
* Edit node submits `PATCH /api/web/knowledge/graph/nodes/{stable_key}`.
* Archive edge/node still calls the existing DELETE endpoints.
* Studio honors `?item=item-2` and loads the requested article body/title.

Still required before closing the browser-visible gate:

* Deploy the current branch to the remote stand.
* Browser screenshots for `/app/admin/knowledge/graph` at 1366x768 and 1920x1080.
* Browser verification that there is no horizontal scroll and that primary graph actions are visible without scrolling.
* Browser verification that add-node, link-node and Studio navigation are usable on the live UI.
