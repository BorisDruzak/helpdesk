# server/AGENTS.md

## Server-specific rules

- Follow root `AGENTS.md`; the local Windows repo remains the source of truth.
- Treat server changes as backend/runtime changes.
- The server role is relay between Web UI and agents through WebSocket Protocol V3 (`ws_ticket_v3`).
- Main WS endpoints:
  - `/ws` for agents; handshake requires version, capabilities, and token.
  - `/ws_ui` for UI; first message is `ui_hello` with token.
- Use only `https://192.168.100.17:9443/admin` for browser checks unless the user explicitly requests another target.
- Do not weaken auth, role, actor, token, audit, or observer behavior.

## Start here

- Read `server/docs/CODEMAP.md` before analysis or edits in `server/`.
- Read `server/docs/SECURITY_AND_AUTH.md` for auth-sensitive work.
- Read `server/docs/PROTOCOL_V3.md` and `.agents/skills/pc-client-protocol-v3/SKILL.md` for Protocol V3 work.
- Read `server/docs/OBSERVER_LAYER.md` and `server/docs/OBSERVER_AUTHORING_RULES.md` when work touches trace, dangerous flow, tech panel, support trace summary, observer API, or trace-visible UI.

## CODEMAP and docs

- The canonical server CODEMAP is `server/docs/CODEMAP.md`.
- Update it when server routes, handlers, services, startup/runtime flows, key entrypoints, or structure change.
- If observer, dangerous flow, or trace-visible API/UI changes, update observer docs in the same change.
- For docs drift decisions, use `.agents/skills/pc-client-docs-drift/SKILL.md`.

## Hard invariants

- `command_result` always completes an operation.
- `device_outbox=delivered` means delivered/processed, not tool success.
- Tool success, error, and `consent_required` are reflected through operation state/result.
- Timeout uses `device_outbox=failed` with `TIMEOUT`; see `server/docs/COMMAND_RESULT_LIFECYCLE.md`.
- `tool_call_started` is created by the server before sending `run_tool`; see `server/docs/TOOL_CALL_STARTED_INVARIANT.md`.
- Do not log raw tokens or auth headers.
