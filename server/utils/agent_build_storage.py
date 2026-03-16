"""
Storage utilities for agent build ZIP files.

Agent builds are used for remote self-update of pc_agent.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import AsyncIterator, Tuple

from loguru import logger


async def save_agent_build_zip_from_stream(
    stream: AsyncIterator[bytes],
    *,
    target: str,
    channel: str,
    version: str,
    storage_dir: Path,
    max_size: int,
    chunk_size: int = 8192,
) -> Tuple[str, str, int]:
    """
    Save agent build ZIP to disk atomically from an async byte stream.

    Layout:
      {storage_dir}/{target}/{channel}/{version}/agent.zip

    Returns:
      (storage_path, sha256_hex, size_bytes) where storage_path is relative to storage_dir.
    """
    build_dir = storage_dir / target / channel / version
    build_dir.mkdir(parents=True, exist_ok=True)

    temp_path = build_dir / "agent.zip.tmp"
    final_path = build_dir / "agent.zip"

    sha256_hash = hashlib.sha256()
    total_size = 0

    try:
        with open(temp_path, "wb") as f:
            async for chunk in stream:
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > max_size:
                    raise ValueError(f"File size {total_size} exceeds maximum {max_size}")
                sha256_hash.update(chunk)
                f.write(chunk)

        sha256_hex = sha256_hash.hexdigest()
        temp_path.rename(final_path)

        storage_path = f"{target}/{channel}/{version}/agent.zip"
        logger.info(
            f"Agent build saved: {storage_path} (sha256={sha256_hex[:16]}..., size={total_size})"
        )
        return storage_path, sha256_hex, total_size
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise

