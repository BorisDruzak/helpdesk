import json
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pc_agent.launcher.installer import apply_update
from pc_agent.ws_agent import WSAgent


def test_apply_update_failure_removes_pending_and_writes_history(tmp_path):
    install_root = tmp_path / "install"
    data_root = tmp_path / "data"
    updates_dir = data_root / "updates"
    downloads_dir = updates_dir / "downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    (install_root / "versions").mkdir(parents=True, exist_ok=True)
    (install_root / "current.json").write_text(json.dumps({"version": "1.0.0"}), encoding="utf-8")

    artifact_path = downloads_dir / "build.zip"
    with zipfile.ZipFile(artifact_path, "w") as zf:
        zf.writestr("README.txt", "no agent binary here")

    pending_path = updates_dir / "pending_update.json"
    pending_path.write_text(
        json.dumps(
            {
                "version": "2.0.0",
                "archive_type": "zip",
                "artifact_path": str(artifact_path),
                "operation_id": "op-1",
                "requested_by": "admin",
                "requested_reason": "test rollout",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    ok, message = apply_update(install_root=install_root, data_root=data_root, pending_path=pending_path)

    assert ok is False
    assert "Agent binary not found" in message
    assert pending_path.exists() is False

    history = json.loads((updates_dir / "update_history.json").read_text(encoding="utf-8"))
    assert history[-1]["success"] is False
    assert history[-1]["reason"] == "binary_not_found"
    assert history[-1]["requested_reason"] == "test rollout"

    failed_pending = json.loads((updates_dir / "last_failed_pending_update.json").read_text(encoding="utf-8"))
    assert failed_pending["pending_payload"]["version"] == "2.0.0"


def test_latest_update_handshake_payload_prefers_latest_failure(tmp_path):
    data_root = tmp_path / "data"
    updates_dir = data_root / "updates"
    updates_dir.mkdir(parents=True, exist_ok=True)
    (updates_dir / "update_history.json").write_text(
        json.dumps(
            [
                {
                    "version": "2.0.0",
                    "success": True,
                    "at": "2026-04-13T09:00:00+00:00",
                    "operation_id": "op-success",
                },
                {
                    "version": "2.1.0",
                    "success": False,
                    "at": "2026-04-13T10:00:00+00:00",
                    "operation_id": "op-failed",
                    "reason": "VERIFY_FAILED",
                    "message": "verify failed",
                },
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    agent = WSAgent(data_root=data_root, install_root=tmp_path / "install")
    payload = agent._get_latest_update_handshake_payload()

    assert payload == {
        "failed_update_version": "2.1.0",
        "failed_update_operation_id": "op-failed",
        "failed_update_reason": "VERIFY_FAILED",
        "failed_update_at": "2026-04-13T10:00:00+00:00",
        "failed_update_message": "verify failed",
    }


def test_latest_update_handshake_payload_returns_success_when_latest_entry_succeeded(tmp_path):
    data_root = tmp_path / "data"
    updates_dir = data_root / "updates"
    updates_dir.mkdir(parents=True, exist_ok=True)
    (updates_dir / "update_history.json").write_text(
        json.dumps(
            [
                {
                    "version": "2.1.0",
                    "success": True,
                    "at": "2026-04-13T11:00:00+00:00",
                    "operation_id": "op-success",
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    agent = WSAgent(data_root=data_root, install_root=tmp_path / "install")
    payload = agent._get_latest_update_handshake_payload()

    assert payload == {
        "applied_update_version": "2.1.0",
        "last_update_operation_id": "op-success",
    }


@pytest.mark.asyncio
async def test_runtime_status_includes_recommended_update_fields(tmp_path, monkeypatch):
    agent = WSAgent(data_root=tmp_path / "data", install_root=tmp_path / "install")
    agent.device_id = "device-1"

    async def fake_fetch_update_status(*, force: bool = False):
        return {
            "agent_version": "3.1.3-beta.1",
            "is_release": False,
            "release_channel": "beta",
            "update_available": True,
            "recommended_version": "3.1.3",
            "recommended_channel": "stable",
            "recommended_reason": "non_release_current_version",
            "recommended_build": {
                "target": "windows_amd64",
                "channel": "stable",
                "version": "3.1.3",
                "is_release": True,
            },
            "update_checked_at": "2026-04-14T10:00:00+00:00",
        }

    monkeypatch.setattr(agent, "_fetch_update_status", fake_fetch_update_status)

    status = await agent.get_runtime_status_async()

    assert status["device_id"] == "device-1"
    assert status["is_release"] is False
    assert status["release_channel"] == "beta"
    assert status["update_available"] is True
    assert status["recommended_version"] == "3.1.3"
    assert status["recommended_channel"] == "stable"
    assert status["recommended_reason"] == "non_release_current_version"


@pytest.mark.asyncio
async def test_fetch_update_status_reports_plain_text_404_cleanly(tmp_path, monkeypatch):
    agent = WSAgent(data_root=tmp_path / "data", install_root=tmp_path / "install")
    agent.device_id = "device-1"
    agent.auth_token = "agent-token-1"

    class FakeResponse:
        status = 404

        async def text(self):
            return "404: Not Found"

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeSession:
        closed = False

        def get(self, url, headers=None):
            return FakeResponse()

    monkeypatch.setattr(
        "pc_agent.ws_agent.get_config",
        lambda: SimpleNamespace(server=SimpleNamespace(api_url="http://example.test/api")),
    )
    agent._http_session = FakeSession()

    status = await agent._fetch_update_status(force=True)

    assert status["update_available"] is False
    assert status["recommended_version"] is None
    assert status["update_status_error"] == "Update recommendation endpoint is unavailable on server (HTTP 404)"
