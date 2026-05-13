# Diagnostic Capabilities Full Implementation Plan

## Active Agent Recipe Runner Production Slice

Goal: add `agent_recipe` as a production execution target backed by a protected managed `agent_recipe_runner` module. Recipes are persisted DB records, not generated ZIP modules; execution uses a first-class `run_recipe` Protocol V3 command and produces operations plus diagnostic evidence.

### Ticket-bound Runner Auto-Install / Auto-Upgrade Slice

Goal: make `agent_recipe` runs able to install or upgrade the protected `agent_recipe_runner` as a runtime dependency without blocking the HTTP request and without bypassing module lifecycle.

- [x] Add `operation_dependencies` plus `operations.phase` for parent operation dependency state.
- [x] Select runner through preferred module assignment and version/platform/primitive compatibility checks.
- [x] Use `device_desired_modules` and `modules.reconcile.reconcile_device` for install/upgrade.
- [x] Return parent `operation_id` immediately in `waiting_dependency` / `installing_runner` state.
- [x] Resume parent recipe operation after dependency terminal result, `module_state_changed`, or `tools_changed`.
- [x] Keep resume idempotent and avoid duplicate `run_recipe` outbox commands.
- [x] Add timeout handling through operation watchdog and dependency timeout timestamps.
- [x] Update support diagnostics UI labels for install/upgrade runner actions and waiting dependency run results.
- [x] Add targeted tests for missing runner dependency creation and idempotent resume.

Hard constraints for this slice:

- No arbitrary PowerShell/Bash/Python command runner.
- No remediation/side effects in the first release.
- No macOS support; only `win32` and `linux`.
- Do not break existing managed modules, `run_tool`, playbooks, observer, diagnostics or Capability Studio.
- Keep primitive execution inside the managed runner module; agent core only resolves and delegates.

Implementation plan:

- [ ] Add failing tests for `agent_recipe` target validation, recipe tables, readiness states, execution enqueue, agent bridge and basic primitives.
- [ ] Reuse `diagnostic_capabilities` / `diagnostic_capability_versions` for capability identity/version contracts; add recipe-specific tables and version contract fields.
- [ ] Add server recipe repo/service, admin recipe APIs and registry projection for published recipe capabilities.
- [ ] Extend readiness and execution router so `agent_recipe` routes to `RecipeExecutionService`, not `ToolExecutionService.run_tool`.
- [ ] Add `run_recipe` Protocol V3 command path and command-result evidence projection for `agent_recipe` operations.
- [ ] Add agent `RecipeRunnerBridge` and protected managed module package `agent_recipe_runner` with read-only primitives.
- [ ] Extend Capability Studio with Agent Recipe authoring MVP and runner provider visibility.
- [ ] Update docs/CODEMAP/navigation for the new tables, endpoints, command and agent module contract.
- [ ] Run targeted backend, agent and frontend checks; then deploy through the standard remote scripts and browser-check the admin UI.

## Goal

Build the full diagnostic capabilities model on top of the existing module/tool system:

`Provider / Module -> Capability / Tool -> Execution Target -> Operation / Session / Query -> Artifacts + Evidence -> Diagnostic Session / Finding / Passport`.

The current work completed the backward-compatible foundation. This plan tracks the remaining full implementation, including persistent evidence, real providers, UI integration, policy/readiness depth, playbook integration, and release/deploy verification.

## Hard Constraints

- Do not break existing `ToolExecutionService.run_tool`.
- Do not break managed ZIP modules, builtin modules, semantic tool ids, aliases, playbooks, observer traces, Protocol V3, DeviceOutbox, `command_result`, operations, passport/evidence, or remote assist.
- Do not move `server_connector`, `observer_query`, `remote_assist`, or `manual` capabilities onto the agent.
- Do not rename canonical ids unless a migration/alias strategy is explicit.
- Keep installation-on-agent as one deployment option, not a universal capability property.
- Work only in `C:\Users\admin-2\CodexProjects\pc_client`.

## Current State

Active slice for this task:

- Goal: add `/app/admin/capabilities` as a top-level Capability Studio MVP over the existing diagnostics capability registry, provider config APIs and Modules Workbench.
- Scope: admin React route/page, catalog/providers/evidence/readiness/SDK tabs, detail drawer, create wizard skeleton, typed admin aliases if needed.
- Non-goals: no ToolExecutionService changes, no playbook/runtime rewrites, no DB schema, no declarative recipe runner, no automation runner, no new Zabbix SDK.
- Current state: implemented route aliases, React Capability Studio page/components, navigation entry, Modules Workbench link and focused tests.
- Verification: backend alias tests pass; `pnpm --dir webapp exec vitest run src/app/router.test.tsx` passes; `pnpm --dir webapp run build` passes; Playwright MCP verified `/app/admin/capabilities` catalog, nav item, detail drawer, Providers tab, Evidence Mapping tab and create modal with mocked API payloads; `python scripts/docs_inventory.py --check-links` and `python scripts/verify_workspace.py` pass.

Stage 1 foundation is implemented:

- Manifest/tool contract accepts optional `execution`, `deployment`, `safety`, `evidence`, and `artifacts`.
- Old managed ZIP manifests default to `agent_managed_module`.
- Builtin agent tools default to `agent_builtin`.
- Validation covers target enum, `server_connector` integration requirements, agent install semantics, evidence requirements, perspective enum, and safety bool fields.
- Agent `@exposed_tool`, registry, `list_tools`, and `describe_tool` expose capability metadata for agent tools.
- `system.collect`, `screen.collect`, `screen.record`, and `diag.logs.collect` have `agent_builtin` metadata.
- `diag.logs.collect` is marked as `logs.bundle`, `domain=logs`, `perspective=endpoint`, `passport_eligible=true`, `artifacts.logs_zip`.
- Server capability projection exists in `server/diagnostics/`.
- Readiness foundation exists.
- Execution router foundation routes only `agent_builtin` / `agent_managed_module` to existing `ToolExecutionService.run_tool`; non-agent targets return unsupported placeholders and do not touch DeviceOutbox.
- Zabbix capabilities are implemented through a bounded server connector client; observer, remote assist, and manual providers are server-side routes.
- Endpoints exist:
  - `GET /api/diagnostics/capabilities`
  - `GET /api/tickets/{ticket_id}/diagnostics/capabilities`
- Support tool DTO can carry capability metadata.
- Docs, CODEMAP, navigation catalog and boundary docs are updated.

Active execution slice:

- [x] Extend manifest/tool metadata with explicit readiness flags for credentials, mapping and policy while keeping old manifests valid.
- [x] Replace placeholder readiness decisions with a real service context that can use device records, installed/desired module state, platform metadata, integration config, credentials, mapping, policy and permission checks.
- [x] Replace unsupported provider placeholders for `observer_query`, `remote_assist` and `manual` with real server-side provider routes built on existing observer, remote assist and passport/evidence services.
- [x] Keep Zabbix as a safe server connector implementation boundary: validate config/credentials/mapping, use persisted provider config at run time, and return bounded provider results through a JSON-RPC client without moving checks onto the agent.
- [x] Prove non-agent targets do not call `ToolExecutionService.run_tool` from the generic capability router.

Verified:

- `python scripts/verify_workspace.py`
- `python -m pytest server/tests/test_modules_manifest_no_db.py server/tests/test_diagnostic_capabilities_no_db.py server/tests/test_module_observer_contract_no_db.py server/tests/test_modules_workbench_api.py server/tests/test_ticket_diagnostic_policy.py server/tests/test_tool_service_builtin_modules.py server/tests/test_tool_service_auto_install_no_db.py -q --tb=short`
- `python -m pytest pc_agent/tests/test_registry_and_module_loading.py pc_agent/tests/test_diag_logs_module.py -q --tb=short`
- `python -m pytest server/tests/test_web_support_api.py -k "tools" -q --tb=short`
- Migration check: remote DB current is `073 (head)`; `run_remote_migrations.py upgrade head` is a no-op.
- `python -m pytest server/tests/test_modules_manifest_no_db.py server/tests/test_diagnostic_capabilities_no_db.py -q --tb=short`
- `python -m pytest pc_agent/tests/test_registry_and_module_loading.py pc_agent/tests/test_diag_logs_module.py -q --tb=short`
- `python -m compileall -q server\diagnostics server\utils\module_manifest.py server\utils\module_builder.py server\routes.py server\web_api\support_handlers.py server\web_api\dto\support.py pc_agent\core\registry.py pc_agent\core\orchestrator.py`
- `python -m pytest server/tests/test_diagnostic_layer.py server/tests/test_ticket_passport_service.py -q --tb=short`
- `python -m pytest server/tests/test_diagnostic_layer.py server/tests/test_ticket_passport_service.py server/tests/test_observer_diagnostics_api.py server/tests/test_ticket_diagnostic_policy.py server/tests/test_playbook_scenarios_no_db.py server/tests/test_remote_assist_no_db.py server/tests/test_agent_observer_events_repo.py pc_agent/tests/test_diag_logs_module.py -q --tb=short`
- `python -m compileall -q server\diagnostics server\app\repos\diagnostics_repo.py server\app\db\models.py server\routes.py`
- `pnpm --dir webapp build`
- `python -m alembic -c alembic.ini heads` from `server/` shows `074 (head)`.
- `git diff --cached --check`
- `python -m pytest server/tests/test_diagnostic_layer.py server/tests/test_diagnostic_capabilities_no_db.py -q --tb=short`
- `python -m pytest pc_agent/tests/test_registry_and_module_loading.py pc_agent/tests/test_diag_logs_module.py -q --tb=short`
- `python scripts/release_server_to_remote.py --allow-local-dirty --gate quick --skip-ci-check --leave-running`
- `python scripts/run_remote_migrations.py current` shows `074 (head)` on Linux.
- `python scripts/manage_remote_stack.py smoke server`
- Browser check at `https://192.168.100.17:9443/admin`: support ticket tools workspace opens the Diagnostics tab; overview loads evidence counts, perspectives, latest evidence and action buttons with no console warnings/errors.

## Active Diagnostic Layer MVP Slice

Goal: build the separate ticket diagnostic layer on top of existing tickets, operations, playbooks, observer, remote assist, artifacts, passport/evidence and capability metadata. Diagnostics must not become a ticket status and must not rewrite tool/module/playbook/observer execution.

Existing diagnostic data sources:

- `operations` plus `tool_call_started` / `tool_call_result` ticket events.
- `playbook_runs` and `playbook_step_runs`.
- observer root trace, compact summary, signatures and bundles.
- remote assist sessions/events.
- artifacts, especially `diag.logs.collect` / `logs_zip`.
- existing passport evidence and manual support context.
- capability readiness and execution metadata from the foundation phase.

Implementation plan:

- [x] Add failing tests for diagnostic overview, operation/artifact/remote evidence projection, session lifecycle, finding rules, evidence passport selection and bundle creation.
- [x] Add Alembic migration and ORM models for `diagnostic_sessions`, `diagnostic_steps`, `diagnostic_evidence`, `diagnostic_findings` and `diagnostic_bundles`.
- [x] Add `DiagnosticRepo` and services in `server/diagnostics/`:
  - `DiagnosticOverviewService`
  - `DiagnosticProjectionService`
  - `DiagnosticEvidenceService`
  - `DiagnosticSessionService`
  - `DiagnosticFindingService`
  - `DiagnosticBundleService`
  - profile registry skeleton.
- [x] Add endpoints:
  - `GET /api/tickets/{ticket_id}/diagnostics/overview`
  - `GET /api/web/support/tickets/{ticket_id}/diagnostics/overview`
  - session/evidence/finding/bundle/profile endpoints from the diagnostic layer spec.
- [x] Add frontend typed API in `webapp/src/features/diagnostics/api.ts`.
- [x] Add a unified Diagnostics panel/tab in the support workspace without removing existing tools/playbooks/observer/remote assist panels.
- [x] Update CODEMAP/navigation/docs for the new diagnostic layer and routes.
- [x] Run targeted backend tests, existing observer/playbook/remote/diag logs regressions, workspace verifier and targeted frontend checks.

Next execution slice:

- [x] Add passport bridge: selected `diagnostic_evidence` can be attached idempotently to existing `ticket_evidence_items` with provenance and artifact refs.
- [x] Add `POST /api/tickets/{ticket_id}/diagnostics/passport/attach-selected`.
- [x] Add `POST /api/tickets/{ticket_id}/diagnostics/run-profile` MVP: create diagnostic session, record recommended capability/playbook steps, project current ticket sources, evaluate findings and optionally auto-select passport-eligible evidence.
- [x] Add frontend actions in the Diagnostics tab: run profile, evaluate findings, build bundle and attach selected evidence to passport.
- [x] Deploy to Linux, apply migration `074`, smoke the remote stack and browser-check the Diagnostics tab.

Acceptance for this slice:

- Level 1 read-only overview works with empty and populated tickets.
- Level 2 persistent sessions/evidence/findings/bundles exists and can be exercised through services/API.
- Existing operations, remote assist sessions and diag logs artifacts can be projected into normalized diagnostic evidence.
- Observer summary appears in the overview without duplicating observer internals.
- Finding engine provides deterministic rule-based suspected findings.
- Evidence can be selected for passport later through `selected_for_passport`.
- Bundle MVP returns JSON summary plus evidence/artifact/observer/remote references.
- Existing tool, playbook, observer and remote assist flows continue to work unchanged.
- Selected diagnostic evidence can be promoted into passport evidence without duplicating existing rows.

## Full Implementation Phases

### Phase 2: Persistent Capability Registry and Config

- [x] Decide whether persisted capability registry is needed now or whether descriptors remain computed from providers plus manifests.
- [x] If persistence is needed, add DB tables:
  - `diagnostic_providers`
  - `diagnostic_capabilities`
  - `diagnostic_capability_versions`
  - `diagnostic_provider_configs`
  - `diagnostic_provider_credentials_refs` or references into an existing secret/config store.
- [x] Add Alembic migration and migration tests.
- [x] Define provider config lifecycle: disabled, configured, credentials_missing, ready, degraded.
- [x] Add admin-safe CRUD/service APIs for provider config without logging secrets.
- [x] Add web-session admin aliases for provider config APIs so the admin UI can use httpOnly session auth.
- [x] Add audit events for provider config changes.
- [x] Update `server/docs/DATABASE.md`, `server/docs/MODULES_API.md`, `server/docs/CODEMAP.md`, `docs/ARCHITECTURE_BOUNDARIES.md`.

Decision: capability descriptors remain computed from manifest/provider sources for now, because agent builtin/managed tools are dynamic and must keep backward-compatible `run_tool` semantics. Migration `075` adds persisted provider/config tables plus capability snapshot tables for admin/config workflows; it does not make the DB the source of truth for agent tool descriptors.

Verification:

- `python scripts/run_remote_migrations.py current`
- migration unit tests
- DB-backed provider config tests
- `python scripts/verify_workspace.py`
- `python -m pytest server/tests/test_diagnostic_provider_config.py -q --tb=short`
- `python -m pytest server/tests/test_diagnostic_provider_config.py server/tests/test_diagnostic_capabilities_no_db.py server/tests/test_diagnostic_layer.py -q --tb=short`
- `python -m compileall -q server\diagnostics server\app\repos\diagnostic_provider_config_repo.py server\app\db\models.py server\routes.py`
- `python -m alembic -c alembic.ini heads` from `server/` shows `075 (head)`.

### Phase 3: Real Readiness Model

- [x] Replace placeholder readiness heuristics with real data sources:
  - device exists / ticket bound to device
  - agent online state
  - platform compatibility from tool metadata, device OS and managed module manifest
  - installed module version and preferred version
  - desired/installing state
  - dependency/preflight state
  - consent requirements
  - RBAC permission checks
  - policy disabled states
  - integration config and credentials state
  - mapping requirements for server connectors
  - observer root trace availability
  - remote assist policy/user consent/device capability state
- [x] Return stable `reason_code` in addition to human-readable `reason`.
- [x] Return available actions with explicit action ids:
  - `install`
  - `run`
  - `configure_integration`
  - `add_credentials`
  - `request_consent`
  - `open_remote_assist`
  - `create_manual_evidence`
- [x] Add no-db and DB-backed tests for readiness statuses and provider-config transitions.
- [x] Ensure readiness cannot make support/admin UI leak devices or integration names outside caller permission.

Decision: readiness payloads keep the existing `readiness` status strings for backward compatibility, but `reason_code` is now a stable machine contract such as `DEVICE_REQUIRED`, `MODULE_INSTALL_REQUIRED`, `PREFLIGHT_FAILED`, `INTEGRATION_NOT_CONFIGURED`, `CREDENTIALS_MISSING`, `MAPPING_MISSING`, `CONSENT_REQUIRED`, `POLICY_DISABLED` or `PERMISSION_DENIED`. Human `reason` strings are generic for permissions/integrations, and callers should drive UI actions from `actions` ids instead of parsing text.

Verification:

- `python -m pytest server/tests/test_diagnostic_capabilities_no_db.py -q --tb=short`
- `python -m pytest server/tests/test_diagnostic_capabilities_no_db.py server/tests/test_diagnostic_provider_config.py -q --tb=short`
- targeted API tests for both global and ticket-scoped capability endpoints

### Phase 4: Execution Router Productionization

- [x] Add explicit operation/session/query model around capability runs without changing existing `run_tool`.
- [x] For `agent_builtin` and `agent_managed_module`, keep calling `ToolExecutionService.run_tool`.
- [x] For `server_builtin`, implement server-local command/query runner with operation records.
- [x] For `server_connector`, implement provider interface:
  - `list_capabilities()`
  - `get_readiness()`
  - `run_query()`
  - `normalize_result()`
  - `map_evidence()`
- [x] For `observer_query`, route to existing observer services for summary/bundle.
- [x] For `remote_assist`, route to existing remote assist request/session APIs rather than `run_tool`.
- [x] For `manual`, create manual evidence/finding flows.
- [x] Add idempotency and timeout semantics per target.
- [x] Add structured error codes:
  - `CAPABILITY_NOT_FOUND`
  - `CAPABILITY_NOT_READY`
  - `CAPABILITY_TARGET_UNSUPPORTED`
  - `INTEGRATION_NOT_CONFIGURED`
  - `CREDENTIALS_MISSING`
  - `MAPPING_MISSING`
  - `POLICY_DENIED`
  - `CONSENT_REQUIRED`
- [x] Ensure non-agent targets never write DeviceOutbox rows.

Decision: Phase 4 establishes the production routing contract without changing agent execution. `CapabilityExecutionRouter.run_capability()` now returns a target-specific envelope with `execution_target`, `execution_kind`, `provider_id`, `provider_type`, `idempotency_key` and `timeout_ms`. The ticket run endpoint computes current readiness and returns `409 CAPABILITY_NOT_READY` before invoking a provider/tool when the capability is blocked. `consent_required` stays executable for agent and remote-assist capabilities when the action is `request_consent`, preserving existing consent initiation flows. `agent_builtin` / `agent_managed_module` still call `ToolExecutionService.run_tool`; server connector, observer, remote assist and manual targets use provider boundaries. `server_builtin` now has a server-local runner for `server.dns.resolve` and `server.http.request`; it creates `operations` rows, transitions `queued -> running -> succeeded/failed`, supports idempotency keys and timeouts, maps evidence preview, and never writes `device_outbox`.

Verification:

- `python -m pytest server/tests/test_diagnostic_capabilities_no_db.py -q --tb=short`
- `python -m pytest server/tests/test_diagnostic_server_builtin_runner.py -q --tb=short`
- router tests proving each target goes to the correct backend
- operation lifecycle tests for `server_builtin` success/failure/idempotency
- negative tests proving server connector / observer / remote assist / manual do not call `ToolExecutionService.run_tool`

### Phase 5: Zabbix Server Connector

- [x] Define config schema:
  - endpoint URL
  - auth method
  - credentials reference
  - TLS options
  - host mapping strategy
  - timeout/retry policy
- [x] Implement Zabbix provider capabilities:
  - `zabbix.problems.lookup`
  - `zabbix.host.health`
  - `zabbix.item.history`
- [x] Add readiness:
  - integration_not_configured
  - credentials_missing
  - mapping_missing
  - available
  - unavailable/degraded
- [x] Implement safe API client with redaction and bounded responses.
- [x] Map Zabbix results to evidence:
  - `monitoring.problem`
  - `monitoring.host_health`
  - `monitoring.metric_history`
- [x] Add tests with fake HTTP server or mocked Zabbix API, not real external calls.
- [x] Add docs and admin config examples.

Decision: `diagnostics.providers.zabbix_provider.ZabbixProvider` is the first real `server_connector` implementation. It performs bounded Zabbix JSON-RPC calls for `problem.get`, `host.get` and `history.get`, accepts runtime config from persisted diagnostic provider config, uses credential references without returning/logging raw tokens, maps results to existing evidence metadata, and keeps all execution on the server side. Persisted provider config can supply URL, TLS/timeout options and mappings; a ready credential ref is passed internally to the provider run path. A full secret-vault resolver and admin UI for secret material are still separate work.

Verification:

- `python -m pytest server/tests/test_zabbix_provider_no_db.py -q --tb=short`
- `python -m pytest server/tests/test_diagnostic_provider_config.py -q --tb=short`
- provider unit tests
- readiness tests
- redaction tests
- no raw token/credential logging checks

### Phase 6: Observer Query Capabilities

- [x] Implement `observer.ticket.summary` using existing observer ticket summary/root trace services.
- [x] Implement `observer.trace.bundle` using existing diagnostics bundle/export path.
- [x] Define output contracts for observer capabilities.
- [x] Convert observer query results into evidence preview:
  - root trace health
  - latest error
  - top signature
  - related traces
  - degraded runtime signals
- [x] Ensure observer query capabilities are read-only and do not generate DeviceOutbox commands.
- [x] Add browser/API tests for support/admin deep links if UI consumes them.

Decision: `diagnostics.providers.observer_provider.ObserverCapabilityProvider` now dispatches `observer.ticket.summary` and `observer.trace.bundle` separately. Ticket summary returns a compact support-facing output with root trace health, latest error, top signature, trace counts, related traces and evidence preview. Trace bundle uses existing observer overlay trace search/detail/signature/degradation services to return a bounded bundle contract with primary trace, related traces, signatures, degradations, recommended next checks and evidence preview. Both capabilities stay `observer_query` / `execution_kind=query`; they do not call `ToolExecutionService.run_tool` and do not enqueue DeviceOutbox rows.

Verification:

- `python -m pytest server/tests/test_observer_capability_provider.py server/tests/test_diagnostic_capabilities_no_db.py -q --tb=short`
- `python -m pytest server/tests/test_observer_capability_provider.py server/tests/test_diagnostic_capabilities_no_db.py server/tests/test_observer_diagnostics_api.py -q --tb=short`
- `python -m pytest server/tests/test_web_support_api.py -k "observer" -q --tb=short`
- `python -m pytest server/tests/test_admin_tech_api.py::test_tech_diagnostics_bundle_collects_trace_context -q --tb=short`
- `python -m compileall -q server/diagnostics server/observer`
- `python scripts/verify_workspace.py`

### Phase 7: Remote Assist Capabilities

- [x] Model remote assist as session capability, not command/tool.
- [x] Add capabilities:
  - `remote_assist.request_view`
  - `remote_assist.request_control`
  - `remote_assist.session.summary`
  - optional later: file transfer, clipboard, elevated/admin as policy-gated sub-capabilities.
- [x] Readiness must use:
  - device online
  - support permission
  - remote assist policy
  - user consent state
  - session availability
- [x] Route execution to existing remote assist service/routes.
- [x] Map session summary to passport-eligible evidence where policy allows.
- [x] Preserve current Remote Assist consent/signaling flow.

Decision: Remote Assist remains a `session` capability target, not a regular tool command. `remote_assist.request_view` requests `view_only`; `remote_assist.request_control` requests `interactive_control` and is gated by `remote_assist.control` plus `remote_assist.interactive_control.enabled`; `remote_assist.session.summary` is a read-side ticket summary that does not require an online device. The provider uses `RemoteAssistService.request_session()` and `send_request_to_agent()` for real session/consent signaling, returns normalized session envelopes and maps both request/summary results to `remote_assist.session` evidence previews. Readiness now accounts for policy flags and active ticket/device sessions before routing.

Verification:

- `python -m pytest server/tests/test_remote_assist_capability_provider.py server/tests/test_remote_assist_no_db.py server/tests/test_diagnostic_capabilities_no_db.py -q --tb=short`
- `python -m compileall -q server/diagnostics server/remote_assist`

### Phase 8: Manual Capabilities

- [x] Add manual evidence creation capabilities:
  - `manual.visual_check`
  - `manual.vendor_response`
  - `manual.operator_note`
  - `manual.customer_confirmation`
- [x] Implement permission checks.
- [x] Add manual evidence DTOs and event payloads.
- [x] Link manual capabilities to ticket passport/evidence candidate flows.
- [x] Add audit trail and source attribution.

Decision: Manual capabilities now create `diagnostic_evidence` first and no longer bypass the Diagnostic Layer by writing directly to `ticket_evidence_items`. `manual.visual_check`, `manual.vendor_response`, `manual.operator_note` and `manual.customer_confirmation` use the `manual` execution target, require `diagnostics.create_manual_evidence`, produce `manual.evidence` output envelopes and write `diagnostic_manual_evidence_created` ticket events for audit/realtime projection. Passport linkage remains the existing selected-evidence bridge: evidence can be marked `selected_for_passport` and attached through `DiagnosticPassportBridgeService`, preserving current passport semantics.

Verification:

- `python -m pytest server/tests/test_manual_capability_provider.py server/tests/test_diagnostic_capabilities_no_db.py::test_capability_registry_projects_agent_and_skeleton_provider_capabilities server/tests/test_diagnostic_capabilities_no_db.py::test_readiness_returns_stable_reason_codes_and_action_ids server/tests/test_diagnostic_layer.py::test_manual_capability_run_creates_diagnostic_evidence_event_and_passport_candidate server/tests/test_diagnostic_layer.py::test_run_profile_and_attach_selected_api -q --tb=short`

### Phase 9: Evidence Persistence and Diagnostic Sessions

- [x] Add DB model if needed:
  - `diagnostic_sessions`
  - `diagnostic_session_capabilities`
  - `diagnostic_evidence`
  - `diagnostic_findings`
  - `diagnostic_artifact_links`
- [x] Define how an operation/session/query result becomes evidence:
  - raw operation result
  - normalized evidence preview
  - accepted evidence
  - passport-linked evidence
  - finding
- [x] Implement `normalize_tool_result_to_evidence_stub` as production mapper.
- [x] Preserve existing `TicketEvidenceService` and passport flows; extend them rather than replacing.
- [x] Add evidence provenance:
  - capability id/version
  - provider id/type
  - operation/session/query id
  - trace id
  - artifact refs
  - actor
  - redaction policy
- [x] Add cleanup/retention policy.

Implemented in phase 9:

- Migration `076` adds `diagnostic_session_capabilities` and `diagnostic_artifact_links`.
- `DiagnosticProjectionService.project_capability_result()` persists non-agent capability results into `diagnostic_evidence`, links artifacts, and writes session-scoped capability snapshots.
- `normalize_tool_result_to_evidence_values()` is the production mapper; the legacy preview helper delegates to it.
- Ticket capability run API now persists evidence for non-agent server/observer/remote capability results while keeping agent `run_tool` async behavior and manual evidence's existing provider-owned persistence.
- `DiagnosticEvidenceRetentionPolicy.cleanup_unselected_evidence()` removes old transient evidence while preserving selected passport evidence.

Verification:

- [x] migration/model tests
- [x] evidence service tests
- [x] passport linking tests
- [x] server_builtin operation/evidence lifecycle tests

### Phase 10: Playbook Integration

- [x] Allow playbooks to reference capability ids in addition to current tool ids.
- [x] Keep old playbooks working unchanged.
- [x] Add playbook step target resolution:
  - agent tool remains on the existing `run_tool` path.
  - server builtin / server connector query route through `CapabilityExecutionRouter`.
  - observer query routes through the observer capability provider.
  - manual checkpoint routes through the manual capability provider.
  - remote assist session request routes through the remote assist capability provider.
- [x] Add readiness preflight for capability-backed playbook steps.
- [x] Add output contracts for non-agent capability steps.
- [x] Add evidence attachment policy per step.
- [x] Add authoring UI/catalog updates for capabilities.

Verification:

- [x] existing playbook tests
- [x] new mixed-target playbook tests
- [x] no regression in auto-install before tool-backed steps

Notes:

- Completed in this phase: playbook drafts now persist `required_capabilities` alongside legacy `required_tools`; non-agent capability steps complete `playbook_step_run` synchronously with router output and do not enqueue DeviceOutbox commands; agent-backed steps still use the existing module install preflight and `run_tool` enqueue path.
- Evidence attachment is opportunistic and safe: playbook capability results with `evidence_preview` project into diagnostic evidence only when the ticket context points to an existing ticket, and projection failure does not fail the playbook step.
- Full policy/RBAC depth for capability playbooks remains part of Phase 12 hardening.

### Phase 11: Diagnostic Center UI

- [x] Add Diagnostic Center UI surfaces in the React webapp:
  - ticket-scoped capability list
  - readiness statuses and actions
  - filters by domain/perspective/provider/target
  - install/run/configure/request consent actions
  - evidence preview and attach-to-passport
  - session/finding view
- [x] Keep legacy support tool panel working.
- [x] Add admin/provider config UI for server connectors.
- [x] Add affordances for non-agent targets:
  - server connector configuration
  - observer summary/bundle
  - remote assist request
  - manual fact entry
- [x] Add browser checks at `http://192.168.100.17:8666/admin` per project browser canon after deploy.

Verification:

- [x] `python scripts/bootstrap_web_toolchain.py`
- [x] webapp type/build/tests
- [x] Playwright/browser checks
- [x] server API tests

Notes:

- Completed in this phase: `/app/tickets/:ticketId` now has a dedicated Diagnostic Center tab backed by `webapp/src/features/diagnostics/diagnostic-center-panel.tsx`. It loads ticket capabilities, readiness, evidence, sessions, findings and overview; filters by execution target/domain/perspective/provider; routes runnable capabilities through `POST /api/tickets/{ticket_id}/diagnostics/capabilities/{capability_id}/run`; supports manual evidence, finding evaluation, diagnostic bundle creation and selected evidence attachment to passport.
- `/app/admin/modules#diagnostic-provider-configs` now exposes `DiagnosticProviderConfigPanel` over the existing web-admin provider config aliases, so server connectors such as `zabbix_connector` can be configured without showing raw secret values from API responses.
- Legacy ticket tools and playbooks panels remain in the sidebar and still use their existing APIs.
- Browser signoff found and fixed a compact-layout drawer hit-testing regression: in ticket mode the right drawer stayed pointer-active over the center panel because Tailwind's `.flex` utility overrode the component-layer `display: none`. `webapp/src/styles.css` now hides the drawer with `display: none !important` for compact ticket mode.
- Follow-up signoff also found that the live `/app/tickets/:ticketId` route is backed by `TicketListPage`; the standalone `TicketDetailPage` route currently lazy-loads the same workspace page. `DiagnosticCenterPanel` is now wired directly into the live `Инструменты -> Диагностика` workspace tab so capability list/readiness/evidence/sessions/findings are visible in the actual support route.
- Follow-up signoff found that the Diagnostic Center was visible but its secondary queries used token-protected `/api/tickets/{ticket_id}/diagnostics/*` paths, which return `401` under the React httpOnly web session. The support workspace now uses `/api/web/support/tickets/{ticket_id}/diagnostics/*` aliases for capabilities, sessions, evidence, findings, bundle, profile-run and passport attach while the legacy `/api/tickets/*` contract remains available.

### Phase 12: Operations, Observer and Audit Hardening

- [x] Ensure every capability execution writes trace-visible lifecycle events.
- [x] Add observer root kinds/spans for:
  - capability run
  - server connector query
  - observer query
  - manual evidence
  - remote assist capability session
- [x] Add operation/session metrics:
  - duration
  - result status
  - readiness failure count
  - provider errors
  - evidence created/linked
- [x] Add audit events for high-risk or externally integrated capabilities.
- [x] Add redaction for integration config, credentials, query params and evidence payloads.
- [x] Update observer docs if new trace-visible API/flows are added.

Implemented in phase 12:

- `CapabilityExecutionRouter` now emits `capability_run_started` plus terminal lifecycle events through an observer sink without changing the old agent `run_tool` path.
- HTTP diagnostic capability runs and playbook non-agent capability steps use `RuntimeAuditCapabilityExecutionObserver`, which writes redacted `agent_runtime_audit` rows for trace projection.
- Observer runtime audit projection now recognizes diagnostic root kinds: `capability_run`, `server_connector_query`, `observer_query`, `manual_evidence` and `remote_assist`.
- Lifecycle audit details include bounded metrics (`duration_ms`, `result_status`, readiness failure count, provider error count and evidence linked count) and evidence metadata.
- Runtime params/result snapshots and persisted session capability snapshots redact integration config, credential refs, sensitive query fields and evidence output payloads.

Verification:

- [x] observer tests
- [x] dangerous-flow canary where applicable
- [x] redaction tests

### Phase 13: Release, Migration and Deployment

- [x] If DB schema changes were added, run migrations only through canonical scripts:
  - `python scripts/deploy_workspace_to_remote.py`
  - `python scripts/run_remote_migrations.py current`
  - `python scripts/run_remote_migrations.py upgrade head`
- [x] Run server release checks:
  - `python scripts/verify_workspace.py`
  - targeted pytest suites
  - remote smoke
  - browser checks for UI changes
- [x] Stop remote server after verification unless user asks to keep it running.
- [ ] Do not publish to GitHub until verified.

Implemented in phase 13:

- Released committed state `49f5775 diagnostics: add capability observability` to `/var/chat_bot/pc_client` through `python scripts/release_server_to_remote.py --allow-local-dirty --gate quick --leave-running`.
- Release flow ran local `verify_workspace.py`, built and uploaded the React bundle, deployed the committed branch to Linux, ran remote Alembic `upgrade head`, started control/server and passed remote server smoke after one retry.
- Confirmed remote Alembic state separately with `python scripts/run_remote_migrations.py current`: `076 (head)`.
- Confirmed remote server status and smoke with `python scripts/manage_remote_stack.py status server` and `python scripts/manage_remote_stack.py smoke server`.
- Browser-checked `http://192.168.100.17:8666/admin`: login page rendered, `admin/admin123` opened the Admin workspace and browser console had no warnings/errors.
- Stopped the remote server with `python scripts/manage_remote_stack.py stop server`; follow-up status reported `inactive/dead`.
- Follow-up live browser signoff on the support workspace opened `http://192.168.100.17:8666/admin`, switched to Support, opened a ticket, and found a compact-layout drawer hit-test issue that blocked the `Диагностика` tab. The UI CSS fix was built locally and is part of the next deploy/browser verification slice.

- Follow-up Phase 12 canary signoff ran `python scripts/run_observer_canary_suite.py --base-url http://192.168.100.17:8666 --ws-url ws://192.168.100.17:8666/ws --ui-ws-url ws://192.168.100.17:8666/ws_ui --report-path artifacts/observer_canaries/diagnostic_phase12_20260513_071408.json --markdown-report-path artifacts/observer_canaries/diagnostic_phase12_20260513_071408.md`. It passed module install/update/remove, consent approve/deny/timeout, retry exhaustion, WS nack/replay/rate-limit, UI replay, agent disconnect timeout, stable agent build registry checks and source coverage for `module_reconcile`, `playbook_run`, `web_auth`, `observer_runtime`, `capability_run`, `server_connector_query`, `observer_query`, `manual_evidence` and `remote_assist`.

Release note:

- This was a quick staging release gate because the local workspace has unrelated pre-existing dirty files and no full CI artifact was required for this iteration. Use the full gate before publishing to GitHub.

## Acceptance Criteria For Full Completion

- [x] Old module manifests still validate.
- [x] Old managed ZIP modules still auto-install and run through `ToolExecutionService.run_tool`.
- [x] Old builtin modules still run.
- [x] Old playbooks still run.
- [x] New manifest blocks are validated and surfaced.
- [x] Capability registry covers agent builtin, managed modules, server builtin/connector, observer, remote assist, manual and hybrid reserved target.
- [x] Readiness is accurate for device, online agent, install state, platform, dependencies, consent, RBAC, policy, integration config, credentials and mapping.
- [x] Non-agent targets never enqueue DeviceOutbox commands.
- [x] Server connector provider skeleton is replaced by at least one real connector implementation, starting with Zabbix.
- [x] Observer query capabilities return real observer data.
- [x] Remote assist capabilities route to existing remote assist service.
- [x] Manual capabilities create auditable manual evidence/facts.
- [x] Evidence is normalized, persisted where needed, traceable and passport-linkable.
- [x] Diagnostic sessions/findings can aggregate capability results.
- [x] UI can display capabilities, readiness, actions, evidence and findings.
- [x] Docs, CODEMAP, navigation catalog and architecture boundaries are current.
- [x] Targeted and cross-subsystem tests pass.
- [x] Migrations, if added, are linear, compile, apply on remote with `upgrade head`, and leave DB at head.

## Current Limitations / Handoff

- Zabbix has a bounded JSON-RPC provider and uses persisted config/mapping/ready credential refs in the ticket run route. Secret material is still expected through a runtime credential ref/resolver boundary; a full vault-backed secret-management UI is not implemented in this slice.
- `observer_query`, `remote_assist` and `manual` targets now route through server providers. Remote Assist uses the existing session service and may enqueue its existing `remote_assist.request` command; it does not use ordinary `ToolExecutionService.run_tool`.
- Diagnostic Center UI now exists in the React ticket detail and provider config UI exists under admin modules. Live browser signoff found and fixed a compact-layout drawer hit-testing issue and web-session diagnostics alias gaps. Remaining UI hardening is now implemented end-to-end: ticket-scoped capabilities return full descriptor metadata (`params_schema`, `output_schema`, `output_contract`, aliases, artifacts), arbitrary capability params render through a schema-driven editor and selected run params are sent to the capability router; blocked readiness states show RBAC/readiness-specific disabled copy with stable `reason_code` when available.
- Existing unrelated dirty worktree files predate this task and must not be reverted as part of this plan.
