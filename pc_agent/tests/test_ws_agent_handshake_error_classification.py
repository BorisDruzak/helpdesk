from pc_agent.ws_agent import _is_auth_rejection_handshake_error


def test_transient_502_with_string_message_is_not_auth_rejection() -> None:
    assert (
        _is_auth_rejection_handshake_error(
            status=502,
            error_msg="502, message='Invalid response status'",
            message="Invalid response status",
        )
        is False
    )


def test_4003_and_token_messages_are_auth_rejections() -> None:
    assert _is_auth_rejection_handshake_error(
        status=4003,
        error_msg="4003, message='Invalid token'",
        message="Invalid token",
    )
    assert _is_auth_rejection_handshake_error(
        status=401,
        error_msg="401",
        message=b"Token required",
    )
