## 2026-04-15 module workbench focus

- For module authoring in the admin UI, start with `server/admin_modules_workbench.js`, `server/admin_modules_workbench.html`, `server/modules/handlers.py`, and `server/modules/workbench_service.py`.
- The module workbench now supports template-driven tool creation, inline validation, validate-before-publish preview, preferred-version assignment, rollout-policy settings for preferred versions, and archive-to-code decomposition.
- The server validate endpoint for the workbench is `POST /api/modules/workbench/validate`.
- Preferred-version rollout settings now live in `server/app/repos/module_rollout_repo.py` and are exposed via `GET/PATCH /api/modules/rollout_settings`; in `installed_devices` mode a preferred-version change rewrites desired state and triggers reconcile for matching devices.

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

Если менялся веб:

- browser verification через MCP на `http://192.168.100.17:8666/admin`

Test DB env vars:

- `TEST_DATABASE_ADMIN_URL`
- `TEST_DATABASE_URL`
- `PC_CLIENT_ALLOW_SHARED_TEST_DB`

## Fast map

| Topic | Open first | Then |
|------|------------|------|
| Protocol V3 / handshake | `server/websocket/agent_handshake.py`, `server/websocket/agent_services.py`, `pc_agent/ws_agent.py`, `pc_agent/ws_agent_runtime_helpers.py` | `server/docs/PROTOCOL_V3.md`, `pc_agent/docs/PROTOCOL_V3.md` |
| Tool execution / operations | `server/tools/service.py`, `server/tools/handlers.py`, `server/app/services/operation_service.py`, `pc_agent/core/orchestrator.py`, `pc_agent/core/orchestrator_collect_helpers.py`, `pc_agent/core/orchestrator_job_helpers.py` | `server/docs/TOOL_CALL_STARTED_INVARIANT.md`, `pc_agent/docs/CODEMAP.md` |
| Agent updates / recommended version / rollout policy | `server/agents/agent_builds_handlers.py`, `server/app/repos/agent_rollout_repo.py`, `server/routes.py`, `pc_agent/ws_agent.py`, `pc_agent/ui_bridge/api_server.py`, `pc_agent/ui_gui/main_window.py` | `server/docs/AGENT_UPDATES_API.md`, `pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md`, `pc_agent/docs/AGENT_UPDATE_WORKFLOW.md` |
| Modules / desired state / reconcile / workbench | `server/modules/handlers.py`, `server/modules/workbench_service.py`, `server/tools/service.py`, `server/websocket/outbox_ingest_components.py`, `server/modules/reconcile.py`, `server/admin_modules_workbench.js`, `pc_agent/core/module_manager.py`, `shared/tool_contracts.py` | `server/docs/MODULES_API.md`, `server/docs/MODULE_AUTHORING_RULES.md`, `server/docs/REGISTRY_PUBLICATION_RULES.md`, `server/docs/RUNTIME_EXECUTION_CONTRACT.md`, `pc_agent/docs/MODULES.md` |
| Ticket flows / helpdesk | `server/tickets/handlers.py`, `server/tickets/create_flow.py`, `server/tickets/workflow_service.py` | `server/docs/TICKET_SYSTEM.md`, `server/docs/CODEMAP.md` |
| Auth / token bootstrap | `server/auth/`, `server/websocket/agent_handshake.py`, `pc_agent/auth/token_source.py`, `pc_agent/auth/connection_request.py` | `server/docs/SECURITY_AND_AUTH.md`, `pc_agent/docs/AUTHENTICATION.md` |
| Agent runtime / UI bridge | `pc_agent/ws_agent.py`, `pc_agent/ws_agent_runtime_helpers.py`, `pc_agent/ui_bridge/api_server.py`, `pc_agent/ui_gui/chat_panel.py` | `pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md`, `pc_agent/docs/CODEMAP.md` |
| Release / deploy / CI | `scripts/task_intake.py`, `scripts/verify_workspace.py`, `scripts/run_ci_suite.py`, `scripts/deploy_workspace_to_remote.py`, `scripts/release_server_to_remote.py` | `AGENTS.md`, `PLANS.md`, `docs/LOCAL_WORKFLOW.md` |

## When to update this file

Обновляйте `docs/QUICK_LOOKUP.md`, если меняются:

- ключевые entrypoints;
- канонический intake/test/release workflow;
- карта основных тем и стартовых файлов;
- статус canonical vs historical docs.
