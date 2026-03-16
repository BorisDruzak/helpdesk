# Ping Check Module

Модуль для проверки сетевой доступности через ping команду.

## Описание

Модуль `ping_check` позволяет проверять доступность IP адресов и хостов через ping команду. По умолчанию пингует `192.168.100.250`, но может быть настроен на любой другой адрес.

## Структура модуля

```
ping_check/
├── manifest.json      # Метаданные модуля (обязательно)
├── module.py          # Код модуля с классом PingCheckCollector
├── build.py           # Скрипт для сборки ZIP архива
├── ping_check-1.0.0.zip  # Готовый ZIP архив для загрузки
└── README.md          # Документация модуля
```

## manifest.json

```json
{
  "module_name": "ping_check",
  "module_version": "1.0.0",
  "description": "Module for checking network connectivity by pinging IP addresses",
  "author": "admin",
  "entrypoint": "module.py"
}
```

## Инструменты (Tools)

Модуль предоставляет один инструмент:

### ping_host

Пингует указанный хост и возвращает результат.

**Параметры:**
- `host` (str, default: "192.168.100.250") - IP адрес или hostname для пинга
- `count` (int, default: 4) - Количество пакетов для отправки
- `timeout` (int, default: 5) - Таймаут в секундах

**Возвращает:**
```json
{
  "host": "192.168.100.250",
  "reachable": true,
  "packets_sent": 4,
  "packets_received": 4,
  "packet_loss": "0%",
  "avg_time_ms": 1.5,
  "message": "Host is reachable"
}
```

## Сборка модуля

Для сборки ZIP архива выполните:

```bash
cd /var/chat_bot/pc_client/modules/ping_check
python3 build.py
```

Скрипт создаст файл `ping_check-1.0.0.zip` с SHA256 хешем.

## Загрузка на сервер

1. Откройте страницу модулей: http://192.168.100.17:8666/modules.html
2. В панели "Module Registry" заполните форму:
   - ZIP File: выберите `ping_check-1.0.0.zip`
   - Module Name: `ping_check`
   - Version: `1.0.0`
3. Нажмите "Upload"
4. После загрузки модуль появится в списке загруженных модулей

## Установка на устройство

1. В панели "Devices" выберите устройство
2. В форме "Deploy to Device":
   - Device: выберите устройство
   - Module: выберите `ping_check (1.0.0)`
3. Нажмите "Install"

## Использование инструмента

После установки и активации модуля, инструмент `ping_host` будет доступен через API:

```bash
POST /api/tools/run
{
  "tool_name": "ping_host",
  "params": {
    "host": "192.168.100.250",
    "count": 4,
    "timeout": 5
  },
  "device_id": "...",
  "ticket_id": "..."
}
```

## Особенности

- **Кроссплатформенность**: Модуль автоматически определяет ОС и использует правильную команду ping (Windows/Linux)
- **Обработка ошибок**: Модуль корректно обрабатывает таймауты и ошибки доступа
- **Парсинг результатов**: Автоматически парсит вывод ping команды для извлечения статистики

## Технические детали

- **Класс модуля**: `PingCheckCollector` наследуется от `BaseCollector`
- **Tool регистрация**: Использует декоратор `@exposed_tool` для регистрации `ping_host`
- **Risk level**: `safe_readonly` - модуль только читает сетевую информацию, не изменяет систему
- **Dependencies**: Использует стандартные библиотеки Python (`subprocess`, `platform`) и системные команды ping


