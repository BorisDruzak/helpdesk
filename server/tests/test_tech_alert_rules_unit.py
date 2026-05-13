import pytest

from tech.handlers import _build_alerts_from_metrics

pytestmark = pytest.mark.no_db


def _kinds(alerts):
    return {a["kind"] for a in alerts}


def test_alert_rules_empty_metrics():
    alerts = _build_alerts_from_metrics(
        stale_count=0,
        stale_sec=300,
        old_pending=0,
        invalid_recent=0,
        invalid_burst_count=5,
        invalid_burst_window_sec=600,
        update_waiting_confirm=0,
        queued_stuck=0,
        sent_stuck=0,
        in_progress_stuck=0,
        outbox_backlog=10,
        outbox_backlog_warn=100,
        watchdog_states={"operation_watchdog": True, "ticket_sla_watchdog": True, "ticket_auto_close_watchdog": True},
    )
    assert alerts == []


@pytest.mark.parametrize(
    "kwargs,expected_kind",
    [
        ({"stale_count": 2}, "device_stale"),
        ({"old_pending": 1}, "connection_request_stuck_pending"),
        ({"invalid_recent": 7}, "invalid_token_burst"),
        ({"update_waiting_confirm": 1}, "update_waiting_handshake_confirm_too_long"),
        ({"queued_stuck": 1}, "operation_queued_too_long"),
        ({"sent_stuck": 1}, "operation_sent_too_long"),
        ({"in_progress_stuck": 1}, "operation_in_progress_too_long"),
        ({"outbox_backlog": 150}, "outbox_backlog_high"),
        ({"env_uuid_duplicate_groups": 2}, "inventory_env_uuid_duplicates"),
        ({"devices_without_location": 3}, "inventory_devices_without_location"),
    ],
)
def test_alert_rule_each_kind(kwargs, expected_kind):
    params = dict(
        stale_count=0,
        stale_sec=300,
        old_pending=0,
        invalid_recent=0,
        invalid_burst_count=5,
        invalid_burst_window_sec=600,
        update_waiting_confirm=0,
        queued_stuck=0,
        sent_stuck=0,
        in_progress_stuck=0,
        outbox_backlog=0,
        outbox_backlog_warn=100,
        watchdog_states={"operation_watchdog": True, "ticket_sla_watchdog": True, "ticket_auto_close_watchdog": True},
    )
    params.update(kwargs)
    alerts = _build_alerts_from_metrics(**params)
    assert expected_kind in _kinds(alerts)


def test_watchdog_not_running_alert():
    alerts = _build_alerts_from_metrics(
        stale_count=0,
        stale_sec=300,
        old_pending=0,
        invalid_recent=0,
        invalid_burst_count=5,
        invalid_burst_window_sec=600,
        update_waiting_confirm=0,
        queued_stuck=0,
        sent_stuck=0,
        in_progress_stuck=0,
        outbox_backlog=0,
        outbox_backlog_warn=100,
        watchdog_states={"operation_watchdog": False, "ticket_sla_watchdog": True, "ticket_auto_close_watchdog": False},
    )
    assert "watchdog_not_running" in _kinds(alerts)
