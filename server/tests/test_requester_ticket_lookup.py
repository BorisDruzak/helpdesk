from datetime import datetime, timedelta, timezone
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import RegistryPerson, RegistryPersonIdentity, Ticket
from requester.identity_service import RequesterIdentityResolver

pytestmark = pytest.mark.db_cleanup("web_support")


def _ticket(actor, **values):
    return Ticket(ticket_id=str(uuid.uuid4()), title="Requester lookup regression",
                  description="Isolated test", status="new", requester_id=actor,
                  device_id=None, custom_fields={}, **values)


@pytest.mark.asyncio
async def test_old_ticket_remains_accessible_by_id_and_code_after_300_newer_tickets(test_engine):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    actor = "lookup-" + uuid.uuid4().hex
    async with maker() as session:
        old = _ticket(actor, created_at=datetime.now(timezone.utc) - timedelta(days=10))
        foreign = _ticket("another-" + uuid.uuid4().hex)
        session.add_all([old, foreign, *[_ticket(actor) for _ in range(301)]])
        await session.commit()
        old_id, old_code = old.ticket_id, old.ticket_code
        foreign_id, foreign_code = foreign.ticket_id, foreign.ticket_code
    async with maker() as session:
        resolver = RequesterIdentityResolver(session)
        recent = await resolver.list_tickets(actor_id=actor, limit=300)
        assert len(recent) == 300
        assert old_id not in {ticket.ticket_id for ticket in recent}
        for reference in (old_id, old_code):
            ticket = await resolver.get_ticket(actor_id=actor, ticket_id=reference)
            assert ticket is not None and ticket.ticket_id == old_id
        for reference in (foreign_id, foreign_code, str(uuid.uuid4())):
            assert await resolver.get_ticket(actor_id=actor, ticket_id=reference) is None


@pytest.mark.asyncio
async def test_direct_lookup_preserves_neutral_scope_and_active_identity_checks(test_engine):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    actor = "lookup-" + uuid.uuid4().hex
    person_id = str(uuid.uuid4())
    async with maker() as session:
        person = RegistryPerson(person_id=person_id, display_name="Lookup test", status="active")
        session.add(person)
        await session.flush()
        session.add(RegistryPersonIdentity(person_id=person_id, provider="ui_login", identifier=actor,
                                           normalized_identifier=actor, verified=True, source="test"))
        neutral = _ticket("different-creator", requester_external_ref=person_id,
                          requester_snapshot_json={"person": {"external_id": person_id}, "display_name": "Lookup test"})
        legacy = _ticket("different-creator", requester_person_id=person_id)
        malformed = _ticket(actor, requester_external_ref=person_id,
                            requester_snapshot_json={"person": {"external_id": "mismatch"}, "display_name": "Lookup test"})
        foreign = _ticket(actor, requester_external_ref="another-person",
                          requester_snapshot_json={"person": {"external_id": "another-person"}, "display_name": "Another test"})
        session.add_all([neutral, legacy, malformed, foreign])
        await session.commit()
        allowed_ids = [neutral.ticket_id, legacy.ticket_id]
        denied_ids = [malformed.ticket_id, foreign.ticket_id]
    async with maker() as session:
        resolver = RequesterIdentityResolver(session)
        for ticket_id in allowed_ids:
            assert await resolver.get_ticket(actor_id=actor, ticket_id=ticket_id) is not None
        for ticket_id in denied_ids:
            assert await resolver.get_ticket(actor_id=actor, ticket_id=ticket_id) is None
        person = await session.get(RegistryPerson, person_id)
        person.status = "inactive"
        await session.commit()
    async with maker() as session:
        resolver = RequesterIdentityResolver(session)
        for ticket_id in allowed_ids + denied_ids:
            assert await resolver.get_ticket(actor_id=actor, ticket_id=ticket_id) is None
