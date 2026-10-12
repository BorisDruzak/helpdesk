import importlib.util
import pytest

pytestmark = pytest.mark.no_db


def test_context_batch_has_six_distinct_steps_and_partial_is_not_success():
    assert importlib.util.find_spec("app.services.endpoint_tool_run_service") is not None
    from app.services.endpoint_tool_run_service import collection_requests, batch_status
    requests = collection_requests()
    assert len(requests) == 6
    assert {r.profile for r in requests if r.kind == "context_collection"} == {"baseline_v1", "health_v1", "network_v1", "inventory_v1", "session_v1"}
    assert [r.kind for r in requests].count("diagnostic") == 1
    assert batch_status(["succeeded"]*5+["failed"]) == "partial"
    assert batch_status(["succeeded"]*5+["expired"]) == "partial"
    assert batch_status(["succeeded"]*6) == "succeeded"
    assert batch_status(["succeeded"]*5+["create_pending"]) == "running"
    assert batch_status(["failed"]*6) == "failed"
