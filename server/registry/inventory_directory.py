"""Read the web_ovpn inventory projection without granting device access."""

from __future__ import annotations

import json
import os
import ssl
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

import aiohttp
from pydantic import AwareDatetime, BaseModel, Field, StringConstraints, ValidationError, model_validator

MAX_RESPONSE_BYTES = 1024 * 1024
PEOPLE_PATH = "/api/internal/helpdesk/v1/inventory/people"
Label = Annotated[str, StringConstraints(max_length=255)]


class InventoryUnavailable(RuntimeError):
    pass


class InventoryPersonMissing(InventoryUnavailable):
    pass


class RegistrationEmployee(BaseModel):
    full_name: Label
    department: Label
    has_agent: bool


class RegistrationPeople(BaseModel):
    people: list[RegistrationEmployee] = Field(max_length=5)
    refine: bool = False


class Assignment(BaseModel):
    inventory_asset_id: UUID
    assignment_id: UUID
    role: Literal["primary", "shared"]
    assigned_at: AwareDatetime
    name: Label | None = None
    inventory_number: Label | None = None
    os_name: Label | None = None
    endpoint_binding_state: Literal["confirmed", "review", "unbound"]
    endpoint_binding_id: UUID | None = None
    endpoint_binding_updated_at: AwareDatetime | None = None
    endpoint_device_id: UUID | None = None
    endpoint_status: Literal["online", "offline", "unknown", "not_detected"]
    last_seen_at: AwareDatetime | None = None
    agent_version: Label | None = None

    @model_validator(mode="after")
    def validate_binding(self):
        if self.endpoint_binding_state == "confirmed":
            if not self.endpoint_device_id or not self.endpoint_binding_id or self.endpoint_status == "not_detected":
                raise ValueError("Incomplete confirmed binding")
        elif self.endpoint_device_id or self.endpoint_binding_id or self.endpoint_status in {"online", "offline"}:
            raise ValueError("Unconfirmed binding contains a device identity")
        return self


class InventoryProfile(BaseModel):
    inventory_person_id: UUID
    full_name: Label
    department: Label
    profile_updated_at: AwareDatetime
    observed_at: AwareDatetime
    assignments: list[Assignment] = Field(max_length=1000)

    @model_validator(mode="after")
    def validate_unique_assignments(self):
        for key in ("inventory_asset_id", "assignment_id", "endpoint_device_id"):
            keys = [getattr(row, key) for row in self.assignments if getattr(row, key) is not None]
            if len(keys) != len(set(keys)):
                raise ValueError("Duplicate inventory assignment")
        return self


def decode_snapshot(raw: bytes, person_id: UUID) -> InventoryProfile:
    try:
        profile = InventoryProfile.model_validate_json(raw)
    except ValidationError:
        raise InventoryUnavailable("Inventory returned an invalid profile") from None
    if profile.inventory_person_id != person_id:
        raise InventoryUnavailable("Inventory returned a different employee")
    return profile


def decode_response(status: int, raw: bytes, person_id: UUID) -> InventoryProfile:
    if status == 200:
        return decode_snapshot(raw, person_id)
    if status == 404:
        try:
            data = json.loads(raw)
        except ValueError:
            data = None
        detail = data.get("detail") if isinstance(data, dict) else None
        if isinstance(detail, dict) and detail.get("code") == "inventory_person_not_found":
            raise InventoryPersonMissing("Inventory employee does not exist")
    raise InventoryUnavailable("Inventory service did not return a profile")


def display_assignments(profile: InventoryProfile, *, stale: bool) -> list[dict]:
    assignments = [row.model_dump(mode="json") for row in profile.assignments]
    if stale:
        for row in assignments:
            row["endpoint_status"] = "unknown"
    return assignments


def inventory_enabled() -> bool:
    return bool(os.getenv("HELPDESK_INVENTORY_BASE_URL", "").strip())


def registration_search_enabled() -> bool:
    return inventory_enabled() and os.getenv("HELPDESK_INVENTORY_REGISTRATION_SEARCH_ENABLED") == "true"


async def fetch_person(person_id: UUID) -> InventoryProfile:
    status, raw = await _read_people(f"/{person_id}")
    return decode_response(status, raw, person_id)


async def search_registration_people(query: str) -> RegistrationPeople:
    status, raw = await _read_people("/registration-search", params={"q": query})
    if status != 200:
        raise InventoryUnavailable("Inventory registration search is unavailable")
    try:
        return RegistrationPeople.model_validate_json(raw)
    except ValidationError:
        raise InventoryUnavailable("Inventory returned invalid registration matches") from None


async def _read_people(path: str, *, params: dict[str, str] | None = None) -> tuple[int, bytes]:
    """Send the credential only to the configured verified HTTPS origin."""
    base = os.getenv("HELPDESK_INVENTORY_BASE_URL", "").strip()
    token_file = os.getenv("HELPDESK_INVENTORY_TOKEN_FILE", "").strip()
    ca_file = os.getenv("HELPDESK_INVENTORY_CA_FILE", "").strip()
    try:
        origin = urlsplit(base)
        if (origin.scheme != "https" or not origin.hostname or origin.username is not None
                or origin.path not in {"", "/"} or origin.query or origin.fragment or not token_file):
            raise InventoryUnavailable("Inventory HTTPS origin or credential is not configured")
        with Path(token_file).open(encoding="ascii") as handle:
            token = handle.read(4097).strip()
        if not 32 <= len(token) <= 4096 or not token.isprintable() or any(ch.isspace() for ch in token):
            raise InventoryUnavailable("Inventory service credential is invalid")
        ssl_context = ssl.create_default_context(cafile=ca_file or None)
        endpoint = f"{base.rstrip('/')}{PEOPLE_PATH}{path}"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=4)) as http:
            async with http.get(endpoint, params=params,
                                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                                ssl=ssl_context, allow_redirects=False) as response:
                if response.status not in {200, 404} or response.content_type != "application/json":
                    raise InventoryUnavailable("Inventory service did not return a profile")
                raw = bytearray()
                async for chunk in response.content.iter_chunked(64 * 1024):
                    raw.extend(chunk)
                    if len(raw) > MAX_RESPONSE_BYTES:
                        raise InventoryUnavailable("Inventory response exceeded its size limit")
                return response.status, bytes(raw)
    except (OSError, ValueError, aiohttp.ClientError, TimeoutError):
        raise InventoryUnavailable("Inventory service unavailable") from None
