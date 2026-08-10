from __future__ import annotations

import asyncio
import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool


# This is deliberately a hand-maintained historical contract.  The active ORM
# no longer describes these tables, so deriving this set from models would let
# an accidental schema resurrection or omission escape the retirement test.
RETIRED_KNOWLEDGE_AI_TABLES = frozenset(
    {
        "ai_model_profiles",
        "ai_policy_profiles",
        "ai_providers",
        "ai_request_audit",
        "knowledge_ai_proposals",
        "knowledge_applicability_rules",
        "knowledge_article_editor_events",
        "knowledge_article_segments",
        "knowledge_article_subscriptions",
        "knowledge_article_views",
        "knowledge_audience_rules",
        "knowledge_bindings",
        "knowledge_chunk_embeddings",
        "knowledge_chunks",
        "knowledge_content_pack_items",
        "knowledge_content_packs",
        "knowledge_correction_requests",
        "knowledge_edges",
        "knowledge_entity_mentions",
        "knowledge_feedback_events",
        "knowledge_gap_findings",
        "knowledge_graph_layouts",
        "knowledge_index_jobs",
        "knowledge_ingestion_jobs",
        "knowledge_item_properties",
        "knowledge_item_taxonomy_terms",
        "knowledge_item_versions",
        "knowledge_items",
        "knowledge_nodes",
        "knowledge_property_definitions",
        "knowledge_quality_models",
        "knowledge_quality_snapshots",
        "knowledge_review_comments",
        "knowledge_review_tasks",
        "knowledge_rollout_policies",
        "knowledge_search_events",
        "knowledge_search_settings",
        "knowledge_segmentation_jobs",
        "knowledge_segmentation_profiles",
        "knowledge_spaces",
        "knowledge_taxonomy_terms",
        "knowledge_user_bookmarks",
        "knowledge_version_diff_cache",
        "problem_known_error_links",
        "ticket_knowledge_links",
    }
)


# The migration must leave every Helpdesk-owned table and every local Registry
# table untouched.  Literal names avoid reusing the manifest under test.
PROTECTED_TABLES = frozenset(
    {
        "tickets",
        "ticket_kb_links",
        "ticket_resolution_passports",
        "problems",
        "ui_users",
        "auth_sessions",
        "ui_tokens",
        "ui_user_audit",
        "ui_password_reset_requests",
        "ticket_public_sessions",
        "access_groups",
        "access_group_members",
        "access_group_permissions",
        "access_group_queue_members",
        "access_audit",
        "ticket_queues",
        "ticket_queue_members",
        "ticket_queue_ola_targets",
        "user_consent_requests",
        "device_account_events",
        "device_account_login_requests",
        "device_account_sessions",
        "device_browser_pairings",
        "device_registration_claims",
        "device_registration_events",
        "device_user_bindings",
        "registry_admin_events",
        "registry_admin_policies",
        "registry_assets",
        "registry_audience_group_members",
        "registry_audience_groups",
        "registry_departments",
        "registry_locations",
        "registry_people",
        "registry_person_department_memberships",
        "registry_person_identities",
        "registry_quality_issue_overrides",
        "registry_services",
        "registry_vendors",
    }
)


SERVER_ROOT = Path(__file__).resolve().parents[1]


# The test owns its real isolated DB migration sequence below.  This prevents
# the global harness from pre-applying ``head`` or a cleanup profile before the
# 133->134 contract; ``test_database_url`` still creates and tears down this
# private database and the test runs real Alembic subprocesses against it.
pytestmark = [pytest.mark.migration_clone, pytest.mark.db_cleanup("full")]


def _run_alembic_upgrade(database_url: str, revision: str) -> None:
    """Run a real Alembic upgrade in a subprocess, matching Windows harness behavior."""

    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(SERVER_ROOT / "alembic.ini"), "upgrade", revision],
        cwd=str(SERVER_ROOT),
        env=environment,
        check=True,
    )


async def _catalog_tables(database_url: str) -> set[str]:
    engine = create_async_engine(database_url, echo=False, pool_pre_ping=True, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_type = 'BASE TABLE'
                    """
                )
            )
            return {str(row[0]) for row in result.all()}
    finally:
        await engine.dispose()


async def _protected_tables_are_selectable(database_url: str) -> None:
    engine = create_async_engine(database_url, echo=False, pool_pre_ping=True, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            for table_name in sorted(PROTECTED_TABLES):
                # ``table_name`` comes from the literal set above, not user input.
                await connection.execute(text(f'SELECT count(*) FROM "{table_name}"'))
    finally:
        await engine.dispose()


def test_clone_upgrade_from_133_retires_only_historical_knowledge_ai_schema(test_database_url: str) -> None:
    """Catch a migration that misses or over-drops the retired physical graph."""

    database_name = make_url(test_database_url).database or ""
    assert database_name.startswith("pc_support_test_")
    assert database_name != "pc_support_test"
    assert len(RETIRED_KNOWLEDGE_AI_TABLES) == 45
    _run_alembic_upgrade(test_database_url, "133")
    before = asyncio.run(_catalog_tables(test_database_url))
    assert RETIRED_KNOWLEDGE_AI_TABLES <= before
    assert PROTECTED_TABLES <= before

    _run_alembic_upgrade(test_database_url, "134")
    after = asyncio.run(_catalog_tables(test_database_url))
    assert not RETIRED_KNOWLEDGE_AI_TABLES & after
    assert before - after == RETIRED_KNOWLEDGE_AI_TABLES
    assert PROTECTED_TABLES <= after
    asyncio.run(_protected_tables_are_selectable(test_database_url))

    _run_alembic_upgrade(test_database_url, "head")
    assert asyncio.run(_catalog_tables(test_database_url)) == after
