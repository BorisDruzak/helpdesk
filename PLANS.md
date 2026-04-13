# PLANS.md

Этот файл — канонический long-horizon артефакт для задач, которые:

- идут дольше одного короткого сеанса;
- затрагивают несколько подсистем;
- требуют согласованных решений до правок;
- нуждаются в handoff между запусками агента.

## Когда вести этот файл

- Крупная фича или рефакторинг.
- Миграции + код + docs + release.
- Исследование, где решения принимаются не сразу.
- Любая задача, для которой важно сохранить не чат, а актуальное состояние работы.

## Как вести

Обновлять файл по мере движения задачи. Держать его коротким и практичным: только то, что помогает продолжить работу без восстановления контекста из диалога.

## Шаблон

### Goal

- Что нужно получить в итоге.
- Надёжная техпанель с внешним control-plane: server status, health block, полные логи, lifecycle API/actions и подтверждения в GUI.

### Scope

- Что входит в задачу.
- Что явно не входит.
- Входит: `server/control_plane.py`, `server/runtime_control.py`, техпанель `server/admin.*`, runtime-скрипты, docs/rules/skills, обязательные local + remote + browser проверки.
- Не входит: новый отдельный desktop launcher вне Linux-runtime; управление сторонними сервисами вне server/agent/control.

### Constraints

- Инварианты, окружение, риски, правила deploy/verification.
- Источник истины для правок: `C:\Users\admin-2\CodexProjects\pc_client`.
- Linux lifecycle только через штатные скрипты; browser checks только на `http://192.168.100.17:8666/admin`.
- После проверок основной сервер на Linux остановить, если не нужна явная работа дальше.

### Context

- Какие файлы, документы и скрипты канонические для этой задачи.

### Decisions

- Принятые решения и почему.
- Runtime lifecycle вынесен в отдельный control-plane на `:8667`, чтобы `stop/restart` не убивали HTTP-обработчик, который сам же должен вернуть ответ.
- Полные логи берутся из `journalctl` через runtime-control слой, а in-memory ring buffer остаётся быстрым источником alerts.
- GUI требует confirm и reason для `stop/restart`, а все lifecycle actions пишутся в аудит.

### Plan

- [x] Реализовать control-plane, runtime-control слой и CLI/remote wrappers.
- [x] Расширить техпанель статусом сервера, health block, полными логами и confirm-модалкой.
- [ ] Обновить docs/rules/skills и прогнать обязательные проверки.

### Verification

- Какие проверки обязательны.
- Что уже прогнано.
- Обязательные: `python scripts/verify_workspace.py`, релевантный pytest, remote deploy/start/smoke, browser check техпанели, stop server.
- Уже прогнано: `py_compile`, `server/tests/test_admin_tech_api.py`, `server/tests/test_control_plane_api.py` (один параллельный прогон словил deadlock по test DB cleanup, нужен последовательный финальный rerun).

### Handoff

- Что сделано.
- Что осталось.
- Что блокирует.
- Остаточные риски.
- Сделано: основная реализация control-plane/runtime-control/GUI.
- Осталось: финальные doc updates already in progress, затем последовательный verify/pytest и remote/browser-check.
- Блокеров нет; есть только техническая оговорка про параллельный pytest на общей test DB.
