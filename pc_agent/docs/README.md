# PC Agent

PC Agent is a desktop-side runtime that connects to the server over WebSocket,
executes approved tools, and sends structured results/events back through
Protocol V3.

This document is a clean entrypoint to the current docs set. Detailed behavior,
contracts, and architecture are split into focused files.

## Start Here

- pc_agent/docs/CODEMAP.md - architecture map and entrypoints
- pc_agent/docs/PROTOCOL_V3.md - agent-side Protocol V3 contract
- pc_agent/docs/AUTHENTICATION.md - token sources and auth flow
- pc_agent/docs/MODULES.md - module packaging and runtime loading
- pc_agent/docs/DATABASE.md - local DB schema and outbox/inbox behavior

## Runtime Overview

- Main runtime: pc_agent/ws_agent.py
- Orchestration and command execution: pc_agent/core/orchestrator.py
- Event delivery and retries: pc_agent/core/sender.py
- UI bridge API/SSE: pc_agent/ui_bridge/
- Optional desktop GUI: pc_agent/ui_gui/

## Core Principles

- Protocol-first transport (ws_ticket_v3, envelope V3, outbox ACK/NACK)
- Deterministic command lifecycle and idempotent delivery
- Strict role/risk checks for tool execution
- Backward compatibility only where explicitly documented

## Local Verification

- Workspace checks: python scripts/verify_workspace.py
- Agent tests: python -m pytest pc_agent/tests/
- Targeted tests by feature area are preferred over full-suite runs during
  incremental development.

## Notes

- Legacy compatibility paths may still exist for migration windows, but new code
  should follow current contracts from PROTOCOL_V3.md and AUTHENTICATION.md.
- Keep this README concise; update detailed behavior in topic-specific docs.
