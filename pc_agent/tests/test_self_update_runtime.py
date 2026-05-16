import json
import io
import sys
import tarfile
import zipfile
from datetime import datetime, timezone
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pc_agent.launcher import installer as installer_module
from pc_agent.launcher.installer import _safe_join, apply_update, extract_artifact
from pc_agent.ws_agent import WSAgent
from pc_agent.core.orchestrator import AgentOrchestrator
from pc_agent.core.tool_response import ToolMeta
from pc_agent.core.action_trace import ActionTraceRecorder, configure_action_trace
from pc_agent.config.config_loader import ConfigLoader, init_config


def test_safe_join_blocks_sibling_prefix_traversal(tmp_path):
    staging_dir = tmp_path / "stage"
    staging_dir.mkdir(parents=True, exist_ok=True)

    with pytest.raises(ValueError, match="Path traversal"):
        _safe_join(staging_dir, "../stage2/evil.txt")


def test_extract_artifact_restores_tar_member_mode_on_posix(monkeypatch, tmp_path):
    artifact_path = tmp_path / "build.tar.gz"
    staging_dir = tmp_path / "staging"
    payload = b"#!/bin/sh\nexit 0\n"

    with tarfile.open(artifact_path, "w:gz") as tf:
        member = tarfile.TarInfo("pc_agent")
        member.size = len(payload)
        member.mode = 0o755
        tf.addfile(member, io.BytesIO(payload))

    chmod_calls = []

    monkeypatch.setattr(installer_module.os, "name", "posix", raising=False)
    monkeypatch.setattr(installer_module.os, "chmod", lambda path, mode: chmod_calls.append((Path(path), mode)))

    extract_artifact("tar.gz", artifact_path, staging_dir)

    assert (staging_dir / "pc_agent").read_bytes() == payload
    assert [(Path(path), mode) for path, mode in chmod_calls] == [(Path(staging_dir / "pc_agent"), 0o755)]


def test_extract_artifact_allows_safe_relative_tar_symlink(monkeypatch, tmp_path):
    artifact_path = tmp_path / "build.tar.gz"
    staging_dir = tmp_path / "staging"
    payload = b"library"

    with tarfile.open(artifact_path, "w:gz") as tf:
        target = tarfile.TarInfo("_internal/libexample.so.1")
        target.size = len(payload)
        tf.addfile(target, io.BytesIO(payload))
        link = tarfile.TarInfo("_internal/libexample.so")
        link.type = tarfile.SYMTYPE
        link.linkname = "libexample.so.1"
        tf.addfile(link)

    symlink_calls = []
    monkeypatch.setattr(installer_module.os, "name", "posix", raising=False)
    monkeypatch.setattr(installer_module.os, "symlink", lambda linkname, dest: symlink_calls.append((linkname, Path(dest))))

    extract_artifact("tar.gz", artifact_path, staging_dir)

    assert (staging_dir / "_internal" / "libexample.so.1").read_bytes() == payload
    assert [(linkname, str(dest).replace("\\", "/")) for linkname, dest in symlink_calls] == [
        ("libexample.so.1", str(staging_dir / "_internal" / "libexample.so").replace("\\", "/"))
    ]


def test_extract_artifact_rejects_symlink_traversal(tmp_path):
    artifact_path = tmp_path / "build.tar.gz"
    staging_dir = tmp_path / "staging"

    with tarfile.open(artifact_path, "w:gz") as tf:
        link = tarfile.TarInfo("_internal/evil")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../outside"
        tf.addfile(link)

    with pytest.raises(ValueError, match="Unsafe symlink target"):
        extract_artifact("tar.gz", artifact_path, staging_dir)


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


def test_apply_update_prunes_old_version_directories_after_success(tmp_path, monkeypatch):
    install_root = tmp_path / "install"
    data_root = tmp_path / "data"
    updates_dir = data_root / "updates"
    downloads_dir = updates_dir / "downloads"
    versions_dir = install_root / "versions"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    versions_dir.mkdir(parents=True, exist_ok=True)
    for version in ("3.1.33", "3.1.34", "3.1.35", "3.1.36", "3.1.37"):
        version_dir = versions_dir / version
        version_dir.mkdir()
        (version_dir / "marker.txt").write_text(version, encoding="utf-8")
    (install_root / "current.json").write_text(
        json.dumps({"version": "3.1.37", "previous": "3.1.36"}),
        encoding="utf-8",
    )

    artifact_path = downloads_dir / "build.zip"
    with zipfile.ZipFile(artifact_path, "w") as zf:
        zf.writestr("pc_agent.exe", "new binary")

    pending_path = updates_dir / "pending_update.json"
    pending_path.write_text(
        json.dumps(
            {
                "version": "3.1.38",
                "archive_type": "zip",
                "artifact_path": str(artifact_path),
                "operation_id": "op-prune-versions",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(installer_module, "run_verify", lambda *_args, **_kwargs: (True, "verify ok"))

    ok, message = apply_update(install_root=install_root, data_root=data_root, pending_path=pending_path)

    assert ok is True
    assert message == "3.1.38"
    assert sorted(path.name for path in versions_dir.iterdir() if path.is_dir()) == ["3.1.37", "3.1.38"]
    assert (versions_dir / "3.1.37" / "marker.txt").read_text(encoding="utf-8") == "3.1.37"
    assert (versions_dir / "3.1.38" / "pc_agent.exe").exists()
    assert json.loads((install_root / "current.json").read_text(encoding="utf-8")) == {
        "version": "3.1.38",
        "previous": "3.1.37",
    }


def test_apply_update_publish_failure_restores_existing_version(tmp_path, monkeypatch):
    install_root = tmp_path / "install"
    data_root = tmp_path / "data"
    updates_dir = data_root / "updates"
    downloads_dir = updates_dir / "downloads"
    versions_dir = install_root / "versions"
    target_version_dir = versions_dir / "2.0.0"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    target_version_dir.mkdir(parents=True, exist_ok=True)
    versions_dir.mkdir(parents=True, exist_ok=True)
    (install_root / "current.json").write_text(json.dumps({"version": "1.0.0"}), encoding="utf-8")
    (target_version_dir / "keep.txt").write_text("keep me", encoding="utf-8")

    artifact_path = downloads_dir / "build.zip"
    with zipfile.ZipFile(artifact_path, "w") as zf:
        zf.writestr("pc_agent.exe", "new binary")

    pending_path = updates_dir / "pending_update.json"
    pending_path.write_text(
        json.dumps(
            {
                "version": "2.0.0",
                "archive_type": "zip",
                "artifact_path": str(artifact_path),
                "operation_id": "op-publish-fail",
                "requested_by": "admin",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    original_move = installer_module.shutil.move
    staging_dir = versions_dir / "_staging" / "2.0.0"

    monkeypatch.setattr(installer_module, "_find_agent_binary", lambda _version_dir: staging_dir / "pc_agent.exe")
    monkeypatch.setattr(installer_module, "run_verify", lambda *_args, **_kwargs: (True, "verify ok"))

    def _fake_move(src, dst):
        if Path(src) == staging_dir and Path(dst) == target_version_dir:
            raise OSError("disk full")
        return original_move(src, dst)

    monkeypatch.setattr(installer_module.shutil, "move", _fake_move)

    ok, message = apply_update(install_root=install_root, data_root=data_root, pending_path=pending_path)

    assert ok is False
    assert "Publish failed" in message
    assert (target_version_dir / "keep.txt").read_text(encoding="utf-8") == "keep me"
    assert json.loads((install_root / "current.json").read_text(encoding="utf-8"))["version"] == "1.0.0"
    assert pending_path.exists() is False


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


def _update_meta() -> ToolMeta:
    return ToolMeta(
        timestamp_iso=datetime.now(timezone.utc).isoformat(),
        command="update",
        request_id="req-self-update",
        module_versions={},
    )


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_update_command_accepts_agent_role_for_server_authorized_self_update(tmp_path, monkeypatch):
    ConfigLoader._instance = None
    ConfigLoader._config = None
    init_config(tmp_path)

    orchestrator = AgentOrchestrator(enabled_modules=[], data_root=tmp_path)
    await orchestrator.initialize()

    artifact_bytes = b"agent-update-zip"
    scheduled_payloads = []

    async def fake_download_file_to_path(**kwargs):
        dest_path = kwargs["dest_path"]
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(artifact_bytes)
        return ("deadbeef", len(artifact_bytes))

    async def fake_schedule_update_exit(payload):
        scheduled_payloads.append(payload)

    monkeypatch.setattr(orchestrator, "_download_file_to_path", fake_download_file_to_path)
    orchestrator.schedule_update_exit = fake_schedule_update_exit

    result = await orchestrator._handle_update(
        {
            "actor_role": "agent",
            "version": "3.1.7",
            "target": "windows_amd64",
            "channel": "stable",
            "download_url": "http://example.test/api/agent_builds/windows_amd64/stable/3.1.7/download",
            "sha256": "deadbeef",
            "size": len(artifact_bytes),
            "archive_type": "zip",
            "reason": "agent_gui_self_update",
        },
        _update_meta(),
    )

    assert result.status == "success"
    assert result.data is not None
    assert result.data.observations["message"] == "scheduled"

    pending_payload = json.loads((tmp_path / "updates" / "pending_update.json").read_text(encoding="utf-8"))
    assert pending_payload["version"] == "3.1.7"
    assert pending_payload["requested_by"] == "agent"
    assert pending_payload["requested_reason"] == "agent_gui_self_update"
    assert scheduled_payloads == [
        {
            "delay_sec": 2,
            "reason": "self_update",
            "version": "3.1.7",
            "operation_id": "req-self-update",
        }
    ]


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_update_command_rejects_when_pending_update_already_exists(tmp_path, monkeypatch):
    ConfigLoader._instance = None
    ConfigLoader._config = None
    init_config(tmp_path)

    orchestrator = AgentOrchestrator(enabled_modules=[], data_root=tmp_path)
    await orchestrator.initialize()

    updates_dir = tmp_path / "updates"
    updates_dir.mkdir(parents=True, exist_ok=True)
    pending_path = updates_dir / "pending_update.json"
    pending_path.write_text(
        json.dumps(
            {
                "version": "3.1.18",
                "operation_id": "existing-op",
                "received_at": "2026-04-22T10:00:00+00:00",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    download_called = {"value": False}

    async def fake_download_file_to_path(**kwargs):
        download_called["value"] = True
        raise AssertionError("download should not run when pending update already exists")

    monkeypatch.setattr(orchestrator, "_download_file_to_path", fake_download_file_to_path)

    result = await orchestrator._handle_update(
        {
            "actor_role": "agent",
            "version": "3.1.19",
            "target": "windows_amd64",
            "channel": "stable",
            "download_url": "http://example.test/build.zip",
            "sha256": "deadbeef",
            "size": 10,
            "archive_type": "zip",
        },
        _update_meta(),
    )

    assert result.status == "error"
    assert result.error is not None
    assert result.error.code == "UPDATE_FAILED"
    assert "already pending" in result.error.message
    assert download_called["value"] is False
    assert json.loads(pending_path.read_text(encoding="utf-8"))["operation_id"] == "existing-op"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_update_command_fails_when_shutdown_cannot_be_scheduled(tmp_path, monkeypatch):
    ConfigLoader._instance = None
    ConfigLoader._config = None
    init_config(tmp_path)

    orchestrator = AgentOrchestrator(enabled_modules=[], data_root=tmp_path)
    await orchestrator.initialize()

    artifact_bytes = b"agent-update-zip"

    async def fake_download_file_to_path(**kwargs):
        dest_path = kwargs["dest_path"]
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(artifact_bytes)
        return ("deadbeef", len(artifact_bytes))

    async def fake_schedule_update_exit(_payload):
        raise RuntimeError("scheduler offline")

    monkeypatch.setattr(orchestrator, "_download_file_to_path", fake_download_file_to_path)
    orchestrator.schedule_update_exit = fake_schedule_update_exit

    result = await orchestrator._handle_update(
        {
            "actor_role": "agent",
            "version": "3.1.20",
            "target": "windows_amd64",
            "channel": "stable",
            "download_url": "http://example.test/build.zip",
            "sha256": "deadbeef",
            "size": len(artifact_bytes),
            "archive_type": "zip",
        },
        _update_meta(),
    )

    assert result.status == "error"
    assert result.error is not None
    assert result.error.code == "UPDATE_FAILED"
    assert "shutdown" in result.error.message.lower()
    assert (tmp_path / "updates" / "pending_update.json").exists() is False
    assert list((tmp_path / "updates" / "downloads").glob("*")) == []


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_update_command_records_action_trace_stages(tmp_path, monkeypatch):
    ConfigLoader._instance = None
    ConfigLoader._config = None
    init_config(tmp_path)
    configure_action_trace(tmp_path)

    orchestrator = AgentOrchestrator(enabled_modules=[], data_root=tmp_path)
    await orchestrator.initialize()

    artifact_bytes = b"agent-update-zip"

    async def fake_download_file_to_path(**kwargs):
        dest_path = kwargs["dest_path"]
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(artifact_bytes)
        return ("deadbeef", len(artifact_bytes))

    async def fake_schedule_update_exit(_payload):
        return {"status": "ok", "scheduled": True}

    monkeypatch.setattr(orchestrator, "_download_file_to_path", fake_download_file_to_path)
    orchestrator.schedule_update_exit = fake_schedule_update_exit

    result = await orchestrator._handle_update(
        {
            "actor_role": "agent",
            "version": "3.1.18",
            "target": "windows_amd64",
            "channel": "stable",
            "download_url": "http://example.test/api/agent_builds/windows_amd64/stable/3.1.18/download",
            "sha256": "deadbeef",
            "size": len(artifact_bytes),
            "archive_type": "zip",
            "reason": "agent_gui_self_update",
        },
        _update_meta(),
    )

    assert result.status == "success"
    recorder = ActionTraceRecorder(tmp_path)
    rows = recorder.search(limit=20, operation_id="req-self-update", tool_name="update", source="orchestrator")
    stages = {(row["stage"], row["status"]) for row in rows if row["action"] == "agent.update.command"}
    assert ("request", "started") in stages
    assert ("downloaded", "ok") in stages
    assert ("pending_written", "ok") in stages
    assert ("shutdown_scheduled", "ok") in stages
    assert ("response", "ok") in stages


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_update_command_still_blocks_unprivileged_actor_role(tmp_path):
    ConfigLoader._instance = None
    ConfigLoader._config = None
    init_config(tmp_path)

    orchestrator = AgentOrchestrator(enabled_modules=[], data_root=tmp_path)
    await orchestrator.initialize()

    result = await orchestrator._handle_update(
        {
            "actor_role": "user",
            "version": "3.1.7",
            "target": "windows_amd64",
            "channel": "stable",
            "download_url": "http://example.test/build.zip",
            "sha256": "deadbeef",
            "size": 10,
            "archive_type": "zip",
        },
        _update_meta(),
    )

    assert result.status == "error"
    assert result.error is not None
    assert result.error.code == "FORBIDDEN"


@pytest.mark.asyncio
async def test_runtime_status_includes_recommended_update_fields(tmp_path, monkeypatch):
    updates_dir = tmp_path / "data" / "updates"
    updates_dir.mkdir(parents=True, exist_ok=True)
    (updates_dir / "pending_update.json").write_text(
        json.dumps(
            {
                "version": "3.1.4",
                "operation_id": "op-pending",
                "received_at": "2026-04-16T09:00:00+00:00",
                "requested_reason": "assigned rollout rollback",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (updates_dir / "update_history.json").write_text(
        json.dumps(
            [
                {
                    "version": "3.1.3",
                    "success": True,
                    "at": "2026-04-16T08:30:00+00:00",
                    "operation_id": "op-success",
                },
                {
                    "version": "3.1.2",
                    "success": False,
                    "at": "2026-04-16T08:00:00+00:00",
                    "operation_id": "op-failed",
                    "reason": "verify_failed",
                    "message": "signature mismatch",
                },
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    agent = WSAgent(data_root=tmp_path / "data", install_root=tmp_path / "install")
    agent.device_id = "device-1"

    async def fake_fetch_update_status(*, force: bool = False):
        return {
            "agent_version": "3.1.5",
            "is_release": True,
            "release_channel": "stable",
            "update_available": True,
            "recommended_version": "3.1.4",
            "recommended_channel": "stable",
            "recommended_reason": "assigned_rollout_older",
            "comparison": "recommended_release_is_older",
            "recommendation_source": "assigned_rollout",
            "assigned_rollout": {
                "target": "windows_amd64",
                "channel": "stable",
                "version": "3.1.4",
            },
            "recommended_build": {
                "target": "windows_amd64",
                "channel": "stable",
                "version": "3.1.4",
                "is_release": True,
            },
            "update_checked_at": "2026-04-14T10:00:00+00:00",
        }

    monkeypatch.setattr(agent, "_fetch_update_status", fake_fetch_update_status)

    status = await agent.get_runtime_status_async()

    assert status["device_id"] == "device-1"
    assert status["is_release"] is True
    assert status["release_channel"] == "stable"
    assert status["update_available"] is False
    assert status["recommended_version"] == "3.1.4"
    assert status["recommended_channel"] == "stable"
    assert status["recommended_reason"] == "assigned_rollout_older"
    assert status["comparison"] == "recommended_release_is_older"
    assert status["recommendation_source"] == "assigned_rollout"
    assert status["assigned_rollout"]["version"] == "3.1.4"
    assert status["pending_update_version"] == "3.1.4"
    assert status["pending_update_operation_id"] == "op-pending"
    assert status["update_request_state"] == "pending_restart"
    assert status["update_request_version"] == "3.1.4"
    assert status["update_request_operation_id"] == "op-pending"
    assert status["last_applied_update_version"] == "3.1.3"
    assert status["last_failed_update_version"] == "3.1.2"
    assert status["last_failed_update_reason"] == "verify_failed"


@pytest.mark.asyncio
async def test_runtime_status_async_preserves_cached_requested_update_state(tmp_path, monkeypatch):
    agent = WSAgent(data_root=tmp_path / "data", install_root=tmp_path / "install")
    agent.device_id = "device-1"
    agent.auth_token = "agent-token-1"
    agent._cached_update_checked_at = "2026-04-22T17:43:54+00:00"
    agent._cached_update_status = {
        "update_available": False,
        "recommended_version": "3.1.21",
        "recommended_channel": "stable",
        "recommended_reason": "update_requested",
        "recommended_build": {
            "target": "windows_amd64",
            "channel": "stable",
            "version": "3.1.21",
        },
        "comparison": "upgrade_available",
        "recommendation_source": "assigned_rollout",
        "assigned_rollout": {"channel": "stable", "version": "3.1.21"},
        "update_request_state": "requested",
        "update_request_version": "3.1.21",
        "update_request_operation_id": "op-local-320",
        "update_request_requested_at": "2026-04-22T17:43:54+00:00",
        "update_request_reason": "agent_gui_self_update",
    }

    async def fake_fetch_update_status(*, force: bool = False):
        return {
            "agent_version": "3.1.20",
            "is_release": True,
            "release_channel": "stable",
            "update_available": True,
            "recommended_version": "3.1.21",
            "recommended_channel": "stable",
            "recommended_reason": "assigned_rollout",
            "comparison": "upgrade_available",
            "recommendation_source": "assigned_rollout",
            "assigned_rollout": {"channel": "stable", "version": "3.1.21"},
            "recommended_build": {
                "target": "windows_amd64",
                "channel": "stable",
                "version": "3.1.21",
            },
            "update_checked_at": "2026-04-22T17:43:55+00:00",
            "update_request_state": None,
            "update_request_version": None,
            "update_request_operation_id": None,
            "update_request_requested_at": None,
            "update_request_reason": None,
        }

    monkeypatch.setattr(agent, "_fetch_update_status", fake_fetch_update_status)

    status = await agent.get_runtime_status_async()

    assert status["update_available"] is False
    assert status["recommended_version"] == "3.1.21"
    assert status["recommended_reason"] == "update_requested"
    assert status["update_request_state"] == "requested"
    assert status["update_request_version"] == "3.1.21"
    assert status["update_request_operation_id"] == "op-local-320"
    assert status["update_request_reason"] == "agent_gui_self_update"


def test_apply_update_failure_records_launcher_action_trace(tmp_path):
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
                "operation_id": "op-launcher-update",
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

    recorder = ActionTraceRecorder(data_root)
    rows = recorder.search(limit=20, operation_id="op-launcher-update", source="launcher")
    assert any(row["action"] == "agent.update.apply" and row["stage"] == "start" for row in rows)
    assert any(
        row["action"] == "agent.update.apply"
        and row["stage"] == "finish"
        and row["status"] == "error"
        and "binary_not_found" in str(row.get("details") or {})
        for row in rows
    )


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


@pytest.mark.asyncio
async def test_fetch_update_status_reuses_recent_cache_for_idle_gui_polling(tmp_path, monkeypatch):
    agent = WSAgent(data_root=tmp_path / "data", install_root=tmp_path / "install")
    agent.device_id = "device-1"
    agent.auth_token = "agent-token-1"
    checked_at = (datetime.now(timezone.utc) - timedelta(minutes=4)).isoformat()
    agent._cached_update_checked_at = checked_at
    agent._cached_update_status = {
        "status": "ok",
        "update_available": False,
        "recommended_version": "3.1.36",
        "update_checked_at": checked_at,
    }

    class FailingSession:
        closed = False

        def get(self, url, headers=None):
            raise AssertionError("idle GUI status polling should not hit update recommendation every few seconds")

    monkeypatch.setattr(
        "pc_agent.ws_agent.get_config",
        lambda: SimpleNamespace(server=SimpleNamespace(api_url="http://example.test/api")),
    )
    agent._http_session = FailingSession()

    status = await agent._fetch_update_status()

    assert status["recommended_version"] == "3.1.36"
    assert status["update_available"] is False
    assert status["update_status_error"] is None
