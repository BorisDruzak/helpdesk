# Optional requester screenshots — 2026-11-06

The staging screenshot report is a scalar-validation defect, not a failed upload:
the Electronic Budget session has images attached, while a separate required
`evidence_note` textarea is empty. All 32 enabled published maps have this stage.
No matching screenshot requirement exists in the legacy form-field registry.

## Change

- New publications remove the exact reviewed `q_evidence` stage and redirect its
  incoming edges to `submit`, preserving conditions, processing, SLA, entrances
  and other coordinates. Screenshots remain optional attachments on text fields.
- Old immutable versions remain pinned. The runtime uses a copied effective
  definition with optional screenshot-comment textareas, preserving their IDs,
  answers, history and files. Final form derivation uses the same definition.
  Other required questions, authentication, lifecycle and attachment controls stay
  authoritative. Similar stages with changed semantics fail closed.
- `scripts/helpdesk_optional_screenshot_stage.py` is an imported staging-only admin
  callable, not an automatic migration. Fresh complete input fingerprint, sorted
  canonical locks and untouched draft/base checks protect user changes. The whole
  batch uses normal draft CAS, preview, confirmation token and publication/audit
  services in one transaction; repeat application is a no-op.

The first strict review caught editor coordinates being mistaken for semantic
references. The bounded fix now ignores only the reviewed stage's coordinate for
matching, retains it in pinned sessions, and removes it in new publications. All
48 historical definitions contain this coordinate. Semantic references still block
the exception. GitNexus MCP is unavailable; narrow source/caller checks were used.

## Verification and deployment

`python -m pytest server/tests/test_request_scenario_optional_evidence.py
scripts/test_helpdesk_optional_screenshot_stage.py
server/tests/test_request_scenario_runtime.py
server/tests/test_request_scenario_submission.py
server/tests/test_request_scenario_processing.py
server/tests/test_request_scenario_v3_processing.py
server/tests/test_request_scenario_assets.py -q`: 147 passed. New regressions
were observed red before implementation. Cases cover exact matching, unrelated
required fields, final validation and 0/1/2 files retained through Back/reload and
claimed once, admin/database/fingerprint/draft guards and late batch rollback.

`pnpm --dir webapp test:e2e tests/requester-optional-screenshots.spec.ts
--output=../tmp/optional-screenshots-20261106/browser-final`: six passed at
1366x768, 1920x1080 and 390x844. Actual Python runtime projections drive fixtures:
empty legacy answers continue to submission, existing files survive resume, and
new flows go directly from required details to submission. No ticket writes,
overflow or browser errors. The fixture's initial navigation/empty-value
expectations were corrected before the passing run. Frontend production build,
workspace verification and diff checks pass. Existing chunk-size and Authlib
deprecation warnings remain.

The wider scenario no-DB selection reported 314 passed and ten failures at the
unchanged publication readiness fixture boundary (mock rows omit `id`). It is not
a clean full-suite result. Focused changed-surface checks pass; real PostgreSQL
publication and rollback are required below. Full CI was not requested.

Fresh read-only staging matching accepts all 32 active and 47 of 48 historical
screenshot definitions. The remaining retired browser-v1 uses different radio and
conditional questions and has no sessions; it remains deliberately protected.
No immutable definition or current session was changed by this diagnostic.

Staging installation/publication receipts follow below. Evidence is private under
`tmp/optional-screenshots-20261106`. Production is outside this task.
