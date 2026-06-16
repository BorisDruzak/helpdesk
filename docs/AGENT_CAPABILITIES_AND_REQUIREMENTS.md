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
- **Браузер (GUI):** проверки веба выполнять на стенде `https://192.168.100.17:9443`; `/admin` использовать для admin/tech-panel, а web-first requester/web-agent сценарии проверять через соответствующие `/app/*` маршруты (`/app/requester`, `/app/requester/devices`, `/app/device/*`) со скиллом **pc-client-browser-check**.
- **Секреты:** не логировать сырой токен; не хардкодить пароли в коде; при необходимости использовать `.env` (в .gitignore/.cursorignore).

## Скиллы проекта

Проектный канон живёт в `AGENTS.md`, `docs/QUICK_LOOKUP.md`, `docs/LOCAL_WORKFLOW.md`, `scripts/navigation_catalog.py` и профильных docs рядом с кодом. User-level Codex skills в `C:\Users\admin-2\.codex\skills` — вспомогательные подсказки для Codex Desktop; они помогают быстро выбрать workflow, но не заменяют проектную документацию.

- **pc-client-plans** — ведение `PLANS.md` для длинных задач и handoff.
- **pc-client-tests** — какие проверки, pytest, browser/smoke и live-сценарии запускать.
- **pc-client-docs-sync** — синхронизация документации, CODEMAP и контрактов.
- **pc-client-browser-check** — проверка веба через `https://192.168.100.17:9443` на route, который является канонической поверхностью сценария: `/admin` для admin/tech-panel, `/app/*` для React/requester/web-agent.
- **pc-client-release** — чеклист перед commit/push/deploy и фиксация проверок.
- **pc-client-migrations** — строгие правила миграций PostgreSQL и remote alembic.
- **pc-client-commit-message** — формат сообщений коммитов.
- **pc-client-log-triage** — разбор server/agent логов через штатные scripts.
- **pc-client-agent-updates** — launcher, self-update, build upload, canary и rollout.
- **pc-client-agent-runtime** — always-on runtime, tray, ui_bridge, shutdown/restart и logs.
- **pc-client-observer-diagnostics** — observer quick diagnosis, traces, signatures, degradations и dangerous-flow regression.

Дополнительные Codex user-level skills могут жить в `C:\Users\admin-2\.codex\skills`; полезные для этого проекта: **pc-client-safe-workflow**, **pc-client-navigation**, **pc-client-remote-control**. Они помогают приложению автоматически выбрать правильный рабочий цикл, но не заменяют repo-local playbook-и.
