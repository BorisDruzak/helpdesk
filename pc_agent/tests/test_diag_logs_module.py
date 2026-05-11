import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "pc_agent"))

from pc_agent.modules.impl.diag_logs import _agent_app_log_sources
from pc_agent.core.registry import ModuleRegistry
from pc_agent.modules.impl.diag_logs import DiagLogsModule


def test_agent_app_log_sources_use_runtime_logs_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("PC_AGENT_DATA_DIR", str(tmp_path))

    sources = _agent_app_log_sources()

    assert sources == [str((tmp_path / "logs").resolve())]


def test_diag_logs_collect_exposes_endpoint_logs_evidence_metadata():
    registry = ModuleRegistry()
    registry.reset()
    registry.register(DiagLogsModule())

    tool = registry.get_tool("diag.logs.collect")

    assert tool is not None
    spec = tool["spec"]
    assert spec["execution"]["target"] == "agent_builtin"
    assert spec["deployment"]["install_required_on_agent"] is False
    assert spec["deployment"]["package_type"] == "builtin"
    assert spec["evidence"] == {
        "produces_evidence": True,
        "kind": "logs.bundle",
        "domain": "logs",
        "perspective": "endpoint",
        "passport_eligible": True,
    }
    assert spec["artifacts"] == {"may_produce_artifacts": True, "artifact_kinds": ["logs_zip"]}
