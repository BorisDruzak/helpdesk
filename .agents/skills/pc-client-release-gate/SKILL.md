---
name: pc-client-release-gate
description: Use for pc_client release candidate work, deploy, full gate, preflight, remote Linux validation, smoke checks, CI artifact validation, pilot readiness, final verification, or pre-push release review.
---

# pc-client-release-gate

## When to use

Use for release, deploy, and final-gate tasks.

Typical triggers: release, deploy, full gate, preflight, RC, release candidate, remote smoke, Linux validation, pilot ready, final check, pre-push, or CI artifact.

## Inputs

- Target branch/SHA.
- Release candidate scope.
- Affected surfaces.
- Requested gate level: targeted checks, workspace sanity, remote smoke, or full CI/full gate.
- Whether services should remain running after validation.

## Workflow

1. Check workspace and branch:
   - `git status --short`
   - `git branch --show-current`
   - `git rev-parse --short HEAD`
2. Confirm candidate state: branch, SHA, dirty/untracked files, whether candidate is frozen, and whether the user explicitly requested full gate.
3. Read relevant docs when available:
   - `docs/CODEX_WORKFLOW.md`
   - `docs/QUICK_LOOKUP.md`
   - `docs/ARCHITECTURE_BOUNDARIES.md`
   - `docs/LOCAL_WORKFLOW.md`
   - `docs/LIVE_TESTING_DEBUG_RULES.md`
4. Run workspace sanity when available:
   - `python scripts/verify_workspace.py`
5. Run targeted checks for affected surfaces.
6. Run full gate only when explicitly requested by the user or required by the current release step.
7. Use documented project scripts only, for example when present and appropriate:
   - `python scripts/release_candidate_preflight.py`
   - `python scripts/run_ci_suite.py`
   - `python scripts/deploy_workspace_to_remote.py`
   - `python scripts/release_server_to_remote.py`
   - `python scripts/manage_remote_stack.py status`
   - `python scripts/manage_remote_stack.py smoke`
   - `python scripts/manage_remote_stack.py logs server`
8. After remote/Linux validation, stop services unless the user explicitly asked to leave them running.
9. Record all checks and results.

## Rules

- Release/deploy work must use project scripts only.
- Do not manually patch deployed files or runtime mirrors.
- Do not run expensive full CI unless explicitly requested or required by release policy.
- Do not deploy from an unknown dirty candidate.
- Do not claim release readiness with skipped critical checks.
- Do not leave remote services running by accident.
- Do not expose tokens, secrets, or credentials in logs.
- If a release check fails, stop and report blockers before continuing.

## Verification

Verify branch, SHA, dirty tree status, local checks, targeted checks, full gate status, remote checks, deploy/release status, and service state after validation.

## Final response requirements

Include branch, SHA, dirty tree status, local checks, targeted checks, full gate status, remote checks, deploy/release status, services left running or stopped, blockers, skipped checks with reason, and residual risks.
