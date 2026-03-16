from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QTimer, QDate, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect, QPoint, QSize
from PyQt5.QtGui import QFont
from documents_table import DocumentsTableModel
from doc_prew import DocumentPreviewDialog
from PyQt5.QtWidgets import QGraphicsOpacityEffect
from ui_styles import AppColors, AppStyles, AppLayout, EnhancedDateEdit, ModernToggleSwitch
from PyQt5.QtGui import QFont, QCursor
import re
class FlowLayout(QLayout):
    """Кастомный FlowLayout для автоматического переноса виджетов"""
    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.item_list = []

    def addItem(self, item):
        self.item_list.append(item)

    def count(self):
        return len(self.item_list)

    def itemAt(self, index):
        if 0 <= index < len(self.item_list):
            return self.item_list[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.item_list):
            return self.item_list.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Horizontal | Qt.Vertical)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self.do_layout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.item_list:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def do_layout(self, rect, test_only=False):
        x = rect.x()
        y = rect.y()
        line_height = 0
        for item in self.item_list:
            wid = item.widget()
            space_x = self.spacing() + item.geometry().width()
            space_y = self.spacing() + item.geometry().height()
            if x + space_x > rect.right() and line_height > 0:
                x = rect.x()
                y += line_height
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x += space_x
            line_height = max(line_height, space_y)
        return y + line_height - rect.y()
class FilterTag(QLabel):
    removed = pyqtSignal(str)

    def __init__(self, field_name: str, display_text: str, parent=None):
        super().__init__(parent)
        self.field_name = field_name
        self.setTextFormat(Qt.RichText)
        self.setOpenExternalLinks(False)
        self.setText(f"""
            <span style="
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.PRIMARY_LIGHT}, stop:1 {AppColors.GRAY_50});
                border: 2px solid {AppColors.PRIMARY};
                border-radius: 6px;
                padding: 4px 10px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10pt;
                font-weight: 500;
                color: {AppColors.PRIMARY_DARK};
            ">{display_text} 
            <a href='remove' style="
                text-decoration: none;
                color: {AppColors.DANGER};
                font-weight: bold;
                font-size: 12pt;
                margin-left: 6px;
            ">×</a>
            </span>
        """)
        self.linkActivated.connect(self.on_close_clicked)
        self.setCursor(Qt.ArrowCursor)  # курсор только на ×
        self.setStyleSheet("QLabel { background-color: transparent; }")

    def on_close_clicked(self, link):
        if link == "remove":
            self.removed.emit(self.field_name)
class AdvancedSearchDialog(QDialog):
    """
    ✨ ОПТИМИЗИРОВАННОЕ диалоговое окно расширенного поиска
    Интерфейс разделен на 2 части:
    - Слева: компактная панель критериев поиска (вертикально)
    - Справа: таблица с результатами поиска
    """
    
    edit_metadata_requested = pyqtSignal(int)
    preview_requested = pyqtSignal(int)
    
    def __init__(self, db_manager, document_handler, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.document_handler = document_handler
        self.active_filters = {}  # {field_name: value}
        
        self.setWindowTitle("🔍 Расширенный поиск документов")
        self.setMinimumSize(1400, 1000)
        self.resize(1400, 1000)
        
        self.setStyleSheet(self.get_dialog_styles())
        
        # Таймер для отложенного поиска
        self.search_timer = QTimer()
        self.search_timer.setInterval(300)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.do_search)
        
        self.init_ui()
    
    def showEvent(self, event):
        super().showEvent(event)
        
        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)
        
        self.animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.animation.setDuration(300)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.start()

    def get_dialog_styles(self):
        """Унифицированные стили для диалога"""
        return f"""
            QDialog {{
                background-color: {AppColors.GRAY_50};
                font-family: 'Segoe UI', Arial, sans-serif;
            }}
            
            /* === ПОЛЯ ВВОДА === */
            {AppStyles.input_field()}
            
            /* === КНОПКИ === */
            {AppStyles.button_primary()}
            
            /* === ГРУППЫ === */
            {AppStyles.group_box()}
            
            /* === КНОПКА ОТМЕНЫ === */
            QPushButton#cancel_btn {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.DANGER}, stop:1 {AppColors.DANGER_DARK});
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
                min-height: 32px;
            }}
            
            QPushButton#cancel_btn:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #E53935, stop:1 #C62828);
            }}
            
            QPushButton#cancel_btn:pressed {{
                background: {AppColors.DANGER_DARK};
            }}
            
            /* === КНОПКА СБРОСА === */
            QPushButton#reset_btn {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.GRAY_500}, stop:1 {AppColors.GRAY_700});
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
                min-height: 32px;
            }}
            
            QPushButton#reset_btn:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.GRAY_700}, stop:1 {AppColors.GRAY_900});
            }}
            
            QPushButton#reset_btn:pressed {{
                background: {AppColors.GRAY_900};
            }}
            
            /* === КОМБОБОКСЫ === */
            QComboBox {{
                border: 2px solid {AppColors.GRAY_300};
                border-radius: 6px;
                padding: 6px 12px;
                background: white;
                min-height: 28px;
                font-size: 10pt;
            }}
            
            QComboBox:hover {{
                border-color: {AppColors.PRIMARY};
            }}
            
            QComboBox:focus {{
                border-color: {AppColors.PRIMARY};
                border-width: 2px;
            }}
            
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            
            QComboBox QAbstractItemView {{
                border: 2px solid {AppColors.GRAY_300};
                background: white;
                selection-background-color: {AppColors.PRIMARY};
                selection-color: white;
            }}
        """
    def init_ui(self):
        """Инициализация UI с панелью тегов и сворачиваемыми фильтрами"""
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #bdc3c7;
                margin: 0px 2px;
            }
            QSplitter::handle:hover {
                background-color: #3498db;
            }
        """)

        # === ЛЕВАЯ ПАНЕЛЬ ===
        self.left_panel = QWidget()
        self.left_panel.setFixedWidth(500)
        self.left_panel.setStyleSheet("QWidget { background-color: #f8f9fa; border-right: 2px solid #e0e0e0; }")
        self.left_scroll = QScrollArea()
        self.left_scroll.setWidgetResizable(True)
        self.left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.left_scroll.setStyleSheet("QScrollArea { border: none; background-color: #f8f9fa; }")

        criteria_widget = QWidget()
        criteria_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        criteria_layout = QVBoxLayout()
        criteria_layout.setSpacing(10)
        criteria_layout.setContentsMargins(10, 10, 10, 10)

        header = QLabel("🔍 Критерии поиска")
        header.setStyleSheet("QLabel { font-size: 14pt; font-weight: bold; color: #2c3e50; padding: 10px; background-color: #ecf0f1; border-radius: 6px; }")
        criteria_layout.addWidget(header)

        # === ПАНЕЛЬ ТЕГОВ (с переносом и скроллом) ===
        self.tags_container = QWidget()
        self.tags_flow_layout = FlowLayout(self.tags_container, margin=6, spacing=6)
        self.tags_container.setLayout(self.tags_flow_layout)

        # Оборачиваем в ScrollArea, если нужно
        self.tags_scroll_area = QScrollArea()
        self.tags_scroll_area.setWidgetResizable(True)
        self.tags_scroll_area.setWidget(self.tags_container)
        self.tags_scroll_area.setMaximumHeight(100)  # Ограничиваем высоту
        self.tags_scroll_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        criteria_layout.addWidget(self.tags_scroll_area)

        # === ПОИСК: РЕГ. НОМЕР + ТЕКСТ ===
        search_group = QGroupBox("🔍 Поиск")
        search_layout = QGridLayout()
        search_layout.setSpacing(AppLayout.SPACING_MD)
        search_layout.setContentsMargins(
            AppLayout.MARGIN_MD, 
            AppLayout.MARGIN_MD, 
            AppLayout.MARGIN_MD, 
            AppLayout.MARGIN_MD
        )

        # === РЕГ. НОМЕР ===
        self.reg_number_field = QLineEdit()
        self.reg_number_field.setPlaceholderText("Например: 12345 или 12-05")
        self.reg_number_field.setMinimumHeight(AppLayout.INPUT_HEIGHT)
        self.reg_number_field.textChanged.connect(
            lambda: self.on_field_changed('reg_number', self.reg_number_field.text())
        )

        reg_label = QLabel("🔖 Рег. номер")
        reg_label.setStyleSheet(f"""
            QLabel {{
                font-weight: bold; 
                font-size: 10pt; 
                color: {AppColors.TEXT_PRIMARY};
                padding-right: 8px;
            }}
        """)
        reg_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        reg_label.setMinimumWidth(100)
        search_layout.addWidget(reg_label, 0, 0)
        search_layout.addWidget(self.reg_number_field, 0, 1)

        # === ТЕКСТОВЫЙ ПОИСК ===
        self.text_search_field = QLineEdit()
        self.text_search_field.setPlaceholderText("По названию, теме, исполнителю...")
        self.text_search_field.setMinimumHeight(AppLayout.INPUT_HEIGHT)
        self.text_search_field.textChanged.connect(
            lambda: self.on_field_changed('text_search', self.text_search_field.text())
        )

        text_label = QLabel("📝 Текст")
        text_label.setStyleSheet(f"""
            QLabel {{
                font-weight: bold; 
                font-size: 10pt; 
                color: {AppColors.TEXT_PRIMARY};
                padding-right: 8px;
            }}
        """)
        text_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        text_label.setMinimumWidth(100)
        search_layout.addWidget(text_label, 1, 0)
        search_layout.addWidget(self.text_search_field, 1, 1)

        # Устанавливаем пропорции колонок
        search_layout.setColumnStretch(0, 0)  # Лейблы фиксированной ширины
        search_layout.setColumnStretch(1, 1)  # Поля ввода растягиваются

        search_group.setLayout(search_layout)
        criteria_layout.addWidget(search_group)

        # === ПЕРИОД РЕГИСТРАЦИИ ===
        date_group = QGroupBox("📅 Период регистрации  ")
        date_main_layout = QVBoxLayout()
        date_main_layout.setSpacing(0)  # Убрали отступы внутри
        date_main_layout.setContentsMargins(0, 0, 0, 0)  # Компактные отступы

        # Переключатель без дополнительного spacing
        self.date_mode_switch = ModernToggleSwitch(parent=self, width=120, height=32)  # Уменьшили высоту
        self.date_mode_switch.setText("Диапазон", "Один день")
        self.date_mode_switch.setChecked(True)
        self.date_mode_switch.toggled.connect(self.on_date_mode_changed)
        date_main_layout.addWidget(self.date_mode_switch)

        # === ГОРИЗОНТАЛЬНЫЙ КОНТЕЙНЕР: поля дат + кнопки ===
        date_row_layout = QHBoxLayout()
        date_row_layout.setSpacing(12)  # Уменьшили расстояние между блоками
        date_row_layout.setContentsMargins(0, 0, 0, 0)

        # === ЛЕВАЯ ЧАСТЬ - ПОЛЯ ДАТ (вертикально, ЦЕНТРИРОВАНО) ===
        dates_container = QWidget()
        dates_container.setStyleSheet("background-color: transparent;")
        dates_layout = QVBoxLayout()
        dates_layout.setSpacing(6)  # Умеренный отступ между строками
        dates_layout.setContentsMargins(6, 6, 6, 6)  # Небольшие внутренние отступы
        dates_layout.setAlignment(Qt.AlignTop)  # Прижимаем содержимое к верху

        # Поле "От"
        self.date_from = EnhancedDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addYears(-1))
        self.date_from.setDisplayFormat("dd.MM.yyyy")
        self.date_from.dateChanged.connect(lambda d: self.on_field_changed('date_from', d.toString("yyyy-MM-dd")))

        from_row = QHBoxLayout()
        from_row.setSpacing(6)
        from_row.setContentsMargins(0, 0, 0, 0)
        from_row.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # Центрируем по вертикали

        from_label = QLabel("От")
        from_label.setFixedWidth(25)  # Фиксируем ширину для выравнивания
        from_label.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        from_row.addWidget(from_label)
        from_row.addWidget(self.date_from)

        # Поле "До"
        self.date_to = EnhancedDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setDisplayFormat("dd.MM.yyyy")
        self.date_to.dateChanged.connect(lambda d: self.on_field_changed('date_to', d.toString("yyyy-MM-dd")))

        to_row = QHBoxLayout()
        to_row.setSpacing(6)
        to_row.setContentsMargins(0, 0, 0, 0)
        to_row.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        to_label = QLabel("До")
        to_label.setFixedWidth(25)  # Сохраняем такую же ширину как у "От"
        to_label.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        to_row.addWidget(to_label)
        to_row.addWidget(self.date_to)

        # Увеличиваем высоту полей до размера кнопок (примерно 28-30px)
        self.date_from.setMaximumHeight(28)
        self.date_to.setMaximumHeight(28)

        # Устанавливаем фиксированную ширину для полей, но с возможностью роста
        self.date_from.setMinimumWidth(120)
        self.date_to.setMinimumWidth(120)

        # Добавляем строки в общий layout
        dates_layout.addLayout(from_row)
        dates_layout.addLayout(to_row)
        dates_container.setLayout(dates_layout)

        # Критически важная настройка: растягиваем контейнер по высоте
        dates_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        dates_container.setLayout(dates_layout)
        date_row_layout.addWidget(dates_container)

        # === ПРАВАЯ ЧАСТЬ - КНОПКИ БЫСТРОГО ДОСТУПА (2×3) ===
        quick_container = QWidget()
        quick_container.setStyleSheet("background-color: transparent;")
        quick_layout = QGridLayout()
        quick_layout.setHorizontalSpacing(8)
        quick_layout.setVerticalSpacing(4)  # Компактнее
        quick_layout.setContentsMargins(0, 0, 0, 0)

        def create_quick_button(text, slot):
            """Создает кнопку быстрого доступа к датам"""
            btn = QPushButton(text)
            btn.setFont(QFont("Segoe UI", 8, QFont.Bold))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 {AppColors.GRAY_100}, stop:1 {AppColors.GRAY_200});
                    border: 2px solid {AppColors.GRAY_300};
                    border-radius: 6px;
                    color: {AppColors.GRAY_700};
                    padding: 6px 10px;
                    min-width: 110px;
                    max-width: 130px;
                    min-height: 28px;
                    font-weight: 600;
                }}
                
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 {AppColors.PRIMARY_LIGHT}, stop:1 {AppColors.GRAY_300});
                    border: 2px solid {AppColors.PRIMARY};
                    color: {AppColors.PRIMARY_DARK};
                }}
                
                QPushButton:pressed {{
                    background: {AppColors.GRAY_400};
                    border: 2px solid {AppColors.GRAY_500};
                }}
            """)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(slot)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            return btn

        buttons = [
            ("Сегодня", self.set_today),
            ("Вчера", self.set_yesterday),
            ("Выбрать день…", self.set_single_day_dialog),
            ("Текущий год", self.set_current_year),
            ("Прошлый год", self.set_last_year),
            ("Квартал", self.set_current_quarter),
        ]

        # Располагаем в 2 колонки × 3 ряда
        for i, (text, slot) in enumerate(buttons):
            row = i // 2
            col = i % 2
            btn = create_quick_button(text, slot)
            quick_layout.addWidget(btn, row, col)

        quick_container.setLayout(quick_layout)
        date_row_layout.addWidget(quick_container)

        # Добавляем stretch, чтобы кнопки были прижаты к правому краю
        date_row_layout.addStretch()

        date_main_layout.addLayout(date_row_layout)
        date_group.setLayout(date_main_layout)

        criteria_layout.addWidget(date_group)
        # === КНОПКА ПЕРЕКЛЮЧЕНИЯ ДОПОЛНИТЕЛЬНЫХ ФИЛЬТРОВ ===
        self.toggle_advanced_btn = QPushButton("▼ Показать дополнительные фильтры")
        self.toggle_advanced_btn.setStyleSheet(AppStyles.button_primary())
        self.toggle_advanced_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.toggle_advanced_btn.clicked.connect(self.toggle_advanced_filters)
        criteria_layout.addWidget(self.toggle_advanced_btn)
        # === ПОИСК ПО ДОПОЛНИТЕЛЬНЫМ ФИЛЬТРАМ ===
        self.filter_search_field = QLineEdit()
        self.filter_search_field.setStyleSheet(AppStyles.input_field())
        self.filter_search_field.setPlaceholderText("🔍 Быстрый поиск по фильтрам...")
        self.filter_search_field.textChanged.connect(self.filter_advanced_groups)
        self.filter_search_field.setVisible(False)  # изначально скрыто
        criteria_layout.addWidget(self.filter_search_field)
        # === СОЗДАЁМ ВСЕ ДОПОЛНИТЕЛЬНЫЕ ГРУППЫ ===
        # Основные параметры
        self.main_group = QGroupBox("📄 Основные параметры")
        main_layout = QFormLayout()
        main_layout.setSpacing(AppLayout.SPACING_MD)
        main_layout.setContentsMargins(
            AppLayout.MARGIN_MD,
            AppLayout.MARGIN_SM, 
            AppLayout.MARGIN_MD,
            AppLayout.MARGIN_MD
        )
        main_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        main_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        self.status_combo = QComboBox()
        self.load_reference('ref_status', self.status_combo)
        self.status_combo.currentIndexChanged.connect(lambda: self.on_combo_changed('status_id', self.status_combo))
        main_layout.addRow("📊 Статус:", self.status_combo)

        self.type_combo = QComboBox()
        self.load_reference('ref_document_types', self.type_combo)
        self.type_combo.currentIndexChanged.connect(lambda: self.on_combo_changed('type_id', self.type_combo))
        main_layout.addRow("📋 Тип:", self.type_combo)

        self.document_kind_combo = QComboBox()
        self.load_reference('ref_document_kinds', self.document_kind_combo)
        self.document_kind_combo.currentIndexChanged.connect(lambda: self.on_combo_changed('document_kind_id', self.document_kind_combo))
        main_layout.addRow("📋 Вид:", self.document_kind_combo)

        self.signing_type_combo = QComboBox()
        self.load_reference('ref_signing_types', self.signing_type_combo)
        self.signing_type_combo.currentIndexChanged.connect(lambda: self.on_combo_changed('signing_type_id', self.signing_type_combo))
        main_layout.addRow("✍️ Подписание:", self.signing_type_combo)

        self.main_group.setLayout(main_layout)

        # Исполнители и тема
        self.executors_group = QGroupBox("👥 Исполнители и тема")
        executors_layout = QFormLayout()
        executors_layout.setSpacing(8)
        self.executor_combo = QComboBox()
        self.load_reference('ref_executors', self.executor_combo)
        self.executor_combo.currentIndexChanged.connect(lambda: self.on_combo_changed('executor_id', self.executor_combo))
        executors_layout.addRow("👤 Исполнитель:", self.executor_combo)

        self.responsible_executor_combo = QComboBox()
        self.load_reference('ref_responsible_executors', self.responsible_executor_combo)
        self.responsible_executor_combo.currentIndexChanged.connect(lambda: self.on_combo_changed('responsible_executor_id', self.responsible_executor_combo))
        executors_layout.addRow("👤 Ответственный:", self.responsible_executor_combo)

        self.theme_combo = QComboBox()
        self.load_reference('ref_themes', self.theme_combo)
        self.theme_combo.currentIndexChanged.connect(lambda: self.on_combo_changed('theme_id', self.theme_combo))
        executors_layout.addRow("🏷 Тема:", self.theme_combo)
        self.executors_group.setLayout(executors_layout)

        # Публикация
        self.publication_group = QGroupBox("📰 Публикация")
        publication_layout = QFormLayout()
        publication_layout.setSpacing(8)
        self.should_publish_combo = QComboBox()
        self.should_publish_combo.addItems(["Любое", "Да", "Нет", "Не указано"])
        self.should_publish_combo.currentIndexChanged.connect(lambda: self.on_field_changed('should_publish', self.should_publish_combo.currentText()))
        publication_layout.addRow("❓ Подлежит:", self.should_publish_combo)

        self.published_where_combo = QComboBox()
        self.load_reference('ref_published_where', self.published_where_combo)
        self.published_where_combo.currentIndexChanged.connect(lambda: self.on_combo_changed('published_where_id', self.published_where_combo))
        publication_layout.addRow("📍 Где:", self.published_where_combo)
        self.publication_group.setLayout(publication_layout)

        # Контроль и списание
        self.control_group = QGroupBox("⚖️ Контроль и списание")
        control_layout = QFormLayout()
        control_layout.setSpacing(8)
        self.removed_from_control_combo = QComboBox()
        self.removed_from_control_combo.addItems(["Любое", "Да", "Нет"])
        self.removed_from_control_combo.currentIndexChanged.connect(lambda: self.on_field_changed('removed_from_control', self.removed_from_control_combo.currentText()))
        control_layout.addRow("📤 Снято:", self.removed_from_control_combo)

        self.case_number_field = QLineEdit()
        self.case_number_field.setPlaceholderText("01-05")
        self.case_number_field.textChanged.connect(lambda: self.on_field_changed('case_number', self.case_number_field.text()))
        control_layout.addRow("📁 Дело №:", self.case_number_field)

        self.volume_number_field = QLineEdit()
        self.volume_number_field.setPlaceholderText("1")
        self.volume_number_field.textChanged.connect(lambda: self.on_field_changed('volume_number', self.volume_number_field.text()))
        control_layout.addRow("📚 Том №:", self.volume_number_field)
        self.control_group.setLayout(control_layout)

        # === КОНТЕЙНЕР ДОПОЛНИТЕЛЬНЫХ ФИЛЬТРОВ (изначально скрыт) ===
        self.advanced_filters_container = QWidget()
        advanced_layout = QVBoxLayout()
        advanced_layout.setSpacing(10)
        advanced_layout.addWidget(self.main_group)
        advanced_layout.addWidget(self.executors_group)
        advanced_layout.addWidget(self.publication_group)
        advanced_layout.addWidget(self.control_group)
        self.advanced_filters_container.setLayout(advanced_layout)
        self.advanced_filters_container.setVisible(False)
        criteria_layout.addWidget(self.advanced_filters_container)

        

        # === СТАТУС + КНОПКИ ===
        self.status_label = QLabel("✅ Готов к поиску")
        self.status_label.setStyleSheet(f"""
            QLabel {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.SUCCESS_LIGHT}, stop:1 #e8f5e9);
                border: 2px solid {AppColors.SUCCESS};
                border-radius: 8px;
                padding: 10px 15px;
                color: {AppColors.SUCCESS_DARK};
                font-size: 10pt;
                font-weight: 600;
                font-family: 'Segoe UI', Arial, sans-serif;
            }}
        """)
        criteria_layout.addWidget(self.status_label)

        button_layout = QHBoxLayout()
        self.reset_btn = QPushButton("🔄 Сброс")
        self.reset_btn.setStyleSheet(AppStyles.butt())
        self.reset_btn.setObjectName("reset_btn")
        self.reset_btn.clicked.connect(self.reset_filters)
        self.cancel_btn = QPushButton("❌ Закрыть")
        self.cancel_btn.setStyleSheet(AppStyles.butt())
        self.cancel_btn.setObjectName("cancel_btn")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.reset_btn)
        button_layout.addWidget(self.cancel_btn)
        criteria_layout.addLayout(button_layout)
        criteria_layout.addStretch()

        criteria_widget.setLayout(criteria_layout)
        self.left_scroll.setWidget(criteria_widget)
        left_panel_layout = QVBoxLayout()
        left_panel_layout.setContentsMargins(0, 0, 0, 0)
        left_panel_layout.addWidget(self.left_scroll)
        self.left_panel.setLayout(left_panel_layout)

        # === ПРАВАЯ ПАНЕЛЬ (без изменений) ===
        right_panel = QWidget()
        right_panel.setStyleSheet("QWidget { background-color: white; }")
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(10)

        results_header = QWidget()
        results_header_layout = QHBoxLayout()
        results_title = QLabel("📊 Результаты поиска")
        results_title.setStyleSheet("QLabel { font-size: 14pt; font-weight: bold; color: #2c3e50; }")
        self.results_count_label = QLabel("Документов: 0")
        self.results_count_label.setStyleSheet("QLabel { font-size: 10pt; color: #7f8c8d; padding: 5px 10px; background-color: #ecf0f1; border-radius: 4px; }")
        results_header_layout.addWidget(results_title)
        results_header_layout.addStretch()
        results_header_layout.addWidget(self.results_count_label)
        results_header.setLayout(results_header_layout)

        self.results_table = SearchResultsTableView(self.db_manager, self)
        self.results_table.edit_metadata_requested.connect(self.edit_metadata_requested)
        self.results_table.preview_requested.connect(self.preview_requested)
        self.results_table.edit_metadata_requested.connect(self.close_dialog)

        right_layout.addWidget(results_header)
        right_layout.addWidget(self.results_table)
        right_panel.setLayout(right_layout)

        splitter.addWidget(self.left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)  # Левая панель может растягиваться
        splitter.setStretchFactor(1, 2)  # Правая панель растягивается с большим весом
        splitter.setSizes([500, 1000])
        layout.addWidget(splitter)
        self.setLayout(layout)

        QTimer.singleShot(100, self.do_search)
    def on_date_mode_changed(self, is_range_mode: bool):
        """
        Обработка переключения режима даты
        :param is_range_mode: True — диапазон, False — один день
        """
        if is_range_mode:
            # Режим диапазона — оба поля активны
            self.date_from.setEnabled(True)
            self.date_to.setEnabled(True)
        else:
            # Режим одного дня — синхронизируем оба поля
            self.date_from.setEnabled(True)
            self.date_to.setEnabled(False)
            current = self.date_from.date()
            self.date_to.setDate(current)
            self.on_field_changed('date_to', current.toString("yyyy-MM-dd"))

    def set_today(self):
        today = QDate.currentDate()
        self.date_from.setDate(today)
        self.date_to.setDate(today)
        if not self.date_mode_switch.isChecked():  # Если "Один день"
            self.date_to.setEnabled(False)
        self.restart_search_timer()

    def set_yesterday(self):
        yesterday = QDate.currentDate().addDays(-1)
        self.date_from.setDate(yesterday)
        self.date_to.setDate(yesterday)
        if not self.date_mode_switch.isChecked():
            self.date_to.setEnabled(False)
        self.restart_search_timer()

    def set_single_day_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Выберите дату")
        dialog.setModal(True)
        dialog_layout = QVBoxLayout()
        calendar = QCalendarWidget()
        calendar.setSelectedDate(QDate.currentDate())
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog_layout.addWidget(calendar)
        dialog_layout.addWidget(button_box)
        dialog.setLayout(dialog_layout)
        if dialog.exec_() == QDialog.Accepted:
            selected = calendar.selectedDate()
            self.date_from.setDate(selected)
            self.date_to.setDate(selected)
            if not self.date_mode_switch.isChecked():
                self.date_to.setEnabled(False)
            self.restart_search_timer()
    def toggle_advanced_filters(self):
        is_visible = self.advanced_filters_container.isVisible()
        new_state = not is_visible
        self.advanced_filters_container.setVisible(new_state)
        self.filter_search_field.setVisible(new_state)

        if new_state:
            self.toggle_advanced_btn.setText("▲ Скрыть дополнительные фильтры")
            self.filter_search_field.setFocus()
        else:
            self.toggle_advanced_btn.setText("▼ Показать дополнительные фильтры")
            self.filter_search_field.clear()
        QTimer.singleShot(50, self.update_scroll_area_size)
        
    def update_scroll_area_size(self):
        """Принудительно обновить размеры scroll area"""
        self.left_scroll.updateGeometry()
        self.left_scroll.widget().updateGeometry()
        # Если нужно — проскроллить к верху
        self.left_scroll.ensureWidgetVisible(self.toggle_advanced_btn)
    def on_combo_changed(self, field_name: str, combo: QComboBox):
        """Обработчик изменения комбобоксов (с данными из reference)"""
        data = combo.currentData()
        if data is None:
            self.active_filters.pop(field_name, None)
        else:
            self.active_filters[field_name] = data
        self.schedule_search_and_update_tags()

    def schedule_search_and_update_tags(self):
        """Запуск таймера поиска + обновление тегов"""
        self.update_filter_tags()
        self.restart_search_timer()

    def update_filter_tags(self):
            """Обновить отображение тегов с поддержкой переноса"""
            # Очистка
            while self.tags_flow_layout.count():
                child = self.tags_flow_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            # Создание тегов
            for field, value in self.active_filters.items():
                display = self.format_filter_display(field, value)
                if not display:
                    continue
                tag = FilterTag(field, display)
                tag.removed.connect(self.on_tag_removed)
                self.tags_flow_layout.addWidget(tag)

            # Если нет фильтров — добавим подсказку
            if not self.active_filters:
                empty_label = QLabel("Нет активных фильтров")
                empty_label.setStyleSheet("color: #95a5a6; font-style: italic; font-size: 9pt;")
                self.tags_flow_layout.addWidget(empty_label)

    def format_filter_display(self, field: str, value) -> str:
        """Преобразует фильтр в человекочитаемый текст для тега"""
        # Обработка текстовых полей ввода
        if field == 'reg_number':
            stripped = value.strip()
            return f"🔖 Рег. номер: {stripped}" if stripped else ""
        if field == 'text_search':
            stripped = value.strip()
            return f"📝 Текст: {stripped}" if stripped else ""
        if field == 'case_number':
            stripped = value.strip()
            return f"📁 Дело №: {stripped}" if stripped else ""
        if field == 'volume_number':
            stripped = value.strip()
            return f"📚 Том №: {stripped}" if stripped else ""

        # Справочники (комбобоксы)
        labels = {
            'status_id': "Статус",
            'type_id': "Тип",
            'document_kind_id': "Вид",
            'signing_type_id': "Подписание",
            'executor_id': "Исполнитель",
            'responsible_executor_id': "Ответственный",
            'theme_id': "Тема",
            'published_where_id': "Где опубл.",
            'should_publish': "Подлежит публикации",
            'removed_from_control': "Снято с контроля",
            'date_from': "От даты",
            'date_to': "До даты",
        }

        # Комбобоксы с _id
        if field.endswith('_id'):
            widget_map = {
                'status_id': self.status_combo,
                'type_id': self.type_combo,
                'document_kind_id': self.document_kind_combo,
                'signing_type_id': self.signing_type_combo,
                'executor_id': self.executor_combo,
                'responsible_executor_id': self.responsible_executor_combo,
                'theme_id': self.theme_combo,
                'published_where_id': self.published_where_combo,
            }
            widget = widget_map.get(field)
            if widget:
                text = widget.currentText()
                if text and text != "Любой":
                    return f"{labels.get(field, field)}: {text}"
            return ""

        # Даты
        if field in ('date_from', 'date_to'):
            if isinstance(value, str) and value.strip():
                return f"{labels[field]}: {value}"
            return ""

        # Булев-подобные поля
        if field == 'should_publish':
            if value not in ("", "Любое", "Не указано"):
                return f"{labels[field]}: {value}"
        if field == 'removed_from_control':
            if value not in ("", "Любое"):
                return f"{labels[field]}: {value}"

        return ""

    def on_tag_removed(self, field_name: str):
        """Обработка удаления тега"""
        self.active_filters.pop(field_name, None)

        # Сброс виджета
        if field_name == 'date_from':
            self.date_from.setDate(QDate.currentDate().addYears(-1))
        elif field_name == 'date_to':
            self.date_to.setDate(QDate.currentDate())
        elif field_name == 'should_publish':
            self.should_publish_combo.setCurrentIndex(0)
        elif field_name == 'removed_from_control':
            self.removed_from_control_combo.setCurrentIndex(0)
        elif field_name == 'case_number':
            self.case_number_field.clear()
        elif field_name == 'volume_number':
            self.volume_number_field.clear()
        elif field_name.endswith('_id'):
            widget_map = {
                'status_id': self.status_combo,
                'type_id': self.type_combo,
                'document_kind_id': self.document_kind_combo,
                'signing_type_id': self.signing_type_combo,
                'executor_id': self.executor_combo,
                'responsible_executor_id': self.responsible_executor_combo,
                'theme_id': self.theme_combo,
                'published_where_id': self.published_where_combo,
            }
            widget = widget_map.get(field_name)
            if widget:
                widget.setCurrentIndex(0)

        self.update_filter_tags()
        self.restart_search_timer()

    def reset_filters(self):
        """Сброс всех фильтров (включая теги)"""
        self.active_filters.clear()
        # Весь ваш существующий код сброса
        
        self.date_from.setDate(QDate.currentDate().addYears(-1))
        self.date_to.setDate(QDate.currentDate())
        self.status_combo.setCurrentIndex(0)
        self.type_combo.setCurrentIndex(0)
        self.document_kind_combo.setCurrentIndex(0)
        self.signing_type_combo.setCurrentIndex(0)
        self.executor_combo.setCurrentIndex(0)
        self.responsible_executor_combo.setCurrentIndex(0)
        self.theme_combo.setCurrentIndex(0)
        self.should_publish_combo.setCurrentIndex(0)
        self.published_where_combo.setCurrentIndex(0)
        self.removed_from_control_combo.setCurrentIndex(0)
        self.case_number_field.clear()
        self.volume_number_field.clear()
        self.update_filter_tags()
        self.restart_search_timer()
        self.update_filter_tags()
        
        self.restart_search_timer()
    
    def load_reference(self, table_name, combo_widget):
        """Загрузка справочника в комбобокс"""
        try:
            combo_widget.clear()
            combo_widget.addItem("Любой", None)
            
            query = f"SELECT id, name FROM {table_name} ORDER BY name"
            items = self.db_manager.execute_query(query)
            
            for item in items:
                combo_widget.addItem(item['name'], item['id'])
            
            print(f"✅ Загружен справочник {table_name}: {len(items)} записей")
        except Exception as e:
            print(f"❌ Ошибка загрузки справочника {table_name}: {e}")
            combo_widget.addItem("-- Ошибка загрузки --", None)
    
    
    def on_field_changed(self, field_name: str, value):
        """Общий обработчик изменения текстовых/дата-полей"""
        if value in ("", "Любое", QDate(), None):
            self.active_filters.pop(field_name, None)
        else:
            self.active_filters[field_name] = value
        self.schedule_search_and_update_tags()
    def filter_advanced_groups(self, text: str):
        """Фильтрует видимость групп внутри advanced_filters_container по названию"""
        if not text.strip():
            # Если пусто — показываем все
            for i in range(self.advanced_filters_container.layout().count()):
                widget = self.advanced_filters_container.layout().itemAt(i).widget()
                if widget:
                    widget.setVisible(True)
            return

        text_lower = text.lower()
        # Сопоставление: текст ↔ группа
        group_labels = {
            self.main_group: "основные параметры статус тип вид подписани",
            self.executors_group: "исполнители ответственный тема",
            self.publication_group: "публикация подлежит где опубликовано",
            self.control_group: "контроль списание дело том",
        }

        for group, keywords in group_labels.items():
            if text_lower in keywords:
                group.setVisible(True)
            else:
                group.setVisible(False)


    def on_tag_removed(self, field_name: str):
        """Обработка удаления тега — сброс соответствующего поля"""
        self.active_filters.pop(field_name, None)

        # Сброс конкретного виджета
        if field_name == 'reg_number':
            self.reg_number_field.clear()
        elif field_name == 'text_search':
            self.text_search_field.clear()
        elif field_name == 'case_number':
            self.case_number_field.clear()
        elif field_name == 'volume_number':
            self.volume_number_field.clear()

        self.update_filter_tags()
        self.restart_search_timer()
    def restart_search_timer(self):
        """Перезапуск таймера поиска"""
        self.search_timer.start()
        self.status_label.setText("🔄 Поиск...")
        self.status_label.setStyleSheet(f"""
            QLabel {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.WARNING_LIGHT}, stop:1 #fff8e1);
                border: 2px solid {AppColors.WARNING};
                border-radius: 8px;
                padding: 10px 15px;
                color: {AppColors.WARNING_DARK};
                font-weight: 600;
                font-size: 10pt;
            }}
        """)
    
    def close_dialog(self):
        """Закрыть диалог при выборе редактирования метаданных"""
        self.accept()
    def set_current_year(self):
        """Установить период на текущий год"""
        current_year = QDate.currentDate().year()
        self.date_from.setDate(QDate(current_year, 1, 1))
        self.date_to.setDate(QDate(current_year, 12, 31))
        self.restart_search_timer()

    def set_last_year(self):
        """Установить период на прошлый год"""
        last_year = QDate.currentDate().year() - 1
        self.date_from.setDate(QDate(last_year, 1, 1))
        self.date_to.setDate(QDate(last_year, 12, 31))
        self.restart_search_timer()

    def set_current_quarter(self):
        """Установить период на текущий квартал"""
        today = QDate.currentDate()
        quarter = (today.month() - 1) // 3
        start_month = quarter * 3 + 1
        end_month = start_month + 2
        # Определяем последний день месяца
        end_day = QDate(today.year(), end_month, 1).daysInMonth()
        self.date_from.setDate(QDate(today.year(), start_month, 1))
        self.date_to.setDate(QDate(today.year(), end_month, end_day))
        self.restart_search_timer()

    def smart_date_fill(self):
        """Интеллектуальное заполнение периода при изменении одной даты"""
        from_date = self.date_from.date()
        to_date = self.date_to.date()
        today = QDate.currentDate()

        # Если "От" не задан, но задан "До" → "От" = начало года
        if from_date == QDate(2024, 1, 1) and to_date != today:  # ваше значение по умолчанию
            self.date_from.setDate(QDate(to_date.year(), 1, 1))
        # Если "До" не задан, но задан "От" → "До" = сегодня
        elif to_date == today and from_date != QDate(2024, 1, 1):
            self.date_to.setDate(today)
    
    def do_search(self):
        """Выполняет поиск с учётом self.active_filters"""
        try:
            query = """
                SELECT 
                    d.id, d.reg_number, d.reg_date, d.title, d.number,
                    d.case_number, d.volume_number,
                    s.name as status_name, dt.name as type_name,
                    dk.name as document_kind_name, st.name as signing_type_name,
                    e.name as executor_name, re.name as responsible_executor_name,
                    t.name as theme_name, pw.name as published_where_name,
                    d.should_publish, d.removed_from_control
                FROM documents d
                LEFT JOIN ref_status s ON d.status_id = s.id
                LEFT JOIN ref_document_types dt ON d.type_id = dt.id
                LEFT JOIN ref_document_kinds dk ON d.document_kind_id = dk.id
                LEFT JOIN ref_signing_types st ON d.signing_type_id = st.id
                LEFT JOIN ref_executors e ON d.executor_id = e.id
                LEFT JOIN ref_responsible_executors re ON d.responsible_executor_id = re.id
                LEFT JOIN ref_themes t ON d.theme_id = t.id
                LEFT JOIN ref_published_where pw ON d.published_where_id = pw.id
                WHERE 1=1
            """
            params = []

            # === ПОИСК ПО РЕГ. НОМЕРУ ===
            if 'reg_number' in self.active_filters:
                query += " AND d.reg_number LIKE ?"
                params.append(f"%{self.active_filters['reg_number']}%")

            # === ТЕКСТОВЫЙ ПОИСК (по другим полям) ===
            if 'text_search' in self.active_filters:
                pattern = f"%{self.active_filters['text_search']}%"
                query += """ AND (
                    d.title LIKE ? OR
                    e.name LIKE ? OR
                    t.name LIKE ? OR
                    d.case_number LIKE ? OR
                    d.number LIKE ?
                )"""
                params.extend([pattern] * 5)

            if 'date_from' in self.active_filters:
                query += " AND d.reg_date >= ?"
                params.append(self.active_filters['date_from'])
            if 'date_to' in self.active_filters:
                query += " AND d.reg_date <= ?"
                params.append(self.active_filters['date_to'])

            id_fields = ['status_id', 'type_id', 'document_kind_id', 'signing_type_id',
                         'executor_id', 'responsible_executor_id', 'theme_id', 'published_where_id']
            for f in id_fields:
                if f in self.active_filters:
                    col = f.replace('_id', '') + '_id'
                    query += f" AND d.{col} = ?"
                    params.append(self.active_filters[f])

            if 'should_publish' in self.active_filters:
                val = self.active_filters['should_publish']
                if val != "Любое":
                    query += " AND d.should_publish = ?"
                    params.append(val)

            if 'removed_from_control' in self.active_filters:
                val = self.active_filters['removed_from_control']
                if val != "Любое":
                    query += " AND d.removed_from_control = ?"
                    params.append(val)

            if 'case_number' in self.active_filters:
                query += " AND d.case_number LIKE ?"
                params.append(f"%{self.active_filters['case_number']}%")

            if 'volume_number' in self.active_filters:
                query += " AND d.volume_number LIKE ?"
                params.append(f"%{self.active_filters['volume_number']}%")

            query += " ORDER BY d.reg_date DESC LIMIT 1000"
            documents = self.db_manager.execute_query(query, tuple(params))
            self.results_table.update_with_documents(documents)
            count = len(documents)
            self.results_count_label.setText(f"Документов: {count}")

            if count == 0:
                self.status_label.setText("❌ Не найдено")
                self.status_label.setStyleSheet(f"""
                    QLabel {{
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 {AppColors.DANGER_LIGHT}, stop:1 #ffebee);
                        border: 2px solid {AppColors.DANGER};
                        border-radius: 8px;
                        padding: 10px 15px;
                        color: {AppColors.DANGER_DARK};
                        font-size: 10pt;
                        font-weight: 600;
                    }}
                """)
            else:
                self.status_label.setText(f"✅ Найдено: {count}")
                self.status_label.setStyleSheet(f"""
                    QLabel {{
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 {AppColors.SUCCESS_LIGHT}, stop:1 #e8f5e9);
                        border: 2px solid {AppColors.SUCCESS};
                        border-radius: 8px;
                        padding: 10px 15px;
                        color: {AppColors.SUCCESS_DARK};
                        font-size: 10pt;
                        font-weight: 600;
                    }}
                """)
            
        except Exception as e:
            self.status_label.setText(f"❌ Ошибка: {str(e)[:30]}...")
            self.status_label.setStyleSheet(f"""
                QLabel {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 {AppColors.DANGER_LIGHT}, stop:1 #ffebee);
                    border: 2px solid {AppColors.DANGER};
                    border-radius: 8px;
                    padding: 10px 15px;
                    color: {AppColors.DANGER_DARK};
                    font-weight: 600;
                    font-size: 10pt;
                }}
            """)
            print(f"❌ Ошибка поиска: {e}")
            import traceback
            traceback.print_exc()


class SearchResultsTableView(QTableView):
    """Таблица результатов поиска с контекстным меню"""
    
    edit_metadata_requested = pyqtSignal(int)
    preview_requested = pyqtSignal(int)
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.setup_table()
    
    def setup_table(self):
        """Настройка таблицы результатов"""
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)
        self.setFocusPolicy(Qt.NoFocus)
        self.setStyleSheet(AppStyles.table_view())
        self.doubleClicked.connect(self.on_double_click)
    
    def update_with_documents(self, documents):
        """Обновление таблицы с документами - РАСШИРЕННАЯ ВЕРСИЯ"""
        try:
            table_data = []
            for doc in documents:
                row = [
                    doc.get('id', ''),
                    doc.get('title') or "Без названия",
                    doc.get('reg_number') or "-",
                    doc.get('number') or "-",
                    doc.get('reg_date') or "-",
                    doc.get('status_name') or "Не указан",
                    doc.get('type_name') or "Не указан",
                    doc.get('document_kind_name') or "-",
                    doc.get('signing_type_name') or "-",
                    doc.get('executor_name') or "Не назначен",
                    doc.get('responsible_executor_name') or "-",
                    doc.get('theme_name') or "Не указана",
                    doc.get('published_where_name') or "-",
                    doc.get('should_publish') or "-",
                    doc.get('case_number') or "-",
                    doc.get('volume_number') or "-",
                ]
                table_data.append(row)
            
            headers = [
                "ID", "Название", "Рег. №", "Доп. №", "Дата", "Статус", 
                "Тип", "Вид", "Подписание", "Исполнитель", "Ответственный",
                "Тема", "Где опубликовано", "К публикации", "Дело №", "Том №"
            ]
            
            # Создаем модель
            self.model_instance = DocumentsTableModel(table_data, headers)
            self.setModel(self.model_instance)
            
            # Настраиваем размеры колонок
            column_widths = [50, 250, 80, 70, 90, 110, 100, 90, 100, 130, 130, 130, 120, 80, 70, 70]
            for i, width in enumerate(column_widths):
                self.setColumnWidth(i, width)
            
            # Устанавливаем высоту строк
            self.verticalHeader().setDefaultSectionSize(35)
            
        except Exception as e:
            print(f"❌ Ошибка обновления таблицы результатов: {e}")
    
    def contextMenuEvent(self, event):
        """Контекстное меню для таблицы результатов"""
        try:
            index = self.indexAt(event.pos())
            if not index.isValid():
                return
            
            menu = QMenu(self)
            menu.setStyleSheet(AppStyles.menu())
            
            row = index.row()
            doc_id = self.model()._data[row][0]
            
            preview_action = QAction("👁 Предпросмотр", self)
            preview_action.triggered.connect(lambda: self.open_preview_dialog(doc_id))
            
            metadata_action = QAction("📋 Редактировать метаданные", self)
            metadata_action.triggered.connect(lambda: self.edit_metadata_requested.emit(doc_id))
            
            menu.addAction(preview_action)
            menu.addSeparator()
            menu.addAction(metadata_action)
            
            menu.exec_(event.globalPos())
        except Exception as e:
            print(f"❌ Ошибка контекстного меню: {e}")
    
    def open_preview_dialog(self, doc_id):
        """Открывает диалог предпросмотра документа"""
        try:
            document_data = self.db_manager.get_document_by_id(doc_id)
            if document_data and document_data.get("document_path"):
                preview_dialog = DocumentPreviewDialog(
                    self.parent().document_handler,
                    document_data["document_path"], 
                    self
                )
                preview_dialog.exec_()
        except Exception as e:
            print(f"❌ Ошибка открытия предпросмотра: {e}")
    
    def on_double_click(self, index):
        """Обработчик двойного клика - открываем редактор метаданных"""
        if not index.isValid():
            return
        
        try:
            row = index.row()
            doc_id = self.model()._data[row][0]
            # ✅ ИЗМЕНЕНО: Открываем редактор метаданных вместо предпросмотра
            self.edit_metadata_requested.emit(doc_id)
            print(f"✅ Двойной клик: открытие редактора для документа ID {doc_id}")
        except Exception as e:
            print(f"❌ Ошибка при двойном клике: {e}")
