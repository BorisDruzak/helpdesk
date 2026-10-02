import json
from types import SimpleNamespace

import pytest

from observability.browser_runtime import browser_runtime_config, serialize_browser_runtime_config

pytestmark = pytest.mark.no_db


def settings(**overrides):
    return SimpleNamespace(**({
        'APP_ENV': 'prod', 'SENTRY_ENVIRONMENT': '', 'SENTRY_RELEASE': '',
        'SENTRY_DSN': 'BACKEND_SECRET', 'SENTRY_TRACES_SAMPLE_RATE': '.10',
        'SENTRY_BROWSER_DSN': 'https://public_test_key@sentry.example.invalid/1',
        'SENTRY_BROWSER_TRACES_SAMPLE_RATE': '.05', 'DATABASE_URL': 'DATABASE_SECRET',
    } | overrides))


@pytest.mark.parametrize('dsn', ['', None, 'broken', 'https://host/1',
    'https://key:password@host/1', 'https://key@host/1?token=x',
    'https://key@host/1#fragment', 'http://key@host/1',
    'https://key@host/not-project', 'https://key@host/1\n',
    'https://key@host\\evil/1', 'https://invalid-key@host/1', 'HTTPS://key@host/1'])
def test_invalid_browser_dsn_disables(dsn, tmp_path):
    assert browser_runtime_config(settings(SENTRY_BROWSER_DSN=dsn), identity_path=tmp_path/'absent') == {'sentry': None}


def test_public_config_reuses_environment_and_immutable_release(tmp_path):
    identity = tmp_path/'release-identity.json'
    identity.write_text(json.dumps({'helpdesk_git_sha': 'A'*40}))
    payload = browser_runtime_config(settings(), identity_path=identity)
    assert payload == {'sentry': {
        'dsn': 'https://public_test_key@sentry.example.invalid/1',
        'environment': 'production', 'release': 'a'*40, 'tracesSampleRate': .05}}
    assert 'SECRET' not in json.dumps(payload)


@pytest.mark.parametrize('rate', ['bad', 'NaN', 'Infinity', '-.1', '1.1', None, True])
def test_invalid_rate_uses_safe_default(rate, tmp_path):
    assert browser_runtime_config(settings(SENTRY_BROWSER_TRACES_SAMPLE_RATE=rate), identity_path=tmp_path/'absent')['sentry']['tracesSampleRate'] == .05


@pytest.mark.parametrize('rate', ['0', '.25', '1'])
def test_valid_rate_retained(rate, tmp_path):
    assert browser_runtime_config(settings(SENTRY_BROWSER_TRACES_SAMPLE_RATE=rate), identity_path=tmp_path/'absent')['sentry']['tracesSampleRate'] == float(rate)


def test_invalid_release_omitted_and_shared_environment_applied(tmp_path):
    payload = browser_runtime_config(settings(SENTRY_RELEASE='invalid', SENTRY_ENVIRONMENT='staging'), identity_path=tmp_path/'absent')
    assert payload['sentry']['environment'] == 'staging'
    assert 'release' not in payload['sentry']


def test_valid_release_override(tmp_path):
    payload = browser_runtime_config(settings(SENTRY_RELEASE='b'*40), identity_path=tmp_path/'absent')
    assert payload['sentry']['release'] == 'b'*40


def test_json_serialization_cannot_break_out_of_script():
    value = {'sentry': '</script><script>alert(1)</script>&\u2028\u2029'}
    encoded = serialize_browser_runtime_config(value)
    assert '<' not in encoded and '>' not in encoded and '&' not in encoded
    assert '\u2028' not in encoded and '\u2029' not in encoded
    assert json.loads(encoded) == value
