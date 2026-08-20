from pathlib import Path


def test_control_plane_reads_bind_address_from_environment() -> None:
    source = (Path(__file__).resolve().parents[1] / "control_plane.py").read_text(encoding="utf-8")

    assert 'CONTROL_HOST = (os.getenv("CONTROL_HOST", "0.0.0.0")' in source
    assert 'CONTROL_PORT = int(os.getenv("CONTROL_PORT", "8667")' in source
