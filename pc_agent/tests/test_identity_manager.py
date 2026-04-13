import json
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pc_agent.core.identity import IdentityManager


def test_identity_manager_creates_machine_id_and_install_id(tmp_path, monkeypatch):
    machine_id = str(uuid.uuid4())
    monkeypatch.setenv("PC_AGENT_MACHINE_ID", machine_id)
    identity_file = tmp_path / "identity.json"

    manager = IdentityManager(str(identity_file))
    payload = manager.load_or_create()

    assert manager.device_id == machine_id
    assert manager.uuid == machine_id
    assert manager.machine_id == machine_id
    assert IdentityManager.is_valid_uuid(manager.install_id)
    assert manager.install_id != machine_id
    assert payload["uuid"] == machine_id
    assert payload["machine_id"] == machine_id
    assert payload["install_id"] == manager.install_id


def test_identity_manager_migrates_legacy_uuid_into_install_id(tmp_path, monkeypatch):
    machine_id = str(uuid.uuid4())
    legacy_uuid = str(uuid.uuid4())
    monkeypatch.setenv("PC_AGENT_MACHINE_ID", machine_id)
    identity_file = tmp_path / "identity.json"
    identity_file.write_text(json.dumps({"uuid": legacy_uuid, "token": None}), encoding="utf-8")

    manager = IdentityManager(str(identity_file))
    payload = manager.load_or_create()

    assert manager.device_id == machine_id
    assert manager.install_id == legacy_uuid
    assert payload["uuid"] == machine_id
    assert payload["install_id"] == legacy_uuid


def test_identity_manager_recreates_install_id_but_keeps_machine_id_after_identity_delete(tmp_path, monkeypatch):
    machine_id = str(uuid.uuid4())
    monkeypatch.setenv("PC_AGENT_MACHINE_ID", machine_id)
    identity_file = tmp_path / "identity.json"

    first = IdentityManager(str(identity_file))
    first.load_or_create()
    first_install_id = first.install_id
    identity_file.unlink()

    second = IdentityManager(str(identity_file))
    second.load_or_create()

    assert second.device_id == machine_id
    assert second.install_id != first_install_id
