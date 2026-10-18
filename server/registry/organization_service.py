from __future__ import annotations

from typing import Any
from sqlalchemy import select

from app.db.models import RegistryDepartment, RegistryLocation, RegistryPerson
from registry.admin_operations_service import RegistryAdminOperationsService
from registry.organization_trust import decide_proposal, field_trust


async def organization_trust_impact(session: Any) -> dict[str, Any]:
    people = (await session.scalars(select(RegistryPerson).where(RegistryPerson.status.in_(["active", "self_reported"])))).all()
    counts = {"legacy_people": 0, "self_reported_people": 0, "pending_people": 0}
    for person in people:
        fields = [field_trust(person, key) for key in ("department_id", "location_id")]
        counts["legacy_people"] += int(any(field.get("state") == "legacy_unknown" and field.get("value") for field in fields))
        counts["self_reported_people"] += int(any(field.get("state") == "self_reported" and field.get("value") for field in fields))
        counts["pending_people"] += int(any(field.get("pending") for field in fields))
    return {"counts": counts, "read_only": True, "strict_legacy_default": False,
            "affected_functions": ["department_scoped_audiences", "location_scoped_audiences"],
            "message": "В строгом режиме исторические неподтверждённые сведения перестанут определять доступность ограниченных материалов и услуг. Публичные услуги и обычные обращения сохраняются."}


async def review_organization_proposal(session: Any, person: Any, review: Any, *, actor_id: str, reason: str | None) -> None:
    if not isinstance(review, dict) or review.get("decision") not in {"approve", "reject"} or not reason:
        raise ValueError("Укажите решение и причину рассмотрения организационного изменения.")
    key = review.get("field")
    if key not in {"department_id", "location_id"}:
        raise ValueError("Неподдерживаемое организационное поле.")
    pending = field_trust(person, key).get("pending") or {}
    approve = review["decision"] == "approve"
    if approve:
        model = RegistryDepartment if key == "department_id" else RegistryLocation
        target = await session.get(model, pending.get("value")) if pending.get("value") else None
        if target is None or target.status != "active":
            raise ValueError("Предложенное значение отсутствует или архивировано.")
    decide_proposal(person, key, str(review.get("proposal_id") or ""), approve=approve, actor_id=actor_id)
    await RegistryAdminOperationsService(session).append_event(
        object_type="person", object_id=person.person_id,
        event_type="organization_proposal_approved" if approve else "organization_proposal_rejected",
        actor_id=actor_id, actor_role="admin", related_person_id=person.person_id, reason=reason,
        payload={"field": key, "proposal_id": pending.get("proposal_id"), "before": pending.get("base_value"), "proposed": pending.get("value")},
    )
