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

Helpdesk has no agent WebSocket server, device outbox sender, tool execution
service, command-result pipeline or local agent operation fallback. `/ws_ui`
is retained solely for browser notification delivery.

## Contracts and verification

- [ENDPOINT_OPERATION_CONTRACT.md](ENDPOINT_OPERATION_CONTRACT.md) is the
  Helpdesk-facing diagnostic and cancel contract.
- `server/tests/test_helpdesk_endpoint_only_boundary.py` and
  `server/tests/test_no_legacy_endpoint_routes.py` protect the retired
  surfaces.
- `server/tests/test_endpoint_contract_lock.py` protects the consumed Endpoint
  API contract.
