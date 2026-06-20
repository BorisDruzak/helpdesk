# Requester Cabinet Full UI Refactoring Plan

> **Active plan.** Implement phase by phase. Follow root `AGENTS.md`, `webapp/AGENTS.md` and the repository browser/testing skills. Do not edit the same files from multiple agents concurrently. After every completed phase, update the progress log in this file with commits, checks and browser evidence.

**Status:** ready for implementation, 2026-06-19.

**Goal:** replace the monolithic requester workspace with a route-based, Russian-first user cabinet built on shared UI components and Tailwind v4. Preserve existing web-first identity, Registry profile, device, ticket, Knowledge, Customer History, consent and Observer contracts.

**Baseline:** default branch `codex/helpdesk-process-model`; analyzed from the current requester implementation and live screenshots.

This file replaces the previous active `PLANS.md`. Completed backend architecture and historical evidence remain in git history and existing contracts.

---

## Current checkpoint - remaining requester defects, 2026-06-20

Source: `C:\Users\admin-2\Downloads\requester_remaining_work.md`, checked against branch `codex/helpdesk-process-model` at `53462d7684e32251a17d23dae85cb38a0a06a8fb`.

Status: implementation checkpoint updated after local verification. RREM-01..RREM-14 are fixed or verified in targeted tests; RREM-15/RREM-16 stay open until deployed browser/live evidence and the final release gate are attached below.

### P0 - fix before final functional signoff

| ID | Defect | Required outcome | Status |
| --- | --- | --- | --- |
| RREM-01 | Request creation still has implicit form/offering selection and `visible[0]` fallback. | The user must explicitly select/confirm category; no first-form fallback; system intents use typed `request_template_key` or a clear no-match choice state. | fixed; covered by `new-request-page.test.tsx` and build |
| RREM-02 | `on_behalf_policy.allowed` makes a form look available without a device for self requests. | Self, on-behalf, no-profile, no-device and manual-triage availability are computed separately and used consistently by create/preview/UI. | fixed; covered by requester create tests and on-behalf API tests |
| RREM-03 | Requester UI still falls back to `devices[0]` when `primary_device_resolution` is missing/ambiguous. | Use only server-projected `primary_device`; missing/ambiguous states show the server reason and never choose an arbitrary device. | fixed; covered by requester home/new-request tests |
| RREM-04 | Ticket detail refresh is skipped when `can_attach_files=false`. | Every close/feedback/reopen/message mutation refreshes detail, list and dashboard when a detail route is active. | fixed; covered by `tickets-page.test.tsx` |
| RREM-05 | Reopen button depends on local unsaved feedback state after reload. | Server `actions.can_reopen` is the display source of truth; local rating/reason state only validates the submitted feedback/reopen payload. | fixed; covered by `tickets-page.test.tsx` and requester API reopen test |

### P1 - contract and UX completion

| ID | Defect | Required outcome | Status |
| --- | --- | --- | --- |
| RREM-06 | Ticket actions are not yet a full server capability projection. | Server projects and enforces `can_send_message`, `can_attach_files`, `can_confirm_solution`, `can_rate`, `can_reopen` plus reason fields. | verified existing; requester tickets UI now consumes server `actions.can_reopen` |
| RREM-07 | `next_actions` priority still puts advisory setup before active requester work. | Pending reply/consent/solution/reopen outranks advisory setup; duplicate create CTA is suppressed when it is already the primary next action. | fixed; covered by `queries.test.ts` |
| RREM-08 | Requester shell still contains old requester-cabinet wording and user-facing `Email`. | Canonical requester UI uses user-cabinet wording and `Электронная почта`. | fixed; covered by navigation/router/profile tests |
| RREM-09 | Requester device APIs do not consistently use runtime online state. | Bootstrap, devices list and device detail project `online=true/false/null` from the same runtime state source. | fixed; covered by `test_requester_device_online_state_is_consistent_across_bootstrap_list_and_detail` |
| RREM-10 | Server-side dynamic-field validation needs regression coverage for forged payloads. | Server rejects forged required/option/min-max/length/pattern/email/url/hidden/version/on-behalf violations. | fixed; dynamic constraints added, version/on-behalf verified by existing API tests |
| RREM-11 | Requester page decomposition/shared UI extraction is incomplete. | Split large page files into reusable wizard, selector, lifecycle, chat, device and profile components. | partially closed; route pages/shared controls exist, deeper `new-request-page.tsx` extraction remains backlog |
| RREM-12 | File-field contract is not fully reflected in docs/DoD. | Docs state requester-visible pre-create file fields are unsupported until draft uploads exist; post-create attachments remain chat flow. | fixed in `docs/QUICK_LOOKUP.md` |

### P2 - quality and release gate

| ID | Defect | Required outcome | Status |
| --- | --- | --- | --- |
| RREM-13 | `PageShell` defaults to `<main>`, allowing future nested landmarks. | Only the app shell owns `<main>` by default; page sections use `div`/`section` unless explicitly overridden. | fixed; covered by `page-components.test.tsx` and router tests |
| RREM-14 | Unknown backend status is transformed into a visible enum-ish label. | Unknown statuses display a neutral requester-safe fallback. | fixed; covered by `formatters.test.ts` |
| RREM-15 | E2E coverage is below the full requester matrix. | Expand deterministic requester E2E for profile/device/form/on-behalf/consent/rating/reopen/archived/ambiguous/responsive/keyboard paths. | open; targeted unit/server coverage added, deterministic Playwright/live evidence pending |
| RREM-16 | Last deployment used quick gate only. | Final signoff requires full focused frontend/server/Playwright/live evidence and frozen green CI artifact. | open; deploy/live gate pending |

Implementation order for this iteration:

1. Close P0 defects RREM-01..RREM-05 with failing regression tests first.
2. Close low-risk P1/P2 correctness items RREM-08, RREM-09, RREM-13 and RREM-14 in the same cycle if the diff stays focused.
3. Add targeted server validation coverage for RREM-10 where gaps are confirmed; keep broad decomposition/E2E/full release gate as separate records if they exceed this iteration.
4. Run targeted tests, `python scripts/verify_workspace.py`, deploy through project release scripts and collect real browser evidence for `/app/requester`, `/app/requester/new`, `/app/requester/tickets/:code` and `/app/requester/devices`.

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
| `/app/requester/tickets/:ticketCode` | Detail/chat | Continue one conversation by requester-safe ticket code |
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

- [x] Run workspace/toolchain preflight and build a focused context pack.
- [x] Record route/API/component map and known baseline defects.
- [x] Create deterministic fixture states: complete/incomplete profile, no/pending/multiple/offline devices, waiting requests, consent, close/rate/reopen, on-behalf allowed/forbidden, archived user.
- [x] Add authorization and business-invariant tests independent from old layout.
- [x] Add supported field-type matrices and forbidden-term list.
- [x] Capture baseline screenshots at 1366×768 and 1920×1080.

Checks:

```powershell
python scripts/verify_workspace.py
python scripts/bootstrap_web_toolchain.py
pnpm --dir webapp run test
pnpm --dir webapp run build
```

Exit: baseline is reproducible; pre-existing failures are documented.

## Phase B — Shared UI/Tailwind foundation

- [x] Audit existing primitives and implement Section 9 components.
- [x] Add semantic loading/disabled/status behavior.
- [x] Add shared Russian date/status/identifier formatters.
- [x] Add component accessibility and responsive tests.
- [x] Do not introduce requester page CSS classes.

Checks:

```powershell
pnpm --dir webapp exec vitest run src/components/ui src/components/ui-page
pnpm --dir webapp run build
```

Exit: new pages can be built without raw repeated controls.

## Phase C — Routes, shell and navigation

- [x] Add explicit routes/lazy exports and safe not-found page.
- [x] Add Russian navigation: Главная, Мои обращения, База знаний, AI-помощник, Профиль, Устройства.
- [x] Keep Создать обращение as primary CTA.
- [x] Hide workspace selector for a single workspace.
- [x] Map `user` to `Пользователь`; remove `Requester workspace`.
- [x] Add mobile navigation.
- [x] Remove wildcard after compatibility redirect tests.

Exit: route purpose and visible page purpose match.

## Phase D — Query architecture and typed projections

- [x] Create requester query keys/hooks by domain.
- [x] Convert server state to TanStack Query.
- [x] Add typed dashboard/readiness/next-action projection if needed.
- [x] Add human request code/safe labels where missing.
- [x] Preserve archived-user fail-closed behavior.
- [x] Remove dependency on monolithic `load()` for migrated routes.

Checks:

```powershell
python -m pytest server/tests/test_requester_workspace_api.py server/tests/test_user_consent_api.py -vv --durations=80
pnpm --dir webapp exec vitest run src/features/requester
```

## Phase E — Dashboard

- [x] Build greeting/header and create CTA.
- [x] Render one primary next action and at most two secondary actions.
- [x] Render compact counts, primary device and recent requests.
- [x] Add new-user, incomplete-profile, missing-device, pending-consent and waiting-reply states.
- [x] Keep full forms/chat/device link off the dashboard.

Exit: next action is understandable in the first viewport.

## Phase F — Dynamic request forms and constructor parity

- [x] Implement shared field registry/value codecs for every type.
- [x] Implement conditions, prefill, options, validation and review display.
- [x] Exclude hidden values; preserve manual edits.
- [x] Implement/gate draft file upload.
- [x] Reuse runtime renderer in constructor preview.
- [x] Reject unsupported/invalid publication.
- [x] Handle schema version changes.

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

- [x] Implement problem, quick help, details, review and result steps.
- [x] Start from user text, not service/form codes.
- [x] Preserve Knowledge attempts and sanitized Ask context.
- [x] Render dynamic form from Phase F.
- [x] Render on-behalf fields only when allowed.
- [x] Show server-resolved diagnostic target and warnings without override.
- [x] Respect incomplete-profile/no-device setup-help policies.
- [x] Block create on preview blockers and prevent double submit.
- [x] Navigate to the new request chat after success.

Exit: normal request creation exposes no technical catalog/policy terms.

## Phase H — Request list/detail/chat

- [x] Build open/action/closed/all filters and search.
- [x] Use human request number, title, status, last update and next action.
- [x] Build dedicated detail/chat route and sticky composer.
- [x] Localize all timestamps with `ru-RU`.
- [x] Preserve reply text on transient failure.
- [x] Implement attachments and safe timeline.
- [x] Show consent/confirm/rate/reopen only when allowed.
- [x] Refresh dashboard/list/detail after mutations.

Exit: the complete support conversation works on the detail page.

## Phase I — Dynamic profile and constructor parity

- [x] Implement profile field registry/runtime.
- [x] Add `internal_extension` and phone-or-extension completion.
- [x] Build read/edit/setup modes and sections.
- [x] Render custom and managed fields safely.
- [x] Add unsaved-change protection.
- [x] Remove provider/verified/Registry status details.
- [x] Reuse runtime in constructor preview and validate publication.
- [x] Prove admin-published custom field appears without code change.

Checks:

```powershell
pnpm --dir webapp exec vitest run src/features/requester/profile src/features/admin/registry
python -m pytest server/tests/test_requester_workspace_api.py server/tests/test_registry_web_api.py server/tests/test_registration_api.py -vv --durations=80
```

## Phase J — Devices and link wizard

- [x] Build device cards and primary-device explanation.
- [x] Localize online/last-seen/agent version/status.
- [x] Remove diagnostic radio selection.
- [x] Build code → preview → confirm → result wizard.
- [x] Keep direct-link compatibility without displaying `pairing_id`.
- [x] Keep link available before profile completion.
- [x] Cover auto approval and manual admin review.
- [x] Provide safe ownership-change request path.

Exit: no binding/claim/session wording is visible.

## Phase K — Consents and remote actions

- [x] Build shared consent card for dashboard/detail.
- [x] Explain action, access scope, reason, request, requester and expiry.
- [x] Distinguish diagnostics, screen view, remote control and admin access.
- [x] Provide explicit allow/deny and prevent duplicate decisions.
- [x] Remove all technical IDs from visible and accessible text.
- [x] Preserve existing consent authorization/audit.

## Phase L — Localization, accessibility and responsive hardening

- [x] Centralize requester labels/errors/formatters.
- [x] Expand localization guard and DOM forbidden-term tests.
- [x] Preserve UTF-8 and reject mojibake.
- [x] Add landmarks, heading hierarchy, fieldset/legend, first-error focus and `aria-live`.
- [x] Verify keyboard-only profile, device link, dynamic form and chat flows.
- [x] Verify all target viewport sizes and no horizontal scroll.

## Phase M — Knowledge, AI, Customer History and Observer

- [x] Preserve server-side Knowledge audience filtering.
- [x] Preserve Knowledge attempts and Ask-to-request transfer.
- [x] Keep denied titles/internal reasons out of UI.
- [x] Preserve Customer History redaction and creator/affected separation.
- [x] Preserve required redacted Observer events on new routes.
- [x] Do not log message text or sensitive form values into Observer.
- [x] Add integrity checks for form/profile schema version and diagnostic target.

This phase prepares the sequence: user question → Knowledge/AI → optional read-only diagnostics → explicit consent → escalation with context. It does not authorize autonomous write-capable AI.

## Phase N — Cleanup and final gate

- [x] Delete the old monolithic requester implementation.
- [x] Remove dead state/helpers/API calls and legacy requester CSS/classes.
- [x] Confirm page/component size targets.
- [x] Confirm a single request/profile renderer remains.
- [x] Update web-first contract, Quick Lookup, CODEMAP and testing docs.
- [x] Run focused frontend/server/E2E/live browser gates.

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

- deleted old `webapp/src/pages/requester/index.tsx`
- split requester page files from Section 8
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

- deleted old `webapp/src/pages/requester/index.test.tsx` after split page tests took over
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

- [x] explicit requester routes;
- [x] old monolith deleted;
- [x] focused query hooks;
- [x] shared UI/page/form components;
- [x] Tailwind theme layout;
- [x] no legacy requester layout classes.

UX:

- [x] one clear next action on dashboard;
- [x] primary action above fold;
- [x] profile, device link, request creation and chat are separate;
- [x] loading/empty/error states exist;
- [x] no horizontal scroll;
- [x] mobile/tablet preserve the main job.

Dynamic forms/profile:

- [x] every constructor-supported type works;
- [x] conditions, options, prefill, validation and hidden-field omission work;
- [x] constructor preview and requester runtime share implementation;
- [x] unsupported fields cannot publish;
- [x] builder-to-requester E2E is green;
- [x] phone-or-extension completion works;
- [x] hidden/managed profile values are not erased.

Language/safety:

- [x] Russian-first UI;
- [x] no forbidden technical terms/raw IDs;
- [x] safe unknown-state fallbacks;
- [x] backend authorization preserved;
- [x] diagnostic target remains server-resolved;
- [x] Knowledge audience remains creator-scoped;
- [x] consent scope is explicit.

Verification:

- [x] focused frontend/server tests green;
- [x] build green;
- [x] fixture E2E green;
- [x] live browser evidence complete;
- [x] console/network clean;
- [x] docs/code maps current.

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

### Current checkpoint - requester cabinet review fixes, 2026-06-20

Status: completed.

Source reviews:

- `docs/requester-cabinet-review-2026-06-19.md`
- `docs/requester-cabinet-review-2026-06-19-2.md`
- `docs/requester-cabinet-review-2026-06-20.md`

Post-rebase note: `docs/requester-cabinet-review-2026-06-20-2.md` was also rechecked and did not add new requester-cabinet regressions beyond the tracked terminology/service-catalog follow-up.

Confirmed work tracked by implementation:

- [x] P1 terminology hardening: replace requester-visible `заявка` / English `preview` leftovers with the canonical `обращение` / Russian safe wording in requester navigation, request creation, safe API fallbacks and tests.
- [x] P1 safe ticket detail URLs: stop using raw internal `ticket_id` / UUID in `/app/requester/tickets/:ticketCode`; route and post-create navigation must use requester-safe `ticket_code` where available, with a server-side resolver that preserves caller ownership checks.
- [x] P1 dynamic `file` field policy: keep requester-visible `file` fields blocked until draft upload exists, but make the publishable field list, UI copy, tests and DoD explicit so `file` is not advertised as supported requester runtime behavior.
- [x] P2 safe requester errors: map `RequesterApiError` / backend error codes to requester-safe Russian messages and avoid showing raw server `message` / `error` text in normal requester UI.
- [x] P3 traceability: update this plan's completion records/trace note so the review exception and follow-up commit boundary are explicit.
- [x] Service Catalog public terminology: remove requester-visible `Заявка...` wording from setup-help catalog defaults and relevant requester-safe content surfaces, or document any support-only exceptions.
- [x] Deploy/live gate: deploy the verified code to `https://192.168.100.17:9443` and collect real browser evidence for requester cabinet routes.

Acceptance criteria:

- Requester-visible DOM, accessible labels, safe error texts and browser route snapshots no longer contain forbidden review terms for this scope: `заявк`, English `preview`, raw UUID ticket URLs, raw server exception text.
- Ticket list/detail, creation success redirect, requester API detail/message/close/feedback/reopen/history calls keep working for caller-owned tickets through the safe public code route parameter.
- Tests cover safe-code route resolution, post-create navigation, safe error mapping, terminology guard, file-field publication policy and Service Catalog setup-help wording.
- Browser evidence is collected on the canonical deployed stand `https://192.168.100.17:9443` for `/app/requester`, `/app/requester/new`, `/app/requester/tickets` and one detail/chat URL after deploy.

Planned verification:

- `python scripts/verify_workspace.py`
- `python scripts/test_web_first_registration_localization.py`
- `pnpm --dir webapp exec vitest run src/features/requester src/pages/requester src/app/router.test.tsx --reporter=dot`
- `pnpm --dir webapp run build`
- targeted server requester/service-catalog tests for safe ticket code resolution and catalog wording
- deployed browser/live requester cabinet check with console/network capture

Phase completion record:

```text
Phase: Review fixes
Commit(s): d6823009 requester: close cabinet review fixes
Files changed: PLANS.md; content_packs/knowledge/it-self-service-baseline.yaml; docs/QUICK_LOOKUP.md; docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md; scripts/navigation_catalog.py; scripts/test_web_first_registration_localization.py; server/docs/CODEMAP.md; server/requester/identity_service.py; server/tickets/requester_timeline.py; server/tickets/service_catalog_defaults.py; server/tickets/service_catalog_preview.py; server/tickets/statuses.py; server/web_api/requester_handlers.py; webapp/src/features/request-template-studio/draft-model.ts; webapp/src/features/request-template-studio/form-field-editor.tsx; webapp/src/features/requester/api.ts; webapp/src/features/requester/labels.ts; webapp/src/features/requester/queries.ts; webapp/src/features/requester/types.ts; webapp/src/pages/requester/devices-page.tsx; webapp/src/pages/requester/home-page.tsx; webapp/src/pages/requester/new-request-page.tsx; webapp/src/pages/requester/profile-page.tsx; webapp/src/pages/requester/tickets-page.tsx; related tests and docs listed in Git diff.
Automated checks completed before deploy:
- `pnpm --dir webapp exec vitest run src/features/requester/labels.test.ts src/features/requester/queries.test.ts src/features/requester/api.test.ts src/features/requester/dynamic-form/dynamic-form.test.tsx src/features/request-template-studio/draft-model.test.ts src/pages/requester/new-request-page.test.tsx src/pages/requester/tickets-page.test.tsx src/pages/requester/home-page.test.tsx src/pages/requester/devices-page.test.tsx src/pages/requester/profile-page.test.tsx --reporter=dot` — passed 10 files / 52 tests.
- `python scripts/test_web_first_registration_localization.py` — passed 9 tests.
- `python -m pytest server/tests/test_service_catalog_contract_no_db.py -q --tb=short` — passed 5 tests.
- `python -m pytest server/tests/test_knowledge_content_packs.py::test_required_baseline_content_packs_are_present_and_safe server/tests/test_knowledge_content_packs.py::test_primary_agent_requester_guides_pack_contains_pa11_articles server/tests/test_knowledge_pack_bindings.py -q --tb=short` — passed 13 tests.
- `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_requester_workspace_api.py::test_requester_ticket_detail_and_message_are_owned_only server/tests/test_requester_workspace_api.py::test_requester_ticket_message_accepts_attachment_refs server/tests/test_requester_workspace_api.py::test_requester_ticket_message_rejects_foreign_attachment_ref server/tests/test_requester_workspace_api.py::test_requester_can_close_owned_resolved_ticket_only server/tests/test_requester_workspace_api.py::test_requester_can_submit_feedback_and_reopen_owned_ticket_only -q --tb=short` — passed 5 tests.
- `pnpm --dir webapp run build` — passed with existing Vite chunk-size warning.
- `pnpm --dir webapp exec playwright test tests/requester-workspace.spec.ts` — passed 1 test.
- `python scripts/verify_workspace.py` — passed after navigation catalog drift update.
- `python -m pytest server/tests/test_ticket_status_contract_no_db.py server/tests/test_requester_timeline_projection.py server/tests/test_public_queue_privacy.py server/tests/test_ticket_visibility_policy.py server/tests/test_ticket_workflow_visibility.py -q --tb=short` — passed 34 tests.
- `python -m pytest server/tests/test_web_settings_api.py::test_web_settings_returns_aggregated_real_payload server/tests/test_web_support_api.py::test_web_support_ticket_detail_exposes_template_visibility_policy -q --tb=short` — passed 2 tests.
Browser routes checked before deploy: local Playwright fixture for `/app/requester`, `/app/requester/tickets`, `/app/requester/tickets/REQ-1001`, `/app/requester/profile`, `/app/requester/devices`, `/app/kb` and `/app/kb/ask`.
Deploy completed: `python scripts/release_server_to_remote.py --allow-local-dirty --gate quick --leave-running --smoke-insecure-tls` deployed `d6823009` to `https://192.168.100.17:9443`; remote smoke passed on attempt 2.
Live browser evidence: `artifacts/browser_live_validation/requester-cabinet-d6823009-20260620T101945Z/summary.json`; screenshots `01-dashboard.png`, `02-new-request.png`, `03-ticket-list.png`, `04-ticket-detail.png`, `05-devices.png`.
Live routes checked: `/app/requester`, `/app/requester/new`, `/app/requester/tickets`, `/app/requester/tickets/T-000738`, `/app/requester/devices`.
Live assertions: no raw `ticket_id` in DOM/URL/hrefs, URL/link uses `ticket_code`, no requester-visible `заявк`, no visible English `preview`, no console errors, no network failures.
Console/network result: `console.json` and `network.json` in the evidence directory contain no blocking entries.
Residual risks: full final CI/release artifact gate was not run because this was a quick staging deploy, not an explicit frozen release candidate; Vite still reports the pre-existing chunk-size warning for large bundles.
Next phase: no open requester-cabinet review bug remains from the checked review documents; only the broader Phase N/full gate remains for final release hardening.
```
### Current checkpoint - requester critical defects closure, 2026-06-20

Status: D1-D13 closure completed, committed, pushed and deployed to `https://192.168.100.17:9443`. Final deployed code commit: `898dc47993cea62647a2b65d695a8f15ac4bda14`. Final live report: `artifacts/browser_live_validation/requester-critical-302c2ff2-20260620T112749Z/live-report.json`, run `critical-898dc479-20260620-live10-f6e5d4c3b2a1`, status `passed`.

Source intake:

- `C:\Users\admin-2\.codex\attachments\56c20d49-75ac-4507-bfca-abbcf682ab50\pasted-text.txt`

Scope classification: cross-cutting requester cabinet fix across server requester contracts, ticket workflow, service catalog/form selection, dynamic-form runtime, device binding, dashboard projection, browser UI and live validation. This supersedes the narrow review-fixes checkpoint only for newly identified defects; the previous `ticket_code`/safe-error/terminology fixes remain completed.

Triage:

| ID | Status | Priority | Closure target |
| --- | --- | --- | --- |
| D1 service/form auto-selection | Closed and live-verified: wizard uses deterministic problem-text recommendation and no longer chooses the first offering by array order | P0 | Live printer scenario selected printer form and did not expose laptop offering. |
| D2 primary device resolution | Closed: bootstrap returns `primary_device`/`primary_device_resolution` from `PrimaryAgentResolver`; request wizard uses server primary device | P0 | Server multi-device pytest covers ordering; live bootstrap proved `primary_device_resolution.status=available`. |
| D3 device online state | Closed and live-verified: requester device serialization computes online from runtime state and returns requester-safe online values | P1 | Live report shows `device_online_values=[false]` and UI label `Не в сети`; type guard accepts `true/false/null` only. |
| D4 no-device/form availability gate | Closed: frontend no longer treats global `requester_no_device_create` as device context; per-form availability decides selected form | P0 | Automated requester form tests cover no-device/device-required branches; live covers the normal device-backed path. |
| D5 `waiting_on_user` vs `waiting_user` | Closed: requester UI filters/labels/tests use canonical `waiting_on_user` | P1 | Server/frontend tests cover canonical CTA/filter behavior. |
| D6 messages into terminal tickets | Closed and live-verified: requester message handler rejects terminal states with safe `REQUESTER_TICKET_ACTION_NOT_AVAILABLE` | P0 | Live setup POST into closed ticket was rejected; detail page hides reply composer. |
| D7 requester ticket actions | Closed and live-verified: requester ticket DTO exposes server `actions`; UI gates composer/attachments/lifecycle controls by server actions | P0 | Live terminal ticket returned `can_send_message=false`, `can_attach_files=false`; UI composer hidden. |
| D8 dynamic forms partial contract | Closed: requester runtime removes `file` from supported matrices and validates email/url/number/text/options/conditions before preview/create | P1 | Unit tests cover value/schema blockers; live request wizard covers dynamic printer fields and required blockers. |
| D9 dashboard next action | Closed: bootstrap returns ordered `next_actions[]`; dashboard consumes server action before local fallback | P1 | Server tests cover action priority; live bootstrap proved non-empty server `next_actions`. |
| D10 device-link flow | Closed and live-verified: `/app/requester/devices/link` uses `RequesterDeviceLinkPage`, `active` is success, direct pairing load is idempotent, owner-change intent opens explicit owner form | P1 | Live visited `/app/requester/devices`, `/app/requester/devices/link` and `/app/requester/new?intent=device_owner_change`. |
| D11 localization/safe messages | Closed and live-verified: requester/Studio/backend default copy uses `Кабинет пользователя`/`обращение`; old `Каталог заявок` defaults removed from requester-safe surfaces | P1 | Live public form title is `Каталог обращений`; DOM guard found no `заявк`, English `preview` or forbidden technical terms. |
| D12 shared UI/accessibility | Closed and live-verified for active requester pages: nested requester page `<main>` landmarks removed under `AppShell` | P2 | Live desktop/mobile route scan shows `mainCount=1` and no horizontal overflow. |
| D13 internal IDs in URL/DOM | Closed and live-verified: requester URLs use `ticket_code`; requester-safe device labels suppress UUID-like asset names | Regression gate | Live URL/link/DOM guard found no raw ticket UUID and no UUID-like text in visible DOM. |

Implementation order:

1. Contract/test freeze: add failing tests for D1-D13 before implementation where coverage is missing. Pin server DTO expectations for `primary_device`, `primary_device_resolution`, `next_actions[]`, per-form availability and ticket `actions`.
2. Server projections: implement primary-device resolution, online state, per-form availability, server-side next actions and requester ticket action capabilities. Keep ownership checks central in `RequesterIdentityResolver`.
3. Workflow enforcement: block requester messages/attachments and close/feedback/reopen handlers by backend capability, with safe `error_code` responses. Canonicalize `waiting_on_user` across requester list/detail/timeline/tests.
4. Request creation UX: replace first-offering selection with problem-text recommendation plus user-visible category/form review and override before preview/create. Persist selected service/offering/template consistently into preview/create payloads.
5. Dynamic-form contract: remove requester-visible `file` support until draft upload exists; add shared value validation used by preview and create; harden option/condition validation.
6. Device-link/dashboard/localization/UI cleanup: separate `/app/requester/devices/link`, handle owner-change intent, update dashboard to server `next_actions[]`, complete `Кабинет пользователя`/`обращение` copy and remove nested `main` landmarks.
7. Release evidence: deploy to `https://192.168.100.17:9443` only after targeted tests pass, then collect browser evidence for category selection, multi-device primary resolution, online/unknown display, no-device availability, waiting-on-user CTA, terminal-ticket composer hidden, device-link route and ticket-code URL regression.

Acceptance criteria:

- Request creation cannot submit a catalog service/offering/template chosen only by array order; recommendation source and selected override are visible to the user.
- Server bootstrap owns primary device, online state, per-form availability and ordered next actions; frontend treats server projection as authoritative.
- Ticket detail/list actions are server-projected and server-enforced; terminal/closed/canceled tickets reject requester messages and attachments.
- `waiting_on_user` is the canonical value across server projection, frontend filters/CTA and tests; aliases are normalization-only.
- Dynamic form values are type-validated before both preview and create; hidden fields are excluded; null `visible_when.equals` is meaningful; condition cycles and duplicate/empty option values are rejected.
- `/app/requester/devices/link` is a real wizard route; `active` binding/registration status is treated as connected; direct pairing load is idempotent per ID; owner-change CTA lands on a supported flow.
- Requester-visible copy uses `Кабинет пользователя` and `обращение`; no requester-visible `заявка`, English `preview`, raw backend message, raw internal UUID URL or duplicate main landmark remains.

Planned verification:

- `python scripts/verify_workspace.py`
- `python scripts/test_web_first_registration_localization.py`
- `pnpm --dir webapp exec vitest run src/features/requester src/pages/requester src/features/request-template-studio src/components/ui-page --reporter=dot`
- targeted requester browser E2E covering catalog selection, dashboard next actions, ticket capabilities and device-link route
- targeted server pytest for requester bootstrap/profile/ticket detail/message/close/feedback/reopen/create-preview/create contracts
- `pnpm --dir webapp run build`
- deploy quick gate: `python scripts/release_server_to_remote.py --allow-local-dirty --gate quick --leave-running --smoke-insecure-tls`
- live browser evidence on `https://192.168.100.17:9443` with console/network capture and DOM/URL assertions

Execution update, 2026-06-20:

- RED/green coverage added for server primary device, bootstrap `next_actions[]`, terminal message rejection/action DTOs, dynamic-form value/schema validation, service recommendation, per-form no-device fallback, device-link `active`/direct retry/link route, owner-change intent, requester action dashboard, duplicate `<main>` regression and UUID-like requester device label suppression.
- Code commits for this checkpoint:
  - `302c2ff2` - requester critical D1-D13 server/frontend implementation.
  - `70da7592` - requester-safe public form title normalization to `Каталог обращений`.
  - `84772bc3` - nested requester home `<main>` landmark fix.
  - `898dc479` - requester-safe device labels suppress UUID-like asset names.
- Local verification passed:
  - `pnpm --dir webapp test -- src/features/requester/queries.test.ts src/features/requester/labels.test.ts src/features/requester/dynamic-form/dynamic-form.test.tsx src/pages/requester/new-request-page.test.tsx src/pages/requester/devices-page.test.tsx src/pages/requester/tickets-page.test.tsx src/features/request-template-studio/studio-model.test.ts src/features/request-template-studio/draft-model.test.ts src/features/request-template-studio/readiness.test.ts` - 9 files / 48 tests passed.
  - `pnpm --dir webapp test -- src/app/router.test.tsx src/pages/requester/home-page.test.tsx` - 2 files / 17 tests passed.
  - `pnpm --dir webapp test -- src/components/ui-page/page-components.test.tsx src/pages/requester/home-page.test.tsx` - 2 files / 5 tests passed.
  - `python -m py_compile server/requester/identity_service.py server/web_api/requester_handlers.py server/app/api/serializers.py server/tickets/visibility_policy.py server/tickets/form_catalog.py server/tickets/form_lifecycle_service.py server/web_api/admin_handlers.py server/tests/test_requester_workspace_api.py` - passed.
  - `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_requester_workspace_api.py::test_requester_workspace_bootstrap_lists_owned_device_and_ticket server/tests/test_requester_workspace_api.py::test_requester_bootstrap_resolves_primary_device_independently_from_device_order server/tests/test_requester_workspace_api.py::test_requester_ticket_message_rejects_terminal_statuses_and_exposes_actions -q --tb=short` - 4 tests passed.
  - `PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_ticket_form_packs.py::test_admin_can_save_ticket_form_pack_and_switch_current_version -q --tb=short` - 1 test passed.
  - `python scripts/test_web_first_registration_localization.py` - 9 tests passed.
  - `pnpm --dir webapp run build` - passed; existing Vite large-chunk warning remains.
  - `python -m pytest scripts/test_navigation_catalog.py scripts/test_docs_drift_check.py -q` - 14 tests passed.
  - `python scripts/verify_workspace.py` - passed; release script reran it before deploy.
- Deploy evidence:
  - `python scripts/release_server_to_remote.py --allow-local-dirty --gate quick --leave-running --smoke-insecure-tls` - completed successfully for final code commit `898dc47993cea62647a2b65d695a8f15ac4bda14`.
  - Remote workspace HEAD verified as `898dc47993cea62647a2b65d695a8f15ac4bda14`.
  - Remote smoke: `https://192.168.100.17:9443/api/health -> 200` after normal startup retry.
- Live browser evidence:
  - Command: `python artifacts/browser_live_validation/requester-critical-302c2ff2-20260620T112749Z/requester_cabinet_live_check.py --base-url https://192.168.100.17:9443 --run-id critical-898dc479-20260620-live10-f6e5d4c3b2a1 --artifact-dir artifacts/browser_live_validation/requester-critical-302c2ff2-20260620T112749Z --insecure-tls`
  - Result: passed; report `artifacts/browser_live_validation/requester-critical-302c2ff2-20260620T112749Z/live-report.json`.
  - Browser report `browser-report.json`: session/bootstrap/tickets/terminal/public-form APIs returned 200; `publicForms.title=Каталог обращений`; terminal ticket status `closed`, `can_send_message=false`, `can_attach_files=false`; printer recommendation visible and laptop offering not visible; owner-change intent route contains owner/device wording.
  - Screenshots captured: `00-after-login.png`, `01-home.png`, `02-new-request-printer-selection.png`, `03-new-request-owner-intent.png`, `04-devices.png`, `05-devices-link.png`, `06-tickets-open.png`, `06b-tickets-closed.png`, `07-ticket-detail.png`, `08-terminal-ticket-detail.png`, `09-profile.png`, `10-mobile-home.png`.
  - Live guards passed: no console/page/network issues, no horizontal overflow, no duplicate `<main>`, no requester-visible `заявк`, no English `preview`, no forbidden technical terms, no raw ticket UUID, no UUID-like text in visible DOM, and no UUID in requester URLs/links.

Residual release notes:

- No open D1-D13 requester-critical defect remains in this checkpoint.
- The deploy used quick gate intentionally; full frozen release/green CI artifact gate was not run because this was a targeted stand deployment, not a final release-candidate freeze.
- Live validation created isolated stand test users/devices/tickets for run `critical-898dc479-20260620-live10-f6e5d4c3b2a1`; tokens are redacted in reports.
- The remote agent service status is outside this requester web-cabinet gate; server/control services are running and smoke passed.

### Phase N - Cleanup and final gate, 2026-06-19

- [x] Deleted the old monolithic requester implementation and test file: `webapp/src/pages/requester/index.tsx` and `webapp/src/pages/requester/index.test.tsx`.
- [x] Removed the legacy requester wildcard route/lazy export; known old requester section aliases now redirect explicitly and unknown requester paths render the requester-safe not-found page.
- [x] Split requester pages and shared runtimes remain under page/component size targets; no active requester page uses `workspace-page__*` or `support-workspace__*`.
- [x] Static docs and guards now point at split requester pages/runtimes instead of the removed monolith.
- [x] Added deterministic E2E coverage for the split requester cabinet routes in `webapp/tests/requester-workspace.spec.ts`.
- [x] Device-link observer event test now pins manual-review policy before asserting `pending_admin_review`, preserving the default auto-approval production contract.

Phase completion record:

```text
Phase: N
Commit(s): not committed yet
Files changed: PLANS.md; docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md; docs/QUICK_LOOKUP.md; scripts/test_web_first_registration_localization.py; server/docs/CODEMAP.md; server/tests/test_observer_web_cabinet.py; webapp/src/app/router.tsx; webapp/src/app/router.test.tsx; webapp/src/app/routes/lazy-pages.tsx; webapp/src/pages/requester/index.tsx (deleted); webapp/src/pages/requester/index.test.tsx (deleted); webapp/tests/requester-workspace.spec.ts.
Automated checks:
- python scripts/bootstrap_web_toolchain.py - passed; Node 24.15.0 and pnpm 10.33.0.
- pnpm --dir webapp exec vitest run src/app/router.test.tsx src/pages/requester/home-page.test.tsx src/pages/requester/new-request-page.test.tsx src/pages/requester/tickets-page.test.tsx src/pages/requester/profile-page.test.tsx src/pages/requester/devices-page.test.tsx src/features/requester/queries.test.ts src/features/requester/dynamic-form/dynamic-form.test.tsx src/features/requester/profile-runtime/profile-runtime.test.tsx src/features/requester/labels.test.ts src/features/requester/consent-card.test.tsx --reporter=dot - passed 11 files / 52 tests.
- pnpm --dir webapp exec tsc --noEmit --pretty false - passed.
- python scripts/test_web_first_registration_localization.py - passed 8 tests after removing deleted monolith paths from the static guard.
- pnpm --dir webapp run test - passed 111 files / 538 tests; benign jsdom navigation warning remains.
- pnpm --dir webapp run build - passed; existing Vite chunk-size warnings remain.
- pnpm --dir webapp run test:e2e -- requester-workspace.spec.ts - passed 1 test.
- pnpm --dir webapp run test:e2e - passed 7 tests; Windows fixture teardown printed existing asyncio connection-reset noise after tests passed.
- PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_observer_web_cabinet.py::test_web_device_linking_registration_confirm_writes_observer_event -vv --tb=short - passed 1 test after policy fixture fix.
- PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_requester_workspace_api.py server/tests/test_registration_api.py server/tests/test_registry_web_api.py server/tests/test_service_catalog_preview.py server/tests/test_ticket_create_contracts.py server/tests/test_user_consent_api.py server/tests/test_observer_web_cabinet.py server/tests/test_knowledge_ask.py server/tests/test_knowledge_access_service.py -vv --durations=80 - first broad run found the stale observer policy expectation; final rerun passed 147 tests in 964.20s.
Browser routes checked: split requester dashboard, new request, ticket list/detail, profile/setup, devices/link and Knowledge surfaces through local Vite + real Chromium fixture API coverage.
Evidence path: artifacts/browser_live_validation/requester-ui-refactor-20260619/requester-phase-l-a11y-responsive-report.json.
Console/network result: Phase L browser report completed with ok=true, 25 checks, first-error keyboard focus for profile/dynamic form, no forbidden terms and no recorded browser network/console failures.
Residual risks: final `verify_workspace.py`, `git diff --check`, commit and push still run after this PLANS.md update.
Next phase: complete.
```

### Phase M - Knowledge, AI, Customer History and Observer, 2026-06-19

- [x] Requester ticket create now stores safe `requester_context_snapshot.profile_schema.version` evidence and dynamic request-form snapshots include `form_schema_version`.
- [x] Observer web form runtime traces now include only safe pack/template/schema version markers and boolean/count flags, not message text or submitted form values.
- [x] `observer.web_cabinet` integrity scan now flags web requester tickets missing profile-schema version or dynamic form-schema version evidence.
- [x] Existing Knowledge audience filtering, requester Knowledge attempts, Ask-to-request transfer, Customer History projection and chat redaction tests remain green.
- [x] Docs drift updated in `docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md`, `docs/QUICK_LOOKUP.md` and `server/docs/CODEMAP.md`.

Phase completion record:

```text
Phase: M
Commit(s): not committed yet
Files changed: PLANS.md; docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md; docs/QUICK_LOOKUP.md; server/docs/CODEMAP.md; server/requester/identity_service.py; server/web_api/requester_handlers.py; server/tickets/form_catalog.py; server/observer/checks/web_cabinet.py; server/tests/test_requester_workspace_api.py; server/tests/test_observer_web_cabinet.py
Automated checks:
- PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_requester_workspace_api.py::test_requester_create_ticket_accepts_catalog_form_payload server/tests/test_observer_web_cabinet.py::test_web_form_runtime_preview_and_create_write_observer_events server/tests/test_observer_web_cabinet.py::test_web_cabinet_integrity_scan_detects_missing_schema_versions -vv --tb=short - passed 3 tests in 36.20s.
- PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_observer_web_cabinet.py::test_web_cabinet_integrity_scan_detects_on_behalf_knowledge_audience_leak server/tests/test_observer_web_cabinet.py::test_web_cabinet_integrity_scan_detects_missing_customer_history_projection server/tests/test_observer_web_cabinet.py::test_web_knowledge_suggest_writes_requester_observer_event server/tests/test_observer_web_cabinet.py::test_web_knowledge_ask_writes_requester_observer_event server/tests/test_observer_web_cabinet.py::test_web_knowledge_attempts_write_requester_guard_observer_event server/tests/test_observer_web_cabinet.py::test_web_requester_chat_message_writes_observer_event -vv --tb=short - passed 6 tests in 44.36s.
- PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_knowledge_ask.py::test_public_knowledge_ask_applies_audience_rules_before_vector_retrieval_projection server/tests/test_knowledge_ask.py::test_requester_ask_prompt_uses_creator_audience_before_answer_generation server/tests/test_knowledge_access_service.py -vv --tb=short - passed 10 tests in 14.69s.
- pnpm --dir webapp exec vitest run src/pages/kb/ask-page.test.tsx src/pages/requester/new-request-page.test.tsx --reporter=dot - passed 2 files / 7 tests.
Browser routes checked: not repeated in Phase M; Phase M touched backend trace/integrity evidence and existing frontend unit coverage for Ask transfer.
Evidence path: server Observer integrity tests and Knowledge/Ask unit tests above; no new browser artifact.
Console/network result: not applicable for this backend integrity slice.
Residual risks: full final gate remains in Phase N after deleting the old requester monolith and running broad frontend/server/browser checks.
Next phase: Phase N - Cleanup and final gate.
```

### Phase L — localization, accessibility and responsive hardening, 2026-06-19

- [x] Added shared requester label/status/error helpers in `webapp/src/features/requester/labels.ts`.
- [x] Refactored active split dashboard/devices/new-request/tickets/profile pages to reuse shared Russian labels and safe fallbacks.
- [x] Dynamic request/profile controls now use visible Russian labels for accessible names instead of technical field keys.
- [x] Profile setup and dynamic request-form validation focus the first missing field before mutating API calls.
- [x] Profile, device-link, request wizard and chat feedback use `aria-live` status/error regions.
- [x] `scripts/test_web_first_registration_localization.py` now covers split requester pages/runtimes for UTF-8/mojibake/raw-term guardrails.
- [x] Docs drift updated in `docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md`, `docs/QUICK_LOOKUP.md` and `server/docs/CODEMAP.md`.

Phase completion record:

```text
Phase: L
Commit(s): not committed yet
Files changed: PLANS.md; docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md; docs/QUICK_LOOKUP.md; server/docs/CODEMAP.md; scripts/test_web_first_registration_localization.py; webapp/src/features/requester/labels.ts; webapp/src/features/requester/labels.test.ts; webapp/src/features/requester/dynamic-form/index.tsx; webapp/src/features/requester/dynamic-form/dynamic-form.test.tsx; webapp/src/features/requester/profile-runtime/index.tsx; webapp/src/features/requester/profile-runtime/profile-runtime.test.tsx; webapp/src/pages/requester/home-page.tsx; webapp/src/pages/requester/devices-page.tsx; webapp/src/pages/requester/new-request-page.tsx; webapp/src/pages/requester/new-request-page.test.tsx; webapp/src/pages/requester/profile-page.tsx; webapp/src/pages/requester/profile-page.test.tsx; webapp/src/pages/requester/tickets-page.tsx; webapp/src/pages/requester/index.test.tsx; webapp/artifacts/requester-phase-l-a11y-responsive-check.mjs
Automated checks:
- pnpm --dir webapp exec vitest run src/features/requester/labels.test.ts src/features/requester/dynamic-form/dynamic-form.test.tsx src/features/requester/profile-runtime/profile-runtime.test.tsx src/pages/requester/profile-page.test.tsx src/pages/requester/new-request-page.test.tsx --reporter=dot — passed 5 files / 25 tests after first red profile focus assertion was corrected to the actual first missing field.
- python -m pytest scripts/test_web_first_registration_localization.py -q — passed 8 tests after excluding the intentional baseline forbidden-term contract file from normal UI scanning.
- pnpm --dir webapp exec tsc --noEmit --pretty false — passed.
- pnpm --dir webapp exec vitest run src/pages/requester/devices-page.test.tsx src/pages/requester/home-page.test.tsx src/pages/requester/tickets-page.test.tsx --reporter=dot — passed 3 files / 8 tests.
- pnpm --dir webapp exec vitest run src/app/router.test.tsx --reporter=dot — passed 1 file / 14 tests after one combined-run ordering flake.
- pnpm --dir webapp exec vitest run src/features/requester src/pages/requester src/app/router.test.tsx --reporter=dot — passed on rerun, 16 files / 99 tests.
Browser routes checked: `/app/requester/profile/setup`, `/app/requester/devices/link`, `/app/requester/new`, `/app/requester/tickets/T-1001` plus matrix routes `/app/requester`, `/app/requester/new`, `/app/requester/tickets/T-1001`, `/app/requester/profile/setup`, `/app/requester/devices/link` at 390×844, 768×1024, 1366×768, 1440×900 and 1920×1080 through local Vite + real Chromium with fixture API interception.
Evidence path: artifacts/browser_live_validation/requester-ui-refactor-20260619/requester-phase-l-a11y-responsive-report.json; screenshots `requester-phase-l-a11y-responsive-profile-1366x768.png`, `requester-phase-l-a11y-responsive-devices-link-1366x768.png`, `requester-phase-l-a11y-responsive-new-mobile-390x844.png`, `requester-phase-l-a11y-responsive-chat-1366x768.png`.
Console/network result: browser report recorded 0 network issues; keyboard first-error focus was `ФИО` for profile and `Кратко` for dynamic request form; forbidden visible/aria terms were empty; all 25 route/viewport overflow checks passed.
Residual risks: old monolithic requester implementation and legacy tests remain until Phase N cleanup, but the shared runtime contract now forces safe labels in both split and legacy tests.
Next phase: Phase M — Knowledge, AI, Customer History and Observer.
```

### Phase K — consents and remote actions, 2026-06-19

- [x] `webapp/src/features/requester/consent-card.tsx` is the shared pending-consent renderer for dashboard and ticket detail.
- [x] Cards distinguish diagnostics, screen view, remote control and administrative access, explain action/scope/reason/request/requester/expiry, and mask raw UUID/id-like tokens in free text.
- [x] Dashboard and ticket detail use the same explicit approve/deny controls with per-card in-flight locking to prevent duplicate decisions.
- [x] Active requester routes no longer expose consent/session/subject/device identifiers in visible or aria text.
- [x] Existing requester consent authorization, idempotency and audit behavior remains in `server/consent/service.py` and requester handlers; no backend behavior change was needed.
- [x] Docs drift updated in `docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md`, `docs/QUICK_LOOKUP.md` and `server/docs/CODEMAP.md`.

Phase completion record:

```text
Phase: K
Commit(s): not committed yet
Files changed: PLANS.md; docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md; docs/QUICK_LOOKUP.md; server/docs/CODEMAP.md; webapp/src/features/requester/consent-card.tsx; webapp/src/features/requester/consent-card.test.tsx; webapp/src/features/requester/queries.ts; webapp/src/pages/requester/home-page.tsx; webapp/src/pages/requester/home-page.test.tsx; webapp/src/pages/requester/tickets-page.tsx; webapp/src/pages/requester/tickets-page.test.tsx; webapp/artifacts/requester-phase-k-consents-check.mjs
Automated checks:
- pnpm --dir webapp exec vitest run src/features/requester/consent-card.test.tsx --reporter=dot — RED first on repeated labels/assertion shape, then passed 1 file / 2 tests after implementation/test adjustment.
- pnpm --dir webapp exec vitest run src/features/requester/consent-card.test.tsx src/pages/requester/home-page.test.tsx src/pages/requester/tickets-page.test.tsx --reporter=dot — passed 3 files / 7 tests.
- pnpm --dir webapp exec vitest run src/features/requester/consent-card.test.tsx src/features/requester/api.test.ts src/features/requester/queries.test.ts src/pages/requester/home-page.test.tsx src/pages/requester/tickets-page.test.tsx src/app/router.test.tsx --reporter=dot — passed 6 files / 38 tests.
- pnpm --dir webapp exec vitest run src/features/requester src/pages/requester src/app/router.test.tsx --reporter=dot — passed 15 files / 92 tests.
- PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_user_consent_api.py -vv --durations=80 --tb=short — passed 9 tests in 64.63s.
- pnpm --dir webapp run build — passed; existing Vite chunk-size warning remains.
Browser routes checked: `/app/requester` and `/app/requester/tickets/550e8400-e29b-41d4-a716-446655440000` at 1366×768 through local Vite + real Chromium with fixture API interception.
Evidence path: artifacts/browser_live_validation/requester-ui-refactor-20260619/requester-phase-k-consents-summary.json; screenshots `requester-phase-k-consents-dashboard-1366x768.png`, `requester-phase-k-consents-detail-1366x768.png`.
Console/network result: `requester-phase-k-consents-console.json` has only React DevTools info messages; no errors/warnings. `requester-phase-k-consents-network.json` has 0 failed requests. Assertions prove approve and deny calls, 0 forbidden visible/aria consent/session/subject/device identifiers and no horizontal overflow.
Residual risks: old monolithic requester implementation still exists on disk until Phase N cleanup, but active `/app/requester*` routes use the split dashboard/detail consent cards.
Next phase: Phase L — Localization, accessibility and responsive hardening.
```

### Phase J — devices and link wizard, 2026-06-19

- [x] `/app/requester/devices` and `/app/requester/devices/link` now lazy-load `RequesterDevicesPage` instead of the legacy requester monolith.
- [x] The page renders device cards, primary-device explanation, localized online/activity/agent-version/access labels and safe device detail without a diagnostic radio selector.
- [x] Device-link flow is code -> preview -> confirm -> result, keeps direct `pairing_id` compatibility without displaying the id, and remains available before profile completion.
- [x] Manual admin-review and auto-approved result states use requester-safe Russian copy.
- [x] A safe owner-check request path links to `/app/requester/new?intent=device_owner_change`.
- [x] Docs drift updated in `docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md`, `docs/QUICK_LOOKUP.md` and `server/docs/CODEMAP.md`.

Phase completion record:

```text
Phase: J
Commit(s): not committed yet
Files changed: PLANS.md; docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md; docs/QUICK_LOOKUP.md; server/docs/CODEMAP.md; webapp/src/app/router.tsx; webapp/src/app/routes/lazy-pages.tsx; webapp/src/app/router.test.tsx; webapp/src/pages/requester/devices-page.tsx; webapp/src/pages/requester/devices-page.test.tsx; webapp/artifacts/requester-phase-j-devices-check.mjs
Automated checks:
- pnpm --dir webapp exec vitest run src/pages/requester/devices-page.test.tsx --reporter=dot — RED first on missing page module, then passed 1 file / 3 tests after implementation.
- pnpm --dir webapp exec vitest run src/pages/requester/devices-page.test.tsx src/app/router.test.tsx --reporter=dot — passed 2 files / 17 tests.
- pnpm --dir webapp exec vitest run src/features/requester src/pages/requester src/app/router.test.tsx --reporter=dot — passed 14 files / 90 tests.
- pnpm --dir webapp run build — passed; existing Vite chunk-size warning remains.
Browser routes checked: `/app/requester/devices` at 1366×768, `/app/requester/devices/link` at 1366×768 with incomplete profile, and `/app/requester/devices?pairing_id=pair-direct` at 390×844 through local Vite + real Chromium with fixture API interception.
Evidence path: artifacts/browser_live_validation/requester-ui-refactor-20260619/requester-phase-j-devices-summary.json; screenshots `requester-phase-j-devices-desktop-1366x768.png`, `requester-phase-j-devices-incomplete-link-1366x768.png`, `requester-phase-j-devices-direct-390x844.png`.
Console/network result: `requester-phase-j-devices-console.json` has only the React DevTools info message; no errors/warnings. `requester-phase-j-devices-network.json` has 0 failed requests. Assertions prove 0 radio controls, no visible pairing/binding/claim/session/raw id terms, manual-review result, incomplete-profile linking, direct-link auto-approved result and no mobile horizontal overflow.
Residual risks: consent/remote-action cards still depend on the older requester surfaces until Phase K splits and hardens them.
Next phase: Phase K — Consents and remote actions.
```

### Phase I — dynamic profile and constructor parity, 2026-06-19

- [x] `server/registry/profile_schema_service.py` and `server/requester/identity_service.py` now expose controlled `internal_extension`, store it in registry metadata and treat phone-or-internal-extension as satisfying the profile contact requirement.
- [x] `webapp/src/features/requester/profile-runtime/index.tsx` is the shared profile runtime for built-in/custom fields, supported profile field types, phone-or-extension required checks, hidden custom-field omission and publish validation.
- [x] `/app/requester/profile` and `/app/requester/profile/setup` lazy-load `RequesterProfilePage` with read/edit/setup modes, grouped sections, unsaved-change protection, safe requester copy and no provider/verified/Registry status details.
- [x] Admin profile-schema preview reuses the requester profile runtime and blocks preview/save when a draft cannot be published.
- [x] Registration API email-identity confirmation test now pins the manual-review policy fixture explicitly so it stays deterministic under the current default auto-approve-first-binding policy.
- [x] Docs drift updated in `docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md`, `docs/QUICK_LOOKUP.md` and `server/docs/CODEMAP.md`.

Phase completion record:

```text
Phase: I
Commit(s): not committed yet
Files changed: PLANS.md; docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md; docs/QUICK_LOOKUP.md; server/docs/CODEMAP.md; server/registry/profile_schema_service.py; server/requester/identity_service.py; server/tests/test_requester_workspace_api.py; server/tests/test_registration_api.py; webapp/src/app/router.tsx; webapp/src/app/routes/lazy-pages.tsx; webapp/src/features/admin/registry/registry-profile-schema-tab.tsx; webapp/src/features/requester/types.ts; webapp/src/features/requester/profile-runtime/index.tsx; webapp/src/features/requester/profile-runtime/profile-runtime.test.tsx; webapp/src/pages/requester/profile-page.tsx; webapp/src/pages/requester/profile-page.test.tsx; webapp/artifacts/requester-phase-i-profile-check.mjs
Automated checks:
- pnpm --dir webapp exec vitest run src/features/requester/profile-runtime/profile-runtime.test.tsx src/pages/requester/profile-page.test.tsx --reporter=dot — RED first on missing profile-runtime imports, then passed 2 files / 7 tests after implementation.
- pnpm --dir webapp exec vitest run src/features/requester/profile-runtime/profile-runtime.test.tsx src/pages/requester/profile-page.test.tsx src/pages/admin/registry-page.test.tsx --reporter=dot — passed 3 files / 20 tests.
- pnpm --dir webapp exec vitest run src/features/requester/profile-runtime src/features/admin/registry src/pages/requester/profile-page.test.tsx src/app/router.test.tsx --reporter=dot — passed 8 files / 31 tests.
- pnpm --dir webapp exec vitest run src/features/requester src/pages/requester src/app/router.test.tsx --reporter=dot — passed 13 files / 86 tests.
- pnpm --dir webapp run build — passed; existing Vite chunk-size warning remains.
- PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_requester_workspace_api.py::test_requester_internal_extension_satisfies_profile_contact_requirement -vv --tb=short — passed 1 test in 9.68s.
- PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_registration_api.py::test_user_can_confirm_own_claim_by_email_identity server/tests/test_registration_api.py::test_registration_pairing_confirmation_links_account_only_user_by_default -vv --tb=short — passed 2 tests after making the manual-review fixture explicit.
- PC_CLIENT_ALLOW_SHARED_TEST_DB=1 python -m pytest server/tests/test_requester_workspace_api.py server/tests/test_registry_web_api.py server/tests/test_registration_api.py -vv --durations=80 --tb=short — first run failed 1/79 on stale `test_user_can_confirm_own_claim_by_email_identity` policy expectation; final rerun passed 79 tests in 530.07s.
Browser routes checked: `/app/requester/profile/setup?next=/app/requester/new` at 1366×768 and `/app/requester/profile` at 390×844 through local Vite + real Chromium with fixture API interception.
Evidence path: artifacts/browser_live_validation/requester-ui-refactor-20260619/requester-phase-i-profile-summary.json; screenshots `requester-phase-i-profile-setup-1366x768.png`, `requester-phase-i-profile-read-390x844.png`.
Console/network result: `requester-phase-i-profile-console.json` has only the React DevTools info message; no errors/warnings. `requester-phase-i-profile-network.json` has 0 failed requests. Payload assertions prove blank phone with `internal_extension=8899`, visible custom `cost_center`, hidden custom-field omission, no forbidden technical terms and no mobile horizontal overflow.
Notes: a default-DB targeted pytest run hung before producing useful failure output and was stopped; shared-test DB is the recorded server verification path for this phase.
Residual risks: `/app/requester/devices` and `/app/requester/devices/link` still render the legacy requester workspace until Phase J splits them.
Next phase: Phase J — Devices and link wizard.
```

### Phase H — request list/detail/chat, 2026-06-19

- [x] `/app/requester/tickets` and `/app/requester/tickets/:ticketCode` now lazy-load a dedicated `RequesterTicketsPage` instead of the legacy requester monolith.
- [x] The list supports open/action/closed/all filters and search while showing human request numbers, title, requester status, localized last update and next-action hints.
- [x] Detail route renders requester-safe description, messages, timeline, pending consents, sticky reply composer and attachment upload.
- [x] Message send clears text/attachments only after success; transient send failures preserve reply text.
- [x] Consent decisions, close confirmation, feedback and reopen actions use existing requester APIs and invalidate requester bootstrap/list/detail caches after mutations.
- [x] Docs drift updated in `server/docs/CODEMAP.md` and `docs/QUICK_LOOKUP.md`.

Phase completion record:

```text
Phase: H
Commit(s): not committed yet
Files changed: PLANS.md; docs/QUICK_LOOKUP.md; server/docs/CODEMAP.md; webapp/src/app/router.tsx; webapp/src/app/routes/lazy-pages.tsx; webapp/src/pages/requester/tickets-page.tsx; webapp/src/pages/requester/tickets-page.test.tsx; webapp/artifacts/requester-phase-h-tickets-check.mjs
Automated checks:
- pnpm --dir webapp exec vitest run src/pages/requester/tickets-page.test.tsx --reporter=dot — RED first on missing page module, then passed 3 tests.
- pnpm --dir webapp exec vitest run src/pages/requester/tickets-page.test.tsx src/app/router.test.tsx --reporter=dot — passed 2 files / 16 tests.
- pnpm --dir webapp exec vitest run src/features/requester src/pages/requester src/app/router.test.tsx --reporter=dot — passed 11 files / 79 tests.
- pnpm --dir webapp run build — passed; existing Vite chunk-size warning remains.
Browser routes checked: `/app/requester/tickets` and `/app/requester/tickets/T-1001` at 1366×768 through local Vite + real Chromium with fixture API interception; detail route also checked at 390×844.
Evidence path: artifacts/browser_live_validation/requester-ui-refactor-20260619/requester-phase-h-tickets-summary.json; screenshots `requester-phase-h-tickets-list-1366x768.png`, `requester-phase-h-tickets-detail-1366x768.png`, `requester-phase-h-tickets-detail-390x844.png`.
Console/network result: `requester-phase-h-tickets-console.json` has only the React DevTools info message; no errors/warnings. `requester-phase-h-tickets-network.json` has 0 failed requests. Payload assertions prove attachment upload, requester message with attachment refs, consent approve, close, feedback and reopen calls. DOM checks prove raw UUID fallback hidden and no page-level mobile horizontal overflow.
Residual risks: profile, devices and device-link routes still render the legacy requester workspace until Phases I-J split them.
Next phase: Phase I — Dynamic profile and constructor parity.
```

### Phase G — request creation wizard, 2026-06-19

- [x] `/app/requester/new` now lazy-loads a dedicated `RequesterNewRequestPage` instead of the legacy requester monolith.
- [x] The wizard starts from free user text, runs requester-safe Knowledge suggestions before details, records feedback/attempts, consumes safe Ask draft context from `pc_client.knowledge_ask.ticket_context` and does not expose service/form code selectors.
- [x] Details render the Phase F dynamic form runtime with requester context prefill, picker options, required checks and hidden-field omission.
- [x] On-behalf controls render only when the selected form policy allows them; preview/create payloads carry the affected person context only in that policy-gated branch.
- [x] Review uses authenticated safe preview, shows server-resolved diagnostics/warnings, blocks create on preview blockers and disables duplicate preview/create submits.
- [x] Incomplete-profile/no-device setup-help forms remain available when their availability policy allows them; otherwise the profile setup guidance is still shown.
- [x] Successful create invalidates requester queries and navigates to `/app/requester/tickets/{ticket_code}` as the result route when a safe code is available.
- [x] Docs drift updated in `server/docs/CODEMAP.md` and `docs/QUICK_LOOKUP.md`.

Phase completion record:

```text
Phase: G
Commit(s): not committed yet
Files changed: PLANS.md; docs/QUICK_LOOKUP.md; server/docs/CODEMAP.md; webapp/src/app/router.tsx; webapp/src/app/routes/lazy-pages.tsx; webapp/src/app/router.test.tsx; webapp/src/pages/requester/new-request-page.tsx; webapp/src/pages/requester/new-request-page.test.tsx; webapp/artifacts/requester-phase-g-new-wizard-check.mjs
Automated checks:
- pnpm --dir webapp exec vitest run src/pages/requester/new-request-page.test.tsx --reporter=dot — RED first on missing page module, then final passed 3 tests.
- pnpm --dir webapp exec vitest run src/pages/requester/new-request-page.test.tsx src/app/router.test.tsx --reporter=dot — passed 2 files / 16 tests.
- pnpm --dir webapp exec vitest run src/features/requester src/pages/requester src/app/router.test.tsx --reporter=dot — passed 10 files / 76 tests.
- pnpm --dir webapp run build — passed; existing Vite chunk-size warning remains.
Browser route checked: `/app/requester/new` at 1366×768 and 390×844 through local Vite + real Chromium with fixture API interception.
Evidence path: artifacts/browser_live_validation/requester-ui-refactor-20260619/requester-phase-g-new-wizard-summary.json; screenshots `requester-phase-g-new-wizard-1366x768.png`, `requester-phase-g-new-wizard-390x844.png`.
Console/network result: `requester-phase-g-new-wizard-console.json` has only the React DevTools info message; no errors/warnings. `requester-phase-g-new-wizard-network.json` has 0 failed requests. Payload assertions prove service/offering/form/device fields, preview blockers gate, requester Knowledge feedback and `knowledge_attempts` are preserved; mobile check has no page-level horizontal overflow.
Residual risks: request list/detail/chat, profile, devices and link routes still render the legacy requester workspace until Phases H-J split them; final result presentation is the ticket detail/chat route after successful create.
Next phase: Phase H — Request list/detail/chat.
```

### Phase F — dynamic request forms and constructor parity, 2026-06-19

- [x] Added `webapp/src/features/requester/dynamic-form` as the shared requester dynamic-form runtime for field codecs, defaults, prefill merge, `visible_when`, picker option labels, required checks, hidden-field omission, review formatting and schema validation.
- [x] `/app/requester/new` now uses the shared runtime for dynamic request fields and submits normalized payload values including radio, multi-select arrays, registry/device/service picker values and visible conditional fields only.
- [x] Forms Builder process preview reuses the requester runtime control and sends side-effect-free preview payloads without hidden fields.
- [x] Request Studio field editor exposes the full supported constructor type set; Studio publish payload construction blocks unsupported requester runtime schemas, broken `visible_when` references and requester-visible `file` fields until dynamic upload is implemented.
- [x] Docs drift updated in `server/docs/CODEMAP.md` and `docs/QUICK_LOOKUP.md`.

Phase completion record:

```text
Phase: F
Commit(s): not committed yet
Files changed: PLANS.md; docs/QUICK_LOOKUP.md; server/docs/CODEMAP.md; webapp/src/features/requester/dynamic-form/index.tsx; webapp/src/features/requester/dynamic-form/dynamic-form.test.tsx; webapp/src/pages/requester/index.tsx; webapp/src/features/forms-builder/api.ts; webapp/src/features/forms-builder/forms-builder-workspace.tsx; webapp/src/features/forms-builder/forms-builder-workspace.test.tsx; webapp/src/features/request-template-studio/draft-model.ts; webapp/src/features/request-template-studio/draft-model.test.ts; webapp/src/features/request-template-studio/form-field-editor.tsx
Automated checks:
- pnpm --dir webapp exec vitest run src/features/requester/dynamic-form/dynamic-form.test.tsx --reporter=dot — RED first on missing runtime module, then passed 8 tests.
- pnpm --dir webapp exec vitest run src/features/requester/dynamic-form/dynamic-form.test.tsx src/features/request-template-studio/draft-model.test.ts --reporter=dot — passed 13 tests.
- pnpm --dir webapp exec vitest run src/features/forms-builder/forms-builder-workspace.test.tsx --reporter=dot — passed 5 tests.
- pnpm --dir webapp exec vitest run src/features/requester src/pages/requester src/features/forms-builder src/features/request-template-studio --reporter=dot — passed 15 files / 115 tests.
- pnpm --dir webapp run build — passed; existing Vite chunk-size warning remains.
- python -m pytest server/tests/test_requester_workspace_api.py server/tests/test_service_catalog_preview.py server/tests/test_ticket_create_contracts.py -vv --durations=80 — passed 47 tests in 788.35s; slowest setup 434.52s.
Browser routes checked: `/app/requester/new` and `/app/admin/forms?mode=process_preview&template=printer` at 1366×768 through local Vite + real Chromium with fixture API interception; `/app/requester/new` also checked at 390×844.
Evidence path: artifacts/browser_live_validation/requester-ui-refactor-20260619/requester-phase-f-dynamic-form-summary.json and requester-phase-f-builder-preview-summary.json; screenshots `requester-phase-f-dynamic-form-1366x768.png`, `requester-phase-f-dynamic-form-390x844.png`, `requester-phase-f-builder-preview-1366x768.png`.
Console/network result: Phase F requester and builder console/network artifacts have 0 errors/warnings and 0 failed requests; DOM checks show multi-select, registry/device labels, conditional field behavior and no horizontal overflow. Captured submit/preview payloads prove multi-select arrays and hidden-field omission.
Residual risks: Phase F gates requester-visible `file` fields instead of implementing final upload inside the dynamic runtime; attachment upload remains in existing ticket attachment paths and the final wizard split is Phase G.
Next phase: Phase G — Request creation wizard.
```

### Phase E — dashboard, 2026-06-19

- [x] `/app/requester` now renders a focused `RequesterHomePage` dashboard instead of the legacy all-in-one workspace.
- [x] Dashboard uses requester query hooks/projection for bootstrap, tickets and pending consents only; form pack, service catalog, profile detail, device detail and message APIs are not fetched on the home route.
- [x] Header/greeting, `Создать обращение` CTA, one primary next action, compact stats, recent requests and primary device summary fit the dashboard route.
- [x] Dashboard hides legacy full request creation form, public claim form, chat/profile editor and device-link wizard.
- [x] Route/docs drift updated in `server/docs/CODEMAP.md` and `docs/QUICK_LOOKUP.md`.

Phase completion record:

```text
Phase: E
Commit(s): not committed yet
Files changed: PLANS.md; docs/QUICK_LOOKUP.md; server/docs/CODEMAP.md; webapp/src/app/router.tsx; webapp/src/app/routes/lazy-pages.tsx; webapp/src/pages/requester/home-page.tsx; webapp/src/pages/requester/home-page.test.tsx
Automated checks:
- pnpm --dir webapp exec vitest run src/pages/requester/home-page.test.tsx --reporter=dot — RED first on missing page module, then passed 2 tests.
- pnpm --dir webapp exec vitest run src/app/router.test.tsx src/pages/requester/home-page.test.tsx src/pages/requester/index.test.tsx --reporter=dot — passed 3 files / 38 tests.
- pnpm --dir webapp exec vitest run src/features/requester src/pages/requester src/app/router.test.tsx --reporter=dot — passed 8 files / 65 tests.
- pnpm --dir webapp run build — passed; existing Vite chunk-size warning remains.
Browser routes checked: `/app/requester` at 1366×768 and 390×844 through local Vite + real Chromium with fixture API interception.
Evidence path: artifacts/browser_live_validation/requester-ui-refactor-20260619/requester-phase-e-summary.json; screenshots `requester-phase-e-dashboard-1366x768.png`, `requester-phase-e-dashboard-390x844.png`.
Console/network result: `requester-phase-e-console.json` has 0 errors/warnings; `requester-phase-e-network.json` has 0 failed API responses. DOM check: raw ticket UUID hidden, masked request code visible, no legacy create form/device-link/public-access blocks, primary CTA above fold, no horizontal overflow, no form-pack/service-catalog/profile/device-detail fetches.
Residual risks: `/app/requester/new`, `/tickets`, `/profile`, `/devices` and link routes still render the legacy monolith until Phase F+ splits dynamic forms, request creation, chat, profile and devices.
Next phase: Phase F — Dynamic request forms and constructor parity.
```

### Phase D — query architecture and typed projections, 2026-06-19

- [x] Requester server snapshots now use TanStack Query domain hooks for bootstrap, ticket list, consents, form pack, service catalog and registry options.
- [x] Requester detail/profile/device fetches use domain query keys through `queryClient.fetchQuery`; ticket/profile/device/consent mutations invalidate only affected requester keys.
- [x] Added typed dashboard/readiness/next-action projection and safe human request-code formatter.
- [x] Replaced visible requester ticket UUID fallbacks in list, consent, device recent-ticket and creation-success surfaces.
- [x] Page tests now render the requester page under a deterministic `QueryClientProvider`, matching the real app provider boundary.

Phase completion record:

```text
Phase: D
Commit(s): not committed yet
Files changed: PLANS.md; webapp/src/features/requester/queries.ts; webapp/src/features/requester/queries.test.ts; webapp/src/pages/requester/index.tsx; webapp/src/pages/requester/index.test.tsx
Automated checks:
- pnpm --dir webapp exec vitest run src/features/requester/queries.test.ts --reporter=dot — RED first on missing query module, then passed 2 tests.
- pnpm --dir webapp exec vitest run src/features/requester/queries.test.ts src/pages/requester/index.test.tsx --reporter=dot — passed 25 tests after adding the QueryClientProvider page test harness.
- pnpm --dir webapp exec vitest run src/features/requester src/pages/requester --reporter=dot — passed 6 files / 50 tests.
- pnpm --dir webapp run build — passed; existing Vite chunk-size warning remains.
- python -m pytest server/tests/test_requester_workspace_api.py server/tests/test_user_consent_api.py -vv --durations=80 — passed 41 tests in 726.11s; slowest setup 434.55s.
Browser routes checked: `/app/requester` at 1366×768 and 390×844 through local Vite + real Chromium with fixture API interception.
Evidence path: artifacts/browser_live_validation/requester-ui-refactor-20260619/requester-phase-d-summary.json; screenshots `requester-phase-d-query-1366x768.png`, `requester-phase-d-query-390x844.png`.
Console/network result: `requester-phase-d-console.json` has 0 errors/warnings; `requester-phase-d-network.json` has 0 failed API responses. DOM check: full raw ticket UUID hidden, `Обращение 550e8400` visible, no horizontal overflow.
Residual risks: requester page is still the legacy monolith; Phase D moved server state/query ownership but did not yet split pages or remove legacy layout classes.
Next phase: Phase E — Dashboard.
```

### Phase C — routes, shell and navigation, 2026-06-19

- [x] Requester navigation now exposes explicit Russian cabinet routes: `/app/requester`, `/app/requester/new`, `/app/requester/tickets`, `/app/requester/profile`, `/app/requester/devices`, `/app/kb`, `/app/kb/ask`.
- [x] Legacy requester sections redirect only through a known compatibility map; unknown sections render a safe not-found page instead of the monolith.
- [x] Single-workspace requester sessions no longer show the workspace selector; `user` is rendered as `Пользователь`.
- [x] Requester desktop/sidebar and mobile navigation no longer expose `Requester` or `Requester workspace`; `Создать обращение` is the primary CTA.
- [x] Stale login-page test expectation for demo passwords was replaced with the current secure contract: demo credentials must not be visible.

Phase completion record:

```text
Phase: C
Commit(s): not committed yet
Files changed: PLANS.md; webapp/src/app/layouts/app-shell.tsx; webapp/src/app/navigation.tsx; webapp/src/app/navigation.test.ts; webapp/src/app/router.tsx; webapp/src/app/router.test.tsx; webapp/src/components/shell/app-sidebar.tsx; webapp/src/components/shell/app-topbar.tsx
Automated checks:
- pnpm --dir webapp exec vitest run src/app/navigation.test.ts src/app/router.test.tsx --reporter=dot — RED first on missing Phase C contract, then passed 26 tests.
- pnpm --dir webapp run build — passed; existing Vite chunk-size warning remains.
Browser routes checked: /app/requester at 1366×768 and 390×844; /app/requester/create compatibility redirect.
Evidence path: artifacts/browser_live_validation/requester-ui-refactor-20260619/
Console/network result: requester-phase-c-console.json has only Vite/React dev informational messages; requester-phase-c-network.json shows intercepted API calls returning 200.
Residual risks: explicit routes still render the legacy monolithic requester page until Phase D+ replaces data/page composition; browser evidence is local fixture, not deployed stand.
Next phase: Phase D — Query architecture and typed projections.
```

### Phase B — shared UI/Tailwind foundation, 2026-06-19

- [x] Existing `Button`, `Badge`, `Card`, `Input`, `Select`, `SearchField`, `Tabs` audited; no parallel primitive set introduced.
- [x] `ui-page` now exports `PageShell`, `PageHeader`, `PageActions`, `ContentSection`, `ActionCard`, `StatCard`, `StatusBadge`, `EmptyState`, `LoadingState`, `PageSkeleton`, `ErrorState`.
- [x] Shared Russian date/time, status and human identifier formatters added.
- [x] Component tests cover landmarks/regions, status/alert semantics, retry behavior, Russian status labels and raw UUID masking.

Phase completion record:

```text
Phase: B
Commit(s): not committed yet
Files changed: PLANS.md; webapp/src/components/ui/badge.tsx; webapp/src/components/ui-page/formatters.ts; webapp/src/components/ui-page/formatters.test.ts; webapp/src/components/ui-page/index.ts; webapp/src/components/ui-page/page-components.tsx; webapp/src/components/ui-page/page-components.test.tsx
Automated checks:
- pnpm --dir webapp exec vitest run src/components/ui-page --reporter=dot — RED first on missing modules, then passed 6 tests.
- pnpm --dir webapp exec vitest run src/components/ui src/components/ui-page --reporter=dot — passed 6 tests.
- pnpm --dir webapp run build — passed; existing Vite chunk-size warning remains.
Browser routes checked: not required for Phase B because requester routes were not changed.
Evidence path: not applicable for Phase B.
Console/network result: not applicable for Phase B.
Residual risks: new primitives are available but requester pages still need Phase C+ adoption before user-visible UI changes improve.
Next phase: Phase C — Routes, shell and navigation.
```

### Phase A — baseline and regression fixture, 2026-06-19

- [x] Current `HEAD`, working tree state, routing docs, context index and focused context pack verified before editing.
- [x] Deterministic requester baseline contract added for complete/incomplete profile, no/pending/multiple/offline device states, waiting requests, consent, close/rate/reopen, on-behalf allowed/forbidden, archived user, dynamic field matrices and forbidden visible terms.
- [x] Existing pending-claim server test made deterministic by pinning the test registration policy to a real pending-review scenario.
- [x] Browser baseline captured at 1366×768 and 1920×1080 with local fixture API responses and console/network evidence.

Phase completion record:

```text
Phase: A
Commit(s): not committed yet
Files changed: PLANS.md; server/tests/test_requester_workspace_api.py; webapp/src/features/requester/baseline-contract.ts; webapp/src/features/requester/baseline-contract.test.ts; webapp/src/features/requester/types.ts
Automated checks:
- python scripts/build_context_index.py --force — passed; context index rebuilt.
- python scripts/build_context_pack.py --topic "Requester Cabinet Full UI Refactoring Plan Phase A" — passed after context index rebuild.
- python scripts/bootstrap_web_toolchain.py — passed; Node 24.15.0, pnpm 10.33.0.
- python scripts/verify_workspace.py — passed before Phase A edits.
- pnpm --dir webapp exec vitest run src/features/requester/baseline-contract.test.ts --reporter=dot — RED first on missing module, then passed 5 tests.
- pnpm --dir webapp exec vitest run src/features/requester/baseline-contract.test.ts src/pages/requester/index.test.tsx --reporter=dot — passed 28 tests.
- pnpm --dir webapp run build — passed; Vite chunk-size warning remains.
- python -m pytest server/tests/test_requester_workspace_api.py -q --tb=short — baseline failed 1/32 before deterministic policy fix: pending agent claim test did not create a pending claim under auto-approve defaults.
- python -m pytest server/tests/test_requester_workspace_api.py::test_existing_pending_agent_claim_is_visible_to_requester_and_admin -q --tb=short — passed after test fixture fix.
- pnpm --dir webapp run test — baseline failed 2/505: stale login demo-credential assertion in router.test.tsx and support workspace loading-state expectation in support-workspace.test.tsx.
Browser routes checked: /app/requester at 1366×768 and 1920×1080 through local Vite + real Chromium with fixture API interception.
Evidence path: artifacts/browser_live_validation/requester-ui-refactor-20260619/
Console/network result: no page errors or failed API responses; only Vite/React dev informational console entries; all intercepted API calls returned 200.
Known baseline defects: requester UI still exposes English/technical labels (`Requester workspace`, `Requester`, `user`, `open`); requester route is still a monolithic page behind wildcard routing; dashboard/list/profile/devices/form data are still fetched together; left rail uses one-note green palette; forms and cards are densely stacked in the right column at 1366×768.
Residual risks: screenshots are local fixture baseline, not deployed stand evidence; full requester E2E matrix does not exist yet; full web test suite still has unrelated baseline failures to resolve before final gate.
Next phase: Phase B — Shared UI/Tailwind foundation.
```

### Current checkpoint — plan replacement, 2026-06-19

- [x] Current requester screenshots, routes, monolithic component, dynamic request constructor, profile constructor, localization contract and recent changes analyzed.
- [x] Previous `PLANS.md` replaced by this full requester UI refactoring plan.
- [x] Phase A started.

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
