# server/AGENTS.md - Server Instructions

## Scope

This file applies to backend/server work under `server/`.

Use it for:

- server routes/endpoints
- backend services
- auth/actor/role logic
- Endpoint integration and ticket-facing operation projections
- persistence/database-facing behavior
- server startup/runtime behavior
- server logs/smoke checks
- server CODEMAP/docs updates

Root `AGENTS.md` still applies.

## Local context

Before non-trivial server edits, consult only the relevant server documentation:

- `docs/CODEX_WORKFLOW.md`
- `docs/ARCHITECTURE_BOUNDARIES.md`
- `server/docs/CODEMAP.md`

## Relevant skills

Use repo-local skills when applicable:

- Bugs, regressions, failing tests: `.agents/skills/pc-client-systematic-debug/SKILL.md`
- Code review: `.agents/skills/pc-client-code-review/SKILL.md`
- Docs/CODEMAP drift: `.agents/skills/pc-client-docs-drift/SKILL.md`
- Release/deploy validation: `.agents/skills/pc-client-release-gate/SKILL.md`

## Server implementation rules

- Treat route/API/auth/actor changes as boundary-sensitive.
- Do not weaken authentication, authorization, actor, role, token, audit, or observer behavior.
- Do not log raw tokens, secrets, credentials, auth headers, or private keys.
- Prefer existing service patterns over introducing parallel architecture.
- Keep error handling explicit and observable without leaking secrets.
- Keep server changes minimal and contract-aware.
- If public routes, payloads, lifecycle behavior, startup behavior, or deployment-relevant code changes, update relevant docs and CODEMAP in the same change.
- Helpdesk is not an agent control plane: preserve the Endpoint contract boundary and do not reintroduce local agent transport, local delivery dispatch, or local endpoint execution.

## Verification

Before claiming completion for server work:

- Run workspace sanity when available:
  - `python scripts/verify_workspace.py`
- Run targeted server tests/checks relevant to the changed files.
- For HTTP/API pytest files, consider `test_client_light` only as an explicit per-file opt-in under `docs/TESTING_RULES.md`; keep browser `/ws_ui` tests on the regular `test_client`.
- For API/route changes, run the project-approved smoke or route-level check when available.
- For runtime changes, inspect relevant logs through project scripts rather than ad-hoc remote patching.
- For release/deploy-sensitive changes, use `.agents/skills/pc-client-release-gate/SKILL.md`.

## Docs/CODEMAP drift

Use `.agents/skills/pc-client-docs-drift/SKILL.md` when server work changes:

- routes/endpoints
- service boundaries
- auth/actor behavior
- Endpoint contract or operation-projection behavior
- startup/runtime behavior
- deploy/release assumptions
- test/check commands
- files listed in `server/docs/CODEMAP.md`

## Final response requirements

For server tasks, include:

- server files changed
- route/API/auth/contract impact
- tests/checks run
- docs/CODEMAP updates or why not needed
- residual backend/runtime risks
