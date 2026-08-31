from pathlib import Path


def test_control_plane_reads_bind_address_from_environment() -> None:
    source = (Path(__file__).resolve().parents[1] / "control_plane.py").read_text(encoding="utf-8")

    assert 'CONTROL_HOST = (os.getenv("CONTROL_HOST", "0.0.0.0")' in source
    assert 'CONTROL_PORT = int(os.getenv("CONTROL_PORT", "8667")' in source


def test_control_plane_supports_fail_closed_lifecycle_mode() -> None:
    source = (Path(__file__).resolve().parents[1] / "control_plane.py").read_text(encoding="utf-8")

    assert "HELPDESK_CONTROL_LIFECYCLE_ENABLED" in source
    assert "CONTROL_LIFECYCLE_UNAVAILABLE" in source
