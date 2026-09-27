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
