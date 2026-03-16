"""
Stage 5: Relations — links (duplicate/related), parent-child.

- Self-link forbidden.
- duplicate: directional (src=duplicate, dst=master).
- related: canonical storage in lexicographic order (min_id, max_id).
"""
from __future__ import annotations

from typing import Optional, Tuple, List, Any

from loguru import logger


class TicketRelationsService:
    """Валидация и канонизация связей тикетов."""

    @staticmethod
    def validate_self_link(ticket_id: str, other_id: str) -> Optional[str]:
        """Forbid self-link. Returns error message or None."""
        if ticket_id == other_id:
            return "Self-link is not allowed"
        return None

    @staticmethod
    def canonicalize_related(ticket_id: str, other_id: str) -> Tuple[str, str]:
        """For related: return (min_id, max_id) for consistent storage."""
        if ticket_id < other_id:
            return (ticket_id, other_id)
        return (other_id, ticket_id)

    @staticmethod
    def duplicate_direction(duplicate_ticket_id: str, master_ticket_id: str) -> Tuple[str, str]:
        """For duplicate: src=duplicate, dst=master. Returns (src_ticket_id, dst_ticket_id)."""
        return (duplicate_ticket_id, master_ticket_id)

    async def add_link(
        self,
        repo,
        ticket_id: str,
        other_ticket_id: str,
        link_type: str,
        created_by: Optional[str],
        add_event_fn,
        device_id: str,
    ) -> Tuple[Optional[Any], Optional[str]]:
        """
        Add ticket link with validation and canonicalization.
        Returns (link_or_None, error_message).
        Writes ticket_link_added event on success.
        """
        err = self.validate_self_link(ticket_id, other_ticket_id)
        if err:
            return (None, err)

        if link_type not in ("duplicate", "related"):
            return (None, "link_type must be 'duplicate' or 'related'")

        if link_type == "related":
            src, dst = self.canonicalize_related(ticket_id, other_ticket_id)
            if await repo.exists_ticket_link(src, dst, "related"):
                return (None, "Related link already exists")
        else:
            # duplicate: src=duplicate, dst=master (this ticket is duplicate of other)
            src, dst = self.duplicate_direction(ticket_id, other_ticket_id)
            if await repo.exists_ticket_link(src, dst, "duplicate"):
                return (None, "Duplicate link already exists")

        try:
            link = await repo.add_ticket_link(src, dst, link_type, created_by)
        except Exception as e:
            logger.warning(f"[Relations] add_ticket_link failed: {e}")
            return (None, str(e))

        await add_event_fn(
            ticket_id,
            device_id,
            "ticket_link_added",
            {"link_id": link.id, "src_ticket_id": src, "dst_ticket_id": dst, "link_type": link_type, "created_by": created_by},
        )
        return (link, None)

    async def set_parent(
        self,
        repo,
        ticket_id: str,
        parent_ticket_id: Optional[str],
        actor_id: str,
        add_event_fn,
        device_id: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Set or clear parent_ticket_id. Forbid parent=self and cycles.
        Returns (success, error_message).
        Writes parent_ticket_changed event on success.
        """
        if parent_ticket_id is not None:
            err = self.validate_self_link(ticket_id, parent_ticket_id)
            if err:
                return (False, err)
            # Cycle: parent's ancestor chain must not contain ticket_id
            parent = await repo.get_ticket(parent_ticket_id)
            if not parent:
                return (False, "Parent ticket not found")
            current = parent
            while current:
                if getattr(current, "ticket_id", None) == ticket_id:
                    return (False, "Cycle in parent-child would be created")
                pid = getattr(current, "parent_ticket_id", None)
                if not pid:
                    break
                current = await repo.get_ticket(pid)

        ok = await repo.set_parent_ticket(ticket_id, parent_ticket_id)
        if not ok:
            return (False, "Ticket not found")
        await add_event_fn(
            ticket_id,
            device_id,
            "parent_ticket_changed",
            {"parent_ticket_id": parent_ticket_id, "actor_id": actor_id},
        )
        return (True, None)
