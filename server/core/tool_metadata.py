"""Server-side alias for the shared tool metadata contract."""

import sys
from pathlib import Path

try:
    from shared.tool_contracts import CanonicalRiskLevel as PolicyRiskLevel
    from shared.tool_contracts import ToolMetadata
except ModuleNotFoundError:  # pragma: no cover - cwd-dependent import fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from shared.tool_contracts import CanonicalRiskLevel as PolicyRiskLevel
    from shared.tool_contracts import ToolMetadata

__all__ = ["PolicyRiskLevel", "ToolMetadata"]
