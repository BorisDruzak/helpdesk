from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


class FileTransferError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class FileTransferConfig:
    enabled: bool = False
    max_bytes: int = 25 * 1024 * 1024
    download_dir: Path | None = None


@dataclass
class _IncomingTransfer:
    transfer_id: str
    name: str
    size: int
    sha256: str | None
    temp_path: Path
    final_path: Path
    received: int = 0
    hasher: Any = None


class FileTransferBridge:
    def __init__(self, *, config: FileTransferConfig, send: Callable[[dict[str, Any]], None]):
        self.config = config
        self.send = send
        self.download_dir = Path(config.download_dir) if config.download_dir else default_download_dir()
        self._transfers: dict[str, _IncomingTransfer] = {}

    async def handle_message(self, message: dict[str, Any]) -> dict[str, Any]:
        message_type = str(message.get("type") or "")
        payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
        if message_type == "file.offer":
            return await self._offer(payload)
        if message_type == "file.chunk":
            return await self._chunk(payload)
        if message_type == "file.complete":
            return await self._complete(payload)
        if message_type == "file.cancel":
            return await self._cancel(payload)
        raise FileTransferError("FILE_MESSAGE_UNSUPPORTED", "File transfer message is unsupported")

    async def stop(self) -> None:
        for transfer in list(self._transfers.values()):
            await asyncio.to_thread(_unlink_quietly, transfer.temp_path)
        self._transfers.clear()

    async def _offer(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._assert_enabled()
        transfer_id = _safe_transfer_id(payload.get("transfer_id"))
        name = sanitize_filename(str(payload.get("name") or "remote-file.bin"))
        size = _parse_size(payload.get("size"))
        if size > self.config.max_bytes:
            raise FileTransferError("FILE_TOO_LARGE", "File exceeds Remote Assist transfer limit")
        sha256 = str(payload.get("sha256") or "").strip().lower() or None
        if sha256 and not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise FileTransferError("FILE_HASH_INVALID", "File checksum is invalid")

        await asyncio.to_thread(self.download_dir.mkdir, parents=True, exist_ok=True)
        final_path = await asyncio.to_thread(_unique_path, self.download_dir, name)
        temp_path = final_path.with_name(f".{final_path.name}.{transfer_id}.part")
        await asyncio.to_thread(temp_path.write_bytes, b"")
        transfer = _IncomingTransfer(
            transfer_id=transfer_id,
            name=final_path.name,
            size=size,
            sha256=sha256,
            temp_path=temp_path,
            final_path=final_path,
            hasher=hashlib.sha256(),
        )
        self._transfers[transfer_id] = transfer
        result = {"type": "file.accepted", "transfer_id": transfer_id, "name": transfer.name, "size": size}
        self.send({"type": "file.accepted", "payload": result})
        return result

    async def _chunk(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._assert_enabled()
        transfer = self._get_transfer(payload.get("transfer_id"))
        encoded = str(payload.get("data") or "")
        try:
            chunk = base64.b64decode(encoded.encode("ascii"), validate=True)
        except Exception as exc:
            raise FileTransferError("FILE_CHUNK_INVALID", "File chunk is not valid base64") from exc
        if not chunk:
            raise FileTransferError("FILE_CHUNK_INVALID", "File chunk is empty")
        if transfer.received + len(chunk) > transfer.size or transfer.received + len(chunk) > self.config.max_bytes:
            raise FileTransferError("FILE_TOO_LARGE", "File transfer exceeds declared size or policy limit")
        await asyncio.to_thread(_append_bytes, transfer.temp_path, chunk)
        transfer.received += len(chunk)
        transfer.hasher.update(chunk)
        result = {
            "type": "file.progress",
            "transfer_id": transfer.transfer_id,
            "received": transfer.received,
            "size": transfer.size,
        }
        self.send({"type": "file.progress", "payload": result})
        return result

    async def _complete(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._assert_enabled()
        transfer = self._get_transfer(payload.get("transfer_id"))
        if transfer.received != transfer.size:
            raise FileTransferError("FILE_INCOMPLETE", "File transfer completed before all bytes were received")
        digest = transfer.hasher.hexdigest()
        if transfer.sha256 and digest != transfer.sha256:
            raise FileTransferError("FILE_CHECKSUM_MISMATCH", "File checksum does not match")
        await asyncio.to_thread(os.replace, transfer.temp_path, transfer.final_path)
        self._transfers.pop(transfer.transfer_id, None)
        result = {
            "type": "file.saved",
            "transfer_id": transfer.transfer_id,
            "name": transfer.name,
            "size": transfer.size,
            "sha256": digest,
        }
        self.send({"type": "file.saved", "payload": result})
        return result

    async def _cancel(self, payload: dict[str, Any]) -> dict[str, Any]:
        transfer = self._transfers.pop(_safe_transfer_id(payload.get("transfer_id")), None)
        if transfer is not None:
            await asyncio.to_thread(_unlink_quietly, transfer.temp_path)
        return {"type": "file.canceled"}

    def _assert_enabled(self) -> None:
        if not self.config.enabled:
            raise FileTransferError("FILE_TRANSFER_DISABLED", "File transfer is disabled for this session")

    def _get_transfer(self, transfer_id: Any) -> _IncomingTransfer:
        safe_id = _safe_transfer_id(transfer_id)
        transfer = self._transfers.get(safe_id)
        if transfer is None:
            raise FileTransferError("FILE_TRANSFER_NOT_FOUND", "File transfer is not active")
        return transfer


def default_download_dir() -> Path:
    return Path.home() / "Downloads" / "Maria Remote Assist"


def sanitize_filename(name: str) -> str:
    base = Path(name.replace("\\", "/")).name.strip().strip(".")
    base = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", base)
    base = re.sub(r"\s+", " ", base).strip()
    return base[:180] or "remote-file.bin"


def _safe_transfer_id(value: Any) -> str:
    transfer_id = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", transfer_id):
        raise FileTransferError("FILE_TRANSFER_ID_INVALID", "File transfer id is invalid")
    return transfer_id


def _parse_size(value: Any) -> int:
    try:
        size = int(value)
    except (TypeError, ValueError) as exc:
        raise FileTransferError("FILE_SIZE_INVALID", "File size is invalid") from exc
    if size < 0:
        raise FileTransferError("FILE_SIZE_INVALID", "File size is invalid")
    return size


def _unique_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    for index in range(1, 1000):
        next_candidate = directory / f"{stem} ({index}){suffix}"
        if not next_candidate.exists():
            return next_candidate
    raise FileTransferError("FILE_NAME_CONFLICT", "Could not allocate a destination filename")


def _append_bytes(path: Path, chunk: bytes) -> None:
    with path.open("ab") as handle:
        handle.write(chunk)


def _unlink_quietly(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass
