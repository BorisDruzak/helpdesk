import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from app.db.models import Base
from auth.middleware import auth_middleware
from routes import setup_routes


pytestmark = pytest.mark.no_db


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/knowledge/suggest"),
        ("POST", "/api/web/knowledge/search"),
        ("GET", "/api/web/knowledge/ai/providers"),
        ("GET", "/api/web/admin/knowledge/audience-rules"),
        ("POST", "/api/web/support/tickets/ticket-1/kb_links"),
        ("POST", "/api/tickets/ticket-1/kb_links"),
        ("GET", "/api/tickets/ticket-1/kb_links"),
        ("DELETE", "/api/tickets/ticket-1/kb_links/1"),
    ],
)
async def test_local_knowledge_route_is_not_registered(method: str, path: str):
    app = web.Application(middlewares=[auth_middleware])
    setup_routes(app)

    async with TestClient(TestServer(app)) as client:
        response = await client.request(method, path)

    assert response.status == 404


def test_active_orm_metadata_has_no_local_knowledge_tables_or_dangling_foreign_keys():
    table_names = set(Base.metadata.tables)

    assert "knowledge_items" not in table_names
    assert "problem_known_error_links" not in table_names
    assert Base.metadata.sorted_tables
