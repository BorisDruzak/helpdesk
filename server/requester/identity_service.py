from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

import config as config_module
from app.api.serializers import ticket_to_dict
from app.db.models import (
    Device,
    DeviceAccountSession,
    DeviceRegistrationClaim,
    DeviceUserBinding,
    RegistryAsset,
    RegistryPerson,
    RegistryPersonIdentity,
    Ticket,
)
from app.repos.registration_repo import RegistrationRepo
from app.repos.registry_repo import RegistryRepo
from registry.profile_schema_service import RequesterProfileSchemaService


REQUESTER_PROFILE_REQUIRED_FIELDS: tuple[tuple[str, str], ...] = (
    ("full_name", "ФИО"),
    ("department_id", "Подразделение"),
    ("location_id", "Локация"),
    ("phone", "Телефон или внутренний номер"),
)
REQUESTER_PROFILE_EDITABLE_FIELDS: tuple[str, ...] = (
    "full_name",
    "department_id",
    "location_id",
    "phone",
    "position",
    "workplace_label",
    "preferred_contact_method",
)


class RequesterProfileValidationError(ValueError):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}


def _clean_text(value: object, *, max_length: int = 500) -> str:
    return str(value or "").strip()[:max_length]


def _metadata_value(row: Any, key: str) -> Any:
    metadata = getattr(row, "metadata_json", None)
    return metadata.get(key) if isinstance(metadata, dict) else None


class RequesterIdentityResolver:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.registration_repo = RegistrationRepo(session)
        self.registry_repo = RegistryRepo(session)

    @staticmethod
    def profile_completion_required() -> bool:
        return bool(getattr(config_module, "PROFILE_COMPLETION_REQUIRED", True))

    async def resolve_person_for_web_user(self, actor_id: str) -> RegistryPerson | None:
        login = str(actor_id or "").strip()
        if not login:
            return None
        for provider in ("ui_login", "email", "windows_login", "ad"):
            person = await self.registration_repo.find_person_by_identity(provider, login)
            if person is not None:
                return person
        return None

    async def list_active_bindings(self, person_id: str | None) -> list[DeviceUserBinding]:
        if not person_id:
            return []
        return await self.registration_repo.list_bindings_for_person(person_id, active_only=True)

    async def list_owned_sessions(self, person_id: str | None, binding_ids: list[str]) -> list[DeviceAccountSession]:
        clauses = []
        if person_id:
            clauses.append(DeviceAccountSession.person_id == str(person_id))
        if binding_ids:
            clauses.append(DeviceAccountSession.binding_id.in_(binding_ids))
        if not clauses:
            return []
        result = await self.session.execute(
            select(DeviceAccountSession)
            .where(or_(*clauses))
            .where(DeviceAccountSession.verification_status.in_(["verified", "pending_verification"]))
            .order_by(desc(DeviceAccountSession.created_at))
        )
        return list(result.scalars().all())

    async def list_allowed_devices(self, person_id: str | None) -> list[dict[str, Any]]:
        devices: list[dict[str, Any]] = []
        for binding in await self.list_active_bindings(person_id):
            device = await self.session.get(Device, binding.device_id)
            asset = await self.registry_repo.get_asset_by_device_id(binding.device_id)
            devices.append(self.serialize_device(binding, device, asset))
        return devices

    async def get_device_detail(self, *, actor_id: str, device_id: str) -> dict[str, Any]:
        _person, binding = await self.require_owned_device(actor_id=actor_id, device_id=device_id)
        device = await self.session.get(Device, binding.device_id)
        asset = await self.registry_repo.get_asset_by_device_id(binding.device_id)
        tickets = [
            ticket
            for ticket in await self.list_tickets(actor_id=actor_id, limit=300)
            if str(getattr(ticket, "device_id", "") or "") == binding.device_id
        ]
        open_statuses = {"resolved", "closed", "canceled"}
        detail = self.serialize_device(binding, device, asset)
        detail.update(
            {
                "asset_type": getattr(asset, "asset_type", None),
                "asset_status": getattr(asset, "status", None),
                "department_id": getattr(asset, "department_id", None),
                "location_id": getattr(asset, "location_id", None),
                "last_seen_at": getattr(getattr(device, "last_seen_at", None), "isoformat", lambda: None)()
                or getattr(getattr(asset, "last_seen_at", None), "isoformat", lambda: None)(),
                "open_ticket_count": sum(
                    1 for ticket in tickets if str(getattr(ticket, "status", "") or "") not in open_statuses
                ),
                "available_actions": {
                    "create_ticket": True,
                    "view_tickets": True,
                },
            }
        )
        return {
            "device": detail,
            "recent_tickets": [ticket_to_dict(ticket, visibility="requester") for ticket in tickets[:10]],
        }

    def serialize_person(self, person: RegistryPerson | None, *, profile_schema: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if person is None:
            return None
        metadata = person.metadata_json if isinstance(person.metadata_json, dict) else {}
        schema_service = RequesterProfileSchemaService(self.session)
        return {
            "person_id": person.person_id,
            "display_name": person.display_name,
            "full_name": person.full_name,
            "email": person.email,
            "phone": person.phone,
            "department_id": person.department_id,
            "location_id": person.location_id,
            "status": person.status,
            "position": metadata.get("position"),
            "workplace_label": metadata.get("workplace_label"),
            "preferred_contact_method": metadata.get("preferred_contact_method"),
            "custom_fields": schema_service.profile_custom_fields(metadata, profile_schema),
        }

    def serialize_profile_schema_for_requester(self, profile_schema: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(profile_schema, dict):
            return None
        public_fields: list[dict[str, Any]] = []
        for raw_field in profile_schema.get("fields", []):
            if not isinstance(raw_field, dict):
                continue
            field = {
                "key": raw_field.get("key"),
                "label": raw_field.get("label"),
                "type": raw_field.get("type"),
                "required": bool(raw_field.get("required")),
                "visible": raw_field.get("visible", True) is not False,
                "system": bool(raw_field.get("system")),
                "custom": bool(raw_field.get("custom")),
                "editable": raw_field.get("editable", True) is not False,
                "can_delete": bool(raw_field.get("can_delete")),
                "can_hide": bool(raw_field.get("can_hide")),
                "help_text": raw_field.get("help_text"),
                "validation": raw_field.get("validation") if isinstance(raw_field.get("validation"), dict) else {},
            }
            if isinstance(raw_field.get("options"), list):
                field["options"] = raw_field["options"]
            public_fields.append(field)
        return {
            "schema_key": profile_schema.get("schema_key"),
            "version": profile_schema.get("version"),
            "updated_at": profile_schema.get("updated_at"),
            "updated_by": profile_schema.get("updated_by"),
            "fields": public_fields,
            "custom_fields": [field for field in public_fields if field.get("custom")],
            "required_fields": [
                {"key": field["key"], "label": field["label"]}
                for field in public_fields
                if field.get("visible", True) and field.get("required")
            ],
            "system_fields": list(profile_schema.get("system_fields") or []),
            "editable_optional_fields": list(profile_schema.get("editable_optional_fields") or []),
            "warnings": list(profile_schema.get("warnings") or []),
        }

    def build_profile_completion(
        self,
        person: RegistryPerson | None,
        *,
        profile_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if profile_schema is not None:
            schema_service = RequesterProfileSchemaService(self.session)
            missing = schema_service.completion_missing_fields(person, profile_schema)
            required_fields = [
                {"key": field["key"], "label": field["label"]}
                for field in profile_schema.get("fields", [])
                if isinstance(field, dict) and field.get("visible", True) and field.get("required")
            ]
        else:
            missing = []
            for key, label in REQUESTER_PROFILE_REQUIRED_FIELDS:
                if person is None or not _clean_text(getattr(person, key, None), max_length=500):
                    missing.append({"key": key, "label": label})
            required_fields = [{"key": key, "label": label} for key, label in REQUESTER_PROFILE_REQUIRED_FIELDS]
        complete = not missing
        required = self.profile_completion_required()
        blocked = required and not complete
        return {
            "complete": complete,
            "required": required,
            "status": "complete" if complete else ("required" if required else "optional"),
            "required_fields": required_fields,
            "missing_fields": missing,
            "setup_path": "/app/requester/profile/setup",
            "blocks": {
                "ticket_create": blocked,
                "ticket_preview": blocked,
                "knowledge_requester_actions": blocked,
                "device_binding_confirmation": blocked,
            },
        }

    async def require_profile_complete(self, actor_id: str) -> RegistryPerson:
        person = await self.resolve_person_for_web_user(actor_id)
        profile_schema = await RequesterProfileSchemaService(self.session).get_schema()
        completion = self.build_profile_completion(person, profile_schema=profile_schema)
        if person is None or completion.get("blocks", {}).get("device_binding_confirmation", True):
            raise PermissionError("Заполните профиль, чтобы продолжить работу в кабинете пользователя.")
        return person

    async def update_own_profile(self, *, actor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        actor_login = _clean_text(actor_id, max_length=240)
        if not actor_login:
            raise RequesterProfileValidationError("Не удалось определить пользователя", {"actor": "missing"})

        current = await self.resolve_person_for_web_user(actor_login)
        supplied_person_id = _clean_text(payload.get("person_id"), max_length=80)
        if supplied_person_id and (current is None or supplied_person_id != current.person_id):
            raise PermissionError("Нельзя изменить чужой профиль.")

        full_name = _clean_text(payload.get("full_name"), max_length=240)
        phone = _clean_text(payload.get("phone"), max_length=80)
        department_id = _clean_text(payload.get("department_id"), max_length=80)
        location_id = _clean_text(payload.get("location_id"), max_length=80)
        position = _clean_text(payload.get("position"), max_length=160)
        workplace_label = _clean_text(payload.get("workplace_label"), max_length=160)
        preferred_contact_method = _clean_text(payload.get("preferred_contact_method"), max_length=80)
        schema_service = RequesterProfileSchemaService(self.session)
        profile_schema = await schema_service.get_schema()
        schema_details, custom_values = schema_service.validate_profile_payload(profile_schema, payload)

        details: dict[str, str] = {}
        if not full_name:
            details["full_name"] = "Укажите ФИО."
        if not phone:
            details["phone"] = "Укажите телефон или внутренний номер."
        if not department_id:
            details["department_id"] = "Выберите подразделение из справочника."
        if not location_id:
            details["location_id"] = "Выберите локацию из справочника."
        details.update(schema_details)
        if details:
            raise RequesterProfileValidationError("Заполните обязательные поля профиля.", details)

        department = await self.registry_repo.get_department(department_id)
        if department is None or getattr(department, "status", "active") != "active":
            raise RequesterProfileValidationError(
                "Выберите подразделение из справочника.",
                {"department_id": "Выберите подразделение из справочника."},
            )
        location = await self.registry_repo.get_location(location_id)
        if location is None or getattr(location, "status", "active") != "active":
            raise RequesterProfileValidationError(
                "Выберите локацию из справочника.",
                {"location_id": "Выберите локацию из справочника."},
            )

        now = datetime.now(timezone.utc)
        metadata_patch = {
            "position": position or None,
            "workplace_label": workplace_label or None,
            "preferred_contact_method": preferred_contact_method or None,
            "profile_updated_from": "requester_web",
            "profile_updated_by": actor_login,
            "profile_updated_at": now.isoformat(),
        }
        if custom_values:
            existing_custom: dict[str, Any] = {}
            if current is not None and isinstance(current.metadata_json, dict):
                raw_custom = current.metadata_json.get("profile_custom_fields")
                if isinstance(raw_custom, dict):
                    existing_custom = raw_custom
            metadata_patch["profile_custom_fields"] = {**existing_custom, **custom_values}
        if current is None:
            current = RegistryPerson(
                person_id=str(uuid.uuid4()),
                display_name=full_name,
                full_name=full_name,
                phone=phone,
                email=actor_login if "@" in actor_login else None,
                department_id=department.department_id,
                location_id=location.location_id,
                source="web_profile",
                status="self_reported",
                profile_key=actor_login,
                last_seen_at=now,
                metadata_json=metadata_patch,
            )
            self.session.add(current)
            await self.session.flush()
            await self.registration_repo.create_or_update_person_identity(
                person_id=current.person_id,
                provider="ui_login",
                identifier=actor_login,
                verified=True,
                source="requester_web",
                metadata={"profile_setup": True},
            )
        else:
            metadata = current.metadata_json if isinstance(current.metadata_json, dict) else {}
            current.display_name = full_name
            current.full_name = full_name
            current.phone = phone
            current.department_id = department.department_id
            current.location_id = location.location_id
            current.last_seen_at = now
            current.metadata_json = {**metadata, **metadata_patch}
            await self.registration_repo.create_or_update_person_identity(
                person_id=current.person_id,
                provider="ui_login",
                identifier=actor_login,
                verified=True,
                source="requester_web",
                metadata={"profile_setup": True},
            )
            await self.session.flush()

        return {
            "profile": self.serialize_person(current, profile_schema=profile_schema),
            "profile_completion": self.build_profile_completion(current, profile_schema=profile_schema),
            "profile_policy": {
                "editable": True,
                "editable_fields": [
                    field["key"]
                    for field in profile_schema.get("fields", [])
                    if isinstance(field, dict) and field.get("visible", True) and field.get("editable", True)
                ],
                "change_request_required": False,
            },
            "profile_schema": self.serialize_profile_schema_for_requester(profile_schema),
        }

    async def list_person_identities(self, person_id: str | None) -> list[dict[str, Any]]:
        if not person_id:
            return []
        result = await self.session.execute(
            select(RegistryPersonIdentity)
            .where(RegistryPersonIdentity.person_id == str(person_id))
            .order_by(RegistryPersonIdentity.provider, RegistryPersonIdentity.identifier)
        )
        return [
            {
                "identity_id": identity.identity_id,
                "provider": identity.provider,
                "identifier": identity.identifier,
                "verified": bool(identity.verified),
                "source": identity.source,
                "last_seen_at": identity.last_seen_at.isoformat() if identity.last_seen_at else None,
                "created_at": identity.created_at.isoformat() if identity.created_at else None,
            }
            for identity in result.scalars().all()
        ]

    def serialize_device(
        self,
        binding: DeviceUserBinding,
        device: Device | None,
        asset: RegistryAsset | None,
    ) -> dict[str, Any]:
        return {
            "device_id": binding.device_id,
            "binding_id": binding.binding_id,
            "relationship_type": binding.relationship_type,
            "binding_status": binding.status,
            "hostname": getattr(device, "hostname", None) or getattr(asset, "hostname", None),
            "os": getattr(device, "os", None) or ((getattr(asset, "discovery_payload", None) or {}).get("os") if asset else None),
            "agent_version": getattr(device, "agent_version", None)
            or ((getattr(asset, "discovery_payload", None) or {}).get("agent_version") if asset else None),
            "last_seen_at": getattr(getattr(device, "last_seen_at", None), "isoformat", lambda: None)(),
            "online": False,
            "asset_id": getattr(asset, "asset_id", None),
            "asset_name": getattr(asset, "name", None),
            "asset_type": getattr(asset, "asset_type", None),
            "asset_status": getattr(asset, "status", None),
            "department_id": getattr(asset, "department_id", None),
            "location_id": getattr(asset, "location_id", None),
        }

    async def build_requester_context(
        self,
        *,
        actor_id: str,
        person: RegistryPerson | None,
        binding: DeviceUserBinding | None = None,
        account_mode: str,
    ) -> dict[str, Any]:
        department = await self.registry_repo.get_department(getattr(person, "department_id", None))
        location = await self.registry_repo.get_location(getattr(person, "location_id", None))
        person_metadata = person.metadata_json if person is not None and isinstance(person.metadata_json, dict) else {}
        device = await self.session.get(Device, binding.device_id) if binding is not None else None
        asset = await self.registry_repo.get_asset_by_device_id(binding.device_id) if binding is not None else None
        asset_department = await self.registry_repo.get_department(getattr(asset, "department_id", None))
        asset_location = await self.registry_repo.get_location(getattr(asset, "location_id", None))

        profile = {
            "person_id": getattr(person, "person_id", None),
            "display_name": getattr(person, "display_name", None),
            "full_name": getattr(person, "full_name", None),
            "email": getattr(person, "email", None),
            "phone": getattr(person, "phone", None),
            "department_id": getattr(person, "department_id", None),
            "department": getattr(department, "name", None),
            "department_code": getattr(department, "code", None),
            "location_id": getattr(person, "location_id", None),
            "location": getattr(location, "display_name", None),
            "building": getattr(location, "building", None),
            "floor": getattr(location, "floor", None),
            "room": getattr(location, "room", None),
            "position": person_metadata.get("position"),
            "workplace_label": person_metadata.get("workplace_label"),
            "preferred_contact_method": person_metadata.get("preferred_contact_method"),
        }
        device_context: dict[str, Any] | None = None
        if binding is not None:
            device_label = (
                getattr(device, "hostname", None)
                or getattr(asset, "hostname", None)
                or getattr(asset, "name", None)
                or binding.device_id
            )
            device_context = {
                "device_id": binding.device_id,
                "binding_id": binding.binding_id,
                "relationship_type": binding.relationship_type,
                "binding_status": binding.status,
                "label": device_label,
                "hostname": getattr(device, "hostname", None) or getattr(asset, "hostname", None),
                "os": getattr(device, "os", None) or ((getattr(asset, "discovery_payload", None) or {}).get("os") if asset else None),
                "agent_version": getattr(device, "agent_version", None)
                or ((getattr(asset, "discovery_payload", None) or {}).get("agent_version") if asset else None),
                "asset_id": getattr(asset, "asset_id", None),
                "asset_name": getattr(asset, "name", None),
                "asset_type": getattr(asset, "asset_type", None),
                "asset_status": getattr(asset, "status", None),
                "department_id": getattr(asset, "department_id", None),
                "department": getattr(asset_department, "name", None),
                "location_id": getattr(asset, "location_id", None),
                "location": getattr(asset_location, "display_name", None),
                "service_id": getattr(asset, "service_id", None),
                "responsible_person_id": _metadata_value(asset, "responsible_person_id"),
            }

        account = {
            "account_mode": account_mode,
            "person_id": profile["person_id"],
            "binding_id": binding.binding_id if binding is not None else None,
            "validation": "web_requester_identity_resolved",
            "source": "web_requester_session",
        }
        form_prefill = {
            "requester_name": profile["full_name"] or profile["display_name"],
            "full_name": profile["full_name"] or profile["display_name"],
            "email": profile["email"] or actor_id,
            "phone": profile["phone"],
            "department_id": profile["department_id"],
            "department": profile["department"],
            "department_code": profile["department_code"],
            "location_id": profile["location_id"],
            "location": profile["location"],
            "building": profile["building"],
            "floor": profile["floor"],
            "room": profile["room"],
            "position": profile["position"],
            "workplace_label": profile["workplace_label"],
        }
        if device_context is not None:
            form_prefill.update(
                {
                    "device_id": device_context.get("device_id"),
                    "device": device_context.get("label"),
                    "device_hostname": device_context.get("hostname"),
                    "hostname": device_context.get("hostname"),
                    "asset_id": device_context.get("asset_id"),
                    "asset": device_context.get("asset_name"),
                    "asset_type": device_context.get("asset_type"),
                }
            )
        return {
            "schema": "requester_context_v1",
            "source": "web_requester_identity_resolved",
            "profile": profile,
            "device": device_context,
            "account": account,
            "form_prefill": {key: value for key, value in form_prefill.items() if value not in (None, "")},
            "routing_facts": {
                "person_id": profile["person_id"],
                "department_id": profile["department_id"],
                "department_code": profile["department_code"],
                "location_id": profile["location_id"],
                "device_id": (device_context or {}).get("device_id"),
                "asset_id": (device_context or {}).get("asset_id"),
                "asset_type": (device_context or {}).get("asset_type"),
                "service_id": (device_context or {}).get("service_id"),
                "account_mode": account_mode,
            },
        }

    @staticmethod
    def requester_context_custom_fields(context: dict[str, Any]) -> dict[str, Any]:
        profile = context.get("profile") if isinstance(context.get("profile"), dict) else {}
        device = context.get("device") if isinstance(context.get("device"), dict) else {}
        account = context.get("account") if isinstance(context.get("account"), dict) else {}
        return {
            "requester_context_snapshot": context,
            "requester_department_id": profile.get("department_id"),
            "requester_department_code": profile.get("department_code"),
            "requester_location_id": profile.get("location_id"),
            "requester_position": profile.get("position"),
            "requester_workplace_label": profile.get("workplace_label"),
            "requester_device_id": device.get("device_id"),
            "requester_asset_id": device.get("asset_id"),
            "requester_asset_type": device.get("asset_type"),
            "requester_binding_id": device.get("binding_id") or account.get("binding_id"),
            "requester_account_mode": account.get("account_mode"),
        }

    @staticmethod
    def requester_context_preview(context: dict[str, Any]) -> dict[str, Any]:
        profile = context.get("profile") if isinstance(context.get("profile"), dict) else {}
        device = context.get("device") if isinstance(context.get("device"), dict) else {}
        summary = [
            {"label": "profile", "value": profile.get("full_name") or profile.get("display_name")},
            {"label": "department", "value": profile.get("department")},
            {"label": "location", "value": profile.get("location")},
            {"label": "device", "value": device.get("label")},
        ]
        return {
            "profile": {
                "display_name": profile.get("display_name"),
                "full_name": profile.get("full_name"),
                "phone": profile.get("phone"),
                "department": profile.get("department"),
                "location": profile.get("location"),
                "position": profile.get("position"),
                "workplace_label": profile.get("workplace_label"),
            },
            "device": {
                "device_id": device.get("device_id"),
                "label": device.get("label"),
                "relationship_type": device.get("relationship_type"),
                "asset_name": device.get("asset_name"),
                "asset_type": device.get("asset_type"),
            } if device else None,
            "form_prefill": dict(context.get("form_prefill") or {}),
            "routing_facts": {
                "department_id": profile.get("department_id"),
                "location_id": profile.get("location_id"),
                "device_id": device.get("device_id"),
                "asset_id": device.get("asset_id"),
                "account_mode": (context.get("account") or {}).get("account_mode") if isinstance(context.get("account"), dict) else None,
            },
            "summary": [item for item in summary if item.get("value")],
        }

    async def get_owned_device_ids(self, person_id: str | None) -> set[str]:
        return {binding.device_id for binding in await self.list_active_bindings(person_id)}

    async def require_owned_device(self, *, actor_id: str, device_id: str) -> tuple[RegistryPerson | None, DeviceUserBinding]:
        person = await self.resolve_person_for_web_user(actor_id)
        if person is None:
            raise PermissionError("requester person not found")
        for binding in await self.list_active_bindings(person.person_id):
            if binding.device_id == str(device_id):
                return person, binding
        raise PermissionError("device is not owned by requester")

    async def list_tickets(self, *, actor_id: str, limit: int = 100) -> list[Ticket]:
        person = await self.resolve_person_for_web_user(actor_id)
        bindings = await self.list_active_bindings(person.person_id if person else None)
        binding_ids = [binding.binding_id for binding in bindings]
        sessions = await self.list_owned_sessions(person.person_id if person else None, binding_ids)
        session_ids = [session.session_id for session in sessions]
        clauses = [Ticket.requester_id == str(actor_id)]
        if person is not None:
            clauses.append(Ticket.requester_person_id == person.person_id)
        if binding_ids:
            clauses.append(Ticket.requester_binding_id.in_(binding_ids))
        if session_ids:
            clauses.append(Ticket.requester_account_session_id.in_(session_ids))
        result = await self.session.execute(
            select(Ticket)
            .where(or_(*clauses))
            .order_by(desc(Ticket.created_at))
            .limit(max(1, min(int(limit or 100), 300)))
        )
        return list(result.scalars().all())

    async def get_ticket(self, *, actor_id: str, ticket_id: str) -> Ticket | None:
        tickets = await self.list_tickets(actor_id=actor_id, limit=300)
        for ticket in tickets:
            if ticket.ticket_id == str(ticket_id):
                return ticket
        return None

    async def count_open_tickets(self, *, actor_id: str) -> int:
        tickets = await self.list_tickets(actor_id=actor_id, limit=300)
        return sum(1 for ticket in tickets if str(getattr(ticket, "status", "") or "") not in {"resolved", "closed", "canceled"})

    async def list_pending_claims(self, person_id: str | None) -> list[dict[str, Any]]:
        if not person_id:
            return []
        result = await self.session.execute(
            select(DeviceRegistrationClaim)
            .where(DeviceRegistrationClaim.person_id == str(person_id))
            .where(DeviceRegistrationClaim.status.in_(["self_reported", "pending_user_confirmation", "user_confirmed", "pending_admin_review", "conflict"]))
            .order_by(desc(DeviceRegistrationClaim.submitted_at))
            .limit(50)
        )
        return [
            {
                "claim_id": claim.claim_id,
                "device_id": claim.device_id,
                "status": claim.status,
                "submitted_at": claim.submitted_at.isoformat() if claim.submitted_at else None,
            }
            for claim in result.scalars().all()
        ]

    async def build_bootstrap(self, *, actor_id: str) -> dict[str, Any]:
        person = await self.resolve_person_for_web_user(actor_id)
        profile_schema = await RequesterProfileSchemaService(self.session).get_schema()
        profile_completion = self.build_profile_completion(person, profile_schema=profile_schema)
        devices = await self.list_allowed_devices(person.person_id if person else None)
        requester_context = await self.build_requester_context(
            actor_id=actor_id,
            person=person,
            account_mode="browser_no_device",
        )
        tickets = await self.list_tickets(actor_id=actor_id, limit=25)
        blocks = profile_completion.get("blocks") if isinstance(profile_completion.get("blocks"), dict) else {}
        ticket_create_allowed = not bool(blocks.get("ticket_create", not profile_completion["complete"]))
        ticket_preview_allowed = not bool(blocks.get("ticket_preview", not profile_completion["complete"]))
        return {
            "workspace": "requester",
            "profile": self.serialize_person(person, profile_schema=profile_schema),
            "profile_schema": self.serialize_profile_schema_for_requester(profile_schema),
            "profile_completion": profile_completion,
            "requester_context": self.requester_context_preview(requester_context),
            "devices": devices,
            "active_bindings": [
                {
                    "binding_id": device["binding_id"],
                    "device_id": device["device_id"],
                    "relationship_type": device["relationship_type"],
                    "status": device["binding_status"],
                }
                for device in devices
            ],
            "pending_registration_claims": await self.list_pending_claims(person.person_id if person else None),
            "open_ticket_count": sum(1 for ticket in tickets if str(getattr(ticket, "status", "") or "") not in {"resolved", "closed", "canceled"}),
            "tickets_requiring_user_action_count": sum(
                1 for ticket in tickets if str(getattr(ticket, "next_action_owner", "") or "") == "requester"
            ),
            "pending_consent_count": 0,
            "recent_tickets": [ticket_to_dict(ticket, visibility="requester") for ticket in tickets[:10]],
            "feature_flags": {
                "requester_ticket_create": ticket_create_allowed,
                "requester_owned_device_create": ticket_create_allowed,
                "requester_no_device_create": ticket_create_allowed and ticket_preview_allowed,
            },
            "policies": {"device_selection_required": False},
        }

    async def build_profile(self, *, actor_id: str) -> dict[str, Any]:
        person = await self.resolve_person_for_web_user(actor_id)
        profile_schema = await RequesterProfileSchemaService(self.session).get_schema()
        person_id = person.person_id if person else None
        devices = await self.list_allowed_devices(person_id)
        requester_context = await self.build_requester_context(
            actor_id=actor_id,
            person=person,
            account_mode="browser_no_device",
        )
        return {
            "profile": self.serialize_person(person, profile_schema=profile_schema),
            "requester_context": self.requester_context_preview(requester_context),
            "identities": await self.list_person_identities(person_id),
            "devices": devices,
            "active_bindings": [
                {
                    "binding_id": device["binding_id"],
                    "device_id": device["device_id"],
                    "relationship_type": device["relationship_type"],
                    "status": device["binding_status"],
                }
                for device in devices
            ],
            "pending_registration_claims": await self.list_pending_claims(person_id),
            "profile_policy": {
                "editable": True,
                "editable_fields": [
                    field["key"]
                    for field in profile_schema.get("fields", [])
                    if isinstance(field, dict) and field.get("visible", True) and field.get("editable", True)
                ],
                "change_request_required": False,
            },
            "profile_schema": self.serialize_profile_schema_for_requester(profile_schema),
            "profile_completion": self.build_profile_completion(person, profile_schema=profile_schema),
        }
