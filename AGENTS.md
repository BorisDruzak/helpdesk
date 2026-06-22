# AGENTS.md - Codex Operating Contract

## Purpose

This file is the always-on operating contract for Codex in this repository. Keep it short. Put detailed workflows in `.agents/skills/*/SKILL.md` and reference material in `docs/`.

## Source of truth

- Work only in the local Windows copy: `C:\Users\admin-2\CodexProjects\pc_client`.
- Treat `\\192.168.100.17\NTFS_Share\pc_client` as a mirror and exchange point, not the edit workspace.
- Treat `/var/chat_bot/pc_client` on Linux as a deployed/stand mirror of committed state, not a manual patch target.
- Code and documentation share one canon: the local Windows working copy.
- Do not change application behavior while editing agent instructions unless the user explicitly asks.

## Start protocol

For any non-trivial task:

1. Bootstrap UTF-8 in PowerShell before working with Russian text:
   - `.\scripts\bootstrap_shell_utf8.ps1`
2. Check the workspace:
   - `git status --short`
3. Run task intake when available:
   - `python scripts/task_intake.py`
4. Read the routing docs when relevant:
   - `docs/CODEX_WORKFLOW.md`
   - `docs/QUICK_LOOKUP.md`
   - `docs/ARCHITECTURE_BOUNDARIES.md`
   - `docs/CONTEXT_INDEX.md`
5. Classify the change:
   - local
   - boundary
   - cross-cutting
   - release-control
6. Build focused context before editing:
   - `python scripts/build_context_pack.py --topic "<task>"`
   - `python scripts/search_context_index.py "<symbol route error concept>"`
   - `python scripts/agent_find.py "<pattern>" --dir server|pc_agent`
7. If context search reports a stale index, rebuild it with `python scripts/build_context_index.py --force` unless the current task is explicitly read-only.
8. For new `webapp/`, React, frontend bundle, or web-asset release work, run:
   - `python scripts/bootstrap_web_toolchain.py`

## Skill routing

Use repo-local Codex skills for repeatable workflows:

- Context discovery, file/symbol search, docs routing: `.agents/skills/pc-client-context-pack/SKILL.md`
- Bugs, regressions, failing tests, runtime errors: `.agents/skills/pc-client-systematic-debug/SKILL.md`
- Browser-visible UI/webapp/admin changes: `.agents/skills/pc-client-browser-check/SKILL.md`
- Release candidate, deploy, remote smoke, full gate: `.agents/skills/pc-client-release-gate/SKILL.md`
- Review diffs, PR-style review, staged/uncommitted changes: `.agents/skills/pc-client-code-review/SKILL.md`
- Docs, CODEMAP, workflow, route, contract drift: `.agents/skills/pc-client-docs-drift/SKILL.md`

See `docs/agent/CODEX_SKILLS_INDEX.md` for the routing table.

Do not duplicate full skill workflows in this file. Keep detailed procedures in the skill files.

## Subagent routing

Use project-scoped custom subagents for parallel read-heavy work and verification support:

- Context mapping: `.codex/agents/context-mapper.toml`
- Test/check execution: `.codex/agents/test-runner.toml`
- Strict diff review: `.codex/agents/reviewer.toml`
- Browser-visible validation: `.codex/agents/browser-verifier.toml`
- Docs/CODEMAP drift audit: `.codex/agents/docs-drift-auditor.toml`

Use subagents for exploration, checks, browser evidence, review, and docs drift audit. Do not use multiple agents to edit the same files concurrently. The main agent owns implementation, final integration, and final verification.

See `docs/agent/SUBAGENTS_INDEX.md`.

## Nested instructions

Subsystem-specific instructions live closer to the code:

- Backend/server work: `server/AGENTS.md`
- PC agent/runtime work: `pc_agent/AGENTS.md`
- Frontend/browser work: `webapp/AGENTS.md`

When working primarily inside one of these directories, consult the local `AGENTS.md` before editing. Local instructions refine this root operating contract; they do not replace global safety, source-of-truth, verification, or release/deploy rules.

Do not duplicate full workflows here. Detailed repeatable workflows live in `.agents/skills/*/SKILL.md`.

## Implementation rules

- Make the smallest correct change.
- Prefer existing project scripts over ad-hoc shell commands.
- Do not add dependencies unless the task requires it and project policy or the user allows it.
- Do not manually copy files into deployment/runtime mirrors when a project script exists.
- Do not overwrite or revert user work.
- If routes, contracts, public behavior, startup flows, deployment flows, key architecture, observer-visible behavior, or CODEMAP-covered structure change, update the relevant docs and CODEMAP files in the same change.
- Use UTF-8 explicitly for text I/O. Preserve Russian text correctly; mojibake is a defect.

## Protocol V3 invariants

- Protocol contracts live in `pc_agent/docs/PROTOCOL_V3.md` and `server/docs/PROTOCOL_V3.md`.
- Event type is defined only by `device_seq` vs `agent_seq`:
  - `device_event` means `device_seq IS NOT NULL AND agent_seq IS NULL`
  - `ticket_event` means `agent_seq IS NOT NULL AND device_seq IS NULL`
- Server handshake requires `protocol_version === "ws_ticket_v3"`, capabilities `protocol_v3`, `envelope_v3`, `outbox_ack_v3`, and token.
- The server takes `device_id` from the token record, not from payload.
- Agent identity model: stable `machine_id`, secondary `install_id`.
- `tool_call_started` is created by the server before sending `run_tool` and is idempotent by `(ticket_id, operation_id, event_type)`.

## Verification contract

Before claiming completion:

1. Run project sanity when available:
   - `python scripts/verify_workspace.py`
2. Run targeted tests/checks for the changed surface.
   - For server pytest fixture selection, cleanup profiles, DB template mode, bounded parallelism, and timing artifacts, follow `docs/TESTING_RULES.md`.
3. For browser-visible changes, collect real browser evidence through the project browser workflow.
4. For GUI/live-debug work, follow `docs/LIVE_TESTING_DEBUG_RULES.md`.
5. Report commands run, results, and any checks not run.

## Release, deploy, and Git contract

- Use only project release/deploy/runtime scripts.
- Do not manually patch deployed files.
- Full CI/full gate is only for explicit frozen release-candidate work.
- Before full release gate, run the project preflight script when available.
- After remote/Linux validation, stop services unless the user explicitly asked to leave them running.
- After local verification, commit locally and push the commit to GitHub `origin` on the current branch unless the user explicitly asked not to publish.

## Browser canon

- Use the deployed stand origin `https://192.168.100.17:9443` for project browser checks unless the user explicitly requests another target.
- Use `/admin` for admin, tech panel, legacy admin/support checks.
- Use the matching `/app/*` route for React workspace checks; web-first requester and web-agent cabinet checks use `/app/requester`, `/app/requester/devices`, and compatible `/app/device/*` linking routes.
- Browser-visible server UI changes require MCP/browser evidence, not only smoke/API/DB checks.
- If tech panel or server-control flow changes, verify status, health, full logs, and confirm behavior for `stop` or `restart`.

## Security and safety

- Never log raw tokens, secrets, credentials, cookies, auth headers, private keys, or consent tokens.
- Token evidence may use only safe prefixes, hashes, lengths, or redacted values.
- Roles and actor context must come only from verified token/auth context such as `AuthContext`.
- Do not weaken authentication, authorization, role, actor, token, audit, or observer safety checks.
- Main HTTP/WS server and external `control-plane` are separate services; lifecycle operations must go through project scripts.
- Do not use destructive git commands unless explicitly requested and safe.

## Final response contract

Every completion response must include:

- what changed
- files changed
- verification commands and results
- skipped checks, if any
- residual risks or follow-up items
