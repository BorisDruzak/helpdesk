# Настройка MCP для работы с базой данных

## Текущая ситуация

Я уже могу просматривать данные из вашей SQLite базы данных через терминальные команды `sqlite3`. Также создан удобный скрипт `scripts/view_db.py` для просмотра данных.

## Варианты доступа к базе данных

### 1. ✅ Текущий способ (уже работает)

Я могу выполнять SQL запросы через терминальные команды:

```bash
sqlite3 pc_agent/data/storage.db "SELECT * FROM ticket_state LIMIT 5;"
```

Или использовать созданный скрипт:

```bash
python scripts/view_db.py --stats              # Статистика по всем таблицам
python scripts/view_db.py --table outbox       # Просмотр таблицы outbox
python scripts/view_db.py --query "SELECT ..." # Произвольный SQL запрос
python scripts/view_db.py --info outbox        # Схема таблицы
```

### 2. Настройка MCP сервера для SQLite (опционально)

Если вы хотите, чтобы я имел прямой доступ через MCP инструменты (как сейчас для PostgreSQL), можно настроить MCP сервер.

#### Шаг 1: Установка MCP сервера для SQLite

Есть несколько вариантов:

**Вариант A: Использовать готовый MCP сервер**

```bash
# Установка через npm (если есть готовый пакет)
npm install -g @modelcontextprotocol/server-sqlite
```

**Вариант B: Создать собственный MCP сервер на Python**

Создайте файл `mcp_sqlite_server.py`:

```python
#!/usr/bin/env python3
"""
MCP сервер для работы с SQLite базой данных агента.
"""

import asyncio
import sqlite3
from pathlib import Path
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Путь к базе данных
DB_PATH = Path("/var/chat_bot/pc_client/pc_agent/data/storage.db")

server = Server("sqlite-agent-db")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="sqlite_query",
            description="Выполняет SQL запрос к базе данных агента",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL запрос для выполнения"
                    }
                },
                "required": ["query"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "sqlite_query":
        query = arguments.get("query", "")
        
        try:
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query)
            
            if query.strip().upper().startswith('SELECT'):
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                
                result = []
                result.append(" | ".join(columns))
                result.append("-" * 80)
                for row in rows:
                    result.append(" | ".join(str(row[col]) for col in columns))
                
                conn.close()
                return [TextContent(type="text", text="\n".join(result))]
            else:
                conn.commit()
                conn.close()
                return [TextContent(type="text", text=f"Запрос выполнен. Затронуто строк: {cursor.rowcount}")]
        
        except Exception as e:
            return [TextContent(type="text", text=f"Ошибка: {e}")]
    
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
```

#### Шаг 2: Настройка в Cursor

1. Откройте **Cursor → Settings → AI Settings → MCP Servers**
2. Нажмите **"Add Server"**
3. Заполните:
   - **Name**: `sqlite-agent-db`
   - **Command**: `python3`
   - **Args**: `["/var/chat_bot/pc_client/mcp_sqlite_server.py"]`
   - **Env**: (можно оставить пустым)

4. Сохраните и перезапустите Cursor

#### Шаг 3: Проверка

После настройки я смогу использовать инструмент `sqlite_query` для выполнения запросов напрямую.

### 3. Настройка MCP для MySQL (если нужно)

Если у вас есть MySQL база данных, можно использовать готовый MCP сервер:

```bash
npm install -g @modelcontextprotocol/server-mysql
```

Затем в настройках Cursor:
- **Command**: `npx`
- **Args**: `["-y", "@modelcontextprotocol/server-mysql", "--connection-string", "mysql://user:password@host:port/database"]`

## Рекомендация

Для вашего случая (SQLite база данных) **рекомендую использовать текущий способ** через терминальные команды или скрипт `view_db.py`, так как:

1. ✅ Уже работает без дополнительной настройки
2. ✅ Не требует установки дополнительных зависимостей
3. ✅ Скрипт `view_db.py` предоставляет удобный интерфейс
4. ✅ Я могу выполнять любые SQL запросы через терминал

MCP сервер имеет смысл настраивать, если:
- Нужен более структурированный доступ через инструменты
- Планируется интеграция с другими системами
- Нужны дополнительные возможности (валидация, безопасность и т.д.)

## Примеры использования

### Через терминал (уже работает):

```bash
# Статистика
sqlite3 pc_agent/data/storage.db "SELECT status, COUNT(*) FROM outbox GROUP BY status;"

# Просмотр данных
sqlite3 -header -column pc_agent/data/storage.db "SELECT * FROM ticket_state LIMIT 5;"
```

### Через скрипт:

```bash
# Статистика по всем таблицам
python scripts/view_db.py --stats

# Просмотр таблицы
python scripts/view_db.py --table outbox --limit 20

# Произвольный запрос
python scripts/view_db.py --query "SELECT ticket_id, status, COUNT(*) as events FROM outbox GROUP BY ticket_id, status"

# Схема таблицы
python scripts/view_db.py --info outbox
```

## Структура базы данных

Основные таблицы в `storage.db`:

- **outbox** - очередь событий для отправки (357 записей)
- **ticket_state** - состояние тикетов (12 записей)
- **jobs** - фоновые задачи (12 записей)
- **auth_tokens** - токены аутентификации (2 записи)
- **seq_ticket** - последовательности для тикетов
- **seq_device** - последовательности для устройств
- **rpc_idempotency_cache** - кэш для идемпотентности RPC
- **scheduled_tasks** - запланированные задачи
- **seen_commands** - обработанные команды
- **seen_messages** - обработанные сообщения
- И другие...

Полную схему можно посмотреть командой:
```bash
sqlite3 pc_agent/data/storage.db ".schema"
```

