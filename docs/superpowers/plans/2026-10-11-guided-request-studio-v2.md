# Guided Request Studio v2 — спецификация и план реализации

**Дата:** 2026-10-11. **Проект:** BorisDruzak/helpdesk. **Ветка:** main. **URL:** /app/admin/request-template-studio.
**Статус:** утверждаемая функциональная архитектура и исполнимый план для Codex; написание документа не означает внедрение.
**Исполнитель:** Codex, поэтапно с RED → GREEN и независимыми проверками.
**Нормативные правила:** AGENTS.md, webapp/AGENTS.md, server/AGENTS.md, документация и действующие контракты проекта.

## 0. Главная идея и непреложные решения

Студия — единый no-code конструктор **сценария обращения**, от навигации по проблемам до помощи пользователю, сбора структурированных фактов и создания тикета, если решить проблему самостоятельно не удалось. После создания тикета управление остаётся в существующем ticket/policy runtime.

**Обязательные продуктовые решения:**
1. При входе администратор видит прежде всего **каталог всех обращений**, поиск, дерево категорий/подкатегорий, статусы, действия «Создать категорию» и «Создать сценарий обращения». Не выводить на стартовом экране одновременно множество редакторов политик.
2. Создание и редактирование сценария — **последовательный административный мастер**: 1) категория и назначение; 2) сценарий пользователя; 3) обработка тикета; 4) тестирование; 5) публикация.
3. Страницы пользовательской формы **не равны шагам административного мастера**. Администратор задаёт любое разумное количество страниц формы, каждая содержит один вопрос либо группу вопросов.
4. Форма собирает максимум известных сотруднику сведений: текст, выборы, устройство, контекст, при поддержке серверного контракта — вложения. Вопросы могут влиять на приоритет, SLA через правила, маршрут, согласование, диагностику, evidence закрытия и отчётность.
5. **Расширенные настройки строго локальные**: у КАЖДОГО поля, блока, инструкции, категории есть встроенный раскрывающийся элемент «Расширенные настройки», сразу под основными полями в ТОМ ЖЕ редакторе. Не делать отдельную вкладку, страницу, глобальный режим Basic/Advanced/Expert или переход в технический конструктор ради редактирования свойств выбранного элемента.
6. Сценарий содержит не только вопросы, но и условия, безопасные инструкции, уточняющие проверки «Помогло?», блок диагностики, просмотр перед отправкой, создание тикета и завершение **без тикета**. Блоков может быть сколько нужно; их порядок/ветвления определяет администратор.
7. Реализовать уже сейчас полноценную инструкцию/проверку результата/ветвление/статический diagnostic block. Endpoint-agent ещё не готов: **запретить реальный pre-ticket diagnostic dispatch** без отдельного подтверждённого auth/consent/operation контракта. Недоступный диагностический блок обязан иметь fallback.
8. Пользователь не назначает себе SLA или queue прямой подменой формы. Сервер преобразует проверенные ответы в факты, вычисляет приоритет действующими policies, применяет SLA/OLA, маршрутизацию, согласования, closure и notification.
9. Публикация проходит серверную валидацию, dry-run, diff, подтверждение краткоживущим привязанным к draft токеном, фиксирует immutable версию. Сессии прохождения прикреплены к конкретной версии. Все старые формы/API/тикеты продолжают работать.
10. Первый обязательный пилот: «Рабочее место → Принтеры и МФУ → Проблемы с печатью → Не печатает» с ветками self-service/создание тикета.

## 1. Реальная архитектура, которую нельзя ломать

Исходный Helpdesk уже содержит цепочку **Service Catalog service → offering → RequestTemplate/FormSchema → effective policy bundle → ticket**. Canonical identifiers: service_code, offering_code/full_code, request_template_key, form_key, version. Это источник истины. **Не создавать второй конкурирующий каталог услуг, вторую ticket model или SLA engine.** Новый hierarchical category tree — отдельный навигационный слой над существующими сущностями.

Повторно использовать и при необходимости переработать:
- webapp/src/pages/admin/request-template-studio-page.tsx — оркестрация текущей Студии (сейчас перегружена);
- webapp/src/features/request-template-studio/create-request-wizard.tsx, draft-model.ts, studio-model.ts, form-field-editor.tsx, process-editors.tsx, process-map.tsx, readiness.ts, readiness-panel.tsx, request-studio-shell.tsx;
- webapp/src/features/requester/dynamic-form/index.tsx и requester/types.ts — динамические типы, видимость, проверка полей;
- webapp/src/pages/requester/new-request-page.tsx, new-request-panels.tsx — основной авторизованный интерфейс сотрудника;
- webapp/src/pages/help/index.tsx — существующий совместимый публичный путь;
- server/tickets/service_catalog_runtime.py, request_template_submission.py, form_catalog.py;
- server/tickets/form_process_preview.py, service_catalog_preview.py, policy_health_service.py;
- server/tickets/request_studio_publication.py и server/web_api/dto/request_studio.py, request_studio_handlers.py — safe preview + confirmation token;
- server/docs/SERVICE_CATALOG.md, REQUEST_FORM_BUILDER.md, DIAGNOSTIC_PLAYBOOKS.md.

В текущем коде StudioDraft хранит поля, conditional visibility и коды политик, но **не** типизированный исполняемый граф из страниц, инструкций, проверок и переходов. Следовательно, одного CSS/UI-редизайна недостаточно: нужна новая версионированная модель сценария и серверный runtime **до создания тикета**. Существующие политики после submit остаются каноническими.

**Границы:** Helpdesk не должен становиться агентским control plane; текущий Endpoint diagnostic facade работает с ticket/support context, и его нельзя молча переиспользовать для pre-ticket запуска. Пользовательский fallback other.unknown и старые form-only клиенты сохраняются.

## 2. Роли и задачи

| Роль | Главное действие | Доступ |
|---|---|---|
| Admin | Найти/создать/отредактировать сценарий, проверить, опубликовать | Управляемый CRUD, policy picker, история и аудит |
| Auditor | Проверить конфигурацию/историю | Только чтение, без draft mutation и publish |
| Requester | Выбрать проблему, пройти вопросы/инструкции, решить или отправить тикет | Только разрешённый published scenario и свои sessions |
| Support | Получить тикет и понять собранные факты и уже пройденные шаги | Существующая авторизация тикетов, не исходный полный admin draft |

Основное действие видно без прокрутки. Пользователь не видит internal queue IDs, политику как JSON, debugging labels и access tokens. Технические значения допустимы в локальных расширенных настройках администратора. Опасные операции архивирования/публикации требуют подтверждения.

## 3. Сущности и их отношения

**Service** — уже существующий предметный раздел каталога (например, workplace).

**Category** — новый узел навигационного дерева: UUID, service_code, parent_id (может быть null), slug, name, description, sort_order, visibility, lifecycle_status draft/published/archived, created/updated timestamps и actor audit. Иерархия не ограничивается двумя уровнями; необходимы обнаружение циклов, проверка принадлежности service и эксплуатационный ограничитель максимальной глубины. Category не изменяет service/offerings или право доступа к ним.

**Offering** — существующий конечный тип обращения, напр. workplace.printer_issue. Лист дерева — это published offering со сценарием или обычной legacy form. Категория может содержать подкатегории и offerings. Нельзя при импорте менять стабильный offering code.

**Scenario** — привязанный к конкретному offering управляемый граф: scenario_key, title/description, category_id, entry_block_id, blocks, transitions, process binding, schema_version. В один момент у одного offering максимум одна действующая published сценарная версия. Черновиковая новая редакция не нарушает предыдущую публикацию.

**Block** — типизированный элемент графа с уникальным стабильным block_id, конкретными настройками и направленными переходами на другие block_id, не индексы.

**Field** — стабильный field key, type, label, required, options, validation, visibility condition, typed process roles. Переименование label не меняет key; изменение key требует проверки зависимостей/миграции.

**ScenarioVersion** — immutable опубликованное определение и снимок ссылок на формальную FormSchema/RequestTemplate/Offering/policies; publish создаёт новую версию.

**ScenarioSession** — owner-scoped временное pre-ticket прохождение определённой версии: current_block, ответы, history, результаты проверок, idempotent submit binding к ticket_id либо результат self-service.

## 4. Экран каталога

Маршрут /app/admin/request-template-studio открывается в виде List + Detail:
- шапка «Студия обращений»;
- primary «Создать сценарий», secondary «Создать категорию»;
- поиск по названию, категории и типу обращения, фильтры «Все / Опубликованные / Черновики / С ошибками / Архив»;
- слева иерархическое дерево категорий по service, сворачиваемое;
- по центру список: понятное название, расположение в дереве, краткое описание, status, версия, дата изменения, последние ошибки, контекстные действия;
- один клик — открыть существующий сценарий/редактор; из списка legacy offerings — открыть обычную форму или создать draft сценария из неё;
- кнопки: создать, редактировать, копировать, переместить, архивировать, история версии;
- при отсутствии данных — осмысленная empty state с одной кнопкой, при загрузке — skeleton, при ошибке — retry и объяснение.

Никакой гигантской карты 11 policy blocks/Policy Health/field list на входе. Разделы «Каталог услуг», «Конструктор форм», «Проверка политик» можно сохранить как совместимые служебные экраны, но обычный администратор не должен туда переходить для настройки своего вопроса.

**Редактор категории:** inline form/panel с parent picker, названием, описанием и сортировкой. Ниже В ЭТОЙ ЖЕ форме — «Расширенные настройки»: slug, allowed visibility, связанный service (searchable picker), auditing. Нельзя создать цикл, категорию под родителем другого service или удалить категорию с опубликованными дочерними offerings. Категории не расширяют visibility service/offering: только пересечение ограничений.

## 5. Административный мастер — точный порядок

### Шаг 1. Категория и назначение
- Выбрать service, путь категории (создать новую, не покидая мастер), existing/new offering.
- Ввести публичное название, описание и профиль: incident, access request, software install, consultation, general request; если потребуется новый профиль — расширить совместимую модель.
- Указать аудиторию/возможность submit on behalf только через существующий безопасный policy.
- Локальные «Расширенные настройки»: service/offering identifiers из picker, request_template_key, стабильный scenario_key, visibility, reporting grouping; не показывать raw IDs по умолчанию.
- «Сохранить черновик» возможно до заполнения остальных шагов. «Далее» только после минимальной проверки уникальности и связности.

### Шаг 2. Сценарий сотрудника
- Создать/отредактировать страницы формы, их группы и вопросы; инструкции, условия, self-resolution, диагностический placeholder, review, submit_ticket, finish.
- Переставлять блоки и группы, задавать обязательные переходы.
- Встроенный live preview именно текущего шага. Переключатель «Предпросмотр всей ветки» открывает simulator, но не другую техническую вкладку.
- Подробности §6–9.

### Шаг 3. Правила и обработка тикета
- В человеческих терминах выбрать existing policy: маршрут/очередь, приоритет по фактам, SLA/OLA, согласование, уведомления, closure.
- UI показывает связь «поле → проверенный факт → действующая политика → прогноз результата».
- Технические refs доступны непосредственно в локальных раскрытиях соответствующих полей/блоков; **никакого второго отдельного конструктора политик для этого процесса**.
- Ненастроенный обязательный маршрут, SLA, закрытие, разрешение видимости — блокер при publish.

### Шаг 4. Тестовый прогон
- Пройти выбранные ветви как requester, задав тестовые ответы и разрешённый mock-контекст.
- Показывать фактические server-evaluated: validated facts, selected branch, priority reasoning, route/queue, SLA/OLA, approval, notifications, closure.
- Отдельно показывать «Исправность политик» и «Готовность сценария». Policy Health=ok не означает, что готова вся форма/маршрут.
- Диагностику можно моделировать только с явной меткой «симуляция — реальная операция не выполнялась».

### Шаг 5. Публикация
- Diff изменений, обнаруженные конфликты и блокеры, полный итог «что увидит сотрудник», version и target offering.
- Save draft -> server preflight -> safe publish preview -> подтверждение *актуального* draft -> publish.
- После публикации показать ссылку на новый requester flow, историю версии и понятный результат.

**Навигация:** stepper с 5 этапами, кнопки «Назад», «Сохранить черновик», «Далее». Автосохранение допустимо только при честном индикаторе, debounce и обработке конфликтов. Переходы назад не теряют правки. Save ≠ publish. Любое изменение, затрагивающее опубликованный preview, инвалидирует token.

## 6. Экран редактора сценария

Page archetype — Workbench: **левый explorer → центральный редактор одного выбранного блока → опциональный правый preview**.

### На 1440–1920 px
- Левая колонка примерно 250–280 px: пронумерованный список блоков с иконками и статусами, drag handle, Add Block, context actions.
- Центральная колонка гибкая: редактируется ТОЛЬКО выбранный блок. Основные свойства наверху, локальная кнопка «Расширенные настройки» ниже.
- Правая preview ~300–340 px: рендер ровно того, что увидит сотрудник на текущем шаге; сворачивается. Preview не является третьим редактором.

### На 1366×768
Опциональный preview открыть по кнопке поверх/в drawer, НЕ создавать горизонтальную прокрутку или два независимых больших scroll. Sticky action bar остаётся в видимой области. На tablet/mobile explorer становится списком/выбором блока; центральный редактор занимает ширину. Тестировать 1366×768, 1440×900 и 1920×1080.

### Операции
- «Добавить блок» открывает небольшую палитру видов и вставляет после выбранного.
- После вставки фокус на названии нового блока.
- Drag/drop с keyboard fallback «Переместить выше/ниже».
- Duplicate, remove, undo/redo в пределах безопасной локальной истории.
- Удаление связанного блока показывает входящие transition references и просит переназначить их: не оставлять сломанные ссылки.
- Изменение порядка НЕ должно автоматически менять явно настроенные переходы.
- Нет общего global Basic/Advanced/Expert selector. Расширенные свойства непосредственно у элемента.

## 7. Страницы формы: один вопрос или целая группа

**form_page** — самостоятельный блок сценария, содержит 1+ групп и любое разумное количество полей. Администратор выбирает представление:
- «Один вопрос» — одна карточка и «Далее»;
- «Группа вопросов» — несколько связанных полей на странице;
- «Раздел формы» — длинная страница, если бизнес-сценарий требует;
- «Условная группа» — появляются дополнительные вопросы при выполнении условий.

Список полей внутри текущей страницы: добавить, копировать, удалить, переупорядочить. По клику на поле раскрывается только его редактор; соседние редакторы не раскрывать одновременно.

**Начальные типы:** text, textarea, select, multi_select, radio, checkbox, number, date, datetime, phone, email, url, user_picker, department_picker, location_picker, device_picker, service_picker. Нормализовать к типам существующего requester/dynamic-form; новые неподдерживаемые типы не публиковать без серверного валидатора.

**База редактора поля:** название вопроса, тип, варианты (если выбор), обязательность, подсказка/пример, порядок, параметры пользователя («Не знаю», если разрешено). Для выбора вариантов labels и machine values разделены, machine keys генерируются безопасно, но их можно раскрыть локально.

**Локальные «Расширенные настройки» внутри того же поля:**
1. Условное отображение: depends on field/answer, equals/in; группа AND/OR при поддержке нового DSL. Не допускаются циклические зависимости или ссылки на несуществующее поле.
2. Валидация: min/max длины/числа, format, allowlisted regex с ограничением, обязательность при условии.
3. Автозаполнение: verified Registry/requester/device context, не доверять user-supplied role/actor/queue.
4. **Влияние на обработку — мультивыбор совместимых ролей**: display_only, priority_impact, priority_urgency, priority_importance, routing_field, diagnostic_input, approval_subject, closure_evidence, reporting_dimension, passport_fact. Допустимы несколько ролей у одного вопроса.
5. Параметры роли: какой проверяемый факт записывать, как нормализовать варианты, какую опубликованную policy он снабжает данными; server validate.
6. Технические свойства: stable field key, typed value, aliases/migration note при rename, source context, masked/visible scope, dependency graph.
7. Read-only «Где используется»: блоки/ветви/политики, зависящие от поля.

Не делать raw JSON главным способом работы. Допустимый developer JSON — только просмотр/экспорт внутри локального раскрывающегося блока при наличии админского разрешения; редактирование raw draft может быть отключено.

**Вложения:** до ticket необходим owner-bound pre-ticket staging, TTL, content-type/size/quota checks и согласованная virus/security проверка. До реализации backend безопасного storage НЕ изображать рабочий upload в UI: type блокируется на publish с объяснением или реализуется полностью в отдельном срезе.

## 8. Типы блоков

| kind | Что видит автор | Локальные расширенные свойства | Выходы |
|---|---|---|---|
| form_page | Название, группы, вопросы, варианты | visibility, validation, process mapping, prefill | next / conditional |
| instruction | Заголовок, текст, изображения, ссылки, кнопка «Выполнено» | условия, аудитория, acknowledgment, storage refs | next |
| decision | Настройка «Если ответ X → блок A, иначе → B» | typed AND/OR, precedence, default branch | branches + else |
| resolution_check | Вопрос «Помогло?», ответы «Да / Нет / Не знаю» | требуемое подтверждение, комментарий, переходы | yes/no/unknown |
| diagnostic | Человеческое описание проверки | capability, consent, availability/timeout, fallback | success/error/denied/unavailable/timeout |
| review | Собранные ответы, результат предыдущих действий, «Изменить» | hidden/redacted fields, выбор отображаемых разделов | submit / back |
| submit_ticket | Сводка и кнопка «Создать обращение» | mapping/guard/idempotency/preview | ticket_created / retry |
| finish | Текст «Решено без обращения», завершающее действие | причина завершения, агрегаты, follow-up | terminal |

**Инструкция:** безопасный Markdown/структурированный rich text, перечни, предупреждения, поддерживаемые изображения/ссылки. Запрет произвольного HTML/JS. Факт «инструкция показана» не равно «проблема решена»: resolution_check требует явного ответа сотрудника. После failed instruction есть путь к заявке без навязанного бесконечного troubleshooting.

**Decision:** строгий типизированный набор операторов: and, or, not, eq, neq, in, exists, gt/gte/lt/lte только для совместимых типов; не выполнять пользовательские выражения eval/JS/Python. При пересечении правил требовать определённый приоритет и явную fallback ветку, иначе reject publish. Условия вычисляются сервером.

**Diagnostic:** модель/инспектор/validator/безопасная симуляция сейчас. Реальное pre-ticket выполнение пока запрещено: текущее Endpoint diagnostic capability имеет ticket-scoped support facade. Пока интеграция не согласована, server возвращает unavailable (с машинно-читаемой причиной) и выполняет обязательно настроенный fallback, например в review/submit. Никогда не выдавать симуляцию за настоящую диагностику. В будущем предусмотреть require consent + capability allowlist + target permission + timeouts + статус. Helpdesk не отправляет команды на устройство.

## 9. Переходы и движок графа

Опубликованный сценарий v1 — направленный ациклический граф (DAG) с одним entry. UI-кнопка «Назад» разрешена через историю посещения, но не вводит автоматических циклов. Можно вернуться к вопросу, изменить ответ, после чего downstream values/derived outputs и preview инвалидируются.

Инварианты validation:
- entry существует; каждый reachable nonterminal block имеет корректный выход;
- каждая decision ветвь имеет существующий target и fallback else;
- у всех ветвей допустимое terminal состояние finish или submit_ticket;
- несуществующие field references, self dependencies, циклы, недостижимые блоки и дубль field key выявляются до publish;
- one-time side-effect блок submit_ticket не повторяется из других исходов после ticket_created;
- required только для видимых полей текущей ветви; скрытые устаревшие ответы не попадают в ticket payload;
- порядок выполнения и порядок ветвей детерминирован, условия типобезопасны;
- обработка ограничена по глубине/числу блоков/размеру данных для защиты от DoS.

Preview и runtime используют **один канонический серверный evaluator**, а не две разные реализации логики.

## 10. Приоритет, SLA, маршрутизация и согласование

Цепочка:
**user answers → validated normalized typed facts → existing priority resolver → resulting priority → effective SLA/OLA resolver → deadlines**.
Параллельно validated facts участвуют в existing routing, approval, diagnostics eligibility, closure и reporting.

Пример:
- «Кого затронуло?» → impact_scope=me|team|all → priority impact.
- «Можно продолжать работу?» → work_continuity=yes|limited|no → urgency fact.
- «Важна ли услуга для приёма граждан?» → verified public_service fact с разрешённым role/source.
- «Какой принтер?» → affected_device (Registry verified) → routing/diagnostic context.
- «Опишите проблему» → free text, информативное поле, НЕ прямой ключ приоритета.

В UI обработки отображать правило в человеческом виде: «Если работа остановлена и затронут отдел, политика приоритета может присвоить P2» + результат настоящего серверного dry-run. Не писать в форме обещание «30 минут», если серверная policy считает иначе.

Не добавлять ручной SLA value к каждому полю. Field advanced роль означает mapping факта в policy. Сохранить inheritance system → ticket_type → category → service → offering → request_template (с фактическим приоритетом существующего resolver). Доступность route/SLA/closure проверяется publish gate. Согласование — действующая approval policy с валидным approver source; никакой произвольной передачи права пользователю выбрать согласующего вне политики.

После создания тикета существующий ticket lifecycle и его события определяют работу исполнителя, подтверждения, reopen, closure evidence. НЕ создавать отдельную систему статусов тикета в сценарном графе.

## 11. Пользовательский интерфейс и состояния

Первичный rollout — /app/requester/new, с per-offering opt-in. Пользователь видит дерево «Рабочее место → Принтеры и МФУ → Проблемы с печатью → Не печатает», либо deep-link на доступную опубликованную форму.

На экране только:
- название проблемы и краткое объяснение;
- текущую страницу/инструкцию/проверку;
- шаги/прогресс, не обещающие одинаковое число шагов для всех ветвей;
- «Назад», «Продолжить», «Не знаю», «Создать обращение» там, где это допустимо;
- ясную ошибку и восстановление прогресса.

При старте сервер проверяет разрешённость service/offering/scenario для роли и создаёт session, прикреплённую к immutable version. На каждом answer/advance сервер валидирует expected current block, actor/owner, версию, значения, вычисляет next и отдаёт только безопасную проекцию следующего шага.

**Ветвь self-service:** ответ «Помогло» → finish → подтверждение «Проблема решена без обращения»; тикет не создан. Хранить минимальное событие/агрегаты по retention и privacy; полный PII-дневник без тикета не нужен.

**Ветвь submit:** review → server-safe ticket preview → idempotent submit через существующий create → ticket_id привязан к session, requester направляется на карточку своего тикета. При double-click/double POST не появляется дубль.

**Escape hatch:** пользователь может перейти к созданию заявки при критичной/непонятной проблеме без обязательного просмотра десятков инструкций, но минимальные mandatory факты, auth, route/policy/consent checks не обходятся.

**Совместимость:** /help и локальный agent остаются на старой форме, пока для них не согласован новый клиент/contract. Если scenario absent/flag off — работает legacy requester path с прежним Service Catalog fallback other.unknown.

## 12. Хранение, версионирование, аудит (предлагаемая схема)

Новые SQLAlchemy/Alembic сущности (корректировать имена по реальным repository conventions):
- request_studio_categories: id UUID PK, service_code, parent_id FK self, slug, title, description, sort_order, visibility, lifecycle_status, created_at, updated_at, actor fields. UNIQUE на service+parent+slug с корректным handling null parent в PostgreSQL.
- request_studio_scenarios: id UUID PK, scenario_key UNIQUE, service_code, offering_full_code, category_id, title, description, published_version_id nullable, current draft revision, timestamps.
- request_studio_scenario_versions: immutable version id, scenario_id, version, schema_version, definition JSONB, canonical content hash, source refs/snapshot, published_at/actor, state published/retired/revoked; уникальность scenario_id+version и один active published per offering.
- request_studio_drafts: scenario_id, definition JSONB, optimistic revision, updated_by/at, базовая опубликованная version.
- request_studio_sessions: opaque id, actor/owner scope, immutable version id, current_block_id, typed answers (protected JSONB or project secure store), state active/completed_self_service/ticket_created/canceled/expired/revoked, linked_ticket_id, created_at/updated_at/expires_at, idempotency state.
- request_studio_audit и минимальный session event trail: кто/что/когда, block ID, version, action, redacted changes; не копировать PII/raw answers в audit.

Не строить event-sourcing платформу, если существующий audit log покрывает нужные операции: допускается уменьшить число новых таблиц без потери инвариантов. Миграции additive, indexes/foreign keys/rollback описать тестами. Существующие ticket_form_packs, service/offering, form_schema и request_templates не заменять.

Draft save защищён revision/If-Match (409 conflict), нельзя молча перетирать чужой или соседний browser-tab. Published version immutable. Активные session pinned на version; при emergency revoke сервер завершает/перезапускает безопасно, не применяет новую логику к старым ответам.

### JSON v1 (проектный пример; финальная схема строго типизирована)

~~~json
{
  "schema_version": 1,
  "scenario_key": "printer_no_print",
  "service_code": "workplace",
  "offering_full_code": "workplace.printer_issue",
  "category_id": "CATEGORY_UUID",
  "entry_block_id": "question_page",
  "blocks": [
    {
      "id": "question_page",
      "kind": "form_page",
      "title": "Уточним неисправность",
      "fields": [
        {
          "key": "work_continuity",
          "type": "radio",
          "label": "Можете продолжать работу?",
          "required": true,
          "options": [
            {"value": "yes", "label": "Да"},
            {"value": "limited", "label": "Частично"},
            {"value": "no", "label": "Нет"}
          ],
          "process_mapping": {
            "roles": ["priority_urgency", "reporting_dimension"]
          }
        }
      ],
      "transitions": [{"to": "instruction_power"}]
    },
    {
      "id": "instruction_power",
      "kind": "instruction",
      "title": "Проверьте питание принтера",
      "content": {
        "format": "markdown",
        "body": "Проверьте индикатор и подключение питания."
      },
      "transitions": [{"to": "helped"}]
    },
    {
      "id": "helped",
      "kind": "resolution_check",
      "title": "Помогло?",
      "transitions": [
        {"when": {"op": "eq", "source": "current_result", "value": "yes"}, "to": "self_done"},
        {"when": {"op": "eq", "source": "current_result", "value": "no"}, "to": "review"},
        {"when": {"op": "eq", "source": "current_result", "value": "unknown"}, "to": "review"}
      ]
    },
    {"id": "review", "kind": "review", "title": "Проверьте данные", "transitions": [{"to": "submit"}]},
    {"id": "submit", "kind": "submit_ticket", "title": "Создать обращение"},
    {"id": "self_done", "kind": "finish", "title": "Проблема решена"}
  ],
  "process_binding": {
    "request_template_key": "printer",
    "priority_source": "existing_server_policy_runtime"
  }
}
~~~

Это **иллюстративный**, не действующий формат. Codex обязан определить единое значение typed source current_result, согласовать schema DTO/TS/test и зафиксировать canon; нельзя позволять arbitrary client references/eval.

## 13. Предлагаемые серверные API

Названия уточнить под стиль server/web_api/routes без изменения семантики.

**Admin (admin edit/publish, auditor read-only):**
- GET /api/web/admin/request-studio/catalog — tree, offerings, scenario state, filters.
- POST/PATCH /api/web/admin/request-studio/categories — create/edit; retire через явное действие.
- GET /api/web/admin/request-studio/scenarios/{key} — detail/current draft/published metadata.
- POST /api/web/admin/request-studio/scenarios — new/bind offering.
- PUT /api/web/admin/request-studio/scenarios/{key}/draft — save If-Match/revision.
- POST /api/web/admin/request-studio/scenarios/{key}/validate — graph + business check.
- POST /api/web/admin/request-studio/scenarios/{key}/simulate — server-side dry-run, no side effects.
- POST /api/web/admin/request-studio/scenarios/{key}/publish-preview — canonical diff + confirmation token.
- POST /api/web/admin/request-studio/scenarios/{key}/publish — guarded immutable publication.
- GET /api/web/admin/request-studio/scenarios/{key}/versions — history/diff.
- POST /api/web/admin/request-studio/scenarios/{key}/archive — guarded archive.
- Rollback старой версии — новая безопасно проверенная публикация её содержимого, а не переписывание старой immutable записи.

**Requester-safe, только доступный scope:**
- GET /api/web/requester/request-scenarios/catalog.
- POST /api/web/requester/request-scenarios/sessions — начать опубликованный scenario.
- GET /api/web/requester/request-scenarios/sessions/{id} — текущий safe step.
- POST /api/web/requester/request-scenarios/sessions/{id}/answer — typed answer, expected_block/revision, next.
- POST /api/web/requester/request-scenarios/sessions/{id}/advance — instruction/check response.
- POST /api/web/requester/request-scenarios/sessions/{id}/ticket-preview — read-only facade на существующий process/requester preview.
- POST /api/web/requester/request-scenarios/sessions/{id}/submit-ticket — idempotent create.
- POST /api/web/requester/request-scenarios/sessions/{id}/finish — self-service completion.

**Ожидаемые ошибки:** SCENARIO_NOT_PUBLISHED, SCENARIO_FORBIDDEN, SESSION_FORBIDDEN, SESSION_EXPIRED, STEP_CONFLICT, INVALID_ANSWER, INVALID_TRANSITION, DRAFT_REVISION_CONFLICT, PUBLISH_BLOCKED, STALE_PREVIEW, DIAGNOSTIC_UNAVAILABLE. Все без утечки internal fields/actor/policy data.

**Сохранить:** /api/web/admin/request-studio/validate-draft, /publish-preview, /publish, /api/service-catalog/preview, старые формы и ticket create. Внедрять новые endpoints additively или через явные versioned DTO; не ломать существующие опубликованные payload. Все contract tests — в двух направлениях.

## 14. Проверка, симуляция, публикация

**Policy Health:** оценка ссылок/исправности политик. **Scenario Readiness:** полная проверка нового графа, полей, ветвлений, category/service/offering, route/SLA/closure, effective visibility, actual requester support и publish dependencies.

Итоговая готовность НЕ может быть «готово», если Policy Health=ok, но есть пустой маршрут, SLA, сломанный переход, недоступный блок или лишённая terminal ветвь.

Встроенные gates:
1. Draft сохранён, revision актуален, права подтверждены.
2. Граф типизирован, DAG, reachable, все ветви завершаются, обязательные fallback заданы.
3. Поля валидны, conditional requirements, совместимость requester dynamic-form, roles и process mappings.
4. Server policy simulation строится через тот же runtime, что production; профильные обязательные route/SLA/approval/closure refs разрешимы.
5. Publish preview показывает изменяемые FormSchema, RequestTemplate, service/offering, scenario graph/version/taxonomy binding и предупреждения.
6. Server token bound к **полному canonical payload hash**, actor/role, revision, nonce, TTL, используется один раз; on submit **повторная** проверка.
7. Atomic commit связанных записей; active pointer меняется лишь после успешного полного publish.
8. Аудит результата без raw confirmation token, personal data и секретов.

### Симулятор
Администратор проходит любой путь как пользователь, меняет ответы и видит переходы и explainable policy results: что привело к приоритету/очереди/срокам и какие ответы войдут в тикет. Ветви diagnostics, не имеющие live реализации, моделируются **только как симуляция**, не как реально выполненная операция. Dry-run не создаёт тикеты/операции/согласования/уведомления.

## 15. Конкретный пилот «Не печатает»

Каталог:
**Рабочее место** (service=workplace) → **Принтеры и МФУ** → **Проблемы с печатью** → **Не печатает** (существующий offering workplace.printer_issue или корректная привязка без его дублирования).

Пример ветвящегося сценария:
1. form_page «Устройство»: выбрать принтер из разрешённого списка либо «Не знаю/нет в списке».
2. form_page «Что происходит»: питание принтера, сообщение об ошибке, текст своими словами, возможность продолжать работу, кого затронуло. Могут быть последовательные вопросы на разных страницах.
3. decision по ответам: выбрать короткую безопасную ручную инструкцию (проверить питание/подключение/индикатор).
4. instruction с кнопкой «Проверил».
5. resolution_check «Помогло?» -> Да: finish без тикета; Нет/не знаю: diagnostic или сразу review.
6. diagnostic (если добавлен): до Endpoint pre-ticket support всегда unavailable -> настроенный fallback к review, никакой реальной операции.
7. review: показать ответы и проверенные шаги, предложить исправить.
8. submit_ticket: серверная safe preview -> ticket create -> реальный server routing/priority/SLA/closure, карточка тикета.
9. Support видит соответствующий безопасный summary, не вынуждает сотрудника повторять уже заполненное.

### Таблица сквозных проверок
A. «Помогло» -> завершение без тикета, счетчик тикетов не увеличился.
B. «Нет» -> один тикет с полями/сводкой и ссылкой на версию сценария.
C. «Не знаю» или без выбранного устройства -> допустимый маршрут без тупика.
D. Затронут целый отдел и работа блокирована -> правильная серверная priority policy, SLA только из runtime.
E. Изменение раннего ответа -> downstream conditional values удалены, preview stale.
F. Повторное нажатие submit и две вкладки -> один ticket или явный безопасный conflict, никаких дублей.
G. Чужая сессия/скрытая категория/нет permissions -> 403/404, не утечь лишняя metadata.
H. Endpoint unavailable/consent denied/timeout -> заданный безопасный fallback.
I. Изменение published definition при активной сессии -> pinned version, без подмены вопросов.
J. Отсутствует route/SLA/closure либо сломанный target -> publish blocked, с точным переходом к проблемному блоку.

## 16. Безопасность и эксплуатация

- Только backend authoritative auth, service/offering visibility, actor permission, session owner/tenant binding; auditor не пишет.
- Никогда не доверять client-supplied actor_id, role, queue, SLA, priority, policy code или любому device ownership без проверки.
- Typed DTO extra=forbid, нормализация UTF-8, лимиты на graph size/depth, fields, answer size, attempt rate; bounded execution, нет eval/JS/shell/Python user expressions.
- Дополнительные Markdown-инструкции рендерить с sanitizer; ссылки с безопасными протоколами; никакого XSS.
- Pre-ticket attachments только после решения хранения, ACL, antivirus policy, TTL, quota; без unsafe временных публичных ссылок.
- Для сценария без тикета минимум PII retention; session raw answers не копировать в logs/Sentry/audit. Для созданного тикета хранить только допустимые сведения и immutable schema reference.
- Multi-tab optimistic concurrency вместо silent overwrite. Expired/revoked session восстанавливать/закрывать управляемо.
- Diagnostic capability не исполняется browser/Helpdesk напрямую; только утверждённый Endpoint port, согласие и RBAC; до подключения unavailable + fallback.
- Нет горизонтального body-scroll; клавиатура/focus/ARIA/контраст; языковые тексты по-русски без mojibake.
- Никаких прямых правок файлов на production серверах, не деплоить без отдельного одобрения.

## 17. Миграция и rollout

1. Новые миграции только additive, старые service/offering/form/template/ticket данные не переписывать.
2. В каталоге показывать legacy offerings как «Обычная форма / нет сценария». Запускать генерацию черновика вручную: form_page -> review -> submit, preserve key/policies. Никакой автопубликации.
3. Per-offering flag opt-in: пока off, старый requester работает; on только при валидной published active scenario.
4. /help, локальный agent, существующие API и tickets остаются на legacy contract до отдельного согласованного перехода.
5. Rollback — отключить active scenario для offering и вернуть прежнюю форму; immutable published versions и аудит сохранить.
6. Старые активные session не мигрировать принудительно на новую версию. Для emergency revoke отдельная безопасная политика возобновления.
7. В стейджинге подтвердить полную регрессию и обратимость до любых production rollout.

## 18. План Codex по проверяемым этапам

**Все этапы исполняются последовательно: RED test -> minimal implementation -> GREEN focused/unit/integration -> browser (для UI) -> review -> docs/CODEMAP -> commit. Не объединять всё в один гигантский patch. При обнаружении контрактной несовместимости останавливать затронутый этап и сообщать точный блокер.**

### P0. Исходный baseline и исследования
- [ ] git status --short, HEAD main, соседние AGENTS, workspace scripts. GitNexus MCP query/context/impact, если доступен. Никакого ручного обхода в private infra.
- [ ] Проверить actual DTO/forms/catalog/requester/policy/ticket/create/endpoint/auth, текущие migrations и тесты.
- [ ] Записать точную dependency matrix, не трактовать design JSON как готовый API.
- [ ] Установить настоящие RED contract tests для нового сценария, доступа, старой совместимости.

### P1. Domain contracts, DB, versioning
- [ ] Typed Pydantic + TS contract, schema_version, typed block union, safe condition AST.
- [ ] Additive миграции categories/scenarios/drafts/versions/sessions/audit, индексы, optimistic revision, snapshot pinning.
- [ ] Unit+PostgreSQL tests: unique, FK, cycles, immutable version, up/down migration; старые ticket/catalog rows не меняются.

### P2. Graph validator/runtime ядро
- [ ] Deterministic reachable graph / terminal / fallback / type/role/field dependency validation.
- [ ] Блокировки broken links/cycles/unknown operations, invalid field keys, invalid conditions.
- [ ] UI и backend используют один исполняемый semantic contract; preview не содержит side effects.
- [ ] RED/GREEN table-driven и property/fuzz tests для safety.

### P3. Admin APIs и каталог
- [ ] Category tree CRUD, scenario draft/version CRUD, RBAC, optimistic concurrency, audit, search/filter.
- [ ] Привязка к существующему service/offering без дублирования.
- [ ] Tests на 200/400/403/404/409 и попытки обхода visibility.

### P4. Новый каталог и мастер в React
- [ ] Каталог вместо текущей мешанины, пять административных этапов, правильный selected-state.
- [ ] Расщепить огромный page.tsx по webapp/AGENTS.md, reuse existing UI abstractions, typed API.
- [ ] Убрать глобальный переключатель «Базовый/Расширенный/Экспертный», сохранить локальные disclosures; никаких отдельных advanced tabs.
- [ ] Component tests empty/loading/error/search/new/edit/save/reload/conflict.

### P5. Конструктор блоков и страниц
- [ ] Explorer + один выбранный блок + preview, palette/add/move/duplicate/remove.
- [ ] Многостраничные формы, один вопрос или группы, conditional branches.
- [ ] Под каждым полем, блоком, инструкцией, категорией — собственное локальное «Расширенные настройки», без переходов/вкладок.
- [ ] Multi-role mapping, picker-based identifiers, validation/alias/dependency UI.
- [ ] Keyboard interaction, focus, 1366×768 и responsive tests.

### P6. Requester session runtime/UI
- [ ] Owner-scoped session, start/resume/answer/advance/finish; immutable version pinning, TTL, idempotence.
- [ ] Инструкции, проверки результата, условная видимость, session Back с очисткой downstream.
- [ ] Diagnostic unavailable+fallback; никаких real Endpoint calls.
- [ ] Выдать новый flow за per-offering flag в /app/requester/new; иначе старый UI.
- [ ] Tests multi-step, branches, invalid required/hidden answers, owner/auth, expired state.

### P7. Реальное создание тикета и политики
- [ ] Собранные валидированные answers -> existing canonical form submission, offering refs, custom_fields snapshot.
- [ ] Safe requester preview -> existing create; server canonical priority/routing/SLA/OLA/approval/closure.
- [ ] Idempotent submit, PostgreSQL transaction consistency, support summary.
- [ ] RED/GREEN интеграции и regression старых /help, agent form-only и default fallback.

### P8. Scenario Readiness + публикация
- [ ] Разделить Health и Readiness, validate all branches и backend effects.
- [ ] Reuse/extending existing safe preview+one-use confirmation token, binding full scenario+form/template/offering/taxonomy hash.
- [ ] Atomic publish immutable version/active pointer, compare diff, optimistic/race checks.
- [ ] Тесты неверного/просроченного/reused token, actor mismatch, edit-after-preview, rollback-as-new-version.

### P9. Диагностика/вложения — безопасные границы
- [ ] Диагностический inspector, typed status/consent/fallback и simulation-only result, без исполнения.
- [ ] Проверить и реализовать safe pre-ticket attachment staging при необходимости; иначе явный publish blocker и отсечка unsupported field.
- [ ] Tests unavailable/denied/timeout/capability absence, no fake success/no ticket side effects.

### P10. End-to-end, выпускные gates и документация
- [ ] Seed в staging ТОЛЬКО тестового черновика «Не печатает», не менять живые published offerings.
- [ ] Пройти A–J в §15, включая настоящую попытку создания тестового тикета в изолированном staging с cleanup по правилам проекта.
- [ ] Playwright/browser screenshots на 1366×768, 1440×900, 1920×1080 и tablet; нет горизонтальной прокрутки, primary visible, один редактор, инлайн advanced settings, no console/network errors.
- [ ] Focused tests, typecheck, build, PostgreSQL tests, canonical CI, Semgrep/SonarQube/coverage gates (не ослаблять).
- [ ] Обновить server/docs/SERVICE_CATALOG.md, REQUEST_FORM_BUILDER.md, CODEMAP, browser/user docs, PLANS.md, migration/rollback runbook.
- [ ] Финальный отчёт: этапы, sha, CI links, RED/GREEN доказательства, браузерные изображения, остаточные риски, STOP до production deploy.

## 19. Критерии приёмки (не сокращать)

- [ ] AC01: В Студии по умолчанию каталог всех типов, поиск, дерево категорий с произвольной вложенностью, статусы, primary «Создать сценарий».
- [ ] AC02: Административный мастер строго пошаговый, на экране текущий шаг вместо всего сразу.
- [ ] AC03: В редакторе открыт только один selected block, остальное навигация; live preview скрываемый.
- [ ] AC04: «Расширенные настройки» ЛОКАЛЬНО внутри каждого поля и блока, НЕТ дополнительной вкладки/страницы/глобального advanced mode.
- [ ] AC05: Страница формы имеет один вопрос или группу, сценарий 30+ вопросов не делает UI непригодным.
- [ ] AC06: Condition/branch вычисляется сервером, conditional required и hidden stale answers работают.
- [ ] AC07: У поля несколько совместимых ролей и правильная серверная проверка process mapping.
- [ ] AC08: Инструкция + «Помогло?» -> self-resolution без тикета либо запрос тикета.
- [ ] AC09: Diagnostic unavailable приводит к fallback; нет фиктивного успешного Endpoint результата и pre-ticket dispatch.
- [ ] AC10: Приоритет/queue/SLA/согласования определяются существующими серверными политиками.
- [ ] AC11: Preview/simulate не создают тикета, операций, согласований или уведомлений.
- [ ] AC12: Double submit создаёт ровно 1 ticket, session становится ticket_created.
- [ ] AC13: Actor/tenant scoping, 403/404 без утечек, revision conflicts и pinned sessions.
- [ ] AC14: Health=ok не маскирует publish blockers графа/маршрута/SLA/закрытия.
- [ ] AC15: Diff + one-use token + revalidation + immutable version; rollback контролируем.
- [ ] AC16: Legacy forms, /help, agent, сервисы, тикеты и API продолжают работать.
- [ ] AC17: Сценарий принтера A–J проходит через браузер без JSON/экспертных страниц.
- [ ] AC18: 1366×768/1920×1080 browser PASS, keyboard/accessibility, no body overflow, loading/empty/error.
- [ ] AC19: Additive migrations/rollback, backend/frontend/E2E/CI green; Semgrep/coverage/Sonar не ослаблены.
- [ ] AC20: Нет включения сценариев и развёртывания на production без отдельного согласования владельца.

## 20. Не входит в текущую реализацию без отдельного разрешения

- Живые pre-ticket Endpoint operations, удалённое выполнение, agent transport и скрытая диагностика устройства.
- Параллельный lifecycle engine после создания тикета, независимые SLA/queue/approval сервисы.
- Генерация правил произвольным AI без admin review, сторонняя Knowledge platform, исполнение пользовательских скриптов.
- Массовая автопубликация seeded/legacy forms в production, изменение исторических тикетов или production data без отдельного релизного допуска.
- Переход /help/локального desktop-agent на новый client runtime без самостоятельного backward-compatibility gate.

## 21. Результат для Codex

По завершении каждого этапа: список файлов, реализованный контракт, запущенные RED/GREEN тесты с командами, git commit SHA, docs/CODEMAP drift, ограничения и фактический результат. Не утверждать «работает» только по компиляции: пользовательский UI должен быть проверен реальным браузером по AGENTS и project browser skill. При реальном блокере contract/infrastructure остановить только соответствующий этап, объяснить blocker, не обходить safety и не продолжать зависимые этапы.

**Production deploy и публикация новых рабочих сценариев — отдельное явное согласование.**
