#!/usr/bin/env python3
"""
Read-only скрипт проверки реальной схемы БД против Alembic head.

Использование (из каталога server):
    python scripts/check_db_schema.py
    DATABASE_URL=postgresql+asyncpg://... python scripts/check_db_schema.py

Читает из БД только: alembic_version, information_schema (таблицы/колонки).
Сравнивает текущую ревизию в БД с head из миграций и выводит отчёт.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

# Добавляем корень server в path
SERVER_ROOT = Path(__file__).resolve().parent.parent
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

# Для sync подключения к Postgres используем psycopg2 URL
def get_sync_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        return ""
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


def get_db_revision(sync_url: str) -> str | None:
    """Читает текущую ревизию из alembic_version (read-only)."""
    try:
        import psycopg2
        from urllib.parse import urlparse
        parsed = urlparse(sync_url)
        conn = psycopg2.connect(
            host=parsed.hostname or "127.0.0.1",
            port=parsed.port or 5432,
            dbname=parsed.path.lstrip("/") if parsed.path else "pc_client",
            user=parsed.username,
            password=parsed.password,
            connect_timeout=5,
        )
        cur = conn.cursor()
        cur.execute("SELECT version_num FROM alembic_version")
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        print(f"Ошибка чтения alembic_version: {e}", file=sys.stderr)
        return None


def get_db_tables_columns(sync_url: str) -> dict[str, list[tuple[str, str]]]:
    """Читает из information_schema список таблиц и колонок (read-only)."""
    try:
        import psycopg2
        from urllib.parse import urlparse
        parsed = urlparse(sync_url)
        conn = psycopg2.connect(
            host=parsed.hostname or "127.0.0.1",
            port=parsed.port or 5432,
            dbname=parsed.path.lstrip("/") if parsed.path else "pc_client",
            user=parsed.username,
            password=parsed.password,
            connect_timeout=5,
        )
        cur = conn.cursor()
        cur.execute("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        result: dict[str, list[tuple[str, str]]] = {}
        for table, col, dtype in rows:
            result.setdefault(table, []).append((col, dtype))
        return result
    except Exception as e:
        print(f"Ошибка чтения information_schema: {e}", file=sys.stderr)
        return {}


def get_alembic_head() -> str | None:
    """Возвращает revision head из каталога миграций (без подключения к БД)."""
    versions_dir = SERVER_ROOT / "app" / "db" / "migrations" / "versions"
    if not versions_dir.is_dir():
        return None
    all_revisions: set[str] = set()
    down_revisions: set[str] = set()
    for f in versions_dir.glob("*.py"):
        if f.name == "env.py":
            continue
        content = f.read_text(encoding="utf-8", errors="ignore")
        m_rev = re.search(r'^\s*revision:\s*str\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        m_down = re.search(r'^\s*down_revision:\s*.*?(["\']([^"\']+)["\']|None)', content, re.MULTILINE | re.DOTALL)
        if m_rev:
            all_revisions.add(m_rev.group(1).strip())
        if m_down and m_down.group(2):
            down_revisions.add(m_down.group(2).strip())
    heads = [r for r in all_revisions if r not in down_revisions]
    # Корень (down_revision=None) не считается head; ищем единственный не-корневой head
    non_root_heads = [h for h in heads if h != "001"]
    if len(non_root_heads) == 1:
        return non_root_heads[0]
    if len(non_root_heads) > 1:
        return f"{non_root_heads!r} (несколько head)"
    if heads:
        return heads[0]  # только корень
    return None


def main() -> None:
    sync_url = get_sync_url()
    if not sync_url:
        print("DATABASE_URL не задан. Задайте переменную окружения.", file=sys.stderr)
        sys.exit(1)

    try:
        import psycopg2
    except ImportError:
        print("Установите psycopg2: pip install psycopg2-binary", file=sys.stderr)
        sys.exit(1)

    head = get_alembic_head()
    current = get_db_revision(sync_url)
    schema = get_db_tables_columns(sync_url)

    print("=== Проверка схемы БД (read-only) ===\n")
    print(f"Alembic head (из файлов):  {head or 'не найден'}")
    print(f"Текущая ревизия в БД:       {current or 'нет таблицы alembic_version'}")
    if current and head:
        if str(current) == str(head):
            print("Состояние: БД совпадает с head.")
        else:
            print("ВНИМАНИЕ: БД не на head. Выполните: alembic upgrade head")
    print()

    print("Таблицы в БД (public):")
    for table in sorted(schema.keys()):
        cols = schema[table]
        print(f"  {table} ({len(cols)} колонок)")
        for col, dtype in cols[:5]:
            print(f"    - {col}: {dtype}")
        if len(cols) > 5:
            print(f"    ... и ещё {len(cols) - 5}")
    print("Готово.")


if __name__ == "__main__":
    main()
