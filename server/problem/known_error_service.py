from __future__ import annotations

from typing import Any

from app.db.models import Problem


class ProblemKnownErrorService:
    def __init__(self, session) -> None:
        self.session = session

    async def create_known_error_draft(self, problem_id: str, *, actor_id: str | None) -> dict[str, Any]:
        return await self._unavailable_projection(problem_id, link_type="known_error", actor_id=actor_id)

    async def create_workaround_draft(self, problem_id: str, *, actor_id: str | None) -> dict[str, Any]:
        return await self._unavailable_projection(problem_id, link_type="workaround", actor_id=actor_id)

    async def _unavailable_projection(
        self,
        problem_id: str,
        *,
        link_type: str,
        actor_id: str | None,
    ) -> dict[str, Any]:
        del actor_id
        problem = await self.session.get(Problem, problem_id)
        if problem is None:
            raise ValueError("problem not found")
        return {
            "problem_id": problem.problem_id,
            "link_type": link_type,
            "external_reference": None,
            "status": "unavailable",
            "code": "knowledge_unavailable",
        }
