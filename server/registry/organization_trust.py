"""Field-level provenance in existing Registry metadata; never infer trust from login."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

TRUST_KEY = "organization_context_v1"
ORGANIZATION_FIELDS = {"department_id", "location_id", "manager_person_id"}


def _value(row: Any, key: str) -> Any:
    if key == "manager_person_id":
        return (getattr(row, "metadata_json", None) or {}).get(key)
    return getattr(row, key, None)


def _records(row: Any) -> dict[str, Any]:
    raw_metadata = getattr(row, "metadata_json", None)
    metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
    trust = metadata.get(TRUST_KEY)
    return deepcopy(trust["fields"]) if isinstance(trust, dict) and trust.get("version") == 1 and isinstance(trust.get("fields"), dict) else {}


def _store(row: Any, fields: dict[str, Any]) -> None:
    row.metadata_json = {**(row.metadata_json or {}), TRUST_KEY: {"version": 1, "fields": fields}}


def field_trust(row: Any, key: str) -> dict[str, Any]:
    metadata = getattr(row, "metadata_json", None) or {}
    if TRUST_KEY in metadata:
        trust = metadata[TRUST_KEY]
        if not isinstance(trust, dict) or trust.get("version") != 1 or not isinstance(trust.get("fields"), dict):
            return {"state": "invalid_provenance", "value": _value(row, key)}
    record = _records(row).get(key)
    if not isinstance(record, dict):
        return {"state": "legacy_unknown", "value": _value(row, key)}
    return record


def organization_value(row: Any, key: str, *, allow_legacy: bool = False) -> Any:
    if row is None:
        return None
    record = field_trust(row, key)
    if record.get("state") != "confirmed" and not (allow_legacy and record.get("state") == "legacy_unknown"):
        return None
    # Bypass writers, imports and stale metadata cannot confer a different value.
    return record.get("value") if record.get("value") == _value(row, key) else None


def confirm_fields(row: Any, keys: list[str], *, actor_id: str) -> None:
    records = _records(row)
    for key in keys:
        if key not in ORGANIZATION_FIELDS:
            raise ValueError("Неподдерживаемое организационное поле.")
        records[key] = {"state": "confirmed", "value": _value(row, key), "source": "registry_admin",
                        "reviewed_by": actor_id, "reviewed_at": datetime.now(timezone.utc).isoformat()}
        if key == "manager_person_id":
            records[key]["department_id"] = getattr(row, "department_id", None)
    _store(row, records)


def propose_fields(row: Any, values: dict[str, Any], *, actor_id: str) -> dict[str, dict[str, Any]]:
    records = _records(row)
    proposals = {}
    for key, value in values.items():
        if key not in {"department_id", "location_id"}:
            raise ValueError("Неподдерживаемое предложение изменения.")
        old = _value(row, key)
        record = field_trust(row, key)
        if value == old:
            records.setdefault(key, record)
            continue
        if old is None or record.get("state") == "self_reported":
            setattr(row, key, value)
            records[key] = {"state": "self_reported", "value": value, "source": "requester_web",
                            "submitted_by": actor_id, "submitted_at": datetime.now(timezone.utc).isoformat()}
        else:
            pending = {"proposal_id": str(uuid4()), "value": value, "base_value": old,
                       "submitted_by": actor_id, "submitted_at": datetime.now(timezone.utc).isoformat()}
            records[key] = {**record, "pending": pending}
            proposals[key] = pending
    _store(row, records)
    return proposals


def decide_proposal(row: Any, key: str, proposal_id: str, *, approve: bool, actor_id: str) -> None:
    record = field_trust(row, key)
    pending = record.get("pending") or {}
    if key not in {"department_id", "location_id"} or not proposal_id or pending.get("proposal_id") != proposal_id:
        raise ValueError("Предложение отсутствует или уже рассмотрено. Обновите данные.")
    if pending.get("base_value") != _value(row, key):
        raise ValueError("Организационные сведения изменились. Обновите данные.")
    records = _records(row)
    if approve:
        setattr(row, key, pending["value"])
        confirm_fields(row, [key], actor_id=actor_id)
        records = _records(row)
    else:
        records[key] = {k: v for k, v in record.items() if k != "pending"}
    records[key]["last_decision"] = {"proposal_id": proposal_id, "decision": "approved" if approve else "rejected",
                                     "reviewed_by": actor_id, "reviewed_at": datetime.now(timezone.utc).isoformat()}
    _store(row, records)


def public_organization_status(row: Any) -> dict[str, dict[str, Any]]:
    if row is None:
        return {}
    # Requester projection contains only their field values/states, no admin metadata.
    return {key: {"state": field_trust(row, key).get("state", "legacy_unknown"),
                  "pending_value": (field_trust(row, key).get("pending") or {}).get("value")}
            for key in ("department_id", "location_id")}
