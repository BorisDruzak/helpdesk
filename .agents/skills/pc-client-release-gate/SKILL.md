---
name: pc-client-release-gate
description: Use for pc_client release candidate freeze, full gate, deploy, remote Linux validation, smoke checks, pilot readiness, CI artifact validation, final pre-push checks, or release/deploy workflow.
---

# pc-client-release-gate

## When to use

Use for release candidates, deploys, remote Linux validation, smoke checks, pilot readiness, full gate, CI artifacts, final pre-push checks, or release/deploy workflow.

## Inputs

- Current branch and candidate SHA.
- Changed files and affected surfaces.
- Whether the user explicitly requested full CI/full gate.
- Remote stand target when different from the project default.

## Workflow

1. Confirm branch and candidate SHA:
   - `git status --short`
   - `git rev-parse --short HEAD`
2. Run workspace sanity:
   - `python scripts/verify_workspace.py`
3. Run targeted checks for affected surfaces.
4. For explicit full-gate work only:
   - run the documented release-candidate preflight
   - run full CI/gate commands for the frozen SHA
5. Use only documented project scripts for deploy/release/remote stack:
   - `python scripts/deploy_workspace_to_remote.py`
   - `python scripts/release_server_to_remote.py`
   - `python scripts/manage_remote_stack.py start|stop|restart|status|smoke|logs server|agent|control`
6. Use explicit `--gate quick` only for iterative stand deploys; it does not replace local verification, targeted pytest, remote smoke, or browser checks.
7. After remote validation, stop services unless the user explicitly asked to leave them running.
8. After local verification, commit and push to GitHub `origin` unless the user explicitly asked not to publish.

## Verification

Confirm:

- workspace sanity result
- targeted check results
- remote smoke/log/browser evidence when applicable
- full gate status when explicitly requested
- services stopped after validation when applicable

## Final response requirements

Include:

- branch/SHA
- local checks
- remote checks
- full gate status
- deploy status
- push status when applicable
- blockers and residual risk
