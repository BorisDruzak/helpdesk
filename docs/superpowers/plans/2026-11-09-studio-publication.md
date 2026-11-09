# Studio publication and focused map settings

> **For agentic workers:** Use superpowers:subagent-driven-development to implement the independent tasks and a fresh strict final review. User requests continuation of the approved Studio implementation; staging release authorized by ongoing project scope, production excluded.

**Goal:** Give administrators a full publication page with authoritative branch outcomes and fix links, one operational queue default, and focused map settings with independent catalog availability.

**Architecture:** Existing React Studio orchestration, server preview/token/revision checks retained. Route and SLA editors own their corresponding settings, Start owns catalog/visibility; no new runtime block kind or schema migration. Optional live visibility action changes only catalog visibility with expected-value concurrency and audit, not draft or publication. Unified mode shows/selects only its actual common queue; preserve historical queue records and references rather than destructive deletion. Apply retirement only when source-verified compatible; no silent graph rewriting.

**Tech Stack:** React19, TanStack Query5, ReactFlow12, existing Python/aiohttp/SQLAlchemy/PostgreSQL. No dependencies.

Actor admin; primary job inspect checks then publish a saved revision. Full-width publication replaces popover, map stays mounted but hidden so local context survives return. Summary/check groups/outcomes/diff/explicit confirmation; stale/dirty/inflight checks fail closed. Separate catalog visibility never implies access grants or overrides parent visibility.

Ruling: Retain all historical queue rows/references — user requires old services preserved; hide obsolete operational choices in unified mode, archive only if compatibility demonstrated. Common queue comes from server configuration, not a UI hardcode. No global SLA durations invented.

Baseline installed9dd3eb43aebd074af5ab1d6c7f51aa9fc1a04158, schema158,71maps/drafts/offerings,109versions,9services,5categories. Shared dirty checkout/index preserved through before snapshot and task-only alternate release index. Evidence `tmp/studio-publication-20261109/`; GitNexus tools unavailable, verify source/tests.

- [ ] Full-page publication component/orchestration, server issue grouping and readable terminal/entry/route/SLA outcomes; TDD and stale-result/dirty checks. Owner publication worker.
- [ ] Server independent visibility with admin-only strict expected-value write/audit; authoritative configured common queue/default for new services, preserve historical runtime compatibility; targeted TDD. Owner backend worker.
- [ ] Focus route/SLA settings in matching attachment blocks, separate service rules grouped in Start and entry visibility in entry cards; unified-only queue chooser/defaults. Owner map worker. No runtime contract change.
- [ ] Integrate live availability UI in Start/publication, docs/contracts/CODEMAP, focused/full checks, browser1366/1920 and fresh final review. Owner root.
- [ ] Verified backup/restore, canonical staging-only guarded immutable release, source/assets/health check, live own draft checks and original data hashes/versions audit. Archive own QA only. Owner root.
