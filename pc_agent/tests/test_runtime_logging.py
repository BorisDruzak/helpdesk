from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loguru import logger

from pc_agent.core.runtime_logging import RuntimeLogBuffer, configure_runtime_logging, read_log_tail, format_log_tail


class _LoggingConfig:
    level = "INFO"
    file = "logs/agent.log"
    console_level = "WARNING"
    rotation = "1 MB"
    retention = "3 days"
    compression = "zip"
    enqueue = False


def test_configure_runtime_logging_creates_log_file(tmp_path: Path):
    buffer = RuntimeLogBuffer(limit=20)
    runtime = configure_runtime_logging(
        data_root=tmp_path,
        logging_config=_LoggingConfig(),
        role_name="agent",
        memory_buffer=buffer,
    )

    logger.info("runtime-log-line")

    log_file = Path(runtime["file"])
    assert log_file.exists()
    text = log_file.read_text(encoding="utf-8")
    assert "runtime-log-line" in text
    assert any("runtime-log-line" in line for line in buffer.snapshot(10))


def test_read_log_tail_and_format(tmp_path: Path):
    log_path = tmp_path / "sample.log"
    log_path.write_text("a\nb\nc\nd\n", encoding="utf-8")

    tail = read_log_tail(log_path, lines=2)
    assert tail == ["c\n", "d\n"]
    assert format_log_tail(tail) == "c\nd"
