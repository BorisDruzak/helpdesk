"""
Repository for device_events table operations.
"""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.models import DeviceEvent


class DeviceEventsRepo:
    """
    Repository for managing device events in the database.
    
    Provides methods for:
    - Adding events with automatic deduplication
    - Retrieving event history for replay
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize repository with a database session.
        
        Args:
            session: Async SQLAlchemy session
        """
        self.session = session
    
    async def add_event(
        self,
        device_id: str,
        device_seq: int,
        event_type: str,
        payload: dict,
        trace_id: Optional[str] = None,
        event_id: Optional[str] = None
    ) -> Optional[int]:
        """
        Add a device event to the database with automatic deduplication.
        
        Uses PostgreSQL ON CONFLICT DO NOTHING for server-side deduplication
        based on (device_id, device_seq) unique constraint.
        
        Args:
            device_id: Device identifier
            device_seq: Device sequence number (monotonic per-device)
            event_type: Type of event
            payload: Full event payload as dict
            trace_id: Optional trace ID for correlation
            event_id: Optional event ID from agent
        
        Returns:
            Event ID if inserted, None if duplicate
        
        Raises:
            Exception: If database operation fails
        """
        # Create insert statement
        stmt = insert(DeviceEvent).values(
            device_id=device_id,
            device_seq=device_seq,
            event_type=event_type,
            payload=payload,
            trace_id=trace_id,
            event_id=event_id,
            created_at=datetime.now(timezone.utc)
        )
        
        # Add ON CONFLICT clause for deduplication
        stmt = stmt.on_conflict_do_nothing(
            constraint='uq_device_events_device_seq'
        )
        
        # Execute with RETURNING to detect duplicates
        stmt = stmt.returning(DeviceEvent.id)
        
        result = await self.session.execute(stmt)
        row = result.first()
        
        if row is None:
            # Duplicate detected
            logger.debug(
                f"[DeviceEventsRepo] Duplicate event detected: "
                f"device_id={device_id} device_seq={device_seq}"
            )
            return None
        
        # New event inserted
        event_id_result = row[0]
        logger.debug(
            f"[DeviceEventsRepo] Inserted event: "
            f"id={event_id_result} device_id={device_id} "
            f"event_type={event_type} device_seq={device_seq}"
        )
        
        return event_id_result
    
    async def get_events(
        self,
        device_id: str,
        since_device_seq: Optional[int] = None,
        limit: int = 1000
    ) -> List[DeviceEvent]:
        """
        Get events for a device, optionally filtered by device_seq.
        
        Args:
            device_id: Device identifier
            since_device_seq: Optional - get events with device_seq > this value
            limit: Maximum number of events to return (default: 1000)
        
        Returns:
            List of DeviceEvent objects ordered by device_seq ascending
        """
        stmt = select(DeviceEvent).where(DeviceEvent.device_id == device_id)
        
        if since_device_seq is not None:
            stmt = stmt.where(DeviceEvent.device_seq > since_device_seq)
        
        stmt = stmt.order_by(DeviceEvent.device_seq.asc()).limit(limit)
        
        result = await self.session.execute(stmt)
        events = result.scalars().all()
        
        logger.info(
            f"[DeviceEventsRepo] Retrieved {len(events)} events for device_id={device_id} "
            f"since_device_seq={since_device_seq}"
        )
        
        return list(events)
    
    async def get_last_device_seq(self, device_id: str) -> Optional[int]:
        """
        Get the last device_seq for a device.
        
        Args:
            device_id: Device identifier
        
        Returns:
            Last device_seq if events exist, None otherwise
        """
        stmt = (
            select(DeviceEvent.device_seq)
            .where(DeviceEvent.device_id == device_id)
            .order_by(DeviceEvent.device_seq.desc())
            .limit(1)
        )
        
        result = await self.session.execute(stmt)
        row = result.first()
        
        if row is None:
            return None
        
        return row[0]
    
    async def get_events_since_id(
        self,
        device_id: str,
        since_event_id: int,
        limit: int = 500
    ) -> List[DeviceEvent]:
        """
        Get device events with id > since_event_id.
        
        Used for UI catch-up after reconnect.
        
        Args:
            device_id: Device identifier
            since_event_id: Event ID to start from (exclusive)
            limit: Maximum number of events to return (default: 500)
        
        Returns:
            List of DeviceEvent objects ordered by id ascending
        """
        stmt = (
            select(DeviceEvent)
            .where(
                DeviceEvent.device_id == device_id,
                DeviceEvent.id > since_event_id
            )
            .order_by(DeviceEvent.id.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())