## Active Work: Registry Visibility Foundation — Production Registry, Registration and Knowledge Audience Scopes

Status: active implementation. Phase 0 architecture/docs contract, Phase 1 backend resolver/API slice and Phase 2 backend audience-group slice completed on 2026-06-13. Phase 3 production Registry UI slice is implemented at local commits `3fb13ea8` (`server: add registry visibility foundation`) and `6204c749` (`webapp: add registry access groups summary`): prompt-free bulk/quality/link dialogs, audience-group management and read-only `Группы доступа · P1` discovery are added, deployed through the quick stand path, and browser evidence is recorded under `artifacts/browser_live_validation/registry-phase3-3fb13ea8-20260613/` plus `artifacts/browser_live_validation/registry-access-groups-6204c749-20260613/`. The remaining Phase 3 `Группы доступа` decision is resolved as a read-only Registry summary/deep link over the canonical `/app/admin/access` RBAC editor. Phase 4 registration hardening is in progress: the admin approval diff UI slice is implemented at local/remote commit `4b61b225` (`webapp: show registry registration approval diff`), quick-deployed to the canonical stand and browser evidence is recorded under `artifacts/browser_live_validation/registry-approval-diff-4b61b225-20260613/`; the registration policy mode UI slice is implemented at local/remote commit `a8f8e81d` (`webapp: expose registry policy modes`), quick-deployed to the canonical stand and browser evidence is recorded under `artifacts/browser_live_validation/registry-policy-modes-a8f8e81d-20260613/`; the backend enforcement/approval side-effect slice now has explicit `server/tests/test_registry_registration_policy.py` coverage and applies strict approved department/location ids to verified existing people before derived asset/inventory sync; the strict browser-registration payload/cookie-bridge slice is implemented and quick-deployed at `d8207ff3` / `e15918fa`. Phase 4 strict Scenario A live evidence was captured on 2026-06-14 under `artifacts/browser_live_validation/phase4-agent-20260614-4ca9a116/`; Scenario B now has negative strict API/DB and browser-pending evidence under `artifacts/browser_live_validation/phase4-invalid-20260614-4ca9a11/`, plus post-fix canonical stand safe-visible-error and no-side-effect evidence under `artifacts/browser_live_validation/phase4-invalid-20260614-b675d99/`. Scenario C other-account safety, Phase 5+ Knowledge audience-rule enforcement and final operability hardening remain open.

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

Plan context refresh, 2026-06-14:

* `python scripts/build_context_pack.py --topic "registry visibility foundation phase 4 strict registration scenario b scenario c knowledge audience"` classified the remaining work as Registry / Assets with `registry_objects`, `knowledge_platform` and `web_platform` context. Keep the next implementation step scoped to one open scenario or one Knowledge ACL slice; do not mix live registration evidence with Knowledge schema/API changes in the same checkpoint unless the user explicitly asks for a combined release gate.
* `python scripts/build_context_index.py --force` rebuilt the local context index after `PLANS.md` changed: 21,432 items, 1,523 chunks, 847 routes, 16,977 symbols and 2,061 tests. If later context search reports `PLANS.md` stale again, rebuild before using search output as a handoff source.
* Current high-signal route/doc anchors for the next work are `POST /api/web/registry/browser-pairings/{pairing_id}/registration/confirm`, `POST /api/registry/agent/account-login-requests`, `GET|POST /api/web/admin/registry/account-login-requests/*`, `server/docs/REGISTRATION_ACCOUNT_SESSIONS.md`, `server/docs/REGISTRY_VISIBILITY_FOUNDATION.md` and `docs/LIVE_TESTING_DEBUG_RULES.md`.
* For docs-only plan/context edits, verification should stay local (`python scripts/verify_workspace.py`, `git diff --check`) and should not deploy, start agents or leave remote services running. For any subsequent live scenario, use project runtime/deploy scripts only and record final service state.
* Latest docs-only context refresh for this PLANS.md update used `python scripts/build_context_pack.py --topic "PLANS Phase 4 Scenario B device registration strict registry ids safe Russian error live validation"` and `python scripts/search_context_index.py "Phase 4 Scenario B device registration strict registry ids safe Russian error account session live validation" --profile debug`. The useful anchors stayed concentrated in Phase 4 registration, `docs/LIVE_TESTING_DEBUG_RULES.md`, `server/registry/registration_service.py`, `server/registry/browser_pairing_service.py`, `server/auth/middleware.py`, `webapp/src/pages/device-pairing/api.ts`, `webapp/src/pages/device-pairing/index.tsx` and `webapp/src/pages/device-pairing/device-pairing-page.test.tsx`.
* The context index was rebuilt again after stale warnings from current plan/webapp edits: 21,438 items, 1,523 chunks, 847 routes, 16,983 symbols and 2,061 tests. Treat future stale-index warnings as a stop-and-rebuild signal before relying on search output for handoff decisions.
* Current workspace hygiene for the next handoff: `PLANS.md`, `webapp/src/pages/device-pairing/api.ts` and `webapp/src/pages/device-pairing/device-pairing-page.test.tsx` belong to the active Scenario B UI/error-mapping checkpoint; `.codex/config.toml`, `pc_agent/ui_gui/tickets_list_model.py` and `scripts/live_agent_uia_state_probe.py` are unrelated dirty tracked files and must not be staged or reverted as part of this plan-context update.

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
* Second implemented local slice: `/app/admin/registry` -> `Политики · P1` now exposes first-class `Режим подразделения` and `Режим локации` select controls backed by the existing policy enum values `allow_pending_request`, `optional` and `required_existing`.
* Policy-control source stays on the existing Registry policy endpoints; no backend route or validation contract was added. Saving sends the selected modes through the existing `PATCH /api/web/admin/registry/policies` reason-gated path, and preview uses the existing dry-run endpoint.
* Guard test: `webapp/src/pages/admin/registry-page.test.tsx` / `exposes department and location modes as first-class registration policy controls`.
* Local verification so far:
  * RED: `pnpm --dir webapp exec vitest run src/pages/admin/registry-page.test.tsx --reporter=dot` failed on missing `Дифф подтверждения`.
  * GREEN: `pnpm --dir webapp exec vitest run src/pages/admin/registry-page.test.tsx --reporter=dot` passed 5 tests.
  * Focused: `pnpm --dir webapp exec vitest run src/pages/admin/registry-page.test.tsx src/features/admin/registry/registry-requests-tab.test.ts --reporter=dot` passed 8 tests.
  * `pnpm --dir webapp exec tsc --noEmit --pretty false` passed.
  * `python scripts/docs_drift_check.py`, `python scripts/docs_inventory.py --check-links`, `python -m pytest scripts/test_navigation_catalog.py scripts/test_task_intake.py scripts/test_docs_drift_check.py -q`, `pnpm --dir webapp build` and `python scripts/verify_workspace.py` passed after `scripts/navigation_catalog.py` was updated with Phase 4 routing context.
  * Quick stand deploy: `python scripts/release_server_to_remote.py --gate quick --allow-local-dirty --leave-running --smoke-insecure-tls` deployed commit `4b61b225`; `/api/health` smoke returned 200 on the second retry.
  * Browser evidence on `https://192.168.100.17:9443/admin` -> `/app/admin/registry` -> `Заявки`: 22 live diff blocks found at 1920x1080 and 1366x768, no body horizontal scroll, console warnings/errors 0, non-static network requests 200. Screenshots and console/network JSON are under `artifacts/browser_live_validation/registry-approval-diff-4b61b225-20260613/`.
  * RED: `pnpm --dir webapp exec vitest run src/pages/admin/registry-page.test.tsx --reporter=dot` failed on missing `Режим подразделения`.
  * GREEN after policy controls: `pnpm --dir webapp exec vitest run src/pages/admin/registry-page.test.tsx --reporter=dot` passed 6 tests.
  * Focused after policy controls: `pnpm --dir webapp exec vitest run src/pages/admin/registry-page.test.tsx src/features/admin/registry/registry-requests-tab.test.ts --reporter=dot` passed 9 tests.
  * `pnpm --dir webapp exec tsc --noEmit --pretty false` passed after adding the policy enum fields to `AdminRegistryPolicyPayload`.
  * Backend anchor after policy controls: `python -m pytest server/tests/test_registry_policies_admin.py::test_registry_policy_api_reads_defaults_and_rejects_invalid_values -q` passed in 396.68s.
  * Docs/navigation after policy controls: `python scripts/docs_drift_check.py`, `python -m pytest scripts/test_navigation_catalog.py scripts/test_task_intake.py scripts/test_docs_drift_check.py -q`, `python scripts/docs_inventory.py --check-links`, `pnpm --dir webapp build`, `python scripts/verify_workspace.py` and `git diff --check` passed before commit `a8f8e81d`.
  * Quick stand deploy after policy controls: `python scripts/release_server_to_remote.py --gate quick --allow-local-dirty --leave-running --smoke-insecure-tls` deployed commit `a8f8e81d`; `/api/health` smoke returned 200 on the second retry.
  * Browser evidence on `https://192.168.100.17:9443/admin` -> `/app/admin/registry` -> `Политики · P1`: `Режим подразделения` and `Режим локации` controls rendered with `allow_pending_request`, `optional` and `required_existing` options; preview changed form values to `department_mode=required_existing` and `location_mode=optional`; visible `Server dry-run` confirmed the existing preview endpoint without saving. 1920x1080 and 1366x900 checks had no body horizontal scroll and console warnings/errors = 0. CDP network capture was unavailable for this Browser tab, so the preview backend hit is corroborated by the remote server log entry for `/api/web/admin/registry/policies/preview`; screenshots, snapshot and console JSON are under `artifacts/browser_live_validation/registry-policy-modes-a8f8e81d-20260613/`.
  * Backend enforcement/approval side-effect slice: added `server/tests/test_registry_registration_policy.py`; RED showed approval left `approved["person"]["department_id"]` as `None` for a verified existing person submitting strict registry ids, then `RegistrationService.approve_claim()` was updated to apply validated claim `department_id` / `location_id` to the person before binding payload and derived asset/inventory sync.
  * Backend verification after this slice: `python -m pytest server/tests/test_registry_registration_policy.py -q` passed 2 tests; `python -m pytest server/tests/test_device_registration_service.py::test_admin_approve_claim_creates_active_binding_and_updates_asset_inventory server/tests/test_device_registration_service.py::test_strict_registration_policy_uses_existing_department_location_pickers server/tests/test_account_session_service.py::test_registration_pending_session_is_revoked_when_claim_is_approved -q` passed 3 tests.
* Remaining Phase 4 work:
  * run the real connected agent registration scenarios before Phase 4 exit.

Phase 4 live-agent handoff context, 2026-06-14:

* `scripts/registry_workflow_smoke.py` is useful preflight/support evidence for Registry Management Center invariants: it drives admin/agent HTTP APIs, issues short-lived admin/agent tokens through `AuthService`, and verifies DB-side person/binding/account-session/ticket-access invariants. It does not replace the Phase 4 exit requirement because it does not prove the real Windows agent GUI, WebSocket runtime, browser pairing pages or UIA-visible account gate transitions.
* Canonical live stand/browser target remains `https://192.168.100.17:9443/admin`. Browser-visible evidence must use the real admin/requester/support UI paths (`/app/admin/registry`, `/app/device/login`, `/app/device/register`, `/app/device/pair` where applicable), not only direct HTTP/DB checks.
* Use a named isolated Windows agent instance for the live run, for example `phase4-reg-<run_id>`, through `python scripts/manage_local_agent.py ...`; do not reuse a real user's daily agent state or manually patch the Linux/SMB mirrors.
* Use one clean run marker across every object and artifact, for example `phase4-agent-YYYYMMDD-<short_sha>` in reason strings, test department/location/person names, ticket title/description and evidence filenames. DB/API/browser checks must filter by that marker rather than old rows.
* Record policy state before changing `registration.department_mode` / `registration.location_mode`, set both to `required_existing` for Scenario A/B, and restore or explicitly record the final policy state at cleanup. Do not leave strict test policy active silently on a shared stand.
* Treat `scripts/registry_workflow_smoke.py --base-url https://192.168.100.17:9443 --insecure-tls` as an optional preflight for registry side effects before the real agent run. A green smoke can shorten diagnosis, but Phase 4 is still blocked until the real agent/browser/UIA evidence is captured.
* Required Phase 4 pass evidence follows `docs/LIVE_TESTING_DEBUG_RULES.md` no-single-signal rule:
  * transport/API: registration form policy fields, browser-pairing create/poll/confirm responses, account-state and account-session validate responses;
  * server DB: `device_registration_claims`, `device_user_bindings`, `device_account_sessions`, derived inventory/asset rows and created ticket requester fields;
  * agent local state: UIA account gate / account page / ticket create state from `scripts/live_agent_uia_state_probe.py` or a tighter UIA probe if needed;
  * browser/UI: admin pending claim, approval diff, support ticket requester context and any requester/device pairing page used in the scenario;
  * logs/action trace: server and agent logs around the run marker, with auth/account-session validation errors classified instead of ignored.
* Sanitization is a hard condition: evidence may contain safe ids, token lengths, safe prefixes or hashes, but must not contain raw account-session tokens, machine tokens, cookies, auth headers, private keys, browser-pairing tokens or manual pairing codes after the one-time create/entry moment.
* Stop rather than substituting evidence if the real agent is not connected through WebSocket, the account gate is not UIA-readable, or a browser-visible step cannot be confirmed in the browser. Record the blocker and layer (`agent`, `UIA`, `browser`, `API`, `DB`, `test contamination`) in this plan before patching or rerunning.
* Cleanup expectations: revoke/expire test account sessions when possible, leave test registry objects identifiable by run marker, stop the isolated local agent and stop remote services unless the user explicitly asks to leave them running.
* Suggested execution order for the next Phase 4 run:
  1. `git status -sb`, capture current commit SHA and run `python scripts/verify_workspace.py`.
  2. Deploy/sync only through project scripts if the stand is not already on the target commit; start remote services through project runtime scripts and stop them at the end.
  3. Create the run marker and test CMDB objects/users, then optionally run `python scripts/registry_workflow_smoke.py --base-url https://192.168.100.17:9443 --insecure-tls`.
  4. Start the isolated agent, verify connection/account gate via UIA, and collect pre-registration account-state evidence.
  5. Execute Scenario A and Scenario B with strict department/location policies, then Scenario C on a confirmed binding.
  6. Capture browser, API, DB, UIA and log evidence under `artifacts/browser_live_validation/registry-phase4-agent-<short_sha>-YYYYMMDD/` or a sibling run-specific folder.
  7. Restore policy/cleanup, stop services, update this Phase 4 block with exact commands, artifact paths and remaining limitations.

Phase 4 partial live/preflight execution, 2026-06-14:

* Refreshed routing state before the live attempt: `python scripts/build_context_index.py --force` rebuilt 21,424 items, 847 routes, 16,970 symbols and 2,060 tests; `python scripts/verify_workspace.py` passed before deploying.
* Quick-deployed committed SHA `ba41cce8aebe7a5bfe9681f3fe5f8cdbb4484250` to `https://192.168.100.17:9443` with `python scripts/release_server_to_remote.py --gate quick --allow-local-dirty --leave-running --smoke-base-url https://192.168.100.17:9443 --smoke-insecure-tls`; remote `/api/health` smoke returned 200 on attempt 2. Full CI/full gate was not requested.
* Local Windows `python scripts/registry_workflow_smoke.py --base-url https://192.168.100.17:9443 --insecure-tls --run-id phase4-preflight-20260614-ba41cce8` failed before HTTP assertions because local `DATABASE_URL` resolves to `127.0.0.1:5432/pc_client`; artifact: `artifacts/browser_live_validation/registry-phase4-agent-ba41cce8-20260614/registry_workflow_smoke.json`. This is environment placement evidence only, not a product failure.
* The same smoke was rerun on the Linux stand from `/var/chat_bot/pc_client` with run id `phase4-preflight-20260614-ba41cce8-remote` and passed scenarios A-F. Sanitized JSON artifact: `artifacts/browser_live_validation/registry-phase4-agent-ba41cce8-20260614/registry_workflow_smoke_remote.json`.
* Started isolated local Windows agent instance `phase4-reg-ba41cce8` with machine/device id `ee6a14a7-365b-5a82-a3ff-299b2e588819`, source GUI mode and UI port `8874`; raw agent token was issued through remote `AuthService` and was not printed or written to artifacts. The agent connected to `wss://192.168.100.17:9443/ws`, received `handshake_ack`, handled `list_tools`, and UI bridge status reported `sidebar_view=account_gate`, `connection_state=connected`, `connection_detail="WS подключён"`.
* Real UIA evidence captured the agent account gate: `AccountGateWidget` was visible with Russian registration copy and the `Зарегистрировать через браузер`, `Регистрация`, `Обновить`, `Настройки` buttons. Artifacts: `agent_account_gate_uia.json`, `agent_account_gate_uia_raw.json`, `agent_account_gate_uia_depth12.json`, `agent_account_gate_uia.png`, `agent_ui_automation_status.json`.
* `scripts/live_agent_uia_state_probe.py --expect-connected` is too strict for the pre-login account-gate entry mode because the connection controls live in the hidden footer/sidebar; the UIA tree did not expose `agent.connection.*` while `/ui/automation/status` did show connected. Treat this as a UIA evidence limitation for Phase 4, not as Scenario A pass.
* Triggered the actual GUI browser-registration action through UIA Invoke on the `Зарегистрировать через браузер` button; artifact: `agent_browser_register_click.json`. Coordinate-based `click_input()` failed with Windows `SetCursorPos`, but UIA Invoke succeeded.
* Server-side safe DB evidence after the UIA action showed a pending registration browser pairing for the isolated device: `pairing_id=b2c86c5f-b225-4022-9239-cd55735fbf51`, `purpose=registration`, `status=pending`, `created_at=2026-06-13T19:36:55.610848+00:00`; artifact: `browser_pairing_after_uia_click.json`. No pairing token, manual code, token hash, account-session token or machine token was saved.
* Captured post-click UIA screenshot/status/log tail artifacts: `agent_account_gate_after_register_click_uia.json`, `agent_account_gate_after_register_click_uia.png`, `agent_ui_automation_status_after_register_click.json`, `agent_logs_tail_after_register_click.txt`.
* Cleanup: local instance `phase4-reg-ba41cce8` was stopped; remote `server` and `control` were stopped and confirmed inactive. Registration policy was not changed in this partial run, so no policy restore was needed.
* This does not close Phase 4. Still required for Phase 4 exit: rerun Scenario A with `registration.department_mode=required_existing` and `registration.location_mode=required_existing`; complete browser confirmation on the device registration page with a test UI user; verify pending claim/diff/approval in `/app/admin/registry`; verify agent leaves pending and creates a ticket with requester account-session fields; run Scenario B invalid strict department/location; run Scenario C other-account boundary; collect browser/API/DB/UIA/log evidence for the same clean run marker.

Phase 4 continuation audit, 2026-06-14:

* Current code inspection shows a planning risk for the next strict-policy live run: `/app/device/register` calls `confirmDevicePairing(pairing_id, "registration")` with an empty JSON body; `handle_web_registry_browser_pairing_registration_confirm()` ignores request body; `BrowserPairingService.confirm_registration_pairing_for_web_user()` builds the claim profile only from the web actor id via `_profile_from_actor()` and therefore cannot submit `department_id` / `location_id`.
* Because `RegistrationService.submit_agent_profile_claim()` raises `RegistrationValidationError("department_id is required")` and `RegistrationValidationError("location_id is required")` when `registration.department_mode` / `registration.location_mode` are `required_existing` and no registry ids are present, the current browser-registration confirmation path is not enough to satisfy "strict policy + browser confirmation" in one run unless code changes add a picker/payload path or the scenario is split.
* Efficient next options before the next live run:
  * preferred product fix: extend the device registration page/API so registration browser confirmation can submit existing `department_id` / `location_id` under strict policy, with server tests, webapp tests and browser evidence;
  * validation split if no product change is intended yet: keep strict `required_existing` for Scenario B and agent-form policy validation, but run browser-pairing confirmation with policy relaxed/restored explicitly and record that it is not a strict-policy pass.
* Focused DB-backed pytest attempts for `server/tests/test_registration_api.py::test_registration_pairing_approval_surfaces_confirmed_binding_to_agent` timed out locally after 180s without producing assertion output. Treat this as a local test-environment/slow DB limitation for this audit, not as pass/fail evidence. Re-run with the standard project test DB setup before using it as a gate.

Phase 4 strict browser-registration payload slice, 2026-06-14:

* Implemented the preferred product fix for the strict-policy browser confirmation path: `/app/device/register` now loads `/api/registry/options`, renders department/location pickers when options exist, and sends selected `department_id` / `location_id` in the `/api/web/registry/browser-pairings/{pairing_id}/registration/confirm` JSON body.
* Backend confirmation now accepts only optional `department_id` / `location_id` from the browser payload and delegates validation to `RegistrationService`, preserving the existing rule that browser users cannot override person, binding, account-session or token fields.
* Added regression anchors:
  * `server/tests/test_registration_api.py::test_registration_pairing_confirmation_accepts_required_registry_ids`
  * `server/tests/test_web_session_api.py::test_web_session_cookie_auth_bridges_react_workbench_paths[/api/registry/options]`
  * `webapp/src/pages/device-pairing/device-pairing-page.test.tsx` coverage for selected department/location ids in the registration confirm POST body.
* Live browser check on `https://192.168.100.17:9443/app/device/register?pairing_id=...` initially exposed a missing auth bridge: the page could fetch `/api/web/registry/browser-pairings/{pairing_id}` only for a `user` web session, but the new `/api/registry/options` request did not accept the same web-session cookie and collapsed to the generic authentication-required state. `server/auth/middleware.py` now includes the narrow `/api/registry/options` cookie bridge so the page can load registry picker options without broadening cookie auth to all agent registry endpoints.
* This removes the previously documented need to relax strict policy for browser pairing, but Phase 4 still requires a real live rerun with strict policies, browser confirmation, admin approval diff, agent account-state transition and ticket requester account-session fields.

Phase 4 next live-run context and efficiency conditions, 2026-06-14:

* Treat the `Phase 4 continuation audit` concern about missing browser department/location payload as resolved by commits `d8207ff3` and `e15918fa`. Do not choose the earlier "validation split" path unless a fresh regression proves the picker/payload path is broken.
* Baseline for the next strict live run is the deployed `e15918fa` behavior: `/app/device/register` must load `/api/registry/options` with the same web-session cookie as the pairing details request, render department/location selects, and send only `department_id` / `location_id` in `registration/confirm`.
* A strict Scenario A pass requires the same run marker to tie together all layers: browser selected ids, registration claim profile ids, admin approval diff labels, approved person department/location ids, active binding, account-state/account-session response, agent UIA state and ticket requester fields. A browser-only fake pairing or DB-seeded pairing is useful partial evidence, but it cannot close the connected-agent requirement.
* Before changing policies, snapshot the current `registration.department_mode` and `registration.location_mode`; set both to `required_existing` only for the run; restore them or explicitly record the final shared-stand state during cleanup.
* If the device registration page shows `Требуется аутентификация` after the user web session is established, classify it first as a web-session cookie bridge or auth-prefix regression. Do not patch policy or registration validation until `/api/web/registry/browser-pairings/{pairing_id}` and `/api/registry/options` are compared under the same browser session.
* Scenario B should not depend on free-text UI input once the strict picker is present. Use a controlled browser/API tamper with an invalid existing-id value, then verify safe Russian user-visible error text, no approved person/binding side effect, no active account session and no raw token/pairing-code leakage in evidence.
* Scenario C should start from a confirmed binding created in the same run when feasible. If an older binding is reused, record why, the source binding id, and the extra contamination checks that prove old history did not affect ticket visibility or ownership assertions.
* Minimum evidence files for the next run folder: browser DOM/screenshot for registration confirm and admin diff, UIA account-gate/account-page dumps before and after approval, sanitized API/DB JSON for claim/binding/session/ticket fields, server log excerpts around the run marker and local agent log excerpts around account-state/ticket create. Redact or hash all raw tokens, cookies, auth headers, pairing tokens and manual codes.

Phase 4 strict Scenario A live evidence, 2026-06-14:

* Run marker: `phase4-agent-20260614-4ca9a116`; deployed commit: `4ca9a1168fc2a2ea6f9b86ce2f3c34e550176bc6`; canonical stand: `https://192.168.100.17:9443`; isolated Windows GUI agent: `phase4-agent-20260614-4ca9a116`; machine/device id: `efad5e17-14a3-4378-b8a4-d09fb63f3d69`.
* Setup artifacts live under `artifacts/browser_live_validation/phase4-agent-20260614-4ca9a116/`. Test CMDB objects used `department_id=989e865a-03a0-456c-9474-4a8711bffb07`, `location_id=6f74fc1f-dc26-487b-ab44-a9da04af9b39`, and person `cb64f08c-365a-4467-990a-abf84a3ff7f1`. Policy snapshot/restore artifacts show `registration.department_mode` and `registration.location_mode` were set to `required_existing` for the run and restored to `allow_pending_request` during cleanup.
* Real agent connection/account-gate evidence: `/ui/automation/status` reported `sidebar_view=account_gate`, `connection_state=connected`, `connection_detail="WS подключён"` before registration; UIA dumps showed the account gate and the browser-registration button. The isolated agent later reached `sidebar_view=tickets`, `account_exists=true`, `account_mode=confirmed_binding`, `display_name=Phase 4 Live User phase4-agent-20260614-4ca9a116`, and `binding_id=f0920fc4-587b-47c5-b7a9-6689ee0a7299`.
* Browser registration evidence: after UIA invoked `Зарегистрировать через браузер`, `/app/device/register?pairing_id=64cb1f59-de7a-4ce7-add5-361cdaeb628d` rendered strict department/location pickers for the same authenticated user. Browser DOM evidence showed `Статус confirmed` and `pending_admin_review`; DB evidence showed the claim profile carried only the selected registry ids (`department_id=989e865a-03a0-456c-9474-4a8711bffb07`, `location_id=6f74fc1f-dc26-487b-ab44-a9da04af9b39`).
* Admin approval diff evidence: `/app/admin/registry` -> `Заявки` showed the same pending claim with `Устройство: ADMIN-2`, `Текущая привязка: нет активной привязки`, `Заявлено: phase4_user_4ca9a116`, the Phase 4 department/location labels, identity and `primary_user`; browser UI approval changed the row to `approved` and disabled completion actions.
* DB side effects after approval: claim `ed974a53-75d0-41f8-b396-af7b8f9a2989` became `approved` with `reviewed_by=p4admina116`; active binding `f0920fc4-587b-47c5-b7a9-6689ee0a7299` was created; `registry_assets.assigned_person_id`, `registry_assets.department_id`, `registry_assets.location_id`, and `device_inventory_bindings.source_binding_id/registration_status` were synchronized.
* Account-session/ticket evidence: agent refresh/login created verified `device_account_sessions.session_id=2b3da255-d6b4-4eeb-9327-2261ca9192f0` with `account_mode=confirmed_binding`, `verification_status=verified`, `verification_method=device_binding`. `scripts/agent_test_driver.py create-ticket ...` created ticket `6dbb8d18-18c0-41d2-af6e-abe9e482488b` / `T-000693`; sanitized DB evidence shows `requester_person_id=cb64f08c-365a-4467-990a-abf84a3ff7f1`, `requester_binding_id=f0920fc4-587b-47c5-b7a9-6689ee0a7299`, `requester_account_session_id=2b3da255-d6b4-4eeb-9327-2261ca9192f0`, `requester_registration_status=admin_confirmed`, and `requester_account_mode=confirmed_binding`.
* Support UI evidence: `browser_support_ticket_requester_context_snapshot.txt` shows ticket `T-000693` in the support queue with requester `Phase 4 Live User phase4-agent-20260614-4ca9a116`; the ticket context panel shows `Заявитель`, the same department and location labels, and the requester email.
* Efficiency notes for the next live run: pairing TTL is short enough that browser confirmation should happen immediately after the UIA click, or the GUI should be refreshed afterward; in this run the agent pairing poll timed out before browser confirmation, but the account-state refresh still surfaced `pending_admin_review` and later the approved confirmed-binding account. `device_browser_pairings.consumed_at` stayed `null`, so rerun a narrower timing check if the pairing-consumption event itself is required as exit evidence. Browser screenshot capture timed out in the Browser plugin; use DOM snapshots plus UIA/OS screenshots unless Browser screenshot reliability is fixed. Browser text entry through `fill`/`type` hit the virtual clipboard limitation; use simple ASCII fixture logins with `press`, or use a verified cookie/token setup that does not print raw secrets.
* Cleanup: raw tokens, cookies, pairing token/code and account-session token were not saved; the ticket create artifact was sanitized after initially returning a public access code. The local agent was stopped, remote `server` and `control` were stopped, and shared registration policy was restored. This evidence closes the strict Scenario A account-session/ticket path, but not all of Phase 4 because Scenario B and Scenario C remain open.

Phase 4 Scenario B/C execution addendum, 2026-06-14:

* Scenario B should be a negative strict-policy proof, not another successful registration. Use a fresh marker such as `phase4-invalid-YYYYMMDD-<short_sha>`, keep `registration.department_mode=required_existing` and `registration.location_mode=required_existing`, and prove that the browser page still loads the strict pickers before the invalid submission is tampered. Because the production UI no longer offers free-text input in strict mode, the invalid value should be injected through a controlled browser/API request against the same authenticated web session and pairing id, then corroborated with browser-visible Russian error text if the UI renders the server response.
* Scenario B pass conditions: HTTP/API returns a validation failure for invalid or missing registry ids; `device_registration_claims` has no approved/new side-effect row for the invalid marker or pairing; no active `device_user_bindings`, `device_account_sessions`, `registry_assets.assigned_person_id`, `device_inventory_bindings.source_binding_id` or ticket requester fields are created/changed for the invalid device; evidence contains no raw cookies, auth headers, pairing token/code, machine token or account-session token. If a claim row is intentionally created as rejected/failed, record the exact terminal status and prove it cannot be approved later.
* Scenario B should run before Scenario C unless there is a strong reason to reuse the confirmed-binding state. It is cheaper, has smaller cleanup surface and validates the strict browser/API boundary before testing the more stateful other-account flow.
* Scenario C should use a confirmed owner from the same clean run when feasible; otherwise record the reused binding id, original run marker and a contamination check that lists owner tickets before the other-account session is created. The other-account request must come from the agent/account gate path and end as `verified_other_account`; it must not create a registration claim, must not mutate the active device binding and must not change the registered owner's primary person/department/location.
* Scenario C pass conditions: the approved other-account session has `account_mode=verified_other_account`; the created ticket stores `requester_account_session_id`, `requester_account_mode=verified_other_account`, `requester_account_warning=ticket_created_from_other_account_on_registered_device` and `custom_fields.requester_account_context`; the other-account session cannot list or open the registered owner's historical tickets; the support UI shows the Russian warning `Обращение создано с другого аккаунта на зарегистрированном устройстве.`; revoking the base binding or session invalidates subsequent agent requester actions.
* For both scenarios, use the no-single-signal rule from `docs/LIVE_TESTING_DEBUG_RULES.md`: browser DOM/screenshot for UI-visible results, UIA dumps for the local agent, sanitized API/DB JSON for side effects, and server/agent log excerpts filtered by the run marker. A direct HTTP/DB helper can support evidence, but it cannot replace the canonical browser or real-agent path where the scenario is UI-visible.

Phase 4 Scenario B partial live evidence and next conditions, 2026-06-14:

* Run marker: `phase4-invalid-20260614-4ca9a11`; remote stand commit for code-under-test: `4ca9a11` (local later commits in this branch were docs/context only); canonical stand: `https://192.168.100.17:9443`; isolated Windows GUI agent: `phase4-invalid-20260614-4ca9a11`; machine/device id: `11111111-2222-4333-8444-4ca9a110000b`.
* Evidence folder: `artifacts/browser_live_validation/phase4-invalid-20260614-4ca9a11/`. Raw UI tokens, cookies, auth headers, pairing token/code, machine token and account-session token were not saved; token evidence is only hash/length in `browser_runtime_token.safe.json` and `setup_policy_user.safe.json`.
* Setup and cleanup evidence: `setup_policy_user.safe.json` shows `registration.department_mode` and `registration.location_mode` were changed from `allow_pending_request` to `required_existing` for the run, with active fixture department `8354f5af-e597-4717-9805-e3b38b26ab4a` and location `da0977c0-0ff9-45ab-a35c-1ed6615df1e0`; `policy_restore.safe.json` shows both policy modes were restored to `allow_pending_request`.
* Real-agent evidence: `/ui/automation/status` showed `sidebar_view=account_gate`, `bridge_connected=true`, `connection_state=connected`, and `connection_detail="WS подключён"` before browser registration. Use `wss://192.168.100.17:9443/ws`; an attempted `/ws_agent` URL produced 404 handshakes and wastes time.
* UIA efficiency note: the account-gate primary action is reliably found by automation id suffix `PrimaryButton`; do not depend on Russian button text in ad-hoc UIA scripts unless the shell has been UTF-8 bootstrapped. The first failed artifact (`agent_browser_register_click.safe.json`) contains mojibake labels; `agent_browser_register_click_retry.safe.json` shows the successful `Зарегистрировать через браузер` click and created pairing `945ce1f1-5a3b-4405-9f36-4bb9eec9e67e`.
* Browser/API negative proof: cookie-auth state-changing POSTs require browser-equivalent `Origin` and `Referer`; without them the invalid confirm returned `403` / `CSRF_ORIGIN_REQUIRED` (`api_invalid_confirm_response.safe.json`). With those headers, posting invalid `department_id=00000000-0000-4000-8000-000000000bad` and valid `location_id=da0977c0-0ff9-45ab-a35c-1ed6615df1e0` returned `404` / `NOT_FOUND` with `department_id not found` (`api_invalid_confirm_with_origin_response.safe.json`).
* Browser-visible state after the invalid API attempt: the Browser plugin page initially stayed on `Проверяем web-сессию`; wait for the auth guard to finish before judging the page. After about five seconds, `browser_register_pending_after_invalid_iab_wait5.safe.json` and `.png` show `/app/device/register?pairing_id=945ce1f1-5a3b-4405-9f36-4bb9eec9e67e` still rendering `Статус pending`, two strict `<select>` controls and one enabled confirmation button, including the Phase 4 fixture department/location options.
* Browser tooling constraints from this run: bundled primary-runtime Node has `playwright` without `playwright-core`; Python Playwright is not installed; `npx --package playwright` did not make `require("playwright")` available. Browser plugin CDP `Fetch` interception hit `Raw CDP is unavailable while Browser Use is resolving a paused document response`; for cookie setup, `Network.setCookie` must use `url` and must not include `domain`.
* DB side-effect proof: `db_after_invalid_confirm.safe.json` shows the pairing had no `claim_id`, `binding_id`, `confirmed_person_id` or `resulting_account_session_id`; `device_registration_claims=0`, `device_user_bindings=0`, `device_account_sessions=0`; the asset remained `unverified` with `assigned_person_id=null` and `active_binding_id=null`. The final DB snapshot was taken after pairing TTL elapsed, but the invalid API response itself was captured before expiry; do not use the final negative `seconds_until_expiry` as evidence that the invalid request was an expiry rejection.
* Local UX fix after this evidence: `webapp/src/pages/device-pairing/api.ts` maps technical `department_id` / `location_id` validation failures to safe Russian requester text before throwing `DevicePairingApiError`; `webapp/src/pages/device-pairing/device-pairing-page.test.tsx` has a focused regression for `NOT_FOUND` / `department_id not found` and asserts the raw English string is not rendered.
* Pre-fix conclusion after `4ca9a11`: backend/API validation and DB no-side-effects were proven, but the requester page still needed a post-fix canonical stand rerun because the deployed UI could render raw `department_id not found`.
* Canonical post-fix rerun evidence: `b675d998` (`webapp: map registration id errors safely`) was quick-deployed with run marker `phase4-invalid-20260614-b675d99`; evidence folder is `artifacts/browser_live_validation/phase4-invalid-20260614-b675d99/`; browser URL was `/app/device/register?pairing_id=f2ddde28-b28e-4d2b-a9bb-6c88c7676f0f`; device id was `11111111-2222-4333-8444-b675d990000b`.
* Deployed-bundle guardrail for the rerun: `deployed_device_pairing_chunk.safe.json` shows the lazy device-pairing bundle `/assets/device-pairing-CVdL8Uc7.js` was available on the stand and did not contain raw `department_id not found`. Its `has_safe_*_ru=false` flags are a detector false negative caused by narrow static string matching/minification; do not use those flags as the decisive UI evidence. The decisive evidence is the Browser page artifact below.
* Browser-visible mapped-error proof: generic CDP `Fetch.enable` failed because Browser Use reserves paused Document responses; the working harness used resourceType-specific Fetch interception for `registration/confirm`, selected the strict department/location options, then tampered only `department_id` to `00000000-0000-4000-8000-000000000bad`. `browser_register_after_tampered_confirm_iab_retry.safe.json` has `paused_event_count=1`, `safe_error_visible=true`, and `raw_error_visible=false`; the paired `.png` screenshot captures the same requester page after the failed confirm.
* DB/no-side-effect proof and cleanup: `db_after_tampered_confirm_and_policy_restore.safe.json` shows the pairing stayed `pending` with no `claim_id`, `binding_id`, `confirmed_person_id` or `resulting_account_session_id`; `device_registration_claims=0`, `device_user_bindings=0`, `device_account_sessions=0`, `tickets_for_device=0`, `tickets_with_requester_context=0`, no asset/inventory assignment, and only one `browser_pairing_created` account event. The helper restored `registration.department_mode` and `registration.location_mode` from `required_existing` back to `allow_pending_request`.
* Evidence hygiene: raw UI tokens, cookies, auth headers, pairing token/code, machine token and account-session token were not saved; safe setup evidence stores only token hash prefixes/lengths. If rerunning through Browser, remember that secret JSON written by PowerShell may carry a BOM and must be read with `utf-8-sig`; remove temp secret files immediately after cookie setup.
* Scenario B status after `b675d99`: the post-fix requester-visible safe Russian error layer and DB no-side-effect layer are closed for the canonical stand. Rerun Scenario B only if the exit bar is tightened to require the same-run pairing to be created by the real Windows GUI agent action instead of the seeded browser-pairing setup; in that case reuse the `b675d99` harness constraints and keep the rerun narrow.
* Scenario C may proceed only after recording that Scenario B is accepted at the `b675d99` evidence level or explicitly noting the stricter real-agent-pairing caveat above. If Scenario C proceeds first, add contamination checks so later Knowledge/Phase 7 work does not treat other-account coverage as a substitute for negative strict registration coverage.

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

Phase 5 implementation efficiency addendum, 2026-06-14:

* Start with a read-only `KnowledgeAccessService`/decision contract and tests before adding authoring UI. The first slice should centralize the decision order from `server/docs/REGISTRY_VISIBILITY_FOUNDATION.md`: actor/session context, space lifecycle, item status/current version, coarse visibility, space audience rules, item audience rules, documented support/admin override, then safe final projection.
* Do not implement private visibility filters inside each endpoint. Wire search, portal/article reads, suggestions, support knowledge, graph/vector retrieval, RAG candidate selection and diagnostics through the same access service or a thin wrapper that returns both `allowed` and `reason_code`.
* Candidate selection and final projection both need tests. A passing Phase 5 slice must prove hidden content is absent from returned item ids, titles, summaries, snippets, chunks, result counts and diagnostics for requester/agent/public roles. Admin explain can show rule ids/reasons only through admin-only routes.
* Reuse Phase 1/2 Registry services for effective identity and audience expansion. Do not duplicate department-tree, access-group-as-audience or audience-group expansion inside Knowledge. A Knowledge rule targeting `access_group` is a targeting fact only; it must not grant RBAC permissions.
* Use small seed fixtures with explicit marker names: two departments, one parent/child department-tree case, one access group, one audience group, two linked UI users and at least one unlinked/anonymous actor. Each negative test should assert both denial and absence of leaked article metadata.
* Preferred implementation order: migration/model/repo contract; audience rule CRUD/preview service; read-only access decision service; enforce item/detail/search; enforce suggestions/portal/support knowledge; enforce vector/RAG candidate paths; add admin explain. Keep Phase 6 authoring selector blocked until Phase 5 anti-leak tests are green.
* Minimal focused tests before broad Knowledge suites: audience rule validation/precedence, requester allowed/denied by department and department_tree, support/internal coarse visibility not widened by matching audience rule, access-group and audience-group targets, unlinked actor behavior, search-count/title/summary/chunk anti-leak, vector/RAG candidate filtering and admin explain authorization/redaction.

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

Phase 7 efficiency context:

* Reuse the Phase 4 live-agent harness, run-marker discipline, isolated agent instance and evidence matrix instead of creating a parallel validation flow for account sessions.
* `scripts/registry_visibility_live_smoke.py` may automate setup, requester/support/admin HTTP checks and sanitized report generation, but it must not claim real-agent proof unless it either drives the actual connected agent flow or links to same-run UIA/browser evidence from the real agent.
* Phase 7 should consume Phase 4 registration/account-session evidence as the identity baseline, then add Knowledge visibility assertions on top: visible scoped article, hidden foreign scoped article, support ticket requester context, revoked-session denial and absence of hidden article metadata in network/API payloads.
* If Phase 4 live evidence is stale relative to the Phase 7 commit, rerun the Phase 4 Scenario A/C account-session portions before signing off Knowledge visibility.

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
