# pc_agent/AGENTS.md - PC Agent Instructions

## Scope

This file applies to work under `pc_agent/`.

Use it for:

- desktop/client agent runtime
- agent startup/shutdown behavior
- client-side Protocol V3 handling
- GUI/UIA/live-debug behavior
- local machine automation
- agent logs/smoke checks
- agent packaging or deployment assumptions
- `pc_agent` CODEMAP/docs updates

Root `AGENTS.md` still applies.

## Local context

Before non-trivial `pc_agent` edits, consult only the relevant agent documentation:

- `docs/CODEX_WORKFLOW.md`
- `docs/ARCHITECTURE_BOUNDARIES.md`
- `docs/LIVE_TESTING_DEBUG_RULES.md`
- `pc_agent/docs/CODEMAP.md`

## Relevant skills

Use repo-local skills when applicable:

- Bugs, regressions, runtime errors: `.agents/skills/pc-client-systematic-debug/SKILL.md`
- Code review: `.agents/skills/pc-client-code-review/SKILL.md`
- Docs/CODEMAP drift: `.agents/skills/pc-client-docs-drift/SKILL.md`
- Release/deploy validation: `.agents/skills/pc-client-release-gate/SKILL.md`

## PC agent implementation rules

- Treat Protocol V3 message/lifecycle changes as boundary-sensitive.
- Check server compatibility before changing client-side protocol behavior.
- Do not introduce behavior that silently diverges from server contracts.
- Preserve existing startup/shutdown and recovery semantics unless the task explicitly changes them.
- Do not log raw tokens, secrets, credentials, private keys, auth headers, or sensitive local-machine data.
- Keep GUI/UIA/live-debug behavior evidence-based.
- Preserve UTF-8; Russian text mojibake is a defect.
- Prefer existing agent runtime patterns over parallel mechanisms.
- If protocol handling, entrypoints, lifecycle states, runtime behavior, or packaging/deploy assumptions change, update relevant docs and CODEMAP.

## Verification

Before claiming completion for `pc_agent` work:

- Run workspace sanity when available:
  - `python scripts/verify_workspace.py`
- Run targeted agent tests/checks relevant to the changed files.
- For GUI/live-debug work, follow `docs/LIVE_TESTING_DEBUG_RULES.md`.
- For Protocol V3 changes, verify both producer and consumer sides.
- For runtime/deploy-sensitive changes, use project-approved smoke/log scripts.

## Docs/CODEMAP drift

Use `.agents/skills/pc-client-docs-drift/SKILL.md` when `pc_agent` work changes:

- agent entrypoints
- protocol handling
- runtime lifecycle
- GUI/UIA behavior
- startup/shutdown behavior
- packaging/deployment assumptions
- files listed in `pc_agent/docs/CODEMAP.md`

## Final response requirements

For `pc_agent` tasks, include:

- agent files changed
- protocol/runtime/GUI impact
- server compatibility impact
- tests/checks run
- docs/CODEMAP updates or why not needed
- residual agent/runtime risks
