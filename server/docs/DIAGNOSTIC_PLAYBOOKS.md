# Diagnostic playbooks

Дата обновления: 2026-04-26

## Модель

Плейбук — это версия сценария из шагов. В текущем low-code UI поддержан безопасный класс `diagnostic`: шаги собирают факты и не меняют устройство.

- Конструктор UI: `/app/admin/playbooks`
- Typed API: `GET /api/web/admin/playbooks/catalog`, `POST /api/web/admin/playbooks/save`
- Каталог блоков: `server/playbooks/catalog.py`
- Автозапуск из формы: `server/playbooks/form_triggers.py`
- Исполнение: существующий `server/app/services/playbook_engine.py`

Каждый диагностический шаг должен возвращать структурированный пакет:

- `status`: `success` или `error`
- `found`: найденные факты
- `error_code`: машинный код ошибки или `null`
- `attachments`: ссылки на логи, скриншоты, замеры или другие артефакты

## Диагностика и исправление

Классы разделены намеренно:

- `diagnostic` — только сбор фактов, без изменений на устройстве.
- `remediation` — может менять состояние, но должен идти отдельным flow с подтверждением пользователя/оператора.

Typed builder сейчас сохраняет только `diagnostic`-блоки. Попытка опубликовать `remediation` через этот endpoint отклоняется, чтобы не смешать сбор доказательств и исправляющие действия.

## Минимальный каталог модулей

Базовые диагностические блоки:

- `system.collect` — системный и сетевой снимок.
- `ip_address.get_ip` — IP и базовая сетевая видимость.
- `diag.logs.collect` — пакет логов агента, может требовать согласие.

Типовые шаблоны сценариев:

- `site_not_opening`
- `printer_not_printing`
- `access_issue`
- `agent_offline`
- `internet_not_working`

## Автозапуск из форм

Форма в каталоге `request_forms` может содержать:

```json
{
  "playbook_triggers": [
    {
      "event": "ticket_created",
      "playbook_key": "site_not_opening",
      "module_kind": "diagnostic",
      "enabled": true
    }
  ]
}
```

При создании тикета `server/tickets/create_flow.py` переносит настройки формы в `custom_fields.request_form_playbook_triggers`, строит `facts_package` из ответов формы и запускает последнюю опубликованную версию плейбука с idempotency key `ticket:<ticket_id>:playbook:<key>:ticket_created`.

Результат старта фиксируется событием тикета `playbook_started`; дальнейшие step results остаются в существующих таблицах `playbook_run` / `playbook_step_run` и operation timeline.

## Проверки

Минимальный локальный baseline при изменении этого потока:

- `python -m pytest server/tests/test_playbook_scenarios_no_db.py server/tests/test_web_admin_api.py server/tests/test_ticket_form_packs.py -q --tb=short`
- `pnpm --dir webapp run test -- --run src/features/playbooks/playbook-builder-panel.test.tsx src/features/forms-builder/forms-builder-panel.test.tsx src/features/agent-updates/device-update-panel.test.tsx`
- `pnpm --dir webapp run build`
