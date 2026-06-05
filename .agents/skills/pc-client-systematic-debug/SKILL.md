---
name: pc-client-systematic-debug
description: Use for pc_client bugs, regressions, failing tests, exceptions, runtime errors, unexpected behavior, log triage, browser failures, GUI failures, flaky behavior, or production-like incidents.
---

# pc-client-systematic-debug

## When to use

Use for any debugging task.

Typical triggers: bug, regression, failing test, pytest failed, exception, traceback, does not work, unexpected behavior, logs show, browser error, GUI issue, flaky, production issue, or live debug.

## Inputs

- Bug report or failing command.
- Expected behavior and actual behavior.
- Logs, traceback, screenshot, route, symbol, or test name.
- Affected surface if known: `server`, `pc_agent`, `webapp`, `browser`, `GUI`, `deploy`, or `protocol`.

## Workflow

1. Capture the failure before patching:
   - exact command or user flow
   - expected behavior
   - actual behavior
   - error/log/traceback
   - environment if relevant
   - whether the issue is reproducible
2. Check workspace state:
   - `git status --short`
3. Run project task intake when available:
   - `python scripts/task_intake.py`
4. Read relevant docs when available:
   - `docs/CODEX_WORKFLOW.md`
   - `docs/QUICK_LOOKUP.md`
   - `docs/CONTEXT_INDEX.md`
   - `docs/ARCHITECTURE_BOUNDARIES.md`
   - `docs/LIVE_TESTING_DEBUG_RULES.md`
5. Build focused context:
   - `python scripts/build_context_pack.py --topic "<bug summary>"`
   - `python scripts/search_context_index.py "<error route symbol concept>"`
   - `python scripts/agent_find.py "<pattern>" --dir server`
   - `python scripts/agent_find.py "<pattern>" --dir pc_agent`
6. Identify likely root cause before editing:
   - failing component
   - immediate cause
   - deeper cause if visible
   - why the old behavior was wrong
   - why the proposed fix is minimal
7. Make the smallest correct fix.
8. Add or update regression coverage when realistic.
9. Verify in increasing scope: targeted check, affected-surface check, workspace sanity, and browser/GUI/remote check when applicable.

## Rules

- Do not patch first.
- Do not hide a failing check.
- Do not claim root cause without evidence.
- Do not broaden the fix beyond the failure unless required.
- Do not bypass project scripts when they exist.
- Do not weaken auth, actor, role, token, or safety checks to make a test pass.
- Do not leave debug logging that exposes secrets or raw tokens.
- Preserve UTF-8; mojibake is a defect.

## Verification

| Surface | Verification |
|---|---|
| Python logic | targeted `pytest` |
| Server route/API | targeted backend tests, smoke command, logs if relevant |
| `pc_agent` runtime | targeted agent test/smoke/log check |
| Webapp/browser | use `pc-client-browser-check` |
| GUI/live debug | follow `docs/LIVE_TESTING_DEBUG_RULES.md` |
| Release/deploy | use `pc-client-release-gate` |
| Docs drift | use `pc-client-docs-drift` |

## Final response requirements

Include observed failure, root cause, fix summary, files changed, tests/checks run, checks not run with reason, and residual risks.
