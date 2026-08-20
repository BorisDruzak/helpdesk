# Пошаговая инструкция: атомарные модули (создание и установка)

Краткий склиз для себя: как создать модуль и установить на агентов через API и веб-панель.

## 1. Создание модуля

### 1.1 Через API (терминал, без веб-панели)

1. Получить токен админки:
   ```bash
   TOKEN=$(curl -s -X POST https://example.test:9443/api/ui_login \
     -H "Content-Type: application/json" \
     -d '{"login":"admin","password":"<пароль>"}' | jq -r '.token')
   ```

2. Создать модуль из кода (единый шаблон на сервере):
   ```bash
   curl -s -X POST https://example.test:9443/api/modules/create \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer $TOKEN" \
     -d '{
       "module_name": "my_tool",
       "version": "1.0.0",
       "tool_name": "get_info",
       "description": "Возвращает информацию",
       "user_function_body": "return {\"ok\": true}",
       "risk_level": "safe_readonly",
       "overwrite": false
     }'
   ```
   При успехе: `status: "success"`, `download_path`, `sha256`. При ошибке валидации/smoke — 400 с `preflight_errors`.

### 1.2 Через веб-панель

1. Открыть https://example.test:9443/admin → вкладка **Модули**.
2. В блоке **Создать модуль из кода** заполнить:
   - Имя модуля, Версия, Имя инструмента, Описание инструмента
   - Уровень риска (safe_readonly / safe_write / dangerous)
   - Тело функции (код) — только тело async-функции, например: `return {"ok": True}`
   - При необходимости включить «Перезаписать при совпадении имени и версии»
3. Нажать **Создать и сохранить модуль**. Сервер соберёт модуль по шаблону, выполнит preflight + smoke; при успехе модуль появится в списке загруженных.

---

## 2. Установка модуля на агентов

### 2.1 Массовая установка через API

1. Убедиться, что модуль создан (есть в `GET /api/modules`).
2. Узнать `device_id` агентов (из `GET /api/devices`).
3. Вызвать массовую установку:
   ```bash
   curl -s -X POST https://example.test:9443/api/modules/bulk_install \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer $TOKEN" \
     -d '{
       "module_name": "my_tool",
       "version": "1.0.0",
       "device_ids": ["device-uuid-1", "device-uuid-2"],
       "replace_if_exists": false
     }'
   ```
   Ответ: 202 Accepted, `operations: [{ device_id, operation_id }, ...]`.
   - Онлайн-агенты: команда уходит сразу; на каждом агенте сначала выполняется smoke-проверка, затем установка.
   - Офлайн-агенты: команда ставится в очередь и выполнится при подключении.

### 2.2 Массовая установка через веб-панель

1. Открыть https://example.test:9443/admin → вкладка **Модули**.
2. В блоке **Массовая установка**:
   - Отметить нужные устройства (чекбоксы; 🟢 — онлайн, 🔴 — офлайн).
   - Выбрать модуль из выпадающего списка.
   - Нажать **Установить на выбранные**.
3. Онлайн-агенты получат установку сразу (сначала smoke на агенте, потом установка), офлайн — при подключении из очереди.

### 2.3 Установка на одно устройство (API)

```bash
curl -s -X POST "https://example.test:9443/api/devices/<device_id>/modules/install" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"module_name": "my_tool", "version": "1.0.0"}'
```
Ответ: 202 Accepted, `operation_id`.

---

## 3. Проверка до сохранения (как в документе)

- **Единый шаблон:** один шаблон костяка на сервере (`server/utils/module_builder.py`) для генерации `module.py` из «только кода функции» + метаданных.
- **Проверка до сохранения:** preflight ZIP (manifest, entrypoint) + smoke_check_module (загрузка, register, list_tools). Модуль не сохраняется, пока smoke не пройдёт.
- **На агенте:** при установке пакета сначала выполняется smoke (загрузка из временной папки, register, list_tools); только при успехе — перенос в store и активация (`pc_agent/core/module_manager.py`).

---

## 4. Полезные эндпоинты

| Метод | URL | Назначение |
|-------|-----|------------|
| POST | /api/modules/create | Создать модуль из кода |
| POST | /api/modules/upload | Загрузить модуль ZIP |
| POST | /api/modules/bulk_install | Массовая установка на device_ids |
| GET  | /api/modules | Список модулей |
| POST | /api/devices/{id}/modules/install | Установка на одно устройство |

Документация контрактов: `server/docs/MODULES_API.md`.
