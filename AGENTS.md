# AGENTS.md - Codex Operating Contract

Keep this root contract short. Put detailed procedures in `.agents/skills/*/SKILL.md` and subsystem documentation.

## Workspace and boundaries

- Work only in `C:\Users\admin-2\CodexProjects\pc_client`.
- Treat `\\192.168.100.17\NTFS_Share\pc_client` as a mirror and `/var/chat_bot/pc_client` as deployed state; do not patch either manually.
- Code and documentation share the local working copy as their canon.
- Before non-trivial work, bootstrap UTF-8 with `.\scripts\bootstrap_shell_utf8.ps1` and inspect `git status --short`.
- Read the nearest relevant `AGENTS.md` and only the documentation for the subsystem being changed.

## GitNexus MCP

GitNexus is the canonical architectural index for this project.

When investigating, planning, debugging, refactoring, or estimating impact:

1. Use GitNexus MCP before broad manual source exploration.
2. Start with query/context/impact/trace as appropriate.
3. For work involving both helpdesk and endpoint_platform, use the
   helpdesk-platform GitNexus group.
4. Check group_status before treating the group registry as stale.
5. Do not run group_sync manually. The central GitNexus server updates
   repository indexes and the Contract Registry automatically.
6. Treat GitNexus as the indexed Git baseline, not as the source of truth
   for uncommitted local changes. Always account for the current local diff.
7. A negative no_path / no ContractLink result is not proof that no
   dependency exists. Verify dynamic Python relationships against source
   and tests when relevant.
8. Do not create manifest links merely to make a cross-repo relation appear.
9. Do not commit or push code only to refresh GitNexus.

## Working rules

- Make the smallest correct change; preserve unrelated user work and use project scripts where available.
- Do not add dependencies without need and permission.
- Keep routes, contracts, public behavior, startup or deployment flows, and CODEMAP documentation in sync when they change.
- Preserve UTF-8 text; mojibake is a defect.
- Protocol V3 contracts and invariants are defined in `pc_agent/docs/PROTOCOL_V3.md` and `server/docs/PROTOCOL_V3.md`; do not weaken them.

## Verification and release

- Before completion, run `python scripts/verify_workspace.py` when available and focused checks for the changed surface.
- Use the project browser workflow for browser-visible work and the applicable project skills for debugging, reviews, releases, and docs drift.
- Use project release/deploy/runtime scripts only; do not manually patch deployed files.
- After remote validation, stop services unless explicitly asked to leave them running.
- Report changed files, checks run or skipped, and residual risks.

## Security

- Never expose raw tokens, credentials, cookies, auth headers, private keys, or consent tokens; use redacted evidence only.
- Do not weaken authentication, authorization, roles, audit, observer, or lifecycle safety controls.
- Do not use destructive Git commands unless explicitly requested and safe.
