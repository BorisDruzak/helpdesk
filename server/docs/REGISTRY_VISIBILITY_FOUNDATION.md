# Registry Visibility Foundation

Status: active foundation contract. Phase 0 recorded the architecture, Phase 1 added the effective identity/audience read model, Phase 2 added Registry audience-group backend APIs, Phase 3 added prompt-free Registry dialogs plus an audience-group editor, Phase 4 hardened registration/account-session flows, Phase 5 closed the backend Knowledge audience-rule enforcement slice, Phase 6 added the Knowledge Studio visibility selector, Phase 7 recorded live browser/UIA signoff evidence, and Phase 8 has the first backend operability slice for Registry quality plus safe audience import/export.

The foundation connects Registry identity, account sessions, audience groups and Knowledge visibility. It extends the current Registry Management Center and Knowledge Platform; it does not replace either one.

## Goals

- Resolve a web actor, support/admin actor or agent account session into one effective registry identity.
- Keep organization, permissions and audiences as separate concepts.
- Let Knowledge visibility use departments, department trees, locations, roles, access groups, audience groups, services and explicit people without leaking hidden content.
- Make registration collect clean registry data when policies require existing departments or locations.
- Preserve current requester/account-session safety: an agent machine token is never a requester identity.

## Canonical Terms

| Term | Meaning | Source of truth |
|---|---|---|
| `department` | Organizational structure, reporting line or business unit. It is not a permission group. | `registry_departments`, primary link from `registry_people.department_id` |
| `location` | Physical or logical office/building/floor/room context. | `registry_locations`, `registry_people.location_id`, derived asset/inventory fields |
| `access_group` | RBAC/permission and queue-access group. Membership can grant permissions. | `access_groups`, `access_group_members`, `access_group_permissions`, `access_group_queue_members` |
| `audience_group` | Content/service/notification targeting group. Membership does not grant permissions. | `registry_audience_groups`, `registry_audience_group_members` |
| `queue` | Support work queue. It is a work-routing object, not an organization unit. | Existing helpdesk/settings/access-control tables |
| `role` | Authenticated actor role such as `admin`, `support`, `auditor`, `user`, `agent` or `requester`. | `AuthContext`, web session, agent token middleware |
| `person` | Human registry record. | `registry_people` |
| `identity` | Verified alias that links a person to a login/email/windows account or other identifier. | `registry_person_identities` |
| `account_session` | Server-issued requester identity for local agent GUI actions. | `device_account_sessions` through `AccountSessionService` |
| `knowledge_audience_rule` | Rule that refines who can view a Knowledge space or item after coarse visibility/status checks pass. | `knowledge_audience_rules` |

## Current Sources

Use the existing sources below before adding new state:

- `ui_users.user_login` is the web login account.
- UI-user to person links are verified identities: `registry_person_identities(provider='ui_login')`.
- `registry_people.department_id` and `registry_people.location_id` are the current primary organization attributes.
- Active `device_user_bindings` is the authoritative device-person binding source.
- `registry_assets.assigned_person_id` and `device_inventory_bindings.person_id/source_binding_id/registration_status` are derived and must be synchronized through registry services.
- `device_account_sessions` carries the requester account-session boundary for the agent GUI.
- `access_groups` and related membership/permission tables remain the RBAC source.
- Knowledge currently enforces coarse role visibility through `knowledge.contracts.actor_visible_visibilities()` and services such as `KnowledgeSearchService`, `KnowledgeVisibilityService`, `KnowledgePortalService` and `KnowledgeRetrievalService`.

## Why Department Is Not Group

Departments describe where a person belongs in the organization. They should answer questions like "which branch of the company owns this employee?" or "which child departments belong to Finance?"

Access groups describe what a person can do. They grant permissions, support queue access and operational capabilities.

Audience groups describe who should see or receive something. They are useful for Knowledge visibility, service targeting and future notifications. They may include departments, locations, access groups, roles, services or explicit people, but they do not grant RBAC permissions by themselves.

Collapsing these concepts would make future AD/SSO sync, support permissions and Knowledge targeting unsafe. For example, adding a person to `finance_staff` for article visibility must not accidentally grant support queue access, and adding a support engineer to `support_l1` must not automatically make them a Finance department member.

## Target Read Models

### Effective Identity

Phase 1 implemented service: `server/registry/effective_identity_service.py`.

Inputs:

- web actor id/role from `AuthContext`;
- agent `device_id` plus account `session_id` and token;
- optional explicit person id for admin explain tools.

Outputs:

- actor id and role;
- resolved `person_id`, display name and linked `ui_login` where available;
- primary department/location;
- department path;
- access groups;
- audience groups;
- account-session summary without raw token;
- deterministic warnings for missing identity, unlinked UI user, inactive person, archived department/location or broad role-only context.

Rules:

- Admin/support actors may resolve without a registry person, but explain output must show that registry person is missing.
- User/requester flows should prefer a linked `RegistryPerson`.
- Agent machine identity alone must not resolve as requester identity.
- Account-session identity must validate through `AccountSessionService`; client-supplied person, binding or account-mode fields are not trusted.
- Explain responses must be deterministic and must not include raw tokens, cookies, pairing codes or auth headers.

### Effective Audience

Phase 1 implemented contracts: `server/registry/audience_contracts.py`. Audience-group expansion remains a later registry-layer service.

Effective audience should include:

- person id;
- primary department and department tree ancestors/children when requested;
- location;
- access groups as targeting facts only;
- audience groups;
- role;
- service/offering targeting facts when a Knowledge request includes service context.

Audience expansion must be deterministic and side-effect-free. Preview endpoints may count expanded people and warnings, but must not mutate state.

## Planned Schema

Phase 2 implemented tables:

- `registry_audience_groups`
- `registry_audience_group_members`
- `registry_person_department_memberships` (compatibility-safe optional multi-department membership; backfilled from `registry_people.department_id`)

Phase 5 implemented first backend table:

- `knowledge_audience_rules`

Optional audit table if existing audit is insufficient:

- `knowledge_access_decisions`

Compatibility constraints:

- Keep `registry_people.department_id` as the primary/default department even if multi-department membership is introduced.
- Do not repurpose `access_groups` for audiences.
- Do not import direct device bindings or account sessions.
- Audience groups and visibility rules should use `status`/archive semantics instead of hard deletes.

## APIs

Phase 1 implemented admin-only explain/read APIs:

- `GET /api/web/admin/registry/identity/effective?actor_id=...`
- `GET /api/web/admin/registry/identity/person/{person_id}/audience`
- `GET /api/web/admin/registry/identity/session/{session_id}/explain`

These endpoints are read-only. Session explain responses validate through `AccountSessionService` when a token is supplied and never echo raw tokens or token hashes.

Phase 2 implemented audience group APIs:

- `GET /api/web/admin/registry/audience-groups`
- `POST /api/web/admin/registry/audience-groups`
- `PATCH /api/web/admin/registry/audience-groups/{audience_group_id}`
- `POST /api/web/admin/registry/audience-groups/{audience_group_id}/archive`
- `GET /api/web/admin/registry/audience-groups/{audience_group_id}/members`
- `PUT /api/web/admin/registry/audience-groups/{audience_group_id}/members`
- `POST /api/web/admin/registry/audience-groups/{audience_group_id}/preview-members`

Phase 5 Knowledge visibility admin APIs:

- `GET /api/web/admin/knowledge/audience-rules?subject_type=&subject_id=`
- `PUT /api/web/admin/knowledge/audience-rules`
- `POST /api/web/admin/knowledge/audience-rules/preview`
- `GET /api/web/admin/knowledge/access/explain?actor_id=&item_id=`

The first admin API slice is implemented in `server/knowledge/audience_rules_service.py` and `server/web_api/knowledge_handlers.py`. These routes are admin-only, replace/list item or space rule rows through `knowledge_audience_rules`, preview item access with transient or persisted rules, and expose admin explain decisions through `KnowledgeAccessService` plus Registry effective audience resolution. `POST /api/web/admin/knowledge/audience-rules/preview` currently supports `subject_type=item`; Phase 5 is not complete until normal requester/support/search/suggest/portal/vector/RAG read paths enforce the same service and have anti-leak coverage. Phase 6 consumes these APIs from `/app/admin/knowledge/studio` through a Russian-first `Область видимости` selector instead of raw JSON; this UI must remain an authoring/debug client and cannot become the access-control boundary.

## Knowledge Access Decision Order

Every Knowledge read/search/suggestion/RAG path must apply the same order:

1. Authenticated actor role and session context.
2. Space lifecycle/status.
3. Item status/current version.
4. Coarse Knowledge visibility.
5. Space audience rules.
6. Item audience rules.
7. Explicit support/admin override only when documented and audited.
8. Safe final projection.

Candidate selection and final projection both matter. Search, portal, suggestions, support knowledge, graph, vector search, RAG candidate selection and diagnostics must not rely on frontend filtering or post-search masking only.

Requester/agent/public responses must not reveal hidden titles, summaries, snippets, chunks, result counts, diagnostics or metadata for denied content. Admin explain endpoints may show rule ids and reasons, but must stay admin-only.

## Registration Policy Boundary

Existing `RegistryPolicyService` already validates:

- `registration.department_mode`: `allow_pending_request`, `optional`, `required_existing`
- `registration.location_mode`: `allow_pending_request`, `optional`, `required_existing`

Phase 4 must expose and enforce these existing modes:

- `required_existing`: registration claim must include a valid department/location id.
- `optional`: picker should use registry objects, but absence can be accepted.
- `allow_pending_request`: free text is pending quality input and must not silently create duplicate departments or locations when strict mode is required.

The current Phase 4 UI slice exposes `registration.department_mode` and `registration.location_mode` in `/app/admin/registry` -> `Политики · P1` as operator selects over the existing enum values. It uses the existing policy preview/save/reset endpoints and does not add a second policy route.

Approval diff must show existing person/device/binding, claimed department/location, proposed identity, proposed binding type, conflicts and blockers. The first Phase 4 UI slice renders this diff in `/app/admin/registry` -> `Заявки` from the existing `/api/web/admin/registry` payload before admin approve/reject actions; it does not add a second approval route. Approval must update person identity, person primary department/location where applicable, device binding, derived asset/inventory state and account-session state through existing services.

The device browser registration page `/app/device/register` reuses `/api/registry/options` for department/location pickers and sends selected `department_id` / `location_id` to `POST /api/web/registry/browser-pairings/{pairing_id}/registration/confirm`. `/api/registry/options` is intentionally included in the web-session cookie bridge because this browser page loads it outside `/api/web/*`; keep that bridge narrow and do not expose agent registry endpoints to cookie auth. The confirmation endpoint accepts only those registry ids from the browser payload and delegates validation to `RegistrationService`, so strict mode uses existing Registry objects without trusting browser-supplied person, binding or session fields.

## UI Contract

Registry production UI should replace raw-id prompt flows with dialogs/drawers using:

- searchable person, department, location, access group and audience group pickers;
- preview/dry-run before dangerous apply;
- required reason for destructive or broad operations;
- apply result reports with selected/success/failed counts;
- raw UUIDs only in `Advanced / служебные поля`.

Phase 3 UI slice removed the known raw prompt anchors from:

- `webapp/src/pages/admin/registry-page.tsx`
- `webapp/src/features/admin/registry/registry-quality-tab.tsx`

The current Registry UI slice also adds:

- `webapp/src/features/admin/registry/registry-bulk-action-dialog.tsx` for bulk device/person/session actions with preview/reason/result reporting;
- `webapp/src/features/admin/registry/registry-link-ui-user-dialog.tsx` for verified UI-login to RegistryPerson linking without raw id prompts;
- `webapp/src/features/admin/registry/registry-reason-dialog.tsx` for reason-only quality and admin actions;
- `webapp/src/features/admin/registry/registry-audience-groups-tab.tsx` for audience-group CRUD, member editing and member preview.

Future Registry UI changes should keep `window.prompt` treated as a regression target and cover representative Russian labels in webapp tests.

All new user-visible labels should be Russian-first. Technical route paths, enum names, table names and observer event codes stay English.

## Observer And Quality Signals

Later phases should surface these as observer events, metrics or Registry quality issues where existing observer patterns allow:

- unlinked UI user;
- identity collision;
- empty audience group;
- failed audience member resolution;
- invalid Knowledge visibility rule;
- hidden result filtered;
- registration blocked by missing required department/location.

These signals must be redacted and should use ids/counts/reason codes, not article bodies, tokens, cookies or personal data dumps.

Phase 8 backend operability currently surfaces these as generated Registry quality issues in `/api/web/admin/registry`:

- `audience_group_empty` for active audience groups whose member preview resolves to zero people;
- `knowledge_audience_rule_invalid_target` for active Knowledge audience rules that reference missing or archived Registry people, departments, locations or audience groups;
- `knowledge_audience_zero_users` for requester-visible published Knowledge items whose active item/space audience rules resolve to zero known Registry users.

`GET /api/web/admin/registry/export?format=csv` now supports `audience_groups`, `audience_group_members` and `knowledge_audience_rules`. Registry CSV import preview/apply supports `audience_groups` and `audience_group_members` with row errors, duplicate detection, required `preview_id` on apply and the existing `registry_import_applied` audit event. Direct `device_user_bindings`, account-session and token imports remain unsupported.

## Verification Matrix

Phase-level implementation must include focused tests for:

- linked and unlinked UI-user identity resolution;
- confirmed binding, verified other-account and registration-pending account sessions;
- department tree expansion;
- audience group expansion;
- access-group-as-audience not granting RBAC;
- required existing department/location registration policy;
- Knowledge requester allowed/denied decisions;
- no hidden article title/summary/chunk leakage in search, suggestions, portal, graph, vector/RAG and diagnostics;
- admin explain route authorization and redaction.

`scripts/registry_visibility_live_smoke.py` is the Phase 7 repeatable HTTP/DB smoke for confirmed binding, verified other-account, registration-pending, revoked-session, support suggestions and account-session Knowledge audience checks. Its sanitized report is useful evidence, but it explicitly does not replace the final real-agent UIA/browser requirement.

Live evidence must cover a real agent account gate, registration pending, confirmed binding, verified other account, revoked session/binding and requester/support/admin Knowledge visibility.

## Related Documents

- [REGISTRY_MANAGEMENT_CENTER.md](REGISTRY_MANAGEMENT_CENTER.md)
- [REGISTRATION_ACCOUNT_SESSIONS.md](REGISTRATION_ACCOUNT_SESSIONS.md)
- [KNOWLEDGE_PLATFORM.md](KNOWLEDGE_PLATFORM.md)
- [KNOWLEDGE_OPERATIONS.md](KNOWLEDGE_OPERATIONS.md)
- [SECURITY_AND_AUTH.md](SECURITY_AND_AUTH.md)
- [CODEMAP.md](CODEMAP.md)
- [Architecture boundaries](../../docs/ARCHITECTURE_BOUNDARIES.md)
- [Quick lookup](../../docs/QUICK_LOOKUP.md)
