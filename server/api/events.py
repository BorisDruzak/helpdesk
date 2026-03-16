"""
API handlers for event replay (Phase D).

Provides endpoints for agents to request event history after reconnection.
"""

from aiohttp import web
from loguru import logger

try:
    from app.db import get_session
    from app.repos import TicketEventsRepo, DeviceEventsRepo
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False


async def handle_get_ticket_events(request):
    """
    Get replay events for a specific ticket.
    
    GET /api/tickets/{ticket_id}/events
    
    Query parameters:
    - since_agent_seq: Optional - get events with agent_seq > this value
    - limit: Optional - maximum number of events (default: 1000)
    - types: Optional - comma-separated list of event types to filter (e.g., "chat_message,chat_started")
    
    Headers:
    - X-Device-Id: Required - Device ID for authorization
    
    Returns:
        JSON response with ticket events ordered by agent_seq
    
    Example:
        # Get all events
        GET /api/tickets/550e8400-e29b-41d4-a716-446655440000/events
        
        # Get events since agent_seq=5
        GET /api/tickets/550e8400-e29b-41d4-a716-446655440000/events?since_agent_seq=5
        
        # Get only chat messages
        GET /api/tickets/550e8400-e29b-41d4-a716-446655440000/events?types=chat_message
        
        # Combination
        GET /api/tickets/550e8400-e29b-41d4-a716-446655440000/events?since_agent_seq=5&types=chat_message,chat_started
        
        Response:
        {
            "ticket_id": "550e8400-e29b-41d4-a716-446655440000",
            "events": [
                {
                    "id": 123,
                    "ticket_id": "550e8400-e29b-41d4-a716-446655440000",
                    "device_id": "device-001",
                    "agent_seq": 6,
                    "event_type": "chat_message",
                    "payload": {...},
                    "trace_id": "trace-123",
                    "event_id": "evt-456",
                    "created_at": "2026-01-10T12:00:00Z"
                },
                ...
            ],
            "count": 5,
            "filters": {
                "since_agent_seq": 5,
                "event_types": ["chat_message", "chat_started"]
            }
        }
    """
    if not DB_AVAILABLE:
        return web.json_response(
            {
                "error": "Database not available",
                "message": "Event replay requires database persistence"
            },
            status=503
        )
    
    try:
        # Extract parameters
        ticket_id = request.match_info.get("ticket_id")
        since_agent_seq = request.query.get("since_agent_seq")
        limit = int(request.query.get("limit", "1000"))
        types_param = request.query.get("types")  # NEW: comma-separated event types
        
        # Extract device_id from header for authorization
        auth_device_id = request.headers.get("X-Device-Id")
        
        if not ticket_id:
            return web.json_response(
                {"error": "Missing ticket_id"},
                status=400
            )
        
        if not auth_device_id:
            return web.json_response(
                {"error": "Missing X-Device-Id header"},
                status=400
            )
        
        # Convert since_agent_seq to int if provided
        if since_agent_seq is not None:
            try:
                since_agent_seq = int(since_agent_seq)
            except ValueError:
                return web.json_response(
                    {"error": "Invalid since_agent_seq parameter"},
                    status=400
                )
        
        # Parse event_types from comma-separated string
        event_types = None
        if types_param:
            # Split by comma and strip whitespace
            event_types = [t.strip() for t in types_param.split(",") if t.strip()]
            if not event_types:
                event_types = None
        
        # Validate limit
        if limit < 1 or limit > 10000:
            return web.json_response(
                {"error": "Limit must be between 1 and 10000"},
                status=400
            )
        
        # Get events from database
        async with get_session() as session:
            repo = TicketEventsRepo(session)
            
            # Check ticket ownership
            ticket_device_id = await repo.get_ticket_device_id(ticket_id)
            
            if ticket_device_id is None:
                return web.json_response(
                    {"error": "Ticket not found"},
                    status=404
                )
            
            # Authorization check - only bound device can access
            if ticket_device_id != auth_device_id:
                return web.json_response(
                    {"error": "Authorization denied"},
                    status=403
                )
            
            # Get events with optional event_types filter
            events = await repo.get_events(
                ticket_id=ticket_id,
                since_agent_seq=since_agent_seq,
                limit=limit,
                event_types=event_types  # NEW: pass event_types filter
            )
            
            # Convert to dict for JSON serialization
            events_data = [
                {
                    "id": e.id,
                    "ticket_id": e.ticket_id,
                    "device_id": e.device_id,
                    "agent_seq": e.agent_seq,
                    "event_type": e.event_type,
                    "payload": e.payload,
                    "trace_id": e.trace_id,
                    "event_id": e.event_id,
                    "created_at": e.created_at.isoformat() if e.created_at else None
                }
                for e in events
            ]
            
            # Include filters in response for clarity
            response_filters = {}
            if since_agent_seq is not None:
                response_filters["since_agent_seq"] = since_agent_seq
            if event_types:
                response_filters["event_types"] = event_types
            
            return web.json_response({
                "ticket_id": ticket_id,
                "events": events_data,
                "count": len(events_data),
                "filters": response_filters if response_filters else None
            })
    
    except Exception as e:
        logger.error(f"[handle_get_ticket_events] Error: {e}", exc_info=True)
        return web.json_response(
            {"error": "Internal server error", "message": str(e)},
            status=500
        )


async def handle_ticket_messages(request):
    """
    Get chat messages for a specific ticket (shortcut endpoint).
    
    GET /api/tickets/{ticket_id}/messages
    
    This is a convenience endpoint that filters ticket_events to return only chat_message events
    in a normalized format. Equivalent to GET /api/tickets/{ticket_id}/events?types=chat_message
    but with a more user-friendly response format.
    
    Query parameters:
    - since_agent_seq: Optional - get messages with agent_seq > this value
    - limit: Optional - maximum number of messages (default: 500)
    
    Headers:
    - X-Device-Id: Required - Device ID for authorization
    
    Returns:
        Normalized list of chat messages:
        {
            "ticket_id": "...",
            "messages": [
                {
                    "message_id": "...",
                    "sender_role": "user|support|agent|system",
                    "text": "...",
                    "ts": "2026-01-10T12:00:00Z",
                    "agent_seq": 5,  # или null для server-originated сообщений
                    "attachments": [...],
                    "created_at": "2026-01-10T12:00:00Z"
                },
                ...
            ],
            "count": 10,
            "filters": {
                "since_agent_seq": 5
            }
        }
    
    Example:
        # Get all chat messages
        GET /api/tickets/550e8400-e29b-41d4-a716-446655440000/messages
        
        # Get messages since agent_seq=5
        GET /api/tickets/550e8400-e29b-41d4-a716-446655440000/messages?since_agent_seq=5
    """
    if not DB_AVAILABLE:
        return web.json_response(
            {
                "error": "Database not available",
                "message": "Chat history requires database persistence"
            },
            status=503
        )
    
    try:
        # Extract parameters
        ticket_id = request.match_info.get("ticket_id")
        since_agent_seq = request.query.get("since_agent_seq")
        limit = int(request.query.get("limit", "500"))
        
        # Extract device_id from header for authorization
        auth_device_id = request.headers.get("X-Device-Id")
        
        if not ticket_id:
            return web.json_response(
                {"error": "Missing ticket_id"},
                status=400
            )
        
        if not auth_device_id:
            return web.json_response(
                {"error": "Missing X-Device-Id header"},
                status=400
            )
        
        # Convert since_agent_seq to int if provided
        if since_agent_seq is not None:
            try:
                since_agent_seq = int(since_agent_seq)
            except ValueError:
                return web.json_response(
                    {"error": "Invalid since_agent_seq parameter"},
                    status=400
                )
        
        # Validate limit
        if limit < 1 or limit > 10000:
            return web.json_response(
                {"error": "Limit must be between 1 and 10000"},
                status=400
            )
        
        # Get events from database
        async with get_session() as session:
            repo = TicketEventsRepo(session)
            
            # Check ticket ownership
            ticket_device_id = await repo.get_ticket_device_id(ticket_id)
            
            if ticket_device_id is None:
                return web.json_response(
                    {"error": "Ticket not found"},
                    status=404
                )
            
            # Authorization check - only bound device can access
            if ticket_device_id != auth_device_id:
                return web.json_response(
                    {"error": "Authorization denied"},
                    status=403
                )
            
            # Get only chat_message events
            events = await repo.get_events(
                ticket_id=ticket_id,
                since_agent_seq=since_agent_seq,
                limit=limit,
                event_types=["chat_message"]  # Filter only chat messages
            )
            
            # Stage 4: agent/requester view gets only public messages
            messages = []
            for e in events:
                payload = e.payload or {}
                if payload.get("visibility") == "internal":
                    continue
                sender_role = (
                    payload.get("from")
                    or payload.get("from_role")
                    or payload.get("sender_role")
                    or "unknown"
                )
                attachments = payload.get("attachments", [])
                if not isinstance(attachments, list):
                    attachments = []
                attachment_refs = payload.get("attachment_refs", [])
                if not isinstance(attachment_refs, list):
                    attachment_refs = []
                
                message = {
                    "message_id": payload.get("message_id"),
                    "sender_role": sender_role,
                    "text": payload.get("text", ""),
                    "ts": payload.get("ts"),
                    "agent_seq": e.agent_seq,
                    "attachments": attachments,
                    "attachment_refs": attachment_refs,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                    "visibility": payload.get("visibility", "public"),
                }
                
                messages.append(message)
            
            # Include filters in response for clarity
            response_filters = {}
            if since_agent_seq is not None:
                response_filters["since_agent_seq"] = since_agent_seq
            
            return web.json_response({
                "ticket_id": ticket_id,
                "messages": messages,
                "count": len(messages),
                "filters": response_filters if response_filters else None
            })
    
    except Exception as e:
        logger.error(f"[handle_ticket_messages] Error: {e}", exc_info=True)
        return web.json_response(
            {"error": "Internal server error", "message": str(e)},
            status=500
        )


async def handle_get_device_events(request):
    """
    Get replay events for a specific device.
    
    GET /api/devices/{device_id}/events
    
    Query parameters:
    - since_device_seq: Optional - get events with device_seq > this value
    - limit: Optional - maximum number of events (default: 1000)
    
    Headers:
    - X-Device-Id: Required - Device ID for authorization
    
    Returns:
        JSON response with device events ordered by device_seq
    
    Example:
        GET /api/devices/device-001/events?since_device_seq=10
        
        Response:
        {
            "device_id": "device-001",
            "events": [
                {
                    "id": 456,
                    "device_id": "device-001",
                    "device_seq": 11,
                    "event_type": "system_metrics",
                    "payload": {...},
                    "trace_id": "trace-789",
                    "event_id": "evt-012",
                    "created_at": "2026-01-10T12:00:00Z"
                },
                ...
            ],
            "count": 3
        }
    """
    if not DB_AVAILABLE:
        return web.json_response(
            {
                "error": "Database not available",
                "message": "Event replay requires database persistence"
            },
            status=503
        )
    
    try:
        # Extract parameters
        device_id = request.match_info.get("device_id")
        since_device_seq = request.query.get("since_device_seq")
        limit = int(request.query.get("limit", "1000"))
        
        # Extract device_id from header for authorization
        auth_device_id = request.headers.get("X-Device-Id")
        
        if not device_id:
            return web.json_response(
                {"error": "Missing device_id"},
                status=400
            )
        
        if not auth_device_id:
            return web.json_response(
                {"error": "Missing X-Device-Id header"},
                status=400
            )
        
        # Authorization check - device can only access its own events
        if device_id != auth_device_id:
            return web.json_response(
                {"error": "Authorization denied"},
                status=403
            )
        
        # Convert since_device_seq to int if provided
        if since_device_seq is not None:
            try:
                since_device_seq = int(since_device_seq)
            except ValueError:
                return web.json_response(
                    {"error": "Invalid since_device_seq parameter"},
                    status=400
                )
        
        # Validate limit
        if limit < 1 or limit > 10000:
            return web.json_response(
                {"error": "Limit must be between 1 and 10000"},
                status=400
            )
        
        # Get events from database
        async with get_session() as session:
            repo = DeviceEventsRepo(session)
            events = await repo.get_events(
                device_id=device_id,
                since_device_seq=since_device_seq,
                limit=limit
            )
            
            # Convert to dict for JSON serialization
            events_data = [
                {
                    "id": e.id,
                    "device_id": e.device_id,
                    "device_seq": e.device_seq,
                    "event_type": e.event_type,
                    "payload": e.payload,
                    "trace_id": e.trace_id,
                    "event_id": e.event_id,
                    "created_at": e.created_at.isoformat() if e.created_at else None
                }
                for e in events
            ]
            
            return web.json_response({
                "device_id": device_id,
                "events": events_data,
                "count": len(events_data)
            })
    
    except Exception as e:
        logger.error(f"[handle_get_device_events] Error: {e}", exc_info=True)
        return web.json_response(
            {"error": "Internal server error", "message": str(e)},
            status=500
        )
