import sqlite3
from datetime import datetime


class DatabaseUpgrader:
    """Обновление базы данных для добавления согласования и подписания"""
    
    def __init__(self):
        self.db_path = r"D:\python_ex\acti_v2\db\documents.db"
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
    
    def upgrade_database(self):
        """Основной метод обновления"""
        print("🔄 Начинаем обновление базы данных...")
        
        try:
            cursor = self.connection.cursor()
            
            # Проверяем текущую структуру таблицы
            cursor.execute("PRAGMA table_info(documents)")
            existing_columns = [row[1] for row in cursor.fetchall()]
            
            # Список всех необходимых колонок для добавления
            new_columns = {
                # Основные поля
                'created_date': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'modified_date': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'filename': 'TEXT',
                'filepath': 'TEXT',
                'status': 'TEXT DEFAULT "Действующий"',
                'type_doc': 'TEXT DEFAULT "Распоряжение"',
                'reg_number': 'TEXT DEFAULT ""',
                'reg_date': 'DATE DEFAULT (date("now"))',
                'executor_id': 'INTEGER',
                'theme_id': 'INTEGER',
                'title': 'TEXT DEFAULT ""',
                
                # Блок публикации
                'gazette_number': 'TEXT DEFAULT ""',
                'published_where': 'TEXT DEFAULT ""',
                'published_date': 'DATE',
                
                # Блок контроля
                'responsible_executor_id': 'INTEGER',
                'control_date': 'DATE',
                'execution_result': 'BOOLEAN',
                'removed_from_control': 'BOOLEAN DEFAULT 0',
                
                # Блок списания
                'case_number': 'TEXT DEFAULT ""',
                'volume_number': 'TEXT DEFAULT ""',
                'sheets': 'TEXT DEFAULT ""',
                
                # Согласование
                'approval_executor_id': 'INTEGER',
                'approval_status': 'TEXT DEFAULT "Не требуется"',
                'approval_date': 'DATE',
                'approval_comment': 'TEXT',
                
                # Подписание  
                'signing_executor_id': 'INTEGER',
                'signing_status': 'TEXT DEFAULT "Не требуется"',
                'signing_date': 'DATE', 
                'signing_comment': 'TEXT'
            }
            
            # Добавляем отсутствующие колонки
            added_columns = 0
            for column_name, column_type in new_columns.items():
                if column_name not in existing_columns:
                    try:
                        sql = f"ALTER TABLE documents ADD COLUMN {column_name} {column_type}"
                        cursor.execute(sql)
                        print(f"✅ Добавлена колонка: {column_name}")
                        added_columns += 1
                    except Exception as e:
                        print(f"❌ Ошибка добавления колонки {column_name}: {e}")
                else:
                    print(f"ℹ️ Колонка {column_name} уже существует")
            
            # Создаем индексы для производительности
            indexes_to_create = [
                "CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status)",
                "CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(type_doc)",
                "CREATE INDEX IF NOT EXISTS idx_documents_reg_date ON documents(reg_date)",
                "CREATE INDEX IF NOT EXISTS idx_documents_executor ON documents(executor_id)",
                "CREATE INDEX IF NOT EXISTS idx_documents_theme ON documents(theme_id)",
                "CREATE INDEX IF NOT EXISTS idx_approval_executor ON documents(approval_executor_id)",
                "CREATE INDEX IF NOT EXISTS idx_approval_status ON documents(approval_status)",
                "CREATE INDEX IF NOT EXISTS idx_signing_executor ON documents(signing_executor_id)",
                "CREATE INDEX IF NOT EXISTS idx_signing_status ON documents(signing_status)"
            ]
            
            for index_sql in indexes_to_create:
                try:
                    cursor.execute(index_sql)
                    print(f"✅ Создан индекс")
                except Exception as e:
                    print(f"❌ Ошибка создания индекса: {e}")
            
            # Создаем таблицы исполнителей и тем, если их нет
            self.create_auxiliary_tables(cursor)
            
            self.connection.commit()
            
            print(f"🎉 Обновление завершено! Добавлено колонок: {added_columns}")
            
            # Показываем текущую структуру
            self.show_table_structure()
            
        except Exception as e:
            print(f"❌ Критическая ошибка обновления: {e}")
            self.connection.rollback()
            raise e
    
    def create_auxiliary_tables(self, cursor):
        """Создание вспомогательных таблиц если их нет"""
        try:
            # Таблица исполнителей
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS executors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    position TEXT,
                    department TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица тем
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS themes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            print("✅ Вспомогательные таблицы проверены/созданы")
            
        except Exception as e:
            print(f"❌ Ошибка создания вспомогательных таблиц: {e}")
            raise
    
    def show_table_structure(self):
        """Показать текущую структуру таблицы"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("PRAGMA table_info(documents)")
            columns = cursor.fetchall()
            
            print("\n📋 ТЕКУЩАЯ СТРУКТУРА ТАБЛИЦЫ DOCUMENTS:")
            print("=" * 60)
            for col in columns:
                print(f"  {col[1]:<25} | {col[2]:<15} | {'NOT NULL' if col[3] else 'NULL':<8} | {col[4] or 'No default'}")
            print("=" * 60)
            
        except Exception as e:
            print(f"❌ Ошибка получения структуры: {e}")
    
    def close(self):
        """Закрыть соединение"""
        if self.connection:
            self.connection.close()


def upgrade_database_for_approval_signing(db_path=r"D:\python_ex\acti_v2\db\documents.db"):
    """Главная функция для обновления БД"""
    upgrader = None
    try:
        print("🚀 ЗАПУСК ОБНОВЛЕНИЯ БАЗЫ ДАННЫХ")
        print("Добавляем поддержку согласования и подписания документов...")
        
        upgrader = DatabaseUpgrader()
        upgrader.upgrade_database()
        
        print("\n✅ ОБНОВЛЕНИЕ БАЗЫ ДАННЫХ ЗАВЕРШЕНО УСПЕШНО!")
        print("Теперь доступны функции согласования и подписания документов")
        
    except Exception as e:
        print(f"\n❌ ОШИБКА ОБНОВЛЕНИЯ БАЗЫ ДАННЫХ: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if upgrader:
            upgrader.close()


if __name__ == "__main__":
    # Запуск обновления
    upgrade_database_for_approval_signing(db_path=r"D:\python_ex\acti_v2\db\documents.db")