from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QModelIndex, QAbstractTableModel, QDate, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QColor, QFont, QKeySequence, QTextCursor, QPalette, QIcon, QPainter, QLinearGradient
from document_loader import DocumentLoader
import re


class ModernButton(QPushButton):
    """Современная стилизованная кнопка"""
    def __init__(self, text, icon="", style_type="primary"):
        super().__init__(text)
        self.setMinimumHeight(32)
        self.setCursor(Qt.PointingHandCursor)
        
        if style_type == "primary":
            self.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #4A90E2, stop:1 #357ABD);
                    border: none;
                    border-radius: 6px;
                    color: white;
                    font-weight: bold;
                    padding: 6px 16px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #5BA0F2, stop:1 #4A90E2);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #357ABD, stop:1 #2E5F8F);
                }
                QPushButton:disabled {
                    background: #CCCCCC;
                    color: #888888;
                }
            """)
        elif style_type == "secondary":
            self.setStyleSheet("""
                QPushButton {
                    background: #F5F5F5;
                    border: 1px solid #E0E0E0;
                    border-radius: 6px;
                    color: #333;
                    padding: 6px 16px;
                }
                QPushButton:hover {
                    background: #EEEEEE;
                    border-color: #D0D0D0;
                }
                QPushButton:pressed {
                    background: #E0E0E0;
                }
                QPushButton:checked {
                    background: #4A90E2;
                    color: white;
                    border-color: #357ABD;
                }
            """)
        elif style_type == "danger":
            self.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #E74C3C, stop:1 #C0392B);
                    border: none;
                    border-radius: 6px;
                    color: white;
                    font-weight: bold;
                    padding: 6px 16px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #EC7063, stop:1 #E74C3C);
                }
            """)


class ModernSearchWidget(QWidget):
    """Современный виджет поиска внизу окна"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_dialog = parent
        self.setup_ui()
        self.setup_style()
        
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        
        # Иконка поиска
        search_icon = QLabel("🔍")
        search_icon.setFixedWidth(30)
        
        # Поле поиска
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по документу... (Ctrl+F)")
        self.search_input.textChanged.connect(self.on_search_changed)
        self.search_input.returnPressed.connect(self.find_next)
        
        # Кнопки навигации
        self.prev_btn = ModernButton("◀", style_type="secondary")
        self.prev_btn.setMaximumWidth(35)
        self.prev_btn.clicked.connect(self.find_previous)
        
        self.next_btn = ModernButton("▶", style_type="secondary") 
        self.next_btn.setMaximumWidth(35)
        self.next_btn.clicked.connect(self.find_next)
        
        # Счетчик результатов
        self.counter_label = QLabel("0/0")
        self.counter_label.setMinimumWidth(60)
        self.counter_label.setAlignment(Qt.AlignCenter)
        
        # Опция учета регистра
        self.case_cb = QCheckBox("Регистр")
        self.case_cb.toggled.connect(self.on_search_changed)
        
        # Кнопка закрытия
        self.close_btn = ModernButton("✕", style_type="danger")
        self.close_btn.setMaximumWidth(30)
        self.close_btn.clicked.connect(self.hide)
        
        # Добавляем виджеты
        layout.addWidget(search_icon)
        layout.addWidget(self.search_input, 1)
        layout.addWidget(self.prev_btn)
        layout.addWidget(self.next_btn)
        layout.addWidget(self.counter_label)
        layout.addWidget(QFrame())  # Разделитель
        layout.addWidget(self.case_cb)
        layout.addWidget(self.close_btn)
        
    def setup_style(self):
        self.setStyleSheet("""
            ModernSearchWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FAFAFA, stop:1 #F0F0F0);
                border-top: 1px solid #E0E0E0;
            }
            QLineEdit {
                border: 1px solid #D0D0D0;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 14px;
                background: white;
            }
            QLineEdit:focus {
                border-color: #4A90E2;
                outline: none;
            }
            QCheckBox {
                color: #555;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                background: white;
                border: 1px solid #CCC;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background: #4A90E2;
                border: 1px solid #357ABD;
                border-radius: 3px;
            }
            QLabel {
                color: #666;
                font-size: 13px;
            }
        """)
        
    def on_search_changed(self):
        if self.parent_dialog:
            self.parent_dialog.perform_search()
            
    def find_next(self):
        if self.parent_dialog:
            self.parent_dialog.find_next()
            
    def find_previous(self):
        if self.parent_dialog:
            self.parent_dialog.find_previous()
            
    def update_counter(self, current, total):
        self.counter_label.setText(f"{current}/{total}")
        
    def focus_search(self):
        self.search_input.setFocus()
        self.search_input.selectAll()


class DocumentPreviewDialog(QDialog):
    """Современное диалоговое окно предпросмотра документа"""
    
    def __init__(self, document_handler, filename, parent=None):
        super().__init__(parent)
        self.document_handler = document_handler
        self.filename = filename
        self.original_text = ""
        self.search_results = []
        self.current_search_index = -1
        
        self.setWindowTitle(f"📄 {filename}")
        self.setMinimumSize(1100, 750)
        self.resize(1300, 900)
        
        self.document_loader = None
        self.init_ui()
        self.setup_shortcuts()
        self.apply_modern_style()
        self.load_document_async()
        
    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Заголовочная панель
        self.create_header()
        main_layout.addWidget(self.header)
        
        # Панель инструментов
        self.create_toolbar()
        main_layout.addWidget(self.toolbar)
        
        # Панель загрузки
        self.create_loading_panel()
        main_layout.addWidget(self.loading_widget)
        
        # Основной контент
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        
        # Создаем главную область с текстом
        text_container = QWidget()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(QFont("Consolas", 12))
        
        text_layout.addWidget(self.text_edit)
        
        # Боковая панель
        self.create_modern_sidebar()
        
        content_layout.addWidget(text_container, 4)
        content_layout.addWidget(self.sidebar, 1)
        
        main_layout.addWidget(content_widget, 1)
        
        # Панель поиска (внизу)
        self.search_widget = ModernSearchWidget(self)
        main_layout.addWidget(self.search_widget)
        self.search_widget.setVisible(False)
        
        # Статусная строка
        self.create_status_bar()
        main_layout.addWidget(self.status_bar)
        
        self.setLayout(main_layout)
        
    def create_header(self):
        """Создать современный заголовок"""
        self.header = QWidget()
        self.header.setFixedHeight(60)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(20, 10, 20, 10)
        
        # Иконка и заголовок
        title_layout = QVBoxLayout()
        self.title_label = QLabel(f"📄 {self.filename}")
        self.title_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        
        self.subtitle_label = QLabel("Предпросмотр документа")
        self.subtitle_label.setFont(QFont("Segoe UI", 10))
        
        title_layout.addWidget(self.title_label)
        title_layout.addWidget(self.subtitle_label)
        title_layout.setSpacing(2)
        
        header_layout.addLayout(title_layout, 1)
        
        # Кнопки управления окном
        self.minimize_btn = ModernButton("🗕", style_type="secondary")
        self.minimize_btn.setMaximumWidth(35)
        self.minimize_btn.clicked.connect(self.showMinimized)
        
        self.close_header_btn = ModernButton("✕", style_type="danger")
        self.close_header_btn.setMaximumWidth(35)
        self.close_header_btn.clicked.connect(self.accept)
        
        header_layout.addWidget(self.minimize_btn)
        header_layout.addWidget(self.close_header_btn)
        
    def create_toolbar(self):
        """Создать современную панель инструментов"""
        self.toolbar = QWidget()
        self.toolbar.setFixedHeight(50)
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(15, 8, 15, 8)
        
        # Группа: Размер текста
        font_group = QWidget()
        font_layout = QHBoxLayout(font_group)
        font_layout.setContentsMargins(0, 0, 0, 0)
        
        font_layout.addWidget(QLabel("Шрифт:"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 32)
        self.font_size_spin.setValue(12)
        self.font_size_spin.valueChanged.connect(self.change_font_size)
        font_layout.addWidget(self.font_size_spin)
        
        # Кнопки управления
        self.word_wrap_btn = ModernButton("📄 Перенос", style_type="secondary")
        self.word_wrap_btn.setCheckable(True)
        self.word_wrap_btn.setChecked(True)
        self.word_wrap_btn.toggled.connect(self.toggle_word_wrap)
        
        self.search_toggle_btn = ModernButton("🔍 Найти", style_type="primary")
        self.search_toggle_btn.clicked.connect(self.toggle_search)
        
        self.copy_btn = ModernButton("📋 Копировать", style_type="secondary")
        self.copy_btn.clicked.connect(self.copy_all_text)
        
        # Добавляем элементы
        toolbar_layout.addWidget(font_group)
        toolbar_layout.addWidget(self.create_separator())
        toolbar_layout.addWidget(self.word_wrap_btn)
        toolbar_layout.addWidget(self.search_toggle_btn)
        toolbar_layout.addWidget(self.create_separator())
        toolbar_layout.addWidget(self.copy_btn)
        toolbar_layout.addStretch()
        
    def create_separator(self):
        """Создать разделитель"""
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        return separator
        
    def create_loading_panel(self):
        """Создать панель загрузки"""
        self.loading_widget = QWidget()
        self.loading_widget.setFixedHeight(60)
        loading_layout = QHBoxLayout(self.loading_widget)
        loading_layout.setContentsMargins(20, 10, 20, 10)
        
        self.loading_label = QLabel("🔄 Загрузка документа...")
        self.loading_label.setFont(QFont("Segoe UI", 11))
        
        self.loading_progress = QProgressBar()
        self.loading_progress.setRange(0, 0)
        self.loading_progress.setFixedHeight(8)
        
        self.cancel_btn = ModernButton("❌ Отменить", style_type="danger")
        self.cancel_btn.clicked.connect(self.cancel_loading)
        
        loading_layout.addWidget(self.loading_label)
        loading_layout.addWidget(self.loading_progress, 1)
        loading_layout.addWidget(self.cancel_btn)
        
    def create_modern_sidebar(self):
        """Создать современную боковую панель"""
        self.sidebar = QWidget()
        self.sidebar.setMaximumWidth(280)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setSpacing(15)
        
        # Статистика файла
        stats_card = self.create_card("📊 Статистика")
        stats_layout = QVBoxLayout()
        
        # Создаем QVBoxLayout внутри карточки
        stats_content = QWidget()
        stats_content_layout = QVBoxLayout(stats_content)
        
        self.stats_labels = {
            'chars': QLabel("Символов: —"),
            'words': QLabel("Слов: —"),
            'lines': QLabel("Строк: —"),
            'size': QLabel("Размер: —")
        }
        
        for label in self.stats_labels.values():
            label.setFont(QFont("Segoe UI", 10))
            stats_content_layout.addWidget(label)
            
        stats_card.layout().addWidget(stats_content)
        
        # Навигация
        nav_card = self.create_card("🧭 Навигация")
        nav_content = QWidget()
        nav_content_layout = QVBoxLayout(nav_content)
        
        # Переход к строке
        goto_layout = QHBoxLayout()
        goto_layout.addWidget(QLabel("Строка:"))
        self.goto_line_input = QSpinBox()
        self.goto_line_input.setMinimum(1)
        self.goto_line_input.setMaximum(1)
        goto_layout.addWidget(self.goto_line_input, 1)
        
        goto_btn = ModernButton("→", style_type="primary")
        goto_btn.setMaximumWidth(35)
        goto_btn.clicked.connect(self.goto_line)
        goto_layout.addWidget(goto_btn)
        
        nav_content_layout.addLayout(goto_layout)
        
        # Быстрые переходы
        nav_buttons_layout = QHBoxLayout()
        top_btn = ModernButton("⬆ Начало", style_type="secondary")
        top_btn.clicked.connect(lambda: self.text_edit.moveCursor(QTextCursor.Start))
        
        bottom_btn = ModernButton("⬇ Конец", style_type="secondary")
        bottom_btn.clicked.connect(lambda: self.text_edit.moveCursor(QTextCursor.End))
        
        nav_buttons_layout.addWidget(top_btn)
        nav_buttons_layout.addWidget(bottom_btn)
        nav_content_layout.addLayout(nav_buttons_layout)
        
        nav_card.layout().addWidget(nav_content)
        
        sidebar_layout.addWidget(stats_card)
        sidebar_layout.addWidget(nav_card)
        sidebar_layout.addStretch()
        
    def create_card(self, title):
        """Создать карточку с заголовком"""
        card = QWidget()
        card.setStyleSheet("""
            QWidget {
                background: white;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
            }
        """)
        
        main_layout = QVBoxLayout(card)
        main_layout.setContentsMargins(15, 10, 15, 10)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        title_label.setStyleSheet("border: none; color: #333; padding: 0; background: transparent;")
        
        main_layout.addWidget(title_label)
        
        return card
        
    def create_status_bar(self):
        """Создать статусную строку"""
        self.status_bar = QWidget()
        self.status_bar.setFixedHeight(30)
        status_layout = QHBoxLayout(self.status_bar)
        status_layout.setContentsMargins(15, 5, 15, 5)
        
        self.status_label = QLabel("Готово к загрузке")
        self.status_label.setFont(QFont("Segoe UI", 9))
        
        status_layout.addWidget(self.status_label, 1)
        
    def apply_modern_style(self):
        """Применить современные стили"""
        self.setStyleSheet("""
            QDialog {
                background: #F8F9FA;
            }
            QWidget#header {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F0F0F0);
                border-bottom: 1px solid #E0E0E0;
            }
            QWidget#toolbar {
                background: #FAFAFA;
                border-bottom: 1px solid #E8E8E8;
            }
            QWidget#loading_widget {
                background: #FFF3CD;
                border: 1px solid #FFEAA7;
                border-radius: 4px;
                margin: 10px;
            }
            QTextEdit {
                background: white;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                padding: 15px;
                font-family: 'Consolas', 'Monaco', monospace;
                line-height: 1.4;
                color: #2C3E50;
            }
            QSpinBox {
                border: 1px solid #D0D0D0;
                border-radius: 4px;
                padding: 4px 8px;
                background: white;
                min-width: 60px;
                color: #333;
            }
            QSpinBox:focus {
                border-color: #4A90E2;
            }
            QProgressBar {
                border: none;
                border-radius: 4px;
                background: #E0E0E0;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4A90E2, stop:1 #74B9FF);
                border-radius: 4px;
            }
            QWidget#status_bar {
                background: #F0F0F0;
                border-top: 1px solid #E0E0E0;
            }
            QLabel {
                color: #2C3E50;
            }
        """)
        
        # Устанавливаем идентификаторы для стилизации
        self.header.setObjectName("header")
        self.toolbar.setObjectName("toolbar")
        self.loading_widget.setObjectName("loading_widget")
        self.status_bar.setObjectName("status_bar")
    
    def setup_shortcuts(self):
        """Настроить горячие клавиши"""
        QShortcut(QKeySequence("Ctrl+F"), self, self.toggle_search)
        QShortcut(QKeySequence("Escape"), self, self.hide_search_if_visible)
        QShortcut(QKeySequence("F3"), self, self.find_next)
        QShortcut(QKeySequence("Shift+F3"), self, self.find_previous)
        QShortcut(QKeySequence("Ctrl+A"), self, self.select_all_text)
    
    def hide_search_if_visible(self):
        """Скрыть поиск если виден"""
        if self.search_widget.isVisible():
            self.search_widget.setVisible(False)
            self.clear_search_highlights()
    
    def toggle_search(self):
        """Переключить панель поиска"""
        visible = not self.search_widget.isVisible()
        self.search_widget.setVisible(visible)
        if visible:
            self.search_widget.focus_search()
        else:
            self.clear_search_highlights()
    
    def perform_search(self):
        """Выполнить поиск"""
        query = self.search_widget.search_input.text().strip()
        if not query:
            self.clear_search_highlights()
            self.search_widget.update_counter(0, 0)
            return
        
        # Определяем флаги поиска
        flags = 0 if self.search_widget.case_cb.isChecked() else re.IGNORECASE
        
        try:
            self.search_results.clear()
            
            # Обычный поиск
            pattern = re.compile(re.escape(query), flags)
            for match in pattern.finditer(self.original_text):
                self.search_results.append((match.start(), match.end()))
            
            # Обновляем интерфейс
            total = len(self.search_results)
            self.search_widget.update_counter(1 if total > 0 else 0, total)
            
            if total > 0:
                self.current_search_index = 0
                self.highlight_search_results()
                self.show_current_result()
            else:
                self.clear_search_highlights()
                self.current_search_index = -1
                
        except re.error as e:
            self.search_widget.update_counter(0, 0)
            self.status_label.setText(f"❌ Ошибка поиска: {str(e)}")
    
    def find_next(self):
        """Найти следующий результат"""
        if not self.search_results:
            return
        
        self.current_search_index = (self.current_search_index + 1) % len(self.search_results)
        self.show_current_result()
        self.search_widget.update_counter(self.current_search_index + 1, len(self.search_results))
    
    def find_previous(self):
        """Найти предыдущий результат"""
        if not self.search_results:
            return
        
        self.current_search_index = (self.current_search_index - 1) % len(self.search_results)
        self.show_current_result()
        self.search_widget.update_counter(self.current_search_index + 1, len(self.search_results))
    
    def show_current_result(self):
        """Показать текущий результат поиска"""
        if not self.search_results or self.current_search_index < 0:
            return
        
        start, end = self.search_results[self.current_search_index]
        
        # Выделяем текущий результат
        cursor = self.text_edit.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()
    
    def highlight_search_results(self):
        """Подсветить все результаты поиска"""
        self.clear_search_highlights()
        
        if not self.search_results:
            return
        
        # Создаем формат для подсветки
        cursor = self.text_edit.textCursor()
        highlight_format = cursor.charFormat()
        highlight_format.setBackground(QColor(255, 255, 0, 80))  # Полупрозрачный желтый
        
        current_format = cursor.charFormat()
        current_format.setBackground(QColor(255, 165, 0, 120))  # Оранжевый для текущего
        
        # Подсвечиваем все результаты
        for i, (start, end) in enumerate(self.search_results):
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            
            if i == self.current_search_index:
                cursor.mergeCharFormat(current_format)
            else:
                cursor.mergeCharFormat(highlight_format)
    
    def clear_search_highlights(self):
        """Очистить подсветку поиска"""
        cursor = self.text_edit.textCursor()
        cursor.select(QTextCursor.Document)
        format = cursor.charFormat()
        format.setBackground(QColor())
        cursor.mergeCharFormat(format)
        cursor.clearSelection()
    
    def load_document_async(self):
        """Асинхронная загрузка документа"""
        try:
            self.document_loader = DocumentLoader(
                self.document_handler, 
                self.filename, 
                100000  # Увеличенный лимит
            )
            
            self.document_loader.text_loaded.connect(self.on_document_loaded)
            self.document_loader.loading_progress.connect(self.update_loading_status)
            self.document_loader.error_occurred.connect(self.on_loading_error)
            
            self.document_loader.start()
            
        except Exception as e:
            self.on_loading_error(f"Ошибка запуска загрузки: {str(e)}")
    
    def update_loading_status(self, message):
        """Обновить статус загрузки"""
        self.loading_label.setText(message)
        self.status_label.setText(message)
    
    def cancel_loading(self):
        """Отменить загрузку"""
        if self.document_loader and self.document_loader.isRunning():
            self.document_loader.cancel()
            self.loading_label.setText("❌ Загрузка отменена")
            self.loading_progress.setVisible(False)
            self.status_label.setText("Загрузка отменена")
    
    def on_document_loaded(self, text, filename):
        """Обработчик успешной загрузки"""
        try:
            self.original_text = text
            self.text_edit.setPlainText(text)
            
            self.loading_widget.setVisible(False)
            self.update_document_stats()
            self.enable_controls(True)
            
            self.status_label.setText(f"✅ {filename} загружен ({len(text):,} символов)")
            
        except Exception as e:
            self.on_loading_error(f"Ошибка отображения: {str(e)}")
    
    def on_loading_error(self, error_message):
        """Обработчик ошибки загрузки"""
        self.text_edit.setPlainText(f"❌ ОШИБКА ЗАГРУЗКИ:\n\n{error_message}")
        self.loading_widget.setVisible(False)
        self.status_label.setText("❌ Ошибка загрузки")
        self.enable_controls(False)
    
    def update_document_stats(self):
        """Обновить статистику документа"""
        text = self.original_text
        
        char_count = len(text)
        word_count = len([word for word in text.split() if word.strip()])
        line_count = text.count('\n') + 1
        size_kb = char_count / 1024
        
        self.stats_labels['chars'].setText(f"Символов: {char_count:,}")
        self.stats_labels['words'].setText(f"Слов: {word_count:,}")
        self.stats_labels['lines'].setText(f"Строк: {line_count:,}")
        self.stats_labels['size'].setText(f"Размер: {size_kb:.1f} КБ")
        
        self.goto_line_input.setMaximum(line_count)
        
    def enable_controls(self, enabled):
        """Включить/выключить контролы"""
        controls = [
            self.search_toggle_btn, self.copy_btn, self.word_wrap_btn
        ]
        for control in controls:
            control.setEnabled(enabled)
    
    def change_font_size(self, size):
        """Изменить размер шрифта"""
        font = QFont("Consolas", size)
        self.text_edit.setFont(font)
    
    def toggle_word_wrap(self, enabled):
        """Переключить перенос строк"""
        self.text_edit.setLineWrapMode(
            QTextEdit.WidgetWidth if enabled else QTextEdit.NoWrap
        )
    
    def select_all_text(self):
        """Выделить весь текст"""
        self.text_edit.selectAll()
    
    def copy_all_text(self):
        """Копировать весь текст"""
        self.text_edit.selectAll()
        self.text_edit.copy()
        self.text_edit.moveCursor(QTextCursor.Start)
        self.status_label.setText("✅ Текст скопирован в буфер обмена")
        QTimer.singleShot(3000, lambda: self.status_label.setText("Готово"))
    
    def goto_line(self):
        """Перейти к строке"""
        line_number = self.goto_line_input.value()
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.Start)
        
        for _ in range(line_number - 1):
            cursor.movePosition(QTextCursor.Down)
        
        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()
    
    def closeEvent(self, event):
        """Обработчик закрытия"""
        if self.document_loader and self.document_loader.isRunning():
            self.document_loader.cancel()
            self.document_loader.wait(1000)
        event.accept()