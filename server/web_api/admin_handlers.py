from auth.middleware import require_auth
from web_api.dto.admin import AdminBootstrapPayload, AdminObserverCapabilities
from web_api.dto.common import SuccessResponse, json_model_response


@require_auth("admin")
async def handle_web_admin_bootstrap(_request):
    payload = AdminBootstrapPayload(
        workspace="admin",
        features=[
            "devices_inventory",
            "agent_rollout",
            "modules_workbench",
            "tech_panel",
        ],
        observer=AdminObserverCapabilities(
            quick_endpoint="/api/admin/tech/observer/quick",
            traces_endpoint="/api/admin/tech/traces",
        ),
    )
    return json_model_response(SuccessResponse[AdminBootstrapPayload](data=payload))
