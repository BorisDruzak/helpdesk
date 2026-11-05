# Requester Chat Context Implementation Plan

> Native implementation with superpowers:executing-plans; independent final
> read-only review for safe requester projection. Preserve current checkout and
> unrelated local changes; no concurrent implementers.

**Goal:** An employee sees handling status, specialist, SLA, device and progress
beside a usable, automatically updating ticket conversation.
**Architecture:** Owner-gated safe detail handling projection; shared pure SLA
timer projection; existing requester polling and public-event visibility.
**Tech Stack:** Existing Python/aiohttp/SQLAlchemy2/PostgreSQL, React19.2.5,
TanStack Query5.99.2, current Tailwind/design system. No dependency/schema changes.
**Spec:** docs/superpowers/specs/2026-11-05-requester-chat-context-design.md.

## Work and verification

1. [x] RED tests for requester handling/SLA and safe device/assignee projection.
   Add `server/requester/ticket_handling.py`; extract pure timer projection into
   `server/tickets/timer_projection.py` and retain support wrapper/output contract.
   Wire only owner-verified `handle_web_requester_ticket_detail`; preserve existing
   policy exclusions and stranger404. Unit + focused disposable PostgreSQL cases.
2. [x] RED requester chat tests: visible status/assignee/SLA/device; public progress
   events, role classification and no duplicate/access-code message. Update
   requester types and focused chat/context/timeline components, retain resolution,
   composer/drafts, refresh and actions. Cover missing/paused/completed/late SLA.
3. [x] Browser desktop/mobile evidence on the built bundle and real authorized
   requester-owned ticket where available; no business mutations on user tickets.
   Check overflow, sticky composer, change refresh, errors and safe labels.
4. [x] Update requester contract/CODEMAP, own PLANS section, focused tests/build/
   workspace/diff checks; independent review, exact committed canonical staging
   release and private backup. Record accepted SHA and service/data preservation.

## Review focus

Foreign ticket/device; internal notes; changed ownership; malformed or missing
Endpoint projection; stalled/completed SLA; template-hidden fields; draft loss on
polling; duplicate system/chat events; inaccessible mobile panel and error state.

## Pre-release evidence

2026-11-05:29 pure backend,2 isolated PostgreSQL/API and27 frontend tests pass;
frontend build and workspace verification pass. Browser1366x900/390x844 built
fixtures verify automatic assignment refresh/draft retention, expandable mobile
context, zero page exceptions and no horizontal overflow.503 retains chat/draft;
404 hides cached content. The initial hidden-target TypeError and inverse
private-event flood were reproduced RED and covered by passing regressions.
Independent final review found no remaining code blocker; API/CODEMAP updated.
Frozen1ba7c8166e1d0317479a965dcf63b1b7d2accd3a deployed canonically to staging;
source nine-file hash, schema153, strict TLShealth200, three active services and
five business table seals verified. Live own-ticket requester page accepted,
console error/warning list empty. No business mutation. Acceptance:
docs/REQUESTER_CHAT_ACCEPTANCE_2026-11-05.md. Staging remains running; preview stops.
