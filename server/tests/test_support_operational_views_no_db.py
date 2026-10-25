import pytest

from tickets.smart_views import matches_smart_view, normalize_smart_view_id

pytestmark = pytest.mark.no_db


@pytest.mark.parametrize("view,matching,excluded", [
    ("open", ["new", "queued", "assigned", "in_progress", "waiting_on_approval"], ["resolved", "closed", "canceled"]),
    ("new", ["new", "queued"], ["in_progress", "resolved", "closed"]),
    ("waiting", ["waiting_on_user", "waiting_on_vendor", "waiting_on_internal_team"], ["new", "in_progress", "closed", "waiting_on_approval"]),
    ("completed", ["resolved", "closed", "canceled"], ["new", "in_progress", "waiting_on_user"]),
])
def test_operational_views_filter_on_server_before_limit(view, matching, excluded):
    assert normalize_smart_view_id(view) == view
    for status in matching:
        assert matches_smart_view({"status": status}, view)
    for status in excluded:
        assert not matches_smart_view({"status": status}, view)
