## 2026-04-19 agent runtime and launcher flow

- Local launcher/runtime work now starts from `pc_agent/launcher_portable_main.py`, `pc_agent/ws_agent.py`, `pc_agent/ui_bridge/api_server.py`, `pc_agent/ui_gui/main.py`, `pc_agent/ui_gui/main_window.py`, and `pc_agent/ui_gui/automation_controller.py`.
- Recommended-update diagnostics and local update state are surfaced through `pc_agent/ws_agent.py`, `pc_agent/ui_bridge/api_server.py`, `pc_agent/ui_gui/main_window.py`, and `pc_agent/docs/AGENT_UPDATE_WORKFLOW.md`.
- Agent-side observer correlation for tech drilldown now uses `pc_agent/core/action_trace.py` plus the `search_action_trace` RPC in `pc_agent/ws_agent.py`; admin tech trace detail can request compact agent actions via `include_agent_actions=1`, span materialization is opt-in with `sync_agent_actions=1`, the React workbench keeps fast trace detail separate from bundle action RPC, the server bounds large `details` payloads before sync/render, the agent stores server `trace_id` in orchestrator/module action rows, and the agent now emits guaranteed module-level execution breakdown (`module.resolve`, `module.execute`) even when a tool module has no custom runtime audit hooks.
- New module authoring canon: every new `BaseCollector` tool must emit observer breadcrumbs through `trace_span(...)` / `trace_event(...)`; generated workbench modules now scaffold this automatically in `server/utils/module_builder.py`, а `server/utils/module_observer_contract.py` + `python scripts/verify_workspace.py` теперь валят CI, если mandatory `tool.entry` span отсутствует.
- Live observer canary suite для опасных flow лежит в `python scripts/run_observer_canary_suite.py`: consent approve/deny/timeout, module install/update/remove, retry exhaustion, agent disconnect during operation, ws ack/nack/replay, source-coverage probes for `module_reconcile` / `playbook_run` / `web_auth` / `observer_runtime`, stable build registry checks for `windows_amd64` and `linux_alt_x86_64`, plus JSON/Markdown coverage reports.
- Local Windows launcher canary flow still goes through `python scripts/manage_local_agent.py start <name> --launcher`, with release artifacts built by `python pc_agent/build_windows_release_v2.py`.
- Server/control runtime wrappers (`scripts/run_server.py`, `scripts/run_control_plane.py`) now always bootstrap repo-root import visibility for shared packages like `shared.redaction`; when debugging Linux boot failures, treat those wrappers as canonical entrypoints instead of ad-hoc `python server/server.py`.

## 2026-04-22 update hardening

- Current launcher-based update debugging starts from `pc_agent/core/orchestrator.py`, `pc_agent/launcher/installer.py`, `pc_agent/launcher/launcher_main.py`, `pc_agent/ws_agent.py`, and `pc_agent/ui_gui/main_window.py`.
- Agent-side update scheduling is now single-flight: an existing `updates/pending_update.json` blocks overlapping update requests, while a repeated request with the same `operation_id` is treated as idempotent.
- Runtime/UI status now surfaces both `pending_update_*` and `update_request_*` through `GET /ui/agent/status`, so the local GUI can show `requesting -> requested -> pending_restart` instead of looking hung after `POST /ui/agent/update`.
- Launcher publish now uses staging + backup/restore, verify returns diagnostic output, `tar.gz` extraction restores POSIX mode bits and rejects links, and both launcher entrypoints roll back after repeated immediate crash of the newly switched version.

## 2026-04-28 local agent Qt GUI redesign

- Local agent GUI visual system now starts from `pc_agent/ui_gui/theme.py`: centralized light/dark tokens, main shell QSS, chat/list QSS, logo path and SVG icon asset helpers.
- Main Qt Widgets shell lives in `pc_agent/ui_gui/main_window.py` + `pc_agent/ui_gui/window_chrome.py`: Maria Agent sidebar, dashboard summary, custom cross-platform frameless title bar, navigation, profile/status cards, runtime/update status and settings theme switch stay backed by existing `ui_bridge` state.
- Ticket list visuals live in `pc_agent/ui_gui/chat_panel.py` + `pc_agent/ui_gui/tickets_list_model.py`: real `TicketsListModel` data, search/filter chips, card delegate, unread counters and double-click/open-chat flow.
- GUI line-icons live in `pc_agent/ui_gui/assets/icons/`; keep new icons and theme object names reflected in `pc_agent/docs/CODEMAP.md` and `scripts/navigation_catalog.py`.

## 2026-04-24 inventory cleanup and notifications

- Typed admin inventory now exposes device identity source and duplicate warnings via `GET /api/web/admin/devices`, and safe offline `env_uuid` duplicate cleanup goes through `POST /api/web/admin/devices/cleanup_env_duplicates`; the cleanup archives device rows through `DevicesRepo.archive_device()`, so active tokens and pending runtime work are revoked/cancelled instead of hard-deleted.
- `/app/admin/inventory` shows identity source badges (`windows_machine_guid`, `linux_machine_id`, `env_uuid`) and duplicate cleanup actions for old `ADMIN-2`-style test records. `/app/admin/access` is the RBAC start point for users, role defaults, access groups, permission grants, queue grants, audit and effective access. `/app/admin/settings` reuses the settings workspace with the `Уведомления` tab for in-app notification preferences, recent notifications and tech alerts.
- RBAC is now enforced server-side for typed support writes and settings writes, not only in React: ticket status/comments/passport/playbook/tool actions call `server/access_control/service.py::can()`, tool execution also checks low/high risk permissions, and `/app/settings` splits write UX/API guards into `settings.manage_queues` and `settings.manage_routing` with `required_permission` denial payloads.
- Notification APIs used by React now go through typed web aliases (`/api/web/notifications`, `/api/web/notifications/preferences`, `/api/web/notifications/unread_count`) instead of direct `/api/notifications*` calls.
- Device provisioning no longer relies on a hard "2 active tokens" limit. The agent sends `device_fingerprint` from `pc_agent/core/device_fingerprint.py`; the server compares hardware hashes in `auth/device_fingerprint.py`, tolerates one changed component, blocks clear mismatches as `DEVICE_FINGERPRINT_MISMATCH`, and rotates old active tokens when a new one is issued.
- `/app/admin/inventory` now has a device-token panel backed by `GET /api/web/admin/devices/{device_id}/tokens` and `POST /api/web/admin/devices/{device_id}/tokens/revoke`; token rows expose ISO `created_at`/`last_used_at` values for live browser rendering, and tech alerts also include `inventory_env_uuid_duplicates` and `inventory_devices_without_location`.
- `/app/admin/inventory` now presents a low-noise agent console: metrics, table, right-side details, tabs for agents / connection requests / tokens / rollout, and the existing manual connection-request flow is available through web-session aliases (`/api/web/admin/connection_policy`, `/api/web/admin/connection_requests*`) without opening legacy admin. The shell notification bell also counts pending connection requests alongside ticket notification unread count and links directly to `?panel=requests`.
- Manual provisioning is idempotent around approval races: if an agent heartbeat posts `POST /api/connection_request` after admin approve but before `GET /api/connection_request/status`, the server does not create a second pending approval prompt, and approval-token delivery is consumed once even for legacy duplicate approved rows.
- Connection request token exhaustion is now explicit: server returns `TOKEN_LIMIT_EXCEEDED` on 429 and marks the pending request metadata; the agent writes `connection_request_error.json`, emits `connection_rejected` with the server message, and GUI auth avoids persisting a permanent local reject flag for this transient block.
- Auth/provisioning/runtime lifecycle is observer-searchable even without an operation: `agent_runtime_audit` rows project into synthetic traces with `root_kind=device_provisioning`, `root_kind=agent_auth`, or `root_kind=agent_runtime`. For Codex/API debugging start with `/api/admin/tech/observer/search?q=connection_request`, `q=invalid_token`, or `/api/admin/tech/diagnostics/bundle?q=connection_request`.

## 2026-04-26 test and CI layering

- Canonical testing rules live in `docs/TESTING_RULES.md`.
- `scripts/run_ci_suite.py` now splits server pytest into `server_pytest_no_db`, `server_pytest_db_api`, and `server_pytest_agent_ws`; each server layer runs with `-vv --durations=80`, a 45 minute timeout, and `PC_CLIENT_PYTEST_WATCHDOG_SECONDS=120`.
- `server/tests/conftest.py` auto-marks tests that use `test_agent` as `agent_ws`/`integration` and prints all Python thread stacks when a watched test exceeds the watchdog threshold.

## 2026-04-26 diagnostic playbooks

- 2026-04-27 self-healing pass: playbooks now save manifest `pc_client.playbook.self_healing.v2`, `server/playbooks/tool_catalog.py` normalizes atomic command manifests, admin catalog merges static diagnostic starters with preferred server module tools, and `server/app/services/playbook_engine.py` runs module auto-install preflight before tool-backed steps with `stage=module_install` / `stage=capability_gate` failures; after a successful DB-backed preflight/install, the immediate `run_tool` enqueue does not wait for inventory/toolset snapshot convergence.
- 2026-04-27 canvas builder pass: `/app/admin/playbooks` is a low-code grid canvas backed by the same typed playbook catalog/save API. Operators drag atomic module commands from the palette, move blocks on the grid, choose the command inside each module-like block, and edit presets/params/output contracts in the right inspector. Canvas positions are UI-only; save order is derived top-to-bottom for the existing runtime.
- Support/tool UI preset selection now carries concrete preset params, while `server/web_api/support_handlers.py` re-expands presets before dispatch. `/app/admin/playbooks` shows module/install/platform/min-agent metadata, output contract status path/values, and quick condition templates generated from `condition_hints`; saved `required_tools` keep `output_schema` separate from `output_contract`.
- Low-code diagnostic scenarios now live in `server/playbooks/catalog.py`, `server/playbooks/form_triggers.py`, existing `server/app/services/playbook_engine.py`, typed admin handlers `GET /api/web/admin/playbooks/catalog` + `POST /api/web/admin/playbooks/save`, and React `/app/admin/playbooks` (`webapp/src/features/playbooks/*`).
- Ticket-bound playbook launch now starts from typed support routes `GET /api/web/support/tickets/{ticket_id}/playbooks` and `POST /api/web/support/tickets/{ticket_id}/playbooks/run`; `/app/tickets/:ticketId` renders the automation panel with readiness, required tools and recent operations before starting `trigger_type=support_ticket` runs.
- Request forms can start diagnostics on ticket creation via `playbook_triggers`; `server/tickets/create_flow.py` and public requester flow `server/tickets/public_ticket_handlers.py` build a structured facts package from `request_form_data` / `request_form_summary`, start the latest published playbook version idempotently, and `server/web_api/support_handlers.py` exposes `playbook_started` in the typed support detail timeline for `/app/tickets/:ticketId`.
- The diagnostic/remediation boundary is explicit: the builder publishes only `diagnostic` blocks (`system.collect`, `ip_address.get_ip`, `diag.logs.collect` in the initial catalog); `remediation` blocks are reserved for a confirmed action flow.
- Canonical doc: `server/docs/DIAGNOSTIC_PLAYBOOKS.md`.

## 2026-04-16 intake forms

- Typed requester intake now lives in `server/tickets/form_catalog.py`, `server/tickets/form_pack_handlers.py`, `server/help.js`, `server/admin_ticket_forms_builder.js`, `server/web_api/admin_handlers.py`, `webapp/src/features/forms-builder/forms-builder-panel.tsx`, and `pc_agent/ui_gui/chat_panel.py`.
- Observer trace overlay now lives in `server/observer/service.py`, `server/observer/runtime.py`, `server/tech/handlers.py`, `server/app/db/models.py`, `server/websocket/agent_services.py`, and `pc_agent/core/action_trace.py`; observer v2/v3 adds canonical ticket-root traces, first-class degradation queries (`duration > N`, timeout/retry/slow rate, `root_kind` flow filtering), synthetic operation-less runtime-audit traces for auth/provisioning/runtime lifecycle, pushed `agent_observer_events` telemetry, `playbook_run` step spans, `module_reconcile`, `web_auth` and `observer_runtime` root kinds, automatic historical backfill, full client-update tracing from request to launcher apply, and isolated short-lived projection sessions so admin/support observer polling does not hold idle DB transactions while waiting on per-trace locks.
- Canonical observer docs now live in `server/docs/OBSERVER_LAYER.md` and `server/docs/OBSERVER_AUTHORING_RULES.md`; quick diagnostics use legacy-compatible `/api/admin/tech/*` endpoints for Codex/prod debugging, while React uses typed aliases under `/api/web/admin/observer/*`: quick, traces, trace-detail, diagnostics bundle, signatures, degradations, runtime, settings and traces rebuild. Support/ticket observer summary uses `GET /api/tickets/{ticket_id}/observer`. That ticket summary must report counts over the full ticket trace set and expose both global `occurrences_count` and ticket-local `ticket_occurrences_count`. Canonical operator trace UX is the `/support` workspace drawer tab `Трасса`, while `/app/admin/observer` now owns the typed observer workbench: quick overview, server-side trace search, diagnostic bundle, signatures, degradations, runtime/settings, global mode without a selected `device_id`, trace detail with `include_agent_actions=1`, evidence-source counters from `attrs_json.source_counts`, diagnostics bundle counters, compact agent-action rows, and explicit detail/bundle error states.
- Browser polling for `/admin` tech and `/support` workspace should stay single-flight: if you touch `server/admin.js` or `server/support.js`, keep observer refresh non-overlapping so stale tabs cannot avalanche `observer/quick` and ticket-summary requests into the DB pool.
- The legacy admin `/admin` shell still has a dedicated `Конструктор форм` tab for versioned request-form packs, served by `/api/ticket_forms/current`, `/public_api/ticket_forms/current`, and `/api/ticket_forms/packs/*`.
- The new `/app/admin` workspace now also exposes a typed `Конструктор форм заявок` through `GET /api/web/admin/forms/current` and `POST /api/web/admin/forms/save`; the React panel edits forms/fields directly, can add/edit server-driven priority questions and process field roles, and still publishes into the same `request_forms` catalog.
- Public `/help` and the local agent ticket dialog now submit `form_key`, `form_payload`, and `ticket_type`; the agent caches the latest form pack in its local data root, renders priority fields from the selected template when present, keeps fixed priority controls only as fallback for legacy packs, and refreshes only when the server reports a newer version.
- Old preferred `request_forms` packs are normalized with the standard priority question fields (`impact_scope`, `work_continuity`, `business_importance`, `critical_service`, `public_service`) so the server UI, `/help`, and the local agent use the same configurable priority facts before the next manual republish; custom priority-policy field keys keep their own fields/roles and do not receive roles for absent default keys.

## 2026-04-23 form-aware routing

- 2026-04-29 process-model slice: request forms are now request templates. `ticket_type` is selected from the template, not from requester input, and maps to server workflow profiles in `server/tickets/workflow_profiles.py` (`incident`, `service_request`, `access_request`, `change_request`, `consultation`). Template context now preserves `category_id`, `service_id`, `subcategory_id`, `default_queue_id`, `sla_policy_id`, field roles and policy JSON; `server/tickets/routing_service.py` now executes `request_template.routing_policy.rules` before global routing rules, then template default queue and fallback.
- 2026-04-30 configurable workflow slice: workflow profiles are stored in `ServerConfig` key `ticket.workflow_profiles` with code defaults as fallback. `PUT /api/web/settings/workflow_profiles` saves process type labels, required fields, flags, suggested path and status transition maps; structured transition entries can also define `allowed_roles` and `required_fields`, which `server/tickets/workflow_service.py` enforces on status changes for the ticket's `ticket_type`. `/app/settings` edits these profiles, and `/app/admin/forms` reads the configured profile list for request-template `ticket_type` selection.
- Old published `request_forms` packs that predate `ticket_type` are backfilled by `server/tickets/form_catalog.py` from form key/request_kind (`breakage`, `printer`, `network`, `site_system`, `mail_issue` -> `incident`; `access`, `new_account` -> `access_request`; standard software/hardware requests -> `service_request`), and the React forms builder mirrors that fallback before saving.
- 2026-04-29 priority/SLA/OLA slice: deterministic priority calculation lives in `server/tickets/priority_policy.py`. Form `priority_policy` maps submitted facts into `impact`, `urgency`, `importance`, `computed_priority`, `effective_priority` and `priority_decision`; `server/tickets/sla_service.py` resolves SLA targets by process priority P0..P3 with legacy P1..P4 fallback and uses `server/tickets/calendar_engine.py` for second-precision due dates when an SLA policy points to `ticket_business_calendars` / business hours; `server/tickets/ola_service.py` starts queue OLA from `priority_class`, so OLA settings must accept process priorities including P0. `server/tickets/form_catalog.py` preserves priority-policy fact keys from submitted payload even when they are agent-collected helper facts rather than visible form fields.
- 2026-04-29 operator-card slice: typed support detail now exposes ticket process fields, priority decision and SLA deadlines for `/app/tickets/:ticketId`; the React detail page renders an operational seven-question ticket card before the workbench.
- Ticket routing now understands form-derived context from `server/tickets/routing_service.py`: `ticket_type`, `request_kind`, `custom_fields`, `request_form_data`, and normalized `request_form_*` metadata are available for live ticket creation and existing preview. Template `routing_policy` rules are first-match by `priority_order` and can set queue, assignee, priority boost/minimum priority, SLA override, approval policy, tags and suggested playbook metadata; loop guards live in `routing_lock`, `do_not_reroute_if_assignee_locked` and `max_auto_reroutes`.
- `tickets.ticket_type` is `varchar(64)` as of migration `061`, so form `request_kind` slugs used by routing preview and real ticket creation share the same practical length budget instead of failing during DB insert.
- The typed settings payload `GET /api/web/settings` now includes a `routing_builder` catalog assembled from the current preferred form pack, so `/app/settings` can build routing rules against both base ticket fields and `request_form_data.<field>` keys without hand-written JSON.
- Settings capabilities are intentionally split: `settings.view` opens the page, `settings.manage_queues` enables queue/member/OLA saves, and `settings.manage_routing` enables routing/SLA/calendar/resolution saves; OLA target editors use process priorities P0..P3 while backend keeps legacy P4 compatibility; denied actions should show the server-provided reason instead of falling back to one broad read-only mode.
- Command-result side effects for `list_installed_modules` and `list_tools` live in `server/websocket/command_result_components.py`; `list_tools` snapshots device ORM scalar fields before async writes to keep auto-install follow-up toolset refreshes free of `greenlet_spawn` warnings.
- The typed admin forms boundary now also exposes `POST /api/web/admin/forms/route-preview`; `/app/admin/forms` can submit a draft form plus sample answers and see which queue/rule would match before publishing.
- The typed support detail payload `GET /api/web/support/tickets/{ticket_id}` now includes normalized `request_form` data for the `/app/support` sidebar block `Данные формы`.
- Reports request-kind labels are no longer hardcoded: `server/web_api/reports_handlers.py` resolves them from the current preferred request-form catalog.
- Ticket work visibility now starts from `server/tickets/statuses.py`, `server/tickets/workflow_service.py`, `server/app/api/serializers.py`, and migrations `056`/`057`: internal statuses are `new/queued/assigned/in_progress/waiting_on_* /scheduled/resolved/closed/canceled`, requester-facing statuses are mapped separately, and `next_action_owner`, `status_reason`, `ticket_waits`, evidence and closure feedback are part of the API contract.
- Request-template `approval_policy` is executed in `server/tickets/approval_policy.py` during workflow transitions. `required=true` allows entering `waiting_on_approval`, but blocks execution statuses such as `assigned`, `in_progress`, `scheduled` and `resolved` until `ticket_approvals` contains the required approved decision; rejected approvals return `APPROVAL_POLICY_BLOCKED` through typed support status actions.
- Ticket resolution passports now live in `server/tickets/passport_service.py`, `server/app/repos/ticket_passport_repo.py`, migration `059`, typed support handlers `GET/POST/PATCH /api/web/support/tickets/{ticket_id}/passport*`, and the React `/app/tickets/:ticketId` tab `Паспорт` plus `/app/tickets/:ticketId/passport/print`; governed tickets with `evidence_required=true` cannot move to `resolved` without `evidence_ref` or `ticket_evidence_items`. Request-template `closure_policy` is executed in `server/tickets/closure_policy.py` during workflow resolution and can require `resolution_code`, public summary and evidence for configured P0..P3 priorities.
- `/app/settings` now has a dedicated `Тикеты` tab backed by `GET /api/web/settings.ticket_settings`: lifecycle/status mapping, requester-facing statuses, `next_action_owner`, governance flags, passport/evidence guard state, operational ticket flags, a visible future service-desk chain (`request_template -> ticket_type/workflow_profile -> priority -> routing -> SLA/OLA -> observer`), editable workflow profiles, read-only planned L1/L2/L3 support-line model and priority model; sibling tabs still own queues, routing, SLA, calendars and resolution codes.

## 2026-04-15 module workbench focus

- For module authoring in the admin UI, start with `server/admin_modules_workbench.js`, `server/admin_modules_workbench.html`, `server/modules/handlers.py`, and `server/modules/workbench_service.py`.
- The module workbench now supports template-driven tool creation, inline validation, validate-before-publish preview, preferred-version assignment, rollout-policy settings for preferred versions, ZIP archive import into the registry, archive-to-code decomposition, and delete-from-registry actions from the module list.
- The admin `Модули` page is split into inner tabs: `Разработка модулей`, `Список модулей`, `Редактор модулей`, and `Модули на устройствах`; the authoring flow inside the first tab is a 4-step wizard.
- Everyday module authoring no longer starts from raw JSON: platforms are selected from supported values, requirements are entered line-by-line, and params/output schemas can be assembled from validated blueprint rows before publish.
- The server validate endpoint for the workbench is `POST /api/modules/workbench/validate`; API clients should prefer the headless authoring trio `GET /api/modules/authoring/catalog`, `POST /api/modules/authoring/validate`, and `POST /api/modules/authoring/publish`. Validate/save/upload must expose `validation_json.server_harness` as the mandatory server-side harness result before publish.
- Server-side module harness runs `pc_agent/scripts/smoke_check_module.py --ignore-platform-check`, so a Linux server can validate Windows-targeted packages structurally without blocking publish only because `manifest.platforms` excludes Linux.
- Windows-targeted modules (`win32` / `windows*`) publish after the server harness but cannot become preferred until `POST /api/modules/{module_name}/{version}/live_tests` records a passed Windows agent run with a compatible agent version; UI should surface the `WINDOWS_LIVE_TEST_REQUIRED_BEFORE_PREFERRED` warning before promotion.
- Published module live testing from React starts with `GET /api/web/admin/modules/workbench/{module_name}/{version}/live_test_candidates?platform=win32|linux` and runs through `POST /api/web/admin/modules/workbench/{module_name}/{version}/live_tests`, while legacy `/api/modules/*` routes remain compatibility aliases. A selected run creates `module_live_test` observer traces; blocked Windows preferred rollout creates `module_preferred_gate` and returns `observer_trace_id`. Module live tests are not ticket-bound; do not pass synthetic `ticket_id` values to the agent run, correlate them by `trace_id`/operation ids. For real agent command results, derive operation ids from top-level response fields or `payload.meta.request_id`.
- New playbook-ready modules should use the module workbench `Playbook decision contract` controls or send `output_contract` through the headless API so the playbook builder can branch on explicit status values instead of raw command text.
- In the typed React UI, the active module constructor is `webapp/src/features/modules/modules-panel.tsx`; keep its payload builder and API preview aligned with the typed `/api/web/admin/modules/workbench/*` endpoints.
- Preferred-version rollout settings now live in `server/app/repos/module_rollout_repo.py` and are exposed via `GET/PATCH /api/modules/rollout_settings`; in `installed_devices` mode a preferred-version change rewrites desired state, triggers reconcile for matching devices, and then refreshes inventory/toolset so the admin UI converges.
- After agent-side module lifecycle changes, `server/websocket/outbox_ingest_components.py` now treats `tools_changed` and `module_state_changed` as convergence signals and queues a debounced `list_tools`, so auto-install/reconcile updates `device_toolset_snapshots` without waiting for reconnect or manual Sync Modules.
- `server/tools/service.py` also queues `list_installed_modules` and `list_tools` after a successful auto-install before `run_tool`, covering no-op/repeated installs where the agent may not emit a fresh `tools_changed`.

# QUICK_LOOKUP

Короткий канонический навигатор по проекту `pc_client`.

## С чего начинать

1. Для нетривиальной задачи сначала запустите `python scripts/task_intake.py`.
2. Если задача описана словами, используйте `python scripts/task_intake.py --task "<описание>"`.
3. Если уже важен diff, используйте `python scripts/task_intake.py` без аргументов.
4. Перед правками откройте `docs/CODEX_WORKFLOW.md` и выберите режим работы: Explore / Debug / Plan / Execute / Feature / Contract / Verify / Commit / Deploy.
5. Затем откройте `docs/ARCHITECTURE_BOUNDARIES.md`, определите ownership zone и проверьте, не меняется ли contract surface.
6. Для быстрого retrieval после intake используйте `python scripts/build_context_pack.py --topic "<описание>"` и `python scripts/search_context_index.py "<символ route error-code concept>"`; если индекс устарел или search печатает stale-warning, `python scripts/build_context_index.py --force`.
7. Если нужна точечная локальная навигация после retrieval:
   - `python scripts/agent_find.py "<pattern>" --dir server|pc_agent`
   - `python scripts/diff_context.py`
8. Для длинной задачи синхронно ведите `PLANS.md`.

Routing-логика живёт в:

- `scripts/task_intake.py`
- `scripts/navigation_catalog.py`
- `scripts/build_context_index.py`
- `scripts/search_context_index.py`
- `scripts/build_context_pack.py`
- `scripts/docs_inventory.py`

Этот файл остаётся human-facing индексом и не должен дублировать весь routing.

## Canonical docs only

Источник истины для структуры и workflow:

- `AGENTS.md`
- `docs/README.md`
- `docs/CODEX_WORKFLOW.md`
- `docs/QUICK_LOOKUP.md`
- `docs/ARCHITECTURE_BOUNDARIES.md`
- `docs/CONTEXT_INDEX.md`
- `server/docs/CODEMAP.md`
- `pc_agent/docs/CODEMAP.md`
- protocol/auth/runtime/update docs рядом с кодом

Historical docs больше не канон:

- `docs/archive/TICKET_CRM_GAP_ANALYSIS.md`
- `docs/archive/TICKET_AND_AGENT_UPDATE_ROADMAP.md`
- `docs/archive/BOTTLENECKS_AND_RISKS.md`

Их архивные копии лежат в `docs/archive/`.

## Truth baseline

Минимальный baseline перед commit:

- `python scripts/verify_workspace.py`
- `python -m pytest server/tests/ ...`
- `python -m pytest pc_agent/tests/ ...`

Если задача затрагивает release/deploy:

- `python scripts/run_ci_suite.py`

Если задача затрагивает `webapp/` или frontend bundle pipeline:

- `python scripts/bootstrap_web_toolchain.py`
- после release живой signoff нового `/app/*`: `pnpm --dir webapp run check:remote:webapp -- --base-url http://192.168.100.17:8666`
- preflight перед включением default-route switch: `python scripts/check_webapp_cutover.py --json`
- operational checklist для полного переключения: `docs/WEBAPP_CUTOVER_CHECKLIST.md`

Если задача про UI/UX/accessibility audit, admin UI или заметную визуальную переработку:

- routing должен попадать в тему `New web workspaces / typed web boundary`;
- для `webapp/` сначала `python scripts/bootstrap_web_toolchain.py`;
- живую проверку делать через MCP на `http://192.168.100.17:8666/admin`.

Если менялся веб:

- browser verification через MCP на `http://192.168.100.17:8666/admin`

Test DB env vars:

- `TEST_DATABASE_ADMIN_URL`
- `TEST_DATABASE_URL`
- `PC_CLIENT_ALLOW_SHARED_TEST_DB`

Windows note:

- On Windows, if `TEST_DATABASE_URL` and `TEST_DATABASE_ADMIN_URL` are not set, server DB-backed pytest now defaults to shared `pc_support_test`.
- In that default mode the harness opens a local SSH tunnel to PostgreSQL using `C:\Users\admin-2\.ssh\pc_client_altserver_ed25519`.
- In shared-DB fallback mode the harness now terminates stale `pc_support_test` backends before `TRUNCATE` and uses a short lock timeout, so leaked sessions fail fast instead of hanging the suite.
- For websocket-heavy pytest on Windows, `server/tests/conftest.py` now forces `WindowsSelectorEventLoopPolicy`, so the old trailing `unexpected connection_lost() call` noise is no longer a completion criterion.
- For isolated ephemeral test DBs from Windows, set `TEST_DATABASE_ADMIN_URL` explicitly.

## 2026-04-28 Protocol hardening notes

- `server/websocket/agent_services.py` now marks an `outbox_id` as runtime-deduped only after a terminal non-retryable outcome or ACK. Retryable `outbox_nack` outcomes must remain retryable by the same `outbox_id`.
- `server/websocket/outbox_ingest_components.py` treats missing `trace_id` as an envelope validation error and returns a typed validation NACK with a fallback server trace id instead of silently skipping ACK/NACK.
- `server/websocket/protocol.py` registers sync `send_ws_command(..., wait_for_result=True)` waiters before waking device dispatch, and copies caller params before consuming internal `_operation_id`.
- `server/tools/service.py` also copies caller params before building `run_tool` command params, so retries/logging/audit code can safely reuse the original dict.
- `pc_agent/ws_agent.py` handshake diagnostics must log the current `PROTOCOL_VERSION` (`ws_ticket_v3`), not legacy `ws_mcp_v1`.

## Fast map

| Topic | Open first | Then |
|------|------------|------|
| Codex workflow / dirty worktree / commit / deploy | `docs/CODEX_WORKFLOW.md`, `AGENTS.md`, `docs/ARCHITECTURE_BOUNDARIES.md` | Use before work to choose Explore, Debug, Plan, Execute, Feature, Contract, Verify, Commit or Deploy mode and follow script-first commands |
| Architecture boundaries / contract impact | `docs/ARCHITECTURE_BOUNDARIES.md`, `AGENTS.md`, `docs/QUICK_LOOKUP.md` | Use before edits to classify a change as local / boundary / cross-cutting / release-control and to choose neighboring docs/tests |
| Context index / retrieval | `docs/CONTEXT_INDEX.md`, `scripts/build_context_index.py`, `scripts/search_context_index.py`, `scripts/build_context_pack.py` | Build with `python scripts/build_context_index.py --force`; search with `python scripts/search_context_index.py "<query>"`; use `--profile debug|contract|route|test|web` for targeted ranking; `build_context_pack.py` includes top context-index hits after `task_intake`; use as retrieval, not as a replacement for CODEMAP/boundaries |
| Protocol V3 / handshake | `server/websocket/agent_handshake.py`, `server/websocket/agent_services.py`, `server/state_manager.py`, `server/app/repos/device_outbox_repo.py`, `pc_agent/ws_agent.py`, `pc_agent/core/sender.py`, `pc_agent/ws_agent_runtime_helpers.py` | `server/docs/PROTOCOL_V3.md`, `pc_agent/docs/PROTOCOL_V3.md` |
| New web workspaces / typed web boundary | `webapp/src/main.tsx`, `webapp/src/app/router.tsx`, `webapp/src/app/routes/lazy-pages.tsx`, `webapp/src/app/layouts/app-shell.tsx`, `webapp/src/app/navigation.tsx`, `webapp/src/components/shell/*`, `webapp/src/components/ui/*`, `webapp/src/features/auth/session-provider.tsx`, `webapp/src/features/auth/login-page.tsx`, `webapp/src/features/auth/workspace-access.ts`, `webapp/src/features/access-control/*`, `webapp/src/features/requester/*`, `webapp/src/features/queues/api.ts`, `webapp/src/features/reports/api.ts`, `webapp/src/features/settings/api.ts`, `webapp/src/features/playbooks/*`, `webapp/src/pages/help/index.tsx`, `webapp/src/pages/requester-ticket/index.tsx`, `webapp/src/pages/tickets/*`, `webapp/src/pages/reports/index.tsx`, `webapp/src/pages/knowledge/index.tsx`, `webapp/src/pages/settings/index.tsx`, `webapp/src/pages/admin/*`, `webapp/playwright.config.ts`, `webapp/scripts/remote-browser-signoff.mjs`, `webapp/package.json`, `webapp/tests/support-workspace.spec.ts`, `webapp/tests/admin-workspace.spec.ts`, `webapp/tests/fixtures/support_fixture_server.py`, `server/access_control/*`, `server/app/repos/access_control_repo.py`, `server/web_api/access_handlers.py`, `server/web_api/session_handlers.py`, `server/web_api/support_handlers.py`, `server/web_api/admin_handlers.py`, `server/web_api/reports_handlers.py`, `server/web_api/settings_handlers.py`, `server/web_api/realtime_handlers.py`, `server/web_api/dto/reports.py`, `server/web_api/dto/settings.py`, `server/static_pages/webapp_assets.py`, `server/static_pages/handlers.py`, `server/config.py`, `server/routes.py`, `server/websocket/ui_handler.py` | `docs/superpowers/specs/2026-04-20-admin-support-web-rearchitecture-design.md`, `docs/superpowers/specs/2026-04-22-admin-support-unified-workspace-style-design.md`, `server/docs/SECURITY_AND_AUTH.md`, `server/docs/OBSERVER_LAYER.md`, `server/docs/REQUEST_FORM_BUILDER.md`, `server/docs/DIAGNOSTIC_PLAYBOOKS.md`; route pages are lazy-loaded from `webapp/src/app/routes/lazy-pages.tsx`; current route model is now SaaS-style and menu-first: `/app/help`, `/app/ticket`, `/app/ticket/:ticketId`, `/app/tickets`, `/app/tickets/:ticketId`, `/app/tickets/:ticketId/passport/print`, `/app/reports`, `/app/knowledge`, `/app/settings`, `/app/admin/inventory`, `/app/admin/device`, `/app/admin/access`, `/app/admin/modules`, `/app/admin/forms`, `/app/admin/playbooks`, `/app/admin/observer`, while `/app/support` and `/app/admin` stay as compatibility aliases; support ticket detail includes the `Паспорт` tab and typed passport API integration; support, admin, access-control, reports and settings pages now read real typed `/api/web/*` payloads instead of frontend mock data, while public requester pages intentionally use `/public_api/*` for anonymous intake/code auth; `/app/admin/access` is the Access Control Center backed by typed `/api/web/admin/access/*` with group creation, permission/member/queue grants and effective access; `/app/admin/playbooks` is the low-code diagnostic playbook builder backed by typed `/api/web/admin/playbooks/*`; `/app/admin/observer` is the full observer workbench with quick/traces/signatures/degradations/runtime tabs, global mode without a selected device, and trace detail backed by `include_agent_actions=1`; the left rail no longer hosts large workspace cards, workspace switching/logout moved to the topbar, and the visual system is now driven by Tailwind v4 tokens plus shared `Button`/`Badge`/`Card`/`Tabs`/`SearchField` primitives |
| Registry objects / Реестры | `server/registry/service.py`, `server/app/repos/registry_repo.py`, `server/web_api/registry_handlers.py`, `server/websocket/agent_handshake.py`, `server/tickets/create_flow.py`, `pc_agent/ui_gui/chat_panel.py`, `pc_agent/ui_gui/server_api.py`, `webapp/src/pages/admin/registry-page.tsx`, `webapp/src/features/admin/api.ts` | `server/docs/CODEMAP.md`, `pc_agent/docs/CODEMAP.md`; lightweight registry for people, departments, buildings/rooms, PC/printer assets, services and vendors. Agent handshake auto-creates PC assets, requester profile sync creates people/locations/departments, support ticket detail exposes registry context, and `/app/admin/registry` reads `GET /api/web/admin/registry`; object grids use a mobile-safe horizontal table scroll |
| Tool execution / operations | `server/tools/service.py`, `server/tools/handlers.py`, `server/app/services/operation_service.py`, `pc_agent/core/orchestrator.py`, `pc_agent/core/orchestrator_collect_helpers.py`, `pc_agent/core/orchestrator_job_helpers.py` | `server/docs/TOOL_CALL_STARTED_INVARIANT.md`, `pc_agent/docs/CODEMAP.md` |
| Observer traces / tech drilldown | `server/observer/service.py`, `server/observer/runtime.py`, `server/tech/handlers.py`, `server/app/db/models.py`, `server/websocket/agent_services.py`, `pc_agent/core/action_trace.py`, `pc_agent/core/orchestrator.py` | `server/docs/OBSERVER_LAYER.md`, `server/docs/OBSERVER_AUTHORING_RULES.md`, `server/docs/CODEMAP.md`, Codex skill `pc-client-observer-diagnostics` |
| Agent updates / recommended version / rollout policy | `server/agents/agent_builds_handlers.py`, `server/app/repos/agent_rollout_repo.py`, `server/routes.py`, `pc_agent/ws_agent.py`, `pc_agent/ui_bridge/api_server.py`, `pc_agent/ui_gui/main_window.py` | `server/docs/AGENT_UPDATES_API.md`, `pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md`, `pc_agent/docs/AGENT_UPDATE_WORKFLOW.md` |
| Modules / desired state / reconcile / workbench | `server/modules/handlers.py`, `server/modules/workbench_service.py`, `server/web_api/admin_handlers.py`, `server/tools/service.py`, `server/websocket/outbox_ingest_components.py`, `server/modules/reconcile.py`, `server/admin_modules_workbench.js`, `webapp/src/features/modules/modules-panel.tsx`, `pc_agent/core/module_manager.py`, `shared/tool_contracts.py` | `server/docs/MODULE_CREATION_GUIDE.md`, `server/docs/MODULES_API.md`, `server/docs/MODULE_AUTHORING_RULES.md`, `server/docs/REGISTRY_PUBLICATION_RULES.md`, `server/docs/RUNTIME_EXECUTION_CONTRACT.md`, `pc_agent/docs/MODULES.md`; новый typed admin surface теперь не только читает `GET /api/web/admin/modules`, но и ведёт `PATCH /api/web/admin/modules/rollout_settings` и `PATCH /api/web/admin/modules/{module_name}/preferred`, чтобы `/app/admin` умел менять preferred-version policy и preferred assignment без legacy workbench/editor shell |
| Ticket flows / helpdesk | `server/tickets/handlers.py`, `server/tickets/create_flow.py`, `server/tickets/workflow_service.py`, `server/tickets/routing_service.py`, `server/tickets/form_catalog.py`, `server/tickets/passport_service.py`, `server/app/repos/ticket_passport_repo.py`, `server/web_api/support_handlers.py` | `server/docs/TICKET_SYSTEM.md`, `server/docs/CODEMAP.md`, `server/docs/REQUEST_FORM_BUILDER.md`; паспорт решения хранит versioned official dossier, evidence/action/approval/related-object facts and powers `/app/tickets/:ticketId` |
| Auth / token bootstrap | `server/auth/`, `server/websocket/agent_handshake.py`, `pc_agent/auth/token_source.py`, `pc_agent/auth/connection_request.py`, `pc_agent/launcher_portable_main.py` | `server/docs/SECURITY_AND_AUTH.md`, `pc_agent/docs/AUTHENTICATION.md`; httpOnly cookie `pc_client_web_session` authenticates `/api/web/*`, including the typed React aliases for modules, observer/tech alerts, notifications and settings. Legacy `/api/modules/*`, `/api/admin/tech/*`, `/api/admin/settings/observer` and `/api/ticket_forms/*` remain compatibility endpoints but should not be new React call targets. |
| Agent runtime / UI bridge | `pc_agent/ws_agent.py`, `pc_agent/ws_agent_runtime_helpers.py`, `pc_agent/ui_bridge/api_server.py`, `pc_agent/ui_gui/main.py`, `pc_agent/ui_gui/main_window.py`, `pc_agent/ui_gui/window_chrome.py`, `pc_agent/ui_gui/chat_panel.py`, `pc_agent/ui_gui/theme.py`, `pc_agent/ui_gui/tickets_list_model.py`, `pc_agent/ui_gui/assets/icons/` | `pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md`, `pc_agent/docs/CODEMAP.md` |
| Release / deploy / CI | `scripts/task_intake.py`, `scripts/bootstrap_web_toolchain.py`, `scripts/check_webapp_cutover.py`, `scripts/verify_workspace.py`, `scripts/run_ci_suite.py`, `scripts/run_observer_canary_suite.py`, `scripts/deploy_workspace_to_remote.py`, `scripts/release_server_to_remote.py`, `webapp/scripts/remote-browser-signoff.mjs` | `AGENTS.md`, `PLANS.md`, `docs/LOCAL_WORKFLOW.md`, `docs/WEBAPP_CUTOVER_CHECKLIST.md` |

## When to update this file

Обновляйте `docs/QUICK_LOOKUP.md`, если меняются:

- ключевые entrypoints;
- канонический intake/test/release workflow;
- карта основных тем и стартовых файлов;
- статус canonical vs historical docs.
- observer quick diagnosis, trace APIs, dangerous-flow coverage или обязательные observer docs/skills.
