from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker

import pytest

from knowledge.content_pack_service import KnowledgeContentPackService, load_content_pack_file
from knowledge.suggestion_service import KnowledgeSuggestionService


pytestmark = pytest.mark.db_cleanup("knowledge")

PACK_DIR = Path("content_packs/knowledge")


async def _install_baseline(session) -> None:
    service = KnowledgeContentPackService(session)
    await service.apply_pack(load_content_pack_file(PACK_DIR / "it-self-service-baseline.yaml"), actor_id="admin-test")
    await service.apply_pack(load_content_pack_file(PACK_DIR / "support-runbooks-baseline.yaml"), actor_id="admin-test", publish=True)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("service_code", "offering_code", "request_template_key", "slug"),
    [
        ("network", "network.vpn_issue", "network", "vpn-basic-checks"),
        ("access", "access.reset_password", "access", "password-reset-before-ticket"),
        ("mail", "mail.mailbox_issue", "mail_issue", "mail-basic-diagnostics"),
        ("workplace", "workplace.printer_issue", "printer", "printer-basic-checks"),
        ("workplace", "workplace.laptop_broken", "breakage", "laptop-power-basic"),
        ("other", "other.unknown", "general_request", "unknown-category-describe-problem"),
    ],
)
async def test_seeded_requester_baseline_suggests_canonical_context(test_engine, service_code, offering_code, request_template_key, slug) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await _install_baseline(session)
        result = await KnowledgeSuggestionService(session).suggest(
            {
                "surface": "requester_portal",
                "service_code": service_code,
                "offering_code": offering_code,
                "request_template_key": request_template_key,
            },
            actor_role="requester",
        )

    assert result["suggestions"][0]["slug"] == slug


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("service_code", "offering_code", "request_template_key", "slug"),
    [
        ("network", "network.vpn_issue", "network", "support-vpn-primary-diagnostics"),
        ("workplace", "workplace.laptop_broken", "breakage", "support-laptop-primary-diagnostics"),
        ("mail", "mail.mailbox_issue", "mail_issue", "support-mail-primary-diagnostics"),
    ],
)
async def test_seeded_support_runbooks_match_canonical_context(test_engine, service_code, offering_code, request_template_key, slug) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await _install_baseline(session)
        result = await KnowledgeSuggestionService(session).suggest(
            {
                "surface": "support_workspace",
                "service_code": service_code,
                "offering_code": offering_code,
                "request_template_key": request_template_key,
            },
            actor_role="support",
        )

    assert any(item["slug"] == slug for item in result["suggestions"])


@pytest.mark.asyncio
async def test_rollout_max_suggestions_limits_seeded_results(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await _install_baseline(session)
        from knowledge.operations_service import KnowledgeOperationsService

        await KnowledgeOperationsService(session).upsert_rollout_policy(
            {"surface": "requester_portal", "max_suggestions": 1},
            actor_id="admin-test",
        )
        result = await KnowledgeSuggestionService(session).suggest(
            {"surface": "requester_portal", "service_code": "network", "offering_code": "network.vpn_issue", "request_template_key": "network"},
            actor_role="requester",
        )

    assert len(result["suggestions"]) == 1
