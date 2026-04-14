# QUICK_LOOKUP

Короткий канонический навигатор по проекту `pc_client`.

## С чего начинать

1. Если задача начинается с локального diff, сначала запустите `python scripts/diff_context.py`.
2. Если затронуты и сервер, и агент, сначала откройте оба CODEMAP:
   - `server/docs/CODEMAP.md`
   - `pc_agent/docs/CODEMAP.md`
3. Для точечного поиска используйте `python scripts/agent_find.py "<pattern>" --dir server|pc_agent`.
4. Для длинной задачи синхронно ведите `PLANS.md`.

## Canonical docs only

Источник истины для структуры и runtime:

- `AGENTS.md`
- `docs/QUICK_LOOKUP.md`
- `server/docs/CODEMAP.md`
- `pc_agent/docs/CODEMAP.md`
- protocol/auth/runtime/update docs рядом с кодом

Historical docs больше не канон:

- `docs/TICKET_CRM_GAP_ANALYSIS.md`
- `docs/TICKET_AND_AGENT_UPDATE_ROADMAP.md`
- `docs/BOTTLENECKS_AND_RISKS.md`

Их актуальные архивные копии лежат в `docs/archive/`.

## Truth baseline

Минимальный production-hardening baseline:

- `python scripts/verify_workspace.py`
- `python -m pytest pc_agent/tests -m "not manual"`
- `python -m pytest server/tests -m "not manual"`

CI / release:

- `python scripts/run_ci_suite.py`
- `python scripts/run_ci_in_temp_workspace.py`
- artifacts layout: `artifacts/ci/<sha>/summary.json`, `junit*.xml`, `logs/...`
- release/deploy scripts по умолчанию требуют green CI artifact

Test DB env vars:

- `TEST_DATABASE_ADMIN_URL`
- `TEST_DATABASE_URL`
- `PC_CLIENT_ALLOW_SHARED_TEST_DB`

## Fast map

| Topic | Open first | Then |
|------|------------|------|
| Protocol V3 / handshake | `server/websocket/agent_handshake.py`, `server/websocket/agent_services.py`, `pc_agent/ws_agent.py`, `pc_agent/ws_agent_runtime_helpers.py` | `server/docs/PROTOCOL_V3.md`, `pc_agent/docs/PROTOCOL_V3.md` |
| Tool execution / operations | `server/tools/service.py`, `server/tools/handlers.py`, `server/app/services/operation_service.py`, `pc_agent/core/orchestrator.py`, `pc_agent/core/orchestrator_collect_helpers.py`, `pc_agent/core/orchestrator_job_helpers.py` | `server/docs/TOOL_CALL_STARTED_INVARIANT.md` |
| Ticket flows / helpdesk | `server/tickets/handlers.py`, `server/tickets/create_flow.py`, `server/tickets/workflow_service.py` | `server/docs/TICKET_SYSTEM.md`, `server/docs/CODEMAP.md` |
| Auth / token bootstrap | `server/auth/`, `server/websocket/agent_handshake.py`, `pc_agent/auth/token_source.py`, `pc_agent/auth/connection_request.py` | `server/docs/SECURITY_AND_AUTH.md`, `pc_agent/docs/AUTHENTICATION.md` |
| Agent runtime / UI bridge | `pc_agent/ws_agent.py`, `pc_agent/ws_agent_runtime_helpers.py`, `pc_agent/ui_bridge/api_server.py`, `pc_agent/ui_gui/chat_panel.py` | `pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md`, `pc_agent/docs/CODEMAP.md` |
| Release / deploy / CI | `scripts/run_ci_suite.py`, `scripts/run_ci_in_temp_workspace.py`, `scripts/deploy_workspace_to_remote.py`, `scripts/release_server_to_remote.py` | `AGENTS.md`, `PLANS.md` |

## When to update this file

Обновляйте `docs/QUICK_LOOKUP.md`, если меняются:

- ключевые entrypoints;
- канонический test/release workflow;
- структура CODEMAP navigation;
- статус canonical vs historical docs.
