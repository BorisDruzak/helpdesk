# AGENTS.md — инструкции для Codex (pc_client)

## Где находится код

- Сервер: `\\192.168.100.17\NTFS_Share\pc_client\server`
- Агент: `\\192.168.100.17\NTFS_Share\pc_client\pc_agent`

При работе по задаче считаем эти две директории источником истины. Если в рабочем каталоге открыт другой проект, сначала переключаемся на нужную директорию.

## Документация (источник истины)

- Сервер: `\\192.168.100.17\NTFS_Share\pc_client\server\docs`
- Агент: `\\192.168.100.17\NTFS_Share\pc_client\pc_agent\docs`

Если правим протокол/контракты — обновляем документацию синхронно с кодом.

## CODEMAP (навигация по кодовой базе)

- Карта кода сервера: `server/docs/CODEMAP.md`.
- Карта кода агента: `pc_agent/docs/CODEMAP.md`.
- Для быстрого понимания структуры/точек входа сначала открывать соответствующий `CODEMAP.md`.
- При изменении структуры кода, маршрутов, ключевых модулей или потоков выполнения **обязательно** обновлять соответствующий `CODEMAP.md` синхронно с кодом. Критерии «когда обновлять» — в `.cursor/rules/codemap.mdc` и в разделах «Когда обновлять этот CODEMAP» в конце каждого CODEMAP.

## Критичные инварианты Protocol V3 (ws_ticket_v3)

- **Контракт:** полная спецификация — `pc_agent/docs/PROTOCOL_V3.md`; требования сервера и коды ошибок — `server/docs/PROTOCOL_V3.md` (дата обновления в документе). При расхождении приоритет у серверной документации для серверного кода, у агентской — для агента.
- Тип события определяется ТОЛЬКО по `device_seq` vs `agent_seq` (а не по `ticket_id`):
  - `device_event` ⇔ `device_seq IS NOT NULL AND agent_seq IS NULL`
  - `ticket_event` ⇔ `agent_seq IS NOT NULL AND device_seq IS NULL`
- Сервер на handshake требует `protocol_version === "ws_ticket_v3"`, обязательные capabilities (`protocol_v3`, `envelope_v3`, `outbox_ack_v3`) и token (см. `server/docs/PROTOCOL_V3.md`).
- `device_id` для сессии берётся сервером из записи токена в БД (payload не является источником истины).
- `tool_call_started` создаётся сервером до отправки `run_tool` и идемпотентен по `(ticket_id, operation_id, event_type)` (см. `server/docs/TOOL_CALL_STARTED_INVARIANT.md`).

## Безопасность

- Не логировать сырой токен. Допустимо только префикс.
- Роли/actor контекст берём только из проверенного токена и `AuthContext` (см. `server/docs/SECURITY_AND_AUTH.md`).

## Подсказка по контексту для Codex

Когда задача про:
- протокол/WS: начать с `pc_agent/docs/PROTOCOL_V3.md` и `server/docs/PROTOCOL_V3.md`
- аутентификацию: `server/docs/SECURITY_AND_AUTH.md` и `pc_agent/docs/AUTHENTICATION.md`
- outbox/ACK: `pc_agent/docs/DATABASE.md`, `pc_agent/docs/SENDER.md`, `server/docs/COMMAND_RESULT_LIFECYCLE.md`
- чат/сообщения: `server/docs/CHAT_MESSAGE_CONTRACT.md`
- модули: `server/docs/MODULES_API.md`, `server/docs/MODULES_DRIFT_AND_SNAPSHOTS.md`, `pc_agent/docs/MODULES.md`
- playbook/runbook: `server/docs/PLAYBOOK_*.md`, `server/docs/PLAYBOOK_API.md`, `server/docs/RUNBOOK_*.md`
- артефакты: `server/docs/ARTIFACTS_API.md`
- узкие места и риски: `docs/BOTTLENECKS_AND_RISKS.md`

Автоматизация (перезапуск сервера/агента, тесты в браузере, вызов run_tool): `.cursor/rules/automation.mdc`, задачи в `.vscode/tasks.json`. Запуск/остановка/перезапуск — только через скрипты `scripts/run_server.py`, `scripts/stop_server.py`, `scripts/restart_server.py` (и аналогично `run_agent.py`, `stop_agent.py`, `restart_agent.py`), чтобы остановка работала по PID без pkill. Тесты: `scripts/smoke_test.py`, `scripts/admin_run_tool.py`. Поиск по коду (один вызов вместо нескольких grep): `python scripts/agent_find.py "<шаблон>"` (опции: `--dir server|pc_agent`, `-n N`); см. `docs/CURSOR_TOKEN_EFFICIENCY.md`.

## Единый URL веб-интерфейса

- Для браузерных проверок использовать **только**: `http://192.168.100.17:8666/admin`.
- Не использовать `127.0.0.1` или другие адреса без явного запроса пользователя.

## Миграции PostgreSQL

- Обновления и миграции БД проводить **самостоятельно**: при наличии MCP с доступом к PostgreSQL на запись — применять миграции через MCP; иначе — из каталога `server` выполнять `alembic upgrade head` (см. `server/docs/DATABASE.md`, `server/docs/README.md`). SQL-скрипты в `server/docs/migrations/` — при необходимости применять вручную или через MCP. После изменений схемы при необходимости проверять состояние БД (MCP или psql).

## Браузер (GUI сервера)

- Изменения в веб-интерфейсе сервера (админка, страницы тикетов, статика) **обязательно** проверять в браузере через MCP (navigate, snapshot, click, fill). Не ограничиваться только smoke_test или перезапуском сервера.

## Остановка сервера после проверок

- После запуска сервера и всех запланированных проверок (тесты, сценарии в браузере, ручные проверки) **обязательно** останавливать сервер: `python scripts/stop_server.py`. Не оставлять процесс запущенным без явной необходимости пользователя.

## Кодировка и символы

- Во всех ответах, документации и изменениях файлов использовать корректную UTF-8 кодировку.
- В Python-коде не полагаться на системную кодировку Windows: при чтении/записи текстовых файлов явно указывать `encoding="utf-8"` (или `Path.read_text(..., encoding="utf-8")` / `Path.write_text(..., encoding="utf-8")`).
- Для вывода/обработки текста из subprocess на Windows по возможности не полагаться на локальную ANSI/OEM кодировку: предпочтительно работать с байтами и декодировать явно в UTF-8 с контролируемым fallback.
- `mojibake` (кракозябры вида `Р...`, `Ð...`, `Ñ...`) **запрещён** в ответах и файлах проекта.
- Если в тексте обнаружен `mojibake`, перед отправкой/сохранением обязательно исправлять кодировку и перечитывать файл в UTF-8.
- Перед отправкой сообщений на русском проверять отсутствие mojibake/«кракозябр» вида `Р...`.
- Не использовать инструменты/команды с несуществующими namespace без проверки доступности в текущей среде.
