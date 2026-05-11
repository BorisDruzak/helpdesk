import io
import json
from pathlib import Path
import zipfile

from pc_agent.core.loader import DynamicModuleLoader
from scripts.build_module_zip import _iter_package_include


def test_remote_assist_runtime_module_registers_and_exposes_factory():
    module_path = Path("pc_agent/modules_packages/remote_assist_runtime").resolve()

    loader = DynamicModuleLoader()
    instance = loader.load_module_from_path(
        "remote_assist_runtime",
        module_path,
        entrypoint="module:register",
    )

    assert instance.name == "remote_assist_runtime"
    assert hasattr(instance, "info")

    import module

    assert callable(module.create_remote_assist_thread)


def test_remote_assist_runtime_package_manifest_passes_server_preflight():
    repo_root = Path.cwd()
    module_path = repo_root / "pc_agent/modules_packages/remote_assist_runtime"
    manifest = json.loads((module_path / "manifest.json").read_text(encoding="utf-8"))

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.write(module_path / "module.py", arcname="module.py")
        included = []
        for include_spec in manifest.get("package_include") or []:
            for source_file, arcname in _iter_package_include(repo_root, include_spec):
                included.append(arcname)
                zf.write(source_file, arcname=arcname)

    assert "remote_assist_runtime_impl/thread.py" in included
    assert "remote_assist_runtime_impl/runtime_host.py" not in included
    assert zip_buffer.getvalue()
    assert manifest["manifest_version"] == 2
    assert manifest["module_api_version"] == "1.0.0"
    assert manifest["owner_scope"] == "platform"
    assert manifest["min_agent_version"] == "3.1.55"
