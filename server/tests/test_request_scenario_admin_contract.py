"""Fast P3 HTTP query/body boundary checks without PostgreSQL."""
import pytest
from pydantic import ValidationError

from web_api import request_scenario_admin_handlers as handlers
from web_api.dto.request_scenario_admin import RevisionInput
from app.repos.request_scenario_repo import ScenarioAdminError

pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
async def test_http_catalog_string_pagination_reaches_repository(monkeypatch):
    captured = {}
    async def run(request, operation):
        class Repo:
            async def catalog_view(self, **kwargs):
                captured.update(kwargs)
        await operation(Repo())
    monkeypatch.setattr(handlers, "_run", run)
    from auth.context import AuthContext, AuthType
    class Request(dict):
        query = {"offset": "100", "limit": "25"}
    request = Request(auth_context=AuthContext(actor_id="admin-test", actor_role="admin", auth_type=AuthType.UI_TOKEN))
    await handlers.handle_scenario_catalog(request)
    assert captured["offset"] == 100 and captured["limit"] == 25


@pytest.mark.parametrize("query", [{"offset": "-1"}, {"limit": "501"}, {"limit": "bad"}, {"status": "invalid"}, {"actor_id": "evil"}])
def test_catalog_query_rejects_unknown_or_out_of_bounds_values(query):
    with pytest.raises(ValidationError):
        handlers.CatalogQuery.model_validate_strings(query)


@pytest.mark.parametrize("revision", [True, "1", 0, -1])
def test_revision_input_is_actual_positive_integer(revision):
    with pytest.raises(ValidationError):
        RevisionInput(revision=revision)


@pytest.mark.asyncio
async def test_body_streaming_accepts_chunks_and_rejects_oversize():
    class Content:
        def __init__(self, chunks):
            self.chunks = chunks
        async def iter_chunked(self, size):
            for chunk in self.chunks:
                yield chunk
    class Request:
        def __init__(self, chunks):
            self.content = Content(chunks)
    payload = await handlers._payload(Request([b'{"revision":', b'1}']), RevisionInput)
    assert payload.revision == 1
    with pytest.raises(ScenarioAdminError) as exc:
        await handlers._payload(Request([b"x" * 65536] * 17), RevisionInput)
    assert exc.value.status == 413


@pytest.mark.asyncio
async def test_error_filter_includes_published_scenario_with_invalid_new_draft():
    from app.db.request_scenario_models import RequestStudioDraft, RequestStudioScenario
    from app.repos.request_scenario_repo import RequestScenarioRepo
    row = RequestStudioScenario(id="scenario", scenario_key="printer", service_code="workplace", offering_full_code="workplace.printer", title="Printer", description="", published_version_id="version", archived=False, enabled=False)
    draft = RequestStudioDraft(scenario_id=row.id, definition={}, revision=2, updated_by="admin-test")
    class Result:
        def all(self): return [(row, draft)]
    class Session:
        async def execute(self, statement): return Result()
    class Catalog:
        async def list_services(self): return []
        async def list_offerings(self): return []
    repo = RequestScenarioRepo(Session(), None)
    repo.catalog = Catalog()
    async def categories(): return []
    repo.categories = categories
    result = await repo.catalog_view(status="errors")
    assert result["total"] == 1 and result["scenarios"][0]["id"] == row.id
    assert result["scenarios"][0]["status"] == "published"
