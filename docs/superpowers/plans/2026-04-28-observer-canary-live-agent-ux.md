# Observer Canary, Live Agent Checks And UX Follow-up

Status: in progress.

## Scope

Execute the approved follow-up tracks:

- observer coverage canary for live source rows;
- live agent telemetry/update registry checks for Windows and Linux targets;
- UX polish for `/app/admin/observer` trace detail evidence.

## Implementation

- Extend `scripts/run_observer_canary_suite.py` with source-coverage probes for `module_reconcile`, `playbook_run`, `web_auth` and `observer_runtime`.
- Add canary JSON + Markdown reporting with required root-kind coverage summary.
- Check the stable agent build registry for the current local `pc_agent.version.AGENT_VERSION` on `windows_amd64` and `linux_alt_x86_64`.
- Add observer evidence helpers and render trace source counters plus diagnostics bundle counters in the observer trace detail panel.

## Verification

- `python -m pytest scripts/test_run_observer_canary_suite.py -q`
- `pnpm --dir webapp run test -- observer`
- `pnpm --dir webapp run build`
- `python scripts/verify_workspace.py`
- deploy/release to the Linux stand, start server, run smoke, then browser-check `http://192.168.100.17:8666/app/admin/observer`.
- run the live observer canary suite and inspect the generated reports.

## Live Safety

The canary script starts an isolated local launcher instance for Windows agent behavior. It verifies Linux/Windows build availability through the server build registry; it does not force-update production devices unless an explicit canary device is supplied in a future step.
