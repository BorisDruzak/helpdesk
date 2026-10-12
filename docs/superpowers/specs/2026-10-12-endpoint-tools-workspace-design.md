# Панель инструментов Endpoint в Helpdesk

Дата: 12.10.2026. Статус: пользователь подтвердил спецификацию и продолжение
к implementation plan; реализация не начата.

## 1. Назначение и согласованный результат

Оператор поддержки выбирает реальную проверку Endpoint для компьютера из обращения,
задаёт её разрешённые параметры, видит результат конкретного запуска и при необходимости
добавляет этот результат в паспорт решения. Под инструментами понимаются опубликованные
модули Endpoint с типизированными проверками, а также поддерживаемые профили контекста.

Пользователь подтвердил направление: инструмент и параметры слева, результат справа,
добавление в паспорт, общий сбор контекста, независимое сворачивание общей навигации
и списка тикетов. Правая панель контекста имеет порядок «заявитель → компьютер → агент»;
Observer находится ниже в сворачиваемом блоке.

Критерий успеха: по экрану ясно, какая проверка доступна для данного устройства,
где она выполняется, что запрошено, какой запуск завершился и насколько свежи его данные.
Успешное принятие запроса, исторический snapshot и выполненная на сервере Helpdesk
проверка не подменяют свежий результат агента.

## 2. Проверенный исходный контракт

Исследован Endpoint main `9144a26472239e5a4c61a79aacdabbda4ec961bc`: Agent 3.2.82,
21 примитив в `endpoint_contracts/capabilities.py`, шесть сборщиков в
`pc_agent/context_profiles/registry.py`. Все примитивы зарегистрированы в диспетчере
`pc_agent/runtime/command_executor.py`. 41 целевая проверка каталогов, контрактов,
параметров, availability и recipes прошла на отдельном снимке исходников.
Это доказательство кода и контрактов, а не исполнения на установленном Agent 3.2.82.

Helpdesk сохраняет lock provider `38ddabe3c0badf09a033bb7523a89a7d2c5059a0`.
До реализации нового consumer-контракта необходимо зафиксировать provider SHA,
опубликованный OpenAPI и сгенерированные контрактные артефакты, содержащие нужные routes.
Последний main, lock Helpdesk и реально установленный Agent учитываются раздельно.

При чтении staging 12.10.2026 текущий служебный доступ Helpdesk получил 403 для
`GET /api/v1/module-capabilities` и `GET /api/v1/modules`. Выбранное устройство было
офлайн; его capabilities содержали только `context.diagnostic.collect`.
`available=true` у этого базового capability допускает постановку сбора в очередь;
это не подтверждает активную связь агента. В текущей панели также смешаны server DNS,
старые Endpoint evidence и незавершённые операции. Эти наблюдения не являются гарантией
последующего состояния стенда.

## 3. Что можно получать от сервера Endpoint уже сейчас

| API | Содержание и существенное ограничение |
| --- | --- |
| `GET /api/v1/module-capabilities` | Закрытый каталог примитивов: ID, русское название, категория, платформы, минимальная версия Agent, policy/flag, параметры, версии схем результата, пределы исполнения. Не каталог опубликованных модулей и не подтверждение доступности конкретного ПК. |
| `GET /api/v1/modules` | Определения модулей: `module_key`, `display_name`. Не содержит полного индекса опубликованных версий. |
| `GET /api/v1/modules/{module_key}` | Последняя созданная версия и recipe. Она может быть draft; запускать её как опубликованную нельзя. |
| `GET /api/v1/modules/{module_key}/versions/{version}` | Точная версия, state и recipe. Источник параметров конкретного опубликованного модуля. |
| `GET /api/v1/devices/{device_id}/capabilities` | Возможности, подтверждённые сервером для устройства. Для primitives учитываются связь, объявление Agent, platform/version и серверная policy. Отсутствие элемента не сообщает само по себе точную причину блокировки. |
| `GET /api/v1/devices/{device_id}/context` | Presence, состояния профилей и сохранённые snapshots; дату наблюдения нельзя смешивать с состоянием последнего запроса. |
| `POST /api/v1/devices/{device_id}/module-operations` | Запуск опубликованного `module_key` и точной `version` с `inputs`; существующий исполнитель Module → Operation → Gateway WSS → Agent. |
| `GET /api/v1/module-operations/{operation_id}` | Caller-owned операция, шаги и безопасные типизированные результаты. |

В Endpoint Console уже есть admin-only `GET /api/admin/console/devices/{device_id}/modules`:
он выбирает published versions и вычисляет совместимость с устройством. Helpdesk не
использует административную cookie-сессию Console в качестве межсервисного доступа.
Новый service-read projection должен переиспользовать эту доменную проверку, а не
создавать независимые правила совместимости.

## 4. Источники каталога и необходимое дополнение Endpoint API

Для полного динамического списка используется каталог из Endpoint, а не статический
массив названий в React и не наличие пакетов на локальном диске Helpdesk.

Текущего `GET /modules` недостаточно: он не сообщает published versions, а получение
latest по ключу может выбрать черновик. Перебор всех versions через guessed URLs,
выбор «самой новой» версии без проверки state и вывод availability из старого evidence
не допускаются.

Предлагается **новый** read-only service route:

`GET /api/v1/devices/{device_id}/modules?limit=...&cursor=...`

Это дополнение опубликованного OpenAPI Endpoint, а не уже существующий service API.
Scopes: `devices.read` и `modules.read`. Ответ — frozen DTO с discriminator
`endpoint_device_modules_v1`, точным `device_id`, `observed_at`, `items` и `next_cursor`.
Каждая запись содержит:

- `module_key`, `display_name`, точную `version` и `state=published`;
- проверенный recipe со входами и шагами; фиксированные literal bindings сохраняются;
- `availability=available/unavailable/unknown` для данного устройства и bounded
  `reason_code`, обязательный при unavailable/unknown и отсутствующий при available;
- причины, подтверждённые provider: offline, несовместимая платформа/версия,
  необъявленная capability, выключенная возможность, ненастроенная network policy;
- при недоступной части provider-данных — unknown, без ложного offline.

`limit` — 1..100, default 50; cursor — opaque keyset. Порядок стабилен по module key,
времени создания версии и UUID; версии не сортируются лексикографически как SemVer.
Возвращаются опубликованные версии, без draft/validated/disabled recipes. Некорректный
recipe не пропускается молча: provider возвращает безопасный код invalid projection.

Таким образом, потребитель читает один paginated индекс published modules с availability
и один общий каталог primitives для русских названий, параметров и схем. Не нужен
неограниченный fan-out по каждому модулю. Старые service routes и ответы не изменяются.
Новый DTO, JSON Schema, OpenAPI и provider contract tests добавляются вместе.

Helpdesk фиксирует каждую выбранную module version. Background refresh не меняет
версию выбранного инструмента и не изменяет уже созданный запуск. На первом выборе
default — максимальная совместимая опубликованная SemVer среди полученных версий;
если индекс ещё неполон, запускающая кнопка для неопределённого default не активна.
Выбор конкретной известной версии возможен независимо от наличия следующих страниц.

## 5. Состав инструментов и параметры

Первый consumer поддерживает закрытые 21 capability и их v1 result codecs.
Новые неизвестные schema/capability не становятся исполняемыми автоматически.
Каталог metadata может показать такую запись как неподдерживаемую данной версией Helpdesk.

| Capability | Параметры |
| --- | --- |
| `dns.resolve` | `target`, `family=any/ipv4/ipv6` |
| `network.ping` | `target`, `count=1..5`, `timeout_ms=100..5000` |
| `tcp.connect` | `target`, `port=1..65535`, `timeout_ms=100..10000` |
| `route.get` | `target`, `port=1..65535`, `family`, `timeout_ms=100..5000` |
| `adapter.list` | Нет |
| `system.service_status` | Фиксированный `service_key`: Agent или updater |
| `system.resource_snapshot` | Нет |
| `process.list` | Нет |
| `process.find` | `name` |
| `service.list` | Нет; закрытый логический каталог, не вся база SCM/systemd |
| `service.status` | Фиксированный `service_key`: Agent, updater или служба печати |
| `printer.list` | Нет |
| `printer.status` | `printer_name` |
| `printer.queue.summary` | Нет; только Windows |
| `software.list` | Нет |
| `software.find` | `name` |
| `filesystem.free_space` | Нет |
| `filesystem.path_exists` | Фиксированный `path_key` install/data/runtime manifest |
| `filesystem.file_metadata` | Фиксированный `path_key` runtime manifest |
| `eventlog.query` | Фиксированные `profile`, `severity`; `lookback_minutes=1..60`, `max_events=1..32`; только Windows |
| `eventlog.recent_errors` | Фиксированный `profile`, `lookback_minutes=1..60`; только Windows |

Одна отдельно запускаемая проверка оформляется опубликованным модулем с одним шагом.
Поддерживаемые multi-step read-only recipes отображаются как группы проверок с
результатами по шагам; не маскируются под одиночный ping. Политика первой версии
разрешает только registry-approved safe_read/controlled_read capability.

Форма строится по **inputs выбранного recipe**, сопоставленным с registry parameter
bindings. Если один input используется несколькими шагами, применяются пересечение
типов/enum/числовых границ и точные проверки каждого связанного DTO; пустое пересечение
блокирует рецепт как invalid projection. Все проверки повторяются на backend/provider.
Helpdesk не импортирует provider Python source в runtime.

`allowed_sources=[literal]` нельзя превращать в свободный input. Такие значения
показываются как фиксированные настройки; для иного service/path/event preset
выбирается другой опубликованный вариант. Не запрашиваются shell, произвольная команда,
произвольный путь, секреты или environment. Network target — hostname/IP, не URL;
политику CIDR/suffix и итоговую разрешённую цель проверяет Endpoint.

## 6. Интерфейс инструментов

Вкладка «Диагностика» содержит только Endpoint profiles и подтверждённые Endpoint
modules. Server DNS/HTTP, monitoring, Observer и ручные факты остаются в явно
обозначенных других разделах; результаты сервера не получают источник «компьютер».

На широком экране содержимое панели:

```text
Инструменты Endpoint · компьютер · состояние связи
┌─────────────────────────┬──────────────────────────────────┐
│ Категория и инструмент  │ Результат выбранного запуска     │
│ Версия и доступность    │ Состояние / время / источник     │
│ Параметры recipe        │ Поля или таблица по result DTO   │
│ Запустить               │ Приложить к паспорту             │
└─────────────────────────┴──────────────────────────────────┘
Общий сбор контекста · состояние каждого профиля
История запусков
```

Две колонки включаются при внутренней ширине панели >=640 px; ниже элементы идут
вертикально: выбор → параметры → запуск → результат → паспорт → общий сбор.
Размеры определяются шириной контейнера, а не только window. Сохраняется существующий
resizer панели; внешние области не должны создавать горизонтальный scroll страницы.

Кнопка примитива «Запустить» активна после полной проверки actor/ticket/device,
published version, поддержки schema, параметров и свежей availability. Offline/unknown
не выводятся как available. Для context/diagnostic сборов при допустимой provider queue
offline-действие называется «Поставить сбор в очередь», с явным отсутствием свежего результата.

Результат привязан к immutable run ID. При смене инструмента или устройства показывается
его собственный выбранный run либо пустое состояние. Запуск B не перетирает отображение
A, если ответ A приходит позже. Пока новый запуск queued/running, предыдущий результат
можно открыть только как исторический с датой; его не показывают результатом нового запуска.

В результатах: русские labels, elapsed/status, причина ошибки, device/source,
input summary, module version, время сбора и таблицы безопасных полей. Unknown/null,
успешный пустой ответ, expired evidence и transport failure имеют разные состояния.
Raw payload, debug endpoints и implementation identifiers не занимают основной экран.

## 7. Общий сбор контекста

Кнопка общего сбора создаёт Helpdesk diagnostic session с шестью отдельными шагами:

| Profile | Provider path | Состав |
| --- | --- | --- |
| `baseline_v1` | Context collection | Система, оборудование, диски, интерфейсы, ПО |
| `health_v1` | Context collection | Uptime/load, свободное место, состояния служб |
| `network_v1` | Context collection | Default route и адреса интерфейсов |
| `inventory_v1` | Context collection | ОС, аппаратная инвентаризация, RAM, storage, адаптеры |
| `session_v1` | Context collection | Login и наличие интерактивной сессии |
| `diagnostic_v1` | Existing diagnostic operation | Ограниченные процессы и безопасный log excerpt; фиксированная причина «Диагностика по обращению» |

Первые пять используют существующие `request_context_collection`/`read_context_collection`;
diagnostic/activity не добавляются в безопасный context port. Diagnostic идёт по
своему accepted operation contract. Activity/DLP не входит в общий активный сбор.

Общий сбор не запускает все 21 primitive и не угадывает target для DNS/ping/TCP.
Состояния каждого шага: pending, queued, running, succeeded, failed, expired,
unavailable; aggregate — pending/running/succeeded/partial/failed. Succeeded только при
успехе всех шести свежих шагов. Доступные завершённые части можно просматривать и
прикладывать отдельно; API 200/201 или requested не равны успешному сбору.

Каждый шаг имеет отдельный стабильный idempotency key. Повтор того же request/run
не создаёт второй remote сбор; явный новый сбор создаёт новый run. Retry по unavailable
использует bounded существующую политику, без циклического пересоздания операций.

## 8. Каталог, запуск и persistence в Helpdesk

Endpoint остаётся исполнителем и владельцем технической identity/presence. Helpdesk
владеет actor/ticket authorization, orchestration, evidence и паспортом. Используются
domain ports и HTTPS adapter; provider DB, локальный Agent transport и local dispatch
не применяются. Binding определяется verified ticket → Endpoint reference service.

Новые BFF routes, предлагаемые для реализации:

- `GET /api/web/support/tickets/{ticket_id}/endpoint-tools`: paginated metadata,
  опубликованные модули с availability, profiles и безопасные причины недоступности;
- `POST .../endpoint-tools/runs`: выбранные `module_key`, `version`, `inputs` и caller
  idempotency key; backend проверяет module в Endpoint и exact device из тикета;
- `GET .../endpoint-tools/runs/{run_id}`: local lifecycle, remote steps, safe results;
- `POST .../endpoint-tools/collections`: общий сбор; `GET .../collections/{run_id}`
  возвращает реальные состояния шести шагов.

Read roles: admin/support/auditor при текущем доступе к тикету; mutation roles:
admin/support плюс существующее permission на запуск. Каждый read/mutation проверяет
принадлежность run/evidence тикету, роли и устройство. Cookies, CSRF, no-store,
opaque refs и безопасные typed errors сохраняются. Нет browser-side service credentials.

Дополнение ports включает: чтение module registry, device published-module page,
точной module version, создание и чтение caller-owned module operation. Bound DTO
для result — closed union 21 schema с registry-defined пределами. Отдельно остаются
существующие diagnostic result и пять context section DTO; универсального unsafe dict
для результатов не вводится. Максимальный provider response — 1 MiB; превышение даёт
typed invalid projection, не обрезанный успешный результат.

Catalog metadata cache — до 60 секунд, keyed по provider identity/schema. Device
availability cache — до 5 секунд и по exact device. HTTP 401/403 не превращается в
пустой список; stale catalog может быть виден как read-only. Перед созданием нового run
backend повторно читает device availability и точную published version. Provider
выполняет финальную проверку при своей операции; конфликт после проверки обрабатывается.

Reuse существующих diagnostic_sessions, diagnostic_steps, operations и evidence.
Для module/context runs требуется additive persistence extension: immutable
`execution_kind` (diagnostic/module/context_collection), exact device ref, caller key,
typed request snapshot, module/version либо profile, local run/step ID, remote ref,
timestamps и безопасный last_error_code. Existing diagnostic links/requests не
переинтерпретируются как module runs; новая схема ссылок/миграция проверяется отдельно.
Actor ID + ticket ID + canonical immutable request участвуют в idempotency scope;
тот же ключ с иными параметрами даёт 409. Browser caller key, ticket ID и actor ID
остаются в Helpdesk. Remote idempotency keys выводятся из local opaque operation ID,
с раздельными namespace для diagnostic/module/context; существующий diagnostic key
`helpdesk-endpoint-operation:<local-operation-id>` не меняется. Correlation header
служит только трассировке, проверяется по accepted response contract и не даёт доступа
к run. В Agent command не добавляются Helpdesk entity identifiers.

Remote dispatch и polling выполняет reconciler. UI poll активных runs — каждые 2 секунды,
останавливается на terminal, unmount и потере session. Сроки и retry берутся из accepted
provider lifecycle; UI timeout не отменяет автоматически удалённый запуск. Для новых
module runs не показывается «Отмена», пока provider не публикует соответствующий контракт.
Логи и audit содержат bounded IDs/outcomes без credentials/raw telemetry.

## 9. Добавление результата в паспорт

Кнопка прикладывает выбранный завершённый безопасный результат через существующие
diagnostic evidence и passport boundary. Сохраняются source=endpoint, exact device,
run/step refs, module/version или profile, bounded input summary, schema version,
collected_at, semantic digest и structured result. Очередь, transport failure и null
result не превращаются в успешный evidence. Completed failure с безопасным результатом
может быть приложен как отрицательное доказательство с сохранённым failure status.

Backend повторно проверяет принадлежность evidence тикету и права. Повторное прикрепление
того же evidence не создаёт дубликат. Кнопка после успеха показывает «В паспорте».
В passport копируется разрешённый safe snapshot, а не только ссылка на Endpoint evidence
с TTL; уже принятый паспорт не ломается после expiry remote result. Если результат
истёк до получения snapshot, требуется новый сбор. Retention существующего паспорта
и Helpdesk audit сохраняется; постоянный Endpoint PIN этой кнопкой не создаётся.

## 10. Контекст и сворачиваемые панели

Порядок контекста:

1. Заявитель: Registry person, отдел, контактные поля и location.
2. Компьютер: exact Endpoint reference, подтверждённый Registry asset, ОС/инвентаризация
   и времена наблюдения; неподтверждённая Registry связь обозначается явно.
3. Агент: подтверждённая presence, последняя связь, version/platform только если эти
   поля реально предоставлены provider; отсутствие версии показывается как «Нет данных».
4. Согласия/согласования и прочие бизнес-данные; Observer по умолчанию свёрнут,
   критичная сводка остаётся заметной и доступной одним действием.

Полная навигация сворачивается до icon rail с доступными именами/tooltip; её toggle
всегда доступен. Список тикетов имеет собственный toggle при открытой карточке;
сворачивание не меняет route/selection, search/filter или текущую вкладку.
Состояния независимы, сохраняются локально для текущего аккаунта и workspace.
Сворачивание не выполняется автоматически при каждом открытии нового тикета; используется
предпочтение оператора. Без выбранного тикета список видим, иначе теряется основной flow.
На узком экране сохраняется существующая overlay-навигация; скрытая колонка не оставляет
пустую ширину и скрытые focus targets. Toggle использует aria-expanded и возвращает focus.

## 11. Права, rollout и контрактные условия

Для discovery нужны `modules.read` и `devices.read`; для запуска/чтения module operations
— `module_operations.create` и `module_operations.read`. Existing context/diagnostic scopes
сохраняются. Helpdesk не получает modules.write/validate/publish. Нужные одношаговые
модули и fixed presets публикуются владельцем Endpoint через штатный lifecycle.
Существующий provisioning CLI для Module workbench выдаёт authoring scopes; для
диагностической панели нужен отдельный узкий audited режим/CLI без этих прав,
с сохранением identity текущего integration client при credential rotation.

Подготовка требует нового provider read projection, его contract acceptance, текущего
provider lock и scoped credential configuration. Это отдельная часть реализации
Endpoint server; Agent binary, wire protocol и registry executable scope не расширяются.
Scopes и публикация модулей здесь описаны, но ещё не изменены.

Feature flag Helpdesk для нового workspace по умолчанию off. Порядок rollout:
provider additive metadata contract → contract lock/acceptance → Helpdesk additive
persistence и consumer → approved service access/modules → staging acceptance →
reviewed production gate. На staging нужен реально подключённый совместимый Agent;
offline-очередь, fixtures и code tests не заменяют live execution.
Rollback отключает новый workspace, сохраняет evidence/history и возвращает прежнюю
диагностическую панель. Additive schema не удаляется при rollback; существующие runs
должны завершаться reconciler-ом даже после выключения нового UI.

## 12. Приёмка

- Catalog приходит от Endpoint: опубликованный совместимый одношаговый модуль появляется
  после refresh без добавления React-констант. Draft/disabled version не запускается;
  unknown schema имеет явную неподдерживаемую availability.
- Primitive metadata, module recipe, platform/version и presence не смешиваются.
  Отдельный тест: latest module draft не скрывает существующую published version в новом индексе.
- DNS/ping/TCP/route forms применяют правильные bounds; literal-only параметры не
  становятся editable. Неверные/лишние входы отклоняются backend и provider.
- На реальном staging Agent один разрешённый DNS либо ping выполняется через Module
  Operation; результат содержит тот же device/run/module/version и реальные timestamps.
  Никакие install/update Agent в эту UI-приёмку не входят.
- Fresh result, success-empty, failed safe result, expired, unknown, queued и offline
  визуально различимы. Старый успешный результат не выдаётся за новый queued run.
- Run/evidence другого тикета, actor и service client недоступны; двойной клик/retry
  не создаёт второй remote operation. Polling и late responses не перемешивают запусков.
- Общий сбор показывает шесть отдельных lifecycle и partial при отказе одного шага;
  набор пяти context + diagnostic проходит без ослабления safe-context port.
- Добавление в passport идемпотентно, сохраняет bounded snapshot/provenance и переживает
  expiry remote evidence; запрещённые/сырые поля не попадают в BFF, logs или passport.
- Context имеет согласованный порядок; две левые панели сворачиваются независимо,
  выбор и фильтры сохраняются. Проверки клавиатурой и viewport 390, 1366, 1920, 2582 px;
  при container width <640 px инструмент и результат идут вертикально без overflow.
- Недоступность Endpoint или 403 catalog не блокирует переписку и обработку обращения.
  Зафиксированы browser console/network, реальные результаты, audit и контрактные тесты;
  deployment readiness оценивается штатным release gate отдельно.

## 13. Затрагиваемые области и граница этой спецификации

Endpoint: canonical OpenAPI/DTO, module service-read projection и reusable compatibility
query, contract/server tests, documentation. Helpdesk: endpoint ports/adapters, facade/
reconciler/persistence, diagnostics/passport projections, ticket context mapper,
diagnostic-center-panel, отдельные tool form/result/context collection components,
app-shell navigation и ticket column layout, backend/frontend/browser tests и CODEMAP.

Эта спецификация не меняет произвольные сервисы/файлы на ПК, не добавляет remote shell,
не устанавливает или обновляет Agent, не раскрывает service credentials в браузере
и не объявляет production готовым. Следующий этап после пользовательского review —
письменный implementation plan с отдельными provider/consumer/acceptance шагами.
