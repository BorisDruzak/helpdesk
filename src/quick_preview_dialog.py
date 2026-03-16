from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QTextCursor, QColor, QKeySequence
import re
import time


class QuickDocumentLoader(QThread):
    """Быстрая загрузка первых N символов документа"""
    
    text_loaded = pyqtSignal(str, dict)  # текст, статистика
    error_occurred = pyqtSignal(str)
    
    def __init__(self, document_handler, filename, max_chars=8000):
        super().__init__()
        self.document_handler = document_handler
        self.filename = filename
        self.max_chars = max_chars
    
    def run(self):
        try:
            start_time = time.time()
            
            # Быстрое извлечение текста
            full_text = self.document_handler.extract_text(self.filename)
            
            if not full_text or not full_text.strip():
                self.error_occurred.emit("📄 Документ пуст")
                return
            
            # Берем только первые N символов
            preview_text = full_text[:self.max_chars]
            
            load_time = time.time() - start_time
            
            # Статистика
            stats = {
                'total_chars': len(full_text),
                'preview_chars': len(preview_text),
                'total_lines': full_text.count('\n') + 1,
                'total_words': len(full_text.split()),
                'load_time': load_time,
                'is_truncated': len(full_text) > self.max_chars
            }
            
            # Добавляем предупреждение если текст обрезан
            if stats['is_truncated']:
                preview_text += f"\n\n{'='*60}\n"
                preview_text += f"⚠️ ПОКАЗАНЫ ПЕРВЫЕ {self.max_chars:,} СИМВОЛОВ\n"
                preview_text += f"📊 Всего в документе: {stats['total_chars']:,} символов\n"
                preview_text += f"💡 Используйте 'Полный просмотр' для всего документа\n"
                preview_text += f"{'='*60}"
            
            self.text_loaded.emit(preview_text, stats)
            
        except Exception as e:
            self.error_occurred.emit(f"❌ Ошибка: {str(e)}")


class QuickPreviewDialog(QDialog):
    """Быстрый легкий предпросмотр документа"""
    
    def __init__(self, document_handler, filename, parent=None):
        super().__init__(parent)
        self.document_handler = document_handler
        self.filename = filename
        self.preview_text_content = ""
        self.search_results = []
        self.current_search_index = -1
        
        self.setWindowTitle(f"⚡ Быстрый просмотр: {filename}")
        self.resize(900, 700)
        
        self.init_ui()
        self.setup_shortcuts()
        self.load_document()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # === ВЕРХНЯЯ ПАНЕЛЬ ===
        top_panel = QWidget()
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        # Заголовок
        title = QLabel(f"📄 {self.filename}")
        title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        title.setStyleSheet("color: #2c3e50;")
        
        # Кнопка полного просмотра
        self.full_preview_btn = QPushButton("🔍 Полный просмотр")
        self.full_preview_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        self.full_preview_btn.clicked.connect(self.open_full_preview)
        
        top_layout.addWidget(title)
        top_layout.addStretch()
        top_layout.addWidget(self.full_preview_btn)
        top_panel.setLayout(top_layout)
        
        # === ТЕКСТОВАЯ ОБЛАСТЬ ===
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(QFont("Consolas", 10))
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 12px;
                line-height: 1.5;
            }
        """)
        
        # === ПАНЕЛЬ ПОИСКА ===
        self.search_panel = QWidget()
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Поиск... (Ctrl+F)")
        self.search_input.textChanged.connect(self.perform_search)
        self.search_input.returnPressed.connect(self.find_next)
        
        self.search_counter = QLabel("0/0")
        
        prev_btn = QPushButton("◀")
        prev_btn.setFixedWidth(30)
        prev_btn.clicked.connect(self.find_previous)
        
        next_btn = QPushButton("▶")
        next_btn.setFixedWidth(30)
        next_btn.clicked.connect(self.find_next)
        
        close_search_btn = QPushButton("✕")
        close_search_btn.setFixedWidth(30)
        close_search_btn.clicked.connect(lambda: self.search_panel.hide())
        
        search_layout.addWidget(QLabel("🔍"))
        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(self.search_counter)
        search_layout.addWidget(prev_btn)
        search_layout.addWidget(next_btn)
        search_layout.addWidget(close_search_btn)
        
        self.search_panel.setLayout(search_layout)
        self.search_panel.setVisible(False)
        self.search_panel.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        
        # === НИЖНЯЯ ПАНЕЛЬ (статистика) ===
        self.stats_label = QLabel("⏳ Загрузка...")
        self.stats_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                padding: 6px;
                border-radius: 4px;
                color: #555;
                font-size: 9pt;
            }
        """)
        
        # === КНОПКИ ===
        button_panel = QWidget()
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        copy_btn = QPushButton("📋 Копировать")
        copy_btn.clicked.connect(self.copy_text)
        
        close_btn = QPushButton("✕ Закрыть")
        close_btn.clicked.connect(self.accept)
        
        button_layout.addWidget(copy_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        button_panel.setLayout(button_layout)
        
        # === СБОРКА ===
        layout.addWidget(top_panel)
        layout.addWidget(self.text_edit, 1)
        layout.addWidget(self.search_panel)
        layout.addWidget(self.stats_label)
        layout.addWidget(button_panel)
        
        self.setLayout(layout)
    
    def setup_shortcuts(self):
        """Горячие клавиши"""
        QShortcut(QKeySequence("Ctrl+F"), self, self.toggle_search)
        QShortcut(QKeySequence("Escape"), self, lambda: self.search_panel.hide())
        QShortcut(QKeySequence("F3"), self, self.find_next)
    
    def load_document(self):
        """Быстрая загрузка документа"""
        self.loader = QuickDocumentLoader(self.document_handler, self.filename)
        self.loader.text_loaded.connect(self.on_loaded)
        self.loader.error_occurred.connect(self.on_error)
        self.loader.start()
    
    def on_loaded(self, text, stats):
        """Обработчик успешной загрузки"""
        self.preview_text_content = text
        self.text_edit.setPlainText(text)
        
        # Статистика
        truncated = " (обрезан)" if stats['is_truncated'] else ""
        self.stats_label.setText(
            f"📊 {stats['preview_chars']:,} / {stats['total_chars']:,} симв. | "
            f"📄 {stats['total_lines']:,} строк | "
            f"⚡ {stats['load_time']:.2f}s{truncated}"
        )
        
        # Активируем кнопку полного просмотра только если документ обрезан
        self.full_preview_btn.setEnabled(stats['is_truncated'])
    
    def on_error(self, error):
        """Обработчик ошибки"""
        self.text_edit.setPlainText(error)
        self.stats_label.setText("❌ Ошибка загрузки")
    
    def toggle_search(self):
        """Показать/скрыть поиск"""
        visible = not self.search_panel.isVisible()
        self.search_panel.setVisible(visible)
        if visible:
            self.search_input.setFocus()
            self.search_input.selectAll()
    
    def perform_search(self):
        """Выполнить поиск"""
        query = self.search_input.text().strip()
        if not query:
            self.clear_highlights()
            self.search_counter.setText("0/0")
            return
        
        self.search_results.clear()
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        
        for match in pattern.finditer(self.preview_text_content):
            self.search_results.append((match.start(), match.end()))
        
        total = len(self.search_results)
        self.search_counter.setText(f"1/{total}" if total > 0 else "0/0")
        
        if total > 0:
            self.current_search_index = 0
            self.highlight_results()
            self.show_current()
        else:
            self.clear_highlights()
    
    def find_next(self):
        """Следующий результат"""
        if not self.search_results:
            return
        self.current_search_index = (self.current_search_index + 1) % len(self.search_results)
        self.show_current()
        self.search_counter.setText(f"{self.current_search_index + 1}/{len(self.search_results)}")
    
    def find_previous(self):
        """Предыдущий результат"""
        if not self.search_results:
            return
        self.current_search_index = (self.current_search_index - 1) % len(self.search_results)
        self.show_current()
        self.search_counter.setText(f"{self.current_search_index + 1}/{len(self.search_results)}")
    
    def show_current(self):
        """Показать текущий результат"""
        if not self.search_results or self.current_search_index < 0:
            return
        
        start, end = self.search_results[self.current_search_index]
        cursor = self.text_edit.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()
    
    def highlight_results(self):
        """Подсветить результаты"""
        self.clear_highlights()
        cursor = self.text_edit.textCursor()
        fmt = cursor.charFormat()
        fmt.setBackground(QColor(255, 255, 0, 100))
        
        for start, end in self.search_results:
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            cursor.mergeCharFormat(fmt)
    
    def clear_highlights(self):
        """Очистить подсветку"""
        cursor = self.text_edit.textCursor()
        cursor.select(QTextCursor.Document)
        fmt = cursor.charFormat()
        fmt.setBackground(QColor())
        cursor.mergeCharFormat(fmt)
    
    def copy_text(self):
        """Копировать текст"""
        self.text_edit.selectAll()
        self.text_edit.copy()
        self.text_edit.moveCursor(QTextCursor.Start)
        self.stats_label.setText("✅ Текст скопирован")
    
    def open_full_preview(self):
        """Открыть полный предпросмотр"""
        from doc_prew import DocumentPreviewDialog
        full_dialog = DocumentPreviewDialog(self.document_handler, self.filename, self)
        self.accept()  # Закрываем быстрый просмотр
        full_dialog.exec_()