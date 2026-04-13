import json
import sys
import zipfile
from pathlib import Path

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
