"""Plan/apply password-level SSO for the fixed Helpdesk staging Keycloak client.

Run as root on the existing SSO host. Credentials stay in protected runtime
storage. Only the selected client's two assurance attributes may change.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8088"
PREFIX = "/admin/realms/sosnadmin"
CLIENT = "helpdesk-staging-web"
CALLBACK = "https://helpdesk-staging.sosnadmin.local/api/web/session/oidc/callback"
PROVISION = Path("/etc/keycloak/pilot-provision-20261027.env")


def password_client(before):
    required = {"clientId": CLIENT, "protocol": "openid-connect", "enabled": True,
                "publicClient": False, "standardFlowEnabled": True, "implicitFlowEnabled": False,
                "directAccessGrantsEnabled": False, "serviceAccountsEnabled": False, "fullScopeAllowed": False}
    if any(before.get(k) != v for k, v in required.items()) or before.get("redirectUris") != [CALLBACK]:
        raise ValueError("UnexpectedClientPolicy")
    if before.get("authenticationFlowBindingOverrides", {}):
        raise ValueError("CustomAuthenticationFlowRequiresReview")
    attrs = before.get("attributes", {})
    if attrs.get("pkce.code.challenge.method") != "S256":
        raise ValueError("PkceRequired")
    if (attrs.get("default.acr.values"), attrs.get("minimum.acr.value")) not in {
        ("urn:sosnadmin:loa:2", "2"), ("urn:sosnadmin:loa:1", "1")
    }:
        raise ValueError("UnexpectedAssurancePolicy")
    after = deepcopy(before)
    after["attributes"].update({"default.acr.values": "urn:sosnadmin:loa:1", "minimum.acr.value": "1"})
    return after


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def reconciled_password_client(current, original):
    """Repair only the verified Keycloak inference from an omitted webOrigins."""
    desired = password_client(original)
    inferred = deepcopy(desired)
    inferred["webOrigins"] = ["https://helpdesk-staging.sosnadmin.local"]
    if original.get("webOrigins") != [] or current != inferred:
        raise ValueError("UnexpectedReconciliationDrift")
    return desired


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Admin:
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        self.token = None

    def request(self, method, path, *, payload=None, form=None):
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        data = None
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        if form is not None:
            data = urllib.parse.urlencode(form).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        request = urllib.request.Request(BASE + path, method=method, data=data, headers=headers)
        try:
            with self.opener.open(request, timeout=10) as response:
                body = response.read(1024 * 1024 + 1)
                if len(body) > 1024 * 1024:
                    raise ValueError("ResponseTooLarge")
                return json.loads(body) if body else None
        except urllib.error.HTTPError as error:
            raise ValueError("ProviderHttp" + str(error.code)) from None

    def login(self):
        details = PROVISION.lstat()
        if not stat.S_ISREG(details.st_mode) or details.st_uid != 0 or stat.S_IMODE(details.st_mode) != 0o600:
            raise ValueError("PrivateProvisionFileRequired")
        values = {}
        for line in PROVISION.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                parsed = shlex.split(value)
                values[key.strip()] = parsed[0] if len(parsed) == 1 else ""
        result = self.request("POST", "/realms/master/protocol/openid-connect/token", form={
            "grant_type": "password", "client_id": "admin-cli", "username": "sso-bootstrap",
            "password": values["SSO_BOOTSTRAP_PASSWORD"]})
        self.token = result["access_token"]

    def client(self, name):
        rows = self.request("GET", PREFIX + "/clients?clientId=" + urllib.parse.quote(name, safe=""))
        if len(rows) != 1 or rows[0].get("clientId") != name:
            raise ValueError("UniqueClientRequired")
        identifier = rows[0]["id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", identifier):
            raise ValueError("InvalidClientId")
        return self.request("GET", PREFIX + "/clients/" + identifier)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-sha256")
    parser.add_argument("--reconcile-backup", type=Path)
    args = parser.parse_args()
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        raise ValueError("LinuxRootRequired")
    addresses = subprocess.check_output(["hostname", "-I"], text=True).split()
    if "192.168.100.19" not in addresses:
        raise ValueError("WrongSsoHost")
    api = Admin()
    api.login()
    guards = {name: api.client(name) for name in (
        "helpdesk-web", "endpoint-admin", "worktime-employee", "endpoint-staging-admin", "worktime-staging-employee")}
    before = api.client(CLIENT)
    after = password_client(before)
    if args.reconcile_backup:
        backup = args.reconcile_backup
        if (backup.parent.parent != Path("/var/backups/keycloak") or not backup.parent.name.startswith("helpdesk-password-")
                or backup.name != "client.json" or backup.is_symlink() or backup.parent.is_symlink()):
            raise ValueError("UnexpectedReconciliationBackup")
        metadata = backup.stat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) != 0o600:
            raise ValueError("PrivateReconciliationBackupRequired")
        after = reconciled_password_client(before, json.loads(backup.read_text()))
    receipt = {"client": CLIENT, "before_sha256": fingerprint(before), "changed": before != after,
               "default_acr": after["attributes"]["default.acr.values"], "minimum_acr": "1", "applied": False}
    if args.apply and before != after:
        if args.expected_sha256 != fingerprint(before):
            raise ValueError("ClientChangedSincePlan")
        # A private metadata backup precedes the single client PUT. No user,
        # credential, required action, realm flow or other client is modified.
        backup_root = Path("/var/backups/keycloak")
        if backup_root.is_symlink() or not backup_root.is_dir():
            raise ValueError("PhysicalBackupDirectoryRequired")
        directory = Path(tempfile.mkdtemp(prefix="helpdesk-password-", dir=backup_root))
        backup = directory / "client.json"
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(before, stream)
            stream.flush()
            os.fsync(stream.fileno())
        if api.client(CLIENT) != before:
            raise ValueError("ClientChangedBeforeWrite")
        # Keycloak 26.8 infers web origins when the field is omitted on PUT.
        # Carry the exact existing value explicitly, including an empty list.
        body = {key: after[key] for key in ("id", "clientId", "fullScopeAllowed", "attributes", "webOrigins")}
        api.request("PUT", PREFIX + "/clients/" + before["id"], payload=body)
        if api.client(CLIENT) != after:
            raise ValueError("ClientReadbackMismatchReconcileBeforeRetry")
        receipt.update(applied=True, backup=str(backup))
    if any(api.client(name) != prior for name, prior in guards.items()):
        raise ValueError("UnrelatedClientChanged")
    receipt["other_clients_unchanged"] = True
    print(json.dumps(receipt))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Provider exception text/response bodies may contain credentials.
        print(json.dumps({"status": "refused", "error_type": type(error).__name__,
                          "code": str(error) if isinstance(error, ValueError) else "OperationFailed"}))
        raise SystemExit(1)
