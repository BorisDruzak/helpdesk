# AGENTS.md — инструкции для Codex и Cursor (pc_client)

## Источник истины

- Все правки, проверки, временные файлы и коммиты делать только в локальной рабочей копии `C:\Users\admin-2\CodexProjects\pc_client`.
- Сетевая шара `\\192.168.100.17\NTFS_Share\pc_client` — зеркало и точка обмена, не основная среда редактирования.
- Linux working copy `/var/chat_bot/pc_client` — стенд и зеркало закоммиченного состояния ветки после deploy.
- Для кода и документации канон один: локальная Windows-копия.

## Обязательный рабочий цикл

1. Открывать и менять код только в локальной копии.
2. Если задача длинная, затрагивает несколько подсистем или требует нескольких заходов, завести и поддерживать `PLANS.md`.
3. Перед правками собрать контекст:
   - если есть diff или локальные правки — `python scripts/diff_context.py`;
   - если задача широкая — `docs/QUICK_LOOKUP.md`;
   - если тема уже ясна — соответствующий `CODEMAP` и затем точечный `python scripts/agent_find.py "<паттерн>" --dir server|pc_agent`.
4. При изменении структуры, маршрутов, контрактов или ключевых потоков синхронно обновлять код, docs и канонический `CODEMAP`.
5. Перед коммитом прогонять минимум `python scripts/verify_workspace.py`, затем релевантные `pytest` и нужные smoke/browser-проверки.
6. После локальной проверки делать локальный commit.
7. Для выкладки на Linux использовать только штатные скрипты:
   - `python scripts/deploy_workspace_to_remote.py`
   - `python scripts/release_server_to_remote.py`
   - `python scripts/manage_remote_stack.py start|stop|restart|status|smoke|logs server|agent|control`
8. После всех проверок на Linux останавливать сервер: `python scripts/manage_remote_stack.py stop server`, если пользователь явно не просил оставить его запущенным.
9. В GitHub публиковать только проверенное состояние.

## Контекст и слои

- Root `AGENTS.md` хранит только инварианты проекта, pipeline и safety-правила.
- `server/AGENTS.md` и `pc_agent/AGENTS.md` — короткие leaf-правила для конкретной части монорепо.
- `docs/QUICK_LOOKUP.md` — короткий навигационный индекс.
- `server/docs/CODEMAP.md` и `pc_agent/docs/CODEMAP.md` — канонические карты кода.
- `.cursor/rules/` — короткие правила-маршрутизаторы и playbook-и.
- `.cursor/skills/` — узкие repeatable workflow skills.
- `.codex/config.toml` — repo-local defaults для Codex.

## Канонические пути и артефакты

- Серверный CODEMAP: `server/docs/CODEMAP.md`
- Агентский CODEMAP: `pc_agent/docs/CODEMAP.md`
- Навигационный индекс: `docs/QUICK_LOOKUP.md`
- Машиночитаемый каталог навигации и drift-правил: `scripts/navigation_catalog.py`
- Long-horizon артефакт: `PLANS.md`

Если меняется структура кода, маршруты, ключевые entrypoints или cross-cutting flow, синхронно обновлять:

- затронутый `CODEMAP`;
- `docs/QUICK_LOOKUP.md`;
- при необходимости `scripts/navigation_catalog.py`;
- при необходимости `PLANS.md`, если задача ведётся в несколько шагов.

## Work Modes

- Для типовых режимов работы использовать `.cursor/rules/subagents-pc-client.mdc`.
- Это не настоящие субагенты, а playbook-и: миграции, Protocol V3, docs sync, тесты по диффу, release.
- Не держать этот playbook как always-on контекст; подключать только по совпадению задачи.

## Repo-local Codex Config

- Repo-local defaults хранятся в `.codex/config.toml`.
- Если проекту нужны другие модель/effort/defaults, менять их там, а не раздувать `AGENTS.md`.
- Глобальные MCP-сервера и общие настройки остаются в `C:\Users\admin-2\.codex\config.toml`.

## Protocol V3: инварианты

- Контракт: `pc_agent/docs/PROTOCOL_V3.md` и `server/docs/PROTOCOL_V3.md`.
- При расхождении приоритет у серверной документации для серверного кода и у агентской — для агента.
- Тип события определяется только по `device_seq` vs `agent_seq`:
  - `device_event` ⇔ `device_seq IS NOT NULL AND agent_seq IS NULL`
  - `ticket_event` ⇔ `agent_seq IS NOT NULL AND device_seq IS NULL`
- Серверный handshake требует `protocol_version === "ws_ticket_v3"`, capabilities `protocol_v3`, `envelope_v3`, `outbox_ack_v3` и token.
- `device_id` для сессии сервер берёт из записи токена в БД; payload не источник истины.
- Каноническая identity-модель агента: `machine_id` как стабильный идентификатор устройства, `install_id` как вторичный идентификатор конкретной инсталляции. В Protocol V3 top-level `device_id` и payload `machine_id` должны совпадать и описывать одно и то же устройство; `install_id` используется только для диагностики, аудита и controlled reprovision.
- `tool_call_started` создаётся сервером до отправки `run_tool` и идемпотентен по `(ticket_id, operation_id, event_type)`.

## Безопасность

- Не логировать сырой токен; допустим только префикс.
- Роли и actor context брать только из проверенного токена и `AuthContext`.
- Не использовать ad-hoc команды вместо штатных скриптов, если сценарий уже покрыт `scripts/`.

## Скрипты: канон

- Локальный агент на Windows: только `python scripts/manage_local_agent.py ...`
- Runtime control на Linux: `python scripts/runtime_stack.py start|stop|restart|status|smoke|logs server|agent|control|all`
- Удалённый сервер на Linux из Windows: только `python scripts/manage_remote_stack.py ...` как SSH-обёртка над `scripts/runtime_stack.py`
- Полный server-flow: `python scripts/release_server_to_remote.py`
- Отдельный deploy закоммиченного состояния: `python scripts/deploy_workspace_to_remote.py`
- Smoke/API helpers: `python scripts/smoke_test.py`, `python scripts/admin_run_tool.py`

## Agent update canon

- Если задача затрагивает self-update, launcher, release build, `ui_bridge`, Agent Updates UI или rollout, начинать с:
  - `pc_agent/docs/AGENT_UPDATE_WORKFLOW.md`
  - `pc_agent/docs/SELF_UPDATE.md`
  - `server/docs/AGENT_UPDATES_API.md`
  - `pc_agent/docs/CODEMAP.md`
- Для таких задач использовать проектный skill `pc-client-agent-updates`.
- Если задача затрагивает always-on runtime, tray, локальный GUI shutdown/restart, `pc_agent/core/runtime_logging.py`, `pc_agent/ui_gui/*` или `pc_agent/ui_bridge/*`, начинать с:
  - `pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md`
  - `pc_agent/docs/CODEMAP.md`
  - `docs/QUICK_LOOKUP.md`
- Для таких задач использовать проектный skill `pc-client-agent-runtime`.
- Если меняется распространяемый бинарь агента или launcher, обязательно обновлять `pc_agent/version.py`.
- Не выпускать новый build под старым номером версии как обычный сценарий.
- Каноническая Windows release-сборка: `python pc_agent/build_windows_release_v2.py`
- Для локального canary через `manage_local_agent.py start <name> --launcher` существующий полный versioned install layout instance должен сохраняться; не превращать canary-instance в текущую repo-версию автоматически.
- После сборки проверять:
  - `pc_agent/dist/launcher.exe`
  - `pc_agent/dist/pc_agent/pc_agent.exe`
  - `pc_agent/dist/release/windows_amd64/stable/<version>/pc_agent-windows_amd64-<version>.zip`
- Rollout делать по цепочке: upload build -> canary update -> diagnostics/handshake verify -> bulk rollout.
- `scheduled` не считать подтверждением успешного обновления; успех подтверждается следующим handshake новой версии.

Замечание по server runtime:

- Основной HTTP/WS сервер и внешний `control-plane` теперь считаются разными сервисами.
- `control-plane` живёт отдельно от main server, отвечает за `start/stop/restart/status/logs/smoke` и нужен для надёжной техпанели.
- Для lifecycle-операций над сервером нельзя делать ad-hoc self-restart из основного aiohttp-процесса.
- `python scripts/release_server_to_remote.py` обязан поднимать `control-plane` до запуска main server.

Запрещено:

- копировать файлы вручную в `/var/chat_bot/pc_client/...`;
- собирать вручную цепочки из `git push`, `ssh`, `git pull`, `run_server.py`, `stop_server.py`, если хватает штатных скриптов;
- запускать сервер на Windows как основной стенд.

## Browser Canon

- Для браузерных проверок использовать только `http://192.168.100.17:8666/admin`.
- Любые изменения веб-интерфейса сервера проверять в браузере через MCP, а не только smoke-тестом.
- Если менялась техпанель или server-control flow, в браузере обязательно проверить:
  - блок статуса сервера (`running/stopped/restarting`, uptime, unit/PID, last restart reason);
  - health block (`PostgreSQL`, latency, pool, WS UI/agent connections, stuck operations);
  - полные логи сервера (tail, level filter, поиск, refresh/copy/download);
  - confirm-модалку для `stop/restart` и аудит с причиной;
  - что техпанель переживает `restart` за счёт внешнего control-plane.

## Проверки и handoff

- Минимум перед коммитом: `python scripts/verify_workspace.py`
- Затем — релевантные `pytest` по затронутой области.
- Если менялся веб — browser check через MCP.
- Если менялись `server/control_plane.py`, `server/runtime_control.py`, `server/admin.*`, `server/tech/handlers.py` или runtime-скрипты:
  - последовательно прогнать verify + релевантный pytest;
  - поднять Linux-стенд через штатный pipeline;
  - отдельно проверить `python scripts/manage_remote_stack.py status control`;
  - в браузере пройти tech-panel сценарий со статусом, health, логами и confirm для lifecycle actions.
- Если менялись `pc_agent/launcher/*`, `pc_agent/ws_agent.py`, `pc_agent/ui_bridge/*`, `pc_agent/ui_gui/*` или server-side Agent Updates flow:
  - прогнать `python -m pytest pc_agent/tests/ -v --tb=short`;
  - точечно прогнать update-контракты сервера, если менялась серверная часть;
  - собрать новый release build;
  - проверить canary update хотя бы на одном устройстве или локальном launcher-instance;
  - зафиксировать, чем именно подтверждён успех: handshake, diagnostics, update history, admin UI.
- Если менялись `pc_agent/ws_agent.py`, `pc_agent/ui_gui/*`, `pc_agent/ui_bridge/*` или `pc_agent/core/runtime_logging.py`:
  - прогнать `python -m pytest pc_agent/tests/test_ui_api_server_shutdown.py -v --tb=short`;
  - прогнать `python -m pytest pc_agent/tests/test_runtime_logging.py -v --tb=short`;
  - поднять именованный локальный инстанс через `python scripts/manage_local_agent.py start <name> --gui --ui-port <port>`;
  - проверить `GET /ui/agent/status`, затем закрыть окно `Maria Agent` и подтвердить, что процесс и локальный API живы;
  - завершить инстанс через `POST /ui/agent/shutdown` или штатный stop path и зафиксировать результат.
- `python scripts/release_server_to_remote.py --skip-verify` допустим только как исключение:
  - если тот же commit уже прошёл локальный `python scripts/verify_workspace.py` и релевантный pytest;
  - если текущая dirty-состояние воркспейса относится к другому локальному WIP и не должно попасть на Linux;
  - если deploy идёт вместе с `--allow-local-dirty`, то есть на Linux уходит именно последний проверенный commit.
- В итоговом отчёте всегда фиксировать:
  - что изменено;
  - что проверено;
  - что не проверено;
  - остаточные риски.

## UTF-8 и Windows shell

- Во всех файлах и ответах использовать корректный UTF-8.
- В Python при чтении и записи текста явно указывать `encoding="utf-8"`.
- Для subprocess на Windows предпочитать байты + явную декодировку в UTF-8 с контролируемым fallback.
- Перед работе с русским текстом в PowerShell запускать `.\scripts\bootstrap_shell_utf8.ps1`.
- `mojibake` (`Р...`, `Ð...`, `Ñ...`) запрещён и должен исправляться до сохранения или отправки.
