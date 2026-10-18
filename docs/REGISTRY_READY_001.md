# Registry and requester context

## Profile contract

`registry/profile_schema_service.py` owns the existing schema policy. The default
contact list uses stable `phone`, `chat`, `email` values. The minimum required
profile remains name, department, location and phone or internal extension.
Additional fields stay optional unless explicitly configured otherwise.

`registry/profile_values.py` validates text/textarea, select, phone (including
extensions), email, HTTP(S) URL without credentials, finite number, ISO calendar
date and an explicit JSON boolean. A false boolean and zero are present answers.
Writes reject invalid values and excess length rather than truncating/coercing
them. Optional custom values can be cleared explicitly. Omitted/hidden metadata
is retained. The schema editor supports labels and stable values for custom
lists; preview/save reject deletion/type/option/constraint changes incompatible
with stored values, including archived profiles.

Validation supports `min_length`, `max_length` (1–1000) and a bounded full-match
pattern. Patterns permit literals, character classes, simple escapes, fixed
repeats up to 1000 and at most one variable repeat; groups, alternation,
lookarounds and backreferences are rejected. Pattern length is at most 200.
Legacy values are read unchanged. `profile.value_issues` explains correction
needs without automatically making previously present values missing.

## Organizational provenance and review

Field provenance uses the existing person/department `metadata_json`, under
`organization_context_v1 = {version: 1, fields: {...}}`. Department, location and
manager links distinguish `confirmed`, `self_reported`, `legacy_unknown` and
invalid/unsupported provenance. Verified UI identity does not establish field
trust. There is no bulk backfill or new employee registry.

New requester-entered department/location values remain usable for profile
completion and contact context, but do not confer organizational audience access.
For an existing organizational value, the employee submits a pending proposal
with a unique ID and base value. The official value remains unchanged. Admins
review proposals in the existing person drawer. The existing person PATCH accepts
`organization_review: {field, proposal_id, decision: approve|reject}` and a reason.
Review is serialized on the person row, validates active target references,
rejects stale/replayed proposals and appends Registry audit events. Admin edits
explicitly containing organizational fields confirm those fields. Changing a
department invalidates a manager link tied to the previous department.

Historical values without provenance retain their previous audience behavior in
the default compatibility mode; they are not relabeled confirmed. Profile edits
cannot replace that legacy baseline with a new self-declared access scope.
`EffectiveIdentityService` and audience previews share the trust boundary. New
untrusted values are omitted from authoritative routing facts. Explicit person,
role and access-group grants continue to use their existing authorization rules.

Strict historical audience behavior is **disabled by default**. To enable it,
an administrator first uses the existing policies preview endpoint and reviews
`organization_trust_impact`. Updating policies to
`organizational_trust.strict_legacy_audiences=true` additionally requires
`confirm_strict_legacy_audiences=true` and `organization_impact_counts` equal to
the current preview counts, plus the normal reason. This is a separate activation;
development/test verification does not activate it on real data. An unrelated
partial policy update preserves an already enabled strict setting. Explicit
reset returns policies to their documented compatibility defaults.

## Assigned approval

`registry/manager_resolution.py` requires a confirmed personal manager, or a
confirmed active department manager when the source explicitly sets
`allow_department_fallback: true`. It then requires an active Registry person,
exactly one verified UI identity and an active account. Multiple identities are
an explicit readiness failure. The configured policy fallback remains canonical;
missing resolution cannot silently select an actor or create an empty manager
approval request. Existing stored assignments and historical snapshots are kept.

Ordinary managers receive `approval.decide.assigned` through the existing Access
Control Center only when an administrator grants it. It is not added to the user
role or to every manager. The requester menu exposes **Мои согласования** at
`/app/requester/approvals`. `GET /api/web/requester/approvals` returns at most 100
own pending assignments with public request text and decision requirements.
There are no internal comments, arbitrary custom fields, other assignments or
support context in that projection. Decisions reuse
`POST /api/web/support/tickets/{ticket_id}/approvals/{approval_id}/decision`.
Server authorization checks the exact assignment and active identity/capability,
then locks ticket/approval, enforces sequence/comment/state and writes the existing
approval event/history. The permission does not grant queues, arbitrary ticket
details, SLA, users, assignees or status transitions. Existing support approval
authorization remains in effect.

## Read-only scenario readiness

The existing Registry **Качество данных** tab offers an explicit check through
`GET /api/web/admin/registry/scenario-readiness` (admin role). It runs in a PostgreSQL
read-only transaction, uses an untruncated Registry snapshot, existing issue keys
and overrides, Policy Health and canonical published-map graph/queue/calendar
validation. It checks nine dimensions and separates a concrete function blocker,
attention and informational findings. Missing device links do not block ordinary
device-optional requests. The report includes remediation and links to Registry,
Policy Health or Studio. It does not persist a separate findings database.

The download contains dimension/impact aggregates only: no object IDs, issue keys,
ticket text, contact details or metadata. Read failures return 503 rather than a
successful empty readiness result. The ordinary Registry view keeps its existing
bounded read behavior; only an explicitly requested readiness scan removes those
display limits.

## Integration and remaining resource limitation

`requester_context_v1`, verified device bindings and immutable v1/v2/v3 scenario
versions remain canonical. `device_picker` still lists only permitted active
personal bindings. A printer request can use a linked PC, or proceed without a PC
when its scenario makes the device optional; browser-only ordinary requests remain
supported. No arbitrary `metadata_json` path is exposed to scenario conditions.

Current catalog `public/internal/restricted` visibility remains independent of
Registry audience membership: confirming a department does not turn a restricted
service public or grant it a new catalog route. This change establishes the
trusted audience projection for its existing consumers; it does not add a new
department-based Service Catalog authorization model.

There is no authorized picker for shared printers, folders or corporate systems
in this change. Collect their names through existing scenario questions. A minimal
follow-up could add a server-filtered `resource_picker` over existing shared
Registry assets/services, with explicit type/scope and stable references; it must
not broaden `device_picker` or introduce a separate CMDB.

## Verification scope

Tests use synthetic actors and disposable staging PostgreSQL databases. The
fixture browser suite `webapp/tests/registry-ready.spec.ts` covers profile/schema,
organizational review, ordinary-manager decisions and readiness at 1366×768 and
1920×1080, including network/JavaScript errors and aggregate export. Fixture
browser evidence and PostgreSQL API persistence evidence are distinct; neither
is production acceptance. No production deployment, real scenario publication,
profile rewrite, account/device rebind or automatic permission rollout is part
of this work. Protocol V3 and Endpoint contracts are unchanged.
