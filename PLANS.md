# PLANS.md

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
