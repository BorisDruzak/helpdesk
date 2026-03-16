from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from datetime import datetime
from ui_styles import AppColors, AppStyles, AppLayout, EnhancedDateEdit
import os 
import shutil
class ReferenceManager:
    """Менеджер справочников для редактора метаданных"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
    
    def execute_query(self, query, params=None):
        """Универсальный метод для выполнения запросов"""
        try:
            if hasattr(self.db_manager, 'execute_query'):
                return self.db_manager.execute_query(query, params or [])
            elif hasattr(self.db_manager, 'conn'):
                cursor = self.db_manager.conn.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
            else:
                import sqlite3
                db_path = getattr(self.db_manager, 'db_path', None)
                if not db_path:
                    raise Exception("Не удалось найти путь к базе данных")
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                result = [dict(row) for row in cursor.fetchall()]
                conn.close()
                return result
        except Exception as e:
            print(f"❌ Ошибка выполнения запроса: {e}")
            return []
    
    def execute_update(self, query, params=None):
        """Универсальный метод для выполнения обновлений"""
        try:
            if hasattr(self.db_manager, 'execute_update'):
                return self.db_manager.execute_update(query, params or [])
            elif hasattr(self.db_manager, 'conn'):
                cursor = self.db_manager.conn.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                self.db_manager.conn.commit()
                return cursor.lastrowid
            else:
                import sqlite3
                db_path = getattr(self.db_manager, 'db_path', None)
                if not db_path:
                    raise Exception("Не удалось найти путь к базе данных")
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                conn.commit()
                last_id = cursor.lastrowid
                conn.close()
                return last_id
        except Exception as e:
            print(f"❌ Ошибка выполнения обновления: {e}")
            return None
    
    def get_reference_items(self, ref_type):
        """Универсальный метод для получения справочников"""
        try:
            table_map = {
                'executors': 'ref_executors',
                'themes': 'ref_themes',
                'responsible_executors': 'ref_responsible_executors',
                'signers': 'ref_signers',
                'approvers': 'ref_approvers',
                'status': 'ref_status',
                'document_types': 'ref_document_types',
                'signing_types': 'ref_signing_types',
                'document_kinds': 'ref_document_kinds',
                'published_where': 'ref_published_where'
            }
            
            table_name = table_map.get(ref_type)
            if not table_name:
                print(f"❌ Неизвестный тип справочника: {ref_type}")
                return []
            
            query = f"SELECT id, name FROM {table_name} ORDER BY name"
            results = self.execute_query(query)
            return results
        except Exception as e:
            print(f"❌ Ошибка при получении справочника {ref_type}: {e}")
            return []
class SearchableComboBox(QWidget):
    """ComboBox с автодополнением через QCompleter"""
    
    def __init__(self, reference_manager, ref_type, parent=None):
        super().__init__(parent)
        self.reference_manager = reference_manager
        self.ref_type = ref_type
        self.all_items = []
        self.init_ui()
    
    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Обычный ComboBox
        self.combo = QComboBox()
        self.combo.setEditable(True)
        self.combo.setInsertPolicy(QComboBox.NoInsert)
        self.combo.setFocusPolicy(Qt.StrongFocus)
        
        # Стиль с правильной стрелочкой
        self.combo.setStyleSheet("""
            QComboBox {
                padding: 6px;
                padding-right: 30px;
                border: 2px solid #3498db;
                border-radius: 4px;
                font-size: 10pt;
                background: white;
            }
            QComboBox:focus {
                border: 2px solid #2980b9;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 30px;
                border-left: 1px solid #bdc3c7;
                background: #ecf0f1;
                border-top-right-radius: 3px;
                border-bottom-right-radius: 3px;
            }
            QComboBox::drop-down:hover {
                background: #d5dbdb;
            }
            QComboBox::down-arrow {
                width: 0;
                height: 0;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #2c3e50;
                margin-right: 5px;
            }
        """)
        
        # LineEdit
        self.line_edit = self.combo.lineEdit()
        self.line_edit.setPlaceholderText("🔍 Начните вводить для поиска...")
        self.line_edit.setClearButtonEnabled(True)
        
        # КЛЮЧЕВОЕ РЕШЕНИЕ: QCompleter для автодополнения
        self.completer = QCompleter()
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)  # Поиск по вхождению
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setMaxVisibleItems(10)  # Максимум 10 элементов видимых
        
        # Стиль для popup completer с фиксированной шириной И ВЫСОТОЙ
        self.completer.popup().setStyleSheet("""
            QListView {
                border: 2px solid #3498db;
                selection-background-color: #3498db;
                selection-color: white;
                font-size: 10pt;
                padding: 4px;
                min-width: 300px;
                min-height: 25px;
            }
            QListView::item {
                padding: 10px 8px;
                min-height: 30px;
                height: 35px;
            }
            QListView::item:hover {
                background-color: #e8f4fd;
            }
        """)
        
        # ВАЖНО: Устанавливаем минимальную ширину и высоту для popup
        self.completer.popup().setMinimumWidth(350)
        self.completer.popup().setMinimumHeight(25)  # Минимальная высота popup
        
        # Подключаем completer к LineEdit
        self.line_edit.setCompleter(self.completer)
        
        # Отключаем прокрутку колесиком
        self.combo.wheelEvent = self._combo_wheel_event
        
        layout.addWidget(self.combo)
        self.setLayout(layout)
        
        # Загружаем данные
        self.load_items()
    
    def _combo_wheel_event(self, event):
        """Обработка колесика мыши"""
        if not self.combo.hasFocus():
            event.ignore()
        else:
            QComboBox.wheelEvent(self.combo, event)
    
    def load_items(self):
        """Загрузить все элементы из БД"""
        try:
            items = self.reference_manager.get_reference_items(self.ref_type)
            self.all_items = items
            
            # Заполняем комбобокс
            self.combo.clear()
            
            # Список имен для completer
            names = []
            
            for item in items:
                name = item.get('name', '')
                item_id = item.get('id')
                self.combo.addItem(name, item_id)
                names.append(name)
            
            # Устанавливаем модель для completer
            from PyQt5.QtCore import QStringListModel
            self.completer.setModel(QStringListModel(names))
            
            # Очищаем поле
            self.line_edit.clear()
            
            print(f"✅ Загружено {len(items)} элементов для {self.ref_type}")
            
        except Exception as e:
            print(f"❌ Ошибка загрузки элементов {self.ref_type}: {e}")
            self.combo.clear()
    
    def current_data(self):
        """Получить ID выбранного элемента"""
        current_text = self.line_edit.text().strip()
        
        if not current_text:
            return None
        
        # Ищем точное совпадение
        for item in self.all_items:
            if item.get('name', '') == current_text:
                return item.get('id')
        
        return None
    
    def current_text(self):
        """Получить текст выбранного элемента"""
        return self.line_edit.text().strip()
    
    def set_current_by_id(self, item_id):
        """Выбрать элемент по ID"""
        if item_id is None:
            self.line_edit.clear()
            return True
        
        # Ищем элемент с таким ID
        for item in self.all_items:
            if item.get('id') == item_id:
                name = item.get('name', '')
                
                # Блокируем сигналы при программной установке
                self.combo.blockSignals(True)
                self.line_edit.blockSignals(True)
                
                # Находим индекс
                index = self.combo.findText(name)
                if index >= 0:
                    self.combo.setCurrentIndex(index)
                
                self.combo.blockSignals(False)
                self.line_edit.blockSignals(False)
                
                return True
        
        return False

class EditableComboBox(QWidget):
    """Виджет ComboBox с возможностью просмотра справочника"""
    
    def __init__(self, reference_manager, ref_type, parent=None):
        super().__init__(parent)
        self.reference_manager = reference_manager
        self.ref_type = ref_type
        self.init_ui()
    
    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.combo = QComboBox()
        self.combo.setFocusPolicy(Qt.StrongFocus)
        self.combo.setEditable(False)
        self.combo.wheelEvent = self._combo_wheel_event
        layout.addWidget(self.combo)
        self.setLayout(layout)
        self.load_items()
    def _combo_wheel_event(self, event):
        """Обработка колесика мыши для внутреннего combo"""
        if not self.combo.hasFocus():
            # Передать событие родителю для прокрутки
            event.ignore()
        else:
            # Обычное поведение когда combo в фокусе
            QComboBox.wheelEvent(self.combo, event)
    def load_items(self):
        """Загрузить элементы в комбобокс"""
        self.combo.clear()
        
        try:
            items = self.reference_manager.get_reference_items(self.ref_type)
            self.combo.addItem("-- Не выбран --", None)
            
            for item in items:
                name = item.get('name', '')
                item_id = item.get('id')
                self.combo.addItem(name, item_id)
        except Exception as e:
            print(f"❌ Ошибка загрузки элементов {self.ref_type}: {e}")
            self.combo.addItem("-- Не выбран --", None)
    
    def current_data(self):
        """Получить ID выбранного элемента"""
        return self.combo.currentData()
    
    def current_text(self):
        """Получить текст выбранного элемента"""
        return self.combo.currentText()
    
    def set_current_by_id(self, item_id):
        """Выбрать элемент по ID"""
        if item_id is None:
            self.combo.setCurrentIndex(0)
            return True
            
        for i in range(self.combo.count()):
            if self.combo.itemData(i) == item_id:
                self.combo.setCurrentIndex(i)
                return True
        return False


class CollapsibleGroupBox(QWidget):
    """Сворачиваемая группа с кнопкой переключения"""
    
    def __init__(self, title="", collapsed=False, parent=None):
        super().__init__(parent)
        self.collapsed = collapsed
        self.title = title
        self.init_ui()
    
    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 5)
        main_layout.setSpacing(0)
        
        # Заголовок с кнопкой
        header_widget = QWidget()
        header_widget.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.PRIMARY}, stop:1 {AppColors.PRIMARY_DARK});
                border-radius: 6px;
            }}
        """)
        
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(10, 8, 10, 8)
        
        self.toggle_btn = QPushButton("▼" if not self.collapsed else "▶")
        self.toggle_btn.setFixedSize(30, 30)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: white;
                font-size: 16pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.2);
                border-radius: 4px;
            }
        """)
        self.toggle_btn.clicked.connect(self.toggle)
        
        title_label = QLabel(self.title)
        title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 14pt;
                font-weight: bold;
                background: transparent;
            }
        """)
        
        header_layout.addWidget(self.toggle_btn)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_widget.setLayout(header_layout)
        
        # Контент
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("""
            QWidget {
                background: white;
                border: 2px solid #3498db;
                border-top: none;
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
                padding: 10px;
            }
        """)
        
        self.content_layout = QFormLayout()
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content_layout.setVerticalSpacing(8)
        self.content_widget.setLayout(self.content_layout)
        self.content_widget.setVisible(not self.collapsed)
        
        main_layout.addWidget(header_widget)
        main_layout.addWidget(self.content_widget)
        self.setLayout(main_layout)
    
    def toggle(self):
        """Переключить видимость контента"""
        self.collapsed = not self.collapsed
        self.content_widget.setVisible(not self.collapsed)
        self.toggle_btn.setText("▶" if self.collapsed else "▼")
    
    def add_row(self, label, widget):
        """Добавить строку в форму"""
        self.content_layout.addRow(label, widget)


class MetadataEditor(QWidget):
    """Полный редактор метаданных документа"""
    metadata_saved = pyqtSignal(int)
    
    def __init__(self, db_manager=None):
        super().__init__()
        self.db_manager = db_manager
        self.current_document_id = None
        self._new_document_path = None
        if db_manager:
            self.reference_manager = ReferenceManager(db_manager)
        else:
            self.reference_manager = None
        self.signers_data = []    # ← ДОБАВИТЬ инициализацию
        self.approvers_data = []  # ← ДОБАВИТЬ инициализацию    
        self.initUI()

    def initUI(self):
        """Инициализация интерфейса редактора"""
        main_layout = QVBoxLayout()
        
        # Текущий документ
        self.current_document_display = QLabel("📄 Документ не выбран")
        self.current_document_display.setStyleSheet("""
            QLabel {
                font-size: 14pt;
                font-weight: bold;
                color: #2980b9;
                background-color: #e8f4fd;
                border: 2px solid #3498db;
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 10px;
            }
        """)
        self.current_document_display.setWordWrap(True)
        self.current_document_display.setMaximumHeight(60)
        main_layout.addWidget(self.current_document_display)
        
        # === ПОИСК ПО ПОЛЯМ ===
        search_widget = QWidget()
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(5, 5, 5, 5)

        search_label = QLabel("🔍 Поиск:")
        search_label.setStyleSheet("font-weight: bold; font-size: 11pt;")

        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Начните вводить название поля или блока...")
        self.search_field.textChanged.connect(self.filter_fields)
        self.search_field.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #3498db;
                border-radius: 6px;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border-color: #2980b9;
                box-shadow: 0 0 5px rgba(52, 152, 219, 0.5);
            }
        """)

        clear_search_btn = QPushButton("✕")
        clear_search_btn.setFixedSize(30, 30)
        clear_search_btn.setStyleSheet("""
            QPushButton {
                background: #e74c3c;
                color: white;
                border: none;
                border-radius: 15px;
                font-weight: bold;
            }
            QPushButton:hover { background: #c0392b; }
        """)
        clear_search_btn.clicked.connect(lambda: self.search_field.clear())

        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_field)
        search_layout.addWidget(clear_search_btn)
        search_widget.setLayout(search_layout)
        main_layout.addWidget(search_widget)
        
        # Прокручиваемая область
        scroll_area = QScrollArea()
        scroll_area.setStyleSheet(AppStyles.scroll_area())
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        
        # Создаем все блоки
        self.main_group = self.create_main_data_group()
        self.pub_group = self.create_publication_group()
        self.control_group = self.create_control_group()
        self.filing_group = self.create_filing_group()
        self.signers_group = self.create_signers_approvers_group()

        scroll_layout.addWidget(self.main_group)
        scroll_layout.addWidget(self.pub_group)
        scroll_layout.addWidget(self.control_group)
        scroll_layout.addWidget(self.filing_group)
        scroll_layout.addWidget(self.signers_group)
        scroll_layout.addStretch()
        
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFocusPolicy(Qt.NoFocus)
        main_layout.addWidget(scroll_area)
        
        # Панель кнопок
        button_layout = self.create_button_panel()
        button_widget = QWidget()
        button_widget.setFixedHeight(70)
        button_widget.setLayout(button_layout)
        main_layout.addWidget(button_widget)
        
        self.setLayout(main_layout)
    def _make_spinbox_scroll_safe(self, spinbox):
        """Делает QSpinBox безопасным для прокрутки"""
        def wheelEvent(event):
            if not spinbox.hasFocus():
                event.ignore()  # Прокрутка уйдет родителю
            else:
                QSpinBox.wheelEvent(spinbox, event)
        
        spinbox.wheelEvent = wheelEvent
    def _make_dateedit_scroll_safe(self, dateedit):
        """Делает QDateEdit безопасным для прокрутки"""
        def wheelEvent(event):
            if not dateedit.hasFocus():
                event.ignore()
            else:
                QDateEdit.wheelEvent(dateedit, event)
        
        dateedit.wheelEvent = wheelEvent
    def create_main_data_group(self):
        """📄 Создание группы основных данных"""
        group = CollapsibleGroupBox("📄 Основные данные документа", collapsed=False)
        
        # Статус
        if self.reference_manager:
            self.status_field = EditableComboBox(self.reference_manager, 'status')
            self.status_field.setFocusPolicy(Qt.StrongFocus)
        else:
            self.status_field = QComboBox()
            self.status_field.setFocusPolicy(Qt.StrongFocus)
            self.status_field.addItems(["Действующий", "Утративший силу", "На согласовании"])
        
        # Тип документа
        if self.reference_manager:
            self.type_field = EditableComboBox(self.reference_manager, 'document_types')
            self.type_field.setFocusPolicy(Qt.StrongFocus)
        else:
            self.type_field = QComboBox()
            self.type_field.setFocusPolicy(Qt.StrongFocus)
            self.type_field.addItems(["Приказ", "Распоряжение", "Положение"])
        
        # Вид документа
        if self.reference_manager:
            self.document_kind_field = EditableComboBox(self.reference_manager, 'document_kinds')
        else:
            self.document_kind_field = QComboBox()
            self.document_kind_field.addItems(["Внутренний", "Внешний"])
        
        # Тип подписания
        if self.reference_manager:
            self.signing_type_field = EditableComboBox(self.reference_manager, 'signing_types')
        else:
            self.signing_type_field = QComboBox()
            self.signing_type_field.addItems(["Единолично", "Коллегиально"])
        
        # Регистрационный номер
        self.reg_number_field = QLineEdit()
        #self.reg_number_field.setStyleSheet(AppStyles.line_e())
        self.reg_number_field.setPlaceholderText("Например: 123/2024-РП")
        

        

        self.reg_date_field = EnhancedDateEdit()
        self._make_dateedit_scroll_safe(self.reg_date_field)
        # Исполнитель (С ПОИСКОМ)
        if self.reference_manager:
            self.executor_field = SearchableComboBox(self.reference_manager, 'executors')
        else:
            self.executor_field = QLineEdit()
            self.executor_field.setPlaceholderText("ФИО исполнителя")
        
        # Ответственный исполнитель (С ПОИСКОМ)
        if self.reference_manager:
            self.responsible_executor_field = SearchableComboBox(self.reference_manager, 'responsible_executors')
        else:
            self.responsible_executor_field = QLineEdit()
            self.responsible_executor_field.setPlaceholderText("ФИО ответственного")
        
        # Тема
        if self.reference_manager:
            self.theme_field = EditableComboBox(self.reference_manager, 'themes')
        else:
            self.theme_field = QLineEdit()
            self.theme_field.setPlaceholderText("Тема документа")
        
        # Заголовок
        self.title_field = QLineEdit()
        self.title_field.setPlaceholderText("Полное название документа")
        
        # Количество листов
        self.pages_count_field = QSpinBox()
        self.pages_count_field.setMinimum(0)
        self.pages_count_field.setMaximum(9999)
        self.pages_count_field.setSuffix(" л.")
        self._make_spinbox_scroll_safe(self.pages_count_field)  
        # Количество приложений
        self.attachments_count_field = QSpinBox()
        self.attachments_count_field.setMinimum(0)
        self.attachments_count_field.setMaximum(999)
        self.attachments_count_field.setSuffix(" шт.")
        self._make_spinbox_scroll_safe(self.attachments_count_field)  
        # Добавление полей
        group.add_row("📊 Статус:", self.status_field)
        group.add_row("📄 Тип документа:", self.type_field)
        group.add_row("📋 Вид документа:", self.document_kind_field)
        group.add_row("✍️ Тип подписания:", self.signing_type_field)
        group.add_row("🔢 Рег. номер:", self.reg_number_field)
        group.add_row("📅 Рег. дата:", self.reg_date_field)
        group.add_row("👤 Исполнитель:", self.executor_field)
        group.add_row("👤 Ответственный:", self.responsible_executor_field)
        group.add_row("📝 Тема:", self.theme_field)
        group.add_row("📋 Заголовок:", self.title_field)
        group.add_row("📄 Количество листов:", self.pages_count_field)
        group.add_row("📎 Приложения:", self.attachments_count_field)
        file_select_widget = QWidget()
        file_select_layout = QHBoxLayout()
        file_select_layout.setContentsMargins(0, 0, 0, 0)
        
        self.document_path_field = QLineEdit()
        self.document_path_field.setPlaceholderText("Путь к файлу не выбран")
        self.document_path_field.setReadOnly(True)
        
        self.select_file_btn = QPushButton("📂 Выбрать файл")
        self.select_file_btn.clicked.connect(self.select_document_file)
        self.select_file_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        
        file_select_layout.addWidget(self.document_path_field, 1)
        file_select_layout.addWidget(self.select_file_btn)
        file_select_widget.setLayout(file_select_layout)
        group.add_row("📄 Файл документа:", file_select_widget)
        return group
    def select_document_file(self):
        """Выбрать файл документа"""
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл документа",
            "",
            "Word Files (*.doc *.docx);;PDF Files (*.pdf);;All Files (*)",
            options=options
        )
        
        if file_path:
            self.document_path_field.setText(file_path)
            # ✅ НОВОЕ: Сохраняем полный путь к новому файлу
            self._new_document_path = file_path
            print(f"📂 Выбран новый файл: {file_path}")
    def create_publication_group(self):
        """📰 Блок публикации"""
        group = CollapsibleGroupBox("📰 Блок публикации", collapsed=True)
        
        # Подлежит ли опубликованию
        self.should_publish_field = QComboBox()
        self.should_publish_field.addItems(["Не указано", "Да", "Нет"])
        self.should_publish_field.setFocusPolicy(Qt.StrongFocus)  # ДОБАВИТЬ ЭТО
        self.should_publish_field.wheelEvent = lambda event: event.ignore() if not self.should_publish_field.hasFocus() else QComboBox.wheelEvent(self.should_publish_field, event)
        # Где опубликовано
        if self.reference_manager:
            self.published_where_field = EditableComboBox(self.reference_manager, 'published_where')
        else:
            self.published_where_field = QComboBox()
            self.published_where_field.addItems(["-- Не выбрано --", "Официальный сайт", "Информационный стенд"])
        
        # Дата публикации
        self.published_date_field = EnhancedDateEdit()
        # Номер газеты (бывший "Доп. номер")
        self.newspaper_number_field = QLineEdit()
        self.newspaper_number_field.setPlaceholderText("Номер газеты")
        self.newspaper_number_field.setStyleSheet("""
            QLineEdit {
                padding: 6px;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
            }
        """)
        
        group.add_row("❓ Подлежит опубликованию:", self.should_publish_field)
        group.add_row("📍 Где опубликовано:", self.published_where_field)
        group.add_row("📅 Дата публикации:", self.published_date_field)
        group.add_row("📰 Номер газеты:", self.newspaper_number_field)
        return group

    def create_control_group(self):
        """⚖️ Блок контроля"""
        group = CollapsibleGroupBox("⚖️ Блок контроля за исполнением", collapsed=True)
        
        # Дата контроля
        self.control_date_field = QDateEdit()
        self.control_date_field.setDate(QDate.currentDate())
        self.control_date_field.setCalendarPopup(True)
        self.control_date_field.setDisplayFormat("dd.MM.yyyy")
        self.control_date_field.setSpecialValueText("Не указана")
        self._make_dateedit_scroll_safe(self.control_date_field)
        # Результат исполнения
        self.execution_result_field = QTextEdit()
        self.execution_result_field.setMaximumHeight(80)
        self.execution_result_field.setPlaceholderText("Результат исполнения...")
        
        # Снято с контроля
        self.removed_from_control_field = QComboBox()
        self.removed_from_control_field.addItems(["Нет", "Да"])
        self.removed_from_control_field.setFocusPolicy(Qt.StrongFocus)  # ДОБАВИТЬ ЭТО
        self.removed_from_control_field.wheelEvent = lambda event: event.ignore() if not self.removed_from_control_field.hasFocus() else QComboBox.wheelEvent(self.removed_from_control_field, event)
        group.add_row("📅 Дата контроля:", self.control_date_field)
        group.add_row("✅ Результат исполнения:", self.execution_result_field)
        group.add_row("📤 Снято с контроля:", self.removed_from_control_field)
        
        return group

    def create_filing_group(self):
        """📁 Блок списания"""
        group = CollapsibleGroupBox("📁 Блок отметки о списании документа в дело", collapsed=True)
        
        # Дело номер
        self.case_number_field = QLineEdit()
        self.case_number_field.setPlaceholderText("Например: 01-05")
        
        # Том номер
        self.volume_number_field = QLineEdit()
        self.volume_number_field.setPlaceholderText("Например: 1")
        
        # Листы
        self.sheets_field = QLineEdit()
        self.sheets_field.setPlaceholderText("Например: 1-15")
        
        group.add_row("📄 Дело номер:", self.case_number_field)
        group.add_row("📚 Том номер:", self.volume_number_field)
        group.add_row("📝 Листы:", self.sheets_field)
        
        return group

    def create_signers_approvers_group(self):
        """✍️🤝 Блок подписантов и согласующих"""
        group = CollapsibleGroupBox("✍️🤝 Подписанты и согласующие", collapsed=True)
        
        # Используем VBoxLayout вместо FormLayout для этой группы
        content_layout = QVBoxLayout()
        
        # Подписанты
        signers_label = QLabel("✍️ Подписанты:")
        signers_label.setStyleSheet("font-weight: bold; font-size: 12pt; margin-top: 5px;")
        content_layout.addWidget(signers_label)
        
        self.signers_list = QListWidget()
        self.signers_list.setMaximumHeight(120)
        self.signers_list.setSelectionMode(QAbstractItemView.MultiSelection)
        content_layout.addWidget(self.signers_list)
        
        signers_buttons = QHBoxLayout()
        self.add_signer_btn = QPushButton("➕ Добавить подписанта")
        self.add_signer_btn.setStyleSheet(AppStyles.button_success())
        self.remove_signer_btn = QPushButton("➖ Удалить подписанта")
        self.remove_signer_btn.setStyleSheet(AppStyles.button_danger())
        signers_buttons.addWidget(self.add_signer_btn)
        signers_buttons.addWidget(self.remove_signer_btn)
        content_layout.addLayout(signers_buttons)
        
        # Согласующие
        content_layout.addSpacing(20)
        approvers_label = QLabel("🤝 Согласующие:")
        approvers_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        content_layout.addWidget(approvers_label)
        
        self.approvers_list = QListWidget()
        self.approvers_list.setMaximumHeight(120)
        self.approvers_list.setSelectionMode(QAbstractItemView.MultiSelection)
        content_layout.addWidget(self.approvers_list)
        
        approvers_buttons = QHBoxLayout()
        self.add_approver_btn = QPushButton("➕ Добавить согласующего")
        self.add_approver_btn.setStyleSheet(AppStyles.button_success())
        self.remove_approver_btn = QPushButton("➖ Удалить согласующего")
        self.remove_approver_btn.setStyleSheet(AppStyles.button_danger())
        approvers_buttons.addWidget(self.add_approver_btn)
        approvers_buttons.addWidget(self.remove_approver_btn)
        content_layout.addLayout(approvers_buttons)
        
        # Заменяем стандартный layout группы
        old_layout = group.content_widget.layout()
        QWidget().setLayout(old_layout)  # Удаляем старый layout
        group.content_widget.setLayout(content_layout)
        
        # Подключаем обработчики
        self.add_signer_btn.clicked.connect(self.add_signer)
        self.remove_signer_btn.clicked.connect(self.remove_signer)
        self.add_approver_btn.clicked.connect(self.add_approver)
        self.remove_approver_btn.clicked.connect(self.remove_approver)
        
        # Загружаем справочники
        self.load_signers_approvers_data()
        
        return group
    
    def load_signers_approvers_data(self):
        """Загрузка справочников подписантов и согласующих"""
        try:
            if self.reference_manager:
                print("📋 Загрузка справочников подписантов и согласующих...")
                
                # Загружаем подписантов
                self.signers_data = self.reference_manager.get_reference_items('signers')
                print(f"  ✅ Загружено подписантов: {len(self.signers_data)}")
                
                # Загружаем согласующих
                self.approvers_data = self.reference_manager.get_reference_items('approvers')
                print(f"  ✅ Загружено согласующих: {len(self.approvers_data)}")
                
                # Проверяем результаты
                if not self.signers_data:
                    print("  ⚠️ Справочник подписантов пуст")
                if not self.approvers_data:
                    print("  ⚠️ Справочник согласующих пуст")
                    
            else:
                print("  ❌ ReferenceManager недоступен")
                self.signers_data = []
                self.approvers_data = []
                
        except Exception as e:
            print(f"❌ Ошибка загрузки справочников подписантов/согласующих: {e}")
            import traceback
            traceback.print_exc()
            self.signers_data = []
            self.approvers_data = []
    
    def add_signer(self):
        """Добавить подписанта с функцией поиска"""
        if not hasattr(self, 'signers_data') or not self.signers_data:
            print("⚠️ Список подписантов пуст или не загружен, перезагружаем...")
            
            try:
                self.load_signers_approvers_data()
            except Exception as e:
                QMessageBox.critical(
                    self, 
                    "❌ Ошибка", 
                    f"Не удалось загрузить справочник подписантов:\n\n{str(e)}"
                )
                return
            
            if not self.signers_data:
                QMessageBox.information(
                    self,
                    "📋 Справочник пуст",
                    "Справочник подписантов пуст.\n\n"
                    "Добавьте подписантов в справочник через:\n"
                    "Меню → Справочники → Подписанты"
                )
                return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Выбор подписанта")
        dialog.resize(450, 400)
        
        layout = QVBoxLayout()
        
        # НОВОЕ: Поле поиска
        search_layout = QHBoxLayout()
        search_label = QLabel("🔍 Поиск:")
        search_field = QLineEdit()
        search_field.setPlaceholderText("Начните вводить ФИО...")
        search_field.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #3498db;
                border-radius: 6px;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border-color: #2980b9;
            }
        """)
        search_layout.addWidget(search_label)
        search_layout.addWidget(search_field)
        layout.addLayout(search_layout)
        
        # Список элементов
        list_widget = QListWidget()
        list_widget.setStyleSheet("QListWidget { font-size: 10pt; }")
        
        # Заполняем список
        def populate_list(filter_text=""):
            list_widget.clear()
            filter_text = filter_text.lower()
            
            for signer in self.signers_data:
                name = signer['name']
                if not filter_text or filter_text in name.lower():
                    item = QListWidgetItem(name)
                    item.setData(Qt.UserRole, signer['id'])
                    list_widget.addItem(item)
        
        populate_list()
        
        # Подключаем поиск
        search_field.textChanged.connect(populate_list)
        
        layout.addWidget(list_widget)
        
        # Кнопки
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        if dialog.exec_() == QDialog.Accepted:
            selected_item = list_widget.currentItem()
            if selected_item:
                # Проверяем дубликаты
                for i in range(self.signers_list.count()):
                    if self.signers_list.item(i).data(Qt.UserRole) == selected_item.data(Qt.UserRole):
                        QMessageBox.information(self, "Информация", "Этот подписант уже добавлен")
                        return
                
                # Добавляем в список
                new_item = QListWidgetItem(selected_item.text())
                new_item.setData(Qt.UserRole, selected_item.data(Qt.UserRole))
                self.signers_list.addItem(new_item)
    
    def remove_signer(self):
        """Удалить подписанта"""
        selected_items = self.signers_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Предупреждение", "Выберите подписанта для удаления")
            return
        
        for item in selected_items:
            self.signers_list.takeItem(self.signers_list.row(item))
    
    def add_approver(self):
        """Добавить согласующего с функцией поиска"""
        if not hasattr(self, 'approvers_data') or not self.approvers_data:
            print("⚠️ Список согласующих пуст или не загружен, перезагружаем...")
            
            try:
                self.load_signers_approvers_data()
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "❌ Ошибка",
                    f"Не удалось загрузить справочник согласующих:\n\n{str(e)}"
                )
                return
            
            if not self.approvers_data:
                QMessageBox.information(
                    self,
                    "📋 Справочник пуст",
                    "Справочник согласующих пуст.\n\n"
                    "Добавьте согласующих в справочник через:\n"
                    "Меню → Справочники → Согласующие"
                )
                return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Выбор согласующего")
        dialog.resize(450, 400)
        
        layout = QVBoxLayout()
        
        # НОВОЕ: Поле поиска
        search_layout = QHBoxLayout()
        search_label = QLabel("🔍 Поиск:")
        search_field = QLineEdit()
        search_field.setPlaceholderText("Начните вводить ФИО...")
        search_field.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #3498db;
                border-radius: 6px;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border-color: #2980b9;
            }
        """)
        search_layout.addWidget(search_label)
        search_layout.addWidget(search_field)
        layout.addLayout(search_layout)
        
        # Список элементов
        list_widget = QListWidget()
        list_widget.setStyleSheet("QListWidget { font-size: 10pt; }")
        
        # Заполняем список
        def populate_list(filter_text=""):
            list_widget.clear()
            filter_text = filter_text.lower()
            
            for approver in self.approvers_data:
                name = approver['name']
                if not filter_text or filter_text in name.lower():
                    item = QListWidgetItem(name)
                    item.setData(Qt.UserRole, approver['id'])
                    list_widget.addItem(item)
        
        populate_list()
        
        # Подключаем поиск
        search_field.textChanged.connect(populate_list)
        
        layout.addWidget(list_widget)
        
        # Кнопки
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        if dialog.exec_() == QDialog.Accepted:
            selected_item = list_widget.currentItem()
            if selected_item:
                # Проверяем дубликаты
                for i in range(self.approvers_list.count()):
                    if self.approvers_list.item(i).data(Qt.UserRole) == selected_item.data(Qt.UserRole):
                        QMessageBox.information(self, "Информация", "Этот согласующий уже добавлен")
                        return
                
                # Добавляем в список
                new_item = QListWidgetItem(selected_item.text())
                new_item.setData(Qt.UserRole, selected_item.data(Qt.UserRole))
                self.approvers_list.addItem(new_item)
    def clear_form(self):
        """Полная очистка формы и сброс данных"""
        # Сброс ID документа
        self.current_document_id = None
        
        # Обновление заголовка
        self.current_document_display.setText("📄 Документ не выбран")
        
        # Очистка всех полей
        # Комбобоксы - сброс на первый элемент
        if hasattr(self.status_field, 'combo'):
            self.status_field.combo.setCurrentIndex(0)
        if hasattr(self.type_field, 'combo'):
            self.type_field.combo.setCurrentIndex(0)
        if hasattr(self.document_kind_field, 'combo'):
            self.document_kind_field.combo.setCurrentIndex(0)
        if hasattr(self.signing_type_field, 'combo'):
            self.signing_type_field.combo.setCurrentIndex(0)
        if hasattr(self.executor_field, 'combo'):
            self.executor_field.combo.setCurrentIndex(0)
        if hasattr(self.responsible_executor_field, 'combo'):
            self.responsible_executor_field.combo.setCurrentIndex(0)
        if hasattr(self.theme_field, 'combo'):
            self.theme_field.combo.setCurrentIndex(0)
        if hasattr(self.published_where_field, 'combo'):
            self.published_where_field.combo.setCurrentIndex(0)
        
        # Текстовые поля
        self.reg_number_field.clear()
        self.newspaper_number_field.clear()
        self.title_field.clear()
        self.case_number_field.clear()
        self.volume_number_field.clear()
        self.sheets_field.clear()
        if hasattr(self, 'document_path_field'):
            self.document_path_field.clear()
        
        # Даты - сброс на текущую дату
        from PyQt5.QtCore import QDate
        self.reg_date_field.setDate(QDate.currentDate())
        self.published_date_field.setDate(QDate.currentDate())
        self.control_date_field.setDate(QDate.currentDate())
        
        # Числовые поля
        self.pages_count_field.setValue(0)
        self.attachments_count_field.setValue(0)
        
        # Текстовые области
        self.execution_result_field.clear()
        
        # КРИТИЧНО: Очистка подписантов и согласующих
        self.signers_list.clear()
        self.approvers_list.clear()
        
        # КРИТИЧНО: Очистка кешированных данных
        self.signers_data = []
        self.approvers_data = []
        
        # Обновление статуса
        self.status_label.setText("📄 Документ не выбран")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #7f8c8d;
                font-size: 12pt;
                padding: 10px;
                background-color: #f8f9fa;
                border-radius: 5px;
            }
        """)
        if hasattr(self, 'delete_button'):
            self.delete_button.setEnabled(False)
        if hasattr(self, 'reset_button'):
            self.reset_button.setEnabled(False)
        if hasattr(self, 'open_in_word_button'):
            self.open_in_word_button.setEnabled(False)
        
        print("🧹 Форма полностью очищена")
    def reset_form_changes(self):
        """
        Сбросить несохраненные изменения и перезагрузить данные документа
        """
        if not self.current_document_id:
            return
        
        try:
            # Запрашиваем подтверждение
            reply = QMessageBox.question(
                self,
                "⚠️ Подтверждение сброса",
                "Вы уверены, что хотите сбросить все несохраненные изменения?\n\n"
                "Все внесенные изменения будут потеряны.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
            
            # Перезагружаем данные документа из БД
            document_data = self.db_manager.get_document_by_id(self.current_document_id)
            
            if document_data:
                self.set_initial_data(document_data)
                
                self.status_label.setText("↩️ Изменения сброшены")
                self.status_label.setStyleSheet("""
                    QLabel {
                        color: #f39c12;
                        font-size: 12pt;
                        padding: 10px;
                        font-weight: bold;
                        background-color: #fef5e7;
                        border-radius: 5px;
                    }
                """)
                
                print(f"↩️ Изменения сброшены для документа ID {self.current_document_id}")
            else:
                QMessageBox.warning(
                    self,
                    "⚠️ Ошибка",
                    "Не удалось загрузить данные документа"
                )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "❌ Ошибка",
                f"Не удалось сбросить изменения:\n\n{str(e)}"
            )
            print(f"❌ Ошибка сброса изменений: {e}")
            import traceback
            traceback.print_exc()
    def delete_current_document(self):
        """
        Удалить текущий открытый документ
        """
        if not self.current_document_id:
            QMessageBox.warning(
                self,
                "⚠️ Документ не выбран",
                "Сначала выберите документ для удаления"
            )
            return
        
        try:
            # Получаем название документа для подтверждения
            doc_title = self.title_field.text().strip() or "Без названия"
            
            # Запрашиваем подтверждение
            reply = QMessageBox.question(
                self,
                "⚠️ Подтверждение удаления",
                f"Вы действительно хотите удалить документ?\n\n"
                f"📄 {doc_title}\n"
                f"🆔 ID: {self.current_document_id}\n\n"
                f"⚠️ ЭТО ДЕЙСТВИЕ НЕЛЬЗЯ ОТМЕНИТЬ!",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
            
            # Удаляем документ из базы данных
            self.db_manager.delete_document(self.current_document_id)
            
            # Очищаем форму
            self.clear_form()
            
            # Получаем главное окно для обновления таблицы
            main_window = self.get_main_window()
            if main_window and hasattr(main_window, 'documents_table_view'):
                main_window.documents_table_view.load_documents()
            
            QMessageBox.information(
                self,
                "✅ Успешно",
                f"Документ успешно удалён:\n{doc_title}"
            )
            
            print(f"✅ Документ ID {self.current_document_id} удален")
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "❌ Ошибка удаления",
                f"Не удалось удалить документ:\n\n{str(e)}"
            )
            print(f"❌ Ошибка удаления документа: {e}")
            import traceback
            traceback.print_exc()
    def reload_reference_data(self):
        """Перезагрузка всех справочников из БД"""
        try:
            print("🔄 Перезагрузка справочников...")
            
            # Перезагружаем комбобоксы
            if hasattr(self.status_field, 'load_items'):
                self.status_field.load_items()
            if hasattr(self.type_field, 'load_items'):
                self.type_field.load_items()
            if hasattr(self.document_kind_field, 'load_items'):
                self.document_kind_field.load_items()
            if hasattr(self.signing_type_field, 'load_items'):
                self.signing_type_field.load_items()
            if hasattr(self.executor_field, 'load_items'):
                self.executor_field.load_items()
            if hasattr(self.responsible_executor_field, 'load_items'):
                self.responsible_executor_field.load_items()
            if hasattr(self.theme_field, 'load_items'):
                self.theme_field.load_items()
            if hasattr(self.published_where_field, 'load_items'):
                self.published_where_field.load_items()
            
            # КРИТИЧНО: Перезагружаем подписантов и согласующих
            self.load_signers_approvers_data()
            
            print("✅ Справочники перезагружены")
            
        except Exception as e:
            print(f"❌ Ошибка перезагрузки справочников: {e}")
    def edit_approver(self):
        """Редактировать согласующего"""
        selected_rows = self.approvers_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        approver_id = self.approvers_model._data[row][0]
        approver_name = self.approvers_model._data[row][1]
        
        new_name, ok = QInputDialog.getText(self, "Редактирование", "ФИО:", QLineEdit.Normal, approver_name)
        
        if ok and new_name.strip():
            try:
                query = "UPDATE ref_approvers SET name = ? WHERE id = ?"
                self.db_manager.execute_update(query, (new_name.strip(), approver_id))
                QMessageBox.information(self, "Успех", "Согласующий обновлен!")
                self.load_approvers()
                self.references_updated.emit()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка при обновлении: {str(e)}")

    def delete_approver(self):
        """Удалить согласующего"""
        selected_rows = self.approvers_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        approver_id = self.approvers_model._data[row][0]
        approver_name = self.approvers_model._data[row][1]
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить согласующего '{approver_name}'?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                query = "DELETE FROM ref_approvers WHERE id = ?"
                self.db_manager.execute_update(query, (approver_id,))
                QMessageBox.information(self, "Успех", f"Согласующий '{approver_name}' удален!")
                self.load_approvers()
                self.references_updated.emit()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка при удалении: {str(e)}")    
    def remove_approver(self):
        """Удалить согласующего"""
        selected_items = self.approvers_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Предупреждение", "Выберите согласующего для удаления")
            return
        
        for item in selected_items:
            self.approvers_list.takeItem(self.approvers_list.row(item))

    def create_button_panel(self):
        """Создание панели кнопок с предпросмотром и открытием файла"""
        button_layout = QHBoxLayout()
        
        # ✅ ДОБАВИТЬ: Кнопка быстрого просмотра
        self.delete_button = QPushButton("🗑️ Удалить документ")
        self.delete_button.setStyleSheet(AppStyles.button_danger())
        self.delete_button.clicked.connect(self.delete_current_document)
        self.delete_button.setEnabled(False)
        
        # ✅ ДОБАВИТЬ: Кнопка открытия в Word
        self.open_in_word_button = QPushButton("📂 Открыть в Word")
        self.open_in_word_button.setStyleSheet(AppStyles.button_primary())
        self.open_in_word_button.clicked.connect(self.open_file_in_word)
        self.open_in_word_button.setEnabled(False)  # Отключена пока не выбран документ
        # === НОВОЕ: Кнопка сброса изменений ===
        self.reset_button = QPushButton("↩️ Сбросить изменения")
        self.reset_button.setStyleSheet(AppStyles.button_warning())
        self.reset_button.clicked.connect(self.reset_form_changes)
        self.reset_button.setEnabled(False)
        # Существующая кнопка сохранения
        self.save_button = QPushButton("💾 Сохранить все данные")
        self.save_button.setStyleSheet(AppStyles.button_success())
        self.save_button.clicked.connect(self.save_metadata)
        
        self.status_label = QLabel("📄 Документ не выбран")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #7f8c8d;
                font-size: 12pt;
                padding: 10px;
                background-color: #f8f9fa;
                border-radius: 5px;
            }
        """)
        
        # ✅ ОБНОВИТЬ: Добавляем новые кнопки в layout
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.reset_button)
        button_layout.addWidget(self.open_in_word_button)
        button_layout.addWidget(self.save_button)
        button_layout.addStretch()
        button_layout.addWidget(self.status_label)
        
        return button_layout

    def filter_fields(self, text):
        """Фильтрация по конкретным полям внутри блоков"""
        text_lower = text.lower().strip()
        
        text_lower = text.lower().strip()
    
        # Список групп для обработки
        groups_to_process = [
            self.main_group,
            self.pub_group,
            self.control_group,
            self.filing_group
        ]
        
        if not text_lower:
            # Показываем все поля и блоки БЕЗ ПОДСВЕТКИ
            for group in groups_to_process:
                self._show_all_fields_in_group(group)
                self._clear_highlight_in_group(group)  # ДОБАВИТЬ
                group.setVisible(True)
            self.signers_group.setVisible(True)
            return
        
        # Проходим по каждой группе
        for group in groups_to_process:
            visible_count = self._filter_group_fields(group, text_lower)
            # Показываем блок только если есть видимые поля
            group.setVisible(visible_count > 0)
        
        # Специальная обработка для блока подписантов (нет FormLayout)
        signers_visible = any(keyword in text_lower for keyword in ['подписан', 'подписант', 'согласующ', 'согласова'])
        self.signers_group.setVisible(signers_visible)
    def _clear_highlight_in_group(self, group):
        """Убрать подсветку со всех полей в группе"""
        layout = group.content_layout
        if not isinstance(layout, QFormLayout):
            return
        
        for i in range(layout.rowCount()):
            label_item = layout.itemAt(i, QFormLayout.LabelRole)
            
            if label_item and label_item.widget():
                # Сбрасываем стиль
                label_item.widget().setStyleSheet("")
    def _show_all_fields_in_group(self, group):
        """Показать все поля в группе"""
        layout = group.content_layout
        if not isinstance(layout, QFormLayout):
            return
        
        for i in range(layout.rowCount()):
            label_item = layout.itemAt(i, QFormLayout.LabelRole)
            field_item = layout.itemAt(i, QFormLayout.FieldRole)
            
            if label_item and label_item.widget():
                label_item.widget().setVisible(True)
            if field_item and field_item.widget():
                field_item.widget().setVisible(True)

    def _filter_group_fields(self, group, search_text):
        """Фильтровать поля в группе по поисковому запросу"""
        layout = group.content_layout
        if not isinstance(layout, QFormLayout):
            return 0
        
        visible_count = 0
        
        for i in range(layout.rowCount()):
            label_item = layout.itemAt(i, QFormLayout.LabelRole)
            field_item = layout.itemAt(i, QFormLayout.FieldRole)
            
            label_text = ""
            if label_item and label_item.widget():
                label_widget = label_item.widget()
                if isinstance(label_widget, QLabel):
                    label_text = label_widget.text().lower()
                    label_text = ''.join(c for c in label_text if c.isalnum() or c.isspace())
            
            is_visible = search_text in label_text
            
            # НОВОЕ: Подсветка найденных полей
            if label_item and label_item.widget():
                label_item.widget().setVisible(is_visible)
                if is_visible:
                    # Подсвечиваем найденное поле
                    label_item.widget().setStyleSheet("""
                        QLabel {
                            background-color: #fff3cd;
                            border: 2px solid #ffc107;
                            border-radius: 4px;
                            padding: 4px;
                            font-weight: bold;
                        }
                    """)
                else:
                    # Сбрасываем стиль для скрытых
                    label_item.widget().setStyleSheet("")
            
            if field_item and field_item.widget():
                field_item.widget().setVisible(is_visible)
            
            if is_visible:
                visible_count += 1
        
        return visible_count
    def _normalize_search_text(self, text):
        """Нормализация поискового запроса с синонимами"""
        text = text.lower().strip()
        
        # Словарь синонимов
        synonyms = {
            'статус': ['статус', 'состояние'],
            'тип': ['тип', 'вид', 'категория'],
            'номер': ['номер', 'num', '№'],
            'дата': ['дата', 'date', 'день'],
            'исполнитель': ['исполнитель', 'исполн', 'ответственный'],
            'публикация': ['публикация', 'публик', 'опубликован'],
            'подписант': ['подписант', 'подпис', 'подписывающий'],
        }
        
        # Ищем совпадения с синонимами
        for key, values in synonyms.items():
            if text in values:
                return key
        
        return text

    def set_initial_data(self, document_data):
        """Установка начальных данных документа"""
        if not document_data:
            return
        
        try:
            self.current_document_id = document_data.get("id")
            
            title = document_data.get("title", "Без названия")
            self.current_document_display.setText(f"📄 Текущий документ: {title}")
            
            # Основные данные
            if hasattr(self.status_field, 'set_current_by_id'):
                self.status_field.set_current_by_id(document_data.get("status_id"))
            
            if hasattr(self.type_field, 'set_current_by_id'):
                self.type_field.set_current_by_id(document_data.get("type_id"))
            
            if hasattr(self.document_kind_field, 'set_current_by_id'):
                self.document_kind_field.set_current_by_id(document_data.get("document_kind_id"))
            
            if hasattr(self.signing_type_field, 'set_current_by_id'):
                self.signing_type_field.set_current_by_id(document_data.get("signing_type_id"))
            if hasattr(self, 'document_path_field'):
                document_path = document_data.get("document_path", "") or document_data.get("filepath", "")
                self.document_path_field.setText(document_path)
            self.reg_number_field.setText(document_data.get("reg_number", ""))
            self.newspaper_number_field.setText(document_data.get("number", ""))
            
            reg_date = document_data.get("reg_date")
            if reg_date:
                try:
                    parsed_date = datetime.strptime(reg_date, "%Y-%m-%d")
                    self.reg_date_field.setDate(QDate(parsed_date.year, parsed_date.month, parsed_date.day))
                except:
                    pass
            
            if hasattr(self.executor_field, 'set_current_by_id'):
                self.executor_field.set_current_by_id(document_data.get("executor_id"))
            
            if hasattr(self.responsible_executor_field, 'set_current_by_id'):
                self.responsible_executor_field.set_current_by_id(document_data.get("responsible_executor_id"))
            
            if hasattr(self.theme_field, 'set_current_by_id'):
                self.theme_field.set_current_by_id(document_data.get("theme_id"))
            
            self.title_field.setText(document_data.get("title", ""))
            self.pages_count_field.setValue(document_data.get("pages_count", 0) or 0)
            self.attachments_count_field.setValue(document_data.get("attachments_count", 0) or 0)
            
            # Публикация
            should_publish = document_data.get("should_publish", "")
            if should_publish == "Да":
                self.should_publish_field.setCurrentText("Да")
            elif should_publish == "Нет":
                self.should_publish_field.setCurrentText("Нет")
            else:
                self.should_publish_field.setCurrentText("Не указано")
            
            if hasattr(self.published_where_field, 'set_current_by_id'):
                self.published_where_field.set_current_by_id(document_data.get("published_where_id"))
            
            published_date = document_data.get("published_date")
            if published_date:
                try:
                    parsed_date = datetime.strptime(published_date, "%Y-%m-%d")
                    self.published_date_field.setDate(QDate(parsed_date.year, parsed_date.month, parsed_date.day))
                except:
                    pass
            
            # Контроль
            control_date = document_data.get("control_date")
            if control_date:
                try:
                    parsed_date = datetime.strptime(control_date, "%Y-%m-%d")
                    self.control_date_field.setDate(QDate(parsed_date.year, parsed_date.month, parsed_date.day))
                except:
                    pass
            
            self.execution_result_field.setPlainText(document_data.get("execution_result", "") or "")
            
            removed = document_data.get("removed_from_control", "")
            self.removed_from_control_field.setCurrentText("Да" if removed == "Да" or removed is True else "Нет")
            
            # Списание
            self.case_number_field.setText(document_data.get("case_number", ""))
            self.volume_number_field.setText(document_data.get("volume_number", ""))
            self.sheets_field.setText(document_data.get("sheets", ""))
            
            # Подписанты и согласующие
            self.load_document_signers_approvers(self.current_document_id)
            
            self.status_label.setText(f"📄 Редактируем документ ID: {self.current_document_id}")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #2980b9;
                    font-size: 12pt;
                    padding: 10px;
                    font-weight: bold;
                    background-color: #e8f4fd;
                    border-radius: 5px;
                }
            """)
            if self.current_document_id:
                self.delete_button.setEnabled(True)
                self.reset_button.setEnabled(True)
                self.open_in_word_button.setEnabled(True)
            
        except Exception as e:
            print(f"❌ Ошибка при загрузке данных: {e}")
            import traceback
            traceback.print_exc()
    
    def load_document_signers_approvers(self, document_id):
        """Загрузка подписантов и согласующих для документа"""
        try:
            if not self.db_manager:
                return
            
            self.signers_list.clear()
            self.approvers_list.clear()
            
            signers_query = """
                SELECT rs.id, rs.name
                FROM document_signers ds
                JOIN ref_signers rs ON ds.signer_id = rs.id
                WHERE ds.document_id = ?
            """
            signers = self.db_manager.execute_query(signers_query, (document_id,))
            
            for signer in signers:
                item = QListWidgetItem(signer['name'])
                item.setData(Qt.UserRole, signer['id'])
                self.signers_list.addItem(item)
            
            approvers_query = """
                SELECT ra.id, ra.name
                FROM document_approvers da
                JOIN ref_approvers ra ON da.approver_id = ra.id
                WHERE da.document_id = ?
            """
            approvers = self.db_manager.execute_query(approvers_query, (document_id,))
            
            for approver in approvers:
                item = QListWidgetItem(approver['name'])
                item.setData(Qt.UserRole, approver['id'])
                self.approvers_list.addItem(item)
            
        except Exception as e:
            print(f"❌ Ошибка загрузки подписантов/согласующих: {e}")

    def save_metadata(self):
        """Сохранение всех метаданных"""
        try:
            if not self.current_document_id:
                QMessageBox.warning(self, "Предупреждение", "Не выбран документ для редактирования")
                return
            
            if not self.db_manager:
                QMessageBox.critical(self, "Ошибка", "База данных недоступна")
                return
            
            # ============================================================
            # ✅ НОВЫЙ БЛОК: Обработка замены файла документа
            # ============================================================
            document_path_to_save = None
            
            # Проверяем, был ли выбран новый файл
            if hasattr(self, '_new_document_path') and self._new_document_path:
                print("\n" + "="*80)
                print("🔄 ОБРАБОТКА ЗАМЕНЫ ФАЙЛА ДОКУМЕНТА")
                print("="*80)
                
                new_file_path = self._new_document_path
                
                # Проверяем что файл существует
                if not os.path.exists(new_file_path):
                    QMessageBox.critical(
                        self,
                        "❌ Ошибка",
                        f"Выбранный файл не найден:\n{new_file_path}"
                    )
                    return
                
                print(f"📂 Новый файл: {new_file_path}")
                
                try:
                    # Получаем текущие данные документа из БД
                    current_doc_data = self.db_manager.get_document_by_id(self.current_document_id)
                    old_document_path = current_doc_data.get('document_path', '')
                    
                    if old_document_path:
                        print(f"📄 Старый файл (относительный путь): {old_document_path}")
                    else:
                        print("📄 Старый файл отсутствовал")
                    
                    # Определяем год и месяц из даты регистрации
                    reg_date_qobject = self.reg_date_field.date()
                    year = reg_date_qobject.year()
                    month = reg_date_qobject.month()
                    
                    print(f"📅 Дата регистрации: {year}-{month:02d}")
                    
                    # Получаем путь к целевой папке
                    target_folder = self.db_manager.get_files_path(year, month)
                    print(f"📁 Целевая папка: {target_folder}")
                    
                    # Создаем папку если не существует
                    if not os.path.exists(target_folder):
                        print(f"📁 Создаем папку: {target_folder}")
                        os.makedirs(target_folder, exist_ok=True)
                    
                    # Формируем имя нового файла
                    # Формируем имя нового файла - СОХРАНЯЕМ ОРИГИНАЛЬНОЕ НАЗВАНИЕ
                    original_filename = os.path.basename(new_file_path)  # Оригинальное имя с расширением
                    new_file_name = os.path.join(target_folder, original_filename)
                    
                    print(f"📝 Оригинальное имя файла: {original_filename}")
                    # Проверяем существование файла с таким именем
                    counter = 1
                    original_new_file_name = new_file_name
                    original_name_without_ext = os.path.splitext(original_filename)[0]
                    original_ext = os.path.splitext(original_filename)[1]
                    
                    while os.path.exists(new_file_name):
                        new_file_name = os.path.join(target_folder, f"{original_name_without_ext}_{counter}{original_ext}")
                        counter += 1
                        print(f"⚠️ Файл существует, пробуем: {os.path.basename(new_file_name)}")
                    
                    if new_file_name != original_new_file_name:
                        print(f"✅ Финальное имя файла: {os.path.basename(new_file_name)}")
                    
                    # Копируем новый файл
                    print(f"\n📋 Копирование нового файла...")
                    print(f"   Источник: {new_file_path}")
                    print(f"   Назначение: {new_file_name}")
                    
                    shutil.copy2(new_file_path, new_file_name)
                    
                    print(f"✅ Файл успешно скопирован!")
                    
                    # Проверяем что файл скопирован
                    if not os.path.exists(new_file_name):
                        raise Exception(f"Файл не найден после копирования: {new_file_name}")
                    
                    file_size = os.path.getsize(new_file_name)
                    print(f"✅ Размер скопированного файла: {file_size} байт")
                    
                    # Создаем относительный путь от папки БД
                    relative_path = os.path.relpath(new_file_name, self.db_manager.db_folder)
                    # Нормализуем путь (заменяем \ на /)
                    relative_path = relative_path.replace('\\', '/')
                    document_path_to_save = relative_path
                    
                    print(f"\n📊 РЕЗУЛЬТАТ КОПИРОВАНИЯ:")
                    print(f"   Абсолютный путь: {new_file_name}")
                    print(f"   Относительный путь: {relative_path}")
                    print(f"   Будет сохранено в БД: '{document_path_to_save}'")
                    
                    # ============================================================
                    # ✅ УДАЛЕНИЕ СТАРОГО ФАЙЛА
                    # ============================================================
                    if old_document_path:
                        try:
                            # Получаем полный путь к старому файлу
                            old_file_full_path = self.db_manager.get_full_file_path(old_document_path)
                            
                            print(f"\n🗑️ УДАЛЕНИЕ СТАРОГО ФАЙЛА:")
                            print(f"   Относительный путь: {old_document_path}")
                            print(f"   Полный путь: {old_file_full_path}")
                            
                            if os.path.exists(old_file_full_path):
                                os.remove(old_file_full_path)
                                print(f"✅ Старый файл успешно удален")
                            else:
                                print(f"⚠️ Старый файл не найден (уже удален или не существовал)")
                        except Exception as e:
                            print(f"⚠️ Предупреждение при удалении старого файла: {e}")
                            # Не прерываем выполнение, так как новый файл уже скопирован
                    
                    # Очищаем флаг нового файла
                    self._new_document_path = None
                    
                    print("="*80)
                    print("✅ ЗАМЕНА ФАЙЛА ЗАВЕРШЕНА УСПЕШНО")
                    print("="*80 + "\n")
                    
                except Exception as e:
                    print(f"\n❌ ОШИБКА ПРИ ЗАМЕНЕ ФАЙЛА:")
                    print(f"   {str(e)}")
                    import traceback
                    traceback.print_exc()
                    
                    QMessageBox.critical(
                        self,
                        "❌ Ошибка замены файла",
                        f"Не удалось заменить файл документа:\n\n{str(e)}"
                    )
                    return
            else:
                # Файл не менялся - используем текущий путь из поля
                current_path = self.document_path_field.text().strip()
                
                # Проверяем - это относительный путь или полный?
                if current_path and not os.path.isabs(current_path):
                    # Уже относительный путь - используем как есть
                    document_path_to_save = current_path
                elif current_path:
                    # Полный путь - преобразуем в относительный
                    try:
                        relative_path = os.path.relpath(current_path, self.db_manager.db_folder)
                        document_path_to_save = relative_path.replace('\\', '/')
                    except:
                        document_path_to_save = current_path
                else:
                    document_path_to_save = ""
            
            # ============================================================
            # Остальная часть функции БЕЗ ИЗМЕНЕНИЙ
            # ============================================================
            updated_data = {
                "status_id": self.status_field.current_data() if hasattr(self.status_field, 'current_data') else None,
                "type_id": self.type_field.current_data() if hasattr(self.type_field, 'current_data') else None,
                "document_kind_id": self.document_kind_field.current_data() if hasattr(self.document_kind_field, 'current_data') else None,
                "signing_type_id": self.signing_type_field.current_data() if hasattr(self.signing_type_field, 'current_data') else None,
                "reg_number": self.reg_number_field.text().strip(),
                "number": self.newspaper_number_field.text().strip(),
                "reg_date": self.reg_date_field.date().toString("yyyy-MM-dd"),
                "executor_id": self.executor_field.current_data() if hasattr(self.executor_field, 'current_data') else None,
                "responsible_executor_id": self.responsible_executor_field.current_data() if hasattr(self.responsible_executor_field, 'current_data') else None,
                "theme_id": self.theme_field.current_data() if hasattr(self.theme_field, 'current_data') else None,
                "title": self.title_field.text().strip(),
                "pages_count": self.pages_count_field.value(),
                "attachments_count": self.attachments_count_field.value(),
                "should_publish": self.should_publish_field.currentText(),
                "published_where_id": self.published_where_field.current_data() if hasattr(self.published_where_field, 'current_data') else None,
                "published_date": self.published_date_field.date().toString("yyyy-MM-dd") if self.published_date_field.date().isValid() else None,
                "control_date": self.control_date_field.date().toString("yyyy-MM-dd") if self.control_date_field.date().isValid() else None,
                "execution_result": self.execution_result_field.toPlainText().strip(),
                "removed_from_control": self.removed_from_control_field.currentText(),
                "case_number": self.case_number_field.text().strip(),
                "volume_number": self.volume_number_field.text().strip(),
                "sheets": self.sheets_field.text().strip(),
                "document_path": document_path_to_save,  # ✅ ИСПОЛЬЗУЕМ ОБРАБОТАННЫЙ ПУТЬ
            }
            
            if not updated_data["title"]:
                QMessageBox.warning(self, "Предупреждение", "Заголовок документа не может быть пустым")
                return
            
            self.db_manager.update_document(self.current_document_id, updated_data)
            
            # Сохраняем подписантов
            signer_ids = [self.signers_list.item(i).data(Qt.UserRole) 
                        for i in range(self.signers_list.count()) 
                        if self.signers_list.item(i).data(Qt.UserRole)]
            
            if signer_ids:
                delete_signers_query = "DELETE FROM document_signers WHERE document_id = ?"
                self.db_manager.execute_update(delete_signers_query, (self.current_document_id,))
                
                for signer_id in signer_ids:
                    insert_signer_query = "INSERT INTO document_signers (document_id, signer_id) VALUES (?, ?)"
                    self.db_manager.execute_update(insert_signer_query, (self.current_document_id, signer_id))
            
            # Сохраняем согласующих
            approver_ids = [self.approvers_list.item(i).data(Qt.UserRole) 
                        for i in range(self.approvers_list.count()) 
                        if self.approvers_list.item(i).data(Qt.UserRole)]
            
            if approver_ids:
                delete_approvers_query = "DELETE FROM document_approvers WHERE document_id = ?"
                self.db_manager.execute_update(delete_approvers_query, (self.current_document_id,))
                
                for approver_id in approver_ids:
                    insert_approver_query = "INSERT INTO document_approvers (document_id, approver_id) VALUES (?, ?)"
                    self.db_manager.execute_update(insert_approver_query, (self.current_document_id, approver_id))
            
            self.status_label.setText("✅ ВСЕ данные успешно сохранены")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #27ae60;
                    font-size: 12pt;
                    padding: 10px;
                    font-weight: bold;
                    background-color: #d5f4e6;
                    border-radius: 5px;
                }
            """)
            
            QMessageBox.information(self, "✅ Успех", "Все метаданные документа успешно обновлены!")
            self.metadata_saved.emit(self.current_document_id)
            
        except Exception as e:
            print(f"❌ Ошибка при сохранении: {e}")
            import traceback
            traceback.print_exc()
            
            self.status_label.setText("❌ Ошибка при сохранении")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #e74c3c;
                    font-size: 12pt;
                    padding: 10px;
                    font-weight: bold;
                    background-color: #fdeaea;
                    border-radius: 5px;
                }
            """)
            
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить метаданные:\n{str(e)}")
    def open_quick_preview(self):
        """Открыть быстрый предпросмотр текущего документа"""
        if not self.current_document_id:
            QMessageBox.warning(
                self,
                "⚠️ Документ не выбран",
                "Сначала выберите документ для предпросмотра"
            )
            return
        
        try:
            # Получаем главное окно
            main_window = self.get_main_window()
            if main_window and hasattr(main_window, 'open_document_preview_by_id'):
                main_window.open_document_preview_by_id(self.current_document_id)
            else:
                QMessageBox.warning(
                    self,
                    "⚠️ Ошибка",
                    "Не удалось открыть предпросмотр"
                )
        except Exception as e:
            QMessageBox.critical(
                self,
                "❌ Ошибка",
                f"Не удалось открыть предпросмотр:\n\n{str(e)}"
            )
            print(f"❌ Ошибка в open_quick_preview: {e}")


    def open_file_in_word(self):
        """Открыть текущий документ в Word/LibreOffice"""
        if not self.current_document_id:
            QMessageBox.warning(
                self,
                "⚠️ Документ не выбран",
                "Сначала выберите документ для открытия"
            )
            return
        
        try:
            # Получаем главное окно
            main_window = self.get_main_window()
            if main_window and hasattr(main_window, 'open_file_by_document_id'):
                main_window.open_file_by_document_id(self.current_document_id)
            else:
                QMessageBox.warning(
                    self,
                    "⚠️ Ошибка",
                    "Не удалось открыть файл"
                )
        except Exception as e:
            QMessageBox.critical(
                self,
                "❌ Ошибка",
                f"Не удалось открыть файл:\n\n{str(e)}"
            )
            print(f"❌ Ошибка в open_file_in_word: {e}")


    def get_main_window(self):
        """Получить ссылку на главное окно приложения"""
        widget = self
        while widget is not None:
            if widget.__class__.__name__ == 'MainWindow':
                return widget
            widget = widget.parent()
        return None        
    def get_metadata(self):
        """Получить все метаданные из формы"""
        metadata = {
            # Основные данные
            'title': self.title_field.text().strip(),
            'status_id': self.status_field.current_data() if hasattr(self.status_field, 'current_data') else None,
            'type_id': self.type_field.current_data() if hasattr(self.type_field, 'current_data') else None,
            'document_kind_id': self.document_kind_field.current_data() if hasattr(self.document_kind_field, 'current_data') else None,
            'signing_type_id': self.signing_type_field.current_data() if hasattr(self.signing_type_field, 'current_data') else None,
            'reg_number': self.reg_number_field.text().strip(),
            'number': self.newspaper_number_field.text().strip(),
            'reg_date': self.reg_date_field.date(),
            'executor_id': self.executor_field.current_data() if hasattr(self.executor_field, 'current_data') else None,
            'responsible_executor_id': self.responsible_executor_field.current_data() if hasattr(self.responsible_executor_field, 'current_data') else None,
            'theme_id': self.theme_field.current_data() if hasattr(self.theme_field, 'current_data') else None,
            'pages_count': self.pages_count_field.value(),
            'attachments_count': self.attachments_count_field.value(),
            
            # Публикация
            'should_publish': self.should_publish_field.currentText(),
            'published_where_id': self.published_where_field.current_data() if hasattr(self.published_where_field, 'current_data') else None,
            'published_date': self.published_date_field.date() if self.published_date_field.date().isValid() else None,
            
            # Контроль
            'control_date': self.control_date_field.date() if self.control_date_field.date().isValid() else None,
            'execution_result': self.execution_result_field.toPlainText().strip(),
            'removed_from_control': self.removed_from_control_field.currentText(),
            
            # Списание
            'case_number': self.case_number_field.text().strip(),
            'volume_number': self.volume_number_field.text().strip(),
            'sheets': self.sheets_field.text().strip(),
            
            # Путь к файлу
            'document_path': self.document_path_field.text().strip() if hasattr(self, 'document_path_field') else None,
        }
        
        # Подписанты
        signer_ids = [self.signers_list.item(i).data(Qt.UserRole) 
                    for i in range(self.signers_list.count()) 
                    if self.signers_list.item(i).data(Qt.UserRole)]
        metadata['signer_ids'] = signer_ids
        
        # Согласующие
        approver_ids = [self.approvers_list.item(i).data(Qt.UserRole) 
                    for i in range(self.approvers_list.count()) 
                    if self.approvers_list.item(i).data(Qt.UserRole)]
        metadata['approver_ids'] = approver_ids
        
        return metadata
    def reload_references(self):
        """
        ⭐ Перезагрузить все справочники после изменений
        
        Вызывается когда пользователь изменил справочники
        (добавил/удалил/редактировал элементы)
        """
        try:
            print("🔄 MetadataEditor: Перезагрузка справочников...")
            
            # Сохраняем текущие выбранные значения (ID)
            current_values = {}
            if self.current_document_id:
                current_values = {
                    'status_id': self.status_field.current_data() if hasattr(self.status_field, 'current_data') else None,
                    'type_id': self.type_field.current_data() if hasattr(self.type_field, 'current_data') else None,
                    'document_kind_id': self.document_kind_field.current_data() if hasattr(self.document_kind_field, 'current_data') else None,
                    'signing_type_id': self.signing_type_field.current_data() if hasattr(self.signing_type_field, 'current_data') else None,
                    'executor_id': self.executor_field.current_data() if hasattr(self.executor_field, 'current_data') else None,
                    'responsible_executor_id': self.responsible_executor_field.current_data() if hasattr(self.responsible_executor_field, 'current_data') else None,
                    'theme_id': self.theme_field.current_data() if hasattr(self.theme_field, 'current_data') else None,
                    'published_where_id': self.published_where_field.current_data() if hasattr(self.published_where_field, 'current_data') else None,
                }
                print(f"   💾 Сохранены текущие значения: {current_values}")
            
            # Перезагружаем все комбобоксы
            combobox_fields = [
                ('status_field', 'Статусы'),
                ('type_field', 'Типы документов'),
                ('document_kind_field', 'Виды документов'),
                ('signing_type_field', 'Типы подписания'),
                ('executor_field', 'Исполнители'),
                ('responsible_executor_field', 'Ответственные исполнители'),
                ('theme_field', 'Темы'),
                ('published_where_field', 'Места публикации'),
            ]
            
            for field_name, description in combobox_fields:
                try:
                    field = getattr(self, field_name, None)
                    if field and hasattr(field, 'load_items'):
                        print(f"   ↻ Перезагрузка: {description}")
                        field.load_items()
                        print(f"   ✅ {description} обновлен")
                except Exception as e:
                    print(f"   ⚠️ Ошибка обновления {description}: {e}")
            
            # Перезагружаем подписантов и согласующих
            if hasattr(self, 'load_signers_approvers_data'):
                print(f"   ↻ Перезагрузка подписантов и согласующих...")
                self.load_signers_approvers_data()
                print(f"   ✅ Подписанты и согласующие обновлены")
            
            # Восстанавливаем выбранные значения (если документ был открыт)
            if self.current_document_id and current_values:
                print(f"   🔄 Восстановление выбранных значений...")
                
                restore_map = [
                    (self.status_field, current_values.get('status_id')),
                    (self.type_field, current_values.get('type_id')),
                    (self.document_kind_field, current_values.get('document_kind_id')),
                    (self.signing_type_field, current_values.get('signing_type_id')),
                    (self.executor_field, current_values.get('executor_id')),
                    (self.responsible_executor_field, current_values.get('responsible_executor_id')),
                    (self.theme_field, current_values.get('theme_id')),
                    (self.published_where_field, current_values.get('published_where_id')),
                ]
                
                for field, value_id in restore_map:
                    if field and value_id and hasattr(field, 'set_current_by_id'):
                        field.set_current_by_id(value_id)
                
                print(f"   ✅ Значения восстановлены")
            
            print("✅ MetadataEditor: Все справочники перезагружены успешно!")
            
        except Exception as e:
            print(f"❌ Ошибка перезагрузки справочников в MetadataEditor: {e}")
            import traceback
            traceback.print_exc()