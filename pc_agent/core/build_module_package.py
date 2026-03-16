import zipfile
import hashlib
import base64
from pathlib import Path
import io

MODULE_DIR = Path("/var/chat_bot/pc_client/pc_agent/core/hello_module")
OUT_ZIP_PATH = Path("/var/chat_bot/pc_client/pc_agent/core/module.zip")  # Указываем полный путь к файлу

def main():
    # Создаём ZIP в памяти или в файл
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(MODULE_DIR / "manifest.json", arcname="manifest.json")
        z.write(MODULE_DIR / "module.py", arcname="module.py")
    
    # Получаем байты из буфера
    data = zip_buffer.getvalue()
    
    # Опционально: сохраняем в файл
    OUT_ZIP_PATH.write_bytes(data)
    
    sha256 = hashlib.sha256(data).hexdigest()
    b64 = base64.b64encode(data).decode()

    print("=== MODULE PACKAGE READY ===")
    print(f"ZIP FILE: {OUT_ZIP_PATH}")
    print(f"SHA256: {sha256}")
    print("\nPACKAGE_B64:\n")
    print(b64)

if __name__ == "__main__":
    main()