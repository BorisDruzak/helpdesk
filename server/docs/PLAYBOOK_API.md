# Playbook API (Этап 4 MVP, Этап 6 deferred + idempotency)

Краткое описание API запуска плейбуков.

## POST /api/playbooks/runs

Запускает плейбук на устройстве: создаётся playbook_run. При немедленном запуске первый шаг ставится в device_outbox (run_tool с require_online=False). При отложенном (scheduled_at в будущем) run создаётся со статусом pending и планировщик запустит первый шаг в срок. Продвижение по шагам выполняется при получении command_result (succeeded/failed/timed_out) в WebSocket-обработчике.

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

**Response 500:** ошибка при создании run или постановке команды в outbox.

---

## Модель данных (кратко)

- **playbook** — ключ, имя, домен, владелец.
- **playbook_version** — версия, manifest_json, status (draft/published).
- **playbook_step** — step_key, order_no, type (run_tool), tool (module.tool), params_template_json, continue_on_error и др.
- **playbook_run** — запуск на устройстве: status (pending/running/success/failed), started_at, finished_at, error_code, error_message.
- **playbook_step_run** — исполнение шага: attempt, status, operation_id, started_at, finished_at, input_json, output_json, error_json.

Создание playbook, version и step — через БД или будущий CRUD API. Для теста можно вставить записи вручную.

См. также: `PLAYBOOK_IMPLEMENTATION.md`, миграция 033.
