from pc_agent.remote_assist.webrtc_client import candidate_summary, count_sdp_candidates


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
