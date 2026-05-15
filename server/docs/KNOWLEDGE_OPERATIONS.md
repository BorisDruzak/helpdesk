# Knowledge Operations

P2.2 turns the existing Universal Knowledge Platform into an operational content loop. It does not replace P2/P2.1 spaces, items, versions, chunks, bindings, graph, feedback, ingestion, passport drafts, ACL filtering or `kb_links` compatibility.

## Content Packs

Baseline packs live in `content_packs/knowledge/*.yaml` and are installed by:

```powershell
python scripts/seed_knowledge_content.py --dry-run --all
python scripts/seed_knowledge_content.py --pack it-self-service-baseline
python scripts/seed_knowledge_content.py --all --force
```

The script supports `--dry-run`, `--pack <code>`, `--all`, `--force`, `--retire-missing`, `--publish` and `--actor <id>`.

Pack installs are idempotent. `KnowledgeContentPackService` records `knowledge_content_packs` and `knowledge_content_pack_items`, hashes pack source and item content, skips unchanged entries, reports conflicts when admin-edited content differs, updates only with explicit `--force`, and can archive pack-managed items missing from a newer pack when `--retire-missing` is supplied.

Requester-safe pack content is linted before publication. Unsafe requester/public text fails the item install instead of being published.

Baseline packs:

- `it-self-service-baseline`: requester-safe articles for VPN, password reset, mail, printer, laptop power and unknown category problem description.
- `support-runbooks-baseline`: support-internal runbook drafts/in-review entries for first-line diagnostics.
- `known-errors-baseline`: generic internal draft placeholders for known error/workaround patterns without fake vendor facts.
- `glossary-baseline`: requester-safe glossary entries for VPN, MFA, SLA, OLA, access request, service offering, known error and workaround.

## Templates And Lint

`server/knowledge/content_templates.py` defines structured templates for article/how-to, FAQ, troubleshooting, support runbook, known error, workaround, policy/process, glossary term and service description. Each template lists required sections and default visibility.

`server/knowledge/content_lint.py` validates:

- title, summary and body;
- owner/reviewer and review due date for published content;
- required sections by `item_type`;
- requester/public safety markers;
- requester/public source refs;
- recommended service/offering binding for self-service items;
- known error status plus workaround or permanent-fix information.

`KnowledgeRepo.publish_item()` runs lint before publication. Lint errors block publish. Non-blocking template/binding warnings can be acknowledged by the server-side publish integration so legacy compatible content can still publish when the hard blockers are absent.

## Review Tasks

Migration `086` adds first-class review workflow tables:

- `knowledge_review_tasks`
- `knowledge_review_comments`

`KnowledgeReviewTaskService` creates and manages tasks for draft review, scheduled review, stale content, negative feedback, gap candidates, passport drafts, ingestion review and unsafe visibility. It supports assignment, start, completion and dismissal with comments.

APIs:

- `GET /api/web/knowledge/review/tasks`
- `GET /api/web/knowledge/review/tasks/{task_id}`
- `POST /api/web/knowledge/review/tasks/{task_id}/assign`
- `POST /api/web/knowledge/review/tasks/{task_id}/start`
- `POST /api/web/knowledge/review/tasks/{task_id}/complete`
- `POST /api/web/knowledge/review/tasks/{task_id}/dismiss`
- `POST /api/web/knowledge/review/generate`

Admin can manage all visible tasks. Support can manage allowed support-visible tasks. Auditor is read-only. Requester, public and agent surfaces have no access.

## Quality Score

`KnowledgeQualityService` computes explainable scores on demand and can persist snapshots in `knowledge_quality_snapshots`.

Dimensions:

- completeness;
- governance;
- safety;
- usefulness;
- freshness;
- coverage.

Output includes total score, grade, dimension values and issue objects with severity, code, message and suggested fix. The existing operations summary maps issue objects back to issue codes for older UI compatibility.

APIs:

- `GET /api/web/knowledge/items/{id}/quality`
- `GET /api/web/knowledge/quality/summary`
- `POST /api/web/knowledge/quality/recompute`
- compatibility summary: `GET /api/web/knowledge/quality`

## Gap Detection

`KnowledgeGapService` persists findings in `knowledge_gap_findings`.

Implemented gap sources:

- published Service Catalog offering without requester-safe published knowledge;
- published offering without support-internal runbook;
- high ticket volume without KB;
- high not-helpful feedback.

Findings include service/offering/template keys, gap type, severity, status, evidence, evidence hash and suggested action. Dismissed findings are not recreated immediately while the evidence hash is unchanged.

APIs:

- `GET /api/web/knowledge/gap-findings`
- `POST /api/web/knowledge/gaps/recompute`
- `POST /api/web/knowledge/gaps/{finding_id}/accept`
- `POST /api/web/knowledge/gaps/{finding_id}/dismiss`
- `POST /api/web/knowledge/gaps/{finding_id}/create-draft`

`create-draft` creates a draft item with service/offering binding and a `gap_candidate` review task.

## Rollout Policies

Existing rollout policies remain the self-service gate for requester and agent suggestions. Requester and agent suggestion calls honor effective rollout before search. Support workspace operations stay available when requester rollout is paused.

Operational rollback for deflection is to disable rollout globally or for a service/offering, not to remove knowledge content.

## Support Workflow

Support-facing knowledge operations use the same backend data as admin:

- read requester-safe and support-internal suggestions;
- see quality/freshness context;
- link/use knowledge through existing KB compatibility and feedback events;
- generate review tasks when knowledge is outdated;
- create article/runbook/known-error/workaround drafts from ticket or gap context.

Support must not receive `admin_internal` or `security_restricted` items through support endpoints.

## Agent And Requester Behavior

Requester `/app/help` and the Qt agent GUI continue to call `POST /api/knowledge/suggest` and `POST /api/knowledge/feedback`. Protocol V3 is unchanged.

If rollout is disabled or the knowledge API is unavailable, ticket creation continues. The agent must not cache support-internal content locally and must not display internal/source metadata. Safe `knowledge_attempts` can still be attached to ticket creation when the user continues after failed self-service.

## Search Analytics

Migration `086` adds `knowledge_search_events`.

`KnowledgeSearchAnalyticsService` records surface, actor role, service/offering context, result count and optional clicked item reference. Raw query text is not stored directly. Query hashes are stored, and `query_text_redacted` is limited to redacted text with email and explicit `device_id=` / `requester_id=` markers removed.

Zero-result and high-frequency query signals are intended to feed gap detection without exposing requester identifiers, device identifiers or raw custom fields.

## Security

Safety invariants:

- requester/public publication runs lint and blocks unsafe content;
- internal source refs cannot be exposed to requester/public content;
- runbooks and known errors default internal unless explicitly made requester-safe and lint passes;
- search, suggestions, direct reads, graph, ingestion, review, quality and gaps apply role visibility;
- requester/agent projections must not include internal ids, queue ids, device ids, requester ids, raw custom fields, internal graph/source refs or restricted chunks;
- content packs are not trusted blindly and still go through publish lint.

## UI

`/app/admin/knowledge` includes operations blocks for content packs, review tasks, quality, gap findings and rollout policies. The webapp API reads first-class review tasks from `/api/web/knowledge/review/tasks` and first-class gap findings from `/api/web/knowledge/gap-findings`, while preserving the older dashboard summary shape for rendering.

`/app/knowledge` remains support-facing and must not show admin-only content pack controls in support mode.

## Rollback

- Disable requester/agent deflection with rollout policy.
- Retire a content pack or rerun without `--force` to preserve admin edits.
- Archive generated or pack-managed items instead of hard-deleting linked content.
- Dismiss gap/review tasks with an auditable reason.
- Keep `ticket_kb_links` compatibility as fallback for existing ticket knowledge links.
- Alembic downgrade for migration `086` removes only P2.2 operations tables: review tasks/comments, quality snapshots, gap findings and search events.
