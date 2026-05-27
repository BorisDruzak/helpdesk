from __future__ import annotations

import pytest

import scripts.live_ws_v3_probe as probe


pytestmark = pytest.mark.no_db


def test_probe_handshake_defaults_to_diagnostic_client_kind():
    message = probe._handshake(token="redacted-token")

    assert message["payload"]["client_kind"] == "diagnostic_probe"
    assert message["meta"]["client_kind"] == "diagnostic_probe"


def test_probe_refuses_runtime_session_without_explicit_override():
    with pytest.raises(SystemExit):
        probe._guard_live_runtime_probe(client_kind="agent_runtime", allow_live_agent_session=False)


def test_probe_allows_diagnostic_session_without_override():
    probe._guard_live_runtime_probe(client_kind="diagnostic_probe", allow_live_agent_session=False)
