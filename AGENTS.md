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
   - затем `docs/CODEX_WORKFLOW.md` и выбрать рабочий режим: Explore / Debug / Plan / Execute / Feature / Contract / Verify / Commit / Deploy;
   - затем `docs/QUICK_LOOKUP.md`;
   - затем `docs/ARCHITECTURE_BOUNDARIES.md` и классифицировать change как local / boundary / cross-cutting / release-control;
   - затем `docs/CONTEXT_INDEX.md`, `python scripts/build_context_pack.py --topic "<описание>"` и точечный `python scripts/search_context_index.py "<символ route error-code concept>"` для быстрого поиска docs/CODEMAP/routes/handlers/tests/symbols; если индекс устарел или search печатает stale-warning, сначала `python scripts/build_context_index.py --force`;
   - затем соответствующий `CODEMAP` и точечный `python scripts/agent_find.py "<паттерн>" --dir server|pc_agent`.
   - если задача затрагивает новый `webapp/`, frontend bundle pipeline или release flow для web-ассетов, перед любыми frontend-командами обязательно выполнить `python scripts/bootstrap_web_toolchain.py`.
4. При изменении структуры, маршрутов, контрактов или ключевых потоков синхронно обновлять код, docs и канонический `CODEMAP`.
5. Перед коммитом прогонять минимум `python scripts/verify_workspace.py`, затем релевантные `pytest` и нужные smoke/browser-проверки.
6. После локальной проверки делать локальный commit и сразу push этого commit в GitHub `origin` на текущую ветку. Локальный commit без GitHub push считается незавершённым checkpoint-ом, если пользователь явно не попросил не публиковать.
7. Для выкладки на Linux использовать только штатные скрипты:
   - `python scripts/deploy_workspace_to_remote.py`
   - `python scripts/release_server_to_remote.py`
   - `python scripts/manage_remote_stack.py start|stop|restart|status|smoke|logs server|agent|control`
   - Для итерационного стенда использовать явный `--gate quick`; он пропускает только full-CI artifact gate и не заменяет `verify_workspace`, релевантные pytest, remote smoke или browser checks.
   - Full CI (`python scripts/run_ci_suite.py`) и full gate (`--gate full` или дефолтный deploy/release без `--gate`) считаются важным финальным release-checkpoint-ом, но Codex запускает их только по явному запросу пользователя и только для frozen release candidate SHA. До freeze использовать targeted tests + quick gate/live checks. После green full CI не делать новых commit до full-gate release; любой новый commit — новый candidate и требует новый full CI artifact. Перед full gate выполнять `python scripts/release_candidate_preflight.py`.
8. После проверок на Linux останавливать сервер: `python scripts/manage_remote_stack.py stop server`, если пользователь явно не просил оставить его запущенным.
9. Каждый локальный commit публиковать в GitHub `origin` тем же рабочим циклом (`git push -u origin <current-branch>` при первом push ветки, затем `git push`). Строгий отдельный secret-scan перед таким push не требуется; достаточно обычного осознанного staging по текущему `.gitignore` и проектным правилам не логировать сырые токены.

## Контекст и артефакты

- Навигационный индекс: `docs/QUICK_LOOKUP.md`
- Каноничный workflow Codex по режимам работы: `docs/CODEX_WORKFLOW.md`
- Карта границ владения и contract surfaces: `docs/ARCHITECTURE_BOUNDARIES.md`
- Локальный индекс контекста и правила индексации: `docs/CONTEXT_INDEX.md`
- Индекс документации: `docs/README.md`
- Серверный CODEMAP: `server/docs/CODEMAP.md`
- Агентский CODEMAP: `pc_agent/docs/CODEMAP.md`
- Машиночитаемый каталог навигации и drift-правил: `scripts/navigation_catalog.py`
- Long-horizon артефакт: `PLANS.md`
- Repo-local defaults для Codex: `.codex/config.toml`
- Live/debug процесс: `docs/LIVE_TESTING_DEBUG_RULES.md`

Если меняется структура кода, маршруты, ключевые entrypoints или cross-cutting flow, синхронно обновлять:

- затронутый `CODEMAP`;
- `docs/CODEX_WORKFLOW.md`, если меняются режимы работы Codex, dirty-worktree правила, commit/deploy flow или обязательные verification gates;
- `docs/QUICK_LOOKUP.md`;
- `docs/ARCHITECTURE_BOUNDARIES.md`, если меняются границы владения, contract surfaces или правила классификации изменений;
- `docs/CONTEXT_INDEX.md`, если меняются правила индексации, источники retrieval, ranking/search profiles, build/search/context-pack команды или freshness cadence;
- `server/docs/OBSERVER_LAYER.md` и `server/docs/OBSERVER_AUTHORING_RULES.md`, если change затрагивает observer, dangerous flow, tech/support trace UI или trace-visible API;
- при необходимости `scripts/navigation_catalog.py`;
- при необходимости `PLANS.md`, если задача ведётся в несколько шагов.

Observer docs поддерживаются в актуальном состоянии наравне с CODEMAP. Изменение dangerous flow без синхронного обновления observer docs считается незавершённой работой.

## Профильные режимы

- Типовые режимы работы держать в каноничных документах (`AGENTS.md`, `docs/QUICK_LOOKUP.md`, `docs/LOCAL_WORKFLOW.md`, профильные docs рядом с кодом) и в `scripts/navigation_catalog.py`.
- Editor-specific rule/skill folders не являются каноном проекта и не должны использоваться как источник правил.
- Корневой `AGENTS.md` хранит только инварианты проекта, pipeline и safety-правила.
- Внешние plugin-skills и user-level Codex skills допустимы как вспомогательные process-playbook-и только если они не конфликтуют с этим `AGENTS.md` и проектной документацией.
- Каноничные внешние skills по умолчанию:
  - `superpowers:systematic-debugging` — для любого бага, падения теста или unexpected behavior: сначала root cause investigation, затем фикс.
  - `superpowers:verification-before-completion` — перед любым claim уровня "готово", "исправлено", "tests pass", а также перед commit/push/PR/deploy; он не заменяет проектные проверки, а требует свежего доказательства через них.
  - `superpowers:writing-plans` — для длинных, многослойных или многошаговых задач; итоговый план фиксировать в `PLANS.md`.
  - `superpowers:executing-plans` — для аккуратного исполнения уже согласованного многошагового плана с checkpoint-ами.
  - `superpowers:requesting-code-review` — как финальный self-review для рискованных, больших или cross-cutting изменений перед публикацией результата.
  - `superpowers:test-driven-development` — использовать там, где реалистично сначала зафиксировать поведение тестом, особенно для bugfix и контрактных изменений.
  - `build-web-apps:frontend-app-builder` — использовать для новых webapp-экранов, крупных визуальных переделок страниц и заметных UI/UX/accessibility-аудитов, когда нужно улучшать композицию, иерархию, плотность и общий уровень интерфейса.
  - `build-web-apps:react-best-practices` — использовать при работе с React/Next.js кодом, если соответствующий стек есть в затронутой части проекта.
- Skills `circleci:*` использовать только когда задача действительно про CircleCI pipeline, `.circleci/config.yml`, Chunk или диагностику CI; они не являются частью обязательного потока локальной разработки и deploy на Linux.
- Для задач по веб-интерфейсу сервера сочетать MCP browser-check из проектного канона с `build-web-apps:frontend-app-builder`, если задача включает дизайн/UX/accessibility или заметную визуальную переработку.
- Для задач по новому `webapp/`, React-коду и frontend build/release pipeline первым шагом считать `python scripts/bootstrap_web_toolchain.py`; каноничный frontend toolchain проекта — `Node.js 24.15.0 + corepack + pnpm 10.33.0` локально и в CI.
- Авто-маршрутизатор для Codex в `pc_client`:
  - bugfix / падение тестов / unexpected behavior -> `superpowers:systematic-debugging`, затем при уместности `superpowers:test-driven-development`
  - длинная задача / несколько подсистем / несколько заходов -> `superpowers:writing-plans` и ведение `PLANS.md`
  - исполнение уже согласованного плана -> `superpowers:executing-plans`
  - UI review / UX review / accessibility / audit интерфейса -> `pc-client-browser-check`, затем `build-web-apps:frontend-app-builder`, если нужен дизайн-аудит или визуальная правка
  - заметная визуальная переделка страницы или admin UI -> `build-web-apps:frontend-app-builder`, затем `pc-client-browser-check`
  - React / Next.js правки -> сначала `python scripts/bootstrap_web_toolchain.py`, затем `build-web-apps:react-best-practices`
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
- Для release/deploy/server-control сценариев ориентироваться на `docs/LOCAL_WORKFLOW.md`, `docs/QUICK_LOOKUP.md` и профильные scripts в `scripts/`.

## Live testing and debugging

Для любых Live validation, debug, Protocol V3, local agent GUI, browser UI, account-session, operation lifecycle, module runtime, deployment/runtime-control или production-like bugfix задач сначала читать и выполнять:

- `docs/LIVE_TESTING_DEBUG_RULES.md`

Эти правила обязательны и запрещают ad-hoc shortcuts. В частности:

- сначала evidence и запись бага, потом root cause и fix;
- validation modes не смешивать: browser, pywinauto/UIA, `/ui/automation/run`, direct API, raw WS, DB и SQLite являются разными test surfaces;
- browser-visible flows требуют real browser evidence;
- local GUI flows требуют `pywinauto==0.6.9` и `Application(backend="uia")`;
- `/ui/automation/run` не считается GUI-equivalent без отдельной проверки account/session/context поведения;
- Live scenario не может быть green по одному сигналу;
- pre-fix contamination должна быть явно помечена и фильтроваться clean-run markers;
- статусы в bug block, checklist, milestone summary и recommended next steps должны быть согласованы.

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

- Для браузерных проверок использовать только `https://192.168.100.17:9443/admin`.
- Любые изменения веб-интерфейса сервера проверять в браузере через MCP, а не только smoke-тестом.
- Если менялась техпанель или server-control flow, обязательно проверить status, health, full logs и confirm для `stop/restart`.

## UTF-8 и Windows shell

- Во всех файлах и ответах использовать корректный UTF-8.
- В Python при чтении и записи текста явно указывать `encoding="utf-8"`.
- Для subprocess на Windows предпочитать байты + явную декодировку в UTF-8 с контролируемым fallback.
- Перед работой с русским текстом в PowerShell запускать `.\scripts\bootstrap_shell_utf8.ps1`.
- `mojibake` (`Р...`, `Ð...`, `Ñ...`) запрещён и должен исправляться до сохранения или отправки.
