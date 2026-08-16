---
name: pc-client-docs-drift
description: Use for pc_client docs drift checks after code changes: CODEMAP updates, route/API changes, protocol changes, scripts, startup/deploy workflows, architecture boundaries, public behavior, or documented command changes.
---

# pc-client-docs-drift

## When to use

Use when code changes may require documentation or CODEMAP updates.

Typical triggers: docs drift, update docs, CODEMAP, route changed, API changed, workflow changed, script changed, deploy changed, startup changed, protocol changed, architecture boundary, public behavior changed, or quick lookup.

## Inputs

- Changed files or diff.
- Affected surfaces.
- Behavior changed.
- Docs suspected stale.
- Whether Codex should edit docs or only report drift.

## Workflow

1. Inspect changed files:
   - `git status --short`
   - `git diff --stat`
   - `git diff`
2. Classify documentation impact:
   - no docs needed
   - docs update recommended
   - docs update required
   - CODEMAP update required
   - protocol/deploy workflow update required
3. Check whether changes affect routes/endpoints, API contracts, Protocol V3/messages/lifecycle, startup flow, deploy/release flow, scripts/commands, configuration, architecture boundaries, user-visible behavior, admin/browser workflow, tests/check commands, or troubleshooting/debug procedures.
4. Read relevant docs when available:
   - `docs/CODEX_WORKFLOW.md`
   - `docs/ARCHITECTURE_BOUNDARIES.md`
   - `docs/LIVE_TESTING_DEBUG_RULES.md`
   - `docs/LOCAL_WORKFLOW.md`
   - `server/docs/CODEMAP.md`
   - `pc_agent/docs/CODEMAP.md`
   - `server/docs/PROTOCOL_V3.md`
   - `pc_agent/docs/PROTOCOL_V3.md`
5. Update docs only when there is real drift.
6. If docs are intentionally not changed, record why.
7. Keep docs concise and navigable.

## Rules

- Do not update docs just to create noise.
- Do not leave CODEMAP stale when entrypoints, key files, flows, or contracts change.
- Do not duplicate large sections across docs.
- Prefer linking to canonical docs over copying.
- Preserve UTF-8 and Russian text.
- Treat mojibake as a defect.
- If code behavior and docs disagree, identify the drift instead of silently choosing one.

## Verification

Confirm docs checked, drift found, docs changed, docs intentionally not changed, CODEMAP impact, and remaining documentation risks.

## Final response requirements

Include documentation impact classification, files/docs changed, files/docs checked, skipped docs with reason, and remaining drift risk.
