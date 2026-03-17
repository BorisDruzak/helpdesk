# MCP Agent UI — подключение к Cursor (пошагово)

MCP-сервер **agent-ui-bridge** даёт доступ к UI Bridge агента pc_agent (те же действия, что в Qt GUI: здоровье, события, consent, настройки, отправка сообщений в чат и т.д.).

---

## Шаг 1. Установить зависимости MCP

В терминале из **корня репозитория** (папка `pc_client`):

```powershell
pip install -r mcp_agent_ui/requirements.txt
```

Проверка: команда `python mcp_agent_ui/server.py` не должна выдавать ошибок импорта (процесс повиснет на вводе — это нормально, закройте Ctrl+C).

---

## Шаг 2. Конфиг MCP уже в проекте

В проекте уже есть файл **`.cursor/mcp.json`** с сервером `agent-ui-bridge`:

- **command:** `python`
- **args:** `["mcp_agent_ui/server.py"]`
- Cursor запускает процесс с **рабочей директорией = корень проекта**, поэтому такой путь корректен.

Если у вас Python не в PATH при запуске Cursor (или нужен другой интерпретатор), откройте `.cursor/mcp.json` и замените `"command": "python"` на полный путь, например:

```json
"command": "C:/Users/admin-2/AppData/Local/Programs/Python/Python314/python.exe"
```

Для **агента на другой машине** добавьте в конфиг переменную окружения. Пример `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "agent-ui-bridge": {
      "command": "python",
      "args": ["mcp_agent_ui/server.py"],
      "env": {
        "AGENT_UI_BASE_URL": "http://192.168.100.17:8765"
      }
    }
  }
}
```

Сохраните файл.

---

## Шаг 3. Открыть настройки MCP в Cursor

1. Откройте **Cursor** с проектом **pc_client** (корень репозитория как папка/workspace).
2. Откройте настройки:
   - **Windows/Linux:** `Ctrl + Shift + J`
   - **Mac:** `Cmd + Shift + J`
3. В левой панели выберите **Tools & MCP** (или **Features → MCP** / **MCP** — в зависимости от версии).

---

## Шаг 4. Убедиться, что сервер подхватился

- В списке MCP должен появиться сервер **agent-ui-bridge** (он читается из `.cursor/mcp.json`).
- Если его нет — проверьте, что файл сохранён и путь к проекту именно корень `pc_client`.
- Переключатель (toggle) рядом с сервером должен быть **включён**.

Если вы **вручную** добавляли сервер через «Add new MCP server», можно не дублировать: либо только `.cursor/mcp.json`, либо только запись в UI (глобальные настройки). Для проекта удобнее один источник истины — `.cursor/mcp.json`.

---

## Шаг 5. Полный перезапуск Cursor

MCP-серверы подхватываются при старте Cursor.

1. Закройте Cursor полностью (все окна).
2. Запустите Cursor снова и откройте проект **pc_client**.

После перезапуска сервер `agent-ui-bridge` должен быть в списке и активен.

---

## Шаг 6. Проверка работы

1. **Запустите агент** с включённым UI Bridge (порт 8765), например локально с GUI или `ui.enabled: true` в конфиге.
2. В **чате с Agent** напишите, например: «Проверь доступность UI Bridge агента» или «Вызови agent_ui_health».
3. Agent должен вызвать инструмент `agent_ui_health` и вернуть JSON с `status`, `service`, `subscribers`.

Если видите ошибку подключения — агент не запущен или не слушает 8765; для удалённого агента проверьте `AGENT_UI_BASE_URL` в `.cursor/mcp.json` и доступность порта (файрвол, SSH-туннель).

---

## Устранение неполадок

| Проблема | Что сделать |
|----------|-------------|
| Сервер не появляется в списке | Проверить наличие и синтаксис `.cursor/mcp.json`. Полный перезапуск Cursor. Открыт ли именно корень pc_client. |
| Ошибка «python not found» / не запускается | В `.cursor/mcp.json` указать полный путь к `python.exe` в `command`. |
| Ошибка импорта (mcp, httpx) | Выполнить `pip install -r mcp_agent_ui/requirements.txt` для того же Python, что указан в `command`. |
| Ошибка подключения к UI Bridge | Запустить агент с UI Bridge (8765). Для удалённого агента задать `AGENT_UI_BASE_URL` в `env` в `.cursor/mcp.json`. |
| Логи MCP | В Cursor: **View → Output** (или `Ctrl+Shift+U` / `Cmd+Shift+U`), в выпадающем списке выбрать **MCP** или **MCP Logs**. |

---

## Предварительные условия (кратко)

- Агент запущен с **UI Bridge** (`ui.enabled: true`, по умолчанию порт **8765**).
- В окружении, откуда Cursor запускает `python`, установлены зависимости из `mcp_agent_ui/requirements.txt`.

---

## Доступные инструменты (tools)

| Инструмент | Назначение |
|------------|------------|
| `agent_ui_health` | Проверка доступности UI Bridge |
| `agent_ui_events` | Получить одно событие (long-poll) |
| `agent_ui_consent_decision` | Решение по согласию (approve/reject) |
| `agent_ui_stop_recording` | Остановить запись экрана |
| `agent_ui_get_settings` | Получить настройки агента |
| `agent_ui_update_settings` | Обновить настройки |
| `agent_ui_test_connection` | Проверка подключения к серверу |
| `agent_ui_restart` | Запросить перезапуск агента |
| `agent_ui_request_support` | Запрос в поддержку |
| `agent_ui_chat_send` | Отправить сообщение в чат тикета (ticket_id, text) |

Подробности по API — в `mcp_agent_ui/README.md` и `pc_agent/ui_bridge/README.md`.
