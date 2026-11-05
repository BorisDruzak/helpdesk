# Clipboard screenshots in ticket chat

Installed on isolated staging: `ff8db7ec972745fe0b0731a93380942b5eda157b`
(`feat(chat): attach pasted screenshots to reply drafts`), branch
`codex/ui-support-001`, 2026-11-05.

Requester `/app/requester/tickets/:id` and default support `/app/tickets/:id`
attach image files from a native paste event to the existing grouped draft queue.
Ctrl+V preserves existing text, ordinary native text/caret insertion and the text
part of mixed image/text clipboard data. There is no background clipboard read,
permission request, external HTML image fetch or automatic message send.
Capabilities, closed/history guards and public/private draft separation apply.
Both composers show a shortcut hint; removing files and explicit Send are unchanged.

Checks:

- Focused Vitest six-file suite: **37 passed** (`chat-file-draft`, upload queue,
  support conversation, requester panels/page/conversation). Five new paste tests
  cover multiple images, native text/default behavior, files fallback, HTML-only
  paste and denied uploads. Four initially failed before implementation.
- `PC_CLIENT_WEBAPP_E2E_PORT=14180 pnpm --dir webapp exec playwright test tests/chat-file-drop.spec.ts --output ../tmp/chat-paste-20261105/browser-final`:
  **16 passed**, including five new real clipboard write + keyboard Ctrl+V cases.
  Requester/support at1366 and390 widths preserve pasted text, append repeated
  screenshots and send one message with text plus two refs; internal screenshots
  stay in the private draft. No page/console/network errors in happy cases.
  The first clipboard fixture PNG failed decoding before paste; its corrected
  PNG is the final acceptance fixture. Existing drop/error/queue cases also pass.
- `pnpm --dir webapp run build`, `python scripts/verify_workspace.py`, scoped
  `git diff --check`: **passed**. Independent review: no findings.
- Canonical frozen-SHA installer after verified schema154 backup: **passed**.
  Seven changed non-PLANS hashes match. Schema154 unchanged; strict TLS health200
  for Helpdesk and Endpoint, three staging services active. Staging left running.
- Live retained admin's own synthetic T-000058: native clipboard image + Ctrl+V
  uploaded one `clipboard.png`, rendered a decoded thumbnail alongside preserved
  text, overflow0 and console errors0. Test draft then cleared via UI; no chat
  message/status command sent. One ticket-scoped test artifact remains. The
  user-owned browser tab/draft was not touched. Fixture port14180 stopped.

Files: shared `webapp/src/components/chat-file-draft.tsx` and its new test;
requester `tickets-panels.tsx`; support `simple-support-conversation.tsx`;
`webapp/tests/chat-file-drop.spec.ts`; `docs/SUPPORT_WORKSPACE.md`, CODEMAP and
the task section of PLANS. Evidence: `tmp/chat-paste-20261105/`, including
`browser-live.json`, `staging-clipboard-draft.png`, unit/browser/build/deploy logs
and verified backup/installed checks. No backend contract/schema/dependency or
Endpoint/native code changes in this commit. Production and unrelated local work
preserved. Full CI/backend DB suites not run for this frontend-only change.

Studio instruction/answer files are a separate follow-up under the same task;
this record does not claim that larger feature is deployed.
