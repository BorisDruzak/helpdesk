# webapp/AGENTS.md - Webapp Instructions

## Scope

This file applies to frontend/browser-visible work under `webapp/`.

Use it for:

- frontend routes/pages/components
- admin UI behavior
- forms, tables, modals, navigation
- browser-visible state and data flows
- visual/CSS/responsive changes
- frontend build/toolchain behavior
- browser validation
- webapp docs updates

Root `AGENTS.md` still applies.

## Local context

Before non-trivial webapp edits, consult only the relevant frontend documentation:

- `docs/CODEX_WORKFLOW.md`
- `docs/LIVE_TESTING_DEBUG_RULES.md`

## Relevant skills

Use repo-local skills when applicable:

- Browser validation: `.agents/skills/pc-client-browser-check/SKILL.md`
- Bugs, regressions, failing tests: `.agents/skills/pc-client-systematic-debug/SKILL.md`
- Code review: `.agents/skills/pc-client-code-review/SKILL.md`
- Docs/CODEMAP drift: `.agents/skills/pc-client-docs-drift/SKILL.md`
- Release/deploy validation: `.agents/skills/pc-client-release-gate/SKILL.md`

## Webapp implementation rules

- Browser-visible changes require real browser validation when project tooling supports it.
- Do not claim UI behavior is fixed based only on code inspection.
- Use the project frontend bootstrap script when required:
  - `python scripts/bootstrap_web_toolchain.py`
- Reuse existing routing, state, data-fetch, component, and styling patterns.
- Do not introduce a parallel UI architecture unless explicitly requested.
- Check console and network errors for UI behavior changes.
- Preserve Russian text rendering; mojibake is a defect.
- If routes, screens, forms, user flows, build behavior, or browser-visible behavior change, update relevant docs.

## UI Page Composition Contract

Любая новая или изменяемая webapp-страница должна проектироваться от роли и сценария, а не от backend endpoint/table/API.

### 1. Перед кодом обязательно определить

- Actor: requester / support / admin / auditor.
- Primary job: одно главное действие, ради которого открывают страницу.
- Secondary jobs: максимум 2-3 вспомогательных действия.
- Dangerous/rare jobs: destructive, raw, migration, debug, bulk, policy override.
- Page archetype:
  - Dashboard: обзор состояния + drilldown.
  - List + Detail: реестр слева/сверху, детали выбранного объекта справа/ниже.
  - Workbench/Studio: explorer + main editor/canvas + inspector.
  - Wizard: пошаговый процесс с preview/confirm/result.
  - Settings: сгруппированные настройки с explain/test/save.
  - Ops Console: очередь/события/логи/ручные операции.

Нельзя начинать верстку, пока archetype не выбран.

### 2. Запрещённый паттерн

Нельзя добавлять новую возможность как очередную Card в конец страницы.

Запрещено:

- одна страница = все CRUD + все настройки + все диагностики + все графики;
- production UI с raw JSON textarea, если это не явно developer/debug console;
- формы с raw id/stable_key/secret_ref как основной способ работы;
- больше трёх крупных видимых зон на экране;
- две независимые вертикальные прокрутки без явного workbench-смысла;
- горизонтальный body-scroll;
- primary action ниже первого экрана;
- смешивать requester/support/admin mental model на одной странице.

Если хочется "просто добавить карточку", сначала выбрать:

- существующая секция;
- новая вкладка внутри страницы;
- drawer/modal;
- отдельная route;
- advanced/debug block.

### 3. Layout rules

Каждая страница должна иметь:

- PageHeading: что это за раздел и для кого.
- Primary action bar: основные действия видны без прокрутки.
- Стабильную структуру:
  - Dashboard: summary -> alerts -> prioritized queue -> drilldown.
  - Workbench: left explorer -> main workspace -> right inspector.
  - Wizard: stepper -> current step -> preview/validation -> result.
  - Settings: grouped sections -> test/preview -> save state.
- Empty/loading/error states для каждого основного блока.
- Sticky inspector/action bar там, где пользователь редактирует или публикует.
- Responsive baseline: 1366x768, 1440x900, 1920x1080.
- Mobile/tablet fallback без потери основного сценария.

### 4. Role-specific UI

Requester:

- минимум технических терминов;
- один понятный next action;
- self-service, поиск, создание обращения, подтверждения;
- не показывать internal ids, ACL, policy/raw/debug.

Support:

- task-first;
- "что сделать дальше" важнее, чем полный CRUD;
- быстрый контекст, история, KB-подсказки, операции агента;
- технические детали доступны, но не мешают первому действию.

Admin:

- технический, но управляемый интерфейс;
- настройки группируются по смыслу;
- опасные действия отделены в Danger zone;
- raw/debug только в advanced mode;
- обязательны preview/dry-run/confirm для массовых действий.

### 5. Form rules

- Не использовать raw JSON editor для обычного admin workflow.
- Для сложных структур делать нормальные поля, таблицы, pickers, toggles, chips.
- Raw JSON/YAML разрешён только в collapsible "Advanced / Developer import" с validation, preview и copy/export.
- ID/stable_key/service_code/offering_code выбирать через searchable picker, а не вводить вручную, если данные есть в API.
- Labels должны быть на русском, технический код можно показывать вторым уровнем: badge, helper text, copy button.
- Каждый save должен иметь clear success/error state.

### 6. Component rules

Page component = orchestration only.

Ориентиры:

- page file <= 200-250 строк;
- крупный feature component <= 300-350 строк;
- всё большее дробить на:
  - `*-page.tsx`
  - `*-layout.tsx`
  - `*-toolbar.tsx`
  - `*-explorer.tsx`
  - `*-inspector.tsx`
  - `*-form.tsx`
  - `*-preview.tsx`
  - `hooks/use-*.ts`
- Data fetching/mutations не смешивать с большим JSX, если компонент уже стал нечитаемым.
- Повторяемые layout primitives вынести в `webapp/src/components/ui-page/`.

### 7. Testing / evidence gate

Каждый UI refactor обязан дать:

- unit/component tests для основного сценария;
- browser screenshots для 1366x768 и 1920x1080;
- проверку отсутствия horizontal scroll;
- проверку, что primary action виден без прокрутки;
- проверку empty/loading/error states;
- краткую запись в PLANS.md: что изменено, какие сценарии проверены, что осталось.

## Verification

Before claiming completion for webapp work:

- Run workspace sanity when available:
  - `python scripts/verify_workspace.py`
- Run targeted frontend checks when available.
- Use `.agents/skills/pc-client-browser-check/SKILL.md` for browser-visible changes.
- Validate the relevant route/page/user flow in a real browser or project browser MCP workflow when available.
- Check console/network status when relevant.

## Docs drift

Use `.agents/skills/pc-client-docs-drift/SKILL.md` when webapp work changes:

- routes/pages
- components with documented behavior
- forms/tables/navigation
- admin workflows
- build/toolchain behavior
- frontend test/check commands

## Final response requirements

For webapp tasks, include:

- frontend files changed
- route/page/user flow impact
- browser evidence
- console/network status when checked
- frontend checks run
- docs updates or why not needed
- residual UI risks
