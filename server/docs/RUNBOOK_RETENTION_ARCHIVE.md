# Runbook: Retention и Archive (тикетные данные)

## Назначение (Stage 12)

Перенос старых записей из «горячих» таблиц в архивные для соблюдения политик хранения и разгрузки БД:

- **ticket_events:** hot 180 дней (по умолчанию), остальное → `ticket_events_archive`.
- **ticket_admin_audit:** hot 365 дней (по умолчанию), остальное → `ticket_admin_audit_archive`.

## Конфигурация (переменные окружения)

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| TICKET_RETENTION_ENABLED | false | Включить перенос в archive |
| TICKET_EVENTS_HOT_RETENTION_DAYS | 180 | Дней хранения ticket_events в hot |
| TICKET_ADMIN_AUDIT_HOT_RETENTION_DAYS | 365 | Дней хранения ticket_admin_audit в hot |
| TICKET_RETENTION_BATCH_SIZE | 5000 | Размер батча при переносе |
| TICKET_RETENTION_MAX_BATCHES_PER_RUN | 200 | Максимум батчей за один запуск |
| TICKET_RETENTION_DRY_RUN | true | true — только подсчёт без переноса (для staging) |

## Запуск

Retention выполняется сервисом (по расписанию, например cron ежедневно). Ручной запуск — вызов `ticket_retention_service.run_retention(session)` (например, из админ-скрипта или отдельной джобы).

Рекомендуемое расписание: один раз в сутки в период низкой нагрузки.

## Dry run (staging)

На staging по умолчанию включён `TICKET_RETENTION_DRY_RUN=true`: перенос не выполняется, в логах/отчёте — только сколько записей было бы перенесено. После проверки на production выставить `TICKET_RETENTION_DRY_RUN=false`.

## Отчёт о прогонах

Таблица `ticket_retention_runs`: `started_at`, `finished_at`, `status`, `moved_events`, `moved_audit`, `error`. По ней можно строить отчёты и алерты при `status = 'error'`.

## Идемпотентность

Повторный запуск не дублирует данные: переносятся только записи старше порога; уже перенесённые в archive из hot удалены.

## Связанные документы

- [TICKET_SYSTEM.md](TICKET_SYSTEM.md#этап-12-operational-hardening) — описание этапа 12 (Retention/Archive).
- [DATABASE.md](DATABASE.md) — структура archive-таблиц и миграция 030.
