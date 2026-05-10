from pc_agent.remote_assist.webrtc_client import (
    _normalize_feature_options,
    _normalize_media_options,
    candidate_summary,
    count_sdp_candidates,
    is_clipboard_channel_message,
)


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
    assert _normalize_feature_options({"clipboard_auto_sync": True, "clipboard_max_bytes": 99_999_999}) == {
        "clipboard_auto_sync": True,
        "clipboard_max_bytes": 1024 * 1024,
    }


def test_clipboard_channel_routing_accepts_enable_alias() -> None:
    assert is_clipboard_channel_message("clipboard_enable") is True
    assert is_clipboard_channel_message("clipboard_disable") is True
    assert is_clipboard_channel_message("clipboard.update") is True
    assert is_clipboard_channel_message("control_enable") is False
