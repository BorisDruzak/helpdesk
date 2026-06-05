---
name: pc-client-systematic-debug
description: Use for pc_client bugs, regressions, failing tests, unexpected behavior, live-debug issues, runtime errors, logs, Protocol V3 failures, browser failures, or GUI failures.
---

# pc-client-systematic-debug

## When to use

Use for any bug, failing test, unexpected behavior, live incident, runtime error, browser failure, GUI failure, Protocol V3 issue, deployment/runtime issue, or log-driven investigation.

## Inputs

- Exact scenario or failing command.
- Expected behavior.
- Actual behavior.
- Error, log, screenshot, trace, ticket id, operation id, or clean-run id when available.

## Workflow

1. Do not patch before establishing the observed failure and likely root cause.
2. Capture the failure:
   - command or UI flow
   - expected behavior
   - actual behavior
   - error/log/screenshot/trace when available
3. Run task intake:
   - `python scripts/task_intake.py`
4. Read relevant debug docs:
   - `docs/LIVE_TESTING_DEBUG_RULES.md`
   - `docs/QUICK_LOOKUP.md`
   - relevant CODEMAP files
5. Build focused context:
   - `python scripts/build_context_pack.py --topic "<bug summary>"`
   - `python scripts/search_context_index.py "<error route symbol concept>"`
   - `python scripts/agent_find.py "<pattern>" --dir server|pc_agent`
6. Form a root-cause hypothesis by layer.
7. Make the smallest fix.
8. Add or update regression coverage when realistic.
9. Verify using the smallest relevant check first, then broader checks if needed.

## Verification

Use the relevant surface:

- Python/unit logic: targeted `pytest`
- Browser/UI: real browser evidence
- Local GUI: `pywinauto==0.6.9` and `Application(backend="uia")`
- Runtime/deploy: project smoke/log scripts
- Workspace sanity: `python scripts/verify_workspace.py`

Do not claim a browser/UI/live bug is fixed from a single non-canonical signal.

## Final response requirements

Include:

- root cause
- fix summary
- files changed
- verification commands and results
- checks not run
- residual risks
