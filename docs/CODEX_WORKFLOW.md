# Codex Workflow

Каноничный рабочий маршрут для Codex в `pc_client`: как начинать задачу, выбирать режим, работать с грязным worktree, планировать, дебажить, коммитить и выкладывать без случайного повреждения соседних контрактов.

Документ намеренно использует существующие проектные скрипты. Не добавляйте новый helper-скрипт только ради обхода этих шагов; если штатного сценария не хватает, сначала обновите workflow и профильный script осознанно.

## Invariants

- Работать только в `C:\Users\admin-2\CodexProjects\pc_client`.
- Не редактировать `\\192.168.100.17\NTFS_Share\pc_client` напрямую.
- Не копировать файлы вручную в `/var/chat_bot/pc_client`.
- Для lifecycle/deploy использовать только scripts из `scripts/`.
- Не делать `git reset --hard`, `git checkout -- <path>` или массовую зачистку без явного разрешения пользователя.
- Не использовать `git add .`; stage только файлы текущей задачи.
- Любой claim "готово", "исправлено", "tests pass", commit, push или deploy требует свежей проверки.

## Universal Start Gate

Перед любой нетривиальной задачей:

```powershell
.\scripts\bootstrap_shell_utf8.ps1
python scripts/task_intake.py --task "<описание задачи>"
python scripts/build_context_pack.py --topic "<описание задачи>"
python scripts/search_context_index.py "<symbols, routes, error codes or concepts>"
python scripts/diff_context.py
git status --short
```

Дальше открыть документы из `task_intake`, минимум:

- `docs/QUICK_LOOKUP.md`
- `docs/CODEX_WORKFLOW.md`
- `docs/ARCHITECTURE_BOUNDARIES.md`
- `docs/CONTEXT_INDEX.md`
- соответствующий `server/docs/CODEMAP.md` или `pc_agent/docs/CODEMAP.md`

`build_context_pack.py` является стандартным компактным intake-результатом: он собирает routing metadata, open-first docs, команды и секцию `Context Index Results`.

`search_context_index.py` является стандартным быстрым retrieval-шагом после `task_intake`: он ищет одновременно по canonical docs, CODEMAP chunks, navigation topics, server routes, route handlers, tests и symbols. Это не заменяет CODEMAP/boundary docs, а ускоряет выбор точных файлов и терминов.

```powershell
python scripts/search_context_index.py "<symbols, routes, error codes or concepts>"
python scripts/search_context_index.py "<route or endpoint>" --profile route --kind route
python scripts/search_context_index.py "<bug behavior>" --profile test --kind test
```

Если индекс выглядит устаревшим или `search_context_index.py` печатает stale-warning:

```powershell
python scripts/build_context_index.py --force
```

Перед правками классифицировать задачу по `docs/ARCHITECTURE_BOUNDARIES.md`:

- `local`
- `boundary`
- `cross-cutting`
- `release-control`

Если classification неясна, считать задачу `boundary` или `cross-cutting` до уточнения.

## Mode Router

| Mode | Use when | Start with | Required artifact |
|---|---|---|---|
| Explore / Intake | Тема неясна, нужно найти область кода | `task_intake`, `diff_context`, `agent_find` | Короткий вывод: зона, файлы, риски |
| Debug / Root Cause | Баг, падение теста, unexpected behavior, live incident | `superpowers:systematic-debugging`, targeted pytest/logs | Repro, hypothesis, evidence |
| Plan / Design | Длинная задача, несколько подсистем, contract change | `superpowers:writing-plans`, `pc-client-plans` | `PLANS.md` |
| Execute Plan | Есть согласованный план | `superpowers:executing-plans` | Обновляемые checkpoints в `PLANS.md` |
| Feature / Code Change | Обычная локальная реализация | ownership zone + focused tests | Код + релевантные tests/docs |
| Contract / Boundary Change | Меняется Protocol, DTO, manifest, DB, auth, observer, runtime contract | `ARCHITECTURE_BOUNDARIES`, CODEMAP, профильные docs | Producer+consumer updates |
| Review / Self-Review | Большой или рискованный diff | `superpowers:requesting-code-review` | Findings or explicit no-findings |
| Verify / Completion Gate | Перед статусом, commit, push, deploy | `superpowers:verification-before-completion` | Fresh command output |
| Commit | Проверенные локальные изменения | targeted `git add`, `git diff --cached` | Commit с файлами задачи |
| Deploy / Release | Нужно выложить на Linux или проверить live | release scripts, remote stack scripts | Commit first, smoke/browser result |
| Dirty Worktree Triage | Есть незакоммиченные файлы | `diff_context`, `git status --short` | Решение: ignore / continue / stop |

## Explore / Intake Mode

Цель: понять, где работа должна происходить, до чтения всего репозитория.

```powershell
python scripts/task_intake.py --task "<описание>"
python scripts/build_context_pack.py --topic "<topic>"
python scripts/search_context_index.py "<symbol route error-code>"
python scripts/agent_find.py "<pattern>" --dir server
python scripts/agent_find.py "<pattern>" --dir pc_agent
```

Использовать `agent_find` точечно: один символ, route, class, event type, endpoint или error code. Если задача касается нового `webapp/`, frontend bundle или release web assets, сначала:

```powershell
python scripts/bootstrap_web_toolchain.py
```

## Debug / Root Cause Mode

Для любого бага, падения теста или unexpected behavior начинать с `superpowers:systematic-debugging`.

Правило: сначала воспроизведение и гипотеза, потом фикс.

Минимальный локальный путь:

```powershell
python scripts/task_intake.py --task "<bug / failure>"
python scripts/build_context_pack.py --topic "<bug / failure>"
python scripts/search_context_index.py "<error|symbol|route|event>" --profile debug
python scripts/search_context_index.py "<expected behavior>" --profile test --kind test
python scripts/diff_context.py
python scripts/agent_find.py "<error|symbol|route|event>" --dir server
python scripts/agent_find.py "<error|symbol|route|event>" --dir pc_agent
python -m pytest <target-test> -v --tb=short
```

Если проблема в логах:

```powershell
python scripts/extract_log_signals.py <log-file>
```

Если проблема только на Linux/runtime:

```powershell
python scripts/manage_remote_stack.py status control
python scripts/manage_remote_stack.py logs server
python scripts/manage_remote_stack.py smoke server
```

Для observer/dangerous-flow regressions:

```powershell
python scripts/run_observer_canary_suite.py
```

Нельзя исправлять "по ощущениям", если нет хотя бы одного из доказательств:

- failing test
- reproduced local command
- log signature
- browser/smoke failure
- narrowed code path with concrete invariant violation

## Plan / Design Mode

Использовать, если задача:

- затрагивает несколько ownership zones;
- меняет contract surface;
- требует нескольких verification stages;
- будет выполняться несколькими заходами;
- требует deploy/release или live verification.

Команды:

```powershell
python scripts/task_intake.py --task "<описание>"
python scripts/build_context_pack.py --topic "<topic>"
python scripts/diff_context.py
```

Артефакт:

```text
PLANS.md
```

План должен фиксировать:

- scope и non-goals;
- ownership zones;
- contract surfaces;
- файлы/доки, которые нужно обновить;
- verification matrix;
- deploy/rollback considerations, если есть runtime impact.

## Execute Plan Mode

Исполнять уже согласованный план через checkpoints.

```powershell
python scripts/task_intake.py --task "<phase>"
python scripts/diff_context.py
python scripts/verify_workspace.py
```

Правила:

- Не добавлять новый scope без обновления `PLANS.md`.
- После каждого meaningful checkpoint обновлять статус плана.
- Если обнаружен bug, перейти в Debug / Root Cause Mode.
- Если найден contract surface, перейти в Contract / Boundary Change Mode.

## Feature / Code Change Mode

Обычный путь для локальной задачи:

```powershell
python scripts/task_intake.py --task "<feature>"
python scripts/diff_context.py
python scripts/verify_workspace.py
```

Добавить проверки по зоне:

```powershell
python -m pytest server/tests/ -v --tb=short
python -m pytest pc_agent/tests/ -v --tb=short
```

Для server/web UI:

```powershell
python scripts/manage_remote_stack.py status control
python scripts/manage_remote_stack.py smoke server
```

Для React/webapp:

```powershell
python scripts/bootstrap_web_toolchain.py
python scripts/check_webapp_cutover.py --json
pnpm --dir webapp run build
pnpm --dir webapp run check:remote:webapp -- --base-url http://192.168.100.17:8666
```

## Contract / Boundary Change Mode

Включать по умолчанию, если меняется:

- Protocol V3 frame, handshake, capability, ACK/NACK, outbox, command_result;
- `shared/tool_contracts.py`, `ToolResponse`, semantic tool ids, risk metadata;
- module manifest/preflight/publish contract;
- `/api/web/*` DTO shape;
- DB schema/migration/repo semantics;
- auth/session/device identity/fingerprint/token binding;
- observer trace/span/root_kind/action_trace/dangerous-flow behavior;
- release/deploy/control-plane lifecycle.

Обязательные действия:

```powershell
python scripts/task_intake.py --task "<contract change>"
python scripts/build_context_pack.py --topic "<contract change>"
python scripts/search_context_index.py "<protocol api observer contract>" --profile contract
python scripts/diff_context.py
python scripts/docs_inventory.py --check-links
python scripts/verify_workspace.py
```

Потом добавить producer+consumer tests. Примеры:

```powershell
python -m pytest server/tests/test_agent_services_pipeline.py -v --tb=short
python -m pytest server/tests/test_web_admin_api.py server/tests/test_web_support_api.py -v --tb=short
python -m pytest pc_agent/tests/test_registry_and_module_loading.py -v --tb=short
```

Если меняется структура, маршруты, entrypoints или поток:

- обновить соответствующий CODEMAP;
- обновить `docs/QUICK_LOOKUP.md`;
- обновить профильные protocol/module/auth/observer/update docs;
- обновить `docs/ARCHITECTURE_BOUNDARIES.md`, если изменилась граница владения или contract surface.

## Dirty Worktree Triage Mode

Перед началом и перед commit:

```powershell
git status --short
python scripts/diff_context.py
```

Решения:

| Situation | Action |
|---|---|
| Только `artifacts/*` или generated outputs не по задаче | Игнорировать, не stage |
| Чужие изменения в unrelated files | Не трогать, не stage |
| Чужие изменения в тех же файлах | Остановиться и сообщить пользователю |
| Свои изменения предыдущего checkpoint | Продолжить или сначала commit/stage явно |
| Непонятный diff в contract file | Остановиться, перечитать boundaries/docs, запросить решение |

Запрещено без явного разрешения:

```powershell
git reset --hard
git checkout -- <path>
git clean -fd
git add .
```

## Commit Mode

Коммит делать только после fresh verification.

```powershell
git status --short
git diff
python scripts/verify_workspace.py
git add <file-1> <file-2> ...
git diff --cached
git commit -m "<type>: <summary>"
```

Если есть unrelated dirty files, они остаются unstaged. В финальном отчёте назвать, что они не включены.

Если нужен commit message для `pc_client`, использовать `pc-client-commit-message`.

## Verify / Completion Gate

Перед любым claim "готово", "исправлено", "tests pass", commit, push, PR или deploy использовать `superpowers:verification-before-completion`.

Минимум:

```powershell
python scripts/verify_workspace.py
```

По области добавить:

```powershell
python -m pytest server/tests/ -v --tb=short
python -m pytest pc_agent/tests/ -v --tb=short
python scripts/run_ci_suite.py
python scripts/docs_inventory.py --check-links
```

Для docs-only изменений допустим focused set:

```powershell
python scripts/docs_inventory.py --check-links
python -m pytest scripts/test_navigation_catalog.py scripts/test_task_intake.py -q
python scripts/verify_workspace.py
```

## Deploy / Release Mode

Deploy только после локального commit.

Полный предпочтительный путь:

```powershell
python scripts/release_server_to_remote.py
python scripts/manage_remote_stack.py status control
python scripts/manage_remote_stack.py smoke server
```

Более простой sync, если полный release flow не нужен:

```powershell
python scripts/deploy_workspace_to_remote.py
python scripts/manage_remote_stack.py status control
python scripts/manage_remote_stack.py smoke server
```

Если менялся web UI, проверить браузером каноничный адрес:

```text
http://192.168.100.17:8666/admin
```

После проверок остановить сервер, если пользователь явно не попросил оставить его запущенным:

```powershell
python scripts/manage_remote_stack.py stop server
```

## Review / Self-Review Mode

Для больших, рискованных или cross-cutting изменений:

```powershell
git diff
python scripts/diff_context.py
python scripts/verify_workspace.py
```

Использовать `superpowers:requesting-code-review`. Проверять в первую очередь:

- нарушенные contract surfaces;
- отсутствующие producer/consumer updates;
- недостающие tests/docs;
- unsafe deploy/runtime assumptions;
- hidden coupling between parallel tasks.

Если пользователь просит "review", отвечать findings-first с file/line references.

## Parallel Work Mode

Параллельно можно работать только если:

- задачи находятся в разных ownership zones;
- ни одна не меняет contract surface;
- не редактируются одни и те же CODEMAP/docs/routes/DTO/shared contracts/migrations/release scripts;
- verification одной задачи не зависит от незакоммиченной другой.

Если нужна параллельная работа с contract changes, использовать отдельные ветки/worktrees и мержить contract branch первой. После merge перезапускать impacted tests.

## Stop Conditions

Codex должен остановиться и сообщить пользователю, если:

- dirty worktree содержит чужие изменения в файлах задачи;
- правка требует destructive git operation;
- migration может затронуть реальные данные и нет явного плана;
- verification падает в зоне, которую текущая задача могла задеть;
- deploy требует оставить сервер запущенным, но пользователь этого не просил;
- task_intake показывает cross-cutting scope, а задача была сформулирована как маленькая правка;
- есть риск logging/token/security regression.

## Final Report Format

Финальный ответ должен кратко сказать:

- что изменено;
- какие файлы важны;
- что проверено с командами;
- что не проверено и почему;
- что осталось unstaged/uncommitted, если есть;
- был ли remote server запущен и остановлен.
