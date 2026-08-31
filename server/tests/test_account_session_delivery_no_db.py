from __future__ import annotations

import copy

import pytest

import config
from registry import account_session_service as service


pytestmark = pytest.mark.no_db


def test_session_token_delivery_envelope_round_trips_without_plaintext(monkeypatch):
    monkeypatch.setattr(config, "ACCOUNT_SESSION_DELIVERY_SECRET", "unit-delivery-secret")
    token = "session-token-that-must-not-be-stored-plain"

    envelope = service._build_session_token_delivery_envelope(
        request_id="request-1",
        session_id="session-1",
        session_token=token,
    )

    assert token not in repr(envelope)
    assert envelope["alg"] == service.SESSION_TOKEN_DELIVERY_ALG
    assert service._decrypt_session_token_delivery_envelope(envelope, request_id="request-1") == token
    assert service._decrypt_session_token_delivery_envelope(envelope, request_id="request-2") is None


def test_session_token_delivery_envelope_rejects_tampering(monkeypatch):
    monkeypatch.setattr(config, "ACCOUNT_SESSION_DELIVERY_SECRET", "unit-delivery-secret")
    envelope = service._build_session_token_delivery_envelope(
        request_id="request-1",
        session_id="session-1",
        session_token="session-token",
    )
    tampered = copy.deepcopy(envelope)
    tampered["ciphertext"] = tampered["ciphertext"][:-1] + ("A" if tampered["ciphertext"][-1:] != "A" else "B")

    assert service._decrypt_session_token_delivery_envelope(tampered, request_id="request-1") is None


def test_session_token_delivery_metadata_resets_delivery_state(monkeypatch):
    monkeypatch.setattr(config, "ACCOUNT_SESSION_DELIVERY_SECRET", "unit-delivery-secret")
    metadata = {
        "session_token_delivered_at": "2026-06-25T00:00:00+00:00",
        "other": "kept",
    }

    updated = service._with_session_token_delivery(
        metadata,
        request_id="request-1",
        session_id="session-1",
        session_token="session-token",
    )

    assert updated["other"] == "kept"
    assert updated["session_token_delivery_status"] == "pending"
    assert "session_token_delivered_at" not in updated
    assert "session_token_delivery" in updated
