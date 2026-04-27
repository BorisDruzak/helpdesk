# Observer Coverage Closure And Agent Telemetry Channel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the current observer blind spots and add a narrow agent telemetry channel so support operators and Codex can diagnose auth, update, module, playbook, web API and agent-side failures from one server-side observer surface.

**Architecture:** Keep the server observer as the single query surface. The agent keeps its local `action_trace.jsonl` black box, but uploads selected bounded/redacted events to the server; the server stores those events as source rows and projects them into the existing `observer_traces`, `observer_spans`, signatures and degradations. Do not create a second independent observer UI or separate truth model inside the agent.

**Tech Stack:** Python/aiohttp server, SQLAlchemy async/PostgreSQL, existing `observer/*` projector, existing Protocol V3 agent websocket, React webapp observer UI, pytest/vitest/browser checks.

---

## Context Snapshot

The repository must be edited in the local Windows working copy:

- `C:\Users\admin-2\CodexProjects\pc_client`

The Linux copy `/var/chat_bot/pc_client` is a deploy/live stand, not the editing source. Browser checks use:

- `http://192.168.100.17:8666/app/admin/observer`
- canonical admin base from project docs: `http://192.168.100.17:8666/admin`

Relevant docs and maps:

- `docs/QUICK_LOOKUP.md`
- `server/docs/CODEMAP.md`
- `pc_agent/docs/CODEMAP.md`
- `server/docs/OBSERVER_LAYER.md`
- `server/docs/OBSERVER_AUTHORING_RULES.md`
- `pc_agent/docs/AUTHENTICATION.md`
- `pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md`
- `pc_agent/docs/SELF_UPDATE.md`
- `pc_agent/docs/AGENT_UPDATE_WORKFLOW.md`

Before broad code changes:

```powershell
.\scripts\bootstrap_shell_utf8.ps1
python scripts/task_intake.py --task "observer coverage closure agent telemetry playbook module reconcile web auth diagnostics"
```

Before frontend commands:

```powershell
python scripts/bootstrap_web_toolchain.py
```

Before completion claims:

```powershell
python scripts/verify_workspace.py
```

---

## Current Observer Model

Current server observer source rows:

- `operations`
- `ticket_events`
- `device_events`
- `agent_runtime_audit`
- manually materialized module live-test/preferred-gate observer rows
- optional agent `action_trace` fetched through diagnostics bundle / trace detail

Current server observer materialized tables:

- `observer_traces`
- `observer_spans`
- `observer_span_links`
- `observer_error_signatures`
- `observer_error_occurrences`

Current important API surfaces:

- `GET /api/web/admin/observer/quick`
- `GET /api/web/admin/observer/traces`
- `GET /api/web/admin/observer/traces/{trace_id}`
- `GET /api/web/admin/observer/diagnostics/bundle`
- `GET /api/web/admin/observer/runtime`
- `GET /api/web/admin/observer/signatures`
- `GET /api/web/admin/observer/degradations`
- legacy equivalents under `/api/admin/tech/*`
- ticket observer summary: `GET /api/tickets/{ticket_id}/observer`

Current known root kinds:

- `ticket`
- `tool_call`
- `command`
- `agent_update`
- `device_provisioning`
- `agent_auth`
- `agent_runtime`
- `module_install`
- `module_update`
- `module_remove`
- `module_live_test`
- `module_preferred_gate`
- `consent`
- `ws_delivery`
- `retry_exhausted`

Live check performed on 2026-04-27 showed:

- `/app/admin/observer` loads with no browser console errors.
- Typed observer endpoints return `200`.
- Observer runtime health is `ok`.
- Real traces exist for `agent_auth`, `device_provisioning`, `agent_update`, `module_live_test`.
- Recent logs include problems that are not first-class traces:
  - `[reconcile] Failed to enqueue install ... Agent not connected`
  - `[AuthMiddleware] Authentication failed: path=/api/tickets`

The server was stopped after the live check with:

```powershell
python scripts/manage_remote_stack.py stop server
```

---

## Known Blind Spots To Close

1. **Module reconcile log-only failures**
   - Source: `server/modules/reconcile.py`
   - Problem: desired-state install/remove failures before a normal operation may only be logged.
   - Required outcome: module reconcile failures become signatures/degradations and appear as `module_reconcile`, `module_install` or `module_remove` observer traces.

2. **Playbook run and local step visibility**
   - Source: `server/app/services/playbook_engine.py`, `server/app/repos/playbook_repo.py`
   - Problem: operation-backed playbook steps are visible through `operations`, but local `decision`, `transform`, `report`, skipped `if_expr`, and pre-enqueue `module_install` / `capability_gate` failures are only `playbook_step_run` rows.
   - Required outcome: playbook run is a first-class observer root with step spans and exact failed step.

3. **Web auth / API boundary failures**
   - Source: `server/auth/middleware.py`, `server/web_api/*`
   - Problem: repeated 401/403/session/API-boundary failures can remain log-only.
   - Required outcome: important repeated auth/API failures are rate-limited audit events and searchable observer signatures.

4. **Agent before handshake, crash, launcher/update local failures**
   - Source: `pc_agent/ws_agent.py`, `pc_agent/ws_agent_runtime_helpers.py`, `pc_agent/core/action_trace.py`, update launcher flow.
   - Problem: if the agent fails before reporting through normal operation result paths, server sees stale/offline or last known state, but not the local cause.
   - Required outcome: the agent uploads compact local telemetry after reconnect or during authenticated session.

5. **Agent action trace is optional and pull-based**
   - Source: `server/tech/handlers.py`, `pc_agent/core/action_trace.py`
   - Problem: action trace is currently fetched through diagnostics bundle/trace detail and may not be materialized unless explicitly requested.
   - Required outcome: selected critical telemetry is pushed/batched to server and projected automatically.

6. **Observer runtime self-health is not trace-visible enough**
   - Source: `server/observer/runtime.py`
   - Problem: runtime endpoint shows health/backlog, but projector lag or last_error is not itself a trace/signature.
   - Required outcome: observer self-health creates a visible system event/signature when degraded.

---

## Core Design Decision: Agent Telemetry Channel

Add a narrow agent observer/telemetry channel, but keep the server observer authoritative.

Agent responsibilities:

- continue writing local `action_trace.jsonl`;
- maintain a small durable upload cursor/queue;
- upload selected event types after successful auth/handshake or over the existing authenticated websocket;
- redact secrets before upload;
- retry with idempotency keys;
- never block normal agent work because telemetry upload failed.

Server responsibilities:

- validate event schema and event type allowlist;
- reject or truncate oversized attrs;
- store normalized source rows;
- project events into the existing observer graph;
- expose them through existing observer UI/API;
- apply retention and sampling settings.

Why not keep it only local:

- support and Codex cannot diagnose offline/reconnect/update history without remote evidence;
- local-only trace is lost when the user cannot access the machine;
- cross-device degradations/signatures require server aggregation.

Why not build a second observer inside the agent:

- two query surfaces will diverge;
- UI and Codex would need to search two systems;
- server-side playbook/module/update traces still need one graph.

---

## Proposed Data Contract

Create a server-side source model named `AgentObserverEvent` unless implementation finds an existing better source table.

Suggested columns:

```python
class AgentObserverEvent(Base):
    __tablename__ = "agent_observer_events"

    id: Mapped[int]
    event_id: Mapped[str]              # stable idempotency key from agent
    device_id: Mapped[str]
    install_id: Mapped[Optional[str]]
    machine_id: Mapped[Optional[str]]
    agent_seq: Mapped[Optional[int]]
    trace_id: Mapped[Optional[str]]
    operation_id: Mapped[Optional[str]]
    ticket_id: Mapped[Optional[str]]
    playbook_run_id: Mapped[Optional[int]]
    playbook_step_run_id: Mapped[Optional[int]]
    root_kind: Mapped[str]             # agent_runtime, agent_update, tool_call, module_install
    event_type: Mapped[str]            # agent.startup, agent.ws.reconnect, agent.tool.step, ...
    severity: Mapped[str]              # info, warning, error, critical
    component: Mapped[str]             # agent, launcher, websocket, tool, module
    stage: Mapped[Optional[str]]
    status: Mapped[Optional[str]]
    tool_name: Mapped[Optional[str]]
    module_name: Mapped[Optional[str]]
    started_at: Mapped[Optional[datetime]]
    finished_at: Mapped[Optional[datetime]]
    duration_ms: Mapped[Optional[int]]
    attrs_json: Mapped[dict]
    created_at: Mapped[datetime]       # agent event timestamp
    received_at: Mapped[datetime]      # server ingest timestamp
```

Indexes:

- unique `event_id`
- `(device_id, created_at)`
- `(trace_id)`
- `(operation_id)`
- `(event_type, created_at)`
- `(severity, created_at)`
- `(root_kind, created_at)`

Allowed initial event types:

- `agent.startup`
- `agent.shutdown`
- `agent.crash_detected`
- `agent.ws.connecting`
- `agent.ws.connected`
- `agent.ws.reconnect`
- `agent.ws.handshake_sent`
- `agent.update.check`
- `agent.update.launcher`
- `agent.update.apply`
- `agent.tool.step`
- `agent.module.install_step`
- `agent.module.activate`
- `agent.telemetry.upload_failed`

Redaction rule:

- no raw token, password, cookie, consent token, connection token, private key or full command output;
- keep token hash prefixes only when server already uses the same pattern;
- attrs should be structured and compact; large logs/artifacts must go through artifact service, not attrs.

---

## Files To Touch

Server model/migration:

- `server/app/db/models.py`
- new Alembic migration under `server/app/db/migrations/versions/`
- new repo: `server/app/repos/agent_observer_events_repo.py`

Server ingest:

- `server/websocket/agent_services.py` or `server/websocket/agent_handler.py`
- `server/routes.py`
- optional HTTP fallback handler under `server/agents/` or `server/api/`

Server observer:

- `server/observer/service.py`
- `server/observer/runtime.py`
- `server/tech/handlers.py`
- `server/web_api/admin_handlers.py`
- `server/app/repos/observer_settings_repo.py` if retention/sampling settings need extension

Playbook observer:

- `server/app/services/playbook_engine.py`
- `server/app/repos/playbook_repo.py`
- `server/app/db/models.py`

Module reconcile observer:

- `server/modules/reconcile.py`
- `server/modules/handlers.py` only if live-test/preferred-gate attrs need alignment

Web auth/API observer:

- `server/auth/middleware.py`
- `server/app/db/models.py`
- possible repo: `server/app/repos/web_runtime_audit_repo.py`

Agent telemetry:

- `pc_agent/core/action_trace.py`
- `pc_agent/core/database.py` if a durable queue table is needed
- `pc_agent/core/orchestrator.py`
- `pc_agent/ws_agent.py`
- `pc_agent/ws_agent_runtime_helpers.py`
- update launcher related files from `pc_agent/docs/SELF_UPDATE.md`

Frontend:

- `webapp/src/features/tech/observer-workbench-api.ts`
- `webapp/src/features/tech/observer-trace-drilldown.tsx`
- `webapp/src/pages/admin/observer-page.tsx`
- observer tests under `webapp/src/features/tech/*.test.ts*`

Docs:

- `server/docs/OBSERVER_LAYER.md`
- `server/docs/OBSERVER_AUTHORING_RULES.md`
- `server/docs/CODEMAP.md`
- `pc_agent/docs/CODEMAP.md`
- `docs/QUICK_LOOKUP.md`
- `PLANS.md`

---

## Task 1: Coverage Matrix And Tests For Existing Gaps

**Files:**

- Create: `server/tests/test_observer_coverage_gaps.py`
- Modify: `server/docs/OBSERVER_LAYER.md`
- Modify: `docs/QUICK_LOOKUP.md`

- [ ] **Step 1: Write coverage matrix in docs**

Add a section to `server/docs/OBSERVER_LAYER.md` named `Coverage Matrix`. It must list each flow, current source, target root_kind and whether it has spans/signatures/diagnostics bundle coverage:

```markdown
| Flow | Source row | Target root_kind | Spans | Signatures | Bundle search |
| --- | --- | --- | --- | --- | --- |
| Agent invalid token | agent_runtime_audit | agent_auth | yes | yes | q=invalid_token |
| Module reconcile enqueue failure | agent_runtime_audit or module_reconcile audit | module_reconcile | planned | planned | q=reconcile |
| Playbook skipped decision | playbook_step_run | playbook_run | planned | no unless failed | playbook_run_id |
| Web auth route failure | web_runtime_audit | web_auth | planned | planned | route=/api/... |
| Agent crash before reconnect | agent_observer_events | agent_runtime | planned | planned | device_id |
```

- [ ] **Step 2: Write failing tests for current gaps**

Create `server/tests/test_observer_coverage_gaps.py` with tests that initially demonstrate no first-class trace for:

- module reconcile enqueue failure;
- playbook pre-enqueue step failure;
- repeated web auth failure;
- agent telemetry event ingestion after the model is introduced in later tasks.

The first version can mark future model-dependent tests with imports guarded by local helpers, but each implemented task must remove the corresponding failing expectation.

- [ ] **Step 3: Run focused tests**

```powershell
python -m pytest server/tests/test_observer_coverage_gaps.py -q
```

Expected at this stage: failures that describe missing implementation, not import/runtime crashes.

---

## Task 2: Agent Telemetry Source Table And Repository

**Files:**

- Modify: `server/app/db/models.py`
- Create: `server/app/repos/agent_observer_events_repo.py`
- Create: Alembic migration under `server/app/db/migrations/versions/`
- Test: `server/tests/test_agent_observer_events_repo.py`

- [ ] **Step 1: Add model**

Add `AgentObserverEvent` with the data contract above. Keep field names explicit and JSON payload redacted before persistence.

- [ ] **Step 2: Add repository**

Implement:

```python
class AgentObserverEventsRepo:
    async def ingest_batch(self, *, device_id: str, events: list[dict]) -> list[AgentObserverEvent]:
        ...

    async def list_recent(self, *, device_id: str | None = None, trace_id: str | None = None, limit: int = 100) -> list[AgentObserverEvent]:
        ...
```

Repository rules:

- dedupe by `event_id`;
- clamp batch size to a safe cap, for example 100 events;
- normalize severity to `info|warning|error|critical`;
- normalize root_kind to an allowlist;
- call `redact_sensitive_payload` before storing `attrs_json`.

- [ ] **Step 3: Add tests**

Test cases:

- duplicate `event_id` is idempotent;
- raw sensitive attrs are redacted;
- unsupported severity becomes `info`;
- batch cap is enforced;
- listing by `device_id` and `trace_id` works.

- [ ] **Step 4: Run tests**

```powershell
python -m pytest server/tests/test_agent_observer_events_repo.py -q
```

Expected: pass.

---

## Task 3: Server Ingestion API For Agent Telemetry

**Files:**

- Modify: `server/websocket/agent_services.py` or `server/websocket/agent_handler.py`
- Modify: `server/routes.py` only if adding HTTP fallback
- Test: `server/tests/test_agent_observer_ingest_api.py`

- [ ] **Step 1: Choose transport**

Preferred transport: existing authenticated agent websocket. Add a command/event envelope such as:

```json
{
  "type": "agent_observer_batch",
  "device_id": "device-id-from-token",
  "events": [
    {
      "event_id": "device:seq:hash",
      "event_type": "agent.ws.reconnect",
      "severity": "warning",
      "root_kind": "agent_runtime",
      "created_at": "2026-04-27T17:00:00Z",
      "attrs_json": {"attempt": 3, "reason": "connection_lost"}
    }
  ]
}
```

Server must ignore payload `device_id` as source of truth and use authenticated session device id.

- [ ] **Step 2: Implement ingest handler**

Handler behavior:

- reject unauthenticated ingest;
- reject invalid schema with a compact error response;
- persist valid events through `AgentObserverEventsRepo`;
- enqueue observer projection for affected trace ids or synthetic runtime trace ids;
- return count accepted/deduped/rejected.

- [ ] **Step 3: Add tests**

Test cases:

- authenticated agent can ingest telemetry;
- payload device id spoofing does not change stored `device_id`;
- invalid event type is rejected or downgraded according to schema rule;
- duplicate batch is idempotent.

- [ ] **Step 4: Run tests**

```powershell
python -m pytest server/tests/test_agent_observer_ingest_api.py -q
```

Expected: pass.

---

## Task 4: Project Agent Telemetry Into Observer

**Files:**

- Modify: `server/observer/service.py`
- Modify: `server/observer/runtime.py`
- Test: `server/tests/test_observer_agent_telemetry_projection.py`

- [ ] **Step 1: Add telemetry source collection**

Extend projection source model with `agent_observer_events`. Candidate trace discovery must include:

- direct `trace_id`;
- linked `operation_id`;
- synthetic runtime trace id when no trace/operation exists.

- [ ] **Step 2: Add span projection**

Each telemetry row becomes an observer span:

- `source_type="agent_observer_event"`
- `component` from event component;
- `event_type` from telemetry event;
- `status` from telemetry status/severity;
- parent span is operation span when linked, otherwise root span.

- [ ] **Step 3: Add occurrences/signatures**

Warning/error/critical telemetry should produce `ObserverErrorOccurrence` with stable signatures based on:

- `event_type`
- `component`
- `module_name` or `tool_name`
- `stage`
- normalized message/reason from attrs.

- [ ] **Step 4: Add runtime discovery**

`ObserverRefreshRuntime` must discover recent telemetry events and enqueue corresponding trace ids.

- [ ] **Step 5: Run tests**

```powershell
python -m pytest server/tests/test_observer_agent_telemetry_projection.py -q
python -m pytest server/tests/test_observer_v2_api.py -q
```

Expected: pass.

---

## Task 5: Agent Local Telemetry Queue And Upload

**Files:**

- Modify: `pc_agent/core/action_trace.py`
- Modify: `pc_agent/core/database.py` if persistent queue needs SQLite
- Modify: `pc_agent/ws_agent.py`
- Modify: `pc_agent/ws_agent_runtime_helpers.py`
- Test: relevant `pc_agent/tests/` or existing agent test location

- [ ] **Step 1: Extend action trace recorder**

Add a method that returns compact upload-ready events from local action trace records:

```python
def export_observer_events(*, after_seq: int | None, limit: int = 100) -> list[dict]:
    ...
```

Mapping:

- trace category `runtime` -> `agent_runtime`;
- update records -> `agent_update`;
- module install records -> `module_install`;
- tool execution records -> `tool_call`.

- [ ] **Step 2: Add upload cursor**

Store last uploaded action trace sequence/event id in a durable local location. If SQLite is already the cleanest place, use `pc_agent/core/database.py`; otherwise use a compact JSON state file next to action trace.

- [ ] **Step 3: Upload after authenticated session**

After successful handshake, periodically send bounded batches. Upload must be best-effort:

- failure logs locally;
- no crash if server rejects telemetry;
- retry later using the same event ids.

- [ ] **Step 4: Instrument critical agent events**

Ensure events exist for:

- startup;
- shutdown when graceful;
- reconnect attempt;
- handshake sent/result;
- update check/apply/launcher result;
- tool step;
- module install/activate step.

- [ ] **Step 5: Add tests**

Test:

- redaction happens before upload;
- event ids are stable;
- failed upload does not advance cursor;
- successful upload advances cursor;
- upload batch is capped.

---

## Task 6: Playbook Run And Step Projection

**Files:**

- Modify: `server/observer/service.py`
- Modify: `server/observer/runtime.py`
- Modify: `server/app/services/playbook_engine.py`
- Modify: `server/app/repos/playbook_repo.py`
- Test: `server/tests/test_observer_playbook_projection.py`

- [ ] **Step 1: Add candidate discovery for playbook runs**

Observer filters should accept:

- `playbook_run_id`
- `playbook_step_run_id`

If adding new fields to `TraceOverlayFilters`, update all typed API handlers that serialize/parse filters.

- [ ] **Step 2: Create `root_kind=playbook_run`**

Root trace attrs should include:

- `playbook_run_id`
- `playbook_version_id`
- `device_id`
- `trigger_type`
- `status`
- `error_code`

- [ ] **Step 3: Create spans for every step_run**

Span attrs:

- `playbook_step_run_id`
- `step_key`
- `step_type`
- `operation_id`
- `tool_name`
- `input_json` redacted/trimmed
- `output_json` summarized/trimmed
- `error_json` redacted

- [ ] **Step 4: Link operation-backed steps**

If step has `operation_id`, link its playbook step span to the operation trace/span.

- [ ] **Step 5: Add tests**

Test:

- skipped decision is visible as span;
- pre-enqueue module install failure is visible as error occurrence;
- operation-backed step links to operation trace;
- diagnostics bundle can search by `playbook_run_id`.

---

## Task 7: Module Reconcile Observer Coverage

**Files:**

- Modify: `server/modules/reconcile.py`
- Modify: `server/observer/service.py` only if new root_kind classification is needed
- Test: `server/tests/test_observer_module_reconcile.py`

- [ ] **Step 1: Add audit writes for pre-operation failures**

When reconcile skips/fails because of:

- module missing in registry;
- archive missing on disk;
- platform mismatch;
- agent not connected;
- enqueue failure;

write a structured runtime/system audit row with:

```python
details_json={
    "module_name": module_name,
    "module_version": desired_version,
    "stage": "reconcile",
    "reason": "...",
    "error_kind": "...",
}
```

- [ ] **Step 2: Classify reconcile failures**

Target root_kind:

- use `module_reconcile` if adding a new root kind;
- or map to `module_install` / `module_remove` with `source=reconcile`.

Preferred: add `module_reconcile` so operators can distinguish desired-state controller failures from explicit module installs.

- [ ] **Step 3: Add tests**

Test:

- offline agent reconcile creates observer-searchable trace;
- missing package creates signature;
- query `q=reconcile` returns trace;
- diagnostics bundle for `q=reconcile` returns recent logs only as fallback, not as sole evidence.

---

## Task 8: Web Auth And API Boundary Observer Coverage

**Files:**

- Modify: `server/auth/middleware.py`
- Create optional repo/model for `web_runtime_audit`
- Modify: `server/observer/service.py`
- Test: `server/tests/test_observer_web_auth.py`

- [ ] **Step 1: Add rate-limited audit**

For important 401/403 failures, write structured audit rows grouped by:

- route pattern;
- method;
- auth state: missing token, invalid session, forbidden role;
- actor role if known;
- user/session id if safe and available.

Do not write one DB row for every noisy unauthenticated request. Add rate limiting or aggregation window.

- [ ] **Step 2: Project as `root_kind=web_auth`**

Create synthetic observer traces for actionable web auth/API failures.

- [ ] **Step 3: Add diagnostics bundle support**

Bundle should accept:

- `route=/api/web/...`
- `root_kind=web_auth`
- `q=AUTH_REQUIRED`
- `q=FORBIDDEN`

- [ ] **Step 4: Add tests**

Test:

- repeated 401 is aggregated/rate-limited;
- 403 forbidden role creates searchable signature;
- normal successful auth does not create noisy warning trace.

---

## Task 9: Observer Runtime Self-Health Trace

**Files:**

- Modify: `server/observer/runtime.py`
- Modify: `server/observer/service.py`
- Test: `server/tests/test_observer_runtime_health_trace.py`

- [ ] **Step 1: Emit self-health event**

When runtime status becomes degraded because of:

- `last_error`;
- `pending_backlog`;
- `projection_lag`;

write a bounded system event/audit row.

- [ ] **Step 2: Project as `root_kind=observer_runtime`**

This trace should appear in quick/dangerous flows only when degraded.

- [ ] **Step 3: Add diagnostics recommendations**

Diagnostics bundle should add recommendations:

- check runtime status;
- rebuild traces if projection stale;
- inspect projector logs.

---

## Task 10: UI/API Expansion

**Files:**

- Modify: `server/web_api/admin_handlers.py`
- Modify: `server/tech/handlers.py`
- Modify: `webapp/src/features/tech/observer-workbench-api.ts`
- Modify: `webapp/src/features/tech/observer-trace-drilldown.tsx`
- Modify: `webapp/src/pages/admin/observer-page.tsx`
- Test: `webapp/src/features/tech/observer-workbench-api.test.ts`

- [ ] **Step 1: Extend filter DTOs**

Support:

- `root_kind=playbook_run`
- `root_kind=module_reconcile`
- `root_kind=web_auth`
- `root_kind=observer_runtime`
- `playbook_run_id`
- `step_run_id`
- `route`

- [ ] **Step 2: Show source badges**

Trace cards/detail should show whether evidence came from:

- operation;
- runtime audit;
- playbook step;
- agent telemetry;
- web auth audit;
- log fallback.

- [ ] **Step 3: Add tests**

Vitest should verify:

- new filters are serialized;
- new root_kind labels render;
- trace detail renders agent telemetry and playbook step spans.

Commands:

```powershell
python scripts/bootstrap_web_toolchain.py
pnpm --dir webapp run test -- observer
pnpm --dir webapp run build
```

---

## Task 11: Docs, Canaries And Live Verification

**Files:**

- Modify: `server/docs/OBSERVER_LAYER.md`
- Modify: `server/docs/OBSERVER_AUTHORING_RULES.md`
- Modify: `server/docs/CODEMAP.md`
- Modify: `pc_agent/docs/CODEMAP.md`
- Modify: `docs/QUICK_LOOKUP.md`
- Create or extend observer canary script under `scripts/`

- [ ] **Step 1: Update docs**

Docs must explain:

- agent telemetry channel;
- source rows and root kinds;
- how Codex should query diagnostics bundle;
- which failures are expected to be first-class traces;
- what remains log-only by design.

- [ ] **Step 2: Add canaries**

Add live canaries for:

- Linux agent startup telemetry;
- Linux agent tool telemetry;
- module reconcile offline failure;
- playbook preflight failure;
- web auth repeated failure;
- observer runtime health endpoint.

- [ ] **Step 3: Run local verification**

```powershell
python -m pytest server/tests/test_observer_diagnostics_api.py -q
python -m pytest server/tests/test_observer_v2_api.py -q
python -m pytest server/tests/test_playbook_scenarios_no_db.py -q
python scripts/verify_workspace.py
```

- [ ] **Step 4: Run live Linux verification**

```powershell
python scripts/deploy_workspace_to_remote.py
python scripts/release_server_to_remote.py
python scripts/manage_remote_stack.py start server
python scripts/manage_remote_stack.py smoke server
```

Browser:

- open `http://192.168.100.17:8666/app/admin/observer`;
- confirm runtime health;
- confirm new root_kind filters;
- run or inspect canary traces;
- verify no console errors and observer endpoints return 200.

Stop server after checks unless the user explicitly asks to keep it running:

```powershell
python scripts/manage_remote_stack.py stop server
```

---

## Acceptance Criteria

This work is complete when:

- module reconcile offline/missing package failures are first-class observer traces/signatures;
- playbook local/skipped/preflight-failed steps are visible as spans under a playbook trace;
- web auth/API boundary failures are queryable and rate-limited;
- agent startup/reconnect/update/tool/module telemetry reaches server after reconnect and projects into observer;
- diagnostics bundle can answer by `device_id`, `trace_id`, `operation_id`, `playbook_run_id`, `step_run_id`, `route` and key text queries;
- `/app/admin/observer` shows new root kinds and trace sources without frontend errors;
- docs and CODEMAP are updated;
- local tests, workspace verification and live Linux checks pass;
- Windows telemetry is not claimed complete until a Windows lab agent live canary passes.

---

## Handoff Summary For A New Session

Start by reading this file, then run:

```powershell
.\scripts\bootstrap_shell_utf8.ps1
python scripts/task_intake.py --task "observer coverage closure agent telemetry"
Get-Content docs/QUICK_LOOKUP.md
Get-Content server/docs/OBSERVER_LAYER.md
Get-Content server/docs/OBSERVER_AUTHORING_RULES.md
```

Then inspect these entrypoints:

```powershell
rg "class TraceOverlayFilters|AgentRuntimeAudit|ObserverTrace|project_trace|_candidate_trace_ids" server/observer server/app/db/models.py -n
rg "playbook_run_id|PlaybookStepRun|create_step_run|module_install|capability_gate" server/app/services server/app/repos server/app/db/models.py -n
rg "Failed to enqueue install|reconcile" server/modules/reconcile.py -n
rg "Authentication failed|require_auth|AUTH_REQUIRED|FORBIDDEN" server/auth server/web_api -n
rg "action_trace|trace_span|trace_event|handshake|update" pc_agent -n
```

Do not begin with UI. First make source rows and projection reliable; the UI should only render what the server can already prove.
