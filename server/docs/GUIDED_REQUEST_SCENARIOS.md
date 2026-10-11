# Guided Request Studio scenario domain

The existing Service Catalog service/offering, RequestTemplate/FormSchema and
policy runtime remain authoritative. Categories are navigation over that catalog.
Scenario execution and publication are separate from saving a draft.

## Contracts (schema version 1)

`web_api/dto/request_scenario.py` defines bounded, strict Pydantic inputs;
`webapp/src/features/request-template-studio/scenario-contract.ts` mirrors the
typed block and condition unions. Legacy Studio DTOs remain separate.

Blocks: form_page, instruction, decision, resolution_check, diagnostic, review,
submit_ticket and finish. Conditions accept only answers and the current block
result, with typed comparisons, membership, existence, AND/OR and NOT. No
expression evaluator, arbitrary context, actor/role/queue/SLA input or operational
dispatch is permitted. Definition limits are 1 MiB, 256 blocks, bounded nesting
and item count; session answer input is limited to 64 KiB. Graph semantics and
answer validation must be enforced by the canonical runtime before execution.
The standard JSON projection of a `current_result` condition has `field: null`;
the TS wire type accepts null or omission and rejects a non-null field key.

Draft definitions may have no blocks or entry point. Executable definitions
require both. All 17 supported legacy field kinds are represented. Attachment
fields are rejected; diagnostic execution mode is only `unavailable`.

## Persistence and upgrade boundary

Migration 147 follows actual head 146 and adds five tables:

- `request_studio_categories`: service-scoped tree with sibling/root slug
  uniqueness, composite parent/service FK, cycle and depth (16) guards.
- `request_studio_scenarios`: canonical service/offering binding and optional
  category, disabled by default, with a same-scenario published-version FK.
- `request_studio_scenario_versions`: immutable definition/hash/source snapshot,
  monotonic lifecycle published → retired/revoked, unique version number and at
  most one published version per offering.
- `request_studio_drafts`: independent definition, positive optimistic revision,
  optional same-scenario base version.
- `request_studio_sessions`: owner/version pinning, positive revision, expiry
  after creation, answers/history/results and optional canonical ticket link.

SQL guards reject version mutation/deletion/reactivation and session identity,
owner or version changes. Category mutations serialize per service and account
for descendant depth when reparenting. Application APIs must add RBAC, visibility,
revision compare-and-swap, publication transactions and audit atomically. These
constraints alone do not constitute requester authorization or publish readiness.
Use the existing `helpdesk_service_catalog_audit` object_type/object_code audit
store for category/scenario actions; do not create another catalog audit engine.

No existing ticket, form, catalog or policy row is rewritten. Four configuration
tables are persistent test fixtures; sessions are ephemeral and included in full
and web-support cleanup. ORM metadata is registered through `app.db.models`.

Rollback is limited to 147 → 146 after stopping scenario use and preserving any
needed scenario/session records: it removes the five new tables and guards and
retains legacy data. Never cross forward-only revisions 144/143. Re-upgrade to
147 recreates empty scenario tables. Rollback is a release procedure, not a
requester operation; it is validated only on a harness-owned private database.

P1 introduces contracts and storage; P2 adds the pure graph runtime. HTTP runtime,
publication and UI remain gated by P3–P10. No production deployment or live publication is
authorized by this implementation.

## Canonical graph semantics (P2)

`tickets/request_scenario_validation.py` rejects duplicate/unknown identifiers,
unreachable blocks, graph/field dependency cycles, unsupported capabilities,
unsafe authority fact keys and incompatible condition/role types. Dependency
checking is iterative across long multi-page chains. Raw HTML and executable
Markdown links are rejected for instructions; the UI must also render safely.

Conditions are typed: boolean differs from number; missing values do not match
comparisons (including neq); membership on multi-select matches any selected item.
Numeric ordering/input/bounds accept finite numbers with absolute value at most
9007199254740991. Both integers and floats share this wire/conversion safety bound.
There is no string-to-number coercion at this boundary. Existing canonical codecs
and constraints normalize valid field values.

Branches execute in ascending explicit priority, then use the final unconditional
fallback. Overlapping conditions require distinct priorities; multi-select branches
may overlap even when their expected choice sets are disjoint. A resolution check
may omit fallback only when result-only conditions cover yes/no/unknown. Conditions
depending on answers cannot prove coverage using an empty answer set. Finish needs
an explicit positive resolution check on every reachable path; acknowledging an
instruction does not establish success.

The pure runtime copies its definition/state and bounds automatic traversal.
Diagnostics yield unavailable/pre_ticket_contract_unavailable with no network
operation. Visible required answers are validated; hidden values are pruned.
Back retains earlier/target-page answers and removes subsequent history, answers
and derived results. Revision/current-block checks reject stale input. Ticket
creation, authorization, immutable version pinning and persistent compare-and-swap
are caller responsibilities in later stages. This engine cannot create tickets,
execute policies or dispatch Endpoint operations.

## Admin API (P3)

New routes are under `/api/web/admin/request-studio`; existing capabilities,
validate-draft, publish-preview and publish endpoints keep their legacy contracts.
All new success responses are `{status: "success", data: ...}`; failures include
a stable error_code without raw failed payloads or database exception parameters.

| Method/path | Access | Behavior |
| --- | --- | --- |
| GET `/catalog` | admin, auditor | Categories, existing services/offerings, scenario summaries; q/status/offset/limit |
| POST `/categories` | admin | Create category from service_code/parent_id/slug/title/description/sort_order/visibility/lifecycle_status |
| PUT `/categories/{identifier}` | admin | Full category update with expected revision |
| DELETE `/categories/{identifier}?revision=N` | admin | Archive empty category; preserves referenced rows |
| POST `/scenarios` | admin | `{definition}` creates disabled scenario and draft revision 1 |
| GET `/scenarios/{identifier}` | admin, auditor | Scenario metadata and editable draft |
| PUT `/scenarios/{identifier}/draft` | admin | `{definition, revision}` saves by optimistic revision |
| POST `/scenarios/{identifier}/archive` | admin | `{revision}` archives/disables without mutating immutable versions |
| GET `/scenarios/{identifier}/versions` | admin, auditor | Immutable version history, newest first |
| POST `/scenarios/{identifier}/simulate` | admin, auditor | `{revision, steps}` executes canonical pure graph from its initial state |

Catalog query defaults are status=all, offset=0, limit=100 (maximum 500). Unknown
parameters, invalid status, negative offsets and oversized limits return 400.
The errors filter includes an invalid new draft even when an older version is
published; the draft filter includes all unpublished scenarios, including invalid
drafts. Archived scenarios have their own filter.
Category entries report effective_visibility as the intersection of the service
and all ancestor/category restrictions; setting a category public cannot widen a
restricted service. Existing offering visibility remains authoritative as well.

Draft save can preserve an incomplete graph; simulation/publication require a
valid executable graph. Scenario key, service and offering remain immutable;
template binding must match the existing offering and a real RequestTemplate.
To copy a scenario, create a new scenario_key with the same offering or another
verified offering/template binding. No Service/Offering/Template row is created
or rewritten. Published-version creation, rollback-as-new-version and enablement
use the separate P8 confirmation/publication protocol; no generic version mutation
or enable flag is accepted in these draft APIs.

Mutations return 409 for stale revision/duplicates/non-empty category/archive
conflicts, 404 for missing records, and 400 for unsafe bindings/tree constraints.
Category service is immutable. Tree changes and scenario moves/archive serialize
with the SQL service advisory lock; locked draft reads refresh the identity map
before checking revision. Audit actor comes only from AuthContext. Draft audit
records contain metadata/revision/definition hash rather than full answers or
arbitrary content. A failed audit rolls back the configuration write. Simulation
does not update drafts, sessions, tickets, policies or Endpoint state. Bodies are
limited to 1 MiB before parsing, and simulation is limited to 256 steps.
