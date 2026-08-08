# Helpdesk Segmentation Design

## Status

Approved direction: execute the PR-0 through PR-12 segmentation programme.  The
first delivery train is PR-0, PR-1 and PR-6.  It establishes the architectural
boundary and removes the in-process Knowledge Platform from Helpdesk.

## Goal

Turn Helpdesk into a ticket and ITSM-process service which consumes Endpoint,
Knowledge and Registry through versioned ports.  It must no longer own agent
control-plane state, canonical knowledge content, or canonical person/device
registry data.

## Ownership

| Domain | Canonical owner | Helpdesk role |
| --- | --- | --- |
| Tickets, queues, workflow, SLA/OLA, approvals, quality/problem/change | Helpdesk | Owns data and UI |
| Endpoint identity, WSS, commands, operations, consent and Remote Assist runtime | Endpoint Platform | Versioned API consumer and ticket facade |
| Knowledge items, content, search, RAG and ACL | Future Knowledge Platform | `KnowledgePort` consumer only |
| People, organization, audience and person-device responsibility | Future Registry Platform | `RegistryPort` consumer only |

`ui_users`, web sessions and Helpdesk RBAC stay in Helpdesk for this programme.
`/ws_ui` stays in Helpdesk; the legacy agent websocket is retired only after
Endpoint cutover acceptance.

## First delivery train

### PR-0 — architecture map and ADR

Add a short ownership map and ADRs that define the service boundaries, external
reference/snapshot model, legacy removal rule and rollback gates.  Document
that Endpoint Platform is an exclusive endpoint-agent control plane, consistent
with its accepted ADRs.  This PR changes no runtime behaviour.

### PR-1 — ports, adapters and import guards

Introduce small Python protocol/DTO modules for `EndpointPort`, `KnowledgePort`
and `RegistryPort`; implementations remain explicitly injected at composition
roots.  Add structural tests that forbid ticket/process code from importing
local Knowledge or Registry persistence/services directly.  There is no HTTP
call or feature switch in this PR.

### PR-6 — KnowledgePort and Knowledge removal

Delete the current Knowledge runtime completely: its backend modules, handlers,
routes, UI routes/features, background jobs, scripts, tests and in-process DB
models/migrations are removed from active Helpdesk code.  Do not retain a local
Knowledge database, local search, RAG, ACL evaluator, content-pack loader, or
compatibility adapter.

The replacement `KnowledgePort` exposes only client-side contracts for a future
external service.  The initial adapter is an explicit unavailable adapter.  It
returns a stable typed `knowledge_unavailable` result, emits redacted telemetry
and never reads local Knowledge tables.  Ticket workflows which used Knowledge
must degrade safely: no suggestion is shown, no hidden content is leaked, and a
ticket can still be created, routed, worked and closed.

Ticket history may retain immutable `TicketKnowledgeLinkSnapshot` records only:
opaque external item/version IDs, title/status snapshot, relation type, actor
and timestamps.  It must not retain canonical article body, chunks, ACL rules,
embeddings, prompt material or a cross-service database foreign key.

Existing `ticket_kb_links` rows and sanitized `knowledge_attempts` remain
read-only historical ticket evidence during the first cutover.  Helpdesk will
not create new local Knowledge links or attempts.  PR-11 will migrate the
former to a neutrally named external-reference model before its old table is
dropped.  This preserves ticket history without treating either shape as a
local Knowledge source of truth.

`server/ai/` and its provider settings are removed with the Knowledge runtime:
the current codebase uses them only for Knowledge search, embeddings and Ask.
They are not re-purposed as a generic Helpdesk AI subsystem in this programme.

The removed `/api/knowledge/*` and `/api/web/knowledge/*` paths are no longer
registered and therefore return the normal 404 response.  Helpdesk does not
provide a misleading local 503 proxy or a compatibility content endpoint.

The PR publishes a minimal versioned OpenAPI/Markdown integration contract:
search/suggestions, item/version projection, ticket-resolution draft request,
feedback, standard error envelope, authentication/scopes, pagination and
redaction rules.  It documents this as an integration target, not a registered
Helpdesk route.

## Later delivery order

1. **PR-2:** server-created requester/person/device external refs and immutable,
   redacted snapshots; no client-supplied identity becomes authoritative.
2. **PR-3:** Endpoint operation/read API contract around durable operation IDs,
   capability bounds, idempotency, consent and safe result projections.
3. **PR-4:** Helpdesk Endpoint read adapter under a feature flag, local fallback
   and comparison telemetry.
4. **PR-5:** Endpoint command/operation cutover under a feature flag with a
   tested rollback to the durable Helpdesk outbox path.  Protocol V3 identity
   and idempotency invariants remain intact until the cutover is accepted.
5. **PR-7:** connect an external Knowledge API with shadow read and controlled
   activation.  This is not a restoration of any local Knowledge runtime.
6. **PR-8:** split local Registry internals into identity, directory,
   binding/registration, derived projection and audited administration seams.
7. **PR-9:** Registry API adapter with documented preview/apply/audit envelopes
   and shadow reads.  Until an external Registry exists, a local reference
   adapter is allowed only behind the port.
8. **PR-10:** remove agent-local Helpdesk/Registry compatibility after
   browser-first and Endpoint/Registry acceptance proves it is unused.
9. **PR-11:** delete legacy agent routes, tables and migrations only after
   acceptance evidence and a tested backup/rollback procedure.
10. **PR-12:** frozen-commit CI, migration, smoke, deployment and rollback gates.

## Cross-service rules

- All external identifiers are opaque strings; Helpdesk does not infer their
  meaning or issue credentials for another service.
- Cross-service data is read through versioned HTTP APIs, never direct imports
  or database foreign keys.
- Snapshots are server-produced, immutable, minimal and redacted.  They support
  history and routing but cannot be treated as a mutable source of truth.
- Feature flags are fail-closed.  A disabled/unavailable remote dependency must
  produce a typed, observable degraded result rather than silently falling back
  to deleted or legacy code.
- Endpoint command execution keeps durable outbox delivery, ACK/NACK/result
  semantics, operation idempotency and consent controls throughout cutover.
- API clients do not receive device credentials, raw endpoint telemetry,
  Knowledge restricted content, sessions, tokens, cookies or secret material.

## Failure and rollback policy

PR-0, PR-1, PR-6 and PR-8 change no Endpoint or Registry runtime behaviour.
PR-6 deliberately removes the Helpdesk Knowledge feature; its rollback is a
normal application rollback to the preceding verified release, not a hidden
local Knowledge fallback.  Database deletion is deferred to PR-11; PR-6 first
makes obsolete tables unreachable and validates that Helpdesk has no production
reads or writes to them.

PR-4, PR-5, PR-7 and PR-9 require feature flags, bounded timeouts, correlation
IDs, comparison telemetry, documented rollback conditions and acceptance
evidence before their flags may become default-on.

## Verification strategy

- Import-guard and architecture tests for every port boundary.
- Focused ticket-flow tests proving that create, routing, support work and close
  continue while `KnowledgePort` is unavailable.
- Contract tests for DTO validation, redaction, error envelopes and feature-flag
  defaults.
- Route/UI tests proving the old Knowledge surfaces are not registered.
- Migration checks proving no active application path reads or writes removed
  Knowledge tables before PR-11 deletes them.
- The existing targeted Endpoint, Registry, agent, browser and release checks
  run in the PRs that change those respective surfaces.

## Explicit non-goals

- Build a new Knowledge or Registry service/database in this repository.
- Preserve the existing Knowledge implementation as a fallback or shim.
- Move Helpdesk web authentication/RBAC into IAM/OIDC.
- Remove agent/operation legacy paths before the Endpoint acceptance gates.
- Deploy or delete remote data as part of PR-0, PR-1 or PR-6.
