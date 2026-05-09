from access_control.catalog import get_role_permission_codes
from remote_assist.service import issue_short_lived_token, verify_token_hash


def test_remote_assist_tokens_are_hashed_and_validated() -> None:
    issued = issue_short_lived_token()

    assert issued.token
    assert issued.token not in issued.token_hash
    assert verify_token_hash(issued.token, issued.token_hash)
    assert not verify_token_hash("wrong-token", issued.token_hash)


def test_support_role_can_request_and_view_remote_assist() -> None:
    permissions = set(get_role_permission_codes("support"))

    assert "remote_assist.request" in permissions
    assert "remote_assist.view" in permissions
