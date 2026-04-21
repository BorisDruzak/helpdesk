# Локальная схема работы с `pc_client`

## Точки среды

- Локальная рабочая копия: `C:\Users\admin-2\CodexProjects\pc_client`
- Сетевая шара: `\\192.168.100.17\NTFS_Share\pc_client`
- Удалённый Linux-хост: `altserver@192.168.100.17:/var/chat_bot/pc_client`

## Правило

- Правки и коммиты делаются только в локальной копии на диске машины.
- На шару и на Linux-хост отправляется только проверенное состояние.
- В GitHub публикуется только то, что уже прошло проверку.
- Канонический порядок: локальные правки -> локальные проверки -> локальный commit -> green CI artifact для коммита -> deploy на Linux -> remote start/smoke/browser -> stop -> push проверенных изменений.
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

6. После локальной проверки сделать локальный commit.

```powershell
git commit -m "<message>"
```

7. Подготовить green CI artifact для целевого коммита:

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

11. Выложить локальную копию на Linux-хост:

```powershell
python scripts/deploy_workspace_to_remote.py
```

`deploy_workspace_to_remote.py` и `release_server_to_remote.py` по умолчанию требуют green CI artifact для текущего commit. Экстренный bypass допускается только явным `--skip-ci-check`, причём для полного `release_server_to_remote.py` этот флаг должен прокидываться и во внутренний шаг `deploy_workspace_to_remote.py`.

12. Поднять сервер на Linux и прогнать smoke:

```powershell
python scripts/manage_remote_stack.py start control
python scripts/manage_remote_stack.py start server
python scripts/manage_remote_stack.py smoke server
```

`manage_remote_stack.py status server` и `scripts/runtime_stack.py status server` теперь дополнительно показывают `external_listener`, если порт `8666` занят не тем процессом, который считает своим systemd-unit. Для `start server` и `stop server` canonical runtime сначала вычищает stray `server.py` из этого workspace, чтобы ручной запуск в shell не ломал transient-unit.
`scripts/run_server.py` и `scripts/run_control_plane.py` считаются единственными canonical wrappers для server/control-plane runtime: они прокидывают repo root в import path/PYTHONPATH, чтобы sibling-пакет `shared/*` был доступен и на Linux, и в локальных repro.

13. Если менялся GUI сервера, дополнительно проверить:

- [admin](http://192.168.100.17:8666/admin)
- [help](http://192.168.100.17:8666/help)
- если менялся новый `webapp` или cutover-логика, дополнительно `pnpm --dir webapp run check:remote:webapp -- --base-url http://192.168.100.17:8666` — helper проверяет `/app`, raw redirects `/login|/admin|/support`, `?legacy=1` и теперь ожидает полноценный webapp-mode как каноническое состояние после финального cutover
- Для техпанели дополнительно проверить status/health/full logs и confirm-модалку для `stop/restart`.

14. После проверок остановить процессы:

```powershell
python scripts/manage_remote_stack.py stop server
python scripts/manage_remote_stack.py stop agent
```

## GitHub

Сейчас локальный Git-репозиторий уже создан. Когда появится URL GitHub-репозитория, его нужно добавить как `origin`, после чего использовать обычный цикл:

```powershell
git remote add origin <github-url>
git push -u origin main
```

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
7. Только после проверок делать локальный commit.
8. Только после локальной проверки и green CI artifact выкладывать состояние на Linux через `python scripts/deploy_workspace_to_remote.py`.
9. Запускать и останавливать удалённый сервер только через `python scripts/manage_remote_stack.py start server` и `python scripts/manage_remote_stack.py stop server`.
10. Перед server lifecycle-проверками держать поднятым внешний control-plane: `python scripts/manage_remote_stack.py start control` или `python scripts/release_server_to_remote.py`.
11. Если `status server` показывает `failed`, но `smoke server` или браузерный GET на `:8666` живы, сначала смотреть строку `external_listener`: это признак ручного `python server.py` вне canonical lifecycle.
12. Если менялся веб-интерфейс, обязательно открыть [admin](http://192.168.100.17:8666/admin) через браузерный MCP; для техпанели проверить status/health/full logs и confirm для `stop/restart`.
13. Для полного verified server-flow предпочитать `python scripts/release_server_to_remote.py`; emergency bypass CI gate допускается только через `--skip-ci-check`.
14. В GitHub публиковать только изменения, которые уже прошли проверки, получили green CI artifact и были запущены по нужному сценарию.

## Observer guard and live canaries

- `python scripts/verify_workspace.py` is now the hard gate for module observer breadcrumbs: every new `BaseCollector` tool must wrap execution with `self.trace_span("tool.entry", ...)`, otherwise workspace verify and module ZIP preflight fail.
- For dangerous observer regressions, use `python scripts/run_observer_canary_suite.py` after deploy to Linux. The suite covers consent approve/deny/timeout, module install/update/remove, retry exhaustion, agent disconnect during operation, and WS ACK/NACK/replay gaps.
