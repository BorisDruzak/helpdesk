# Система модулей - Документация

## Обзор

Система модулей PC Agent позволяет создавать плагины для сбора данных с компьютера. Модули могут быть статическими (в `modules/impl/`) или пакетными (ZIP в `data/modules_store/`, устанавливаются через `install_module_package`).

## Основные компоненты

### BaseCollector

Абстрактный базовый класс для всех модулей.

**Файл:** `pc_agent/modules/base_module.py`

**Контракт:**
```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseCollector(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Уникальное имя модуля."""
        pass
    
    @abstractmethod
    async def collect(self) -> Dict[str, Any]:
        """Асинхронный сбор данных."""
        pass
```

**Пример реализации:**
```python
from modules.base_module import BaseCollector

class SystemCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "system"
    
    async def collect(self) -> Dict[str, Any]:
        import psutil
        return {
            "cpu": psutil.cpu_percent(interval=1),
            "ram": psutil.virtual_memory().percent,
            "disk": psutil.disk_usage('/').percent
        }
```

### ModuleRegistry

Реестр модулей с автоматической регистрацией инструментов через декоратор `@exposed_tool`.

**Файл:** `pc_agent/core/registry.py`

**Использование:**
```python
from core.registry import ModuleRegistry, exposed_tool

registry = ModuleRegistry()

@exposed_tool(
    name="get_system_info",
    description="Get system information",
    risk_level="safe_readonly"
)
async def get_system_info() -> Dict[str, Any]:
    return {"cpu": 45.2, "ram": 67.8}

registry.register(module)
tools = registry.get_tools_flat()
```

### ModuleFactory

Фабрика для динамического создания экземпляров модулей.

**Файл:** `pc_agent/modules/__init__.py`

**Использование:**
```python
from modules import ModuleFactory

factory = ModuleFactory()
collector = factory.create("system")
data = await collector.collect()
```

## Типы модулей

### Статические модули

Модули в `modules/impl/`, загружаются при старте агента.

**Структура:**
```
modules/
├── __init__.py
├── base_module.py
└── impl/
    ├── system.py
    ├── screen.py
    ├── input.py
    └── diag_logs.py
```

**Пример:** `modules/impl/system.py`

### Пакетные модули

Модули, устанавливаемые во время выполнения через `install_module_package` (ZIP с сервера). Хранятся в `data/modules_store/<name>/<version>/`.

## Создание модуля

### Class-based модуль

```python
from modules.base_module import BaseCollector

class CustomCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "custom"
    
    async def collect(self) -> Dict[str, Any]:
        return {
            "custom_data": "value",
            "timestamp": time.time()
        }
```

### Function-based модуль

```python
async def collect() -> Dict[str, Any]:
    """Сбор данных."""
    return {"data": "value"}

# Обертывается в FunctionWrapper автоматически
```

### Модуль с инструментами (tools)

```python
from core.registry import exposed_tool

class CustomCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "custom"
    
    async def collect(self) -> Dict[str, Any]:
        return {}
    
    @exposed_tool(
        name="custom_tool",
        description="Custom tool description",
        risk_level="safe_readonly"
    )
    async def custom_tool(self, param1: str) -> Dict[str, Any]:
        """Кастомный инструмент."""
        return {"result": f"Processed: {param1}"}
```

## Установка модулей

### install_module_package

Установка модуля из пакета через HTTP download или base64 (legacy fallback).

**Новый формат (HTTP download):**
```python
result = await orchestrator.handle_command({
    "cmd": "install_module_package",
    "params": {
        "module_name": "custom_module",
        "module_version": "1.0.0",
        "download_url": "http://server:8666/api/modules/custom_module/1.0.0/download",
        "sha256": "a1b2c3d4e5f6...",
        "size": 12345,
        "package_b64": None,
        "replace_if_different_sha": false
    }
})
```

- **replace_if_different_sha** (опционально, по умолчанию `false`): при переустановке той же версии с другим SHA — если `true`, старый каталог удаляется и пакет устанавливается заново; иначе возвращается ошибка `INSTALL_CONFLICT_SHA`.

**Legacy формат (base64 fallback):**
```python
result = await orchestrator.handle_command({
    "cmd": "install_module_package",
    "params": {
        "module_name": "custom_module",
        "module_version": "1.0.0",
        "package_b64": "base64-encoded-zip",
        "sha256": "hash"
    }
})
```

**Поведение (HTTP download):**
1. Скачивает ZIP по `download_url` во временный файл (streaming)
2. Вычисляет SHA256 при скачивании (потоково)
3. Проверяет SHA256 соответствие (`expected_sha256`)
4. Если проверка успешна → вызывает `install_zip_bytes()`
5. Модуль активируется автоматически
6. Вызывается `_rebuild_registry_from_active_modules()`
7. Отправляется `tools_changed` event если hash изменился

**Поведение (base64 fallback):**
- Декодирует base64 → ZIP bytes
- Проверяет SHA256 (если указан)
- Вызывает `install_zip_bytes()`
- Модуль активируется автоматически
- Вызывается `_rebuild_registry_from_active_modules()`
- Отправляется `tools_changed` event если hash изменился

**Обработка ошибок:**
- `MODULE_DOWNLOAD_FAILED` — ошибка скачивания по HTTP
- `HASH_MISMATCH` — SHA256 не совпадает
- `INSTALL_FAILED` — ошибка установки модуля

## Версионирование модулей

### ModuleManager

Управление версиями модулей с активацией/откатом.

**Файл:** `pc_agent/core/module_manager.py`

**Реальный API ModuleManager:**

- `install_zip_bytes(module_name, version, zip_bytes, sha256=None)` — установка модуля из ZIP
- `activate(module_name, module_version)` — активация версии (возвращает Path к активному модулю)
- `deactivate(module_name)` — деактивация модуля
- `rollback(module_name)` — откат на предыдущую версию (возвращает Path или None)
- `list_installed()` — список установленных модулей и версий (dict)
- `get_active_path(module_name)` — путь к активной версии модуля (или None)
- `remove_version(module_name, version)`, `remove_version_force(...)`, `remove_module(module_name)` — удаление версий/модуля

Команды оркестратора (install_module_package, activate_module, deactivate_module, rollback_module, list_installed_modules) вызывают эти методы внутри.

**Пример:**
```python
from core.module_manager import ModuleManager

module_manager = ModuleManager(data_dir="data", temp_dir="data/temp")

# Установка
await module_manager.install_zip_bytes("custom", "1.0.0", zip_bytes)

# Активация
await module_manager.activate("custom", "1.0.0")

# Откат
await module_manager.rollback("custom")
```

## Инструменты (Tools)

### Регистрация инструментов

Инструменты регистрируются через декоратор `@exposed_tool`:

```python
from core.registry import exposed_tool

@exposed_tool(
    name="get_system_info",
    description="Get system information",
    risk_level="safe_readonly",
    capabilities=["read_system"]
)
async def get_system_info() -> Dict[str, Any]:
    """Получение системной информации."""
    return {"cpu": 45.2, "ram": 67.8}
```

### Параметры инструментов

```python
@exposed_tool(
    name="custom_tool",
    description="Custom tool with parameters",
    risk_level="safe_readonly",
    params_schema={
        "type": "object",
        "properties": {
            "param1": {"type": "string"},
            "param2": {"type": "integer"}
        },
        "required": ["param1"]
    }
)
async def custom_tool(self, param1: str, param2: int = 0) -> Dict[str, Any]:
    """Инструмент с параметрами."""
    return {"result": f"{param1}: {param2}"}
```

### Уровни риска

- `safe_readonly` — безопасное чтение (безопасно)
- `sensitive_read` — чтение чувствительных данных (требует consent)
- `write` — запись данных (требует consent)
- `code_exec` — выполнение кода (требует consent)

### Использование инструментов

```python
# Через orchestrator
result = await orchestrator.handle_command({
    "cmd": "run_tool",
    "tool": "get_system_info",
    "params": {}
})

# Через registry
tools = registry.get_tools_flat()
tool = registry.get_tool("get_system_info")
result = await tool.func()
```

## Реализованные модули

### system

Сбор системной информации (CPU, RAM, диск, сеть).

**Инструменты:**
- `get_system_info` — системная информация
- `get_cpu_info` — информация о CPU
- `get_memory_info` — информация о памяти
- `get_disk_info` — информация о дисках

### screen

Скриншоты экрана и запись экрана (видео). Доступен как встроенный модуль (`modules/impl/screen.py`) и как **пакет для загрузки на сервер** (см. раздел «Пакеты модулей для сервера и агентов»). При стандартной установке агента модуль screen не входит в `enabled_modules` по умолчанию — его нужно либо добавить в конфиг, либо установить пакетом через сервер.

**Инструменты:**
- `screen.collect` — сделать скриншот (preset `primary_monitor`). Возвращает артефакт `kind=screenshot`, загружаемый на сервер. Используется кнопкой «Screenshot» в GUI агента.
- `screen.record` — записать экран в MP4 (параметры: `duration_sec` 1–300, `fps`, `max_width`, `quality_crf`, `monitor`). Presets: `short` (30 сек), `long` (300 сек). Возвращает артефакт `kind=screen_recording`. Досрочная остановка — через STOP-кнопку в GUI (POST `/ui/stop_recording` с `operation_id`). Требуется **ffmpeg** в PATH.

### input

Активность пользователя (клавиатура, мышь).

**Инструменты:**
- `get_keyboard_activity` — активность клавиатуры
- `get_mouse_activity` — активность мыши

### diag_logs

Сбор логов агента.

**Инструменты:**
- `get_logs` — получение логов

## Пакеты модулей для сервера и агентов

Модули из `modules/impl/` (screen, input и др.) при установке агента «из коробки» могут не попадать в рабочий каталог или не быть включены в `enabled_modules`. Чтобы раздавать такие модули через сервер и устанавливать на агенты командой `install_module_package`, их нужно собирать в ZIP-пакеты.

### Структура пакета

- Исходники пакета лежат в **`pc_agent/modules_packages/<module_name>/`**.
- В пакете обязательны:
  - **`manifest.json`** — поля `module_name`, `module_version`, опционально `entrypoint` (по умолчанию `module:register`), `description`, `requirements`.
  - **`module.py`** — код модуля и функция **`register()`**, возвращающая экземпляр `BaseCollector` (для entrypoint `module:register`).

Пример `manifest.json`:

```json
{
  "module_name": "screen",
  "module_version": "1.0.0",
  "description": "Скриншоты и запись экрана",
  "entrypoint": "module:register",
  "requirements": ["mss", "pydantic"]
}
```

### Сборка ZIP

Из корня репозитория:

```bash
python3 scripts/build_module_zip.py screen 1.0.0
```

Скрипт создаёт `dist/screen-1.0.0.zip`, выводит SHA256 и примеры вызовов для загрузки и установки.

### Загрузка на сервер

```bash
curl -X POST -F file=@dist/screen-1.0.0.zip \
  -F module_name=screen -F version=1.0.0 \
  http://localhost:8666/api/modules/upload
```

Или через веб-панель: раздел модулей → загрузка ZIP (поля module_name, version, file).

### Установка на агента

После загрузки модуля на сервер установка на устройство выполняется через API или панель:

- **POST** `/api/devices/{device_id}/modules/install`  
  Тело: `{"module_name": "screen", "version": "1.0.0"}`

Сервер ставит команду `install_module_package` в outbox устройства; агент скачивает ZIP по `download_url`, проверяет SHA256, распаковывает в `data/modules_store/<name>/<version>`, активирует модуль и пересобирает реестр. Модуль появляется в `loaded_modules` и инструменты (например, `screen.collect`) становятся доступны без добавления в `enabled_modules`.

### Готовый пакет: screen

- **Исходники:** `pc_agent/modules_packages/screen/` (manifest.json, module.py).
- **Зависимости:** mss, pydantic; для `screen.record` — ffmpeg в PATH или пакет imageio-ffmpeg.
- После установки пакета на агента ошибка «Экземпляр модуля "screen" не найден в loaded_modules» устраняется: модуль загружается из `modules_store` при старте и при установке.

## Примеры

### Простой модуль

```python
from modules.base_module import BaseCollector

class SimpleCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "simple"
    
    async def collect(self) -> Dict[str, Any]:
        return {"message": "Hello from simple module"}
```

### Модуль с инструментами

```python
from modules.base_module import BaseCollector
from core.registry import exposed_tool

class AdvancedCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "advanced"
    
    async def collect(self) -> Dict[str, Any]:
        return {}
    
    @exposed_tool(
        name="process_data",
        description="Process data",
        risk_level="safe_readonly"
    )
    async def process_data(self, input_data: str) -> Dict[str, Any]:
        """Обработка данных."""
        return {"processed": input_data.upper()}
```

### Динамическая установка

```python
code = """
from modules.base_module import BaseCollector

class DynamicCollector(BaseCollector):
    @property
    def name(self):
        return "dynamic"
    
    async def collect(self):
        return {"dynamic": True}
"""
```

Установка такого модуля выполняется через пакет: соберите ZIP с `manifest.json` и `module.py`, загрузите на сервер, затем используйте `install_module_package` (см. раздел «Пакеты модулей для сервера и агентов»).

## HTTP Download механизм

С версии V3 модули устанавливаются через **HTTP download** вместо передачи base64 в WebSocket:

1. **Сервер загружает модуль:**
   - `POST /api/modules/upload` → сохраняет ZIP на диск и в БД
   - Возвращает `download_url`: `/api/modules/{name}/{version}/download`

2. **Сервер отправляет команду:**
   - `install_module_package` с `download_url`, `sha256`, `size`
   - Команда попадает в `device_outbox` на сервере

3. **Агент получает команду:**
   - Скачивает ZIP по `download_url` (streaming)
   - Проверяет SHA256 при скачивании
   - Устанавливает модуль из скачанного файла

**Преимущества:**
- ✅ Нет ограничения размера (base64 увеличивает размер на ~33%)
- ✅ Потоковая передача (не держит весь ZIP в памяти)
- ✅ Переиспользование модулей (один ZIP для всех устройств)
- ✅ Кеширование (ETag headers)
- ✅ Fallback на base64 для совместимости

## Handshake: modules и modules_inventory

В handshake в payload уходят два поля:

- **modules** — список имён включённых модулей из конфига (`enabled_modules`), для совместимости.
- **modules_inventory** — полный список установленных пакетов с версиями и состоянием (active/installed). Сервер синхронизирует таблицу `device_modules` по **modules_inventory**; при его отсутствии ставит в очередь команду `list_installed_modules`. Подробнее: [PROTOCOL_V3.md](PROTOCOL_V3.md).

## Ссылки

- [AgentOrchestrator документация](ORCHESTRATOR.md) — обработка команд
- [Protocol V3 документация](PROTOCOL_V3.md) — протокол общения с сервером
- [DatabaseManager документация](DATABASE.md) — работа с базой данных
- [BOTTLENECKS_AND_RISKS.md](../../docs/BOTTLENECKS_AND_RISKS.md) — узкие места и риски (модули, ModuleManager API)



## Update 2026-03-11

### Runtime stability
- `ModuleRegistry` now separates public tool alias from `real_method_name`.
- `call_tool()` always invokes the real runtime method, so alias-based tools no longer break when `@exposed_tool(name=...)` differs from the Python method name.
- `ModuleOrchestrator` keeps a persistent module load context and rebuilds built-in modules through one helper path.
- `extra_paths` survives rebuild and now resolves both `<module_name>.py` and legacy `test_<module_name>.py`.
- `ModuleManager` uses one semver-aware ordering helper for `list_installed()`, `rollback()` and GC.

### Agent error codes
- `TOOL_METHOD_NOT_FOUND`
- `MODULE_REBUILD_CONTEXT_LOST`
- `MODULE_MANIFEST_INVALID`
- `MODULE_VERSION_INVALID`
- `MODULE_LOAD_FAILED`
- `MODULE_PLATFORM_MISMATCH`

## Update 2026-03-11: Runtime reload and rollback

- Package-module runtime reload now uses unique Python import keys per module version. This prevents stale code reuse after `install_module_package` or `activate_module`.
- `install_module_package` validates that the new version can be imported, then rebuilds the registry from a clean runtime cache. The active runtime must switch to the new version without a second manual activation.
- `rollback_module` now emits `module_state_changed` immediately after registry rebuild and returns both `active_path` and `active_version` in observations.
- Full registry rebuild clears tracked dynamic imports before loading active package modules, so runtime bindings always come from the currently active version on disk.
## Runtime Convergence Notes

- `activate_module`, `rollback_module`, `deactivate_module`, `remove_module`, and removal of the last installed version now force a runtime purge before the registry rebuild.
- The agent clears the registry entry, loaded module instance, and dynamic loader cache for the target module before rebuilding the active toolset.
- Goal: a removed or deactivated package module must stop being callable without requiring an agent restart.

## Runtime Self-Heal Notes

- `run_tool` and `list_tools` now verify package runtime against the active module inventory before using the registry.
- If `current.json` / active manifest says one version is active, but the in-memory instance points to another version or to a removed package, the agent purges that runtime and rebuilds the registry automatically.
- This protects rollback, deactivate, remove, and restart edge cases from leaving stale package code callable in memory.
