import pytest

from pc_agent.ui_gui.server_api import ServerApiError, TicketApiClient


pytestmark = pytest.mark.no_db


class _FakeResponse:
    def __init__(self, *, status: int, text: str):
        self.status = status
        self._text = text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def text(self) -> str:
        return self._text

    async def json(self):
        raise AssertionError("error response should be parsed from text once")


class _FakeSession:
    def __init__(self, response: _FakeResponse):
        self.response = response
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append({"method": "POST", "url": url, **kwargs})
        return self.response


@pytest.mark.asyncio
async def test_create_ticket_validation_denial_raises_structured_server_api_error():
    response = _FakeResponse(
        status=400,
        text=(
            '{"status":"error","error":"validation_error","error_code":"VALIDATION_ERROR",'
            '"details":{"form_payload":{"impact_scope":"Поле обязательно","work_continuity":"Поле обязательно"}}}'
        ),
    )
    session = _FakeSession(response)
    client = TicketApiClient(base_url="https://server.test/api", device_id="device-1")

    async def _get_session():
        return session

    client._get_session = _get_session

    with pytest.raises(ServerApiError) as exc_info:
        await client.create_ticket(
            title="invalid",
            description="invalid",
            form_key="network",
            ticket_type="incident",
            form_payload={"diagnostic_marker": "p4-01-test"},
            requester_account={"account_session_id": "session-1", "session_token": "secret-token"},
        )

    error = exc_info.value
    assert error.http_status == 400
    assert error.error == "validation_error"
    assert error.error_code == "VALIDATION_ERROR"
    assert error.details["form_payload"]["impact_scope"] == "Поле обязательно"
    assert error.url_path == "/api/tickets/create"
    assert "secret-token" not in str(error)
    assert session.calls[0]["json"]["requester_account"]["session_id"] == "session-1"
    assert TicketApiClient._trace_payload_preview(session.calls[0]["json"])["requester_account"]["session_token"] == "<redacted>"


def test_server_api_error_derives_error_code_from_error_name():
    error = ServerApiError.from_response(
        http_status=409,
        response_text='{"status":"error","error":"ticket_closed","details":{"state":"closed"}}',
        url_path="/tickets/ticket-1/message",
    )

    assert error.http_status == 409
    assert error.error == "ticket_closed"
    assert error.error_code == "TICKET_CLOSED"
    assert error.details == {"state": "closed"}
