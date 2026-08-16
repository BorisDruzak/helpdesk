# Nested AGENTS.md Index

## Purpose

This repository uses nested `AGENTS.md` files to keep root `AGENTS.md` concise while preserving subsystem-specific Codex guidance.

Root `AGENTS.md` contains always-on project rules. Nested `AGENTS.md` files contain local rules that apply only to a subsystem.

## Files

| Path | Applies to | Purpose |
|---|---|---|
| `AGENTS.md` | Entire repository | Source-of-truth, global safety, start protocol, verification contract, release/deploy contract |
| `server/AGENTS.md` | Backend/server work | Server routes, services, auth/actor logic, server runtime, server CODEMAP/docs |
| `pc_agent/AGENTS.md` | PC agent work | Agent runtime, Protocol V3 client behavior, GUI/live-debug, agent CODEMAP/docs |
| `webapp/AGENTS.md` | Frontend/browser work | Webapp UI, browser validation, frontend build/toolchain, webapp docs |

## What belongs in root

Keep these in root `AGENTS.md`:

- source-of-truth paths
- global safety rules
- general start protocol
- project-wide context discovery
- verification contract
- release/deploy contract
- final response contract
- skill routing
- nested instruction routing

## What belongs in nested AGENTS.md

Put these in nested files:

- subsystem-specific docs/CODEMAP paths
- subsystem-specific test/check commands
- subsystem-specific implementation conventions
- subsystem-specific risk reminders
- local skill routing
- local docs/CODEMAP drift rules

## What does not belong in nested AGENTS.md

Do not put these in nested files:

- full copies of root `AGENTS.md`
- full copies of skill workflows
- temporary override/freeze rules
- commands that do not exist in the project
- broad architecture essays
- obsolete troubleshooting notes

## Skills relationship

Nested `AGENTS.md` files should route to skills, not duplicate them.

Use:

- `.agents/skills/pc-client-systematic-debug/SKILL.md`
- `.agents/skills/pc-client-browser-check/SKILL.md`
- `.agents/skills/pc-client-release-gate/SKILL.md`
- `.agents/skills/pc-client-code-review/SKILL.md`
- `.agents/skills/pc-client-docs-drift/SKILL.md`

## Maintenance rules

- Add a nested rule only after repeated mistakes or clear subsystem friction.
- Keep each nested file short and operational.
- Prefer links to canonical docs over duplicated text.
- If a rule applies to all subsystems, keep it in root.
- If a rule applies to one subsystem, put it in that subsystem.
- If a rule is a repeatable procedure, put it in a skill.
- If a rule is reference material, put it in docs.
