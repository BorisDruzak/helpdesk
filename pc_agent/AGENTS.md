# pc_agent/AGENTS.md

## Agent-specific rules

- Follow root `AGENTS.md`; the local Windows repo remains the source of truth.
- Treat `pc_agent` changes as client/runtime/Protocol V3-sensitive unless clearly local.
- The agent role includes local data collection, Qt GUI, WebSocket client runtime, module execution, and outbox/ACK delivery.
- Local agent DB is SQLite `data/storage.db`; see `pc_agent/docs/DATABASE.md`.
- Check server compatibility before changing messages, lifecycle states, identity, outbox behavior, account/session behavior, or agent runtime behavior.
- Do not log raw tokens, passwords, cookies, consent tokens, or auth headers.

## Start here

- Read `pc_agent/docs/CODEMAP.md` before analysis or edits in `pc_agent/`.
- Read `pc_agent/docs/PROTOCOL_V3.md` and `.agents/skills/pc-client-protocol-v3/SKILL.md` for Protocol V3 work.
- Read `pc_agent/docs/AUTHENTICATION.md` for token source or provisioning work.
- Read `pc_agent/docs/MODULES.md`, `pc_agent/docs/ORCHESTRATOR.md`, and `pc_agent/docs/SENDER.md` for module/runtime/outbox work.
- Read `pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md` for always-on runtime, tray, `ui_bridge`, or `ui_gui` work.
- Read `pc_agent/docs/AGENT_UPDATE_WORKFLOW.md`, `pc_agent/docs/SELF_UPDATE.md`, and `server/docs/AGENT_UPDATES_API.md` for launcher/update/rollout work.
- Read `server/docs/OBSERVER_LAYER.md` and `server/docs/OBSERVER_AUTHORING_RULES.md` when work touches action trace, module breadcrumbs, update trace, or agent-side dangerous flow instrumentation.

## Module observer rule

- Every new `BaseCollector` module must use the observer SDK from `pc_agent/modules/base_module.py`.
- Add at least one top-level `with self.trace_span("tool.entry", ...)` per tool method.
- Add `self.trace_event(...)` or `self.trace_span(...)` around dangerous steps such as subprocess, network, retry, timeout, artifact, consent, and publish.
- Never put raw tokens, passwords, cookies, consent tokens, or other sensitive fields in `details`; use built-in redaction helpers.
- Do not remove generated trace SDK scaffolding from workbench/builder modules unless replacing it with equivalent instrumentation.

## CODEMAP and docs

- The canonical agent CODEMAP is `pc_agent/docs/CODEMAP.md`.
- Update it when agent structure, core/modules/ui_gui/ui_bridge entrypoints, runtime flows, or key files change.
- If agent-side observer coverage, module breadcrumbs, action trace bridge, update trace, or dangerous flow instrumentation changes, update observer docs in the same change.
- For docs drift decisions, use `.agents/skills/pc-client-docs-drift/SKILL.md`.

## Protocol V3 invariants

- Protocol version on handshake is `ws_ticket_v3`.
- Event type is determined only by `device_seq` vs `agent_seq`.
- ACK for outbox means delete the outbox row; there is no durable `sent` state.
- For protocol work, check both server and agent producers/consumers before editing.
