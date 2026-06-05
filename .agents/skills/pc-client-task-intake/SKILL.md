---
name: pc-client-task-intake
description: Use at the start of any non-trivial pc_client task, unclear request, multi-step change, architecture-sensitive change, release-control change, or task that needs planning before edits.
---

# pc-client-task-intake

## When to use

Use before implementation when the task is not a trivial one-file edit. Use for unclear scope, multi-stage work, dirty-worktree triage, boundary-sensitive work, and release-control changes.

## Inputs

- User request or plan.
- Current workspace state.
- Root `AGENTS.md`.
- Routing docs when present: `docs/CODEX_WORKFLOW.md`, `docs/QUICK_LOOKUP.md`, `docs/ARCHITECTURE_BOUNDARIES.md`, `docs/CONTEXT_INDEX.md`.

## Workflow

1. Work from `C:\Users\admin-2\CodexProjects\pc_client`.
2. Bootstrap UTF-8 before reading or writing Russian text:
   - `.\scripts\bootstrap_shell_utf8.ps1`
3. Check workspace state:
   - `git status --short`
4. Run intake when available:
   - `python scripts/task_intake.py`
5. Read routing docs when relevant:
   - `docs/CODEX_WORKFLOW.md`
   - `docs/QUICK_LOOKUP.md`
   - `docs/CONTEXT_INDEX.md`
   - `docs/ARCHITECTURE_BOUNDARIES.md`
6. Classify the task:
   - local
   - boundary
   - cross-cutting
   - release-control
7. Identify likely affected surfaces:
   - server
   - pc_agent
   - webapp
   - docs
   - deploy/release scripts
   - Protocol V3 or other contracts
8. Decide whether `PLANS.md` is needed.

## Verification

Before editing, confirm:

- Workspace dirtiness is understood and unrelated user work will not be overwritten.
- The change classification is stated.
- Relevant docs or CODEMAP files have been identified.
- The verification plan matches the affected surface.

## Final response requirements

For intake-only work, report:

- task classification
- affected surfaces
- files/docs likely involved
- verification plan
- risks and assumptions
