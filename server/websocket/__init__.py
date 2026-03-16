"""
WebSocket module - WebSocket коммуникация с агентами и UI.
"""

from .agent_handler import websocket_handler
from .ui_handler import websocket_ui_handler
from .protocol import send_ws_command

__all__ = ['websocket_handler', 'websocket_ui_handler', 'send_ws_command']

