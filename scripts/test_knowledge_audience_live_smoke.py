import pytest

import scripts.knowledge_audience_live_smoke as smoke


pytestmark = pytest.mark.no_db


def test_knowledge_audience_live_smoke_space_is_rag_eligible_for_ask_checks() -> None:
    payload = smoke.knowledge_space_payload("phase5-knowledge-test", "Phase 5 Knowledge Test")

    assert payload["code"] == "phase5-knowledge-test"
    assert payload["title"] == "Phase 5 Knowledge Test"
    assert payload["visibility"] == "requester"
    assert payload["lifecycle_status"] == "active"
    assert payload["allow_rag"] is True
