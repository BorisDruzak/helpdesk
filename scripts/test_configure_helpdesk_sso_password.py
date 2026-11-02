from copy import deepcopy

import pytest

from scripts.configure_helpdesk_sso_password import password_client
from scripts import configure_helpdesk_sso_password as module


def client():
    return {"id": "fixed-id", "clientId": "helpdesk-staging-web", "enabled": True,
            "protocol": "openid-connect", "publicClient": False, "standardFlowEnabled": True,
            "implicitFlowEnabled": False, "directAccessGrantsEnabled": False,
            "serviceAccountsEnabled": False, "fullScopeAllowed": False,
            "redirectUris": ["https://helpdesk-staging.sosnadmin.local/api/web/session/oidc/callback"],
            "webOrigins": [],
            "attributes": {"default.acr.values": "urn:sosnadmin:loa:2", "minimum.acr.value": "2",
                           "pkce.code.challenge.method": "S256", "other": "retained"}}


def test_password_client_changes_only_two_assurance_attributes():
    before = client()
    original = deepcopy(before)
    after = password_client(before)
    expected = deepcopy(before)
    expected["attributes"].update({"default.acr.values": "urn:sosnadmin:loa:1", "minimum.acr.value": "1"})
    assert after == expected and before == original
    assert password_client(after) == after


@pytest.mark.parametrize("change", [
    {"clientId": "endpoint-staging-admin"}, {"clientId": "helpdesk-web"},
    {"publicClient": True}, {"directAccessGrantsEnabled": True}, {"fullScopeAllowed": True},
    {"redirectUris": ["https://elsewhere.example/callback"]},
    {"authenticationFlowBindingOverrides": {"browser": "custom-flow"}},
    {"attributes": {"pkce.code.challenge.method": "plain"}},
])
def test_password_client_rejects_wrong_scope_or_unreviewed_policy(change):
    before = client()
    before.update(change)
    with pytest.raises(ValueError):
        password_client(before)


def test_reconcile_accepts_only_provider_inferred_origin():
    original = client()
    current = password_client(original)
    current["webOrigins"] = ["https://helpdesk-staging.sosnadmin.local"]
    assert module.reconciled_password_client(current, original) == password_client(original)
    current["enabled"] = False
    with pytest.raises(ValueError, match="UnexpectedReconciliationDrift"):
        module.reconciled_password_client(current, original)


@pytest.mark.parametrize("failure", [None, "fingerprint", "concurrent", "readback", "other_client"])
def test_apply_verifies_backup_scope_and_readback(monkeypatch, tmp_path, failure):
    before = client()
    calls = []
    class Api:
        reads = 0
        written = False
        def login(self):
            pass
        def client(self, name):
            if name != module.CLIENT:
                return {"name": name, "changed": self.written and failure == "other_client"}
            self.reads += 1
            if self.reads == 2 and failure == "concurrent":
                return {**before, "name": "concurrently changed"}
            return deepcopy(password_client(before) if self.written and failure != "readback" else before)
        def request(self, method, path, *, payload):
            backups = list(tmp_path.glob("helpdesk-password-*/client.json"))
            assert len(backups) == 1
            import json
            assert json.loads(backups[0].read_text()) == before
            assert method == "PUT" and path == module.PREFIX + "/clients/fixed-id"
            assert payload == {key: password_client(before)[key] for key in ("id", "clientId", "fullScopeAllowed", "attributes", "webOrigins")}
            calls.append(payload)
            self.written = True
    monkeypatch.setattr(module, "Admin", Api)
    monkeypatch.setattr(module.os, "geteuid", lambda: 0, raising=False)
    monkeypatch.setattr(module.subprocess, "check_output", lambda *a, **kw: "192.168.100.19")
    real_path = module.Path
    monkeypatch.setattr(module, "Path", lambda value: tmp_path if str(value) == "/var/backups/keycloak" else real_path(value))
    expected = "wrong" if failure == "fingerprint" else module.fingerprint(before)
    monkeypatch.setattr("sys.argv", ["helper", "--apply", "--expected-sha256", expected])
    if failure:
        with pytest.raises(ValueError, match={"fingerprint": "ClientChangedSincePlan", "concurrent": "ClientChangedBeforeWrite",
            "readback": "ClientReadbackMismatch", "other_client": "UnrelatedClientChanged"}[failure]):
            module.main()
    else:
        module.main()
    assert len(calls) == (0 if failure in ("fingerprint", "concurrent") else 1)
