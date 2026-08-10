# Helpdesk Segmentation Boundaries

Status: normative segmentation boundary record, updated through the PR-9
Registry Platform read adapter and shadow-read gate.

## Ownership

| Domain | Canonical owner | Helpdesk responsibility |
| --- | --- | --- |
| Ticket and ITSM process | Helpdesk | Tickets, queues, workflow, SLA/OLA, approvals, quality, problem and change processes, plus their user experiences. |
| Endpoint agent control plane | Endpoint Platform | Endpoint identity, agent WebSocket transport, commands, durable operations, consent and Remote Assist runtime. Helpdesk is an API consumer and ticket facade only. |
| Knowledge | Future Knowledge Platform | Canonical items, versions, content, search, suggestions, RAG and access control. Helpdesk consumes `KnowledgePort` only. |
| Registry | Future Registry Platform | Canonical people, organisation, audience and person-device responsibility data. Helpdesk consumes `RegistryPort` only. |

`ui_users`, Helpdesk web sessions, Helpdesk RBAC and `/ws_ui` remain Helpdesk
concerns. The legacy agent WebSocket remains in Helpdesk only until the Endpoint
cutover is accepted; this does not make Helpdesk the endpoint-agent control
plane.

## Domain-port rules

- Cross-domain reads and commands use versioned service APIs through
  `EndpointPort`, `KnowledgePort` or `RegistryPort`; implementations are
  explicitly composed at Helpdesk boundaries.
- Helpdesk code must not import another domain's persistence, ORM models,
  repositories or internal services. Direct cross-domain database foreign keys
  are forbidden.
- External identifiers are opaque strings. Helpdesk neither interprets their
  format nor creates credentials for the owning service.
- A Helpdesk ticket may keep only server-produced, immutable and redacted
  external-reference snapshots needed for history, routing or audit. It cannot
  retain canonical knowledge bodies, chunks, ACL policy, embeddings, endpoint
  telemetry or mutable Registry truth.
- Authentication, authorisation and redaction remain enforced by the owning
  service. Helpdesk must not use a snapshot to bypass those controls.

## Knowledge transition rule

PR-0 documents the target while the current in-process Knowledge runtime still
exists. It is not a new Helpdesk route and it is not an adapter implementation.
PR-6 removes that runtime. There is **no local fallback** after removal:
unavailable Knowledge is represented by the typed `knowledge_unavailable`
outcome from `KnowledgePort`; ticket creation, routing, support work and closure
continue without content or hidden retrieval.

PR-6 rollback is a normal rollback to the preceding verified application
release, never a local compatibility fallback. PR-11a revision `134` has
removed the already-unreachable local Knowledge/AI physical graph, including
`ticket_knowledge_links` and `problem_known_error_links`, after clone-path
verification. That migration preserves `ticket_kb_links`, tickets, problems,
resolution passports, Helpdesk identity/session/RBAC and every Registry table.
It is forward-only: rollback is application rollback plus verified PostgreSQL
backup restore, never Alembic downgrade.

The future integration contract is
[KNOWLEDGE_PLATFORM_API_V1.md](KNOWLEDGE_PLATFORM_API_V1.md). Every path in that
document is a future external Knowledge Platform target, never a Helpdesk route.

## Endpoint and Registry transition rules

Endpoint Platform is the exclusive endpoint-agent control plane, consistent
with its accepted ADR 0001 and ADR 0002. Future cutover work preserves the
durable operation, consent, identity and audit invariants until its acceptance
gates pass.

Registry is a separate external domain. Until its external API is introduced,
Helpdesk must keep Registry access behind `RegistryPort`; it must not turn
temporary local implementation details into a cross-domain contract.
PR-8 composes the existing Registry through `server/registry_adapter/local.py`
by default. Its DTOs expose only opaque refs and redacted projections. PR-9
adds `server/registry_adapter/http.py` as a versioned authenticated read client;
`external` fails closed unless its HTTPS URL and service token are configured,
while local reads remain authoritative and Helpdesk observes redacted external
parity. Commands and auth remain local until
their separate acceptance cutover; local commands are not invoked until they
can honor caller-provided operation
IDs with deterministic idempotency outcomes.

The PR-8 Helpdesk read cutover uses the represented port operations for requester
display snapshots, active device bindings, redacted account status and requester
history. Ticket creation, immutable requester history, inventory requester
projection and the support current-requester projection use those operations
without a local ORM/service fallback. The support DTO keeps a
typed unavailable or not-found current-state result visible as
`status`/`source`/`code` and may display only a previously validated immutable
ticket requester snapshot as history. It must not reconstruct current contact,
organisation, asset or service data from local Registry tables.

Use `python scripts/check_domain_import_boundaries.py --registry-scope
requester,tickets,customer_history,inventory,web_api` for the incremental
Registry boundary. The scoped guard covers every new ticket module and rejects
new Registry ORM/repository/service imports in selected migration paths, while
an exact symbol ledger records operations still waiting for a richer external
contract. This is not yet a repository-wide claim: requester profile/on-behalf
resolution, rich ticket diagnostic context, exact binding/session authorization
and Registry commands remain
explicitly deferred.

### Rich Registry read contract (Task 5)

`RegistryPort` also defines frozen redacted requester-profile, directory,
device-context and requester-history projections. They carry opaque refs,
display/location/department labels and safe state codes only — never contacts,
identity aliases, account-session IDs, asset IDs, serials or ORM metadata.
Directory results are capped at 50; audience and history collections are capped
at 100 by their DTOs, including future external adapters.

Audience, directory, requester-profile and requester-history visibility takes a
`RegistryReadActor` produced only from verified Helpdesk auth context. A
requester actor is limited to its matching opaque requester ref; directory
enumeration accepts only support/admin actors. The local compatibility adapter
passes actor id and role to the Registry effective-identity resolver, so
access-group and role targeting remains authoritative. A malformed authoritative
projection is typed as `invalid`, separately from `not_found` and
`unavailable`; local reads use a nested transaction when available, preventing
a failed query from aborting the caller-owned session.

Customer History is the first rich consumer cut over: it accepts only a typed
`RegistryReadActor` assembled from verified Helpdesk middleware context and
passes it to `RegistryPort.requester_history()`. Requester actors are checked
against the server-resolved opaque ref before the call. Its `source_states`
expose typed `available`, `unavailable`, `not_found` or `invalid` Registry
state; it never reads local binding/session ORM rows as a fallback. Remaining
rich consumers must be cut over separately and may not bypass the port.

## PR-11 retirement boundary

`scripts/registry_retirement_manifest.py` is the sole reviewed declaration of
the remaining future local Registry-table retirement. Revision `134` owns the
separate, static historical Knowledge/AI graph; the Registry manifest retains
that list solely as historical audit provenance and does not request its row
counts or FK signature in future Registry evidence. It covers local
`registry_*`, device registration, account-session and browser-pairing tables
and records the required detachment of legacy Registry columns from tickets,
consent and Helpdesk services before any table drop.

The manifest explicitly excludes and protects actual Helpdesk identity/session
tables `ui_users`, `auth_sessions`, `ui_tokens`, `ui_user_audit`,
`ui_password_reset_requests`, `ticket_public_sessions`; RBAC/queue tables
`access_groups`, `access_group_members`, `access_group_permissions`,
`access_group_queue_members`, `access_audit`, `ticket_queues`,
`ticket_queue_members`, `ticket_queue_ola_targets`; plus `tickets`,
`user_consent_requests` and `TicketKbLink` / `ticket_kb_links` read-only
history.
The no-write `rehearse_registry_retirement.py` gate remains fail-closed while
any local Registry runtime/route/writer/consumer exists, or while external
command acceptance, clone counts, backup hash, restore drill, approved
maintenance, advisory-lock evidence or a trusted public-key/KMS attestation is
absent. The evidence binds a single environment/revision to immutable backup,
clone and catalog IDs and the reviewed FK-graph signature; the backup and
restore/catalog links must match exactly. `--require-ready` derives the
workspace Git `HEAD`, requires the expected immutable environment identifier,
and rejects stale (over 24 hours), materially future (over five minutes),
cross-context or out-of-order backup → restore → catalog → maintenance →
attestation proof. PR-11 is forward-only; rollback is an application rollback
plus tested PostgreSQL restore, never an Alembic downgrade.

## Non-goals

This programme does not create a new Knowledge or Registry service in this
repository, deploy a remote service, move Helpdesk auth/RBAC to an IAM service,
or delete legacy data in PR-0.
