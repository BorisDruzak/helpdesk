from __future__ import annotations

from app.db.base import Base


def test_ticket_passport_tables_are_registered():
    tables = Base.metadata.tables

    assert "ticket_resolution_passports" in tables
    assert "ticket_evidence_items" in tables
    assert "ticket_action_log" in tables
    assert "ticket_approvals" in tables
    assert "ticket_related_objects" in tables

    passport = tables["ticket_resolution_passports"]
    assert {
        "ticket_id",
        "version",
        "status",
        "summary_source",
        "source_event_ids",
        "source_operation_ids",
    }.issubset(passport.columns.keys())

    evidence = tables["ticket_evidence_items"]
    assert {
        "ticket_id",
        "passport_id",
        "evidence_type",
        "source_ref",
        "visibility",
    }.issubset(evidence.columns.keys())
