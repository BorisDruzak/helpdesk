# Agent/Server Contract Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the agent/server WebSocket contract so reconnect races, synchronous waiters, per-agent execution ordering, control-command latency, and high-rate outbox traffic behave predictably under load without regressing Protocol V3 compatibility.

**Architecture:** Implement the work in correctness-first phases. First make server runtime state reconnect-safe, then decouple synchronous waiters from socket-local metadata, then add an explicit agent execution scheduler and server-side dispatch priorities. Only after phases 1-4 are green should we consider negotiated wire batching as an optional throughput phase behind a new capability flag.

**Tech Stack:** Python 3.12, aiohttp WebSocket, asyncio, SQLAlchemy/PostgreSQL, SQLite/aiosqlite, pytest, project deploy scripts, Playwright MCP browser checks on the canonical admin URL.

---

## Scope and sequencing

- Phases 1-4 are mandatory correctness work and should ship before any protocol throughput optimization.
- Phase 5 (wire batching) is optional and should be gated behind explicit capability negotiation so old agents/servers continue to interoperate.
- Every phase must leave the system in a deployable state with focused tests, workspace verification, and at least one live validation scenario.
- Do not mix reconnect-safety refactors with queue-priority DB changes in the same commit unless the test coverage for both phases is already green and isolated.

## Implementation snapshot (2026-04-21)

- Reconnect-safe runtime ownership and state-level waiter registry are implemented.
- Agent `run_tool` execution is now lane-aware: risky/stateful tools serialize, safe reads keep limited parallelism, queued operations remain cancelable.
- `device_outbox` priority ordering shipped without schema change: dispatch lane is derived from `command` (`cancel_operation` -> update -> control/health -> FIFO).
- Optional wire batching also shipped behind `outbox_batch_v1`; both sides fall back to single `outbox_item` frames when capability negotiation does not enable batching.

## Planned file map

- `server/state_manager.py`
  Runtime connection registry plus new command waiter registry that survives reconnect.
- `server/websocket/agent_handler.py`
  Safe disconnect logic that unregisters only the currently active socket/session.
- `server/websocket/agent_handshake.py`
  Runtime metadata enrichment with connection/session identity and replacement handling.
- `server/websocket/protocol.py`
  `send_ws_command` waiter registration, timeout cleanup, and command priority assignment.
- `server/websocket/command_result_components.py`
  Resolve waiters through a state-level registry instead of connection metadata.
- `server/websocket/device_outbox_sender.py`
  Dispatch drain ordering validation and priority-aware smoke assertions.
- `server/app/repos/device_outbox_repo.py`
  Priority-aware outbox ordering and ready-queue interaction.
- `server/app/services/operation_service.py`
  Priority assignment for `approve_consent()` re-enqueue path and cancel/update workflows.
- `server/tools/service.py`
  Default run-tool priority and any supporting transport metadata.
- `pc_agent/ws_agent.py`
  Incoming command scheduling, queue admission, reconnect-safe command execution flow.
- `pc_agent/core/orchestrator.py`
  Tool execution integration with the scheduler and `running_tasks` lifecycle.
- `pc_agent/core/sender.py`
  Optional batched outbox transport after correctness phases are complete.
- `pc_agent/core/database.py`
  Only if Task 5 ships: persist any batching-related cursor metadata that cannot remain purely in memory.
- `server/docs/PROTOCOL_V3.md`
  Contract updates for reconnect-safe waiter behavior, command priority, and optional batching capability.
- `pc_agent/docs/PROTOCOL_V3.md`
  Agent-side contract updates.
- `server/docs/CODEMAP.md`
  New runtime responsibilities and queue components.
- `pc_agent/docs/CODEMAP.md`
  New scheduler/runtime boundaries.
  Updated navigation hints for reconnect safety, command waiters, scheduler, and priority dispatch.

## Test inventory to add or extend

- Create: `server/tests/test_ws_reconnect_safety.py`
- Create: `server/tests/test_ws_command_waiters.py`
- Create: `server/tests/test_device_outbox_priority.py`
- Create: `pc_agent/tests/test_command_scheduler.py`
- Create: `pc_agent/tests/test_outbox_batch_transport.py` (Phase 5 only)
- Modify: `server/tests/test_agent_disconnect_runtime_audit.py`
- Modify: `server/tests/test_device_dispatch_integration.py`
- Modify: `server/tests/test_tool_dispatch_failure.py`
- Modify: `server/tests/test_agent_services_pipeline.py`
- Modify: `server/tests/test_integration_p0.py` if an existing command-result idempotency test can be extended instead of duplicated

### Task 1: Make duplicate same-device reconnects safe

**Files:**
- Modify: `server/state_manager.py`
- Modify: `server/websocket/agent_handler.py`
- Modify: `server/websocket/agent_handshake.py`
- Test: `server/tests/test_ws_reconnect_safety.py`
- Test: `server/tests/test_agent_disconnect_runtime_audit.py`

- [ ] **Step 1: Write the failing reconnect-safety tests**

```python
@pytest.mark.asyncio
async def test_old_socket_disconnect_does_not_unregister_new_connection():
    state = StateManager()
    first_ws = SimpleNamespace(closed=False)
    second_ws = SimpleNamespace(closed=False)

    first_connection_id = state.register_agent(
        "device-1",
        first_ws,
        {"status": "online", "connected_at": 1.0},
    )
    second_connection_id = state.register_agent(
        "device-1",
        second_ws,
        {"status": "online", "connected_at": 2.0},
    )

    assert first_connection_id != second_connection_id

    removed = state.unregister_agent_if_current(
        "device-1",
        expected_connection_id=first_connection_id,
    )

    assert removed is False
    assert state.get_agent("device-1")["ws"] is second_ws


@pytest.mark.asyncio
async def test_disconnect_handler_ignores_superseded_socket(monkeypatch):
    # Arrange a state entry for the newer ws, then call disconnect for the old one.
    ...
```

- [ ] **Step 2: Run the focused server tests and verify they fail for the current race**

Run: `python -m pytest server/tests/test_ws_reconnect_safety.py server/tests/test_agent_disconnect_runtime_audit.py -q`
Expected: FAIL because `StateManager` only has unconditional `unregister_agent()` and the disconnect handler always removes the entry.

- [ ] **Step 3: Implement connection/session identity in the runtime registry**

```python
# server/state_manager.py
def register_agent(self, device_id: str, ws: Any, metadata: dict) -> str:
    connection_id = str(uuid.uuid4())
    entry = {
        "ws": ws,
        "metadata": {**metadata, "connection_id": connection_id},
        "connected_at": metadata.get("connected_at"),
    }
    previous = self.connected_agents.get(device_id)
    self.connected_agents[device_id] = entry
    return connection_id


def unregister_agent_if_current(
    self,
    device_id: str,
    *,
    expected_connection_id: Optional[str] = None,
    expected_ws: Optional[Any] = None,
) -> bool:
    current = self.connected_agents.get(device_id)
    if current is None:
        return False
    current_connection_id = current.get("metadata", {}).get("connection_id")
    current_ws = current.get("ws")
    if expected_connection_id and current_connection_id != expected_connection_id:
        return False
    if expected_ws is not None and current_ws is not expected_ws:
        return False
    del self.connected_agents[device_id]
    return True
```

- [ ] **Step 4: Make handshake replacement and disconnect handling use the safe unregister path**

```python
# server/websocket/agent_handshake.py
connection_id = state.register_agent(agent_id, ws, metadata)
metadata["connection_id"] = connection_id

# server/websocket/agent_handler.py
removed = state.unregister_agent_if_current(
    device_id,
    expected_ws=connection_ctx.ws,
)
if not removed:
    logger.info("[WS handler] Skip unregister for superseded socket")
```

- [ ] **Step 5: Re-run the focused reconnect tests**

Run: `python -m pytest server/tests/test_ws_reconnect_safety.py server/tests/test_agent_disconnect_runtime_audit.py -q`
Expected: PASS

- [ ] **Step 6: Commit the reconnect-safety slice**

```bash
git add server/state_manager.py server/websocket/agent_handler.py server/websocket/agent_handshake.py server/tests/test_ws_reconnect_safety.py server/tests/test_agent_disconnect_runtime_audit.py
git commit -m "fix: harden agent reconnect runtime state"
```

### Task 2: Move synchronous command waiters out of connection-local metadata

**Files:**
- Modify: `server/state_manager.py`
- Modify: `server/websocket/protocol.py`
- Modify: `server/websocket/command_result_components.py`
- Test: `server/tests/test_ws_command_waiters.py`
- Test: `server/tests/test_tool_dispatch_failure.py`

- [ ] **Step 1: Write the failing waiter-survival tests**

```python
@pytest.mark.asyncio
async def test_command_waiter_survives_connection_replacement():
    state = StateManager()
    future = state.register_command_waiter("cmd-1", device_id="device-1")

    # Simulate reconnect: active socket entry changes before command_result arrives.
    state.register_agent("device-1", SimpleNamespace(), {"status": "online", "connected_at": 1.0})
    state.register_agent("device-1", SimpleNamespace(), {"status": "online", "connected_at": 2.0})

    resolved = state.resolve_command_waiter("cmd-1", {"payload": {"status": "success"}})

    assert resolved is True
    assert future.done()


@pytest.mark.asyncio
async def test_send_ws_command_timeout_cleans_waiter_registry():
    ...
```

- [ ] **Step 2: Run the waiter-focused tests and confirm the current implementation fails**

Run: `python -m pytest server/tests/test_ws_command_waiters.py server/tests/test_tool_dispatch_failure.py -q`
Expected: FAIL because waiters live in `agent_info["metadata"]["pending_command_futures"]` tied to the active socket entry.

- [ ] **Step 3: Add a state-level waiter registry keyed by command_id**

```python
# server/state_manager.py
def register_command_waiter(self, command_id: str, *, device_id: str) -> asyncio.Future:
    if not hasattr(self, "_pending_command_waiters"):
        self._pending_command_waiters = {}
    future = asyncio.get_event_loop().create_future()
    self._pending_command_waiters[command_id] = {
        "device_id": device_id,
        "future": future,
        "created_at": time.time(),
    }
    return future


def resolve_command_waiter(self, command_id: str, result_data: dict) -> bool:
    entry = getattr(self, "_pending_command_waiters", {}).pop(command_id, None)
    if not entry:
        return False
    future = entry["future"]
    if not future.done():
        future.set_result(result_data)
    return True


def cancel_command_waiter(self, command_id: str) -> None:
    entry = getattr(self, "_pending_command_waiters", {}).pop(command_id, None)
    if entry and not entry["future"].done():
        entry["future"].cancel()
```

- [ ] **Step 4: Update `send_ws_command` and the resolver to use the new registry**

```python
# server/websocket/protocol.py
future = state.register_command_waiter(command_id, device_id=device_id)
...
except asyncio.TimeoutError:
    state.cancel_command_waiter(command_id)
    raise

# server/websocket/command_result_components.py
def resolve_from_context(self, command_id, result_data, ctx):
    state = getattr(ctx, "state", None)
    if state is None or not command_id:
        return False
    return state.resolve_command_waiter(command_id, result_data)
```

- [ ] **Step 5: Re-run waiter-focused tests and the existing dispatch-failure regression**

Run: `python -m pytest server/tests/test_ws_command_waiters.py server/tests/test_tool_dispatch_failure.py -q`
Expected: PASS

- [ ] **Step 6: Commit the waiter-registry slice**

```bash
git add server/state_manager.py server/websocket/protocol.py server/websocket/command_result_components.py server/tests/test_ws_command_waiters.py server/tests/test_tool_dispatch_failure.py
git commit -m "fix: preserve command waiters across reconnect"
```

### Task 3: Add explicit per-agent execution scheduling on the agent

**Files:**
- Create: `pc_agent/core/command_scheduler.py`
- Modify: `pc_agent/ws_agent.py`
- Modify: `pc_agent/core/orchestrator.py`
- Test: `pc_agent/tests/test_command_scheduler.py`

- [ ] **Step 1: Write failing scheduler tests for serialized tool execution and high-priority control commands**

```python
@pytest.mark.asyncio
async def test_run_tool_commands_execute_one_at_a_time():
    events = []

    async def slow_tool(name):
        events.append(("start", name))
        await asyncio.sleep(0.05)
        events.append(("finish", name))

    scheduler = AgentCommandScheduler(tool_concurrency=1)
    await asyncio.gather(
        scheduler.submit(priority="normal", command="run_tool", coro=lambda: slow_tool("A")),
        scheduler.submit(priority="normal", command="run_tool", coro=lambda: slow_tool("B")),
    )

    assert events == [
        ("start", "A"),
        ("finish", "A"),
        ("start", "B"),
        ("finish", "B"),
    ]


@pytest.mark.asyncio
async def test_cancel_operation_uses_control_lane():
    ...
```

- [ ] **Step 2: Run the scheduler tests and verify they fail before the scheduler exists**

Run: `python -m pytest pc_agent/tests/test_command_scheduler.py -q`
Expected: FAIL because the runtime still dispatches directly via `asyncio.create_task(...)`.

- [ ] **Step 3: Implement a focused scheduler with two lanes**

```python
# pc_agent/core/command_scheduler.py
class AgentCommandScheduler:
    def __init__(self, *, tool_concurrency: int = 1) -> None:
        self._tool_queue = asyncio.PriorityQueue()
        self._control_queue = asyncio.PriorityQueue()
        self._tool_concurrency = tool_concurrency
        self._tool_workers = []
        self._control_worker = None

    async def submit(self, *, priority: int, lane: str, command_id: str, runner: Callable[[], Awaitable[None]]) -> None:
        target = self._control_queue if lane == "control" else self._tool_queue
        await target.put((priority, time.monotonic(), command_id, runner))
```

- [ ] **Step 4: Route incoming commands through the scheduler instead of immediate background execution**

```python
# pc_agent/ws_agent.py
lane = "control" if command in {"cancel_operation", "update", "ping"} else "tool"
priority = 0 if lane == "control" else 50

await self.command_scheduler.submit(
    priority=priority,
    lane=lane,
    command_id=command_id,
    runner=lambda: self._execute_command_and_send_result(ws, **execution_kwargs),
)
```

- [ ] **Step 5: Keep `orchestrator.running_tasks` as the cancel source of truth**

```python
# pc_agent/core/orchestrator.py
task = asyncio.create_task(_execute_tool(), name=f"tool.{operation_id}")
self.running_tasks[operation_id] = task
try:
    observations = await task
finally:
    self.running_tasks.pop(operation_id, None)
```

- [ ] **Step 6: Re-run agent scheduler tests plus a targeted cancel regression**

Run: `python -m pytest pc_agent/tests/test_command_scheduler.py pc_agent/tests/test_ws_agent.py -k "scheduler or cancel" -q`
Expected: PASS

- [ ] **Step 7: Commit the agent scheduling slice**

```bash
git add pc_agent/core/command_scheduler.py pc_agent/ws_agent.py pc_agent/core/orchestrator.py pc_agent/tests/test_command_scheduler.py
git commit -m "fix: serialize agent tool execution with control lane"
```

### Task 4: Add priority-aware server dispatch lanes for `device_outbox`

**Files:**
- Modify: `server/app/db/models.py`
- Create: `server/app/db/migrations/versions/20260421_1200_055_device_outbox_priority.py`
- Modify: `server/app/repos/device_outbox_repo.py`
- Modify: `server/websocket/protocol.py`
- Modify: `server/app/services/operation_service.py`
- Modify: `server/tools/service.py`
- Test: `server/tests/test_device_outbox_priority.py`
- Test: `server/tests/test_device_dispatch_integration.py`

- [ ] **Step 1: Write the failing priority-order tests**

```python
@pytest.mark.asyncio
async def test_cancel_operation_dispatches_before_normal_run_tool(session):
    repo = DeviceOutboxRepo(session)
    await repo.enqueue_command(device_id="device-1", command_id="run", command="run_tool", params={}, priority=50)
    await repo.enqueue_command(device_id="device-1", command_id="cancel", command="cancel_operation", params={}, priority=100)

    pending = await repo.get_pending_commands_for_device("device-1", limit=10)

    assert [cmd.command_id for cmd in pending][:2] == ["cancel", "run"]


@pytest.mark.asyncio
async def test_same_priority_commands_keep_fifo_order(session):
    ...
```

- [ ] **Step 2: Run the priority tests and confirm the current FIFO-only ordering fails**

Run: `python -m pytest server/tests/test_device_outbox_priority.py -q`
Expected: FAIL because ordering is currently `created_at ASC` only.

- [ ] **Step 3: Add a priority column and explicit command-priority mapping**

```python
# server/app/db/models.py
priority = mapped_column(SmallInteger, nullable=False, default=50, server_default="50")

# server/websocket/protocol.py
COMMAND_PRIORITIES = {
    "cancel_operation": 100,
    "update": 90,
    "ping": 80,
    "list_tools": 70,
    "list_installed_modules": 70,
    "run_tool": 50,
}
priority = COMMAND_PRIORITIES.get(command, 50)
```

- [ ] **Step 4: Propagate priority through both enqueue paths**

```python
# server/app/repos/device_outbox_repo.py
async def enqueue_command(..., priority: int = 50) -> int:
    outbox_entry = DeviceOutbox(..., priority=priority)

# server/app/repos/device_outbox_repo.py
.order_by(DeviceOutbox.priority.desc(), DeviceOutbox.created_at.asc(), DeviceOutbox.id.asc())

# server/app/services/operation_service.py
await repo.enqueue_command(
    device_id=operation.device_id,
    command_id=operation_id,
    command="run_tool",
    params=params,
    operation_id=operation_id,
    priority=50,
)
```

- [ ] **Step 5: Re-run priority tests and existing dispatch integration checks**

Run: `python -m pytest server/tests/test_device_outbox_priority.py server/tests/test_device_dispatch_integration.py -q`
Expected: PASS

- [ ] **Step 6: Commit the dispatch-priority slice**

```bash
git add server/app/db/models.py server/app/db/migrations/versions server/app/repos/device_outbox_repo.py server/websocket/protocol.py server/app/services/operation_service.py server/tools/service.py server/tests/test_device_outbox_priority.py server/tests/test_device_dispatch_integration.py
git commit -m "feat: prioritize per-device command dispatch"
```

### Task 5: Optional negotiated wire batching for agent outbox transport

**Files:**
- Modify: `pc_agent/core/sender.py`
- Modify: `pc_agent/ws_agent.py`
- Modify: `server/websocket/agent_handler.py`
- Modify: `server/websocket/agent_services.py`
- Modify: `server/websocket/outbox_ingest_components.py`
- Modify: `server/docs/PROTOCOL_V3.md`
- Modify: `pc_agent/docs/PROTOCOL_V3.md`
- Test: `pc_agent/tests/test_outbox_batch_transport.py`
- Test: `server/tests/test_agent_services_pipeline.py`

- [ ] **Step 1: Gate the phase with a measured need**

Run:
`python -m pytest server/tests/test_agent_services_pipeline.py server/tests/test_device_dispatch_integration.py -q`
`python scripts/manage_remote_stack.py logs server --lines 200 --contains outbox`

Expected: gather baseline evidence that per-item frames are a material bottleneck before changing the protocol.

- [ ] **Step 2: Write failing batch-transport tests behind a new capability**

```python
@pytest.mark.asyncio
async def test_sender_uses_batch_envelope_when_server_advertises_outbox_batch_v1():
    sender = WSOutboxFlusher(...)
    capabilities = {"outbox_batch_v1"}
    ...
    assert sent_message["type"] == "outbox_batch"
    assert len(sent_message["payload"]["items"]) == 3
```

- [ ] **Step 3: Introduce a backward-compatible transport shape**

```python
# pc_agent/core/sender.py
if "outbox_batch_v1" in negotiated_capabilities:
    await send_func(
        "outbox_batch",
        request_id,
        {"items": items_payload},
        None,
        None,
    )
else:
    for item in batch:
        await send_single_item(...)
```

- [ ] **Step 4: Teach the server router to unpack the batch and reuse the same ingest pipeline**

```python
# server/websocket/agent_services.py
if msg_type == "outbox_batch":
    for item_message in payload["items"]:
        await self.handle({**message, "type": "outbox_item", "payload": item_message}, ctx)
    return "__continue__"
```

- [ ] **Step 5: Re-run batch transport tests and keep the old path green**

Run: `python -m pytest pc_agent/tests/test_outbox_batch_transport.py server/tests/test_agent_services_pipeline.py -q`
Expected: PASS

- [ ] **Step 6: Commit batching only if phases 1-4 are already green and live-validated**

```bash
git add pc_agent/core/sender.py pc_agent/ws_agent.py server/websocket/agent_handler.py server/websocket/agent_services.py server/websocket/outbox_ingest_components.py server/docs/PROTOCOL_V3.md pc_agent/docs/PROTOCOL_V3.md pc_agent/tests/test_outbox_batch_transport.py server/tests/test_agent_services_pipeline.py
git commit -m "feat: add negotiated outbox batch transport"
```

### Task 6: Documentation sync, full verification, and live checks

**Files:**
- Modify: `server/docs/PROTOCOL_V3.md`
- Modify: `pc_agent/docs/PROTOCOL_V3.md`
- Modify: `server/docs/CODEMAP.md`
- Modify: `pc_agent/docs/CODEMAP.md`
- Modify: `PLANS.md`

- [ ] **Step 1: Update protocol and navigation docs after the code phases land**

```markdown
- reconnect-safe connection identity and disconnect guard
- state-level command waiter registry
- agent command scheduler / control lane
- device_outbox priority ordering
- optional `outbox_batch_v1` capability (only if Task 5 ships)
```

- [ ] **Step 2: Run repository-level verification**

Run: `python scripts/verify_workspace.py`
Expected: PASS

- [ ] **Step 3: Run the focused regression matrix**

Run:
`python -m pytest server/tests/test_ws_reconnect_safety.py server/tests/test_ws_command_waiters.py server/tests/test_device_outbox_priority.py server/tests/test_agent_disconnect_runtime_audit.py server/tests/test_device_dispatch_integration.py server/tests/test_agent_services_pipeline.py server/tests/test_tool_dispatch_failure.py -q`

Run:
`python -m pytest pc_agent/tests/test_command_scheduler.py pc_agent/tests -k "cancel or scheduler or ws_agent" -q`

Expected: PASS

- [ ] **Step 4: Run a broader mixed baseline before live rollout**

Run:
`python -m pytest server/tests/test_integration_p0.py -q`
`python -m pytest pc_agent/tests -m "not manual" -q`

Expected: PASS, or explicitly document remaining unrelated failures before release.

- [ ] **Step 5: Perform local live checks with a named Windows agent instance**

Run:
`python scripts/manage_local_agent.py verify reconnect-probe --machine-id reconnect-probe-01`

Run:
`python scripts/manage_local_agent.py start reconnect-probe --launcher --issue-token --machine-id reconnect-probe-01 --ui-port 8871`

Run:
`python scripts/manage_local_agent.py status reconnect-probe`

Live scenarios:
- enqueue one long-running `run_tool`, then force a reconnect by restarting the local agent instance; confirm the new session stays online and the old disconnect does not drop the runtime entry;
- enqueue a `run_tool`, then enqueue `cancel_operation`; confirm cancel reaches the agent without waiting behind a normal tool tail;
- enqueue mixed `run_tool`, `ping`, and update/control traffic; confirm priority ordering in logs/runtime audit.

- [ ] **Step 6: Perform canonical remote deployment and Linux smoke**

Run:
`python scripts/release_server_to_remote.py`

Run:
`python scripts/manage_remote_stack.py status server --json`

Run:
`python scripts/manage_remote_stack.py smoke server`

Expected: remote release succeeds, status is healthy, smoke is green.

- [ ] **Step 7: Perform browser/live admin verification on the canonical URL**

Use MCP browser on: `http://192.168.100.17:8666/admin`

Checks:
- agent/device stays online across a forced reconnect;
- operation timeline does not lose state after reconnect;
- cancel/update/control actions are visible ahead of normal queued work where expected;
- tech status, health, full logs, and any stop/restart confirmations still work if touched by the rollout.

- [ ] **Step 8: Collect rollback evidence and stop the remote server if the user did not request it to stay up**

Run:
`python scripts/manage_remote_stack.py logs server --lines 200 --contains reconnect`

Run:
`python scripts/manage_remote_stack.py logs server --lines 200 --contains command_delivery_failed`

Run:
`python scripts/manage_remote_stack.py stop server`

Expected: logs show no new reconnect/waiter regressions, and the server is stopped after verification unless explicitly left running.

- [ ] **Step 9: Commit the docs + verification handoff**

```bash
git add server/docs/PROTOCOL_V3.md pc_agent/docs/PROTOCOL_V3.md server/docs/CODEMAP.md pc_agent/docs/CODEMAP.md PLANS.md
git commit -m "docs: sync contract hardening plan and protocol notes"
```

## Self-review checklist

- Reconnect race covered: Task 1
- Lost waiter across reconnect covered: Task 2
- Per-agent execution queue covered: Task 3
- Server dispatch priority covered: Task 4
- Optional batching isolated behind capability and delayed until after correctness phases: Task 5
- Docs, focused tests, broader tests, local live checks, remote smoke, browser verification, and shutdown hygiene covered: Task 6

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-21-agent-server-contract-hardening.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
