from datetime import datetime, timezone

import pytest

from utils import id_generators

pytestmark = pytest.mark.no_db


def test_now_iso_uses_aware_utc_and_preserves_z_format(monkeypatch):
    class Clock:
        @staticmethod
        def now(tz):
            assert tz is timezone.utc
            return datetime(2026, 10, 1, 12, 34, 56, 123456, tzinfo=tz)

    monkeypatch.setattr(id_generators, "datetime", Clock)
    assert id_generators.now_iso() == "2026-10-01T12:34:56.123456Z"
