# Анализ: обновление агента через сервер (remote self-update)

**Дата:** 2026-02-22  
**Цель:** оценка готовности к тестированию и перечень доработок.

---

## 1. Что уже реализовано

### 1.1 Сервер

| Компонент | Статус | Описание |
|-----------|--------|----------|
| **POST /api/agent_builds/upload** | ✅ | Загрузка ZIP/tar.gz, проверка `archive_type`, сохранение в `AGENT_BUILDS_STORAGE_DIR`, запись в `agent_builds`. Только admin. |
| **GET /api/agent_builds** | ⚠️ | Список билдов по target/channel/limit. **Нет проверки auth** (в доке указано «Auth: обязателен»). |
| **GET /api/agent_builds/{target}/{channel}/{version}/download** | ✅ | Выдача файла, Bearer auth, ETag, audit в `agent_build_download_audit`. |
| **POST /api/devices/{device_id}/agent/update** | ✅ | Проверка online, policy system_write (admin), выбор билда (latest или по version), создание операции `agent_update`, `enqueue_command_async("update", params, actor_role)`. Ответ 202 + operation_id. |
| **БД** | ✅ | Таблицы `agent_builds`, `agent_build_download_audit`, миграции 016 и 017 (artifact_filename, archive_type, mime_type). |
| **Доставка команды** | ✅ | Команда `update` попадает в `device_outbox`, отправляется агенту через DeviceOutboxSender в payload: `command`, `params`, `actor_role`. |
| **Обработка command_result** | ✅ | Общая логика: success → mark_succeeded, обновление операции. Специальной обработки для `update` не требуется. |

### 1.2 Агент

| Компонент | Статус | Описание |
|-----------|--------|----------|
| **Приём команды `update`** | ✅ | В `orchestrator_commands`, маршрутизация в `_handle_update(command, meta)`. |
| **Валидация** | ✅ | Проверка actor_role == admin, наличие version/download_url/sha256, archive_type in (zip, tar.gz). |
| **Скачивание** | ✅ | `_download_file_to_path`: Bearer из `identity_manager.token`, проверка 200/401, streaming SHA256 и size. |
| **pending_update.json** | ✅ | Пишется в `data_root/updates/`, поля: version, target, channel, archive_type, artifact_path, received_at, operation_id, requested_by, sha256, size. |
| **Завершение** | ✅ | command_result "scheduled", затем `loop.call_later(restart_delay, lambda: os._exit(EXIT_UPDATE_PENDING))` (код 42). |
| **Режим --verify** | ✅ | В `ws_agent.py`: `_run_verify_mode`, используется launcher’ом для проверки новой версии перед переключением. |

### 1.3 Launcher

| Компонент | Статус | Описание |
|-----------|--------|----------|
| **launcher_main.py** | ✅ | Запуск версии из current.json, при exit 42 или наличии pending_update.json — `apply_update`. |
| **launcher_portable_main.py** | ✅ | То же для portable-режима, авто-определение install_root/data_root. |
| **installer.apply_update** | ✅ | Чтение pending_update.json, распаковка в _staging, backup БД, run_verify, при успехе — переименование staging → versions/<ver>, current.json, update_history.json, удаление pending. При провале verify — восстановление БД, запись в history, rollback. |
| **Формат pending_update** | ✅ | Совместим с тем, что пишет оркестратор (version, archive_type, artifact_path и т.д.). |

### 1.4 Документация

| Файл | Статус |
|------|--------|
| **server/docs/AGENT_UPDATES_API.md** | ✅ Описание API и WS-команды |
| **pc_agent/docs/SELF_UPDATE.md** | ✅ Модель v2, layout, поведение агента и launcher |

---

## 2. Что нужно доработать

### 2.1 Критично для тестирования

1. **Auth для GET /api/agent_builds**  
   В документации указано: «Auth: обязателен». В коде (`handle_list_agent_builds`) проверки `auth_context` нет — любой неавторизованный запрос может получить список билдов.  
   **Действие:** добавить проверку auth (и при необходимости ограничение по роли, как в upload).

### 2.2 Важно для удобства и отладки

2. **UI для запуска обновления**  
   В админке/интерфейсе нет кнопки или формы «Обновить агента на устройстве» (выбор устройства, target/channel/version, запуск POST .../agent/update).  
   **Действие:** добавить в админку раздел или модальное окно: выбор устройства (online), выбор билда (target/channel/version или «latest»), кнопка «Обновить» → вызов API, отображение operation_id и статуса операции.

3. **UI для загрузки билдов (опционально)**  
   Загрузка билда сейчас только через API (curl/Postman). Для тестирования удобно иметь форму в админке: выбор файла, target, channel, version, archive_type, кнопка «Загрузить».

4. **Отображение операций agent_update**  
   Операции с kind=agent_update создаются и обновляются через общий command_result. Стоит убедиться, что в списке операций/тикетов они отображаются с понятным названием (например «Обновление агента») и что после успешного «scheduled» статус операции переходит в succeeded.

### 2.3 Улучшения (по желанию)

5. **Логирование токена при download**  
   В оркестраторе: `logger.debug(f"[UpdateDownload] Using token: {token[:8]}...")` — префикс уже есть, убедиться, что нигде не логируется полный токен.

6. **Тесты**  
   Нет автотестов на сервере для POST .../agent/update (мок агента online, вызов API, проверка записи в outbox и создания операции). Нет E2E: загрузка билда → триггер update → агент получает команду, скачивает, пишет pending, выходит 42 → launcher применяет (такой сценарий можно оформить как ручной или отдельный E2E).

7. **Конфигурация SERVER_PUBLIC_BASE_URL**  
   Download URL строится из `config.SERVER_PUBLIC_BASE_URL`. Если агент в другой сети, этот URL должен быть доступен с устройства. В доке/конфиге явно описать необходимость настройки для продакшена.

---

## 3. Готовность к тестированию

| Аспект | Готовность |
|--------|------------|
| **Сценарий «админ дергает API вручную»** | ✅ Готов: upload (curl), list (curl), POST .../agent/update (curl) при подключённом агенте. Ожидаемое поведение: команда в outbox → агент скачивает, пишет pending, выходит 42 → launcher применяет обновление. |
| **Проверка прав** | ✅ Policy и проверка admin на сервере и в агенте есть. |
| **Безопасность** | ⚠️ List builds без auth — лучше закрыть до тестов. |
| **Удобное тестирование через браузер** | ❌ Нет UI для update и (опционально) для upload. |

**Итог:** бэкенд и агент реализованы и согласованы с документацией. Для целенаправленного тестирования достаточно:  
1) добавить auth для GET /api/agent_builds;  
2) провести ручной E2E (upload → update → проверка на агенте с launcher).  
UI в админке — следующий шаг для удобства, но не блокер для проверки сценария через API.
