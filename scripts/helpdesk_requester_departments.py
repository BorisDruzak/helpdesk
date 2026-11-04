"""Names-only requester department publication; caller owns backup and staging transport."""
import hashlib
import json
from pathlib import Path


def load_department_names():
    data = json.loads((Path(__file__).resolve().parents[1] / "server/registry/requester_departments_20260831.json").read_text(encoding="utf-8"))
    names = data["departments"]
    if len(names) != 30 or len({name.casefold() for name in names}) != 30 or any(not isinstance(name, str) or not name.strip() for name in names):
        raise ValueError("Invalid names-only department catalog")
    return names


def require_database(database, *, isolated_test=False):
    if isolated_test:
        if not database.startswith("pc_support_test_") or database.startswith("pc_support_test_template") or database == "pc_support_test_":
            raise ValueError("Isolated per-run test database required")
    elif database != "helpdesk_staging_db":
        raise ValueError("Helpdesk staging database required")


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


async def publish_department_catalog(session_factory, auth, *, synthetic_departments, synthetic_locations,
                                     apply=False, expected_fingerprint=None, isolated_test=False):
    from sqlalchemy import select, text
    from app.db.models import RegistryDepartment, RegistryLocation
    from registry.admin_operations_service import RegistryAdminOperationsService
    if auth.actor_role != "admin" or not auth.actor_id:
        raise PermissionError("Explicit administrator actor required")
    names = load_department_names()
    async with session_factory() as session:
        async with session.begin():
            require_database(await session.scalar(text("SELECT current_database()")), isolated_test=isolated_test)
            if apply:
                await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": 611042026})
            dq, lq = select(RegistryDepartment).order_by(RegistryDepartment.department_id), select(RegistryLocation).order_by(RegistryLocation.location_id)
            if apply:
                dq, lq = dq.with_for_update(), lq.with_for_update()
            departments = list(await session.scalars(dq))
            locations = list(await session.scalars(lq))
            state = {"departments": [{"id": row.department_id, "name": row.name, "code": row.code, "status": row.status} for row in departments],
                     "locations": [{"id": row.location_id, "name": row.display_name, "status": row.status} for row in locations]}
            state_fingerprint = fingerprint(state)
            if apply and expected_fingerprint != state_fingerprint:
                raise ValueError("Department catalog changed since reviewed plan")
            by_department = {row.department_id: row for row in departments}
            by_location = {row.location_id: row for row in locations}
            for candidates, rows, attribute in ((synthetic_departments, by_department, "name"), (synthetic_locations, by_location, "display_name")):
                for identifier, expected_name in candidates.items():
                    row = rows.get(identifier)
                    if row is None or getattr(row, attribute) != expected_name or not (
                        expected_name.startswith("Synthetic ") or expected_name.startswith("Guided Studio synthetic staging ")
                        or expected_name.startswith("Readiness 8989 Test ")):
                        raise ValueError("Exact synthetic catalog record required")
            existing = {}
            for row in departments:
                if row.department_id not in synthetic_departments and row.status == "active":
                    existing.setdefault(row.name.casefold(), []).append(row)
            if any(len(rows) > 1 for name, rows in existing.items() if name in {item.casefold() for item in names}):
                raise ValueError("Existing real department duplicates need explicit reconciliation")
            create = [name for name in names if name.casefold() not in existing]
            archive_departments = [identifier for identifier in synthetic_departments if by_department[identifier].status == "active"]
            archive_locations = [identifier for identifier in synthetic_locations if by_location[identifier].status == "active"]
            result = {"fingerprint": state_fingerprint, "create": create, "archive_departments": archive_departments,
                      "archive_locations": archive_locations, "applied": False, "department_count": len(names)}
            if apply:
                service = RegistryAdminOperationsService(session)
                reason = "Employee onboarding: replace synthetic staging choices with shared departments from staff list dated 2026-08-31"
                for identifier in archive_departments:
                    await service.archive_department(identifier, {"reason": reason, "force": True}, actor_id=auth.actor_id)
                for identifier in archive_locations:
                    await service.archive_location(identifier, {"reason": reason, "force": True}, actor_id=auth.actor_id)
                for name in create:
                    await service.create_department({"name": name, "code": "staff-20260831-" + hashlib.sha256(name.encode()).hexdigest()[:16],
                        "reason": reason, "metadata_json": {"catalog_source": "staff-list-20260831"}}, actor_id=auth.actor_id)
                result["applied"] = True
            return result
