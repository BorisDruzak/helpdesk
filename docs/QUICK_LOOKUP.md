# QUICK_LOOKUP

Короткий навигационный индекс для `pc_client`: с чего начинать поиск, какие файлы открывать первыми и какие документы проверять до широкого grep.

## Как использовать

1. Если задача начинается с диффа, сначала запустите `python scripts/diff_context.py`.
2. Если тема пока неясна, откройте нужный `CODEMAP` и этот файл:
   - `server/docs/CODEMAP.md`
   - `pc_agent/docs/CODEMAP.md`
3. Для точечного поиска используйте `python scripts/agent_find.py "<ключевое слово>"`.
4. Перед коммитом проверяйте, не забыты ли docs/CODEMAP: `python scripts/docs_drift_check.py`.

## Темы

| Тема | Открыть сначала | Связанные документы | Быстрые команды |
|------|------------------|---------------------|-----------------|
| Protocol V3 / handshake | `server/websocket/agent_handshake.py`, `server/websocket/agent_services.py`, `pc_agent/ws_agent.py`, `pc_agent/core/sender.py` | `server/docs/PROTOCOL_V3.md`, `pc_agent/docs/PROTOCOL_V3.md`, `server/docs/COMMAND_RESULT_LIFECYCLE.md`, `server/docs/TOOL_CALL_STARTED_INVARIANT.md` | `python scripts/agent_find.py "handshake"`, `python scripts/agent_find.py "outbox_ack"` |
| `run_tool` / consent | `server/tools/service.py`, `server/tools/handlers.py`, `server/app/services/operation_service.py`, `pc_agent/core/orchestrator.py` | `server/docs/TOOL_CALL_STARTED_INVARIANT.md`, `server/docs/CODEMAP.md`, `pc_agent/docs/CODEMAP.md` | `python scripts/agent_find.py "run_tool" --dir server` |
| Auth / token bootstrap | `server/auth/`, `server/app/repos/auth_tokens_repo.py`, `pc_agent/auth/token_source.py`, `pc_agent/core/identity.py` | `server/docs/SECURITY_AND_AUTH.md`, `pc_agent/docs/AUTHENTICATION.md` | `python scripts/agent_find.py "auth" --dir server`, `python scripts/agent_find.py "token" --dir pc_agent` |
| Tickets / chat / queue | `server/tickets/handlers.py`, `server/tickets/workflow_service.py`, `server/chat/`, `server/api/events.py` | `server/docs/TICKET_SYSTEM.md`, `server/docs/CHAT_MESSAGE_CONTRACT.md`, `server/docs/CODEMAP.md` | `python scripts/agent_find.py "ticket" --dir server`, `python scripts/agent_find.py "chat" --dir server` |
| Modules / reconcile | `server/modules/service.py`, `server/websocket/modules_sync.py`, `pc_agent/core/module_manager.py`, `pc_agent/core/registry.py` | `server/docs/MODULES_API.md`, `server/docs/MODULES_DRIFT_AND_SNAPSHOTS.md`, `pc_agent/docs/MODULES.md` | `python scripts/agent_find.py "modules" --dir server`, `python scripts/agent_find.py "module_manager" --dir pc_agent` |
| Server UI / admin pages | `server/support.js`, `server/admin.js`, `server/tech/handlers.py`, `server/ticket.js`, `server/static_pages/`, `server/routes.py` | `server/docs/CODEMAP.md` | `python scripts/diff_context.py`, затем browser check через MCP на `http://192.168.100.17:8666/admin` |
| Agent GUI / `ui_bridge` | `pc_agent/ui_gui/main_window.py`, `pc_agent/ui_gui/chat_panel.py`, `pc_agent/ui_bridge/api_server.py`, `pc_agent/ui_bridge/event_bus.py` | `pc_agent/docs/CODEMAP.md` | `python scripts/agent_find.py "ui bridge" --dir pc_agent` |
| Database / migrations | `server/app/db/models.py`, `server/app/db/migrations/versions/`, `pc_agent/core/database.py` | `server/docs/DATABASE.md`, `pc_agent/docs/DATABASE.md` | `python scripts/agent_find.py "alembic" --dir server`, `python scripts/agent_find.py "DB_SCHEMA_VERSION" --dir pc_agent` |
| Release / deploy / smoke | `scripts/verify_workspace.py`, `scripts/release_server_to_remote.py`, `scripts/manage_remote_stack.py` | `AGENTS.md`, оба `CODEMAP` | `python scripts/verify_workspace.py`, `python scripts/release_server_to_remote.py` |

## Когда обновлять этот файл

Обновляйте `docs/QUICK_LOOKUP.md`, если меняются:

- ключевые точки входа, стартовые файлы или канонический путь для темы;
- cross-cutting темы, по которым раньше приходилось долго искать руками;
- скрипты навигации и проверки (`agent_find.py`, `diff_context.py`, `docs_drift_check.py`, `verify_workspace.py`);
- общие правила быстрого поиска, которые полезны и серверу, и агенту.
