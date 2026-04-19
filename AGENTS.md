# AGENTS.md — инструкции для Codex (pc_client)

## Источник истины

- Все правки, проверки, временные файлы и коммиты делать только в локальной рабочей копии `C:\Users\admin-2\CodexProjects\pc_client`.
- Сетевая шара `\\192.168.100.17\NTFS_Share\pc_client` — зеркало и точка обмена, не основная среда редактирования.
- Linux working copy `/var/chat_bot/pc_client` — стенд и зеркало закоммиченного состояния ветки после deploy.
- Для кода и документации канон один: локальная Windows-копия.

## Обязательный рабочий цикл

1. Открывать и менять код только в локальной копии.
2. Если задача длинная, затрагивает несколько подсистем или требует нескольких verification stages, вести `PLANS.md`.
3. Перед правками собрать контекст:
   - для нетривиальной задачи сначала `python scripts/task_intake.py`;
   - затем `docs/QUICK_LOOKUP.md`;
   - затем соответствующий `CODEMAP` и точечный `python scripts/agent_find.py "<паттерн>" --dir server|pc_agent`.
4. При изменении структуры, маршрутов, контрактов или ключевых потоков синхронно обновлять код, docs и канонический `CODEMAP`.
5. Перед коммитом прогонять минимум `python scripts/verify_workspace.py`, затем релевантные `pytest` и нужные smoke/browser-проверки.
6. После локальной проверки делать локальный commit.
7. Для выкладки на Linux использовать только штатные скрипты:
   - `python scripts/deploy_workspace_to_remote.py`
   - `python scripts/release_server_to_remote.py`
   - `python scripts/manage_remote_stack.py start|stop|restart|status|smoke|logs server|agent|control`
8. После проверок на Linux останавливать сервер: `python scripts/manage_remote_stack.py stop server`, если пользователь явно не просил оставить его запущенным.
9. В GitHub публиковать только проверенное состояние.

## Контекст и артефакты

- Навигационный индекс: `docs/QUICK_LOOKUP.md`
- Серверный CODEMAP: `server/docs/CODEMAP.md`
- Агентский CODEMAP: `pc_agent/docs/CODEMAP.md`
- Машиночитаемый каталог навигации и drift-правил: `scripts/navigation_catalog.py`
- Long-horizon артефакт: `PLANS.md`
- Repo-local defaults для Codex: `.codex/config.toml`

Если меняется структура кода, маршруты, ключевые entrypoints или cross-cutting flow, синхронно обновлять:

- затронутый `CODEMAP`;
- `docs/QUICK_LOOKUP.md`;
- при необходимости `scripts/navigation_catalog.py`;
- при необходимости `PLANS.md`, если задача ведётся в несколько шагов.

## Профильные режимы

- Типовые режимы работы и длинные playbook-и держать в repo-local каталогах `.cursor/rules/` и `.cursor/skills/` (это историческое имя папки, для Codex они тоже считаются каноничными playbook-ами проекта).
- Корневой `AGENTS.md` хранит только инварианты проекта, pipeline и safety-правила.
- Внешние plugin-skills допустимы как вспомогательные process-playbook-и только если они не конфликтуют с этим `AGENTS.md` и repo-local skill-ами проекта.
- Каноничные внешние skills по умолчанию:
  - `superpowers:systematic-debugging` — для любого бага, падения теста или unexpected behavior: сначала root cause investigation, затем фикс.
  - `superpowers:verification-before-completion` — перед любым claim уровня "готово", "исправлено", "tests pass", а также перед commit/push/PR/deploy; он не заменяет проектные проверки, а требует свежего доказательства через них.
  - `superpowers:writing-plans` — для длинных, многослойных или многошаговых задач; итоговый план фиксировать в `PLANS.md`.
  - `superpowers:executing-plans` — для аккуратного исполнения уже согласованного многошагового плана с checkpoint-ами.
  - `superpowers:requesting-code-review` — как финальный self-review для рискованных, больших или cross-cutting изменений перед публикацией результата.
  - `superpowers:test-driven-development` — использовать там, где реалистично сначала зафиксировать поведение тестом, особенно для bugfix и контрактных изменений.
  - `build-web-apps:web-design-guidelines` — обязательный внешний skill для review дизайна, UX и accessibility веб-страниц; особенно для admin UI и любых заметных правок интерфейса сервера.
  - `build-web-apps:frontend-skill` — использовать для крупных визуальных переделок страниц, когда нужно улучшать композицию, иерархию, плотность и общий уровень интерфейса, а не только чинить отдельные элементы.
  - `build-web-apps:react-best-practices` — использовать при работе с React/Next.js кодом, если соответствующий стек есть в затронутой части проекта.
- Skills `circleci:*` использовать только когда задача действительно про CircleCI pipeline, `.circleci/config.yml`, Chunk или диагностику CI; они не являются частью обязательного потока локальной разработки и deploy на Linux.
- Для задач по веб-интерфейсу сервера сочетать MCP browser-check из проектного канона с `build-web-apps:web-design-guidelines`: сначала привести интерфейс к рабочему состоянию, затем отдельно оценить качество UI/UX и читаемость.
- Авто-маршрутизатор для Codex в `pc_client`:
  - bugfix / падение тестов / unexpected behavior -> `superpowers:systematic-debugging`, затем при уместности `superpowers:test-driven-development`
  - длинная задача / несколько подсистем / несколько заходов -> `superpowers:writing-plans` и ведение `PLANS.md`
  - исполнение уже согласованного плана -> `superpowers:executing-plans`
  - UI review / UX review / accessibility / audit интерфейса -> `build-web-apps:web-design-guidelines`
  - заметная визуальная переделка страницы или admin UI -> `build-web-apps:frontend-skill`, затем `build-web-apps:web-design-guidelines`
  - React / Next.js правки -> `build-web-apps:react-best-practices`
  - завершение работы / claim "готово" / commit / push / deploy -> `superpowers:verification-before-completion`; для рискованных или широких изменений дополнительно `superpowers:requesting-code-review`
- Отдельного внешнего skill-а именно для TODO в этом наборе нет; его роль в проекте выполняют `superpowers:writing-plans`, `superpowers:executing-plans`, локальный `PLANS.md` и явная фиксация шагов по ходу задачи.
- Для agent update / launcher / rollout начинать с:
  - `pc_agent/docs/AGENT_UPDATE_WORKFLOW.md`
  - `pc_agent/docs/SELF_UPDATE.md`
  - `server/docs/AGENT_UPDATES_API.md`
  - `pc_agent/docs/CODEMAP.md`
- Для always-on runtime / tray / `ui_bridge` / `ui_gui` начинать с:
  - `pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md`
  - `pc_agent/docs/CODEMAP.md`
  - `docs/QUICK_LOOKUP.md`
- Для release/deploy/server-control сценариев ориентироваться на `docs/LOCAL_WORKFLOW.md` и профильные repo-local playbook-и в `.cursor/rules/*`.

## Protocol V3: инварианты

- Контракт: `pc_agent/docs/PROTOCOL_V3.md` и `server/docs/PROTOCOL_V3.md`.
- Тип события определяется только по `device_seq` vs `agent_seq`:
  - `device_event` ⇔ `device_seq IS NOT NULL AND agent_seq IS NULL`
  - `ticket_event` ⇔ `agent_seq IS NOT NULL AND device_seq IS NULL`
- Серверный handshake требует `protocol_version === "ws_ticket_v3"`, capabilities `protocol_v3`, `envelope_v3`, `outbox_ack_v3` и token.
- `device_id` для сессии сервер берёт из записи токена в БД; payload не источник истины.
- Каноническая identity-модель агента: `machine_id` как стабильный идентификатор устройства, `install_id` как вторичный идентификатор конкретной инсталляции.
- `tool_call_started` создаётся сервером до отправки `run_tool` и идемпотентен по `(ticket_id, operation_id, event_type)`.

## Безопасность

- Не логировать сырой токен; допустим только префикс.
- Роли и actor context брать только из проверенного токена и `AuthContext`.
- Не использовать ad-hoc команды вместо штатных скриптов, если сценарий уже покрыт `scripts/`.
- Не копировать файлы вручную в `/var/chat_bot/pc_client/...`.
- Основной HTTP/WS сервер и внешний `control-plane` считаются разными сервисами; lifecycle-операции над сервером должны идти через штатные скрипты и внешний `control-plane`.

## Browser Canon

- Для браузерных проверок использовать только `http://192.168.100.17:8666/admin`.
- Любые изменения веб-интерфейса сервера проверять в браузере через MCP, а не только smoke-тестом.
- Если менялась техпанель или server-control flow, обязательно проверить status, health, full logs и confirm для `stop/restart`.

## UTF-8 и Windows shell

- Во всех файлах и ответах использовать корректный UTF-8.
- В Python при чтении и записи текста явно указывать `encoding="utf-8"`.
- Для subprocess на Windows предпочитать байты + явную декодировку в UTF-8 с контролируемым fallback.
- Перед работой с русским текстом в PowerShell запускать `.\scripts\bootstrap_shell_utf8.ps1`.
- `mojibake` (`Р...`, `Ð...`, `Ñ...`) запрещён и должен исправляться до сохранения или отправки.
