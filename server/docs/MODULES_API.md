# Modules API

The current modules API evolves the existing `modules` path in-place and now uses the unified semantic tool contract.

## Canonical docs

Read these first:

- `server/docs/MODULE_CREATION_GUIDE.md`
- `server/docs/MODULE_AUTHORING_RULES.md`
- `server/docs/REGISTRY_PUBLICATION_RULES.md`
- `server/docs/RUNTIME_EXECUTION_CONTRACT.md`

## Domain model

- `module` = delivery pack, versioning, ownership
- `tool` = atomic typed executable contract
- `playbook` = orchestration layer over tools
- `provider` = module or service that owns capabilities
- `capability` = universal projection of a tool, connector query, observer query, remote assist session action or manual diagnostic check
- `execution_target` = where the capability runs: `agent_builtin`, `agent_managed_module`, `server_builtin`, `server_connector`, `observer_query`, `remote_assist`, `manual` or reserved `hybrid`

Canonical tool ids stay semantic-only:

- `dns.resolve`
- `network.ping`
- `screen.collect`

Legacy aliases exist only as compatibility bridges.

## Server responsibilities

- preflight ZIP and manifest normalization
- ownership/conflict checks
- publish into the server registry
- preferred-version policy per module family
- rollout settings for how preferred-version changes propagate to devices
- preferred-version resolution for auto-install
- desired-state persistence before auto-install
- version-aware auto-install/update before `run_tool`
- capability projection through `GET /api/diagnostics/capabilities`
- ticket-scoped readiness through `GET /api/tickets/{ticket_id}/diagnostics/capabilities`
- ticket-scoped capability execution through `POST /api/tickets/{ticket_id}/diagnostics/capabilities/{capability_id}/run`
- admin-safe provider config through `GET /api/diagnostics/providers/configs`, `GET /api/diagnostics/providers/configs/{provider_id}` and `PUT /api/diagnostics/providers/configs/{provider_id}`; the same redacted contract is available to web-session admin clients through `/api/web/admin/diagnostics/providers/configs*`
- routing agent capabilities to existing `ToolExecutionService.run_tool` while routing server connectors, observer queries, remote assist and manual checks through server-side providers

## Diagnostic capability projection

The first-stage capability registry is an additive service layer over existing modules and tools. It does not rename or replace `run_tool`.

Sources:

- agent builtin and managed tools from current tool manifests/snapshots
- server builtin capabilities: `server.dns.resolve`, `server.http.request`
- server connector capabilities, currently the Zabbix JSON-RPC provider: `zabbix.problems.lookup`, `zabbix.host.health`, `zabbix.item.history`
- observer query capabilities: `observer.ticket.summary`, `observer.trace.bundle`
- remote assist session capabilities: `remote_assist.request_view`, `remote_assist.request_control`, `remote_assist.session.summary`
- manual diagnostic evidence capabilities: `manual.visual_check`, `manual.vendor_response`, `manual.operator_note`, `manual.customer_confirmation`

Capability descriptors include provider id/type, execution target, schemas/contracts, safety flags, deployment metadata, readiness requirements, evidence metadata, artifact metadata and legacy aliases.

Readiness statuses are: `available`, `install_required`, `installing`, `unsupported_platform`, `agent_offline`, `missing_dependency`, `consent_required`, `integration_not_configured`, `credentials_missing`, `mapping_missing`, `permission_denied`, `disabled_by_policy`, `unavailable`, `unknown`.

Readiness payloads keep those status strings for compatibility and add stable machine-readable `reason_code` values plus explicit `actions` ids. UI code should drive controls from `actions` such as `install`, `run`, `configure_integration`, `add_credentials`, `request_consent`, `open_remote_assist` and `create_manual_evidence`; it should not parse the human `reason` text.

Compatibility rules:

- old managed ZIP manifests default to `agent_managed_module` and keep auto-install semantics
- old builtin tools default to `agent_builtin` and never require server ZIP install
- `server_connector` capabilities require `integration_key` and do not enqueue agent commands
- observer and manual targets never enqueue agent commands
- remote assist targets route to the existing Remote Assist session service instead of `ToolExecutionService.run_tool`

Capability execution responses are normalized with `execution_target`, `execution_kind`, `provider_id`, `provider_type`, `idempotency_key` and `timeout_ms`. `execution_kind` is `operation` for agent tools, `query` for server connector and observer lookups, `session` for remote assist, and `manual_evidence` for manual checks. The ticket-scoped run endpoint checks readiness before dispatch; blocked capabilities return `409` with `error_code=CAPABILITY_NOT_READY` and a stable `reason_code`. `consent_required` remains executable for agent and remote-assist capabilities when the action is `request_consent`, so existing consent workflows can still be initiated.

`server_builtin` capabilities run on the Maria server and create ordinary `operations` rows with `kind=server_capability`, `command_name=server_builtin`, and `tool_name=<capability id>`. They transition `queued -> running -> succeeded/failed`, support idempotency keys and timeouts, expose `/api/operations/{operation_id}` as `poll_url`, map evidence previews, and do not enqueue `device_outbox` commands.

When a non-agent capability is executed through `POST /api/tickets/{ticket_id}/diagnostics/capabilities/{capability_id}/run`, successful server/query/session results are also projected into persistent `diagnostic_evidence` when the capability produces evidence. Migration `076` adds `diagnostic_session_capabilities` for session-scoped capability snapshots and `diagnostic_artifact_links` for normalized artifact references. The mapper path is:

- raw operation/session/query result
- `normalize_tool_result_to_evidence_values()` production evidence values
- `diagnostic_evidence` row with provider, capability, source, trace, artifact, actor and redaction provenance
- optional `diagnostic_session_capabilities` snapshot when the request passes a valid `session_id`
- optional passport row only after `selected_for_passport` and `/diagnostics/passport/attach-selected`

Agent-side targets keep their asynchronous `ToolExecutionService.run_tool` behavior and are projected from terminal operation results later. Manual capabilities still persist their own diagnostic evidence in `ManualCapabilityProvider`, so the generic run endpoint does not duplicate them.

Zabbix `server_connector` capabilities run on the Maria server through `diagnostics.providers.zabbix_provider.ZabbixProvider`. The provider reads bounded runtime config from diagnostic provider config, calls Zabbix JSON-RPC methods `problem.get`, `host.get` and `history.get`, caps returned problem/history rows, maps outputs to `monitoring.problem`, `monitoring.host_health` and `monitoring.metric_history`, and never returns raw credential material in result payloads. Ticket-scoped capability runs inject persisted integration config, mapping and ready credential refs into the server connector route before dispatch.

Observer `observer_query` capabilities run on the Maria server through `diagnostics.providers.observer_provider.ObserverCapabilityProvider`. `observer.ticket.summary` calls the existing ticket observer summary/root trace service and returns a compact support-facing contract: root trace id, health, trace/signature counts, latest error, top signature, related traces and recent occurrences. `observer.trace.bundle` uses the existing observer overlay trace search/detail/signature/degradation services to return a bounded trace bundle: primary trace, related traces, error occurrences, signatures, degradations, recommended next checks and observer links. Both capabilities map to observer evidence previews and remain read-only query targets; they never call `ToolExecutionService.run_tool` and never enqueue DeviceOutbox rows.

Remote Assist `remote_assist` capabilities are session targets. `remote_assist.request_view` maps to the existing `view_only` consent flow, `remote_assist.request_control` maps to `interactive_control` and requires `remote_assist.control` plus the interactive-control policy flag, and `remote_assist.session.summary` reads ticket sessions without requiring an online device. Requests route through `RemoteAssistService.request_session()` and `send_request_to_agent()` so the existing consent/signaling lifecycle stays authoritative; the generic capability router still treats the result as `execution_kind=session`, not as an ordinary tool operation. Session request and summary outputs map to passport-eligible `remote_assist.session` evidence previews.

Manual `manual` capabilities create support-authored diagnostic evidence. `manual.visual_check`, `manual.vendor_response`, `manual.operator_note` and `manual.customer_confirmation` require `diagnostics.create_manual_evidence`, return `manual.evidence` output contracts, persist rows in `diagnostic_evidence`, and write `diagnostic_manual_evidence_created` ticket events for audit/realtime projection. They do not write directly to `ticket_evidence_items`; passport linkage remains the selected diagnostic evidence bridge (`selected_for_passport` plus `/diagnostics/passport/attach-selected`).

Readiness input sources:

- ticket-bound device record and agent online state
- device OS/platform against capability `platforms`
- `device_modules` and `device_desired_modules` for installed/active/installing state
- dependency status supplied by caller/service context
- integration config, credential state and mapping state supplied by connector config context
- effective RBAC permission set from the authenticated actor
- persisted diagnostic provider config (`diagnostic_provider_configs`), credential references and mappings for server connectors
- policy flags supplied by diagnostic/provider policy context
- observer root trace and remote assist consent/policy/active-session metadata

Provider config persistence starts at migration `075`. Runtime capability descriptors remain computed from module manifests and provider skeletons so dynamic agent toolsets do not depend on DB snapshots. The persisted tables hold provider/config lifecycle and audit data:

- `diagnostic_provider_configs.status`: `disabled`, `configured`, `credentials_missing`, `ready`, `degraded`
- `diagnostic_provider_credential_refs.secret_ref`: reference only; API responses redact it
- config payloads are redacted before persistence for sensitive keys such as password, token, secret, api key and credentials
- Zabbix readiness consumes persisted `integration_key=zabbix`, credential readiness and `mappings.zabbix.host`
- Zabbix runtime config supports URL, TLS verification flag, timeout and mapping fields; credential refs remain internal runtime inputs and are redacted from admin/API payloads
- permission, policy and integration blockers return generic human reasons while preserving detail through stable `reason_code`, preventing support/admin projections from exposing raw provider config or credential data

## Admin workbench

`/admin` embeds a dedicated module-development workbench loaded from:

- `server/admin_modules_workbench.html`
- `server/admin_modules_workbench.js`

Workbench API:

- `GET /api/modules/workbench` - grouped module families with versions and preferred-version state
- `GET /api/modules/rollout_settings` - current rollout policy for preferred-version changes
- `PATCH /api/modules/rollout_settings` - update the rollout policy (`manual` or `installed_devices`, plus reconcile/refresh toggle)
- `GET /api/modules/authoring/catalog` - headless module-authoring catalog: supported platforms/scopes/lifecycles, output-contract template, sample payload and common tool templates for API clients
- `POST /api/modules/authoring/validate` - headless validate endpoint; uses the same package builder, preflight, smoke check, conflict detection and editable preview as the workbench
- `POST /api/modules/authoring/publish` - headless publish endpoint; validates/smokes and persists the module using the same registry flow as the workbench save action
- `GET /api/modules/workbench/{module_name}/{version}` - module detail plus editable draft reconstructed from manifest and archive contents
- `POST /api/modules/workbench/validate` - build a package in memory, run preflight/smoke, report ownership conflicts, and return an editable preview without publishing
- `POST /api/modules/workbench/save` - build, validate, smoke-check, and persist a module from the structured UI payload
- `POST /api/modules/upload` - upload a ready ZIP package, run server preflight/smoke, publish it into the registry, and make it available for immediate editing in the workbench
- `GET /api/modules/{module_name}/{version}/live_test_candidates?platform=win32|linux` - list lab-agent candidates for a published module version with normalized platform, online state, agent version compatibility and blocking reasons
- `POST /api/modules/{module_name}/{version}/live_tests` - install and run a published module command on a selected real lab agent, then append the result to `validation_json.live_tests`
- `DELETE /api/modules/{module_name}/{version}` - remove a published module version from the registry and delete its archive from storage; clears preferred-version assignment if the deleted version was preferred
- `PATCH /api/modules/{module_name}/preferred` - assign the preferred version used by auto-install/runtime resolution

Workbench UX expectations:

- the `Модули` page is split into inner tabs for guided development, catalog/list, advanced editor, and device install state
- the guided flow is a 4-step wizard: `Каркас -> Инструменты -> Политики -> Проверка`
- the catalog/list view is also the entrypoint for ZIP import and destructive actions on published versions, so authors do not need a separate screen for archive onboarding
- common manifest/tool fields no longer require raw JSON for everyday authoring:
  - module platforms are chosen from supported platform pills (`any`, `linux`, `win32`, `darwin`)
  - module `requirements` and `optional_requirements` are entered as one item per line instead of JSON arrays/objects
  - params/output schemas can be assembled from validated line-based blueprint rows such as `hostname:string! | Имя хоста`, while raw JSON schema stays available as an advanced fallback
- local validation is expected to catch platform mistakes, owner-scope conflicts, and malformed schema JSON before server-side validate/publish
- local validation also checks the playbook decision contract: status path, allowed status values, success/error subsets, summary path and error-code path
- the guided wizard and advanced editor expose these contract fields directly, and the wizard side summary shows a readiness checklist for module id, version, platforms, tool ids and output contracts
- the typed `/app/admin/modules` editor mirrors the same contract fields and sends validate/publish requests to `/api/modules/authoring/*`
- when a draft targets Windows (`win32` / `windows*`), the UI must show that it is not verified on a Windows agent yet; publish can proceed after the server harness, but preferred rollout is blocked until a Windows live test passes
- archive import expects `module_name` and `version` for the upload contract, but canonical values are still reconciled against `manifest.json` inside the ZIP

Workbench detail and validate preview both expose archive/source decomposition for generated ZIP packages:

- extracted text files from the archive
- detected `@exposed_tool` functions and method names
- per-tool reconstruction strategy (`markers`, `ast`, `raw`)
- unresolved tools and methods so the editor can highlight where manual cleanup is still needed

The preferred version is stored server-side and is the same source of truth used by:

- the admin UI
- `run_tool` auto-install and auto-update
- preferred module resolution in the server registry

## Validation and live-test gates

Server-side validation always runs the package preflight plus the local smoke/runtime harness before publish. The server harness deliberately ignores the manifest platform guard so a Linux server can still validate the package structure, imports, registration and tool catalog for Windows-targeted modules; real OS compatibility is enforced by the live-test/preferred gate. Successful validate/save/upload responses include `validation_json.server_harness`:

```json
{
  "server_harness": {
    "status": "passed",
    "required_before_publish": true,
    "runner": "pc_agent.scripts.smoke_check_module",
    "platform": "win32",
    "checked_at": "2026-04-27T00:00:00+00:00",
    "tools_count": 1,
    "smoke_result": {},
    "errors": []
  }
}
```

If `manifest.platforms` contains Windows (`win32` or `windows*`), validation also adds the warning code `WINDOWS_LIVE_TEST_REQUIRED_BEFORE_PREFERRED`. This warning is not a publish blocker by itself.

Promotion to preferred is stricter for Windows-targeted modules: `PATCH /api/modules/{module_name}/preferred` and the typed admin preferred endpoint return `409 MODULE_WINDOWS_LIVE_TEST_REQUIRED` until `validation_json.live_tests` contains a passed live test with:

- `platform == "win32"`
- `status == "passed"`
- `agent_version` greater than or equal to the module/tool `min_agent_version`

Run the live test with:

```http
GET /api/modules/{module_name}/{version}/live_test_candidates?platform=win32
```

Candidate rows are sorted with compatible/online agents first and include:

```json
{
  "device_id": "windows-lab-device-id",
  "hostname": "win-lab-01",
  "platform": "win32",
  "agent_version": "1.3.0",
  "online": true,
  "compatible": true,
  "reasons": []
}
```

The admin React workbench uses this preflight report to let the operator choose the exact Windows or Linux lab agent before the module is installed.

```http
POST /api/modules/{module_name}/{version}/live_tests
```

Request body:

```json
{
  "device_id": "windows-lab-device-id",
  "tool_name": "network.ping",
  "params": {},
  "timeout_sec": 45
}
```

The server first sends `install_module_package` to the selected agent, then sends `run_tool` only if installation succeeds. Module live tests are not ticket-bound, so the run command must not invent a synthetic `ticket_id`; correlation is via `trace_id` and operation ids. Operation ids are read from the transport response or the agent `payload.meta.request_id`, because real agent command results may expose the command id only in metadata. Each attempt is appended to `validation_json.live_tests` with the install/run stage, device id, normalized platform, agent version, operation ids, trace id and compact payloads.

Observer coverage for this flow is first-class:

- successful and failed live tests create `observer_traces.root_kind = module_live_test`;
- spans include `module.live_test`, `module.lab_agent_select`, `module.install_module_package` and `module.run_tool`;
- terminal install/run failures create an `observer_error_occurrences` row;
- preferred-gate failures create `observer_traces.root_kind = module_preferred_gate` and return `observer_trace_id` next to `MODULE_WINDOWS_LIVE_TEST_REQUIRED`.

## Tool output contracts for playbooks

`output_schema` describes the full JSON payload a tool may return. `output_contract` is the smaller deterministic contract used by the low-code playbook builder for branching and compact support-facing display.

For predictable automation, each playbook-ready tool should declare:

```json
{
  "output_contract": {
    "schema_version": "1.0",
    "status_path": "result.status",
    "status_values": ["ok", "error"],
    "success_values": ["ok"],
    "error_values": ["error"],
    "summary_path": "result.output.summary",
    "error_code_path": "result.error.code",
    "compact_fields": [
      { "path": "result.output.reachable", "label": "Reachable", "type": "boolean" }
    ]
  }
}
```

Server manifest normalization keeps `output_schema` and `output_contract` separate. When `output_contract` is present, `status_values` must be explicit and unique; `success_values` and `error_values` must be subsets of `status_values`. The admin playbook catalog derives `condition_hints` from the contract and known `error_codes`, so `/app/admin/playbooks` can offer stable condition templates such as `steps.ping.output.result.status == 'ok'` instead of forcing operators to parse raw command text.

Generated modules preserve `output_contract` in `manifest.json`, `manifest_summary` and the editable workbench preview. Older modules that do not declare an output contract remain valid; the field is not written as an empty object unless the author explicitly provides it.

Preferred-version rollout now has an explicit server-side setting:

- `manual` - changing preferred only changes the registry/source-of-truth; devices update later through `run_tool`, manual install, or other runtime touch points
- `installed_devices` - changing preferred immediately rewrites desired state for devices that already have the module installed (or already have `desired=installed`), triggers reconcile so the target version is enqueued to the agent, and then queues inventory/toolset refresh so server-side actual state converges in the UI

## Builtin modules

Builtin providers such as `system` and `screen` use the same contract vocabulary and validation model, but they do not require server ZIP installation.

## Historical note

Legacy `module.tool` naming and the old risk vocabulary remain only as internal compatibility layers. The public canon now centers on semantic tool ids and the shared contract vocabulary.
# Agent Recipe Runner note

`agent_recipe_runner` is a protected managed module, but individual recipe capabilities are not ZIP modules. The server stores recipe capability contracts in `diagnostic_capabilities` / `diagnostic_capability_versions` and concrete recipes in `agent_recipe_versions`. The runner package is still managed through the existing module lifecycle (`preferred`, install, live test, rollout, rollback), while recipe authoring uses `/api/web/admin/agent-recipes*`.

Protected runner manifests may set `system_module=true` and `protected=true` and declare no support-visible tools. The server must not generate a normal support tool for `agent_recipe_runner`; recipe execution uses Protocol V3 `run_recipe`, not `run_tool`.
