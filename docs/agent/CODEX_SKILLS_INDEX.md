# Codex Skills Index

## Purpose

Route recurring Codex work in `pc_client` to the correct repo-local skill and supporting documentation.

| Task type | Skill | Supporting docs | Required checks |
|---|---|---|---|
| New task intake, unclear scope, multi-step planning, architecture-sensitive work | `pc-client-task-intake` | `docs/CODEX_WORKFLOW.md`, `docs/QUICK_LOOKUP.md`, `docs/ARCHITECTURE_BOUNDARIES.md` | `git status --short`, `python scripts/task_intake.py`, change classification |
| Codebase exploration, finding files, routes, symbols, tests, contracts, or docs | `pc-client-context-pack` | `docs/CONTEXT_INDEX.md`, `docs/QUICK_LOOKUP.md`, relevant CODEMAP files | context pack/search output, targeted `agent_find` result |
| Bug, regression, failing test, live incident, runtime error, GUI/browser failure | `pc-client-systematic-debug` | `docs/LIVE_TESTING_DEBUG_RULES.md`, `docs/CODEX_WORKFLOW.md`, relevant CODEMAP files | recorded repro evidence, root-cause hypothesis, targeted tests |
| Browser-visible server UI, `webapp/`, forms, navigation, visual state, accessibility | `pc-client-browser-check` | `docs/LIVE_TESTING_DEBUG_RULES.md`, `docs/QUICK_LOOKUP.md`, `webapp/AGENTS.md` | real browser route/flow evidence, relevant frontend checks |
| Release candidate freeze, deploy, remote Linux validation, smoke checks, full gate | `pc-client-release-gate` | `docs/LOCAL_WORKFLOW.md`, `docs/CODEX_WORKFLOW.md`, `docs/ARCHITECTURE_BOUNDARIES.md` | `verify_workspace`, targeted checks, explicit full gate only when requested |
| Review changed code or risky diffs before commit/release | `pc-client-code-review` | `docs/ARCHITECTURE_BOUNDARIES.md`, security/protocol docs, CODEMAP files | severity-ranked findings or explicit no-finding result |
| Docs, CODEMAP, route, contract, startup, deploy, observer, or navigation drift | `pc-client-docs-drift` | `docs/QUICK_LOOKUP.md`, `docs/CONTEXT_INDEX.md`, CODEMAP files, observer docs | docs checked/updated list |
| Protocol V3, websocket, outbox ACK, ticket lifecycle, identity, actor/auth contract | `pc-client-protocol-v3` | `pc_agent/docs/PROTOCOL_V3.md`, `server/docs/PROTOCOL_V3.md`, CODEMAP files | producer/consumer search, contract tests/checks, docs updated |

## External skills

Repo-local skills are the first routing layer for project-specific workflow. External skills remain useful when they do not conflict with root `AGENTS.md` or project docs:

| Situation | External skill |
|---|---|
| Any bug, test failure, or unexpected behavior | `superpowers:systematic-debugging` |
| Long or multi-stage plan | `superpowers:writing-plans` |
| Executing an agreed plan | `superpowers:executing-plans` |
| Before claiming completion, commit, push, PR, or deploy | `superpowers:verification-before-completion` |
| Risky or broad final review | `superpowers:requesting-code-review` |
| New webapp screen or major visual redesign | `build-web-apps:frontend-app-builder` |
| React/Next.js performance-sensitive changes | `build-web-apps:react-best-practices` |

## Notes

- Full CI/full gate is a release-candidate checkpoint and is run only by explicit user request for a frozen SHA.
- Browser-visible behavior requires real browser evidence, not only API, DB, smoke, or unit-test evidence.
- Keep source-of-truth, security, verification, UTF-8, and release/deploy invariants in root `AGENTS.md`; keep detailed procedures in skills and docs.
