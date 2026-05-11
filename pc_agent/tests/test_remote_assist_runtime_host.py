import json
from pathlib import Path


def test_runtime_host_falls_back_to_bundled_thread(tmp_path, monkeypatch):
    from pc_agent.remote_assist import runtime_host

    created = {}

    class FakeBundledThread:
        def __init__(self, **kwargs):
            created.update(kwargs)

    monkeypatch.setattr(runtime_host, "BundledRemoteAssistThread", FakeBundledThread)

    thread = runtime_host.create_remote_assist_thread(
        signaling_url="ws://server/ws/remote-assist/session",
        token="agent-token",
        ice_servers=[],
        mode="interactive_control",
        media={"fps": 15},
        features={"clipboard_auto_sync": True},
        parent="main-window",
        data_dir=tmp_path,
    )

    assert isinstance(thread, FakeBundledThread)
    assert created["signaling_url"] == "ws://server/ws/remote-assist/session"
    assert created["token"] == "agent-token"
    assert created["mode"] == "interactive_control"
    assert created["media"] == {"fps": 15}
    assert created["features"] == {"clipboard_auto_sync": True}
    assert created["parent"] == "main-window"


def test_runtime_host_loads_active_managed_runtime_module(tmp_path):
    from pc_agent.remote_assist import runtime_host

    module_dir = tmp_path / "modules_store" / "remote_assist_runtime"
    version_dir = module_dir / "1.0.0"
    version_dir.mkdir(parents=True)
    (module_dir / "current.json").write_text(json.dumps({"version": "1.0.0"}), encoding="utf-8")
    (version_dir / "manifest.json").write_text(
        json.dumps({"module_name": "remote_assist_runtime", "module_version": "1.0.0"}),
        encoding="utf-8",
    )
    (version_dir / "module.py").write_text(
        """
class ManagedThread:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

def create_remote_assist_thread(**kwargs):
    return ManagedThread(**kwargs)
""".strip(),
        encoding="utf-8",
    )

    thread = runtime_host.create_remote_assist_thread(
        signaling_url="wss://server/ws/remote-assist/session",
        token="agent-token",
        ice_servers=[{"urls": ["turn:example"]}],
        mode="elevated_admin",
        media={"max_width": 1280},
        features={"file_transfer": True},
        parent=None,
        data_dir=tmp_path,
    )

    assert thread.__class__.__name__ == "ManagedThread"
    assert thread.kwargs["signaling_url"] == "wss://server/ws/remote-assist/session"
    assert thread.kwargs["token"] == "agent-token"
    assert thread.kwargs["ice_servers"] == [{"urls": ["turn:example"]}]
    assert thread.kwargs["mode"] == "elevated_admin"
    assert thread.kwargs["media"] == {"max_width": 1280}
    assert thread.kwargs["features"] == {"file_transfer": True}
