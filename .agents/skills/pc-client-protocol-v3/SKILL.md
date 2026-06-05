---
name: pc-client-protocol-v3
description: Use for pc_client Protocol V3 changes, client/server contract work, ticket lifecycle changes, agent protocol messages, outbox ACK, auth/actor context, compatibility, migrations, or contract tests.
---

# pc-client-protocol-v3

## When to use

Use for Protocol V3, websocket, outbox ACK, ticket lifecycle, agent/server message schema, identity, auth/actor context, compatibility, migrations, or contract tests.

## Inputs

- Contract or behavior being changed.
- Producer and consumer files.
- Protocol docs and CODEMAP files.
- Relevant tests or live evidence.

## Workflow

1. Treat protocol changes as boundary changes even when the diff is small.
2. Read protocol docs:
   - `server/docs/PROTOCOL_V3.md`
   - `pc_agent/docs/PROTOCOL_V3.md`
   - relevant CODEMAP files
3. Identify affected contract:
   - message schema
   - endpoint
   - lifecycle state
   - sequencing
   - ACK behavior
   - auth/actor context
   - backward compatibility
   - migration/default behavior
4. Search for all consumers and producers:
   - `python scripts/search_context_index.py "<protocol symbol route message>"`
   - `python scripts/agent_find.py "<protocol symbol>" --dir server`
   - `python scripts/agent_find.py "<protocol symbol>" --dir pc_agent`
5. Preserve hard invariants:
   - event type is determined only by `device_seq` vs `agent_seq`
   - handshake uses `protocol_version === "ws_ticket_v3"` and required capabilities
   - server `device_id` comes from the token record, not payload
   - identity model is stable `machine_id` plus secondary `install_id`
   - server creates idempotent `tool_call_started` before `run_tool`
   - ACK deletes outbox rows according to the agent sender contract
6. Update both sides of the contract when required.
7. Add or update contract tests when realistic.
8. Update protocol docs and CODEMAP files.

## Verification

Run targeted producer/consumer tests. For live protocol work, collect evidence from the canonical test surface and avoid raw WS probes unless the plan explicitly requires them.

## Final response requirements

Include:

- contract changed
- producer/consumer files checked
- compatibility impact
- tests/checks
- docs updated
