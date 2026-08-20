# Codex Subagents Index

## Purpose

This document indexes project-scoped Codex custom subagents in `.codex/agents/`.

Subagents are helpers for parallel context gathering, checks, browser evidence, review, and docs drift audit. They do not replace root `AGENTS.md`, subsystem `AGENTS.md`, repo-local skills, or the main agent's responsibility for implementation, final verification, commit, push, and deploy decisions.

## Global Limits

- These subagents are project-scoped only; do not copy them into `~/.codex/agents`.
- Do not use subagents to edit the same source files concurrently.
- Read-only agents must not write files, artifacts, git state, or remote state.
- Workspace-write agents may write only normal verification artifacts, caches, logs, screenshots, traces, or temporary profiles.
- No subagent may stage, commit, push, deploy, manually patch `/var/chat_bot/pc_client`, or manually patch `\\example.test\NTFS_Share\pc_client`.
- The main agent owns source edits, docs edits, final integration, and final completion claims.

## Agent Routing

| Agent | Sandbox | Use for | Do not use for |
|---|---|---|---|
| `context-mapper` | `read-only` | Finding affected files, docs, routes, symbols, tests, CODEMAP entries, and ownership boundaries before implementation. | Editing files, running mutating checks, or deciding final completion. |
| `test-runner` | `workspace-write` | Running focused checks, pytest, `verify_workspace`, and reporting command evidence. | Source edits, docs edits, git operations, deploy, or full CI without explicit request. |
| `reviewer` | `read-only` | Strict PR-style review of staged or uncommitted diffs. | Making fixes or rewriting patches. |
| `browser-verifier` | `workspace-write` | Browser-visible validation, screenshots, traces, console/network evidence, and admin/webapp UI checks. | UI fixes, source edits, commits, deploys, or replacing project smoke checks. |
| `docs-drift-auditor` | `read-only` | Checking docs, CODEMAP, AGENTS, workflow, observer, protocol, and release/deploy drift. | Editing documentation or treating docs drift review as final verification. |

## Suggested Prompts

```text
Ask context-mapper to map the ticket lifecycle files, docs, tests, and risk boundaries for this change.
Ask test-runner to run python scripts/verify_workspace.py and the targeted pytest for the changed server route.
Ask reviewer to review the staged diff for regressions, missing tests, and project-rule violations.
Ask browser-verifier to validate the relevant route on https://example.test:9443 in a real browser and capture evidence.
Ask docs-drift-auditor to check whether this route/contract change requires CODEMAP or workflow doc updates.
```

## Model Fields

The agent TOML files intentionally omit `model` and reasoning fields. The current project `.codex/config.toml` already sets the default model, and this repository should not guess custom agent model IDs without verified Codex app support for those exact IDs.

## Maintenance

- Update this index when adding, renaming, or deleting `.codex/agents/*.toml`.
- Keep root `AGENTS.md` concise and link here instead of duplicating full agent instructions.
- Keep subagent instructions UTF-8 clean and free of mojibake.
- Do not add hooks, rules, MCP config, or personal agents as part of project subagent routing.
