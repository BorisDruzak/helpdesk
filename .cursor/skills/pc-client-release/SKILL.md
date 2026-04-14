---
name: pc-client-release
description: Checklist before pushing pc_client to GitHub. Use when preparing to push or to document what was verified.
---

# PC Client — чеклист перед push в GitHub

Пуш в GitHub только для **проверенных** изменений.

## Что должно быть сделано

1. **Правки** — только в локальной копии `C:\Users\admin-2\CodexProjects\pc_client`.
2. **Локальные проверки:**  
   `python scripts/verify_workspace.py` + релевантные pytest (`server/tests/`, `pc_agent/tests/`) по области изменений.
   Если меняется agent release/update flow — следовать скиллу `pc-client-agent-updates` и не выпускать изменённый бинарь под старой версией.
   Если меняется always-on runtime / tray / runtime logs — следовать скиллу `pc-client-agent-runtime` и не закрывать задачу без живого E2E через `manage_local_agent.py`.
3. **Green CI artifact для коммита:**  
   `python scripts/run_ci_suite.py`  
   или self-hosted runner `python scripts/run_ci_in_temp_workspace.py`.
4. **Локальный коммит** — после успешных проверок.
5. **Deploy на Linux** (если нужен прогон на стенде):  
   `python scripts/deploy_workspace_to_remote.py`  
   затем при необходимости: start `control` → start server → smoke → browser check → stop server.
   По умолчанию deploy/release scripts требуют green CI artifact; emergency bypass только через `--skip-ci-check`.
6. **Фиксация в отчёте:** что изменено, что проверено, что не проверено, остаточные риски.
7. Если задача велась в несколько шагов или сессий — обновить `PLANS.md` перед handoff.

## Что не пушить

- Непроверенный код.
- Секреты, сырые токены, пароли в коде (допустим только префикс токена в логах).
- Временные отладочные правки без последующей очистки.

## Перед push

- Кратко зафиксировать: какие тесты/сценарии прошли, затронута ли веб-часть (и проверена ли в браузере по `http://192.168.100.17:8666/admin`), проверялись ли status/health/full logs/confirm в техпанели, поднят ли `control-plane`, остановлен ли сервер на Linux после проверок (если не оставлен специально).
