#!/usr/bin/env python3
"""
Скрипт для сборки модуля ping_check в ZIP архив.
"""

import zipfile
import hashlib
import json
from pathlib import Path

MODULE_DIR = Path(__file__).parent
OUT_ZIP_PATH = MODULE_DIR / "ping_check-1.0.0.zip"

def main():
    """Собирает модуль в ZIP архив."""
    print(f"Building module from: {MODULE_DIR}")
    
    # Проверяем наличие файлов
    manifest_path = MODULE_DIR / "manifest.json"
    module_path = MODULE_DIR / "module.py"
    
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.json not found: {manifest_path}")
    if not module_path.exists():
        raise FileNotFoundError(f"module.py not found: {module_path}")
    
    # Создаём ZIP архив
    with zipfile.ZipFile(OUT_ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(manifest_path, arcname="manifest.json")
        z.write(module_path, arcname="module.py")
    
    # Вычисляем SHA256
    zip_data = OUT_ZIP_PATH.read_bytes()
    sha256 = hashlib.sha256(zip_data).hexdigest()
    
    # Читаем manifest для информации
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
    
    print("\n=== Module Package Ready ===")
    print(f"Module: {manifest['module_name']}")
    print(f"Version: {manifest['module_version']}")
    print(f"ZIP File: {OUT_ZIP_PATH}")
    print(f"SHA256: {sha256}")
    print(f"Size: {len(zip_data)} bytes")
    print("\nYou can upload this ZIP file to the server via /api/modules/upload")

if __name__ == "__main__":
    main()


