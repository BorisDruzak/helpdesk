from copy import deepcopy

import pytest

from scripts.helpdesk_requester_confirmation import build_confirmation_request, pending_expiry_update
from types import SimpleNamespace

pytestmark = pytest.mark.no_db


def test_ordinary_confirmation_preserves_existing_rules_and_disables_automatic_closure():
    baseline = {"code": "guided_studio_20261011_closure", "version": "1.0.2", "title": "Обычное закрытие",
        "scope_level": "system", "scope_ref": None, "config": {"require_public_summary": True,
        "require_resolution_code": False, "evidence": {"unchanged": True}, "requester_confirmation": {"required": False}}}
    original = deepcopy(baseline)
    request = build_confirmation_request(baseline)
    assert baseline == original
    assert request["requested_version"] == "1.0.3"
    assert request["config"]["requester_confirmation"] == {"required": True, "auto_close_after_days": None, "reopen_on_negative_feedback": True}
    assert request["config"]["evidence"] == {"unchanged": True}
    assert request["config"]["require_resolution_code"] is False
    with pytest.raises(ValueError):
        build_confirmation_request({**baseline, "code": "special_policy"})
    with pytest.raises(ValueError):
        build_confirmation_request({**baseline, "version": "unexpected"})


def test_existing_pending_request_loses_automatic_expiry_without_replacing_request_or_decision():
    fields = {"resolution_confirmation": {"pending": True, "request_id": "keep-request", "responded_option_id": None},
              "resolution_confirmation_policy": {"required": True, "auto_close_after_days": 3}}
    original = deepcopy(fields)
    ticket = SimpleNamespace(custom_fields=fields)
    update = pending_expiry_update(ticket, {"required": True, "auto_close_after_days": None})
    assert fields == original
    assert update["resolution_confirmation"] == original["resolution_confirmation"]
    assert update["resolution_confirmation_policy"]["auto_close_after_days"] is None
    assert pending_expiry_update(ticket, {"required": True, "auto_close_after_days": 3}) is None
    fields["resolution_confirmation"]["pending"] = False
    assert pending_expiry_update(ticket, {"required": True, "auto_close_after_days": None}) is None
