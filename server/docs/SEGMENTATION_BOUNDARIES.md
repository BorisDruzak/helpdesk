# Helpdesk Segmentation Boundaries

Status: normative segmentation boundary record, updated through the PR-8
RegistryPort read cutover.

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
release, never a local compatibility fallback. Knowledge table deletion is
deferred to PR-11 and may occur only after the relevant cutover acceptance
evidence and backup/rollback procedure are accepted; PR-6 first makes those
tables unreachable from active Helpdesk code.

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
by default. Its DTOs expose only opaque refs and redacted projections. The
`external` mode remains explicitly unavailable until PR-9 acceptance, and
local commands are not invoked until they can honor caller-provided operation
IDs with deterministic idempotency outcomes.

The PR-8 Helpdesk read cutover is deliberately limited to operations represented
by the frozen port: requester display snapshots, active device bindings and
redacted account status. Ticket creation, immutable requester history,
inventory requester projection and the support current-requester projection use
those operations without a local ORM/service fallback. The support DTO keeps a
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
resolution, rich ticket diagnostic context, customer-history binding/session
events, exact binding/session authorization and Registry commands remain
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

The contract itself does not migrate any additional Helpdesk consumer. Such
consumers must be cut over in a later task and may not bypass the port with a
local Registry fallback.

## Non-goals

This programme does not create a new Knowledge or Registry service in this
repository, deploy a remote service, move Helpdesk auth/RBAC to an IAM service,
or delete legacy data in PR-0.
