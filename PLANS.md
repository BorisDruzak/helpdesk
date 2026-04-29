# PLANS.md

## 2026-04-28 Agent Qt GUI SaaS Redesign

Status: completed locally; Windows build `3.1.24` uploaded to server and assigned as preferred `windows_amd64/stable` rollout on 2026-04-28.

### Goal

Redesign the local PySide6/Qt Widgets agent GUI into a modern SaaS-style desktop interface while preserving ticket, chat, profile, settings, runtime status and update behavior.

### Constraints

- Work only in `C:\Users\admin-2\CodexProjects\pc_client`.
- Keep the existing PySide6/Qt Widgets architecture; do not migrate to QML or web UI.
- Do not change websocket/API/protocol logic or ticket/chat business handlers unless a UI integration requires a narrow adapter.
- Keep real ticket/profile/runtime/update data from existing models and `ui_bridge`; do not introduce mock ticket data.
- Centralize visual tokens and QSS in `pc_agent/ui_gui/theme.py`.

### Implementation Tracks

1. Refresh theme tokens for light/dark palettes and add centralized QSS for the main shell, sidebar, controls and ticket list.
2. Add reusable GUI affordances around the current widgets:
   - logo support from `C:\Users\admin-2\Desktop\лого\512-512.png`;
   - icon assets under `pc_agent/ui_gui/assets/icons`;
   - custom cross-platform frameless window chrome in `pc_agent/ui_gui/window_chrome.py`;
   - helper styling for shadows and status dots.
3. Redesign `MainWindow` shell:
   - custom Maria Agent title bar with minimize/maximize/close, drag and edge resize;
   - active desktop/dashboard screen backed by current ticket/profile/runtime state;
   - fixed 280-300 px left sidebar;
   - Maria Agent brand block;
   - navigation buttons for desktop, create ticket, tickets and settings;
   - bottom profile and agent status cards backed by current profile/runtime state.
4. Redesign `TicketsSidebarWidget` and `TicketCardDelegate`:
   - search + filters row;
   - minimal Filters menu wired to the existing open/closed/search filters;
   - tab/chip-style all/open/closed filters with counts;
   - card rendering with type icon, code, status, priority, title, source/time, unread badge and chevron;
   - active/hover visual states without changing the list model.
5. Keep settings theme switch connected to existing `ui.theme_mode`, with no restart needed for theme-only changes.
6. Verify:
   - Python compile/import checks for touched modules;
   - `python scripts/verify_workspace.py`;
   - focused agent runtime tests where feasible;
   - manual GUI scenarios: create ticket, search/filter, select ticket, double-click/open chat, settings, theme switch, status/update footer.

### Release Notes

- Windows release artifact: `pc_agent-windows_amd64-3.1.24.zip`.
- Server rollout assignment: `windows_amd64 / stable / 3.1.24`.
- Launcher note: the release script compiles `launcher.exe` into the install layout, but the uploaded self-update ZIP contains the versioned `pc_agent.exe` payload only; launcher self-update remains a separate future mechanism.

## 2026-04-28 Admin Support SaaS Redesign And Playbook Module Entry

Status: in progress.

### Goal

Redesign the React support and admin workspaces into one dense SaaS-style operator UI, using the existing device inventory and playbook builder as the visual/functional baseline, without adding a new UI library.

### Constraints

- Work only in `C:\Users\admin-2\CodexProjects\pc_client`.
- Keep the existing React/Tailwind/component stack.
- Prefer typed `/api/web/*` contracts; add server aliases only when the current frontend cannot express a required workflow.
- Do not expose raw JSON as the normal operator configuration path. UI must use controlled fields and generate payloads for the existing JSON-backed APIs.
- Keep legacy `/admin?legacy=1` and `/support?legacy=1` as rollback escapes unless a separate cutover task explicitly removes them.

### Implementation Tracks

1. Add a shared schema-driven parameter editor for module/tool/playbook params:
   - render text, textarea, boolean, number, integer, select/radio-like enum and object/array fields from typed schema;
   - keep object/array JSON only as a bounded advanced field where the schema does not expose a safer shape;
   - expose generated params preview as read-only/debug context.
2. Make `/app/admin/playbooks` the true entry point for module command launch and setup:
   - group command catalog by module/source/platform/risk;
   - show install policy, preset, params, output contract and condition hints in one inspector;
   - replace `Params JSON` with controlled parameter controls from `params_schema`;
   - keep save payload compatible with `POST /api/web/admin/playbooks/save`.
3. Apply the same parameter editor to support ticket tool launches in `/app/tickets/:ticketId` and compatibility `/app/support`.
4. Replace settings JSON textareas with controlled builders where server payload already provides the catalog:
   - routing condition builder writes `condition_json`;
   - SLA business hours and calendars use day/time rows and holiday rows;
   - JSON remains only as read-only preview or advanced fallback if needed.
5. Tighten the shared SaaS shell:
   - compact topbar/sidebar, reduce decorative copy, keep accessible labels;
   - use existing `Button`, `Badge`, `Card`, `Tabs`, `Select`, `SearchField`;
   - no new UI library.
6. Verify:
   - focused Vitest for params editor/playbooks/support/settings;
   - `pnpm --dir webapp run build`;
   - focused server pytest if typed API changes;
   - `python scripts/verify_workspace.py`;
   - live remote smoke/browser check at `http://192.168.100.17:8666/admin`, then stop server.

### Current Notes

- Current live signoff shows `/app/admin/inventory` and `/app/tickets` working, but long tables and raw JSON fields need an operator-focused pass.
- Main raw JSON hotspots found in:
  - `webapp/src/features/playbooks/playbook-builder-panel.tsx`;
  - `webapp/src/features/modules/modules-panel.tsx`;
  - `webapp/src/pages/tickets/detail-page.tsx`;
  - `webapp/src/features/queues/support-workspace.tsx`;
  - `webapp/src/pages/settings/index.tsx`.
- First implementation slice starts with playbook/module command params because it directly supports fast launch and configuration of concrete modules.

### 2026-04-28 Second Wave: Ticket Control, Forms And Status Logic

Current focus:

1. Build one shared frontend presentation model for ticket statuses:
   - internal status stage and tone;
   - requester-facing status;
   - next-action owner;
   - waiting/evidence/terminal gates;
   - Russian labels without mojibake.
2. Apply that model in `/app/tickets`, ticket detail and compatibility support workspace so support sees the same status logic everywhere.
3. Improve ticket management controls:
   - make status transition intent clearer;
   - show who is expected to act next;
   - make evidence/resolution readiness visible before closure.
4. Improve `/app/admin/forms` as the request entry builder:
   - route preview stays functional;
   - playbook/module trigger readiness is visible;
   - no raw JSON as the normal operator path.
5. Align `/app/settings` ticket lifecycle display with the same status model and labels.

### 2026-04-28 Third Wave: Form Playbook Runtime Proof

Current focus:

1. Prove the form-triggered playbook path end to end:
   - published playbook;
   - request form trigger;
   - ticket creation;
   - real `playbook_run`;
   - `playbook_started` event in the support detail timeline.
2. Make support ticket automation panel show form-triggered autodiagnostics as an explicit operator signal.
3. Re-check lazy module install behavior and stale toolset snapshot handling through existing playbook engine tests.
4. Verify on the Linux stand with two active agents through smoke, observer-aware checks and browser signoff.
6. Verify with focused Vitest, webapp build, workspace verification and live browser checks on `http://192.168.100.17:8666/admin`.

Completed:

- Shared ticket status presentation helper now drives `/app/tickets`, ticket detail, support workspace and settings lifecycle badges.
- Ticket detail shows stage, next action owner, operator action and evidence gate.
- Forms builder shows playbook-trigger readiness and route preview no longer exposes condition JSON as the normal operator surface.

### 2026-04-28 Third Wave: Safer Ticket Status Actions

Current focus:

1. Replace immediate status mutation from the ticket detail select with a deliberate transition panel:
   - choose target status;
   - preview the target stage;
   - show evidence/passport guard before resolution;
   - apply through an explicit button.
2. Keep the server FSM/evidence validation authoritative; frontend only explains the next action.
3. Keep support/admin styling dense and operational.

Completed:

- Ticket detail now applies status transitions only through an explicit confirmation button.
- Forms builder shows the launch chain from request form to routing and playbook trigger.

### 2026-04-28 Fourth Wave: Ticket Automation Entry

Current focus:

1. Add typed support endpoints for ticket-bound playbook launch:
   - list published playbooks available from a ticket;
   - expose version id, required tools, blocks count and readiness;
   - start a selected playbook against the ticket device with `trigger_type=support_ticket`.
2. Add an `/app/tickets/:ticketId` automation panel:
   - show playbook readiness/preflight summary;
   - launch through an explicit `Запустить плейбук` action;
   - show recent operation context next to the launch surface.
3. Keep the existing module command launcher intact for typed params/presets while the new automation panel becomes the entry point for playbook runs.

Completed:

- Ticket-bound playbook launch is available from `/app/tickets/:ticketId` through typed support endpoints.
- Live staging check exposed a real lazy module install edge case: `network_basic@1.0.0` installed successfully, but the playbook failed before `run_tool` because the strict capability gate read a stale/no toolset snapshot.
- The lazy-install playbook gate now allows the immediate `run_tool` after successful DB-backed module install, and live observer signoff confirmed `network.ping` completed successfully.

### 2026-04-28 Tenth Wave: Ticket Control And Forms UX

Current focus:

1. Make ticket status management more operator-safe:
   - group available transitions by workflow stage;
   - show quick action cards with next-action owner and evidence/terminal markers;
   - keep the explicit apply button as the only mutation path.
2. Make form visibility rules predictable for admins:
   - replace `visible_when.field` / `visible_when.equals` / `visible_when.values` technical inputs with field/condition/value controls;
   - derive value choices from the selected dependency field when it has options;
   - continue generating the same `visible_when` payload for the server.
3. Replace pipe-delimited option editing with row-based value/label controls.
4. Keep playbook-trigger readiness and route preview visible, but avoid raw JSON or schema-like labels in the normal authoring surface.
5. Verify with focused red/green Vitest, full webapp test/build, `python scripts/verify_workspace.py`, deploy smoke and live browser checks for `/app/tickets/:id` + `/app/admin/forms`.

### 2026-04-28 Fifth Wave: Module Launch Convergence

Current focus:

1. Verify whether `device_toolset_snapshots` converge after module install/auto-install without a reconnect or manual Sync Modules.
2. Check the full server-agent path:
   - agent `install_module_package` rebuilds registry and emits `tools_changed` / `module_state_changed`;
   - server outbox pipeline syncs inventory and refreshes toolset snapshots;
   - playbook/run_tool uses observer traces for the install and tool call.
3. Add a regression test before any fix and verify the live path on `http://192.168.100.17:8666/admin`.

Findings:

- Root cause found: server processed `module_state_changed` into `device_modules`, but ignored `tools_changed`, so `list_tools` was not queued after agent-side registry rebuild. Snapshot could stay stale until reconnect or manual sync even though the module was already usable.
- Fix in progress: outbox publish now debounces and queues `list_tools` after `tools_changed`; `module_state_changed` also requests the same refresh as a fallback.
- Live no-op auto-install showed that agent lifecycle events are not enough as the only convergence trigger, so server-side `_ensure_module_installed()` now also queues `list_installed_modules` and `list_tools` immediately after successful `install_module_package`.

### 2026-04-28 Fifth Wave: Live Playbook Run And Auto-Install Fix

Current focus:

1. Reproduce real playbook launch from a support ticket against an online Windows agent.
2. Verify module auto-install through server logs and observer trace/detail/bundle.
3. Fix stale snapshot gating after successful lazy install so the playbook proceeds to `run_tool`.
4. Re-deploy and repeat live playbook run with observer proof.

Completed:

- Added a regression test for successful lazy install with strict capability gate and stale/no snapshot.
- Updated playbook engine preflight so successful DB-backed module install/registry preflight is authoritative for the immediate command enqueue.

### 2026-04-28 Sixth Wave: Settings Calendar Editor

Current focus:

1. Continue removing operator-facing raw JSON from `/app/settings`.
2. Replace calendar holiday textarea with controlled date rows:
   - one row per holiday/exclusion;
   - add/remove actions;
   - API `holidays_json` generated automatically;
   - JSON visible only as a read-only preview.
3. Keep SLA/calendar setup dense and predictable for support/admin users.

Completed:

- Calendar holidays now use typed date inputs instead of a free-form textarea.
- SettingsPage regression covers routing/SLA/calendar bounded editors and verifies no textarea is left on the settings page.

### 2026-04-28 Seventh Wave: Module Policy Editor

Current focus:

1. Continue `/app/admin/modules` redesign around fast, predictable module publishing.
2. Replace normal operator JSON editors in tool policy with bounded controls:
   - lifecycle select;
   - metadata risk/kind/domain/origin/platforms/roles/scopes/flags;
   - dependencies and resources by named fields;
   - redaction flags and redact-field list;
   - presets as rows with id/label/description and `key=value` params;
   - errors and artifact kinds as simple line lists.
3. Keep schema JSON and validation/payload JSON as preview/advanced authoring surfaces until the schema-builder slice replaces them.

Completed:

- `modules-panel` no longer exposes metadata/presets/dependencies/resources/redaction/error/artifact policy as raw JSON textareas.
- ModulesPanel regression now verifies bounded tool policy controls and absence of the removed JSON editors.

### 2026-04-28 Eighth Wave: Module Schema Builder

Current focus:

1. Remove the remaining normal JSON authoring surface for module tool schemas.
2. Add a reusable schema-object builder for `type: object` JSON Schema:
   - field rows with name/type/description/default/enum/required;
   - generated `properties` and `required`;
   - read-only Schema preview.
3. Use it for `params_schema` and `output_schema` in `/app/admin/modules`.

Completed:

- `SchemaObjectBuilder` now builds object schemas without an editable JSON textarea.
- Module tool editor uses the builder for Params schema and Output schema.
- Focused regression covers builder output and module UI absence of schema JSON textareas.

### 2026-04-28 Ninth Wave: Runtime Params Without JSON

Current focus:

1. Remove the remaining normal JSON fallback from runtime parameter editing:
   - `SchemaParamEditor` must render object params as bounded nested field groups.
   - Array params must render as explicit item rows with add/remove controls.
   - JSON preview/debug can remain read-only elsewhere, but launch/config flows must not ask operators to hand-write JSON.
2. Preserve one shared behavior across:
   - playbook block command params in `/app/admin/playbooks`;
   - support ticket tool launch in `/app/tickets/:ticketId`;
   - support workspace tool launch panels.
3. Carry nested schema metadata from playbook catalog normalization into the shared editor so module-defined `properties` and `items` become real controls.
4. Verify in TDD order:
   - focused `SchemaParamEditor` red/green tests;
   - playbook builder regression for object/array params;
   - webapp test/build;
   - workspace verification;
   - live browser check on `http://192.168.100.17:8666/admin`, then stop the remote server.

Completed:

- `SchemaParamEditor` now renders object params as nested controls and array params as explicit rows with add/remove controls.
- Playbook catalog normalization preserves nested `properties` and `items` so module command params are editable without JSON.
- Focused regressions cover object/array runtime params and playbook save payload generation without `... JSON` textareas.

## 2026-04-29 RBAC Access Control Center

Status: in progress; first read-only access-control slice implemented locally.

### Goal

Create a full RBAC management surface for the new admin/support workspaces: admins should be able to manage users, access groups, queue membership, workspace visibility, module/tool launch rights and ticket actions from one predictable SaaS-style panel, while the server remains the source of truth for every permission check.

### Constraints

- Work only in `C:\Users\admin-2\CodexProjects\pc_client`.
- Do not add a new UI library; use the existing React/Tailwind primitives.
- Keep `AuthContext` as the only source of actor identity and actor role.
- Keep existing role behavior compatible: `admin`, `support`, `auditor`, `user`, `agent`, `system`.
- Do not replace queue membership with generic groups; queue membership remains the authoritative visibility boundary for support ticket work.
- Do not trust frontend visibility for security. UI hides/disables elements for clarity, backend enforces all mutations.
- Avoid raw JSON authoring. Permission sets, groups, queue memberships and module access must be controlled fields/toggles/selects with generated payloads.
- Preserve legacy admin users endpoints until the React replacement has parity.

### Current Baseline

- Backend role checks exist through `server/auth/context.py` and `server/auth/middleware.py`.
- DB-backed UI users already exist through `server/auth/admin_users_handlers.py` and `server/app/repos/ui_users_repo.py`.
- React workspace access currently comes from `GET /api/web/session/me` via `default_workspace` and `available_workspaces`.
- Support ticket visibility is already constrained by queue membership and assignee logic in the ticket/support backend.
- Module/tool policy has `metadata.allow_roles`, but it is not part of one central RBAC panel.
- There is no unified React panel for groups, permission matrix, element visibility or effective access preview.

### Target Model

1. **Users**
   - Existing `ui_users` stay the login/account source.
   - User row shows login, role, active state, actor id, group memberships, queue memberships, last audit facts where available.
   - Admin can create/deactivate users, change role, reset password and assign groups/queues from one page.

2. **Roles**
   - Built-in roles stay stable and not user-editable as arbitrary strings.
   - Role permissions are presented as a readable matrix:
     - workspace access;
     - admin pages;
     - support pages;
     - ticket read/write actions;
     - queue settings;
     - module authoring;
     - module/tool launch;
     - observer access;
     - runtime/control actions.
   - The first implementation can keep built-in role defaults server-defined, then allow additive group grants where safe.

3. **Access Groups**
   - Add explicit admin-defined groups such as `support_l1`, `support_l2`, `ops_admin`, `auditors`.
   - Groups can grant permission codes and queue memberships.
   - A user can have multiple groups.
   - Effective permissions are the union of role defaults, group grants and direct queue memberships, with backend-deny rules still taking precedence.

4. **Permission Catalog**
   - Introduce a typed permission catalog instead of free-form JSON:
     - `workspace.admin.view`
     - `workspace.support.view`
     - `admin.inventory.view`
     - `admin.inventory.manage_tokens`
     - `admin.modules.view`
     - `admin.modules.author`
     - `admin.playbooks.view`
     - `admin.playbooks.publish`
     - `admin.forms.view`
     - `admin.forms.publish`
     - `admin.observer.view`
     - `settings.view`
     - `settings.manage_queues`
     - `settings.manage_routing`
     - `ticket.queue.view`
     - `ticket.detail.view`
     - `ticket.status.change`
     - `ticket.queue.change`
     - `ticket.assign`
     - `ticket.comment.public`
     - `ticket.comment.internal`
     - `ticket.passport.manage`
     - `ticket.playbook.run`
     - `ticket.tool.run`
     - `module.tool.run.low_risk`
     - `module.tool.run.high_risk`
     - `observer.trace.view`
     - `control.server.view`
     - `control.server.action`
   - Catalog labels must be human-readable and grouped by page/domain.

5. **Queues**
   - Keep `ticket_queue_members` and `role_in_queue`.
   - New RBAC UI should show queue access as a first-class tab:
     - queue list;
     - members;
     - role in queue: primary/backup/lead/observer;
     - effective ticket visibility preview for selected support user.
   - Group-to-queue membership can be added as a separate mapping if direct per-user queue management becomes too noisy.

6. **UI Visibility**
   - Server session payload should expose typed capabilities/effective permissions for the current user.
   - React shell uses those capabilities to hide or disable navigation entries, page actions, dangerous buttons and ticket controls.
   - Page-level gates stay route-based; element-level visibility uses a shared helper instead of scattered role comparisons.
   - Hidden/disabled UI is convenience only; backend still checks permission on every write.

7. **Audit And Explainability**
   - Every RBAC mutation writes audit:
     - who changed;
     - target user/group/permission/queue;
     - before/after;
     - reason if provided.
   - Access Center includes an “Effective access” inspector:
     - selected user;
     - role defaults;
     - groups;
     - queues;
     - module/tool grants;
     - final permissions.

### Backend Implementation Plan

1. Inventory existing access checks:
   - map all `require_auth(...)` usage;
   - map queue-membership ticket visibility checks;
   - map React route/workspace gates;
   - map module/tool `allow_roles` checks.
2. Add a permission catalog module:
   - server-owned list of known permission codes;
   - labels, descriptions, domain/page grouping;
   - built-in role defaults.
3. Add DB schema if needed:
   - `access_groups`;
   - `access_group_members`;
   - `access_group_permissions`;
   - optional `access_group_queue_members`;
   - `access_audit` or reuse existing audit table if it fits.
4. Add `AccessControlService`:
   - resolve role defaults;
   - resolve user groups;
   - resolve direct/group queue memberships;
   - calculate effective permissions;
   - answer `can(actor, permission, resource)` for typed server handlers.
5. Add typed web API under `/api/web/admin/access/*`:
   - `GET /catalog`;
   - `GET /summary`;
   - `GET /users`;
   - `POST/PATCH /users`;
   - `GET/POST/PATCH/DELETE /groups`;
   - `POST/DELETE /groups/{group_id}/members`;
   - `PUT /groups/{group_id}/permissions`;
   - `PUT /groups/{group_id}/queues`;
   - `GET /effective-access?actor_id=...`;
   - all write endpoints admin-only.
6. Extend session payload:
   - keep `default_workspace` and `available_workspaces`;
   - add `capabilities` or `permissions` as a typed list;
   - add a version/hash so the UI can refresh when permissions change.
7. Gradually replace direct role checks in new web handlers with permission checks where the permission model is ready:
   - start with admin/support page gates and high-risk actions;
   - keep legacy role checks as a hard floor during transition.
8. Add server tests:
   - permission catalog defaults;
   - group membership effective permissions;
   - admin-only RBAC mutations;
   - support without permission cannot access admin APIs;
   - queue membership still limits ticket visibility;
   - module/tool run permission does not bypass existing tool policy.

### Frontend Implementation Plan

1. Add typed access API client and DTOs in `webapp/src/features/access-control/`.
2. Add shared permission helpers:
   - `hasPermission(session, code)`;
   - `hasAnyPermission(session, codes)`;
   - `canShowNavItem(session, navItem)`;
   - `canUseTicketAction(session, action)`.
3. Add `/app/admin/access` route and navigation entry visible to admins with access-control permission.
4. Build the Access Control Center with tabs:
   - **Users**: account list, role, active state, groups, queue badges, quick actions.
   - **Groups**: group CRUD, member management, permission assignments.
   - **Permissions Matrix**: grouped matrix by domain/page/action with role defaults and group grants.
   - **Queues**: queue membership management and group/direct membership preview.
   - **Modules & Tools**: map module/tool `allow_roles` and future permission requirements into a readable launch policy view.
   - **Effective Access**: select user and inspect final workspace/pages/actions/queues/modules.
   - **Audit**: recent RBAC changes.
5. Apply capability-based visibility to the shell:
   - workspace switcher;
   - sidebar navigation;
   - admin route cards;
   - settings/ticket/admin action buttons.
6. Apply capability hints in ticket detail:
   - disabled state with reason for status change, queue switch, assign, internal comment, passport edit, playbook/tool launch.
7. Apply capability hints in admin modules/playbooks/forms:
   - view-only mode when a user can view but not publish/run/change.
8. Add frontend tests:
   - access page renders catalog/groups/users;
   - permission toggles generate typed payloads;
   - support user cannot see admin nav;
   - admin can see Access Control;
   - disabled ticket actions show reasons;
   - no raw JSON textareas in the Access Control Center.

### UX Requirements

- Dense SaaS admin style, closer to inventory/playbook builder than to a marketing page.
- No decorative cards inside cards.
- Tables must be scannable with filters/search and compact side inspector.
- Use controlled toggles, checkboxes, selects and segmented tabs.
- Permission names must be Russian operator labels with stable technical codes shown only as secondary detail or tooltip.
- “Effective access” is mandatory so admins can verify why a support user sees or cannot see a queue/action.
- Dangerous changes require explicit save/apply action, not instant mutation on toggle.

### Documentation Plan

- Update `server/docs/SECURITY_AND_AUTH.md` with:
  - permission catalog;
  - groups;
  - effective permission resolution;
  - UI visibility vs backend enforcement.
- Update `server/docs/CODEMAP.md` with new access-control service/API and React route.
- Update `docs/QUICK_LOOKUP.md` if `/app/admin/access` becomes the canonical RBAC start point.
- Update `scripts/navigation_catalog.py` if new access-control files become primary navigation targets.
- Keep `PLANS.md` current after each implementation slice.

### Verification Plan

1. Local setup:
   - `python scripts/bootstrap_web_toolchain.py`
2. Backend:
   - focused pytest for access-control service/API;
   - focused ticket queue RBAC regression;
   - focused module/tool permission regression;
   - `python scripts/verify_workspace.py`
3. Frontend:
   - focused Vitest for Access Control Center and permission-gated shell/ticket controls;
   - `pnpm --dir webapp run test`;
   - `pnpm --dir webapp run build`.
4. Deploy/live:
   - `python scripts/deploy_workspace_to_remote.py`;
   - `python scripts/release_server_to_remote.py`;
   - `python scripts/manage_remote_stack.py restart server`;
   - browser check only on `http://192.168.100.17:8666/admin`.
5. Live scenarios:
   - admin opens `/app/admin/access`;
   - admin creates group and assigns support user;
   - support user sees only support workspace;
   - support user sees only allowed queues;
   - queue switch from one queue to another is allowed only when membership permits it;
   - support user without admin permission cannot open `/app/admin/*`;
   - auditor/read-only user sees disabled mutations;
   - module/tool/playbook launch visibility follows permissions and existing backend policy;
   - backend returns 403 when UI-hidden action is called directly.
6. After live check:
   - save screenshots/JSON artifacts under `artifacts/browser_checks/` or `artifacts/live_checks/`;
   - stop the remote server unless the user explicitly asks to leave it running.

### Efficient Execution Order

1. Build backend permission catalog and effective-access resolver first.
2. Add API and tests around effective access before frontend work.
3. Extend session payload with permissions and wire shell visibility.
4. Build Access Control Center read-only view.
5. Add group/user/permission/queue mutations with explicit save actions.
6. Apply permissions to ticket/admin/module/playbook controls.
7. Run full local verification.
8. Deploy and perform live RBAC, queue-routing and module-launch checks.

### 2026-04-29 First Slice Completed Locally

- Added server-owned permission catalog, role defaults and `permissions_version`.
- Added typed read-only admin access endpoints:
  - `GET /api/web/admin/access/catalog`;
  - `GET /api/web/admin/access/summary`;
  - `GET /api/web/admin/access/effective`.
- Extended `GET /api/web/session/me` with effective role permissions so the React shell can hide permission-gated navigation.
- Added `/app/admin/access` with a dense read-only Access Control Center: users, queues, built-in roles, grouped permission catalog and effective access inspector.
- Wired the admin sidebar to hide `Access Control` unless the session has `admin.access.view`.
- Deferred CRUD groups/memberships/audit writes to the next slice; current effective access is role defaults plus direct queue membership.

### Handoff

Start from:

- `server/auth/context.py`
- `server/auth/middleware.py`
- `server/auth/admin_users_handlers.py`
- `server/app/repos/ui_users_repo.py`
- `server/web_api/session_handlers.py`
- `server/web_api/settings_handlers.py`
- `server/web_api/support_handlers.py`
- `server/tickets/admin_config_handlers.py`
- `server/app/repos/ticket_admin_config_repo.py`
- `server/app/repos/ticket_events_repo.py`
- `webapp/src/features/auth/workspace-access.ts`
- `webapp/src/app/router.tsx`
- `webapp/src/app/layouts/app-shell.tsx`
- `webapp/src/app/navigation.tsx`
- `webapp/src/pages/tickets/detail-page.tsx`
- `webapp/src/features/modules/modules-panel.tsx`
- `webapp/src/features/playbooks/playbook-builder-panel.tsx`
- `webapp/src/pages/settings/index.tsx`

## 2026-04-27 Webapp Unification And API Boundary

Status: local implementation verified; remote/live signoff pending.

### Goal

Finish the new React web stack in three implementation tracks:

1. Split the current React bundle so large admin/support workspaces do not ship as one heavy chunk.
2. Move requester-facing `/help` and `/ticket` flows into React under `/app/help` and `/app/ticket/*`, keeping legacy escape routes during cutover.
3. Normalize React API calls behind typed `/api/web/*` boundaries where practical, starting with observer, notifications and module workbench calls.

### Plan

- Detailed implementation plan: `docs/superpowers/plans/2026-04-27-webapp-unification-and-api-boundary.md`.
- Phase 1: lazy route boundaries and nested admin panel splitting; verify `pnpm --dir webapp run test`, `pnpm --dir webapp run build`, and cutover preflight.
- Phase 2: requester API client, React `/app/help`, React requester ticket view, and controlled `/help`/`/ticket` cutover flags defaulting off.
- Phase 3: endpoint inventory and typed `/api/web/*` aliases for observer, notifications and modules workbench; migrate React clients without removing legacy endpoints.
- Phase 4: remote browser signoff and docs sync.

### 2026-04-27 Progress

- Done locally: React route-level lazy imports, public `/app/help`, public `/app/ticket` / `/app/ticket/:ticketId`, `/help` and `/ticket` cutover flags defaulting off, and typed web aliases for observer, notifications, module workbench and tech alerts.
- React no longer calls the migrated legacy admin/module/notification URLs directly; remaining non-`/api/web/*` calls are intentional public requester APIs or support/ticket runtime APIs that stay outside this pass.
- Verified locally with frontend tests/build, static-page handler tests, Python compile checks, and cutover preflight. Remote browser signoff and deploy remain next.

### Verification Target

- `python scripts/bootstrap_web_toolchain.py`
- `pnpm --dir webapp run test`
- `pnpm --dir webapp run build`
- `python -m pytest server/tests/test_static_pages_handlers.py -q`
- `python -m pytest server/tests/test_web_admin_api.py -q`
- `python scripts/check_webapp_cutover.py --json`
- `python scripts/verify_workspace.py`
- `pnpm --dir webapp run check:remote:webapp -- --base-url http://192.168.100.17:8666`

## 2026-04-27 Observer Coverage For Agent Auth, Update And Runtime

Status: in progress.

### Problem

- Agent authorization and runtime lifecycle already write `agent_runtime_audit` records, but the observer projection only picked those records up when they were linked to an operation or ticket.
- Manual provisioning, invalid-token handshakes and other auth-only failures have no operation, so `/api/admin/tech/observer/search`, diagnostics bundles and quick dangerous-flow summaries could miss the exact failing step.
- Agent updates are better covered because they have `operation.kind=agent_update`, but update runtime audit should stay attached to the same trace and visible in bundle/detail.

### Plan

1. Add first-class observer classification for runtime audit events:
   - `device_provisioning` for connection request create/approve/reject/token-delivery/token-limit/fingerprint issues;
   - `agent_auth` for invalid/revoked token and handshake auth failures;
   - `agent_runtime` for lifecycle/offline/superseded runtime events;
   - keep operation-backed `agent_update` traces authoritative for updates.
2. Project operation-less runtime audit records as synthetic observer traces so search, trace detail and diagnostics bundle can find them by event name, device id and root kind.
3. Treat warning-level auth/provisioning failures as observer signatures where they represent an actionable problem.
4. Include auth/provisioning/runtime trace kinds in hot-trace and dangerous-flow summaries.
5. Add regression tests for:
   - search by `connection_request` and `invalid_token`;
   - `root_kind=device_provisioning` trace search;
   - diagnostics bundle by auth/provisioning query;
   - quick dangerous-flow visibility.
6. Update observer docs, CODEMAP and QUICK_LOOKUP.

### Verification Target

- `python -m pytest server/tests/test_observer_diagnostics_api.py -q`
- `python -m pytest server/tests/test_observer_v2_api.py -q`
- `python -m pytest server/tests/test_connection_request_api.py -q`
- `python scripts/verify_workspace.py`
- Live Linux smoke + browser/API check at `http://192.168.100.17:8666/admin`.

## 2026-04-27 Observer Coverage Closure And Agent Telemetry Channel

Status: planned.

Detailed implementation and handoff plan:

- `docs/superpowers/plans/2026-04-27-observer-coverage-closure-agent-telemetry.md`

### Goal

Close the known observer blind spots so support operators and Codex can diagnose authorization, updates, module reconcile, playbook execution, web API failures and agent-side failures through one server-side observer surface.

### Core Decision

Add a narrow agent observer/telemetry channel, but do not create a second independent observer system inside the agent.

The agent may keep local `action_trace.jsonl` as its durable local black box, but important lifecycle/action events must be uploaded to the server as bounded, redacted telemetry and projected into the existing server observer tables. The server remains the canonical query surface for support UI, diagnostics bundles and Codex API access.

### Scope

Covered in this plan:

- server observer projection gaps;
- module reconcile and module auto-install failures;
- playbook run/step/preflight visibility;
- web auth/RBAC/API boundary failures;
- agent local black-box upload for crashes, startup, update launcher, WS reconnect and tool execution;
- observer runtime self-health.

Out of scope for this plan:

- replacing existing operations/ticket/device event contracts;
- making routing fully editable as arbitrary automation;
- streaming raw logs/tokens/screenshots without redaction and retention limits.

### Architecture

Use one canonical observer graph on the server:

- existing sources stay: `operations`, `ticket_events`, `device_events`, `agent_runtime_audit`;
- add server-side source rows for `playbook_step_run` and selected system flows;
- add bounded `agent_observer_events` or equivalent ingestion source for agent local telemetry;
- projector materializes all sources into `observer_traces`, `observer_spans`, signatures and degradations.

Agent-side telemetry should be batched, redacted, idempotent and best-effort:

- local append-only queue on agent;
- upload after successful auth/handshake or via existing WS/RPC channel;
- no raw token, password, cookie, consent token, or full command output by default;
- server accepts only known event schemas and applies retention/sampling.

### Implementation Plan

1. Inventory trace sources and define a coverage matrix:
   - rows: auth/provisioning, update, module reconcile, module live test, playbook, web auth, ticket routing, notification delivery, agent startup/crash, WS reconnect, tool execution;
   - columns: source table, root_kind, spans, signatures, UI entrypoint, Codex diagnostics bundle.
2. Add first-class projection for playbook runs:
   - `root_kind=playbook_run`;
   - spans for preflight, skipped decision/local steps, module install precheck, command dispatch, retry, result normalization and ticket fact attachment;
   - link each operation-backed step to its operation trace.
3. Make module reconcile observer-visible:
   - write `agent_runtime_audit` or a dedicated system audit record for desired-state install/remove failures before enqueue;
   - emit `root_kind=module_reconcile` or map to `module_install` / `module_remove` with `source=reconcile`;
   - produce signatures for missing package, platform mismatch, agent offline and enqueue failure.
4. Add web auth/API boundary observability:
   - record rate-limited audit events for repeated 401/403 on important `/api/web/*`, `/api/tickets*`, `/api/admin/*` paths;
   - group by route, actor role, error_code and session state;
   - expose in diagnostics bundle and admin observer.
5. Add agent observer telemetry ingestion:
   - define schema for `agent.startup`, `agent.shutdown`, `agent.crash_detected`, `agent.ws.reconnect`, `agent.update.launcher`, `agent.update.apply`, `agent.tool.step`, `agent.module.install_step`;
   - implement local agent queue using the existing action trace recorder as source;
   - upload compact batches with sequence/idempotency keys;
   - store server-side rows linked by `device_id`, `operation_id`, `trace_id`, `tool_name`, `module_name`.
6. Project agent telemetry into server observer:
   - attach telemetry events to operation traces when `operation_id`/`trace_id` exists;
   - create synthetic `agent_runtime` traces for startup/crash/reconnect events without an operation;
   - create signatures for repeated crash/update/reconnect/tool-step failures.
7. Add observer self-health:
   - expose projector backlog, last error and stale projection as a trace-visible system health event;
   - keep `/api/web/admin/observer/runtime` as quick status;
   - add diagnostics bundle recommendations when projection is lagging.
8. Update UI:
   - `/app/admin/observer` root_kind filters include playbook, module reconcile and web auth/API;
   - trace detail shows playbook step graph and agent telemetry spans;
   - ticket Automation overlay links to the exact failing playbook step trace.
9. Update API for Codex/support:
   - diagnostics bundle accepts `playbook_run_id`, `step_run_id`, `route`, `root_kind=web_auth`, `root_kind=module_reconcile`;
   - bundle includes recent server logs only as fallback, with a flag when no first-class trace exists.
10. Add tests and canaries:
   - unit tests for projection from every new source;
   - integration tests for playbook preflight fail, reconcile offline agent, repeated web auth failure, agent telemetry upload and projection;
   - live canary for Linux agent startup/tool/update telemetry;
   - Windows live agent telemetry canary when a Windows lab agent is available.

### Verification Target

- `python -m pytest server/tests/test_observer_diagnostics_api.py -q`
- `python -m pytest server/tests/test_observer_v2_api.py -q`
- `python -m pytest server/tests/test_playbook_scenarios_no_db.py -q`
- new tests for playbook observer projection, module reconcile observer projection, web auth observer audit and agent telemetry ingestion;
- targeted agent tests for telemetry queue/upload/redaction;
- `python scripts/verify_workspace.py`;
- browser check on `http://192.168.100.17:8666/app/admin/observer`;
- live Linux agent check for startup, reconnect and tool telemetry;
- optional Windows lab check before claiming Windows telemetry coverage.

### Handoff

Start from:

- `server/observer/service.py`
- `server/observer/runtime.py`
- `server/tech/handlers.py`
- `server/app/services/playbook_engine.py`
- `server/app/repos/playbook_repo.py`
- `server/modules/reconcile.py`
- `server/auth/middleware.py`
- `server/web_api/admin_handlers.py`
- `server/websocket/agent_handshake.py`
- `server/websocket/agent_handler.py`
- `pc_agent/core/action_trace.py`
- `pc_agent/core/orchestrator.py`
- `pc_agent/ws_agent.py`
- `pc_agent/ws_agent_runtime_helpers.py`
- `webapp/src/features/tech/*`
- `webapp/src/pages/admin/observer-page.tsx`
- `server/docs/OBSERVER_LAYER.md`
- `server/docs/OBSERVER_AUTHORING_RULES.md`
- `server/docs/CODEMAP.md`
- `pc_agent/docs/CODEMAP.md`
- `docs/QUICK_LOOKUP.md`

Design rule: every newly observed problem must answer three questions in the UI/API: what failed, at which exact step, and what source row/event proves it.

### 2026-04-28 Follow-up: Canary, Live Agent Checks And UX

Status: in progress.

Detailed follow-up plan:

- `docs/superpowers/plans/2026-04-28-observer-canary-live-agent-ux.md`

Current execution focus:

1. Extend the live observer canary suite so it verifies first-class traces for `module_reconcile`, `playbook_run`, `web_auth` and `observer_runtime`.
2. Add report-level coverage closure output in JSON and Markdown.
3. Verify the current agent release is present in the stable build registry for both `windows_amd64` and `linux_alt_x86_64`.
4. Improve `/app/admin/observer` trace detail UX with evidence-source and diagnostics-bundle counters.

## 2026-04-27 Connection Request Duplicate Approval Bug

Status: fixed locally; release verification in progress.

### Findings

- The observer layer did not expose this as a first-class provisioning trace; the useful facts came from `connection_requests`, `agent_tokens` and server runtime audit/logs.
- Real DB showed duplicate approved rows for the same `device_id` on `Sirius` and `AD-MAIN`.
- Root cause: while waiting for approval, the agent sends heartbeat `POST /api/connection_request`; if admin approval happens just before that heartbeat, the server no longer sees a `pending` row and created a fresh pending request.
- Secondary issue: old `set_approval_token` updated every approved row for the same device, so legacy duplicate approved rows could retain an undelivered approval token.

### Fix

- Manual provisioning now treats post-approval heartbeats as "already approved, waiting for token delivery" and does not create a second pending row.
- New approval tokens are stored only on the latest approved request.
- Status consumption marks all undelivered approved-token rows for the device as delivered, preventing legacy duplicate rows from returning a token more than once.

### Verification

- Added regression tests for the approval heartbeat race and legacy duplicate approval-token consumption.
- Ran focused server and agent connection-request tests successfully.

## 2026-04-27 Playbook Low-Code Canvas UI

Status: completed and verified on the Linux stand.

### Goal

Rebuild `/app/admin/playbooks` from a linear block list into a real low-code builder:

- module command palette on the left;
- draggable block canvas with a visible grid;
- module-like blocks that can be moved and edited;
- command selector inside each diagnostic block;
- selected-block inspector with presets, params, output contract and error handling;
- preview/result panel for the selected command contract;
- preserve the current server save contract and published playbook runtime.

### Implementation Notes

- Keep the existing typed API: `GET /api/web/admin/playbooks/catalog` and `POST /api/web/admin/playbooks/save`.
- Store canvas positions in client state for now; save order is derived by block position from top to bottom.
- Use native HTML drag/drop and pointer movement to avoid a new dependency.
- Keep remediation out of the builder; this pass is diagnostic-only.

### Verification

- Update the playbook panel unit test for drag/drop and command selection.
- Ran targeted playbook tests, webapp build, `verify_workspace.py`, release smoke, and a browser check on `http://192.168.100.17:8666/app/admin/playbooks`.
- Live browser check published smoke playbook `codex_canvas_smoke_1777297678971` after changing a block command, adding a decision block, dragging a block on the canvas, and saving successfully.

## 2026-04-27 Self-Healing Automation And Playbook Orchestration

Status: core implementation completed locally; observer drilldown and full ticket playbook runner remain next-stage work.

### Goal

Build self-healing automation around the existing module/tool runtime:

- modules remain installable containers;
- atomic playbook units are module commands/tools;
- playbooks orchestrate commands, conditions, install/preflight flows, retries and fact packages;
- support sees every step, including module install and infrastructure failures, with observer trace drilldown.

### Core Decisions

- Do not replace low-level system primitives with editable playbooks.
- Keep critical primitives in code: module preflight, module install, activate, sync toolset, verify tool, operation wait, agent online check, ticket fact attachment.
- Represent those primitives as protected/system playbook blocks in the UI so operators can see and tune allowed parameters without breaking bootstrap behavior.
- Playbook runtime should operate on tool/command manifests, not on module names directly.
- Module auto-install should happen at the module-owner level, but be visible as a step/sub-playbook result.
- Presets from tool manifests must be expanded into concrete params at save/run time; the agent should receive normal command params, not only `preset_id`.

### Target Model

1. A playbook step references an atomic command such as `system.collect` or `ip_address.get_ip`.
2. The server resolves the owning module for the command from the preferred server module registry.
3. Preflight reports:
   - command source: builtin, device snapshot, server registry;
   - owning module/version;
   - install state;
   - platform compatibility;
   - min agent version;
   - risk/consent requirements;
   - output schema and known error codes.
4. At execution time, the engine starts the next eligible step.
5. If the command owner module is missing on the agent, the engine runs a protected install flow before the command.
6. Install flow results become first-class step facts:
   - `already_installed`
   - `installed`
   - `module_not_on_server`
   - `platform_mismatch`
   - `agent_version_too_old`
   - `download_failed`
   - `activate_failed`
   - `toolset_sync_failed`
   - `install_timeout`
7. Decision blocks can branch on both command results and install/preflight results.
8. Final output is attached to the ticket as a structured fact package.

### UI Direction

- `/app/admin/playbooks` should use the real dynamic tool catalog, not a static list of three diagnostic blocks.
- Tool picker groups commands by module and shows:
  - tool name;
  - module/version;
  - source: agent/server/builtin;
  - install required;
  - supported platforms;
  - min agent version;
  - risk and consent;
  - presets and params schema;
  - output schema and error codes.
- Step inspector should provide:
  - preset selector;
  - generated params preview;
  - manual param overrides from `params_schema`;
  - retry/timeout/continue-on-error;
  - condition builder based on previous step output/error/status;
  - install policy: `lazy`, `preinstall`, `fail_if_missing`, `skip_if_missing`.
- Ticket UI should expose an Automation overlay/modal:
  - run one command;
  - run a playbook;
  - inspect preflight;
  - see progress by step;
  - open observer trace for the failed step.

### Observer Direction

Observer should be attached to playbook execution as a first-class execution graph:

- root trace: playbook run;
- spans:
  - preflight;
  - module install sub-flow;
  - command dispatch;
  - agent policy/consent;
  - module execution;
  - result normalization;
  - ticket fact attachment;
- every step has `playbook_run_id`, `step_key`, `operation_id`, `tool_name`, `module_name`, `trace_id`;
- UI can show exactly where the failure happened, not just "playbook failed".

### Routing Question

Ticket routing can be moved partly into this model, but not as fully free-form automation.

Recommended boundary:

- Keep the existing routing service as the authoritative deterministic engine.
- Add a visible protected routing playbook/view that shows routing as steps:
  - normalize form/request data;
  - match request kind;
  - match registry/service/location;
  - choose queue;
  - choose priority/SLA;
  - optional auto-assign;
  - write routing reason.
- Allow admins to edit routing rules through the existing safe rule model, while observer shows the step-by-step routing trace.
- Do not allow arbitrary remediation/action blocks inside routing until there is explicit approval/governance.

This gives transparency and observer drilldown without turning ticket routing into an unrestricted workflow engine.

### Implementation Plan

1. Add a playbook tool-catalog service that merges device snapshot tools and server registry tools.
2. Extend playbook manifest to v2 with required tools, install policy, output contract and preflight metadata.
3. Fix playbook runtime to use the existing module auto-install primitive before tool-backed steps.
4. Record install/preflight as explicit step runs or protected sub-step facts.
5. Fix actor role/auth context for playbook tool execution so diagnostic tools do not fail as `system`.
6. Expand presets into params for both command run and playbook step configuration.
7. Replace static diagnostic builder catalog with dynamic module-command blocks.
8. Add low-code condition builder for command output, error code and install errors.
9. Add ticket Automation overlay for running commands/playbooks with preflight preview.
10. Add observer trace links and step-level error drilldown.
11. Update docs/CODEMAP/QUICK_LOOKUP and add regression tests.

### Verification Target

- Server tests:
  - playbook manifest v2 normalization;
  - dynamic tool catalog from device/server registry;
  - module owner resolution for command;
  - playbook auto-install before command;
  - install failure branching;
  - actor role/policy regression;
  - preset expansion into params.
- Webapp tests:
  - playbook builder renders dynamic commands;
  - preset selector changes params preview;
  - condition builder can reference step status/output/error;
  - ticket Automation overlay can select command/playbook and show preflight.
- Live checks:
  - run playbook against Linux agent with builtin `system.collect`;
  - run playbook that requires server module auto-install, then command execution;
  - force install/preflight error and verify support-facing package plus observer step drilldown.

### Handoff

Start implementation from:

- `server/tools/service.py`
- `server/app/services/playbook_engine.py`
- `server/app/services/playbook_capability.py`
- `server/playbooks/catalog.py`
- `server/web_api/admin_handlers.py`
- `server/web_api/support_handlers.py`
- `webapp/src/features/playbooks/*`
- `webapp/src/features/queues/*`
- `webapp/src/pages/tickets/detail-page.tsx`
- `pc_agent/core/orchestrator.py`
- `pc_agent/core/registry.py`

Before frontend commands, run:

- `python scripts/bootstrap_web_toolchain.py`

Before any completion claim, run focused pytest/vitest/build plus `python scripts/verify_workspace.py`, then live browser check at `http://192.168.100.17:8666/admin`.

### 2026-04-27 Implementation Notes

Completed in this pass:

- Added `server/playbooks/tool_catalog.py` for normalized atomic command manifests.
- Playbook manifest is now saved as `pc_client.playbook.self_healing.v2` with `required_tools`, install policy, output schema, presets, platforms and min agent version.
- `/api/web/admin/playbooks/catalog` now merges the static diagnostic starter blocks with installable commands from the preferred server module registry.
- Playbook execution now runs the existing module auto-install preflight before tool-backed steps. Install/preflight failures become failed step runs with `stage=module_install` or `stage=capability_gate` and are not enqueued to the agent.
- Playbook tool dispatch now uses the support actor role for diagnostic commands instead of `system`.
- Support tool runs and playbook builder steps expand manifest presets into concrete params; the agent no longer depends on receiving only `preset_id`.
- `/app/admin/playbooks` shows module/source/install/platform/min-agent metadata and lets an operator select presets and inspect/edit params JSON per step.
- Ticket tool surfaces now carry preset params to the server, and the server still re-expands the preset before dispatch for consistency.

### 2026-04-27 Output Contract Tightening

Completed in this pass:

- Module manifest normalization now preserves a separate tool-level `output_contract` instead of relying on verbose `output_schema`.
- Declared `output_contract.status_values` must be explicit and unique; `success_values` / `error_values` are checked against the declared status set.
- `server/playbooks/tool_catalog.py` derives `condition_hints` from `output_contract` and known `error_codes` so the low-code builder can offer predictable condition templates.
- Saved playbook `required_tools` now carry `output_schema`, `output_contract` and `condition_hints` separately.
- `/app/admin/playbooks` displays status path, allowed status values, summary path and error codes for each command block, and decision blocks can insert a quick condition from previous command output.

Deferred to the observer stage:

- First-class observer spans for playbook root, preflight, install, command dispatch and ticket fact attachment.
- A dedicated ticket Automation modal for launching full playbooks with preflight preview and step progress.
- Editable protected routing visualization over the existing routing service.

### 2026-04-27 Module Authoring API/UI Notes

Completed in this pass:

- Added headless module authoring API:
  - `GET /api/modules/authoring/catalog`
  - `POST /api/modules/authoring/validate`
  - `POST /api/modules/authoring/publish`
- The headless endpoints reuse the existing workbench package builder, preflight, smoke check, ownership-conflict check and registry persistence path.
- Generated module packages now preserve explicit `output_contract` in `manifest.json`, `manifest_summary` and editable workbench previews.
- Agent-side `@exposed_tool` now accepts `output_contract` and includes it in registry/tool specs, so installed module commands can expose the same predictable contract.
- The module workbench UI now has a `Playbook decision contract` block in legacy guided/advanced editors and in the typed `/app/admin/modules` React editor, readiness chips/local validation for contract paths/status buckets, and API preview snippets pointing at the headless authoring endpoints.

Verification focus:

- Legacy module payloads without `output_contract` must stay valid.
- New playbook-ready module payloads should declare explicit `status_values`, `success_values`, `error_values`, `summary_path` and `error_code_path`.
- `/app/admin/playbooks` can consume these contracts through the existing module/tool catalog path.

### 2026-04-27 Module Test Harness And Windows Gate

Current plan:

1. [done] Make the existing server-side module smoke/runtime harness explicit and mandatory in authoring validation before publish.
2. [done] Store harness status in `validation_json.server_harness` for each module version.
3. [done] For Windows-targeted modules (`win32` / `windows*` platforms), show a warning that a Windows lab agent live test is still required before production/preferred rollout.
4. [done] Add a live-test API for a published module version that installs/runs the module command on a selected real agent and records the result back into `validation_json.live_tests`.
5. [done] Block setting a Windows-targeted module version as preferred unless `validation_json.live_tests` contains a passed Windows test on an agent whose version satisfies the module `min_agent_version`.
6. [done] Keep Linux/any modules publishable with server harness only; live lab testing stays optional unless the module targets Windows and is being promoted to preferred.

Verification target:

- Server tests for mandatory harness metadata, Windows warning, live-test recording and preferred gate.
- React test for the Windows lab warning in the module constructor.
- Live check on `/app/admin/modules` plus headless API validation on the Linux server.

### 2026-04-27 Module Lab Agent Selection And Observer Coverage

Goal:

- Let an operator choose the exact Linux or Windows lab agent used to live-test a published module version.
- Make module authoring and lab-test failures observer-visible now, so later UI can render a step-by-step problem map instead of a raw error message.

Current plan:

1. [done] Add a server API that returns compatible lab-agent candidates for a module version, including normalized platform, online state, agent version compatibility and warning reasons.
2. [done] Add a typed React lab-test panel on `/app/admin/modules` for the selected published version: platform filter, agent selector, tool selector and live-test run button.
3. [done] Wire the panel to the existing live-test endpoint using the chosen `device_id`; show the latest result and trace id.
4. [done] Add observer materialization for preferred gate and live-test steps: root trace, spans for candidate selection / install / run / gate, and error occurrence on terminal failures.
5. [done] Update docs/CODEMAP/observer docs and add automated tests for API candidates, UI selector and observer trace output.

Verification target:

- Server pytest for candidate filtering, explicit `device_id` live-test, preferred gate and observer trace rows.
- React test for selecting Linux/Windows lab agent and calling the live-test endpoint.
- `python scripts/verify_workspace.py`, webapp build/test and live browser/API check on `http://192.168.100.17:8666/app/admin/modules`.

### 2026-04-27 Observer Coverage Closure And Agent Telemetry

Current status:

1. [done] Added `agent_observer_events` source rows, websocket `agent_observer_batch` ingest, projection into observer spans/signatures and agent-side action-trace export/upload cursor.
2. [done] Added first-class `module_reconcile`, `playbook_run`, `web_auth` and `observer_runtime` root kinds for previously log-only gaps.
3. [done] Extended typed observer filters for `playbook_run_id`, `step_run_id` and `route`; React observer workbench serializes the new filters and shows source evidence from trace attrs.
4. [in progress] Verification/release: focused pytest and observer Vitest are green; full workspace verification, Linux/Windows agent release artifacts, deploy and live browser checks are next.

Verification target:

- `python scripts/verify_workspace.py`
- focused server/agent observer pytest
- `pnpm --dir webapp run test -- observer` and `pnpm --dir webapp run build`
- Windows release via `python pc_agent/build_windows_release_v2.py`
- Linux release on `/var/chat_bot/pc_client` via the documented PyInstaller specs, then upload both agent builds and verify `/app/admin/observer` live.

### 2026-04-28 Protocol/Outbox Review Fixes

Current plan:

1. [in progress] Add focused regressions for outbox retry NACK dedupe, sync waiter race, missing trace_id NACK, params immutability and protocol-version logging.
2. [pending] Fix server-side outbox ingest and command dispatch without touching unrelated worktree changes.
3. [pending] Bump/build the Windows agent release only for the `ws_agent.py` protocol-log change, upload it and promote it as the preferred version.
4. [pending] Run local verification, deploy server fixes to Linux with the project scripts, smoke the remote stack and stop the server afterwards unless a follow-up requires it online.

Verification target:

- `python -m pytest server/tests/test_agent_services_pipeline.py server/tests/test_protocol_waiters.py server/tests/test_tool_service_auto_install_no_db.py pc_agent/tests/test_ws_agent_protocol_logging.py -q`
- `python scripts/verify_workspace.py`
- `python pc_agent/build_windows_release_v2.py`
- remote deploy/release and agent-build promotion through the documented scripts/APIs.

### 2026-04-28 Eleventh Wave: Ticket FSM And Form Launch UX

Goal:

- Make ticket status management more operator-safe by separating allowed transitions from blocked transitions and explaining the guard before apply.
- Make the forms builder publish path safer by showing a validation summary and an end-to-end intake -> routing -> diagnostic playbook preview.

Current plan:

1. [completed] Add failing React tests for FSM-aware status actions: allowed transitions remain clickable, blocked transitions are visible with a reason, and blocked transitions cannot be applied.
2. [completed] Implement transition classification in `/app/tickets/:ticketId` without changing the typed server contract: use server-provided `status_options` as allowed transitions and derive blocked common statuses client-side for operator visibility.
3. [completed] Add failing React tests for forms builder validation summary and playbook launch preview: missing form keys, duplicate field keys, select/radio options, enabled trigger key, and publish disabled when hard validation fails.
4. [completed] Implement validation summary and a predictable launch preview panel next to route preview; keep serialized payload compatible with existing `playbook_triggers`.
5. [in progress] Run focused Vitest, full webapp test/build, `python scripts/verify_workspace.py`, deploy to Linux, live browser-check ticket/actions/forms, then stop the remote server.

Verification target:

- `pnpm --dir webapp exec vitest run src/pages/tickets/detail-page.test.tsx src/features/forms-builder/forms-builder-panel.test.tsx`
- `pnpm --dir webapp run test`
- `pnpm --dir webapp run build`
- `python scripts/verify_workspace.py`
- Browser live check on `http://192.168.100.17:8666/admin`, then `python scripts/manage_remote_stack.py stop server`.
