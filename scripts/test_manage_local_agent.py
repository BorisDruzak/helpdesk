from __future__ import annotations

import importlib.util
import json
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
