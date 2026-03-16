"""
Stage 5: Metrics — unified filters (period, queue, priority) and response format.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

from loguru import logger


class TicketMetricsService:
    """Единые фильтры периода/очереди и нормализация ответа API."""

    def __init__(
        self,
        default_days: int = 30,
        max_days: int = 365,
    ):
        self.default_days = default_days
        self.max_days = max_days

    def parse_period(
        self,
        days: Optional[int] = None,
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
    ) -> tuple[datetime, datetime]:
        """Return (period_start, period_end) as timezone-aware UTC datetimes."""
        now = datetime.now(timezone.utc)
        if period_start and period_end:
            try:
                start = datetime.fromisoformat(period_start.replace("Z", "+00:00"))
                end = datetime.fromisoformat(period_end.replace("Z", "+00:00"))
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                if end.tzinfo is None:
                    end = end.replace(tzinfo=timezone.utc)
                return (start, end)
            except (ValueError, TypeError):
                pass
        d = self.default_days
        if days is not None:
            d = min(max(1, int(days)), self.max_days)
        end = now
        start = now - timedelta(days=d)
        return (start, end)

    def normalize_response(
        self,
        metric: str,
        period_start: datetime,
        period_end: datetime,
        filters: Dict[str, Any],
        data: Any,
    ) -> Dict[str, Any]:
        """Единый формат ответа: metric, period, filters, data."""
        return {
            "metric": metric,
            "period": {
                "start": period_start.isoformat(),
                "end": period_end.isoformat(),
            },
            "filters": filters,
            "data": data,
        }
