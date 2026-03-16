# Метрики и алерты Playbook / Operations

## Обязательные метрики

- **success-rate** — доля операций со статусом `succeeded` по команде/устройству.
- **timeout-rate** — доля операций со статусом `timed_out` (в т.ч. по `command_name=list_tools`).
- **UNKNOWN_COMMAND-rate** — доля операций с `error_code=UNKNOWN_COMMAND` (целевой показатель: 0 по модульным командам).
- **p95 duration** — 95-й перцентиль длительности выполнения по каждой команде (по `started_at`–`finished_at` из `operations`).

Источник данных: таблица `operations` (поля `status`, `error_code`, `command_name`, `device_id`, `started_at`, `finished_at`).

## Алерты

- Всплеск **list_tools timeout**: например, если за последние 1 ч доля `timed_out` по `command_name=list_tools` превышает порог (например 5% или 1% по плану).
- Всплеск **UNKNOWN_COMMAND**: если за период появляются операции с `error_code=UNKNOWN_COMMAND` (цель: 0 после внедрения capability check и снятия smoke_install_and_run).

## Реализация

- Агрегаты можно считать по `operations` (SQL или выгрузка в систему метрик).
- Канарейка и откат: через флаги `PLAYBOOK_SCHEDULER_ENABLED`, `PLAYBOOK_PARALLEL_ENABLED`, `CAPABILITY_GATE_STRICT` без смены транспорта.
