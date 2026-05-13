#!/usr/bin/env python3
"""
Очистка токенов авторизации и флага отклонения на локальном агенте.

Использование:
  python scripts/clear_local_agent_tokens.py [--data-dir PATH]

- Деактивирует все записи в таблице auth_tokens (storage.db).
- Удаляет файл connection_rejected.flag (чтобы можно было снова запросить одобрение).

Для именованного инстанса (manage_local_agent):
  python scripts/clear_local_agent_tokens.py --data-dir .local-agent/instances/notoken/data

Если после нажатия «Отклонить» в админке агент больше не подключается:
  выполните этот скрипт с --data-dir вашего инстанса — флаг будет удалён, можно снова
  запросить одобрение.

Если ошибка «Cannot connect to host localhost:8666» или «Удаленный компьютер отклонил»:
  сервер может быть на другом хосте. Задайте переменные окружения перед запуском агента:
  PC_AGENT_WS_URL=wss://192.168.100.17:9443/ws  PC_AGENT_API_URL=https://192.168.100.17:9443/api
  (или укажите URL вашего сервера). Либо используйте scripts/manage_local_agent.py start notoken --gui,
  он подставляет нужные URL для тестового сервера.

Где хранится токен на агенте:
  В SQLite: <data_dir>/storage.db, таблица auth_tokens (поле token, device_id, is_active).
  Пример: .local-agent/instances/notoken/data/storage.db
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from pc_agent.core.runtime_paths import resolve_data_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Очистить токены агента и флаг отклонения")
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Путь к data-директории агента (по умолчанию: из env или LOCALAPPDATA)",
    )
    args = parser.parse_args()
    data_root = resolve_data_root(cli_value=args.data_dir)
    data_root.mkdir(parents=True, exist_ok=True)

    db_path = data_root / "storage.db"
    flag_path = data_root / "connection_rejected.flag"

    cleared_tokens = 0
    if db_path.exists():
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.execute("UPDATE auth_tokens SET is_active = 0 WHERE is_active = 1")
            cleared_tokens = cur.rowcount
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Ошибка при очистке auth_tokens: {e}", file=sys.stderr)
            return 1
    else:
        print(f"БД не найдена: {db_path}")

    if flag_path.exists():
        try:
            flag_path.unlink()
            print("Файл connection_rejected.flag удалён.")
        except Exception as e:
            print(f"Не удалось удалить флаг: {e}", file=sys.stderr)
    else:
        print("Файл connection_rejected.flag отсутствовал.")

    print(f"Деактивировано записей в auth_tokens: {cleared_tokens}. data_root={data_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
