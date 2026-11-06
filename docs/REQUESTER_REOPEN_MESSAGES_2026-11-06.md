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

Canonical exact-SHA staging installation, verified backup, real PostgreSQL
rollback/idempotence, recovery receipts and support-browser evidence follow before
acceptance. Full CI and production are outside this targeted staging scope.

Source is frozen with a private index on top of
`d4720f76f5d5154d72adcd745b2a4370c33cbed2` to preserve accepted SLA/typing/catalog
changes and unrelated shared workspace/index edits. Private evidence directory:
`tmp/reopen-message-fix-20261106`. Initial diagnostics were sanitized to exclude
ordinary chat text and access messages; no environment/auth values are retained.
