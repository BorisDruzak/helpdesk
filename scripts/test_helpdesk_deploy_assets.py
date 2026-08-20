from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "deploy" / "helpdesk"


def test_ip_bootstrap_proxies_to_loopback_without_port_collision() -> None:
    nginx = (ROOT / "helpdesk.nginx.conf").read_text(encoding="utf-8")
    environment = (ROOT / "helpdesk.env.example").read_text(encoding="utf-8")

    assert "listen 8080;" in nginx
    assert "proxy_pass http://127.0.0.1:8666;" in nginx
    assert "listen 8666;" not in nginx
    assert "SERVER_HOST=127.0.0.1" in environment
    assert "SERVER_PORT=8666" in environment


def test_production_dependencies_and_runtime_data_root_are_declared() -> None:
    requirements = (ROOT.parents[1] / "server" / "requirements.txt").read_text(encoding="utf-8")
    environment = (ROOT / "helpdesk.env.example").read_text(encoding="utf-8")

    assert "loguru" in requirements
    assert "pydantic>=2.0" in requirements
    assert "PC_CLIENT_SERVER_DATA_ROOT=/var/lib/helpdesk" in environment
    assert "PC_CLIENT_DISABLE_LEGACY_RUNTIME_MIGRATION=true" in environment
