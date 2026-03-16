"""
Repository for job_events table operations.
"""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, and_, or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.models import JobEvent


class JobEventsRepo:
    """
    Repository for managing job events in the database.
    
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
    
    @staticmethod
    def _extract_event_metadata(payload: dict) -> tuple[Optional[int], Optional[str], datetime]:
        """
        Extract metadata from event payload.
        
        Args:
            payload: Event payload dictionary
        
        Returns:
            Tuple of (seq, message_id, timestamp)
        """
        # Extract seq if present
        seq = payload.get("seq")
        if seq is not None:
            try:
                seq = int(seq)
            except (ValueError, TypeError):
                seq = None
        
        # Extract message_id if present
        message_id = payload.get("message_id")
        
        # Extract timestamp - try multiple fields
        ts = None
        for ts_field in ["ts", "timestamp", "created_at"]:
            ts_value = payload.get(ts_field)
            if ts_value is not None:
                # Handle both float (Unix timestamp) and string (ISO format)
                if isinstance(ts_value, (int, float)):
                    ts = datetime.fromtimestamp(ts_value, tz=timezone.utc)
                    break
                elif isinstance(ts_value, str):
                    try:
                        # Try parsing ISO format
                        ts = datetime.fromisoformat(ts_value.replace('Z', '+00:00'))
                        break
                    except (ValueError, AttributeError):
                        pass
        
        # Default to current time if no valid timestamp found
        if ts is None:
            ts = datetime.now(timezone.utc)
        
        return seq, message_id, ts
    
    async def add_event(
        self,
        job_id: str,
        event_type: str,
        payload: dict,
    ) -> None:
        """
        Add a job event to the database with automatic deduplication.
        
        Extracts seq, message_id, and timestamp from payload.
        Uses PostgreSQL ON CONFLICT DO NOTHING for server-side deduplication.
        
        Args:
            job_id: Job identifier
            event_type: Type of event (e.g., 'chat_message', 'chat_started')
            payload: Full event payload as dict
        """
        # Extract metadata
        seq, message_id, ts = self._extract_event_metadata(payload)
        
        # Create insert statement
        stmt = insert(JobEvent).values(
            job_id=job_id,
            seq=seq,
            ts=ts,
            event_type=event_type,
            message_id=message_id,
            payload=payload,
        )
        
        # Add ON CONFLICT clause only if message_id is not None
        # Partial unique index works only with NOT NULL message_id
        if message_id is not None:
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["job_id", "message_id"],
            )
        
        try:
            await self.session.execute(stmt)
            await self.session.commit()
            
            logger.debug(
                f"[JobEventsRepo] Stored event: job_id={job_id} "
                f"event_type={event_type} seq={seq} message_id={message_id}"
            )
        except Exception as e:
            logger.error(
                f"[JobEventsRepo] Failed to store event: job_id={job_id} "
                f"event_type={event_type} error={e}"
            )
            await self.session.rollback()
            # Don't raise - best effort persistence
    
    async def get_last_events(
        self,
        job_id: str,
        limit: int = 200,
    ) -> List[dict]:
        """
        Get the last N events for a job, ordered chronologically (oldest to newest).
        
        Returns events ordered by:
        1. seq ASC (if seq is present)
        2. ts ASC (for events without seq or as secondary sort)
        
        Args:
            job_id: Job identifier
            limit: Maximum number of events to return (default: 200)
        
        Returns:
            List of event payload dictionaries in chronological order
        """
        # First, get the last N events (most recent)
        # We need to get them in reverse order first, then flip
        subquery = (
            select(JobEvent)
            .where(JobEvent.job_id == job_id)
            .order_by(JobEvent.ts.desc(), JobEvent.seq.desc())
            .limit(limit)
            .subquery()
        )
        
        # Then order them chronologically for replay
        stmt = (
            select(subquery)
            .order_by(
                # Primary: order by seq if available
                subquery.c.seq.asc().nullslast(),
                # Secondary: order by timestamp
                subquery.c.ts.asc(),
            )
        )
        
        result = await self.session.execute(stmt)
        rows = result.all()
        
        # Extract payloads
        payloads = [row[0].payload for row in rows]
        
        logger.info(
            f"[JobEventsRepo] Retrieved {len(payloads)} last events for job_id={job_id}"
        )
        
        return payloads
    
    async def get_events_since_seq(
        self,
        job_id: str,
        since_seq: int,
        limit: int = 2000,
    ) -> List[dict]:
        """
        Get events with seq > since_seq, ordered by seq ascending.
        
        Args:
            job_id: Job identifier
            since_seq: Get events with seq greater than this value
            limit: Maximum number of events to return (default: 2000)
        
        Returns:
            List of event payload dictionaries ordered by seq
        """
        stmt = (
            select(JobEvent)
            .where(
                and_(
                    JobEvent.job_id == job_id,
                    JobEvent.seq > since_seq,
                    JobEvent.seq.isnot(None),  # Only events with seq
                )
            )
            .order_by(JobEvent.seq.asc())
            .limit(limit)
        )
        
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        
        # Extract payloads
        payloads = [row.payload for row in rows]
        
        logger.info(
            f"[JobEventsRepo] Retrieved {len(payloads)} events since seq={since_seq} "
            f"for job_id={job_id}"
        )
        
        return payloads
    
    async def get_events_since_id(
        self,
        job_id: str,
        since_event_id: int,
        limit: int = 500
    ) -> List[JobEvent]:
        """
        Get job events with id > since_event_id.
        
        Used for UI catch-up after reconnect.
        
        Args:
            job_id: Job identifier
            since_event_id: Event ID to start from (exclusive)
            limit: Maximum number of events to return (default: 500)
        
        Returns:
            List of JobEvent objects ordered by id ascending
        """
        stmt = (
            select(JobEvent)
            .where(
                JobEvent.job_id == job_id,
                JobEvent.id > since_event_id
            )
            .order_by(JobEvent.id.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        events = result.scalars().all()
        
        logger.debug(
            f"[JobEventsRepo] Retrieved {len(events)} events for job_id={job_id} "
            f"since_event_id={since_event_id}"
        )
        
        return list(events)


