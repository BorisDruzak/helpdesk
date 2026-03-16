# AgentOrchestrator - Документация

## Обзор

`AgentOrchestrator` — это универсальный контроллер агента, который обрабатывает все команды и координирует работу модулей сбора данных. Является единой точкой входа для выполнения команд.

**Файл:** `pc_agent/core/orchestrator.py`

## Основные возможности

- ✅ Единая точка входа: `handle_command()`
- ✅ Унифицированные ответы: формат `ToolResponse`
- ✅ Управление модулями сбора данных
- ✅ Установка модулей из пакетов (`install_module_package`)
- ✅ Выполнение скриптов в памяти (`exec_script`)
- ✅ Версионирование модулей (активация/откат)
- ✅ Полная обработка ошибок с логированием
- ✅ Интеграция с JobManager для фоновых задач
- ✅ Отправка `tools_changed` event при изменении toolset

## Инициализация

```python
from core.orchestrator import AgentOrchestrator
from core.database import DatabaseManager

db_manager = DatabaseManager("data/storage.db")
await db_manager.initialize()

orchestrator = AgentOrchestrator(
    db_manager=db_manager,
    enabled_modules=["system", "screen", "input"],
    agent_uuid="agent-uuid",
    identity_manager=identity_manager
)

await orchestrator.initialize()
```

**Параметры конструктора:**
- `db_manager` (опционально) — менеджер базы данных
- `enabled_modules` (опционально) — список имен активных модулей
- `agent_uuid` (опционально) — идентификатор агента
- `identity_manager` (опционально) — менеджер идентификации для загрузки артефактов

## Основной метод: handle_command

### Сигнатура

```python
async def handle_command(self, command: Dict[str, Any]) -> Dict[str, Any]
```

### Формат команды

```python
{
    "cmd": "command_name",
    "modules": ["module1", "module2"],  # опционально
    "params": {...},  # опционально
    "request_id": "uuid",  # опционально
    "device_id": "uuid",  # опционально
    "actor_role": "user"  # опционально
}
```

### Формат ответа

Все команды возвращают ответ в формате `ToolResponse`:

```python
{
    "status": "success" | "error" | "partial",
    "data": {...},
    "error": {...},  # только при status="error"
    "meta": {
        "timestamp": "2026-01-08T21:10:57.027006+00:00",
        "command": "ping",
        "request_id": "uuid",
        "agent_id": "uuid",
        "duration_ms": 123.45
    }
}
```

## Поддерживаемые команды

### ping

Проверка статуса агента.

**Запрос:**
```python
{"cmd": "ping"}
```

**Ответ:**
```python
{
    "status": "success",
    "data": {
        "status": "online",
        "uptime": 12345.67,
        "agent_version": "3.0.0",
        "modules_count": 3
    }
}
```

### collect

Сбор данных с модулей.

**Запрос:**
```python
{"cmd": "collect"}  # все модули
{"cmd": "collect", "modules": ["system", "screen"]}  # конкретные модули
```

**Ответ:**
```python
{
    "status": "success",
    "data": {
        "system": {
            "cpu": 45.2,
            "ram": 67.8,
            "disk": 34.5
        },
        "screen": {
            "screenshot": "base64-encoded-image"
        }
    }
}
```

### list_modules

Список доступных (активных) модулей.

**Запрос:**
```python
{"cmd": "list_modules"}
```

**Ответ:**
```python
{
    "status": "success",
    "data": {
        "modules": [
            {
                "name": "system",
                "version": "1.0.0",
                "status": "active"
            },
            {
                "name": "screen",
                "version": "1.0.0",
                "status": "active"
            }
        ]
    }
}
```

### list_installed_modules

Список установленных модулей (все версии).

**Запрос:**
```python
{"cmd": "list_installed_modules"}
```

**Ответ:**
```python
{
    "status": "success",
    "data": {
        "modules": [
            {
                "name": "system",
                "versions": ["1.0.0", "1.0.1"],
                "active_version": "1.0.1"
            }
        ]
    }
}
```

### list_tools

Список доступных инструментов (tools).

**Запрос:**
```python
{"cmd": "list_tools"}
```

**Ответ:**
```python
{
    "status": "success",
    "data": {
        "observations": {
            "tools": [
                {
                    "tool": "get_system_info",
                    "module": "system",
                    "spec": {
                        "description": "Get system information",
                        "risk_level": "safe_readonly",
                        "params_schema": {...}
                    }
                }
            ]
        }
    }
}
```

**Примечание:** Используется для синхронизации toolset с сервером. Сервер запрашивает `list_tools` при изменении `toolset_hash`.

### activate_module

Активация модуля (переключение на версию).

**Запрос:**
```python
{
    "cmd": "activate_module",
    "name": "system",
    "version": "1.0.1",
    "actor_role": "user"
}
```

**Ответ:**
```python
{
    "status": "success",
    "data": {
        "name": "system",
        "version": "1.0.1",
        "status": "activated"
    }
}
```

**Побочные эффекты:**
- Вызывается `_rebuild_registry_from_active_modules()`
- Отправляется `tools_changed` event если hash изменился

### rollback_module

Откат модуля на предыдущую версию.

**Запрос:**
```python
{
    "cmd": "rollback_module",
    "name": "system",
    "actor_role": "user"
}
```

**Ответ:**
```python
{
    "status": "success",
    "data": {
        "name": "system",
        "previous_version": "1.0.1",
        "current_version": "1.0.0",
        "status": "rolled_back"
    }
}
```

**Побочные эффекты:**
- Вызывается `_rebuild_registry_from_active_modules()`
- Отправляется `tools_changed` event если hash изменился

### deactivate_module

Деактивация модуля.

**Запрос:**
```python
{
    "cmd": "deactivate_module",
    "name": "system",
    "actor_role": "user"
}
```

**Ответ:**
```python
{
    "status": "success",
    "data": {
        "name": "system",
        "status": "deactivated"
    }
}
```

### install_module_package

Установка модуля из пакета (base64-encoded zip).

**Запрос:**
```python
{
    "cmd": "install_module_package",
    "name": "custom_module",
    "version": "1.0.0",
    "package_b64": "base64-encoded-zip",
    "sha256": "hash",
    "actor_role": "user"
}
```

**Ответ:**
```python
{
    "status": "success",
    "data": {
        "name": "custom_module",
        "version": "1.0.0",
        "status": "installed"
    }
}
```

**Побочные эффекты:**
- Пакет распаковывается и валидируется
- SHA256 проверяется
- Модуль активируется автоматически
- Вызывается `_rebuild_registry_from_active_modules()`
- Отправляется `tools_changed` event если hash изменился

### exec_script

Выполнение скрипта в памяти (без сохранения).

**Запрос:**
```python
{
    "cmd": "exec_script",
    "code": "import time; return {'timestamp': time.time()}",
    "actor_role": "user"
}
```

**Ответ:**
```python
{
    "status": "success",
    "data": {
        "result": {...}
    }
}
```

**Безопасность:**
- Код валидируется через `CodeValidator`
- Выполняется в изолированном контексте
- Результат не сохраняется в БД

### get_manifest

Получение манифеста агента (метаданные).

**Запрос:**
```python
{"cmd": "get_manifest"}
```

**Ответ:**
```python
{
    "status": "success",
    "data": {
        "agent_version": "3.0.0",
        "db_schema_version": 5,
        "modules": [...],
        "tools": [...]
    }
}
```

## Внутренние методы

### _rebuild_registry_from_active_modules

Пересборка реестра модулей из активных модулей.

**Использование:**
- Вызывается после `activate_module`, `rollback_module`, `deactivate_module`, `install_module_package`
- Отправляет `tools_changed` device event если hash изменился

**Edge Guard:** Событие отправляется только если `toolset_hash` изменился.

### _build_tools_list

Построение списка инструментов для `list_tools` и `toolset_hash`.

**Критично:** Должен возвращать **ТОЧНО** тот же формат, что и `_handle_list_tools()` (полный spec).

## Интеграция с JobManager

```python
job_manager = JobManager(db_manager=db_manager, ...)
orchestrator.attach_job_manager(job_manager)
```

После подключения JobManager доступен через `self.job_manager` для создания фоновых задач.

## Интеграция с EventBus

```python
orchestrator.ui_bus = event_bus
```

После установки EventBus события публикуются в реальном времени для UI.

## Toolset Hash и Tools Changed Event

Агент отслеживает изменения toolset через `toolset_hash`:

1. При `_rebuild_registry_from_active_modules()` вычисляется новый hash
2. Если hash изменился, отправляется `tools_changed` device event
3. Сервер может запросить `list_tools` для синхронизации

**Формат tools_changed event:**
```json
{
    "event": "tools_changed",
    "toolset_hash": "a1b2c3d4e5f6",
    "tools_count": 10,
    "tools_version": "tools_v1",
    "agent_version": "3.0.0",
    "reason": "registry_rebuilt"
}
```

## Обработка ошибок

Все команды обрабатывают ошибки унифицированно:

```python
{
    "status": "error",
    "error": {
        "code": "ERROR_CODE",
        "message": "Error description",
        "details": {...}
    },
    "meta": {...}
}
```

**Типичные коды ошибок:**
- `MODULE_NOT_FOUND` — модуль не найден
- `VALIDATION_ERROR` — ошибка валидации кода
- `INSTALLATION_FAILED` — ошибка установки модуля
- `EXECUTION_ERROR` — ошибка выполнения команды

## Примеры использования

### Базовый пример

```python
from core.orchestrator import AgentOrchestrator

orchestrator = AgentOrchestrator(enabled_modules=["system"])
await orchestrator.initialize()

# Ping
result = await orchestrator.handle_command({"cmd": "ping"})
print(result["data"]["status"])  # "online"

# Collect
result = await orchestrator.handle_command({"cmd": "collect"})
print(result["data"]["system"]["cpu"])  # 45.2

# List modules
result = await orchestrator.handle_command({"cmd": "list_modules"})
print(result["data"]["modules"])  # [...]
```

### Установка модуля

```python
code = """
from modules.base_module import BaseCollector

class CustomCollector(BaseCollector):
    @property
    def name(self):
        return "custom"
    
    async def collect(self):
        return {"custom_data": "value"}
"""

# Установка: соберите пакет (ZIP) и используйте install_module_package
result = await orchestrator.handle_command({
    "cmd": "install_module_package",
    "params": {"module_name": "custom", "module_version": "1.0.0", "download_url": "..."},
    "actor_role": "admin"
})
print(result["status"])  # "success"
```

## Ссылки

- [Protocol V3 документация](PROTOCOL_V3.md) — протокол общения с сервером
- [DatabaseManager документация](DATABASE.md) — работа с базой данных
- [Система модулей документация](MODULES.md) — создание модулей


