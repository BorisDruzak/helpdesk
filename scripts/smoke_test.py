#!/usr/bin/env python3
"""
Быстрая проверка после изменений сервера/фронта.
Запуск: из корня репозитория, после перезапуска сервера.
  python scripts/smoke_test.py
  BASE_URL=https://example.test:9443 python scripts/smoke_test.py
"""
import os
import ssl
import sys
import urllib.parse

import urllib.request
import urllib.error

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8666")
INSECURE_TLS = str(os.environ.get("SMOKE_INSECURE_TLS") or os.environ.get("REMOTE_SMOKE_INSECURE_TLS") or "").lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def _ssl_context_for(url: str) -> ssl.SSLContext | None:
    if not INSECURE_TLS:
        return None
    if urllib.parse.urlparse(url).scheme.lower() != "https":
        return None
    return ssl._create_unverified_context()


def get(url: str, expected_status: int = 200) -> bool:
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5, context=_ssl_context_for(url)) as r:
            if r.status != expected_status:
                print(f"  FAIL {url} -> {r.status} (expected {expected_status})")
                return False
            print(f"  OK   {url} -> {r.status}")
            return True
    except urllib.error.HTTPError as e:
        print(f"  FAIL {url} -> HTTP {e.code}")
        return False
    except Exception as e:
        print(f"  FAIL {url} -> {e}")
        return False


def main():
    print(f"Smoke test: {BASE_URL}\n")
    ok = True
    ok &= get(f"{BASE_URL}/api/health")
    # Опционально: скачивание артефакта по ticket_id (если есть тестовые данные)
    ticket_id = os.environ.get("SMOKE_TICKET_ID")
    artifact_id = os.environ.get("SMOKE_ARTIFACT_ID")
    if ticket_id and artifact_id:
        ok &= get(f"{BASE_URL}/api/artifacts/{artifact_id}/download?ticket_id={ticket_id}", expected_status=200)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
