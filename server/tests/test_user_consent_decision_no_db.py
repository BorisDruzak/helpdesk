from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from consent import service

pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", ["approved", "denied"])
@pytest.mark.parametrize("status", [None, "queued", "failed"])
async def test_changed_or_missing_subject_cannot_accept_consent(monkeypatch, decision, status):
    operation = SimpleNamespace(status=status) if status is not None else None
    operations = SimpleNamespace(get_by_operation_id=AsyncMock(return_value=operation))
    monkeypatch.setattr(service, "OperationsRepo", lambda session: operations)
    row = SimpleNamespace(subject_type="operation", subject_id="operation-test")
    with pytest.raises(service.ConsentAccessError) as caught:
        await service.UserConsentService(object())._apply_subject_decision(row, decision=decision, actor_id="requester-test", reason=None)
    assert caught.value.status == 409
    assert caught.value.error_code == "OPERATION_STATE_CONFLICT"


@pytest.mark.asyncio
async def test_non_operation_consent_does_not_require_operation_transition(monkeypatch):
    lookup = AsyncMock(side_effect=AssertionError("non-operation subject must not query operation"))
    monkeypatch.setattr(service, "OperationsRepo", lambda session: SimpleNamespace(get_by_operation_id=lookup))
    row = SimpleNamespace(subject_type="remote_assist", subject_id="remote-assist-test")
    await service.UserConsentService(object())._apply_subject_decision(row, decision="approved", actor_id="requester-test", reason=None)
    lookup.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", ["approved", "denied"])
@pytest.mark.parametrize("transitioned", [False, True])
async def test_subject_decision_requires_successful_operation_transition(monkeypatch, decision, transitioned):
    operation = SimpleNamespace(status="waiting_consent")
    operations = SimpleNamespace(get_by_operation_id=AsyncMock(return_value=operation))
    lifecycle = SimpleNamespace(
        approve_consent=AsyncMock(return_value=transitioned),
        deny_consent=AsyncMock(return_value=transitioned),
    )
    monkeypatch.setattr(service, "OperationsRepo", lambda session: operations)
    monkeypatch.setattr(service, "OperationService", lambda session, **kwargs: lifecycle)
    row = SimpleNamespace(subject_type="operation", subject_id="operation-test")
    consent = service.UserConsentService(object())
    if transitioned:
        await consent._apply_subject_decision(row, decision=decision, actor_id="requester-test", reason=None)
    else:
        with pytest.raises(service.ConsentAccessError) as caught:
            await consent._apply_subject_decision(row, decision=decision, actor_id="requester-test", reason=None)
        assert caught.value.status == 409
        assert caught.value.error_code == "OPERATION_STATE_CONFLICT"
    method = lifecycle.approve_consent if decision == "approved" else lifecycle.deny_consent
    await_method = lifecycle.deny_consent if decision == "approved" else lifecycle.approve_consent
    method.assert_awaited_once_with("operation-test", decided_by="requester-test", reason=None)
    await_method.assert_not_awaited()
