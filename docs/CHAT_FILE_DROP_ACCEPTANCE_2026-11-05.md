# Chat file drops and grouped replies

Date: 2026-11-05. Branch: `codex/ui-support-001`.
Installed: `f69b5632dddbd9adb7d6693b15bacacbc5cb2ae4` —
`feat(chat): add file drops and grouped reply attachments`.

Requester chat and default support Dialog/Internal notes accept local screenshots
and files dropped over the conversation. Automatic upload adds them to one reply
draft. The user can type while uploading, inspect image previews, remove individual
attachments and send text plus all remaining files as one message. Sending stays
explicit; Ctrl+Enter and file-only messages remain supported. The picker accepts
multiple files. Sent images reuse the existing in-page preview.

Shared `chat-file-draft` UI and `use-chat-uploads` queue retain successful files
after partial failure, show the failed filename and queue repeated drops. Send
waits for the uploads to finish. Ticket/audience/permission changes and unmount
discard late callbacks and stop queued work. Public/private drafts stay separate.
Read-only/history views reject uploads. Local file drops prevent browser
navigation; URL/HTML drops do not navigate or fetch external images. Folders are
skipped with an explanation. Ordinary text dragging keeps its editing behavior.
Existing authenticated upload/message endpoints, ownership, work/assignment,
capabilities, artifact scope and internal-note permissions remain authoritative.
No backend, schema, dependency or public API change.

Verification performed:

- `pnpm --dir webapp exec vitest run src/components/use-chat-uploads.test.tsx src/pages/tickets/components/simple-support-conversation.test.tsx src/pages/requester/tickets-panels.test.tsx src/pages/requester/ticket-chat-page.test.tsx src/pages/requester/ticket-conversation.test.tsx`: **32 passed** in five files.
- `pnpm --dir webapp exec playwright test tests/chat-file-drop.spec.ts --output ../tmp/chat-drop-20261105/browser-green` with `PC_CLIENT_WEBAPP_E2E_PORT=14179`: **11 passed**. Both actors at 1366/1920/390 widths; drop overlay, multiple files, picker addition/removal, one message with text + two refs, image/file in the same bubble, visible Send and no horizontal overflow. Partial failures, repeated drops during upload, premature-send blocking, Ctrl+Enter and separate private/public drafts also pass. Six happy-path responsive cases report no page/console/network errors; expected upload failures are injected only in the two failure cases.
- `pnpm --dir webapp run build`, `python scripts/verify_workspace.py`, scoped
  `git diff --check`: **passed**. Independent read-only review: no remaining blockers.
- Regression checks first reproduced missing drop/group UI and URL/folder guards;
  failed intermediate runs are not acceptance evidence. No source changes followed
  the final green test/build run, apart from documentation.

Deployment used the canonical frozen committed-release installer on isolated
staging `192.168.101.118`, after a verified schema 154 backup of previous release
`cf51046d5f864f11fa4ea1dea40164acf2ce0a0b`. All 14 changed non-PLANS file hashes
matched the installed release. Schema remains154. Strict TLS health returned 200
for Helpdesk and Endpoint; Helpdesk, Endpoint and its worker were active after
acceptance. Staging remains running as explicitly requested. Rollback uses the
previous committed release, without a schema rollback.

Live acceptance used retained `admin`'s own synthetic T-000058 in requester
workspace. The native multi-file picker uploaded a generated benign PNG and TXT
into a two-file group alongside test text. One explicit Send produced one bubble
containing the text and both attachments. Reload preserved the message, thumbnail
decoded, horizontal overflow was 0 and browser console errors were 0. Database
counts changed by exactly one event and two artifacts; ticket count 75 and status
counts remained unchanged. Real user T-000075 was not modified. Live validation
used the picker through the same shared upload queue; drag behavior and ordinary
requester/support roles were checked by the 11 fixture scenarios above. No
impersonation, assignment, status or identity change was performed.

Production, Endpoint and native agent code were not changed. Full CI and backend
DB suites were not run for this frontend-only change; no push or production
deployment was performed. Existing server upload limits continue to apply.

Private evidence: `tmp/chat-drop-20261105/` contains unit/build/browser/deploy logs,
responsive draft/message screenshots, `browser-live.json`, `staging-draft.png`,
`staging-grouped-message.png`, installed hash/health checks and verified backup
metadata. Fixture port 14179 is closed after tests. Unrelated local changes remain unstaged.

Feature file manifest:

```text
PLANS.md
docs/SUPPORT_WORKSPACE.md
server/docs/CODEMAP.md
webapp/src/components/chat-file-draft.css
webapp/src/components/chat-file-draft.tsx
webapp/src/components/use-chat-uploads.test.tsx
webapp/src/components/use-chat-uploads.ts
webapp/src/pages/requester/ticket-chat-page.tsx
webapp/src/pages/requester/tickets-panels.test.tsx
webapp/src/pages/requester/tickets-panels.tsx
webapp/src/pages/requester/use-ticket-chat.ts
webapp/src/pages/tickets/components/simple-support-conversation.test.tsx
webapp/src/pages/tickets/components/simple-support-conversation.tsx
webapp/src/pages/tickets/list-page.tsx
webapp/tests/chat-file-drop.spec.ts
```
