# Final minor fix report — HD1 capability projections v2

Date: 2026-08-29

## Scope

- Updated the design specification status from the pre-implementation gate to
  the implemented, pinned-contract state. The normative requirements are
  unchanged.
- Added a DB-backed regression test for the compatibility invariant: a
  completed historical unversioned v1 module snapshot is read through the
  production repository without change, and the v2 module reconciler does not
  claim it for mutation.
- No production code changed: the new regression test characterizes the
  existing compatible behaviour.

## Test design

The fixture reproduces the exact pre-v2 module snapshot shape written by the
former reconciler (`{"steps": [...]}` with `safe_values` and no
`schema_version`). It persists a terminal `endpoint.module.recipe` link, reads
it via `EndpointOperationLinksRepo`, runs
`SqlAlchemyEndpointModuleOperationReconcileStore.claim_ready`, then reads it
again. The assertions protect both required behaviours: the historical value is
readable byte-for-value as JSON data, and the v2 worker leaves terminal history
outside its reconciliation set.

## Commands and results

| Command | Result |
| --- | --- |
| `python -m pytest server/tests/test_endpoint_operation_reconciler.py::test_module_reconcile_keeps_historical_unversioned_v1_snapshot_readable_and_unchanged -v --tb=short` | Blocked during pytest fixture setup before the test body: the Windows test DB SSH tunnel could not resolve `example.test`. |
| `python -m pytest server/tests/test_endpoint_operation_reconciler.py::test_module_reconcile_keeps_historical_unversioned_v1_snapshot_readable_and_unchanged --collect-only -q` | Passed: 1 test collected. |
| `python -m pytest server/tests/test_endpoint_module_operation_reconciler.py server/tests/test_diagnostic_layer.py -v --tb=short -m no_db` | Passed: 24 passed, 11 deselected. |
| `python scripts/verify_workspace.py` | Attempted twice; each invocation returned without output after approximately 30 seconds in this shell integration, so no passing result is claimed. |
| `git diff --check` | Passed; no whitespace errors. |

## Residual verification concern

The new DB-backed regression test needs the approved test database tunnel (or
the corresponding test DB environment variables) to resolve and execute. No
credentials or endpoint overrides were added or changed by this work.
