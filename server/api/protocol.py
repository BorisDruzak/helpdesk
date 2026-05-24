"""
Protocol API - документация протокола.
"""

from aiohttp import web


async def handle_protocol(request):
    """
    HTTP API для получения документации протокола: GET /api/protocol
    
    Возвращает описание всех доступных команд и их параметров.
    """
    protocol_doc = {
        "version": "1.0",
        "websocket_endpoints": {
            "/ws": "Agent WebSocket connection",
            "/ws_ui": "UI WebSocket connection"
        },
        "http_endpoints": {
            "POST /api/login": "Admin-only manual agent token issue",
            "GET /api/agents": "List connected agents",
            "GET /api/devices": "List device IDs",
            "POST /api/tickets/create": "Create new ticket",
            "GET /api/tickets/{ticket_id}": "Get ticket details",
            "GET /api/tickets": "List all tickets",
            "POST /api/tickets/{ticket_id}/message": "Send message to ticket",
            "POST /api/tickets/{ticket_id}/close": "Close ticket",
            "GET /api/tools": "List available tools",
            "POST /api/tools/run": "Run tool",
            "POST /api/upload": "Upload file"
        },
        "commands": {
            "ping": "Check agent status",
            "list_tools": "Get list of available tools",
            "run_tool": "Execute tool on agent",
            "job_send_event": "Send event to job",
            "job_end_session": "End job session"
        }
    }
    
    return web.json_response(protocol_doc)
