"""
UI Publisher interface and implementation for pushing events to UI subscribers.
"""
from abc import ABC, abstractmethod
from typing import Optional
from app.db.models import Operation
from state_manager import StateManager


class UiPublisher(ABC):
    """Interface for UI event publishing."""
    
    @abstractmethod
    async def push_operation_updated(self, operation: Operation):
        """Push operation_updated event."""
        pass


class UiPublisherImpl(UiPublisher):
    """Implementation using SubscriptionRegistry."""
    
    def __init__(self, state: StateManager):
        self.state = state
    
    async def push_operation_updated(self, operation: Operation):
        """Push operation_updated event."""
        from websocket.ui_handler import push_operation_updated
        await push_operation_updated(self.state, operation)


class NoOpUiPublisher(UiPublisher):
    """No-op publisher for testing."""
    
    async def push_operation_updated(self, operation: Operation):
        """No-op."""
        pass


