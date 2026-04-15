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
