# OS Check Module

Модуль для проверки операционной системы и сбора информации о системе.

## Описание

Модуль `os_check` определяет тип операционной системы (Windows, Linux, Mac) и собирает детальную информацию о системе, используя только стандартные библиотеки Python.

## Импорты (BaseCollector, exposed_tool)

Модули, устанавливаемые на агента через сервер, загружаются в окружении агента. В frozen-сборке (PyInstaller) пакет `pc_agent` может отсутствовать в `sys.path`, поэтому в коде используется совместимый импорт: сначала `pc_agent.*`, при `ImportError` — `modules.base_module` и `core.registry`. Так модуль работает и из исходников, и из собранного агента.

## Структура модуля

```
os_check/
├── manifest.json      # Метаданные модуля (обязательно)
├── module.py          # Код модуля с классом OSCheckCollector
├── build.py           # Скрипт для сборки ZIP архива
├── os_check-1.0.0.zip  # Готовый ZIP архив для загрузки
└── README.md          # Документация модуля
```

## manifest.json

```json
{
  "module_name": "os_check",
  "module_version": "1.0.0",
  "description": "Module for checking operating system information (Windows, Linux, Mac)",
  "author": "admin",
  "entrypoint": "module.py"
}
```

## Инструменты (Tools)

Модуль предоставляет один инструмент:

### get_os_info

Собирает информацию об операционной системе.

**Параметры:** Нет параметров

**Возвращает:**
```json
{
  "os_type": "Linux",
  "os_name": "Linux",
  "os_version": "6.12.27-6.12-alt1",
  "os_release": "6.12.27",
  "architecture": "x86_64",
  "machine": "x86_64",
  "processor": "x86_64",
  "platform": "Linux-6.12.27-6.12-alt1-x86_64-with-glibc2.38",
  "python_version": "3.11.5",
  "python_implementation": "CPython",
  "distribution": "ALT Linux",
  "distribution_version": "10.2",
  "distribution_id": "alt",
  "distribution_pretty_name": "ALT Linux 10.2"
}
```

### Примеры для разных ОС

#### Windows
```json
{
  "os_type": "Windows",
  "os_name": "Windows",
  "os_version": "10.0.19045",
  "os_release": "10",
  "architecture": "AMD64",
  "windows_version": "10",
  "windows_build": "19045",
  "windows_release": "10"
}
```

#### macOS
```json
{
  "os_type": "Mac",
  "os_name": "Darwin",
  "os_version": "Darwin Kernel Version 23.1.0",
  "os_release": "23.1.0",
  "architecture": "arm64",
  "macos_version": "14.1.0"
}
```

#### Linux
```json
{
  "os_type": "Linux",
  "os_name": "Linux",
  "os_version": "6.12.27-6.12-alt1",
  "os_release": "6.12.27",
  "architecture": "x86_64",
  "distribution": "ALT Linux",
  "distribution_version": "10.2",
  "distribution_id": "alt"
}
```

## Сборка модуля

Для сборки ZIP архива выполните:

```bash
cd /var/chat_bot/pc_client/modules/os_check
python3 build.py
```

Скрипт создаст файл `os_check-1.0.0.zip` с SHA256 хешем.

## Загрузка на сервер

1. Откройте страницу модулей: http://192.168.100.17:8666/modules.html
2. В панели "Module Registry" заполните форму:
   - ZIP File: выберите `os_check-1.0.0.zip`
   - Module Name: `os_check`
   - Version: `1.0.0`
3. Нажмите "Upload"
4. После загрузки модуль появится в списке загруженных модулей

## Установка на устройство

1. В панели "Devices" выберите устройство
2. В форме "Deploy to Device":
   - Device: выберите устройство
   - Module: выберите `os_check (1.0.0)`
3. Нажмите "Install"

## Использование инструмента

После установки и активации модуля, инструмент `get_os_info` будет доступен через API:

```bash
POST /api/tools/run
{
  "tool_name": "get_os_info",
  "params": {},
  "device_id": "...",
  "ticket_id": "..."
}
```

## Особенности

- **Кроссплатформенность**: Модуль работает на Windows, Linux и macOS
- **Только стандартные библиотеки**: Использует только `platform` и `sys` из стандартной библиотеки Python
- **Детальная информация**: Собирает специфичную информацию для каждой ОС:
  - Linux: информация о дистрибутиве из `/etc/os-release`
  - Windows: версия, билд и редакция Windows
  - macOS: версия macOS
- **Обработка ошибок**: Корректно обрабатывает случаи, когда информация недоступна

## Технические детали

- **Класс модуля**: `OSCheckCollector` наследуется от `BaseCollector`
- **Tool регистрация**: Использует декоратор `@exposed_tool` для регистрации `get_os_info`
- **Risk level**: `safe_readonly` - модуль только читает системную информацию, не изменяет систему
- **Dependencies**: Использует только стандартные библиотеки Python (`platform`, `sys`)
- **Методы определения ОС**:
  - `platform.system()` - основной метод определения ОС
  - `/etc/os-release` - для Linux дистрибутивов
  - `platform.win32_ver()` - для Windows
  - `platform.mac_ver()` - для macOS

