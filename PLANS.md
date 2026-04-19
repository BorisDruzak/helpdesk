# PLANS.md

## 2026-04-19 Observer live canaries + hard module CI guard

- Scope:
  - сделать observer breadcrumbs обязательным CI-контрактом для всех новых `BaseCollector` tool methods, а не только правилом из docs;
  - валить module ZIP preflight и `python scripts/verify_workspace.py`, если в `@exposed_tool` нет mandatory `self.trace_span("tool.entry", ...)`;
  - добавить живой canary-suite для оставшихся опасных flow: consent approve/deny/timeout, module install/update/remove, retry exhausted, agent disconnect during operation, ws ack/nack/replay;
  - добить runtime sync между `device_outbox` и `operations`, чтобы retry exhaustion и send failures были видны в observer слое как нормальные operation/runtime-audit события;
  - задокументировать новый hard guard и canary entrypoint, затем прогнать локальные тесты, Linux deploy и browser E2E.
- Deliverables:
  1. `server/utils/module_observer_contract.py` + wiring в `module_preflight.py` и `scripts/verify_workspace.py`;
  2. обновлённые builtin/managed module sources, удовлетворяющие hard guard;
  3. regression tests для AST guard, workspace verify и retry/delivery sync;
  4. `scripts/run_observer_canary_suite.py` + helper tests для его локальной оркестровки;
  5. docs sync (`MODULES.md`, `CODEMAP.md`, `QUICK_LOOKUP.md`) по hard guard и live canary flow;
  6. подтверждённый live run на Linux + browser verification техпанели.
- Verification target:
  - `python scripts/verify_workspace.py`
  - targeted `pytest` для `server/tests`, `scripts/` и затронутых `pc_agent` модулей
  - `python scripts/release_server_to_remote.py`
  - `python scripts/run_observer_canary_suite.py`
  - browser verification на `http://192.168.100.17:8666/admin`

## 2026-04-19 Observer v3: spans, propagation, health, module SDK, settings, security

- Scope:
  - materialize agent-side `action_trace` entries into first-class `observer_spans` / `observer_span_links` instead of returning them only as an attached JSON block in trace detail;
  - finish trace propagation for remaining server-originated paths so ticket-bound work converges on canonical ticket root traces and dangerous background flows stop generating isolated ad-hoc traces by default;
  - promote observer runtime into a monitored subsystem with explicit health/config/status payloads suitable for alerts and the tech/settings UI;
  - introduce a standard module-level observability SDK/hook in `BaseCollector`, make it the required path for new modules, and update current built-in modules to emit nested trace breadcrumbs consistently;
  - add small default retention/sampling settings for testing, store them in server settings, and expose them in the settings UI;
  - harden security by fixing `manage_local_agent --issue-token`, removing noisy default-admin-password warnings, and redacting sensitive fields from `details_json`, action traces, observer attrs, and tech exports.
- Deliverables:
  1. observer action-trace projection into persisted spans/links;
  2. centralized trace propagation updates and regression coverage;
  3. observer health/settings repo + tech/settings API + UI wiring;
  4. module instrumentation SDK + built-in module updates + docs/rules update;
  5. redaction helpers applied to runtime audit, action trace, observer payloads, and tech endpoints;
  6. fixed local token issue flow, new agent build, Linux deploy, browser verification, and post-check server stop.
- Verification target:
  - `python scripts/verify_workspace.py`
  - targeted `pytest` for observer/settings/tech/manage_local_agent tests
  - targeted `pytest` for `pc_agent/tests` covering action-trace/module instrumentation
  - `node --check server/admin.js`
  - `python pc_agent/build_windows_release_v2.py`
  - remote release via `python scripts/release_server_to_remote.py`
  - browser verification at `http://192.168.100.17:8666/admin`

## 2026-04-19 Observer v2: full ticket trace + degradations + historical backfill

- Scope:
  - make a ticket-scoped observer root trace canonical for the full lifecycle of a ticket;
  - ensure server-originated ticket events and ticket-bound operations converge on the same trace instead of ad-hoc `uuid4()` values;
  - extend observer search with first-class degradation queries (`duration > N`, timeout rate, retry rate);
  - add automatic historical backfill to the observer runtime so older traces do not require manual rebuild;
  - guarantee deeper module-level agent breakdown through action-trace instrumentation even when a module does not emit custom runtime audit entries.
- Deliverables:
  1. schema support for canonical ticket observer root trace;
  2. server-side trace propagation and observer API/runtime upgrades;
  3. degradation query endpoint and tech-panel UI for it;
  4. agent-side module execution breakdown in action trace;
  5. updated docs/CODEMAP/QUICK_LOOKUP for observer v2;
  6. local tests, Linux deploy, browser E2E, and rollback-safe stop of the remote server.
- Verification target:
  - `python scripts/verify_workspace.py`
  - targeted `pytest` for new server observer tests and agent action-trace tests
  - `node --check server/admin.js`
  - remote release via `python scripts/release_server_to_remote.py`
  - browser verification at `http://192.168.100.17:8666/admin`

## 2026-04-17 Trace overlay + observer hardening

- Scope:
  - ввести observer-domain поверх текущей доменной модели без замены `tickets/problems/operations`;
  - добавить сущности `observer_traces`, `observer_spans`, `observer_span_links`, `observer_error_occurrences`, `observer_error_signatures`;
  - построить projection/overlay из текущих источников: `operations`, `ticket_events`, `device_events`, `agent_runtime_audit`, agent `action_trace`;
  - дать tech API для поиска и drilldown по `trace_id`, `ticket_id`, `job_id`, `operation_id`, `device_id`, `tool_name`, `module_name`, `error_signature`;
  - закрыть найденные баги: ложный `running` у `manage_local_agent`, шумный `404` по пустому toolset snapshot, зависание cancel-flow.
- Deliverables:
  1. схема БД + миграция + projection service для trace overlay;
  2. tech API для traces/signatures/detail/rebuild и bridge к agent action trace;
  3. incremental/background refresh runtime для hot traces + runtime status endpoint в tech panel;
  4. regression fixes по runtime/toolset/cancel-flow;
  5. sync docs/CODEMAP/QUICK_LOOKUP по новым observer entrypoints;
  6. подтверждённые локальные тесты и browser check техпанели.
- Verification target:
  - `python scripts/verify_workspace.py`
  - targeted `pytest` для `server/tests` и `scripts/test_manage_local_agent.py`
  - regression run для `server/tests/test_cancel_operations.py`
  - browser check на `http://192.168.100.17:8666/admin`
  - если поднимался Linux-стенд, в конце остановить `server`, если пользователь отдельно не просил оставить его запущенным.

## 2026-04-16 Agent tracing + automation hardening

- Scope:
  - закрыть баги, найденные на живом launcher/GUI прогоне: tool RBAC/policy gaps, stale tool metadata, неполный refresh/detail и локальную automation response path;
  - усилить agent/server logging до action-trace уровня, чтобы ticket/message/tool/confirm/reply/screenshot/video flows легко искались по `ticket_id`, `operation_id`, `trace_id`, `message_id` и локальному `action_id`;
  - расширить localhost automation surface агента до полного smoke/E2E набора: ticket create, smart-form fill, send message, screenshot, video, focused log collection, chat snapshot и server-event injection;
  - провести ручной и полуавтоматический E2E прогон через launcher agent + `/admin` + server/agent logs + DB, включая формы, RBAC, новый tool и confirmation flow.
- Deliverables:
  1. локально подтверждённые fixes на agent/server;
  2. новый trace/logging слой и способы получить focused trace по действию;
  3. рабочий automation driver для полного agent smoke;
  4. оформленный manual QA checklist/result с фактами из UI, логов и БД.
- Verification target:
  - `python scripts/verify_workspace.py`
  - targeted `pytest` для `server/tests` и `pc_agent/tests`
  - launcher smoke через `python scripts/manage_local_agent.py start <name> --launcher --gui --ui-port <port>`
  - remote server smoke + browser/manual checks на `http://192.168.100.17:8666/admin`
  - в конце, если пользователь отдельно не просит оставить стенд, remote server должен быть остановлен.

## 2026-04-16 Agent GUI themes + ticket wizard

- Scope:
  - довести обе темы GUI до согласованной light/dark palette вместо partial recolor;
  - переделать создание тикета из модального диалога в page-wizard внутри основного окна;
  - сделать creation flow пошаговым: профиль -> тип/доп. поля -> описание/вложения -> срочность/важность;
  - добавить вложения скриншота/видео на этапе создания тикета с отправкой первым сообщением после create.
- Verification target:
  - локальный GUI инстанс без коммита и без деплоя;
  - `verify_workspace` и релевантные agent GUI tests;
  - ручная локальная проверка page-wizard и переключения тем.

## 2026-04-16 Agent GUI sidebar UX

- Scope:
  - свернуть старую левую панель профиля в новую функциональную навигацию;
  - перенести настройки в верх навигационной рейки;
  - вынести список тикетов в отдельную функцию слева с открытием чата по двойному клику;
  - убрать дублирующую кнопку из профиля инициатора.
- Verification target:
  - локальный запуск GUI агента без коммита и без выкладки на Linux;
  - точечные проверки `verify_workspace` и/или релевантные agent GUI тесты, насколько они не конфликтуют с текущим WIP.

## Goal

- Довести первую production-волну hardening/modularization до состояния, где проект можно проверять и выпускать без ручной магии.
- Получить предсказуемый baseline для `verify_workspace`, `server/tests`, `pc_agent/tests`, isolated test DB, self-hosted CI gate и актуальной документации.

## Scope

- Входит:
  - корневой pytest-контур и маркировка `unit` / `integration` / `manual` / `no_db`;
  - isolated test DB с canonical env vars;
  - CI artifacts и release/deploy gate;
  - docs sync и архивирование устаревших roadmap/gap-analysis документов;
  - удаление unreachable legacy runtime paths;
  - точечная modularization самых перегруженных runtime-path.
- Не входит:
  - новые продуктовые helpdesk/LLM features;
  - browser E2E в CI;
  - смена основных HTTP/WS контрактов сверх уже закреплённого async `/api/tools/run`.

## Constraints

- Источник истины для правок: `C:\Users\admin-2\CodexProjects\pc_client`.
- Linux-хост `altserver@192.168.100.17` остаётся местом self-hosted CI/release gate.
- Обратную совместимость сохраняем только там, где она нужна для миграции уже существующих установок, токенов и SQLite-схем.
- Любое новое release/deploy ограничение должно иметь явный emergency bypass.

## Decisions

- Shared DB `pc_support_test` больше не канон: по умолчанию тесты должны работать на уникальной БД `pc_support_test_<runid>`.
- Shared test DB разрешается только при явном `PC_CLIENT_ALLOW_SHARED_TEST_DB=1`.
- Канонические test/CI env vars:
  - `TEST_DATABASE_ADMIN_URL`
  - `TEST_DATABASE_URL`
  - `PC_CLIENT_ALLOW_SHARED_TEST_DB`
- CI artifacts живут в `artifacts/ci/<sha>/`.
- `deploy_workspace_to_remote.py` и `release_server_to_remote.py` по умолчанию требуют green CI artifact; bypass только через `--skip-ci-check`.
- Stale roadmap/gap-analysis документы выносятся в `docs/archive/` и больше не считаются каноном.

## Current State

- Сделано:
  - добавлен корневой `pytest.ini` и обновлены server markers;
  - `pc_agent/tests/test_support_chat_reliability.py` выведен из auto-collection через `pytest.mark.manual`;
  - `server/tests/conftest.py` переведён на isolated test DB-per-run и session-scoped engine;
  - добавлены `requirements-ci.txt`, `scripts/ci_artifacts.py`, `scripts/run_ci_suite.py`;
  - release/deploy scripts проверяют CI artifact;
  - async contract `/api/tools/run` закреплён тестами;
  - cancel-operation flow доведён до зелёного integration baseline;
  - `server/server_old.py` и `server/tickets/service.py` удалены из активного runtime tree;
  - docs archive/sync wave начата.

## Next Steps

- Синхронизировать канонические docs/CODEMAP после архивирования.
- Прогнать `verify_workspace` и релевантные pytest после docs cleanup.
- Отдельно оценить остаточные падения полного `server/tests` suite, если они ещё есть.
- Следующий пакет правок должен идти в порядке:
  1. docs sync / CODEMAP / QUICK_LOOKUP;
  2. `verify_workspace`;
  3. выборочный или полный server pytest regression run;
  4. только потом новые рефакторинги крупных файлов.

## Verification

- Минимум:
  - `python scripts/verify_workspace.py`
  - `python -m pytest pc_agent/tests -m "not manual"`
- Локально для server suite сейчас удобно:
  - `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/...`
- Целевой CI baseline:
  - `python scripts/run_ci_suite.py`

## Handoff

- Ключевой риск: production-волна одновременно затрагивает тестовую инфраструктуру, release flow и крупные runtime-файлы, поэтому после каждого пакета изменений нужен повторный baseline-прогон.

## 2026-04-15 Module Development Workbench Follow-up

- Expanded the admin module workbench toward a full authoring surface:
  - template-driven tool starters now cover `dns.resolve`, `network.ping`, `tcp.connect`, `route.get`, `adapter.list`, `http.request`, and `system.service_status`;
  - inline validation runs directly in the editor while payload/API preview stays in sync;
  - server-side validate preview (`POST /api/modules/workbench/validate`) now reports publish readiness, ownership conflicts, and archive/source reconstruction without publishing;
  - module archives are decomposed back into editable source fragments through builder markers or AST analysis of `@exposed_tool` functions.
- Remaining execution steps for this task:
  1. run local verify + targeted pytest;
  2. deploy committed state to Linux with the standard release script;
  3. browser-check the richer `Модули` tab on `http://192.168.100.17:8666/admin`, including archive/source explorer and save/validate flow with a live agent;
  4. stop the remote server after smoke.

## 2026-04-14 Audit: Agent Update + Modules

- Scope:
  - self-update с server-side выбором целевой версии, beta/release семантикой и GUI агента;
  - server-managed modules flow: upload -> install -> activate -> run_tool -> result -> reconcile/toolset sync.
- Уже есть:
  - server-side `agent_builds` registry, remote update command `update`, launcher apply/verify/rollback и handshake-confirm;
  - module registry, desired/actual tables, periodic reconcile, device-scoped install/remove API, agent package install/reload, auto-install before `run_tool`.
- Основные gap-ы для production:
  - у self-update нет server-side “recommended build” логики: `get_latest_build()` выбирает по `created_at`, а не по semver/channel/release-priority;
  - локальный GUI агента не умеет показывать release/non-release статус, не знает о доступном recommended update и не умеет инициировать self-update с агента;
  - agent UI/runtime status не отдаёт build channel/update availability/update history summary;
  - auto-install для `run_tool` не пишет desired state (`reason=run_tool`), поэтому server-first source of truth для модулей неполный;
  - docs обещают immediate reconcile после `module_state_changed`, но в коде сейчас найден periodic/manual path и follow-up sync, без явного event-triggered reconcile;
  - часть module endpoints (`activate/deactivate/sync/remove/reconcile`, legacy rollback path) всё ещё полагается на `actor_role` из body или hardcoded role вместо полного `AuthContext` + policy/audit.
- Следующий пакет работ:
  1. спроектировать `recommended agent update` contract и semver-aware selection policy;
  2. расширить UI bridge / GUI агента статусом версии, release-меткой и кнопкой update;
  3. выровнять module endpoints по auth/policy/audit;
  4. довести module desired-state + reconcile/event pipeline до server-first convergence;
  5. добавить regression tests на update recommendation, GUI/runtime status contract и module reconcile/auth flows.

## 2026-04-15 In-Place Module/Playbook Refactor

- Implemented in the current path, without a parallel V2:
  - current module manifest normalization now supports canonical semantic tool ids, legacy aliases and output schema while keeping existing `module.tool` modules working;
  - current agent registry/orchestrator now resolves canonical tool ids plus aliases through the existing runtime registry, and `list_tools` / `describe_tool` expose fuller metadata needed for policy/catalog layers;
  - current server tool auto-install path resolves owning module by manifest tool binding instead of assuming `tool_name.split(".", 1)[0]` is always the physical module name;
  - current playbook engine now executes local typed steps (`transform`, `decision`, `report`) inside the existing `playbook_*` tables and step-run model.
- Guardrails kept:
  - builtin screenshot path `screen.collect` and agent-side screen/system regressions were kept green;
  - artifact-heavy flows were not rewritten and remain on the current result/artifact path.
- Unified standards rollout follow-up in the same in-place path:
  - added shared `shared/tool_contracts.py` for canonical risk/lifecycle/error/artifact/dependency/runtime-envelope vocabulary used by both server and agent;
  - tightened server manifest validation with `module_api_version`, `owner_scope`, `contract_version`, `dependencies`, `lifecycle`, `error_codes`, `artifact_types`, `redaction`, `resources`, plus reserved namespace governance;
  - upgraded agent registry/orchestrator to expose the richer tool contract and to emit canonical execution envelope in `data.result` while keeping legacy `ToolResponse` transport shell compatible;
  - rewired builtin `system` and `screen` tools to publish the same contract blocks as managed packs.
- Verification snapshot:
  - passed: `python scripts/verify_workspace.py`
  - passed: `python -m pytest pc_agent/tests/test_registry_and_module_loading.py pc_agent/tests/test_builtin_modules_screen_system.py -v --tb=short`
  - passed: `python -m pytest server/tests/test_playbook_fixes.py::TestPlaybookCapabilityMetadataSource::test_check_tool_available_async_and_spec_metadata server/tests/test_playbook_fixes.py::TestPlaybookTypedLocalSteps::test_if_expr_supports_steps_alias_and_collections server/tests/test_modules_manifest_api.py::test_normalize_manifest_keeps_semantic_tool_name_and_legacy_alias server/tests/test_tool_service_builtin_modules.py -v --tb=short`
  - passed: `python -m pytest pc_agent/tests/test_support_module_packages.py -v --tb=short`
  - passed: `python -m pytest server/tests/test_modules_manifest_api.py::test_normalize_manifest_rejects_duplicate_tool_alias_conflicts server/tests/test_modules_manifest_api.py::test_build_module_package_supports_multi_tool_semantic_names -v --tb=short`
  - blocked externally: DB-backed server pytest requires PostgreSQL access; with `-o asyncio_mode=strict` the suite reaches real DB auth and currently fails at `pg_hba.conf` / test database access from this workstation.

## 2026-04-15 Module Workbench UI

- Added a dedicated module-development workbench inside `/admin` while keeping a single admin shell:
  - static fragment/script: `server/admin_modules_workbench.html`, `server/admin_modules_workbench.js`
  - server APIs: grouped module families, editable draft detail, save-from-UI, preferred-version assignment
  - server-side preferred module version now lives in `server_config` via `app/repos/module_rollout_repo.py`
- Runtime impact:
  - `run_tool` preferred module resolution now respects the same server-side preferred-version assignment as the UI
  - module detail/workbench can reconstruct editable tool fragments from generated archives (`modules/workbench_service.py`)
- Verification:
  - passed: `python -m py_compile ...` for touched server files/tests
  - passed: `node --check server/admin_modules_workbench.js`
  - passed: `python -m pytest server/tests/test_modules_manifest_no_db.py -v --tb=short`
  - passed with shared DB: `python -m pytest -o asyncio_mode=strict server/tests/test_modules_workbench_api.py server/tests/test_tool_service_auto_install_versions.py -v --tb=short`

## 2026-04-16 Modules page workspace refactor

- Refactored the admin `Модули` page into nested workspace tabs:
  - `Разработка модулей`
  - `Список модулей`
  - `Редактор модулей`
  - `Модули на устройствах`
- Rebuilt `Разработка модулей` as a guided authoring flow with four steps:
  1. module scaffold;
  2. tool templates and code;
  3. runtime policies;
  4. validation, rollout settings, API preview, and source explorer.
- Kept a separate advanced editor for full manifest/tool JSON fields so power-user editing stays available without overloading the main authoring path.
- Verification for this refactor:
  - passed: `python scripts/verify_workspace.py`
  - passed: `python -m pytest server/tests/test_modules_workbench_api.py -v --tb=short`

## 2026-04-16 Intake Forms Manual QA

- Scope:
  - versioned request-form packs in admin UI;
  - public `/help` dynamic intake forms;
  - local agent ticket-create dialog with cached form-pack refresh;
  - end-to-end ticket creation with `form_key`, `form_pack_key`, `form_pack_version`, `form_payload`, `ticket_type`.
- Manual check matrix:
  1. Admin constructor:
     - open `/admin`, switch to `Конструктор форм`;
     - confirm current preferred pack/version loads without JS errors;
     - create/edit fields for `printer`, `access`, `site_system`;
     - save a new version and assign it preferred.
  2. Public help form:
     - open `/help`;
     - verify request type cards render from `/public_api/ticket_forms/current`;
     - choose `printer` and confirm `cabinet`, `model`, `printer_number`;
     - choose `access` and confirm `system`, `role`, `approver`;
     - choose `site_system` with site-down issue and confirm conditional `url`, `source_pc`, `scope`;
     - submit a ticket and verify success response.
  3. Local agent dialog:
     - bootstrap local agent runtime;
     - start a named GUI instance via `python scripts/manage_local_agent.py start <name> --gui --ui-port <port>`;
     - open create-ticket dialog and verify the same dynamic forms/conditional fields;
     - submit a ticket and confirm the dialog blocks missing required dynamic fields.
  4. Regression spot-check:
     - confirm classic free-text/title/contacts path still submits;
     - confirm old or missing cached pack falls back to built-in defaults;
     - confirm server accepts unchanged clients without `form_payload`.
- Verification target for this task:
  - `python scripts/verify_workspace.py`
  - `python -m pytest server/tests/test_ticket_form_packs.py server/tests/test_ticket_create_contracts.py server/tests/test_ticket_device_binding.py -v --tb=short`
  - `python -m pytest pc_agent/tests -v --tb=short`
  - browser/manual QA against `http://192.168.100.17:8666/admin`

## 2026-04-16 Agent update normalization

- Scope:
  - server-side rollout recommendation and actionability;
  - agent runtime polling/logging for recommended release;
  - GUI wording for current version vs server rollout;
  - diagnostics for pending/applied/failed update state.
- Root cause captured:
  - `assigned_rollout` older than current agent version was treated as "актуально" instead of actionable rollback;
  - agent GUI badge showed only the local release version, which looked like the server rollout version;
  - runtime status omitted `comparison`, `recommendation_source`, `assigned_rollout`, and local update-state files, so troubleshooting required raw logs/files.
- Current fix wave:
  1. make any assigned-rollout mismatch actionable on the server, including older recommended release;
  2. log recommendation fetch/request details in `pc_agent/ws_agent.py`;
  3. expose pending/history/failure update state through `/ui/agent/status`;
  4. update GUI badge/button/diagnostics wording to distinguish local agent version from server rollout and surface rollback clearly;
  5. sync update docs and targeted tests, then rebuild the Windows release.

## 2026-04-17 Full-system verification wave

- Scope:
  - провести безопасный baseline-прогон по текущему локальному WIP без откатов и принудительной очистки дерева;
  - проверить минимальный канон `verify_workspace`, затем server/agent pytest и доступные локальные runtime/API/browser-smoke;
  - использовать локально запущенный agent, а при необходимости проверить bootstrap/update path штатными скриптами;
  - собрать фактический список багов, регрессий, broken flows и непроверенных зон с привязкой к командам и артефактам.
- Verification target:
  - `python scripts/verify_workspace.py`
  - `python -m pytest server/tests/ -v --tb=short`
  - `python -m pytest pc_agent/tests/ -v --tb=short`
  - локальные проверки через `python scripts/manage_local_agent.py ...`
  - browser/API smoke для доступных UI-flow, если main server/runtime доступны
- Reporting target:
  - отдельно зафиксировать, что прошло;
  - что упало и с какими симптомами;
  - что не удалось проверить;
  - нужен ли rebuild/update локального агента для продолжения.
