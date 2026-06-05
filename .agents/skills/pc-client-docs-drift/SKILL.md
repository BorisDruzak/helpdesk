---
name: pc-client-docs-drift
description: Use when pc_client changes routes, APIs, contracts, startup flows, deployment flows, architecture boundaries, CODEMAP-covered files, scripts, observer-visible behavior, or documented behavior.
---

# pc-client-docs-drift

## When to use

Use when code or instructions change routes, APIs, Protocol V3, deployment, startup, scripts, architecture boundaries, observer-visible behavior, CODEMAP-covered files, or documented behavior.

## Inputs

- Changed files.
- Diff summary.
- Affected ownership zone.
- Existing docs and CODEMAP files.

## Workflow

1. Inspect changed files:
   - `git status --short`
   - `git diff --stat`
2. Determine whether changes affect:
   - routes
   - APIs
   - Protocol V3
   - deployment
   - startup
   - scripts
   - architecture boundaries
   - public behavior
   - observer/dangerous-flow behavior
   - tests/checks
3. Check relevant docs:
   - `docs/QUICK_LOOKUP.md`
   - `docs/CONTEXT_INDEX.md`
   - relevant CODEMAP files
   - protocol docs
   - release/deploy docs
   - observer docs
4. Update docs in the same change when required.
5. Do not update docs just to create noise; update only when behavior, workflow, navigation, or structure changed.

## Verification

Confirm:

- docs that should change were updated
- docs intentionally not changed have a reason
- CODEMAP updates match the changed ownership zone
- observer docs are updated for dangerous-flow or trace-visible changes

## Final response requirements

Include:

- docs checked
- docs changed
- docs intentionally not changed, with reason
- remaining drift risk
