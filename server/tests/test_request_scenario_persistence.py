"""P1 PostgreSQL schema invariants, independent of runtime/UI execution."""
from datetime import datetime, timedelta, timezone
import asyncio
import importlib
import os
from pathlib import Path
import subprocess
import sys
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import HelpdeskService, HelpdeskServiceOffering

pytestmark = pytest.mark.db_cleanup("full")


def _models():
    return importlib.import_module("app.db.request_scenario_models")


async def _seed(session):
    m = _models()
    code = "scenario_" + uuid.uuid4().hex[:8]
    service = HelpdeskService(service_id=str(uuid.uuid4()), code=code, name="Scenario test", public_title="Scenario test")
    session.add(service)
    await session.flush()
    offering = HelpdeskServiceOffering(offering_id=str(uuid.uuid4()), service_id=service.service_id, code="printer", full_code=code + ".printer", name="Printer", public_title="Printer")
    session.add(offering)
    category = m.RequestStudioCategory(id=str(uuid.uuid4()), service_code=code, slug="printers", title="Принтеры")
    session.add(category)
    await session.flush()
    scenario = m.RequestStudioScenario(id=str(uuid.uuid4()), scenario_key=code, service_code=code, offering_full_code=offering.full_code, category_id=category.id, title="Не печатает")
    session.add(scenario)
    await session.flush()
    return m, service, offering, category, scenario


@pytest.mark.asyncio
async def test_category_root_slug_unique_and_cycle_rejected(test_engine):
    async with async_sessionmaker(test_engine, expire_on_commit=False)() as session:
        m, service, _, root, _ = await _seed(session)
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(m.RequestStudioCategory(id=str(uuid.uuid4()), service_code=service.code, slug=root.slug, title="Duplicate"))
                await session.flush()
        child = m.RequestStudioCategory(id=str(uuid.uuid4()), service_code=service.code, parent_id=root.id, slug="child", title="Child")
        session.add(child)
        await session.flush()
        with pytest.raises(DBAPIError):
            async with session.begin_nested():
                await session.execute(sa.update(m.RequestStudioCategory).where(m.RequestStudioCategory.id == root.id).values(parent_id=child.id))


@pytest.mark.asyncio
async def test_category_parent_cannot_cross_service(test_engine):
    async with async_sessionmaker(test_engine, expire_on_commit=False)() as session:
        m, _, _, root, _ = await _seed(session)
        _, other, _, _, _ = await _seed(session)
        with pytest.raises(DBAPIError):
            async with session.begin_nested():
                session.add(m.RequestStudioCategory(id=str(uuid.uuid4()), service_code=other.code, parent_id=root.id, slug="illegal", title="Illegal"))
                await session.flush()


@pytest.mark.asyncio
async def test_versions_are_immutable_and_session_is_pinned(test_engine):
    async with async_sessionmaker(test_engine, expire_on_commit=False)() as session:
        m, _, offering, _, scenario = await _seed(session)
        version = m.RequestStudioScenarioVersion(id=str(uuid.uuid4()), scenario_id=scenario.id, offering_full_code=offering.full_code, version=1, schema_version=1, definition={"schema_version": 1}, content_hash="a" * 64, source_snapshot={}, published_by="synthetic-admin")
        session.add(version)
        await session.flush()
        with pytest.raises(DBAPIError):
            async with session.begin_nested():
                await session.execute(sa.update(m.RequestStudioScenarioVersion).where(m.RequestStudioScenarioVersion.id == version.id).values(definition={"changed": True}))
        # Retire changes only status; immutable graph/snapshot stay intact for sessions.
        version.state = "retired"
        await session.flush()
        next_version = m.RequestStudioScenarioVersion(id=str(uuid.uuid4()), scenario_id=scenario.id, offering_full_code=offering.full_code, version=2, schema_version=1, definition={"schema_version": 1}, content_hash="b" * 64, source_snapshot={}, published_by="synthetic-admin")
        session.add(next_version)
        await session.flush()
        run = m.RequestStudioSession(id=str(uuid.uuid4()), owner_actor_id="synthetic-requester", version_id=version.id, current_block_id="questions", expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        session.add(run)
        await session.flush()
        with pytest.raises(DBAPIError):
            async with session.begin_nested():
                await session.execute(sa.update(m.RequestStudioSession).where(m.RequestStudioSession.id == run.id).values(version_id=next_version.id))
        assert (await session.get(m.RequestStudioSession, run.id)).version_id == version.id


@pytest.mark.asyncio
async def test_only_one_active_version_and_draft_revision_positive(test_engine):
    async with async_sessionmaker(test_engine, expire_on_commit=False)() as session:
        m, _, offering, _, scenario = await _seed(session)
        first = m.RequestStudioScenarioVersion(id=str(uuid.uuid4()), scenario_id=scenario.id, offering_full_code=offering.full_code, version=1, schema_version=1, definition={}, content_hash="a" * 64, source_snapshot={}, published_by="synthetic-admin")
        session.add(first)
        await session.flush()
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(m.RequestStudioScenarioVersion(id=str(uuid.uuid4()), scenario_id=scenario.id, offering_full_code=offering.full_code, version=2, schema_version=1, definition={}, content_hash="b" * 64, source_snapshot={}, published_by="synthetic-admin"))
                await session.flush()
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(m.RequestStudioDraft(scenario_id=scenario.id, definition={}, revision=0, updated_by="synthetic-admin"))
                await session.flush()


@pytest.mark.asyncio
async def test_category_depth_bound_includes_reparented_subtree(test_engine):
    async with async_sessionmaker(test_engine, expire_on_commit=False)() as session:
        m, service, _, root, _ = await _seed(session)
        parent = root
        for depth in range(2, 17):
            node = m.RequestStudioCategory(id=str(uuid.uuid4()), service_code=service.code, parent_id=parent.id, slug=f"level_{depth}", title="Level")
            session.add(node)
            await session.flush()
            parent = node
        with pytest.raises(DBAPIError):
            async with session.begin_nested():
                session.add(m.RequestStudioCategory(id=str(uuid.uuid4()), service_code=service.code, parent_id=parent.id, slug="too_deep", title="Too deep"))
                await session.flush()
        separate = m.RequestStudioCategory(id=str(uuid.uuid4()), service_code=service.code, slug="separate", title="Separate")
        session.add(separate)
        await session.flush()
        with pytest.raises(DBAPIError):
            async with session.begin_nested():
                await session.execute(sa.update(m.RequestStudioCategory).where(m.RequestStudioCategory.id == root.id).values(parent_id=separate.id))


@pytest.mark.asyncio
async def test_retired_version_cannot_reactivate_or_delete_and_session_owner_is_fixed(test_engine):
    async with async_sessionmaker(test_engine, expire_on_commit=False)() as session:
        m, _, offering, _, scenario = await _seed(session)
        version = m.RequestStudioScenarioVersion(id=str(uuid.uuid4()), scenario_id=scenario.id, offering_full_code=offering.full_code, version=1, schema_version=1, definition={}, content_hash="a" * 64, source_snapshot={}, published_by="synthetic-admin")
        session.add(version)
        await session.flush()
        version.state = "retired"
        await session.flush()
        for statement in (
            sa.update(m.RequestStudioScenarioVersion).where(m.RequestStudioScenarioVersion.id == version.id).values(state="published"),
            sa.delete(m.RequestStudioScenarioVersion).where(m.RequestStudioScenarioVersion.id == version.id),
        ):
            with pytest.raises(DBAPIError):
                async with session.begin_nested():
                    await session.execute(statement)
        run = m.RequestStudioSession(id=str(uuid.uuid4()), owner_actor_id="synthetic-requester", version_id=version.id, current_block_id="questions", expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        session.add(run)
        await session.flush()
        with pytest.raises(DBAPIError):
            async with session.begin_nested():
                await session.execute(sa.update(m.RequestStudioSession).where(m.RequestStudioSession.id == run.id).values(owner_actor_id="another-requester"))


def test_additive_revision_rollback_preserves_legacy_catalog(test_database_url, test_database_admin_url):
    """Only 147 -> 146 -> 147, isolated from later forward-only revisions."""
    database = "pc_support_test_studio147_" + uuid.uuid4().hex
    test_database_url = sa.engine.make_url(test_database_url).set(database=database).render_as_string(hide_password=False)

    async def manage_database(create):
        engine = create_async_engine(test_database_admin_url, isolation_level="AUTOCOMMIT")
        try:
            async with engine.connect() as connection:
                await connection.execute(sa.text(("CREATE DATABASE " if create else "DROP DATABASE ") + '"' + database + '"'))
        finally:
            await engine.dispose()

    server_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["DATABASE_URL"] = test_database_url
    service_id = str(uuid.uuid4())
    code = "rollback_" + uuid.uuid4().hex[:8]

    async def inspect(seed=False):
        engine = create_async_engine(test_database_url)
        try:
            async with engine.begin() as connection:
                if seed:
                    await connection.execute(sa.text("INSERT INTO helpdesk_services (service_id,code,name,public_title) VALUES (:id,:code,'Legacy sentinel','Legacy sentinel')"), {"id": service_id, "code": code})
                row = (await connection.execute(sa.text("SELECT code,name,public_title FROM helpdesk_services WHERE service_id=:id"), {"id": service_id})).one()
                tables = set((await connection.execute(sa.text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))).scalars())
                revision = set((await connection.execute(sa.text("SELECT version_num FROM alembic_version"))).scalars())
                return tuple(row), tables, revision
        finally:
            await engine.dispose()

    def migrate(command, revision):
        result = subprocess.run([sys.executable, "-m", "alembic", "-c", str(server_root / "alembic.ini"), command, revision], cwd=server_root, env=environment, capture_output=True, text=True)
        # Do not emit subprocess diagnostics that might contain a database URL.
        assert result.returncode == 0, f"isolated Alembic {command} {revision} failed"

    asyncio.run(manage_database(True))
    try:
        migrate("upgrade", "147")
        before, tables, head = asyncio.run(inspect(seed=True))
        assert head == {"147"}
        try:
            migrate("downgrade", "146")
            after, downgraded, revision = asyncio.run(inspect())
            assert before == after
            assert revision == {"146"}
            assert tables - downgraded == {"request_studio_categories", "request_studio_scenarios", "request_studio_scenario_versions", "request_studio_drafts", "request_studio_sessions"}
        finally:
            migrate("upgrade", "147")
        after, restored, revision = asyncio.run(inspect())
        assert after == before and restored == tables and revision == {"147"}
    finally:
        asyncio.run(manage_database(False))


@pytest.mark.asyncio
async def test_version_bindings_cannot_cross_scenario_or_offering(test_engine):
    async with async_sessionmaker(test_engine, expire_on_commit=False)() as session:
        m, _, offering, _, scenario = await _seed(session)
        _, _, other_offering, _, other = await _seed(session)
        version = m.RequestStudioScenarioVersion(id=str(uuid.uuid4()), scenario_id=scenario.id, offering_full_code=offering.full_code, version=1, schema_version=1, definition={}, content_hash="a" * 64, source_snapshot={}, published_by="synthetic-admin")
        session.add(version)
        await session.flush()
        with pytest.raises(IntegrityError) as wrong_binding:
            async with session.begin_nested():
                session.add(m.RequestStudioScenarioVersion(id=str(uuid.uuid4()), scenario_id=other.id, offering_full_code=offering.full_code, version=1, schema_version=1, definition={}, content_hash="b" * 64, source_snapshot={}, state="retired", published_by="synthetic-admin"))
                await session.flush()
        assert wrong_binding.value.orig.sqlstate == "23503"
        with pytest.raises(IntegrityError) as wrong_base:
            async with session.begin_nested():
                session.add(m.RequestStudioDraft(scenario_id=other.id, base_version_id=version.id, definition={}, revision=1, updated_by="synthetic-admin"))
                await session.flush()
        assert wrong_base.value.orig.sqlstate == "23503"
        with pytest.raises(IntegrityError) as wrong_active:
            async with session.begin_nested():
                await session.execute(sa.update(m.RequestStudioScenario).where(m.RequestStudioScenario.id == other.id).values(published_version_id=version.id))
                await session.execute(sa.text("SET CONSTRAINTS fk_studio_scenario_active_version IMMEDIATE"))
        assert wrong_active.value.orig.sqlstate == "23503"
        assert offering.full_code != other_offering.full_code


@pytest.mark.asyncio
async def test_concurrent_category_reparent_cannot_commit_cycle(test_engine):
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as session:
        m, service, _, root, _ = await _seed(session)
        other = m.RequestStudioCategory(id=str(uuid.uuid4()), service_code=service.code, slug="other_root", title="Other")
        session.add(other)
        await session.commit()
        left, right = root.id, other.id
    ready = asyncio.Event()
    arrived = 0

    async def reparent(child, parent):
        nonlocal arrived
        async with factory() as session:
            await session.execute(sa.text("SET LOCAL lock_timeout = '5s'"))
            arrived += 1
            if arrived == 2:
                ready.set()
            await ready.wait()
            try:
                await session.execute(sa.update(m.RequestStudioCategory).where(m.RequestStudioCategory.id == child).values(parent_id=parent))
                await session.commit()
                return True
            except DBAPIError as error:
                await session.rollback()
                # Raw UPDATE locks its row before the trigger's service lock.
                # PostgreSQL may abort the opposing transaction as a deadlock;
                # the admin API instead acquires the service lock first.
                assert error.orig.sqlstate in {"23514", "40P01"}
                return False

    committed = await asyncio.gather(reparent(left, right), reparent(right, left))
    assert sum(committed) == 1
    async with factory() as session:
        rows = dict((await session.execute(sa.select(m.RequestStudioCategory.id, m.RequestStudioCategory.parent_id).where(m.RequestStudioCategory.id.in_([left, right])))).all())
        assert set(rows) == {left, right}
        assert rows[left] is None or rows[right] is None
        winning_child, winning_parent = (left, right) if committed[0] else (right, left)
        assert rows[winning_child] == winning_parent
        assert rows[winning_parent] is None
        # After the winner commits, the rejected edge must deterministically
        # fail the cycle constraint, without a competing transaction.
        with pytest.raises(DBAPIError) as cycle:
            await session.execute(sa.update(m.RequestStudioCategory).where(
                m.RequestStudioCategory.id == winning_parent).values(parent_id=winning_child))
        await session.rollback()
        assert cycle.value.orig.sqlstate == "23514"
