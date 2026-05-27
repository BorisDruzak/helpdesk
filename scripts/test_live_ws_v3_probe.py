import scripts.live_ws_v3_probe as probe


def test_mixed_batch_default_device_event_is_side_effect_neutral():
    items = probe._build_mixed_batch_items(
        run_id="p1-test-run",
        ticket_id="ticket-1",
        valid_agent_seq=10,
        duplicate_agent_seq=9,
        valid_device_seq=11,
        invalid_seq_base=910000,
        valid_device_event="probe_device_event",
    )

    valid_device = next(
        item for item in items if item["payload"]["outbox_id"].endswith("-valid-device")
    )

    assert valid_device.get("ticket_id") is None
    assert valid_device["payload"]["device_seq"] == 11
    assert "agent_seq" not in valid_device["payload"]
    assert valid_device["payload"]["event"]["event"] == "probe_device_event"
    assert valid_device["payload"]["event"]["probe_run_id"] == "p1-test-run"


def test_mixed_batch_parser_defaults_to_probe_device_event():
    parser = probe.build_parser()

    args = parser.parse_args(
        [
            "mixed-batch",
            "--ticket-id",
            "ticket-1",
            "--run-id",
            "p1-test-run",
            "--valid-agent-seq",
            "10",
            "--duplicate-agent-seq",
            "9",
            "--valid-device-seq",
            "11",
        ]
    )

    assert args.command == "mixed-batch"
    assert args.valid_device_event == "probe_device_event"
