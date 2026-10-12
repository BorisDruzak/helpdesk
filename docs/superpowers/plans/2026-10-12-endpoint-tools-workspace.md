# Endpoint Tools Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Динамически получать реальные инструменты Endpoint, запускать опубликованные
проверки с параметрами, показывать выбранный результат и прикладывать его в паспорт.

**Architecture:** Endpoint публикует device-scoped read-only индекс published modules,
используя существующую проверку совместимости. Helpdesk получает его через typed port,
создаёт ticket-scoped facade runs и использует существующие Module/Context Operations.
Reconciler сохраняет безопасные результаты; браузер работает только с Helpdesk BFF.

**Tech Stack:** Python/Pydantic, FastAPI Endpoint, aiohttp Helpdesk, SQLAlchemy/Alembic,
PostgreSQL; React 19.2.5, TanStack Query 5.99.2, TypeScript, существующие UI-компоненты.
Новые зависимости не требуются.

**Spec:** [2026-10-12-endpoint-tools-workspace-design.md](../specs/2026-10-12-endpoint-tools-workspace-design.md).

## Global Constraints

- Provider reference исследования: `9144a26472239e5a4c61a79aacdabbda4ec961bc`, Agent 3.2.82;
  Helpdesk lock до реализации: `38ddabe3c0badf09a033bb7523a89a7d2c5059a0`. До execution
  проверить актуальные main/lock, не менять dirty Endpoint checkout с пользовательскими edits.
- Первая версия consumer исполняет только registry-approved 21 primitives, safe_read/
  controlled_read; unknown schemas и capabilities не расширяют allowlist.
- Discovery: `devices.read`, `modules.read`; module execution: `module_operations.create`,
  `module_operations.read`. Helpdesk не получает права write/validate/publish modules.
- Provider response <=1 MiB; metadata cache <=60 секунд, presence/availability cache <=5 секунд.
- Две UI-колонки при container width >=640 px, ниже — вертикальная раскладка.
- Общий сбор: baseline/health/network/inventory/session через safe Context port плюс
  diagnostic через существующий operation contract; не запускать network probes без target.
- Actor/ticket/verified device, cookie/CSRF, no-store, idempotency и audit сохраняются.
  Caller key/ticket ID остаются в Helpdesk; Agent wire, binary и update policy не меняются.
- Исторический успех не заменяет свежий queued run. Passport хранит safe snapshot;
  Endpoint PIN не создаётся. При rollout флаг нового workspace первоначально off.
- Это один интеграционный проект с последовательным provider/consumer gate. Tasks
  не дают разрешения пропускать review, contract acceptance или production release gate.

## Review Focus

1. Latest draft не должен скрывать более старую published version — Task 1.
2. Input, используемый несколькими шагами, должен удовлетворять всем DTO; conflicting
   bounds блокируют форму и backend run — Tasks 2 и 7.
3. Поздний ответ run A после выбора B не должен заменить результат B — Tasks 4 и 7.
4. Expiry Endpoint evidence после прикрепления не должен повредить паспорт — Task 6.
5. Смена пользователя/device при cached catalog не должна разрешить чужой или
   устаревший запуск; collapsed layout не должен сохранить невидимые focus targets — Tasks 5 и 9.

## Рабочие копии и проверка базовой ревизии

Helpdesk documents находятся на `codex/endpoint-tools-workspace` в project-local worktree.
До implementation безопасно привести эту ветку к принятому Helpdesk main, сохранив
commits спецификации/плана и чужие edits. Не переносить несогласованные изменения
Request Studio из другого checkout. Endpoint implementation вести в отдельном
checkout/worktree его репозитория на принятом main; снимок `artifacts/tool-panel/endpoint-main`
использован только для исследования, из него нельзя deploy/push implementation.

В каждом репозитории прочитать действующие AGENTS, проверить clean baseline и GitNexus
repo/group freshness. Context7 применяется перед library-dependent implementation,
с pinned versions из соответствующего checkout; внутренний исходный код туда не передавать.

Команды ниже выполняются из root указанного репозитория, web-команды — из `webapp`.
DB tests запускаются с утверждённой isolated PostgreSQL fixture/environment; production
DB не используется для tests. В каждой Task: FAIL от нового теста → minimal implementation
→ PASS focused tests → полный diff/diff-check → atomic Conventional Commit.

## Task 1: Published module index в Endpoint

**Files (Endpoint):** Create `endpoint_contracts/device_modules.py`,
`endpoint_server/modules/device_catalog.py`, `endpoint_server/modules/device_catalog_routes.py`,
`tests/server/test_device_module_catalog.py`, `tests/contracts/test_device_module_catalog.py`.
Modify `endpoint_server/console/modules.py`, `endpoint_server/main.py`,
`contracts/openapi/endpoint-platform-v1.yaml`, `tools/contracts/generate_contract_artifacts.py`;
generated schema `contracts/jsonschema/endpoint-device-modules-v1.json` и
`docs/architecture/endpoint-capability-platform-v2.md`.

**Interfaces:** `EndpointDeviceModulesPageV1(schema_version, device_id, observed_at,
items, next_cursor)`; `PublishedDeviceModuleV1(module_key, display_name, version,
state, recipe, availability, reason_code)`.
`project_device_modules(session, settings, connection, device_id, limit, cursor)
-> EndpointDeviceModulesPageV1`. Новая service route:
`GET /api/v1/devices/{device_id}/modules`, scopes `devices.read` + `modules.read`.

- [ ] **Test:** `test_draft_does_not_hide_published_version` и
  `test_device_modules_page_auth_and_bounds`. Assertions:
  `assert {x.state for x in page.items} == {'published'}`;
  `assert page.schema_version == 'endpoint_device_modules_v1'`;
  draft/validated/disabled отсутствуют, offline => unavailable, missing facts => unknown,
  0/101 limit =>422, invalid cursor =>400, missing scopes =>403, retired device =>404.
- [ ] **FAIL:** `python -m pytest tests/server/test_device_module_catalog.py tests/contracts/test_device_module_catalog.py -q`.
- [ ] **Implement:** вынести reusable published-version query и compatibility projection
  из Console, сохранив его admin authentication. Service DTO не раскрывает sessions/tokens.
  Keyset по module key/created_at/UUID, SemVer не сортировать строкой; invalid published
  recipe даёт безопасный invalid projection. На новой route echo bounded correlation header.
- [ ] **PASS:** та же команда плюс `python -m pytest tests/server/test_console_modules.py -q`;
  `python tools/contracts/generate_contract_artifacts.py --write`, затем
  `python tools/contracts/generate_contract_artifacts.py --check`; проверить diff generated artifacts.
- [ ] **Commit:** `feat(modules): expose published device module catalog`.

## Task 2: Typed consumer и параметрические схемы Helpdesk

**Files (Helpdesk):** Create `server/domain_ports/endpoint_modules.py`,
`server/endpoint_adapter/modules_http.py`, `server/endpoint_adapter/modules_wire.py`,
`server/diagnostics/endpoint_tool_parameters.py`,
`server/tests/test_endpoint_modules_adapter.py`, `server/tests/test_endpoint_tool_parameters.py`.
Modify `server/domain_ports/container.py`, `integration/endpoint_contract.lock.json`,
`.github/workflows/endpoint-contract-acceptance.yml`,
`server/tests/acceptance/test_endpoint_operations_v1_acceptance.py` и `server/docs/CODEMAP.md`.

**Interfaces:** `EndpointModulesPort.list_primitives()`,
`list_device_modules(device, *, limit, cursor)`, `read_module_version(key, version)`,
`create_module_operation(device, request, *, idempotency_key, correlation_id)`,
`read_module_operation(ref)` — frozen success/failure outcomes.
`derive_recipe_inputs(recipe, primitive_catalog) -> ToolInputSchemaV1`;
`validate_tool_inputs(schema, inputs) -> CanonicalToolInputsV1`.

- [ ] **Test:** `test_registry_does_not_make_unpublished_module_runnable`,
  `test_shared_input_bounds_intersect`, `test_literal_parameter_is_not_input`.
  Assert shared timeout intersection is 100..5000; empty intersection is invalid;
  target URL/extra params rejected; wrong device, redirects, >1 MiB, unknown result schema
  and 403 give typed errors, not empty/successful catalogs.
- [ ] **FAIL:** `python -m pytest server/tests/test_endpoint_modules_adapter.py server/tests/test_endpoint_tool_parameters.py -q`.
- [ ] **Implement:** generated/provider-verified DTO schemas для 21 results, closed codecs,
  explicit method/status/correlation rules из OpenAPI. Не импортировать provider runtime;
  metadata controls labels, known DTO validation controls execution.
- [ ] **PASS:** команда FAIL и real provider contract-acceptance workflow на clean Task 1 SHA
  с isolated migrated PostgreSQL. Только затем обновить lock/OpenAPI digest.
- [ ] **Commit:** `feat(endpoint): consume typed module catalogs and operations`.

## Task 3: Persistence для immutable tool runs

**Files:** Modify `server/app/db/models.py`, `server/app/repos/endpoint_operation_links_repo.py`.
Create `server/app/repos/endpoint_tool_runs_repo.py`,
`server/app/db/migrations/versions/20261012_147_endpoint_tool_runs.py`,
`server/tests/test_endpoint_tool_runs_repo.py`, `server/tests/test_endpoint_tool_runs_migration.py`.

**Interfaces:** `EndpointToolRunsRepo.create_pending(request, actor_id, ticket_id,
device_ref, caller_key) -> ToolRunStoredV1`; `get_authorized_run(run_id, ticket_id)`;
`claim_ready(owner, limit, now)`; `commit_projection(claim, projection)`.
Immutable snapshot содержит execution kind, module/version или profile, canonical inputs
и recipe digest; local run/step ID и remote reference имеют разные поля.

- [ ] **Test:** `test_same_actor_key_replays_same_request`,
  `test_changed_inputs_reusing_key_conflicts`, `test_existing_diagnostic_rows_survive_upgrade`.
  Assert один local/remote intent при replay; conflict =>409; diagnostic keys и snapshots
  сохраняются, leases эксклюзивны, stable references не смешивают виды runs.
- [ ] **FAIL:** `python -m pytest server/tests/test_endpoint_tool_runs_repo.py server/tests/test_endpoint_tool_runs_migration.py -q`.
- [ ] **Implement:** перед миграцией проверить actual schema и residue revisions 139–142.
  Использовать уже физически существующие module_key/module_version/module snapshots;
  не добавлять их второй раз. Новая revision расширяет модель, constraints и context run
  linkage additive; старые migrations не редактировать. Retired module residue
  не становится новым runnable intent: старые неизвестные rows остаются unclaimed,
  пока отдельный audited review не подтвердит их принадлежность/immutable request.
  Если head уже не146, выбрать
  следующий уникальный revision и проверить chain до commit, без второго Alembic head.
- [ ] **PASS:** команда FAIL и существующие
  `python -m pytest server/tests/test_endpoint_operation_links_repo.py server/tests/test_endpoint_operation_links_migration.py -q`.
- [ ] **Commit:** `feat(diagnostics): persist immutable Endpoint tool runs`.

## Task 4: Facade, общий сбор и reconciler

**Files:** Create `server/app/services/endpoint_tool_run_service.py`,
`server/app/services/endpoint_tool_reconciler.py`,
`server/tests/test_endpoint_tool_run_service.py`, `server/tests/test_endpoint_tool_reconciler.py`.
Modify `server/server.py`, `server/app/services/endpoint_operation_reconciler.py`
и `server/docs/CODEMAP.md`.

**Interfaces:** `EndpointToolRunService.create_module(actor, ticket_id, request, caller_key)`;
`create_context_batch(actor, ticket_id, caller_key) -> ToolBatchStoredV1`;
`EndpointToolReconciler.run_once(limit, now) -> ReconcileSummaryV1`.
`EndpointToolReconcilerRunner.start()` / `async stop()` из того же service module.
Consumers: Task 2 port + Task 3 repo + current actor authorization/device reference resolver.

- [ ] **Test:** `test_context_batch_has_six_distinct_steps`,
  `test_reconcile_resume_does_not_resubmit_module`, `test_partial_batch_is_not_success`,
  `test_legacy_reconciler_does_not_claim_module_rows`.
  Assert пять safe-context steps плюс один diagnostic, stable server-generated keys,
  late/duplicate delivery не переписывает другой run, failure одного шага =>partial,
  create acceptance != succeeded, expired не становится success.
- [ ] **FAIL:** `python -m pytest server/tests/test_endpoint_tool_run_service.py server/tests/test_endpoint_tool_reconciler.py -q`.
- [ ] **Implement:** локальный intent transaction, remote I/O только reconciler, bounded
  retry/lease и safe snapshot persistence. Module/context namespace separate; existing
  diagnostic idempotency key неизменен. Claim predicates старого и нового reconciler
  непересекающиеся; legacy unclassified module rows не dispatch-ятся. New UI flag off
  не останавливает активные новые runs. Start/stop подключить в `server/server.py`.
- [ ] **PASS:** команда FAIL плюс
  `python -m pytest server/tests/test_endpoint_operation_reconciler.py server/tests/test_endpoint_operation_bridge.py -q`.
- [ ] **Commit:** `feat(diagnostics): reconcile module runs and context batches`.

## Task 5: Ticket-scoped BFF и права

**Files:** Create `server/web_api/endpoint_tool_handlers.py`,
`server/web_api/dto/endpoint_tools.py`, `server/tests/test_web_endpoint_tools.py`.
Modify `server/routes.py`, `server/config.py`, `server/server.py`,
`server/docs/CODEMAP.md`, `docs/segmentation/HELPDESK_ENDPOINT_OPERATION_BOUNDARY.md`.

**Interfaces:** Task 4 service + Task 2 catalog cache → spec BFF routes:
GET ticket endpoint-tools; POST/GET runs; POST/GET collections. DTOs:
`EndpointToolCatalogPayloadV1`, `EndpointToolRunCreateV1`, `EndpointToolRunPayloadV1`,
`EndpointToolBatchPayloadV1`; все имеют discriminator/schema version.

- [ ] **Test:** `test_changed_device_invalidates_cached_run_permission`,
  `test_auditor_can_read_but_cannot_run`, `test_foreign_ticket_run_is_not_readable`.
  Assert mutation CSRF required, fresh catalog checked before POST; stale catalog read-only,
  403 provider is explicit, metadata TTL60/device TTL5 соблюдаются, wrong ticket =>404/403,
  same key/change inputs =>409; unpublished version cannot be supplied by caller.
- [ ] **FAIL:** `python -m pytest server/tests/test_web_endpoint_tools.py -q`.
- [ ] **Implement:** exact device from server resolver, not client body; no-store, safe errors,
  flag default off. Browser caller key не передаётся provider. Poll GET reads persisted state.
- [ ] **PASS:** команда FAIL плюс
  `python -m pytest server/tests/test_web_support_api.py server/tests/test_observer_web_auth.py -q`.
- [ ] **Commit:** `feat(web): expose authorized ticket Endpoint tool API`.

## Task 6: Evidence и паспорт с собственным snapshot

**Files:** Create `server/diagnostics/endpoint_tool_evidence.py`,
`server/tests/test_endpoint_tool_passport.py`. Modify `server/diagnostics/passport_bridge.py`,
`server/app/repos/ticket_passport_repo.py` только в части выбранного diagnostic evidence.

**Interfaces:** `materialize_tool_evidence(run, step) -> DiagnosticEvidenceDraftV1`;
`DiagnosticPassportBridgeService.attach_selected_diagnostic_evidence_to_passport(...)`
сохраняет source/device/module/version/profile/input summary/schema/time/digest и safe result.

- [ ] **Test:** `test_passport_snapshot_survives_provider_expiry`,
  `test_attach_same_evidence_is_idempotent`, `test_failed_safe_result_keeps_failure_status`.
  Assert snapshot неизменен после remote expiry; повтор создаёт 1 evidence item;
  queued/null result нельзя прикрепить как success, чужой ticket запрещён,
  source server никогда не становится source endpoint.
- [ ] **FAIL:** `python -m pytest server/tests/test_endpoint_tool_passport.py -q`.
- [ ] **Implement:** Task 2 codec validation перед сохранением; digest по canonical safe
  payload и immutable provenance. Passport не зависит только от remote TTL link и не PIN-ит Endpoint.
- [ ] **PASS:** та же команда плюс
  `python -m pytest server/tests/test_diagnostic_layer.py server/tests/test_diagnostic_phase9_persistence.py -q`.
- [ ] **Commit:** `feat(passport): retain selected Endpoint tool evidence snapshots`.

## Task 7: Каталог, формы и выбранный результат в webapp

**Files:** Create `webapp/src/features/endpoint-tools/api.ts`, `types.ts`,
`tool-inputs.ts`, `tool-inputs.test.ts`, `use-endpoint-tools.ts`,
`endpoint-tools-panel.tsx`, `endpoint-tools-panel.test.tsx`, `tool-result.tsx`.
Modify `webapp/src/features/diagnostics/diagnostic-center-panel.tsx` как composition point.

**Interfaces:** `useEndpointTools(ticketId)` возвращает catalog/selection/runs;
`EndpointToolsPanel({ticketId})`; `deriveInputControls(recipe, catalog)` использует
Task 5 schemas; `EndpointToolResult({run})` принимает closed result DTO из types.ts.

- [ ] **Test:** `keeps_selected_run_when_an_older_response_arrives`,
  `renders_literal_as_fixed_setting`, `does_not_enable_unknown_or_unpublished_tool`.
  Assert selected B не меняется после A; server DNS отсутствует в Endpoint diagnostics;
  target/count/timeout fields с точными bounds, invalid intersection blocked, queued
  shows no fresh result, historical result содержит собственную дату.
- [ ] **FAIL:** `pnpm test -- src/features/endpoint-tools/tool-inputs.test.ts src/features/endpoint-tools/endpoint-tools-panel.test.tsx`.
- [ ] **Implement:** инструмент/параметры слева, selected run result справа; container
  query 640 px; query keys содержат account/ticket/device/module/version/run. Unknown
  data, success-empty, failed safe result, expired и offline имеют разные UI states.
- [ ] **PASS:** команда FAIL и `pnpm build`.
- [ ] **Commit:** `feat(webapp): add Endpoint tool forms and selected run results`.

## Task 8: Общий сбор и прикрепление из UI

**Files:** Create `webapp/src/features/endpoint-tools/context-batch-panel.tsx`,
`context-batch-panel.test.tsx`; modify `endpoint-tools-panel.tsx`, diagnostic API/bridge usage.
Точные integration files: `webapp/src/features/diagnostics/api.ts`,
`webapp/src/features/endpoint-tools/api.ts`.

**Interfaces:** `ContextBatchPanel({ticketId, batch})`; `attachSelectedToolResult(runId, stepId)`
пользуется существующим backend evidence selection/attach flow с Task 6 authorization.

- [ ] **Test:** `shows_partial_batch_without_reusing_old_snapshots`,
  `attaches_only_selected_completed_result_once`. Assertions:
  `expect(steps).toHaveLength(6)`; failed network step =>partial, не success;
  pending result has disabled attach, failed safe evidence retains failure label,
  duplicate attach shows «В паспорте», expired before capture requires a new collection.
- [ ] **FAIL:** `pnpm test -- src/features/endpoint-tools/context-batch-panel.test.tsx`.
- [ ] **Implement:** общий сбор ниже двух колонок; step statuses из Task 5, poll2s
  активных runs, stop terminal/unmount/logout. Attachment имеет отдельный mutation key;
  output другого run не прикладывается вследствие смены selection.
- [ ] **PASS:** команда FAIL и tests Task 7.
- [ ] **Commit:** `feat(webapp): show context batches and passport attachment`.

## Task 9: Контекст и независимое сворачивание колонок

**Files:** Create `webapp/src/features/endpoint-tools/ticket-context-panel.tsx`,
`ticket-context-panel.test.tsx`, `webapp/src/shared/ui/workspace-panel-preferences.ts`,
`workspace-panel-preferences.test.ts`; modify `webapp/src/pages/tickets/list-page.tsx`,
`webapp/src/app/layouts/app-shell.tsx`, their existing tests и `webapp/src/styles.css`.

**Interfaces:** `TicketContextPanel({requester, device, agent, observer})`;
`loadPanelPreferences(accountId, workspace)` / `savePanelPreferences(...)`;
independent `navigationCollapsed` и `ticketListCollapsed` flags.

- [ ] **Test:** `orders_requester_device_agent_before_observer`,
  `collapses_panels_independently_without_changing_selection`,
  `storage_failure_keeps_navigation_usable`, `hidden_panel_has_no_focus_targets`.
  Assert route/filter/selection unchanged; account A prefs не наследуются B; no selected
  ticket =>list visible; critical Observer summary видна при collapsed details.
- [ ] **FAIL:** `pnpm test -- src/features/endpoint-tools/ticket-context-panel.test.tsx src/shared/ui/workspace-panel-preferences.test.ts src/app/layouts/app-shell.test.tsx src/pages/tickets/list-page.test.tsx`.
- [ ] **Implement:** вынести только context composition, не переписывать весь list-page.
  Icon rail с labels/tooltip, aria-expanded/focus; отсутствие Agent version =>«Нет данных».
  Сохранить существующие resize/overlay behavior и light/dark preference.
- [ ] **PASS:** команда FAIL и `pnpm build`.
- [ ] **Commit:** `feat(workspace): reorder ticket context and collapse side panels`.

## Task 10: Контрактные и браузерные regression gates

**Files:** Create `webapp/tests/endpoint-tools.spec.ts`; modify
`server/tests/acceptance/test_endpoint_operations_v1_acceptance.py`,
`docs/segmentation/HELPDESK_ENDPOINT_OPERATION_BOUNDARY.md`,
`docs/segmentation/HELPDESK_ENDPOINT_CONTEXT_BOUNDARY.md`, `server/docs/CODEMAP.md`.

**Interfaces:** собранные Tasks 1–9, pinned provider artifact, accepted webapp bundle.

- [ ] **Test:** browser scenarios для real-shaped fixtures: dynamic published module,
  user-defined inputs, run A/B race, old result vs queued, partial six-step batch,
  evidence attach, independent collapse и viewport390/1366/1920/2582.
- [ ] **FAIL → PASS:** `pnpm test:e2e -- endpoint-tools.spec.ts`; fixtures нельзя
  записывать как live Agent acceptance. Проверить отсутствие console/network errors.
- [ ] **Verify:** scoped `python scripts/verify_workspace.py --workspace .`, focused backend/
  frontend tests, builds, exact-SHA canonical CI и pinned real provider contract acceptance.
  Reviewer проверяет auth, schema migration, idempotency, provenance, code/doc drift;
  открытые блокирующие findings исправляются до следующей Task.
- [ ] **Commit:** `test(endpoint): cover tool workspace integration and regressions`.

## Task 11: Scoped service access, staging acceptance и rollout

**Files (Endpoint):** Create `endpoint_server/auth/provision_helpdesk_diagnostic_credential.py`,
`tests/server/test_helpdesk_diagnostic_credential.py`, modify service credential runbook.
Helpdesk: reviewed runtime/config procedures, evidence вне tracked source. Никаких
passwords/tokens в plan, commits, stdout, screenshot или durable evidence.

**Interfaces:** clean provider/consumer SHAs, published catalog v1, accepted CI bundle,
новый schema revision и exact declared deployment/config profiles.

- [ ] **Test/FAIL:** `test_diagnostic_rotation_does_not_grant_authoring_scopes`,
  `test_rotation_preserves_client_identity_and_existing_operation_reads`:
  `assert not {'modules.write', 'modules.validate', 'modules.publish'} & set(scopes)`.
  Run `python -m pytest tests/server/test_helpdesk_diagnostic_credential.py -q`.
- [ ] **Implement/PASS:** узкий audited root-only CLI поверх существующих credential
  services. Сохранять identity текущего integration client, нужные existing read/context/
  diagnostic scopes и rollback credential; добавить только approved module read/create/read.
  Legacy workbench CLI `provision_helpdesk_module_credential.py` по умолчанию выдаёт
  write/validate/publish: его нельзя использовать без изменения policy для этого flow.
  Неожиданные existing authoring scopes требуют отдельного review, не молчаливого расширения.
  Повторить test command и commit `feat(auth): provision scoped Helpdesk diagnostic access`.
- [ ] **Prepare:** проверить production/staging отдельно. Provision/rotation только
  по штатному secret-channel workflow. Получить actual published single-step
  DNS/ping module от владельца Endpoint; не публиковать его через Helpdesk token.
- [ ] **Deploy staging:** project release/migration scripts, свежий backup/restore drill,
  feature flag on только на staging. Verify new catalog returns200 и правильный device,
  scopes/flags/policies реально действуют; не ослаблять CA/hostname validation.
- [ ] **Live acceptance:** совместимый подключённый Agent без install/update; один
  разрешённый DNS либо ping, реальные module run/step result и паспорт после reload;
  общий сбор с результатами отдельных profiles, панели/keyboard/responsive и degraded
  Endpoint path при продолжающейся работе ticket chat. Сопоставить browser/DB audit/
  provider operation IDs; удалить membership/отключить только принадлежащие тесту accounts.
- [ ] **Release:** production только по действующему reviewed gate и пользовательской
  авторизации; current risk audit, real Windows/degraded acceptance, exact SHA/bundle/lock,
  migration/backup и rollback должны быть concrete PASS. UNKNOWN не повышается до PASS.
  После rollout повторить browser/tool/passport/core workflow verification и runtime identity.
- [ ] **Cleanup/report:** восстановить все временные test VM/service settings; staging
  stop, если пользователь не просил оставить его работающим. Report versions, commits,
  checked/skipped gates и residual risks. Наличие плана не означает выполненный deploy.

## Self-review и следующий этап

Spec sections 1–5 покрыты Tasks1–2; section6 — Task7; section7 — Tasks4/8; section8 —
Tasks2–5; section9 — Task6/8; section10 — Task9; section11 — Tasks1/10/11;
section12 — tests Tasks1–11; section13 — file ownership этих Tasks.
Все пять Review Focus conditions закреплены named tests в указанных владельцах.
Interfaces из Tasks2–6 должны оставаться едиными между backend/DTO/web types.

План готов для review. Execution method пока не выбран. Рекомендация — native:
интерфейсы provider → adapter → persistence → reconciler → UI тесно связаны, поэтому
последовательная реализация в одной сессии сокращает стоимость повторной передачи контекста.
После реализации требуется независимый review всей ветки; альтернативный метод —
subagent-driven с отдельной implementation/review gate на каждую Task.
