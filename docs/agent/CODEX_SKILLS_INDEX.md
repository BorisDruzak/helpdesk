# Codex Skills Index

## Purpose

This document routes recurring Codex work to repo-local skills.

Root `AGENTS.md` should stay concise. Detailed repeatable workflows live in `.agents/skills/*/SKILL.md`.

Subsystem-specific instructions are indexed in `docs/agent/NESTED_AGENTS_INDEX.md`.

Project-scoped Codex custom subagents are indexed in `docs/agent/SUBAGENTS_INDEX.md`.

## Routing table

| Task type | Skill | Supporting docs | Required evidence/checks |
|---|---|---|---|
| Bug, regression, failing test, unexpected behavior, runtime error | `pc-client-systematic-debug` | `docs/LIVE_TESTING_DEBUG_RULES.md`, `docs/CODEX_WORKFLOW.md`, relevant CODEMAP files | repro, root cause, targeted test/check |
| Browser-visible UI/admin/webapp change | `pc-client-browser-check` | frontend docs, browser/live testing docs | real browser evidence, route/flow tested |
| Release candidate, deploy, remote smoke, full gate | `pc-client-release-gate` | release/deploy docs, workflow docs | SHA/branch, local checks, remote checks |
| Review changed code or PR-style diff | `pc-client-code-review` | architecture/security docs, CODEMAP files | actionable findings with severity |
| Docs/CODEMAP drift after code, route, workflow, contract, deploy, or script change | `pc-client-docs-drift` | relevant CODEMAP files, protocol/deploy docs | docs checked, docs updated or intentionally skipped |

## Usage examples

Explicit skill invocation examples:

```text
Use pc-client-systematic-debug to investigate this failing pytest.
Use pc-client-browser-check to validate the admin UI change in a real browser.
Use pc-client-release-gate for release candidate preflight.
Use pc-client-code-review to review uncommitted changes.
Use pc-client-docs-drift to check whether docs/CODEMAP need updates.
```

## Maintenance rules

- Keep each skill focused on one job.
- Do not move hard safety rules out of root `AGENTS.md`.
- Do not duplicate full workflows between root `AGENTS.md` and skills.
- Update this index when adding, renaming, or deleting a skill.
