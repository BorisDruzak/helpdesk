# helpdesk-server-debug MCP Server

`helpdesk-server-debug` is a standalone stdio MCP server for Codex read-only diagnostics in `pc_client`.

It exposes Observer, Tech locator, Context Index, DB health and persisted runtime/presence snapshots through project Python services and DB sessions. It does not proxy the HTTP API and does not start the aiohttp server.

## Safety Model

- Mode: `debug_readonly`.
- No business mutation tools.
- No `run_tool`.
- No DeviceOutbox writes.
- No approvals or consent decisions.
- No WS RPC or live agent commands.
- No observer rebuild by default.
- No raw tokens, cookies, auth headers, consent tokens, API keys, private keys or raw connection strings in output.
- Every tool response is JSON text and passes recursive redaction.

## Tools

- `helpdesk_db_health`: checks PostgreSQL reachability through project DB bootstrap with redacted error output.
- `helpdesk_context_search`: searches the deterministic local Context Index.
- `helpdesk_context_freshness`: reports index freshness without rebuilding.
- `helpdesk_locate`: locates tickets, devices, operations and traces from DB evidence.
- `observer_debug_bundle`: returns a bounded observer diagnostics bundle for one locator input.
- `observer_trace_detail`: returns trace, spans, span links and error occurrences.
- `observer_ticket_summary`: returns compact ticket-scoped observer summary.
- `observer_runtime_status`: returns a fresh persisted `server_runtime_snapshots` row written by the live aiohttp server; if no fresh row exists it returns a controlled partial.
- `observer_presence_snapshot`: returns persisted `device_presence_snapshots`, DB `Device.last_seen_at` / `last_handshake_at` evidence, and live WS evidence from the latest fresh server runtime snapshot when available. Without `device_id`, fresh runtime snapshots expose aggregate connected-agent WS evidence; with `device_id`, they expose that device's live WS evidence.
- `helpdesk_mcp_manifest`: returns the server manifest.

## Admin UI

The React admin route `/app/admin/ai-integration` shows the MCP server status, DB health, Context Index freshness, latest persisted runtime snapshot and the reload-after-deploy instruction. The backing endpoint is `GET /api/web/admin/ai-integration/mcp` and stays read-only.

After deploy, restart or reload the Codex MCP connection so the stdio process imports the new server code instead of keeping an old Python import graph.

## Codex Config Example

Run Codex from the repository root, or set the MCP server working directory to:

```text
C:\Users\admin-2\CodexProjects\pc_client
```

Example `C:\Users\admin-2\.codex\config.toml` entry:

```toml
[mcp_servers.helpdesk-server-debug]
command = "python"
args = ["-m", "mcp_helpdesk_server.server"]

[mcp_servers.helpdesk-server-debug.env]
MCP_HELPDESK_MODE = "debug_readonly"
```

If `DATABASE_URL` is needed, use a placeholder in docs and put the real value only in local environment/config:

```toml
DATABASE_URL = "postgresql+asyncpg://<user>:<password>@<host>:<port>/<db>"
```

## Manual Smoke

Install dependencies:

```powershell
pip install -r mcp_helpdesk_server/requirements.txt
```

Import/config smoke:

```powershell
python scripts/mcp_helpdesk_server_doctor.py
```

DB health smoke:

```powershell
python scripts/mcp_helpdesk_server_doctor.py --db-health
```

Stdio MCP smoke:

```powershell
python -m mcp_helpdesk_server.server
```

The stdio process should start and wait for MCP input without import errors.
