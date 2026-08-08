# Helpdesk Segmentation Boundaries

Status: normative PR-0 architecture record. This document changes no runtime
behaviour.

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

## Non-goals

This programme does not create a new Knowledge or Registry service in this
repository, deploy a remote service, move Helpdesk auth/RBAC to an IAM service,
or delete legacy data in PR-0.
