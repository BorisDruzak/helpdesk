import subprocess
import sys
from pathlib import Path

import scripts.verify_workspace as verify


def test_verify_workspace_tracks_harness_text_files() -> None:
    assert ".mdc" in verify.TEXT_SUFFIXES
    assert ".ps1" in verify.TEXT_SUFFIXES
    assert ".cursor" not in verify.SKIP_DIRS


def test_verify_workspace_module_guard_flags_impl_and_ignores_dynamic(tmp_path: Path) -> None:
    workspace = tmp_path / "pc_client"
    impl_dir = workspace / "pc_agent" / "modules" / "impl"
    dynamic_dir = workspace / "pc_agent" / "modules" / "dynamic"
    packages_dir = workspace / "pc_agent" / "modules_packages" / "sample"
    impl_dir.mkdir(parents=True)
    dynamic_dir.mkdir(parents=True)
    packages_dir.mkdir(parents=True)

    invalid_source = """
from typing import Dict, Any
from pc_agent.modules.base_module import BaseCollector
from pc_agent.core.registry import exposed_tool


class ExampleCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "example"

    async def collect(self) -> Dict[str, Any]:
        return {}

    @exposed_tool(name="example.run", description="Run example", risk_level="safe_readonly")
    async def run(self, **kwargs) -> Dict[str, Any]:
        return {"ok": True}
"""
    valid_source = invalid_source.replace(
        'return {"ok": True}',
        'with self.trace_span("tool.entry", details={"tool_name": "example.run"}):\n            return {"ok": True}',
    )

    (impl_dir / "example.py").write_text(invalid_source, encoding="utf-8")
    (dynamic_dir / "scratch.py").write_text(invalid_source, encoding="utf-8")
    (packages_dir / "module.py").write_text(valid_source, encoding="utf-8")

    failures = verify.run_module_observer_guard(workspace)

    assert len(failures) == 1
    assert "pc_agent\\modules\\impl\\example.py" in failures[0]


def test_run_docs_links_returns_no_failures_on_success(monkeypatch, tmp_path: Path) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout=b"ok\n", stderr=b"")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)

    assert verify.run_docs_links(tmp_path) == []


def test_run_docs_links_returns_output_on_failure(monkeypatch, tmp_path: Path) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 1, stdout=b"broken\n", stderr=b"details\n")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)

    assert verify.run_docs_links(tmp_path) == ["broken", "details"]


def test_run_docs_links_calls_docs_inventory_check(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)

    verify.run_docs_links(tmp_path)

    assert calls == [[sys.executable, str(tmp_path / "scripts" / "docs_inventory.py"), "--check-links"]]
