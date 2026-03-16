#!/usr/bin/env python3
"""
Скрипт для просмотра данных из SQLite базы данных агента.
Использование:
    python scripts/view_db.py --table outbox --limit 10
    python scripts/view_db.py --query "SELECT * FROM ticket_state WHERE status='open'"
    python scripts/view_db.py --stats
"""

import sqlite3
import json
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime


def get_db_path() -> Path:
    """Получает путь к базе данных."""
    agent_dir = Path(__file__).resolve().parent.parent
    db_path = agent_dir / "pc_agent" / "data" / "storage.db"
    return db_path


def format_timestamp(ts: Optional[float]) -> str:
    """Форматирует Unix timestamp в читаемый формат."""
    if ts is None:
        return "N/A"
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OSError):
        return str(ts)


def print_table_info(conn: sqlite3.Connection, table_name: str):
    """Выводит информацию о таблице."""
    cursor = conn.cursor()
    
    # Получаем схему таблицы
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    
    print(f"\n{'='*80}")
    print(f"Таблица: {table_name}")
    print(f"{'='*80}")
    print(f"{'Имя':<20} {'Тип':<15} {'NULL':<8} {'Default':<15} {'PK':<5}")
    print("-" * 80)
    for col in columns:
        cid, name, col_type, notnull, default, pk = col
        print(f"{name:<20} {col_type:<15} {'NO' if notnull else 'YES':<8} {str(default) if default else 'None':<15} {'YES' if pk else 'NO':<5}")
    
    # Количество записей
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    print(f"\nВсего записей: {count}")


def print_table_data(conn: sqlite3.Connection, table_name: str, limit: int = 10):
    """Выводит данные из таблицы."""
    cursor = conn.cursor()
    
    # Получаем все записи
    query = f"SELECT * FROM {table_name} LIMIT {limit}"
    cursor.execute(query)
    
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    
    if not rows:
        print(f"\nТаблица {table_name} пуста")
        return
    
    # Вычисляем ширину колонок
    col_widths = {}
    for col in columns:
        col_widths[col] = max(len(col), 15)
        for row in rows:
            val = str(row[columns.index(col)])[:50]  # Обрезаем длинные значения
            col_widths[col] = max(col_widths[col], len(val))
    
    # Заголовок
    header = " | ".join(col.ljust(col_widths[col]) for col in columns)
    print(f"\n{'='*len(header)}")
    print(header)
    print("-" * len(header))
    
    # Данные
    for row in rows:
        values = []
        for col in columns:
            val = row[columns.index(col)]
            if val is None:
                val_str = "NULL"
            elif isinstance(val, (int, float)):
                val_str = str(val)
            elif isinstance(val, str):
                # Пытаемся распарсить JSON
                if col.endswith("_json") or col == "payload_json" or col == "metadata_json":
                    try:
                        parsed = json.loads(val)
                        val_str = json.dumps(parsed, ensure_ascii=False)[:50]
                    except:
                        val_str = val[:50]
                else:
                    val_str = val[:50]
            else:
                val_str = str(val)[:50]
            
            # Форматируем timestamp
            if col.endswith("_at") or col == "created_at" or col == "updated_at" or col == "sent_at" or col == "last_run_at" or col == "next_run_at" or col == "expires_at":
                try:
                    ts = float(val_str)
                    val_str = format_timestamp(ts)
                except:
                    pass
            
            values.append(val_str.ljust(col_widths[col]))
        
        print(" | ".join(values))
    
    print(f"\nПоказано {len(rows)} из {limit} записей")


def print_stats(conn: sqlite3.Connection):
    """Выводит статистику по базе данных."""
    cursor = conn.cursor()
    
    print("\n" + "="*80)
    print("СТАТИСТИКА БАЗЫ ДАННЫХ")
    print("="*80)
    
    # Список всех таблиц
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    print("\n📊 Количество записей по таблицам:")
    print("-" * 80)
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {table:<30} {count:>10} записей")
    
    # Статистика по outbox
    if 'outbox' in tables:
        print("\n📦 Статистика по outbox:")
        print("-" * 80)
        cursor.execute("""
            SELECT 
                status,
                COUNT(*) as count,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM outbox), 2) as percent
            FROM outbox 
            GROUP BY status
            ORDER BY count DESC
        """)
        for row in cursor.fetchall():
            status, count, percent = row
            print(f"  {status:<20} {count:>6} ({percent:>5.1f}%)")
        
        # Статистика по ticket_id
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT ticket_id) as unique_tickets,
                COUNT(*) as total_events
            FROM outbox
        """)
        row = cursor.fetchone()
        if row:
            unique_tickets, total_events = row
            print(f"\n  Уникальных тикетов: {unique_tickets}")
            print(f"  Всего событий: {total_events}")
    
    # Статистика по ticket_state
    if 'ticket_state' in tables:
        print("\n🎫 Статистика по ticket_state:")
        print("-" * 80)
        cursor.execute("""
            SELECT 
                status,
                COUNT(*) as count
            FROM ticket_state 
            GROUP BY status
            ORDER BY count DESC
        """)
        for row in cursor.fetchall():
            status, count = row
            print(f"  {status:<20} {count:>6}")
    
    # Статистика по jobs
    if 'jobs' in tables:
        print("\n⚙️  Статистика по jobs:")
        print("-" * 80)
        cursor.execute("""
            SELECT 
                status,
                COUNT(*) as count
            FROM jobs 
            GROUP BY status
            ORDER BY count DESC
        """)
        for row in cursor.fetchall():
            status, count = row
            print(f"  {status:<20} {count:>6}")


def execute_query(conn: sqlite3.Connection, query: str):
    """Выполняет произвольный SQL запрос."""
    cursor = conn.cursor()
    
    try:
        cursor.execute(query)
        
        # Если это SELECT, выводим результаты
        if query.strip().upper().startswith('SELECT'):
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            
            if not rows:
                print("\nЗапрос не вернул результатов")
                return
            
            # Вычисляем ширину колонок
            col_widths = {}
            for col in columns:
                col_widths[col] = max(len(col), 10)
                for row in rows:
                    val = str(row[columns.index(col)])[:50]
                    col_widths[col] = max(col_widths[col], len(val))
            
            # Заголовок
            header = " | ".join(col.ljust(col_widths[col]) for col in columns)
            print(f"\n{header}")
            print("-" * len(header))
            
            # Данные
            for row in rows:
                values = []
                for col in columns:
                    val = row[columns.index(col)]
                    val_str = str(val) if val is not None else "NULL"
                    values.append(val_str[:50].ljust(col_widths[col]))
                print(" | ".join(values))
            
            print(f"\nНайдено записей: {len(rows)}")
        else:
            # Для не-SELECT запросов
            conn.commit()
            print(f"\n✅ Запрос выполнен успешно. Затронуто строк: {cursor.rowcount}")
    
    except sqlite3.Error as e:
        print(f"\n❌ Ошибка выполнения запроса: {e}")


def main():
    parser = argparse.ArgumentParser(description="Просмотр данных из SQLite базы данных агента")
    parser.add_argument("--table", "-t", help="Имя таблицы для просмотра")
    parser.add_argument("--limit", "-l", type=int, default=10, help="Лимит записей (по умолчанию: 10)")
    parser.add_argument("--query", "-q", help="Произвольный SQL запрос")
    parser.add_argument("--stats", "-s", action="store_true", help="Показать статистику по базе")
    parser.add_argument("--info", "-i", help="Показать информацию о таблице (схему)")
    parser.add_argument("--db-path", help="Путь к базе данных (по умолчанию: pc_agent/data/storage.db)")
    
    args = parser.parse_args()
    
    # Определяем путь к БД
    if args.db_path:
        db_path = Path(args.db_path)
    else:
        db_path = get_db_path()
    
    if not db_path.exists():
        print(f"❌ База данных не найдена: {db_path}")
        return 1
    
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        
        if args.stats:
            print_stats(conn)
        elif args.info:
            print_table_info(conn, args.info)
        elif args.query:
            execute_query(conn, args.query)
        elif args.table:
            print_table_data(conn, args.table, args.limit)
        else:
            # По умолчанию показываем статистику
            print_stats(conn)
        
        conn.close()
        return 0
    
    except sqlite3.Error as e:
        print(f"❌ Ошибка работы с базой данных: {e}")
        return 1
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return 1


if __name__ == "__main__":
    exit(main())

