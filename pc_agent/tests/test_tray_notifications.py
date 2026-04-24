from pc_agent.ui_gui.tray_notifications import tray_notification_from_event


def test_tray_notification_for_token_limit():
    notification = tray_notification_from_event(
        {
            "event_type": "connection_rejected",
            "data": {"error_code": "TOKEN_LIMIT_EXCEEDED", "message": "too many"},
        }
    )

    assert notification == ("Maria Agent: токены устройства", "too many")


def test_tray_notification_for_fingerprint_mismatch():
    notification = tray_notification_from_event(
        {
            "event_type": "connection_rejected",
            "data": {"error_code": "DEVICE_FINGERPRINT_MISMATCH"},
        }
    )

    assert notification is not None
    assert "проверка устройства" in notification[0]


def test_tray_notification_ignores_regular_events():
    assert tray_notification_from_event({"event_type": "connection_state", "data": {}}) is None
