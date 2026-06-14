## Active Work: Knowledge Platform Refactor — Production Authoring, Sections, Visibility and Help Desk Integration

Status, 2026-06-15: Registry Visibility Foundation is ready enough to start Knowledge Platform refactor. Registry now separates departments, locations, access groups, audience groups, roles, people, identities and account sessions. Knowledge visibility has backend foundation through `knowledge_audience_rules`, `KnowledgeAccessService`, `KnowledgeAudienceRulesService`, admin preview/explain APIs, and effective-audience enforcement in search/suggest/Ask/RAG/retrieval paths. The next work is not another card-level UI pass. The next work is a product refactor of Knowledge authoring: simplify article creation, introduce Knowledge Sections as policy containers, connect articles to Registry audiences and Help Desk context, and hide internal mechanics such as review, manual segmentation and version plumbing from the normal editor.

Execution checkpoint, 2026-06-15: K0 registry preflight was closed by commit `baa0fe8e` before this Knowledge refactor slice. K1 is closed locally and on the live stand: `/app/admin/knowledge/sections` is the product route for `Разделы базы знаний`; it reuses existing `GET|POST /api/web/knowledge/spaces` for section policy and existing `subject_type=space` audience-rule APIs for default section audience preview/save, stores article counts/allowed types/exposure flags/length recommendation without a schema migration, and shows per-list audience summaries without raw target ids. K2 initial local slice is now implemented: `/app/admin/knowledge/studio` hides default review/version/segmentation mechanics, exposes one primary `Сохранить статью` action, creates a version and publishes it in one flow, keeps rollback inside `История версий`, adds Russian field explanations and uses backend reviewer autofill when `KNOWLEDGE_REVIEW_REQUIRED` is false. Remaining K2 gap: live browser evidence for create/edit/save article on the stand.

### Problem Statement

The current Knowledge Studio still exposes too much internal platform machinery to the user:

- review workflow is visible even though it does not match current admin/support workflow;
- version creation and publishing are separate visible actions;
- manual segmentation appears like a required part of article creation;
- metadata, taxonomy, applicability, quality and visibility controls are mixed with authoring;
- article visibility is technically powerful but not yet shaped into a simple product-level control;
- articles are not yet presented as first-class help desk assets connected to services, request templates, tickets and support suggestions;
- “space” is still a technical term; the intended product concept is “Раздел базы знаний”.

The goal is to make Knowledge authoring production-grade:

> A support/admin user writes a useful article, selects where it belongs, chooses who can see it, links it to help desk context, and clicks one primary action: “Сохранить статью”.

The system should handle versions, chunks, indexing, RAG eligibility, visibility checks and publication mechanics.

---

## 0. Preflight / Known Unfinished Registry Tasks

### 0.1. Expose `access_group` in audience-group member UI

Current backend/types support audience group members of type:

- `person`
- `department`
- `department_tree`
- `location`
- `access_group`
- `role`
- `service`

But the Registry audience group UI member type dropdown currently omits `access_group` even though the label exists. Add `access_group` to the selectable member type list and load options from `/api/web/admin/access/summary`.

Acceptance:

- `/app/admin/registry` → `Аудитории` allows adding `Группа доступа` as audience member.
- Member preview resolves people from access group membership.
- Existing warning text remains clear: access groups grant RBAC permissions, while audiences only target content.
- Add/adjust vitest coverage for selecting `Группа доступа`.
- Keep raw group ids hidden except in advanced/debug text.

### 0.2. Keep Registry quality issues visible

Registry quality must continue surfacing:

- `audience_group_empty`
- `knowledge_audience_rule_invalid_target`
- `knowledge_audience_zero_users`

These are not blockers for starting Knowledge refactor, but they are safety checks that must remain visible in `/app/admin/registry` → `Качество данных`.

### 0.3. Document current access limitations

Current `knowledge_audience_rules` are allow-only. There is no deny/exclude precedence yet.

Current privileged roles:

- `support`
- `admin`
- `security`
- `auditor`

may pass audience rules through privileged override after coarse visibility. Keep this behavior for support/admin workspaces, but document a future AI policy decision:

`ai_respects_audience_for_privileged_roles`.

This is not required for the current Knowledge Studio simplification.

---

## 1. Product Model Decisions

### 1.1. Rename “Space” to “Раздел базы знаний”

User-facing term:

- Old: `Пространство`
- New: `Раздел базы знаний`

Internal API/database names can stay `KnowledgeSpace`, `space_id`, `space_code`.

Meaning:

A Knowledge Section is a policy container. It is not merely a folder.

A section defines:

- display name and description;
- default visibility;
- default audience rules;
- allowed article types;
- whether publication is allowed;
- whether ingestion/import is allowed;
- whether RAG/AI usage is allowed;
- whether requester portal exposure is allowed;
- default review/refresh policy if review is enabled later;
- default category/taxonomy scope;
- default help desk binding behavior.

Example sections:

- `Самообслуживание сотрудников`
- `IT Support`
- `Известные ошибки`
- `Глоссарий`
- `Регламенты организации`
- `Информационная безопасность`
- `Администрирование систем`

### 1.2. Separate four concepts

Do not mix these concepts in UI or backend naming:

1. **Раздел базы знаний**
   - Where the article lives.
   - Defines defaults and policy.

2. **Тип материала**
   - What kind of content it is.
   - Defines template/structure.

3. **Кому доступна статья**
   - Coarse visibility plus Registry audience rules.

4. **Где показывать статью**
   - Portal, support workspace, agent, AI/RAG, request form suggestions.

### 1.3. Keep coarse visibility as safety boundary

Coarse visibility remains a hard safety boundary:

- `requester`
- `agent_requester_safe`
- `support_internal`
- `admin_internal`
- `security_restricted`
- `auditor_read`

Audience rules can narrow or allow within this boundary, but must not turn `support_internal` into requester-visible content.

UI labels:

- `requester` → `Видна заявителю`
- `agent_requester_safe` → `Видна заявителю и агенту`
- `support_internal` → `Только поддержке`
- `admin_internal` → `Только администраторам`
- `security_restricted` → `Ограничено безопасностью`
- `auditor_read` → `Только аудиторам`

Normal article editor should show only the safe common choices. Advanced choices can remain hidden for admin/security cases.

---

## 2. Knowledge Sections Constructor

Create or refactor a dedicated page:

`/app/admin/knowledge/sections`

Purpose:

A production editor for Knowledge Sections / “Разделы базы знаний”.

### 2.1. Section list

Show:

- name;
- code;
- status;
- default visibility;
- RAG enabled/disabled;
- portal enabled/disabled;
- article count;
- audience summary;
- warnings.

### 2.2. Section editor

Fields:

- Название раздела
- Код
- Описание
- Статус: active / draft / archived
- Видимость по умолчанию
- Разрешённые типы материалов
- Разрешить публикацию
- Разрешить импорт
- Разрешить использование в RAG / AI
- Показывать в портале заявителя
- Показывать в рабочем месте поддержки
- Default category/taxonomy scope, if available
- Default article length recommendation
- Default audience

### 2.3. Section audience

Embed simplified visibility/audience controls at section level.

Modes:

- Всем в рамках видимости
- Только выбранным подразделениям
- Только выбранным аудиториям
- Только выбранным локациям
- Только выбранным сервисам
- Расширенные правила

Rules are saved as `knowledge_audience_rules` with `subject_type=space`.

### 2.4. Section policy inheritance

Define and document behavior:

- Article inherits section audience if the article has no item-level rules.
- Article can narrow or override using item-level rules.
- Item-level rules and section-level rules are both evaluated by `KnowledgeAccessService`.
- UI should explain this in plain Russian:
  “Статьи наследуют правила раздела. Можно задать отдельные правила для конкретной статьи.”

### 2.5. Acceptance

- Admin can create/edit/archive a section without raw JSON.
- Admin can set default audience for a section.
- Admin can preview who will see articles in the section.
- Section editor does not expose raw ids by default.
- Existing `KnowledgeSpace` backend can be reused unless a small API extension is needed.

---

## 3. Simplify Knowledge Studio

Route:

`/app/admin/knowledge/studio`

Current Studio must be simplified into a real article editor.

### 3.1. Main principle

Default Studio UI must not show:

- review workflow;
- manual version selection;
- manual segmentation;
- raw audience rules;
- advanced metadata tabs;
- AI/debug blocks;
- raw ids.

Default Studio UI must show:

- article list;
- article editor;
- basic settings;
- visibility/audience;
- help desk binding;
- one primary action: `Сохранить статью`.

### 3.2. Remove review workflow from default UI

Hide from normal UI:

- `Отправить на ревью`
- `Одобрить`
- `Запросить правки`
- `Добавить комментарий`
- `Комментарий ревью`
- reviewer checklist

Backend review code can remain.

Publishing must not fail due to missing reviewer in simplified mode.

Required backend/product decision:

- Add config/policy: `KNOWLEDGE_REVIEW_REQUIRED=false`, or
- Auto-fill `reviewer_actor_id` with current actor or `servicedesk` when empty.

Acceptance:

- User can save/publish a normal article without manually assigning reviewer.
- Review UI is not visible in default Studio.
- Review-related code is not deleted unless required; it can remain as future/advanced governance.

### 3.3. One save action

Replace visible “Создать версию” + “Опубликовать версию” workflow with one button:

`Сохранить статью`

Behavior:

1. If new article: create item draft.
2. Create new version from current form.
3. Publish new version as current.
4. Refresh item list and selected item.
5. Show success:
   “Статья сохранена и опубликована. Текущая версия: vN.”

Keep version history in a drawer:

- `История версий`
- current version marked clearly;
- old versions can be previewed;
- restore/rollback only inside the drawer with confirmation.

### 3.4. Article editor fields

Default form:

- Заголовок
- Краткое описание
- Раздел базы знаний
- Тип материала
- Кому доступна статья
- Аудитория
- Где показывать статью
- Связанные услуги / формы обращения
- Теги
- Текст статьи

### 3.5. Explain important fields in the UI

For `Раздел базы знаний`:

“Раздел определяет, где хранится статья и какие политики применяются по умолчанию: видимость, аудитория, RAG, импорт и допустимые типы материалов.”

For `Тип материала`:

“Тип определяет шаблон и смысл статьи. Для обычной инструкции выбирайте ‘Инструкция / статья’.”

For `Кому доступна статья`:

“Это базовый уровень доступа. Он ограничивает, кто вообще может получить статью: заявитель, агент, поддержка, администратор.”

For `Аудитория`:

“Аудитория уточняет доступ внутри выбранной видимости: подразделения, группы, локации, сервисы или отдельные сотрудники.”

For `Где показывать статью`:

“Определяет, в каких сценариях система будет предлагать статью: портал заявителя, форма обращения, карточка тикета, агент, AI/RAG.”

### 3.6. Default article types

Normal UI:

- Инструкция / статья
- FAQ
- Известная ошибка
- Обходное решение
- Термин

Advanced types hidden:

- policy
- document
- troubleshooting_tree
- service_description
- external_source
- resolution_draft

### 3.7. Segmentation policy

Default:

- manual segmentation hidden;
- chunks are created automatically by backend from version body;
- optional auto-segmentation hidden under advanced.

Display simple status:

“Поисковые фрагменты создаются автоматически по заголовкам и тексту статьи.”

Advanced section:

- Поисковые фрагменты
- Авторазметка
- Ручная разметка
- Сегменты версии

Acceptance:

- The default article flow does not require creating segments.
- Manual boost/full-text/embedding checkboxes are not visible by default.
- Advanced segmentation still available for long documents and RAG tuning.

---

## 4. Article Visibility and Audience UX

### 4.1. Default visibility modes

In article editor, show simple options:

1. `Всем в выбранной видимости`
2. `Только выбранным подразделениям`
3. `Только выбранным аудиториям`
4. `Только выбранным сервисам`
5. `Расширенные правила`

Internally these save `knowledge_audience_rules`.

### 4.2. Human-friendly audience rules

The UI must avoid “target_type / target_id”.

Use labels:

- Подразделение
- Подразделение и дочерние
- Аудитория
- Группа доступа
- Локация
- Сервис
- Сотрудник
- Роль

The advanced/debug view may show technical ids.

### 4.3. Preview

Every visibility editor must show:

- estimated people count;
- examples of matched people;
- warnings:
  - no rules means broad visibility;
  - rules resolve to zero people;
  - internal article cannot become requester-visible through audience;
  - invalid/archived target.

### 4.4. Explain access

Keep admin-only explain:

- choose test user/login;
- show “видит / не видит”;
- show reason code;
- do not expose hidden content to denied users.

---

## 5. Help Desk Context Binding

The Knowledge Platform must connect articles to help desk flows.

### 5.1. Rename “bindings” in UI

User-facing label:

`Где показывать статью`

or

`Связь с обращениями`

Do not expose “binding_id” or raw binding model in the default UI.

### 5.2. Binding fields

Support these context links:

- service_code
- offering_code
- request_template_key
- ticket_type
- reporting_category
- device_class
- os_family
- symptom_code
- error_code
- queue_code
- priority / weight

Start with the most valuable:

- Service
- Offering
- Request template
- Ticket type
- OS family / device class if available

### 5.3. Surfaces

For each article or binding, define where it can be suggested:

- requester portal before submit;
- requester portal after submit;
- support ticket workspace;
- support command center;
- agent;
- AI/RAG.

This can be stored either in binding metadata or article metadata initially, but must be represented consistently in UI.

### 5.4. Acceptance

- Article can be linked to a service/offering/request template from Studio.
- Requester ticket creation can use requester-safe articles filtered by effective requester audience.
- Support ticket suggestions can use requester-safe articles by requester audience and support_internal runbooks by support context.
- No hidden article title/snippet leaks into denied suggestions.

---

## 6. Search / RAG / AI Readiness

### 6.1. Current enforcement must stay

All candidate paths must continue applying effective audience before projection:

- keyword search;
- segment search;
- vector search;
- suggestions;
- Ask/RAG;
- retrieval;
- portal home/collections/article detail;
- support ticket suggestions.

### 6.2. Article properties required for RAG

The simplified article model must preserve:

- title;
- summary;
- body;
- section;
- type;
- coarse visibility;
- audience rules;
- current published version;
- chunks;
- source/freshness fields;
- service/request-template binding;
- related articles / graph links later.

### 6.3. RAG eligibility

Add clear setting at section and/or article level:

- `Использовать в AI/RAG`

Default from section.

Options:

- Allowed
- Disabled
- Admin/support only
- Requester-safe only

This should not replace visibility. It is a second gate: content can be visible to a user but still excluded from AI answers if policy requires.

---

## 7. Knowledge Operations Center Adjustments

Route:

`/app/admin/knowledge`

This should be an operations dashboard, not a CRUD/editor page.

Show:

- health summary;
- low quality articles;
- empty/broken audience rules;
- sections with zero articles;
- requester-visible articles with zero effective users;
- indexing errors;
- zero-result searches;
- help desk gaps;
- articles without service/request template binding.

Remove or hide:

- raw content pack JSON;
- article creation form;
- publish forms;
- large policy editors.

---

## 8. Knowledge Import

Route:

`/app/admin/knowledge/import`

Keep import as wizard:

1. Source
2. Preview
3. Create article draft
4. Open in Studio

Important:

- Imported document should default to draft/internal until reviewed.
- Long imported documents may use auto-segmentation.
- Import should select section, visibility and audience.
- AI enrichment stays policy-gated.

---

## 9. Registry Follow-ups Required by Knowledge

### 9.1. Audience group member type `access_group`

Add to UI member types and tests.

### 9.2. Registry quality surface

Confirm `/app/admin/registry` quality tab shows:

- empty audience groups;
- invalid knowledge audience rule targets;
- requester-visible knowledge scoped to zero users.

### 9.3. Registry option pickers

Knowledge UI needs reliable pickers for:

- departments;
- locations;
- people;
- audience groups;
- access groups;
- services.

Use existing Registry/Admin APIs where possible.

---

## 10. Tests

### 10.1. Backend tests

Add/keep coverage for:

- audience-scoped requester article visible to matching department;
- denied department cannot see title/snippet/body/result count;
- audience group rule works;
- space-level rule works;
- item-level rule works;
- service-context rule works;
- privileged actor behavior documented;
- support suggestions do not leak requester-scoped articles for other departments;
- Ask/RAG/vector retrieval filters before citations/prompt construction;
- simplified save article creates version and publishes current version;
- review disabled/autofill mode allows saving without manual reviewer.

### 10.2. Frontend tests

Add/keep coverage for:

- Registry audience groups can add person/department/department_tree/location/role/service/access_group.
- Knowledge Studio default UI has no review buttons.
- Knowledge Studio has one primary `Сохранить статью` button.
- Article save calls create item/version/publish flow or new unified endpoint.
- Manual segmentation hidden by default.
- Advanced section can reveal segmentation.
- Visibility selector can choose department/audience/service.
- Visibility selector warns on zero audience.
- Section constructor can save default visibility/audience/RAG settings.
- No horizontal scroll at 1366x768.

### 10.3. Live validation

Capture browser evidence for:

- `/app/admin/registry` → `Аудитории`: create audience, add members, preview.
- `/app/admin/registry` → `Качество данных`: audience/knowledge visibility issues visible.
- `/app/admin/knowledge/sections`: create/edit section, set default audience.
- `/app/admin/knowledge/studio`: create article, set section, set visibility/audience, save article.
- Requester portal search: matching user sees article.
- Non-matching user does not see article or title/snippet.
- Support ticket suggestions: requester-safe scoped articles filtered by requester; support_internal runbooks still visible to support.

---

## 11. Implementation Order

### Phase K0 — Registry preflight

- Done in commit `baa0fe8e`: added `access_group` selector to Registry audience group members.
- Done in commit `baa0fe8e`: verified Registry quality issues for audience/knowledge visibility.
- Done in commit `baa0fe8e`: recorded browser evidence for the registry audience/quality slice.

Exit bar:

- focused tests pass;
- browser evidence for audience group member preview;
- no raw prompt regression.

### Phase K1 — Knowledge Section Constructor

- Done, initial slice: add `/app/admin/knowledge/sections` and navigation entry.
- Done, initial slice: use “Раздел базы знаний” / “Разделы базы знаний” in the new user-facing section constructor while keeping internal `KnowledgeSpace` API names.
- Done, initial slice: build section list/editor for title, code, description, status, default visibility, RAG/import/publication flags.
- Done, initial slice: add default audience editor for sections with preview/save via `subject_type=space`.
- Done, initial slice: reuse existing backend APIs; no schema migration required.
- Done, follow-up slice: show section article counts, allowed material type controls, requester-portal/support-workspace exposure controls and article length recommendation; save them through existing `KnowledgeSpace.allowed_item_types` and `KnowledgeSpace.metadata`.
- Done, follow-up slice: explain policy inheritance in the section audience panel: “Статьи наследуют правила раздела. Можно задать отдельные правила для конкретной статьи.”
- Done, follow-up slice: show per-list audience summaries from `subject_type=space` rules, including estimated matched people when Registry lookups resolve, while hiding raw target ids in the normal list.
- Done, final live browser evidence for create/edit/default-audience: `artifacts/browser_live_validation/knowledge-sections-k1-9127b545-audience-summary-1781470964426/summary.json`.

Exit bar:

- admin can configure section policy without raw JSON;
- section-level audience preview works;
- docs updated.

### Phase K2 — Simplified Knowledge Studio

- Done, initial local slice: remove review actions, reviewer checklist and review comments from default Studio UI.
- Done, initial local slice: replace visible create-version/publish-version actions with one `Сохранить статью` button that creates a new version and publishes that exact version.
- Done, initial local slice: backend publication no longer fails a normal item only because reviewer is empty when `KNOWLEDGE_REVIEW_REQUIRED=false`; missing reviewer is autofilled from current actor or `servicedesk`.
- Done, initial local slice: hide manual segmentation and advanced metadata by default; manual/auto segment controls remain behind advanced tools.
- Done, initial local slice: add Russian field explanations for section, material type, coarse visibility, audience and display surfaces.
- Done, initial local slice: keep rollback/version selection inside `История версий` drawer with explicit confirmation.
- Done, final live browser evidence for creating/editing/saving an article through the simplified Studio: `artifacts/browser_live_validation/knowledge-studio-k2-10a7a5ef-simplified-save-1781475681396/summary.json`.

Exit bar:

- a support/admin user can create and publish a basic article in one flow;
- no review actions visible;
- no manual version selection required;
- no segmentation required;
- primary action visible above fold.

### Phase K3 — Help Desk binding

- Add “Где показывать статью” / “Связь с обращениями”.
- Link article to service/offering/request template.
- Ensure suggestions use service/request-template context plus audience filtering.
- Add UI preview: “где статья будет предложена”.

Exit bar:

- article appears in relevant request/support contexts;
- denied audience does not see requester-safe content.

### Phase K4 — RAG readiness

- Add section/article AI/RAG eligibility.
- Ensure retrieval respects visibility + audience + RAG eligibility.
- Add trace/explain for why article was included/excluded.
- Keep citations safe.

Exit bar:

- Ask/RAG never uses denied content;
- admin explain can show rule reason;
- requester response never leaks hidden metadata.

### Phase K5 — Operations polish

- Update `/app/admin/knowledge` as Knowledge Operations Center.
- Add actionable queues:
  - no audience users;
  - missing help desk binding;
  - stale article;
  - indexing failed;
  - low quality;
  - zero-result searches.
- Keep Studio focused on authoring.

Exit bar:

- operations page shows what needs attention;
- authoring page stays simple.

---

## 12. Non-goals For This Refactor

Do not implement now:

- full deny/exclude rule precedence;
- full AD/LDAP sync;
- full document management system;
- complex approval/CAB-like review workflow;
- manual segment tuning as default;
- AI rewriting/generation as default;
- public internet publishing.

These can remain future capabilities.

---

## 13. Product Acceptance Definition

The refactor is successful when:

1. A support/admin user can create a useful article without understanding versions, chunks, segments or review.
2. A section admin can define default policies for a Knowledge Section.
3. Article visibility can target departments, audience groups, services and people through Registry.
4. Requester/support/AI search uses the same backend access decision path.
5. Hidden articles do not leak titles, snippets, result counts, citations or body text.
6. Help Desk forms/tickets can receive contextually relevant articles.
7. Manual segmentation and advanced metadata exist only as advanced tools.
8. Registry remains the source of truth for people, departments, groups and audiences.
