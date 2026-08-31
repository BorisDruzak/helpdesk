from pathlib import Path


COMMANDS_API = Path("server/docs/REGISTRY_PLATFORM_COMMANDS_V1.md")


def test_registry_command_contract_blocks_authority_cutover_without_security_and_acceptance_evidence() -> None:
    """The command contract must make an unsafe external-authority change ineligible."""
    contract = COMMANDS_API.read_text(encoding="utf-8")
    normalized = " ".join(contract.split())

    for required_term in (
        "HTTPS",
        "service authentication",
        "never log raw tokens",
        "authoritative actor authorization",
        "idempotency key",
        "replay",
        "correlation ID",
        "fail closed",
        "registry_unavailable",
        "registry_unauthorized",
        "registry_operation_uncertain",
        "exactly-once",
        "immutable ticket and consent references",
        "ui_users",
        "web sessions",
        "RBAC",
        "external service acceptance evidence",
        "local/off",
        "no runtime authority change",
    ):
        assert required_term in normalized

    for command in (
        "UI-login eligibility",
        "registration request",
        "approve",
        "reject",
        "bind",
        "revoke",
        "session create",
        "validate",
        "logout",
        "browser pairing",
        "other-account approval",
    ):
        assert command.casefold() in normalized.casefold()


def test_disabling_an_external_operation_flag_never_restores_local_authority_after_remote_execution() -> None:
    """Rollback leaves a remotely executed or uncertain operation fail-closed."""
    contract = " ".join(COMMANDS_API.read_text(encoding="utf-8").split()).casefold()

    assert "disabling a per-operation external flag must not restore local command authority" in contract
    assert "after a remote success or `registry_operation_uncertain`" in contract
    assert "operation remains unavailable and fail-closed" in contract
    assert "explicit reconciliation or state-sync evidence approves an authority" in contract
