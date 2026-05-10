from access_control.catalog import get_role_permission_codes
import config
from remote_assist.ice import build_remote_assist_ice_servers
from remote_assist.policy import (
    get_remote_assist_mode_permission,
    is_remote_assist_mode_enabled,
)
from remote_assist.service import issue_short_lived_token, verify_token_hash
from web_api.support_handlers import _timeline_event_label, _timeline_event_text


def test_remote_assist_tokens_are_hashed_and_validated() -> None:
    issued = issue_short_lived_token()

    assert issued.token
    assert issued.token not in issued.token_hash
    assert verify_token_hash(issued.token, issued.token_hash)
    assert not verify_token_hash("wrong-token", issued.token_hash)


def test_support_role_can_request_and_view_remote_assist() -> None:
    permissions = set(get_role_permission_codes("support"))

    assert "remote_assist.request" in permissions
    assert "remote_assist.view" in permissions
    assert "remote_assist.control" in permissions
    assert "remote_assist.file_transfer" not in permissions
    assert "remote_assist.elevated" not in permissions
    assert "remote_assist.unattended" not in permissions


def test_remote_assist_mode_permissions_are_explicit() -> None:
    assert get_remote_assist_mode_permission("view_only") == "remote_assist.request"
    assert get_remote_assist_mode_permission("interactive_control") == "remote_assist.control"
    assert get_remote_assist_mode_permission("file_transfer") == "remote_assist.file_transfer"
    assert get_remote_assist_mode_permission("elevated_admin") == "remote_assist.elevated"


def test_post_mvp_remote_assist_modes_are_disabled_by_default() -> None:
    assert is_remote_assist_mode_enabled("view_only")
    assert not is_remote_assist_mode_enabled("interactive_control")
    assert not is_remote_assist_mode_enabled("file_transfer")
    assert not is_remote_assist_mode_enabled("elevated_admin")


def test_turn_credentials_are_generated_from_server_secret(monkeypatch) -> None:
    monkeypatch.setattr(
        config,
        "REMOTE_ASSIST_ICE_SERVERS",
        [{"urls": ["turn:turn.example.local:3478?transport=udp"], "credential_mode": "time_limited_hmac", "ttl_seconds": 3600}],
    )
    monkeypatch.setattr(config, "REMOTE_ASSIST_TURN_SHARED_SECRET", "server-only-secret")

    servers = build_remote_assist_ice_servers(now=1000)

    assert servers[0]["urls"] == ["turn:turn.example.local:3478?transport=udp"]
    assert servers[0]["username"] == "4600:remote-assist"
    assert servers[0]["credential"]
    assert servers[0]["credential"] != "server-only-secret"
    assert "credential_mode" not in servers[0]


def test_remote_assist_control_events_have_timeline_system_messages() -> None:
    assert _timeline_event_label("remote_assist_control_enabled") == "Удалённое управление включено"
    assert _timeline_event_text("remote_assist_control_enabled", {}) == "Оператор включил управление мышью и клавиатурой."
    assert _timeline_event_text("remote_assist_control_disabled", {}) == "Оператор выключил управление мышью и клавиатурой."
    assert _timeline_event_text("remote_assist_control_rejected", {}) == "Команда удалённого управления отклонена агентом."
