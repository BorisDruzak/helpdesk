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
It loads `DATABASE_URL` from the environment or `server/.env`; `--database-url` can override it for isolated maintenance runs.

Pack installs are idempotent. `KnowledgeContentPackService` records `knowledge_content_packs` and `knowledge_content_pack_items`, hashes pack source and item content, skips unchanged entries, reports conflicts when admin-edited content differs, updates only with explicit `--force`, and can archive pack-managed items missing from a newer pack when `--retire-missing` is supplied.

Requester-safe pack content is linted before publication. Unsafe requester/public text fails the item install instead of being published.

Baseline packs:

- `it-self-service-baseline` v2: requester-safe articles for VPN, password reset, mail, printer, laptop power and unknown category problem description, bound to the current Service Catalog baseline keys.
- `support-runbooks-baseline` v2: support-internal first-line diagnostic runbooks, bound to the current Service Catalog baseline keys.
- `known-errors-baseline`: generic internal draft placeholders for known error/workaround patterns without fake vendor facts.
- `glossary-baseline`: requester-safe glossary entries for VPN, MFA, SLA, OLA, access request, service offering, known error and workaround.

Canonical Service Catalog binding matrix for baseline content:

| Scenario | service_code | offering_code | request_template_key |
|---|---|---|---|
| VPN | `network` | `network.vpn_issue` | `network` |
| Internet | `network` | `network.internet_issue` | `network` |
| Password reset | `access` | `access.reset_password` | `access` |
| Grant access | `access` | `access.grant_access` | `access` |
| Mail | `mail` | `mail.mailbox_issue` | `mail_issue` |
| Printer | `workplace` | `workplace.printer_issue` | `printer` |
| Laptop | `workplace` | `workplace.laptop_broken` | `breakage` |
| Software | `workplace` | `workplace.software_install` | `software_install` |
| Other | `other` | `other.unknown` | `general_request` |

Validate pack bindings before seed or release:

```powershell
python scripts/validate_knowledge_pack_bindings.py --strict
python scripts/validate_knowledge_pack_bindings.py --strict --json
```

The validator loads `server/tickets/service_catalog_defaults.py`, parses `content_packs/knowledge/*.yaml`, and rejects unknown services, unknown or mismatched offerings, stale template keys such as `password_reset`, `laptop_issue`, `printer_issue`, `other_unknown` and stale full codes such as `communications.mail_issue`, `access.password_reset`, `workplace.laptop_issue` unless the live catalog explicitly defines them.

If packs were already installed before a binding correction, repair installed pack-managed bindings without overwriting article bodies:

```powershell
python scripts/repair_knowledge_pack_bindings.py --dry-run --all
python scripts/repair_knowledge_pack_bindings.py --all
python scripts/repair_knowledge_pack_bindings.py --dry-run --pack it-self-service-baseline
```

The repair path updates only pack-managed slugs from installed content-pack state, rewrites `knowledge_bindings` and binding graph edges to the pack YAML, records a `bindings_repaired` content-pack item audit with old/new bindings, and preserves item body/title/summary, versions, feedback and events. Rerunning the command is idempotent. Admin-edited article content is still protected by the normal seed conflict rules and is not overwritten without explicit `--force`.
It uses the same `DATABASE_URL` resolution as the seed script and also supports `--database-url`.

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

P4 Problem Management uses these templates and lint rules when creating known-error and workaround drafts from a problem. Problem-created drafts are support-internal by default and should be reviewed, linted and explicitly published before any requester-safe exposure.

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

Phase 14 quality model extension:

- `knowledge_quality_models` stores per-space or global scoring models with `weights` and `thresholds`; migration `119` enforces unique global `code`, one active default global model and one active default model per space.
- When a space has an active/default model, `GET /api/web/knowledge/quality` includes `quality_model` and adds metadata dimensions from model weights.
- `properties` weight is granted only when applicable required properties are present; otherwise issue code `missing_required_property:<code>` is emitted.
- `taxonomy` weight is granted when the item has at least one governed taxonomy term.
- `applicability` weight is granted when the item has explicit include/exclude applicability rules.
- The legacy completeness/governance/safety/usefulness/freshness/coverage dimensions remain backward-compatible.

## Metadata Model

Phase 14 adds governed metadata operations without changing requester/public projection:

- `knowledge_taxonomy_terms`: space-scoped category/product/audience/topic/tag terms.
- `knowledge_property_definitions`: typed property definitions with value type, allowed values, required flag, item-type applicability and optional quality weight.
- `knowledge_item_properties` and `knowledge_item_taxonomy_terms`: validated item metadata assignments. Assigned taxonomy terms keep their own visibility boundary; item metadata reads filter term rows by actor-visible visibility and metadata updates reject taxonomy terms whose visibility the actor cannot mutate.
- `knowledge_applicability_rules`: explicit include/exclude item applicability by service, offering, request template, role, device OS/family, audience, taxonomy term or custom scope.
- `knowledge_quality_models`: active/default scoring models.
- `GET /api/web/knowledge/metadata` returns all visible management rows plus `summary` total/active counts. Dashboard coverage must use active counts so draft/archived taxonomy terms and property definitions do not count as active model coverage.

APIs:

- `GET /api/web/knowledge/metadata`: admin/support/auditor read bundle.
- `POST /api/web/knowledge/taxonomy`: admin/support upsert taxonomy term; mutation checks the requested term `visibility` as well as the parent space, so support cannot create or escalate terms to `admin_internal` or `security_restricted`.
- `POST /api/web/knowledge/properties`: admin/support upsert property definition.
- `GET|PUT /api/web/knowledge/items/{item_id_or_slug}/metadata`: read/update item property values and taxonomy terms. Read responses hide assigned taxonomy terms the actor cannot read, even when the item itself is visible; updates reject hidden/admin-only taxonomy term assignment for support.
- `GET|POST /api/web/knowledge/items/{item_id_or_slug}/applicability`: read/replace applicability rules.
- `POST /api/web/knowledge/quality-models`: admin/support upsert quality model.

Phase 14C adds the first-class management editor:

- `/app/admin/knowledge/metadata` is the admin/support workbench for taxonomy terms, property definitions, applicability rules and quality models. It uses structured fields, typed selectors where available and Russian-first labels instead of raw JSON as the normal workflow.
- `/app/admin/knowledge/studio` includes item-level metadata tabs: `Таксономия`, `Свойства`, `Применимость` and `Качество`. The tabs call the same protected item metadata/applicability APIs and validate required properties, allowed values, item-type applicability and term visibility.
- Business taxonomy and property definitions are governed data, not frontend code constants. The optional default seed is `content_packs/knowledge/default_metadata.json`; apply it with `python scripts/seed_knowledge_metadata.py --dry-run` or `python scripts/seed_knowledge_metadata.py --apply`. The seed is idempotent, keeps existing admin edits unless `--force` is explicit and rejects requester-visible internal/security-classified defaults.
- Live validation evidence for this editor should create/update taxonomy, property, applicability and quality-model rows, then verify `/app/admin/knowledge`, requester `/app/kb/search`, public-compatible `/api/knowledge/search` and support `/app/knowledge` projections.

Requester/public endpoints (`/api/knowledge/search`, `/api/knowledge/suggest`, `/api/knowledge/ask`, portal article APIs and `/app/help`) must not include this admin metadata bundle, raw property diagnostics, applicability internals or quality model weights.

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

Revision `087` expands rollout policies from `enabled + rollout_percent` into an explicit self-service deflection policy:

- scope: `global`, `service`, `offering` or `template`;
- surface: `requester_portal`, `agent_gui`, `support_workspace`, `api` or `all`;
- visibility controls: `show_before_form`, `show_after_form`, `show_known_errors`, `show_quality_badge`, `show_review_freshness`;
- gating controls: `require_suggestions_before_submit`, `allow_skip`, `urgency_bypass`, `impact_bypass`, `min_suggestions`, `max_suggestions`;
- fallback controls: `no_suggestions_behavior` and `api_unavailable_behavior` as `allow_submit`, `show_message`/`show_warning` or `block_submit`;
- prompt/feedback controls: `deflection_prompt_enabled`, `feedback_required_on_article_view`;
- optional `bypass_roles`, `effective_from`, `effective_until`, `reason` and `metadata_json`.

Effective policy resolution order is template exact match, offering exact match, service exact match, global surface match, then global `all` surface match. Rollout percentage uses deterministic bucketing from stable request context, not per-request randomness. If the request is urgent or high impact and bypass is enabled, suggestions may still load but submit must not be blocked.

Requester and agent defaults are non-blocking: when the knowledge API is unavailable or suggestions are empty, ticket creation continues unless an admin explicitly configured a blocking behavior. Rollout never changes ACL or visibility filtering; requester and agent surfaces still receive only requester-safe published items.

`max_suggestions=0` is an explicit empty-result policy and does not force a minimum of one result. `min_suggestions` is enforced by requester and agent submit gates when the effective policy requires suggestions. When `show_known_errors=false`, `known_error` items are removed from the main `suggestions` list and from the `known_errors` bucket. Quality and freshness are returned only as requester-safe labels and are omitted when their rollout toggles are disabled.

Operational rollback for deflection is to disable rollout globally, disable it per service/offering/template, set `rollout_percent=0`, or set unavailable/no-suggestions behavior to `allow_submit`; do not remove knowledge content as a rollout rollback.

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

P2.2.1 requester and agent flows consume the effective rollout decision from `POST /api/knowledge/suggest`. `/app/help` applies `show_before_form`, `require_suggestions_before_submit`, `allow_skip`, `min_suggestions`, no-suggestions/API-unavailable behavior, known-error hiding, quality/freshness label toggles, urgent/high-impact bypass and `max_suggestions`. The Qt agent GUI sends urgency/impact context, reads the returned rollout, applies the same submit gate at wizard state level, and uses safe default `allow_submit` if the API is unavailable before a policy is known. Both surfaces keep create-ticket flow available by default when rollout disables suggestions, rollout bucket excludes the context, no suggestions are returned or the API is temporarily unavailable.

## Search Analytics

Migration `086` adds `knowledge_search_events`.

`KnowledgeSearchAnalyticsService` records surface, actor role, service/offering context, result count and optional clicked item reference. Raw query text is not stored directly. Query hashes are stored, and `query_text_redacted` is limited to redacted text with email and explicit `device_id=` / `requester_id=` markers removed.

Zero-result and high-frequency query signals are intended to feed gap detection without exposing requester identifiers, device identifiers or raw custom fields.

## P3 Quality Loop

P3 treats knowledge operations as one source of experience-quality evidence. Negative feedback, failed deflection (`ticket_created_after_view`) and CSAT reason `knowledge_article_failed` can trigger ticket QA reviews and continuous-improvement actions, while `/api/web/quality/service-quality` aggregates failed knowledge attempt counts by service/offering/period.

The boundary remains explicit: Knowledge Operations owns article review, gap findings, content packs, rollout and quality scores; Quality Loop owns ticket CSAT, reopen events, QA review queue, improvement actions and aggregate service/offering quality snapshots. Requester/public quality responses must not expose internal article metadata, source refs, knowledge review notes or raw feedback comments in aggregate analytics.

## Security

Safety invariants:

- requester/public publication runs lint and blocks unsafe content;
- internal source refs cannot be exposed to requester/public content;
- runbooks and known errors default internal unless explicitly made requester-safe and lint passes;
- search, suggestions, direct reads, graph, ingestion, review, quality and gaps apply role visibility;
- requester/agent projections must not include internal ids, queue ids, device ids, requester ids, raw custom fields, internal graph/source refs or restricted chunks;
- content packs are not trusted blindly and still go through publish lint.

## UI

`/app/admin/knowledge` includes operations blocks for content packs, review tasks, quality, gap findings and structured rollout policies. The rollout editor uses first-class fields instead of raw JSON for scope/surface, enabled percent, gating, bypass, max/min suggestions, known-error/quality/freshness labels and fallback behavior. The webapp API reads first-class review tasks from `/api/web/knowledge/review/tasks` and first-class gap findings from `/api/web/knowledge/gap-findings`, while preserving the older dashboard summary shape for rendering.

`/app/knowledge` remains support-facing and must not show admin-only content pack controls in support mode.

## Knowledge vNext Operations

Knowledge vNext добавляет продуктовые поверхности постепенно. До реализации конкретной фазы целевые маршруты из `KNOWLEDGE_PLATFORM.md` остаются задокументированными границами, а не обязательством runtime route registration.

Операционные правила для всех фаз:

- пользовательские тексты, safe display errors, empty states, toasts, health-check results и инструкции live-проверок пишутся на русском;
- route paths, API field names, enum values, observer event codes, metric names и task codes остаются английскими техническими контрактами;
- OpenRouter key вводится только через утверждённый secret/config path и в UI показывается только masked state;
- browser/live evidence не должен содержать raw API keys, tokens, cookies, prompts с restricted content или внутренние ACL-only article bodies;
- каждая UI-фаза должна иметь browser evidence с проверкой русских labels и отсутствия mojibake;
- AI-off mode является обязательной операционной проверкой для search, portal, authoring, graph и helpdesk linking.

## Rollback

- Disable requester/agent deflection with rollout policy.
- Retire a content pack or rerun without `--force` to preserve admin edits.
- Archive generated or pack-managed items instead of hard-deleting linked content.
- Dismiss gap/review tasks with an auditable reason.
- Disable P3 quality triggers/prompts if quality-loop rollout needs to pause; keep existing knowledge feedback and gaps read-only.
- Keep `ticket_kb_links` compatibility as fallback for existing ticket knowledge links.
- Alembic downgrade for migration `086` removes only P2.2 operations tables: review tasks/comments, quality snapshots, gap findings and search events.
- Alembic downgrade for migration `087` removes rollout hardening columns and restores the previous rollout/content-pack audit status constraints.
