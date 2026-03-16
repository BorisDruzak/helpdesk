from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from datetime import datetime
from ui_styles import AppColors, AppStyles, AppLayout

class CollapsibleSection(QWidget):
    """Сворачиваемая секция для экономии места"""
    
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.toggle_button = QPushButton(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(True)
        self.toggle_button.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                padding: 6px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.GRAY_100}, stop:1 {AppColors.GRAY_200});
                border: 1px solid {AppColors.GRAY_300};
                border-radius: 4px;
                font-weight: bold;
                font-size: 9pt;
                color: {AppColors.TEXT_PRIMARY};
            }}
            QPushButton:checked {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.PRIMARY}, stop:1 {AppColors.PRIMARY_DARK});
                color: white;
            }}
            QPushButton:hover {{
                border-color: {AppColors.PRIMARY};
            }}
        """)
        self.content_area = QWidget()
        self.content_layout = QFormLayout()
        self.content_layout.setVerticalSpacing(3)
        self.content_layout.setContentsMargins(8, 4, 8, 4)
        self.content_area.setLayout(self.content_layout)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.content_area)
        self.setLayout(layout)
        
        self.toggle_button.toggled.connect(self.toggle_content)
        
    def toggle_content(self, checked):
        """Переключить видимость контента"""
        self.content_area.setVisible(checked)
        arrow = "▼ " if checked else "▶ "
        text = self.toggle_button.text()
        if text.startswith(("▼ ", "▶ ")):
            text = text[2:]
        self.toggle_button.setText(arrow + text)
    
    def add_field(self, label, widget):
        """Добавить поле в секцию"""
        self.content_layout.addRow(label, widget)
        
    def add_widget(self, widget):
        """Добавить виджет в секцию"""
        self.content_layout.addRow(widget)


class CompactMetadataEditor(QWidget):
    """Оптимизированный компактный редактор метаданных 400x870"""
    
    metadata_saved = pyqtSignal(int)
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_document_id = None
        self.setFixedWidth(500)
        self.setMinimumHeight(870)
        self.setMaximumHeight(900)
        self.init_ui()
        self.apply_modern_styles()
    
    def init_ui(self):
        """Инициализация оптимизированного интерфейса"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(4)
        
        # Заголовок
        self.header_label = QLabel("📋 Метаданные")
        self.header_label.setAlignment(Qt.AlignCenter)
        self.header_label.setStyleSheet(f"""
            QLabel {{
                font-size: 11pt;
                font-weight: bold;
                color: white;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppColors.PRIMARY}, stop:1 {AppColors.PRIMARY_DARK});
                padding: 8px;
                border-radius: 6px;
                margin-bottom: 4px;
            }}
        """)
        
        # Название документа
        self.title_display = QLabel("Документ не выбран")
        self.title_display.setWordWrap(True)
        self.title_display.setAlignment(Qt.AlignCenter)
        self.title_display.setMaximumWidth(500)
        self.title_display.setMaximumHeight(60)
        self.title_display.setMinimumHeight(30)
        self.title_display.setStyleSheet(AppStyles.lable())
        
        # Прокручиваемая область
        scroll_area = QScrollArea()
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #f8f9fa;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #6c757d;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #495057;
            }
        """)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_layout.setContentsMargins(0, 0, 8, 0)
        scroll_layout.setSpacing(6)
        
        # === ОСНОВНАЯ ИНФОРМАЦИЯ ===
        self.status_field = self.create_compact_combo(["-- Загрузка --"])
        self.type_field = self.create_compact_combo(["-- Загрузка --"])
        self.document_kind_field = self.create_compact_combo(["-- Загрузка --"])
        self.signing_type_field = self.create_compact_combo(["-- Загрузка --"])
        main_section = CollapsibleSection("📄 Основная информация")
        self.reg_number_field = self.create_compact_line_edit("Введите номер")

        # Дополнительный номер
        self.number_field = self.create_compact_line_edit("Доп. номер")

        self.reg_date_field = self.create_compact_date_edit()

        self.executor_field = self.create_compact_combo(["-- Загрузка --"])
        self.theme_field = self.create_compact_combo(["-- Загрузка --"])

        # Заголовок
        self.title_field = self.create_compact_line_edit("Заголовок")

        # Количество листов
        self.pages_count_field = QSpinBox()
        self.pages_count_field.setMinimum(0)
        self.pages_count_field.setMaximum(9999)
        self.pages_count_field.setSuffix(" л.")
        self.pages_count_field.setFixedHeight(24)
        self.pages_count_field.setStyleSheet("""
            QSpinBox {
                border: 1px solid #ced4da;
                border-radius: 3px;
                padding: 2px 6px;
                background: white;
                font-size: 8pt;
            }
            QSpinBox:focus {
                border-color: #007bff;
            }
        """)

        # Количество приложений
        self.attachments_count_field = QSpinBox()
        self.attachments_count_field.setMinimum(0)
        self.attachments_count_field.setMaximum(999)
        self.attachments_count_field.setSuffix(" шт.")
        self.attachments_count_field.setFixedHeight(24)
        self.attachments_count_field.setStyleSheet("""
            QSpinBox {
                border: 1px solid #ced4da;
                border-radius: 3px;
                padding: 2px 6px;
                background: white;
                font-size: 8pt;
            }
            QSpinBox:focus {
                border-color: #007bff;
            }
        """)

        main_section.add_field("Статус:", self.status_field)
        main_section.add_field("Тип:", self.type_field)
        main_section.add_field("Вид:", self.document_kind_field)
        main_section.add_field("Подписание:", self.signing_type_field)
        main_section.add_field("Рег. №:", self.reg_number_field)
        main_section.add_field("Доп. №:", self.number_field)
        main_section.add_field("Дата рег.:", self.reg_date_field)
        main_section.add_field("Исполнитель:", self.executor_field)
        main_section.add_field("Тема:", self.theme_field)
        main_section.add_field("Заголовок:", self.title_field)
        main_section.add_field("Листов:", self.pages_count_field)
        main_section.add_field("Приложений:", self.attachments_count_field)
        
        # Добавляем секцию в layout
        scroll_layout.addWidget(main_section)
        scroll_layout.addStretch()
        
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        
        # Кнопки управления
        buttons_widget = QWidget()
        buttons_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #f8f9fa, stop: 1 #e9ecef);
                border-top: 1px solid #dee2e6;
                border-radius: 4px;
            }
        """)
        buttons_layout = QHBoxLayout()
        # ✅ ДОБАВИТЬ: Кнопка быстрого просмотра
        self.quick_preview_btn = QPushButton("Просмотр")
        self.quick_preview_btn.setStyleSheet(AppStyles.button_primary())
        self.quick_preview_btn.clicked.connect(self.open_quick_preview)
        font = self.quick_preview_btn.font()
        font.setPointSize(7)  # Уменьши шрифт
        self.quick_preview_btn.setFont(font)
        self.quick_preview_btn.setEnabled(False)
        self.quick_preview_btn.setMinimumHeight(36)  # Добавь высоту

        # ✅ ДОБАВИТЬ: Кнопка открытия в Word  
        self.open_file_btn = QPushButton("Открыть")
        self.open_file_btn.setStyleSheet(AppStyles.button_primary())
        self.open_file_btn.clicked.connect(self.open_in_word)
        self.open_file_btn.setEnabled(False)
        self.open_file_btn.setMinimumHeight(36)  # Добавь высоту
        
        self.save_btn = QPushButton("💾")
        self.save_btn.setToolTip("Сохранить изменения")
        self.save_btn.setStyleSheet(self.get_button_style("#28a745", "#1E7C32"))
        
        self.save_btn.clicked.connect(self.save_metadata)
        self.save_btn.setEnabled(False)

        self.reset_btn = QPushButton("🔄")
        self.reset_btn.setToolTip("Сбросить изменения") 
        self.reset_btn.setStyleSheet(self.get_button_style("#ffc107", "#e0a800"))
        
        self.reset_btn.clicked.connect(self.reset_form)
        self.reset_btn.setEnabled(False)
        
        # Статус бар
        self.status_bar = QLabel("Готов к работе")
        self.status_bar.setStyleSheet("""
            QLabel {
                background: transparent;
                color: #6c757d;
                font-size: 8pt;
                padding: 2px;
            }
        """)
        # ✅ ДОБАВИТЬ кнопки в layout
        buttons_layout.addWidget(self.quick_preview_btn)
        buttons_layout.addWidget(self.open_file_btn)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.status_bar)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.save_btn)
        buttons_layout.addWidget(self.reset_btn)
        buttons_widget.setLayout(buttons_layout)
        
        # Сборка главного лайаута
        main_layout.addWidget(self.header_label)
        main_layout.addWidget(self.title_display)
        main_layout.addWidget(scroll_area, 1)
        main_layout.addWidget(buttons_widget)
        
        self.setLayout(main_layout)
        
        # Загружаем справочники
        self.load_references()
        self.connect_change_signals()
    
    def create_compact_combo(self, items):
        """Создать компактный combobox"""
        combo = QComboBox()
        combo.addItems(items)
        combo.setFixedHeight(24)
        combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #ced4da;
                border-radius: 3px;
                padding: 2px 6px;
                background: white;
                font-size: 8pt;
            }
            QComboBox:focus {
                border-color: #007bff;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOCIgdmlld0JveD0iMCAwIDEyIDgiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xIDFMNiA2TDExIDEiIHN0cm9rZT0iIzZjNzU3ZCIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPC9zdmc+);
                width: 12px;
                height: 8px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #ced4da;
                background: white;
                selection-background-color: #007bff;
                font-size: 8pt;
            }
        """)
        return combo
    
    def create_compact_line_edit(self, placeholder=""):
        """Создать компактный line edit"""
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setFixedHeight(24)
        edit.setMaximumWidth(350)
        edit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ced4da;
                border-radius: 3px;
                padding: 2px 6px;
                background: white;
                font-size: 8pt;
            }
            QLineEdit:focus {
                border-color: #007bff;
                box-shadow: 0 0 0 2px rgba(0,123,255,.25);
            }
        """)
        return edit
    
    def create_compact_date_edit(self):
        """Создать компактный date edit"""
        date_edit = QDateEdit()
        date_edit.setDate(QDate.currentDate())
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("dd.MM.yyyy")
        date_edit.setFixedHeight(24)
        date_edit.setStyleSheet("""
            QDateEdit {
                border: 1px solid #ced4da;
                border-radius: 3px;
                padding: 2px 6px;
                background: white;
                font-size: 8pt;
            }
            QDateEdit:focus {
                border-color: #007bff;
            }
            QDateEdit::drop-down {
                border: none;
                width: 20px;
            }
            QDateEdit::down-arrow {
                width: 12px;
                height: 8px;
            }
        """)
        return date_edit
    
    def get_button_style(self, color, hover_color):
        """Получить унифицированный стиль кнопки"""
        if color == "#28a745":  # Success
            return AppStyles.button_success()
        elif color == "#ffc107":  # Warning
            return AppStyles.button_warning()
        else:
            return AppStyles.button_primary()
    
    def apply_modern_styles(self):
        """Применить унифицированные стили"""
        self.setStyleSheet(f"""
            QWidget {{
                background-color: white;
                color: {AppColors.TEXT_PRIMARY};
                font-family: 'Segoe UI', Arial, sans-serif;
            }}
            
            QLabel {{
                font-size: 10pt;
                color: {AppColors.TEXT_PRIMARY};
            }}
            
            {AppStyles.input_field()}
            {AppStyles.scroll_bar()}
        """)
    
    def load_references(self):
        """Загрузить все справочники"""
        print("📚 Загрузка справочников...")
        self.load_statuses()
        self.load_document_types()
        self.load_document_kinds()
        self.load_signing_types()
        self.load_executors()
        self.load_themes()
        print("✅ Все справочники загружены")
    def load_executors(self):
        """Загрузить исполнителей"""
        try:
            self.executor_field.clear()
            self.executor_field.addItem("-- Не выбран --", None)
            
            executors = self.db_manager.get_executors(active_only=True)
            for executor in executors:
                name = executor.get('name', '')
                position = executor.get('position', '')
                display_text = f"{name} ({position})" if position else name
                self.executor_field.addItem(display_text, executor.get('id'))
                
        except Exception as e:
            print(f"❌ Ошибка загрузки исполнителей: {e}")
    
    def load_themes(self):
        """Загрузить темы"""
        try:
            self.theme_field.clear()
            self.theme_field.addItem("-- Не выбрана --", None)
            
            themes = self.db_manager.get_themes(active_only=True)
            for theme in themes:
                self.theme_field.addItem(theme.get('name', ''), theme.get('id'))
                
        except Exception as e:
            print(f"❌ Ошибка загрузки тем: {e}")
    
    def connect_change_signals(self):
        """Подключить сигналы изменения полей"""
        try:
            fields = [
                self.status_field, self.type_field, self.document_kind_field, 
                self.signing_type_field, self.executor_field, self.theme_field
            ]
            
            for field in fields:
                if isinstance(field, QComboBox):
                    field.currentTextChanged.connect(self.on_field_changed)
            
            line_edits = [self.reg_number_field, self.number_field, self.title_field]
            for field in line_edits:
                field.textChanged.connect(self.on_field_changed)
            
            self.reg_date_field.dateChanged.connect(self.on_field_changed)
            
            # Количества
            self.pages_count_field.valueChanged.connect(self.on_field_changed)
            self.attachments_count_field.valueChanged.connect(self.on_field_changed)
                
        except Exception as e:
            print(f"❌ Ошибка подключения сигналов: {e}")
    def load_statuses(self):
        """Загрузить статусы из БД"""
        try:
            self.status_field.clear()
            self.status_field.addItem("-- Не выбран --", None)
            
            query = "SELECT id, name FROM ref_status ORDER BY name"
            cursor = self.db_manager.connection.cursor()
            cursor.execute(query)
            statuses = cursor.fetchall()
            
            for status in statuses:
                self.status_field.addItem(status[1], status[0])  # name, id
            
            print(f"✅ Загружено статусов: {len(statuses)}")
                
        except Exception as e:
            print(f"❌ Ошибка загрузки статусов: {e}")


    def load_document_types(self):
        """Загрузить типы документов из БД"""
        try:
            self.type_field.clear()
            self.type_field.addItem("-- Не выбран --", None)
            
            query = "SELECT id, name FROM ref_document_types ORDER BY name"
            cursor = self.db_manager.connection.cursor()
            cursor.execute(query)
            types = cursor.fetchall()
            
            for doc_type in types:
                self.type_field.addItem(doc_type[1], doc_type[0])  # name, id
            
            print(f"✅ Загружено типов документов: {len(types)}")
                
        except Exception as e:
            print(f"❌ Ошибка загрузки типов документов: {e}")


    def load_document_kinds(self):
        """Загрузить виды документов из БД"""
        try:
            self.document_kind_field.clear()
            self.document_kind_field.addItem("-- Не выбран --", None)
            
            query = "SELECT id, name FROM ref_document_kinds ORDER BY name"
            cursor = self.db_manager.connection.cursor()
            cursor.execute(query)
            kinds = cursor.fetchall()
            
            for kind in kinds:
                self.document_kind_field.addItem(kind[1], kind[0])  # name, id
            
            print(f"✅ Загружено видов документов: {len(kinds)}")
                
        except Exception as e:
            print(f"❌ Ошибка загрузки видов документов: {e}")


    def load_signing_types(self):
        """Загрузить типы подписания из БД"""
        try:
            self.signing_type_field.clear()
            self.signing_type_field.addItem("-- Не выбран --", None)
            
            query = "SELECT id, name FROM ref_signing_types ORDER BY name"
            cursor = self.db_manager.connection.cursor()
            cursor.execute(query)
            types = cursor.fetchall()
            
            for signing_type in types:
                self.signing_type_field.addItem(signing_type[1], signing_type[0])  # name, id
            
            print(f"✅ Загружено типов подписания: {len(types)}")
                
        except Exception as e:
            print(f"❌ Ошибка загрузки типов подписания: {e}")
    def disconnect_change_signals(self):
        """Отключить сигналы изменения полей"""
        try:
            # ComboBox'ы
            fields = [
                self.status_field, self.type_field, self.document_kind_field,
                self.signing_type_field, self.executor_field, self.theme_field
            ]
            
            for field in fields:
                if isinstance(field, QComboBox):
                    try:
                        field.currentTextChanged.disconnect(self.on_field_changed)
                    except TypeError:
                        pass  # Сигнал не был подключен
            
            # LineEdit'ы
            line_edits = [self.reg_number_field, self.number_field, self.title_field]
            for field in line_edits:
                try:
                    field.textChanged.disconnect(self.on_field_changed)
                except TypeError:
                    pass
            
            # DateEdit
            try:
                self.reg_date_field.dateChanged.disconnect(self.on_field_changed)
            except TypeError:
                pass
            
            # SpinBox'ы
            try:
                self.pages_count_field.valueChanged.disconnect(self.on_field_changed)
            except TypeError:
                pass
            
            try:
                self.attachments_count_field.valueChanged.disconnect(self.on_field_changed)
            except TypeError:
                pass
                
        except Exception as e:
            print(f"⚠️ Предупреждение при отключении сигналов: {e}")
    
    def on_field_changed(self):
        """Обработчик изменения любого поля"""
        if self.current_document_id:
            self.save_btn.setEnabled(True)
            self.reset_btn.setEnabled(True)
            self.status_bar.setText("Есть несохраненные изменения")
            self.status_bar.setStyleSheet("QLabel { color: #dc3545; font-weight: bold; }")
    
    def set_document(self, document_data):
        """Установить данные документа"""
        try:
            # ⭐⭐⭐ КРИТИЧЕСКИ ВАЖНО: Добавьте эти строки В САМОЕ НАЧАЛО!
            print(f"\n{'='*60}")
            print(f"🎯 CompactMetadataEditor.set_document() ВЫЗВАН!")
            print(f"   Тип данных: {type(document_data)}")
            
            if document_data:
                print(f"   ✅ Данные получены:")
                print(f"      ID: {document_data.get('id', 'НЕТ')}")
                print(f"      Название: {document_data.get('title', 'НЕТ')[:50]}")
                print(f"      Статус: {document_data.get('status', 'НЕТ')}")
            else:
                print(f"   ❌ document_data = None или пустой!")
                print(f"{'='*60}\n")
            
            # СУЩЕСТВУЮЩИЙ КОД начинается здесь:
            if not document_data:
                print(f"   ⚠️ Вызываем clear_form() т.к. данные пустые")
                self.clear_form()
                return
            
            self.current_document_id = document_data.get("id")
            print(f"   📝 Установлен current_document_id = {self.current_document_id}")
            
            self.disconnect_change_signals()
            print(f"   🔇 Отключены сигналы изменения")
            
            # Обновляем заголовок
            title = document_data.get("title", "Без названия")
            if len(title) > 40:
                self.title_display.setText(f"📄 {title[:37]}...")
                self.title_display.setToolTip(title)
            else:
                self.title_display.setText(f"📄 {title}")
                self.title_display.setToolTip("")
            
            print(f"   ✅ Заголовок установлен: {title[:30]}...")
            
            # Загружаем данные в поля через ID
            print(f"   📋 Загружаем данные в поля...")
            print(f"      status_id: {document_data.get('status_id')}")
            print(f"      type_id: {document_data.get('type_id')}")
            print(f"      document_kind_id: {document_data.get('document_kind_id')}")
            print(f"      signing_type_id: {document_data.get('signing_type_id')}")

            # Устанавливаем значения через ID
            self.set_combo_by_id(self.status_field, document_data.get("status_id"))
            self.set_combo_by_id(self.type_field, document_data.get("type_id"))
            self.set_combo_by_id(self.document_kind_field, document_data.get("document_kind_id"))
            self.set_combo_by_id(self.signing_type_field, document_data.get("signing_type_id"))
            
            self.reg_number_field.setText(document_data.get("reg_number", ""))
            self.number_field.setText(document_data.get("number", ""))
            self.title_field.setText(document_data.get("title", ""))
            
            # Даты
            reg_date = document_data.get("reg_date")
            if reg_date:
                try:
                    parsed_date = datetime.strptime(reg_date, "%Y-%m-%d")
                    self.reg_date_field.setDate(QDate(parsed_date.year, parsed_date.month, parsed_date.day))
                except:
                    pass
            
            # Справочники
            self.set_combo_by_id(self.executor_field, document_data.get("executor_id"))
            self.set_combo_by_id(self.theme_field, document_data.get("theme_id"))
            
            # Количества
            self.pages_count_field.setValue(document_data.get("pages_count", 0) or 0)
            self.attachments_count_field.setValue(document_data.get("attachments_count", 0) or 0)
            
            # Обновляем UI
            self.save_btn.setEnabled(False)
            self.reset_btn.setEnabled(True)
            self.status_bar.setText("Данные загружены")
            self.status_bar.setStyleSheet("QLabel { color: #28a745; }")
            # Активируем кнопки предпросмотра и открытия
            if self.current_document_id:
                self.quick_preview_btn.setEnabled(True)
                self.open_file_btn.setEnabled(True)
        
        
            self.connect_change_signals()
            
            
        except Exception as e:
            print(f"❌ Ошибка загрузки метаданных: {e}")
            import traceback
            traceback.print_exc()
    def open_quick_preview(self):
        """Открыть быстрый предпросмотр"""
        if not self.current_document_id:
            return
        
        try:
            main_window = self.get_main_window()
            if main_window:
                main_window.open_document_preview_by_id(self.current_document_id)
        except Exception as e:
            print(f"❌ Ошибка открытия предпросмотра: {e}")


    def open_in_word(self):
        """Открыть файл в Word/LibreOffice"""
        if not self.current_document_id:
            return
        
        try:
            main_window = self.get_main_window()
            if main_window:
                main_window.open_file_by_document_id(self.current_document_id)
        except Exception as e:
            print(f"❌ Ошибка открытия файла: {e}")


    def get_main_window(self):
        """Получить главное окно"""
        widget = self
        while widget is not None:
            if widget.__class__.__name__ == 'MainWindow':
                return widget
            widget = widget.parent()
        return None

    def set_combo_by_id(self, combo, target_id):
        """Установить значение комбобокса по ID"""
        if target_id:
            for i in range(combo.count()):
                if combo.itemData(i) == target_id:
                    combo.setCurrentIndex(i)
                    return
        combo.setCurrentIndex(0)
    
    def clear_form(self):
        """Очистить форму"""
        self.current_document_id = None
        self.title_display.setText("📄 Документ не выбран")
        
        # Сброс всех полей
        for combo in [self.status_field, self.type_field, self.document_kind_field,
                     self.signing_type_field, self.executor_field, self.theme_field]:
            combo.setCurrentIndex(0)
        
        for edit in [self.reg_number_field, self.number_field, self.title_field]:
            edit.clear()
        
        self.reg_date_field.setDate(QDate.currentDate())
        self.pages_count_field.setValue(0)
        self.attachments_count_field.setValue(0)
        
        self.save_btn.setEnabled(False)
        self.reset_btn.setEnabled(False)
        self.status_bar.setText("Готов к работе")
        self.status_bar.setStyleSheet("QLabel { color: #6c757d; }")
        if hasattr(self, 'quick_preview_btn'):
            self.quick_preview_btn.setEnabled(False)
        if hasattr(self, 'open_file_btn'):
            self.open_file_btn.setEnabled(False)
    def save_metadata(self):
        """Сохранить изменения метаданных"""
        if not self.current_document_id:
            return
        
        try:
            print(f"\n{'='*60}")
            print(f"💾 СОХРАНЕНИЕ МЕТАДАННЫХ документа ID: {self.current_document_id}")
            
            # Получаем ID из комбобоксов (они хранятся в itemData)
            status_id = self.status_field.currentData()
            type_id = self.type_field.currentData()
            kind_id = self.document_kind_field.currentData()
            signing_id = self.signing_type_field.currentData()
            executor_id = self.executor_field.currentData()
            theme_id = self.theme_field.currentData()
            
            # Выводим для отладки
            print(f"   status_id: {status_id} ({self.status_field.currentText()})")
            print(f"   type_id: {type_id} ({self.type_field.currentText()})")
            print(f"   kind_id: {kind_id} ({self.document_kind_field.currentText()})")
            print(f"   signing_id: {signing_id} ({self.signing_type_field.currentText()})")
            print(f"   executor_id: {executor_id}")
            print(f"   theme_id: {theme_id}")
            
            # Формируем данные для обновления (используем правильные имена полей БД)
            updated_data = {
                "status_id": status_id,
                "type_id": type_id,
                "document_kind_id": kind_id,
                "signing_type_id": signing_id,
                "reg_number": self.reg_number_field.text().strip(),
                "number": self.number_field.text().strip(),
                "reg_date": self.reg_date_field.date().toString("yyyy-MM-dd"),
                "executor_id": executor_id,
                "theme_id": theme_id,
                "title": self.title_field.text().strip(),
                "pages_count": self.pages_count_field.value(),
                "attachments_count": self.attachments_count_field.value(),
            }
            
            print(f"   📦 Данные для сохранения: {updated_data}")
            
            # Сохраняем в БД
            self.db_manager.update_document(self.current_document_id, updated_data)
            
            print(f"✅ Метаданные сохранены успешно!")
            print(f"{'='*60}\n")
            
            # Обновляем UI
            self.save_btn.setEnabled(False)
            self.reset_btn.setEnabled(True)
            self.status_bar.setText("✅ Сохранено")
            self.status_bar.setStyleSheet("QLabel { color: #28a745; font-weight: bold; }")
            
            # Отправляем сигнал для обновления таблиц
            self.metadata_saved.emit(self.current_document_id)
            
            # Таймер для сброса статуса
            QTimer.singleShot(3000, lambda: (
                self.status_bar.setText("Готов к работе"),
                self.status_bar.setStyleSheet("QLabel { color: #6c757d; }")
            ))
            
        except Exception as e:
            print(f"❌ ОШИБКА СОХРАНЕНИЯ: {e}")
            import traceback
            traceback.print_exc()
            print(f"{'='*60}\n")
            
            self.status_bar.setText("❌ Ошибка сохранения")
            self.status_bar.setStyleSheet("QLabel { color: #dc3545; font-weight: bold; }")
    def get_reference_id(self, table_name, name):
        """
        Получить ID элемента справочника по имени
        
        Args:
            table_name: Имя таблицы справочника
            name: Название элемента
        
        Returns:
            int или None: ID элемента или None если не найден
        """
        try:
            query = f"SELECT id FROM {table_name} WHERE name = ?"
            cursor = self.db_manager.connection.cursor()
            cursor.execute(query, (name,))
            result = cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            print(f"❌ Ошибка получения ID из {table_name}: {e}")
            return None
    def reset_form(self):
        """Сбросить форму к исходным значениям"""
        if self.current_document_id:
            try:
                document_data = self.db_manager.get_document_by_id(self.current_document_id)
                if document_data:
                    self.set_document(document_data)
            except Exception as e:
                print(f"❌ Ошибка сброса формы: {e}")
    
    def set_document_data(self, document_data):
        """Установить данные документа (альтернативное название для совместимости)"""
        self.set_document(document_data)
    
    def refresh_references(self):
        """Обновить справочники"""
        self.load_references()
    def reload_references(self):
        """
        ⭐ Перезагрузить все справочники после изменений
        
        Вызывается когда пользователь изменил справочники
        """
        try:
            print("🔄 CompactMetadataEditor: Перезагрузка справочников...")
            
            # Сохраняем текущие выбранные ID
            current_values = {}
            if self.current_document_id:
                current_values = {
                    'status_id': self.status_field.currentData(),
                    'type_id': self.type_field.currentData(),
                    'document_kind_id': self.document_kind_field.currentData(),
                    'signing_type_id': self.signing_type_field.currentData(),
                    'executor_id': self.executor_field.currentData(),
                    'theme_id': self.theme_field.currentData(),
                }
                print(f"   💾 Сохранены текущие значения: {current_values}")
            
            # Отключаем сигналы на время перезагрузки
            self.disconnect_change_signals()
            
            # Перезагружаем все справочники
            print(f"   ↻ Перезагрузка статусов...")
            self.load_statuses()
            
            print(f"   ↻ Перезагрузка типов документов...")
            self.load_document_types()
            
            print(f"   ↻ Перезагрузка видов документов...")
            self.load_document_kinds()
            
            print(f"   ↻ Перезагрузка типов подписания...")
            self.load_signing_types()
            
            print(f"   ↻ Перезагрузка исполнителей...")
            self.load_executors()
            
            print(f"   ↻ Перезагрузка тем...")
            self.load_themes()
            
            # Восстанавливаем выбранные значения
            if self.current_document_id and current_values:
                print(f"   🔄 Восстановление выбранных значений...")
                
                self.set_combo_by_id(self.status_field, current_values.get('status_id'))
                self.set_combo_by_id(self.type_field, current_values.get('type_id'))
                self.set_combo_by_id(self.document_kind_field, current_values.get('document_kind_id'))
                self.set_combo_by_id(self.signing_type_field, current_values.get('signing_type_id'))
                self.set_combo_by_id(self.executor_field, current_values.get('executor_id'))
                self.set_combo_by_id(self.theme_field, current_values.get('theme_id'))
                
                print(f"   ✅ Значения восстановлены")
            
            # Включаем сигналы обратно
            self.connect_change_signals()
            
            print("✅ CompactMetadataEditor: Все справочники перезагружены успешно!")
            
        except Exception as e:
            print(f"❌ Ошибка перезагрузки справочников в CompactMetadataEditor: {e}")
            import traceback
            traceback.print_exc()