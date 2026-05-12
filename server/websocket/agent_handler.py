"""Transport-only websocket handler for agent connections."""

import json

from aiohttp import web
from loguru import logger

from tech.runtime_audit import write_agent_runtime_audit
from websocket.batch_ack_manager import BatchAckManager
from websocket.contexts import AgentConnectionContext, EnvelopeContext
from websocket.validator import EventValidator
from websocket.agent_services import (
    AgentCommandService,
    AgentLoopSafetyService,
    AgentMessageRouter,
    CommandAckService,
    CommandResultService,
    HandshakeService,
    OutboxBatchIngestService,
    OutboxIngestService,
    RpcResponseService,
)
from websocket.agent_handshake import handle_handshake


async def _handle_agent_disconnect(state, connection_ctx: AgentConnectionContext) -> None:
    if not connection_ctx.agent_id:
        return

    device_id = connection_ctx.agent_id
    expected_ws = getattr(connection_ctx, "ws", None)
    expected_connection_id = getattr(connection_ctx, "connection_id", None)

    is_current = True
    if hasattr(state, "is_current_agent_connection"):
        is_current = state.is_current_agent_connection(
            device_id,
            expected_ws=expected_ws,
            expected_connection_id=expected_connection_id,
        )

    if not is_current:
        logger.info(
            "[WS handler] Ignoring disconnect from superseded connection: "
            f"device_id={device_id} connection_id={expected_connection_id}"
        )
        return

    if hasattr(state, "set_agent_status"):
        state.set_agent_status(
            device_id,
            "offline",
            expected_ws=expected_ws,
            expected_connection_id=expected_connection_id,
        )
    else:
        agent_info = state.get_agent(device_id)
        if agent_info:
            agent_info["metadata"]["status"] = "offline"

    removed = state.unregister_agent(
        device_id,
        expected_ws=expected_ws,
        expected_connection_id=expected_connection_id,
    )
    if not removed:
        logger.info(
            "[WS handler] Disconnect raced with newer connection; runtime entry preserved: "
            f"device_id={device_id} connection_id={expected_connection_id}"
        )
        return

    await write_agent_runtime_audit(
        device_id=device_id,
        event_type="agent_offline",
        severity="info",
        source="websocket_handler",
        actor_id=device_id,
        actor_role="agent",
        details_json={"reason": "connection_closed"},
    )
    logger.info(
        f"[WS handler] Exiting handler for agent_id={device_id}, unregistering (connection closed)"
    )
    logger.warning(f"🔴 Agent disconnected: {device_id}")


async def websocket_handler(request):
    """Transport-only WebSocket loop for agent connections."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    state = request.app["state"]
    batch_ack_manager = BatchAckManager()
    event_validator = EventValidator()
    loop_safety_service = AgentLoopSafetyService()

    connection_ctx = AgentConnectionContext(ws=ws, request=request, state=state)
    dispatch_service = getattr(state, "device_dispatch_service", None)
    outbox_ingest_service = OutboxIngestService(
        None,
        batch_ack_manager=batch_ack_manager,
        event_validator=event_validator,
    )

    router = AgentMessageRouter(
        handshake_service=HandshakeService(handle_handshake, dispatch_service=dispatch_service),
        command_ack_service=CommandAckService(),
        command_result_service=CommandResultService(),
        rpc_response_service=RpcResponseService(),
        outbox_ingest_service=outbox_ingest_service,
        outbox_batch_ingest_service=OutboxBatchIngestService(
            outbox_ingest_service,
            batch_ack_manager,
        ),
        agent_command_service=AgentCommandService(),
    )

    logger.info("🟢 New agent websocket connection")

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                data = {}
                msg_type = None
                try:
                    data = json.loads(msg.data)
                    envelope = EnvelopeContext.from_message(data)
                    msg_type = envelope.message_type
                    if msg_type in {"command_ack", "command_result"}:
                        payload = data.get("payload")
                        payload_status = payload.get("status") if isinstance(payload, dict) else None
                        logger.info(
                            "[WS handler] inbound agent command lifecycle message: "
                            f"type={msg_type} request_id={data.get('request_id')} "
                            f"ctx_agent_id={connection_ctx.agent_id} "
                            f"ctx_connection_id={connection_ctx.connection_id} "
                            f"payload_status={payload_status}"
                        )

                    if (
                        msg_type != "handshake"
                        and connection_ctx.agent_id
                        and hasattr(state, "is_current_agent_connection")
                        and not state.is_current_agent_connection(
                            connection_ctx.agent_id,
                            expected_ws=ws,
                            expected_connection_id=connection_ctx.connection_id,
                        )
                    ):
                        logger.warning(
                            "[WS handler] Closing superseded connection before message processing: "
                            f"device_id={connection_ctx.agent_id} connection_id={connection_ctx.connection_id}"
                        )
                        await ws.close(code=4002, message=b"Superseded by newer connection")
                        break

                    route_result = await router.route(data, connection_ctx, envelope)
                    if route_result is ws:
                        return ws
                    if route_result is None and msg_type not in {
                        "handshake",
                        "pong",
                        "command_ack",
                        "command_result",
                        "rpc_response",
                        "command",
                        "outbox_item",
                        "outbox_items_batch",
                        "agent_observer_batch",
                    }:
                        await loop_safety_service.handle_unknown_message_type(msg_type, connection_ctx)
                    if route_result == "__continue__":
                        continue

                    if connection_ctx.agent_id and batch_ack_manager.has_pending(connection_ctx.agent_id):
                        await batch_ack_manager.flush(ws, connection_ctx.agent_id)

                except json.JSONDecodeError:
                    logger.warning(f"⚠️ Received non-JSON message: {msg.data}")
                except Exception as e:
                    logger.opt(exception=True).error(f"❌ Message processing error: {e!r}")
                    if msg_type == "outbox_item" and connection_ctx.agent_id:
                        try:
                            await loop_safety_service.handle_outbox_processing_exception(
                                batch_ack_manager=batch_ack_manager,
                                data=data,
                                agent_id=connection_ctx.agent_id,
                                error=e,
                                ws=ws,
                            )
                        except Exception as nack_error:
                            logger.opt(exception=True).error(
                                f"❌ Failed to send NACK for outbox_item: {nack_error!r}"
                            )
            elif msg.type == web.WSMsgType.ERROR:
                logger.error(f"❌ WebSocket error: {ws.exception()!r}")
                break
    finally:
        await _handle_agent_disconnect(state, connection_ctx)

    return ws
