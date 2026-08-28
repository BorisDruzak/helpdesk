# Module Platform Canary Closure v1 — итоговый отчёт

Дата: 2026-08-28
Контур: изолированный staging. Production-хосты, сервисы, БД и учётные данные
не использовались.

## Итог

Acceptance выполнен. Финальный принятый запуск опубликованного рецепта
`network.canary.check@1.0.0` через Helpdesk ticket завершился успешно и прошёл
повторную reconciliation без дубликатов.

Ранние явно разрешённые попытки сохранены только как диагностическая история:
они не редактировались и не переигрывались. Предварительный HTTP 400 финального
запуска не создал Operation: BFF требует `idempotency_key` в JSON-теле. После
передачи ключа в предусмотренном поле принят ровно один запуск в итоговом
acceptance scope.

## Поставленные изменения

- В Endpoint `main` интегрированы 15 canary-fix commits; staging работал на
  `684dab261f995aa80f8c18e347d72878d0fe0edd`.
- Helpdesk hardening включает повторное ограниченное чтение уже созданного
  remote parent: `3f65a543557a36e89e4c95a800f917ab7973c462`.
- Корневая причина terminal projection устранена в
  `f4223cdcef73d271623a4285aafb98e1f500c9eb`: безопасный ответ
  `network.ping` содержит 11 скалярных полей, а локальный контракт разрешает
  максимум 8. Адаптер сохраняет фиксированную безопасную сводку из 7 полей;
  статус, код ошибки и время остаются отдельными полями шага.

## Финальная трасса acceptance

- Ticket: `ef87193f-3824-4aba-a712-65a655cabe7b`.
- Local Operation: `e495b6e4-c066-5753-a718-94e78edcc50d`.
- Remote parent operation: `0368f27e-3c21-4ef4-ab21-2b07db48472b`.

| Проверка | Результат |
| --- | --- |
| Local Operation | ровно 1 |
| EndpointOperationLink | ровно 1, `succeeded` |
| Remote parent | ровно 1, `succeeded` |
| Child steps | ровно 3, все `succeeded`: DNS, ping, TCP |
| DiagnosticEvidence | ровно 1, `endpoint.module.recipe` |
| Ticket.status | не изменён: `in_progress` |
| DeviceOutbox | 0 записей, связанных с Operation |
| ToolService | 0: путь BFF/reconciler использует только typed Endpoint port |
| Legacy WebSocket | 0: legacy WS-dispatch на этом пути отсутствует |

После terminal `succeeded` link наблюдался восемь следующих интервалов
reconciliation: remote parent и единственная DiagnosticEvidence не
дублировались.

## Проверки

- Endpoint full CI: `1971 passed, 36 skipped` (`python -m pytest -q`).
- Helpdesk focused suite: `24 passed`:
  `test_endpoint_module_operation_reconciler`,
  `test_endpoint_modules_http_adapter`,
  `test_endpoint_modules_port_contracts`, `test_endpoint_module_bff`.
- `python -m compileall -q server/endpoint_adapter/modules_http.py` — успешно.

## Rollback и безопасность

- Helpdesk и Endpoint staging environment-файлы восстановлены из снимков и
  сравнены с ними побайтно.
- Временная network-probe allowlist удалена с Windows test VM; EndpointAgent
  перезапущен и находится в состоянии `RUNNING`.
- Helpdesk, Endpoint API и Endpoint worker после отката находились в `active`.
- Временный staging module credential отозван штатной Endpoint CLI.
- Удалены временные credential, cookie, login- и HTTP-response-файлы.
- Redacted off-host evidence:
  `C:\Users\admin-2\Documents\module-platform-evidence\module-platform-canary-closure-v1-2026-08-28.md`
  (SHA-256: `C8EA298F1214C816FC5784FE183F3EC75C2460590532C9292EFF424BA56CAB19`).

Секреты, токены, пароли, cookie и сырые payload в этот отчёт не включены.
