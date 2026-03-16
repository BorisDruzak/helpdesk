"""
Stage 5: Resolution policy — validation of resolution_code and root_cause.

Modes: warn (return warnings, do not block) | enforce (422 on violation).
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from loguru import logger


class TicketResolutionPolicyService:
    """Проверка качества резолюции при переходе в Resolved/Closed."""

    def __init__(
        self,
        mode: str = "warn",
        require_root_cause_priorities: str = "P1,P2",
    ):
        self.mode = mode  # warn | enforce
        self._require_rc_priorities = set(
            p.strip() for p in require_root_cause_priorities.split(",") if p.strip()
        )

    def validate(
        self,
        to_status: str,
        resolution_code: Optional[str],
        root_cause: Optional[str],
        priority: Optional[str],
        active_codes: List[str],
    ) -> Tuple[bool, List[str]]:
        """
        Validate resolution for transition to Resolved/Closed.
        Returns (ok, list of warning/error messages).
        If mode=warn: ok is always True, messages are warnings.
        If mode=enforce: ok is False and messages are errors when validation fails.
        """
        messages: List[str] = []
        if to_status not in ("resolved", "closed"):
            return (True, [])

        # Resolution code must be one of active codes
        if resolution_code:
            if resolution_code not in active_codes:
                messages.append(f"resolution_code '{resolution_code}' is not in active resolution codes")
        else:
            messages.append("resolution_code is required when resolving or closing")

        # P1/P2 require root_cause when enforce
        if priority and priority in self._require_rc_priorities:
            if not (root_cause and (root_cause or "").strip()):
                messages.append(f"root_cause is required for priority {priority}")

        if not messages:
            return (True, [])

        if self.mode == "enforce":
            return (False, messages)
        # warn: do not block
        return (True, messages)
