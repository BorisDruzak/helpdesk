from __future__ import annotations

import asyncio
import importlib.util
import json
import sqlite3
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parent / "manage_local_agent.py"
SPEC = importlib.util.spec_from_file_location("manage_local_agent_for_test", MODULE_PATH)
manage_local_agent = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(manage_local_agent)


def _fake_build_root(tmp_path: Path) -> Path:
    build_root = tmp_path / "build-root"
    (build_root / "pc_agent").mkdir(parents=True)
    (build_root / "launcher.exe").write_bytes(b"launcher")
    (build_root / "pc_agent" / "pc_agent.exe").write_bytes(b"agent")
    return build_root


def _write_identity(data_dir: Path, *, machine_id: str, install_id: str) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "identity.json").write_text(
        json.dumps(
            {
                "version": 2,
                "uuid": machine_id,
                "machine_id": machine_id,
                "install_id": install_id,
                "machine_id_source": "windows_machine_guid",
                "token": None,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _active_tokens(db_path: Path) -> list[tuple[str, str]]:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT device_id, token FROM auth_tokens WHERE is_active = 1 ORDER BY created_at DESC"
        )
        return cur.fetchall()
    finally:
        conn.close()


def test_seed_release_install_keeps_existing_versioned_layout(tmp_path, monkeypatch):
    monkeypatch.setattr(manage_local_agent, "INSTANCE_ROOT", tmp_path / "instances")
    monkeypatch.setattr(manage_local_agent, "_read_agent_version", lambda: "3.0.3")
    build_root = _fake_build_root(tmp_path)

    install_root = tmp_path / "instances" / "legacy-canary" / "install"
    (install_root / "versions" / "3.0.2").mkdir(parents=True, exist_ok=True)
    (install_root / "launcher.exe").write_bytes(b"legacy-launcher")
    (install_root / "current.json").write_text(
        json.dumps({"version": "3.0.2", "previous": "3.0.1"}),
        encoding="utf-8",
    )

    seeded = manage_local_agent._seed_release_install("legacy-canary", build_root)

    assert seeded == "3.0.2"
    assert not (install_root / "versions" / "3.0.3").exists()
    payload = json.loads((install_root / "current.json").read_text(encoding="utf-8"))
    assert payload["version"] == "3.0.2"


def test_seed_release_install_keeps_existing_layout_without_repo_build(tmp_path, monkeypatch):
    monkeypatch.setattr(manage_local_agent, "INSTANCE_ROOT", tmp_path / "instances")
    monkeypatch.setattr(manage_local_agent, "_read_agent_version", lambda: "3.0.3")
    build_root = tmp_path / "missing-build-root"

    install_root = tmp_path / "instances" / "existing-canary" / "install"
    (install_root / "versions" / "3.0.2").mkdir(parents=True, exist_ok=True)
    (install_root / "launcher.exe").write_bytes(b"legacy-launcher")
    (install_root / "current.json").write_text(
        json.dumps({"version": "3.0.2", "previous": "3.0.1"}),
        encoding="utf-8",
    )

    seeded = manage_local_agent._seed_release_install("existing-canary", build_root)

    assert seeded == "3.0.2"
    assert not build_root.exists()


def test_seed_release_install_reseeds_if_current_layout_is_broken(tmp_path, monkeypatch):
    monkeypatch.setattr(manage_local_agent, "INSTANCE_ROOT", tmp_path / "instances")
    monkeypatch.setattr(manage_local_agent, "_read_agent_version", lambda: "3.0.3")
    build_root = _fake_build_root(tmp_path)

    install_root = tmp_path / "instances" / "broken-canary" / "install"
    install_root.mkdir(parents=True, exist_ok=True)
    (install_root / "launcher.exe").write_bytes(b"legacy-launcher")
    (install_root / "current.json").write_text(
        json.dumps({"version": "3.0.2", "previous": "3.0.1"}),
        encoding="utf-8",
    )

    seeded = manage_local_agent._seed_release_install("broken-canary", build_root)

    assert seeded == "3.0.3"
    payload = json.loads((install_root / "current.json").read_text(encoding="utf-8"))
    assert payload["version"] == "3.0.3"
    assert (install_root / "versions" / "3.0.3" / "pc_agent.exe").exists()


def test_sync_instance_token_from_primary_install_imports_token_for_same_machine(tmp_path, monkeypatch):
    machine_id = "7a3429ec-1c0b-5495-9aad-b284f08ae965"
    primary_data = tmp_path / "primary-data"
    instance_data = tmp_path / "instances" / "gui-agent" / "data"

    _write_identity(primary_data, machine_id=machine_id, install_id="1dad7556-bd05-4c5f-ac3a-cbdd176244e6")
    _write_identity(instance_data, machine_id=machine_id, install_id="ea184549-1277-475e-bf83-a1db92f303e1")

    from pc_agent.core.database import DatabaseManager

    DatabaseManager._instance = None
    source_db = DatabaseManager(str(primary_data / "storage.db"))
    asyncio.run(source_db.init_db())
    asyncio.run(source_db.save_auth_token("primary-token-value", machine_id))

    monkeypatch.setattr(manage_local_agent, "_default_primary_agent_data_dir", lambda: primary_data)

    copied = manage_local_agent._sync_instance_token_from_primary_install("gui-agent", instance_data)

    assert copied is True
    tokens = _active_tokens(instance_data / "storage.db")
    assert tokens == [(machine_id, "primary-token-value")]


def test_sync_instance_token_from_primary_install_skips_machine_id_mismatch(tmp_path, monkeypatch):
    primary_data = tmp_path / "primary-data"
    instance_data = tmp_path / "instances" / "gui-agent" / "data"

    _write_identity(
        primary_data,
        machine_id="7a3429ec-1c0b-5495-9aad-b284f08ae965",
        install_id="1dad7556-bd05-4c5f-ac3a-cbdd176244e6",
    )
    _write_identity(
        instance_data,
        machine_id="11111111-2222-4333-8444-555555555555",
        install_id="ea184549-1277-475e-bf83-a1db92f303e1",
    )

    from pc_agent.core.database import DatabaseManager

    DatabaseManager._instance = None
    source_db = DatabaseManager(str(primary_data / "storage.db"))
    asyncio.run(source_db.init_db())
    asyncio.run(source_db.save_auth_token("primary-token-value", "7a3429ec-1c0b-5495-9aad-b284f08ae965"))

    monkeypatch.setattr(manage_local_agent, "_default_primary_agent_data_dir", lambda: primary_data)
    import pc_agent.core.identity as identity_module

    resolved_values = iter(
        [
            ("11111111-2222-4333-8444-555555555555", "test-target"),
            ("7a3429ec-1c0b-5495-9aad-b284f08ae965", "test-source"),
        ]
    )
    monkeypatch.setattr(identity_module, "resolve_machine_identity", lambda: next(resolved_values))

    copied = manage_local_agent._sync_instance_token_from_primary_install("gui-agent", instance_data)

    assert copied is False
    if (instance_data / "storage.db").exists():
        assert _active_tokens(instance_data / "storage.db") == []


def test_normalize_machine_id_accepts_uuid_and_seed():
    original = "7A3429EC-1C0B-5495-9AAD-B284F08AE965"
    assert manage_local_agent._normalize_machine_id(original) == "7a3429ec-1c0b-5495-9aad-b284f08ae965"

    seeded_first = manage_local_agent._normalize_machine_id("qa-launcher-device")
    seeded_second = manage_local_agent._normalize_machine_id("qa-launcher-device")
    other_seed = manage_local_agent._normalize_machine_id("qa-source-device")

    assert seeded_first == seeded_second
    assert seeded_first != other_seed


def test_resolve_start_machine_id_prefers_explicit_override() -> None:
    current = {"machine_id": "16a3bdb1-78fe-5459-aca4-a911c5ae76cb"}

    resolved = manage_local_agent._resolve_start_machine_id(
        "codex-live",
        "explicit-live-agent",
        current,
    )

    assert resolved == manage_local_agent._normalize_machine_id("explicit-live-agent")


def test_resolve_start_machine_id_reuses_saved_instance_identity() -> None:
    current = {"machine_id": "16a3bdb1-78fe-5459-aca4-a911c5ae76cb"}

    resolved = manage_local_agent._resolve_start_machine_id("codex-live", None, current)

    assert resolved == "16a3bdb1-78fe-5459-aca4-a911c5ae76cb"


def test_resolve_start_machine_id_without_existing_identity_returns_none() -> None:
    assert manage_local_agent._resolve_start_machine_id("codex-live", None, None) is None


def test_build_env_includes_machine_id_and_auth_token():
    env = manage_local_agent._build_env(
        "ws://example/ws",
        "http://example/api",
        "secret-token",
        8878,
        "7a3429ec-1c0b-5495-9aad-b284f08ae965",
        Path("C:/tmp/agent-data"),
        Path("C:/tmp/agent-install"),
    )

    assert env["PC_AGENT_WS_URL"] == "ws://example/ws"
    assert env["PC_AGENT_API_URL"] == "http://example/api"
    assert env["AUTH_TOKEN"] == "secret-token"
    assert env["PC_AGENT_UI_PORT"] == "8878"
    assert env["PC_AGENT_MACHINE_ID"] == "7a3429ec-1c0b-5495-9aad-b284f08ae965"
    assert env["PC_AGENT_DATA_DIR"].endswith("agent-data")
    assert env["PC_AGENT_INSTALL_ROOT"].endswith("agent-install")


def test_issue_agent_token_returns_token_without_logging_raw_value(monkeypatch):
    captured = {}

    def _fake_request(method, url, payload=None):
        captured["method"] = method
        captured["url"] = url
        captured["payload"] = payload
        return 200, {"status": "success", "token": "very-secret-token"}

    monkeypatch.setattr(manage_local_agent, "_request_json", _fake_request)

    token = manage_local_agent._issue_agent_token(
        "http://example/api",
        "7a3429ec-1c0b-5495-9aad-b284f08ae965",
    )

    assert token == "very-secret-token"
    assert captured == {
        "method": "POST",
        "url": "http://example/api/login",
        "payload": {"uuid": "7a3429ec-1c0b-5495-9aad-b284f08ae965"},
    }


def test_issue_agent_token_normalizes_root_api_url(monkeypatch):
    captured = {}

    def _fake_request(method, url, payload=None):
        captured["method"] = method
        captured["url"] = url
        captured["payload"] = payload
        return 200, {"status": "ok", "token": "issued-from-root"}

    monkeypatch.setattr(manage_local_agent, "_request_json", _fake_request)

    token = manage_local_agent._issue_agent_token(
        "http://example",
        "7a3429ec-1c0b-5495-9aad-b284f08ae965",
    )

    assert token == "issued-from-root"
    assert captured["url"] == "http://example/api/login"


def test_status_treats_reused_pid_as_stopped(tmp_path, monkeypatch, capsys):
    instance_root = tmp_path / "instances"
    instance_dir = instance_root / "launcher-automation-3111"
    instance_dir.mkdir(parents=True, exist_ok=True)
    (instance_dir / "instance.json").write_text(
        json.dumps(
            {
                "name": "launcher-automation-3111",
                "pid": 19092,
                "gui": True,
                "start_mode": "launcher",
                "ws_url": "wss://192.168.100.17:9443/ws",
                "data_dir": str(instance_dir / "data"),
                "install_root": str(instance_dir / "install"),
                "launcher_log": str(instance_dir / "launcher.log"),
                "stopped_at": "2026-04-16T16:36:25.271694+00:00",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(manage_local_agent, "INSTANCE_ROOT", instance_root)
    monkeypatch.setattr(
        manage_local_agent,
        "_get_process_snapshot",
        lambda pid: {
            "pid": pid,
            "name": "explorer.exe",
            "command_line": "C:\\Windows\\Explorer.EXE",
            "executable_path": "C:\\Windows\\explorer.exe",
        },
    )

    exit_code = manage_local_agent._status("launcher-automation-3111")

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "launcher-automation-3111: stopped" in out
