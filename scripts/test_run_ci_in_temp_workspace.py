from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    path = Path(__file__).with_name("run_ci_in_temp_workspace.py")
    spec = importlib.util.spec_from_file_location("run_ci_in_temp_workspace_test_subject", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_temp_workspace_runs_full_ci_with_bounded_parallel_workers(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_module()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    temp_root = tmp_path / "temp-ci"
    commands: list[list[str]] = []

    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: module.argparse.Namespace(
            workspace=workspace,
            commit="deadbeef",
            python=sys.executable,
            keep_workspace=True,
        ),
    )
    monkeypatch.setattr(module, "detect_commit", lambda _workspace, _commit: "deadbeef")
    monkeypatch.setattr(module.tempfile, "mkdtemp", lambda **_kwargs: str(temp_root))

    def fake_run(command: list[str], *, cwd: Path, env=None) -> None:
        commands.append(command)
        if command[:2] == ["git", "clone"]:
            (temp_root / "checkout").mkdir(parents=True)
        if len(command) > 1 and command[1].endswith("run_ci_suite.py"):
            (temp_root / "checkout" / "artifacts" / "ci" / "deadbeef").mkdir(
                parents=True
            )

    monkeypatch.setattr(module, "run", fake_run)

    module.main()

    ci_command = next(command for command in commands if command[1].endswith("run_ci_suite.py"))
    assert ci_command[-5:] == ["--commit", "deadbeef", "--parallel", "--max-workers", "2"]
