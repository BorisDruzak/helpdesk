import sqlite3
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime


class DatabaseManager:
    def __init__(self, db_path: str):
        """
        Инициализирует соединение с базой данных.
        
        :param db_path: Путь к файлу базы данных
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row  # Для удобного доступа по имени столбца
        self.cursor = self.conn.cursor()
        
        # Создаем базовые таблицы если их нет
        self.create_tables_if_not_exist()
    def add_documents_batch(self, documents_list):
        """Массовое добавление документов"""
        try:
            for doc_data in documents_list:
                self.add_document(doc_data)
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise e
    def create_tables_if_not_exist(self):
        """Создание таблиц если их нет"""
        try:
            # Основная таблица документов
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT,
                    filepath TEXT,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    -- Основные поля
                    status TEXT DEFAULT 'Действующий',
                    type_doc TEXT DEFAULT 'Распоряжение',
                    reg_number TEXT DEFAULT '',
                    reg_date DATE DEFAULT (date('now')),
                    executor_id INTEGER,
                    theme_id INTEGER,
                    title TEXT DEFAULT '',
                    
                    -- Блок публикации
                    gazette_number TEXT DEFAULT '',
                    published_where TEXT DEFAULT '',
                    published_date DATE,
                    
                    -- Блок контроля
                    responsible_executor_id INTEGER,
                    control_date DATE,
                    execution_result BOOLEAN,
                    removed_from_control BOOLEAN DEFAULT 0,
                    
                    -- Блок списания
                    case_number TEXT DEFAULT '',
                    volume_number TEXT DEFAULT '',
                    sheets TEXT DEFAULT '',
                    
                    -- Внешние ключи
                    FOREIGN KEY (executor_id) REFERENCES executors(id),
                    FOREIGN KEY (theme_id) REFERENCES themes(id),
                    FOREIGN KEY (responsible_executor_id) REFERENCES executors(id)
                )
            """)
            
            # Таблица исполнителей
            self.cursor.execute("""
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
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS themes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Индексы для быстрого поиска
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(type_doc)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_reg_date ON documents(reg_date)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_executor ON documents(executor_id)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_theme ON documents(theme_id)")
            
            self.conn.commit()
            print("✅ Структура базы данных проверена и обновена")
            
        except Exception as e:
            print(f"❌ Ошибка создания таблиц: {e}")

    def close(self):
        """Закрывает соединение с базой данных."""
        if self.conn:
            self.conn.close()

    # === МЕТОДЫ ДЛЯ ДОКУМЕНТОВ ===
    
    def add_document(self, data: Dict[str, Any]) -> int:
        """
        Добавляет новую запись о документе в базу данных.
        
        :param data: Словарь с данными нового документа
        :return: ID вставленной записи
        """
        try:
            # Добавляем дату создания
            data['created_date'] = datetime.now().isoformat()
            data['modified_date'] = datetime.now().isoformat()
            
            columns = ', '.join(data.keys())
            placeholders = ':' + ', :'.join(data.keys())
            query = f"INSERT INTO documents ({columns}) VALUES ({placeholders})"
            
            self.cursor.execute(query, data)
            self.conn.commit()
            
            doc_id = self.cursor.lastrowid
            print(f"✅ Документ добавлен с ID: {doc_id}")
            return doc_id
            
        except Exception as e:
            print(f"❌ Ошибка добавления документа: {e}")
            self.conn.rollback()
            raise

    def update_document(self, document_id, updated_data):
        """Обновление документа в БД - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            if not updated_data:
                return
            
            # Получаем текущую структуру таблицы
            cursor = self.connection.cursor()
            cursor.execute("PRAGMA table_info(documents)")
            existing_columns = [row[1] for row in cursor.fetchall()]
            
            # Фильтруем только существующие колонки
            valid_updates = {}
            for key, value in updated_data.items():
                if key in existing_columns:
                    valid_updates[key] = value
                else:
                    print(f"⚠️ Пропускаем несуществующую колонку: {key}")
            
            if not valid_updates:
                print("❌ Нет валидных полей для обновления")
                return
            
            # Формируем SQL запрос
            set_clause = ", ".join([f"{key} = ?" for key in valid_updates.keys()])
            values = list(valid_updates.values())
            values.append(document_id)
            
            sql = f"UPDATE documents SET {set_clause} WHERE id = ?"
            
            print(f"🔄 Обновляем документ ID {document_id}: {valid_updates}")
            
            cursor.execute(sql, values)
            self.connection.commit()
            
            if cursor.rowcount > 0:
                print(f"✅ Документ ID {document_id} успешно обновлен")
            else:
                print(f"⚠️ Документ ID {document_id} не найден")
            
        except Exception as e:
            print(f"❌ Ошибка обновления документа: {e}")
            self.connection.rollback()
            raise e

    def update_document_field(self, doc_id: int, field_name: str, value: Any):
        """
        Обновляет отдельное поле документа в базе данных.

        :param doc_id: Идентификатор документа
        :param field_name: Название поля для обновления
        :param value: Новое значение поля
        """
        try:
            # Расширенный список допустимых полей
            allowed_fields = [
                'status', 'type_doc', 'reg_number', 'reg_date', 'executor', 'kind_doc', 'subject', 'title',
                'executor_id', 'theme_id', 'gazette_number', 'published_where', 'published_date',
                'responsible_executor_id', 'control_date', 'execution_result', 'removed_from_control',
                'case_number', 'volume_number', 'sheets'
            ]
            
            if field_name not in allowed_fields:
                raise ValueError(f"Недопустимое поле для обновления: {field_name}")

            # Обновляем поле и дату изменения
            query = f"UPDATE documents SET {field_name} = ?, modified_date = ? WHERE id = ?"
            self.cursor.execute(query, (value, datetime.now().isoformat(), doc_id))
            self.conn.commit()
            
            print(f"✅ Поле {field_name} обновлено для документа ID {doc_id}")
            
        except Exception as e:
            print(f"❌ Ошибка обновления поля: {e}")
            self.conn.rollback()
            raise

    def delete_document(self, doc_id: int):
        """
        Удаляет документ из базы данных.
        
        :param doc_id: ID удаляемого документа
        """
        try:
            query = "DELETE FROM documents WHERE id=?"
            self.cursor.execute(query, (doc_id,))
            self.conn.commit()
            print(f"✅ Документ ID {doc_id} удалён")
            
        except Exception as e:
            print(f"❌ Ошибка удаления документа: {e}")
            self.conn.rollback()
            raise

    def get_documents(self, filters: Dict[str, Any] = None) -> List[Dict]:
        """
        Получает список документов по заданным фильтрам.
        
        :param filters: Словарь фильтров для отбора документов
        :return: Список найденных документов
        """
        try:
            where_clause = ""
            params = []
            
            if filters:
                conditions = []
                for key, value in filters.items():
                    if isinstance(value, list):
                        # Для списков используем IN
                        placeholders = ','.join('?' * len(value))
                        conditions.append(f"{key} IN ({placeholders})")
                        params.extend(value)
                    else:
                        conditions.append(f"{key}=?")
                        params.append(value)
                where_clause = f"WHERE {' AND '.join(conditions)}"
                
            query = f"""
                SELECT d.*, 
                       e.name as executor_name, e.position as executor_position,
                       t.name as theme_name,
                       re.name as responsible_executor_name
                FROM documents d
                LEFT JOIN executors e ON d.executor_id = e.id
                LEFT JOIN themes t ON d.theme_id = t.id
                LEFT JOIN executors re ON d.responsible_executor_id = re.id
                {where_clause}
                ORDER BY d.reg_date DESC
            """
            
            self.cursor.execute(query, tuple(params))
            rows = self.cursor.fetchall()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            print(f"❌ Ошибка получения документов: {e}")
            return []

    def get_all_documents(self):
        """Получает все документы с расширенной информацией"""
        return self.get_documents()

    def get_document_by_id(self, doc_id: int) -> Dict:
        """
        Получает документ по его ID с полной информацией.
        
        :param doc_id: ID искомого документа
        :return: Словарь с данными документа
        """
        try:
            query = """
                SELECT d.*, 
                       e.name as executor_name, e.position as executor_position,
                       t.name as theme_name,
                       re.name as responsible_executor_name
                FROM documents d
                LEFT JOIN executors e ON d.executor_id = e.id
                LEFT JOIN themes t ON d.theme_id = t.id
                LEFT JOIN executors re ON d.responsible_executor_id = re.id
                WHERE d.id=?
            """
            self.cursor.execute(query, (doc_id,))
            row = self.cursor.fetchone()
            
            return dict(row) if row else {}
            
        except Exception as e:
            print(f"❌ Ошибка получения документа по ID: {e}")
            return {}

    # === МЕТОДЫ ПОИСКА ===
    
    def search_documents(self, keyword: str) -> List[Dict]:
        """
        Осуществляет полнотекстовый поиск среди документов.
        
        :param keyword: Ключевое слово для поиска
        :return: Список найденных документов
        """
        try:
            query = """
                SELECT d.*, 
                       e.name as executor_name, e.position as executor_position,
                       t.name as theme_name,
                       re.name as responsible_executor_name
                FROM documents d
                LEFT JOIN executors e ON d.executor_id = e.id
                LEFT JOIN themes t ON d.theme_id = t.id
                LEFT JOIN executors re ON d.responsible_executor_id = re.id
                WHERE d.filename LIKE ? 
                   OR d.title LIKE ? 
                   OR d.reg_number LIKE ?
                   OR e.name LIKE ?
                   OR t.name LIKE ?
                ORDER BY d.reg_date DESC
            """
            
            search_pattern = f'%{keyword}%'
            self.cursor.execute(query, (search_pattern,) * 5)
            rows = self.cursor.fetchall()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            print(f"❌ Ошибка поиска документов: {e}")
            return []

    def search_by_tags(self, **criteria) -> List[Dict]:
        """
        Продвинутый поиск документов по различным критериям (тегам).
        
        Параметры:
        - status: список статусов или один статус
        - type_doc: список типов документов или один тип
        - executor_ids: список ID исполнителей
        - theme_ids: список ID тем
        - date_from: дата от (включительно)
        - date_to: дата до (включительно)
        - execution_result: результат исполнения (True/False/None)
        - removed_from_control: снято с контроля (True/False)
        - keywords: ключевые слова для поиска в тексте
        """
        try:
            conditions = []
            params = []
            
            # Статус документа
            if 'status' in criteria:
                status = criteria['status']
                if isinstance(status, list):
                    placeholders = ','.join('?' * len(status))
                    conditions.append(f"d.status IN ({placeholders})")
                    params.extend(status)
                else:
                    conditions.append("d.status = ?")
                    params.append(status)
            
            # Тип документа
            if 'type_doc' in criteria:
                type_doc = criteria['type_doc']
                if isinstance(type_doc, list):
                    placeholders = ','.join('?' * len(type_doc))
                    conditions.append(f"d.type_doc IN ({placeholders})")
                    params.extend(type_doc)
                else:
                    conditions.append("d.type_doc = ?")
                    params.append(type_doc)
            
            # Исполнители
            if 'executor_ids' in criteria:
                executor_ids = criteria['executor_ids']
                if isinstance(executor_ids, list):
                    placeholders = ','.join('?' * len(executor_ids))
                    conditions.append(f"(d.executor_id IN ({placeholders}) OR d.responsible_executor_id IN ({placeholders}))")
                    params.extend(executor_ids * 2)
                else:
                    conditions.append("(d.executor_id = ? OR d.responsible_executor_id = ?)")
                    params.extend([executor_ids, executor_ids])
            
            # Темы
            if 'theme_ids' in criteria:
                theme_ids = criteria['theme_ids']
                if isinstance(theme_ids, list):
                    placeholders = ','.join('?' * len(theme_ids))
                    conditions.append(f"d.theme_id IN ({placeholders})")
                    params.extend(theme_ids)
                else:
                    conditions.append("d.theme_id = ?")
                    params.append(theme_ids)
            
            # Период дат
            if 'date_from' in criteria:
                conditions.append("d.reg_date >= ?")
                params.append(criteria['date_from'])
            
            if 'date_to' in criteria:
                conditions.append("d.reg_date <= ?")
                params.append(criteria['date_to'])
            
            # Результат исполнения
            if 'execution_result' in criteria:
                conditions.append("d.execution_result = ?")
                params.append(criteria['execution_result'])
            
            # Снято с контроля
            if 'removed_from_control' in criteria:
                conditions.append("d.removed_from_control = ?")
                params.append(criteria['removed_from_control'])
            
            # Ключевые слова
            if 'keywords' in criteria:
                keywords = criteria['keywords']
                search_pattern = f'%{keywords}%'
                keyword_conditions = [
                    "d.filename LIKE ?",
                    "d.title LIKE ?", 
                    "d.reg_number LIKE ?",
                    "e.name LIKE ?",
                    "t.name LIKE ?"
                ]
                conditions.append("(" + " OR ".join(keyword_conditions) + ")")
                params.extend([search_pattern] * 5)
            
            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            
            query = f"""
                SELECT d.*, 
                    e.name as executor_name, e.position as executor_position,
                    t.name as theme_name,
                    re.name as responsible_executor_name
                FROM documents d
                LEFT JOIN executors e ON d.executor_id = e.id
                LEFT JOIN themes t ON d.theme_id = t.id
                LEFT JOIN executors re ON d.responsible_executor_id = re.id
                {where_clause}
                ORDER BY d.reg_date DESC"""
            
            self.cursor.execute(query, params)
            rows = self.cursor.fetchall()
            
            print(f"🔍 Найдено документов по критериям: {len(rows)}")
            return [dict(row) for row in rows]
            
        except Exception as e:
            print(f"❌ Ошибка поиска по тегам: {e}")
            return []

    def get_documents_statistics(self) -> Dict[str, Any]:
        """
        Получает статистику по документам.
        
        :return: Словарь со статистикой
        """
        try:
            stats = {}
            
            # Общее количество
            self.cursor.execute("SELECT COUNT(*) FROM documents")
            stats['total_documents'] = self.cursor.fetchone()[0]
            
            # По статусам
            self.cursor.execute("""
                SELECT status, COUNT(*) 
                FROM documents 
                GROUP BY status 
                ORDER BY COUNT(*) DESC
            """)
            stats['by_status'] = dict(self.cursor.fetchall())
            
            # По типам
            self.cursor.execute("""
                SELECT type_doc, COUNT(*) 
                FROM documents 
                GROUP BY type_doc 
                ORDER BY COUNT(*) DESC
            """)
            stats['by_type'] = dict(self.cursor.fetchall())
            
            # По исполнителям
            self.cursor.execute("""
                SELECT e.name, COUNT(d.id) 
                FROM executors e
                LEFT JOIN documents d ON e.id = d.executor_id
                WHERE e.is_active = 1
                GROUP BY e.id, e.name
                ORDER BY COUNT(d.id) DESC
                LIMIT 10
            """)
            stats['by_executor'] = dict(self.cursor.fetchall())
            
            # По темам
            self.cursor.execute("""
                SELECT t.name, COUNT(d.id) 
                FROM themes t
                LEFT JOIN documents d ON t.id = d.theme_id
                WHERE t.is_active = 1
                GROUP BY t.id, t.name
                ORDER BY COUNT(d.id) DESC
                LIMIT 10
            """)
            stats['by_theme'] = dict(self.cursor.fetchall())
            
            return stats
            
        except Exception as e:
            print(f"❌ Ошибка получения статистики: {e}")
            return {}

    # === МЕТОДЫ ДЛЯ СПРАВОЧНИКОВ ===
    
    def get_executors(self, active_only: bool = True) -> List[Dict]:
        """Получить список исполнителей"""
        try:
            where_clause = "WHERE is_active = 1" if active_only else ""
            query = f"SELECT * FROM executors {where_clause} ORDER BY name"
            self.cursor.execute(query)
            return [dict(row) for row in self.cursor.fetchall()]
        except Exception as e:
            print(f"❌ Ошибка получения исполнителей: {e}")
            return []

    def add_executor(self, name: str, position: str = "", department: str = "") -> Optional[int]:
        """Добавить исполнителя"""
        try:
            query = "INSERT INTO executors (name, position, department) VALUES (?, ?, ?)"
            self.cursor.execute(query, (name, position, department))
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            print(f"❌ Ошибка добавления исполнителя: {e}")
            return None

    def get_themes(self, active_only: bool = True) -> List[Dict]:
        """Получить список тем"""
        try:
            where_clause = "WHERE is_active = 1" if active_only else ""
            query = f"SELECT * FROM themes {where_clause} ORDER BY name"
            self.cursor.execute(query)
            return [dict(row) for row in self.cursor.fetchall()]
        except Exception as e:
            print(f"❌ Ошибка получения тем: {e}")
            return []

    def add_theme(self, name: str, description: str = "") -> Optional[int]:
        """Добавить тему"""
        try:
            query = "INSERT INTO themes (name, description) VALUES (?, ?)"
            self.cursor.execute(query, (name, description))
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            print(f"❌ Ошибка добавления темы: {e}")
            return None

    def deactivate_executor(self, executor_id: int):
        """Деактивировать исполнителя (не удаляем, а помечаем неактивным)"""
        try:
            query = "UPDATE executors SET is_active = 0 WHERE id = ?"
            self.cursor.execute(query, (executor_id,))
            self.conn.commit()
        except Exception as e:
            print(f"❌ Ошибка деактивации исполнителя: {e}")

    def deactivate_theme(self, theme_id: int):
        """Деактивировать тему"""
        try:
            query = "UPDATE themes SET is_active = 0 WHERE id = ?"
            self.cursor.execute(query, (theme_id,))
            self.conn.commit()
        except Exception as e:
            print(f"❌ Ошибка деактивации темы: {e}")

    # === ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ===
    
    def execute_query(self, query: str, params: List[Any] = None) -> List[Dict]:
        """Универсальный метод для выполнения SELECT запросов"""
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            rows = self.cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"❌ Ошибка выполнения запроса: {e}")
            return []

    def execute_update(self, query: str, params: List[Any] = None) -> Optional[int]:
        """Универсальный метод для выполнения INSERT/UPDATE/DELETE запросов"""
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            print(f"❌ Ошибка выполнения обновления: {e}")
            self.conn.rollback()
            return None

    def get_connection(self):
        """Получить соединение с базой данных (для обратной совместимости)"""
        return self.conn
    def search_documents_with_filters(self, filters):
        """Поиск документов с расширенными фильтрами"""
        try:
            query = """
                SELECT 
                    d.id,
                    d.title,
                    d.reg_number,
                    d.reg_date,
                    d.status,
                    d.type_doc,
                    d.filename,
                    e.name as executor_name,
                    t.name as theme_name,
                    d.approval_status,
                    ae.name as approval_executor_name,
                    d.approval_date,
                    d.signing_status,
                    se.name as signing_executor_name,
                    d.signing_date
                FROM documents d
                LEFT JOIN executors e ON d.executor_id = e.id
                LEFT JOIN themes t ON d.theme_id = t.id
                LEFT JOIN executors ae ON d.approval_executor_id = ae.id
                LEFT JOIN executors se ON d.signing_executor_id = se.id
                WHERE 1=1
            """
            
            params = []
            
            # Фильтр по тексту (название или рег. номер)
            if filters.get('search_text'):
                query += " AND (d.title LIKE ? OR d.reg_number LIKE ?)"
                search_term = f"%{filters['search_text']}%"
                params.extend([search_term, search_term])
            
            # Фильтр по статусу
            if filters.get('status'):
                query += " AND LOWER(d.status) LIKE ?"
                params.append(f"%{filters['status']}%")
            
            # Фильтр по дате
            if filters.get('date_from'):
                query += " AND d.reg_date >= ?"
                params.append(filters['date_from'])
            
            if filters.get('date_to'):
                query += " AND d.reg_date <= ?"
                params.append(filters['date_to'])
            
            query += " ORDER BY d.reg_date DESC, d.id DESC"
            
            cursor = self.connection.cursor()
            cursor.execute(query, params)
            documents = cursor.fetchall()
            
            # Преобразуем в список словарей
            result = []
            for doc in documents:
                result.append({
                    'id': doc[0],
                    'title': doc[1],
                    'reg_number': doc[2],
                    'reg_date': doc[3],
                    'status': doc[4],
                    'type_doc': doc[5],
                    'filename': doc[6],
                    'executor_name': doc[7],
                    'theme_name': doc[8],
                    'approval_status': doc[9],
                    'approval_executor_name': doc[10],
                    'approval_date': doc[11],
                    'signing_status': doc[12],
                    'signing_executor_name': doc[13],
                    'signing_date': doc[14]
                })
            
            return result
            
        except Exception as e:
            print(f"Ошибка при поиске документов: {e}")
            return []

    @property
    def connection(self):
        """Свойство для доступа к соединению"""
        return self.conn