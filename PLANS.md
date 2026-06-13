## Active Work: Registry Visibility Foundation — Production Registry, Registration and Knowledge Audience Scopes

Status: active implementation. Phase 0 architecture/docs contract, Phase 1 backend resolver/API slice and Phase 2 backend audience-group slice completed on 2026-06-13. Phase 3 production Registry UI slice is implemented at local commits `3fb13ea8` (`server: add registry visibility foundation`) and `6204c749` (`webapp: add registry access groups summary`): prompt-free bulk/quality/link dialogs, audience-group management and read-only `Группы доступа · P1` discovery are added, deployed through the quick stand path, and browser evidence is recorded under `artifacts/browser_live_validation/registry-phase3-3fb13ea8-20260613/` plus `artifacts/browser_live_validation/registry-access-groups-6204c749-20260613/`. The remaining Phase 3 `Группы доступа` decision is resolved as a read-only Registry summary/deep link over the canonical `/app/admin/access` RBAC editor. Phase 4 registration hardening is in progress: the admin approval diff UI slice is implemented at local/remote commit `4b61b225` (`webapp: show registry registration approval diff`), quick-deployed to the canonical stand and browser evidence is recorded under `artifacts/browser_live_validation/registry-approval-diff-4b61b225-20260613/`. Phase 4 live-agent signoff, Phase 5+ Knowledge audience-rule enforcement and final operability hardening remain open.

Branch target:

* Work on a new branch, for example `codex/registry-visibility-foundation`.
* Keep all changes incremental, tested, documented and backward-compatible with the existing Registry Management Center, registration, account-session and Knowledge Platform contracts.
* This is not an MVP. Build a production-grade but not over-engineered foundation for the functionality that already exists and the near-term planned functionality: user web cabinet, agent registration, requester-safe knowledge, support/admin knowledge, RAG ACL filtering and future AD/SSO sync.

Goal:

* Turn `/app/admin/registry` into the central production registry for people, departments, locations, device ownership, UI-user links, account sessions, access groups and knowledge audiences.
* Keep departments and groups as separate concepts:
  * Departments = organizational structure.
  * Access groups = permissions/RBAC and support work access.
  * Audience groups = content visibility, knowledge targeting, service visibility and future notifications.
* Add an effective identity/audience layer that can answer:
  * Who is this actor?
  * Which registry person is linked to this actor/session?
  * Which department/location/groups/audiences apply?
  * Why can or cannot this actor see a knowledge item?
* Add production knowledge visibility rules for spaces/items using registry departments, department trees, access groups, audience groups, roles, locations, services and explicit people.
* Harden registration so department/location selection can be controlled by policy and verified from the registry instead of producing free-text data drift.
* Add live verification with a real connected agent/account-session flow, not only unit tests.

Non-negotiable principles:

* Do not collapse departments into groups.
* Do not replace the existing Registry Management Center. Extend it.
* Do not duplicate `ui_users` into `registry_people`. UI login links must remain represented through verified `registry_person_identities(provider='ui_login')`.
* `device_user_bindings` remains the authoritative device-person binding source.
* `registry_assets.assigned_person_id` and `device_inventory_bindings.person_id/source_binding_id/registration_status` remain derived/synchronized state.
* Knowledge visibility must be ACL-first:
  * role/visibility/status checks before search result projection;
  * audience rules before semantic/vector/RAG output;
  * no hidden article title/summary/chunk leakage in search, suggestions, Ask/RAG or diagnostics.
* AI/RAG must consume only already-authorized knowledge candidates.
* Admin/support broad access must be explicit and auditable, not accidental.
* Every dangerous registry operation must have preview/dry-run and audit.
* Every permission/visibility decision must have an explain/debug path for admin troubleshooting.
* All new user-facing UI text must be Russian-first.
* Technical enum/API/table names can remain English.
* No raw secrets, tokens, account-session tokens or personal data dumps in logs, screenshots or committed artifacts.

Current baseline context:

* `/app/admin/registry` already contains tabs for overview, devices, people, bindings, requests, account sessions, quality, locations, departments and policies.
* Registry already has people, departments, locations, assets, device-user bindings, registration claims, person identities and account sessions.
* Access groups already exist separately for RBAC/permissions/queues.
* Knowledge spaces/items already have coarse `visibility`, but there is no production audience-scope layer for department/group/person/service-based article visibility.
* Registration policies already include `department_mode` and `location_mode`, but the current Registry Policies UI does not expose these fields as first-class production controls.
* Some Registry bulk UI paths still use `window.prompt` with raw IDs. These must become production dialogs with pickers, preview and result reports.
* Browser pairing and account sessions already define the critical identity boundary:
  * device identity is not requester identity;
  * confirmed binding session = registered user on device;
  * verified other-account session = temporary approved requester identity;
  * registration_pending session must not open normal ticket workspace before approval.

Production target model:

* Registry identity:
  * `UiUser.user_login`
  * `registry_person_identities(provider='ui_login')`
  * `registry_people.person_id`
  * `registry_people.department_id`
  * `registry_people.location_id`
  * `device_user_bindings`
  * `device_account_sessions`
* Organization:
  * `registry_departments`
  * `registry_locations`
  * optional person department memberships for future multi-department cases, while preserving current `registry_people.department_id` as primary/default.
* Access:
  * `access_groups`
  * `access_group_members`
  * `access_group_permissions`
  * `access_group_queue_members`
* Audience:
  * new `registry_audience_groups`
  * new `registry_audience_group_members`
  * new `knowledge_audience_rules`
* Visibility:
  * coarse `knowledge_items.visibility` still applies;
  * new audience rules refine who can see requester-safe/public/internal content;
  * support/admin access must still respect status/lifecycle/policy rules.

Out of scope for this work:

* Do not implement full AD/LDAP synchronization yet.
* Do not implement a generic enterprise ABAC engine.
* Do not rewrite the whole Knowledge Platform.
* Do not replace existing Access Control pages unless needed for linking/explaining registry identity.
* Do not add AI-specific behavior except ensuring RAG/search uses the new authorization boundary.
* Do not implement complex negative/deny rules unless the schema supports them safely and tests cover precedence. Prefer allow-only in the first applied UI if deny behavior is not fully proven.

Change classification and ownership zones:

* Treat this as a cross-cutting contract change, not a local Registry UI cleanup.
* Primary ownership zones from `docs/ARCHITECTURE_BOUNDARIES.md`:
  * Registry / inventory / CMDB;
  * Auth, sessions and device identity;
  * Typed web boundary;
  * React webapp UI;
  * Knowledge Platform;
  * Agent runtime / GUI account-session flow;
  * DB schema and repo contract;
  * Observer instrumentation contract.
* Any implementation phase that changes route payloads, identity semantics, DB schema, search/RAG authorization, account-session validation or browser-visible admin/requester behavior must update producer, consumer, tests and docs in the same checkpoint.
* Do not run parallel edits against `server/routes.py`, migrations, CODEMAP, auth/account-session code or Knowledge ACL/search code from separate tasks unless the contract branch is merged first.

Existing entrypoints to reuse before adding new abstractions:

* Registry/account-session backend:
  * `server/registry/account_state_service.py`
  * `server/registry/account_session_service.py`
  * `server/registry/registration_service.py`
  * `server/registry/registration_form_service.py`
  * `server/registry/policy_service.py`
  * `server/web_api/registry_handlers.py`
  * `server/app/repos/registry_repo.py`
  * `server/routes.py`
* Registry/admin webapp:
  * `webapp/src/pages/admin/registry-page.tsx`
  * `webapp/src/features/admin/registry/*`
  * `webapp/src/features/admin/registry/registry-policies-tab.tsx`
  * `webapp/src/features/admin/registry/registry-quality-tab.tsx`
* Access-control boundary:
  * `server/access_control/*`
  * `server/web_api/access_handlers.py`
  * existing `access_groups`, `access_group_members`, `access_group_permissions` and queue membership repos/routes.
* Knowledge authorization/search:
  * `server/knowledge/contracts.py`
  * `server/knowledge/visibility.py`
  * `server/knowledge/search_service.py`
  * `server/knowledge/retrieval_service.py`
  * `server/knowledge/portal_service.py`
  * `server/knowledge/metadata_service.py`
  * `server/web_api/knowledge_handlers.py`
  * `server/app/repos/knowledge_repo.py`
* Agent/requester boundary:
  * `pc_agent/core/account_session.py`
  * `pc_agent/ui_gui/account_gate.py`
  * `pc_agent/ui_gui/main_window.py`
  * `pc_agent/ui_gui/server_api.py`
  * `pc_agent/ui_gui/chat_panel.py`
  * `server/tickets/account_access_service.py`
  * `server/tickets/create_flow.py`
  * `server/web_api/requester_handlers.py`
* Canonical docs to keep aligned:
  * `server/docs/REGISTRATION_ACCOUNT_SESSIONS.md`
  * `server/docs/REGISTRY_MANAGEMENT_CENTER.md`
  * `server/docs/REGISTRY_VISIBILITY_FOUNDATION.md`
  * `server/docs/KNOWLEDGE_PLATFORM.md`
  * `server/docs/KNOWLEDGE_OPERATIONS.md`
  * `server/docs/SECURITY_AND_AUTH.md`
  * `server/docs/DATABASE.md`
  * `server/docs/CODEMAP.md`
  * `pc_agent/docs/CODEMAP.md`
  * `docs/QUICK_LOOKUP.md`

Implementation efficiency rules:

* Start each phase with `python scripts/build_context_pack.py --topic "registry visibility foundation <phase>"` and one focused `python scripts/search_context_index.py "<route symbol contract>" --profile contract` query.
* Prefer extending existing Registry services and repos over adding a parallel identity or membership store.
* Effective identity must be a read model/resolver over verified sources. It must not mutate account sessions, registration claims, bindings or people.
* Add the audience-group schema and expansion service before wiring Knowledge audience rules. Knowledge phases should depend on stable audience expansion tests, not duplicate expansion logic.
* Keep `registry_people.department_id` as the compatibility primary department even if `registry_person_department_memberships` is added.
* Use archive/status columns for audience groups and rules; avoid hard deletes for admin-managed visibility objects.
* Route additions must be reflected in backend handler tests, TS API clients/types and CODEMAP/QUICK_LOOKUP when they become canonical.
* UI pickers must consume names/codes from APIs and show raw UUIDs only under `Advanced / служебные поля`.
* Existing `window.prompt` usage is a regression target. Registry production flows should use dialogs/drawers with preview, reason and result reports.
* Knowledge ACL enforcement must be placed at candidate selection and final projection. Do not rely only on UI filtering or post-search masking.
* Search, suggestions, portal, support knowledge, agent suggestion APIs and RAG/vector retrieval must all share the same access service or a thin wrapper over it.
* Any live script or browser evidence must redact account-session token, machine token, pairing token/code, cookies, raw auth headers and hidden article content.
* Treat `/app/admin/access` as the canonical RBAC/access-group editor until the plan explicitly says otherwise. If Phase 3 adds a Registry `Группы доступа` surface, prefer a read-only summary/deep link over a second mutation UI unless operator workflow, tests and docs justify duplication.
* For docs-only plan/context updates, run docs/navigation verification instead of deploy. Do not run release scripts just to update `PLANS.md`.

Phase dependency gates:

* Phase 0 must finish before behavior changes: the architecture contract and docs list are the handoff anchor.
* Phase 1 must finish before Phase 5/6/7. Knowledge visibility cannot safely consume actor/session context until effective identity is test-covered.
* Phase 2 must finish before audience rules are enforced in Knowledge. Do not let Knowledge implement its own private audience expansion.
* Phase 3 can proceed after the relevant backend APIs exist, but UI dialogs must not fake successful preview/apply without server dry-run support.
* Phase 4 live agent registration checks must pass before Phase 7 signoff; unit tests alone are insufficient for account gate/session transitions.
* Phase 5 must prove anti-leak behavior before Phase 6 exposes authoring controls to operators.
* Phase 8 is final operability hardening; do not treat observer/quality/import-export as cosmetic if earlier phases introduce data drift or hidden ACL failures.

Current context from intake, 2026-06-13:

* `python scripts/build_context_pack.py --topic "registry visibility foundation registration knowledge audience scopes"` classified the work as `Feature / Cross-cutting` and matched `knowledge_platform`, `web_platform` and `registry_objects`.
* `python scripts/build_context_index.py --force` rebuilt the local retrieval index after stale warnings: 21,216 items, 837 routes, 16,813 symbols and 2,048 tests.
* Relevant existing route anchors include:
  * `GET /api/registry/agent/registration-form`
  * `GET /api/registry/agent/registration-status`
  * `POST /api/registry/agent/account-sessions/registration-pending`
  * `POST /api/web/registry/browser-pairings/{pairing_id}/registration/confirm`
  * `POST /api/web/admin/registry/ui-users/{user_login}/link-person`
  * `POST /api/knowledge/search`
  * `POST /api/knowledge/suggest`
  * `POST /api/knowledge/feedback`
  * `GET|POST /api/web/knowledge/*`
* Existing policy code already validates `registration.department_mode` and `registration.location_mode` values in `server/registry/policy_service.py`; Phase 4 should expose/enforce the existing contract rather than invent new mode names.
* Existing Knowledge visibility levels are `public`, `requester`, `agent_requester_safe`, `support_internal`, `admin_internal`, `security_restricted` and `auditor_read`. Audience rules refine these levels; they must not make internal/support-only content requester-visible.
* Existing tests already cover important anchors such as account sessions, registration, Knowledge visibility/search, vector ACL-before-similarity and RAG ACL evaluation. Reuse and extend them before creating broad new suites.

Current handoff context, 2026-06-13:

* Current local branch at this intake is `codex/helpdesk-process-model`. Before starting the next implementation step, run `git status -sb` and verify the branch contains `3fb13ea8`; do not assume the local branch, GitHub `origin` and deployed stand are aligned without checking.
* Phase 3 live/browser evidence for commit `3fb13ea8` is under `artifacts/browser_live_validation/registry-phase3-3fb13ea8-20260613/`.
* Browser evidence covers `/app/admin/registry` overview at 1366 and 1920 widths, `Аудитории · P1` create/preview/save/archive, member preview counts, device bulk dialog with reason/preview controls, and people/UI-account linking controls. The temporary test audience code `codex_phase3_3fb13ea8` was archived during cleanup.
* Access groups already have a production surface at `/app/admin/access` backed by `webapp/src/features/access-control/api.ts`, `webapp/src/pages/admin/access-page.tsx` and `/api/web/admin/access/*` in `server/web_api/access_handlers.py`.
* Access groups are RBAC/queue-permission facts. Registry effective identity and audience expansion may read them as targeting facts, but Registry audience groups must not grant or mutate access-group permissions.
* The Phase 3 `Группы доступа` expectation is to keep `/app/admin/access` as canonical editor and expose only a read-only Registry summary/deep link. If this changes later, tests must prove the UI reuses existing Access Control APIs and does not create a competing permissions model.
* Current workspace contains unrelated tracked changes in `.codex/config.toml`, `pc_agent/ui_gui/tickets_list_model.py` and `scripts/live_agent_uia_state_probe.py`, plus many untracked artifacts. Stage only files that belong to the active task.
* If the remote stack is still running from browser validation and no further live checks are planned, stop it through `python scripts/manage_remote_stack.py stop server` and `python scripts/manage_remote_stack.py stop control`.

---

## Phase 0 — Architecture audit and contracts

Goal:

* Record the production contract before code changes.
* Map the current registry, registration, access-control and knowledge visibility boundaries.
* Identify exact files/services/routes that must change.

Tasks:

* Review current code and document:
  * `/app/admin/registry`
  * `server/web_api/registry_handlers.py`
  * `server/registry/*`
  * `server/web_api/access_handlers.py`
  * `server/access_control/*`
  * Knowledge search/view/suggestion/RAG paths.
* Add/update docs:
  * `server/docs/REGISTRY_MANAGEMENT_CENTER.md`
  * `server/docs/REGISTRY_VISIBILITY_FOUNDATION.md`
  * `server/docs/KNOWLEDGE_OPERATIONS.md`
  * `server/docs/CODEMAP.md`
  * `docs/QUICK_LOOKUP.md`
* Define canonical terms:
  * `department`
  * `access_group`
  * `audience_group`
  * `queue`
  * `role`
  * `person`
  * `identity`
  * `account_session`
  * `knowledge_audience_rule`
* Add an architecture note explaining why department != group.

Verification:

* `git diff --check`
* `python -m compileall -q server shared scripts`
* Verify docs contain no mojibake.
* Verify docs clearly say departments are organizational structure, not RBAC groups.
* Verify no runtime behavior changed in Phase 0.

Exit criteria:

* Architecture contract is recorded.
* Tables/services/routes planned before implementation.
* Live-check expectations are documented.
* No code behavior changed.

Phase 0 execution, 2026-06-13:

* Added `server/docs/REGISTRY_VISIBILITY_FOUNDATION.md` as the canonical architecture contract for Registry identity, audience groups, account sessions and Knowledge visibility before runtime implementation.
* Updated `server/docs/REGISTRY_MANAGEMENT_CENTER.md` to link the new foundation and explicitly separate departments, access groups and future audience groups.
* Updated `server/docs/KNOWLEDGE_PLATFORM.md` and `server/docs/KNOWLEDGE_OPERATIONS.md` so future Registry audience rules refine coarse Knowledge visibility without leaking support/admin-only content.
* Updated `server/docs/CODEMAP.md` and `docs/QUICK_LOOKUP.md` with the new routing/context anchor and implementation entrypoints.
* Behavior changed: none. No runtime routes, migrations, services or UI behavior were added in Phase 0.
* Phase 0 verification target: `git diff --check`; `python -m compileall -q server shared scripts`; `python scripts/docs_inventory.py --check-links`; `python scripts/verify_workspace.py`; mojibake scan for changed docs.

---

## Phase 1 — Effective identity and audience resolver

Goal:

* Add a single backend service that resolves actor/session identity into effective registry identity and audience context.
* All future visibility decisions must use this resolver.

Backend service:

Add:

* `server/registry/effective_identity_service.py`
* `server/registry/audience_contracts.py`

Required methods:

```python
resolve_actor_identity(actor_id: str, actor_role: str) -> EffectiveIdentity
resolve_account_session_identity(device_id: str, session_id: str, session_token: str | None) -> EffectiveIdentity
resolve_person_audience(person_id: str | None, actor_id: str | None, actor_role: str) -> EffectiveAudience
explain_identity(actor_id: str, actor_role: str) -> dict
```

Effective identity payload:

```json
{
  "actor_id": "ivanov",
  "actor_role": "user",
  "person_id": "...",
  "person_name": "Иванов Иван Иванович",
  "ui_login": "ivanov",
  "department_id": "...",
  "department_path": ["root", "finance"],
  "location_id": "...",
  "access_groups": ["support_l1"],
  "audience_groups": ["finance_staff", "edo_users"],
  "account_session": {
    "session_id": "...",
    "account_mode": "confirmed_binding",
    "device_id": "...",
    "binding_id": "..."
  },
  "warnings": []
}
```

Rules:

* Admin/support actor identity may resolve without registry person, but explain output must show that registry person is missing.
* User-facing requester flows should prefer linked registry person; unlinked user must be visible in Registry quality issues.
* Agent machine identity alone must not resolve as requester person.
* Account session identity must validate through AccountSessionService; never trust client-supplied person/binding fields.

Admin API:

Add:

GET /api/web/admin/registry/identity/effective?actor_id=...
GET /api/web/admin/registry/identity/person/{person_id}/audience
GET /api/web/admin/registry/identity/session/{session_id}/explain

TDD checkpoints:

RED test: linked ui_login resolves to RegistryPerson.
RED test: unlinked ui_user returns no person_id plus warning.
RED test: confirmed binding account session resolves person/device/binding.
RED test: verified other-account session resolves declared person/session but does not change device owner.
RED test: agent machine token alone does not resolve requester identity.
RED test: access group membership is included from existing access-control repo.
RED test: department tree/path is returned.
RED test: explain output is deterministic and contains no raw tokens.

Verification:

python -m pytest server/tests/test_registry_effective_identity_service.py
python -m pytest server/tests/test_registration_account_sessions.py
python -m compileall -q server shared scripts
git diff --check

Live checks:

Start server.
Login as admin in web UI.
Open a new temporary debug/admin identity view or call API.
Check:
admin user resolves with role and access groups;
test requester with linked UI login resolves to person;
unlinked UI user appears as unresolved;
real agent account session resolves only after account login.
Save evidence:
API JSON with tokens redacted;
screenshot of admin identity/explain view if UI exists.

Exit criteria:

Effective identity resolver is the only new identity source used by later phases.
Existing registration/account-session tests still pass.
No requester identity is inferred from agent machine token.

Phase 1 execution, 2026-06-13:

* Added `server/registry/audience_contracts.py` with side-effect-free `EffectiveIdentity` and `EffectiveAudience` read-model contracts.
* Added `server/registry/effective_identity_service.py` to resolve UI actors, verified `ui_login` / email identities, registry people, department paths, locations, existing access groups and server-validated account sessions.
* Added admin-only read/explain APIs:
  * `GET /api/web/admin/registry/identity/effective?actor_id=...&actor_role=...`
  * `GET /api/web/admin/registry/identity/person/{person_id}/audience`
  * `GET /api/web/admin/registry/identity/session/{session_id}/explain`
* Added `server/tests/test_registry_effective_identity_service.py` covering linked UI login, unlinked UI user warnings, agent machine-token non-requester behavior, confirmed binding account sessions, verified other-account sessions without owner leakage, department path/access group facts and token redaction.
* Verified with focused DB tests through the project test DB tunnel at `127.0.0.1:55432/pc_support_test`; this is not a full release gate.
* Phase 1 does not add audience-group tables, Knowledge audience filtering or UI management. Those remain Phase 2+ work.

---

## Phase 2 — Audience groups and registry membership model

Goal:

Add production audience groups for content visibility and future notifications/service targeting.
Keep them separate from access groups.

Backend schema:

Add migration:

registry_audience_groups
audience_group_id
code
name
description
source: manual, department_rule, import, system, future_sync
status: active, archived
metadata_json
created_at, updated_at, created_by, updated_by
registry_audience_group_members
membership_id
audience_group_id
member_type: person, department, department_tree, location, access_group, role, service
member_id
include_children
valid_from
valid_to
source
metadata_json
timestamps/audit fields

Optional but recommended compatibility-safe schema:

registry_person_department_memberships
membership_id
person_id
department_id
is_primary
role_in_department
valid_from
valid_to
source
metadata_json

Rules:

Preserve registry_people.department_id as primary department for compatibility.
Backfill registry_person_department_memberships from registry_people.department_id if this table is added.
Do not remove or repurpose existing access groups.
Audience group membership can include access group as source, but audience group does not grant permissions.

Backend API:

Add:

GET /api/web/admin/registry/audience-groups
POST /api/web/admin/registry/audience-groups
PATCH /api/web/admin/registry/audience-groups/{audience_group_id}
POST /api/web/admin/registry/audience-groups/{audience_group_id}/archive
GET /api/web/admin/registry/audience-groups/{audience_group_id}/members
PUT /api/web/admin/registry/audience-groups/{audience_group_id}/members
POST /api/web/admin/registry/audience-groups/{audience_group_id}/preview-members

Preview requirements:

Preview must expand department_tree, access_group, role, location and person members into effective person counts.
Preview must not mutate state.
Preview must show warnings:
empty group;
archived department/location;
unknown referenced object;
group includes broad role such as user.

Audit:

Every create/update/archive/member change writes registry_admin_events.
Timeline drawer must show audience-group events where relevant.

TDD checkpoints:

RED migration test for new tables and constraints.
RED test for audience group CRUD.
RED test for membership expansion.
RED test for department_tree expansion.
RED test for access_group membership expansion.
RED test that audience group does not grant RBAC permissions.
RED test for audit events.
RED test for archived group exclusion.

Verification:

python -m pytest server/tests/test_registry_audience_groups.py
python -m pytest server/tests/test_registry_effective_identity_service.py
python -m compileall -q server shared scripts
git diff --check

Live checks:

Create test departments:
ИТО
Бухгалтерия
Бухгалтерия / Расчётная группа
Create test people and link at least one UI user.
Create audience groups:
all_staff
finance_staff
it_staff
edo_users
Add members:
department_tree=Бухгалтерия
person=<specific person>
access_group=<existing support group>
Run preview and verify expanded counts.
Save browser evidence:
audience group list;
member editor;
preview with expanded people;
audit/timeline event.

Exit criteria:

Audience groups exist and are usable without changing RBAC semantics.
Membership expansion is deterministic and test-covered.
Registry audit records changes.

Phase 2 backend execution, 2026-06-13:

* Added migration `120` in `server/app/db/migrations/versions/20260613_120_registry_audience_groups.py`.
* Added SQLAlchemy models for `registry_audience_groups`, `registry_audience_group_members` and compatibility-safe `registry_person_department_memberships`.
* Added `server/registry/audience_group_service.py` for admin CRUD, member replacement, archive, deterministic preview expansion and warnings for empty groups, unknown objects, archived departments/locations and broad roles.
* Added admin-only APIs under `/api/web/admin/registry/audience-groups*`.
* Added `server/tests/test_registry_audience_groups.py` covering CRUD, expansion, department tree, access-group-as-audience, no RBAC grant from audience membership, audit events and archived exclusion.
* Updated test DB cleanup to truncate the new audience tables.
* Phase 2 backend does not add the production UI editor; `/app/admin/registry` audience-group management remains Phase 3.

---

## Phase 3 — Production Registry UI for people, departments, groups and bulk actions

Goal:

Make /app/admin/registry usable as production registry UI, not only a technical table/workbench.
Remove raw-ID prompt flows from main operator paths.

UI changes:

Add or improve Registry tabs:
Пользователи
UI аккаунты
Подразделения
Локации
Группы доступа
Аудитории
Политики
Качество данных
Add clear person detail drawer:
ФИО
linked UI login
identities
department
location
access groups
audience groups
devices
account sessions
tickets count
knowledge visibility debug entry point
Add unlinked UI users view:
linked/unlinked status;
actor role;
active/locked state;
link to existing person;
create person from UI user;
identity collision handling;
audit reason.
Replace window.prompt bulk actions with dialogs:
device assign department;
device assign location;
people assign department;
revoke sessions;
audience group member changes.
Bulk dialogs must use searchable pickers, preview, reason and normalized apply report.

UX rules:

Raw IDs may be visible only in Advanced / служебные поля.
Primary operator flow must use names, codes and searchable selectors.
Destructive/dangerous actions require reason.
Apply button disabled until preview succeeds where preview is available.
Result report must show selected/success/failed counts and copyable failed rows.
All visible product text must be Russian.

TDD checkpoints:

RED webapp test for no window.prompt in registry bulk actions.
RED webapp test for department/location searchable picker.
RED webapp test for unlinked UI users.
RED webapp test for link UI user to person.
RED webapp test for audience group editor.
RED webapp test for Russian labels and no mojibake.
RED webapp test for preview-before-apply behavior.

Verification:

pnpm --dir webapp exec vitest run src/pages/admin/registry-page.test.tsx --reporter=dot
pnpm --dir webapp exec vitest run src/features/admin/registry/*.test.tsx --reporter=dot
pnpm --dir webapp exec tsc --noEmit --pretty false
pnpm --dir webapp build
git diff --check

Live checks:

Start webapp/server.
Open /app/admin/registry.
Browser widths:
1366x768
1920x1080
Verify:
no horizontal body scroll;
main actions visible without hidden technical prompts;
people tab shows linked/unlinked UI users;
department picker works in bulk assign;
audience groups can be created/edited;
preview appears before dangerous apply;
action result report is visible;
console errors/warnings = 0.
Save evidence under:
artifacts/registry-visibility-foundation-YYYYMMDD/registry-overview-1366x768.png
registry-people-linked-ui-1366x768.png
registry-bulk-preview-1366x768.png
registry-audience-groups-1366x768.png
registry-console.json
registry-network.json

Exit criteria:

Registry UI can be operated without copying raw UUIDs for normal tasks.
UI-user/person linking is production-usable.
Audience groups are manageable in UI.
Bulk actions have preview/result reports.

Phase 3 UI execution, 2026-06-13:

* Added typed frontend API methods for `registry_audience_groups` CRUD, member replacement and member preview under `webapp/src/features/admin/api.ts`.
* Added `/app/admin/registry` tab `Аудитории · P1` backed by the Phase 2 `/api/web/admin/registry/audience-groups*` routes. The first slice supports group create/update/archive, member editor, department-tree/person/department/location/role/service member selection, required reason, preview-before-save and preview counts/warnings.
* Replaced the known `window.prompt` operator paths in `webapp/src/pages/admin/registry-page.tsx` and `webapp/src/features/admin/registry/registry-quality-tab.tsx` with dialogs:
  * bulk device/person/session actions use `RegistryBulkActionDialog` with searchable department/location pickers, reason, server preview and normalized apply report;
  * UI-user linking uses `RegistryLinkUiUserDialog` with an unlinked-account picker and reason;
  * quality ignore/snooze/resolve and other reason-only actions use `RegistryReasonDialog`;
  * bind-person-to-known-device preselects the person in `RegistryBindPersonDialog` instead of asking for a raw device id through prompt.
* Added `webapp/src/pages/admin/registry-page.test.tsx` to guard no `window.prompt`, searchable bulk picker preview/apply behavior and the audience-group editor path.
* Current local verification for this slice:
  * `pnpm --dir webapp exec vitest run src/pages/admin/registry-page.test.tsx --reporter=dot`
  * `pnpm --dir webapp exec tsc --noEmit --pretty false`
  * `rg -n "window\.prompt|prompt\(" webapp\src\pages\admin\registry-page.tsx webapp\src\features\admin\registry`
* Phase 3 verification and evidence completed after the initial local slice:
  * focused Registry vitest suite, registry backend pytest, docs drift/link checks, webapp typecheck, webapp build, `python scripts/verify_workspace.py` and `git diff --check` passed before commit `3fb13ea8`;
  * quick stand deploy applied migration `120` and uploaded the webapp bundle for browser validation;
  * browser evidence under `artifacts/browser_live_validation/registry-phase3-3fb13ea8-20260613/` confirms no horizontal body scroll and no captured console/network errors on the checked Registry paths;
  * checked flows: Registry overview, `Аудитории · P1` empty/create/preview/save/archive, device bulk dialog reason/preview controls, people tab UI-account linking controls.
* Phase 3 access-groups addendum completed at commit `6204c749`:
  * added `webapp/src/features/admin/registry/registry-access-groups-tab.tsx`;
  * added `/app/admin/registry` tab `Группы доступа · P1` that reads `fetchAccessSummary` / `/api/web/admin/access/summary`;
  * the tab is read-only and links to `/app/admin/access`; it must not create/update permissions, members or queue grants.
* Phase 3 access-groups addendum verification, 2026-06-13:
  * `python scripts/release_server_to_remote.py --gate quick --allow-local-dirty --leave-running --smoke-insecure-tls` deployed commit `6204c749` to the canonical stand; smoke passed on attempt 2;
  * browser evidence is under `artifacts/browser_live_validation/registry-access-groups-6204c749-20260613/`;
  * checked `Группы доступа · P1` at 1366x768 and 1920x1080: read-only summary rendered, `/api/web/admin/access/summary` returned 200, deep link points to `/app/admin/access`, no horizontal body scroll, captured console warnings/errors = 0, captured non-static network failures = 0.
* Remaining Phase 3 work before exit:
  * none for the Registry UI access-groups addendum;
  * proceed to Phase 4 only after confirming no newer operator expectation changes the canonical RBAC-editor decision.

---

## Phase 4 — Registration policy hardening and agent/browser registration flow

Goal:

Make registration collect clean registry data.
Ensure department/location policies are visible, configurable and enforced.
Verify with a real connected agent and account-session flow.

Policy UI:

Expose in /app/admin/registry policies tab:

registration.department_mode
allow_pending_request
optional
required_existing
registration.location_mode
allow_pending_request
optional
required_existing

Russian labels:

Подразделение при регистрации
Локация при регистрации
Разрешить свободный ввод с последующей проверкой
Необязательно, но выбирать из реестра
Обязательно выбрать из реестра

Backend enforcement:

If department_mode=required_existing, registration claim must contain valid department_id.
If location_mode=required_existing, registration claim must contain valid location_id.
Free-text department, building, floor, room must be treated as pending data-quality input, not silently creating duplicates when policy requires existing registry objects.
Admin approval must show a diff:
existing person/device/binding;
claimed department/location;
proposed person identity;
proposed binding type;
conflicts/blockers.
Approval must update:
person identity;
person primary department/location where applicable;
device binding;
asset/inventory derived fields;
registration/account-session state.

Agent/browser live flow:

Agent creates browser pairing for registration/login.
Browser registration confirms as web-authenticated user where applicable.
Agent polls pairing result and account state.
Pending registration session must not open normal ticket workspace.
After admin approval, agent must show confirmed account login/confirmed binding state.
Ticket create/list must use valid account session.

TDD checkpoints:

RED backend test for department_mode=required_existing.
RED backend test for location_mode=required_existing.
RED backend test that free text is not accepted as valid existing department/location in required mode.
RED backend test approval updates person department/location and binding.
RED backend test pending registration session invalidates after approval/reject.
RED webapp test for policy UI fields.
RED webapp test for approval diff.
RED agent/API test for account gate behavior if existing pc_agent test patterns support it.

Phase 4 execution, 2026-06-13:

* First implemented slice: `/app/admin/registry` -> `Заявки` now shows a compact approval diff for every registration claim before admin actions.
* Diff source stays read-only from the existing `/api/web/admin/registry` payload; no new route or mutation contract was added.
* The diff shows existing device/binding context, claimed person, claimed department/location labels, proposed identity, proposed binding type and conflict/blocker reason.
* Guard test: `webapp/src/pages/admin/registry-page.test.tsx` / `shows an approval diff for registration claims before admin actions`.
* Local verification so far:
  * RED: `pnpm --dir webapp exec vitest run src/pages/admin/registry-page.test.tsx --reporter=dot` failed on missing `Дифф подтверждения`.
  * GREEN: `pnpm --dir webapp exec vitest run src/pages/admin/registry-page.test.tsx --reporter=dot` passed 5 tests.
  * Focused: `pnpm --dir webapp exec vitest run src/pages/admin/registry-page.test.tsx src/features/admin/registry/registry-requests-tab.test.ts --reporter=dot` passed 8 tests.
  * `pnpm --dir webapp exec tsc --noEmit --pretty false` passed.
  * `python scripts/docs_drift_check.py`, `python scripts/docs_inventory.py --check-links`, `python -m pytest scripts/test_navigation_catalog.py scripts/test_task_intake.py scripts/test_docs_drift_check.py -q`, `pnpm --dir webapp build` and `python scripts/verify_workspace.py` passed after `scripts/navigation_catalog.py` was updated with Phase 4 routing context.
  * Quick stand deploy: `python scripts/release_server_to_remote.py --gate quick --allow-local-dirty --leave-running --smoke-insecure-tls` deployed commit `4b61b225`; `/api/health` smoke returned 200 on the second retry.
  * Browser evidence on `https://192.168.100.17:9443/admin` -> `/app/admin/registry` -> `Заявки`: 22 live diff blocks found at 1920x1080 and 1366x768, no body horizontal scroll, console warnings/errors 0, non-static network requests 200. Screenshots and console/network JSON are under `artifacts/browser_live_validation/registry-approval-diff-4b61b225-20260613/`.
* Remaining Phase 4 work:
  * expose first-class `department_mode` / `location_mode` controls in the Registry policies tab if the current UI still lacks them;
  * add/verify explicit backend tests for strict department/location enforcement and approval update side effects under the Phase 4 command names;
  * run the real connected agent registration scenarios before Phase 4 exit.

Verification:

python -m pytest server/tests/test_registry_registration_policy.py
python -m pytest server/tests/test_registration_api.py
python -m pytest server/tests/test_browser_pairing_service.py
python -m pytest server/tests/test_registry_people_admin.py
pnpm --dir webapp exec vitest run src/features/admin/registry/registry-policies-tab.test.tsx --reporter=dot
pnpm --dir webapp exec vitest run src/features/admin/registry/registry-requests-tab.test.tsx --reporter=dot
python -m compileall -q server shared scripts pc_agent
pnpm --dir webapp build
git diff --check

Live checks with real agent:

Prerequisites:

Server running on the live/dev stand.
One Windows agent connected through WebSocket.
Optional second ALT Linux agent if available.
Admin web session available.
At least one test UI user available.
Test departments and locations created in Registry.

Scenario A — clean new device registration:

Set:
department_mode=required_existing
location_mode=required_existing
Start agent on an unregistered or test-reset device.
Open agent account gate.
Start registration through browser pairing.
Select existing department and location.
Submit registration.
Confirm in admin /app/admin/registry that claim is pending.
Open claim diff.
Approve claim.
Agent polls and leaves pending state.
Login/select confirmed binding account session.
Create a test ticket from agent.
Verify ticket stores:
requester_person_id
requester_binding_id
requester_account_session_id
requester_registration_status
Verify support UI sees requester context.

Scenario B — blocked bad registration:

Keep department_mode=required_existing.
Try submitting free-text or invalid department.
Verify backend returns validation error.
Verify no person/binding is created.
Verify user-visible error is Russian and safe.
Verify observer/quality event if implemented.

Scenario C — other-account session safety:

Device has confirmed owner.
Login/request another account from agent.
Admin approves other-account request.
Agent receives verified other-account session.
Create ticket.
Verify:
device binding did not change;
owner historical ticket is not visible to other-account session;
support UI shows other-account warning.

Evidence:

Save screenshots:
agent account gate before registration;
browser pairing page;
admin pending registration claim;
approval diff;
agent confirmed account state;
created ticket in support UI.
Save sanitized API/evidence JSON:
no raw account-session token;
no machine token;
no pairing token/code after create response.
Record exact commands and environment in PLANS.md.

Exit criteria:

Required-existing department/location policy works.
Agent registration live scenario passes.
Pending session cannot access normal workspace.
Approval updates registry and account-session state.
Other-account login does not transfer ownership.

---

## Phase 5 — Knowledge audience rules and ACL enforcement

Goal:

Add production knowledge visibility rules using Registry effective identity and audience groups.
Ensure search, article view, suggestions and future RAG use the same authorization boundary.

Backend schema:

Add migration:

knowledge_audience_rules
rule_id
subject_type: space, item
subject_id
effect: allow, optional deny
target_type: role, person, department, department_tree, location, access_group, audience_group, service
target_id
priority
status: active, disabled
reason
metadata_json
created_at, updated_at, created_by, updated_by

Optional audit table if no existing knowledge access audit can be reused:

knowledge_access_decisions
decision_id
actor_id
actor_role
person_id
item_id
space_id
decision: allowed, denied
reason_code
explain_json
created_at

Backend service:

Add:

server/knowledge/access_service.py
server/knowledge/audience_rules_service.py

Required methods:

can_view_space(actor_context, space) -> AccessDecision
can_view_item(actor_context, item) -> AccessDecision
filter_visible_items(actor_context, items) -> list
explain_knowledge_access(actor_context, item_id) -> dict

Decision order:

Actor role/authenticated state.
Space lifecycle/status.
Item status/current version.
Coarse visibility.
Audience rules from space.
Audience rules from item.
Explicit support/admin policy override only if intended.
Return decision + explain.

Rules:

Published requester-safe items can still be hidden by audience rules if scoped.
Support/internal items must not become requester-visible through audience rules.
Admin can inspect rules, but normal requester APIs must not leak hidden item metadata.
Search result counts must not reveal hidden records unless admin diagnostics endpoint is used.
RAG/vector/hybrid search must receive only authorized candidate item/chunk IDs.

APIs:

Add admin APIs:

GET /api/web/admin/knowledge/audience-rules?subject_type=&subject_id=
PUT /api/web/admin/knowledge/audience-rules
POST /api/web/admin/knowledge/audience-rules/preview
GET /api/web/admin/knowledge/access/explain?actor_id=&item_id=

Add requester/support enforcement to existing knowledge endpoints:

article list
article detail
search
suggestions
Ask/RAG candidate retrieval
ticket knowledge suggestions
public help/deflection where relevant

TDD checkpoints:

RED test: requester sees article with matching department rule.
RED test: requester does not see article from another department.
RED test: requester cannot infer hidden article through search count/title/summary.
RED test: support_internal item not exposed to requester even if audience rule matches.
RED test: admin explain returns matched rule.
RED test: access group target works.
RED test: audience group target works.
RED test: department_tree target includes child departments.
RED test: item rule can narrow/extend space rule according to documented precedence.
RED test: RAG/search candidate selection filters unauthorized items before semantic ranking.
RED test: chunks inherit item authorization and do not leak hidden text.

Verification:

python -m pytest server/tests/test_knowledge_audience_rules.py
python -m pytest server/tests/test_knowledge_access_service.py
python -m pytest server/tests/test_knowledge_search_acl.py
python -m pytest server/tests/test_knowledge_rag_acl.py
Existing focused knowledge tests.
python -m compileall -q server shared scripts
git diff --check

Live checks:

Create two departments:
ИТО
Бухгалтерия
Create/link two users:
user A in ИТО
user B in Бухгалтерия
Create knowledge items:
Публичная инструкция
Инструкция для ИТО
Инструкция для бухгалтерии
Support internal runbook
Add rules:
item visible to department_tree=ИТО
item visible to department_tree=Бухгалтерия
item visible to audience_group=finance_staff
Login as user A:
sees public + ИТО item;
does not see бухгалтерия item;
does not see support internal runbook.
Login as user B:
sees public + бухгалтерия item;
does not see ИТО item.
Login as support:
sees requester-safe items where support is allowed;
sees support_internal runbook in support/admin context.
Run search for title terms of hidden article:
no result;
no hidden metadata in network response.
Run admin explain:
allowed case shows matched rule;
denied case shows no matching rule or blocked coarse visibility.
Save evidence:
requester search screenshots;
article detail screenshots;
network JSON with hidden fields absent;
admin explain screenshot/JSON.

Exit criteria:

Knowledge visibility rules enforce real access control.
Search/suggestions/RAG candidates do not leak hidden content.
Explain endpoint makes decisions debuggable.

---

## Phase 6 — Knowledge authoring UI visibility selector

Goal:

Let admins/authors configure article and space visibility without raw JSON.
Provide preview/explain before publishing or changing scoped articles.

UI changes:

In /app/admin/knowledge/studio metadata/visibility step:

Add Область видимости panel.
Show current coarse visibility.
Show audience rules:
role
person
department
department tree
location
access group
audience group
service
Add searchable pickers from Registry.
Add preview button:
estimated visible people count;
matched departments/groups;
warnings for broad/narrow rules;
blocked states.
Add test access field:
choose user/person;
show Можно видеть / Скрыто;
show explanation.

In /app/admin/knowledge or dedicated route:

Add visibility audit/debug view:
articles with no audience rules;
requester-visible articles scoped to nobody;
broad rules such as all users;
support_internal with requester-facing rules that are ignored/blocked.

Russian UI labels:

Область видимости
Кто увидит статью
Подразделение
Подразделение и дочерние
Группа доступа
Аудитория
Проверить доступ
Причина решения
Эта статья не будет видна выбранному пользователю

TDD checkpoints:

RED webapp test for visibility selector.
RED webapp test for department tree picker.
RED webapp test for audience group picker.
RED webapp test for access preview.
RED webapp test for support_internal cannot be made requester-visible accidentally.
RED webapp test for Russian labels/no mojibake.
RED webapp test for saved rules round-trip.

Verification:

pnpm --dir webapp exec vitest run src/features/knowledge/article-visibility-panel.test.tsx --reporter=dot
pnpm --dir webapp exec vitest run src/pages/admin/knowledge-studio-page.test.tsx --reporter=dot
pnpm --dir webapp exec tsc --noEmit --pretty false
pnpm --dir webapp build
git diff --check

Live checks:

Open /app/admin/knowledge/studio.
Select or create article.
Open metadata/visibility step.
Add department-tree rule.
Preview visible audience.
Test access for user from matching department.
Test access for user from different department.
Save rules.
Reopen article and verify rules persisted.
Publish article if publishing flow is safe.
Verify requester portal/search reflects the rule.
Browser evidence:
Studio visibility panel 1366x768 and 1920x1080;
preview modal/drawer;
test access allowed/denied;
requester visible/hidden result.

Exit criteria:

Admin can configure scoped article visibility without raw JSON.
Preview and test-access explain are available.
Rules persist and affect real requester search/view.

---

## Phase 7 — Agent/requester/support end-to-end visibility signoff

Goal:

Verify that registry identity, registration, account sessions and knowledge visibility work end-to-end with the actual agent flow.

Live script:

Add or update:

scripts/registry_visibility_live_smoke.py

Required capabilities:

Create deterministic test departments/locations/people/audience groups.
Create or identify test UI users.
Create knowledge spaces/items and audience rules.
Use admin APIs for setup and cleanup where safe.
Use real HTTP APIs for requester/support/admin checks.
Use agent endpoints/account-session validation where possible.
Never print raw tokens.
Emit sanitized JSON report under artifacts/registry-visibility-foundation-YYYYMMDD/.

Agent live matrix:

Scenario 1 — registered owner sees department knowledge:

Device has confirmed primary binding to person A.
Person A belongs to ИТО.
Agent starts account gate.
User logs in/selects confirmed account session.
Agent/user opens knowledge/search/suggestions.
ИТО article appears.
Бухгалтерия article does not appear.
Create ticket from agent.
Support ticket detail shows correct requester registry context.

Scenario 2 — verified other-account sees only own scoped context:

Device owner is person A.
Other user/person B requests other-account session.
Admin approves.
Agent receives verified other-account session.
Knowledge visibility is based on person B/session identity, not device owner A.
Owner A historical tickets remain hidden.
Ticket created from B stores other-account warning.

Scenario 3 — pending registration has no normal workspace:

Device has no confirmed binding.
User submits registration.
Agent receives registration_pending session/state.
Knowledge/ticket normal workspace remains blocked.
Admin approves.
Agent can login/select confirmed binding.
Knowledge visibility starts working from approved person.

Scenario 4 — revoked session/binding loses access:

User has valid account session.
Admin revokes account session or binding.
Agent detects invalid session.
Knowledge/ticket actions are blocked.
Browser/API access with old session fails.

Verification commands:

python scripts/registry_visibility_live_smoke.py --base-url <stand-url> --insecure-tls
python scripts/registry_workflow_smoke.py --base-url <stand-url> --insecure-tls
Focused pytest/vitest from previous phases.
python scripts/verify_workspace.py if available and still valid.

Evidence requirements:

Save screenshots:
agent account gate;
agent confirmed account state;
registration pending state;
admin registry person/device/claim;
knowledge search visible case;
knowledge search hidden case;
support ticket requester context.
Save sanitized network/console logs:
no raw tokens;
no hidden article metadata;
no browser console errors.
Update PLANS.md with:
exact date/time;
stand URL;
commit SHA;
commands run;
tests passed;
evidence file paths;
known limitations.

Exit criteria:

Real agent live checks pass for registered owner and pending registration.
Other-account ownership boundary is preserved.
Knowledge visibility follows account-session/person identity, not machine token.
Revoked sessions lose access.
Evidence is recorded.

---

## Phase 8 — Observer, quality issues, import/export and final product signoff

Goal:

Make Registry Visibility Foundation operable in production.
Surface broken identity/visibility data as quality issues.
Add import/export where needed without unsafe direct binding imports.

Observer events:

Emit observer events/metrics where existing observer patterns allow:

registry.identity.unlinked_ui_user
registry.identity.identity_collision
registry.audience.empty_group
registry.audience.member_resolution_failed
knowledge.visibility.rule_invalid
knowledge.visibility.denied_unexpected
knowledge.visibility.hidden_result_filtered
registration.policy.blocked_missing_department
registration.policy.blocked_missing_location

Quality issues:

Add generated data-quality issues:

UI user without linked RegistryPerson.
RegistryPerson without verified identity.
Person with archived department/location.
Audience group with zero effective members.
Knowledge item requester-visible but scoped to zero users.
Knowledge item has invalid/deleted department/group/location rule.
Device has active binding to inactive person.
Pending registration claim expired or blocked by missing required registry fields.

Import/export:

Extend existing registry import/export safely:

Export:
people with department/location/audience summary;
departments;
locations;
audience groups;
audience group members;
knowledge audience rules.
Import:
audience groups;
audience group members;
optional person department memberships if implemented.
Do not import direct device bindings.
Do not import account sessions.
Import must be preview/apply with row-level errors, duplicate detection and reason.

TDD checkpoints:

RED test for observer event emission.
RED test for quality issue generation.
RED test for audience group export CSV.
RED test for audience group import preview/apply.
RED test for knowledge audience rules export.
RED test for invalid rule quality issue.
RED webapp test for quality remediation actions.

Verification:

python -m pytest server/tests/test_registry_visibility_quality.py
python -m pytest server/tests/test_registry_audience_import_export.py
python -m pytest server/tests/test_knowledge_visibility_observer.py
pnpm --dir webapp exec vitest run src/features/admin/registry/registry-quality-tab.test.tsx --reporter=dot
python -m compileall -q server shared scripts
pnpm --dir webapp build
git diff --check

Live checks:

Create invalid states intentionally on test data:
unlinked UI user;
audience group with missing department;
knowledge rule referencing archived department;
requester-visible item scoped to zero users.
Open /app/admin/registry quality tab.
Verify quality issues appear.
Fix issues through UI where remediation exists.
Open observer/admin tech surfaces and verify events/metrics if available.
Export/import audience groups through UI/API.
Confirm CSV formula injection escaping remains safe for exported reports.
Save evidence:
quality tab before/after;
observer events;
import preview;
import apply report;
exported CSV sample with sensitive data reviewed.

Exit criteria:

Production operators can find and fix broken registry/visibility data.
Observer shows meaningful visibility/identity failures.
Import/export does not bypass registration/binding safety.
Final live signoff is recorded in PLANS.md.

---

## Final signoff checklist

Backend:

Effective identity resolver implemented.
Audience groups implemented.
Knowledge audience rules implemented.
Registration department/location policy enforced.
Knowledge search/view/suggestions/RAG candidates are ACL-first.
Explain/debug endpoints implemented.
Observer/quality issues implemented.
Import/export safe.

Frontend:

/app/admin/registry production UI has no raw-ID prompt workflows in normal paths.
UI users can be linked to RegistryPerson.
Audience groups can be managed.
Registry policies expose department/location modes.
Knowledge Studio has visibility selector and test-access explain.
Requester/support/admin visible text is Russian-first.
No mojibake.

Agent/live:

Real agent registration pending flow verified.
Real confirmed binding account-session flow verified.
Real other-account flow verified.
Revoked session/binding access loss verified.
Knowledge visibility follows account session/person identity.
Hidden article metadata does not leak through agent/requester search or suggestions.

Security:

No requester identity inferred from agent machine token.
No hidden KB content in search/RAG/network payloads.
No raw account-session tokens in logs/screenshots.
Admin explain endpoints are admin-only.
Dangerous operations require reason and audit.

## Required final commands

python -m compileall -q server shared scripts pc_agent
python -m pytest server/tests/test_registry_effective_identity_service.py
python -m pytest server/tests/test_registry_audience_groups.py
python -m pytest server/tests/test_registry_registration_policy.py
python -m pytest server/tests/test_knowledge_audience_rules.py
python -m pytest server/tests/test_knowledge_access_service.py
python -m pytest server/tests/test_knowledge_search_acl.py
python -m pytest server/tests/test_registry_visibility_quality.py
pnpm --dir webapp exec tsc --noEmit --pretty false
pnpm --dir webapp test -- --reporter=dot
pnpm --dir webapp build
git diff --check

## Required final live commands

python scripts/registry_workflow_smoke.py --base-url <stand-url> --insecure-tls
python scripts/registry_visibility_live_smoke.py --base-url <stand-url> --insecure-tls

## Final exit criteria

All focused tests pass.
Webapp build passes.
Live agent checks are recorded with evidence.
PLANS.md, REGISTRY_MANAGEMENT_CENTER.md, REGISTRY_VISIBILITY_FOUNDATION.md, KNOWLEDGE_OPERATIONS.md, CODEMAP.md and QUICK_LOOKUP.md are updated.
No unresolved security blockers.
Any remaining follow-up is explicitly documented as non-blocking with reason.
