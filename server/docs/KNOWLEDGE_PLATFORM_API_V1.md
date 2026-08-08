# Knowledge Platform API v1

Status: future external integration target for Helpdesk. This specification
defines no local Helpdesk route, proxy or compatibility endpoint. All paths
below are owned by the future Knowledge Platform and are intentionally absent
from Helpdesk route registration.

## Transport and common rules

- Base path: `https://<knowledge-platform>/v1`. The hostname is configured at
  composition time; Helpdesk does not infer it from a ticket or external id.
- Service callers authenticate with mTLS and an OAuth 2.0 client-credential
  access token. Knowledge validates both caller identity and the required scope.
- External IDs (`item_ref`, `version_ref`, `feedback_ref`, `draft_ref`) and
  `correlation_id` are opaque strings. Helpdesk preserves them exactly without
  trimming, case-folding or parsing, and does not expose them to untrusted
  clients. The initial client-side DTOs reject values longer than 512
  characters rather than truncating or rewriting them.
- `correlation_id` is supplied by Helpdesk per operation and is safe for
  redacted tracing. It must not contain tokens, cookies, raw search text,
  personal data or article content.
- Requester-safe results contain only fields authorised by Knowledge. No
  endpoint returns hidden titles, body text, chunks, ACL rules, embeddings,
  credentials or raw policy diagnostics.
- List results use cursor pagination. `page_size` is optional and bounded by
  the service; `next_cursor` is opaque and returned only by Knowledge.

## Standard envelope

Successful responses use an operation-specific `data` object and may include
`correlation_id`. Errors use this stable envelope:

```json
{
  "error": {
    "code": "knowledge_unavailable",
    "message": "Knowledge Platform is unavailable.",
    "retryable": true
  },
  "correlation_id": "opaque-correlation"
}
```

`knowledge_unavailable` means Helpdesk could not obtain an authorised response
from the external service. It is the typed degraded result for a timeout,
disabled integration or unavailable service; it never authorises a local
Knowledge lookup or a local fallback. Other stable codes include
`invalid_request`, `forbidden`, `not_found` and `rate_limited`.

## Future external operations

Every operation in this section is a **future external Knowledge Platform
target, not a Helpdesk route**.

### `POST /v1/search`

Required scope: `knowledge.search`. Request fields are `query`, safe
`audience_context`, optional `service_ref`, `page_size`, `cursor` and
`correlation_id`. `query` is request-only and must not be retained in Helpdesk
logs or ticket history. Response `data` includes `items` and `next_cursor`.
Each item is a safe projection: `item_ref`, `version_ref`, `title`, optional
redacted `summary`, `status` and optional safe relevance metadata.

### `POST /v1/suggestions`

Required scope: `knowledge.suggest`. Request fields are safe intent/context
signals, optional `service_ref`, `audience_context`, `page_size`, `cursor` and
`correlation_id`. The request must not send raw ticket conversation,
credentials, endpoint telemetry or restricted attachments. The response uses
the search projection and cursor rules. An empty authorised result is distinct
from `knowledge_unavailable`.

### `GET /v1/items/{item_ref}/versions/{version_ref}`

Required scope: `knowledge.read_projection`. Returns one authorised
item/version projection with opaque references, `title`, redacted `summary`,
`status`, and a version timestamp only when authorised. This is not a
canonical-content export: it never promises article body, chunks, source,
embeddings or ACL rules.

### `POST /v1/resolution-drafts`

Required scope: `knowledge.resolution_draft`. Request fields are opaque
`ticket_ref`, optional safe item/version references, redacted structured
resolution facts and `correlation_id`. It cannot contain secrets, full ticket
chat, hidden Knowledge content or caller-supplied ACL decisions. Response
contains `draft_ref`, `status` and a safe redacted draft projection. The result
is advisory; Helpdesk retains ownership of ticket resolution and workflow.

### `POST /v1/feedback`

Required scope: `knowledge.feedback`. Request fields are opaque `item_ref`,
optional `version_ref`, controlled feedback code/value, optional redacted
reason category and `correlation_id`. Helpdesk must not send free-form ticket
text unless a later contract explicitly permits and redacts it. Response
contains opaque `feedback_ref` and acknowledgement status; it does not grant
Helpdesk authority to mutate canonical Knowledge content.

## Failure, telemetry and evolution

Callers use bounded timeouts and record only redacted operation name, outcome,
stable error code and opaque correlation. They do not log access tokens, mTLS
material, cookies, raw queries, article body, ACL data or endpoint telemetry.

Breaking changes require a new major API version. Additive fields must be
ignored safely by Helpdesk clients. Availability does not block core ticket
creation, routing, support work or closure.
