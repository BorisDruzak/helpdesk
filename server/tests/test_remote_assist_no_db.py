import pytest

from access_control.catalog import get_role_permission_codes
import config
from remote_assist.features import build_remote_assist_features, wants_clipboard_auto_sync, wants_file_transfer
from remote_assist.ice import build_remote_assist_ice_servers
from remote_assist.media import build_remote_assist_media_options
from remote_assist.policy import (
    get_remote_assist_mode_permission,
    get_remote_assist_mode_policy,
    is_remote_assist_mode_enabled,
)
from remote_assist.service import issue_short_lived_token, verify_token_hash
from web_api.support_handlers import _timeline_event_label, _timeline_event_text

pytestmark = pytest.mark.no_db


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
    assert "remote_assist.file_transfer" in permissions
    assert "remote_assist.elevated" not in permissions
    assert "remote_assist.unattended" not in permissions


def test_remote_assist_mode_permissions_are_explicit() -> None:
    assert get_remote_assist_mode_permission("view_only") == "remote_assist.request"
    assert get_remote_assist_mode_permission("interactive_control") == "remote_assist.control"
    assert get_remote_assist_mode_permission("file_transfer") == "remote_assist.file_transfer"
    assert get_remote_assist_mode_permission("elevated_admin") == "remote_assist.elevated"


def test_elevated_admin_mode_is_control_capable_but_policy_gated() -> None:
    policy = get_remote_assist_mode_policy("elevated_admin")

    assert policy is not None
    assert policy.control_channel is True
    assert policy.elevated is True


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


def test_remote_assist_media_options_default_to_balanced_profile() -> None:
    options = build_remote_assist_media_options({})

    assert options == {
        "quality_profile": "balanced",
        "max_width": 1600,
        "max_height": 900,
        "fps": 8,
        "monitor_id": "primary",
    }


def test_remote_assist_media_options_include_smooth_profile() -> None:
    options = build_remote_assist_media_options({"quality_profile": "smooth"})

    assert options == {
        "quality_profile": "smooth",
        "max_width": 1280,
        "max_height": 720,
        "fps": 15,
        "monitor_id": "primary",
    }


def test_remote_assist_media_options_clamp_custom_values() -> None:
    options = build_remote_assist_media_options(
        {
            "quality_profile": "sharp",
            "max_width": 9999,
            "max_height": 9999,
            "fps": 120,
            "monitor_id": "primary",
        }
    )

    assert options["quality_profile"] == "sharp"
    assert options["max_width"] == 1920
    assert options["max_height"] == 1080
    assert options["fps"] == 15
    assert options["monitor_id"] == "primary"


def test_remote_assist_clipboard_features_are_policy_gated(monkeypatch) -> None:
    assert wants_clipboard_auto_sync({"clipboard_auto_sync": True})
    monkeypatch.setattr(config, "REMOTE_ASSIST_CLIPBOARD_ENABLED", False)
    assert build_remote_assist_features({"clipboard_auto_sync": True})["clipboard_auto_sync"] is False
    monkeypatch.setattr(config, "REMOTE_ASSIST_CLIPBOARD_ENABLED", True)
    features = build_remote_assist_features({"clipboard_auto_sync": True})
    assert features["clipboard_auto_sync"] is True
    assert features["clipboard_max_bytes"] == config.REMOTE_ASSIST_CLIPBOARD_MAX_BYTES


def test_remote_assist_file_transfer_features_are_policy_gated(monkeypatch) -> None:
    assert wants_file_transfer({"file_transfer": True})

    monkeypatch.setattr(config, "REMOTE_ASSIST_FILE_TRANSFER_ENABLED", False)
    assert build_remote_assist_features({"file_transfer": True})["file_transfer"] is False

    monkeypatch.setattr(config, "REMOTE_ASSIST_FILE_TRANSFER_ENABLED", True)
    monkeypatch.setattr(config, "REMOTE_ASSIST_FILE_TRANSFER_MAX_BYTES", 12345)
    features = build_remote_assist_features({"file_transfer": True})
    assert features["file_transfer"] is True
    assert features["file_transfer_max_bytes"] == 12345


def test_remote_assist_default_features_can_combine_view_only_clipboard_and_files(monkeypatch) -> None:
    monkeypatch.setattr(config, "REMOTE_ASSIST_CLIPBOARD_ENABLED", True)
    monkeypatch.setattr(config, "REMOTE_ASSIST_FILE_TRANSFER_ENABLED", True)

    features = build_remote_assist_features({"clipboard_auto_sync": True, "file_transfer": True})

    assert features["clipboard_auto_sync"] is True
    assert features["file_transfer"] is True


def test_remote_assist_control_events_have_timeline_system_messages() -> None:
    assert _timeline_event_label("remote_assist_control_enabled") == "Удалённое управление включено"
    assert _timeline_event_text("remote_assist_control_enabled", {}) == "Оператор включил управление мышью и клавиатурой."
    assert _timeline_event_text("remote_assist_control_disabled", {}) == "Оператор выключил управление мышью и клавиатурой."
    assert _timeline_event_text("remote_assist_control_rejected", {}) == "Команда удалённого управления отклонена агентом."
    assert _timeline_event_text("remote_assist_clipboard_sync_enabled", {}) == "Автосинхронизация буфера обмена включена."
    assert _timeline_event_label("remote_assist_file_transfer_completed") == "Файл передан"
    assert _timeline_event_text("remote_assist_file_transfer_completed", {"name": "report.txt"}) == "Файл передан на устройство: report.txt."
