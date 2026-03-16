# RUNBOOK: Ticket Queue Operations

Операционный runbook для новой модели тикетной очереди.

## Подготовка

1. Остановить сервер:
   `python3 scripts/stop_server.py`
2. Применить миграции:
   `cd server && DATABASE_URL='postgresql+asyncpg://chatbot:chatbot@127.0.0.1:5432/pc_client' PYTHONPATH=. alembic upgrade head`
3. Запустить сервер:
   `python3 scripts/run_server.py`

## Базовая проверка

1. Health:
   `curl -s http://127.0.0.1:8666/api/health`
2. Логин UI:
   `curl -s -X POST http://127.0.0.1:8666/api/ui_login -H 'Content-Type: application/json' -d '{"login":"admin","password":"admin123"}'`
3. Проверить ревизию БД:
   `SELECT version_num FROM alembic_version;`

## API smoke-check

Проверить последовательность:

1. Создание тикета с `requester_profile`.
2. Назначение через `/api/tickets/{id}/assign`: `admin` — ручное/auto, `support` — только на себя (take-to-self).
3. Обновление приоритета через `/api/tickets/{id}/priority` с `urgency`, `importance`, `urgency_reason`, `importance_reason`.
4. Обновление профиля инициатора через `/api/tickets/{id}/requester_profile`.
5. Переходы статусов: `new -> triaged -> in_progress -> resolved`, а `closed` выставляется только после подтверждения пользователя.
6. Проверка `snapshot`: `priority_class`, `requester_display_name`, `history`.

## Браузерная проверка

Использовать только:

`http://192.168.100.17:8666/admin`

Проверить:

1. В очереди нет колонок `SLA FR`, `SLA Res`, `OLA`.
2. Статусы русифицированы и цвета применяются к `waiting_on_*`.
3. Инициатор отображается по `requester_display_name`.
4. В карточке тикета видна двухпанельная компоновка.
5. Левая панель сохраняет профиль инициатора и отражает изменение в истории.

## Наблюдаемость

Контрольные показатели:

1. Время до взятия в работу: `created_at -> first assign/status in_progress`.
2. Время решения: `created_at -> resolved/closed`.
3. Доля waiting-статусов.
4. Загрузка операторов: `active_count` считается только по `in_progress`; `triaged` = «В очереди у оператора».
5. Ошибки лимита назначения: ответы `409 assignment_limit`.

## Завершение

После проверок обязательно остановить сервер:

`python3 scripts/stop_server.py`
