# Codex Workflow

## Start

For a non-trivial task, inspect `git status --short`, classify the change as local, boundary, cross-cutting, or release-control, then open only the documentation and CODEMAP sections directly related to the files being changed. Do not load broad lookup, index, or intake material.

## Modes

| Mode | Required evidence |
|---|---|
| Explore | Relevant paths, ownership zone, and risks |
| Debug | Reproduction, root cause, and focused regression check |
| Change | Minimal diff plus tests for the changed surface |
| Boundary | Producer/consumer compatibility and docs/CODEMAP review |
| Browser-visible | Real browser route and console/network evidence |
| Release-control | Project release script output and matching remote smoke |

## Working rules

- Work only in the local Windows checkout. Do not patch SMB or Linux mirrors manually.
- Preserve unrelated dirty files and stage only files belonging to the task.
- Use project lifecycle and deployment scripts rather than manual remote changes.
- For webapp work, bootstrap the frontend toolchain before frontend checks.
- For live debugging, GUI, protocol, browser, or runtime work, follow `docs/LIVE_TESTING_DEBUG_RULES.md`.

## Completion

Run `python scripts/verify_workspace.py` plus the narrowest relevant checks. For browser-visible changes, collect browser evidence. For routes, contracts, entrypoints, deployment, or workflow changes, update the matching docs/CODEMAP in the same change.

Full CI and the full release gate are release-candidate actions, not routine completion checks.
