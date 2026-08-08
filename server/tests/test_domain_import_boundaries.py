from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.no_db


WORKSPACE = Path(__file__).resolve().parents[2]
CHECKER = WORKSPACE / "scripts" / "check_domain_import_boundaries.py"


def run_check(workspace: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), "--workspace", str(workspace)],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )


def test_check_rejects_ticket_import_of_local_knowledge(tmp_path: Path) -> None:
    source = tmp_path / "server" / "tickets" / "bad.py"
    source.parent.mkdir(parents=True)
    source.write_text("from knowledge.search_service import KnowledgeSearchService\n", encoding="utf-8")

    result = run_check(tmp_path)

    assert result.returncode == 1
    assert "server/tickets/bad.py:1" in result.stdout
    assert "knowledge.search_service" in result.stdout


def test_check_rejects_knowledge_repository_import(tmp_path: Path) -> None:
    source = tmp_path / "server" / "tickets" / "bad.py"
    source.parent.mkdir(parents=True)
    source.write_text("from app.repos.knowledge_repo import KnowledgeRepository\n", encoding="utf-8")

    result = run_check(tmp_path)

    assert result.returncode == 1
    assert "app.repos.knowledge_repo" in result.stdout


def test_check_rejects_relative_knowledge_repository_import(tmp_path: Path) -> None:
    source = tmp_path / "server" / "app" / "repos" / "consumer.py"
    source.parent.mkdir(parents=True)
    source.write_text("from .knowledge_repo import KnowledgeRepo\n", encoding="utf-8")

    result = run_check(tmp_path)

    assert result.returncode == 1
    assert "app.repos.knowledge_repo" in result.stdout


def test_check_rejects_parent_relative_knowledge_repository_import(tmp_path: Path) -> None:
    source = tmp_path / "server" / "app" / "services" / "consumer.py"
    source.parent.mkdir(parents=True)
    source.write_text("from ..repos import knowledge_repo\n", encoding="utf-8")

    result = run_check(tmp_path)

    assert result.returncode == 1
    assert "from app.repos import knowledge_repo" in result.stdout


def test_check_rejects_knowledge_orm_model_import(tmp_path: Path) -> None:
    source = tmp_path / "server" / "tickets" / "bad.py"
    source.parent.mkdir(parents=True)
    source.write_text("from app.db.models import KnowledgeItem, Ticket\n", encoding="utf-8")

    result = run_check(tmp_path)

    assert result.returncode == 1
    assert "KnowledgeItem" in result.stdout


def test_check_rejects_ticket_knowledge_link_orm_model_import(tmp_path: Path) -> None:
    source = tmp_path / "server" / "tickets" / "bad.py"
    source.parent.mkdir(parents=True)
    source.write_text("from app.db.models import TicketKnowledgeLink\n", encoding="utf-8")

    result = run_check(tmp_path)

    assert result.returncode == 1
    assert "TicketKnowledgeLink" in result.stdout


def test_check_rejects_relative_ticket_knowledge_link_orm_model_import(tmp_path: Path) -> None:
    source = tmp_path / "server" / "app" / "repos" / "consumer.py"
    source.parent.mkdir(parents=True)
    source.write_text("from ..db.models import TicketKnowledgeLink\n", encoding="utf-8")

    result = run_check(tmp_path)

    assert result.returncode == 1
    assert "app.db.models" in result.stdout


def test_check_allows_knowledge_imports_in_historical_migrations(tmp_path: Path) -> None:
    source = tmp_path / "server" / "app" / "db" / "migrations" / "versions" / "old.py"
    source.parent.mkdir(parents=True)
    source.write_text("from knowledge.search_service import KnowledgeSearchService\n", encoding="utf-8")

    result = run_check(tmp_path)

    assert result.returncode == 0


def test_check_ignores_comment_text(tmp_path: Path) -> None:
    source = tmp_path / "server" / "tickets" / "good.py"
    source.parent.mkdir(parents=True)
    source.write_text("# from knowledge.search_service import KnowledgeSearchService\n", encoding="utf-8")

    result = run_check(tmp_path)

    assert result.returncode == 0


def test_check_allows_relative_import_named_knowledge(tmp_path: Path) -> None:
    source = tmp_path / "server" / "domain_ports" / "__init__.py"
    source.parent.mkdir(parents=True)
    source.write_text("from .knowledge import KnowledgePort\n", encoding="utf-8")

    result = run_check(tmp_path)

    assert result.returncode == 0
