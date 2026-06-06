from __future__ import annotations

import pytest

from mcp_helpdesk_server.bootstrap import configure_paths


@pytest.fixture(autouse=True)
def _configure_project_paths() -> None:
    configure_paths()
