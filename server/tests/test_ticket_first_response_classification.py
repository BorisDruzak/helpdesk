from tickets.public_access import build_public_access_message, is_public_support_reply_payload
import pytest


pytestmark = pytest.mark.db_cleanup("tickets")

def test_public_access_message_is_system_notice_not_first_response():
    payload = build_public_access_message("RZ76RPDR", "ticket-1")

    assert payload["sender_role"] == "system"
    assert payload["from"] == "system"
    assert is_public_support_reply_payload(payload) is False


def test_first_response_requires_public_staff_reply_not_client_agent_message():
    assert is_public_support_reply_payload(
        {"sender_role": "support", "from": "support", "visibility": "public", "text": "Взял в работу"}
    )
    assert is_public_support_reply_payload(
        {"sender_role": "admin", "from": "admin", "visibility": "public", "text": "Ответ поддержки"}
    )
    assert not is_public_support_reply_payload(
        {"sender_role": "agent", "from": "agent", "visibility": "public", "text": "Сообщение пользователя из агента"}
    )
    assert not is_public_support_reply_payload(
        {"sender_role": "support", "from": "support", "visibility": "internal", "text": "Внутренняя заметка"}
    )
