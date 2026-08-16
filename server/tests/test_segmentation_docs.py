import re
from pathlib import Path

import pytest


pytestmark = pytest.mark.no_db


DOCS_ROOT = Path("server/docs")


def test_registry_docs_define_correlated_observer_profile_completion_not_found() -> None:
    api = (DOCS_ROOT / "REGISTRY_PLATFORM_API_V1.md").read_text(encoding="utf-8")
    normalized_api = " ".join(api.split())

    assert "only documented non-200 projection envelopes" in normalized_api
    assert (
        "observer requester-profile-completion read returns a correlated exact `404` envelope"
        in normalized_api
    )
    assert (
        '`data` is exactly `{ "status": "not_found", "code": "registry_requester_not_found" }`'
        in normalized_api
    )
    assert "unknown codes, additional fields or correlation mismatch are invalid projections" in normalized_api


def test_segmentation_docs_define_external_knowledge_contract_without_fallback() -> None:
    boundaries = (DOCS_ROOT / "SEGMENTATION_BOUNDARIES.md").read_text(encoding="utf-8")
    adr = (DOCS_ROOT / "adr/0001-helpdesk-external-domain-ports.md").read_text(
        encoding="utf-8"
    )
    api = (DOCS_ROOT / "KNOWLEDGE_PLATFORM_API_V1.md").read_text(encoding="utf-8")
    normalized_boundaries = " ".join(boundaries.split())
    normalized_adr = " ".join(adr.split())
    normalized_api = " ".join(api.split())

    assert "KnowledgePort" in boundaries
    assert "no local fallback" in boundaries
    assert "preceding verified application release" in normalized_boundaries
    assert "PR-11" in boundaries
    assert "not a Helpdesk route" in api
    assert "knowledge_unavailable" in api
    assert "never authorises a local Knowledge lookup or a local fallback" in normalized_api
    assert "opaque" in api
    assert "correlation_id" in api
    assert "cursor pagination" in api
    assert "redacted" in api
    for operation in (
        "POST /v1/search",
        "POST /v1/suggestions",
        "GET /v1/items/{item_ref}/versions/{version_ref}",
        "POST /v1/resolution-drafts",
        "POST /v1/feedback",
    ):
        assert operation in api
    for scope in (
        "knowledge.search",
        "knowledge.suggest",
        "knowledge.read_projection",
        "knowledge.resolution_draft",
        "knowledge.feedback",
    ):
        assert scope in api
    assert "preceding verified application release" in normalized_adr
    assert "PR-11" in adr


def test_docs_reference_external_knowledge_contract_not_removed_runtime() -> None:
    architecture = Path("docs/ARCHITECTURE_BOUNDARIES.md").read_text(encoding="utf-8")
    ticket_system = (DOCS_ROOT / "TICKET_SYSTEM.md").read_text(encoding="utf-8")
    database = (DOCS_ROOT / "DATABASE.md").read_text(encoding="utf-8")

    assert "external Knowledge Platform" in architecture
    assert "server/knowledge/" not in architecture
    assert "KnowledgePort" in ticket_system
    assert "knowledge_unavailable" in ticket_system
    assert "PR-11" in database
    assert "Retired local Knowledge/AI schema (revision 134)" in database


def test_codemaps_do_not_advertise_removed_local_knowledge_runtime() -> None:
    server_codemap = (DOCS_ROOT / "CODEMAP.md").read_text(encoding="utf-8")
    agent_runtime = Path("pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md").read_text(
        encoding="utf-8"
    )

    for text in (server_codemap, agent_runtime):
        for removed_surface in (
            "server/knowledge/",
            "server/ai/",
            "/api/knowledge/",
            "/api/web/knowledge/",
            "/app/knowledge",
            "KNOWLEDGE_PLATFORM.md",
        ):
            assert removed_surface not in text
    assert "KnowledgePort" in server_codemap
    assert "PR-7" in server_codemap
    assert "PR-11" in server_codemap


def test_server_codemap_does_not_preserve_deleted_knowledge_platform_claims() -> None:
    server_codemap = (DOCS_ROOT / "CODEMAP.md").read_text(encoding="utf-8")

    for deleted_artifact in (
        "test_knowledge_ask.py",
        "test_knowledge_access_service.py",
        "webapp/src/features/knowledge/",
        "knowledge.metadata.manage",
        "seed_knowledge_metadata.py",
        "content_packs/knowledge/",
        "server/web_api/knowledge_handlers.py",
        "knowledge_audience_live_smoke.py",
        "/app/admin/knowledge/",
        "test_knowledge_portal.py",
        "knowledge_feedback_events",
        "knowledge_correction_requests",
        "knowledge_user_bookmarks",
        "KNOWLEDGE_REMOTE_IMPORT_",
        "knowledge_audience_rule",
        "knowledge_provider.py",
        "app.repos.knowledge_repo",
        "TicketKnowledgeLink",
    ):
        assert deleted_artifact not in server_codemap


def test_server_codemap_limits_knowledge_to_external_boundary_and_history() -> None:
    server_lines = (DOCS_ROOT / "CODEMAP.md").read_text(encoding="utf-8").splitlines()
    agent_lines = Path("pc_agent/docs/CODEMAP.md").read_text(encoding="utf-8").splitlines()
    approved_server_lines = {
        "  configuration and content packs are removed. `KnowledgePort` is external-only",
        "  and remains fail-closed as `knowledge_unavailable` until PR-7 accepts a",
        "  the physical legacy graph; `TicketKbLink`/`ticket_kb_links` history and",
        "  sanitized `knowledge_attempts` remain read-only historical projections.",
        "  control plane; future Knowledge and Registry Platforms are separate domains.",
        "  to consume Endpoint, Knowledge and Registry only through explicitly composed,",
        "- `server/docs/KNOWLEDGE_PLATFORM_API_V1.md` defines a future external",
        "  Knowledge API contract. `KnowledgePort` remains unavailable until explicit",
        "  composition and reports `knowledge_unavailable`.",
        "- `server/domain_ports/knowledge.py`, `registry.py` and `endpoint.py` define the",
        "  neutral, runtime-checkable dependency-injection protocols. Knowledge request",
        "  adapters with no DB or HTTP work.",
        "  fresh adapters from the fail-closed `server/config.py::KNOWLEDGE_PORT_MODE`",
    }
    approved_agent_line = (
        "Protocol V3 is unchanged. The Qt client continues the Service Catalog/form ticket flow; "
        "any future external content integration must be composed behind the Helpdesk "
        "`KnowledgePort` contract, not as a direct agent-to-Helpdesk API."
    )
    retirement_start = next(
        line_number
        for line_number, line in enumerate(server_lines, start=1)
        if line == "## 2026-08-10 Knowledge/AI schema retirement (PR-11a)"
    )

    for line_number, line in enumerate(server_lines, start=1):
        if "knowledge" in line.casefold():
            if line_number <= 50:
                assert line in approved_server_lines, line
                assert not re.search(r"\b(local|fallback|search|ask|service|route)\b", line, re.I), line
            else:
                assert retirement_start <= line_number <= retirement_start + 14, line

    for line in agent_lines:
        if "knowledge" in line.casefold():
            assert line == approved_agent_line, line

    for line in (*server_lines, *agent_lines):
        assert re.search(r"\bkb\b", line, flags=re.IGNORECASE) is None, line


def test_canonical_docs_do_not_advertise_local_knowledge_flows() -> None:
    database_lines = (DOCS_ROOT / "DATABASE.md").read_text(encoding="utf-8").splitlines()
    web_first_lines = Path("docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md").read_text(
        encoding="utf-8"
    ).splitlines()
    canonical_text = "\n".join((*database_lines, *web_first_lines))

    assert not any("knowledge" in line.casefold() for line in web_first_lines)

    # The removed requester content flow must not be renamed and retained under
    # a neutral label. Ordinary request-form drafts remain documented elsewhere;
    # only the former external-content draft context is prohibited here.
    assert "external-content" not in canonical_text
    assert "draft context" not in canonical_text.casefold()

    for line in database_lines:
        assert re.search(r"\bKB\b", line) is None, line
        assert "kb_linked" not in line and "kb_unlinked" not in line, line
        if "kb_links" in line:
            assert "TicketKbLink" in line, line
            assert "read-only historical projection" in line, line
        if "TicketKbLink" in line:
            assert "read-only historical projection" in line, line
        if "knowledge_attempts" in line:
            assert "read-only" in line.casefold(), line

    database = "\n".join(database_lines)
    assert "Retired local Knowledge/AI schema (revision 134)" in database
    assert "134_retire_local_knowledge_ai_schema.py" in database
    assert "forward-only removal" in database

    for forbidden_surface in (
        "knowledge_repo.py",
        "knowledge.access_service",
        "knowledge.metadata_service",
        "knowledge.content_pack_service",
        "knowledge.review_task_service",
        "knowledge.search_analytics_service",
        "knowledge.search_settings_service",
        "knowledge.operations_service",
        "server/knowledge/",
        "server/ai/",
        "/api/knowledge/",
        "/api/web/knowledge/",
        "/app/knowledge",
        "webapp/src/features/knowledge/",
        "content_packs/knowledge/",
        "KnowledgeSpace",
        "KnowledgeAccessService",
        "KnowledgeRepo",
        "KnowledgeRetrievalService",
        "KnowledgeVectorSearchService",
        "requester_knowledge",
        "knowledge_attempt_guard",
        "knowledge_draft_hints",
        "Knowledge Ask",
        "Knowledge RAG",
    ):
        assert forbidden_surface not in canonical_text


def test_observer_docs_do_not_advertise_retired_requester_knowledge_events() -> None:
    authoring_rules = (DOCS_ROOT / "OBSERVER_AUTHORING_RULES.md").read_text(encoding="utf-8")
    for retired_event in (
        "requester_knowledge",
        "knowledge_suggest_succeeded",
        "knowledge_ask_succeeded",
        "knowledge_attempt_guard_succeeded",
    ):
        assert retired_event not in authoring_rules
