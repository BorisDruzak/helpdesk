## 2026-04-19 agent runtime and launcher flow

- Local launcher/runtime work now starts from `pc_agent/launcher_portable_main.py`, `pc_agent/ws_agent.py`, `pc_agent/ui_bridge/api_server.py`, `pc_agent/ui_gui/main.py`, `pc_agent/ui_gui/main_window.py`, and `pc_agent/ui_gui/automation_controller.py`.
- Recommended-update diagnostics and local update state are surfaced through `pc_agent/ws_agent.py`, `pc_agent/ui_bridge/api_server.py`, `pc_agent/ui_gui/main_window.py`, and `pc_agent/docs/AGENT_UPDATE_WORKFLOW.md`.
- Agent-side observer correlation for tech drilldown now uses `pc_agent/core/action_trace.py` plus the `search_action_trace` RPC in `pc_agent/ws_agent.py`; admin tech trace detail requests agent actions via `include_agent_actions=1`, and the agent now emits guaranteed module-level execution breakdown (`module.resolve`, `module.execute`) even when a tool module has no custom runtime audit hooks.
- New module authoring canon: every new `BaseCollector` tool must emit observer breadcrumbs through `trace_span(...)` / `trace_event(...)`; generated workbench modules now scaffold this automatically in `server/utils/module_builder.py`, а `server/utils/module_observer_contract.py` + `python scripts/verify_workspace.py` теперь валят CI, если mandatory `tool.entry` span отсутствует.
- Live observer canary suite для опасных flow лежит в `python scripts/run_observer_canary_suite.py`: consent approve/deny/timeout, module install/update/remove, retry exhaustion, agent disconnect during operation, ws ack/nack/replay.
- Local Windows launcher canary flow still goes through `python scripts/manage_local_agent.py start <name> --launcher`, with release artifacts built by `python pc_agent/build_windows_release_v2.py`.
- Server/control runtime wrappers (`scripts/run_server.py`, `scripts/run_control_plane.py`) now always bootstrap repo-root import visibility for shared packages like `shared.redaction`; when debugging Linux boot failures, treat those wrappers as canonical entrypoints instead of ad-hoc `python server/server.py`.

## 2026-04-16 intake forms

- Typed requester intake now lives in `server/tickets/form_catalog.py`, `server/tickets/form_pack_handlers.py`, `server/help.js`, `server/admin_ticket_forms_builder.js`, and `pc_agent/ui_gui/chat_panel.py`.
- Observer trace overlay now lives in `server/observer/service.py`, `server/observer/runtime.py`, `server/tech/handlers.py`, `server/app/db/models.py`, `server/websocket/agent_services.py`, and `pc_agent/core/action_trace.py`; observer v2 adds canonical ticket-root traces, first-class degradation queries (`duration > N`, timeout/retry/slow rate, `root_kind` flow filtering), automatic historical backfill, full client-update tracing from request to launcher apply, and isolated short-lived projection sessions so admin/support observer polling does not hold idle DB transactions while waiting on per-trace locks.
- Canonical observer docs now live in `server/docs/OBSERVER_LAYER.md` and `server/docs/OBSERVER_AUTHORING_RULES.md`; quick diagnostics use `GET /api/admin/tech/observer/quick`, the new typed admin surface now includes `GET /api/web/admin/observer/quick`, `GET /api/web/admin/observer/traces`, and `GET /api/web/admin/observer/traces/{trace_id}`, and support/ticket observer summary uses `GET /api/tickets/{ticket_id}/observer`. That ticket summary must report counts over the full ticket trace set and expose both global `occurrences_count` and ticket-local `ticket_occurrences_count`. Canonical operator trace UX is the `/support` workspace drawer tab `Трасса`, while `/app/admin` now owns the typed observer overview plus trace drilldown; legacy `/ticket` remains a separate ticket shell, not the primary observer surface.
- Browser polling for `/admin` tech and `/support` workspace should stay single-flight: if you touch `server/admin.js` or `server/support.js`, keep observer refresh non-overlapping so stale tabs cannot avalanche `observer/quick` and ticket-summary requests into the DB pool.
- The admin `/admin` shell has a dedicated `Конструктор форм` tab for versioned request-form packs, served by `/api/ticket_forms/current`, `/public_api/ticket_forms/current`, and `/api/ticket_forms/packs/*`.
- Public `/help` and the local agent ticket dialog now submit `form_key`, `form_payload`, and `ticket_type`; the agent caches the latest form pack in its local data root and refreshes only when the server reports a newer version.

## 2026-04-15 module workbench focus

- For module authoring in the admin UI, start with `server/admin_modules_workbench.js`, `server/admin_modules_workbench.html`, `server/modules/handlers.py`, and `server/modules/workbench_service.py`.
- The module workbench now supports template-driven tool creation, inline validation, validate-before-publish preview, preferred-version assignment, rollout-policy settings for preferred versions, ZIP archive import into the registry, archive-to-code decomposition, and delete-from-registry actions from the module list.
- The admin `Модули` page is split into inner tabs: `Разработка модулей`, `Список модулей`, `Редактор модулей`, and `Модули на устройствах`; the authoring flow inside the first tab is a 4-step wizard.
- Everyday module authoring no longer starts from raw JSON: platforms are selected from supported values, requirements are entered line-by-line, and params/output schemas can be assembled from validated blueprint rows before publish.
- The server validate endpoint for the workbench is `POST /api/modules/workbench/validate`.
- Preferred-version rollout settings now live in `server/app/repos/module_rollout_repo.py` and are exposed via `GET/PATCH /api/modules/rollout_settings`; in `installed_devices` mode a preferred-version change rewrites desired state, triggers reconcile for matching devices, and then refreshes inventory/toolset so the admin UI converges.

# QUICK_LOOKUP

Короткий канонический навигатор по проекту `pc_client`.

## С чего начинать

1. Для нетривиальной задачи сначала запустите `python scripts/task_intake.py`.
2. Если задача описана словами, используйте `python scripts/task_intake.py --task "<описание>"`.
3. Если уже важен diff, используйте `python scripts/task_intake.py` без аргументов.
4. Если нужна точечная локальная навигация после intake:
   - `python scripts/agent_find.py "<pattern>" --dir server|pc_agent`
   - `python scripts/diff_context.py`
5. Для длинной задачи синхронно ведите `PLANS.md`.

Routing-логика живёт в:

- `scripts/task_intake.py`
- `scripts/navigation_catalog.py`

Этот файл остаётся human-facing индексом и не должен дублировать весь routing.

## Canonical docs only

Источник истины для структуры и workflow:

- `AGENTS.md`
- `docs/QUICK_LOOKUP.md`
- `server/docs/CODEMAP.md`
- `pc_agent/docs/CODEMAP.md`
- protocol/auth/runtime/update docs рядом с кодом

Historical docs больше не канон:

- `docs/TICKET_CRM_GAP_ANALYSIS.md`
- `docs/TICKET_AND_AGENT_UPDATE_ROADMAP.md`
- `docs/BOTTLENECKS_AND_RISKS.md`

Их архивные копии лежат в `docs/archive/`.

## Truth baseline

Минимальный baseline перед commit:

- `python scripts/verify_workspace.py`
- `python -m pytest server/tests/ ...`
- `python -m pytest pc_agent/tests/ ...`

Если задача затрагивает release/deploy:

- `python scripts/run_ci_suite.py`

Если задача затрагивает `webapp/` или frontend bundle pipeline:

- `python scripts/bootstrap_web_toolchain.py`

Если менялся веб:

- browser verification через MCP на `http://192.168.100.17:8666/admin`

Test DB env vars:

- `TEST_DATABASE_ADMIN_URL`
- `TEST_DATABASE_URL`
- `PC_CLIENT_ALLOW_SHARED_TEST_DB`

Windows note:

- On Windows, if `TEST_DATABASE_URL` and `TEST_DATABASE_ADMIN_URL` are not set, server DB-backed pytest now defaults to shared `pc_support_test`.
- In that default mode the harness opens a local SSH tunnel to PostgreSQL using `C:\Users\admin-2\.ssh\pc_client_altserver_ed25519`.
- In shared-DB fallback mode the harness now terminates stale `pc_support_test` backends before `TRUNCATE` and uses a short lock timeout, so leaked sessions fail fast instead of hanging the suite.
- For isolated ephemeral test DBs from Windows, set `TEST_DATABASE_ADMIN_URL` explicitly.

## Fast map

| Topic | Open first | Then |
|------|------------|------|
| Protocol V3 / handshake | `server/websocket/agent_handshake.py`, `server/websocket/agent_services.py`, `pc_agent/ws_agent.py`, `pc_agent/ws_agent_runtime_helpers.py` | `server/docs/PROTOCOL_V3.md`, `pc_agent/docs/PROTOCOL_V3.md` |
| New web workspaces / typed web boundary | `webapp/src/main.tsx`, `webapp/src/app/router.tsx`, `webapp/src/app/layouts/app-shell.tsx`, `webapp/src/features/auth/session-provider.tsx`, `webapp/src/features/auth/login-page.tsx`, `webapp/src/features/queues/api.ts`, `webapp/src/features/queues/support-workspace.tsx`, `webapp/src/features/admin/api.ts`, `webapp/src/features/admin/admin-workspace.tsx`, `webapp/src/features/agent-updates/api.ts`, `webapp/src/features/agent-updates/device-update-panel.tsx`, `webapp/src/features/modules/api.ts`, `webapp/src/features/modules/modules-panel.tsx`, `webapp/src/features/tech/api.ts`, `webapp/src/features/tech/observer-quick-panel.tsx`, `webapp/src/features/tech/observer-trace-drilldown.tsx`, `webapp/src/pages/admin/index.tsx`, `webapp/playwright.config.ts`, `webapp/tests/support-workspace.spec.ts`, `webapp/tests/admin-workspace.spec.ts`, `webapp/tests/fixtures/support_fixture_server.py`, `server/web_api/session_handlers.py`, `server/web_api/support_handlers.py`, `server/web_api/admin_handlers.py`, `server/web_api/realtime_handlers.py`, `server/static_pages/webapp_assets.py`, `server/routes.py` | `docs/superpowers/specs/2026-04-20-admin-support-web-rearchitecture-design.md`, `docs/superpowers/plans/2026-04-20-admin-support-web-rearchitecture.md`, `server/docs/SECURITY_AND_AUTH.md`, `server/docs/OBSERVER_LAYER.md`; support wave now also includes `GET /api/web/support/tickets/{ticket_id}/tools`, `POST /api/web/support/tickets/{ticket_id}/tools/run`, tool events in the typed timeline, а admin wave 1 теперь кроме `GET /api/web/admin/devices` добавляет typed device update surface `GET /api/web/admin/devices/{device_id}/updates` + `POST /api/web/admin/devices/{device_id}/updates/run`, device-scoped observer slices `GET /api/web/admin/observer/quick`, `GET /api/web/admin/observer/traces` и `GET /api/web/admin/observer/traces/{trace_id}`, а также typed modules registry/actions `GET /api/web/admin/modules`, `PATCH /api/web/admin/modules/rollout_settings` и `PATCH /api/web/admin/modules/{module_name}/preferred`, которые кормят русскоязычную панель `Реестр модулей` в `/app/admin` с preferred-version policy, family-level validation/preflight summary и операциями назначения preferred-версии через общий fixture-server |
| Tool execution / operations | `server/tools/service.py`, `server/tools/handlers.py`, `server/app/services/operation_service.py`, `pc_agent/core/orchestrator.py`, `pc_agent/core/orchestrator_collect_helpers.py`, `pc_agent/core/orchestrator_job_helpers.py` | `server/docs/TOOL_CALL_STARTED_INVARIANT.md`, `pc_agent/docs/CODEMAP.md` |
| Observer traces / tech drilldown | `server/observer/service.py`, `server/observer/runtime.py`, `server/tech/handlers.py`, `server/app/db/models.py`, `server/websocket/agent_services.py`, `pc_agent/core/action_trace.py`, `pc_agent/core/orchestrator.py` | `server/docs/OBSERVER_LAYER.md`, `server/docs/OBSERVER_AUTHORING_RULES.md`, `server/docs/CODEMAP.md`, `.cursor/skills/pc-client-observer-diagnostics/SKILL.md` |
| Agent updates / recommended version / rollout policy | `server/agents/agent_builds_handlers.py`, `server/app/repos/agent_rollout_repo.py`, `server/routes.py`, `pc_agent/ws_agent.py`, `pc_agent/ui_bridge/api_server.py`, `pc_agent/ui_gui/main_window.py` | `server/docs/AGENT_UPDATES_API.md`, `pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md`, `pc_agent/docs/AGENT_UPDATE_WORKFLOW.md` |
| Modules / desired state / reconcile / workbench | `server/modules/handlers.py`, `server/modules/workbench_service.py`, `server/web_api/admin_handlers.py`, `server/tools/service.py`, `server/websocket/outbox_ingest_components.py`, `server/modules/reconcile.py`, `server/admin_modules_workbench.js`, `webapp/src/features/modules/modules-panel.tsx`, `pc_agent/core/module_manager.py`, `shared/tool_contracts.py` | `server/docs/MODULE_CREATION_GUIDE.md`, `server/docs/MODULES_API.md`, `server/docs/MODULE_AUTHORING_RULES.md`, `server/docs/REGISTRY_PUBLICATION_RULES.md`, `server/docs/RUNTIME_EXECUTION_CONTRACT.md`, `pc_agent/docs/MODULES.md`; новый typed admin surface теперь не только читает `GET /api/web/admin/modules`, но и ведёт `PATCH /api/web/admin/modules/rollout_settings` и `PATCH /api/web/admin/modules/{module_name}/preferred`, чтобы `/app/admin` умел менять preferred-version policy и preferred assignment без legacy workbench/editor shell |
| Ticket flows / helpdesk | `server/tickets/handlers.py`, `server/tickets/create_flow.py`, `server/tickets/workflow_service.py` | `server/docs/TICKET_SYSTEM.md`, `server/docs/CODEMAP.md` |
| Auth / token bootstrap | `server/auth/`, `server/websocket/agent_handshake.py`, `pc_agent/auth/token_source.py`, `pc_agent/auth/connection_request.py`, `pc_agent/launcher_portable_main.py` | `server/docs/SECURITY_AND_AUTH.md`, `pc_agent/docs/AUTHENTICATION.md` |
| Agent runtime / UI bridge | `pc_agent/ws_agent.py`, `pc_agent/ws_agent_runtime_helpers.py`, `pc_agent/ui_bridge/api_server.py`, `pc_agent/ui_gui/chat_panel.py` | `pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md`, `pc_agent/docs/CODEMAP.md` |
| Release / deploy / CI | `scripts/task_intake.py`, `scripts/bootstrap_web_toolchain.py`, `scripts/verify_workspace.py`, `scripts/run_ci_suite.py`, `scripts/run_observer_canary_suite.py`, `scripts/deploy_workspace_to_remote.py`, `scripts/release_server_to_remote.py` | `AGENTS.md`, `PLANS.md`, `docs/LOCAL_WORKFLOW.md` |

## When to update this file

Обновляйте `docs/QUICK_LOOKUP.md`, если меняются:

- ключевые entrypoints;
- канонический intake/test/release workflow;
- карта основных тем и стартовых файлов;
- статус canonical vs historical docs.
- observer quick diagnosis, trace APIs, dangerous-flow coverage или обязательные observer docs/skills.
