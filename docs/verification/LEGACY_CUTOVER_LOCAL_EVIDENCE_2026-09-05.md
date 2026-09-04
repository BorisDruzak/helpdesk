# Legacy Cutover — Local Evidence (2026-09-05)

This is a redacted local pre-release record. It is **not** production
acceptance and does not replace
[LEGACY_CUTOVER_PRODUCTION_ACCEPTANCE.md](LEGACY_CUTOVER_PRODUCTION_ACCEPTANCE.md).

## Exact revisions and contract lock

| Item | Value |
| --- | --- |
| Helpdesk checkout and remote branch | `82f9c899e124ea68fd518e36e8eb75ffc1913fdc` on `codex/helpdesk-process-model` |
| Endpoint Platform checkout | `22060e2bd3eae9fff874a64d01d80d18be9ff576` on `main` |
| Lock provider commit | `22060e2bd3eae9fff874a64d01d80d18be9ff576` |
| Locked canonical OpenAPI SHA-256 | `2982924427c731b83cfbd203e2fc86533c6e7b0fb4ec234cacd2d96f838fc04f` |

`python scripts/validate_endpoint_contract_lock.py --lock
integration/endpoint_contract.lock.json --provider-root <endpoint checkout>`
passed against the exact Endpoint checkout above. The acceptance test module
also collected successfully with `ENDPOINT_PLATFORM_REPO` set to that clean
checkout.

## Targeted local gates

The historical full suite was intentionally not run.

| Gate | Command / scope | Outcome |
| --- | --- | --- |
| Endpoint server/contracts/gateway | `python -m pytest tests/contracts tests/operations tests/gateway -q` | `491 passed, 5 skipped` |
| Endpoint contract artifacts | `python tools/contracts/generate_contract_artifacts.py --check` | PASS |
| Endpoint compile | `python -m compileall -q endpoint_contracts endpoint_server pc_agent` | PASS |
| Endpoint headless/package boundary | Selected runtime, gateway, Linux packaging and Windows tests from the cutover plan | `234 passed` |
| Helpdesk contract lock | `python -m pytest server/tests/test_endpoint_contract_lock.py -q` | `9 passed` |
| Helpdesk no-DB cutover boundary | 16 present targeted files with `-m no_db` | `149 passed, 1 skipped, 8 deselected` |
| Helpdesk workspace verifier | `python scripts/verify_workspace.py --workspace <Helpdesk worktree>` | PASS |
| Helpdesk compile | `python -m compileall -q server scripts` | PASS |
| Helpdesk webapp production build | `pnpm --dir webapp run build` after `pnpm --dir webapp install --frozen-lockfile` | PASS |

The plan names two Helpdesk module-specific test files that are absent from
the final tree (`test_endpoint_modules_http_adapter.py` and
`test_endpoint_module_operation_service.py`); they were not silently
substituted. The no-DB command therefore records its precise present-file
scope above.

## Static deletion checks

The Endpoint static scan found only exclusion lists and proof-of-absence tests;
the Helpdesk scan found only historical migrations, synthetic audit/deployment
fixtures, and negative boundary guards. No match was an active production
import, route, or runtime authority. The focused Helpdesk boundary tests above
verify the same conclusion.

## Windows MSI candidate

| Item | Value |
| --- | --- |
| Version | `3.2.37` |
| MSI SHA-256 | `5c611824d64236be6abb60a4c31076621ed824298211edc9e446390a1b6006f4` |
| Binding manifest files | 2,544 |
| Forbidden GUI/Ticket API/old-WS payload paths | 0 |
| Runtime-stage source revision from release sidecar | `58cacec27008c2100ba62c4bee296d0acc62d281` |

The MSI was built locally from the clean Endpoint checkout using the reviewed
schema-5 retained runtime stage and its evidence. Its release sidecar records
the runtime-stage source revision above; this record does not assert that a
real Windows canary has accepted the package.

`git diff --name-only 58cace… 22060e…` over the headless runtime, launcher,
Windows payload specs and packaging inputs found no runtime-payload changes;
the only changed package-side paths were `build-msi.ps1` and the reviewed
`initial-runtime-3.2.37.json` manifest. This is why the retained runtime stage
is valid for the final checkout, subject to real-canary verification.

## Not yet proven

- No ALT RPM was built: the local host has no Linux builder (Git Bash is not a
  Linux build environment and no WSL distribution is installed).
- No Helpdesk DB-backed gate was run after the final lock update: the
  parent-owned staging test tunnel lacks current runner SSH authentication.
- No ALT or Windows real-agent canary, immutable tag/main creation, production
  Endpoint release, Helpdesk release, production smoke, or production E2E was
  performed.
- No destructive legacy schema drop was performed.
