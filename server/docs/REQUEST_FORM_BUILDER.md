# Конструктор форм заявок

Документ описывает рабочий сценарий администратора для каталога входящих заявок `request_forms`.

## Канонические поверхности

- Legacy shell: вкладка `Конструктор форм` в `/admin`, файлы `server/admin_ticket_forms_builder.html` и `server/admin_ticket_forms_builder.js`.
- Новый typed workspace: панель `Конструктор форм заявок` в `/app/admin`, файлы `webapp/src/features/forms-builder/forms-builder-panel.tsx` и `webapp/src/features/forms-builder/api.ts`.
- Новый typed boundary для React-панели: `GET /api/web/admin/forms/current`, `POST /api/web/admin/forms/save` и `POST /api/web/admin/forms/route-preview`.
- Доменный pack-registry остаётся общим: `GET /api/ticket_forms/current`, `GET /public_api/ticket_forms/current`, `POST /api/ticket_forms/packs/save`, `PATCH /api/ticket_forms/packs/{pack_key}/{version}/preferred`.

## Зачем нужен конструктор

Конструктор управляет типовыми формами, которые используют:

- пользователь на странице `/help`;
- локальный агент при создании заявки;
- сервер при валидации `form_key`, `form_payload` и `ticket_type`;
- настройки маршрутизации в `/app/settings`, которые получают typed catalog текущих форм и могут строить правила по `request_form_data.<field>`;
- support workspace `/app/support`, который показывает нормализованную сводку ответов в блоке `Данные формы`;
- diagnostic playbooks, которые могут стартовать при создании тикета и получать пакет фактов из ответов формы;
- отчёты, которые подписывают `request_kind` по текущему preferred form pack.

Цель конструктора: собирать понятные формы без ручного редактирования JSON и без лишних технических решений в обычном операторском сценарии.

## Основные сущности

- Каталог форм: пакет с `pack_key`, внутренней `version`, `title`, `description`, `forms`.
- Форма: тип заявки с `key`, `request_kind`, `title`, `description`, `fields`, опциональными `playbook_triggers`.
- Поле: элемент формы с `key`, `label`, `type`, `required`, `placeholder`, `help_text`, `options`, `visible_when`.
- `playbook_triggers`: список автозапусков сценариев; сейчас поддержан `event=ticket_created` и безопасный `module_kind=diagnostic`.

Важно: сейчас в продукте используется один рабочий каталог `request_forms`. Поэтому в обычном UI администратор работает в первую очередь с формами и полями, а не со служебными параметрами каталога. Версионность каталога остаётся внутренней серверной механикой.

## Обычный сценарий администратора

### 1. Открыть список форм

Слева показывается единый список форм. Достаточно нажать на форму один раз, чтобы открыть её поля и параметры.

Если нужна новая форма, используйте кнопку `Новая форма`.

### 2. Заполнить основу формы

На базовом пути администратор заполняет только:

- название формы;
- системный ключ формы;
- список полей.

Дополнительные параметры должны быть скрыты в `Расширенных настройках`.

### 3. Добавить поля

Для каждого поля в базовом сценарии нужны:

- название поля;
- ключ поля;
- тип поля;
- обязательность.

Если тип поля `select` или `radio`, редактор должен запросить варианты ответа.

Добавление поля должно идти через раскрывающееся меню `Добавить поле`, а не через набор разрозненных кнопок по экрану.

### 4. Проверить форму

Перед сохранением администратор должен видеть:

- краткую сводку по форме;
- список ошибок или предупреждений, если что-то не заполнено;
- понятное подтверждение, что после сохранения каталога изменения сразу станут активными.

### 5. Сохранить каталог

Публикация каталога делается одной кнопкой `Сохранить изменения`.

При сохранении сервер:

- автоматически создаёт новую внутреннюю версию пакета;
- сразу делает её активной;
- отдаёт обновлённый каталог в `/help` и агент.

От администратора не требуется:

- вручную указывать номер версии;
- выбирать активную версию;
- переключаться между историческими версиями в обычном интерфейсе.
- постоянно видеть название или описание каталога в базовом сценарии.

### 6. Привязать диагностический плейбук

В блоке `Плейбук при создании тикета` можно указать ключ опубликованного плейбука, например `site_not_opening`, и включить автозапуск.

При создании тикета сервер переносит trigger в `custom_fields.request_form_playbook_triggers`, собирает `facts_package` из `request_form_data` и `request_form_summary`, запускает последнюю опубликованную версию сценария и пишет событие `playbook_started` в тикет.

Плейбуки описаны в `server/docs/DIAGNOSTIC_PLAYBOOKS.md`. В этом UI допустим только класс `diagnostic`: он собирает факты и не меняет устройство.

## Что считается расширенными настройками

Эти параметры не должны мешать базовому сценарию и должны быть скрыты под `details/summary` или отдельным advanced-блоком:

- `title` и `description` каталога;
- `description` формы;
- `request_kind`, если он отличается от `key`;
- `placeholder`;
- `help_text`;
- `visible_when`;
- raw JSON preview.

## Маршрутизация и preview

- Конструктор форм теперь напрямую связан с routing builder: `GET /api/web/settings` возвращает `routing_builder` catalog, собранный из текущего preferred pack, поэтому правила маршрутизации можно настраивать по базовым полям тикета и по `request_form_data.<field>` без ручного угадывания ключей.
- Preview маршрута вызывается через `POST /api/web/admin/forms/route-preview`: React-панель отправляет текущий draft формы и примерные значения, а сервер отвечает, какая очередь и какое правило совпадут, либо что сработал fallback.
- Runtime routing использует тот же form-aware context, что и preview: `ticket_type`, `request_kind`, `custom_fields`, `request_form_data`, `request_form_key`, `request_form_title`, `request_form_summary`.

## Integrity rules для зависимых полей

- `visible_when.field` должен ссылаться на реально существующее поле внутри той же формы; серверная валидация отклоняет пакеты с битой ссылкой ещё до публикации.
- При rename/delete поля React builder должен автоматически обновлять или очищать связанные `visible_when.field`, чтобы администратор не оставил невидимое навсегда поле.
- Visibility rules поддерживают как `equals`, так и `in`; это покрыто серверными тестами и должно оставаться совместимым для `/help`, локального агента и preview маршрута.

## Правила ключей

- Используйте латиницу, цифры и `_`.
- Для форм придерживайтесь коротких semantic key: `printer`, `access`, `site_system`.
- Для полей придерживайтесь snake_case: `printer_model`, `system_name`, `affected_scope`.
- Если `request_kind` не переопределён, он должен совпадать с `key`.
- Ключ формы должен быть уникальным в каталоге.
- Ключ поля должен быть уникальным внутри своей формы.

## Подсказки, которые должны быть в UI

Интерфейс должен объяснять:

- что в системе один рабочий каталог и в обычной работе нужно думать именно о формах;
- что клик по форме открывает поля, а клик по полю открывает его параметры;
- что ключи нужны для API, аналитики и маршрутизации;
- что сложные правила показа доступны в расширенных настройках;
- что после кнопки сохранения сервер сам выпускает новую активную редакцию каталога.

## Где используется этот контракт

- UI администратора: `server/admin_ticket_forms_builder.html`, `server/admin_ticket_forms_builder.js`, `server/admin.html`, `webapp/src/features/forms-builder/forms-builder-panel.tsx`
- Серверная валидация и default pack: `server/tickets/form_catalog.py`
- HTTP API pack registry: `server/tickets/form_pack_handlers.py`, typed web boundary `server/web_api/admin_handlers.py`
- Публичная форма: `server/help.html`, `server/help.js`
- Агентский диалог создания тикета: `pc_agent/ui_gui/chat_panel.py`
## 2026-04-29 priority question contract

- Priority facts are normal request-template fields, not hardcoded priority selectors.
- The standard field keys are `impact_scope`, `work_continuity`, `business_importance`, `critical_service` and `public_service`.
- `priority_policy.impact_field`, `priority_policy.urgency_field`, `priority_policy.importance_field` map those fields into the deterministic priority engine.
- `priority_policy.modifier_fields` maps boolean modifiers such as `critical_service` and `public_service`.
- `field_roles` marks how fields participate in process execution. The supported roles in the React builder are `routing_field`, `priority_field`, `sla_field`, `approval_field`, `diagnostic_input`, `closure_evidence` and `display_only`.
- `/app/admin/forms` can add the standard priority question set to any request template, after which every label, option, required flag and role remains editable in the server UI.
- The local agent reads the same server form pack. If a template defines priority fields, the agent renders those fields in the priority step and sends their values in `form_payload`. Fixed local priority controls are only a fallback for old packs without priority fields.
- SLA shown to the requester/agent is not local text. It is read from the created/refreshed ticket payload (`first_response_due_at`, `resolution_due_at`) after the server computes effective priority and SLA targets.
