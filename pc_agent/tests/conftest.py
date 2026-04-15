from __future__ import annotations

import sys
from pathlib import Path


PC_AGENT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PC_AGENT_ROOT.parent

for path in (str(PC_AGENT_ROOT), str(PROJECT_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)
