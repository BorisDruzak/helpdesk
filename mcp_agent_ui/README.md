# MCP Agent UI

MCP-сервер для взаимодействия с UI Bridge агента pc_agent. Позволяет через инструменты MCP вызывать тот же HTTP API, которым пользуется Qt GUI агента.

## Требования

- Агент должен быть запущен с включённым UI Bridge (`ui.enabled: true` в конфиге, по умолчанию порт 8765).
- Python 3.10+.

## Установка

```bash
cd mcp_agent_ui
pip install -r requirements.txt
```

Или из корня репозитория:

```bash
pip install -r mcp_agent_ui/requirements.txt
```

## Запуск

Сервер работает через stdio (ожидает, что Cursor или другой MCP-клиент запустит процесс и обменивается JSON-RPC по stdin/stdout):

```bash
python mcp_agent_ui/server.py
```

Либо из корня репозитория:

```bash
python -m mcp_agent_ui.server
```

(при необходимости добавьте корень репо в `PYTHONPATH` или запускайте из `mcp_agent_ui`.)

## Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `AGENT_UI_BASE_URL` | Базовый URL UI Bridge | `http://127.0.0.1:8765` |

Для агента на другой машине задайте, например: `AGENT_UI_BASE_URL=http://192.168.100.17:8765`.

## Инструменты (tools)

| Имя | Описание |
|-----|----------|
| `agent_ui_health` | Проверка доступности UI Bridge |
| `agent_ui_events` | Long-poll одно событие (job_started, consent_required и др.) |
| `agent_ui_consent_decision` | Отправить решение по согласию (approve/reject) |
| `agent_ui_stop_recording` | Остановить запись экрана по operation_id |
| `agent_ui_get_settings` | Получить настройки агента |
| `agent_ui_update_settings` | Обновить настройки |
| `agent_ui_test_connection` | Проверка подключения к серверу |
| `agent_ui_restart` | Запросить перезапуск агента |
| `agent_ui_request_support` | Запрос в поддержку |
| `agent_ui_chat_send` | Отправить сообщение в чат тикета (ticket_id, text) |

Подробности эндпоинтов — в `pc_agent/ui_bridge/api_server.py` и `pc_agent/ui_bridge/README.md`.

## Настройка в Cursor

См. [docs/MCP_AGENT_UI.md](../docs/MCP_AGENT_UI.md).
