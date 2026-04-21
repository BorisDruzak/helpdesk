from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from auth.middleware import require_auth
from web_api.dto.common import SuccessResponse, json_model_response


class RealtimeChannelContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str
    scope: Literal["ticket", "device", "chat"]
    subscribe_message_type: str
    unsubscribe_message_type: str
    supports_catchup: bool = True
    supports_live_only: bool = True


class RealtimeBootstrapPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transport: Literal["ws_ui_bridge"]
    auth_mode: Literal["session_cookie"]
    hello_message_type: Literal["ui_hello"]
    socket_url: str
    ping_interval_ms: int = Field(ge=5_000, le=120_000)
    channels: list[RealtimeChannelContract]


@require_auth("admin", "support", "auditor", "user")
async def handle_web_realtime_bootstrap(_request):
    payload = RealtimeBootstrapPayload(
        transport="ws_ui_bridge",
        auth_mode="session_cookie",
        hello_message_type="ui_hello",
        socket_url="/ws_ui",
        ping_interval_ms=20_000,
        channels=[
            RealtimeChannelContract(
                channel="support.queue",
                scope="ticket",
                subscribe_message_type="subscribe_ticket",
                unsubscribe_message_type="unsubscribe_ticket",
            ),
            RealtimeChannelContract(
                channel="ticket.stream",
                scope="ticket",
                subscribe_message_type="subscribe_ticket",
                unsubscribe_message_type="unsubscribe_ticket",
            ),
            RealtimeChannelContract(
                channel="admin.devices",
                scope="device",
                subscribe_message_type="subscribe_device",
                unsubscribe_message_type="unsubscribe_device",
            ),
            RealtimeChannelContract(
                channel="tech.feed",
                scope="device",
                subscribe_message_type="subscribe_device",
                unsubscribe_message_type="unsubscribe_device",
            ),
        ],
    )
    return json_model_response(SuccessResponse[RealtimeBootstrapPayload](data=payload))
