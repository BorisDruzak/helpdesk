# Requester reopen reasons in the support conversation — 2026-11-06

User report confirmed on staging T-000077: two requester returns are recorded in
`ticket_reopen_events` and `ticket_reopened` facts, with `public_comment` also in
status history, but no public chat message. Support's ordinary conversation reads
chat messages, so the reason/comment is absent from that surface.

## Change

- `quality/reopen_message.py` owns Russian reason labels and stable UUID5 message
  identity per ticket/reopen. It includes only public reason/comment and canonical
  requester display-name enrichment.
- `quality/reopen_service.py` appends one public requester message atomically with
  the existing workflow/reopen/quality facts. Operator quality notes do not become
  public. Missing message persistence fails the transaction.
- Requester, legacy quality and public reopen routes publish the captured normal
  chat event only after commit through the existing ticket WebSocket helper. HTTP
  responses, actor/scope gates and the canonical workflow remain unchanged.
  Requester failures explicitly rollback instead of allowing the context manager
  to auto-commit caught errors; conflicts return 409.
- `helpdesk_recover_t77_reopen_messages.py` recovers only the two diagnosed facts,
  requiring admin/staging/exact-ticket/source-owner-role-reason-comment proof and
  a fresh full-input fingerprint under lock. It appends missing chat rows at their
  original fact times plus one internal audit; no old row, status, rating or SLA
  is rewritten. It is an imported protected maintenance callable, not a startup
  migration or general bulk command.

## Verification

- New service regressions failed before the fix; focused backend/maintenance/
  quality/concurrency/atomicity checks now pass: 50 tests. They cover both message
  serializers, postcommit delivery, rollback/conflict/access denial, legacy/public
  commit failure, stable IDs, private operator notes and recovery source guards.
- Browser fixture: 3 passed at 1366x768, 1920x1080 and 390x844. The existing
  confirmation/reject flow uses the actual Python payload and requester serializer,
  checks reason/comment visible once after return, no overflow or console errors.
  Existing requester display whitespace normalization remains unchanged.
- Workspace verification and diff check pass. Independent review's source-author
  guard finding was fixed; CODEMAP and QUALITY_LOOP document the new ownership and
  transaction. GitNexus MCP is unavailable; narrow source/callers were checked.
  SQLAlchemy 2.0 transaction semantics were consulted through Context7.

## Staging acceptance

Installed immutable release `99f7428692d9627160eac77e2316c42397716462` using
`scripts/deploy_helpdesk_release.py` on the approved isolated staging host.
Commit: `fix(requester): publish reopen reasons in ticket conversations`.
The eight changed source/test files match the frozen Git objects. Schema remains
155; Helpdesk and Endpoint HTTPS health checks return 200 with CA and hostname
verification, and all three staging services remain active for user acceptance.

Verified backup before code deployment: SHA256
`ef34d26df90ba27f5be80da7f624097d9273d027fb86d75bbf7d08f4888ac116`.
Fresh verified backup before data recovery: SHA256
`eb4f4c0fc05412e98329c671fc61ae061b8f1901ac522106eae16ab5acbea46a`.
The recovery helper was first exercised against real PostgreSQL with an injected
missing-audit failure: both flushed message inserts rolled back and all seals
remained unchanged. Apply then appended two messages and one internal audit.
All T77 columns, both reopen records, five feedback records, 27 existing T77
events and the other 76 tickets were unchanged; a repeat apply was a no-op.
Counts after recovery: 77 tickets, 18489 events, six artifacts, 160 users and
44 registry people.

The actual support browser conversation displays both restored reasons/comments,
including “Непонятная инструкция”; no warning/error console entries were captured.
Evidence: `tmp/reopen-message-fix-20261106/live-t77-comments.jpg`,
`recover-rollback.json`, `recover-apply.json` and `installed.json`.
Only the temporary verification tab was closed; the user's tab was preserved.
Full CI and production are outside this targeted staging scope.

Source is frozen with a private index on top of
`d4720f76f5d5154d72adcd745b2a4370c33cbed2` to preserve accepted SLA/typing/catalog
changes and unrelated shared workspace/index edits. Private evidence directory:
`tmp/reopen-message-fix-20261106`. Initial diagnostics were sanitized to exclude
ordinary chat text and access messages; no environment/auth values are retained.
