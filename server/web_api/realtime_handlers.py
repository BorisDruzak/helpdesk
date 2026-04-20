from pydantic import BaseModel, ConfigDict

from auth.middleware import require_auth
from web_api.dto.common import SuccessResponse, json_model_response


class RealtimeBootstrapPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transport: str
    channels: list[str]


@require_auth("admin", "support", "auditor", "user")
async def handle_web_realtime_bootstrap(_request):
    payload = RealtimeBootstrapPayload(
        transport="ws_ui_bridge",
        channels=["support.queue", "ticket.stream", "admin.devices", "tech.feed"],
    )
    return json_model_response(SuccessResponse[RealtimeBootstrapPayload](data=payload))
