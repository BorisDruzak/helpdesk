from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from scripts import run_mutation_smoke


def _write_registry(workspace: Path, payload: dict) -> Path:
    registry_path = workspace / "quality" / "mutation_smoke_targets.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(payload), encoding="utf-8")
    return registry_path


def test_run_mutation_smoke_reports_killed_mutant_and_restores_temp_file(tmp_path, monkeypatch):
    module_path = tmp_path / "shared" / "redaction.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text("VALUE = True\n", encoding="utf-8")
    test_path = tmp_path / "server" / "tests" / "test_contract.py"
    test_path.parent.mkdir(parents=True)
    test_path.write_text("def test_contract():\n    pass\n", encoding="utf-8")
    registry_path = _write_registry(
        tmp_path,
        {
            "schema": "pc_client.mutation_smoke.v1",
            "mutants": [
                {
                    "id": "redaction.boolean_flip",
                    "file": "shared/redaction.py",
                    "replacements": [{"old": "VALUE = True", "new": "VALUE = False"}],
                    "tests": ["server/tests/test_contract.py::test_contract"],
                }
            ],
        },
    )
    seen_mutant_text: list[str] = []

    def fake_prepare_workspace(workspace: Path, temp_workspace: Path) -> None:
        (temp_workspace / "shared").mkdir(parents=True)
        (temp_workspace / "server" / "tests").mkdir(parents=True)
        (temp_workspace / "shared" / "redaction.py").write_text(module_path.read_text(encoding="utf-8"), encoding="utf-8")
        (temp_workspace / "server" / "tests" / "test_contract.py").write_text(
            test_path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    def fake_run_pytest(workspace: Path, tests: list[str], timeout_seconds: float):
        seen_mutant_text.append((workspace / "shared" / "redaction.py").read_text(encoding="utf-8"))
        return SimpleNamespace(returncode=1, stdout="failed as expected", stderr="")

    monkeypatch.setattr(run_mutation_smoke, "_prepare_temp_workspace", fake_prepare_workspace)
    monkeypatch.setattr(run_mutation_smoke, "_run_pytest", fake_run_pytest)

    report = run_mutation_smoke.run_mutation_smoke(tmp_path, registry_path=registry_path)

    assert report["status"] == "ok"
    assert report["mutants"][0]["status"] == "killed"
    assert seen_mutant_text == ["VALUE = False\n"]
    assert module_path.read_text(encoding="utf-8") == "VALUE = True\n"


def test_run_mutation_smoke_fails_surviving_mutant(tmp_path, monkeypatch):
    module_path = tmp_path / "shared" / "redaction.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text("VALUE = True\n", encoding="utf-8")
    test_path = tmp_path / "server" / "tests" / "test_contract.py"
    test_path.parent.mkdir(parents=True)
    test_path.write_text("def test_contract():\n    pass\n", encoding="utf-8")
    registry_path = _write_registry(
        tmp_path,
        {
            "schema": "pc_client.mutation_smoke.v1",
            "mutants": [
                {
                    "id": "redaction.boolean_flip",
                    "file": "shared/redaction.py",
                    "replacements": [{"old": "VALUE = True", "new": "VALUE = False"}],
                    "tests": ["server/tests/test_contract.py::test_contract"],
                }
            ],
        },
    )

    def fake_prepare_workspace(workspace: Path, temp_workspace: Path) -> None:
        (temp_workspace / "shared").mkdir(parents=True)
        (temp_workspace / "server" / "tests").mkdir(parents=True)
        (temp_workspace / "shared" / "redaction.py").write_text(module_path.read_text(encoding="utf-8"), encoding="utf-8")
        (temp_workspace / "server" / "tests" / "test_contract.py").write_text(
            test_path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    monkeypatch.setattr(run_mutation_smoke, "_prepare_temp_workspace", fake_prepare_workspace)

    def fake_run_pytest(workspace: Path, tests: list[str], timeout_seconds: float):
        return SimpleNamespace(returncode=0, stdout="survived", stderr="")

    monkeypatch.setattr(run_mutation_smoke, "_run_pytest", fake_run_pytest)

    report = run_mutation_smoke.run_mutation_smoke(tmp_path, registry_path=registry_path)

    assert report["status"] == "fail"
    assert report["mutants"][0]["status"] == "survived"
