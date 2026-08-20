# Анализ тикетной системы и CRM-готовности

Актуальный обзор по состоянию ticketing/request system в архитектуре агент-сервер: что уже реализовано, что остаётся узким местом и что стоит делать дальше, если цель именно полноценная система заявок или CRM.

**Дата:** 2026-03-15

## 1. Что уже есть в проекте

Серверная часть уже закрывает большую часть классического service desk / helpdesk:

- создание тикета через `POST /api/tickets/create` c DB-first сохранением;
- очереди, правила маршрутизации, ручной и серверный порядок в очереди;
- SLA и OLA, breach-метрики, бизнес-календари;
- назначение исполнителя, RBAC, workflow статусов;
- чат в контексте тикета через `ticket_events`;
- worklog, watchers, ticket links, parent-child, KB links;
- problems, change links, in-app notifications, notification preferences;
- публичная очередь `/queue` с безопасным read-only API;
- отдельная карточка тикета и админская очередь в web UI.

По факту это уже не "заготовка", а довольно развитая ITSM/helpdesk система.

## 2. Что было багом раньше, но уже исправлено

Часть исторических замечаний больше не актуальна и не должна попадать в новый backlog:

- `chat_raise` теперь создаёт тикет с `status="new"` и `requester_id=agent_id` в [server/websocket/agent_handler.py](/example.test/NTFS_Share/pc_client/server/websocket/agent_handler.py#L1877).
- начальное сообщение при создании тикета уже пишет `sender_role="user"` в [server/tickets/handlers.py](/example.test/NTFS_Share/pc_client/server/tickets/handlers.py#L586).
- документация уже зафиксировала это поведение в [server/docs/TICKET_SYSTEM.md](/example.test/NTFS_Share/pc_client/server/docs/TICKET_SYSTEM.md).

## 3. Актуальные проблемы и пробелы

### P0. Это пока не CRM, а service desk с CRM-полями

В схеме есть тикеты, очереди, worklog, уведомления, problems и change links, но нет отдельных сущностей:

- клиента / контакта;
- компании / организации;
- лида / сделки;
- воронки / стадий продаж;
- истории коммуникаций по клиенту вне тикета.

Это видно по текущей модели данных в [server/app/db/models.py](/example.test/NTFS_Share/pc_client/server/app/db/models.py#L23): есть `tickets`, `ticket_events`, `ticket_queues`, `ticket_watchers`, `ticket_worklogs`, `problems`, `ticket_change_links`, но нет `customers`, `contacts`, `organizations`, `deals`, `pipelines`.

Если цель именно CRM, нужен отдельный домен данных, а не только расширение `tickets.custom_fields`.

### P0. Критичный разрыв между API и UI

Бэкенд уже умеет:

- watchers;
- links/parent-child;
- KB links;
- problems;
- change links;
- notification preferences;
- ticket metrics.

Это видно по маршрутам в [server/routes.py](/example.test/NTFS_Share/pc_client/server/routes.py#L296) и обработчикам в [server/tickets/handlers.py](/example.test/NTFS_Share/pc_client/server/tickets/handlers.py#L3430).

Но в текущем UI почти не выведено:

- в [server/ticket.js](/example.test/NTFS_Share/pc_client/server/ticket.js) есть статус, очередь, requester profile и worklog;
- нет полноценного интерфейса для watchers, links, KB links, problems, change links, notification prefs и дашбордов;
- в [server/admin.js](/example.test/NTFS_Share/pc_client/server/admin.js) операторская очередь ограничена управлением статусом, назначением, очередью и профилем инициатора.

Итог: функциональность есть, но оператору она недоступна без прямой работы с API.

### P0. Массовый mojibake в операторском коде и админке

В проекте остаётся много битых строк и комментариев:

- [server/admin.js](/example.test/NTFS_Share/pc_client/server/admin.js)
- [server/tickets/handlers.py](/example.test/NTFS_Share/pc_client/server/tickets/handlers.py)
- [server/websocket/agent_handler.py](/example.test/NTFS_Share/pc_client/server/websocket/agent_handler.py)

Для русскоязычной админки это не косметика, а UX-дефект: часть подписей, сообщений и логов уже выглядит повреждённой. По `AGENTS.md` это прямо запрещено, поэтому задачу стоит считать техническим долгом высокого приоритета.

### P1. В коде остаётся legacy state-only путь создания тикета

`TicketService` до сих пор живёт как старый in-memory сценарий:

- создаёт тикет со `status="open"` в [server/tickets/service.py](/example.test/NTFS_Share/pc_client/server/tickets/service.py#L91);
- пишет только в `state`, а не в PostgreSQL в [server/tickets/service.py](/example.test/NTFS_Share/pc_client/server/tickets/service.py#L116);
- формирует legacy message payload через `from_role` в [server/tickets/service.py](/example.test/NTFS_Share/pc_client/server/tickets/service.py#L128).

Сейчас прямых вызовов этого сервиса в рабочем коде почти не видно, что хорошо. Но сам класс остаётся миной замедленного действия: любая новая интеграция может случайно пойти через него и создать тикет мимо БД и мимо канонических статусов.

### P1. Две параллельные модели чата

Система одновременно поддерживает:

- job-based chat через `/api/chat_start`, `/api/chat_raise`, `/api/chat_send`;
- ticket-based chat через `/api/tickets/{ticket_id}/message`.

Маршруты видны в [server/routes.py](/example.test/NTFS_Share/pc_client/server/routes.py#L314) и [server/routes.py](/example.test/NTFS_Share/pc_client/server/routes.py#L404).

Архитектурно это создаёт путаницу:

- часть коммуникации живёт вокруг `job_id`;
- часть вокруг `ticket_id`;
- UI и тестовая документация уже отдельно объясняют, что это две разные системы.

Для полноценной заявочной системы стоит определить единый канонический путь: желательно, чтобы пользовательская переписка шла прежде всего через тикет, а job-chat остался только техническим транспортом, если он вообще нужен.

### P1. Сессии всё ещё гибридные: БД плюс runtime state

Тикеты и события лежат в PostgreSQL, но runtime session по-прежнему восстанавливается из памяти и событий, что видно в [server/tickets/handlers.py](/example.test/NTFS_Share/pc_client/server/tickets/handlers.py#L234).

Сейчас это уже переживает рестарт лучше, чем раньше, но полноценная CRM/ITSM обычно хранит открытые коммуникационные сессии как first-class сущность в БД.

### P1. Нет полноценного intake-потока для внешнего клиента

Публичная очередь умеет показывать:

- очереди;
- открытые тикеты;
- публичные KPI.

Но не умеет создавать заявку без входа. Это видно по read-only API в [server/tickets/public_queue_handlers.py](/example.test/NTFS_Share/pc_client/server/tickets/public_queue_handlers.py#L65).

Если нужен клиентский портал, не хватает:

- публичной формы создания заявки;
- подтверждения по email/телефону;
- гостевого статуса обращения;
- безопасной self-service страницы клиента.

### P2. Внешние каналы уведомлений отсутствуют

In-app notifications есть, но email/SMS/мессенджеры не встроены. Для service desk это ещё терпимо, для CRM почти всегда недостаточно.

### P2. Тестовое покрытие на бизнес-функции слабое

В тестах много покрытия по Protocol V3, операциям и transport layer, но мало регрессий на саму предметную область:

- есть точечный тест на вложения в [server/test_ticket_message_attachments.py](/example.test/NTFS_Share/pc_client/server/test_ticket_message_attachments.py);
- есть немного unit-тестов на problems/notifications в [server/tests/test_stage8.py](/example.test/NTFS_Share/pc_client/server/tests/test_stage8.py);
- почти нет отдельных тестов на watchers, KB links, requester profile, queue UX, metrics API, public queue и CRM-потоки.

Это повышает риск тихих регрессий при любом рефакторинге тикетной части.

## 4. Что стоит делать дальше

### Если нужна сильная система заявок / service desk

Приоритетный план:

1. Убрать mojibake из серверной части и web UI.
2. Закрыть разрыв между API и UI: вывести watchers, links, KB, problems, change links, notifications, metrics.
3. Закрепить регрессиями базовые ticket-инварианты и Stage 5-8 функции.
4. Убрать или жёстко задепрекейтить `TicketService` state-only путь.
5. Сделать единый ticket-centric UX вместо раздвоения на chat/job и ticket chat.
6. Добавить публичный intake-поток для внешнего клиента.

### Если нужна именно CRM

После стабилизации service desk нужен отдельный этап проектирования:

1. `crm_accounts` / `crm_contacts` / `crm_companies`.
2. связи `ticket -> contact/company`.
3. timeline клиента, а не только timeline тикета.
4. pipeline/deals/opportunities.
5. customer portal и внешние каналы уведомлений.
6. сегментация и поиск по клиентской базе.

Без этого текущий продукт лучше называть "тикетная система / service desk", а не CRM.

## 5. Самые полезные quick wins

- добавить UI-блоки для watchers, KB links, related tickets, problems и change links;
- сделать операторский dashboard на базе уже готовых `/api/tickets/metrics/*`;
- почистить кодировку `admin.js` и `tickets/handlers.py`;
- добавить regression tests на создание тикета и основные relations API;
- явно пометить `TicketService` как legacy-only и запретить новый код через него.
