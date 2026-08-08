from __future__ import annotations

from types import SimpleNamespace

import pytest

from tickets.knowledge_provider import clean_knowledge_text, project_legacy_knowledge_attempts


pytestmark = pytest.mark.no_db


def test_clean_knowledge_text_handles_empty_values() -> None:
    assert clean_knowledge_text(None) is None
    assert clean_knowledge_text("  ") is None
    assert clean_knowledge_text(" T-1 ") == "T-1"


def test_legacy_attempt_projection_rejects_unsanitized_rows() -> None:
    assert project_legacy_knowledge_attempts([SimpleNamespace(result="viewed"), {"result": "viewed"}]) == []
