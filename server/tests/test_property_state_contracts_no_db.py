from __future__ import annotations

from copy import deepcopy

import pytest

from shared.redaction import REDACTED, redact_sensitive_payload
from tickets.statuses import (
    CANONICAL_STATUSES,
    LEGACY_STATUS_ALIASES,
    TERMINAL_STATUSES,
    is_valid_canonical_status,
    normalize_status,
    requester_status_for_internal,
    resolve_status,
    status_label_ru,
)
from tickets.workflow_profiles import (
    DEFAULT_REQUESTER_TRANSITIONS,
    DEFAULT_SUPPORT_TRANSITIONS,
    normalize_workflow_profile,
    list_workflow_profiles,
)
from tickets.workflow_service import validate_transition_for_profile


pytestmark = pytest.mark.no_db


def test_redaction_property_nested_payloads_are_non_mutating_idempotent_and_secret_free() -> None:
    payloads = [
        {
            "headers": {
                "Authorization": "Bearer raw-token",
                "token_hash": "safe-token-hash",
                "request_id": "req-1",
            },
            "body": [
                {"password": "nested-password", "safe": "kept"},
                {"api_key": "api-key-value", "trace_id": "trace-1"},
            ],
        },
        {
            "raw_request_body": {"session_token": "session-secret"},
            "items": (
                {"refresh_token": "refresh-secret", "device_id": "dev-1"},
                {"credential_blob": {"secret": "deep-secret"}},
            ),
            "loose_values": {"Token loose-secret", "ordinary"},
        },
    ]
    raw_secrets = (
        "Bearer raw-token",
        "nested-password",
        "api-key-value",
        "session-secret",
        "refresh-secret",
        "deep-secret",
        "Token loose-secret",
    )

    for payload in payloads:
        original = deepcopy(payload)

        redacted = redact_sensitive_payload(payload, extra_markers={"raw_request_body", "credential"})
        redacted_again = redact_sensitive_payload(redacted, extra_markers={"raw_request_body", "credential"})

        assert payload == original
        assert redacted_again == redacted
        redacted_repr = repr(redacted)
        assert REDACTED in redacted_repr
        if "safe-token-hash" in repr(original):
            assert "safe-token-hash" in redacted_repr
        if "req-1" in repr(original):
            assert "req-1" in redacted_repr
        assert all(secret not in repr(redacted) for secret in raw_secrets)


def test_ticket_status_normalization_property_is_idempotent_and_strict_mode_rejects_aliases() -> None:
    for status in CANONICAL_STATUSES:
        assert normalize_status(status) == (status, False)
        assert normalize_status(status.upper()) == (status, True)
        assert resolve_status(status.upper(), fsm_mode="strict") == (None, False)
        assert resolve_status(status, fsm_mode="strict") == (status, False)
        assert resolve_status(status, fsm_mode="soft") == (status, False)
        assert normalize_status(normalize_status(status)[0] or "") == (status, False)
        assert is_valid_canonical_status(status)
        assert status_label_ru(status)
        assert requester_status_for_internal(status)

    for alias, canonical in LEGACY_STATUS_ALIASES.items():
        assert normalize_status(alias) == (canonical, True)
        assert resolve_status(alias, fsm_mode="soft") == (canonical, True)
        assert resolve_status(alias, fsm_mode="strict") == (None, False)
        assert normalize_status(canonical) == (canonical, False)


def test_workflow_profiles_state_machine_property_has_valid_edges_and_no_dead_nonterminal_states() -> None:
    canonical = set(CANONICAL_STATUSES)
    for profile in list_workflow_profiles():
        allowed = set(profile.allowed_statuses)
        transitions = profile.transitions or DEFAULT_SUPPORT_TRANSITIONS

        assert allowed <= canonical
        assert profile.suggested_path[0] == "new"
        assert set(profile.suggested_path) <= allowed
        assert not [status for status in allowed - TERMINAL_STATUSES if not transitions.get(status)]

        for from_status, targets in transitions.items():
            assert from_status in allowed
            assert len(targets) == len(set(targets))
            for to_status in targets:
                assert to_status in allowed
                assert from_status != to_status
                assert validate_transition_for_profile(profile, from_status, to_status, True)

        for from_status, to_status in zip(profile.suggested_path, profile.suggested_path[1:]):
            assert validate_transition_for_profile(profile, from_status, to_status, True)

        reachable = {"new"}
        queue = ["new"]
        while queue:
            current = queue.pop(0)
            for target in transitions.get(current, ()):
                if target not in reachable:
                    reachable.add(target)
                    queue.append(target)
        assert reachable & TERMINAL_STATUSES

        for from_status, targets in DEFAULT_REQUESTER_TRANSITIONS.items():
            for to_status in targets:
                if from_status in allowed and to_status in allowed:
                    assert validate_transition_for_profile(profile, from_status, to_status, False)


def test_workflow_profile_serialization_property_round_trips_default_state_machines() -> None:
    for profile in list_workflow_profiles():
        assert normalize_workflow_profile(profile.to_dict()).to_dict() == profile.to_dict()
