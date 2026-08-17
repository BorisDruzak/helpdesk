# Helpdesk Endpoint Residual Inventory

## Status and rule

This is the baseline retirement inventory for Helpdesk's remaining direct
agent interactions. It is intentionally an inventory, not deletion approval.
Every future cutover must establish a versioned EndpointPort contract, retain
ticket-facing history, pass its dedicated acceptance gate, and update this
table before a legacy component changes classification.

Classifications: `KEEP_HELPDESK`, `KEEP_AS_HELPDESK_FACADE`,
`EXTRACT_ENDPOINT`, `LEGACY_ROLLBACK_ONLY`, `DELETE_AFTER_CUTOVER`, and
`UNRESOLVED`.

| Component | Current owner / primary callers | Current routes, tables, tests | Target owner | Classification | EndpointPort path and prerequisite |
| --- | --- | --- | --- | --- | --- |
| UI WebSocket | Helpdesk; support/requester web clients via `websocket.ui_handler`, `StateManager` | `/ws_ui`; UI connection state; UI websocket tests | Helpdesk | `KEEP_HELPDESK` | None. Preserve registration and auth behaviour. |
| Agent WebSocket protocol and handler | Helpdesk; `routes.py`, `websocket.protocol`, `websocket.agent_handler` | `/ws`; agent connection state; Protocol V3 and handler tests | Endpoint Platform | `DELETE_AFTER_CUTOVER` | Requires acceptance for every migrated endpoint capability and endpoint-agent auth/operations replacement. |
| `StateManager` agent connections | Helpdesk runtime; protocol/tools/operations use online state | In-memory agent connections; `is_agent_online` tests | Endpoint Platform | `EXTRACT_ENDPOINT` | New Endpoint path reads only safe availability/capability projections; delete only after legacy paths end. |
| `DeviceOutbox` | Helpdesk; `OperationService`, tools, websocket sender | `device_outbox`; `/ws`; outbox/retry/result tests | Endpoint Platform | `EXTRACT_ENDPOINT` | Endpoint diagnostic must create no outbox row; legacy outbox stays until all legacy dispatches cut over. |
| `OperationService` and local `Operation` | Helpdesk; tools, diagnostics, support UI | `operations`; operation APIs and lifecycle tests | Split: Endpoint runtime / Helpdesk facade | `KEEP_AS_HELPDESK_FACADE` | Keep local ticket-facing operation. Add external-link bridge without equating IDs. |
| `ToolService` / `run_tool` | Helpdesk; diagnostic execution router and legacy admin flows | Tool APIs, operation and tool tests | Endpoint Platform for migrated endpoint operations | `LEGACY_ROLLBACK_ONLY` | Endpoint capability provider must not import/call ToolService. Other tools stay unchanged. |
| Agent module installation | Helpdesk; module handlers and websocket sync | Module APIs, module storage, install tests | Endpoint Platform | `EXTRACT_ENDPOINT` | Separate module-management contract and acceptance; excluded from this slice. |
| Agent recipes | Helpdesk diagnostics recipes and runner rollout | Recipe data/config/tests | Endpoint Platform | `EXTRACT_ENDPOINT` | Separate recipe contract; excluded. |
| Inventory collection | Helpdesk registry/inventory plus agent data | Inventory routes/tables/tests | Endpoint Platform authoritative technical state; Helpdesk safe projection | `EXTRACT_ENDPOINT` | Requires explicit safe inventory projection; no raw device-context copy. |
| Device presence | Helpdesk `StateManager` and handshake | `/ws`, runtime state/tests | Endpoint Platform | `EXTRACT_ENDPOINT` | Endpoint capability availability is the only current permitted read. |
| Screenshots/artifacts | Helpdesk agent command/upload path | Upload/artifact routes, storage, tests | Endpoint Platform | `EXTRACT_ENDPOINT` | Requires artifact metadata/content contract and retention/privacy decision. |
| Remote Assist ticket link | Helpdesk ticket/support workflow | Ticket links, support UI/tests | Helpdesk | `KEEP_AS_HELPDESK_FACADE` | Retain opaque reference and authorization facade only. |
| Remote Assist runtime | Helpdesk signaling/agent runtime | `/ws/remote-assist/{session_id}`, sessions/tests | Endpoint Platform | `EXTRACT_ENDPOINT` | Requires endpoint-side signaling and consent acceptance. |
| Agent update/build/rollout | Helpdesk agent build, update handlers and launcher integration | Agent build tables/routes/tests | Endpoint Platform | `EXTRACT_ENDPOINT` | Requires update API and rollout/rollback acceptance; excluded. |
| Consent runtime | Helpdesk consent and agent dispatch | Consent tables/routes/tests | Endpoint Platform for endpoint technical execution | `UNRESOLVED` | Read-only diagnostic has no consent. Any later risky capability requires a separate ownership/approval decision. |
| Agent observer events | Helpdesk websocket ingest and Observer | Protocol/event tables/tests | Endpoint Platform emits technical events; Helpdesk consumes safe evidence | `EXTRACT_ENDPOINT` | Define redacted event/evidence contract first. |
| Local Qt / `pc_agent` code | Helpdesk repository legacy agent implementation | `pc_agent/**`, runtime/UI tests | Endpoint Platform | `DELETE_AFTER_CUTOVER` | Remove only after all endpoint-agent responsibilities and release lifecycle have moved and accepted. |
| Agent HTTP/WS handlers | Helpdesk server routes/websocket modules | `/ws` and agent-related HTTP routes/tests | Endpoint Platform | `DELETE_AFTER_CUTOVER` | Route-by-route acceptance; `/ws_ui` explicitly excluded. |

## Required invariants for the first slice

- `/ws_ui` is `KEEP_HELPDESK`.
- Agent `/ws` is `DELETE_AFTER_CUTOVER`, never a dependency of the new path.
- Helpdesk `Operation` is `KEEP_AS_HELPDESK_FACADE`; Endpoint operation is
  `EXTRACT_ENDPOINT`.
- Ticket diagnostic sessions/evidence stay `KEEP_HELPDESK`; endpoint execution
  is `EXTRACT_ENDPOINT`.
- Remote Assist ticket link is `KEEP_AS_HELPDESK_FACADE`; its runtime is
  `EXTRACT_ENDPOINT`.
- No code is removed by the Endpoint diagnostic vertical slice.
