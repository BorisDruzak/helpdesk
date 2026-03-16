"""
🔍 ПРОСТОЙ ТЕКОВЫЙ ПОИСК (теги внутри + выпадающий список)
===========================================================

Виджет тегового поиска с:
- Тегами ВНУТРИ поля ввода
- Выпадающим списком полей при фокусе
- Разворачиваемым списком (основные/все поля)
- Календарём для выбора дат

Автор: Assistant
Версия: 3.1 (cleaned)
"""
from datetime import datetime, date
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from typing import List, Dict, Optional
from ui_styles import AppStyles, AppColors, AppLayout

from PyQt5 import sip

def validate_and_format_date(date_str: str) -> tuple:
    """
    Проверяет и форматирует дату.
    Возвращает: (успех, отформатированная_дата, сообщение_об_ошибке)
    Поддерживаемые форматы: ДД.ММ.ГГГГ, ГГГГ-ММ-ДД, ДД/ММ/ГГГГ
    """
    date_str = date_str.strip()
    
    if not date_str:
        return (False, "", "Дата не может быть пустой")
    
    formats = ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            # Возвращаем в стандартном формате ГГГГ-ММ-ДД для SQL
            return (True, dt.strftime("%Y-%m-%d"), "")
        except ValueError:
            continue
    
    return (False, "", "Неверный формат даты. Используйте ДД.ММ.ГГГГ")
class SearchableValueSelector(QWidget):
    """
    Виджет выбора значения из справочника с поиском
    
    Особенности:
    - Встроенный поиск по мере ввода
    - Стилизация согласно ui_styles.py
    - Удобная навигация клавиатурой
    - Подсветка найденных элементов
    """
    value_selected = pyqtSignal(str, str)  # (display_value, actual_value)
    
    def __init__(self, field_name: str, db_field: str, values: List[Dict], parent=None):
        super().__init__(parent)
        self.field_name = field_name
        self.db_field = db_field
        self.all_values = values  # Храним все значения
        self.filtered_values = values.copy()  # Отфильтрованные значения
        #Флаги состояния
        self.was_cancelled = False  # Явная отмена через кнопку
        self.was_selected = False   # Явный выбор значения
        self.setup_ui()
        self.populate_list()
        
        # Автофокус на поиске
        QTimer.singleShot(50, self.search_input.setFocus)
    
    def setup_ui(self):
        """Создание UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # === ЗАГОЛОВОК ===
        header = QLabel(f"🔍 Выберите: {self.field_name}")
        header.setStyleSheet(f"""
            QLabel {{
                font-size: 11pt;
                font-weight: bold;
                color: {AppColors.PRIMARY_DARK};
                padding: 8px;
                background: {AppColors.PRIMARY_LIGHT};
                border-radius: 6px;
            }}
        """)
        
        # === ПОЛЕ ПОИСКА ===
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(f"🔎 Поиск {self.field_name.lower()}...")
        self.search_input.setStyleSheet(AppStyles.line_e())
        self.search_input.textChanged.connect(self.filter_list)
        self.search_input.returnPressed.connect(self.select_first_item)
        
        # === СПИСОК ЗНАЧЕНИЙ ===
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(AppStyles.list_widget())
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.list_widget.setMinimumHeight(300)
        self.list_widget.setMaximumHeight(400)
        
        # === КНОПКИ ===
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        
        self.select_btn = QPushButton("✓ Выбрать")
        self.select_btn.setStyleSheet(AppStyles.button_success())
        self.select_btn.clicked.connect(self.on_select_clicked)
        
        self.cancel_btn = QPushButton("✕ Отмена")
        self.cancel_btn.setStyleSheet(AppStyles.button_danger())
        self.cancel_btn.clicked.connect(self.on_cancel_clicked)
        
        buttons_layout.addWidget(self.select_btn)
        buttons_layout.addWidget(self.cancel_btn)
        
        # === СЧЕТЧИК ===
        self.count_label = QLabel()
        self.count_label.setStyleSheet(f"""
            QLabel {{
                color: {AppColors.TEXT_SECONDARY};
                font-size: 9pt;
                padding: 4px;
            }}
        """)
        self.update_count_label()
        
        # === СБОРКА ===
        layout.addWidget(header)
        layout.addWidget(self.search_input)
        layout.addWidget(self.list_widget)
        layout.addWidget(self.count_label)
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
        
        # Стиль виджета
        self.setStyleSheet(f"""
            SearchableValueSelector {{
                background: white;
                border: 2px solid {AppColors.PRIMARY};
                border-radius: 8px;
            }}
        """)
        
        # Размеры
        self.setMinimumWidth(400)
        self.setMinimumHeight(450)
        self.setMaximumWidth(600)
        self.setMaximumHeight(550)
    
    def populate_list(self):
        """Заполнить список значениями"""
        self.list_widget.clear()
        
        for item in self.filtered_values:
            display_text = item.get('name', '')
            list_item = QListWidgetItem(display_text)
            list_item.setData(Qt.UserRole, item.get('id'))  # Сохраняем ID
            self.list_widget.addItem(list_item)
        
        # Автовыбор первого элемента
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
        
        self.update_count_label()
    
    def filter_list(self, search_text: str):
        """Фильтрация списка по тексту"""
        search_text = search_text.lower().strip()
        
        if not search_text:
            # Если поиск пустой - показываем всё
            self.filtered_values = self.all_values.copy()
        else:
            # Фильтруем по вхождению подстроки
            self.filtered_values = [
                item for item in self.all_values
                if search_text in item.get('name', '').lower()
            ]
        
        self.populate_list()
    
    def update_count_label(self):
        """Обновить счетчик найденных элементов"""
        total = len(self.all_values)
        filtered = len(self.filtered_values)
        
        if filtered == total:
            self.count_label.setText(f"📊 Всего: {total}")
        else:
            self.count_label.setText(f"📊 Найдено: {filtered} из {total}")
    
    def select_first_item(self):
        """Выбрать первый элемент списка (при Enter в поиске)"""
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
            self.on_select_clicked()
    
    def on_item_double_clicked(self, item: QListWidgetItem):
        """Обработчик двойного клика по элементу"""
        self.was_selected = True
        display_value = item.text()
        actual_value = item.data(Qt.UserRole)
        self.value_selected.emit(display_value, str(actual_value))
    
    def on_select_clicked(self):
        """Обработчик кнопки Выбрать"""
        current_item = self.list_widget.currentItem()
        
        if not current_item:
            QMessageBox.warning(
                self,
                "⚠️ Не выбрано",
                "Выберите элемент из списка"
            )
            return
        self.was_selected = True
        display_value = current_item.text()
        actual_value = current_item.data(Qt.UserRole)
        self.value_selected.emit(display_value, str(actual_value))
    
    def on_cancel_clicked(self):
        """Обработчик кнопки Отмена"""
        # ✅ ИСПРАВЛЕНО: Сигнализируем родителю о закрытии
        self.was_cancelled = True
        parent = self.parent()
        if parent and hasattr(parent, '_cancel_tag_creation'):
            # Обнуляем ссылку в родителе ПЕРЕД удалением
            if hasattr(parent, 'value_selector'):
                parent.value_selector = None
        
        # Закрываем виджет без выбора
        self.close()
        self.deleteLater()
    
    def keyPressEvent(self, event):
        """Обработка клавиатуры"""
        # ESC - отмена (как кнопка "Отмена")
        if event.key() == Qt.Key_Escape:
            # ✅ ИЗМЕНЕНО: Помечаем как явную отмену
            self.was_cancelled = True
            self.on_cancel_clicked()
        
        # Enter - выбрать текущий элемент (если фокус на списке)
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.list_widget.hasFocus():
                self.on_select_clicked()
        
        # Стрелки - навигация по списку
        elif event.key() in (Qt.Key_Down, Qt.Key_Up):
            self.list_widget.setFocus()
        
        super().keyPressEvent(event)
    def closeEvent(self, event):
        """
        Обработка закрытия окна
        
        Отличаем явную отмену от потери фокуса:
        - Если была явная отмена (кнопка) -> уведомляем родителя
        - Если просто потеря фокуса -> ничего не делаем (состояние сохранится)
        """
        # Если была явная отмена - уведомляем родителя
        if self.was_cancelled:
            parent = self.parent()
            if parent and hasattr(parent, '_on_selector_cancelled'):
                parent._on_selector_cancelled()
        
        super().closeEvent(event)
class ValueSelectorComboBox(QComboBox):
    """
    Выпадающий список для выбора значения из справочника
    """
    value_selected = pyqtSignal(str, str)  # (display_value, actual_value)
    
    def __init__(self, field_name: str, db_field: str, values: List[Dict], parent=None):
        super().__init__(parent)
        self.field_name = field_name
        self.db_field = db_field
        
        # Настройка стиля
        self.setStyleSheet(f"""
            FieldSelectorPopup {{
                background: white;
                border: 2px solid {AppColors.GRAY_300};
                border-radius: 8px;
            }}
        """)
        
        # Добавляем значения
        self.addItem("-- Выберите значение --", None)
        
        for item in values:
            display_text = item.get('name', '')
            item_id = item.get('id')
            self.addItem(display_text, item_id)
        
        # Подключаем сигнал
        self.currentIndexChanged.connect(self._on_selection_changed)
        
        # Автоматически открываем список
        QTimer.singleShot(50, self.showPopup)
    
    def _on_selection_changed(self, index):
        """Обработка выбора значения"""
        if index > 0:  # Пропускаем placeholder
            display_text = self.currentText()
            actual_value = self.currentData()
            self.value_selected.emit(display_text, str(actual_value))

class DateInputFilter(QObject):
    """Фильтр для QLineEdit: только цифры, авто-точки и Enter"""
    
    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            key = event.key()
            
            # ✅ РАЗРЕШАЕМ Enter и Return
            if key in (Qt.Key_Return, Qt.Key_Enter):
                return False  # Пусть QLineEdit обработает
            
            # Разрешаем навигацию и удаление
            if key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Home, 
                      Qt.Key_End, Qt.Key_Backspace, Qt.Key_Delete):
                return False
            
            # Разрешаем только цифры
            if key >= Qt.Key_0 and key <= Qt.Key_9:
                current_text = obj.text()
                
                # Ограничиваем длину (10 символов = 8 цифр + 2 точки)
                if len(current_text) >= 10:
                    return True  # Блокируем
                
                # Авто-вставка точки после 2 и 5 цифр
                if len(current_text) == 2 or len(current_text) == 5:
                    obj.setText(current_text + '.' + chr(event.key()))
                    return True  # Обработали сами
                
                return False  # Стандартная обработка
            
            # Блокируем всё остальное
            return True
        
        return False

class InlineSearchTag(QWidget):
    """Чип тега для отображения внутри поля ввода"""
    
    removed = pyqtSignal(object)
    clicked = pyqtSignal(object)
    
    def __init__(self, field_name: str, value: str, parent=None):
        super().__init__(parent)
        self.field_name = field_name
        self.value = value
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(6, 3, 6, 3)  # Немного увеличили для лучшего вида
        layout.setSpacing(4)
        
        # Текст тега
        self.label = QLabel(f"{self.field_name}: {self.value}")
        self.label.setStyleSheet(f"""
            QLabel {{
                color: {AppColors.PRIMARY_DARK};
                font-size: 9pt;
                font-weight: 600;
                padding: 0px;
                margin: 0px;
                background: transparent;
            }}
        """)
        
        # Кнопка закрытия
        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(16, 16)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {AppColors.GRAY_600};
                font-size: 12pt;
                font-weight: bold;
                padding: 0px;
            }}
            QPushButton:hover {{
                background: {AppColors.DANGER_LIGHT};
                color: {AppColors.DANGER};
                border-radius: 8px;
            }}
        """)
        self.close_btn.clicked.connect(lambda: self.removed.emit(self))
        
        layout.addWidget(self.label)
        layout.addWidget(self.close_btn)
        self.setLayout(layout)
        
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(24)  # Немного увеличили высоту
        
        # Основной стиль тега
        self.setStyleSheet(f"""
            InlineSearchTag {{
                background: {AppColors.PRIMARY_LIGHT};
                border: 2px solid {AppColors.PRIMARY};
                border-radius: 8px;
            }}
            InlineSearchTag:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.PRIMARY_LIGHT}, stop:1 #D0E8F5);
                border-color: {AppColors.PRIMARY_DARK};
            }}
        """)
    
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        
        if event.button() != Qt.LeftButton:
            return
        
        if self.close_btn.underMouse():
            return
        
        self.clicked.emit(self)

class FieldSelectorPopup(QFrame):
    """Выпадающий список полей с ВЕРТИКАЛЬНЫМ разворачиванием"""
    
    field_selected = pyqtSignal(str, str)
    date_selected = pyqtSignal(str, str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.expanded = False
        self.buttons = []
        self.visible_buttons = []
        self.selected_index = -1
        self.setup_ui()
        self.hide()
        
        self.setStyleSheet("""
            FieldSelectorPopup {
                background: white;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
            }
        """)
    
    def setup_ui(self):
        """Создание UI"""
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(4)
        
        # Основные поля
        self.reg_number_btn = self.create_field_button("📋 Рег.номер", "reg_number")
        self.buttons.append(self.reg_number_btn)
        self.main_layout.addWidget(self.reg_number_btn)
        
        self.date_from_btn = self.create_field_button("📅 От", "reg_date_from", True)
        self.buttons.append(self.date_from_btn)
        self.main_layout.addWidget(self.date_from_btn)
        
        self.date_to_btn = self.create_field_button("📅 До", "reg_date_to", True)
        self.buttons.append(self.date_to_btn)
        self.main_layout.addWidget(self.date_to_btn)
        
        self.date_exact_btn = self.create_field_button("📆 Выбрать дату", "reg_date_exact", True)
        self.buttons.append(self.date_exact_btn)
        self.main_layout.addWidget(self.date_exact_btn)
        
        self.title_btn = self.create_field_button("📝 Заголовок", "title")
        self.buttons.append(self.title_btn)
        self.main_layout.addWidget(self.title_btn)
        
        # Дополнительные поля
        self.additional_container = QWidget()
        self.additional_layout = QVBoxLayout(self.additional_container)
        self.additional_layout.setContentsMargins(0, 0, 0, 0)
        self.additional_layout.setSpacing(4)
        
        self.status_btn = self.create_field_button("🔖 Статус", "status")
        self.buttons.append(self.status_btn)
        self.additional_layout.addWidget(self.status_btn)
        
        self.type_btn = self.create_field_button("📄 Тип", "type")
        self.buttons.append(self.type_btn)
        self.additional_layout.addWidget(self.type_btn)
        
        self.executor_btn = self.create_field_button("👤 Исполнитель", "executor")
        self.buttons.append(self.executor_btn)
        self.additional_layout.addWidget(self.executor_btn)
        
        self.theme_btn = self.create_field_button("🏷️ Тема", "theme")
        self.buttons.append(self.theme_btn)
        self.additional_layout.addWidget(self.theme_btn)
        
        self.number_btn = self.create_field_button("🔢 Номер", "number")
        self.buttons.append(self.number_btn)
        self.additional_layout.addWidget(self.number_btn)
        
        self.additional_container.setVisible(False)
        self.main_layout.addWidget(self.additional_container)
        
        # Кнопка разворачивания
        self.expand_btn = QPushButton("⋯ Показать все поля")
        self.expand_btn.setStyleSheet(AppStyles.button_success(height=10,font_size=20, hover_light="#B4B4B4C0", hover_dark="#B4B0B0FF", bg_color="#FFFFFFFF", text_color="dark"))
        self.expand_btn.setFixedHeight(28)
        self.expand_btn.clicked.connect(self.toggle_expansion)
        self.main_layout.addWidget(self.expand_btn)
        
        self.setLayout(self.main_layout)
        self.setMinimumWidth(250)
    
    def create_field_button(self, label: str, db_field: str, is_date: bool = False) -> QPushButton:
        """Создать кнопку выбора поля"""
        btn = QPushButton(label)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(36)  # Немного увеличили для лучшего вида
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # Используем стили из ui_styles
        btn.setStyleSheet(f"""
            QPushButton {{
                background: white;
                border: 1px solid {AppColors.GRAY_300};
                border-radius: 6px;
                padding: 8px 12px;
                text-align: left;
                color: {AppColors.TEXT_PRIMARY};
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10pt;
                font-weight: 500;
            }}
            
            QPushButton:hover {{
                background: {AppColors.PRIMARY_LIGHT};
                border-color: {AppColors.PRIMARY};
                color: {AppColors.PRIMARY_DARK};
            }}
            
            QPushButton[selected="true"] {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.PRIMARY}, stop:1 {AppColors.PRIMARY_DARK});
                border-color: {AppColors.PRIMARY_DARK};
                color: white;
                font-weight: bold;
            }}
        """)
        
        btn.clicked.connect(lambda: self.on_field_clicked(label, db_field))
        
        return btn
    
    def navigate_down(self):
        """Переместить выделение вниз"""
        if not self.visible_buttons:
            return
        
        if len(self.visible_buttons) != len([btn for btn in self.buttons if btn.isVisible()]):
            self.update_visible_buttons()
        
        if self.selected_index >= 0:
            old_btn = self.visible_buttons[self.selected_index]
            self.set_button_normal(old_btn)
        
        self.selected_index = (self.selected_index + 1) % len(self.visible_buttons)
        new_btn = self.visible_buttons[self.selected_index]
        self.set_button_selected(new_btn)

    def navigate_up(self):
        """Переместить выделение вверх"""
        if not self.visible_buttons:
            return
        
        if len(self.visible_buttons) != len([btn for btn in self.buttons if btn.isVisible()]):
            self.update_visible_buttons()
        
        if self.selected_index >= 0:
            old_btn = self.visible_buttons[self.selected_index]
            self.set_button_normal(old_btn)
        
        self.selected_index = (self.selected_index - 1) % len(self.visible_buttons)
        new_btn = self.visible_buttons[self.selected_index]
        self.set_button_selected(new_btn)
    
    def select_current(self):
        """Выбрать текущую выделенную кнопку"""
        if self.selected_index >= 0 and self.visible_buttons:
            self.visible_buttons[self.selected_index].click()
    
    def set_button_normal(self, btn: QPushButton):
        """Убрать выделение с кнопки"""
        btn.setProperty("selected", False)
        btn.setStyleSheet(btn.styleSheet())  # Принудительно обновляем стиль
        btn.update()

    def set_button_selected(self, btn: QPushButton):
        """Выделить кнопку"""
        btn.setProperty("selected", True)
        btn.setStyleSheet(btn.styleSheet())  # Принудительно обновляем стиль
        btn.update()
    
    def update_visible_buttons(self):
        """Обновить список видимых кнопок и сбросить выделение"""
        self.visible_buttons = [btn for btn in self.buttons if btn.isVisible()]
        self.selected_index = -1
        
        for btn in self.buttons:
            self.set_button_normal(btn)
    
    def filter_fields(self, text: str):
        """✅ ИСПРАВЛЕНО: Убран дублированный код"""
        text = text.lower().strip()
        
        # ЕСТЬ ТЕКСТ: скрываем кнопку, показываем ВСЕ поля для поиска
        if text:
            self.expand_btn.setVisible(False)
            self.additional_container.setVisible(True)
            
            # Сначала показать ВСЕ кнопки
            all_buttons = [self.reg_number_btn, self.date_from_btn, self.date_to_btn, 
                        self.date_exact_btn, self.title_btn, self.status_btn, 
                        self.type_btn, self.executor_btn, self.theme_btn, self.number_btn]
            for btn in all_buttons:
                btn.setVisible(True)
            
            # Затем скрыть ненайденные
            self.reg_number_btn.setVisible('рег.номер'.startswith(text) or 'рег' in text or 'номер' in text)
            self.date_from_btn.setVisible('от'.startswith(text) or text in 'от')
            self.date_to_btn.setVisible('до'.startswith(text) or text in 'до')
            self.date_exact_btn.setVisible('выбрать дату'.startswith(text) or 'дата' in text or 'выб' in text)
            self.title_btn.setVisible('заголовок'.startswith(text) or 'заг' in text or 'назв' in text)
            self.status_btn.setVisible('статус'.startswith(text) or 'стат' in text)
            self.type_btn.setVisible('тип'.startswith(text) or text in 'тип')
            self.executor_btn.setVisible('исполнитель'.startswith(text) or 'исп' in text)
            self.theme_btn.setVisible('тема'.startswith(text) or text in 'те')
            self.number_btn.setVisible('номер'.startswith(text) or 'ном' in text)
        else:
            # ТЕКСТА НЕТ: показываем кнопку и возвращаем исходное состояние
            self.expand_btn.setVisible(True)
            
            # Показываем основные поля (всегда видимы)
            for btn in [self.reg_number_btn, self.date_from_btn, self.date_to_btn, 
                        self.date_exact_btn, self.title_btn]:
                btn.setVisible(True)
            
            # Показываем контейнер только если развернут
            self.additional_container.setVisible(self.expanded)
            
            # Все кнопки в контейнере должны быть видны, если контейнер виден
            for btn in [self.status_btn, self.type_btn, self.executor_btn, self.theme_btn, self.number_btn]:
                btn.setVisible(self.expanded)
        
        # ✅ ИСПРАВЛЕНО: Убран тройной дубликат кода выделения
        self.update_visible_buttons()
        if len(self.visible_buttons) == 1:
            self.selected_index = 0
            self.set_button_selected(self.visible_buttons[0])
        
        QTimer.singleShot(0, self.adjustSize)

    def on_field_clicked(self, field_name: str, db_field: str):
        clean_name = field_name.split(maxsplit=1)[1] if ' ' in field_name else field_name
        self.field_selected.emit(clean_name, db_field)
        self.hide()
    
    def toggle_expansion(self):
        """Переключить разворачивание"""
        self.expanded = not self.expanded
        
        self.additional_container.setVisible(self.expanded)
        self.expand_btn.setText("⋯ Скрыть дополнительные поля" if self.expanded else "⋯ Показать все поля")
        
        for btn in [self.status_btn, self.type_btn, self.executor_btn, self.theme_btn, self.number_btn]:
            btn.setVisible(self.expanded)
        
        self.update_visible_buttons()
        QTimer.singleShot(0, self.adjustSize)
    
    def show_at_widget(self, widget: QWidget):
        main_window = widget.window()
        widget_pos = widget.mapTo(main_window, QPoint(0, widget.height()))
        
        self.move(widget_pos)
        self.setFixedWidth(widget.width())
        self.raise_()
        self.show()
        
        search_text = widget.text() if hasattr(widget, 'text') else ""
        self.expand_btn.setVisible(not search_text.strip())
        self.update_visible_buttons()
        
        QTimer.singleShot(0, self.adjustSize)


class TagInputField(QWidget):
    """Кастомное поле ввода с тегами и inline-календарем"""
    
    returnPressed = pyqtSignal()
    textChanged = pyqtSignal(str)
    focusReceived = pyqtSignal()
    date_selected = pyqtSignal(str)
    tag_removed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tags = []
        self._date_error = False
        self._is_date_mode = False
        self._popup_calendar = None
        self._date_filter = DateInputFilter()
        
        self.setup_ui()
    
    def setup_ui(self):
        """Создание UI"""
        self.main_layout = QHBoxLayout()
        self.main_layout.setContentsMargins(8, 6, 8, 6)
        self.main_layout.setSpacing(4)
        self.main_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        # Контейнер для тегов
        self.tags_container = QWidget()
        self.tags_container.setFixedHeight(24)
        self.tags_layout = QHBoxLayout(self.tags_container)
        self.tags_layout.setContentsMargins(0, 0, 0, 0)
        self.tags_layout.setSpacing(4)

        # ✅ КРИТИЧНО: Скрываем контейнер когда он пуст
        self.tags_container.setVisible(False)

        # ✅ НОВОЕ: Правильный sizePolicy для контейнера
        self.tags_container.setSizePolicy(
            QSizePolicy.Preferred,  # Занимает столько места сколько нужно
            QSizePolicy.Fixed       # Фиксированная высота
        )
        
        # Поле ввода
        self.input_field = QLineEdit()
        self.input_field.setFrame(False)
        self.input_field.setStyleSheet(AppStyles.input_field())
        self.input_field.setMinimumWidth(100)
        self.input_field.setPlaceholderText("Выберите поле из списка...")
        self.input_field.setSizePolicy(
        QSizePolicy.Expanding,  # Расширяется по горизонтали
        QSizePolicy.Preferred   # Предпочтительный размер по вертикали
    )
        # Кнопка календаря
        self.calendar_btn = QPushButton("📅")
        self.calendar_btn.setFixedSize(20, 20)
        self.calendar_btn.setCursor(Qt.PointingHandCursor)
        self.calendar_btn.clicked.connect(self._toggle_popup_calendar)
        self.calendar_btn.hide()
        
        # Подключаем сигналы
        self.input_field.returnPressed.connect(self.returnPressed)
        self.input_field.textChanged.connect(self._on_text_changed)
        self.input_field.mousePressEvent = self.on_input_field_clicked
        
        # Добавляем в layout
        self.main_layout.addWidget(self.tags_container)
        self.main_layout.addWidget(self.input_field, 1)
        self.main_layout.addWidget(self.calendar_btn)
        
        self.setLayout(self.main_layout)
        
        # Стили поля
        self.setStyleSheet(f"""
            TagInputField {{
                background: white;
                border: 2px solid {AppColors.GRAY_300};
                border-radius: 6px;
                padding: 4px;
            }}
            TagInputField:hover {{
                border-color: {AppColors.GRAY_400};
                background: {AppColors.GRAY_50};
            }}
            TagInputField:focus-within {{
                border-color: {AppColors.PRIMARY};
                border-width: 2px;
                background: white;
            }}
            
            QLineEdit {{
                background: transparent;
                border: none;
                font-size: 10pt;
                padding: 0px;
                margin: 0px;
                color: {AppColors.TEXT_PRIMARY};
            }}
        """)
        self.setMinimumHeight(44)  # Немного увеличили
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    
    def _toggle_popup_calendar(self):
        """Показать/скрыть popup календарь"""
        if not self._is_date_mode:
            return
        
        if self._popup_calendar is None:
            self._create_popup_calendar()
        
        if self._popup_calendar.isVisible():
            self._popup_calendar.hide()
            return
        
        global_pos = self.mapToGlobal(self.rect().bottomLeft())
        self._popup_calendar.move(global_pos)
        self._popup_calendar.show()
        self._popup_calendar.raise_()
        self._popup_calendar.setFocus()
        
        self._sync_calendar_with_text()
    
    def _create_popup_calendar(self):
        """✅ ИСПРАВЛЕНО: Убран дубликат метода"""
        if self._popup_calendar is not None:
            return
        
        self._popup_calendar = QCalendarWidget()
        self._popup_calendar.setGridVisible(True)
        self._popup_calendar.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self._popup_calendar.setFixedSize(530, 280)
        
        main_window = self.window()
        if main_window:
            self._popup_calendar.setParent(main_window)
        
        self._popup_calendar.clicked.connect(self._on_popup_calendar_date_selected)
        self._popup_calendar.activated.connect(self._on_popup_calendar_date_selected)
        
        self._popup_calendar.setStyleSheet("""
            QCalendarWidget {
                background: white;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
            }
            QCalendarWidget QWidget {
                alternate-background-color: #f8f9fa;
            }
            QCalendarWidget QAbstractItemView:enabled {
                selection-background-color: #3498db;
                selection-color: white;
            }
        """)
    
    def _sync_calendar_with_text(self):
        """Синхронизировать календарь с текстом в поле"""
        text = self.input_field.text().strip()
        if not text:
            return
        
        is_valid, formatted_date, _ = validate_and_format_date(text)
        if is_valid:
            try:
                dt = datetime.strptime(formatted_date, "%Y-%m-%d")
                self._popup_calendar.blockSignals(True)
                self._popup_calendar.setSelectedDate(QDate(dt.year, dt.month, dt.day))
                self._popup_calendar.blockSignals(False)
            except:
                pass
    
    def _on_popup_calendar_date_selected(self, date: QDate):
        """Выбор даты в popup календаре"""
        display_date = date.toString("dd.MM.yyyy")
        self.input_field.setText(display_date)
        self._popup_calendar.hide()
        
        sql_date = date.toString("yyyy-MM-dd")
        self.date_selected.emit(sql_date)
    
    def _on_text_changed(self, text):
        """Обработка текста в реальном времени"""
        self.textChanged.emit(text)
        
        if self._is_date_mode and text.strip():
            self._validate_date_input(text)
        elif self._is_date_mode and not text.strip():
            self._clear_date_error()
    
    def set_date_mode(self, enabled: bool):
        """Включить/выключить режим ввода даты"""
        self._is_date_mode = enabled
        
        if enabled:
            self.calendar_btn.show()
            self.input_field.setPlaceholderText("ДД.ММ.ГГГГ")
            self.input_field.installEventFilter(self._date_filter)
            self.input_field.setMaxLength(10)
        else:
            self.calendar_btn.hide()
            if self._popup_calendar:
                self._popup_calendar.hide()
            self.input_field.setPlaceholderText("Выберите поле из списка...")
            self.input_field.removeEventFilter(self._date_filter)
            self.input_field.setMaxLength(32767)
            self._clear_date_error()
    
    def _validate_date_input(self, date_str: str):
        """Валидация даты в реальном времени"""
        if len(date_str) == 10:
            is_valid, formatted_date, error = validate_and_format_date(date_str)
            
            if is_valid:
                self._clear_date_error()
                if self._popup_calendar:
                    try:
                        dt = datetime.strptime(formatted_date, "%Y-%m-%d")
                        self._popup_calendar.blockSignals(True)
                        self._popup_calendar.setSelectedDate(QDate(dt.year, dt.month, dt.day))
                        self._popup_calendar.blockSignals(False)
                    except:
                        pass
            else:
                self._show_date_error(error)
        else:
            self._clear_date_error()
    
    def _show_date_error(self, error_msg: str):
        """Показать ошибку"""
        self._date_error = True
        self.setStyleSheet(self._get_error_stylesheet())
        self.input_field.setToolTip(error_msg)

    def _clear_date_error(self):
        """Скрыть ошибку"""
        if self._date_error:
            self._date_error = False
            self.setStyleSheet(self._get_normal_stylesheet())
            self.input_field.setToolTip("")

    def _get_normal_stylesheet(self):
        return f"""
            TagInputField {{
                background: white;
                border: 2px solid {AppColors.GRAY_300};
                border-radius: 6px;
                padding: 4px;
            }}
            TagInputField:hover {{
                border-color: {AppColors.GRAY_400};
                background: {AppColors.GRAY_50};
            }}
            TagInputField:focus-within {{
                border-color: {AppColors.PRIMARY};
                border-width: 2px;
                background: white;
            }}
            QLineEdit {{
                background: transparent;
                border: none;
                font-size: 10pt;
                padding: 0px;
                margin: 0px;
                color: {AppColors.TEXT_PRIMARY};
            }}
        """

    def _get_error_stylesheet(self):
        return f"""
            TagInputField {{
                background: {AppColors.DANGER_LIGHT};
                border: 2px solid {AppColors.DANGER};
                border-radius: 6px;
                padding: 4px;
            }}
            TagInputField:hover {{
                border-color: {AppColors.DANGER_DARK};
                background: #fff0f0;
            }}
            TagInputField:focus-within {{
                border-color: {AppColors.DANGER};
                border-width: 2px;
                background: white;
            }}
            QLineEdit {{
                background: transparent;
                border: none;
                font-size: 10pt;
                padding: 0px;
                margin: 0px;
                color: {AppColors.TEXT_PRIMARY};
            }}
        """
    
    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.input_field.setFocus()
        self.focusReceived.emit()
        if not self.input_field.text().strip():
            self.focusReceived.emit()
    
    def on_input_field_clicked(self, event):
        """Открыть popup при клике на поле ввода"""
        if event.button() == Qt.LeftButton:
            self.focusReceived.emit()  
        
        QLineEdit.mousePressEvent(self.input_field, event)
    
    def add_tag(self, field_name: str, db_field: str, value: str):
        """Добавить тег (отображение = значение)"""
        self.add_tag_with_display(field_name, db_field, value, value)
    
    def add_tag_with_display(self, field_name: str, db_field: str, value: str, display_value: str):
        """Добавить тег с отдельным значением для отображения"""
        tag_widget = InlineSearchTag(field_name, display_value)
        tag_widget.removed.connect(self.remove_tag)
        
        self.tags.append((field_name, db_field, value, tag_widget))
        self.tags_layout.addWidget(tag_widget)
        
        # ✅ КРИТИЧНО: Показываем контейнер когда добавляем тег
        self.tags_container.setVisible(True)
        print(f"✅ Контейнер тегов показан (добавлен тег '{field_name}: {display_value}')")
        
        self.input_field.clear()
        self.tags_container.adjustSize()
        self.adjustSize()
    
    def remove_tag(self, tag_widget: InlineSearchTag):
        """Удалить тег"""
        for i, (field_name, db_field, value, widget) in enumerate(self.tags):
            if widget == tag_widget:
                self.tags.pop(i)
                widget.deleteLater()
                
                # ✅ КРИТИЧНО: Скрываем контейнер когда тегов не осталось
                if len(self.tags) == 0:
                    self.tags_container.setVisible(False)
                    print("✅ Контейнер тегов скрыт (тегов больше нет)")
                
                self.tags_container.adjustSize()
                self.adjustSize()
                self.tag_removed.emit()
                break
    
    def edit_tag(self, tag_widget: InlineSearchTag):
        """✅ ДОБАВЛЕН: Редактирование тега"""
        for i, (field_name, db_field, value, widget) in enumerate(self.tags):
            if widget == tag_widget:
                # Показываем значение в поле ввода для редактирования
                if 'date' in db_field:
                    # Для дат конвертируем в DD.MM.YYYY
                    try:
                        dt = datetime.strptime(value, "%Y-%m-%d")
                        display_value = dt.strftime("%d.%m.%Y")
                    except:
                        display_value = value
                    self.input_field.setText(display_value)
                else:
                    self.input_field.setText(value)
                
                # Удаляем тег из списка
                self.tags.pop(i)
                widget.deleteLater()
                self.tags_container.adjustSize()
                self.adjustSize()
                break
    
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            QTimer.singleShot(50, self.focusReceived.emit)
    
    def clear_tags(self):
        """Очистить все теги"""
        for _, _, _, widget in self.tags:
            widget.deleteLater()
        self.tags.clear()
        
        # ✅ КРИТИЧНО: Скрываем контейнер когда очищаем все теги
        self.tags_container.setVisible(False)
        print("✅ Контейнер тегов скрыт (все теги удалены)")
        
        self.tags_container.adjustSize()
        self.adjustSize()
    
    def get_tags(self) -> List[tuple]:
        """Получить список тегов"""
        return [(fn, df, val) for fn, df, val, _ in self.tags]
    
    def text(self) -> str:
        return self.input_field.text()
    
    def clear(self):
        self.input_field.clear()
    
    def setPlaceholderText(self, text: str):
        self.input_field.setPlaceholderText(text)
    
    def setFocus(self):
        self.input_field.setFocus()


class SimpleTagSearchWidget(QWidget):
    """Простой виджет тегового поиска с выпадающим списком"""
    
    search_requested = pyqtSignal(dict)
    tags_cleared = pyqtSignal()
    
    FIELD_MAPPING = {
        'Рег.номер': 'reg_number',
        'От': 'reg_date_from',
        'До': 'reg_date_to',
        'Выбрать дату': 'reg_date_exact',
        'Заголовок': 'title',
        'Статус': 'status',
        'Тип': 'type',
        'Исполнитель': 'executor',
        'Тема': 'theme',
        'Номер': 'number',
    }
    
    def __init__(self, db_manager=None, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._reference_cache = {}
        self.REFERENCE_FIELDS = {
            'Исполнитель': {
                'db_field': 'executor',
                'method': 'get_executors',
                'params': {'active_only': True}
            },
            'Тема': {
                'db_field': 'theme',
                'method': 'get_themes',
                'params': {'active_only': True}
            },
            'Тип': {
                'db_field': 'type',
                'table': 'ref_document_types'
            },
            'Статус': {
                'db_field': 'status',
                'table': 'ref_status'
            }
        }

        # Виджет для выбора значения из справочника
        self.value_selector = None
        self.current_field = None
        self.current_db_field = None
        self.field_popup = FieldSelectorPopup()
        self._editing_tag = None
        self._popup_visible = False
        self.setup_ui()
    def _safe_close_value_selector(self):
        """
        Безопасное закрытие виджета выбора значений
        
        Проверяет существование объекта перед удалением
        и обнуляет ссылку в любом случае
        """
        if not self.value_selector:
            return
        
        try:
            if not sip.isdeleted(self.value_selector):
                if self.value_selector.isVisible():
                    self.value_selector.close()
                self.value_selector.deleteLater()
        except (RuntimeError, AttributeError) as e:
            print(f"⚠️ Виджет выбора уже удален: {e}")
        finally:
            self.value_selector = None
    def test_referenc(self):
        print(self._reference_cache)
    def setup_ui(self):
        """Создание UI"""
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 12) 
        # ✅ КРИТИЧНО: Устанавливаем минимальную высоту всего виджета
    
        self.setMinimumHeight(80)  # Минимум 80px
        self.setMaximumHeight(120)  # Максимум 120px
        
        # ✅ КРИТИЧНО: Запрещаем сжатие виджета
        self.setSizePolicy(
            QSizePolicy.Expanding,   # По горизонтали расширяется
            QSizePolicy.Fixed        # По вертикали фиксированный размер
        )
        # === КОНТЕЙНЕР ПОИСКА ===
        search_container = QWidget()
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(6)
        search_container.setLayout(search_layout)  # ✅ ИСПРАВЛЕНИЕ
        
        self.field_popup.hide()
        self.field_popup.raise_()
        
        # Кастомное поле ввода с тегами
        self.tag_input = TagInputField()
        self.tag_input.input_field.installEventFilter(self)
        self.field_popup.field_selected.connect(self.on_field_selected)
        self.field_popup.date_selected.connect(self.on_date_selected)
        self.tag_input.date_selected.connect(self._on_inline_date_selected)
        
        # Обработка сигналов
        self.tag_input.returnPressed.connect(self.process_input)
        self.tag_input.focusReceived.connect(self.show_field_selector)
        self.tag_input.input_field.textChanged.connect(self.on_text_changed)
        self.tag_input.tag_removed.connect(self.on_tag_removed)
        
        # Popup как дочерний виджет
        self.field_popup.setParent(self)
        self.field_popup.raise_()
        
        # Динамические кнопки
        self.action_btn = QPushButton("🔍")
        self.action_btn.setFixedSize(36, 36)
        self.action_btn.setCursor(Qt.PointingHandCursor)
        self.action_btn.clicked.connect(self._on_action_btn_clicked)

        self.cancel_btn = QPushButton("×")
        self.cancel_btn.setFixedSize(36, 36)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self._on_cancel_btn_clicked)

        search_layout.addWidget(self.tag_input, 1)
        search_layout.addWidget(self.action_btn)
        search_layout.addWidget(self.cancel_btn)
        
        # === ПОДСКАЗКА ===
        self.hint_label = QLabel("💡 Кликните на поле → выберите фильтр из списка")
        self.hint_label.setStyleSheet(f"""
            QLabel {{
                color: {AppColors.TEXT_SECONDARY};
                font-size: 9pt;
                font-weight: 500;
                padding: 6px 10px;
                background: {AppColors.GRAY_100};
                border-radius: 4px;
                border: 1px solid {AppColors.GRAY_200};
            }}
        """)
        self.hint_label.setWordWrap(True)
        
        # Сборка
        layout.addWidget(search_container)
        
        
        self.setLayout(layout)
        self._update_buttons_state()
    def _set_hint_style_normal(self):
        """Обычный стиль подсказки"""
        self.hint_label.setStyleSheet(f"""
            QLabel {{
                color: {AppColors.TEXT_SECONDARY};
                font-size: 9pt;
                font-weight: 500;
                padding: 6px 10px;
                background: {AppColors.GRAY_100};
                border-radius: 4px;
                border: 1px solid {AppColors.GRAY_200};
            }}
        """)

    def _set_hint_style_interactive(self):
        """Стиль подсказки для интерактивного режима (можно кликнуть)"""
        self.hint_label.setStyleSheet(f"""
            QLabel {{
                color: {AppColors.PRIMARY_DARK};
                font-size: 9pt;
                font-weight: 600;
                padding: 6px 10px;
                background: {AppColors.PRIMARY_LIGHT};
                border-radius: 4px;
                border: 2px solid {AppColors.PRIMARY};
            }}
        """)
    def _update_buttons_state(self):
        """Обновить состояние кнопок в зависимости от режима"""
        if self.current_field is not None:
            # Режим создания тега
            self.action_btn.setText("✓")
            self.action_btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 {AppColors.SUCCESS}, stop:1 {AppColors.SUCCESS_DARK});
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-size: 16pt;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #43A047, stop:1 #2E7D32);
                }}
                QPushButton:pressed {{
                    background: {AppColors.SUCCESS_DARK};
                }}
            """)
            self.action_btn.setToolTip("Добавить тег")
            
            self.cancel_btn.setText("✕")
            self.cancel_btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 {AppColors.DANGER}, stop:1 {AppColors.DANGER_DARK});
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-size: 14pt;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #E53935, stop:1 #C62828);
                }}
                QPushButton:pressed {{
                    background: {AppColors.DANGER_DARK};
                }}
            """)
            self.cancel_btn.setToolTip("Отменить создание тега")
        else:
            # Обычный режим (теги созданы)
            self.action_btn.setText("🔍")
            self.action_btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 {AppColors.PRIMARY}, stop:1 {AppColors.PRIMARY_DARK});
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-size: 14pt;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #1E88E5, stop:1 #1565C0);
                }}
                QPushButton:pressed {{
                    background: {AppColors.PRIMARY_DARK};
                }}
            """)
            self.action_btn.setToolTip("Выполнить поиск")
            
            self.cancel_btn.setText("×")
            self.cancel_btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 {AppColors.DANGER}, stop:1 {AppColors.DANGER_DARK});
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-size: 16pt;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #E53935, stop:1 #C62828);
                }}
                QPushButton:pressed {{
                    background: {AppColors.DANGER_DARK};
                }}
            """)
            self.cancel_btn.setToolTip("Очистить все теги")
    
    def _on_action_btn_clicked(self):
        """
        Обработчик для кнопки Добавить тег / Поиск
        
        Умная логика:
        - Если идет создание тега -> пытаемся добавить тег
        - Если виджет выбора был закрыт (но состояние сохранено) -> открываем снова
        - Иначе -> выполняем поиск
        """
        if self.current_field is not None:
            # Идет создание тега
            
            # ✅ НОВОЕ: Проверяем - может виджет выбора был случайно закрыт?
            field_is_reference = self.current_field in self.REFERENCE_FIELDS
            
            if field_is_reference and not self.value_selector:
                # Виджет выбора был закрыт, но состояние сохранено
                # Открываем его снова!
                print(f"🔄 Переоткрываем виджет выбора для '{self.current_field}'")
                
                values = self._get_reference_values(self.current_field)
                if values:
                    self._show_value_selector(self.current_field, self.current_db_field, values)
                return
            
            # Обычная логика добавления тега
            self.process_input()
        else:
            # Нет активного создания тега - выполняем поиск
            self.perform_search()
    
    def _on_cancel_btn_clicked(self):
        """✅ ДОБАВЛЕН: Обработчик для кнопки Отмена / Очистить все"""
        if self.current_field is not None:
            self._cancel_tag_creation()
        else:
            self.clear_all()
    
    def _cancel_tag_creation(self):
        """
        Полная отмена создания тега - ФИНАЛЬНАЯ ВЕРСИЯ
        """
        print("🚫 Полная отмена создания тега через кнопку ✕")
        
        # 1. Закрываем виджет выбора
        if self.value_selector:
            try:
                if not sip.isdeleted(self.value_selector):
                    self.value_selector.was_cancelled = True
                    self.value_selector.close()
                    self.value_selector.deleteLater()
            except (RuntimeError, AttributeError):
                pass
            finally:
                self.value_selector = None
        
        # 2. ✅ НОВОЕ: Проверяем видимость контейнера тегов
        if hasattr(self.tag_input, 'tags_container'):
            has_tags = len(self.tag_input.tags) > 0
            self.tag_input.tags_container.setVisible(has_tags)
            print(f"📦 Контейнер тегов: {'показан' if has_tags else 'скрыт'} (тегов: {len(self.tag_input.tags)})")
        
        # 3. Восстанавливаем поле ввода
        self.tag_input.input_field.show()
        self.tag_input.input_field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.tag_input.input_field.setMinimumWidth(100)
        
        # 4. Принудительное обновление layout
        self.tag_input.input_field.updateGeometry()
        self.tag_input.updateGeometry()
        
        # ✅ НОВОЕ: Обновляем main_layout явно
        if hasattr(self.tag_input, 'main_layout'):
            self.tag_input.main_layout.invalidate()
            self.tag_input.main_layout.update()
            self.tag_input.main_layout.activate()
        
        QApplication.processEvents()
        
        # 5. Очистка состояния
        self.tag_input.clear()
        self.current_field = None
        self.current_db_field = None
        self._editing_tag = None
        
        # 6. Закрываем календарь
        if self.tag_input._popup_calendar:
            self.tag_input._popup_calendar.hide()
        
        # 7. Восстанавливаем UI
        self.tag_input.setPlaceholderText("Выберите поле из списка...")
        
        if hasattr(self, '_set_hint_style_normal'):
            self._set_hint_style_normal()
        self.hint_label.setText("💡 Кликните на поле → выберите фильтр из списка")
        
        self.tag_input.set_date_mode(False)
        self._update_buttons_state()
        
        # 8. Финальное обновление через event loop
        QTimer.singleShot(10, self._force_layout_update)
        
        print("✅ Создание тега отменено, layout восстановлен")
    def _get_reference_values(self, field_name: str) -> List[Dict]:
        """
        Получить значения из справочника для поля (с кэшированием)
        
        Args:
            field_name: Название поля (Исполнитель, Тема, Тип, Статус)
        
        Returns:
            List[Dict]: Список значений [{'id': ..., 'name': ...}, ...]
        """
        if not self.db_manager:
            return []
        
        if field_name not in self.REFERENCE_FIELDS:
            return []
        
        # ✅ Проверяем кэш
        if field_name in self._reference_cache:
            print(f"📦 Использован кэш для '{field_name}'")
            return self._reference_cache[field_name]
        
        ref_config = self.REFERENCE_FIELDS[field_name]
        
        try:
            values = []
            
            # Для Исполнителя и Темы используем специальные методы
            if 'method' in ref_config:
                method_name = ref_config['method']
                method = getattr(self.db_manager, method_name)
                params = ref_config.get('params', {})
                values = method(**params)
            
            # Для простых справочников используем get_simple_reference
            elif 'table' in ref_config:
                table_name = ref_config['table']
                values = self.db_manager.get_simple_reference(table_name)
            
            # ✅ Сохраняем в кэш
            if values:
                self._reference_cache[field_name] = values
                print(f"💾 Кэш обновлен для '{field_name}' ({len(values)} записей)")
            
            return values
            
        except Exception as e:
            print(f"❌ Ошибка получения значений справочника '{field_name}': {e}")
            import traceback
            traceback.print_exc()
            return []
    def _force_layout_update(self):
        """Принудительное обновление layout виджета поиска"""
        try:
            self.tag_input.adjustSize()
            self.tag_input.updateGeometry()
            
            # Обновляем родительский layout
            if self.layout():
                self.layout().invalidate()
                self.layout().update()
                self.layout().activate()
            
            self.updateGeometry()
            
            print("🔄 Layout принудительно обновлен")
        except Exception as e:
            print(f"⚠️ Ошибка обновления layout: {e}")
    def clear_reference_cache(self):
        """
        Очистить кэш справочников
        
        Вызывается при:
        - Переключении базы данных
        - Обновлении справочников (добавление/удаление/редактирование)
        """
        self._reference_cache.clear()
        print("🗑️ Кэш справочников очищен")
    def _show_value_selector(self, field_name: str, db_field: str, values: List[Dict]):
        """
        Показать виджет выбора значения с поиском
        
        Поддерживает повторное открытие если виджет был случайно закрыт
        """
        # ✅ ИЗМЕНЕНО: Если виджет уже существует и видим - просто активируем
        if self.value_selector:
            try:
                if not sip.isdeleted(self.value_selector):
                    if self.value_selector.isVisible():
                        # Виджет уже открыт - просто активируем его
                        print("♻️ Виджет выбора уже открыт - активируем")
                        self.value_selector.raise_()
                        self.value_selector.activateWindow()
                        self.value_selector.search_input.setFocus()
                        return
                    else:
                        # Виджет существует но скрыт - показываем снова
                        print("♻️ Показываем скрытый виджет выбора")
                        global_pos = self.tag_input.mapToGlobal(self.tag_input.rect().bottomLeft())
                        self.value_selector.move(global_pos)
                        self.value_selector.show()
                        self.value_selector.raise_()
                        self.value_selector.activateWindow()
                        self.value_selector.search_input.setFocus()
                        return
            except RuntimeError:
                pass
            
            # Если дошли сюда - объект поврежден, удаляем
            self.value_selector = None
        
        # Создаем новый виджет
        print(f"🆕 Создаем новый виджет выбора для '{field_name}'")
        
        self.value_selector = SearchableValueSelector(
            field_name, 
            db_field, 
            values, 
            self
        )
        
        # Подключаем обработку выбора значения
        self.value_selector.value_selected.connect(self._on_value_from_selector)
        
        # Позиционируем относительно tag_input
        global_pos = self.tag_input.mapToGlobal(self.tag_input.rect().bottomLeft())
        self.value_selector.move(global_pos)
        
        # Устанавливаем как popup окно
        self.value_selector.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        
        # Показываем
        self.value_selector.show()
        self.value_selector.raise_()
        self.value_selector.activateWindow()
    def populate_list(self):
        """Заполнить список значениями с подсветкой поиска"""
        self.list_widget.clear()
        search_text = self.search_input.text().lower().strip()
        
        for item in self.filtered_values:
            display_text = item.get('name', '')
            list_item = QListWidgetItem()
            
            # ✅ НОВОЕ: Подсветка найденного текста
            if search_text and search_text in display_text.lower():
                # Находим позицию найденного текста
                start_pos = display_text.lower().find(search_text)
                
                # Создаем текст с подсветкой
                before = display_text[:start_pos]
                match = display_text[start_pos:start_pos + len(search_text)]
                after = display_text[start_pos + len(search_text):]
                
                # HTML с подсветкой
                highlighted = f"{before}<b style='background: {AppColors.WARNING_LIGHT}; color: {AppColors.WARNING_DARK};'>{match}</b>{after}"
                list_item.setText(highlighted)
            else:
                list_item.setText(display_text)
            
            list_item.setData(Qt.UserRole, item.get('id'))
            self.list_widget.addItem(list_item)
        
        # Автовыбор первого элемента
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
        
        self.update_count_label()
    def _on_value_from_selector(self, display_value: str, actual_value: str):
        """
        Обработка выбора значения из виджета выбора
        """
        if not self.current_field or not self.current_db_field:
            return
        
        # Создаем тег с выбранным значением
        self.add_tag(
            self.current_field, 
            self.current_db_field, 
            display_value,
            display_value
        )
        self._restore_input_field_size()
        # ✅ ИСПРАВЛЕНО: Безопасное удаление селектора
        if self.value_selector:
            try:
                if not sip.isdeleted(self.value_selector):
                    self.value_selector.close()
                    self.value_selector.deleteLater()
            except (RuntimeError, AttributeError):
                pass
            finally:
                self.value_selector = None
        
        # Сбрасываем состояние
        self.tag_input.clear()
        self.current_field = None
        self.current_db_field = None
        self._editing_tag = None
        
        self.tag_input.setPlaceholderText("Выберите поле из списка...")
        self.hint_label.setText("💡 Кликните на поле → выберите фильтр из списка")
        self.tag_input.set_date_mode(False)
        
        self._update_buttons_state()
    def _on_selector_cancelled(self):
        """
        Обработка ЯВНОЙ отмены выбора значения
        
        Вызывается когда пользователь нажал кнопку "Отмена" или ESC
        Полностью сбрасывает создание тега
        """
        print("🚫 Явная отмена выбора - сбрасываем создание тега")
        
        # Закрываем виджет выбора
        self._safe_close_value_selector()
        
        # ПОЛНЫЙ СБРОС состояния
        self.tag_input.input_field.show()
        self.tag_input.clear()
        self.current_field = None
        self.current_db_field = None
        self._editing_tag = None
        
        if self.tag_input._popup_calendar:
            self.tag_input._popup_calendar.hide()
        
        self.tag_input.setPlaceholderText("Выберите поле из списка...")
        self.hint_label.setText("💡 Кликните на поле → выберите фильтр из списка")
        self.tag_input.set_date_mode(False)
        
        self._update_buttons_state()
    def perform_search(self):
        """✅ ДОБАВЛЕН: Выполнить поиск с текущими тегами"""
        tags = self.tag_input.get_tags()
        
        if not tags:
            QMessageBox.information(self, "Поиск", "Добавьте хотя бы один фильтр для поиска")
            return
        
        search_data = self.build_sql_query(tags)
        self.search_requested.emit(search_data)
        print(f"🔍 Выполняем поиск с {len(tags)} фильтрами")
    
    def clear_all(self):
        """✅ ДОБАВЛЕН: Очистить все теги"""
        self.tag_input.clear_tags()
        self.tag_input.clear()
        
        # ✅ НОВОЕ: Убеждаемся что контейнер тегов скрыт
        if hasattr(self.tag_input, 'tags_container'):
            self.tag_input.tags_container.setVisible(False)
        
        self.current_field = None
        self.current_db_field = None
        self._editing_tag = None
        
        if self.tag_input._popup_calendar:
            self.tag_input._popup_calendar.hide()
        
        self.tag_input.setPlaceholderText("Выберите поле из списка...")
        
        if hasattr(self, '_set_hint_style_normal'):
            self._set_hint_style_normal()
        self.hint_label.setText("💡 Кликните на поле → выберите фильтр из списка")
        
        self.tag_input.set_date_mode(False)
        
        self.tags_cleared.emit()
        self._update_buttons_state()
        
        # ✅ НОВОЕ: Принудительное обновление layout
        QTimer.singleShot(10, self._force_layout_update)
        
        print("🗑️ Все теги очищены, контейнер скрыт")
    
    def _validate_date(self, date_str: str) -> tuple:
        """Валидация даты"""
        return validate_and_format_date(date_str)
    
    def showEvent(self, event):
        """Вызывается когда виджет показывается"""
        super().showEvent(event)
        if self.parent():
            self.parent().installEventFilter(self)
    
    def eventFilter(self, obj, event):
        """Обработка событий клавиатуры и мыши"""
        # 1. Обработка клавиатуры
        if obj == self.tag_input.input_field and event.type() == QEvent.KeyPress:
            key = event.key()
            
            # ESCAPE — отмена редактирования
            if key == Qt.Key_Escape:
                if self.current_field is not None:
                    self._cancel_tag_creation()
                    return True
                
                if self.field_popup.isVisible():
                    self.field_popup.hide()
                    return True
            
            # Обработка клавиатуры для field_popup
            if self.field_popup.isVisible():
                if key == Qt.Key_Down:
                    self.field_popup.navigate_down()
                    return True
                elif key == Qt.Key_Up:
                    self.field_popup.navigate_up()
                    return True
                elif key in (Qt.Key_Return, Qt.Key_Enter):
                    if self.field_popup.selected_index >= 0:
                        self.field_popup.select_current()
                        return True
        
        # 2. Закрытие popup'ов при клике вне
        if obj == self.window() and event.type() == QEvent.MouseButtonPress:
            click_pos = event.pos()
            
            # Проверяем клик вне field_popup
            if self.field_popup.isVisible():
                popup_rect = QRect(self.field_popup.pos(), self.field_popup.size())
                if not popup_rect.contains(click_pos):
                    self.field_popup.hide()
            
            # Проверяем клик вне popup календаря
            if self.tag_input._popup_calendar and self.tag_input._popup_calendar.isVisible():
                calendar_rect = QRect(self.tag_input._popup_calendar.pos(), 
                                    self.tag_input._popup_calendar.size())
                
                button_global_pos = self.tag_input.calendar_btn.mapToGlobal(
                    self.tag_input.calendar_btn.pos()
                )
                button_rect = QRect(button_global_pos, self.tag_input.calendar_btn.size())
                
                if not calendar_rect.contains(click_pos) and not button_rect.contains(click_pos):
                    self.tag_input._popup_calendar.hide()
        
        return super().eventFilter(obj, event)
    
    def _on_inline_date_selected(self, sql_date: str):
        """Обработка выбора даты из календаря"""
        try:
            dt = datetime.strptime(sql_date, "%Y-%m-%d")
            display_date = dt.strftime("%d.%m.%Y")
        except:
            display_date = sql_date
        
        self.tag_input.input_field.setText(display_date)
    
    def show_field_selector(self):
        """
        Показать селектор поля или виджет выбора значения
        
        Умная логика:
        1. Если выбрано справочное поле и окно выбора закрыто -> открываем окно выбора
        2. Если выбрано обычное поле -> фокус на поле ввода
        3. Если поле не выбрано -> показываем список полей
        """
        
        # ✅ НОВОЕ: Проверяем активное состояние справочного поля
        if self.current_field is not None:
            # Поле уже выбрано
            
            # Проверяем, это справочное поле?
            is_reference_field = self.current_field in self.REFERENCE_FIELDS
            
            if is_reference_field:
                # Справочное поле - проверяем виджет выбора
                if not self.value_selector or sip.isdeleted(self.value_selector) or not self.value_selector.isVisible():
                    # Виджет закрыт - открываем его снова!
                    print(f"🔄 Переоткрываем виджет выбора для '{self.current_field}' по клику на поле")
                    
                    values = self._get_reference_values(self.current_field)
                    if values:
                        self._show_value_selector(self.current_field, self.current_db_field, values)
                    return
                else:
                    # Виджет уже открыт - просто активируем его
                    print("♻️ Виджет выбора уже открыт - активируем")
                    self.value_selector.raise_()
                    self.value_selector.activateWindow()
                    self.value_selector.search_input.setFocus()
                    return
            else:
                # Обычное поле (дата или текст) - просто фокус
                self.tag_input.input_field.setFocus()
                return
        
        # Поле не выбрано - показываем список полей
        main_window = self.window()
        if self.field_popup.parent() != main_window:
            self.field_popup.setParent(main_window)
        
        # Защита от перекрытия
        self.field_popup.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.field_popup.raise_()
        
        if not self.current_field or (self.current_field and not self.tag_input.text().strip()):
            self.field_popup.show_at_widget(self.tag_input)
            self._popup_visible = True
            main_window.installEventFilter(self)
            
            current_text = self.tag_input.text()
            self.field_popup.filter_fields(current_text)
            QTimer.singleShot(10, lambda: self.field_popup.adjustSize())
            self.tag_input.input_field.setFocus()
            self.tag_input.input_field.setCursorPosition(len(current_text))
    def _restore_input_field_size(self):
        """
        Восстановить размеры поля ввода после закрытия виджетов
        
        Используется для предотвращения "схлопывания" поля
        """
        # Показываем поле
        self.tag_input.input_field.show()
        
        # Восстанавливаем sizePolicy
        self.tag_input.input_field.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred
        )
        
        # Восстанавливаем минимальную ширину
        self.tag_input.input_field.setMinimumWidth(100)
        
        # Принудительно обновляем геометрию
        self.tag_input.input_field.updateGeometry()
        self.tag_input.updateGeometry()
        self.tag_input.layout().update()
        
        # Обновляем через event loop
        QApplication.processEvents()
        
        print("✅ Размеры поля ввода восстановлены")
    def on_text_changed(self, text):
        if self.current_field:
            return

        if not self.field_popup.isVisible() and not self.current_field:
            self.show_field_selector()
            self.tag_input.input_field.setFocus()
            return

        if self.field_popup.isVisible():
            self.field_popup.filter_fields(text)
            self.tag_input.input_field.setFocus()
    
    def on_field_selected(self, field_name: str, db_field: str):
        """Обработка выбора поля"""
        self.current_field = field_name
        self.current_db_field = db_field
        self.field_popup.hide()
        
        # Сбросить expanded состояние
        self.field_popup.expanded = False
        self.field_popup.additional_container.setVisible(False)
        self.field_popup.expand_btn.setText("⋯ Показать все поля")
        
        for btn in [self.field_popup.status_btn, self.field_popup.type_btn, 
                    self.field_popup.executor_btn, self.field_popup.theme_btn, 
                    self.field_popup.number_btn]:
            btn.setVisible(False)
        
        self.tag_input.clear()
        
        # ✅ НОВОЕ: Проверяем, является ли поле справочным
        is_reference_field = field_name in self.REFERENCE_FIELDS
        
        if is_reference_field:
            values = self._get_reference_values(field_name)
            
            if is_reference_field:
                values = self._get_reference_values(field_name)
                
                if values:
                    self._show_value_selector(field_name, db_field, values)
                    
                    # ✅ НОВОЕ: Интерактивная подсказка
                    self._set_hint_style_interactive()
                    self.hint_label.setText(
                        f"💡 Выберите <b>{field_name}</b>. "
                        f"👆 <b>Клик на поле</b> для повторного открытия списка"
                    )
                    
                    self._update_buttons_state()
                    return
            else:
                QMessageBox.warning(
                    self, 
                    "Справочник пуст", 
                    f"Справочник '{field_name}' пуст.\n"
                    f"Добавьте значения в Управлении справочниками."
                )
                self._cancel_tag_creation()
                return
        
        # Включить режим календаря для датовых полей
        is_date_field = 'date' in db_field
        self.tag_input.set_date_mode(is_date_field)
        
        try:
            self.tag_input.date_selected.disconnect()
        except:
            pass
        self.tag_input.date_selected.connect(lambda date: self._on_inline_date_selected(date))
        
        if is_date_field:
            self.tag_input.input_field.setPlaceholderText(f"Введите дату для '{field_name}' (ДД.ММ.ГГГГ)...")
            self.hint_label.setText(f"💡 Введите дату для поля <b>{field_name}</b> (ДД.ММ.ГГГГ) или выберите в календаре")
        else:
            self.tag_input.input_field.setPlaceholderText(f"Введите значение для '{field_name}'...")
            self.hint_label.setText(f"💡 Введите значение для поля <b>{field_name}</b> и нажмите Enter")
        
        self.tag_input.setFocus()
        self._update_buttons_state()
    
    def moveEvent(self, event):
        """Перемещаем popup вместе с окном"""
        super().moveEvent(event)
        if self.field_popup.isVisible():
            self.field_popup.show_at_widget(self.tag_input)

    def resizeEvent(self, event):
        """Пересчитать позицию popup при изменении размера"""
        super().resizeEvent(event)
        if self.field_popup.isVisible():
            self.field_popup.show_at_widget(self.tag_input)
    
    def on_date_selected(self, field_name: str, date_str: str, db_field: str):
        """Обработка выбора даты"""
        if db_field:
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                display_date = date_obj.strftime("%d.%m.%Y")
            except:
                display_date = date_str
            
            self.add_tag(field_name, db_field, date_str, display_date)
            self.tag_input.set_date_mode(False)
            self.current_field = None
            self.current_db_field = None
            self.tag_input.setPlaceholderText("Выберите поле из списка...")
            self.hint_label.setText("💡 Кликните на поле → выберите фильтр из списка")
            self._update_buttons_state()
    
    def process_input(self):
        """Обработка ввода текста"""
        text = self.tag_input.text().strip()
        
        if not text and self.current_field:
            QMessageBox.warning(self, "Пустое значение", f"Введите значение для поля '{self.current_field}'")
            return
        
        # Если выбрано поле - создаем тег
        if self.current_field and self.current_db_field:
            final_value = text
            
            # Валидация даты для датовых полей
            if 'date' in self.current_db_field:
                is_valid, formatted_date, error = self._validate_date(text)
                if not is_valid:
                    QMessageBox.warning(self, "Ошибка даты", error)
                    return
                
                final_value = formatted_date
            
            # Создаем тег с валидированным значением
            self.add_tag(self.current_field, self.current_db_field, final_value)
            
            # Сброс режима даты
            self.tag_input.set_date_mode(False)
            self.current_field = None
            self.current_db_field = None
            self.tag_input.setPlaceholderText("Выберите поле из списка...")
            self.hint_label.setText("💡 Кликните на поле → выберите фильтр из списка")
            self._update_buttons_state()
    
    def add_tag(self, field_name: str, db_field: str, value: str, display_value: str = None):
        """Добавить тег (с корректным отображением дат)"""
        if not value.strip():
            return
        
        # Для дат показываем DD.MM.YYYY
        if display_value is None and 'date' in db_field:
            try:
                dt = datetime.strptime(value, "%Y-%m-%d")
                display_value = dt.strftime("%d.%m.%Y")
            except:
                display_value = value
        
        self.tag_input.add_tag_with_display(field_name, db_field, value, display_value or value)
        
        # Подключаем редактирование
        if self.tag_input.tags:
            tag_widget = self.tag_input.tags[-1][3]
            tag_widget.clicked.connect(self.on_tag_clicked)
    
    def on_tag_clicked(self, tag_widget):
        """Обработчик клика по тегу"""
        for field_name, db_field, value, widget in self.tag_input.tags:
            if widget == tag_widget:
                # Запоминаем, что мы редактируем
                self._editing_tag = (field_name, db_field, value)
                
                # Устанавливаем текущее поле
                self.current_field = field_name
                self.current_db_field = db_field
                
                # Начинаем редактирование
                self.tag_input.edit_tag(tag_widget)
                
                # Обновляем подсказку
                self.hint_label.setText(f"💡 Редактируйте поле <b>{field_name}</b> и нажмите Enter")
                
                break
    
    def on_tag_removed(self):
        """Обработчик удаления одного тега"""
        tags = self.tag_input.get_tags()
        
        if tags:
            search_data = self.build_sql_query(tags)
            self.search_requested.emit(search_data)
        else:
            self.tags_cleared.emit()
    
    def build_sql_query(self, tags: List[tuple]) -> dict:
        """Построить SQL запрос из тегов"""
        conditions = []
        params = []
        
        for field_name, db_field, value in tags:
            if 'date' in db_field:
                if 'from' in db_field:
                    conditions.append("d.reg_date >= ?")
                    params.append(value)
                elif 'to' in db_field:
                    conditions.append("d.reg_date <= ?")
                    params.append(value)
                elif 'exact' in db_field:
                    conditions.append("d.reg_date = ?")
                    params.append(value)
            else:
                if db_field in ('reg_number', 'title', 'number'):
                    conditions.append(f"d.{db_field} LIKE ?")
                    params.append(f"%{value}%")
                elif db_field == 'status':
                    conditions.append("s.name LIKE ?")
                    params.append(f"%{value}%")
                elif db_field == 'type':
                    conditions.append("dt.name LIKE ?")
                    params.append(f"%{value}%")
                elif db_field == 'executor':
                    conditions.append("e.name LIKE ?")
                    params.append(f"%{value}%")
                elif db_field == 'theme':
                    conditions.append("t.name LIKE ?")
                    params.append(f"%{value}%")
        
        base_query = """
            SELECT 
                d.id, d.title, d.reg_number, d.reg_date,
                COALESCE(s.name, 'Не указан') as status,
                COALESCE(dt.name, 'Не указан') as type_doc,
                COALESCE(e.name, 'Не назначен') as executor_name,
                COALESCE(t.name, 'Не указана') as theme_name,
                d.document_path as filename
            FROM documents d
            LEFT JOIN ref_status s ON d.status_id = s.id
            LEFT JOIN ref_document_types dt ON d.type_id = dt.id
            LEFT JOIN ref_executors e ON d.executor_id = e.id
            LEFT JOIN ref_themes t ON d.theme_id = t.id
            WHERE {conditions}
            ORDER BY d.reg_date DESC, d.id DESC
            LIMIT 1000
        """
        
        conditions_sql = " AND ".join(conditions)
        final_query = base_query.format(conditions=conditions_sql)
        
        return {
            'query': final_query,
            'params': params
        }


def execute_simple_tag_search(db_manager, search_data: dict) -> list:
    """Выполнить поиск в БД"""
    try:
        cursor = db_manager.connection.cursor()
        
        query = search_data['query']
        params = search_data['params']
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        documents = []
        for row in rows:
            documents.append({
                'id': row[0],
                'title': row[1] or "Без названия",
                'reg_number': row[2] or "-",
                'reg_date': row[3] or "-",
                'status': row[4],
                'type_doc': row[5],
                'executor_name': row[6],
                'theme_name': row[7],
                'filename': row[8] or "-"
            })
        
        print(f"✅ Найдено документов: {len(documents)}")
        return documents
    
    except Exception as e:
        print(f"❌ Ошибка поиска: {e}")
        import traceback
        traceback.print_exc()
        return []


if __name__ == "__main__":
    import sys
    
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("🔍 Тековый поиск (с выпадающим списком)")
    window.resize(800, 150)
    
    widget = SimpleTagSearchWidget()
    
    def on_search(data):
        print("\n" + "="*60)
        print("🔍 ПОИСК")
        print("="*60)
        print(data['query'])
        print("Параметры:", data['params'])
        print("="*60 + "\n")
    
    widget.search_requested.connect(on_search)
    
    window.setCentralWidget(widget)
    window.show()
    
    sys.exit(app.exec_())