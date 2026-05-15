# Локальная схема работы с `pc_client`

## Точки среды

- Локальная рабочая копия: `C:\Users\admin-2\CodexProjects\pc_client`
- Сетевая шара: `\\192.168.100.17\NTFS_Share\pc_client`
- Удалённый Linux-хост: `altserver@192.168.100.17:/var/chat_bot/pc_client`

## Правило

- Правки и коммиты делаются только в локальной копии на диске машины.
- На шару и на Linux-хост отправляется только проверенное состояние.
- Каждый локальный commit публикуется в GitHub `origin` сразу после commit: локальный commit и GitHub push являются одним checkpoint-ом.
- Для обычного push dev-ветки в GitHub не нужен отдельный строгий secret-scan или full CI artifact; достаточно осознанного staging по текущему `.gitignore`, `git diff --cached` и проектного запрета на логирование сырых токенов.
- Канонический финальный release-checkpoint: локальные правки -> локальные проверки -> локальный commit -> push в GitHub `origin` -> green CI artifact для коммита -> deploy на Linux через `--gate full` -> remote start/smoke/browser -> stop -> release-отчёт. Codex запускает full CI/full gate только по явному запросу пользователя; если блок изменений ещё идёт частями, Codex должен напомнить об этом checkpoint-е и уточнить, запускать ли его сейчас.
- Для быстрой итерации на Linux-стенде использовать явный quick gate: `python scripts/release_server_to_remote.py --gate quick` или `python scripts/deploy_workspace_to_remote.py --gate quick`. Quick gate пропускает только требование green CI artifact текущего commit; он не отменяет локальный commit, `verify_workspace`, релевантные pytest, remote smoke и browser/live проверки по затронутой зоне.
- Для длинных задач состояние держать в `PLANS.md`, а не пытаться восстанавливать его по истории чата.
- Разовая синхронизация от 17 марта 2026 года уже втянула более новую Linux-версию в локальный Windows-репозиторий. После этого локальная Windows-копия считается главным источником истины.
- Git для Linux настроен через bare-репозиторий `altserver@192.168.100.17:/var/chat_bot/git/pc_client.git`; локальный Windows-remote: `linux`; Linux working copy `/var/chat_bot/pc_client` использует `origin`.

## Рекомендуемый поток

1. Если локальной копии нет или она устарела, обновить её:

```powershell
python scripts/bootstrap_local_workspace.py
```

2. Работать локально в `C:\Users\admin-2\CodexProjects\pc_client`.

3. Перед чтением/записью русского текста в терминале включить UTF-8:

```powershell
.\scripts\bootstrap_shell_utf8.ps1
```

Если задача затрагивает новый `webapp/` или frontend build/release pipeline, сначала зафиксировать каноничный web toolchain:

```powershell
python scripts/bootstrap_web_toolchain.py
```

Каноничный frontend toolchain: локально и в CI использовать `Node.js 24.15.0 + corepack + pnpm 10.33.0`. Linux-хост остаётся runtime host и не считается canonical frontend build host.

Если задача включает фактический cutover legacy `/login`, `/support`, `/admin` на новый shell, перед release дополнительно прогнать:

```powershell
python scripts/check_webapp_cutover.py --json
```

4. Если задача длинная или многосоставная, обновить `PLANS.md`.

5. Перед синхронизацией прогнать быстрые проверки:

```powershell
python scripts/verify_workspace.py
```

`verify_workspace.py` включает UTF-8/compile checks, module observer guard, `docs_drift_check.py` и active-doc broken-link check через `docs_inventory.py --check-links`.

6. После локальной проверки сделать локальный commit и сразу отправить его в GitHub `origin`.

```powershell
git commit -m "<message>"
git push -u origin <current-branch>
```

Если upstream для ветки уже настроен, использовать `git push`.

7. Если пользователь явно запросил финальный full-checkpoint, подготовить green CI artifact для целевого коммита:

```powershell
python scripts/run_ci_suite.py
```

Для self-hosted runner/hook в отдельном checkout:

```powershell
python scripts/run_ci_in_temp_workspace.py
```

8. При необходимости отправить commit на Linux через Git:

```powershell
git push linux master
```

9. При необходимости посмотреть, что уйдёт на шару:

```powershell
python scripts/sync_local_to_share.py
```

10. Применить синхронизацию на шару:

```powershell
python scripts/sync_local_to_share.py --apply
```

11. Для итерационной проверки выложить локальную копию на Linux-хост через quick gate:

```powershell
python scripts/deploy_workspace_to_remote.py --gate quick
```

`deploy_workspace_to_remote.py` и `release_server_to_remote.py` по умолчанию работают в `--gate full` и требуют green CI artifact для текущего commit. Поэтому Codex не запускает их без явного `--gate quick` во время итераций и не запускает full gate без явного запроса пользователя. Экстренный старый bypass `--skip-ci-check` оставлен для совместимости и считается эквивалентом quick gate; для полного `release_server_to_remote.py` он прокидывается во внутренний шаг `deploy_workspace_to_remote.py`.

12. Поднять сервер на Linux и прогнать smoke:

```powershell
python scripts/manage_remote_stack.py start control
python scripts/manage_remote_stack.py start server
python scripts/manage_remote_stack.py smoke server
```

`manage_remote_stack.py status server` и `scripts/runtime_stack.py status server` теперь дополнительно показывают `external_listener`, если порт `8666` занят не тем процессом, который считает своим systemd-unit. Для `start server` и `stop server` canonical runtime сначала вычищает stray `server.py` из этого workspace, чтобы ручной запуск в shell не ломал transient-unit.
`scripts/run_server.py` и `scripts/run_control_plane.py` считаются единственными canonical wrappers для server/control-plane runtime: они прокидывают repo root в import path/PYTHONPATH, чтобы sibling-пакет `shared/*` был доступен и на Linux, и в локальных repro.

13. Если менялся GUI сервера, дополнительно проверить:

- [admin](https://192.168.100.17:9443/admin)
- [help](https://192.168.100.17:9443/help)
- если менялся новый `webapp` или cutover-логика, дополнительно `pnpm --dir webapp run check:remote:webapp -- --base-url https://192.168.100.17:9443` — helper проверяет `/app`, raw redirects `/login|/admin|/support`, `?legacy=1` и теперь ожидает полноценный webapp-mode как каноническое состояние после финального cutover
- Для техпанели дополнительно проверить status/health/full logs и confirm-модалку для `stop/restart`.

14. После проверок остановить процессы:

```powershell
python scripts/manage_remote_stack.py stop server
python scripts/manage_remote_stack.py stop agent
```

## GitHub

GitHub remote настроен как `origin`. Обязательный цикл после каждого локального commit:

```powershell
git push -u origin <current-branch>
```

Для последующих push той же ветки:

```powershell
git push
```

GitHub push dev-ветки не ждёт `python scripts/run_ci_suite.py`; full CI нужен для финального release/deploy-claim и публикации проверенного release-состояния, но запускается только по явному запросу пользователя. Если план идёт частями, в конце очередного блока Codex должен напомнить об этом и уточнить, запускать ли full-checkpoint сейчас.

Если нужно обновить именно Linux working copy через Git, рабочий цикл такой:

```bash
cd /var/chat_bot/pc_client
git pull --ff-only origin master
```

Для быстрой SSH-проверки после deploy можно выполнить:

```bash
cd /var/chat_bot/pc_client
git rev-parse HEAD
git status --short
```

## Жёсткий порядок действий

1. Работать только в `C:\Users\admin-2\CodexProjects\pc_client`.
2. Перед изменениями при необходимости обновить локальную копию через `python scripts/bootstrap_local_workspace.py`.
3. Вносить правки локально.
4. Прогнать локальные проверки через `python scripts/verify_workspace.py` и дополнительные тесты по задаче.
   Для задач по `webapp/` и frontend release pipeline перед этим сначала выполнить `python scripts/bootstrap_web_toolchain.py`.
5. Для длинных задач вести `PLANS.md`.
6. Если задача затрагивает локальный агент, использовать `python scripts/manage_local_agent.py ...` и проверять нужный сценарий на отдельном инстансе.
7. Только после проверок делать локальный commit и сразу push в GitHub `origin`.
8. Для итерационной проверки на стенде использовать явный `--gate quick`; результат такого deploy нельзя считать финально проверенным для release/deploy-claim.
   Full CI и дефолтный/full deploy (`--gate full` или deploy/release без `--gate`) запускать только по явному запросу пользователя.
9. Запускать и останавливать удалённый сервер только через `python scripts/manage_remote_stack.py start server` и `python scripts/manage_remote_stack.py stop server`.
10. Перед server lifecycle-проверками держать поднятым внешний control-plane: `python scripts/manage_remote_stack.py start control` или `python scripts/release_server_to_remote.py`.
11. Если `status server` показывает `failed`, но `smoke server` или браузерный GET на `:8666` живы, сначала смотреть строку `external_listener`: это признак ручного `python server.py` вне canonical lifecycle.
12. Если менялся веб-интерфейс, обязательно открыть [admin](https://192.168.100.17:9443/admin) через браузерный MCP; для техпанели проверить status/health/full logs и confirm для `stop/restart`.
13. Для полного verified server-flow по явному запросу пользователя использовать `python scripts/release_server_to_remote.py` в дефолтном `--gate full`; для итерационного стенда использовать `--gate quick`, а emergency bypass CI gate через `--skip-ci-check` использовать только как совместимый аварийный алиас.
14. GitHub push выполняется сразу после каждого локального commit. Green CI artifact и full gate обязательны не для самого dev-branch push, а для финального release/deploy-claim; Codex напоминает о них в конце блока изменений и уточняет запуск, если план выполняется частями.

## Observer guard and live canaries

- `python scripts/verify_workspace.py` is now the hard gate for module observer breadcrumbs: every new `BaseCollector` tool must wrap execution with `self.trace_span("tool.entry", ...)`, otherwise workspace verify and module ZIP preflight fail.
- For dangerous observer regressions, use `python scripts/run_observer_canary_suite.py` after deploy to Linux. The suite covers consent approve/deny/timeout, module install/update/remove, retry exhaustion, agent disconnect during operation, and WS ACK/NACK/replay gaps.
