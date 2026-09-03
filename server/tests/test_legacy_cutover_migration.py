from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.no_db


def test_endpoint_agent_authority_marker_is_forward_only() -> None:
    migration = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "db"
        / "migrations"
        / "versions"
        / "20260903_143_endpoint_agent_authority_marker.py"
    ).read_text(encoding="utf-8")

    assert 'revision = "143"' in migration
    assert 'down_revision = "142"' in migration
    assert "endpoint_agent_control_plane_authority" in migration
    assert "endpoint_platform" in migration
    assert "forward-only" in migration
