from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.no_db


WORKSPACE = Path(__file__).resolve().parents[2]
CHECKER = WORKSPACE / "scripts" / "check_domain_import_boundaries.py"


def run_check(
    workspace: Path,
    *,
    registry_scope: str | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(CHECKER), "--workspace", str(workspace)]
    if registry_scope is not None:
        command.extend(["--registry-scope", registry_scope])
    return subprocess.run(
        command,
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


def test_registry_scope_rejects_ticket_orm_import(tmp_path: Path) -> None:
    source = tmp_path / "server" / "tickets" / "bad.py"
    source.parent.mkdir(parents=True)
    source.write_text("from app.db.models import RegistryPerson, Ticket\n", encoding="utf-8")

    result = run_check(tmp_path, registry_scope="tickets")

    assert result.returncode == 1
    assert "server/tickets/bad.py:1" in result.stdout
    assert "RegistryPerson" in result.stdout
    assert "Ticket" not in result.stdout


def test_registry_scope_rejects_registry_service_and_repository_imports(tmp_path: Path) -> None:
    service = tmp_path / "server" / "web_api" / "support_handlers.py"
    repository = tmp_path / "server" / "inventory" / "service.py"
    service.parent.mkdir(parents=True)
    repository.parent.mkdir(parents=True)
    service.write_text(
        "from registry.primary_agent_resolver import PrimaryAgentResolver\n",
        encoding="utf-8",
    )
    repository.write_text(
        "from app.repos.registry_repo import RegistryRepo\n",
        encoding="utf-8",
    )

    result = run_check(tmp_path, registry_scope="web_api,inventory")

    assert result.returncode == 1
    assert "registry.primary_agent_resolver" in result.stdout
    assert "app.repos.registry_repo" in result.stdout


def test_registry_scope_rejects_registry_repository_package_reexports(tmp_path: Path) -> None:
    source = tmp_path / "server" / "tickets" / "bad.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from app.repos import DevicesRepo, RegistryRepo, RegistrationRepo\n",
        encoding="utf-8",
    )

    result = run_check(tmp_path, registry_scope="tickets")

    assert result.returncode == 1
    assert "RegistryRepo, RegistrationRepo" in result.stdout
    assert "DevicesRepo" not in result.stdout


def test_registry_scope_rejects_broad_model_and_repository_modules(tmp_path: Path) -> None:
    source = tmp_path / "server" / "tickets" / "bad.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "import app.db.models as models\n"
        "from app import repos\n",
        encoding="utf-8",
    )

    result = run_check(tmp_path, registry_scope="tickets")

    assert result.returncode == 1
    assert "import app.db.models as models" in result.stdout
    assert "from app import repos" in result.stdout


@pytest.mark.parametrize(
    ("source_text", "expected_import"),
    [
        ("import app.db as db\n", "import app.db as db"),
        ("from app import db\n", "from app import db"),
    ],
)
def test_registry_scope_rejects_broad_database_package_imports(
    tmp_path: Path,
    source_text: str,
    expected_import: str,
) -> None:
    source = tmp_path / "server" / "tickets" / "bad.py"
    source.parent.mkdir(parents=True)
    source.write_text(source_text, encoding="utf-8")

    result = run_check(tmp_path, registry_scope="tickets")

    assert result.returncode == 1
    assert "server/tickets/bad.py:1" in result.stdout
    assert expected_import in result.stdout


def test_registry_scope_does_not_claim_unselected_paths(tmp_path: Path) -> None:
    source = tmp_path / "server" / "registry" / "local_runtime.py"
    source.parent.mkdir(parents=True)
    source.write_text("from app.db.models import RegistryPerson\n", encoding="utf-8")

    result = run_check(tmp_path, registry_scope="tickets")

    assert result.returncode == 0


def test_registry_scope_allows_only_declared_create_flow_command_debt(tmp_path: Path) -> None:
    source = tmp_path / "server" / "tickets" / "create_flow.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from registry.account_session_service import AccountSessionService\n"
        "from registry.service import RegistryIngestionService\n",
        encoding="utf-8",
    )

    allowed = run_check(tmp_path, registry_scope="tickets")
    source.write_text(
        source.read_text(encoding="utf-8")
        + "from app.repos.registry_repo import RegistryRepo\n",
        encoding="utf-8",
    )
    rejected = run_check(tmp_path, registry_scope="tickets")

    assert allowed.returncode == 0
    assert rejected.returncode == 1
    assert "app.repos.registry_repo" in rejected.stdout
