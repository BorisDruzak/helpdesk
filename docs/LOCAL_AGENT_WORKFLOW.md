# Локальный запуск отдельных агентов на Windows

## Назначение

Этот сценарий нужен для безопасного запуска одного или нескольких отдельных агентов с Windows-машины, не затрагивая основной удалённый агент на Linux.

Каждый локальный агент запускается как отдельный именованный инстанс со своими каталогами:

- данные: `.local-agent/instances/<name>/data`
- установка: `.local-agent/instances/<name>/install`
- метаданные запуска: `.local-agent/instances/<name>/instance.json`
- launcher log: `.local-agent/instances/<name>/launcher.log`

## Быстрый старт

1. Один раз подготовить окружение:

```powershell
python scripts/manage_local_agent.py bootstrap
```

2. Проверить инициализацию отдельного инстанса:

```powershell
python scripts/manage_local_agent.py verify test-agent
```

3. Запустить отдельный headless-инстанс:

```powershell
python scripts/manage_local_agent.py start test-agent
```

Если токен ещё не выдан, headless-инстанс обычно завершится после попытки запросить токен из консоли. Для первого запуска без токена лучше использовать GUI-режим или сразу передавать `--auth-token`.

4. Запустить отдельный GUI-инстанс:

```powershell
python scripts/manage_local_agent.py start gui-agent --gui
```

5. Посмотреть статус:

```powershell
python scripts/manage_local_agent.py status
python scripts/manage_local_agent.py status test-agent
```

6. Посмотреть логи:

```powershell
python scripts/manage_local_agent.py logs test-agent
```

7. Остановить инстанс:

```powershell
python scripts/manage_local_agent.py stop test-agent
```

## Scripted automation

После запуска GUI-инстанса можно управлять им без ручных кликов через localhost automation surface:

```powershell
python scripts/agent_test_driver.py status gui-agent
python scripts/agent_test_driver.py upsert-profile gui-agent --display-name "QA User" --full-name "QA User" --building HQ --room 101
python scripts/agent_test_driver.py create-ticket gui-agent --title "Printer issue" --description "Тестовая заявка" --form-key printer --ticket-type incident --form-payload-json "{\"cabinet\":\"101\",\"model\":\"HP\",\"printer_number\":\"PR-1\"}"
python scripts/agent_test_driver.py send-message gui-agent --text "Проверка ответа от пользователя"
python scripts/agent_test_driver.py inject-event gui-agent --event-json "{\"event_type\":\"connection_state\",\"data\":{\"state\":\"connected\",\"detail\":\"scripted\"}}"
python scripts/agent_test_driver.py run gui-agent window.close
```

For PowerShell-heavy payloads, pass JSON via stdin or `@file` instead of inline quoting:

```powershell
@{ event_type = "connection_state"; data = @{ state = "connected"; detail = "scripted" } } |
  ConvertTo-Json -Compress |
  python scripts/agent_test_driver.py inject-event gui-agent --event-json -
```

Под капотом driver использует `GET /ui/automation/status` и `POST /ui/automation/run` локального `UiApiServer`, поэтому сценарий остаётся в рамках именованного инстанса и не требует ad-hoc desktop automation.

## Сервер по умолчанию

По умолчанию локальные инстансы идут на удалённый Linux-сервер:

- WS: `ws://192.168.100.17:8666/ws`
- API: `http://192.168.100.17:8666/api`

При необходимости URLs можно переопределить:

```powershell
python scripts/manage_local_agent.py start test-agent --ws-url ws://192.168.100.17:8666/ws --api-url http://192.168.100.17:8666/api
```

## Токен

Если известен токен агента, его можно передать на запуске:

```powershell
python scripts/manage_local_agent.py start test-agent --auth-token "<token>"
```

Токен передаётся только через окружение процесса и не записывается в `instance.json`.

## Правила безопасности

- Не использовать один и тот же `name` для разных живых инстансов.
- Не запускать локальный агент напрямую без `scripts/manage_local_agent.py`, если нужен повторяемый сценарий.
- Не запускать сервер на Windows как рабочий production-стенд, если задача требует штатного окружения Linux.
- После проверки останавливать ненужные локальные инстансы.
