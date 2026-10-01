import pytest

from shared.production_security import production_config_errors


def secure():
    return dict(APP_ENV="prod", ENABLE_DB_PERSISTENCE="true", REQUIRE_HTTPS="true",
                REQUIRE_WSS="true", WEB_SESSION_COOKIE_SECURE="true",
                ALLOW_INSECURE_DEV_DEFAULTS="false", AUTH_ALLOW_QUERY_TOKEN="false",
                AUTH_UI_CONFIG_FALLBACK_ENABLED="false", SERVER_HOST="127.0.0.1",
                CONTROL_HOST="127.0.0.1", SERVER_PUBLIC_BASE_URL="https://helpdesk.sosnadmin.local",
                TRUST_X_FORWARDED_FOR="true", TRUSTED_PROXY_CIDRS="127.0.0.1/32")


def test_secure_production_passes():
    assert production_config_errors(secure()) == []


@pytest.mark.parametrize("name,value", [
    ("WEB_SESSION_COOKIE_SECURE", "false"), ("REQUIRE_HTTPS", "false"),
    ("REQUIRE_WSS", "false"), ("ENABLE_DB_PERSISTENCE", "false"),
    ("SERVER_PUBLIC_BASE_URL", "http://helpdesk.sosnadmin.local"),
    ("SERVER_PUBLIC_BASE_URL", "https://user:password@example.test"),
    ("SERVER_HOST", "0.0.0.0"), ("CONTROL_HOST", "192.168.1.10"),
    ("TRUSTED_PROXY_CIDRS", ""), ("TRUSTED_PROXY_CIDRS", "0.0.0.0/0"),
    ("TRUSTED_PROXY_CIDRS", "invalid"), ("TRUST_X_FORWARDED_FOR", "false"),
    ("ALLOW_INSECURE_DEV_DEFAULTS", "true"), ("AUTH_ALLOW_QUERY_TOKEN", "true"),
    ("AUTH_UI_CONFIG_FALLBACK_ENABLED", "true"),
])
def test_insecure_production_fails_without_echoing_values(name, value):
    values = secure(); values[name] = value
    errors = production_config_errors(values)
    assert any(name in error for error in errors)
    assert "password" not in " ".join(errors)


def test_development_remains_supported():
    assert production_config_errors({"APP_ENV": "dev"}) == []


def test_missing_flags_are_fatal_in_production():
    assert production_config_errors({"APP_ENV": "prod"})


@pytest.mark.parametrize("dsn", ["", "synthetic-invalid-optional-config"])
def test_sentry_is_optional_and_cannot_weaken_security(dsn):
    values = secure()
    values.update(SENTRY_DSN=dsn, SENTRY_ENVIRONMENT="production", SENTRY_TRACES_SAMPLE_RATE="0.10")
    assert production_config_errors(values) == []
    values["WEB_SESSION_COOKIE_SECURE"] = "false"
    assert production_config_errors(values)


def test_cli_accepts_optional_sentry_in_safe_fixture(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    path = tmp_path / "safe-fixture.env"
    values = secure()
    values.update(SENTRY_DSN="", SENTRY_ENVIRONMENT="production", SENTRY_TRACES_SAMPLE_RATE="0.10")
    path.write_text("\n".join(f"{k}={v}" for k, v in values.items()), encoding="utf-8")
    result = subprocess.run([sys.executable, str(Path(__file__).with_name("validate_production_config.py")),
                             "--environment-file", str(path), "--require-production"], capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.strip() == "Production configuration validation passed"
