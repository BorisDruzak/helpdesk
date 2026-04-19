# Возможности агента и что нужно для работы

Краткий ориентир: что агент может делать в проекте pc_client и что ему для этого нужно.

## SSH

- **Проверка подключения:** агент может проверить SSH до `altserver@192.168.100.17` (ключ `C:\Users\admin-2\.ssh\pc_client_altserver_ed25519` или пароль через `PC_CLIENT_SSH_PASSWORD`).
- **Выполнение команд на удалённом хосте:** через `ssh` из терминала или через скрипты скилла pc-client-remote-control (`ssh_remote.py exec`, `manage_remote.py`).
- **Ограничение:** интерактивные команды и ввод пароля в stdin с Windows неудобны; предпочтительно использование ключа.

## Миграции на удалённом сервере

- Агент **может** запускать миграции одной командой с Windows: `python scripts/run_remote_migrations.py` (по умолчанию `upgrade head`) или `python scripts/run_remote_migrations.py current`. Скрипт по SSH выполняет на хосте `server/scripts/run_migrations.py`, который подгружает `server/.env` и запускает alembic.
- **Один раз** на удалённом хосте нужно создать `server/.env` с `DATABASE_URL=postgresql+asyncpg://...`. Шаблон: `server/.env.example`. Без этого миграции и сервер на хосте не работают.
- Подробно: скилл **pc-client-migrations** и `server/docs/DATABASE.md`.

## Запуск сервера и агента

- Локальный агент (Windows): только через `python scripts/manage_local_agent.py ...` (именованный инстанс).
- Удалённые сервер и агент (Linux): через `python scripts/manage_remote_stack.py start|stop|restart|smoke|logs server|agent`.
- Агент может вызывать эти скрипты из терминала при наличии доступа к репозиторию и (для удалённого) SSH.

## Что ещё нужно для нормальной работы

- **Локальная копия кода:** `C:\Users\admin-2\CodexProjects\pc_client` — все правки и коммиты только здесь.
- **Скрипты в `scripts/`:** deploy, verify_workspace, manage_remote_stack, manage_local_agent — агент должен использовать их, а не ad-hoc команды.
- **Документация и CODEMAP:** при изменении структуры/API/протокола — обновлять доки и CODEMAP (скилл **pc-client-docs-sync**).
- **Браузер (GUI):** проверки веба только по `http://192.168.100.17:8666/admin` (скилл **pc-client-browser-check**).
- **Секреты:** не логировать сырой токен; не хардкодить пароли в коде; при необходимости использовать `.env` (в .gitignore/.cursorignore).

## Скиллы проекта

Repo-local скиллы проекта сейчас лежат в `.cursor/skills/` (историческое имя каталога):

- **pc-client-tests** — какие тесты и pytest запускать.
- **pc-client-docs-sync** — синхронизация документации и CODEMAP.
- **pc-client-browser-check** — проверка веба, только 192.168.100.17.
- **pc-client-release** — чеклист перед push.
- **pc-client-migrations** — строгие правила миграций, в т.ч. при PostgreSQL на удалённой шаре.
- **pc-client-commit-message** — формат сообщений коммитов.

Использовать их по контексту задачи.
