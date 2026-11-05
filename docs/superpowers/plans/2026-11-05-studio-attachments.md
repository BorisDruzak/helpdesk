# Studio instruction and answer attachments

User-confirmed behavior: allow screenshots and documents/files both in author
instructions/help and in employee answers to text/textarea questions. The chat
Ctrl+V task is separately committed/deployed as ff8db7ec. This plan covers the
larger Studio addition and its acceptance.

Actors and placement:

- Studio author, existing map workbench: attach/remove files alongside instruction
  text and question help. Images use in-page preview. Save/reload/publication pin
  materials with the scenario definition/version.
- Requester, existing scenario wizard: attach/remove supplemental files alongside
  text answers, preserving the typed answer during uploads. Files persist on
  session reload; back/branch changes follow retained field visibility. Required
  text and policy/condition evaluation keep scalar answer semantics.
- Support: created ticket receives retained answer files in the initial message
  and per-field context, using canonical ticket artifact access.

Implementation decisions:

1. Add a scoped Studio asset table, migration after154. Existing Artifact requires
   ticket/device; do not weaken that check or create placeholder tickets. Immutable
   author blobs belong to the scenario/draft; employee blobs belong to an owned,
   active, available pinned session/current field. Bound references to10 per field
   or instruction and retain the existing per-file200MiB limit.
2. Extend ScenarioField with help_attachments and InstructionContent with
   attachments. Canonical metadata: asset_id,name,mime_type,size_bytes,url.
   Validate published references and read availability server-side. Scalar Answer
   and ScenarioAnswerRequest stay unchanged; supplementary associations are rows.
3. Upload/remove through authenticated commands below existing admin/requester
   route prefixes. Requester commands carry current block/revision and draft
   answers for conditional visibility. Query associations into field/review
   answer_attachments. Upload/remove does not advance the wizard or create tickets.
4. At explicit final submit revalidate retained visible route, create canonical
   ticket artifacts and publish attachment refs in the same transaction, preserving
   repeated-submit idempotency. Discarded branches/foreign sessions never transfer.
5. Safe download checks draft permissions or visible published/pinned scenario
   access, or owned active session. No external URL embedding; inline raster
   previews only. Other formats use explicit download/nosniff. Cleanup cannot remove
   version/ticket referenced files or uncommitted-unknown blobs.

Ownership: backend worker owns server/model/migration/API/tests/exported schema;
frontend worker owns scenario author/requester UI/shared asset display/tests.
Parent owns integration, docs, browser checks, isolated staging DB verification,
review and canonical exact-SHA rollout. Preserve unrelated PLANS and worktree edits.

Acceptance: focused contract/storage/session/submission tests, owner/foreign ID,
expiry/revocation/current-block/revision checks; saved/published author material;
requester image+document, removal/reload/back/branch filtering and one explicit
ticket creation with field-linked artifacts. Browser desktop/mobile, no console
or failed network calls, scalar text conditions unaffected. Verified schema154
backup before deployment; test migration155 on isolated test DB first, then
canonical release/migration, exact hashes, strict TLS and live synthetic proof.
Leave staging running; production/Endpoint unchanged. No full CI unless needed
by the release procedure or explicitly requested.
