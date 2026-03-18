"""Transport-only websocket handler for agent connections."""

import json

from aiohttp import web
from loguru import logger

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
    OutboxIngestService,
)
from websocket.agent_handshake import handle_handshake


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

    router = AgentMessageRouter(
        handshake_service=HandshakeService(handle_handshake, dispatch_service=dispatch_service),
        command_ack_service=CommandAckService(),
        command_result_service=CommandResultService(),
        outbox_ingest_service=OutboxIngestService(
            None,
            batch_ack_manager=batch_ack_manager,
            event_validator=event_validator,
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

                    route_result = await router.route(data, connection_ctx, envelope)
                    if route_result is ws:
                        return ws
                    if route_result is None and msg_type not in {
                        "handshake",
                        "pong",
                        "command_ack",
                        "command_result",
                        "command",
                        "outbox_item",
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
        if connection_ctx.agent_id:
            agent_info = state.get_agent(connection_ctx.agent_id)
            if agent_info:
                agent_info["metadata"]["status"] = "offline"
            state.unregister_agent(connection_ctx.agent_id)
            logger.info(
                f"[WS handler] Exiting handler for agent_id={connection_ctx.agent_id}, unregistering (connection closed)"
            )
            logger.warning(f"🔴 Agent disconnected: {connection_ctx.agent_id}")

    return ws
