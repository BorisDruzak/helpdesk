#!/usr/bin/env python3
"""
Сборка ZIP-пакета модуля для загрузки на сервер (POST /api/modules/upload)
и установки на агенты (install_module_package).

Использование:
  python scripts/build_module_zip.py [module_name] [version]
  python scripts/build_module_zip.py screen 1.0.0
  python scripts/build_module_zip.py screen   # версия из manifest.json

Исходники: pc_agent/modules_packages/<module_name>/
Выход: dist/<module_name>-<version>.zip
"""

import hashlib
import json
import zipfile
from pathlib import Path


def _iter_package_include(repo_root: Path, include_spec: dict):
    source_raw = str(include_spec.get("source") or "").strip()
    target_raw = str(include_spec.get("target") or "").strip()
    if not source_raw or not target_raw:
        raise ValueError("package_include entries require source and target")

    source = (repo_root / source_raw).resolve()
    repo_resolved = repo_root.resolve()
    if repo_resolved not in source.parents and source != repo_resolved:
        raise ValueError(f"package_include source escapes repository: {source_raw}")
    if not source.is_dir():
        raise ValueError(f"package_include source directory not found: {source}")

    target = Path(target_raw)
    if target.is_absolute() or ".." in target.parts or any(part.startswith(".") for part in target.parts):
        raise ValueError(f"Invalid package_include target: {target_raw}")

    excluded = {str(item).strip() for item in include_spec.get("exclude") or [] if str(item).strip()}
    for path in source.rglob("*"):
        rel = path.relative_to(source)
        if any(part in excluded for part in rel.parts):
            continue
        if any(part == "__pycache__" or part.endswith(".pyc") for part in rel.parts):
            continue
        if any(part.startswith(".") for part in rel.parts):
            continue
        if path.is_file():
            yield path, (target / rel).as_posix()


def main():
    import sys
    repo_root = Path(__file__).resolve().parent.parent
    pc_agent = repo_root / "pc_agent"
    packages_dir = pc_agent / "modules_packages"
    dist_dir = repo_root / "dist"

    module_name = (sys.argv[1] if len(sys.argv) > 1 else "screen").strip()
    version_override = sys.argv[2].strip() if len(sys.argv) > 2 else None

    module_src = packages_dir / module_name
    if not module_src.is_dir():
        print(f"Ошибка: директория модуля не найдена: {module_src}")
        sys.exit(1)

    manifest_path = module_src / "manifest.json"
    if not manifest_path.is_file():
        print(f"Ошибка: manifest.json не найден в {module_src}")
        sys.exit(1)

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    version = version_override or manifest.get("module_version", "1.0.0")
    if version_override:
        manifest["module_version"] = version

    module_py = module_src / "module.py"
    if not module_py.is_file():
        print(f"Ошибка: module.py не найден в {module_src}")
        sys.exit(1)

    dist_dir.mkdir(parents=True, exist_ok=True)
    zip_name = f"{module_name}-{version}.zip"
    out_zip = dist_dir / zip_name

    zip_buffer = __import__("io").BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        z.write(module_py, arcname="module.py")
        for include_spec in manifest.get("package_include") or []:
            if not isinstance(include_spec, dict):
                raise ValueError("package_include entries must be objects")
            for source_file, arcname in _iter_package_include(repo_root, include_spec):
                z.write(source_file, arcname=arcname)

    data = zip_buffer.getvalue()
    out_zip.write_bytes(data)
    sha256 = hashlib.sha256(data).hexdigest()

    print("=== Пакет модуля готов ===")
    print(f"Модуль:   {module_name}")
    print(f"Версия:   {version}")
    print(f"ZIP:      {out_zip}")
    print(f"SHA256:   {sha256}")
    print()
    print("Загрузка на сервер:")
    print(f"  curl -X POST -F file=@{out_zip} -F module_name={module_name} -F version={version} http://localhost:8666/api/modules/upload")
    print()
    print("Установка на устройство (после загрузки):")
    print(f"  POST /api/devices/{{device_id}}/modules/install  body: {{\"module_name\": \"{module_name}\", \"version\": \"{version}\"}}")


if __name__ == "__main__":
    main()
