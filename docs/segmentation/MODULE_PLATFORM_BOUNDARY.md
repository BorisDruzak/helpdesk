# Endpoint Module Platform Boundary

## Purpose

This document separates the legacy Helpdesk module system from Endpoint-native
declarative modules. It applies while both systems coexist.

## Current legacy surface

The existing Workbench accepts Python-oriented module drafts including
`user_function_body`; `server/modules/workbench_service.py` reconstructs code
from ZIP archives; the legacy server validates/publishes module packages and
uses `ToolExecutionService`, `DeviceOutbox`, and the Helpdesk agent WebSocket
for delivery. This remains the `legacy` authority and is not removed by v1.

## Endpoint-native surface

Endpoint Recipe is a distinct Workbench type. Its canonical source, recipe
validation, version lifecycle, publication, compatibility, technical command
rows, and agent execution belong exclusively to Endpoint Platform. Helpdesk
stores only a safe historical snapshot: module key/version/title/SHA-256 and a
bounded result summary.

Browser requests remain Helpdesk BFF requests. The BFF calls Endpoint only via
a versioned, typed HTTPS adapter. Browser sessions and Endpoint service tokens
never cross this boundary.

## Typed port

`server/domain_ports/endpoint_modules.py` will define frozen, `extra=forbid`,
bounded/versioned DTOs and these operations:

`availability`, `list_modules`, `read_module`, `read_module_version`,
`create_module_version`, `validate_module_version`, `publish_module_version`,
`deprecate_module_version`, `create_operation`, and `read_operation`.

`server/endpoint_adapter/modules_http.py` implements exactly those methods
over HTTPS. It is not a generic proxy and has no Helpdesk database, WebSocket,
ticket, or browser-session dependency.

The legacy Admin shell exposes this boundary in a distinct `Endpoint recipes`
subtab. Its declarative form can compose only the current allowlisted
`dns.resolve`, `network.ping` and `tcp.connect` steps with fixed safe literals
and named inputs. It never renders a source-code field and calls only the
Helpdesk BFF `/api/web/admin/endpoint-modules`; it does not call Endpoint from
the browser or reuse a legacy module endpoint.

## Execution boundary

For one endpoint-native run, Helpdesk creates exactly one local facade
Operation and one durable `EndpointOperationLink`, commits, then lets its
reconciler create/read the remote parent operation. Terminal projection writes
one `DiagnosticEvidence` of kind `endpoint.module.recipe`; it does not mutate
`Ticket.status`.

Endpoint-native execution must cause zero Helpdesk `DeviceOutbox` rows,
`ToolService` calls, legacy WebSocket calls, or module-package installations.
Legacy modules do not run through Endpoint automatically. There is no automatic
fallback in either direction.

## Authorization and audit

Admin users may create/edit draft/validate/publish/deprecate. Support may list
compatible published modules and run them against an accessible ticket/device.
Requesters may do neither; auditors read metadata/audit only.

Helpdesk audit retains the Helpdesk actor, action, module key/version, request
correlation, time, and redacted Endpoint outcome. Endpoint audit records only
its service-client identity. Neither side stores service tokens, raw agent
results, raw command data, stdout/stderr, or agent credentials in this flow.

## Feature flags

Default Helpdesk configuration is fail-closed:

- `ENDPOINT_MODULE_PORT_MODE=unavailable`
- `MODULE_WORKBENCH_AUTHORITY=legacy`
- `ENDPOINT_MODULE_EXECUTION_MODE=disabled`
- `LEGACY_MODULE_EXECUTION_ENABLED=true`

`endpoint_shadow` is read-only and creates no dual writes. `endpoint` creates
and executes only Endpoint-native recipes. Changing from legacy to endpoint is
an explicit configuration/deployment action, never a runtime recovery path.
