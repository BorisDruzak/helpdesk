"""
Stage 7: Репозиторий для problems и problem_ticket_links.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Problem, ProblemTicketLink


class ProblemsRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        title: str,
        description: str,
        status: str = "New",
        priority: str = "P3",
        owner_id: Optional[str] = None,
    ) -> Problem:
        problem_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        p = Problem(
            problem_id=problem_id,
            title=title,
            description=description,
            status=status,
            priority=priority,
            owner_id=owner_id,
            created_at=now,
            updated_at=now,
        )
        self.session.add(p)
        await self.session.flush()
        return p

    async def get(self, problem_id: str) -> Optional[Problem]:
        stmt = select(Problem).where(Problem.problem_id == problem_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_problems(
        self,
        status: Optional[str] = None,
        owner_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Problem]:
        stmt = select(Problem).order_by(Problem.updated_at.desc())
        if status:
            stmt = stmt.where(Problem.status == status)
        if owner_id:
            stmt = stmt.where(Problem.owner_id == owner_id)
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(
        self,
        problem_id: str,
        new_status: str,
        resolved_at: Optional[datetime] = None,
        closed_at: Optional[datetime] = None,
        root_cause: Optional[str] = None,
        workaround: Optional[str] = None,
        kb_article_ref: Optional[str] = None,
    ) -> bool:
        now = datetime.now(timezone.utc)
        values: dict = {"status": new_status, "updated_at": now}
        if resolved_at is not None:
            values["resolved_at"] = resolved_at
        if closed_at is not None:
            values["closed_at"] = closed_at
        if root_cause is not None:
            values["root_cause"] = root_cause
        if workaround is not None:
            values["workaround"] = workaround
        if kb_article_ref is not None:
            values["kb_article_ref"] = kb_article_ref
        stmt = update(Problem).where(Problem.problem_id == problem_id).values(**values)
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def add_ticket_link(self, problem_id: str, ticket_id: str, linked_by: str) -> bool:
        """Добавить связь problem-ticket. При дубликате (UNIQUE) — IntegrityError."""
        link = ProblemTicketLink(
            problem_id=problem_id,
            ticket_id=ticket_id,
            linked_by=linked_by,
        )
        self.session.add(link)
        await self.session.flush()
        return True

    async def remove_ticket_link(self, problem_id: str, ticket_id: str) -> bool:
        stmt = delete(ProblemTicketLink).where(
            ProblemTicketLink.problem_id == problem_id,
            ProblemTicketLink.ticket_id == ticket_id,
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def list_ticket_links(self, problem_id: str) -> List[ProblemTicketLink]:
        stmt = (
            select(ProblemTicketLink)
            .where(ProblemTicketLink.problem_id == problem_id)
            .order_by(ProblemTicketLink.linked_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_problems_by_ticket(self, ticket_id: str) -> List[tuple[Problem, ProblemTicketLink]]:
        """Возвращает (Problem, link) для тикета."""
        stmt = (
            select(Problem, ProblemTicketLink)
            .join(ProblemTicketLink, Problem.problem_id == ProblemTicketLink.problem_id)
            .where(ProblemTicketLink.ticket_id == ticket_id)
            .order_by(ProblemTicketLink.linked_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.all())
