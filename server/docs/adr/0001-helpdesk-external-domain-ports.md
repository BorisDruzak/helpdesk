# ADR 0001: Helpdesk consumes external domain ports

## Status

Accepted for Helpdesk segmentation PR-0.

## Context

The current repository contains Helpdesk together with runtime areas that are
future independent domains. This coupling makes ownership, access control and
future deployment boundaries unclear. Accepted Endpoint ADR 0001 and ADR 0002
already establish Endpoint Platform as the endpoint-agent control plane.

## Decision

Helpdesk owns tickets and ITSM processes. It consumes Endpoint, Knowledge and
Registry through versioned, explicitly injected ports:

- `EndpointPort` for endpoint identity, read state, commands and durable
  operation projections;
- `KnowledgePort` for safe Knowledge search, suggestions, item/version
  projection, resolution drafts and feedback;
- `RegistryPort` for person, organisation, audience and responsibility
  projections.

Ports are the only active cross-domain dependency layer. Helpdesk does not
import domain internals or use cross-domain database foreign keys. External
identifiers are opaque and Helpdesk stores only minimal immutable, redacted
snapshots when ticket history requires them.

The Knowledge API described in
[KNOWLEDGE_PLATFORM_API_V1.md](../KNOWLEDGE_PLATFORM_API_V1.md) is a future
external target. None of its paths are registered by Helpdesk. During PR-0 the
existing Knowledge runtime is unchanged; after PR-6 its replacement is an
explicit unavailable port, with no local fallback.

PR-6 rollback returns the application to the preceding verified application
release; it never restores a local compatibility fallback. Knowledge table
deletion is deferred to PR-11 until cutover acceptance evidence and a tested
backup/rollback procedure permit the forward-only deletion.

## Consequences

- Ticket workflow and Helpdesk UI remain independently deployable from endpoint
  control-plane and content ownership.
- Cross-domain contracts require versioning, authentication scopes, redaction,
  opaque correlation and contract tests.
- A remote dependency outage produces a typed, observable degraded result;
  Helpdesk must not silently read legacy local tables or compatibility routes.
- Existing legacy history is retained only as read-only evidence until a later,
  accepted migration replaces it with neutral external references.

## Rejected alternatives

- Keep local Knowledge as a hidden fallback: this preserves split ownership,
  risks stale or restricted-content leakage and hides an external outage.
- Expose a Helpdesk proxy under the future Knowledge paths: consumers could
  mistake a local compatibility surface for the external service.
- Share ORM models or foreign keys: deployment and data ownership would remain
  coupled.
