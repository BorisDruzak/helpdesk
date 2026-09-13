# Playbook API

Краткое описание API запуска плейбуков.

## POST /api/playbooks/runs

Запускает playbook run для устройства. При немедленном запуске Helpdesk
разрешает первый шаг только как Endpoint или server capability и передаёт его
через `CapabilityExecutionRouter`; Endpoint capability создаёт ticket-facing
operation facade. Helpdesk не создаёт `device_outbox` и не доставляет команды
агенту локально. При отложенном `scheduled_at` run создаётся со статусом
`pending`, а планировщик запускает его в срок.

**Request (JSON):**

| Поле | Тип | Обязательное | Описание |
|------|-----|--------------|----------|
| playbook_version_id | int | да | ID версии плейбука (playbook_version.id). |
| device_id | string | да | UUID устройства. |
| trigger_type | string | нет | Тип запуска (manual, schedule, …). |
| context_json | object | нет | Контекст для шаблонов параметров (MVP: params как есть). |
| scheduled_at | string | нет | UTC ISO (например 2026-02-21T12:00:00Z). Если в будущем — run создаётся pending, первый шаг поставит планировщик. |
| idempotency_key | string | нет | Ключ идемпотентности: при повторном POST с тем же ключом возвращается 200 и существующий run. |
| dry_run | bool | нет | Если true — только валидация (версия и шаги), ответ 200 без создания run. |

**Response 202 Accepted (новый run):**

```json
{
  "playbook_run_id": 1,
  "status": "running"
}
```
или при отложенном запуске: `"status": "pending"`.

**Response 200 OK (idempotency или dry_run):**

При idempotency_key и существующем run:
```json
{
  "playbook_run_id": 1,
  "status": "running"
}
```
При dry_run:
```json
{
  "valid": true,
  "playbook_version_id": 1,
  "steps_count": 3,
  "version_status": "published"
}
```

**Response 400:** неверный JSON или отсутствуют playbook_version_id/device_id.

**Response 404:** версия плейбука не найдена.

**Response 500:** ошибка при создании run или разрешении capability.

---

## Модель данных (кратко)

- **playbook** — ключ, имя, домен, владелец.
- **playbook_version** — версия, manifest_json, status (draft/published).
- **playbook_step** — step_key, order_no, type (logical tool-backed step),
  tool (capability id), params_template_json, continue_on_error и др.
- **playbook_run** — запуск на устройстве: status (pending/running/success/failed), started_at, finished_at, error_code, error_message.
- **playbook_step_run** — исполнение шага: attempt, status, operation_id, started_at, finished_at, input_json, output_json, error_json.

Tool-backed step обязан разрешаться в Endpoint или server capability; иначе run
фиксирует `ENDPOINT_ONLY_CAPABILITY_REQUIRED`. Создание playbook, version и
step — через БД или будущий CRUD API. Для теста можно вставить записи вручную.

См. также: `PLAYBOOK_IMPLEMENTATION.md`, миграция 033.
