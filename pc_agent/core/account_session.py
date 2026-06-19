from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import uuid
from typing import Any

from pc_agent.core.runtime_paths import resolve_data_root


ACCOUNT_SESSION_SCHEMA_VERSION = 1
ACCOUNT_SESSION_MODES = {"confirmed_binding", "registration_pending", "verified_other_account"}
ACCOUNT_SESSION_STORAGE_MODES = ACCOUNT_SESSION_MODES | {"pending_other_account_request"}
ACCOUNT_SESSION_INVALID_ERROR_CODES = {
    "ACCOUNT_SESSION_REQUIRED",
    "ACCOUNT_SESSION_MISSING",
    "ACCOUNT_SESSION_INVALID",
    "ACCOUNT_SESSION_NOT_FOUND",
    "ACCOUNT_SESSION_REVOKED",
    "ACCOUNT_SESSION_EXPIRED",
    "ACCOUNT_SESSION_TOKEN_REQUIRED",
    "ACCOUNT_SESSION_TOKEN_INVALID",
    "ACCOUNT_SESSION_BINDING_INACTIVE",
    "ACCOUNT_SESSION_BASE_BINDING_INACTIVE",
    "ACCOUNT_SESSION_CLAIM_INACTIVE",
    "ACCOUNT_SESSION_PERSON_INACTIVE",
}
ACCOUNT_SESSION_REFRESH_ERROR_CODES = {"ACCOUNT_SESSION_CLAIM_APPROVED"}
ACCOUNT_SESSION_ACCESS_ERROR_CODES = {"ACCOUNT_ACCESS_DENIED"}
SESSION_FIELDS = {
    "schema_version",
    "account_session_id",
    "session_token",
    "device_id",
    "account_mode",
    "person_id",
    "binding_id",
    "display_name",
    "full_name",
    "login",
    "email",
    "phone",
    "reason",
    "registration_status",
    "verification_status",
    "verification_method",
    "expires_at",
    "other_account",
    "base_binding_id",
    "base_person_id",
    "base_display_name",
    "pending_login_request_id",
    "pending_login_request_status",
    "pending_login_requested_at",
    "pending_login_rejection_reason",
    "created_from_other_account",
    "logged_in_at",
    "last_seen_at",
    "metadata",
}


def _clean(value: Any, *, max_length: int = 300) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if "<script" in text.lower() or "</" in text.lower():
        return ""
    return text[:max_length]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_text(*values: Any) -> str | None:
    for value in values:
        text = _clean(value)
        if text:
            return text
    return None


def account_session_error_code(error: Any) -> str | None:
    if isinstance(error, dict):
        for key in ("error_code", "code"):
            value = _clean(error.get(key), max_length=120)
            if value:
                return value
        data = error.get("data")
        if isinstance(data, dict):
            value = account_session_error_code(data)
            if value:
                return value
        body = error.get("body")
        if isinstance(body, str):
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                payload = {}
            value = account_session_error_code(payload)
            if value:
                return value
    text = str(error or "")
    match = re.search(
        r"(ACCOUNT_SESSION_[A-Z_]+|ACCOUNT_ACCESS_DENIED)",
        text,
    )
    return match.group(1) if match else None


def account_session_error_action(error: Any) -> str:
    code = account_session_error_code(error)
    if code in ACCOUNT_SESSION_INVALID_ERROR_CODES:
        return "clear_session"
    if code in ACCOUNT_SESSION_REFRESH_ERROR_CODES:
        return "refresh_account_state"
    if code in ACCOUNT_SESSION_ACCESS_ERROR_CODES:
        return "deny_access"
    return "ignore"


@dataclass
class AccountSessionManager:
    data_root: Path | None = None

    @property
    def path(self) -> Path:
        root = self.data_root or resolve_data_root()
        return root / "account_session.json"

    def load(self) -> dict[str, Any]:
        path = self.path
        if not path.exists():
            return {"schema_version": ACCOUNT_SESSION_SCHEMA_VERSION, "account_mode": "none"}
        try:
            with path.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return {"schema_version": ACCOUNT_SESSION_SCHEMA_VERSION, "account_mode": "none"}
        if not isinstance(payload, dict):
            return {"schema_version": ACCOUNT_SESSION_SCHEMA_VERSION, "account_mode": "none"}
        return self.sanitize(payload)

    def save(self, session: dict[str, Any]) -> dict[str, Any]:
        sanitized = self.sanitize(session)
        path = self.path
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".json.tmp")
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(sanitized, fh, ensure_ascii=False, indent=2, sort_keys=True)
        tmp_path.replace(path)
        return sanitized

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            return

    def is_logged_in(self) -> bool:
        session = self.load()
        return session.get("account_mode") in ACCOUNT_SESSION_MODES and bool(session.get("account_session_id"))

    def sanitize(self, session: dict[str, Any] | None) -> dict[str, Any]:
        session = session or {}
        mode = str(session.get("account_mode") or "none").strip()
        if mode not in ACCOUNT_SESSION_STORAGE_MODES:
            mode = "none"
        result: dict[str, Any] = {"schema_version": ACCOUNT_SESSION_SCHEMA_VERSION, "account_mode": mode}
        if mode == "none":
            return result
        if mode in ACCOUNT_SESSION_MODES:
            result["account_session_id"] = _clean(session.get("account_session_id"), max_length=80) or str(uuid.uuid4())
        for key in SESSION_FIELDS:
            if key in {"schema_version", "account_session_id", "account_mode", "metadata"}:
                continue
            if key in {"other_account", "created_from_other_account"}:
                result[key] = bool(session.get(key))
                continue
            if key not in session:
                continue
            limit = 320 if key == "email" else 300
            if key in {"reason", "pending_login_rejection_reason"}:
                limit = 500
            value = _clean(session.get(key), max_length=limit)
            if value:
                result[key] = value
        if result.get("email"):
            result["email"] = str(result["email"]).lower()
            if "@" not in result["email"]:
                result.pop("email", None)
        result["other_account"] = bool(result.get("other_account") or mode == "verified_other_account")
        result["created_from_other_account"] = bool(
            result.get("created_from_other_account") or mode == "verified_other_account"
        )
        result.setdefault("logged_in_at", _now_iso())
        result["last_seen_at"] = _now_iso()
        metadata = session.get("metadata") if isinstance(session.get("metadata"), dict) else {}
        result["metadata"] = {
            str(key): _clean(value, max_length=500)
            for key, value in metadata.items()
            if str(key or "").strip()
        }
        return result

    def build_confirmed_binding_session(self, account: dict[str, Any], *, device_id: str) -> dict[str, Any]:
        person = _dict(account.get("person"))
        return self.sanitize(
            {
                "device_id": device_id,
                "account_session_id": account.get("session_id") or account.get("account_session_id"),
                "session_token": account.get("session_token"),
                "account_mode": "confirmed_binding",
                "person_id": account.get("person_id") or person.get("person_id"),
                "binding_id": account.get("binding_id"),
                "display_name": _first_text(account.get("display_name"), person.get("display_name"), account.get("full_name"), person.get("full_name")),
                "full_name": _first_text(account.get("full_name"), person.get("full_name")),
                "login": _first_text(account.get("login"), person.get("login")),
                "email": _first_text(account.get("email"), person.get("email")),
                "phone": _first_text(account.get("phone"), person.get("phone")),
                "registration_status": account.get("registration_status") or "admin_confirmed",
                "verification_status": account.get("verification_status") or "verified",
                "verification_method": account.get("verification_method") or "device_binding",
                "expires_at": account.get("expires_at"),
                "other_account": False,
                "created_from_other_account": False,
            }
        )

    def build_registration_pending_session(
        self,
        profile: dict[str, Any],
        registration: dict[str, Any],
        *,
        device_id: str,
        server_session: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        server_session = server_session or {}
        claim_id = registration.get("claim_id") or registration.get("pending_claim_id")
        return self.sanitize(
            {
                "device_id": device_id,
                "account_session_id": server_session.get("session_id") or server_session.get("account_session_id"),
                "session_token": server_session.get("session_token"),
                "account_mode": "registration_pending",
                "person_id": server_session.get("person_id") or registration.get("person_id"),
                "display_name": profile.get("display_name") or profile.get("full_name") or profile.get("login"),
                "full_name": profile.get("full_name"),
                "login": profile.get("login"),
                "email": profile.get("email"),
                "registration_status": registration.get("status") or "registration_pending",
                "verification_status": server_session.get("verification_status") or "pending_verification",
                "verification_method": server_session.get("verification_method") or "registration_claim",
                "expires_at": server_session.get("expires_at"),
                "metadata": {"claim_id": claim_id} if claim_id else {},
            }
        )

    def build_verified_other_account_session(
        self,
        profile: dict[str, Any],
        server_session: dict[str, Any] | None,
        *,
        device_id: str,
    ) -> dict[str, Any]:
        server_session = server_session or {}
        declared = server_session.get("declared_account") if isinstance(server_session.get("declared_account"), dict) else {}
        base_account = {
            **declared,
            **profile,
        }
        return self.sanitize(
            {
                "device_id": device_id,
                "account_session_id": server_session.get("session_id") or server_session.get("account_session_id"),
                "session_token": server_session.get("session_token"),
                "account_mode": "verified_other_account",
                "display_name": base_account.get("display_name") or base_account.get("full_name") or base_account.get("login"),
                "full_name": base_account.get("full_name"),
                "login": base_account.get("login"),
                "email": base_account.get("email"),
                "phone": base_account.get("phone"),
                "reason": base_account.get("reason") or server_session.get("reason"),
                "registration_status": "other_account",
                "verification_status": server_session.get("verification_status") or "verified",
                "verification_method": server_session.get("verification_method") or "admin_approval",
                "expires_at": server_session.get("expires_at"),
                "other_account": True,
                "created_from_other_account": True,
                "base_binding_id": server_session.get("base_binding_id") or server_session.get("binding_id"),
                "base_person_id": server_session.get("base_person_id") or server_session.get("person_id"),
                "base_display_name": server_session.get("base_display_name") or server_session.get("display_name") or server_session.get("full_name"),
                "metadata": {
                    "verification_status": server_session.get("verification_status"),
                    "verification_method": server_session.get("verification_method"),
                },
            }
        )

    def build_pending_other_account_request_session(
        self,
        profile: dict[str, Any],
        request: dict[str, Any],
        *,
        device_id: str,
    ) -> dict[str, Any]:
        requested = request.get("requested_account") if isinstance(request.get("requested_account"), dict) else {}
        base = {**requested, **(profile or {})}
        return self.sanitize(
            {
                "device_id": device_id,
                "account_mode": "pending_other_account_request",
                "display_name": base.get("display_name") or base.get("full_name") or base.get("login"),
                "full_name": base.get("full_name"),
                "login": base.get("login"),
                "email": base.get("email"),
                "phone": base.get("phone"),
                "reason": base.get("reason") or request.get("reason"),
                "pending_login_request_id": request.get("request_id"),
                "pending_login_request_status": request.get("status") or "pending_verification",
                "pending_login_requested_at": request.get("requested_at"),
                "pending_login_rejection_reason": request.get("rejection_reason"),
                "metadata": {"pending_other_account_request": "true"},
            }
        )

    def build_other_account_session(
        self,
        profile: dict[str, Any],
        active_account: dict[str, Any] | None,
        *,
        device_id: str,
    ) -> dict[str, Any]:
        active_account = active_account or {}
        return self.sanitize(
            {
                "device_id": device_id,
                "account_mode": "verified_other_account",
                "display_name": profile.get("display_name") or profile.get("full_name") or profile.get("login"),
                "full_name": profile.get("full_name"),
                "login": profile.get("login"),
                "email": profile.get("email"),
                "phone": profile.get("phone"),
                "reason": profile.get("reason"),
                "registration_status": "other_account",
                "other_account": True,
                "created_from_other_account": True,
                "base_binding_id": active_account.get("binding_id"),
                "base_person_id": active_account.get("person_id"),
                "base_display_name": active_account.get("display_name") or active_account.get("full_name"),
                "metadata": {"legacy_local_other_account": "true"},
            }
        )

    def enrich_from_account_state(self, session: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        sanitized = self.sanitize(session)
        mode = str(sanitized.get("account_mode") or "")
        accounts = [item for item in (state or {}).get("accounts") or [] if isinstance(item, dict)]
        match: dict[str, Any] | None = None
        if mode == "confirmed_binding":
            binding_id = str(sanitized.get("binding_id") or "")
            match = next(
                (
                    item
                    for item in accounts
                    if item.get("account_mode") == "confirmed_binding" and str(item.get("binding_id") or "") == binding_id
                ),
                None,
            )
        elif mode == "verified_other_account":
            session_id = str(sanitized.get("account_session_id") or "")
            match = next(
                (
                    item
                    for item in accounts
                    if item.get("account_mode") == "verified_other_account" and str(item.get("session_id") or "") == session_id
                ),
                None,
            )
        if not match:
            return sanitized
        merged = dict(sanitized)
        for key in (
            "person_id",
            "binding_id",
            "display_name",
            "full_name",
            "login",
            "email",
            "phone",
            "reason",
            "base_binding_id",
            "base_person_id",
            "base_display_name",
        ):
            if match.get(key):
                merged[key] = match.get(key)
        if not merged.get("display_name"):
            merged["display_name"] = _first_text(merged.get("full_name"), merged.get("login"))
        return self.sanitize(merged)

    def matches_account_state(self, session: dict[str, Any], state: dict[str, Any]) -> bool:
        sanitized = self.sanitize(session)
        mode = str(sanitized.get("account_mode") or "")
        if mode not in ACCOUNT_SESSION_MODES:
            return False
        if mode == "registration_pending":
            session_id = str(sanitized.get("account_session_id") or "")
            if not session_id:
                return False
            server_sessions = [item for item in (state or {}).get("server_sessions") or [] if isinstance(item, dict)]
            return any(
                item.get("account_mode") == "registration_pending"
                and item.get("verification_status") == "pending_verification"
                and str(item.get("session_id") or "") == session_id
                for item in server_sessions
            )
        session_id = str(sanitized.get("account_session_id") or "")
        if not session_id:
            return False
        accounts = [item for item in (state or {}).get("accounts") or [] if isinstance(item, dict)]
        server_sessions = [item for item in (state or {}).get("server_sessions") or [] if isinstance(item, dict)]
        if mode == "confirmed_binding":
            binding_id = str(sanitized.get("binding_id") or "")
            return any(
                item.get("account_mode") == "confirmed_binding"
                and item.get("verification_status") == "verified"
                and str(item.get("session_id") or "") == session_id
                and str(item.get("binding_id") or "") == binding_id
                for item in server_sessions + accounts
            )
        if mode == "verified_other_account":
            return any(
                item.get("account_mode") == "verified_other_account"
                and item.get("verification_status") == "verified"
                and str(item.get("session_id") or "") == session_id
                for item in accounts + server_sessions
            )
        return False
