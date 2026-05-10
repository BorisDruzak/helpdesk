from pc_agent.remote_assist.webrtc_client import (
    RemoteAssistWebRTCClient,
    _normalize_feature_options,
    _normalize_media_options,
    candidate_summary,
    count_sdp_candidates,
    is_clipboard_channel_message,
    is_file_transfer_channel_message,
)
from pc_agent.remote_assist.tls import build_remote_assist_ssl_context, tls_error_hint


def test_count_sdp_candidates_counts_only_candidate_lines() -> None:
    sdp = "\r\n".join(
        [
            "v=0",
            "a=group:BUNDLE 0",
            "a=candidate:1 1 udp 2130706431 192.168.100.11 50321 typ host",
            "a=end-of-candidates",
            "a=candidate:2 1 udp 1694498815 192.168.100.11 50322 typ srflx raddr 0.0.0.0 rport 0",
        ]
    )

    assert count_sdp_candidates(sdp) == 2


def test_candidate_summary_omits_address_and_port() -> None:
    summary = candidate_summary("candidate:1 1 udp 2130706431 192.168.100.11 50321 typ host")

    assert summary == {"type": "host", "protocol": "udp"}


def test_normalize_media_options_clamps_agent_capture_limits() -> None:
    assert _normalize_media_options({"max_width": 9999, "max_height": 9999, "fps": 120}) == {
        "max_width": 1920,
        "max_height": 1080,
        "fps": 15,
    }


def test_normalize_feature_options_clamps_clipboard_limits() -> None:
    assert _normalize_feature_options({"clipboard_auto_sync": True, "clipboard_max_bytes": 99_999_999, "file_transfer": True, "file_transfer_max_bytes": 999_999_999}) == {
        "clipboard_auto_sync": True,
        "clipboard_max_bytes": 1024 * 1024,
        "file_transfer": True,
        "file_transfer_max_bytes": 100 * 1024 * 1024,
    }


def test_clipboard_channel_routing_accepts_enable_alias() -> None:
    assert is_clipboard_channel_message("clipboard_enable") is True
    assert is_clipboard_channel_message("clipboard_disable") is True
    assert is_clipboard_channel_message("clipboard.update") is True
    assert is_clipboard_channel_message("control_enable") is False


def test_file_transfer_channel_routing_accepts_file_messages() -> None:
    assert is_file_transfer_channel_message("file.offer") is True
    assert is_file_transfer_channel_message("file.chunk") is True
    assert is_file_transfer_channel_message("file.complete") is True
    assert is_file_transfer_channel_message("clipboard.update") is False


def test_elevated_admin_mode_enables_elevated_input_controller() -> None:
    client = RemoteAssistWebRTCClient(signaling_url="ws://127.0.0.1/ws", token="token", mode="elevated_admin")

    assert client.input_controller.mode_enabled is True
    assert client.input_controller.elevated is True


def test_remote_assist_tls_context_only_for_secure_urls() -> None:
    assert build_remote_assist_ssl_context("ws://192.168.100.17/ws/remote-assist/session") is None
    assert build_remote_assist_ssl_context("wss://192.168.100.17/ws/remote-assist/session") is not None


def test_tls_error_hint_mentions_agent_ca_configuration() -> None:
    message = tls_error_hint(RuntimeError("SSLCertVerificationError: CERTIFICATE_VERIFY_FAILED"))

    assert "PC_AGENT_TLS_CA_FILE" in message
    assert "Trusted Root Certification Authorities" in message
