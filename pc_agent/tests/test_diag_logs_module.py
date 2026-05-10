import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "pc_agent"))

from pc_agent.modules.impl.diag_logs import _agent_app_log_sources


def test_agent_app_log_sources_use_runtime_logs_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("PC_AGENT_DATA_DIR", str(tmp_path))

    sources = _agent_app_log_sources()

    assert sources == [str((tmp_path / "logs").resolve())]
