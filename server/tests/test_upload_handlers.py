from types import SimpleNamespace

import pytest

from uploads.handlers import _content_disposition_attachment, _operation_bound_agent_upload_error


@pytest.mark.no_db
def test_content_disposition_attachment_uses_ascii_fallback_and_utf8_filename_star():
    header = _content_disposition_attachment("p2 вложение run.txt")

    assert header.startswith('attachment; filename="')
    assert 'filename="p2_run.txt"' in header
    assert "filename*=UTF-8''p2%20%D0%B2%D0%BB%D0%BE%D0%B6%D0%B5%D0%BD%D0%B8%D0%B5%20run.txt" in header
    assert "вложение" not in header.split("filename=", 1)[1].split(";", 1)[0]


@pytest.mark.no_db
def test_content_disposition_attachment_sanitizes_path_like_fallback():
    header = _content_disposition_attachment("../evil name.txt")

    assert 'filename="evil_name.txt"' in header
    assert "../" not in header


@pytest.mark.no_db
def test_operation_bound_agent_upload_allows_matching_operation_context():
    auth_context = SimpleNamespace(actor_id="device-a")
    operation = SimpleNamespace(ticket_id="ticket-a", device_id="device-a")

    assert (
        _operation_bound_agent_upload_error(
            operation=operation,
            auth_context=auth_context,
            ticket_id="ticket-a",
        )
        is None
    )


@pytest.mark.no_db
def test_operation_bound_agent_upload_denies_ticket_mismatch():
    auth_context = SimpleNamespace(actor_id="device-a")
    operation = SimpleNamespace(ticket_id="ticket-b", device_id="device-a")

    response = _operation_bound_agent_upload_error(
        operation=operation,
        auth_context=auth_context,
        ticket_id="ticket-a",
    )

    assert response is not None
    assert response.status == 403


@pytest.mark.no_db
def test_operation_bound_agent_upload_denies_device_mismatch():
    auth_context = SimpleNamespace(actor_id="device-a")
    operation = SimpleNamespace(ticket_id="ticket-a", device_id="device-b")

    response = _operation_bound_agent_upload_error(
        operation=operation,
        auth_context=auth_context,
        ticket_id="ticket-a",
    )

    assert response is not None
    assert response.status == 403
