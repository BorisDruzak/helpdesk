from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from problem.candidate_service import ProblemCandidateService
from problem.known_error_service import ProblemKnownErrorService
from scripts.check_domain_import_boundaries import find_forbidden_imports


pytestmark = pytest.mark.no_db

WORKSPACE = Path(__file__).resolve().parents[2]


class _ProblemSession:
    def __init__(self) -> None:
        self.problem = SimpleNamespace(
            problem_id="problem-boundary",
            problem_key="PRB-1",
            title="VPN failure",
            description="VPN failure pattern",
            status="investigating",
        )
        self.writes: list[object] = []

    async def get(self, _model: object, problem_id: str) -> object | None:
        return self.problem if problem_id == self.problem.problem_id else None

    async def execute(self, _statement: object) -> object:
        raise AssertionError("problem draft must not query local Knowledge persistence")

    def add(self, value: object) -> None:
        self.writes.append(value)

    async def flush(self) -> None:
        raise AssertionError("problem draft must not write local Knowledge persistence")


class _EmptyResult:
    def scalars(self) -> _EmptyResult:
        return self

    def all(self) -> list[object]:
        return []


class _RecordingSession:
    def __init__(self) -> None:
        self.statements: list[str] = []

    async def execute(self, statement: object) -> _EmptyResult:
        self.statements.append(str(statement).lower())
        return _EmptyResult()


@pytest.mark.asyncio
async def test_problem_known_error_does_not_create_local_knowledge_item() -> None:
    session = _ProblemSession()

    result = await ProblemKnownErrorService(session).create_known_error_draft(
        "problem-boundary",
        actor_id="support-1",
    )

    assert result == {
        "problem_id": "problem-boundary",
        "link_type": "known_error",
        "external_reference": None,
        "status": "unavailable",
        "code": "knowledge_unavailable",
    }
    assert session.problem.status == "investigating"
    assert session.writes == []


@pytest.mark.asyncio
async def test_problem_candidate_scan_does_not_query_local_knowledge_tables() -> None:
    session = _RecordingSession()

    result = await ProblemCandidateService(session).scan(
        actor_id="support-1",
        now=datetime(2026, 8, 9, tzinfo=timezone.utc),
        dry_run=True,
    )

    assert result["candidates"] == []
    assert not any(
        table_name in statement
        for statement in session.statements
        for table_name in ("knowledge_feedback_events", "knowledge_gap_findings")
    )


def test_problem_services_have_no_local_knowledge_dependency() -> None:
    violations = find_forbidden_imports(WORKSPACE)
    owned_paths = {
        WORKSPACE / "server" / "problem" / "known_error_service.py",
        WORKSPACE / "server" / "problem" / "candidate_service.py",
    }

    assert [violation.imported for violation in violations if violation.path in owned_paths] == []
