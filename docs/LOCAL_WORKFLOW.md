# Локальная схема работы с `pc_client`

## Точки среды

- Локальная рабочая копия: `C:\Users\admin-2\CodexProjects\pc_client`
- Сетевая шара: `\\192.168.100.17\NTFS_Share\pc_client`
- Удалённый Linux-хост: `altserver@192.168.100.17:/var/chat_bot/pc_client`

## Правило

- Правки и коммиты делаются только в локальной копии на диске машины.
- На шару и на Linux-хост отправляется только проверенное состояние.
- В GitHub публикуется только то, что уже прошло проверку.
- Канонический порядок: локальные правки -> локальные проверки -> локальный commit -> deploy на Linux -> remote start/smoke/browser -> stop -> push проверенных изменений.
- Разовая синхронизация от 17 марта 2026 года уже втянула более новую Linux-версию в локальный Windows-репозиторий. После этого локальная Windows-копия считается главным источником истины.
- Git для Linux настроен через bare-репозиторий `altserver@192.168.100.17:/var/chat_bot/git/pc_client.git`; локальный Windows-remote: `linux`; Linux working copy `/var/chat_bot/pc_client` использует `origin`.

## Рекомендуемый поток

1. Если локальной копии нет или она устарела, обновить её:

```powershell
python scripts/bootstrap_local_workspace.py
```

2. Работать локально в `C:\Users\admin-2\CodexProjects\pc_client`.

3. Перед синхронизацией прогнать быстрые проверки:

```powershell
python scripts/verify_workspace.py
```

4. После локальной проверки сделать локальный commit.

```powershell
git commit -m "<message>"
```

5. При необходимости отправить commit на Linux через Git:

```powershell
git push linux master
```

6. При необходимости посмотреть, что уйдёт на шару:

```powershell
python scripts/sync_local_to_share.py
```

7. Применить синхронизацию на шару:

```powershell
python scripts/sync_local_to_share.py --apply
```

8. Выложить локальную копию на Linux-хост:

```powershell
python scripts/deploy_workspace_to_remote.py
```

9. Поднять сервер на Linux и прогнать smoke:

```powershell
python scripts/manage_remote_stack.py start server
python scripts/manage_remote_stack.py smoke server
```

10. Если менялся GUI сервера, дополнительно проверить:

- [admin](http://192.168.100.17:8666/admin)
- [help](http://192.168.100.17:8666/help)

11. После проверок остановить процессы:

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

## Жёсткий порядок действий

1. Работать только в `C:\Users\admin-2\CodexProjects\pc_client`.
2. Перед изменениями при необходимости обновить локальную копию через `python scripts/bootstrap_local_workspace.py`.
3. Вносить правки локально.
4. Прогнать локальные проверки через `python scripts/verify_workspace.py` и дополнительные тесты по задаче.
5. Если задача затрагивает локальный агент, использовать `python scripts/manage_local_agent.py ...` и проверять нужный сценарий на отдельном инстансе.
6. Только после проверок делать локальный commit.
7. Только после локальной проверки выкладывать состояние на Linux через `python scripts/deploy_workspace_to_remote.py`.
8. Запускать и останавливать удалённый сервер только через `python scripts/manage_remote_stack.py start server` и `python scripts/manage_remote_stack.py stop server`.
9. Если менялся веб-интерфейс, обязательно открыть [admin](http://192.168.100.17:8666/admin) через браузерный MCP.
10. В GitHub публиковать только изменения, которые уже прошли проверки и были запущены по нужному сценарию.
