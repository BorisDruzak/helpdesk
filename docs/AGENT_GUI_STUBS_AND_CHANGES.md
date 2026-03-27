# Maria Agent GUI: changes and stubs

Date: 2026-03-26
Scope: local desktop agent GUI (`pc_agent/ui_gui/*`), no server changes.

## Implemented UI changes

1. Ticket list filters:
- Added open/closed filters in the ticket list header.
- Default state: open tickets are shown, closed tickets are hidden.

2. Mandatory requester profile at agent level:
- Creating a ticket is blocked when no active profile is selected.
- User gets a warning and profile manager opens.
- Added top status near app header with current profile or warning.

3. Chat message sides:
- User messages are rendered on the left.
- Support messages are rendered on the right.

4. Softer blue background:
- Chat timeline background switched to softer blue shades.

5. Right-click message actions:
- Added custom context menu in timeline:
  - Copy message text
  - Reply (stub)
  - Pin message
- Reply is implemented as a stub:
  - Stores selected text as local reply target.
  - Shows a "reply stub" banner above input.
  - On send, attaches metadata field:
    - `agent_stub_reply_to_message`
    - includes source, text preview, local timestamp.

6. Auth code + web ticket link pinned on top:
- Added top info block in chat view with:
  - public access code
  - public access URL
- Displayed as a pinned-style block above timeline.

7. Close confirmation as chat-like message with buttons:
- Removed modal popup confirmation for resolved tickets.
- Added in-chat style confirmation block with Russian buttons:
  - `Подтвердить`
  - `Отклонить`

8. Ticket status moved to top and used for background adaptation:
- Status badge moved from left panel to top of chat area.
- Chat screen background now adapts by ticket status color.

9. Removed "Подтвердить и закрыть" button:
- Deleted the separate close button from left side panel.

10. Pin message feature:
- Added pin action in context menu.
- Added pinned messages section at top.
- Shows latest pinned messages for current ticket.

11. Ticket description visibility:
- Left-side ticket metadata area moved into scrollable view to avoid clipping.
- Long descriptions no longer overflow fixed panel height.

12. Agent naming:
- App window title and header renamed to `Maria Agent`.

## Additional UI refinement changes (2026-03-26, iteration 2)

1. Softer status background for eyes:
- For `resolved` status, chat background now uses a darker transparent green overlay instead of bright mint.
- `closed` and default statuses also use low-alpha overlays to keep text readable.

2. Pinned messages visibility:
- Pinned block is hidden when there are no pinned messages.
- Block appears only after at least one message is pinned.

3. Pinned messages remove action:
- Added `✕` button in pinned block to clear pinned messages for current ticket.

4. Ticket metadata panel without scrollbar:
- Removed left-panel metadata scroll area.
- Metadata area now expands in the panel and stays directly visible.

5. Chat scrollbar behavior:
- Vertical scrollbar in timeline is visually hidden by default.
- Rounded scrollbar appears on hover/interaction in the scrollbar area.

6. Copyable ticket metadata fields:
- Ticket metadata text supports direct selection/copy with mouse/keyboard.

7. Click-to-copy ticket number:
- Ticket number in header is clickable.
- On click, ticket code is copied to clipboard and a confirmation message is shown.

## Messenger-style refactor (2026-03-26, iteration 3)

1. Timeline renderer rewrite:
- Replaced HTML-in-`QTextEdit` timeline rendering with widget-based message bubbles inside `QScrollArea`.
- Each message/event is now a separate Qt widget instead of one rich-text document.

2. Bubble menu only on messages:
- Removed default document context menu behavior.
- Custom context menu is now available only on message bubbles.
- Empty chat area no longer opens message actions.

3. Messenger bubble behavior:
- Left/right aligned bubbles are real widgets with constrained max width.
- Qt size policy was adjusted to avoid full-row stretching that caused the old "flat bar" bug.

4. Attachment UX:
- File button replaced with paperclip attach menu.
- Added attach options:
  - photo
  - document
  - any file
- Attachments inside messages render as messenger-like chips inside the bubble.

5. Convenience and interaction:
- Bubble menu keeps only custom actions:
  - copy text
  - reply (stub)
  - pin message
- Default `Copy` / `Select All` entries from text editor context menu are no longer used.

## UX and visual polish (2026-03-26, iteration 4)

1. Auto-scroll fix:
- Timeline scroll restore was changed to multi-step deferred restore.
- Sending text or attachments now explicitly forces timeline back to bottom after refresh.
- This fixes the bug where the chat jumped to the top after sending.

2. User-friendly system messages:
- Internal event text formatting was rewritten into human-readable Russian phrases.
- Tool/module actions now appear as understandable status messages for end users instead of raw technical payload keys.

3. Telegram-like theme refresh:
- Updated the whole agent UI palette to softer Telegram-style whites and blues.
- Primary action color moved closer to Telegram blue.
- Surfaces, list rows, pinned/info blocks, and top window controls were restyled for a cleaner official look.

4. Agent versioning:
- Agent version is now explicitly bumped in `pc_agent/version.py`.
- GUI window title shows the current version, e.g. `Maria Agent v3.0.2`.
- The same `AGENT_VERSION` is already used in the WebSocket handshake, so the server sees the updated agent version after reconnect/restart.

## Implemented stubs (require server support later)

### Stub: reply to a specific message

Current agent-side behavior:
- User selects message text and clicks `Reply (stub)`.
- UI stores reply target locally and shows reply banner.
- When sending message, GUI includes metadata:
  - key: `agent_stub_reply_to_message`
  - fields: `source`, `target_preview`, `target_ts`.

What server should implement later:
- Accept structured reply target (`parent_message_id` preferred).
- Persist relation in message model.
- Return relation in ticket message payload.
- Render thread/reply reference in agent + admin UI.

Suggested contract direction:
- Request payload for message send:
  - `metadata.reply_to.parent_message_id` (canonical)
- Response payload for message:
  - `reply_to.parent_message_id`
  - optional cached preview for UI convenience.

### Stub limitations (current)
- No real message ID binding from selected bubble yet (text selection only).
- No backend validation/lookup of reply target.
- No threaded rendering from server history yet.

