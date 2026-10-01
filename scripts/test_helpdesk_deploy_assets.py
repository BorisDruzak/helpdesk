from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "deploy" / "helpdesk"


def test_production_tls_proxies_to_loopback_without_port_collision() -> None:
    nginx = (ROOT / "helpdesk.nginx.conf").read_text(encoding="utf-8")
    environment = (ROOT / "helpdesk.env.example").read_text(encoding="utf-8")

    assert "listen 443 ssl;" in nginx
    assert "return 308 https://helpdesk.sosnadmin.local$request_uri;" in nginx
    assert "ssl_certificate_key /etc/helpdesk/tls/privkey.pem;" in nginx
    assert "proxy_set_header X-Forwarded-Proto $scheme;" in nginx
    assert "proxy_pass http://127.0.0.1:8666;" in nginx
    assert "listen 8666;" not in nginx
    assert "SERVER_HOST=127.0.0.1" in environment
    assert "SERVER_PORT=8666" in environment
    assert "APP_ENV=prod" in environment
    assert "REQUIRE_HTTPS=true" in environment
    assert "REQUIRE_WSS=true" in environment
    assert "WEB_SESSION_COOKIE_SECURE=true" in environment


def test_production_dependencies_and_runtime_data_root_are_declared() -> None:
    requirements = (ROOT.parents[1] / "server" / "requirements.txt").read_text(encoding="utf-8")
    environment = (ROOT / "helpdesk.env.example").read_text(encoding="utf-8")

    assert "loguru" in requirements
    assert "pydantic>=2.12,<3" in requirements
    assert "PC_CLIENT_SERVER_DATA_ROOT=/var/lib/helpdesk" in environment
    assert "PC_CLIENT_DISABLE_LEGACY_RUNTIME_MIGRATION=true" in environment
    assert "HELPDESK_CONTROL_LIFECYCLE_ENABLED=false" in environment


def test_host_bootstrap_preserves_isolation_and_requires_root_owned_env() -> None:
    bootstrap = (ROOT / "install_helpdesk_host.sh").read_text(encoding="utf-8")

    assert "id -u" in bootstrap
    assert "/etc/helpdesk/helpdesk.env" in bootstrap
    assert "useradd --system" in bootstrap
    assert "/opt/helpdesk/releases" in bootstrap
    assert "/var/lib/helpdesk" in bootstrap
    assert "helpdesk-server.service" in bootstrap
    assert "helpdesk-control.service" in bootstrap
    assert "helpdesk-migrate.service" in bootstrap
    assert "/etc/nginx/sites-available/helpdesk" in bootstrap
    assert "endpoint-platform" not in bootstrap


def test_sentry_runtime_contract_is_optional_and_server_only() -> None:
    from scripts.validate_production_config import read_environment
    environment = read_environment(ROOT / "helpdesk.env.example")
    assert environment["SENTRY_DSN"] == ""
    assert environment["SENTRY_ENVIRONMENT"] == "production"
    assert environment["SENTRY_TRACES_SAMPLE_RATE"] == "0.10"
    assert "sentry-sdk==2.71.0" in (ROOT.parents[1] / "server" / "requirements.txt").read_text(encoding="utf-8")
    migrate = (ROOT / "helpdesk-migrate.service").read_text(encoding="utf-8")
    assert "EnvironmentFile=/etc/helpdesk/helpdesk.env" in migrate
    assert "run_server.py" not in migrate and "configure_sentry" not in migrate
