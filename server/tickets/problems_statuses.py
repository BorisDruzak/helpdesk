"""
Stage 7: Problem FSM — New -> Investigating -> Mitigated -> Resolved -> Closed.
Разрешён Resolved -> Investigating (reopen).
"""
from __future__ import annotations

from typing import Tuple, Optional

PROBLEM_STATUSES = (
    "New",
    "Investigating",
    "Mitigated",
    "Resolved",
    "Closed",
)

PROBLEM_TRANSITIONS = {
    "New": ["Investigating"],
    "Investigating": ["Mitigated", "Resolved"],
    "Mitigated": ["Investigating", "Resolved"],
    "Resolved": ["Closed", "Investigating"],  # reopen
    "Closed": [],
}


def normalize_problem_status(raw: str) -> Tuple[Optional[str], bool]:
    if not raw or not isinstance(raw, str):
        return None, False
    s = raw.strip()
    if not s:
        return None, False
    key = s
    if s.lower() in (st.lower() for st in PROBLEM_STATUSES):
        for st in PROBLEM_STATUSES:
            if st.lower() == s.lower():
                return st, (st != s)
    if s in PROBLEM_STATUSES:
        return s, False
    return None, False


def validate_problem_transition(from_status: str, to_status: str) -> bool:
    """Проверяет разрешён ли переход для support/admin."""
    allowed = PROBLEM_TRANSITIONS.get(from_status, [])
    return to_status in allowed
