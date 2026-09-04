from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.no_db


ROOT = Path(__file__).resolve().parents[2]


def test_remote_assist_runtime_sources_and_routes_are_absent() -> None:
    source = ROOT / "server" / "remote_assist"
    routes = (ROOT / "server" / "routes.py").read_text(encoding="utf-8")

    assert list(source.glob("*.py")) == []
    assert "remote-assist" not in routes
