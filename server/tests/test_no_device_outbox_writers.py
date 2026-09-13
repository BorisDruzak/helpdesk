from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.no_db


ROOT = Path(__file__).resolve().parents[2]
ENDPOINT_TRANSITION_SOURCES = (
    ROOT / "server" / "web_api" / "endpoint_operation_handlers.py",
    ROOT / "server" / "diagnostics" / "providers" / "endpoint_platform.py",
    ROOT / "server" / "app" / "services" / "endpoint_diagnostic_operation_service.py",
)


def test_endpoint_transition_paths_do_not_write_legacy_device_outbox() -> None:
    offenders = {
        path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8-sig")
        for path in ENDPOINT_TRANSITION_SOURCES
        if "DeviceOutbox" in path.read_text(encoding="utf-8-sig")
        or "device_outbox" in path.read_text(encoding="utf-8-sig")
    }

    assert offenders == {}


def test_legacy_device_outbox_writer_repository_is_physically_removed() -> None:
    assert not (ROOT / "server" / "app" / "repos" / "device_outbox_repo.py").exists()
