# AGENTS.md Refactor Map

## Purpose

This document records how the old root `AGENTS.md` content was redistributed into a smaller operating contract plus repo-local skills, reference docs, and nested subsystem instructions.

## Migration table

| Old section / topic | New location | Classification | Reason | Risk if lost |
|---|---|---|---|---|
| Source-of-truth paths: local Windows repo, SMB mirror, Linux stand | `AGENTS.md` | keep-root | Applies to every task before any file operation | Codex may edit the SMB mirror or manually patch the deployed tree |
| Mandatory work cycle: local edits, `PLANS.md`, intake, workflow docs, context pack, CODEMAP | `AGENTS.md`, `.agents/skills/pc-client-task-intake/SKILL.md`, `.agents/skills/pc-client-context-pack/SKILL.md` | split | Root keeps the universal start gate; skills hold detailed repeatable workflow | Codex may skip intake, classification, or targeted context |
| Context and artifacts index | `docs/agent/CODEX_SKILLS_INDEX.md`, existing `docs/QUICK_LOOKUP.md`, `docs/CODEX_WORKFLOW.md`, `docs/CONTEXT_INDEX.md` | move-doc | Reference material does not need to stay in always-on root instructions | Root grows back into a command catalog |
| Docs and CODEMAP synchronization rules | `AGENTS.md`, `.agents/skills/pc-client-docs-drift/SKILL.md`, `docs/ARCHITECTURE_BOUNDARIES.md`, relevant CODEMAP files | split | Root keeps the invariant; skill owns the checklist | Routes, contracts, and entrypoints may drift from docs |
| Observer and dangerous-flow docs sync | `.agents/skills/pc-client-docs-drift/SKILL.md`, `server/AGENTS.md`, `pc_agent/AGENTS.md`, `server/docs/OBSERVER_LAYER.md`, `server/docs/OBSERVER_AUTHORING_RULES.md` | split | Observer rules are subsystem-sensitive and workflow-specific | Dangerous flows may lose trace-visible coverage or authoring rules |
| Profile modes and auto-router | `docs/agent/CODEX_SKILLS_INDEX.md`, `.agents/skills/*/SKILL.md`, existing workflow docs | move-doc | Routing belongs in an index and trigger-focused skill descriptions | Codex may select an ad-hoc workflow |
| External plugin skill references | `docs/agent/CODEX_SKILLS_INDEX.md` | move-doc | Useful routing reference, not a root invariant | Duplicated or stale plugin-routing prose in root |
| Live testing and debugging rules | `AGENTS.md`, `.agents/skills/pc-client-systematic-debug/SKILL.md`, `.agents/skills/pc-client-browser-check/SKILL.md`, `docs/LIVE_TESTING_DEBUG_RULES.md` | split | Root keeps the evidence requirement; skill/doc keep the detailed playbook | Live fixes may be claimed from a single signal |
| Protocol V3 invariants | `AGENTS.md`, `.agents/skills/pc-client-protocol-v3/SKILL.md`, `server/AGENTS.md`, `pc_agent/AGENTS.md`, protocol docs | split | Core wire-contract invariants stay always-on; details load only for protocol work | Server and agent may drift on sequencing, identity, or ACK semantics |
| Security and token hygiene | `AGENTS.md`, `server/AGENTS.md`, `pc_agent/AGENTS.md`, live-debug docs | keep-root / split | Raw token and auth-context rules are always-on; subsystem files repeat local hard edges | Raw credentials may be logged or actor context may be trusted from payloads |
| Browser canon and admin URL | `AGENTS.md`, `.agents/skills/pc-client-browser-check/SKILL.md`, `server/AGENTS.md`, `webapp/AGENTS.md` | split / move-nested | Browser evidence is global for visible UI; route and frontend checks are subsystem-specific | UI may be validated only through smoke/API checks |
| Release, deploy, full gate, remote stop | `AGENTS.md`, `.agents/skills/pc-client-release-gate/SKILL.md`, `docs/LOCAL_WORKFLOW.md`, release scripts docs | split | Root keeps scripts-only and full-gate policy; skill owns execution details | Manual deploy, stale release candidate, or server left running |
| Commit and GitHub push checkpoint rule | `AGENTS.md`, `.agents/skills/pc-client-release-gate/SKILL.md` | keep-root / split | Publishing policy affects completion state for every task | Local commit may be mistaken for a finished checkpoint |
| UTF-8 and Windows shell rules | `AGENTS.md`, task-intake/context skills | keep-root | The user works in Windows PowerShell with Russian text | Mojibake or corrupt docs may be saved |
| Server-specific relay, WS, command-result, `tool_call_started` rules | `server/AGENTS.md`, `.agents/skills/pc-client-protocol-v3/SKILL.md` | move-nested / move-skill | These rules only apply inside server work | Server may break operation lifecycle semantics |
| Agent-specific SQLite, modules, observer SDK, ACK rules | `pc_agent/AGENTS.md`, `.agents/skills/pc-client-protocol-v3/SKILL.md` | move-nested / move-skill | These rules only apply inside agent work | Agent runtime, module trace, or outbox ACK semantics may break |
| Frontend/bootstrap/browser workflow | `webapp/AGENTS.md`, `.agents/skills/pc-client-browser-check/SKILL.md` | move-nested / move-skill | `webapp/` exists and has distinct toolchain/browser checks | React/browser work may skip bootstrap or real browser evidence |
| Duplicate long reminders already present in docs | `docs/agent/AGENTS_REFACTOR_MAP.md` | remove-duplicate | Retained as mapped references instead of duplicated prose | Low if the target location remains accurate |

## Post-refactor invariant

The new root `AGENTS.md` must be sufficient to start any task safely, but it must not contain every detailed debug, browser, release, or protocol playbook. Load the relevant repo-local skill and supporting docs when the task enters one of those workflows.
