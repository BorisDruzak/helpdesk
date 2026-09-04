from pathlib import Path

import pytest


pytestmark = pytest.mark.no_db


def test_server_requirements_include_database_engine_runtime_logger() -> None:
    requirements = {
        line.strip()
        for line in (Path(__file__).parents[1] / "requirements.txt").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip() and not line.startswith("#")
    }

    assert "loguru" in requirements


def test_ci_requirements_include_cross_repository_acceptance_websocket_client() -> None:
    requirements = {
        line.strip().split("=", 1)[0].split("<", 1)[0].split(">", 1)[0]
        for line in (Path(__file__).parents[2] / "requirements-ci.txt").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip() and not line.startswith("#") and not line.startswith("-")
    }

    assert "websockets" in requirements
    assert "uvicorn" in requirements


def test_ci_requirements_reference_the_helpdesk_server_entrypoint() -> None:
    root = Path(__file__).parents[2]
    requirements_path = root / "requirements-ci.txt"
    requirements = requirements_path.read_text(encoding="utf-8")

    assert "-r server/requirements.txt" in requirements
    assert "-r pc_agent/requirements.txt" not in requirements
    assert (root / "server" / "requirements.txt").is_file()
