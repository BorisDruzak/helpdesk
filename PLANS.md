# Active Work: Primary Agent, GUI Login and On-Behalf Ticket Context

Status, 2026-06-16: planning document. This plan follows the completed Web-first Registration/Profile refactor and defines the next product decision: one ordinary requester has one primary agent/PC by default, the web cabinet does not ask the requester to choose a device in normal flows, and tickets may optionally be created for another person through explicit form policy. No implementation is accepted until the automated and live validation gates below are satisfied.

Previous completed baseline:

- Web-first registration/profile/device-linking refactor is treated as completed baseline at candidate `c5be05b90cb991903b08cee7cd88c7ecbe06bf11` plus follow-up agent cleanup noted in the previous PLANS history.
- The old active plan established: account != profile, profile != device, device != user; browser-first registration; GUI agent no longer owns requester profile; request forms and Knowledge consume Registry context.
- This new plan does not revert that architecture. It clarifies how normal requester ticket context and diagnostic target selection work after registration.
- 2026-06-16 follow-up audit closed source-level drift in the 3.1.67 agent contract: `/ui/automation/run` no longer exposes an active-profile status flag or locally rejects `ticket.create` on a profile gate before the server account-session contract runs; `ChatPanel` no longer keeps a `requester_profiles.json` path or `has_active_profile` gate. Verification: focused red/green tests -> 2 passed, targeted agent/docs tests -> 194 + 14 passed, `python scripts/verify_workspace.py` -> passed, `python scripts/run_ci_suite.py --layer verify_workspace --layer pc_agent_pytest` -> green with 455 selected pc_agent tests passed.

---

## Product thesis

The primary production model is:

1. One ordinary requester has one primary active agent/PC.
2. The web cabinet belongs to the requester, not to the current physical PC.
3. The primary agent is a technical diagnostic target resolved by the server from Registry bindings.
4. The GUI agent is a local tool for connection/setup/status/optional local actions; it is not the primary requester workspace.
5. Rebinding a device is not a login flow. It is an admin-controlled transfer or an audited user request for ownership change.
6. Creating a ticket for another person is not a rebinding. It is an explicit ticket context: creator != affected user.

Core invariant:

- Normal requester ticket: `creator_person == affected_person`, diagnostic target = creator primary agent.
- On-behalf ticket: `creator_person != affected_person`, diagnostic target = affected person's primary agent.
- If affected person's primary agent is offline or missing, that is diagnostic evidence, not a reason to run checks on the creator's current PC.

---

## Terms and Russian UI wording

Use these user-facing names:

- `Кабинет пользователя` — web requester workspace.
- `Основное устройство` — the primary active agent/PC bound to the affected person.
- `Проблема у другого сотрудника` — requester-facing toggle for on-behalf ticket creation.
- `Сотрудник, у которого проблема` — the affected person selector.
- `Создал обращение` — creator/person who submitted the ticket.
- `Кого касается обращение` — affected person.
- `Устройство для диагностики` — server-resolved affected user's primary agent/PC.
- `Запросить смену владельца устройства` — user-facing request, not immediate rebinding.
- `Передать устройство другому пользователю` — admin transfer action.

Avoid in normal requester UI:

- `pairing`, `binding`, `claim`, `session`, `registry person`, raw UUIDs, raw enum values.

Technical names may remain in code/API/tests where useful:

- `creator_person_id`
- `affected_person_id`
- `target_device_id`
- `target_binding_id`
- `created_on_behalf`
- `diagnostic_target_source`

---

## Target behavior summary

### Normal requester flow

1. User opens `/app/requester` from any browser/device.
2. Server resolves web account -> `RegistryPerson`.
3. Server resolves that person's primary active binding.
4. Request forms prefill profile facts and primary agent/device context.
5. User does not choose a device in the normal path.
6. Ticket create stores creator, affected person and target device context.
7. Diagnostics run only against the server-resolved primary target device when allowed and online.
8. If the primary agent is offline, the ticket records offline evidence and does not try to diagnose the current browser PC.

### On-behalf requester flow

1. A form may opt into `allow_on_behalf=true`.
2. The requester toggles `Проблема у другого сотрудника`.
3. The requester selects the affected person.
4. The form does not ask for a separate diagnostic device in the normal case.
5. Server resolves affected person's primary active agent.
6. Ticket is marked as created on behalf of another person.
7. Support sees both:
   - who created the ticket;
   - who is affected;
   - which device is the diagnostic target.
8. Knowledge shown to the creator remains filtered by the creator's access; affected context may be used for routing/diagnostic target only and must not leak restricted Knowledge to the creator.

### GUI agent flow

1. If the agent has no machine token, GUI opens as connection/setup tool only.
2. If the agent has machine token but no user binding, GUI opens as device-linking wizard only.
3. If the agent is bound, it runs in background by default.
4. GUI does not auto-open as a full workspace after binding.
5. If the user explicitly opens GUI and wants local GUI access, they may enter login/password.
6. The server validates credentials and grants a local GUI account session only if the logged-in user is bound to this current agent/device.
7. If the credentials are valid but the user is not bound to this agent, GUI must not rebind; it offers:
   - `Открыть мой кабинет`;
   - `Создать обращение в web`;
   - `Запросить временный доступ к этому агенту`;
   - `Сообщить, что устройство нужно передать другому пользователю`.

### Admin flow

1. Admin manages ownership changes in one registration/registry center.
2. User cannot directly remove another user's binding or silently rebind a PC through login.
3. User may create an audited request for ownership change.
4. Admin reviews device, current owner, requested affected user, recent sessions, tickets, and quality warnings in one place.
5. Admin chooses transfer/revoke/shared/responsible/reject actions with preview, reason and audit.

---

## What we explicitly do not do

Do not implement these behaviors:

- Do not automatically rebind an agent when another user logs into GUI.
- Do not use the current browser/physical PC as diagnostic target just because the requester is sitting there.
- Do not require normal requester to choose a device in the default ticket flow.
- Do not show a global list of all users in every form by default.
- Do not let on-behalf ticket creation leak Knowledge articles restricted to the affected user.
- Do not run diagnostics on the creator's PC when the ticket is for another person.
- Do not create a new generic registry constructor as part of this work.

---

## Scope

In scope:

- Server-side primary-agent resolver for a person.
- Server-side ticket context model: creator, affected person, target diagnostic device.
- Request form policy flag allowing on-behalf creation.
- Requester UI toggle/search for affected user only when the form allows it.
- Automatic diagnostic target resolution from affected user's primary active binding.
- Knowledge suggestion/access separation: creator-visible Knowledge vs affected-context routing/diagnostic target.
- GUI agent login with server-side credential validation and bound-device check.
- GUI agent state machine for no token / no binding / bound background / bound local GUI login / wrong user on this agent.
- Admin registration/registry center improvements for user/device ownership transfer and on-behalf evidence.
- Automated backend/frontend/agent tests.
- Live validation with real or controlled server, webapp, DB and GUI agent evidence.

Out of scope:

- Full SSO/AD replacement.
- Multi-device user selection as default requester UX.
- Automatic self-service device rebinding by ordinary users.
- Large CMDB redesign.
- Support workspace redesign except showing the new ticket context clearly.

---

## Data model target

Prefer explicit fields if migrations are acceptable. If the current slice avoids migration, store the same structure in `ticket.custom_fields` under stable keys and add migration later.

Required logical fields:

```json
{
  "created_on_behalf": true,
  "creator_person_id": "person_creator",
  "creator_actor_id": "ivanov",
  "affected_person_id": "person_affected",
  "affected_display_name": "Петров П.П.",
  "affected_department_id": "department_finance",
  "affected_location_id": "location_12",
  "target_device_id": "device_petrov_primary",
  "target_binding_id": "binding_petrov_primary",
  "target_agent_status": "offline",
  "diagnostic_target_source": "affected_user_primary_agent",
  "on_behalf_reason": "ПК не включается, сотрудник не может создать обращение"
}
```

For normal tickets:

```json
{
  "created_on_behalf": false,
  "creator_person_id": "person_creator",
  "affected_person_id": "person_creator",
  "target_device_id": "creator_primary_device",
  "diagnostic_target_source": "creator_primary_agent"
}
```

Naming rule:

- Keep existing `requester_*` fields for backward compatibility.
- Introduce new explicit semantics for new code:
  - `creator_*` = who submitted the ticket.
  - `affected_*` = who has the problem.
  - `target_device_*` = where diagnostics should run.

Do not overload `requester_*` to mean both creator and affected user.

---

## Request form policy target

Add form-level policy/config fields, not a hardcoded field in every form:

```json
{
  "on_behalf_policy": {
    "allowed": true,
    "label": "Проблема у другого сотрудника",
    "affected_person_required": false,
    "reason_required": true,
    "allowed_scope": "same_department_or_privileged",
    "diagnostic_target": "affected_person_primary_agent",
    "knowledge_visibility": "creator_only",
    "support_visibility": "creator_and_affected"
  }
}
```

Recommended admin wording in form builder:

- `Разрешить создание обращения за другого сотрудника`.
- Help text: `Если включено, заявитель сможет выбрать сотрудника, у которого проблема. Диагностика будет выполняться по основному устройству выбранного сотрудника, а не по ПК заявителя.`

Default:

- `allowed=false` for all existing forms unless explicitly enabled.

Forms where it is usually useful:

- `Не включается ПК`.
- `Не могу войти`.
- `Проблема с рабочим местом`.
- `Принтер / МФУ`.
- `Нет доступа`.
- `Новый сотрудник / смена сотрудника`.
- `Помощь с регистрацией или привязкой устройства`.

Forms where it should normally remain disabled:

- `Изменить мой профиль`.
- `Мои согласия`.
- `Моя обратная связь`.
- `Персональные настройки`.
- Any form that requires personal verification by the account owner.

---

## Knowledge and RAG access target

Strict rule:

- Creator sees only Knowledge allowed for the creator's own audience.
- Affected person context may be used for diagnostic target, routing, priority, and support context.
- Affected person context must not make restricted articles visible to the creator.
- Support/admin may see both creator and affected context according to their role and Knowledge visibility.

Examples:

- Ivanov creates ticket for Petrov from Finance.
- Ivanov is not in Finance.
- Pre-submit Knowledge suggestions shown to Ivanov must not include Finance-only articles just because Petrov is affected.
- The ticket may route to Finance IT queue if the affected user/affected service context requires it.
- Support workspace may show that the ticket affects Petrov from Finance and may show support-visible related articles.

Tests must verify no leakage before snippets/citations/RAG prompt construction.

---

## GUI agent target

### State 1 — no machine token

Show only:

- `Агент не подключён к серверу`.
- `Ввести токен`.
- `Запросить подключение`.
- `Настройки`.
- `Проверить соединение`.

### State 2 — machine authorized, no user binding

Show only:

- `Устройство ещё не привязано к пользователю`.
- `Создать аккаунт`.
- `Привязать это устройство`.
- `Показать код привязки`.
- `Настройки подключения`.

No tickets, profile, modules, diagnostics or full workspace.

### State 3 — bound, background default

On normal OS startup:

- agent starts hidden/tray/background;
- no full GUI opens automatically;
- server sees agent online.

If opened manually:

- show bound status;
- show `Открыть кабинет`;
- show `Войти в GUI агента`;
- show `Настройки`.

### State 4 — GUI login success for bound user

User enters login/password in GUI. Server validates credentials and verifies binding to current `device_id`.

If allowed, issue short-lived account session for this GUI/device. GUI stores only session id/token, never password.

### State 5 — valid credentials but wrong device binding

Do not rebind. Show:

- `Этот агент привязан к другому пользователю`.
- `Открыть мой кабинет`.
- `Создать обращение в web`.
- `Запросить временный доступ к этому агенту`.
- `Сообщить, что устройство нужно передать другому пользователю`.

### GUI login endpoint options

Preferred implementation:

- Add dedicated endpoint `POST /api/registry/agent/account-sessions/login`.
- Request: agent auth + device_id from token context + login/password.
- Server authenticates account, resolves person, checks active binding for this device, returns account session only if allowed.
- Reject wrong-bound user with safe code `AGENT_GUI_LOGIN_DEVICE_MISMATCH` and Russian message.

Alternative:

- Reuse `/api/web/session/login` only for credentials, then call a second device-scoped session endpoint. This is more round-trip and easier to misuse; dedicated endpoint is cleaner.

---

## Admin registry center target

The admin should not jump between inventory, users and registry pages to resolve registration.

Existing `/app/admin/registry` should become/continue as `Центр регистрации и привязок` with scenario-first sections:

1. `Очередь регистрации`
   - pending device links;
   - on-behalf/ownership-change requests;
   - users without completed profile;
   - devices without active owner;
   - duplicate identities;
   - pending department/location quality issues.

2. `Карточка пользователя`
   - web account;
   - RegistryPerson;
   - identities;
   - profile completeness;
   - primary device;
   - recent tickets;
   - access/audience groups;
   - password reset/admin actions;
   - audit timeline.

3. `Карточка устройства`
   - agent identity;
   - online/offline status;
   - current owner;
   - responsible/shared users;
   - pending claims;
   - recent account sessions;
   - recent tickets;
   - transfer owner;
   - revoke sessions;
   - diagnostics status.

4. `Конфликты`
   - device already bound but new user requests binding;
   - user has no primary device;
   - multiple primary devices for one person;
   - active session after ownership transfer.

5. `Preview before apply`
   - transfer owner;
   - add shared user;
   - revoke binding;
   - revoke account sessions;
   - merge persons;
   - reject request.

All destructive/admin actions require reason and audit.

---

## Phase PA0 — Baseline and current behavior check

Status: completed on 2026-06-16. Baseline documented only; no PA1+ behavior changes were made in this phase.

Tasks:

1. Confirm current account-state and requester context behavior.
2. Confirm current form builder policy surface.
3. Confirm current Knowledge suggestion filtering and RAG access gates.
4. Confirm current admin registry device/person/binding/action surfaces.
5. Confirm current GUI agent account gate and browser-login behavior.

Files to inspect:

- `server/registry/account_state_service.py`
- `server/registry/account_session_service.py`
- `server/registry/browser_pairing_service.py`
- `server/requester/identity_service.py`
- `server/web_api/requester_handlers.py`
- `server/tickets/form_catalog.py`
- `server/tickets/create_flow.py`
- `server/knowledge/suggestion_service.py`
- `server/knowledge/access_service.py`
- `webapp/src/pages/requester/index.tsx`
- `webapp/src/pages/admin/registry-page.tsx`
- `pc_agent/ui_gui/account_gate.py`
- `pc_agent/ui_gui/main_window.py`

Tests:

- Existing requester workspace tests.
- Existing registration/account-session tests.
- Existing form builder tests.
- Existing Knowledge access/RAG tests.
- Existing agent account gate tests.

Acceptance:

- Baseline behavior documented in this file before changes.
- Existing tests pass or known failures are documented.

PA0 baseline checkpoint, 2026-06-16:

- Scope classification: cross-cutting baseline only. This checkpoint did not change runtime behavior.
- Account-state/session/requester context: server account state already exposes `confirmed_binding`, `registration_pending`, and `verified_other_account` account modes; confirmed accounts are tied to active Registry bindings, and other-account sessions are tied to an active base binding. Requester web context currently builds `requester_context_v1` from the authenticated actor, optional owned device binding, profile, location, department, device, asset, and account mode; ticket preview/create persists `requester_context_snapshot` and requester-derived custom fields.
- Form builder policy surface: request forms already support Registry-aware field types (`user_picker`, `department_picker`, `location_picker`, `device_picker`, `service_picker`), field roles/process mappings, template policy refs, and effective Registry policies. The inspected ticket/requester/admin/GUI surfaces have no current `on_behalf`, `affected_person`, `creator_person`, or `primary_agent` workflow tokens, so PA3-PA5 still need explicit on-behalf policy and context fields.
- Knowledge/RAG access: suggestions collect safe text from `form_payload`, `requester_context`, and `device_metadata`, then call search with actor role, service/offering/template context, and `effective_audience`. Knowledge access gates currently enforce item/space lifecycle, coarse visibility, active audience rules, privileged-role override, and rule targets for role/person/department/department tree/location/access group/audience group/service. No creator-vs-affected access split exists yet.
- Admin Registry surface: the admin registry page already exposes overview, devices, people, bindings, requests, account sessions, quality, locations, departments, access groups, audience groups, profile schema, and policies. Current actions include bind primary user, assign responsible, add shared user, transfer owner with preview, revoke binding/sessions with reason, registration claim approval/rejection, and other-account login request approval/rejection. There is no dedicated primary-agent resolver or ownership-change request workflow yet.
- GUI agent gate/login: the Qt account gate is browser-first for registration/login, supports confirmed-binding login and approved other-account login, and hides ticket/profile/create workspace views unless the local session validates as `confirmed_binding` or `verified_other_account`. Browser login pairings create server account sessions for active bindings; browser registration pairings submit registration claims. Login/password-only local GUI behavior from PA8 is not implemented yet.
- Verification baseline:
  - `python scripts/build_context_index.py --force` rebuilt the stale context index.
  - Two broad server pytest batches covering requester/registration/forms/Knowledge timed out at 304s when run as large combined commands; this is recorded as a batching/runtime limitation, not an observed test failure.
  - `$env:PC_CLIENT_ALLOW_SHARED_TEST_DB='1'; python -m pytest server/tests/test_account_session_service.py server/tests/test_browser_pairing_service.py -q --tb=short` -> 23 passed.
  - `$env:PC_CLIENT_ALLOW_SHARED_TEST_DB='1'; python -m pytest server/tests/test_registration_api.py -q --tb=short` -> 34 passed.
  - `$env:PC_CLIENT_ALLOW_SHARED_TEST_DB='1'; python -m pytest server/tests/test_requester_workspace_api.py -q --tb=short` -> 25 passed.
  - `$env:PC_CLIENT_ALLOW_SHARED_TEST_DB='1'; python -m pytest server/tests/test_ticket_form_packs.py -q --tb=short` -> 40 passed.
  - `$env:PC_CLIENT_ALLOW_SHARED_TEST_DB='1'; python -m pytest server/tests/test_knowledge_access_service.py server/tests/test_knowledge_api.py server/tests/test_knowledge_ask.py server/tests/test_knowledge_hybrid_retrieval.py server/tests/test_knowledge_suggestions.py server/tests/test_knowledge_rag_policy.py -q --tb=short` -> 47 passed.
  - `python -m pytest pc_agent/tests/test_account_gate.py pc_agent/tests/test_main_window_runtime_windows.py -q --tb=short` -> 36 passed.
- Known PA0 follow-up: live browser evidence was not collected because PA0 is documentation-only and made no browser-visible change; PA1+ browser-visible changes must use the project browser workflow.

---

## Phase PA1 — Primary agent resolver

Status: completed.

Goal:

Server can resolve a person's primary diagnostic target without asking the requester to choose a device.

Tasks:

1. Add service function: resolve primary active agent/binding for person.
2. Prefer active `primary_user` binding.
3. If no primary exists:
   - fallback to single active binding only if policy allows;
   - otherwise return `primary_device_missing` or `ambiguous_primary_device`.
4. Return safe diagnostic status:
   - device id;
   - binding id;
   - hostname;
   - online/offline;
   - last_seen/last_handshake;
   - agent_version;
   - reason when unavailable.
5. Do not expose raw technical ids in normal requester UI unless needed by admin/support/debug.

Tests:

- Person with one primary device resolves target.
- Person with only shared/responsible device follows policy.
- Person with no device returns no target and safe reason.
- Person with multiple primary bindings returns data-quality/ambiguity issue.
- Offline primary device returns target with `online=false`, not failure.

Acceptance:

- Normal requester forms can get primary device context without device picker.
- Offline agent is represented as diagnostic evidence.

Completed PA1 checkpoint:

- Added `server/registry/primary_agent_resolver.py` with `PrimaryAgentResolver.resolve_for_person(person_id)`.
- Resolution order: one active `primary_user` binding wins; multiple primary bindings return `ambiguous_primary_device`; missing primary returns `primary_device_missing`; a single shared/responsible active binding is allowed only when `diagnostic_target.allow_single_active_binding_fallback=true`.
- Resolved payload is diagnostic-safe: device id, binding id, asset id, relationship, hostname, online/connection state, last seen/handshake and agent version; it does not return tokens, capabilities or raw device metadata.
- Added registry policy default/validation for `diagnostic_target.allow_single_active_binding_fallback` and aligned the typed admin policy payload.
- Updated navigation/docs: `server/docs/CODEMAP.md`, `docs/QUICK_LOOKUP.md`, `scripts/navigation_catalog.py`.
- PA1 verification:
  - `$env:PC_CLIENT_ALLOW_SHARED_TEST_DB='1'; python -m pytest server/tests/test_primary_agent_resolver.py server/tests/test_registry_policy_metadata_unit.py -q --tb=short` -> 9 passed.
  - `$env:PC_CLIENT_ALLOW_SHARED_TEST_DB='1'; python -m pytest server/tests/test_registry_policies_admin.py -q --tb=short` -> 3 passed.
  - `pnpm vitest run src/pages/admin/registry-page.test.tsx` from `webapp/` -> 11 passed.
  - `python -m pytest scripts/test_navigation_catalog.py scripts/test_docs_drift_check.py -q --tb=short` -> 14 passed.

---

## Phase PA2 — Ticket context model: creator, affected person, target device

Status: not started.

Goal:

Ticket creation distinguishes who created the ticket from who has the problem and where diagnostics should run.

Tasks:

1. Add server-side ticket context builder.
2. For normal ticket:
   - creator = authenticated requester;
   - affected = creator;
   - target device = creator primary agent.
3. For on-behalf ticket:
   - creator = authenticated requester;
   - affected = selected person;
   - target device = affected person's primary agent.
4. Store stable context snapshot in ticket custom fields or columns.
5. Preserve compatibility with existing `requester_*` fields.
6. Add explicit `created_on_behalf` marker.
7. Add `diagnostic_target_source` with values:
   - `creator_primary_agent`;
   - `affected_user_primary_agent`;
   - `no_primary_agent`;
   - `ambiguous_primary_agent`;
   - `manual_support_target` for support/admin only.

Tests:

- Normal requester ticket stores creator=affected and creator primary target.
- On-behalf ticket stores creator != affected and affected primary target.
- If affected agent offline, ticket still creates and stores offline target status.
- If affected has no primary agent, ticket creates only if form/policy allows no-agent target.
- Client-supplied target device cannot override server resolution.

Acceptance:

- Support can clearly see creator, affected user and diagnostic target.
- Diagnostics never run on the creator's current PC just because they submitted the ticket there.

---

## Phase PA3 — Request form policy: allow on-behalf creation

Status: not started.

Goal:

On-behalf creation is opt-in per request form/template, not global UI noise.

Tasks:

1. Extend request form schema with `on_behalf_policy`.
2. Add form builder UI toggle:
   - `Разрешить создание обращения за другого сотрудника`.
3. Add helper text explaining diagnostic target behavior.
4. Add policy settings:
   - reason required;
   - allowed scope;
   - affected person required/optional;
   - no-primary-agent behavior;
   - support/admin override behavior.
5. Default `allowed=false` for existing forms.
6. Add migration/backfill if current form packs need explicit defaults.

Tests:

- Form schema validation accepts valid on-behalf policy.
- Invalid policy is rejected.
- Existing forms without policy behave unchanged.
- Form builder renders toggle and saves config.
- Public/requester API returns policy only as safe requester-facing capability.

Acceptance:

- Ordinary forms do not show affected-user selector unless explicitly enabled.
- Admin understands that diagnostics target affected user's primary agent.

---

## Phase PA4 — Requester UI: affected user selector

Status: not started.

Goal:

Requester can create a ticket for another employee only when the form allows it.

Tasks:

1. Add collapsed block in ticket form:
   - `Проблема у другого сотрудника`.
2. If enabled, show person search/select field:
   - `Сотрудник, у которого проблема`.
3. Require reason if policy says so.
4. Show explanation after selection:
   - creator;
   - affected person;
   - affected department/location;
   - primary device status if allowed to display.
5. Do not show device picker in normal on-behalf path.
6. If affected person has no primary agent, show safe note:
   - `У выбранного сотрудника нет привязанного устройства. Диагностика агента недоступна.`
7. Respect allowed scope:
   - ordinary user may search only allowed people;
   - privileged roles may search broader scope.

Tests:

- Toggle hidden when form policy disabled.
- Toggle visible when policy enabled.
- Search only calls allowed endpoint.
- Selected affected user included in preview/create payload.
- UI says diagnostics will use affected user's primary device.
- No raw ids or forbidden technical terms appear in normal UI.

Acceptance:

- User understands they are creating a ticket for another employee.
- User does not choose or see confusing duplicated device fields.

---

## Phase PA5 — Server-side authorization for affected person selection

Status: not started.

Goal:

Users can create on-behalf tickets only within allowed policy scope.

Recommended scopes:

- `self_only` — default.
- `same_department` — ordinary users may choose coworkers in same department.
- `direct_reports` — managers may choose direct reports when manager relation exists.
- `same_department_or_privileged` — ordinary same department, support/admin any.
- `privileged_only` — support/admin only.
- `exact_search_only` — ordinary user must enter exact login/full-name match and receives minimal result.

Tasks:

1. Add person search endpoint for requester on-behalf selection or reuse safe registry options with scope filtering.
2. Enforce scope server-side on preview and create.
3. Never trust client-selected person without revalidation.
4. Add audit reason when creator != affected.
5. Add rate limiting for person search if endpoint is broad.

Tests:

- Ordinary user cannot choose person outside allowed scope.
- Support/admin can choose allowed broader scope.
- Exact search does not expose full directory browsing when policy is restrictive.
- Preview/create reject unauthorized affected_person_id.
- Audit payload records creator, affected and reason.

Acceptance:

- On-behalf feature does not become an employee directory leak.

---

## Phase PA6 — Diagnostics and module execution target

Status: not started.

Goal:

Diagnostics and modules use the ticket's server-resolved target device, not the submitter's current browser/agent.

Tasks:

1. Update ticket diagnostic launch context to read `target_device_id` / diagnostic target snapshot.
2. If target agent is offline, do not enqueue normal agent modules; record `target_agent_offline` evidence.
3. If target device missing/ambiguous, route to manual support queue or require support selection.
4. Ensure support/manual run tool UI clearly shows target device and affected user.
5. Ensure request-form autorun/diagnostic policy uses server-resolved target.
6. Add safety check: client cannot submit a different target device for requester ticket.

Tests:

- Normal ticket autorun targets creator primary agent.
- On-behalf ticket autorun targets affected primary agent.
- Offline target does not enqueue module and stores evidence.
- Missing/ambiguous target prevents autorun and marks manual triage.
- Support manual override is audited.

Live diagnostics evidence:

- Create ticket for self with online primary agent -> module enqueue target self primary device.
- Create ticket for another user with offline primary agent -> no module enqueue, offline evidence visible.
- Create ticket for another user with online primary agent -> module enqueue target affected user's device.

Acceptance:

- No diagnostic operation is sent to the wrong user's agent.

---

## Phase PA7 — Knowledge and RAG access separation

Status: not started.

Goal:

On-behalf context improves routing/diagnostics without leaking affected user's restricted Knowledge to creator.

Tasks:

1. Keep requester pre-submit Knowledge filtered by creator audience.
2. Allow affected context only as safe query signal where it does not reveal restricted content.
3. Support workspace may show creator and affected context with support-role access.
4. RAG/Ask must use creator audience in requester surface.
5. Ticket metadata should record whether suggestions were creator-visible or support-only.

Tests:

- Creator outside affected department cannot see affected department restricted article.
- Ticket still routes/targets affected department/device when allowed.
- Support can see support-visible related articles.
- RAG prompt contains no inaccessible affected-user restricted snippets for requester.
- Suggestions skip raw ids, phone/email/token/session fields.

Acceptance:

- On-behalf ticket creation does not become a Knowledge access bypass.

---

## Phase PA8 — GUI agent login by login/password

Status: not started.

Goal:

GUI can offer local login, but only the server validates credentials and issues a device-scoped GUI account session.

Tasks:

1. Add GUI login form with login/password only when agent is bound or when policy allows local GUI login.
2. Add dedicated server endpoint `POST /api/registry/agent/account-sessions/login`.
3. Server validates credentials through existing auth service.
4. Server resolves `RegistryPerson` from account.
5. Server verifies active binding to current `device_id`.
6. If valid and bound, issue short-lived account session/token.
7. If credentials valid but user not bound, return `AGENT_GUI_LOGIN_DEVICE_MISMATCH` with safe Russian message.
8. GUI stores only session id/token, never password.
9. GUI offers web cabinet / create ticket in web / temporary access request on mismatch.

Tests:

- Bound user can log into GUI and receives account session.
- Wrong password rejected without leaking account info.
- Valid user on another agent gets mismatch response and no account session.
- GUI does not store password in config/session file.
- Existing browser handoff still works.
- Other-account temporary/admin approval remains separate.

Live evidence:

- Local GUI login as bound user succeeds.
- Local GUI login as different user shows mismatch actions.
- No automatic rebinding occurs.

Acceptance:

- GUI login is device-scoped and safe.

---

## Phase PA9 — Admin registration/ownership center

Status: not started.

Goal:

Admin has one practical place to review registration, device ownership, password/user linkage, on-behalf context and data quality.

Tasks:

1. Improve `/app/admin/registry` as `Центр регистрации и привязок`.
2. Add scenario-first queue cards:
   - pending device links;
   - ownership change requests;
   - users without primary agent;
   - devices without owner;
   - users without completed profile;
   - duplicate identities;
   - active sessions on transferred devices.
3. Add card/detail actions:
   - reset/change UI password;
   - link UI account to person;
   - approve/reject device link;
   - transfer owner;
   - add shared/responsible user;
   - revoke sessions;
   - open user/device timeline.
4. Add on-behalf ticket visibility to admin/support detail:
   - created by;
   - affected user;
   - target device;
   - reason;
   - diagnostic target status.

Tests:

- Registry overview shows new queues.
- Admin can open device and person cards from queues.
- Transfer owner preview remains mandatory before apply.
- Password reset/admin user link actions remain role-restricted.
- On-behalf ticket detail renders creator/affected/target context.

Acceptance:

- Admin does not need to jump between inventory and registry to solve registration issues.

---

## Phase PA10 — Forms allowed without full registration/profile/agent

Status: not started.

Goal:

Support emergency/help scenarios without breaking normal profile/device discipline.

Tasks:

1. Add form-level capabilities:
   - `available_without_completed_profile`;
   - `available_without_agent_binding`;
   - `requires_manual_triage`;
   - `contact_required`;
   - `allowed_for_anonymous` only if explicitly needed later, default false.
2. Use for forms such as:
   - `Не могу войти`;
   - `Не включается ПК`;
   - `Помощь с регистрацией`;
   - `Запросить смену владельца устройства`.
3. Show clear warnings that diagnostics may be unavailable until profile/device context is resolved.
4. Route these tickets to manual triage/support queue.
5. Do not auto-run device diagnostics unless a valid target device is resolved.

Tests:

- Incomplete profile can see only allowed forms.
- Incomplete profile cannot see normal forms.
- No-agent user can create allowed emergency form.
- Manual triage marker is stored.
- Diagnostics autorun is suppressed when no valid target exists.

Acceptance:

- Users are not stranded, but normal forms still require the right context.

---

## Phase PA11 — Documentation and localization

Status: not started.

Tasks:

1. Update product docs:
   - web cabinet vs primary agent vs GUI agent;
   - on-behalf ticket semantics;
   - no self-rebinding rule;
   - admin ownership transfer rule.
2. Update user-facing help articles:
   - `Как создать обращение за другого сотрудника`;
   - `Что делать, если мой ПК не включается`;
   - `Как запросить смену владельца устройства`;
   - `Как привязать устройство к аккаунту`.
3. Ensure all new UI strings are Russian.
4. Add static localization guard for forbidden raw terms in normal requester/agent UI.

Tests:

- Docs drift tests updated.
- Localization guard passes.
- No raw `affected_person_id`, `target_device_id`, `binding_id`, `claim_id` in normal requester UI.

Acceptance:

- Non-technical user understands what to do.
- Support/admin can explain why diagnostics target another user's primary agent.

---

## Automated test matrix

Backend required:

- primary-agent resolver;
- ticket context builder;
- on-behalf form policy validation;
- affected person authorization scopes;
- ticket preview/create normal path;
- ticket preview/create on-behalf path;
- diagnostic target selection;
- offline/missing/ambiguous target behavior;
- Knowledge/RAG no-leak tests;
- GUI login endpoint;
- admin registry queues/actions.

Frontend required:

- requester form policy disabled -> no on-behalf UI;
- policy enabled -> toggle/search/reason UI;
- affected user selected -> preview context summary;
- no device picker in default one-user-one-agent flow;
- incomplete profile emergency form visibility;
- admin registry queue/card/detail visibility;
- support ticket detail creator/affected/target context;
- Russian labels and no raw ids in normal UI.

Agent required:

- no token state;
- no binding state;
- bound background/default state;
- GUI login success for bound user;
- GUI login mismatch for unbound user;
- no auto-rebinding;
- no password persistence;
- browser cabinet open remains available.

Integration/e2e required:

- normal user creates ticket -> target own primary agent;
- user creates ticket for another user -> target affected primary agent;
- affected primary agent offline -> no autorun, offline evidence stored;
- wrong user logs into GUI on another PC -> mismatch, no rebind;
- admin transfers ownership -> new primary target used in future tickets;
- creator cannot see affected-only Knowledge.

---

## Live validation checklist

### LV-PA1 — Normal ticket target

1. Seed/create user A with one primary bound online agent.
2. Login as user A in web cabinet.
3. Create normal ticket.
4. Verify ticket creator=A, affected=A.
5. Verify target device=A primary agent.
6. Verify diagnostics enqueue to A device when policy allows.

### LV-PA2 — On-behalf ticket target

1. Seed/create user A and user B.
2. User B has primary bound agent.
3. Login as A.
4. Use form with `allow_on_behalf=true`.
5. Select B as affected person.
6. Create ticket.
7. Verify creator=A, affected=B, target=B primary agent.
8. Verify no diagnostic operation targets A device.

### LV-PA3 — Affected agent offline

1. User B primary agent offline.
2. User A creates ticket for B.
3. Verify ticket creates.
4. Verify no module enqueue to offline target.
5. Verify offline evidence is visible to support.

### LV-PA4 — Knowledge no-leak

1. User B has department-restricted Knowledge article.
2. User A creates ticket for B but lacks B department access.
3. Verify pre-submit suggestions/RAG for A do not expose B restricted article.
4. Verify support/admin can see appropriate support-visible context.

### LV-PA5 — GUI login

1. Start bound GUI agent for user B's device.
2. Login to GUI as B -> success.
3. Login to same GUI as A -> valid account but mismatch, no session.
4. Verify no binding change occurred.
5. Verify GUI offers open web cabinet / request temporary access / ownership change request.

### LV-PA6 — Admin ownership transfer

1. Device initially bound to B.
2. Admin transfers device to C through preview/apply.
3. Verify B future tickets no longer target that device.
4. Verify C future tickets target that device.
5. Verify old sessions are revoked or marked according to policy.

Evidence folder format:

`artifacts/browser_live_validation/primary-agent-on-behalf-<commit>-<YYYYMMDD>/`

Each live run must include:

- commit hash;
- environment summary;
- screenshots or UIA evidence for GUI;
- browser screenshots;
- API/DB excerpts with sensitive values redacted;
- test command output;
- clear pass/fail notes.

---

## Release gate

Do not mark this plan complete until all are true:

1. Normal requester does not choose a device in the default flow.
2. Normal ticket targets creator's primary agent.
3. On-behalf ticket targets affected user's primary agent.
4. On-behalf capability is form-policy controlled and disabled by default.
5. Creator and affected person are stored and visible to support/admin.
6. Client cannot override target diagnostic device in requester flow.
7. Offline/missing/ambiguous primary agent is handled as diagnostic/triage evidence.
8. Knowledge/RAG cannot leak affected user's restricted articles to creator.
9. GUI login by login/password is server-validated and device-scoped.
10. GUI login mismatch never rebinds the agent.
11. Device ownership transfer remains admin preview/apply with reason/audit.
12. Emergency/no-profile/no-agent forms are explicitly allowed per form and routed to manual triage.
13. Russian UI labels are clear and normal user UI does not show raw technical ids.
14. Backend, frontend, agent and e2e tests pass.
15. Live validation covers normal, on-behalf, offline, Knowledge no-leak, GUI mismatch and admin transfer scenarios.

---

## Open decisions before implementation

1. What is the first rollout scope for ordinary users choosing affected people: same department, exact search, or privileged-only?
2. Should managers be allowed to create tickets for direct reports before manager relations are fully reliable?
3. Should on-behalf reason be always required for ordinary users?
4. Should support/admin be able to manually choose diagnostic target when affected user's primary agent is missing?
5. Should one-user-one-agent be enforced by data quality only, or by hard DB constraint for primary bindings?
6. How should shared PCs be represented in requester UI: hidden by default, or separate `Общее устройство` context?
7. Which forms should be enabled first for on-behalf creation?
8. Which emergency forms are allowed before full profile completion?

---

## Implementation discipline for Codex

Work in vertical slices. For every slice:

1. Update server contract first.
2. Add failing tests before implementation where practical.
3. Implement backend.
4. Implement frontend/agent UI.
5. Add Russian labels and safe error mapping.
6. Run targeted backend/frontend/agent tests.
7. Run at least one live check for user-visible flow.
8. Record evidence and status in this file.
9. Do not mix unrelated UI redesign, registry broadening or Knowledge authoring work into this plan.
