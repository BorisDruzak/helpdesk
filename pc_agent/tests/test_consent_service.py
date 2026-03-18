import time
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pc_agent.core.consent_service import ConsentService, ConsentState


class _FakeDbManager:
    def __init__(self):
        self.pending = {}

    async def add_pending_consent(self, **kwargs):
        self.pending[kwargs["operation_id"]] = kwargs

    async def get_pending_consent(self, operation_id: str):
        return self.pending.get(operation_id)

    async def remove_pending_consent(self, operation_id: str):
        return self.pending.pop(operation_id, None) is not None

    async def cleanup_expired_consents(self):
        now = int(time.time())
        expired = [k for k, v in self.pending.items() if v.get("expires_at", now + 1) < now]
        for k in expired:
            self.pending.pop(k, None)
        return len(expired)


@pytest.mark.asyncio
async def test_create_and_approve_pending_consent():
    db = _FakeDbManager()
    service = ConsentService(db, device_id_getter=lambda: "dev-1")

    created = await service.create_pending(
        tool_name="screen.collect",
        params={"a": 1},
        payload_hash="hash",
        request_id="req-1",
        session_key="sess-1",
        actor_role="user",
        ticket_id="t-1",
        job_id="j-1",
        expires_in_sec=60,
    )
    assert created.state == ConsentState.WAITING_USER

    resolved = await service.apply_decision(consent_token=created.consent_token, approved=True)
    assert resolved.state == ConsentState.APPROVED
    assert resolved.pending["tool_name"] == "screen.collect"


@pytest.mark.asyncio
async def test_expired_pending_consent_returns_expired():
    db = _FakeDbManager()
    service = ConsentService(db, device_id_getter=lambda: "dev-1")
    token = "tok-expired"
    db.pending[token] = {
        "operation_id": token,
        "tool_name": "x",
        "params": {},
        "actor_role": "user",
        "expires_at": int(time.time()) - 1,
    }

    resolved = await service.apply_decision(consent_token=token, approved=True)
    assert resolved.state == ConsentState.EXPIRED
