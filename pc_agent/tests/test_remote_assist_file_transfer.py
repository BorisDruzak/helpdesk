from __future__ import annotations

import asyncio
import base64
import hashlib

import pytest

from pc_agent.remote_assist.file_transfer import FileTransferBridge, FileTransferConfig, FileTransferError


def test_file_transfer_saves_chunked_file_with_sanitized_name(tmp_path) -> None:
    async def scenario() -> None:
        sent: list[dict] = []
        bridge = FileTransferBridge(
            config=FileTransferConfig(enabled=True, max_bytes=1024, download_dir=tmp_path),
            send=sent.append,
        )
        content = b"hello remote file"
        digest = hashlib.sha256(content).hexdigest()
        await bridge.handle_message(
            {
                "type": "file.offer",
                "payload": {
                    "transfer_id": "transfer-1",
                    "name": "..\\unsafe/report.txt",
                    "size": len(content),
                    "sha256": digest,
                },
            }
        )
        await bridge.handle_message(
            {
                "type": "file.chunk",
                "payload": {
                    "transfer_id": "transfer-1",
                    "seq": 0,
                    "data": base64.b64encode(content).decode("ascii"),
                },
            }
        )
        result = await bridge.handle_message({"type": "file.complete", "payload": {"transfer_id": "transfer-1"}})

        assert result["type"] == "file.saved"
        assert result["name"] == "report.txt"
        assert (tmp_path / "report.txt").read_bytes() == content
        assert sent[-1]["type"] == "file.saved"
        assert sent[-1]["payload"]["name"] == "report.txt"

    asyncio.run(scenario())


def test_file_transfer_rejects_files_over_policy_limit(tmp_path) -> None:
    async def scenario() -> None:
        bridge = FileTransferBridge(
            config=FileTransferConfig(enabled=True, max_bytes=4, download_dir=tmp_path),
            send=lambda _message: None,
        )
        with pytest.raises(FileTransferError) as excinfo:
            await bridge.handle_message(
                {
                    "type": "file.offer",
                    "payload": {"transfer_id": "transfer-1", "name": "too-large.bin", "size": 5},
                }
            )
        assert excinfo.value.code == "FILE_TOO_LARGE"

    asyncio.run(scenario())
