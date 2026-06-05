---
name: pc-client-code-review
description: Use for pc_client code review: review uncommitted changes, staged changes, PR diffs, risky edits, security-sensitive changes, architecture changes, missing tests, regressions, or pre-commit review.
---

# pc-client-code-review

## When to use

Use to review changed code or a proposed implementation.

Typical triggers: review, check my changes, PR review, pre-commit, diff, staged changes, uncommitted changes, risky, security, regression, missing tests, or architecture.

## Inputs

- Diff, branch, PR, commit, or working tree.
- Affected surfaces.
- User concerns.
- Release sensitivity.
- Whether to edit or only report findings.

## Workflow

1. Inspect workspace state:
   - `git status --short`
   - `git diff --stat`
   - `git diff`
2. For staged-only review when requested:
   - `git diff --cached --stat`
   - `git diff --cached`
3. Classify changed surfaces: `server`, `pc_agent`, `webapp`, `docs`, `scripts`, deploy/release, tests, protocol/contracts.
4. Read relevant docs/CODEMAP files when the diff touches those surfaces.
5. Review for correctness, regressions, security, auth/actor/role/token handling, data loss, race conditions, error handling, backward compatibility, contract drift, missing tests, observability/logging risk, docs/CODEMAP drift, deployment/runtime impact, and unnecessary broad changes.
6. Verify claims against code, not assumptions.
7. Prefer actionable findings.

## Rules

- Review like a strict maintainer. Prioritize correctness and risk over style.
- Do not nitpick formatting unless it affects correctness or project standards.
- Do not approve risky code without verification.
- Do not ignore docs/CODEMAP drift if routes, contracts, workflows, or deployment behavior changed.
- Do not suggest large rewrites unless the current approach is structurally unsafe.
- Do not expose secrets from diffs or logs.
- If there are no findings, say that explicitly and list what was reviewed.

## Verification

Use severities:

- Blocker: must fix before merge/release.
- High: likely bug, security issue, data loss, or serious regression.
- Medium: plausible bug, missing important test, compatibility/doc drift.
- Low: maintainability, clarity, small test/doc improvement.

## Final response requirements

Include verdict, findings grouped by severity, files reviewed, docs/tests considered, gaps, and assumptions.
