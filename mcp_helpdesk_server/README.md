# helpdesk-server-debug MCP

Read-only stdio MCP server for `pc_client` diagnostics. It exposes Observer, Tech locator, Context Index, DB health and runtime/presence snapshot tools without HTTP API proxying, `run_tool`, DeviceOutbox writes, approvals or observer rebuild.

Run from the repository root:

```powershell
pip install -r mcp_helpdesk_server/requirements.txt
python -m mcp_helpdesk_server.server
```

The process waits for MCP JSON-RPC on stdio. It should not print raw `DATABASE_URL`, tokens, cookies or credentials.
