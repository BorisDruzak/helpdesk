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

## Staging acceptance

Installed exact immutable source `9c247da1f5ae65c5ad131eccc305e3891852486e`:
`fix(requester): make screenshot evidence optional`, private branch
`codex/requester-optional-screenshots`, based on accepted reopen/SLA/typing/catalog
changes (`213292bfb443e17bb07d25f4ef54c2ffbacf03a7`). The canonical
`scripts/deploy_helpdesk_release.py` rebuilt frozen-lock frontend assets and
installed only on `osn-admin@192.168.101.118`. Seven source/test file hashes match
Git objects. Schema remains 155. Helpdesk and Endpoint health are 200 with CA and
hostname verification; all three staging services remain active for user use.

Source commit files: runtime compatibility module, runtime/submission integration,
backend regression file, bounded publication helper and its tests, browser fixture,
CODEMAP, guided-scenario documentation, this report and the scoped PLANS section.
Shared HEAD/index and unrelated workspace changes were preserved.

Verified backup before code installation: SHA256
`b1626671300d8fc47c14c167d274c96c71468b40260c38e1c73d224f8542607a`.
Fresh backup before publication: SHA256
`9a2a4028f20ebe41d28bdf08f291075e958d7f969dc7b8efef6b0130b75435fd`.
A deliberate failure after the second real PostgreSQL publication/flush rolled
back the complete batch, including tokens and audits; full input/state seals
matched before/after.

The 32-map canonical batch then committed 32 new immutable versions. All 33 active
maps now have no screenshot stage; the map already without one stayed unchanged.
All published definitions equal the exact reviewed transform, including preserved
conditions, processing, SLA and entrances. Old 77 immutable versions retain every
column except canonical published-to-retired state transitions; version count is
109. Unrelated scenario/draft rows are unchanged.

The SSH wait timed out after 180 seconds while canonical validation still consumed
CPU remotely. No duplicate publication was started and the running operation was
left intact. Its terminal committed state was independently confirmed after its
transaction ended: the verifier checked the SHA256-verified pre-publication dump
using read-only `pg_restore --data-only` extraction and compared sorted COPY rows
to current staging data. No restore or database mutation was used for this proof.
All 56 sessions, seven pre-ticket assets, 77 tickets, 18491 ticket events, two reopen
records, five feedback records, six artifacts and 58 create-ledger rows match the
backup exactly. Categories, services/offerings, templates/forms, queues, SLA and
configuration rows also match. Fresh plan/reapply reports zero changes and zero
new audits; its complete before/after seals match.

After retirement of pinned versions, the three real sessions at `q_evidence`
(0/1/2 attachments, including Electronic Budget) were loaded through the actual
owner-scoped repository, advanced with empty screenshot answers, and prepared for
submission. The canonical requester ticket preview returned HTTP200/`ok:true` for
all three. All transactional test changes were rolled back and row seals matched;
no test ticket was created. Existing asset claim-once has focused regression
coverage; a committed end-to-end ticket send was intentionally not performed on
the user's draft.

Browser evidence is the six passing local cases driven by actual Python runtime
projections. A later review tightened the fixture to explicitly count/reject guided
`/sessions/{id}/submit` writes, then all six cases passed again. The actual staging
browser account `admin` has an incomplete profile; its normal-form gate remains
visible and only profile/device help is offered. No profile was changed, no user
draft/session was created, and no browser warning/error was captured. Temporary
verification tabs were closed. Live ordinary-form browser acceptance under a
complete requester profile remains outside this account's capability; real
owner-scoped backend preview and fixture results are stated separately above.

Receipts: `publication-acceptance.json`, `publication-before-plan.json`,
`publish-rollback.json`, `publish-apply.json` (no-op repeat), `publish-sessions.json`,
`installed.json` and `browser-final/`, under
`tmp/optional-screenshots-20261106`. Production is unchanged.
