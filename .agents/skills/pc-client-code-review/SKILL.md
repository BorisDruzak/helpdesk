---
name: pc-client-code-review
description: Use to review pc_client changed code, PR diffs, staged changes, risky edits, security-sensitive changes, architecture changes, or test coverage before commit/release.
---

# pc-client-code-review

## When to use

Use for reviewing changed code, staged changes, PR diffs, risky edits, security-sensitive changes, architecture changes, or test coverage before commit/release.

## Inputs

- Diff or PR.
- Changed files.
- Intended behavior.
- Test and verification results when available.

## Workflow

1. Inspect diff:
   - `git status --short`
   - `git diff --stat`
   - `git diff`
2. Classify affected surfaces.
3. Review for:
   - correctness
   - security, auth, token handling
   - contract drift
   - race conditions
   - error handling
   - missing tests
   - docs/CODEMAP drift
   - deploy/runtime risk
4. Prefer actionable findings over style commentary.
5. If there are no findings, say that clearly and mention residual test gaps.

## Verification

Check whether the verification commands match the affected surfaces. Treat missing relevant tests as a finding when it creates real risk.

## Final response requirements

Lead with findings ordered by severity:

- Blocker
- High
- Medium
- Low

Each finding must include:

- file/path
- issue
- why it matters
- suggested fix
- verification needed
