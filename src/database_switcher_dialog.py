from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from database_optimized import DatabaseSwitcher
import os


class DatabaseSwitcherDialog(QDialog):
    """Диалог для переключения между базами данных"""
    
    database_changed = pyqtSignal(str, object)  # Сигнал: (имя БД, новый менеджер)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.switcher = DatabaseSwitcher()
        self.init_ui()
        self.load_databases()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        self.setWindowTitle("Управление базами данных")
        self.setMinimumSize(700, 500)
        self.setModal(True)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Заголовок
        header = QLabel("🗄️ Управление базами данных")
        header.setStyleSheet("""
            QLabel {
                font-size: 18pt;
                font-weight: bold;
                color: #2c3e50;
                padding: 10px;
            }
        """)
        
        # Таблица с базами данных
        self.databases_table = QTableWidget()
        self.databases_table.setColumnCount(4)
        self.databases_table.setHorizontalHeaderLabels(
            ["Название", "Путь", "Дата добавления", "Действия"]
        )
        self.databases_table.horizontalHeader().setStretchLastSection(False)
        self.databases_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.databases_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.databases_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.databases_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.databases_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.databases_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.databases_table.setAlternatingRowColors(True)
        self.databases_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #e0e0e0;
                background-color: white;
                selection-background-color: #3498db;
                selection-color: white;
            }
            QHeaderView::section {
                background-color: #34495e;
                color: white;
                font-weight: bold;
                padding: 8px;
                border: none;
            }
        """)
        
        # Панель управления
        controls_layout = QHBoxLayout()
        
        # Кнопка добавления существующей БД
        self.add_existing_btn = QPushButton("📂 Добавить существующую БД")
        self.add_existing_btn.clicked.connect(self.add_existing_database)
        self.add_existing_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        
        # Кнопка создания новой БД
        self.create_new_btn = QPushButton("✨ Создать новую БД")
        self.create_new_btn.clicked.connect(self.create_new_database)
        self.create_new_btn.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)
        
        # Кнопка удаления из списка
        self.remove_btn = QPushButton("🗑️ Удалить из списка")
        self.remove_btn.clicked.connect(self.remove_database)
        self.remove_btn.setEnabled(False)
        self.remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #999999;
            }
        """)
        
        controls_layout.addWidget(self.add_existing_btn)
        controls_layout.addWidget(self.create_new_btn)
        controls_layout.addStretch()
        controls_layout.addWidget(self.remove_btn)
        
        # Текущая БД
        self.current_db_label = QLabel("Текущая БД: не выбрана")
        self.current_db_label.setStyleSheet("""
            QLabel {
                background-color: #ecf0f1;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
                color: #2c3e50;
            }
        """)
        
        # Кнопки диалога
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        
        # Сборка
        main_layout.addWidget(header)
        main_layout.addWidget(self.current_db_label)
        main_layout.addWidget(self.databases_table, 1)
        main_layout.addLayout(controls_layout)
        main_layout.addWidget(button_box)
        
        self.setLayout(main_layout)
        
        # Подключаем сигналы
        self.databases_table.itemSelectionChanged.connect(self.on_selection_changed)
    
    def load_databases(self):
        """Загрузить список БД с визуальным выделением активной"""
        self.databases_table.setRowCount(0)
        
        databases = self.switcher.get_database_list()
        current_db = self.switcher.current_db
        
        for db in databases:
            row = self.databases_table.rowCount()
            self.databases_table.insertRow(row)
            
            is_active = (db['name'] == current_db)
            
            # Название
            name_text = db['name']
            if is_active:
                name_text = f"⭐ {name_text} (АКТИВНА)"
            
            name_item = QTableWidgetItem(name_text)
            name_item.setFont(QFont("Arial", 10, QFont.Bold if is_active else QFont.Normal))
            
            # НОВОЕ: Визуальное выделение активной БД
            if is_active:
                from PyQt5.QtGui import QColor, QBrush
                # Зеленый фон для активной БД
                name_item.setBackground(QBrush(QColor(212, 237, 218)))  # Светло-зеленый
                name_item.setForeground(QBrush(QColor(21, 87, 36)))     # Темно-зеленый текст
            
            self.databases_table.setItem(row, 0, name_item)
            
            # Путь
            path_item = QTableWidgetItem(db['path'])
            if is_active:
                path_item.setBackground(QBrush(QColor(212, 237, 218)))
            self.databases_table.setItem(row, 1, path_item)
            
            # Дата добавления
            date_item = QTableWidgetItem(db.get('added', 'Неизвестно'))
            if is_active:
                date_item.setBackground(QBrush(QColor(212, 237, 218)))
            self.databases_table.setItem(row, 2, date_item)
            
            # Кнопка переключения
            if is_active:
                # Для активной БД показываем статус
                status_btn = QPushButton("✅ Активна")
                status_btn.setEnabled(False)
                status_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #27ae60;
                        color: white;
                        padding: 5px 10px;
                        border: none;
                        border-radius: 3px;
                        font-weight: bold;
                    }
                    QPushButton:disabled {
                        background-color: #27ae60;
                        color: white;
                    }
                """)
                self.databases_table.setCellWidget(row, 3, status_btn)
            else:
                # Для неактивных - кнопка переключения
                switch_btn = QPushButton("⚡ Переключить")
                switch_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #9b59b6;
                        color: white;
                        padding: 5px 10px;
                        border: none;
                        border-radius: 3px;
                    }
                    QPushButton:hover {
                        background-color: #8e44ad;
                    }
                """)
                switch_btn.clicked.connect(
                    lambda checked, name=db['name']: self.switch_database(name)
                )
                self.databases_table.setCellWidget(row, 3, switch_btn)
        
        # Обновляем текущую БД с эмодзи
        if current_db:
            self.current_db_label.setText(f"⭐ Текущая БД: {current_db}")
            self.current_db_label.setStyleSheet("""
                QLabel {
                    background-color: #d4edda;
                    padding: 10px;
                    border-radius: 5px;
                    font-weight: bold;
                    color: #155724;
                    border: 2px solid #28a745;
                }
            """)
        else:
            self.current_db_label.setText("⚠️ Текущая БД: не выбрана")
            self.current_db_label.setStyleSheet("""
                QLabel {
                    background-color: #fff3cd;
                    padding: 10px;
                    border-radius: 5px;
                    font-weight: bold;
                    color: #856404;
                    border: 2px solid #ffc107;
                }
            """)
    def create_database_structure(self, db_name: str, db_source_path: str = None) -> str:
        """
        Создать файловую структуру для базы данных
        
        Args:
            db_name: Название базы данных
            db_source_path: Путь к исходному файлу БД (для копирования) или None (для создания новой)
        
        Returns:
            str: Путь к созданной/скопированной БД в новой структуре
        
        Создает структуру:
            data/
            └── (db_name)/
                ├── database.db    (скопированная или новая БД)
                └── files/         (папка для документов)
        """
        try:
            # 1. Определяем базовые пути
            app_dir = os.getcwd()  # Папка с exe файлом
            data_root = os.path.join(app_dir, "data")
            db_folder = os.path.join(data_root, db_name)
            db_file_path = os.path.join(db_folder, "database.db")
            files_folder = os.path.join(db_folder, "files")
            
            # 2. Создаем папки
            print(f"📁 Создание структуры для БД '{db_name}'...")
            os.makedirs(data_root, exist_ok=True)
            os.makedirs(db_folder, exist_ok=True)
            os.makedirs(files_folder, exist_ok=True)
            
            # 3. Работа с файлом БД
            if db_source_path:
                # Копируем существующую БД
                print(f"📋 Копирование БД из: {db_source_path}")
                print(f"📋 Копирование БД в: {db_file_path}")
                
                if os.path.exists(db_file_path):
                    # Если файл уже есть - спрашиваем перезаписать
                    reply = QMessageBox.question(
                        None,
                        "Перезаписать БД?",
                        f"База данных '{db_name}' уже существует.\nПерезаписать?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    
                    if reply == QMessageBox.No:
                        raise Exception("Отменено пользователем")
                    
                    # Удаляем старую БД
                    os.remove(db_file_path)
                
                # Копируем файл БД
                import shutil
                shutil.copy2(db_source_path, db_file_path)
                print(f"✅ БД скопирована")
            else:
                # Создаем новую пустую БД
                print(f"🆕 Создание новой БД")
                from database_optimized import DatabaseManager
                new_manager = DatabaseManager(db_file_path, create_if_not_exists=True)
                new_manager.close()
                print(f"✅ Новая БД создана")
            
            print(f"✅ Структура создана:")
            print(f"   📁 Папка БД: {db_folder}")
            print(f"   📄 Файл БД: {db_file_path}")
            print(f"   📂 Папка файлов: {files_folder}")
            
            return db_file_path
            
        except Exception as e:
            print(f"❌ Ошибка создания структуры: {e}")
            raise    
    def add_existing_database(self):
        """Добавить существующую БД с проверкой схемы и созданием структуры"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл базы данных",
            "",
            "SQLite Database (*.db);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            # 1. Проверяем схему БД
            is_valid, message = self.switcher.validate_database_schema(file_path)
            
            if not is_valid:
                reply = QMessageBox.warning(
                    self,
                    "⚠️ Некорректная схема БД",
                    f"Выбранная база данных имеет проблемы:\n\n{message}\n\n"
                    f"Добавить её в список всё равно?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                
                if reply == QMessageBox.No:
                    return
            
            # 2. Запрашиваем название
            name, ok = QInputDialog.getText(
                self,
                "Название базы данных",
                "Введите название для этой БД:"
            )
            
            if not ok or not name:
                return
            
            # 🆕 3. Создаем файловую структуру и копируем БД
            progress = QProgressDialog(
                "Создание файловой структуры и копирование БД...",
                "Отмена",
                0, 0,
                self
            )
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.show()
            QApplication.processEvents()
            
            try:
                # Создаем структуру и копируем БД
                new_db_path = self.create_database_structure(name, file_path)
                
                # 4. Добавляем в конфигурацию
                self.switcher.add_database(name, new_db_path)
                
                progress.close()
                
                # 5. Обновляем интерфейс
                self.load_databases()
                
                # 6. Сообщаем результат
                if is_valid:
                    QMessageBox.information(
                        self,
                        "✅ Успешно",
                        f"База данных '{name}' успешно добавлена!\n\n"
                        f"📁 Структура создана в: data/{name}/\n"
                        f"📄 БД: data/{name}/database.db\n"
                        f"📂 Файлы: data/{name}/files/\n\n"
                        f"{message}"
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "⚠️ БД добавлена с предупреждением",
                        f"База данных '{name}' добавлена, но имеет проблемы:\n\n{message}"
                    )
                    
            except Exception as e:
                progress.close()
                raise e
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "❌ Ошибка",
                f"Не удалось добавить БД: {str(e)}"
            )
    
    def create_new_database(self):
        """Создать новую БД с правильной структурой папок"""
        # 1. Запрашиваем название
        name, ok = QInputDialog.getText(
            self,
            "Новая база данных",
            "Введите название для новой БД:"
        )
        
        if not ok or not name:
            return
        
        try:
            # 🆕 2. Создаем структуру БД (без исходного файла)
            progress = QProgressDialog(
                "Создание новой базы данных...",
                "Отмена",
                0, 0,
                self
            )
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.show()
            QApplication.processEvents()
            
            try:
                # Создаем структуру и новую пустую БД
                new_db_path = self.create_database_structure(name, db_source_path=None)
                
                # 3. Добавляем в конфигурацию
                self.switcher.add_database(name, new_db_path)
                
                progress.close()
                
                # 4. Обновляем интерфейс
                self.load_databases()
                
                # 5. Сообщаем результат
                QMessageBox.information(
                    self,
                    "✅ Успешно",
                    f"Новая база данных '{name}' создана!\n\n"
                    f"📁 Структура:\n"
                    f"   data/{name}/\n"
                    f"   ├── database.db\n"
                    f"   └── files/"
                )
                
            except Exception as e:
                progress.close()
                raise e
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "❌ Ошибка",
                f"Не удалось создать БД: {str(e)}"
            )
    
    def switch_database(self, name: str):
        """Переключиться на выбранную БД с валидацией"""
        try:
            reply = QMessageBox.question(
                self,
                "Подтверждение",
                f"Переключиться на базу данных '{name}'?\n\n"
                "Текущие несохраненные изменения будут потеряны.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Показываем прогресс
                progress = QProgressDialog(
                    "Проверка и подключение к базе данных...",
                    "Отмена",
                    0, 0,
                    self
                )
                progress.setWindowModality(Qt.WindowModal)
                progress.setMinimumDuration(0)
                progress.show()
                QApplication.processEvents()
                
                try:
                    # ИЗМЕНЕНИЕ: Получаем новый менеджер (с валидацией внутри)
                    new_manager = self.switcher.switch_database(name)
                    
                    # НОВОЕ: Сохраняем ссылку на новый менеджер
                    self.new_manager = new_manager
            
                    progress.close()
            
            # Обновляем интерфейс
                    self.load_databases()  # Перерисовываем таблицу с новым выделением
            
            # Эмитим сигнал с новым менеджером
                    self.database_changed.emit(name, new_manager)
                    
                    QMessageBox.information(
                        self,
                        "✅ Успешно",
                        f"Переключено на базу данных '{name}'\n\n"
                        f"Схема БД проверена и корректна."
                    )
                    
                except Exception as e:
                    progress.close()
                    raise e
                    
        except Exception as e:
            QMessageBox.critical(
                self,
                "❌ Ошибка",
                f"Не удалось переключить БД:\n\n{str(e)}\n\n"
                f"Возможно, база данных повреждена или имеет некорректную структуру."
            )
            print(f"❌ Ошибка переключения БД: {e}")
    
    def remove_database(self):
        """Удалить БД из списка"""
        selected_rows = self.databases_table.selectionModel().selectedRows()
        
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        name = self.databases_table.item(row, 0).text()
        
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Удалить '{name}' из списка?\n\n"
            "Файл базы данных не будет удален с диска.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if name in self.switcher.databases:
                del self.switcher.databases[name]
                self.switcher.save_config()
                self.load_databases()
                
                QMessageBox.information(
                    self,
                    "Успешно",
                    f"'{name}' удалена из списка"
                )
    
    def on_selection_changed(self):
        """Обработчик изменения выбора"""
        has_selection = len(self.databases_table.selectionModel().selectedRows()) > 0
        self.remove_btn.setEnabled(has_selection)
