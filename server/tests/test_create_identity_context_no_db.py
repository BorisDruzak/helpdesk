from types import SimpleNamespace
import inspect
from unittest.mock import AsyncMock

import pytest

from tickets import create_flow

pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
async def test_confirmed_context_requires_exact_verified_binding():
    binding = create_flow.VerifiedRequesterBinding(device_id="device", person_id="person", binding_id="binding")
    for device, person, binding_id, expected in [("device", "person", "binding", "confirmed_binding"),
        ("other", "person", "binding", ""), ("device", "other", "binding", ""),
        ("device", "person", "other", "")]:
        context = await create_flow._resolve_requester_identity_context(object(), device_id=device,
            requester_id="actor", requester_account={"account_mode": "confirmed_binding", "person_id": person, "binding_id": binding_id},
            verified_requester_binding=binding, state=None)
        assert context.account_mode == expected
        assert context.confirmed_binding is (binding if expected else None)


@pytest.mark.asyncio
async def test_browser_context_uses_verified_identity(monkeypatch):
    verify = AsyncMock(return_value="verified-person")
    monkeypatch.setattr(create_flow, "_verify_browser_requester_identity", verify)
    context = await create_flow._resolve_requester_identity_context(object(), device_id=None,
        requester_id="actor", requester_account={"account_mode": "browser_no_device", "person_id": "claimed"},
        verified_requester_binding=None, state=SimpleNamespace())
    assert context.browser_person_id == "verified-person"
    assert context.confirmed_binding is None
    assert context.account_mode == "browser_no_device"


@pytest.mark.asyncio
@pytest.mark.parametrize("forged_binding", [False, True])
async def test_create_context_preserves_active_binding_and_rejects_forged_claim(monkeypatch, forged_binding):
    status = {"status": "admin_confirmed", "active_binding": {"person_id": "person", "binding_id": "binding", "asset_id": "asset"}}
    monkeypatch.setattr(create_flow, "_read_registry_account_status", AsyncMock(return_value=status))
    monkeypatch.setattr(create_flow, "TicketContextBuilder", lambda *args, **kwargs: SimpleNamespace(
        requester_reference_snapshot=AsyncMock(return_value=({"person_id": "person"}, {"person_id": "person"})),
        build=AsyncMock(return_value=None),
    ))
    signature = inspect.signature(create_flow.create_ticket_with_side_effects)
    arguments = signature.bind(object(), device_id="device", requester_id="actor", title="Title", description="Description", user_display_name="Actor")
    arguments.apply_defaults()
    data = {name: arguments.arguments[name] for name in create_flow.TicketCreateInput.__dataclass_fields__}
    if forged_binding:
        data["requester_account"] = {"account_mode": "confirmed_binding", "person_id": "person", "binding_id": "binding"}
    context = await create_flow._build_ticket_create_context(object(), submission=create_flow.TicketCreateInput(**data),
        ticket_id="ticket", registry=object(), verified_requester_binding=None, state=None)
    assert context.requester_person_id == (None if forged_binding else "person")
    assert context.requester_binding_id == (None if forged_binding else "binding")
