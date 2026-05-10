from pathlib import Path


def test_windows_agent_specs_collect_remote_assist_webrtc_dependencies() -> None:
    root = Path(__file__).resolve().parents[1]
    for spec_name in ("pyinstaller_agent_win.spec", "pyinstaller_agent_win_release.spec"):
        text = (root / spec_name).read_text(encoding="utf-8")

        assert "collect_submodules" in text
        assert '"aiortc"' in text
        assert '"aioice"' in text
        assert '"av"' in text
        assert '"pylibsrtp"' in text
        assert '"pc_agent.remote_assist.elevated_helper"' in text
        assert '"pc_agent.remote_assist.file_transfer"' in text
