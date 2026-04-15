"""
Playbook Engine: запуск плейбука и продвижение по шагам при терминальном статусе операции.

Этап 4 MVP: последовательные шаги, один operation_id на шаг, продвижение по факту
command_result (success/error). Этап 6: deferred run (pending + scheduled_at), idempotency_key.
Этап 7: if_expr, params_template (context + prev_steps), retry_policy, timeout_sec.
Этап 8: parallel_group — fan-out/fan-in, лимит параллелизма per run.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple, Any, List

from loguru import logger

import config
from app.repos.playbook_repo import PlaybookRepo
from app.db.models import PlaybookStep
from app.utils.playbook_step_eval import evaluate_if_expr, resolve_params_template
from app.services.playbook_capability import check_tool_available

TOOL_BACKED_STEP_TYPES = frozenset({"run_tool", "collect", "enrich", "remediate"})
LOCAL_STEP_TYPES = frozenset({"transform", "decision", "report"})


def _step_type(step: PlaybookStep) -> str:
    return str(getattr(step, "type", None) or ("run_tool" if step.tool else "transform")).strip().lower()


def _is_tool_backed_step(step: PlaybookStep) -> bool:
    step_type = _step_type(step)
    return step_type in TOOL_BACKED_STEP_TYPES or bool(step.tool and step_type not in LOCAL_STEP_TYPES)


def _has_local_steps(group: List[Tuple[PlaybookStep, int]]) -> bool:
    return any(not _is_tool_backed_step(step) for step, _ in group)


async def _execute_local_step(
    repo: PlaybookRepo,
    run,
    step: PlaybookStep,
    context: dict,
    prev_steps: dict,
):
    now = datetime.now(timezone.utc)
    step_type = _step_type(step)
    input_payload = _step_params(step, context, prev_steps)
    output_payload = None
    error_payload = None
    status = "success"
    try:
        if step_type == "decision":
            decision = None
            matched_rule = None
            rules = input_payload.get("rules") if isinstance(input_payload, dict) else None
            if not isinstance(rules, list):
                rules = []
            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                when_expr = rule.get("when")
                if when_expr and not evaluate_if_expr(str(when_expr), context, prev_steps):
                    continue
                matched_rule = rule
                decision = rule.get("set")
                if decision is None:
                    decision = rule.get("value") or rule.get("branch")
                break
            if decision is None and isinstance(input_payload, dict):
                decision = input_payload.get("default")
            output_payload = {
                "decision": decision,
                "matched_rule": matched_rule.get("id") if isinstance(matched_rule, dict) else None,
            }
        else:
            output_payload = input_payload
    except Exception as exc:
        status = "failed"
        error_payload = {"code": "LOCAL_STEP_FAILED", "message": str(exc), "step_type": step_type}

    return await repo.create_step_run(
        playbook_run_id=run.id,
        playbook_step_id=step.id,
        operation_id=None,
        attempt=1,
        input_json=input_payload,
        status=status,
        output_json=output_payload,
        error_json=error_payload,
        finished_at=now,
    )


def _retry_allowed(step: PlaybookStep, step_run, error_code: Optional[str]) -> bool:
    """Этап 7: Проверка retry_policy: max_attempts, retry_on_codes."""
    policy = step.retry_policy_json if isinstance(step.retry_policy_json, dict) else None
    if not policy:
        return False
    max_attempts = policy.get("max_attempts")
    if max_attempts is None:
        return False
    try:
        max_attempts = int(max_attempts)
    except (TypeError, ValueError):
        return False
    if step_run.attempt >= max_attempts:
        return False
    retry_on_codes = policy.get("retry_on_codes")
    if retry_on_codes is not None and isinstance(retry_on_codes, list) and len(retry_on_codes) > 0:
        if not error_code or error_code not in retry_on_codes:
            return False
    return True


def _group_steps_by_parallel(steps: List[PlaybookStep]) -> List[List[Tuple[PlaybookStep, int]]]:
    """
    Этап 8: Разбивает шаги на группы по parallel_group.
    Подряд идущие шаги с одинаковым parallel_group (в т.ч. None) — одна группа.
    Возвращает список групп; каждая группа — список (step, index).
    """
    if not steps:
        return []
    groups: List[List[Tuple[PlaybookStep, int]]] = []
    current: List[Tuple[PlaybookStep, int]] = [(steps[0], 0)]
    prev_group = steps[0].parallel_group
    for i in range(1, len(steps)):
        step = steps[i]
        if step.parallel_group == prev_group:
            current.append((step, i))
        else:
            groups.append(current)
            current = [(step, i)]
            prev_group = step.parallel_group
    groups.append(current)
    return groups


async def _next_executable_step_index(
    steps: List[PlaybookStep],
    from_index: int,
    context: dict,
    prev_steps: dict,
    repo: PlaybookRepo,
    playbook_run_id: int,
) -> Optional[int]:
    """
    Этап 7: Возвращает индекс следующего шага для выполнения.
    Шаги с if_expr=False помечаются как skipped (create_step_run_skipped), prev_steps обновляется.
    """
    for i in range(from_index, len(steps)):
        step = steps[i]
        if not step.tool:
            return i
        if step.if_expr and not evaluate_if_expr(step.if_expr, context, prev_steps):
            await repo.create_step_run_skipped(
                playbook_run_id, step.id, reason="if_expr=false"
            )
            prev_steps[step.step_key] = {
                "output": None,
                "error": None,
                "status": "skipped",
            }
            continue
        return i
    return None


async def _start_group_steps(
    session,
    state,
    repo: PlaybookRepo,
    run,
    group: List[Tuple[PlaybookStep, int]],
    context: dict,
    prev_steps: dict,
    max_to_start: int,
) -> Tuple[int, Optional[str]]:
    """
    Этап 8: Запускает до max_to_start шагов из группы (step_run + operation + enqueue).
    Возвращает (количество запущенных, first_operation_id или None).
    """
    from app.services.operation_service import OperationService
    from websocket.protocol import enqueue_command_async

    op_service = OperationService(session, publisher=getattr(state, "ui_publisher", None))
    started_tools = 0
    processed_steps = 0
    first_op_id: Optional[str] = None
    for (step, _idx) in group:
        if _is_tool_backed_step(step) and started_tools >= max_to_start:
            break
        if step.if_expr and not evaluate_if_expr(step.if_expr, context, prev_steps):
            await repo.create_step_run_skipped(run.id, step.id, reason="if_expr=false")
            prev_steps[step.step_key] = {"output": None, "error": None, "status": "skipped"}
            continue
        if not _is_tool_backed_step(step):
            local_step_run = await _execute_local_step(repo, run, step, context, prev_steps)
            processed_steps += 1
            prev_steps = await repo.get_prev_steps_for_run(run.id)
            await _process_run_after_step_terminal(session, state, repo, run, step, local_step_run)
            if getattr(run, "status", None) != "running":
                break
            continue
        # Этап 9: Capability Gate — проверка до enqueue (отключается CAPABILITY_GATE_STRICT=false)
        if config.CAPABILITY_GATE_STRICT:
            ok, err_code, err_msg = await check_tool_available(session, run.device_id, step.tool)
            if not ok:
                step_run_fail = await repo.create_step_run_failed(
                    run.id, step.id, err_code or "UNSUPPORTED_CAPABILITY", err_msg or "Tool not available"
                )
                processed_steps += 1
                await _process_run_after_step_terminal(session, state, repo, run, step, step_run_fail)
                if getattr(run, "status", None) != "running":
                    break
                continue
        operation_id = str(uuid.uuid4())
        if first_op_id is None:
            first_op_id = operation_id
        await op_service.enqueue_operation(
            operation_id=operation_id,
            device_id=run.device_id,
            kind="tool_call",
            actor_role="system",
            trace_id=str(uuid.uuid4()),
            ticket_id=None,
            job_id=None,
            tool_name=step.tool,
            timeout_override_sec=step.timeout_sec,
            playbook_run_id=run.id,
        )
        params = _step_params(step, context, prev_steps)
        await repo.create_step_run(
            playbook_run_id=run.id,
            playbook_step_id=step.id,
            operation_id=operation_id,
            attempt=1,
            input_json=params,
        )
        await enqueue_command_async(
            state,
            device_id=run.device_id,
            command="run_tool",
            params={"tool_name": step.tool, "params": params},
            actor_role="system",
            operation_id=operation_id,
            require_online=False,
        )
        started_tools += 1
        processed_steps += 1
        logger.info(
            f"[PlaybookEngine] Started run_id={run.id} step_key={step.step_key} operation_id={operation_id}"
        )
    return (processed_steps, first_op_id)


async def _process_run_after_step_terminal(
    session, state, repo: PlaybookRepo, run, step: PlaybookStep, step_run,
) -> None:
    """
    Общая логика после перехода step_run в терминал: проверка группы, переход к следующей группе или завершение run.
    Вызывается из advance_after_terminal и при capability-fail (step_run без operation_id).
    """
    version, steps = (await repo.get_version_with_steps(run.playbook_version_id)) or (None, [])
    if not version or not steps:
        await repo.finish_run(run.id, "failed", error_code="NO_STEPS", error_message="No steps")
        return
    current_index = next((i for i, s in enumerate(steps) if s.id == step.id), -1)
    groups = _group_steps_by_parallel(steps)
    group_index = next((gi for gi, g in enumerate(groups) if any(s.id == step.id for s, _ in g)), 0)
    group = groups[group_index]
    step_ids_in_group = [s.id for s, _ in group]
    step_runs_in_group = await repo.get_step_runs_for_run_by_step_ids(run.id, step_ids_in_group)
    started_step_ids = {sr.playbook_step_id for sr in step_runs_in_group}
    not_started = [(s, idx) for (s, idx) in group if s.id not in started_step_ids]
    if not_started:
        return
    if not all(sr.finished_at for sr in step_runs_in_group):
        return
    for sr in step_runs_in_group:
        step_def = next((s for s, _ in group if s.id == sr.playbook_step_id), None)
        if step_def and sr.status == "failed" and not step_def.continue_on_error:
            await repo.finish_run(
                run.id, "failed", error_code="STEP_FAILED",
                error_message=f"Step {step_def.step_key} failed",
            )
            logger.info(f"[PlaybookEngine] Run {run.id} failed at step {step_def.step_key}")
            return
    await _advance_to_next_group_or_finish(session, state, repo, run, steps, groups, group_index)


async def _advance_to_next_group_or_finish(
    session, state, repo: PlaybookRepo, run, steps: List[PlaybookStep],
    groups: List[List[Tuple[PlaybookStep, int]]], completed_group_index: int,
) -> None:
    """
    Этап 8: После завершения группы — запустить следующую группу или завершить run success.
    """
    next_gi = completed_group_index + 1
    if next_gi >= len(groups):
        await repo.finish_run(run.id, "success")
        logger.info(f"[PlaybookEngine] Run {run.id} finished success (no more groups)")
        return
    context = run.context_json or {}
    prev_steps = await repo.get_prev_steps_for_run(run.id)
    max_parallel = config.PLAYBOOK_MAX_PARALLEL_STEPS_PER_RUN if config.PLAYBOOK_PARALLEL_ENABLED else 1
    await _start_group_steps(
        session, state, repo, run, groups[next_gi], context, prev_steps, max_parallel
    )


async def start_run(
    session,
    state,
    playbook_version_id: int,
    device_id: str,
    trigger_type: Optional[str] = None,
    context_json: Optional[dict] = None,
    scheduled_at: Optional[datetime] = None,
    idempotency_key: Optional[str] = None,
) -> Tuple[int, Optional[str]]:
    """
    Создаёт playbook_run и при немедленном запуске ставит в очередь первый шаг (run_tool).
    Этап 6: при idempotency_key возвращает существующий run; при scheduled_at в будущем — pending без шага.

    Returns:
        (playbook_run_id, first_operation_id или None если шагов нет / отложенный run / idempotency)
    """
    from app.services.operation_service import OperationService
    from websocket.protocol import enqueue_command_async

    repo = PlaybookRepo(session)
    now = datetime.now(timezone.utc)

    if idempotency_key:
        existing = await repo.get_run_by_idempotency_key(idempotency_key)
        if existing:
            logger.info(f"[PlaybookEngine] Idempotency: existing run_id={existing.id} status={existing.status}")
            return (existing.id, None)

    version_and_steps = await repo.get_version_with_steps(playbook_version_id)
    if not version_and_steps:
        raise ValueError(f"Playbook version {playbook_version_id} not found")
    version, steps = version_and_steps
    if version.status != "published" and version.status != "draft":
        logger.warning(f"[PlaybookEngine] Version {playbook_version_id} status={version.status}")

    # Отложенный запуск: scheduled_at в будущем → pending, без постановки шага
    if scheduled_at is not None and scheduled_at > now:
        run = await repo.create_run(
            playbook_version_id=playbook_version_id,
            device_id=device_id,
            trigger_type=trigger_type,
            context_json=context_json,
            status="pending",
            scheduled_at=scheduled_at,
            started_at=None,
            idempotency_key=idempotency_key,
        )
        logger.info(f"[PlaybookEngine] Deferred run_id={run.id} scheduled_at={scheduled_at}")
        return (run.id, None)

    if not steps:
        run = await repo.create_run(
            playbook_version_id=playbook_version_id,
            device_id=device_id,
            trigger_type=trigger_type,
            context_json=context_json,
            idempotency_key=idempotency_key,
        )
        await repo.finish_run(run.id, "success")
        return (run.id, None)

    run = await repo.create_run(
        playbook_version_id=playbook_version_id,
        device_id=device_id,
        trigger_type=trigger_type,
        context_json=context_json,
        idempotency_key=idempotency_key,
    )
    context = context_json or {}
    prev_steps = await repo.get_prev_steps_for_run(run.id)
    groups = _group_steps_by_parallel(steps)
    if not groups:
        await repo.finish_run(run.id, "success")
        return (run.id, None)
    max_parallel = config.PLAYBOOK_MAX_PARALLEL_STEPS_PER_RUN if config.PLAYBOOK_PARALLEL_ENABLED else 1
    started, first_op_id = await _start_group_steps(
        session, state, repo, run, groups[0], context, prev_steps, max_parallel
    )
    if started == 0:
        # Все шаги первой группы пропущены по if_expr или без tool — проверяем, есть ли ещё группы
        await _advance_to_next_group_or_finish(session, state, repo, run, steps, groups, 0)
        return (run.id, None)
    return (run.id, first_op_id)


async def advance_after_terminal(
    session,
    state,
    operation_id: str,
    terminal_status: str,
    result_payload: Optional[dict] = None,
) -> bool:
    """
    Вызывается при переходе операции в terminal (succeeded/failed/timed_out/canceled).
    Обновляет step_run, при необходимости запускает следующий шаг или завершает run.
    Этап 5: timed_out приходит из operation_watchdog после mark_timed_out.

    Returns:
        True если операция была привязана к playbook_step_run и обработка выполнена.
    """
    from app.services.operation_service import OperationService
    from websocket.protocol import enqueue_command_async

    repo = PlaybookRepo(session)
    triple = await repo.get_step_run_by_operation_id(operation_id)
    if not triple:
        return False
    step_run, step, run = triple
    output_json = None
    error_json = None
    if result_payload:
        if terminal_status == "succeeded":
            output_json = result_payload.get("data") or result_payload
        else:
            error_json = result_payload.get("error") or result_payload
    status = "success" if terminal_status == "succeeded" else "failed"
    await repo.update_step_run_terminal(
        step_run_id=step_run.id,
        status=status,
        output_json=output_json,
        error_json=error_json,
    )

    # Этап 7: retry по policy при failed
    if status == "failed":
        error_code = None
        if error_json and isinstance(error_json, dict):
            error_code = error_json.get("code") or (error_json.get("error") or {}).get("code")
        if _retry_allowed(step, step_run, error_code):
            next_attempt = step_run.attempt + 1
            next_operation_id = str(uuid.uuid4())
            op_service = OperationService(session, publisher=getattr(state, "ui_publisher", None))
            await op_service.enqueue_operation(
                operation_id=next_operation_id,
                device_id=run.device_id,
                kind="tool_call",
                actor_role="system",
                trace_id=str(uuid.uuid4()),
                ticket_id=None,
                job_id=None,
                tool_name=step.tool,
                timeout_override_sec=step.timeout_sec,
                playbook_run_id=run.id,
            )
            context = run.context_json or {}
            prev_steps = await repo.get_prev_steps_for_run(run.id)
            params = _step_params(step, context, prev_steps)
            await repo.create_step_run(
                playbook_run_id=run.id,
                playbook_step_id=step.id,
                operation_id=next_operation_id,
                attempt=next_attempt,
                input_json=params,
            )
            await session.commit()
            await enqueue_command_async(
                state,
                device_id=run.device_id,
                command="run_tool",
                params={"tool_name": step.tool, "params": params},
                actor_role="system",
                operation_id=next_operation_id,
                require_online=False,
            )
            logger.info(
                f"[PlaybookEngine] Retry run_id={run.id} step_key={step.step_key} attempt={next_attempt} operation_id={next_operation_id}"
            )
            return True
        if not step.continue_on_error:
            await repo.finish_run(
                run.id,
                "failed",
                error_code="STEP_FAILED",
                error_message=f"Step {step.step_key} failed",
            )
            logger.info(f"[PlaybookEngine] Run {run.id} failed at step {step.step_key}")
            return True

    version, steps = (await repo.get_version_with_steps(run.playbook_version_id)) or (None, [])
    if not version or not steps:
        await repo.finish_run(run.id, "failed", error_code="NO_STEPS", error_message="No steps")
        await session.commit()
        return True
    context = run.context_json or {}
    prev_steps = await repo.get_prev_steps_for_run(run.id)
    groups = _group_steps_by_parallel(steps)
    group_index = next((gi for gi, g in enumerate(groups) if any(s.id == step.id for s, _ in g)), 0)
    group = groups[group_index]
    step_ids_in_group = [s.id for s, _ in group]
    step_runs_in_group = await repo.get_step_runs_for_run_by_step_ids(run.id, step_ids_in_group)
    started_step_ids = {sr.playbook_step_id for sr in step_runs_in_group}
    not_started = [(s, idx) for (s, idx) in group if s.id not in started_step_ids]
    if not_started:
        running_count = await repo.count_running_step_runs_for_run(run.id)
        max_parallel = config.PLAYBOOK_MAX_PARALLEL_STEPS_PER_RUN if config.PLAYBOOK_PARALLEL_ENABLED else 1
        to_start = min(len(not_started), max(0, max_parallel - running_count))
        if to_start > 0 or _has_local_steps(not_started):
            await _start_group_steps(
                session, state, repo, run, not_started, context, prev_steps, to_start
            )
        await session.commit()
        return True
    await _process_run_after_step_terminal(session, state, repo, run, step, step_run)
    await session.commit()
    return True


async def start_first_step_for_run(session, state, run_id: int) -> Optional[str]:
    """
    Этап 6: переводит pending run в running и ставит в очередь первый шаг.
    Вызывается планировщиком для due runs. Возвращает operation_id первого шага или None.
    """
    from app.services.operation_service import OperationService
    from websocket.protocol import enqueue_command_async

    from app.db.models import PlaybookRun

    repo = PlaybookRepo(session)
    await repo.set_run_running(run_id)
    run = await session.get(PlaybookRun, run_id)
    if not run or run.status != "running":
        return None
    version_and_steps = await repo.get_version_with_steps(run.playbook_version_id)
    if not version_and_steps:
        await repo.finish_run(run_id, "failed", error_code="NO_STEPS", error_message="No steps")
        return None
    _, steps = version_and_steps
    if not steps:
        await repo.finish_run(run_id, "success")
        return None
    context = run.context_json or {}
    prev_steps = await repo.get_prev_steps_for_run(run_id)
    groups = _group_steps_by_parallel(steps)
    max_parallel = config.PLAYBOOK_MAX_PARALLEL_STEPS_PER_RUN if config.PLAYBOOK_PARALLEL_ENABLED else 1
    started, first_op_id = await _start_group_steps(
        session, state, repo, run, groups[0], context, prev_steps, max_parallel
    )
    if started == 0:
        await _advance_to_next_group_or_finish(session, state, repo, run, steps, groups, 0)
        return None
    return first_op_id


def _step_params(
    step: PlaybookStep,
    context: dict,
    prev_steps: Optional[dict] = None,
) -> dict:
    """Этап 7: Параметры шага с подстановкой {{ context.* }}, {{ steps.*.output.* }} из prev_steps."""
    if not step.params_template_json or not isinstance(step.params_template_json, dict):
        return {}
    return resolve_params_template(
        step.params_template_json,
        context or {},
        prev_steps or {},
    )
