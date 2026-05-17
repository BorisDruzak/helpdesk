from __future__ import annotations

import uuid
from typing import Any

from app.db.models import KnowledgeSpace, Problem, ProblemKnownErrorLink
from knowledge.graph_service import KnowledgeGraphService
from app.repos.knowledge_repo import KnowledgeRepo
from problem.contracts import clean_text


class ProblemKnownErrorService:
    def __init__(self, session) -> None:
        self.session = session

    async def create_known_error_draft(self, problem_id: str, *, actor_id: str | None) -> dict[str, Any]:
        return await self._create_draft(problem_id, item_type="known_error", link_type="known_error", actor_id=actor_id)

    async def create_workaround_draft(self, problem_id: str, *, actor_id: str | None) -> dict[str, Any]:
        return await self._create_draft(problem_id, item_type="workaround", link_type="workaround", actor_id=actor_id)

    async def _create_draft(self, problem_id: str, *, item_type: str, link_type: str, actor_id: str | None) -> dict[str, Any]:
        problem = await self.session.get(Problem, problem_id)
        if problem is None:
            raise ValueError("problem not found")
        space_code = await self._ensure_space(actor_id=actor_id)
        slug = f"{item_type}-{problem.problem_key.lower()}"
        repo = KnowledgeRepo(self.session)
        item = await repo.create_item_draft(
            {
                "space_code": space_code,
                "slug": slug,
                "item_type": item_type,
                "title": f"{problem.problem_key}: {problem.title}",
                "summary": problem.description,
                "visibility": "support_internal",
                "source_kind": "problem",
                "source_ref": problem.problem_id,
                "tags": ["problem", problem.problem_key],
                "metadata": {
                    "problem_id": problem.problem_id,
                    "problem_key": problem.problem_key,
                    "service_code": problem.service_code,
                    "offering_code": problem.offering_code,
                    "status": problem.status,
                    "known_error_status": problem.status,
                    "workaround": problem.workaround_summary,
                    "permanent_fix": problem.permanent_fix_summary,
                },
            },
            actor_id=actor_id,
            actor_role="support",
        )
        body = self._body(problem, item_type=item_type)
        await repo.create_version(item["item_id"], {"title": item["title"], "summary": item["summary"], "body": body}, actor_id=actor_id, actor_role="support")
        link = ProblemKnownErrorLink(
            link_id=str(uuid.uuid4()),
            problem_id=problem.problem_id,
            knowledge_item_id=item["item_id"],
            link_type=link_type,
            visibility="support_internal",
            created_by=actor_id,
            metadata_json={},
        )
        self.session.add(link)
        await KnowledgeGraphService(self.session).ensure_item_binding_edges(
            item["item_id"],
            service_code=problem.service_code,
            offering_code=problem.offering_code,
            actor_id=actor_id,
        )
        await self.session.flush()
        if link_type == "known_error" and problem.status == "investigating":
            problem.status = "known_error"
        if link_type == "workaround" and problem.status in {"investigating", "known_error"}:
            problem.status = "workaround_available"
        return {"link_id": link.link_id, "problem_id": problem.problem_id, "knowledge_item_id": item["item_id"], "link_type": link.link_type}

    async def _ensure_space(self, *, actor_id: str | None) -> str:
        repo = KnowledgeRepo(self.session)
        existing = await repo.get_space_by_code("problem-management")
        if existing is not None:
            return existing.code
        row = KnowledgeSpace(
            space_id=str(uuid.uuid4()),
            code="problem-management",
            title="Problem Management",
            description="Known errors and workarounds created from Problem Management.",
            visibility="support_internal",
            lifecycle_status="active",
            allowed_item_types=["known_error", "workaround", "runbook", "article"],
            created_by=actor_id,
            updated_by=actor_id,
        )
        self.session.add(row)
        await self.session.flush()
        return row.code

    def _body(self, problem: Problem, *, item_type: str) -> str:
        workaround = clean_text(problem.workaround_summary or problem.workaround) or "Unknown."
        fix = clean_text(problem.permanent_fix_summary) or "Permanent fix is not confirmed yet."
        return "\n".join(
            [
                f"# {problem.problem_key}: {problem.title}",
                "",
                f"Problem status: {problem.status}",
                f"Affected service: {problem.service_code or 'legacy'} / {problem.offering_code or 'uncategorized'}",
                "",
                "## Symptoms",
                problem.description,
                "",
                "## Root cause",
                clean_text(problem.root_cause_summary or problem.root_cause) or "Under investigation.",
                "",
                "## Workaround",
                workaround,
                "",
                "## Permanent fix",
                fix,
            ]
        )
