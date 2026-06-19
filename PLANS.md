# Requester Cabinet Full UI Refactoring Plan

> **Active plan.** Implement phase by phase. Follow root `AGENTS.md`, `webapp/AGENTS.md` and the repository browser/testing skills. Do not edit the same files from multiple agents concurrently. After every completed phase, update the progress log in this file with commits, checks and browser evidence.

**Status:** ready for implementation, 2026-06-19.

**Goal:** replace the monolithic requester workspace with a route-based, Russian-first user cabinet built on shared UI components and Tailwind v4. Preserve existing web-first identity, Registry profile, device, ticket, Knowledge, Customer History, consent and Observer contracts.

**Baseline:** default branch `codex/helpdesk-process-model`; analyzed from the current requester implementation and live screenshots.

This file replaces the previous active `PLANS.md`. Completed backend architecture and historical evidence remain in git history and existing contracts.

---

## 1. Product outcome

The cabinet must answer three questions immediately:

1. What do I need to do now?
2. How do I get help?
3. What is happening with my requests?

Required result:

- one clear primary action per page;
- dashboard, request creation, request list, request chat, profile and devices are separate routes;
- requester pages use shared UI/page/form components and Tailwind theme tokens;
- no requester dependence on `workspace-page__*` or `support-workspace__*` layout classes;
- request fields render dynamically from the request-form constructor;
- profile fields render dynamically from the profile-schema constructor;
- constructor preview and requester runtime share the same field controls and value codecs;
- Russian labels, statuses, validation and action-oriented errors;
- no raw IDs, backend enums or technical Registry/device-link/session terms;
- correct behavior for incomplete profile, missing or pending device, multiple devices, on-behalf requests, offline agents, pending consents and archived users;
- stable extension point for AI answers, Customer History and agent tools.

The cabinet is a personal task-oriented workspace, not an admin console and not a list of backend objects.

---

## 2. Current problems to remove

- `webapp/src/pages/requester/index.tsx` is a roughly 3,200-line component.
- `/app/requester`, `/profile`, `/profile/setup`, `/devices` and wildcard sections render the same component.
- Profile setup, device linking, request creation, request list, chat, consent and feedback compete on one long page.
- Requester layout uses legacy class names without a coherent requester page system.
- Many buttons, inputs, alerts and cards duplicate raw Tailwind markup.
- Runtime strings can expose `Requester`, `user`, `verified`, `profile not linked`, raw status values or identifiers.
- Request-form field types published by the constructor do not all share a complete runtime implementation.
- Profile constructor preview and requester profile runtime can drift.
- One `load()` flow fetches unrelated page data together.

The refactor must change composition and architecture, not only colors and spacing.

---

## 3. Scope

### In scope

- explicit requester routes and page decomposition;
- shared page, action, state and form components;
- Tailwind-only requester layout;
- Russian-first shell and navigation;
- dynamic request-form runtime and constructor parity;
- dynamic profile runtime and constructor parity;
- guided request creation with Knowledge/AI suggestions and preview;
- separate request list and request chat;
- separate profile and devices pages;
- device-link wizard;
- consent, closure, rating and reopen presentation;
- focused TanStack Query hooks;
- minimal typed API projection changes required for safe UI;
- Observer, audit and Customer History preservation;
- unit, server, E2E and live browser checks;
- responsive and accessibility hardening;
- deletion of the old monolithic page after migration.

### Narrow constructor scope

The form and profile constructors are changed only as needed to:

- share the runtime field registry and preview controls;
- prevent unsupported or invalid fields from being published;
- configure labels, help text, options, conditions, order and safe presentation metadata;
- prove builder-to-requester behavior through tests.

### Out of scope

- full support/admin redesign;
- generic CMDB/schema builder;
- requester self-rebinding or ownership transfer;
- frontend-owned routing, SLA, priority or diagnostic policy;
- full AD/SSO;
- new production LLM provider or autonomous write-capable AI;
- broad rollout before final evidence.

---

## 4. Locked invariants

### Account, profile and device

- **Аккаунт** is login/password/web access.
- **Профиль** is Registry-backed person and work context.
- **Устройство** is a computer with an agent.
- **Привязка устройства** is the relationship between profile and device.
- Device linking remains independent from profile completion.
- Profile completion may block normal request forms by policy, but not device-link confirmation.

### Web-first

- `/app/requester` remains the canonical requester workspace.
- The local GUI agent may show status/code and open the web cabinet.
- The GUI agent does not own profile lifecycle and does not silently change ownership.

### Diagnostic target

```text
Normal request:
creator == affected employee
target = creator's server-resolved primary active device

On-behalf request:
creator != affected employee
target = affected employee's server-resolved primary active device

Missing/offline/ambiguous target:
record evidence and route/manual-triage by policy
never use the browser host or arbitrary user-selected PC as fallback
```

A user may identify the device with the problem, but cannot override the diagnostic target.

### Authorization

- Frontend visibility never replaces backend authorization.
- On-behalf search appears only when the selected form permits it.
- Affected-person context does not expand the creator's Knowledge audience.
- Requester APIs expose only caller-owned profile, devices and requests.
- Archived/inactive/merged/disabled users remain blocked.
- Raw account-session, binding, claim, person, operation, trace and token data stay out of normal UI.

### Dynamic constructors

- Published form/profile schemas are sources of truth.
- Requester pages do not hardcode custom fields.
- A field type cannot be publishable without rendering, serialization, validation and tests.
- Constructor preview and requester runtime use the same implementation.

---

## 5. Russian terminology contract

Canonical requester labels:

| Concept | Label |
| --- | --- |
| Workspace | Кабинет пользователя |
| Dashboard | Главная |
| Request | Обращение |
| Request list | Мои обращения |
| Create | Создать обращение |
| Profile | Профиль |
| Device | Устройство |
| Link | Привязка устройства |
| Primary target | Основное устройство |
| Affected person | Сотрудник, у которого проблема |
| Diagnostic target | Устройство для диагностики |
| Knowledge | База знаний |
| Ask/RAG | AI-помощник |
| Pending action | Требуется ваше действие |

Use `Обращение`, not a mixture of `тикет`, `заявка` and `обращение`.

Forbidden in requester-visible DOM, errors and accessible labels:

- `Requester`, `user`, `ticket`;
- `pairing`, `binding`, `claim`, `session`, `registry person`;
- `verified`, `not verified`, `profile not linked`;
- raw UUIDs and `*_id` names;
- raw backend enums, policy keys, trace/operation/consent/artifact IDs;
- raw server exception text.

Every error must explain what happened and what the user should do next. Unknown states use safe fallbacks such as `Статус уточняется`.

---

## 6. Target routes

| Route | Archetype | Primary job |
| --- | --- | --- |
| `/app/requester` | Dashboard | See next action and current state |
| `/app/requester/new` | Wizard | Create an обращение |
| `/app/requester/tickets` | List | Find an обращение |
| `/app/requester/tickets/:ticketId` | Detail/chat | Continue one conversation |
| `/app/requester/profile` | Settings | View/edit profile |
| `/app/requester/profile/setup` | Required setup | Complete required profile fields |
| `/app/requester/devices` | Device dashboard | View devices and link state |
| `/app/requester/devices/link` | Wizard | Link a computer by code |
| `/app/kb` | Knowledge | Find instructions |
| `/app/kb/ask` | AI assistant | Ask with sources |

Compatibility:

- keep `/app/device/pair`, `/app/device/register`, `/app/device/login`;
- redirect known old requester section URLs;
- unknown requester paths render a requester-safe not-found page;
- remove generic `/app/requester/:section` after tests cover redirects.

---

## 7. Page composition

### Global

Every page has:

- shared `PageShell` and `PageHeader`;
- one primary action above the fold at 1366×768;
- no more than three major visible zones;
- loading, empty and error states for each main block;
- no horizontal body scroll;
- responsive behavior at 390×844, 768×1024, 1366×768, 1440×900, 1920×1080.

### Dashboard

Order:

1. greeting and `Создать обращение`;
2. one highest-priority next action;
3. up to three compact summaries;
4. recent requests and useful Knowledge links.

Do not embed full profile, device-link, request creation, chat or rating forms.

### Request creation

Wizard:

1. describe the problem;
2. show Knowledge/AI suggestions;
3. ask dynamic clarification fields;
4. show requester-safe review and preview;
5. create and open the request chat.

Do not expose service codes, form keys, workflow or policy names.

### Request detail

- human request number, title, status, next action;
- conversation and safe system timeline;
- sticky reply composer;
- consent/confirm/rate/reopen controls only when state permits them.

### Profile

- read mode after completion;
- edit mode after explicit action;
- required setup mode when blocked;
- sections: main data, contact, work, additional;
- organization-managed fields explain why they cannot be edited;
- no identity-provider internals.

### Devices

- name, OS, online state, last seen, agent version, primary label, open requests;
- no radio selector suggesting direct diagnostic-target control;
- separate link wizard;
- ownership change is a support/admin request, never direct self-rebinding.

---

## 8. Frontend architecture

Target pages:

```text
webapp/src/pages/requester/
  home-page.tsx
  new-request-page.tsx
  tickets-page.tsx
  ticket-detail-page.tsx
  profile-page.tsx
  profile-setup-page.tsx
  devices-page.tsx
  device-link-page.tsx
  requester-not-found-page.tsx
  index.ts
```

Target feature boundaries:

```text
webapp/src/features/requester/
  dashboard/
  request-create/
  requests/
  request-chat/
  profile/
  devices/
  consents/
  dynamic-form/
  dynamic-profile/
  hooks/
  api.ts
  query-keys.ts
  types.ts
  status-labels.ts
  error-messages.ts
  formatters.ts
```

Rules:

- page files are orchestration only, target ≤250 lines;
- feature components target ≤350 lines;
- TanStack Query owns server state;
- local state is limited to wizard values, unsaved form values and local dialogs;
- remove the all-in-one `load()` pattern;
- invalidate only affected query keys;
- do not render normal UI from generic `policies: Record<string, unknown>`;
- use typed capabilities/readiness/next actions;
- use Tailwind v4, theme tokens and `cn()`;
- no new requester BEM/page CSS selectors;
- remove old requester CSS after migration.

---

## 9. Shared UI components

Audit and extend existing `Button`, `Badge`, `Card`, `Input`, `Select`, `SearchField`, `Tabs`. Do not create parallel primitives.

Create under the accepted shared locations:

### Page/state

- `PageShell`, `PageHeader`, `PageActions`;
- `ContentSection`, `ActionCard`, `StatCard`, `StatusBadge`;
- `EmptyState`, `LoadingState`, `PageSkeleton`, `ErrorState`;
- `InlineAlert`, `StickyActionBar`, `Stepper`, `ConfirmDialog`, `Drawer`.

### Form

- `FieldShell` with label/help/error IDs;
- text, textarea, number, date and datetime controls;
- checkbox and radio group;
- select, multi-select and searchable picker;
- file upload;
- `FieldErrorSummary`, `FormActions`.

Acceptance:

- requester pages do not duplicate full button/input/alert class strings;
- raw form elements live inside shared field components, not pages;
- keyboard access, visible focus and Russian accessible names are tested;
- errors are not represented by color alone;
- pointer targets are at least 44px for primary actions.

---

## 10. Dynamic request-form contract

Canonical value model:

```ts
type DynamicFieldValue = string | number | boolean | string[] | null;
type DynamicFormValues = Record<string, DynamicFieldValue>;
```

Each field type defines default value, control, normalization, validation, serialization and review display.

Required field types:

- `text`, `textarea`, `email`, `phone`, `url`;
- `number`, `date`, `datetime`;
- `checkbox`, `radio`, `select`, `multi_select`;
- `user_picker`, `department_picker`, `location_picker`, `device_picker`, `service_picker`;
- `file`.

A type must never silently degrade to text.

### Conditions

Support `visible_when.field`, `equals` and `in`/normalized constructor values.

- required validation applies only to visible fields;
- hidden values are excluded from preview/create payloads;
- invalid references are rejected by constructor validation;
- condition changes do not erase unrelated manual edits.

### Prefill

- profile/device/service context prefills untouched fields;
- manual edits always win over later refresh;
- technical IDs stay internal;
- option loading/error/empty states are field-local.

### Validation

- required visible fields;
- type format and configured limits;
- allowed option membership;
- on-behalf employee/reason;
- setup/emergency contact requirement;
- first invalid field receives focus;
- server errors map to Russian field labels.

### Constructor parity

One field registry is used by:

- constructor palette;
- constructor preview;
- requester runtime;
- review display;
- tests.

Publication fails for unsupported types, invalid/duplicate keys, empty labels, invalid options/conditions or incompatible validation.

### File field

Audit the current pre-create upload contract. If absent, add requester-scoped draft uploads with TTL, size/type limits and caller-owned references. Until that is green, the constructor must reject requester-visible `file` publication.

### Version changes

Keep form pack/version in preview and create. If schema changes while editing, preserve compatible values but require the user to review the refreshed form.

---

## 11. Dynamic profile contract

Supported profile types:

- `text`, `textarea`, `select`, `phone`, `email`, `url`, `number`, `date`, `checkbox`.

Required completion:

- full name;
- department;
- location;
- **phone or internal extension**.

The frontend must not require `phone` when `internal_extension` satisfies the server contract.

Safe presentation metadata may include:

- `section`, `order`, `width`;
- `editable`, requester-safe managed/source label;
- `help_text`, `options`, `validation`.

Do not expose storage targets or audit internals.

Behavior:

- completed profile opens read-only;
- edit/setup uses the shared profile renderer;
- save/cancel remains visible on long forms;
- required setup preserves safe `next` path;
- managed fields show `Значение управляется организацией`;
- create/switch account CTA appears only for explicit account mismatch/required state;
- submit only visible/editable values;
- hidden/managed custom values are not erased by unrelated saves.

Profile constructor preview uses the same runtime controls. Publish rejects unsupported fields, invalid options, duplicate keys, protected-field changes, required hidden fields and technical wording.

---

## 12. Typed API projection

Add typed DTO fields only where the UI would otherwise duplicate policy logic.

Dashboard projection should provide:

- compact profile summary;
- server-resolved primary device summary;
- open/waiting/consent counts;
- readiness for profile/device/request creation;
- ordered requester-safe next actions;
- recent request summaries.

Capabilities should cover:

- create normal/setup-help request;
- edit profile;
- link device;
- use AI;
- on-behalf availability for selected form;
- close/rate/reopen request;
- approve/deny consent.

Requirements:

- server still enforces every action;
- human request code is available;
- no raw policy JSON drives normal rendering;
- dashboard does not fetch form pack/messages;
- profile does not fetch tickets/forms;
- devices do not fetch full request messages;
- request detail fetches only selected request and actions.

---

## 13. Implementation phases

## Phase A — Baseline and regression fixture

- [ ] Run workspace/toolchain preflight and build a focused context pack.
- [ ] Record route/API/component map and known baseline defects.
- [ ] Create deterministic fixture states: complete/incomplete profile, no/pending/multiple/offline devices, waiting requests, consent, close/rate/reopen, on-behalf allowed/forbidden, archived user.
- [ ] Add authorization and business-invariant tests independent from old layout.
- [ ] Add supported field-type matrices and forbidden-term list.
- [ ] Capture baseline screenshots at 1366×768 and 1920×1080.

Checks:

```powershell
python scripts/verify_workspace.py
python scripts/bootstrap_web_toolchain.py
pnpm --dir webapp run test
pnpm --dir webapp run build
```

Exit: baseline is reproducible; pre-existing failures are documented.

## Phase B — Shared UI/Tailwind foundation

- [ ] Audit existing primitives and implement Section 9 components.
- [ ] Add semantic loading/disabled/status behavior.
- [ ] Add shared Russian date/status/identifier formatters.
- [ ] Add component accessibility and responsive tests.
- [ ] Do not introduce requester page CSS classes.

Checks:

```powershell
pnpm --dir webapp exec vitest run src/components/ui src/components/ui-page
pnpm --dir webapp run build
```

Exit: new pages can be built without raw repeated controls.

## Phase C — Routes, shell and navigation

- [ ] Add explicit routes/lazy exports and safe not-found page.
- [ ] Add Russian navigation: Главная, Мои обращения, База знаний, AI-помощник, Профиль, Устройства.
- [ ] Keep Создать обращение as primary CTA.
- [ ] Hide workspace selector for a single workspace.
- [ ] Map `user` to `Пользователь`; remove `Requester workspace`.
- [ ] Add mobile navigation.
- [ ] Remove wildcard after compatibility redirect tests.

Exit: route purpose and visible page purpose match.

## Phase D — Query architecture and typed projections

- [ ] Create requester query keys/hooks by domain.
- [ ] Convert server state to TanStack Query.
- [ ] Add typed dashboard/readiness/next-action projection if needed.
- [ ] Add human request code/safe labels where missing.
- [ ] Preserve archived-user fail-closed behavior.
- [ ] Remove dependency on monolithic `load()` for migrated routes.

Checks:

```powershell
python -m pytest server/tests/test_requester_workspace_api.py server/tests/test_user_consent_api.py -vv --durations=80
pnpm --dir webapp exec vitest run src/features/requester
```

## Phase E — Dashboard

- [ ] Build greeting/header and create CTA.
- [ ] Render one primary next action and at most two secondary actions.
- [ ] Render compact counts, primary device and recent requests.
- [ ] Add new-user, incomplete-profile, missing-device, pending-consent and waiting-reply states.
- [ ] Keep full forms/chat/device link off the dashboard.

Exit: next action is understandable in the first viewport.

## Phase F — Dynamic request forms and constructor parity

- [ ] Implement shared field registry/value codecs for every type.
- [ ] Implement conditions, prefill, options, validation and review display.
- [ ] Exclude hidden values; preserve manual edits.
- [ ] Implement/gate draft file upload.
- [ ] Reuse runtime renderer in constructor preview.
- [ ] Reject unsupported/invalid publication.
- [ ] Handle schema version changes.

Required tests:

- every field type renders and serializes correctly;
- radio is a radio group, multi-select is an array;
- Registry/device/service labels hide technical values;
- user picker appears only by on-behalf policy;
- hidden required fields do not block and are omitted;
- invalid conditions/unsupported types fail publication;
- manual edits survive context refresh;
- constructor-published form renders without frontend code change.

Checks:

```powershell
pnpm --dir webapp exec vitest run src/features/requester/dynamic-form src/features/forms-builder
python -m pytest server/tests/test_requester_workspace_api.py server/tests/test_service_catalog_preview.py server/tests/test_ticket_create_contracts.py -vv --durations=80
```

## Phase G — Request creation wizard

- [ ] Implement problem, quick help, details, review and result steps.
- [ ] Start from user text, not service/form codes.
- [ ] Preserve Knowledge attempts and sanitized Ask context.
- [ ] Render dynamic form from Phase F.
- [ ] Render on-behalf fields only when allowed.
- [ ] Show server-resolved diagnostic target and warnings without override.
- [ ] Respect incomplete-profile/no-device setup-help policies.
- [ ] Block create on preview blockers and prevent double submit.
- [ ] Navigate to the new request chat after success.

Exit: normal request creation exposes no technical catalog/policy terms.

## Phase H — Request list/detail/chat

- [ ] Build open/action/closed/all filters and search.
- [ ] Use human request number, title, status, last update and next action.
- [ ] Build dedicated detail/chat route and sticky composer.
- [ ] Localize all timestamps with `ru-RU`.
- [ ] Preserve reply text on transient failure.
- [ ] Implement attachments and safe timeline.
- [ ] Show consent/confirm/rate/reopen only when allowed.
- [ ] Refresh dashboard/list/detail after mutations.

Exit: the complete support conversation works on the detail page.

## Phase I — Dynamic profile and constructor parity

- [ ] Implement profile field registry/runtime.
- [ ] Add `internal_extension` and phone-or-extension completion.
- [ ] Build read/edit/setup modes and sections.
- [ ] Render custom and managed fields safely.
- [ ] Add unsaved-change protection.
- [ ] Remove provider/verified/Registry status details.
- [ ] Reuse runtime in constructor preview and validate publication.
- [ ] Prove admin-published custom field appears without code change.

Checks:

```powershell
pnpm --dir webapp exec vitest run src/features/requester/profile src/features/admin/registry
python -m pytest server/tests/test_requester_workspace_api.py server/tests/test_registry_web_api.py server/tests/test_registration_api.py -vv --durations=80
```

## Phase J — Devices and link wizard

- [ ] Build device cards and primary-device explanation.
- [ ] Localize online/last-seen/agent version/status.
- [ ] Remove diagnostic radio selection.
- [ ] Build code → preview → confirm → result wizard.
- [ ] Keep direct-link compatibility without displaying `pairing_id`.
- [ ] Keep link available before profile completion.
- [ ] Cover auto approval and manual admin review.
- [ ] Provide safe ownership-change request path.

Exit: no binding/claim/session wording is visible.

## Phase K — Consents and remote actions

- [ ] Build shared consent card for dashboard/detail.
- [ ] Explain action, access scope, reason, request, requester and expiry.
- [ ] Distinguish diagnostics, screen view, remote control and admin access.
- [ ] Provide explicit allow/deny and prevent duplicate decisions.
- [ ] Remove all technical IDs from visible and accessible text.
- [ ] Preserve existing consent authorization/audit.

## Phase L — Localization, accessibility and responsive hardening

- [ ] Centralize requester labels/errors/formatters.
- [ ] Expand localization guard and DOM forbidden-term tests.
- [ ] Preserve UTF-8 and reject mojibake.
- [ ] Add landmarks, heading hierarchy, fieldset/legend, first-error focus and `aria-live`.
- [ ] Verify keyboard-only profile, device link, dynamic form and chat flows.
- [ ] Verify all target viewport sizes and no horizontal scroll.

## Phase M — Knowledge, AI, Customer History and Observer

- [ ] Preserve server-side Knowledge audience filtering.
- [ ] Preserve Knowledge attempts and Ask-to-request transfer.
- [ ] Keep denied titles/internal reasons out of UI.
- [ ] Preserve Customer History redaction and creator/affected separation.
- [ ] Preserve required redacted Observer events on new routes.
- [ ] Do not log message text or sensitive form values into Observer.
- [ ] Add integrity checks for form/profile schema version and diagnostic target.

This phase prepares the sequence: user question → Knowledge/AI → optional read-only diagnostics → explicit consent → escalation with context. It does not authorize autonomous write-capable AI.

## Phase N — Cleanup and final gate

- [ ] Delete the old monolithic requester implementation.
- [ ] Remove dead state/helpers/API calls and legacy requester CSS/classes.
- [ ] Confirm page/component size targets.
- [ ] Confirm a single request/profile renderer remains.
- [ ] Update web-first contract, Quick Lookup, CODEMAP and testing docs.
- [ ] Run focused frontend/server/E2E/live browser gates.

Frontend gate:

```powershell
python scripts/verify_workspace.py
python scripts/bootstrap_web_toolchain.py
pnpm --dir webapp run test
pnpm --dir webapp run build
pnpm --dir webapp run test:e2e -- requester-workspace.spec.ts
python scripts/test_web_first_registration_localization.py
```

Focused server gate:

```powershell
python -m pytest server/tests/test_requester_workspace_api.py server/tests/test_registration_api.py server/tests/test_registry_web_api.py server/tests/test_service_catalog_preview.py server/tests/test_ticket_create_contracts.py server/tests/test_user_consent_api.py server/tests/test_observer_web_cabinet.py server/tests/test_knowledge_ask.py server/tests/test_knowledge_access_service.py -vv --durations=80
```

---

## 14. Required E2E matrix

Create deterministic `webapp/tests/requester-workspace.spec.ts` coverage:

| ID | Scenario |
| --- | --- |
| E2E-01 | New account, incomplete profile, no device |
| E2E-02 | Link device before profile completion |
| E2E-03 | Complete dynamic profile and update readiness |
| E2E-04 | Admin adds custom profile field; requester sees it |
| E2E-05 | Admin publishes dynamic request form; requester sees it |
| E2E-06 | All supported field types render/validate/create |
| E2E-07 | Conditional required field is omitted when hidden |
| E2E-08 | Knowledge resolves issue without request |
| E2E-09 | Knowledge fails; sanitized context transfers to request |
| E2E-10 | Normal request uses primary online device |
| E2E-11 | Offline/missing device routes to warning/manual triage |
| E2E-12 | On-behalf allowed uses affected employee context |
| E2E-13 | On-behalf forbidden has no control and rejects forged payload |
| E2E-14 | Chat reply and attachment |
| E2E-15 | Consent approve/deny |
| E2E-16 | Confirm solution, rate and reopen |
| E2E-17 | Multiple devices show primary without arbitrary selector |
| E2E-18 | Manual device approval status |
| E2E-19 | Archived user denied safely |
| E2E-20 | Responsive and keyboard-only main flows |

---

## 15. Live browser evidence

Canonical origin:

```text
https://192.168.100.17:9443
```

Required routes:

- `/app/requester`;
- `/app/requester/new`;
- `/app/requester/tickets`;
- one request detail/chat;
- `/app/requester/profile/setup` and `/profile`;
- `/app/requester/devices` and link flow;
- `/app/kb` and `/app/kb/ask`.

For key routes capture 1366×768 and 1920×1080 screenshots; capture narrow viewport for forms/chat. Record:

- no horizontal scroll;
- primary action above fold;
- console status;
- failed network requests;
- forbidden terminology DOM check.

Evidence path:

```text
artifacts/browser_live_validation/requester-ui-refactor-<YYYYMMDD>/
```

---

## 16. Main file map

Frontend shell/routes:

- `webapp/src/app/router.tsx`
- `webapp/src/app/routes/lazy-pages.tsx`
- `webapp/src/app/navigation.tsx`
- `webapp/src/app/layouts/app-shell.tsx`
- `webapp/src/components/shell/*`
- `webapp/src/styles.css`

Shared UI:

- `webapp/src/components/ui/*`
- `webapp/src/components/ui-page/*`
- shared form component location selected during Phase B

Requester:

- replace/split `webapp/src/pages/requester/index.tsx`
- new requester page files from Section 8
- `webapp/src/features/requester/api.ts`
- `webapp/src/features/requester/types.ts`
- new requester hooks, queries, dynamic form/profile and page features

Constructors:

- `webapp/src/features/forms-builder/forms-builder-panel.tsx`
- `webapp/src/features/forms-builder/forms-builder-panel.test.tsx`
- `webapp/src/features/admin/registry/registry-profile-schema-tab.tsx`
- focused profile-schema tests

Server only where required:

- `server/web_api/requester_handlers.py`
- `server/requester/identity_service.py`
- `server/tickets/form_catalog.py`
- request preview/create validation
- profile-schema safe projection
- Observer web-cabinet checks
- draft attachment service/route if absent

Tests/docs:

- split `webapp/src/pages/requester/index.test.tsx`
- `webapp/tests/requester-workspace.spec.ts`
- `webapp/tests/fixtures/*`
- focused requester/registration/registry/catalog/ticket/consent/Observer/Knowledge tests
- `scripts/test_web_first_registration_localization.py`
- `docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md`
- `docs/QUICK_LOOKUP.md`
- `docs/TESTING_RULES.md` when commands change
- `server/docs/CODEMAP.md`
- relevant ticket/Knowledge/Observer docs

---

## 17. Definition of done

Architecture:

- [ ] explicit requester routes;
- [ ] old monolith deleted;
- [ ] focused query hooks;
- [ ] shared UI/page/form components;
- [ ] Tailwind theme layout;
- [ ] no legacy requester layout classes.

UX:

- [ ] one clear next action on dashboard;
- [ ] primary action above fold;
- [ ] profile, device link, request creation and chat are separate;
- [ ] loading/empty/error states exist;
- [ ] no horizontal scroll;
- [ ] mobile/tablet preserve the main job.

Dynamic forms/profile:

- [ ] every constructor-supported type works;
- [ ] conditions, options, prefill, validation and hidden-field omission work;
- [ ] constructor preview and requester runtime share implementation;
- [ ] unsupported fields cannot publish;
- [ ] builder-to-requester E2E is green;
- [ ] phone-or-extension completion works;
- [ ] hidden/managed profile values are not erased.

Language/safety:

- [ ] Russian-first UI;
- [ ] no forbidden technical terms/raw IDs;
- [ ] safe unknown-state fallbacks;
- [ ] backend authorization preserved;
- [ ] diagnostic target remains server-resolved;
- [ ] Knowledge audience remains creator-scoped;
- [ ] consent scope is explicit.

Verification:

- [ ] focused frontend/server tests green;
- [ ] build green;
- [ ] fixture E2E green;
- [ ] live browser evidence complete;
- [ ] console/network clean;
- [ ] docs/code maps current.

---

## 18. Compatibility and commit strategy

- Preserve existing endpoints during route migration unless a typed replacement is required.
- Keep `/app/device/*` compatibility and safe `next` paths.
- Do not maintain two permanent requester UIs.
- Migrate route by route, then delete legacy code.
- Roll back by reverting phase commits/deploying the previous committed build through project scripts.
- Never manually patch the deployed stand.

Recommended commit boundaries:

1. shared requester page primitives;
2. requester routes and Russian shell;
3. typed dashboard projection and dashboard;
4. dynamic request runtime and constructor parity;
5. request creation wizard;
6. request list and chat;
7. dynamic profile runtime and constructor parity;
8. devices and link wizard;
9. localization/accessibility hardening;
10. E2E/live gate and docs.

Do not combine the whole refactor into one commit.

---

## 19. Progress log

### Current checkpoint — plan replacement, 2026-06-19

- [x] Current requester screenshots, routes, monolithic component, dynamic request constructor, profile constructor, localization contract and recent changes analyzed.
- [x] Previous `PLANS.md` replaced by this full requester UI refactoring plan.
- [ ] Phase A started.

Phase completion record:

```text
Phase:
Commit(s):
Files changed:
Automated checks:
Browser routes checked:
Evidence path:
Console/network result:
Residual risks:
Next phase:
```
