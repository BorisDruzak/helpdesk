from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QIcon, QFont
from datetime import datetime
from ui_styles import AppColors, AppStyles, AppLayout
class SimpleReferenceEditDialog(QDialog):
    """Универсальный диалог редактирования простого справочника (ID + name)"""
    
    def __init__(self, parent=None, data=None, title="Редактирование"):
        super().__init__(parent)
        self.data = data
        self.dialog_title = title
        self.init_ui()
        
        if data:
            self.load_data()
    
    def init_ui(self):
        self.setWindowTitle(self.dialog_title)
        self.setModal(True)
        self.resize(450, 200)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.FramelessWindowHint)
        layout = QFormLayout()
        
        # Поля ввода
        self.name_field = QLineEdit()
        self.name_field.setPlaceholderText("Название")
        self.name_field.setStyleSheet(AppStyles.line_e())
        # Информационные поля (только для редактирования)
        if self.data:
            self.id_label = QLabel()
            self.id_label.setStyleSheet(AppStyles.lable())
            layout.addRow("ID:", self.id_label)
            layout.addRow("", QFrame())  # Разделитель
        
        layout.addRow("Название *:", self.name_field)
        
        # Кнопки
        buttons = QDialogButtonBox()

        # СОЗДАТЬ КАСТОМНЫЕ КНОПКИ
        add_button = buttons.addButton("Добавить", QDialogButtonBox.AcceptRole)
        cancel_button = buttons.addButton("Отмена", QDialogButtonBox.RejectRole)

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.setStyleSheet(AppStyles.butt())
        layout.addWidget(buttons)
        self.setStyleSheet(AppStyles.dia())
        self.setLayout(layout)
    
    def load_data(self):
        """Загрузить данные для редактирования"""
        if not self.data:
            return
        
        self.name_field.setText(self.data.get('name', ''))
        
        if hasattr(self, 'id_label'):
            self.id_label.setText(str(self.data.get('id', '')))
    
    def get_data(self):
        """Получить данные из формы"""
        return {
            'name': self.name_field.text().strip()
        }
    def show_warning(self, title, text):
        """Показать предупреждение со стилем"""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setStyleSheet(AppStyles.message_box())
        
        # Русский текст
        ok_button = msg.button(QMessageBox.Ok)
        ok_button.setText("ОК")
        
        msg.exec_()
    
    def validate(self):
        """Валидация данных"""
        if not self.name_field.text().strip():
            self.show_warning("Ошибка", "Название не может быть пустым")
            return False
        return True
class ExecutorsTableModel(QAbstractTableModel):
    """Модель таблицы исполнителей"""
    
    def __init__(self, data, headers):
        super().__init__()
        self._data = data
        self._headers = headers
    def show_warning(self, title, text):
        """Показать предупреждение со стилем"""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setStyleSheet(AppStyles.message_box())
        
        # Русский текст
        ok_button = msg.button(QMessageBox.Ok)
        ok_button.setText("ОК")
        
        msg.exec_()    
    def rowCount(self, parent=None):
        return len(self._data)
    
    def columnCount(self, parent=None):
        return len(self._headers)
    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        
        if role == Qt.DisplayRole:
            return str(self._data[index.row()][index.column()])
        elif role == Qt.TextAlignmentRole:
            if index.column() == 0:  # ID колонка
                return Qt.AlignCenter
        elif role == Qt.BackgroundRole:
            # Подсвечиваем неактивных исполнителей
            if len(self._data[index.row()]) > 4 and not self._data[index.row()][4]:
                from PyQt5.QtGui import QColor
                return QColor(255, 240, 240)  # Светло-красный
        
        return None
    
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._headers[section]
        return None
    
    def update_data(self, new_data):
        """Обновить данные модели"""
        self.beginResetModel()
        self._data = new_data
        self.endResetModel()


class ThemesTableModel(QAbstractTableModel):
    """Модель таблицы тем"""
    
    def __init__(self, data, headers):
        super().__init__()
        self._data = data
        self._headers = headers
        
    def rowCount(self, parent=None):
        return len(self._data)
    
    def columnCount(self, parent=None):
        return len(self._headers)
    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        
        if role == Qt.DisplayRole:
            value = self._data[index.row()][index.column()]
            if index.column() == 2 and isinstance(value, str) and len(value) > 50:
                # Обрезаем длинные описания
                return value[:50] + "..."
            return str(value)
        elif role == Qt.TextAlignmentRole:
            if index.column() == 0:  # ID колонка
                return Qt.AlignCenter
        elif role == Qt.BackgroundRole:
            # Подсвечиваем неактивные темы
            if len(self._data[index.row()]) > 3 and not self._data[index.row()][3]:
                from PyQt5.QtGui import QColor
                return QColor(255, 240, 240)  # Светло-красный
        
        return None
    
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._headers[section]
        return None
    
    def update_data(self, new_data):
        """Обновить данные модели"""
        self.beginResetModel()
        self._data = new_data
        self.endResetModel()


class ExecutorEditDialog(QDialog):
    """Диалог редактирования исполнителя"""
    
    def __init__(self, parent=None, executor_data=None):
        super().__init__(parent)
        self.executor_data = executor_data
        self.init_ui()
        
        if executor_data:
            self.load_data()
    def show_warning(self, title, text):
        """Показать предупреждение со стилем"""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setStyleSheet(AppStyles.message_box())
        
        # Русский текст
        ok_button = msg.button(QMessageBox.Ok)
        ok_button.setText("ОК")
        
        msg.exec_()
    def init_ui(self):
        self.setWindowTitle("Редактирование исполнителя" if self.executor_data else "Добавление исполнителя")
        self.setModal(True)
        self.resize(500, 300)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.FramelessWindowHint)
        layout = QFormLayout()

        
        # Поля ввода
        self.name_field = QLineEdit()
        self.name_field.setStyleSheet(AppStyles.line_e())
        self.name_field.setPlaceholderText("Фамилия И.О.")
        
        self.position_field = QLineEdit()
        self.position_field.setPlaceholderText("Должность")
        self.position_field.setStyleSheet(AppStyles.line_e())

        self.department_field = QLineEdit()
        self.department_field.setPlaceholderText("Отдел/Подразделение")
        self.department_field.setStyleSheet(AppStyles.line_e())

        self.active_checkbox = QCheckBox("Активный")
        self.active_checkbox.setStyleSheet(AppStyles.check())
        self.active_checkbox.setChecked(True)
        
        # Информационные поля (только для редактирования)
        if self.executor_data:
            self.created_at_label = QLabel()
            self.created_at_label.setStyleSheet(AppStyles.lable())
            self.id_label = QLabel()
            layout.addRow("ID:", self.id_label)
            layout.addRow("Создан:", self.created_at_label)
            layout.addRow("", QFrame())  # Разделитель
        
        layout.addRow("ФИО *:", self.name_field)
        layout.addRow("Должность:", self.position_field)
        layout.addRow("Отдел:", self.department_field)
        layout.addRow("", self.active_checkbox)
        
        # Кнопки
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        # ИЗМЕНИТЬ ТЕКСТ КНОПОК НА РУССКИЙ
        ok_button = buttons.button(QDialogButtonBox.Ok)
        cancel_button = buttons.button(QDialogButtonBox.Cancel)

        ok_button.setText("Добавить")
        cancel_button.setText("Отмена")

        buttons.setStyleSheet(AppStyles.butt())
        self.setStyleSheet(AppStyles.dia())
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def load_data(self):
        """Загрузить данные исполнителя для редактирования"""
        if not self.executor_data:
            return
        
        data = self.executor_data
        self.name_field.setText(data.get('name', ''))
        self.position_field.setText(data.get('position', ''))
        self.department_field.setText(data.get('department', ''))
        self.active_checkbox.setChecked(data.get('is_active', True))
        
        if hasattr(self, 'id_label'):
            self.id_label.setText(str(data.get('id', '')))
        
        if hasattr(self, 'created_at_label'):
            created_at = data.get('created_at', '')
            if created_at:
                try:
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    self.created_at_label.setText(dt.strftime('%d.%m.%Y %H:%M'))
                except:
                    self.created_at_label.setText(created_at)
    
    def get_data(self):
        """Получить данные из формы"""
        return {
            'name': self.name_field.text().strip(),
            'position': self.position_field.text().strip(),
            'department': self.department_field.text().strip(),
            'is_active': self.active_checkbox.isChecked()
        }
    
    def validate(self):
        """Валидация данных"""
        if not self.name_field.text().strip():
            self.show_warning("Ошибка", "Название не может быть пустым")
            return False
        return True


class ThemeEditDialog(QDialog):
    """Диалог редактирования темы"""
    
    def __init__(self, parent=None, theme_data=None):
        super().__init__(parent)
        self.theme_data = theme_data
        self.init_ui()
        
        if theme_data:
            self.load_data()
    def show_warning(self, title, text):
        """Показать предупреждение со стилем"""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setStyleSheet(AppStyles.message_box())
        
        # Русский текст
        ok_button = msg.button(QMessageBox.Ok)
        ok_button.setText("ОК")
        
        msg.exec_()
    def init_ui(self):
        self.setWindowTitle("Редактирование темы" if self.theme_data else "Добавление темы")
        self.setModal(True)
        self.resize(500, 350)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.FramelessWindowHint)
        
        layout = QFormLayout()
        
        # Поля ввода
        self.name_field = QLineEdit()
        self.name_field.setStyleSheet(AppStyles.line_e())
        self.name_field.setPlaceholderText("Краткое название темы")
        
        self.description_field = QTextEdit()
        self.description_field.setStyleSheet(AppStyles.text_e())
        self.description_field.setMaximumHeight(80)
        self.description_field.setPlaceholderText("Подробное описание темы...")
        
        self.active_checkbox = QCheckBox("Активная")
        self.active_checkbox.setStyleSheet(AppStyles.check())
        self.active_checkbox.setChecked(True)
        
        # Информационные поля (только для редактирования)
        if self.theme_data:
            self.created_at_label = QLabel()
            self.created_at_label.setStyleSheet(AppStyles.lable())
            self.id_label = QLabel()
            self.id_label.setStyleSheet(AppStyles.lable())  
            layout.addRow("ID:", self.id_label)
            layout.addRow("Создана:", self.created_at_label)
            layout.addRow("", QFrame())  # Разделитель
        
        layout.addRow("Название *:", self.name_field)
        layout.addRow("Описание:", self.description_field)
        layout.addRow("", self.active_checkbox)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        # ИЗМЕНИТЬ ТЕКСТ КНОПОК НА РУССКИЙ
        ok_button = buttons.button(QDialogButtonBox.Ok)
        cancel_button = buttons.button(QDialogButtonBox.Cancel)

        ok_button.setText("Добавить")
        cancel_button.setText("Отмена")

        buttons.setStyleSheet(AppStyles.butt())
        layout.addWidget(buttons)
        self.setStyleSheet(AppStyles.dia())
        self.setLayout(layout)
    
    def load_data(self):
        """Загрузить данные темы для редактирования"""
        if not self.theme_data:
            return
        
        data = self.theme_data
        self.name_field.setText(data.get('name', ''))
        self.description_field.setPlainText(data.get('description', ''))
        self.active_checkbox.setChecked(data.get('is_active', True))
        
        if hasattr(self, 'id_label'):
            self.id_label.setText(str(data.get('id', '')))
        
        if hasattr(self, 'created_at_label'):
            created_at = data.get('created_at', '')
            if created_at:
                try:
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    self.created_at_label.setText(dt.strftime('%d.%m.%Y %H:%M'))
                except:
                    self.created_at_label.setText(created_at)
    
    def get_data(self):
        """Получить данные из формы"""
        return {
            'name': self.name_field.text().strip(),
            'description': self.description_field.toPlainText().strip(),
            'is_active': self.active_checkbox.isChecked()
        }
    
    def validate(self):
        """Валидация данных"""
        if not self.name_field.text().strip():
            QMessageBox.warning(self, "Ошибка", "Название не может быть пустым")
            return False
        return True

class ResponsibleExecutorEditDialog(QDialog):
    """Диалог редактирования ответственного исполнителя"""
    
    def __init__(self, parent=None, executor_data=None):
        super().__init__(parent)
        self.executor_data = executor_data
        self.init_ui()
        
        if executor_data:
            self.load_data()
    def show_warning(self, title, text):
        """Показать предупреждение со стилем"""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setStyleSheet(AppStyles.message_box())
        
        # Русский текст
        ok_button = msg.button(QMessageBox.Ok)
        ok_button.setText("ОК")
        
        msg.exec_()
    def init_ui(self):
        self.setWindowTitle("Редактирование ответственного исполнителя" 
                            if self.executor_data else "Добавление ответственного исполнителя")
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.FramelessWindowHint)
        self.resize(500, 250)
        
        layout = QFormLayout()
        
        # Поля ввода
        self.name_field = QLineEdit()
        self.name_field.setStyleSheet(AppStyles.line_e())
        self.name_field.setPlaceholderText("Фамилия И.О.")
        
        self.active_checkbox = QCheckBox("Активный")
        self.active_checkbox.setStyleSheet(AppStyles.check())
        self.active_checkbox.setChecked(True)
        
        # Информационные поля (только для редактирования)
        if self.executor_data:
            self.id_label = QLabel()
            self.id_label.setStyleSheet(AppStyles.lable())
            layout.addRow("ID:", self.id_label)
            layout.addRow("", QFrame())  # Разделитель
        
        layout.addRow("ФИО *:", self.name_field)
        layout.addRow("", self.active_checkbox)
        
        # Кнопки
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        # ИЗМЕНИТЬ ТЕКСТ КНОПОК НА РУССКИЙ
        ok_button = buttons.button(QDialogButtonBox.Ok)
        cancel_button = buttons.button(QDialogButtonBox.Cancel)

        ok_button.setText("Добавить")
        cancel_button.setText("Отмена")

        buttons.setStyleSheet(AppStyles.butt())
        layout.addWidget(buttons)
        self.setStyleSheet(AppStyles.dia())
        self.setLayout(layout)
    
    def load_data(self):
        """Загрузить данные для редактирования"""
        if not self.executor_data:
            return
        
        data = self.executor_data
        self.name_field.setText(data.get('name', ''))
        self.active_checkbox.setChecked(data.get('is_active', True))
        
        if hasattr(self, 'id_label'):
            self.id_label.setText(str(data.get('id', '')))
    
    def get_data(self):
        """Получить данные из формы"""
        return {
            'name': self.name_field.text().strip(),
            'is_active': self.active_checkbox.isChecked()
        }
    
    def validate(self):
        """Валидация данных"""
        if not self.name_field.text().strip():
            self.show_warning("Ошибка", "ФИО не может быть пустым")
            return False
        return True

class SimpleReferenceTableModel(QAbstractTableModel):
    """Модель таблицы для простых справочников (только ID и name)"""
    
    def __init__(self, data, headers):
        super().__init__()
        self._data = data
        self._headers = headers
    def show_warning(self, title, text):
        """Показать предупреждение со стилем"""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setStyleSheet(AppStyles.message_box())
        
        # Русский текст
        ok_button = msg.button(QMessageBox.Ok)
        ok_button.setText("ОК")
        
        msg.exec_()    
    def rowCount(self, parent=None):
        return len(self._data)
    
    def columnCount(self, parent=None):
        return len(self._headers)
    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        
        if role == Qt.DisplayRole:
            return str(self._data[index.row()][index.column()])
        elif role == Qt.TextAlignmentRole:
            if index.column() == 0:  # ID колонка
                return Qt.AlignCenter
        elif role == Qt.BackgroundRole:
            # Подсвечиваем неактивных (если есть поле is_active)
            if len(self._data[index.row()]) > 2 and not self._data[index.row()][2]:
                from PyQt5.QtGui import QColor
                return QColor(255, 240, 240)  # Светло-красный
        
        return None
    
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._headers[section]
        return None
    
    def update_data(self, new_data):
        """Обновить данные модели"""
        self.beginResetModel()
        self._data = new_data
        self.endResetModel()
class PublishedWhereEditDialog(QDialog):
    """Диалог редактирования места публикации"""
    
    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        self.data = data
        self.init_ui()
        
        if data:
            self.load_data()
    def show_warning(self, title, text):
        """Показать предупреждение со стилем"""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setStyleSheet(AppStyles.message_box())
        
        # Русский текст
        ok_button = msg.button(QMessageBox.Ok)
        ok_button.setText("ОК")
        
        msg.exec_()
    def init_ui(self):
        self.setWindowTitle("Редактирование места публикации" 
                            if self.data else "Добавление места публикации")
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.FramelessWindowHint)
        self.setModal(True)
        self.resize(450, 200)
        
        layout = QFormLayout()
        
        # Поля ввода
        self.name_field = QLineEdit()
        self.name_field.setStyleSheet(AppStyles.line_e())
        self.name_field.setPlaceholderText("Название места публикации")
        
        # Информационные поля (только для редактирования)
        if self.data:
            self.id_label = QLabel()
            self.id_label.setStyleSheet(AppStyles.lable())
            layout.addRow("ID:", self.id_label)
            layout.addRow("", QFrame())  # Разделитель
        
        layout.addRow("Название *:", self.name_field)
        
        # Кнопки
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        # ИЗМЕНИТЬ ТЕКСТ КНОПОК НА РУССКИЙ
        ok_button = buttons.button(QDialogButtonBox.Ok)
        cancel_button = buttons.button(QDialogButtonBox.Cancel)

        ok_button.setText("Добавить")
        cancel_button.setText("Отмена")

        buttons.setStyleSheet(AppStyles.butt())
        
        layout.addWidget(buttons)
        
        self.setStyleSheet(AppStyles.dia())
        self.setLayout(layout)
    
    def load_data(self):
        """Загрузить данные для редактирования"""
        if not self.data:
            return
        
        self.name_field.setText(self.data.get('name', ''))
        
        if hasattr(self, 'id_label'):
            self.id_label.setText(str(self.data.get('id', '')))
    
    def get_data(self):
        """Получить данные из формы"""
        return {
            'name': self.name_field.text().strip()
        }
    
    def validate(self):
        """Валидация данных"""
        if not self.name_field.text().strip():
            self.show_warning("Ошибка", "Название не может быть пустым")
            return False
        return True
class ReferenceManagerDialog(QDialog):
    """Главное окно управления справочниками"""
    
    # Сигналы для обновления данных в основном приложении
    references_updated = pyqtSignal()
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.init_ui()
        self.load_all_data()
    
    def init_ui(self):
        self.setWindowTitle("🛠 Управление справочниками")
        self.setModal(False)  # Немодальное окно
        self.resize(1400, 800)
        
        # Главный лейаут
        main_layout = QVBoxLayout()
        
        # Заголовок
        header_widget = QWidget()
        header_widget.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {AppColors.PRIMARY}, stop:1 {AppColors.PRIMARY_DARK});
                border-radius: 10px;
            }}
        """)
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(20, 15, 20, 15)

        header_icon = QLabel("🛠")
        header_icon.setStyleSheet("font-size: 32px; color: white; background: transparent;")

        header_text_layout = QVBoxLayout()
        header_title = QLabel("Управление справочниками")
        header_title.setStyleSheet("""
            QLabel {
                font-size: 18pt;
                font-weight: bold;
                color: white;
                background: transparent;
            }
        """)
        header_subtitle = QLabel("Редактирование всех справочных данных системы")
        header_subtitle.setStyleSheet(f"""
            QLabel {{
                font-size: 10pt;
                color: {AppColors.GRAY_100};
                background: transparent;
            }}
        """)

        header_text_layout.addWidget(header_title)
        header_text_layout.addWidget(header_subtitle)

        header_layout.addWidget(header_icon)
        header_layout.addLayout(header_text_layout)
        header_layout.addStretch()
        header_widget.setLayout(header_layout)
        main_layout.addWidget(header_widget)
        
        # Вкладки
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(AppStyles.tab_widget()) 
        # Вкладка исполнителей
        self.executors_tab = self.create_executors_tab()
        self.tab_widget.addTab(self.executors_tab, "👤 Исполнители")
        
        # Вкладка тем
        self.themes_tab = self.create_themes_tab()
        self.tab_widget.addTab(self.themes_tab, "📝 Темы")
        # Вкладка согласующих
        self.approvers_tab = self.create_approvers_tab()
        self.tab_widget.addTab(self.approvers_tab, "🤝 Согласующие")

        # Вкладка подписантов  
        self.signers_tab = self.create_signers_tab()
        self.tab_widget.addTab(self.signers_tab, "✍️ Подписанты")
        main_layout.addWidget(self.tab_widget)
        # Вкладка ответственных исполнителей
        self.responsible_executors_tab = self.create_responsible_executors_tab()
        self.tab_widget.addTab(self.responsible_executors_tab, "👔 Ответственные исполнители")

        # Вкладка мест публикации
        self.published_where_tab = self.create_published_where_tab()
        self.tab_widget.addTab(self.published_where_tab, "📰 Места публикации")
        # Вкладка статусов
        self.statuses_tab = self.create_simple_reference_tab(
            'ref_status', 'status_id', 'Статусы', '📌'
        )
        self.tab_widget.addTab(self.statuses_tab, "📌 Статусы")

        # Вкладка типов документов
        self.doc_types_tab = self.create_simple_reference_tab(
            'ref_document_types', 'type_id', 'Типы документов', '📄'
        )
        self.tab_widget.addTab(self.doc_types_tab, "📄 Типы документов")

        # Вкладка типов подписания
        self.signing_types_tab = self.create_simple_reference_tab(
            'ref_signing_types', 'signing_type_id', 'Типы подписания', '✍️'
        )
        self.tab_widget.addTab(self.signing_types_tab, "✍️ Типы подписания")

        # Вкладка видов документов
        self.doc_kinds_tab = self.create_simple_reference_tab(
            'ref_document_kinds', 'document_kind_id', 'Виды документов', '📋'
        )
        self.tab_widget.addTab(self.doc_kinds_tab, "📋 Виды документов")
        # Нижняя панель с общими кнопками
        bottom_panel = self.create_bottom_panel()
        main_layout.addLayout(bottom_panel)
        
        self.setLayout(main_layout)
    
    def create_executors_tab(self):
        """Создание вкладки исполнителей"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Панель управления
        control_panel = QHBoxLayout()
        
        # Кнопки
        self.add_executor_btn = QPushButton("➕ Добавить исполнителя")
        self.add_executor_btn.setStyleSheet(AppStyles.button_success(height="20px"))  # ← ДОБАВИТЬ
        self.add_executor_btn.clicked.connect(self.add_executor)

        self.edit_executor_btn = QPushButton("✏️ Редактировать")
        self.edit_executor_btn.setStyleSheet(AppStyles.button_success(height="20px",bg_color='#03A9F4',hover_light='#0288D1'))  # ← ДОБАВИТЬ
        self.edit_executor_btn.clicked.connect(self.edit_executor)
        self.edit_executor_btn.setEnabled(False)

        self.delete_executor_btn = QPushButton("🗑 Удалить")
        self.delete_executor_btn.setStyleSheet(AppStyles.button_success(height="20px",bg_color='#F44336',hover_light='#D32F2F'))  # ← ДОБАВИТЬ
        self.delete_executor_btn.clicked.connect(self.delete_executor)
        self.delete_executor_btn.setEnabled(False)

        self.refresh_executors_btn = QPushButton("🔄 Обновить")
        self.refresh_executors_btn.setStyleSheet(AppStyles.button_success(height="20px",bg_color='#03A9F4',hover_light='#0288D1'))  # ← ДОБАВИТЬ
        self.refresh_executors_btn.clicked.connect(self.load_executors)
        
        # Фильтры
        self.executors_filter = QLineEdit()
        self.executors_filter.setPlaceholderText("🔍 Поиск по имени или должности...")
        self.executors_filter.setStyleSheet(AppStyles.input_field())
        self.executors_filter.textChanged.connect(self.filter_executors)
        
        self.show_inactive_executors = QCheckBox("Показать неактивных")
        self.show_inactive_executors.setStyleSheet(AppStyles.checkbox_widget())
        self.show_inactive_executors.stateChanged.connect(self.load_executors)
        
        control_panel.addWidget(self.add_executor_btn)
        control_panel.addWidget(self.edit_executor_btn)
        control_panel.addWidget(self.delete_executor_btn)
        control_panel.addWidget(self.refresh_executors_btn)
        control_panel.addStretch()
        control_panel.addWidget(QLabel("Фильтр:"))
        control_panel.addWidget(self.executors_filter)
        control_panel.addWidget(self.show_inactive_executors)
        
        # Таблица исполнителей
        self.executors_table = QTableView()
        self.executors_table.setStyleSheet(AppStyles.table_view())
        self.executors_model = ExecutorsTableModel([], ['ID', 'ФИО', 'Должность', 'Отдел', 'Активный'])
        self.executors_table.setModel(self.executors_model)
        self.executors_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.executors_table.selectionModel().selectionChanged.connect(self.on_executor_selection_changed)
        self.executors_table.doubleClicked.connect(self.edit_executor)
        
        # Настройка таблицы
        self.executors_table.horizontalHeader().setStretchLastSection(True)
        self.executors_table.setAlternatingRowColors(True)
        self.executors_table.setSortingEnabled(True)
        self.executors_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.executors_table.setSelectionMode(QAbstractItemView.SingleSelection)
        
        # Информация
        self.executors_info = QLabel("📊 Загружается...")
        
        layout.addLayout(control_panel)
        layout.addWidget(self.executors_table)
        layout.addWidget(self.executors_info)
        
        tab.setLayout(layout)
        return tab
    def create_published_where_tab(self):
        """Создание вкладки мест публикации"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Панель управления
        control_panel = QHBoxLayout()
        
        # Кнопки
        self.add_pub_where_btn = QPushButton("➕ Добавить")
        self.add_pub_where_btn.setStyleSheet(AppStyles.button_success(height="20px"))
        self.add_pub_where_btn.clicked.connect(self.add_published_where)
        
        self.edit_pub_where_btn = QPushButton("✏️ Редактировать")
        self.edit_pub_where_btn.setStyleSheet(AppStyles.button_success(height="20px",bg_color='#03A9F4',hover_light='#0288D1'))
        self.edit_pub_where_btn.clicked.connect(self.edit_published_where)
        self.edit_pub_where_btn.setEnabled(False)
        
        self.delete_pub_where_btn = QPushButton("🗑 Удалить")
        self.delete_pub_where_btn.setStyleSheet(AppStyles.button_success(height="20px",bg_color='#F44336',hover_light='#D32F2F'))
        self.delete_pub_where_btn.clicked.connect(self.delete_published_where)
        self.delete_pub_where_btn.setEnabled(False)
        
        self.refresh_pub_where_btn = QPushButton("🔄 Обновить")
        self.refresh_pub_where_btn.setStyleSheet(AppStyles.button_success(height="20px",bg_color='#03A9F4',hover_light='#0288D1'))
        self.refresh_pub_where_btn.clicked.connect(self.load_published_where)
        
        # Фильтр
        self.pub_where_filter = QLineEdit()
        self.pub_where_filter.setStyleSheet(AppStyles.input_field())
        self.pub_where_filter.setPlaceholderText("🔍 Поиск по названию...")
        self.pub_where_filter.textChanged.connect(self.filter_published_where)
        
        control_panel.addWidget(self.add_pub_where_btn)
        control_panel.addWidget(self.edit_pub_where_btn)
        control_panel.addWidget(self.delete_pub_where_btn)
        control_panel.addWidget(self.refresh_pub_where_btn)
        control_panel.addStretch()
        control_panel.addWidget(QLabel("Фильтр:"))
        control_panel.addWidget(self.pub_where_filter)
        
        # Таблица
        self.pub_where_table = QTableView()
        self.pub_where_model = SimpleReferenceTableModel([], ['ID', 'Название'])
        self.pub_where_table.setStyleSheet(AppStyles.table_view())
        self.pub_where_table.setModel(self.pub_where_model)
        self.pub_where_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.pub_where_table.selectionModel().selectionChanged.connect(
            self.on_published_where_selection_changed
        )
        self.pub_where_table.doubleClicked.connect(self.edit_published_where)
        
        # Настройка таблицы
        self.pub_where_table.horizontalHeader().setStretchLastSection(True)
        self.pub_where_table.setAlternatingRowColors(True)
        self.pub_where_table.setSortingEnabled(True)
        
        # Информация
        self.pub_where_info = QLabel("📊 Загружается...")
        
        layout.addLayout(control_panel)
        layout.addWidget(self.pub_where_table)
        layout.addWidget(self.pub_where_info)
        
        tab.setLayout(layout)
        return tab
    def create_approvers_tab(self):
        "Создание вкладки согласующих"
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Панель управления
        control_panel = QHBoxLayout()
        
        # Кнопки
        self.add_approver_btn = QPushButton("➕ Добавить согласующего")
        self.add_approver_btn.setStyleSheet(AppStyles.button_success(height="20px"))
        self.add_approver_btn.clicked.connect(self.add_approver_from_executors)
        
        self.edit_approver_btn = QPushButton("✏️ Редактировать")
        self.edit_approver_btn.setStyleSheet(AppStyles.button_success(height="20px",bg_color='#03A9F4',hover_light='#0288D1'))
        self.edit_approver_btn.clicked.connect(self.edit_approver)
        self.edit_approver_btn.setEnabled(False)
        
        self.delete_approver_btn = QPushButton("🗑 Удалить")
        self.delete_approver_btn.setStyleSheet(AppStyles.button_success(height="20px",bg_color='#F44336',hover_light='#D32F2F'))
        self.delete_approver_btn.clicked.connect(self.delete_approver)
        self.delete_approver_btn.setEnabled(False)
        
        self.refresh_approvers_btn = QPushButton("🔄 Обновить")
        self.refresh_approvers_btn.setStyleSheet(AppStyles.button_success(height="20px",bg_color='#03A9F4',hover_light='#0288D1'))
        self.refresh_approvers_btn.clicked.connect(self.load_approvers)
        
        # Фильтры
        self.approvers_filter = QLineEdit()
        self.approvers_filter.setStyleSheet(AppStyles.input_field())
        self.approvers_filter.setPlaceholderText("🔍 Поиск по имени...")
        self.approvers_filter.textChanged.connect(self.filter_approvers)
        
        control_panel.addWidget(self.add_approver_btn)
        control_panel.addWidget(self.edit_approver_btn)
        control_panel.addWidget(self.delete_approver_btn)
        control_panel.addWidget(self.refresh_approvers_btn)
        control_panel.addStretch()
        control_panel.addWidget(QLabel("Фильтр:"))
        control_panel.addWidget(self.approvers_filter)
        
        # Таблица согласующих
        self.approvers_table = QTableView()
        self.approvers_table.setStyleSheet(AppStyles.table_view())
        self.approvers_model = ExecutorsTableModel([], ['ID', 'ФИО'])
        self.approvers_table.setModel(self.approvers_model)
        self.approvers_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.approvers_table.selectionModel().selectionChanged.connect(self.on_approver_selection_changed)
        self.approvers_table.doubleClicked.connect(self.edit_approver)
        
        # Настройка таблицы
        self.approvers_table.horizontalHeader().setStretchLastSection(True)
        self.approvers_table.setAlternatingRowColors(True)
        self.approvers_table.setSortingEnabled(True)
        
        # Информация
        self.approvers_info = QLabel("📊 Загружается...")
        
        layout.addLayout(control_panel)
        layout.addWidget(self.approvers_table)
        layout.addWidget(self.approvers_info)
        
        tab.setLayout(layout)
        return tab

    def create_signers_tab(self):
        """Создание вкладки подписантов"""
        # Аналогично create_approvers_tab, но для подписантов
        tab = QWidget()
        layout = QVBoxLayout()
        
        control_panel = QHBoxLayout()
        
        self.add_signer_btn = QPushButton("➕ Добавить подписанта")
        self.add_signer_btn.setStyleSheet(AppStyles.button_success(height="20px"))
        self.add_signer_btn.clicked.connect(self.add_signer_from_executors)
        
        self.edit_signer_btn = QPushButton("✏️ Редактировать")
        self.edit_signer_btn.setStyleSheet(AppStyles.button_success(height="20px",bg_color='#03A9F4',hover_light='#0288D1'))
        self.edit_signer_btn.clicked.connect(self.edit_signer)
        self.edit_signer_btn.setEnabled(False)
        
        self.delete_signer_btn = QPushButton("🗑 Удалить")
        self.delete_signer_btn.setStyleSheet(AppStyles.button_success(height="20px",bg_color='#F44336',hover_light='#D32F2F'))
        self.delete_signer_btn.clicked.connect(self.delete_signer)
        self.delete_signer_btn.setEnabled(False)
        
        self.refresh_signers_btn = QPushButton("🔄 Обновить")
        self.refresh_signers_btn.setStyleSheet(AppStyles.button_success(height="20px",bg_color='#03A9F4',hover_light='#0288D1'))
        self.refresh_signers_btn.clicked.connect(self.load_signers)
        
        self.signers_filter = QLineEdit()
        self.signers_filter.setStyleSheet(AppStyles.input_field())
        self.signers_filter.setPlaceholderText("🔍 Поиск...")
        self.signers_filter.textChanged.connect(self.filter_signers)
        
        control_panel.addWidget(self.add_signer_btn)
        control_panel.addWidget(self.edit_signer_btn)
        control_panel.addWidget(self.delete_signer_btn)
        control_panel.addWidget(self.refresh_signers_btn)
        control_panel.addStretch()
        control_panel.addWidget(QLabel("Фильтр:"))
        control_panel.addWidget(self.signers_filter)
        
        self.signers_table = QTableView()
        self.signers_table.setStyleSheet(AppStyles.table_view())
        self.signers_model = ExecutorsTableModel([], ['ID', 'ФИО'])
        self.signers_table.setModel(self.signers_model)
        self.signers_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.signers_table.selectionModel().selectionChanged.connect(self.on_signer_selection_changed)
        self.signers_table.horizontalHeader().setStretchLastSection(True)
        self.signers_table.setAlternatingRowColors(True)
        
        self.signers_info = QLabel("📊 Загружается...")
        
        layout.addLayout(control_panel)
        layout.addWidget(self.signers_table)
        layout.addWidget(self.signers_info)
        
        tab.setLayout(layout)
        return tab
    def create_responsible_executors_tab(self):
        """Создание вкладки ответственных исполнителей"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Панель управления
        control_panel = QHBoxLayout()
        
        # Кнопки
        self.add_resp_exec_btn = QPushButton("➕ Добавить")
        self.add_resp_exec_btn.setStyleSheet(AppStyles.button_success(height="20px")) 
        self.add_resp_exec_btn.clicked.connect(self.add_responsible_executor)
        
        self.edit_resp_exec_btn = QPushButton("✏️ Редактировать")
        self.edit_resp_exec_btn.setStyleSheet(AppStyles.button_success(height="20px",bg_color='#03A9F4',hover_light='#0288D1')) 
        self.edit_resp_exec_btn.clicked.connect(self.edit_responsible_executor)
        self.edit_resp_exec_btn.setEnabled(False)
        
        self.delete_resp_exec_btn = QPushButton("🗑 Удалить")
        self.delete_resp_exec_btn.setStyleSheet(AppStyles.button_success(height="20px",bg_color='#F44336',hover_light='#D32F2F')) 
        self.delete_resp_exec_btn.clicked.connect(self.delete_responsible_executor)
        self.delete_resp_exec_btn.setEnabled(False)
        
        self.refresh_resp_exec_btn = QPushButton("🔄 Обновить")
        self.refresh_resp_exec_btn.setStyleSheet(AppStyles.button_success(height="20px",bg_color='#03A9F4',hover_light='#0288D1')) 
        self.refresh_resp_exec_btn.clicked.connect(self.load_responsible_executors)
        
        # Фильтр
        self.resp_exec_filter = QLineEdit()
        self.resp_exec_filter.setStyleSheet(AppStyles.input_field())
        self.resp_exec_filter.setPlaceholderText("🔍 Поиск по ФИО...")
        self.resp_exec_filter.textChanged.connect(self.filter_responsible_executors)
        
        self.show_inactive_resp_exec = QCheckBox("Показать неактивных")
        self.show_inactive_resp_exec.setStyleSheet(AppStyles.checkbox_widget())
        self.show_inactive_resp_exec.stateChanged.connect(self.load_responsible_executors)
        
        control_panel.addWidget(self.add_resp_exec_btn)
        control_panel.addWidget(self.edit_resp_exec_btn)
        control_panel.addWidget(self.delete_resp_exec_btn)
        control_panel.addWidget(self.refresh_resp_exec_btn)
        control_panel.addStretch()
        control_panel.addWidget(QLabel("Фильтр:"))
        control_panel.addWidget(self.resp_exec_filter)
        control_panel.addWidget(self.show_inactive_resp_exec)
        
        # Таблица
        self.resp_exec_table = QTableView()
        self.resp_exec_table.setStyleSheet(AppStyles.table_view()) 
        self.resp_exec_model = SimpleReferenceTableModel([], ['ID', 'ФИО', 'Активный'])
        self.resp_exec_table.setModel(self.resp_exec_model)
        self.resp_exec_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.resp_exec_table.selectionModel().selectionChanged.connect(
            self.on_responsible_executor_selection_changed
        )
        self.resp_exec_table.doubleClicked.connect(self.edit_responsible_executor)
        
        # Настройка таблицы
        self.resp_exec_table.horizontalHeader().setStretchLastSection(True)
        self.resp_exec_table.setAlternatingRowColors(True)
        self.resp_exec_table.setSortingEnabled(True)
        
        # Информация
        self.resp_exec_info = QLabel("📊 Загружается...")
        
        layout.addLayout(control_panel)
        layout.addWidget(self.resp_exec_table)
        layout.addWidget(self.resp_exec_info)
        
        tab.setLayout(layout)
        return tab    
    def create_themes_tab(self):
        """Создание вкладки тем"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Панель управления
        control_panel = QHBoxLayout()
        
        # Кнопки
        self.add_theme_btn = QPushButton("➕ Добавить тему")
        self.add_theme_btn.setStyleSheet(AppStyles.button_success(height="20px"))
        self.add_theme_btn.clicked.connect(self.add_theme)
        
        self.edit_theme_btn = QPushButton("✏️ Редактировать")
        self.edit_theme_btn.setStyleSheet(AppStyles.button_success(height="20px",bg_color='#03A9F4',hover_light='#0288D1'))
        self.edit_theme_btn.clicked.connect(self.edit_theme)
        self.edit_theme_btn.setEnabled(False)
        
        self.delete_theme_btn = QPushButton("🗑 Удалить")
        self.delete_theme_btn.setStyleSheet(AppStyles.button_success(height="20px",bg_color='#F44336',hover_light='#D32F2F'))
        self.delete_theme_btn.clicked.connect(self.delete_theme)
        self.delete_theme_btn.setEnabled(False)
        
        self.refresh_themes_btn = QPushButton("🔄 Обновить")
        self.refresh_themes_btn.setStyleSheet(AppStyles.button_success(height="20px",bg_color='#03A9F4',hover_light='#0288D1'))
        self.refresh_themes_btn.clicked.connect(self.load_themes)
        
        # Фильтры
        self.themes_filter = QLineEdit()
        self.themes_filter.setStyleSheet(AppStyles.input_field())
        self.themes_filter.setPlaceholderText("🔍 Поиск по названию или описанию...")
        self.themes_filter.textChanged.connect(self.filter_themes)
        
        self.show_inactive_themes = QCheckBox("Показать неактивные")
        self.show_inactive_themes.setStyleSheet(AppStyles.checkbox_widget())
        self.show_inactive_themes.stateChanged.connect(self.load_themes)
        
        control_panel.addWidget(self.add_theme_btn)
        control_panel.addWidget(self.edit_theme_btn)
        control_panel.addWidget(self.delete_theme_btn)
        control_panel.addWidget(self.refresh_themes_btn)
        control_panel.addStretch()
        control_panel.addWidget(QLabel("Фильтр:"))
        control_panel.addWidget(self.themes_filter)
        control_panel.addWidget(self.show_inactive_themes)
        
        # Таблица тем
        self.themes_table = QTableView()
        self.themes_table.setStyleSheet(AppStyles.table_view()) 
        self.themes_model = ThemesTableModel([], ['ID', 'Название', 'Описание', 'Активная'])
        self.themes_table.setModel(self.themes_model)
        self.themes_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.themes_table.selectionModel().selectionChanged.connect(self.on_theme_selection_changed)
        self.themes_table.doubleClicked.connect(self.edit_theme)
        
        # Настройка таблицы
        self.themes_table.horizontalHeader().setStretchLastSection(True)
        self.themes_table.setAlternatingRowColors(True)
        self.themes_table.setSortingEnabled(True)
        
        # Информация
        self.themes_info = QLabel("📊 Загружается...")
        
        layout.addLayout(control_panel)
        layout.addWidget(self.themes_table)
        layout.addWidget(self.themes_info)
        
        tab.setLayout(layout)
        return tab
    def show_warning(self, title, text):
        """Показать предупреждение со стилем"""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setStyleSheet(AppStyles.message_box())
        
        # Русский текст
        ok_button = msg.button(QMessageBox.Ok)
        ok_button.setText("ОК")
        
        msg.exec_()
    def load_approvers(self):
        """Загрузить согласующих"""
        try:
            query = "SELECT id, name FROM ref_approvers ORDER BY name"
            approvers = self.db_manager.execute_query(query)
            
            table_data = [[a['id'], a['name']] for a in approvers]
            self.approvers_model.update_data(table_data)
            self.approvers_original_data = approvers
            
            self.approvers_info.setText(f"📊 Всего согласующих: {len(approvers)}")
            print(f"✅ Загружено согласующих: {len(approvers)}")
        except Exception as e:
            print(f"❌ Ошибка загрузки согласующих: {e}")
            self.show_warning(self, "Ошибка", f"Не удалось загрузить согласующих: {str(e)}")

    def load_signers(self):
        """Загрузить подписантов"""
        try:
            query = "SELECT id, name FROM ref_signers ORDER BY name"
            signers = self.db_manager.execute_query(query)
            
            table_data = [[s['id'], s['name']] for s in signers]
            self.signers_model.update_data(table_data)
            self.signers_original_data = signers
            
            self.signers_info.setText(f"📊 Всего подписантов: {len(signers)}")
            print(f"✅ Загружено подписантов: {len(signers)}")
        except Exception as e:
            print(f"❌ Ошибка загрузки подписантов: {e}")
            self.show_warning(self, "Ошибка", f"Не удалось загрузить подписантов: {str(e)}")
    def add_approver_from_executors(self):
        """Добавить согласующего из списка активных исполнителей"""
        try:
            # Получаем список активных исполнителей
            active_executors = self.db_manager.get_executors(active_only=True)
            
            if not active_executors:
                QMessageBox.warning(self, "Внимание", "Нет активных исполнителей")
                return
            
            # Создаем диалог
            dialog = QDialog(self)
            dialog.setWindowTitle("Выбор исполнителя для добавления")
            dialog.resize(600, 550)
            
            # Стилизация диалога
            dialog.setStyleSheet(AppStyles.dia())
            
            layout = QVBoxLayout()
            layout.setContentsMargins(20, 20, 20, 20)
            layout.setSpacing(15)
            
            # === ЗАГОЛОВОК ===
            title_label = QLabel("Выберите исполнителя:")
            title_label.setStyleSheet(AppStyles.lable())
            layout.addWidget(title_label)
            
            # === ПОЛЕ ПОИСКА ===
            search_widget = QWidget()
            search_layout = QHBoxLayout()
            search_layout.setContentsMargins(0, 0, 0, 0)
            
            search_label = QLabel("🔍")
            search_label.setStyleSheet(AppStyles.lable())
            
            search_field = QLineEdit()
            search_field.setPlaceholderText("Поиск по ФИО или должности...")
            search_field.setStyleSheet(AppStyles.input_field())
            
            # Кнопка очистки поиска
            clear_search_btn = QPushButton("✕")
            clear_search_btn.setFixedSize(30, 30)
            clear_search_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {AppColors.GRAY_400};
                    color: white;
                    border: none;
                    border-radius: 15px;
                    font-weight: bold;
                    font-size: 12pt;
                }}
                QPushButton:hover {{
                    background: {AppColors.GRAY_600};
                }}
            """)
            clear_search_btn.clicked.connect(lambda: search_field.clear())
            
            search_layout.addWidget(search_label)
            search_layout.addWidget(search_field, 1)
            search_layout.addWidget(clear_search_btn)
            search_widget.setLayout(search_layout)
            
            layout.addWidget(search_widget)
            
            # === СПИСОК ИСПОЛНИТЕЛЕЙ ===
            list_widget = QListWidget()
            list_widget.setStyleSheet(f"""
                QListWidget {{
                    border: 2px solid {AppColors.GRAY_300};
                    border-radius: 6px;
                    background: white;
                    padding: 5px;
                }}
                QListWidget::item {{
                    padding: 10px;
                    border-bottom: 1px solid {AppColors.GRAY_200};
                }}
                QListWidget::item:hover {{
                    background: {AppColors.PRIMARY_LIGHT};
                }}
                QListWidget::item:selected {{
                    background: {AppColors.PRIMARY};
                    color: white;
                }}
            """)
            
            layout.addWidget(list_widget, 1)  # Растягиваем список
            
            # === СЧЕТЧИК ЗАПИСЕЙ (СОЗДАЕМ ДО ФУНКЦИИ populate_list) ===
            count_label = QLabel(f"📊 Всего исполнителей: {len(active_executors)}")
            count_label.setStyleSheet(f"""
                QLabel {{
                    color: {AppColors.TEXT_SECONDARY};
                    font-size: 9pt;
                    padding: 5px;
                }}
            """)
            layout.addWidget(count_label)
            
            # === ПОДСКАЗКА ===
            hint_label = QLabel("💡 Совет: дважды кликните для быстрого выбора")
            hint_label.setStyleSheet(AppStyles.lable())
            layout.addWidget(hint_label)
            
            # ✅ ФУНКЦИЯ ЗАПОЛНЕНИЯ СПИСКА (ТЕПЕРЬ count_label УЖЕ СУЩЕСТВУЕТ)
            def populate_list(filter_text=""):
                """Заполнить список исполнителями с учетом фильтра"""
                list_widget.clear()
                filter_text = filter_text.lower().strip()
                
                visible_count = 0
                for executor in active_executors:
                    name = executor['name']
                    position = executor.get('position', '')
                    department = executor.get('department', '')
                    
                    # Формируем отображаемый текст
                    display_parts = [name]
                    if position:
                        display_parts.append(f"({position})")
                    if department:
                        display_parts.append(f"- {department}")
                    display_text = " ".join(display_parts)
                    
                    # Проверяем соответствие фильтру
                    if not filter_text or \
                    filter_text in (name or "").lower() or \
                    filter_text in (position or "").lower() or \
                    filter_text in (department or "").lower():
                        
                        item = QListWidgetItem(display_text)
                        item.setData(Qt.UserRole, executor['id'])
                        list_widget.addItem(item)
                        visible_count += 1
                
                # Обновляем счетчик
                if filter_text:
                    count_label.setText(f"📊 Найдено: {visible_count} из {len(active_executors)}")
                else:
                    count_label.setText(f"📊 Всего исполнителей: {len(active_executors)}")
            
            # ✅ ПОДКЛЮЧАЕМ ПОИСК
            search_field.textChanged.connect(populate_list)
            
            # Заполняем список первый раз
            populate_list()
            
            # === КНОПКИ ===
            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            
            # Изменяем текст кнопок на русский
            ok_button = buttons.button(QDialogButtonBox.Ok)
            cancel_button = buttons.button(QDialogButtonBox.Cancel)
            
            ok_button.setText("✅ Добавить")
            ok_button.setStyleSheet(AppStyles.button_success())
            
            cancel_button.setText("❌ Отмена")
            cancel_button.setStyleSheet(AppStyles.button_neutral())
            
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            
            layout.addWidget(buttons)
            
            # ✅ ДВОЙНОЙ КЛИК ДЛЯ БЫСТРОГО ВЫБОРА
            list_widget.itemDoubleClicked.connect(dialog.accept)
            
            # ✅ АВТОФОКУС НА ПОИСКЕ
            search_field.setFocus()
            
            dialog.setLayout(layout)
            
            # === ВЫПОЛНЕНИЕ ДИАЛОГА ===
            if dialog.exec_() == QDialog.Accepted:
                selected_item = list_widget.currentItem()
                if not selected_item:
                    QMessageBox.warning(self, "Предупреждение", "Выберите исполнителя из списка")
                    return
                
                executor_id = selected_item.data(Qt.UserRole)
                # Получаем имя исполнителя
                executor = next((e for e in active_executors if e['id'] == executor_id), None)
                if executor:
                    # Добавляем в ref_approvers
                    query = "INSERT INTO ref_approvers (name) VALUES (?)"
                    self.db_manager.execute_update(query, (executor['name'],))
                    
                    QMessageBox.information(
                        self, 
                        "✅ Успех", 
                        f"Согласующий '{executor['name']}' успешно добавлен!"
                    )
                    self.refresh_all_lists()
                    self.references_updated.emit()
                    
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self, 
                "❌ Ошибка", 
                f"Ошибка при добавлении согласующего:\n\n{str(e)}"
            )
    def on_approver_selection_changed(self):
        has_selection = len(self.approvers_table.selectionModel().selectedRows()) > 0
        self.edit_approver_btn.setEnabled(has_selection)
        self.delete_approver_btn.setEnabled(has_selection)

    def on_signer_selection_changed(self):
        has_selection = len(self.signers_table.selectionModel().selectedRows()) > 0
        self.edit_signer_btn.setEnabled(has_selection)
        self.delete_signer_btn.setEnabled(has_selection)

    def filter_approvers(self):
        filter_text = self.approvers_filter.text().lower()
        if not hasattr(self, 'approvers_original_data'):
            return
        
        if not filter_text:
            self.load_approvers()
            return
        
        filtered = [a for a in self.approvers_original_data if filter_text in a['name'].lower()]
        table_data = [[a['id'], a['name']] for a in filtered]
        self.approvers_model.update_data(table_data)

    def filter_signers(self):
        filter_text = self.signers_filter.text().lower()
        if not hasattr(self, 'signers_original_data'):
            return
        
        if not filter_text:
            self.load_signers()
            return
        
        filtered = [s for s in self.signers_original_data if filter_text in s['name'].lower()]
        table_data = [[s['id'], s['name']] for s in filtered]
        self.signers_model.update_data(table_data)
    def add_signer_from_executors(self):
        """Добавить согласующего из списка активных исполнителей"""
        try:
            # Получаем список активных исполнителей
            active_executors = self.db_manager.get_executors(active_only=True)
            
            if not active_executors:
                QMessageBox.warning(self, "Внимание", "Нет активных исполнителей")
                return
            
            # Создаем диалог
            dialog = QDialog(self)
            dialog.setWindowTitle("Выбор исполнителя для добавления в подписанты")
            dialog.resize(600, 550)
            
            # Стилизация диалога
            dialog.setStyleSheet(AppStyles.dia())
            
            layout = QVBoxLayout()
            layout.setContentsMargins(20, 20, 20, 20)
            layout.setSpacing(15)
            
            # === ЗАГОЛОВОК ===
            title_label = QLabel("Выберите исполнителя:")
            title_label.setStyleSheet(AppStyles.lable())
            layout.addWidget(title_label)
            
            # === ПОЛЕ ПОИСКА ===
            search_widget = QWidget()
            search_layout = QHBoxLayout()
            search_layout.setContentsMargins(0, 0, 0, 0)
            
            search_label = QLabel("🔍")
            search_label.setStyleSheet(AppStyles.lable())
            
            search_field = QLineEdit()
            search_field.setPlaceholderText("Поиск по ФИО или должности...")
            search_field.setStyleSheet(AppStyles.input_field())
            
            # Кнопка очистки поиска
            clear_search_btn = QPushButton("✕")
            clear_search_btn.setFixedSize(30, 30)
            clear_search_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {AppColors.GRAY_400};
                    color: white;
                    border: none;
                    border-radius: 15px;
                    font-weight: bold;
                    font-size: 12pt;
                }}
                QPushButton:hover {{
                    background: {AppColors.GRAY_600};
                }}
            """)
            clear_search_btn.clicked.connect(lambda: search_field.clear())
            
            search_layout.addWidget(search_label)
            search_layout.addWidget(search_field, 1)
            search_layout.addWidget(clear_search_btn)
            search_widget.setLayout(search_layout)
            
            layout.addWidget(search_widget)
            
            # === СПИСОК ИСПОЛНИТЕЛЕЙ ===
            list_widget = QListWidget()
            list_widget.setStyleSheet(f"""
                QListWidget {{
                    border: 2px solid {AppColors.GRAY_300};
                    border-radius: 6px;
                    background: white;
                    padding: 5px;
                }}
                QListWidget::item {{
                    padding: 10px;
                    border-bottom: 1px solid {AppColors.GRAY_200};
                }}
                QListWidget::item:hover {{
                    background: {AppColors.PRIMARY_LIGHT};
                }}
                QListWidget::item:selected {{
                    background: {AppColors.PRIMARY};
                    color: white;
                }}
            """)
            
            layout.addWidget(list_widget, 1)  # Растягиваем список
            
            # === СЧЕТЧИК ЗАПИСЕЙ (СОЗДАЕМ ДО ФУНКЦИИ populate_list) ===
            count_label = QLabel(f"📊 Всего исполнителей: {len(active_executors)}")
            count_label.setStyleSheet(f"""
                QLabel {{
                    color: {AppColors.TEXT_SECONDARY};
                    font-size: 9pt;
                    padding: 5px;
                }}
            """)
            layout.addWidget(count_label)
            
            # === ПОДСКАЗКА ===
            hint_label = QLabel("💡 Совет: дважды кликните для быстрого выбора")
            hint_label.setStyleSheet(AppStyles.lable())
            layout.addWidget(hint_label)
            
            # ✅ ФУНКЦИЯ ЗАПОЛНЕНИЯ СПИСКА (ТЕПЕРЬ count_label УЖЕ СУЩЕСТВУЕТ)
            def populate_list(filter_text=""):
                """Заполнить список исполнителями с учетом фильтра"""
                list_widget.clear()
                filter_text = filter_text.lower().strip()
                
                visible_count = 0
                for executor in active_executors:
                    name = executor['name']
                    position = executor.get('position', '')
                    department = executor.get('department', '')
                    
                    # Формируем отображаемый текст
                    display_parts = [name]
                    if position:
                        display_parts.append(f"({position})")
                    if department:
                        display_parts.append(f"- {department}")
                    display_text = " ".join(display_parts)
                    
                    # Проверяем соответствие фильтру
                    if not filter_text or \
                    filter_text in (name or "").lower() or \
                    filter_text in (position or "").lower() or \
                    filter_text in (department or "").lower():
                        
                        item = QListWidgetItem(display_text)
                        item.setData(Qt.UserRole, executor['id'])
                        list_widget.addItem(item)
                        visible_count += 1
                
                # Обновляем счетчик
                if filter_text:
                    count_label.setText(f"📊 Найдено: {visible_count} из {len(active_executors)}")
                else:
                    count_label.setText(f"📊 Всего исполнителей: {len(active_executors)}")
            
            # ✅ ПОДКЛЮЧАЕМ ПОИСК
            search_field.textChanged.connect(populate_list)
            
            # Заполняем список первый раз
            populate_list()
            
            # === КНОПКИ ===
            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            
            # Изменяем текст кнопок на русский
            ok_button = buttons.button(QDialogButtonBox.Ok)
            cancel_button = buttons.button(QDialogButtonBox.Cancel)
            
            ok_button.setText("✅ Добавить")
            ok_button.setStyleSheet(AppStyles.button_success())
            
            cancel_button.setText("❌ Отмена")
            cancel_button.setStyleSheet(AppStyles.button_neutral())
            
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            
            layout.addWidget(buttons)
            
            # ✅ ДВОЙНОЙ КЛИК ДЛЯ БЫСТРОГО ВЫБОРА
            list_widget.itemDoubleClicked.connect(dialog.accept)
            
            # ✅ АВТОФОКУС НА ПОИСКЕ
            search_field.setFocus()
            
            dialog.setLayout(layout)
            
            # === ВЫПОЛНЕНИЕ ДИАЛОГА ===
            if dialog.exec_() == QDialog.Accepted:
                selected_item = list_widget.currentItem()
                if not selected_item:
                    QMessageBox.warning(self, "Предупреждение", "Выберите исполнителя из списка")
                    return
                
                executor_id = selected_item.data(Qt.UserRole)
                # Получаем имя исполнителя
                executor = next((e for e in active_executors if e['id'] == executor_id), None)
                if executor:
                    # Добавляем в ref_approvers
                    query = "INSERT INTO ref_signers (name) VALUES (?)"
                    self.db_manager.execute_update(query, (executor['name'],))
                    
                    QMessageBox.information(
                        self, 
                        "✅ Успех", 
                        f"Подписант '{executor['name']}' успешно добавлен!"
                    )
                    self.refresh_all_lists()
                    self.references_updated.emit()
                    
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self, 
                "❌ Ошибка", 
                f"Ошибка при добавлении согласующего:\n\n{str(e)}"
            )
    def create_bottom_panel(self):
        """Создание нижней панели"""
        layout = QHBoxLayout()
        
        # Общая статистика
        self.general_stats = QLabel("📊 Статистика загружается...")
        
        # Кнопка закрытия
        close_btn = QPushButton("✖️ Закрыть")
        close_btn.setStyleSheet(AppStyles.button_success()) 
        close_btn.clicked.connect(self.close)
        
        layout.addWidget(self.general_stats)
        layout.addStretch()
        layout.addWidget(close_btn)
        
        return layout
    
    # === МЕТОДЫ ЗАГРУЗКИ ДАННЫХ ===
    
    def load_all_data(self):
        """Загрузить все данные"""
        self.load_executors()
        self.load_themes()
        self.load_responsible_executors()  
        self.load_published_where()        
        self.load_approvers()  
        self.load_signers() 
        self.update_general_stats()
        self.load_simple_reference('ref_status')
        self.load_simple_reference('ref_document_types')
        self.load_simple_reference('ref_signing_types')
        self.load_simple_reference('ref_document_kinds')
    
    def load_executors(self):
        "Загрузить исполнителей"
        try:
            active_only = not self.show_inactive_executors.isChecked()
            
            if active_only:
                query = "SELECT * FROM ref_executors WHERE is_active = 1 ORDER BY name"
                executors = self.db_manager.execute_query(query)
            else:
                query = "SELECT * FROM ref_executors ORDER BY name"
                executors = self.db_manager.execute_query(query)
            
            # Преобразуем в формат таблицы
            table_data = []
            for executor in executors:
                # Явно получаем is_active, обрабатываем NULL как неактивный
                is_active = executor.get('is_active')
                is_active_bool = bool(is_active) if is_active is not None else False
                
                table_data.append([
                    executor.get('id'),
                    executor.get('name', ''),
                    executor.get('position', ''),
                    executor.get('department', ''),
                    '✅' if is_active_bool else '❌'
                ])
            
            self.executors_model.update_data(table_data)
            self.executors_original_data = executors
            
            # Обновляем информацию
            active_count = sum(1 for e in executors if e.get('is_active'))
            inactive_count = len(executors) - active_count
            self.executors_info.setText(
                f"📊 Всего исполнителей: {len(executors)} | "
                f"Активных: {active_count} | "
                f"Неактивных: {inactive_count}"
            )
            
            print(f"✅ Загружено исполнителей: {len(executors)}")
            
        except Exception as e:
            print(f"❌ Ошибка загрузки исполнителей: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить исполнителей: {str(e)}")
    
    def load_themes(self):
        "Загрузить темы"
        try:
            active_only = not self.show_inactive_themes.isChecked()
            
            if active_only:
                query = "SELECT * FROM ref_themes WHERE is_active = 1 ORDER BY name"
                themes = self.db_manager.execute_query(query)
            else:
                query = "SELECT * FROM ref_themes ORDER BY name"
                themes = self.db_manager.execute_query(query)
            
            # Преобразуем в формат таблицы
            table_data = []
            for theme in themes:
                # Явно получаем is_active, обрабатываем NULL как неактивный
                is_active = theme.get('is_active')
                is_active_bool = bool(is_active) if is_active is not None else False
                
                table_data.append([
                    theme.get('id'),
                    theme.get('name', ''),
                    theme.get('description', ''),
                    '✅' if is_active_bool else '❌'
                ])
            
            self.themes_model.update_data(table_data)
            self.themes_original_data = themes
            
            # Обновляем информацию
            active_count = sum(1 for t in themes if t.get('is_active'))
            inactive_count = len(themes) - active_count
            self.themes_info.setText(
                f"📊 Всего тем: {len(themes)} | "
                f"Активных: {active_count} | "
                f"Неактивных: {inactive_count}"
            )
            
            print(f"✅ Загружено тем: {len(themes)}")
            
        except Exception as e:
            print(f"❌ Ошибка загрузки тем: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить темы: {str(e)}")
    
    def update_general_stats(self):
        "Обновить общую статистику"
        try:
            stats = self.db_manager.get_documents_statistics()
            total_docs = stats.get('total_documents', 0)
            
            executors_count = len(getattr(self, 'executors_original_data', []))
            themes_count = len(getattr(self, 'themes_original_data', []))
            approvers_count = len(getattr(self, 'approvers_original_data', []))  # ← ДОБАВЛЕНО
            signers_count = len(getattr(self, 'signers_original_data', []))      # ← ДОБАВЛЕНО
            resp_exec_count = len(getattr(self, 'resp_exec_original_data', []))
            pub_where_count = len(getattr(self, 'pub_where_original_data', []))
            
            self.general_stats.setText(
                f"📊 База данных: {total_docs} документов | "
                f"Исполнители: {executors_count} | "
                f"Темы: {themes_count} | "
                f"Согласующие: {approvers_count} | "
                f"Подписанты: {signers_count} | "
                f"Отв. исполнители: {resp_exec_count} | "
                f"Места публикации: {pub_where_count} | "
                f"Статусы: {len(getattr(self, 'ref_status_original_data', []))} | "
                f"Типы док.: {len(getattr(self, 'ref_document_types_original_data', []))} | "
                f"Типы подпис.: {len(getattr(self, 'ref_signing_types_original_data', []))} | "
                f"Виды док.: {len(getattr(self, 'ref_document_kinds_original_data', []))}"
            )
        except Exception as e:
            print(f"❌ Ошибка обновления статистики: {e}")
    
    # === ФИЛЬТРАЦИЯ ===
    
    def filter_executors(self):
        "Фильтрация исполнителей"
        filter_text = self.executors_filter.text().lower()
        
        if not filter_text:
            # Если фильтр пустой - просто перезагружаем с учетом чекбокса
            self.load_executors()
            return
        
        if not hasattr(self, 'executors_original_data'):
            return
        
        # Фильтруем с учетом чекбокса активности
        active_only = not self.show_inactive_executors.isChecked()
        
        filtered_executors = []
        for executor in self.executors_original_data:
            # Проверяем активность
            if active_only and not executor.get('is_active'):
                continue
            
            # Проверяем текстовый фильтр
            name = (executor.get('name') or '').lower()
            position = (executor.get('position') or '').lower()
            department = (executor.get('department') or '').lower()
            
            if (filter_text in name or filter_text in position or filter_text in department):
                filtered_executors.append(executor)
        
        # Обновляем таблицу
        table_data = []
        for executor in filtered_executors:
            is_active = executor.get('is_active')
            is_active_bool = bool(is_active) if is_active is not None else False
            
            table_data.append([
                executor.get('id'),
                executor.get('name', ''),
                executor.get('position', ''),
                executor.get('department', ''),
                '✅' if is_active_bool else '❌'
            ])
        
        self.executors_model.update_data(table_data)
    
    def filter_themes(self):
        "Фильтрация тем"
        filter_text = self.themes_filter.text().lower()
        
        if not filter_text:
            # Если фильтр пустой - просто перезагружаем с учетом чекбокса
            self.load_themes()
            return
        
        if not hasattr(self, 'themes_original_data'):
            return
        
        # Фильтруем с учетом чекбокса активности
        active_only = not self.show_inactive_themes.isChecked()
        
        filtered_themes = []
        for theme in self.themes_original_data:
            # Проверяем активность
            if active_only and not theme.get('is_active'):
                continue
            
            # Проверяем текстовый фильтр
            name = theme.get('name', '').lower()
            description = theme.get('description', '').lower()
            
            if filter_text in name or filter_text in description:
                filtered_themes.append(theme)
        
        # Обновляем таблицу
        table_data = []
        for theme in filtered_themes:
            is_active = theme.get('is_active')
            is_active_bool = bool(is_active) if is_active is not None else False
            
            table_data.append([
                theme.get('id'),
                theme.get('name', ''),
                theme.get('description', ''),
                '✅' if is_active_bool else '❌'
            ])
        
        self.themes_model.update_data(table_data)
    
    # === ОБРАБОТЧИКИ СОБЫТИЙ ===
    def refresh_all_lists(self):
        "Обновить все списки справочников"
        try:
            self.load_executors()
            self.load_themes()
            if hasattr(self, 'load_approvers'):
                self.load_approvers()
            if hasattr(self, 'load_signers'):
                self.load_signers()
            if hasattr(self, 'load_responsible_executors'):  
                self.load_responsible_executors()
            if hasattr(self, 'load_published_where'):        
                self.load_published_where()
            self.update_general_stats()
        except Exception as e:
            print(f"❌ Ошибка обновления списков: {e}")
    def on_executor_selection_changed(self):
        """Обработчик изменения выбора исполнителя"""
        has_selection = len(self.executors_table.selectionModel().selectedRows()) > 0
        self.edit_executor_btn.setEnabled(has_selection)
        self.delete_executor_btn.setEnabled(has_selection)
    
    def on_theme_selection_changed(self):
        """Обработчик изменения выбора темы"""
        has_selection = len(self.themes_table.selectionModel().selectedRows()) > 0
        self.edit_theme_btn.setEnabled(has_selection)
        self.delete_theme_btn.setEnabled(has_selection)
    
    # === CRUD ОПЕРАЦИИ ИСПОЛНИТЕЛЕЙ ===
    
    def add_executor(self):
        """Добавить исполнителя"""
        dialog = ExecutorEditDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            if dialog.validate():
                data = dialog.get_data()
                try:
                    executor_id = self.db_manager.add_executor(
                        data['name'], 
                        data['position'], 
                        data['department'],
                        data['is_active']
                    )
                    
                    if executor_id:
                        QMessageBox.information(self, "Успех", f"Исполнитель '{data['name']}' добавлен!")
                        self.refresh_all_lists()
                        self.update_general_stats()
                        self.references_updated.emit()
                    else:
                        QMessageBox.warning(self, "Ошибка", "Не удалось добавить исполнителя")
                        
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", f"Ошибка при добавлении: {str(e)}")
    def load_approvers(self):
        "Загрузить согласующих"
        try:
            query = """SELECT id, name FROM ref_approvers ORDER BY name"""
            approvers = self.db_manager.execute_query(query)
            
            table_data = [[a['id'], a['name']] for a in approvers]
            self.approvers_model.update_data(table_data)
            self.approvers_original_data = approvers
            
            self.approvers_info.setText(f"📊 Всего согласующих: {len(approvers)}")
            print(f"✅ Загружено согласующих: {len(approvers)}")
        except Exception as e:
            print(f"❌ Ошибка загрузки согласующих: {e}")
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить согласующих: {str(e)}")
    
    def load_signers(self):
        "Загрузить подписантов"
        try:
            query = "SELECT id, name FROM ref_signers ORDER BY name"
            signers = self.db_manager.execute_query(query)
            
            table_data = [[s['id'], s['name']] for s in signers]
            self.signers_model.update_data(table_data)
            self.signers_original_data = signers
            
            self.signers_info.setText(f"📊 Всего подписантов: {len(signers)}")
            print(f"✅ Загружено подписантов: {len(signers)}")
        except Exception as e:
            print(f"❌ Ошибка загрузки подписантов: {e}")
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить подписантов: {str(e)}")
    def filter_responsible_executors(self):
        """Фильтрация ответственных исполнителей"""
        filter_text = self.resp_exec_filter.text().lower()
        
        if not filter_text:
            self.load_responsible_executors()
            return
        
        if not hasattr(self, 'resp_exec_original_data'):
            return
        
        active_only = not self.show_inactive_resp_exec.isChecked()
        
        filtered = []
        for executor in self.resp_exec_original_data:
            if active_only and not executor.get('is_active'):
                continue
            
            name = executor.get('name', '').lower()
            if filter_text in name:
                filtered.append(executor)
        
        table_data = []
        for executor in filtered:
            is_active = executor.get('is_active')
            is_active_bool = bool(is_active) if is_active is not None else False
            
            table_data.append([
                executor.get('id'),
                executor.get('name', ''),
                '✅' if is_active_bool else '❌'
            ])
        
        self.resp_exec_model.update_data(table_data)

    def filter_published_where(self):
        """Фильтрация мест публикации"""
        filter_text = self.pub_where_filter.text().lower()
        
        if not filter_text:
            self.load_published_where()
            return
        
        if not hasattr(self, 'pub_where_original_data'):
            return
        
        filtered = [item for item in self.pub_where_original_data 
                    if filter_text in item['name'].lower()]
        table_data = [[item['id'], item['name']] for item in filtered]
        self.pub_where_model.update_data(table_data)
    def on_responsible_executor_selection_changed(self):
        """Обработчик изменения выбора ответственного исполнителя"""
        has_selection = len(self.resp_exec_table.selectionModel().selectedRows()) > 0
        self.edit_resp_exec_btn.setEnabled(has_selection)
        self.delete_resp_exec_btn.setEnabled(has_selection)

    def on_published_where_selection_changed(self):
        """Обработчик изменения выбора места публикации"""
        has_selection = len(self.pub_where_table.selectionModel().selectedRows()) > 0
        self.edit_pub_where_btn.setEnabled(has_selection)
        self.delete_pub_where_btn.setEnabled(has_selection)
    def load_responsible_executors(self):
        """Загрузить ответственных исполнителей"""
        try:
            active_only = not self.show_inactive_resp_exec.isChecked()
            executors = self.db_manager.get_responsible_executors(active_only)
            
            table_data = []
            for executor in executors:
                is_active = executor.get('is_active')
                is_active_bool = bool(is_active) if is_active is not None else False
                
                table_data.append([
                    executor.get('id'),
                    executor.get('name', ''),
                    '✅' if is_active_bool else '❌'
                ])
            
            self.resp_exec_model.update_data(table_data)
            self.resp_exec_original_data = executors
            
            active_count = sum(1 for e in executors if e.get('is_active'))
            inactive_count = len(executors) - active_count
            self.resp_exec_info.setText(
                f"📊 Всего: {len(executors)} | "
                f"Активных: {active_count} | "
                f"Неактивных: {inactive_count}"
            )
            
            print(f"✅ Загружено ответственных исполнителей: {len(executors)}")
            
        except Exception as e:
            print(f"❌ Ошибка загрузки ответственных исполнителей: {e}")
            QMessageBox.warning(self, "Ошибка", 
                                f"Не удалось загрузить ответственных исполнителей: {str(e)}")

    def load_published_where(self):
        """Загрузить места публикации"""
        try:
            items = self.db_manager.get_published_where()
            
            table_data = [[item['id'], item['name']] for item in items]
            self.pub_where_model.update_data(table_data)
            self.pub_where_original_data = items
            
            self.pub_where_info.setText(f"📊 Всего мест публикации: {len(items)}")
            print(f"✅ Загружено мест публикации: {len(items)}")
            
        except Exception as e:
            print(f"❌ Ошибка загрузки мест публикации: {e}")
            QMessageBox.warning(self, "Ошибка", 
                                f"Не удалось загрузить места публикации: {str(e)}")
    def edit_executor(self):
        """Редактировать исполнителя"""
        selected_rows = self.executors_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        executor_id = self.executors_model._data[row][0]
        
        # Найдем полные данные исполнителя
        executor_data = None
        for executor in getattr(self, 'executors_original_data', []):
            if executor.get('id') == executor_id:
                executor_data = executor
                break
        
        if not executor_data:
            QMessageBox.warning(self, "Ошибка", "Не удалось найти данные исполнителя")
            return
        
        dialog = ExecutorEditDialog(self, executor_data)
        if dialog.exec_() == QDialog.Accepted:
            if dialog.validate():
                data = dialog.get_data()
                try:
                    # Обновляем через прямой SQL запрос
                    query = """
                        UPDATE ref_executors 
                        SET name = ?, position = ?, department = ?, is_active = ?
                        WHERE id = ?
                    """
                    self.db_manager.execute_update(query, [
                        data['name'], data['position'], data['department'],
                        data['is_active'], executor_id
                    ])
                    
                    QMessageBox.information(self, "Успех", f"Исполнитель '{data['name']}' обновлен!")
                    self.load_executors()
                    self.update_general_stats()
                    self.references_updated.emit()
                    
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", f"Ошибка при обновлении: {str(e)}")
    
    def delete_executor(self):
        """Удалить (деактивировать) исполнителя"""
        selected_rows = self.executors_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        executor_id = self.executors_model._data[row][0]
        executor_name = self.executors_model._data[row][1]
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Деактивировать исполнителя '{executor_name}'?\n\n"
            "Исполнитель станет неактивным, но не будет удален из базы.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.db_manager.deactivate_executor(executor_id)
                QMessageBox.information(self, "Успех", f"Исполнитель '{executor_name}' деактивирован!")
                self.load_executors()
                self.update_general_stats()
                self.references_updated.emit()
                
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка при деактивации: {str(e)}")
    
    # === CRUD ОПЕРАЦИИ ТЕМ ===
    
    def add_theme(self):
        """Добавить тему"""
        dialog = ThemeEditDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            if dialog.validate():
                data = dialog.get_data()
                try:
                    theme_id = self.db_manager.add_theme(
                        data['name'], 
                        data['description'],
                        data['is_active']
                    )
                    
                    if theme_id:
                        QMessageBox.information(self, "Успех", f"Тема '{data['name']}' добавлена!")
                        self.refresh_all_lists()
                        self.update_general_stats()
                        self.references_updated.emit()
                    else:
                        QMessageBox.warning(self, "Ошибка", "Не удалось добавить тему")
                        
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", f"Ошибка при добавлении: {str(e)}")
        # === CRUD ОПЕРАЦИИ ОТВЕТСТВЕННЫХ ИСПОЛНИТЕЛЕЙ ===

    def add_responsible_executor(self):
        """Добавить ответственного исполнителя"""
        dialog = ResponsibleExecutorEditDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            if dialog.validate():
                data = dialog.get_data()
                try:
                    executor_id = self.db_manager.add_responsible_executor(
                        data['name'], 
                        data['is_active']
                    )
                    
                    if executor_id:
                        QMessageBox.information(self, "Успех", 
                            f"Ответственный исполнитель '{data['name']}' добавлен!")
                        self.load_responsible_executors()
                        self.update_general_stats()
                        self.references_updated.emit()
                    else:
                        QMessageBox.warning(self, "Ошибка", 
                            "Не удалось добавить ответственного исполнителя")
                        
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", 
                        f"Ошибка при добавлении: {str(e)}")

    def edit_responsible_executor(self):
        """Редактировать ответственного исполнителя"""
        selected_rows = self.resp_exec_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        executor_id = self.resp_exec_model._data[row][0]
        
        # Найдем полные данные
        executor_data = None
        for executor in getattr(self, 'resp_exec_original_data', []):
            if executor.get('id') == executor_id:
                executor_data = executor
                break
        
        if not executor_data:
            QMessageBox.warning(self, "Ошибка", 
                "Не удалось найти данные ответственного исполнителя")
            return
        
        dialog = ResponsibleExecutorEditDialog(self, executor_data)
        if dialog.exec_() == QDialog.Accepted:
            if dialog.validate():
                data = dialog.get_data()
                try:
                    self.db_manager.update_responsible_executor(
                        executor_id, data['name'], data['is_active']
                    )
                    
                    QMessageBox.information(self, "Успех", 
                        f"Ответственный исполнитель '{data['name']}' обновлен!")
                    self.load_responsible_executors()
                    self.update_general_stats()
                    self.references_updated.emit()
                    
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", 
                        f"Ошибка при обновлении: {str(e)}")
        # === CRUD ОПЕРАЦИИ МЕСТ ПУБЛИКАЦИИ ===

    def add_published_where(self):
        """Добавить место публикации"""
        dialog = PublishedWhereEditDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            if dialog.validate():
                data = dialog.get_data()
                try:
                    item_id = self.db_manager.add_published_where(data['name'])
                    
                    if item_id:
                        QMessageBox.information(self, "Успех", 
                            f"Место публикации '{data['name']}' добавлено!")
                        self.load_published_where()
                        self.update_general_stats()
                        self.references_updated.emit()
                    else:
                        QMessageBox.warning(self, "Ошибка", 
                            "Не удалось добавить место публикации")
                        
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", 
                        f"Ошибка при добавлении: {str(e)}")

    def edit_published_where(self):
        """Редактировать место публикации"""
        selected_rows = self.pub_where_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        item_id = self.pub_where_model._data[row][0]
        
        # Найдем полные данные
        item_data = None
        for item in getattr(self, 'pub_where_original_data', []):
            if item.get('id') == item_id:
                item_data = item
                break
        
        if not item_data:
            QMessageBox.warning(self, "Ошибка", 
                "Не удалось найти данные места публикации")
            return
        
        dialog = PublishedWhereEditDialog(self, item_data)
        if dialog.exec_() == QDialog.Accepted:
            if dialog.validate():
                data = dialog.get_data()
                try:
                    self.db_manager.update_published_where(item_id, data['name'])
                    
                    QMessageBox.information(self, "Успех", 
                        f"Место публикации '{data['name']}' обновлено!")
                    self.load_published_where()
                    self.update_general_stats()
                    self.references_updated.emit()
                    
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", 
                        f"Ошибка при обновлении: {str(e)}")

    def delete_published_where(self):
        """Удалить место публикации"""
        selected_rows = self.pub_where_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        item_id = self.pub_where_model._data[row][0]
        item_name = self.pub_where_model._data[row][1]
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить место публикации '{item_name}'?\n\n"
            "Внимание: если это место используется в документах, удаление будет невозможно!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.db_manager.delete_published_where(item_id)
                QMessageBox.information(self, "Успех", 
                    f"Место публикации '{item_name}' удалено!")
                self.load_published_where()
                self.update_general_stats()
                self.references_updated.emit()
                
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", 
                    f"Ошибка при удалении: {str(e)}")
    def delete_responsible_executor(self):
        """Удалить (деактивировать) ответственного исполнителя"""
        selected_rows = self.resp_exec_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        executor_id = self.resp_exec_model._data[row][0]
        executor_name = self.resp_exec_model._data[row][1]
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Деактивировать ответственного исполнителя '{executor_name}'?\n\n"
            "Исполнитель станет неактивным, но не будет удален из базы.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.db_manager.deactivate_responsible_executor(executor_id)
                QMessageBox.information(self, "Успех", 
                    f"Ответственный исполнитель '{executor_name}' деактивирован!")
                self.load_responsible_executors()
                self.update_general_stats()
                self.references_updated.emit()
                
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", 
                    f"Ошибка при деактивации: {str(e)}")
    def edit_theme(self):
        """Редактировать тему"""
        selected_rows = self.themes_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        theme_id = self.themes_model._data[row][0]
        
        # Найдем полные данные темы
        theme_data = None
        for theme in getattr(self, 'themes_original_data', []):
            if theme.get('id') == theme_id:
                theme_data = theme
                break
        
        if not theme_data:
            QMessageBox.warning(self, "Ошибка", "Не удалось найти данные темы")
            return
        
        dialog = ThemeEditDialog(self, theme_data)
        if dialog.exec_() == QDialog.Accepted:
            if dialog.validate():
                data = dialog.get_data()
                try:
                    # Обновляем через прямой SQL запрос
                    query = """
                        UPDATE ref_themes 
                        SET name = ?, description = ?, is_active = ?
                        WHERE id = ?
                    """
                    self.db_manager.execute_update(query, [
                        data['name'], data['description'], data['is_active'], theme_id
                    ])
                    
                    QMessageBox.information(self, "Успех", f"Тема '{data['name']}' обновлена!")
                    self.refresh_all_lists()
                    self.update_general_stats()
                    self.references_updated.emit()
                    
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", f"Ошибка при обновлении: {str(e)}")
    
    def delete_theme(self):
        """Удалить (деактивировать) тему"""
        selected_rows = self.themes_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        theme_id = self.themes_model._data[row][0]
        theme_name = self.themes_model._data[row][1]
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Деактивировать тему '{theme_name}'?\n\n"
            "Тема станет неактивной, но не будет удалена из базы.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.db_manager.deactivate_theme(theme_id)
                QMessageBox.information(self, "Успех", f"Тема '{theme_name}' деактивирована!")
                self.refresh_all_lists()
                self.update_general_stats()
                self.references_updated.emit()
                
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка при деактивации: {str(e)}")
    def delete_approver(self):
        "Удалить согласующего"
        selected_rows = self.approvers_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        approver_id = self.approvers_model._data[row][0]
        approver_name = self.approvers_model._data[row][1]
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить согласующего '{approver_name}'?"
            "Внимание: это также удалит все связи с документами!",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # Сначала удаляем связи с документами
                self.db_manager.execute_update(
                    "DELETE FROM document_approvers WHERE approver_id = ?", 
                    (approver_id,)
                )
                
                # Затем удаляем самого согласующего
                query = "DELETE FROM ref_approvers WHERE id = ?"
                self.db_manager.execute_update(query, (approver_id,))
                
                QMessageBox.information(self, "Успех", 
                    f"Согласующий '{approver_name}' удален!")
                self.load_approvers()
                self.update_general_stats()
                self.references_updated.emit()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка при удалении: {str(e)}")
    
    def delete_signer(self):
        "Удалить подписанта"
        selected_rows = self.signers_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        signer_id = self.signers_model._data[row][0]
        signer_name = self.signers_model._data[row][1]
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить согласующего '{signer_name}'?"
            "Внимание: это также удалит все связи с документами!",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # Сначала удаляем связи с документами
                self.db_manager.execute_update(
                    "DELETE FROM document_signers WHERE signer_id = ?", 
                    (signer_id,)
                )
                
                # Затем удаляем самого подписанта
                query = "DELETE FROM ref_signers WHERE id = ?"
                self.db_manager.execute_update(query, (signer_id,))
                
                QMessageBox.information(self, "Успех", 
                    f"Подписант '{signer_name}' удален!")
                self.load_signers()
                self.update_general_stats()
                self.references_updated.emit()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка при удалении: {str(e)}")
    def edit_approver(self):
        "Редактировать согласующего"
        selected_rows = self.approvers_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        approver_id = self.approvers_model._data[row][0]
        approver_name = self.approvers_model._data[row][1]
        
        new_name, ok = QInputDialog.getText(
            self, "Редактирование согласующего", 
            "ФИО:", QLineEdit.Normal, approver_name
        )
        
        if ok and new_name.strip() and new_name.strip() != approver_name:
            try:
                query = """UPDATE ref_approvers SET name = ? WHERE id = ?"""
                self.db_manager.execute_update(query, (new_name.strip(), approver_id))
                QMessageBox.information(self, "Успех", 
                    f"Согласующий обновлен: '{approver_name}' → '{new_name.strip()}'")
                self.refresh_all_lists()
                self.references_updated.emit()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка при обновлении: {str(e)}")
    
    def edit_signer(self):
        "Редактировать подписанта"
        selected_rows = self.signers_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        signer_id = self.signers_model._data[row][0]
        signer_name = self.signers_model._data[row][1]
        
        new_name, ok = QInputDialog.getText(
            self, "Редактирование подписанта", 
            "ФИО:", QLineEdit.Normal, signer_name
        )
        
        if ok and new_name.strip() and new_name.strip() != signer_name:
            try:
                query = "UPDATE ref_signers SET name = ? WHERE id = ?"
                self.db_manager.execute_update(query, (new_name.strip(), signer_id))
                QMessageBox.information(self, "Успех", 
                    f"Подписант обновлен: '{signer_name}' → '{new_name.strip()}'")
                self.load_signers()
                self.references_updated.emit()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка при обновлении: {str(e)}")
    
    def closeEvent(self, event):
        """Обработчик закрытия окна"""
        # Можно добавить сохранение настроек фильтров и т.д.
        event.accept()
    def create_simple_reference_tab(self, table_name: str, foreign_key: str, 
                                    title: str, icon: str):
        """
        Создание вкладки для простого справочника
        
        Args:
            table_name: Название таблицы (ref_status, ref_document_types и т.д.)
            foreign_key: Поле FK в таблице documents (status_id, type_id и т.д.)
            title: Название справочника для отображения
            icon: Эмодзи-иконка
        """
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Панель управления
        control_panel = QHBoxLayout()
        
        # Кнопки
        add_btn = QPushButton(f"➕ Добавить")
        add_btn.setStyleSheet(AppStyles.button_success(height="20px")) 
        add_btn.clicked.connect(lambda: self.add_simple_reference(table_name, title))
        
        edit_btn = QPushButton("✏️ Редактировать")
        edit_btn.setStyleSheet(AppStyles.button_success(height="20px",bg_color='#03A9F4',hover_light='#0288D1')) 
        edit_btn.clicked.connect(lambda: self.edit_simple_reference(table_name, title))
        edit_btn.setEnabled(False)
        
        delete_btn = QPushButton("🗑 Удалить")
        delete_btn.setStyleSheet(AppStyles.button_success(height="20px",bg_color='#F44336',hover_light='#D32F2F')) 
        delete_btn.clicked.connect(lambda: self.delete_simple_reference(
            table_name, foreign_key, title))
        delete_btn.setEnabled(False)
        
        refresh_btn = QPushButton("🔄 Обновить")
        refresh_btn.setStyleSheet(AppStyles.button_success(height="20px",bg_color='#03A9F4',hover_light='#0288D1')) 
        refresh_btn.clicked.connect(lambda: self.load_simple_reference(table_name))
        
        # Фильтр
        filter_field = QLineEdit()
        filter_field.setStyleSheet(AppStyles.input_field())
        filter_field.setPlaceholderText("🔍 Поиск...")
        filter_field.textChanged.connect(
            lambda text: self.filter_simple_reference(table_name, text))
        
        control_panel.addWidget(add_btn)
        control_panel.addWidget(edit_btn)
        control_panel.addWidget(delete_btn)
        control_panel.addWidget(refresh_btn)
        control_panel.addStretch()
        control_panel.addWidget(QLabel("Фильтр:"))
        control_panel.addWidget(filter_field)
        
        # Таблица
        table = QTableView()
        table.setStyleSheet(AppStyles.table_view())
        model = SimpleReferenceTableModel([], ['ID', 'Название'])
        table.setModel(model)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.selectionModel().selectionChanged.connect(
            lambda: self.on_simple_reference_selection_changed(
                table, edit_btn, delete_btn))
        table.doubleClicked.connect(lambda: self.edit_simple_reference(table_name, title))
        
        # Настройка таблицы
        table.horizontalHeader().setStretchLastSection(True)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(True)
        
        # Информация
        info_label = QLabel(f"{icon} Загружается...")
        
        layout.addLayout(control_panel)
        layout.addWidget(table)
        layout.addWidget(info_label)
        
        # Сохраняем ссылки для доступа
        setattr(self, f'{table_name}_table', table)
        setattr(self, f'{table_name}_model', model)
        setattr(self, f'{table_name}_info', info_label)
        setattr(self, f'{table_name}_filter', filter_field)
        setattr(self, f'{table_name}_edit_btn', edit_btn)
        setattr(self, f'{table_name}_delete_btn', delete_btn)
        
        tab.setLayout(layout)
        return tab

    def load_simple_reference(self, table_name: str):
        """Загрузить данные простого справочника"""
        try:
            items = self.db_manager.get_simple_reference(table_name)
            
            table_data = [[item['id'], item['name']] for item in items]
            
            model = getattr(self, f'{table_name}_model')
            model.update_data(table_data)
            
            # Сохраняем оригинальные данные для фильтрации
            setattr(self, f'{table_name}_original_data', items)
            
            # Обновляем информацию
            info_label = getattr(self, f'{table_name}_info')
            info_label.setText(f"📊 Всего записей: {len(items)}")
            
            print(f"✅ Загружено записей из {table_name}: {len(items)}")
            
        except Exception as e:
            print(f"❌ Ошибка загрузки {table_name}: {e}")
            QMessageBox.warning(self, "Ошибка", 
                f"Не удалось загрузить справочник: {str(e)}")

    def add_simple_reference(self, table_name: str, title: str):
        """Добавить элемент в простой справочник"""
        dialog = SimpleReferenceEditDialog(
            self, 
            title=f"Добавление: {title}"
        )
        
        if dialog.exec_() == QDialog.Accepted:
            if dialog.validate():
                data = dialog.get_data()
                try:
                    item_id = self.db_manager.add_simple_reference(
                        table_name, data['name'])
                    
                    if item_id:
                        QMessageBox.information(
                            self, "Успех", 
                            f"Элемент '{data['name']}' добавлен!")
                        self.load_simple_reference(table_name)
                        self.update_general_stats()
                        self.references_updated.emit()
                    else:
                        QMessageBox.warning(
                            self, "Ошибка", 
                            "Не удалось добавить элемент")
                        
                except Exception as e:
                    QMessageBox.critical(
                        self, "Ошибка", 
                        f"Ошибка при добавлении: {str(e)}")

    def edit_simple_reference(self, table_name: str, title: str):
        """Редактировать элемент простого справочника"""
        table = getattr(self, f'{table_name}_table')
        selected_rows = table.selectionModel().selectedRows()
        
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        model = getattr(self, f'{table_name}_model')
        item_id = model._data[row][0]
        
        # Найдем полные данные
        original_data = getattr(self, f'{table_name}_original_data', [])
        item_data = None
        for item in original_data:
            if item.get('id') == item_id:
                item_data = item
                break
        
        if not item_data:
            QMessageBox.warning(
                self, "Ошибка", 
                "Не удалось найти данные элемента")
            return
        
        dialog = SimpleReferenceEditDialog(
            self, item_data,
            title=f"Редактирование: {title}"
        )
        
        if dialog.exec_() == QDialog.Accepted:
            if dialog.validate():
                data = dialog.get_data()
                try:
                    self.db_manager.update_simple_reference(
                        table_name, item_id, data['name'])
                    
                    QMessageBox.information(
                        self, "Успех", 
                        f"Элемент '{data['name']}' обновлен!")
                    self.load_simple_reference(table_name)
                    self.update_general_stats()
                    self.references_updated.emit()
                    
                except Exception as e:
                    QMessageBox.critical(
                        self, "Ошибка", 
                        f"Ошибка при обновлении: {str(e)}")

    def delete_simple_reference(self, table_name: str, foreign_key: str, title: str):
        """Удалить элемент из простого справочника"""
        table = getattr(self, f'{table_name}_table')
        selected_rows = table.selectionModel().selectedRows()
        
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        model = getattr(self, f'{table_name}_model')
        item_id = model._data[row][0]
        item_name = model._data[row][1]
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить '{item_name}' из справочника '{title}'?\n\n"
            f"Внимание: если элемент используется в документах, "
            f"удаление будет невозможно!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.db_manager.delete_simple_reference(
                    table_name, item_id, foreign_key, check_usage=True)
                
                QMessageBox.information(
                    self, "Успех", 
                    f"Элемент '{item_name}' удален!")
                self.load_simple_reference(table_name)
                self.update_general_stats()
                self.references_updated.emit()
                
            except Exception as e:
                QMessageBox.critical(
                    self, "Ошибка", 
                    f"Ошибка при удалении: {str(e)}")

    def filter_simple_reference(self, table_name: str, filter_text: str):
        """Фильтрация простого справочника"""
        filter_text = filter_text.lower()
        
        if not filter_text:
            self.load_simple_reference(table_name)
            return
        
        original_data = getattr(self, f'{table_name}_original_data', [])
        
        if not original_data:
            return
        
        filtered = [item for item in original_data 
                    if filter_text in item['name'].lower()]
        
        table_data = [[item['id'], item['name']] for item in filtered]
        
        model = getattr(self, f'{table_name}_model')
        model.update_data(table_data)

    def on_simple_reference_selection_changed(self, table, edit_btn, delete_btn):
        """Обработчик изменения выбора в таблице простого справочника"""
        has_selection = len(table.selectionModel().selectedRows()) > 0
        edit_btn.setEnabled(has_selection)
        delete_btn.setEnabled(has_selection)