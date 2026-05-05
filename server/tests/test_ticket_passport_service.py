from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import func, select

from app.db.engine import async_sessionmaker
from app.db.models import Artifact, Operation, Ticket, TicketEvent, TicketEvidenceItem, TicketResolutionPassport, TicketWorklog
from app.repos.ticket_passport_repo import TicketPassportRepo
from tickets.passport_service import TicketPassportService


@pytest.mark.asyncio
async def test_passport_service_builds_requester_problem_and_object_sections(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        ticket = Ticket(
            ticket_id=ticket_id,
            device_id=device_id,
            title="Не печатает принтер",
            description="В кабинете 214 не печатаются документы",
            status="in_progress",
            requester_id="user-214",
            requester_status="in_work",
            next_action_owner="support",
            custom_fields={
                "user_display_name": "Иванов Иван",
                "requester_profile": {"department": "Бухгалтерия", "building": "A", "room": "214"},
            },
        )
        session.add(ticket)
        session.add(
            TicketEvent(
                ticket_id=ticket_id,
                device_id=device_id,
                agent_seq=None,
                event_type="chat_message",
                payload={"text": "Принтер HP не печатает", "sender_role": "user", "visibility": "public"},
            )
        )
        await session.flush()

        payload = await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="create")

        assert payload["passport"]["version"] == 1
        sections = payload["passport"]["sections"]
        assert "Иванов Иван" in sections["requester"]
        assert "Не печатает принтер" in sections["problem"]
        assert "кабинете 214" in sections["problem"]
        assert device_id in sections["affected_object"]


@pytest.mark.asyncio
async def test_passport_service_collects_tool_events_as_automated_checks(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    operation_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Диагностика сети",
                description="Проверить доступность сайта",
                status="in_progress",
                requester_id="user-net",
                requester_status="in_work",
                next_action_owner="support",
            )
        )
        session.add(
            TicketEvent(
                ticket_id=ticket_id,
                device_id=device_id,
                agent_seq=None,
                event_type="tool_call_result",
                operation_id=operation_id,
                payload={"tool_name": "network.ping", "result_summary": "Пинг успешен"},
            )
        )
        session.add(
            Operation(
                operation_id=operation_id,
                device_id=device_id,
                ticket_id=ticket_id,
                kind="tool",
                tool_name="network.ping",
                actor_role="support",
                trace_id=str(uuid.uuid4()),
                status="succeeded",
                queued_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                result_summary="Средняя задержка 3 мс",
            )
        )
        await session.flush()

        payload = await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="create")

        assert "network.ping" in payload["passport"]["sections"]["automated_checks"]
        assert "Средняя задержка 3 мс" in payload["passport"]["sections"]["automated_checks"]
        assert operation_id in payload["passport"]["source_operation_ids"]
        assert payload["actions"][0]["operation_id"] == operation_id


@pytest.mark.asyncio
async def test_passport_service_materializes_diagnostic_operation_evidence_from_policy(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    operation_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Website unavailable",
                description="Check website availability",
                status="in_progress",
                requester_id="user-net",
                requester_status="in_work",
                next_action_owner="support",
                custom_fields={
                    "request_template": {
                        "key": "website_unavailable",
                        "ticket_type": "incident",
                        "diagnostic_policy": {
                            "id": "website_diagnostics",
                            "attach_results": {
                                "to_passport": True,
                                "as_evidence": True,
                            },
                        },
                    },
                },
            )
        )
        session.add(
            Operation(
                operation_id=operation_id,
                device_id=device_id,
                ticket_id=ticket_id,
                kind="tool",
                tool_name="diagnose.website",
                actor_role="support",
                trace_id=str(uuid.uuid4()),
                status="succeeded",
                queued_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                result_summary="HTTP 200 OK, DNS resolved",
            )
        )
        await session.flush()

        first_payload = await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="create")
        second_payload = await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="refresh")

        evidence_rows = (
            await session.execute(
                select(TicketEvidenceItem).where(TicketEvidenceItem.ticket_id == ticket_id)
            )
        ).scalars().all()

        assert len(evidence_rows) == 1
        evidence = evidence_rows[0]
        assert evidence.evidence_type == "diagnostic_result"
        assert evidence.source_ref == f"operation:{operation_id}"
        assert evidence.source_kind == "operation"
        assert evidence.source_id == operation_id
        assert evidence.required_fact == "evidence"
        assert evidence.section_key == "evidence"
        assert evidence.verification_status == "accepted"
        assert evidence.export_visibility == "internal"
        assert evidence.metadata_json["operation_status"] == "succeeded"
        assert evidence.metadata_json["tool_name"] == "diagnose.website"
        assert evidence.title == "diagnose.website"
        assert evidence.summary == "HTTP 200 OK, DNS resolved"
        assert evidence.created_by == "op1"
        assert first_payload["evidence"][0]["source_ref"] == f"operation:{operation_id}"
        assert first_payload["evidence"][0]["source_kind"] == "operation"
        assert first_payload["evidence"][0]["source_id"] == operation_id
        assert first_payload["evidence"][0]["required_fact"] == "evidence"
        assert first_payload["evidence"][0]["verification_status"] == "accepted"
        assert "HTTP 200 OK" in first_payload["passport"]["sections"]["evidence"]
        assert len(second_payload["evidence"]) == 1


@pytest.mark.asyncio
async def test_passport_service_does_not_materialize_diagnostic_evidence_when_policy_disables_it(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Website unavailable",
                description="Check website availability",
                status="in_progress",
                requester_id="user-net",
                requester_status="in_work",
                next_action_owner="support",
                custom_fields={
                    "request_template": {
                        "key": "website_unavailable",
                        "ticket_type": "incident",
                        "diagnostic_policy": {
                            "id": "website_diagnostics",
                            "attach_results": {"to_passport": True, "as_evidence": False},
                        },
                    },
                },
            )
        )
        session.add(
            Operation(
                operation_id=str(uuid.uuid4()),
                device_id=device_id,
                ticket_id=ticket_id,
                kind="tool",
                tool_name="diagnose.website",
                actor_role="support",
                trace_id=str(uuid.uuid4()),
                status="succeeded",
                queued_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                result_summary="HTTP 200 OK",
            )
        )
        await session.flush()

        payload = await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="create")

        evidence_count = await session.scalar(
            select(func.count(TicketEvidenceItem.id)).where(TicketEvidenceItem.ticket_id == ticket_id)
        )
        assert evidence_count == 0
        assert payload["evidence"] == []


@pytest.mark.asyncio
async def test_passport_service_does_not_materialize_foreign_ticket_device_operation(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    other_ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Website unavailable",
                description="Current ticket has no own operations",
                status="in_progress",
                requester_id="user-net",
                requester_status="in_work",
                next_action_owner="support",
                custom_fields={
                    "request_template": {
                        "key": "website_unavailable",
                        "ticket_type": "incident",
                        "diagnostic_policy": {
                            "id": "website_diagnostics",
                            "attach_results": {"to_passport": True, "as_evidence": True},
                        },
                    },
                },
            )
        )
        session.add(
            Ticket(
                ticket_id=other_ticket_id,
                device_id=device_id,
                title="Previous website check",
                description="Owns the operation",
                status="in_progress",
                requester_id="user-net",
                requester_status="in_work",
                next_action_owner="support",
            )
        )
        session.add(
            Operation(
                operation_id=str(uuid.uuid4()),
                device_id=device_id,
                ticket_id=other_ticket_id,
                kind="tool",
                tool_name="diagnose.website",
                actor_role="support",
                trace_id=str(uuid.uuid4()),
                status="succeeded",
                queued_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                result_summary="HTTP 200 OK for another ticket",
            )
        )
        await session.flush()

        payload = await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="create")

        evidence_count = await session.scalar(
            select(func.count(TicketEvidenceItem.id)).where(TicketEvidenceItem.ticket_id == ticket_id)
        )
        assert evidence_count == 0
        assert payload["evidence"] == []
        assert payload["passport"]["source_operation_ids"] == []
        assert "HTTP 200 OK for another ticket" not in payload["passport"]["sections"].get("automated_checks", "")


@pytest.mark.asyncio
async def test_passport_repo_add_evidence_is_idempotent_by_source_and_fact(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    operation_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=str(uuid.uuid4()),
                title="Need evidence",
                description="Manual backend evidence test",
                status="in_progress",
                requester_id="user-evidence",
                requester_status="in_work",
                next_action_owner="support",
            )
        )
        repo = TicketPassportRepo(session)
        first = await repo.add_evidence(
            ticket_id=ticket_id,
            passport_id=None,
            evidence_type="operation_log",
            source_ref=f"operation:{operation_id}",
            source_kind="operation",
            source_id=operation_id,
            required_fact="operator_checks",
            section_key="operator_checks",
            title="Operation log",
            summary="Collected log",
            visibility="internal",
            verification_status="accepted",
            export_visibility="internal",
            metadata_json={"operation_status": "succeeded"},
            created_by="op1",
        )
        second = await repo.add_evidence(
            ticket_id=ticket_id,
            passport_id=None,
            evidence_type="operation_log",
            source_ref=f"operation:{operation_id}",
            source_kind="operation",
            source_id=operation_id,
            required_fact="operator_checks",
            section_key="operator_checks",
            title="Operation log duplicate",
            summary="Collected log duplicate",
            visibility="internal",
            verification_status="accepted",
            export_visibility="internal",
            metadata_json={"operation_status": "succeeded"},
            created_by="op1",
        )
        await session.flush()

        count = await session.scalar(
            select(func.count(TicketEvidenceItem.id)).where(TicketEvidenceItem.ticket_id == ticket_id)
        )

        assert first.id == second.id
        assert count == 1
        assert second.title == "Operation log"


@pytest.mark.asyncio
async def test_passport_refresh_creates_new_version_without_overwriting_previous(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        ticket = Ticket(
            ticket_id=ticket_id,
            device_id=device_id,
            title="Первый заголовок",
            description="Первое описание",
            status="in_progress",
            requester_id="user-refresh",
            requester_status="in_work",
            next_action_owner="support",
        )
        session.add(ticket)
        await session.flush()

        first = await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="create")
        ticket.description = "Описание после уточнения"
        second = await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="refresh")
        await session.flush()

        passports = (
            await session.execute(
                select(TicketResolutionPassport)
                .where(TicketResolutionPassport.ticket_id == ticket_id)
                .order_by(TicketResolutionPassport.version)
            )
        ).scalars().all()

        assert first["passport"]["version"] == 1
        assert second["passport"]["version"] == 2
        assert len(passports) == 2
        assert "Первое описание" in passports[0].problem_summary
        assert "Описание после уточнения" in passports[1].problem_summary
@pytest.mark.asyncio
async def test_passport_payload_marks_stale_after_new_evidence(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Stale passport",
                description="Initial passport",
                status="in_progress",
                requester_id="user-stale",
                requester_status="in_work",
                next_action_owner="support",
            )
        )
        first = await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="create")
        session.add(
            TicketEvidenceItem(
                ticket_id=ticket_id,
                evidence_type="manual_note",
                source_kind="manual",
                source_id="note-after-passport",
                required_fact="evidence",
                section_key="evidence",
                source_ref="manual:note-after-passport",
                title="Evidence after passport",
                summary="Added after generation",
                visibility="internal",
                verification_status="accepted",
                created_by="op1",
            )
        )
        await session.flush()

        payload = await TicketPassportService(session).get_payload(ticket_id)

        assert first["passport"]["stale"] is False
        assert payload["passport"]["stale"] is True
        assert payload["passport"]["source_payload"]["stale_reasons"] == ["evidence_changed"]


@pytest.mark.asyncio
async def test_passport_payload_marks_stale_after_new_worklog_source(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Stale passport source",
                description="Initial passport",
                status="in_progress",
                requester_id="user-stale-source",
                requester_status="in_work",
                next_action_owner="support",
            )
        )
        first = await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="create")
        session.add(
            TicketWorklog(
                ticket_id=ticket_id,
                actor_id="op1",
                spent_minutes=5,
                note="Checked source after passport generation.",
            )
        )
        await session.flush()

        payload = await TicketPassportService(session).get_payload(ticket_id)

        assert first["passport"]["stale"] is False
        assert payload["passport"]["stale"] is True
        assert "worklogs_changed" in payload["passport"]["source_payload"]["stale_reasons"]
        assert payload["passport"]["source_payload"]["current_source_counts"]["worklogs"] == 1


@pytest.mark.asyncio
async def test_passport_service_applies_reporting_policy_sections_and_evidence_package(test_engine):
    from sqlalchemy import delete

    from app.db.models import HelpdeskPolicyAudit, ReportingPolicy
    from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo

    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        await session.execute(delete(HelpdeskPolicyAudit).where(HelpdeskPolicyAudit.entity_type == "reporting_policies"))
        await session.execute(delete(ReportingPolicy))
        await HelpdeskPolicyRepo(session).publish_policy(
            kind="reporting",
            code="website_passport_reporting",
            title="Website passport reporting",
            scope_level="request_template",
            scope_ref="website_unavailable",
            config={
                "required_sections": ["problem", "evidence", "user_result"],
                "evidence_package": {
                    "include_action_log": False,
                    "include_related_objects": False,
                },
                "export_visibility": {
                    "hide_sections": ["internal_result", "operator_checks"],
                },
                "report_tags": ["critical_service", "diagnostics"],
            },
            actor_id="admin-test",
            actor_role="admin",
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Website unavailable",
                description="Cannot open reporting site",
                status="resolved",
                requester_id="user-net",
                requester_status="resolved",
                next_action_owner="support",
                resolution_code="fixed_remote",
                resolution_summary="DNS cache cleared",
                custom_fields={
                    "request_template": {
                        "key": "website_unavailable",
                        "ticket_type": "incident",
                    },
                },
            )
        )
        session.add(
            TicketEvent(
                ticket_id=ticket_id,
                device_id=device_id,
                agent_seq=None,
                event_type="status_changed",
                payload={"status": "resolved", "actor_id": "support-1"},
            )
        )
        session.add(
            TicketEvidenceItem(
                ticket_id=ticket_id,
                evidence_type="diagnostic_result",
                title="HTTP check",
                summary="HTTP 200 OK",
                visibility="internal",
                created_by="support-1",
            )
        )
        await session.flush()

        payload = await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="create")

    passport = payload["passport"]
    assert {"problem", "evidence", "user_result", "internal_result", "operator_checks"}.issubset(set(passport["sections"]))
    assert "HTTP 200 OK" in passport["sections"]["evidence"]
    assert passport["source_payload"]["report_tags"] == ["critical_service", "diagnostics"]
    assert passport["source_payload"]["reporting_policy"]["required_sections"] == ["problem", "evidence", "user_result"]
    assert payload["requirements"]["export_preview"]["visible_sections"] == ["problem", "evidence", "user_result"]
    assert payload["requirements"]["export_preview"]["hidden_sections"] == ["internal_result", "operator_checks"]
    assert payload["actions"] == []
    assert payload["related_objects"] == []


@pytest.mark.asyncio
async def test_passport_service_reports_missing_required_facts_and_export_preview(test_engine):
    from sqlalchemy import delete

    from app.db.models import HelpdeskPolicyAudit, ReportingPolicy

    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        await session.execute(delete(HelpdeskPolicyAudit).where(HelpdeskPolicyAudit.entity_type == "reporting_policies"))
        await session.execute(delete(ReportingPolicy))
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Website unavailable",
                description="Cannot open reporting site",
                status="in_progress",
                requester_id="user-net",
                requester_status="in_work",
                next_action_owner="support",
                custom_fields={
                    "request_template": {
                        "key": "website_unavailable",
                        "ticket_type": "incident",
                        "reporting_policy": {
                            "required_sections": ["problem", "evidence", "user_result", "internal_result"],
                            "export_visibility": {"hide_sections": ["internal_result", "operator_checks"]},
                            "require_official_passport": True,
                            "knowledge_draft_hints": {"enabled": True, "source": "passport"},
                        },
                    },
                },
            )
        )
        await session.flush()

        payload = await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="create")

    requirements = payload["requirements"]
    assert requirements["required_sections"] == ["problem", "evidence", "user_result", "internal_result"]
    assert requirements["require_official_passport"] is True
    assert requirements["blocking_missing_count"] == 3
    missing_by_key = {item["required_fact"]: item for item in requirements["missing_facts"]}
    assert missing_by_key["evidence"]["source"] == "ticket_evidence_items"
    assert missing_by_key["evidence"]["current_value"] is None
    assert missing_by_key["evidence"]["section_key"] == "evidence"
    assert missing_by_key["evidence"]["blocking_for_closure"] is True
    assert "diagnostic_result" in missing_by_key["evidence"]["accepted_evidence_types"]
    assert missing_by_key["evidence"]["candidate_count"] == 0
    assert missing_by_key["evidence"]["recommended_actions"]
    assert missing_by_key["evidence"]["requester_visible_label"] == "Доказательство решения"
    assert missing_by_key["user_result"]["source"] == "ticket.requester_resolution_summary"
    assert "resolution_summary" in missing_by_key["user_result"]["accepted_evidence_types"]
    assert missing_by_key["internal_result"]["source"] == "ticket.resolution_summary"
    assert requirements["export_preview"]["visible_sections"] == ["problem", "evidence", "user_result"]
    assert requirements["export_preview"]["hidden_sections"] == ["internal_result", "operator_checks"]
    assert requirements["knowledge_draft_hints"] == {"enabled": True, "source": "passport"}
    assert payload["passport"]["source_payload"]["passport_requirements"]["blocking_missing_count"] == 3


@pytest.mark.asyncio
async def test_passport_support_payload_keeps_sections_hidden_only_from_export(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Support-visible passport",
                description="Internal result must stay visible to support.",
                status="in_progress",
                requester_id="user-net",
                requester_status="in_work",
                next_action_owner="support",
                resolution_summary="Root cause fixed internally",
                requester_resolution_summary="Issue is fixed for user",
                custom_fields={
                    "request_template": {
                        "key": "support_visible_passport",
                        "ticket_type": "incident",
                        "reporting_policy": {
                            "required_sections": ["problem", "evidence", "user_result"],
                            "export_visibility": {"hide_sections": ["internal_result", "operator_checks"]},
                            "require_official_passport": True,
                        },
                    },
                },
            )
        )
        await session.flush()

        payload = await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="create")

    sections = payload["passport"]["sections"]
    assert sections["internal_result"] == "Root cause fixed internally"
    assert "operator_checks" in sections
    assert payload["requirements"]["export_preview"]["visible_sections"] == ["problem", "evidence", "user_result"]
    assert payload["requirements"]["export_preview"]["hidden_sections"] == ["internal_result", "operator_checks"]


@pytest.mark.asyncio
async def test_passport_missing_facts_include_source_candidates(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Website unavailable",
                description="Need evidence candidates",
                status="in_progress",
                requester_id="user-net",
                requester_status="in_work",
                next_action_owner="support",
                custom_fields={
                    "request_template": {
                        "key": "source_candidates_passport",
                        "ticket_type": "incident",
                        "reporting_policy": {
                            "required_sections": ["problem", "evidence", "user_result"],
                            "require_official_passport": True,
                        },
                    },
                },
            )
        )
        session.add(
            Artifact(
                artifact_id=artifact_id,
                storage_path=f"tickets/{ticket_id}/screen.png",
                original_name="screen.png",
                mime_type="image/png",
                size_bytes=128,
                sha256="a" * 64,
                kind="screenshot",
                device_id=device_id,
                ticket_id=ticket_id,
            )
        )
        session.add(
            TicketEvent(
                ticket_id=ticket_id,
                device_id=device_id,
                agent_seq=None,
                event_type="chat_message",
                payload={
                    "text": "У меня сайт всё ещё не открывается.",
                    "sender_role": "requester",
                    "visibility": "public",
                },
            )
        )
        await session.flush()

        payload = await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="create")

    missing_by_key = {item["required_fact"]: item for item in payload["requirements"]["missing_facts"]}
    assert missing_by_key["evidence"]["candidate_count"] == 1
    assert missing_by_key["evidence"]["source_candidates"][0]["candidate_id"] == f"artifact:{artifact_id}"
    assert missing_by_key["evidence"]["source_candidates"][0]["source_kind"] == "artifact"
    assert missing_by_key["user_result"]["candidate_count"] == 1
    assert missing_by_key["user_result"]["source_candidates"][0]["source_kind"] == "chat_message"
    assert missing_by_key["user_result"]["source_candidates"][0]["required_fact"] == "user_result"


@pytest.mark.asyncio
async def test_passport_requirements_use_reporting_policy_evidence_types(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Need screenshot evidence",
                description="Manual note must not satisfy screenshot-only policy",
                status="in_progress",
                requester_id="user-evidence-policy",
                requester_status="in_work",
                next_action_owner="support",
                custom_fields={
                    "request_template": {
                        "key": "screenshot_only_reporting",
                        "ticket_type": "incident",
                        "reporting_policy": {
                            "required_sections": ["evidence"],
                            "required_evidence_types": {"evidence": ["screenshot"]},
                        },
                    },
                },
            )
        )
        session.add(
            TicketEvidenceItem(
                ticket_id=ticket_id,
                evidence_type="manual_note",
                source_kind="manual",
                source_id="note-1",
                required_fact="evidence",
                section_key="evidence",
                source_ref="manual:note-1",
                title="Manual note",
                summary="Operator says a screenshot exists",
                visibility="internal",
                verification_status="accepted",
                created_by="support-1",
            )
        )
        session.add(
            Artifact(
                artifact_id=artifact_id,
                storage_path=f"tickets/{ticket_id}/requester-screen.png",
                original_name="requester-screen.png",
                mime_type="image/png",
                size_bytes=128,
                sha256="b" * 64,
                kind="screenshot",
                device_id=device_id,
                ticket_id=ticket_id,
            )
        )
        await session.flush()

        payload = await TicketPassportService(session).generate(ticket_id, actor_id="op1", mode="create")

    missing_by_key = {item["required_fact"]: item for item in payload["requirements"]["missing_facts"]}
    assert missing_by_key["evidence"]["accepted_evidence_types"] == ["screenshot"]
    assert missing_by_key["evidence"]["candidate_count"] == 1
    assert missing_by_key["evidence"]["source_candidates"][0]["candidate_id"] == f"artifact:{artifact_id}"
