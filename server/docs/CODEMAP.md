# Helpdesk server code map

## Entry points

- `server/server.py` builds the Helpdesk aiohttp application.
- `server/web_api/` provides authenticated Helpdesk browser and support APIs.
- `server/tech/snapshot.py` builds the read-only Tech Panel readiness model;
  the `endpoint_platform` connection-policy state is valid after the legacy
  Helpdesk agent runtime is retired.
- `server/control_plane.py` controls the independent Helpdesk server lifecycle.
- `server/runtime_control.py` manages only the Helpdesk server and control
  plane units.

## Endpoint operation facade

- `server/diagnostics/` projects the Endpoint diagnostic capability, validates
  ticket access and stores reconciled evidence.
- `server/endpoint/` contains the HTTP adapter and versioned contract types.
- `server/app/repos/` persists ticket, operation and Endpoint facade state.
- `server/web_api/support_handlers.py` exposes the canonical support
  diagnostic route and its browser compatibility alias.
- `server/web_api/requester_handlers.py` derives a `VerifiedRequesterBinding`
  only after the authenticated requester-device ownership check;
  `server/tickets/create_flow.py` accepts that internal context only when its
  device, person, and binding identifiers match, preserving requester scope
  for shared devices without changing the public request payload.
- `server/web_api/admin_handlers.py` supplies the browser admin bootstrap;
  its active feature catalog is limited to inventory, forms and the Tech Panel
  and does not advertise retired agent rollout or module-workbench surfaces.
- `server/tickets/handlers.py` projects requester and support UI presence;
  the retired Helpdesk agent runtime is always reported as offline.
- `server/registry/primary_agent_resolver.py` resolves a person's primary
  Endpoint device and projects runtime presence when the supplied state
  provider is available; an unavailable provider remains `unknown`.
- `server/tickets/diagnostic_policy.py` uses the ticket-context target rather
  than the retired Helpdesk agent runtime; an explicitly offline Endpoint
  target records a `diagnostic_autorun_skipped` event instead of starting a
  diagnostic playbook.
- `server/web_api/registry_handlers.py` creates admin registry people with a
  server-generated UUID, so the identity and audit flows never accept a
  caller-supplied person identifier.
- `server/observer/integrity_service.py` scans and resolves findings only for
  its active checks; retired protocol and local-runtime sources are excluded
  from new scans and leave existing events unchanged. Browser authentication
  failures remain in the
  `UiUserAudit` trail rather than the retired agent-runtime audit stream.

Helpdesk has no agent WebSocket server, device outbox sender, tool execution
service, command-result pipeline or local agent operation fallback. `/ws_ui`
is retained solely for browser notification delivery. The legacy local
`run_tool` CLI, GUI-agent debug driver and `/ws_ui_test` page are not shipped.
This also includes the retired UIA create-ticket harness for the local agent.

## Contracts and verification

- [ENDPOINT_OPERATION_CONTRACT.md](ENDPOINT_OPERATION_CONTRACT.md) is the
  Helpdesk-facing diagnostic and cancel contract.
- `server/tests/test_helpdesk_endpoint_only_boundary.py` and
  `server/tests/test_no_legacy_endpoint_routes.py` protect the retired
  surfaces.
- `server/tests/test_endpoint_contract_lock.py` protects the consumed Endpoint
  API contract.
# Production security policy

- `server/security_profile.py`: shared dependency-free production transport,
  bind and proxy policy; called by runtime `config.validate_security_config()`.
- `scripts/validate_production_config.py`: safe deployment/systemd preflight;
  optionally reads a root-owned env file and emits key-only errors.
