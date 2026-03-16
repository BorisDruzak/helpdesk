"""
Subscription Registry for UI WebSocket subscriptions.

Manages subscriptions for tickets and devices with explicit set() for reliability.
"""
import asyncio
from typing import Dict, Set, Optional
from aiohttp import web
from loguru import logger


class SubscriptionRegistry:
    """
    Manages UI WebSocket subscriptions for tickets and devices.
    
    Uses explicit set() with manual cleanup for reliability.
    WeakSet may not work reliably with aiohttp WebSocketResponse.
    """
    
    def __init__(self):
        # ticket_id -> Set[WebSocketResponse]
        self.ticket_subscribers: Dict[str, Set] = {}
        # device_id -> Set[WebSocketResponse]
        self.device_subscribers: Dict[str, Set] = {}
        # job_id -> Set[WebSocketResponse] (for job-based chat)
        self.chat_subscribers: Dict[str, Set] = {}
        # Lock for thread-safety
        self._lock = asyncio.Lock()
    
    async def add_ticket_subscriber(self, ticket_id: str, ws: web.WebSocketResponse):
        """Add WebSocket to ticket subscription."""
        async with self._lock:
            if ticket_id not in self.ticket_subscribers:
                self.ticket_subscribers[ticket_id] = set()
            self.ticket_subscribers[ticket_id].add(ws)
            logger.debug(f"[SubscriptionRegistry] Added ticket subscriber: ticket_id={ticket_id}")
    
    async def remove_ticket_subscriber(self, ticket_id: str, ws: web.WebSocketResponse):
        """Remove WebSocket from ticket subscription."""
        async with self._lock:
            if ticket_id in self.ticket_subscribers:
                self.ticket_subscribers[ticket_id].discard(ws)
                if not self.ticket_subscribers[ticket_id]:
                    del self.ticket_subscribers[ticket_id]
                    logger.debug(f"[SubscriptionRegistry] Removed ticket subscription: ticket_id={ticket_id}")
    
    async def add_device_subscriber(self, device_id: str, ws: web.WebSocketResponse):
        """Add WebSocket to device subscription."""
        async with self._lock:
            if device_id not in self.device_subscribers:
                self.device_subscribers[device_id] = set()
            self.device_subscribers[device_id].add(ws)
            logger.debug(f"[SubscriptionRegistry] Added device subscriber: device_id={device_id}")
    
    async def remove_device_subscriber(self, device_id: str, ws: web.WebSocketResponse):
        """Remove WebSocket from device subscription."""
        async with self._lock:
            if device_id in self.device_subscribers:
                self.device_subscribers[device_id].discard(ws)
                if not self.device_subscribers[device_id]:
                    del self.device_subscribers[device_id]
                    logger.debug(f"[SubscriptionRegistry] Removed device subscription: device_id={device_id}")
    
    async def broadcast_to_ticket(self, ticket_id: str, message: dict):
        """
        Broadcast message to all ticket subscribers.
        
        Automatically removes dead connections on send failure.
        """
        async with self._lock:
            subscribers = self.ticket_subscribers.get(ticket_id, set()).copy()
        
        dead_ws = set()
        for ws in subscribers:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.debug(f"[SubscriptionRegistry] Dead WS in ticket {ticket_id}: {e}")
                dead_ws.add(ws)
        
        # Clean up dead connections
        if dead_ws:
            async with self._lock:
                if ticket_id in self.ticket_subscribers:
                    self.ticket_subscribers[ticket_id] -= dead_ws
                    if not self.ticket_subscribers[ticket_id]:
                        del self.ticket_subscribers[ticket_id]
    
    async def broadcast_to_device(self, device_id: str, message: dict):
        """
        Broadcast message to all device subscribers.
        
        Automatically removes dead connections on send failure.
        """
        async with self._lock:
            subscribers = self.device_subscribers.get(device_id, set()).copy()
        
        dead_ws = set()
        for ws in subscribers:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.debug(f"[SubscriptionRegistry] Dead WS in device {device_id}: {e}")
                dead_ws.add(ws)
        
        # Clean up dead connections
        if dead_ws:
            async with self._lock:
                if device_id in self.device_subscribers:
                    self.device_subscribers[device_id] -= dead_ws
                    if not self.device_subscribers[device_id]:
                        del self.device_subscribers[device_id]
    
    async def cleanup_ws(self, ws: web.WebSocketResponse):
        """
        Remove WebSocket from all subscriptions.
        
        Called on disconnect to ensure complete cleanup.
        """
        async with self._lock:
            # Remove from all ticket subscriptions
            for ticket_id in list(self.ticket_subscribers.keys()):
                self.ticket_subscribers[ticket_id].discard(ws)
                if not self.ticket_subscribers[ticket_id]:
                    del self.ticket_subscribers[ticket_id]
            
            # Remove from all device subscriptions
            for device_id in list(self.device_subscribers.keys()):
                self.device_subscribers[device_id].discard(ws)
                if not self.device_subscribers[device_id]:
                    del self.device_subscribers[device_id]
            
            # Remove from all chat subscriptions
            for job_id in list(self.chat_subscribers.keys()):
                self.chat_subscribers[job_id].discard(ws)
                if not self.chat_subscribers[job_id]:
                    del self.chat_subscribers[job_id]
        
        logger.debug(f"[SubscriptionRegistry] Cleaned up WebSocket from all subscriptions")
    
    async def add_chat_subscriber(self, job_id: str, ws: web.WebSocketResponse):
        """Add WebSocket to chat subscription."""
        async with self._lock:
            if job_id not in self.chat_subscribers:
                self.chat_subscribers[job_id] = set()
            self.chat_subscribers[job_id].add(ws)
            logger.debug(f"[SubscriptionRegistry] Added chat subscriber: job_id={job_id}")
    
    async def remove_chat_subscriber(self, job_id: str, ws: web.WebSocketResponse):
        """Remove WebSocket from chat subscription."""
        async with self._lock:
            if job_id in self.chat_subscribers:
                self.chat_subscribers[job_id].discard(ws)
                if not self.chat_subscribers[job_id]:
                    del self.chat_subscribers[job_id]
                    logger.debug(f"[SubscriptionRegistry] Removed chat subscription: job_id={job_id}")
    
    async def broadcast_to_chat(self, job_id: str, message: dict):
        """
        Broadcast message to all chat subscribers.
        
        Automatically removes dead connections on send failure.
        """
        async with self._lock:
            subscribers = self.chat_subscribers.get(job_id, set()).copy()
        
        dead_ws = set()
        for ws in subscribers:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.debug(f"[SubscriptionRegistry] Dead WS in chat {job_id}: {e}")
                dead_ws.add(ws)
        
        # Clean up dead connections
        if dead_ws:
            async with self._lock:
                if job_id in self.chat_subscribers:
                    self.chat_subscribers[job_id] -= dead_ws
                    if not self.chat_subscribers[job_id]:
                        del self.chat_subscribers[job_id]

