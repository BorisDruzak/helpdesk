"""Shared Observer integrity checker result contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence, TypeVar

from app.repos.observer_integrity_repo import ObserverIntegrityEventInput


@dataclass(slots=True)
class ObserverIntegrityCheckResult:
    source: str
    events: list[ObserverIntegrityEventInput] = field(default_factory=list)
    complete: bool = True
    scanned_count: int = 0
    limit: int | None = None


T = TypeVar("T")


def limit_plus_one_window(rows: Sequence[T], *, limit: int) -> tuple[list[T], bool]:
    """Return the processable window and whether the underlying query fit in it."""
    return list(rows[:limit]), len(rows) <= limit
