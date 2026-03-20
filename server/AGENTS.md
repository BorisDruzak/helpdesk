# AGENTS.md — инструкции для Codex и Cursor (server)

Канон инструкций и доков — **локальная рабочая копия** монорепо; шара `\\192.168.100.17\NTFS_Share\pc_client` и Linux `/var/chat_bot/pc_client` — зеркала. См. корневой `AGENTS.md`.

## Главное про сервер

- Роль: relay-сервер между Web UI и агентами по WebSocket Protocol V3 (`ws_ticket_v3`).
- WS endpoints:
  - `/ws` — агенты (handshake обязателен: version/capabilities/token)
  - `/ws_ui` — UI (первое сообщение `ui_hello` с токеном)

## Документация, с которой начинать

- `docs/README.md`
- `docs/SECURITY_AND_AUTH.md`
- `docs/PROTOCOL_V3.md` (серверные требования + ссылка на полную спецификацию у агента)

## CODEMAP

- Каноническая карта сервера — **только** `docs/CODEMAP.md` в этом дереве (путь от корня монорепо: `server/docs/CODEMAP.md`).
- Перед анализом/правками сначала смотреть этот файл.
- При изменении структуры серверного кода, маршрутов или runtime-потоков **обязательно** обновлять `server/docs/CODEMAP.md`. Критерии — в конце файла и в `.cursor/rules/codemap.mdc`.

## Единый URL GUI

- Для открытия веб-интерфейса сервера использовать **только**: `http://192.168.100.17:8666/admin`.
- Не использовать `127.0.0.1` и альтернативные URL без явного запроса пользователя.

## Инварианты, которые нельзя ломать

- `command_result` всегда завершает операцию; `outbox=delivered` означает “доставлено/обработано”, а не “успех выполнения”:
  - успех/ошибка/consent_required → `device_outbox: delivered`, а `operations` отражает результат выполнения
  - таймаут → `device_outbox: failed` с `TIMEOUT` (см. `docs/COMMAND_RESULT_LIFECYCLE.md`)
- `tool_call_started` создаётся сервером до отправки команды (см. `docs/TOOL_CALL_STARTED_INVARIANT.md`)


