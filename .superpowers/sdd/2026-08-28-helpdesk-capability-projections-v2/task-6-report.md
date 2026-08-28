# Task 6 — HD1 provider-count remediation

## TDD evidence

- Red: `python -m pytest server/tests/test_endpoint_modules_port_contracts.py server/tests/test_endpoint_modules_http_adapter.py server/tests/test_endpoint_module_operation_reconciler.py -q --tb=short` — 9 failures: the typed projection and wire rejected `expected_step_count`, and the public mutable projector registry remained.
- Green: the same command — `64 passed in 0.78s`.
- Red: `python -m pytest server/tests/test_endpoint_modules_port_contracts.py::test_succeeded_module_operation_with_results_requires_provider_step_count -q --tb=short` — failed because a succeeded result projection without the provider count was accepted.
- Green: the same command — `1 passed in 0.16s`.
- Final focused suite: `python -m pytest server/tests/test_endpoint_contract_lock.py server/tests/test_endpoint_modules_http_adapter.py server/tests/test_endpoint_modules_port_contracts.py server/tests/test_endpoint_module_bff.py server/tests/test_endpoint_module_operation_reconciler.py -q --tb=short` — `83 passed in 8.52s`.
- Additional checks: `python scripts/verify_workspace.py --workspace .`, `python -m compileall -q server scripts`, and `git diff --check` passed.

## Change record

- Updated the provider lock to Endpoint `64f400741f023c272e38d7bfcf39430d05e3de2e` and OpenAPI SHA-256 `5d27a1ebeb7abe670a4f7160a0075ad893f88cbbc94b52b2458107f13be6c735`.
- Operation detail now requires the provider-authoritative count; succeeded projections accept only the exact `0..expected_step_count-1` child sequence. Queued and failed behavior remains unchanged.
- The projector registry is private, immutable, and regression-tested for its exact six capabilities.
- Changed: provider lock, typed domain/wire/HTTP adapter/projector, focused tests, `PLANS.md`, and `server/docs/CODEMAP.md`.
- Commit: `fix(modules): validate complete endpoint operation details` (this task commit).

## Concern

This is local typed-HTTP coverage only; provider, Gateway WSS, real-agent, staging-canary, and production acceptance remain separate gates.

## Review fix round 1

- Corrected the OpenAPI SHA-256 to the raw Git blob digest `800a09225daea050cd1cc34fdc224354d8b6769096daab115923c049b1ddd3c4`; the prior digest was checkout-line-ending-sensitive.
- Verified the corrected lock against `C:\Users\admin-2\.codex\worktrees\98c9\endpoint` at `64f400741f023c272e38d7bfcf39430d05e3de2e` with `ENDPOINT_PLATFORM_REPO` set: `python scripts/validate_endpoint_contract_lock.py --lock integration/endpoint_contract.lock.json --provider-root $env:ENDPOINT_PLATFORM_REPO` passed.
- Focused suite: `python -m pytest server/tests/test_endpoint_contract_lock.py server/tests/test_endpoint_contract_acceptance_workflow.py -q --tb=short` — `10 passed in 7.53s`; acceptance collection against the same provider found 2 tests.
