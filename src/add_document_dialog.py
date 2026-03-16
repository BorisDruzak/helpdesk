from PyQt5.QtWidgets import *
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtCore import Qt, pyqtSignal
from database import DatabaseManager
from work_with_word_docs import WordDocumentHandler
import os
import shutil
from datetime import datetime
from metadata_form import MetadataEditor
from ui_styles import AppColors, AppStyles, AppLayout

class AddDocumentDialog(QDialog):
    """Современное окно добавления документа с увеличенным размером и оптимизированными пропорциями"""
    
    document_added = pyqtSignal()
    
    def __init__(self, db_manager: DatabaseManager, document_handler: WordDocumentHandler, parent=None, file_path=None):
        super().__init__(parent)
        print("\n" + "#"*80)
        print("🎉 ИНИЦИАЛИЗАЦИЯ AddDocumentDialog")
        print("#"*80)
        
        self.db_manager = db_manager
        self.document_handler = document_handler
        
        print(f"✅ db_manager: {db_manager}")
        print(f"✅ document_handler: {document_handler}")
        
        self.setup_ui()
        print("✅ UI создан")
        
        self.apply_modern_styles()
        print("✅ Стили применены")
        
        # Если передан file_path, устанавливаем его в редакторе метаданных
        if file_path:
            print(f"📂 Передан file_path при инициализации: {file_path}")
            if hasattr(self.metadata_editor, 'set_document_path'):
                self.metadata_editor.set_document_path(file_path)
        
        print("✅ Инициализация завершена\n")
    def setup_ui(self):
        """Настройка увеличенного интерфейса"""
        self.setWindowTitle("✨ Добавление нового документа")
        
        # === АДАПТИВНЫЙ РАЗМЕР ОКНА ===
        from PyQt5.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        
        # Окно занимает 75% ширины и 85% высоты экрана
        window_width = int(screen_geometry.width() * 0.75)
        window_height = int(screen_geometry.height() * 0.85)
        
        # Минимальные размеры для маленьких экранов
        min_width = min(900, screen_geometry.width() - 50)
        min_height = min(600, screen_geometry.height() - 50)
        
        # Максимальные размеры для очень больших экранов
        max_width = min(1600, screen_geometry.width() - 50)
        max_height = min(1100, screen_geometry.height() - 50)
        
        # Применяем ограничения
        window_width = max(min_width, min(window_width, max_width))
        window_height = max(min_height, min(window_height, max_height))
        
        self.setMinimumSize(min_width, min_height)
        self.resize(window_width, window_height)

        # Основной layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)  # Уменьшили отступы между секциями

        # === КОМПАКТНЫЙ ЗАГОЛОВОК ===
        header_section = self.create_compact_header()
        main_layout.addWidget(header_section)

        # === КОМПАКТНАЯ СЕКЦИЯ ВЫБОРА ФАЙЛА ===
        file_section = self.create_compact_file_section()
        main_layout.addWidget(file_section)

        # === РАСШИРЕННЫЙ РЕДАКТОР МЕТАДАННЫХ ===
        metadata_section = self.create_expanded_metadata_section()
        main_layout.addWidget(metadata_section, 1)  # Растягиваем метаданные на максимум

        # === КНОПКИ ДЕЙСТВИЙ ===
        actions_section = self.create_actions_section()
        main_layout.addWidget(actions_section)

        self.setLayout(main_layout)

    def create_compact_header(self):
        """Создать компактную секцию заголовка"""
        header_frame = QFrame()
        header_frame.setObjectName("headerFrame")
        header_frame.setFixedHeight(60)  # Уменьшили высоту
        
        layout = QHBoxLayout(header_frame)
        layout.setContentsMargins(20, 10, 20, 10)
        
        # Иконка и заголовок
        icon_label = QLabel("📄")
        icon_label.setStyleSheet("font-size: 24px;")  # Уменьшили иконку
        
        title_layout = QVBoxLayout()
        title_label = QLabel("Добавление документа")
        title_label.setObjectName("mainTitle")
        
        subtitle_label = QLabel("Выберите файл и заполните метаданные")
        subtitle_label.setObjectName("subtitle")
        
        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)
        
        
        
        layout.addWidget(icon_label)
        layout.addLayout(title_layout)
        layout.addStretch()
        #layout.addWidget(self.progress_widget)
        
        return header_frame

    

    def create_compact_file_section(self):
        """Создать компактную секцию для названия документа"""
        file_frame = QFrame()
        file_frame.setObjectName("fileSection")
        file_frame.setMaximumHeight(80)  # Уменьшили высоту - только название
        
        layout = QHBoxLayout(file_frame)
        layout.setContentsMargins(20, 12, 20, 12)
        
        # === ТОЛЬКО ПОЛЕ ВВОДА НАЗВАНИЯ ДОКУМЕНТА ===
        title_label = QLabel("📝 Название документа:")
        title_label.setObjectName("titleLabel")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #2d3748;")
        
        self.filename_edit = QLineEdit()
        self.filename_edit.setPlaceholderText("Введите название документа (обязательно)")
        self.filename_edit.setObjectName("filenameEdit")
        self.filename_edit.setMinimumHeight(35)
        
        layout.addWidget(title_label)
        layout.addWidget(self.filename_edit, 1)
        
        return file_frame

    def create_expanded_metadata_section(self):
        """Создать расширенную секцию метаданных"""
        metadata_frame = QFrame()
        metadata_frame.setObjectName("metadataSection")
        
        layout = QVBoxLayout(metadata_frame)
        layout.setContentsMargins(20, 15, 20, 20)
        
        # Компактный заголовок секции
        section_title = QLabel("📋 Метаданные документа")
        section_title.setObjectName("sectionTitle")
        
        # Прокручиваемая область с метаданными (увеличенная)
        scroll_area = QScrollArea()
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # ИСПРАВЛЕНО!
        
        self.metadata_editor = MetadataEditor(self.db_manager)
        
        # Скрываем ненужные элементы
        self.hide_unnecessary_elements()
        
        # Оптимизируем редактор для большего размера
        self.optimize_metadata_editor()
        
        scroll_area.setWidget(self.metadata_editor)
        
        layout.addWidget(section_title)
        layout.addWidget(scroll_area, 1)  # Максимально растягиваем область метаданных
        
        return metadata_frame

    def hide_unnecessary_elements(self):
        """Скрыть ненужные элементы в редакторе метаданных"""
        # ✅ НОВЫЙ ПОДХОД: Используем findChildren для рекурсивного поиска
        
        # 1️⃣ Скрываем элементы по именам атрибутов
        elements_to_hide = [
            'current_document_display', 'save_button', 'status_label', 
            'document_display', 'title_field', 'quick_preview_button', 
            'open_in_word_button'
        ]
        
        for attr_name in elements_to_hide:
            if hasattr(self.metadata_editor, attr_name):
                element = getattr(self.metadata_editor, attr_name)
                if element:
                    element.hide()
                    # Скрываем также родительский layout если есть
                    if element.parent():
                        parent = element.parent()
                        parent_layout = parent.layout()
                        if parent_layout:
                            # Пытаемся скрыть всю строку в лейауте
                            for i in range(parent_layout.count()):
                                item = parent_layout.itemAt(i)
                                if item and item.widget() == element:
                                    element.hide()
        
        # 2️⃣ Ищем и скрываем кнопки по тексту
        buttons_to_hide = [
            "Сохранить", "Сброс", "Очистить",
            "сохранить", "очистить", "💾", "🧹"
        ]
        
        for button in self.metadata_editor.findChildren(QPushButton):
            button_text = button.text()
            # Проверяем содержит ли текст кнопки запрещенные слова
            if any(text in button_text for text in buttons_to_hide):
                print(f"   🔒 Скрываем кнопку: '{button_text}'")
                button.hide()
                # Скрываем родительский виджет если он содержит только эту кнопку
                if button.parent():
                    parent = button.parent()
                    if isinstance(parent, QWidget):
                        # Проверяем сколько видимых детей
                        visible_children = [child for child in parent.findChildren(QWidget) 
                                        if child.isVisible()]
                        if len(visible_children) <= 2:  # Только кнопка и возможно label
                            parent.hide()
        
        # 3️⃣ УСИЛЕННОЕ СКРЫТИЕ ПОЛЯ "ЗАГОЛОВОК"
        for line_edit in self.metadata_editor.findChildren(QLineEdit):
            obj_name = line_edit.objectName().lower()
            placeholder = line_edit.placeholderText().lower()
            
            # Ищем по имени объекта и placeholder
            if 'title' in obj_name or 'заголовок' in placeholder or \
            'название документа' in placeholder:
                line_edit.hide()
                # Скрываем родителя (обычно это QWidget с label)
                if line_edit.parent():
                    line_edit.parent().hide()
        
        # 4️⃣ Скрываем QLabel с текстом "Заголовок"
        for label in self.metadata_editor.findChildren(QLabel):
            label_text = label.text().lower()
            if 'заголовок' in label_text and 'документ' not in label_text:
                label.hide()
                # Скрываем соседний виджет (поле ввода)
                if label.parent():
                    parent_layout = label.parent().layout()
                    if parent_layout and isinstance(parent_layout, QFormLayout):
                        # Ищем соседний виджет в FormLayout
                        for i in range(parent_layout.rowCount()):
                            label_item = parent_layout.itemAt(i, QFormLayout.LabelRole)
                            field_item = parent_layout.itemAt(i, QFormLayout.FieldRole)
                            
                            if label_item and label_item.widget() == label:
                                # Нашли строку с этим label
                                if field_item and field_item.widget():
                                    field_item.widget().hide()
                                label.hide()
                                break
        
        print("✅ Ненужные элементы скрыты")

    def optimize_metadata_editor(self):
        """Оптимизировать редактор метаданных для большого окна"""
        # Изменяем заголовки групп
        for group_box in self.metadata_editor.findChildren(QGroupBox):
            title = group_box.title()
            if "Основные данные документа" in title:
                group_box.setTitle("📝 Основные данные нового документа")
            elif "Дополнительная информация" in title:
                group_box.setTitle("📋 Дополнительная информация")
        
        # Устанавливаем минимальные размеры для полей
        for line_edit in self.metadata_editor.findChildren(QLineEdit):
            line_edit.setMinimumHeight(30)
        
        for combo_box in self.metadata_editor.findChildren(QComboBox):
            combo_box.setMinimumHeight(30)
        
        for date_edit in self.metadata_editor.findChildren(QDateEdit):
            date_edit.setMinimumHeight(30)
        
        for text_edit in self.metadata_editor.findChildren(QTextEdit):
            text_edit.setMinimumHeight(60)

    def create_actions_section(self):
        """Создать секцию кнопок действий"""
        actions_frame = QFrame()
        actions_frame.setObjectName("actionsSection")
        actions_frame.setFixedHeight(70)  # Фиксированная компактная высота
        
        layout = QHBoxLayout(actions_frame)
        layout.setContentsMargins(20, 15, 20, 15)
        
        # Кнопка выхода (слева)
        self.exit_btn = QPushButton("🚪 ВЫХОД")
        
        self.exit_btn.setStyleSheet(AppStyles.button_primary())
        self.exit_btn.setObjectName("exitButton")
        self.exit_btn.clicked.connect(self.reject)
        self.exit_btn.setCursor(Qt.PointingHandCursor)
        
        # Кнопка сброса
        self.reset_btn = QPushButton("🔄 СБРОС")
        self.reset_btn.setStyleSheet(AppStyles.button_primary())
        self.reset_btn.setObjectName("resetButton")
        self.reset_btn.clicked.connect(self.reset_form)
        self.reset_btn.setCursor(Qt.PointingHandCursor)
        
        # Главная кнопка добавления
        self.add_btn = QPushButton("✨ ДОБАВИТЬ ДОКУМЕНТ")
        self.add_btn.setStyleSheet(AppStyles.button_primary())
        self.add_btn.setObjectName("addButton")
        self.add_btn.clicked.connect(self.add_document)
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setDefault(True)
        
        layout.addWidget(self.exit_btn)
        layout.addStretch()
        layout.addWidget(self.reset_btn)
        layout.addWidget(self.add_btn)
        
        return actions_frame

    def apply_modern_styles(self):
        """Применить оптимизированные стили для большого окна"""
        self.setStyleSheet(f"""
        QDialog {{
            background: {AppColors.GRAY_50};
            font-family: 'Segoe UI', Arial, sans-serif;
        }}
        
        #headerFrame {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {AppColors.PRIMARY}, stop:1 {AppColors.PRIMARY_DARK});
            border: none;
            border-radius: 10px;
        }}
        
        #mainTitle {{
            font-size: 16px;
            font-weight: bold;
            color: white;
        }}
        
        #subtitle {{
            font-size: 11px;
            color: {AppColors.GRAY_100};
        }}
        
        #fileSection, #metadataSection, #actionsSection {{
            background: white;
            border: 2px solid {AppColors.GRAY_300};
            border-radius: 10px;
        }}
        
        #fileSelectButton {{
            {AppStyles.button_primary()}
        }}
        
        #addButton {{
            {AppStyles.button_success()}
            padding: 12px 25px;
            font-size: 12px;
            min-width: 160px;
        }}
        
        #resetButton {{
            {AppStyles.button_warning()}
        }}
        
        #exitButton {{
            background: {AppColors.GRAY_500};
            color: white;
            border: none;
            border-radius: 6px;
            padding: 10px 18px;
            font-weight: bold;
        }}
        
        #exitButton:hover {{
            background: {AppColors.GRAY_700};
        }}
        
        {AppStyles.input_field()}
        {AppStyles.scroll_bar()}
        {AppStyles.group_box()}
    """)
    def reset_form(self):
        """Сбросить форму"""
        print("\n🔄 СБРОС ФОРМЫ")
        
        self.filename_edit.clear()
        
        if hasattr(self.metadata_editor, 'reset_form'):
            self.metadata_editor.reset_form()
        
        print("✅ Форма сброшена\n")
        
        # self.update_progress_step(1, False)  # Отключено - прогресс-индикатор удален
        # self.update_progress_step(2, False)
        # self.update_progress_step(3, False)

    def update_progress_step(self, step, completed):
        """Обновить прогресс-индикатор (отключено - UI элементы удалены)"""
        # Метод оставлен для обратной совместимости, но ничего не делает
        pass
    def convert_qdate_for_sql(qdate):
        """Преобразует QDate для использования в SQL"""
        if qdate is None or not qdate.isValid():
            return None
        
        # Возвращаем строку в ISO формате
        return qdate.toString("yyyy-MM-dd")
    def add_document(self):
        """Добавить документ"""
        print("\n" + "="*80)
        print("🚀 НАЧАЛО ДОБАВЛЕНИЯ ДОКУМЕНТА")
        print("="*80)
        
        # Проверяем обязательное поле - название документа
        title = self.filename_edit.text().strip()
        print(f"📝 Название документа: '{title}'")
        
        if not title:
            QMessageBox.warning(
                self, 
                "⚠️ Название не указано", 
                "Пожалуйста, введите название документа.\nЭто поле обязательно для заполнения."
            )
            self.filename_edit.setFocus()
            return

        # Получаем метаданные
        try:
            metadata = self.metadata_editor.get_metadata()
            print(f"✅ Метаданные получены")
            print(metadata)
        except Exception as e:
            print(f"❌ Ошибка получения метаданных: {e}")
            QMessageBox.critical(
                self, 
                "❌ Ошибка получения данных", 
                f"Не удалось получить метаданные:\n{str(e)}"
            )
            return
        
        # 🆕 ПОЛУЧАЕМ ФАЙЛ ИЗ РЕДАКТОРА МЕТАДАННЫХ
        selected_file = metadata.get('document_path', '').strip()
        print(f"📂 Файл из редактора метаданных: '{selected_file}'")
        
        # Работа с файлом - опциональна
        new_file_path = None
        
        if selected_file and os.path.exists(selected_file):
            print("\n" + "-"*80)
            print("📁 НАЧАЛО КОПИРОВАНИЯ ФАЙЛА")
            print("-"*80)
            
            try:
                # Извлекаем год и месяц из даты регистрации
                reg_date_qobject = metadata['reg_date']
                year = reg_date_qobject.year()
                month = reg_date_qobject.month()
                
                print(f"📅 Дата регистрации: {year}-{month:02d}")
                
                # Получаем путь к папке для файлов из DatabaseManager
                target_folder = self.db_manager.get_files_path(year, month)
                print(f"📁 Целевая папка: {target_folder}")
                
                # Проверяем что папка создана
                if not os.path.exists(target_folder):
                    print(f"⚠️ Папка не существует, создаем...")
                    os.makedirs(target_folder, exist_ok=True)
                    print(f"✅ Папка создана: {target_folder}")
                else:
                    print(f"✅ Папка существует")
                
            except Exception as e:
                print(f"❌ Ошибка создания папки: {e}")
                import traceback
                traceback.print_exc()
                QMessageBox.critical(
                    self, 
                    "❌ Ошибка создания папки", 
                    f"Не удалось создать папку для файлов:\n{str(e)}"
                )
                return

            # Формируем имя файла - СОХРАНЯЕМ ОРИГИНАЛЬНОЕ НАЗВАНИЕ
            original_filename = os.path.basename(selected_file)  # Оригинальное имя с расширением
            new_file_name = os.path.join(target_folder, original_filename)
            
            print(f"📝 Оригинальное имя файла: {original_filename}")
            print(f"📝 Полный путь (первая попытка): {new_file_name}")

            # Проверяем, не существует ли уже файл с таким именем
            counter = 1
            original_new_file_name = new_file_name
            original_name_without_ext = os.path.splitext(original_filename)[0]
            original_ext = os.path.splitext(original_filename)[1]
            
            while os.path.exists(new_file_name):
                new_file_name = os.path.join(target_folder, f"{original_name_without_ext}_{counter}{original_ext}")
                counter += 1
                print(f"⚠️ Файл существует, пробуем: {new_file_name}")
            
            if new_file_name != original_new_file_name:
                print(f"✅ Финальное имя файла: {os.path.basename(new_file_name)}")

            # Копируем файл в целевую папку
            try:
                print(f"\n📋 Копирование файла...")
                print(f"   Источник: {selected_file}")
                print(f"   Назначение: {new_file_name}")
                
                shutil.copy2(selected_file, new_file_name)
                
                print(f"✅ Файл успешно скопирован!")
                
                # Проверяем что файл действительно скопирован
                if not os.path.exists(new_file_name):
                    raise Exception(f"Файл не найден после копирования: {new_file_name}")
                
                file_size = os.path.getsize(new_file_name)
                print(f"✅ Размер скопированного файла: {file_size} байт")
                
                # 🔑 КРИТИЧНО: Сохраняем ОТНОСИТЕЛЬНЫЙ путь от папки БД
                relative_path = os.path.relpath(new_file_name, self.db_manager.db_folder)
                # Нормализуем путь (заменяем \ на /)
                relative_path = relative_path.replace('\\', '/')
                new_file_path = relative_path
                
                print(f"\n📊 РЕЗУЛЬТАТ КОПИРОВАНИЯ:")
                print(f"   Абсолютный путь: {new_file_name}")
                print(f"   Относительный путь: {relative_path}")
                print(f"   Будет сохранено в БД: '{new_file_path}'")
                
            except Exception as e:
                print(f"❌ ОШИБКА КОПИРОВАНИЯ: {e}")
                import traceback
                traceback.print_exc()
                QMessageBox.critical(
                    self, 
                    "❌ Ошибка копирования файла", 
                    f"Не удалось скопировать файл:\n\nОшибка: {str(e)}\n\nИсточник: {selected_file}\nНазначение: {new_file_name}"
                )
                return
        else:
            print("⏭️ Пропускаем копирование - файл не выбран или не существует")

        # Формируем данные для БД
        # КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: title берется из filename_edit, НЕ из имени файла
        reg_date_qobject = metadata['reg_date']
        reg_date_string = reg_date_qobject.toString("yyyy-MM-dd")

        print(f"QDate object: {reg_date_qobject}, type: {type(reg_date_qobject)}")
        print(f"Converted string: '{reg_date_string}', type: {type(reg_date_string)}")
        document_data = {
            "title": title,  # Берем из поля ввода
            "document_path": new_file_path or "",  # Путь к файлу или пустая строка
            "reg_number": metadata.get('reg_number', ''),
            "reg_date": metadata['reg_date'].toString("yyyy-MM-dd"),
            "status_id": metadata.get('status_id'),
            "type_id": metadata.get('type_id'),
            "executor_id": metadata['executor_id'],
            "theme_id": metadata['theme_id'],
        }
        for key, value in document_data.items():
            print(f"{key}: {value} (type: {type(value)})")

        # Добавляем опциональные поля
        optional_fields = [
            'number', 'signing_type_id', 'document_kind_id',
            'responsible_executor_id', 'should_publish', 'published_where_id',
            'published_date', 'control_date', 'removed_from_control',
            'execution_result', 'pages_count', 'attachments_count',
            'case_number', 'volume_number', 'sheets'
        ]
        
        for field in optional_fields:
            if field in metadata:
                # Обрабатываем ВСЕ поля с датами
                if field in ['published_date', 'control_date', 'removed_from_control'] and metadata[field]:
                    # Проверяем что это QDate и валидная дата
                    qdate = metadata[field]
                    if hasattr(qdate, 'isValid') and qdate.isValid():
                        document_data[field] = qdate.toString("yyyy-MM-dd")
                    else:
                        document_data[field] = None
                else:
                    document_data[field] = metadata[field]

        # Подписанты и согласующие: передаём в ключах 'signers'/'approvers' для database_optimized
        signer_ids = metadata.get('signer_ids') or []
        approver_ids = metadata.get('approver_ids') or []
        if isinstance(signer_ids, list):
            document_data['signers'] = [int(x) for x in signer_ids if x is not None]
        else:
            document_data['signers'] = []
        if isinstance(approver_ids, list):
            document_data['approvers'] = [int(x) for x in approver_ids if x is not None]
        else:
            document_data['approvers'] = []

        # Сохраняем в БД
        try:
            # Обновляем путь к файлу в данных документа
            document_data['document_path'] = new_file_path or ""
            
            # Сохраняем документ в БД
            print("\n💾 Начинаем сохранение в БД...")
            print(f"📊 Данные для сохранения: {document_data}")
            
            doc_id = self.db_manager.add_document(document_data)
            
            if doc_id:
                print(f"✅ Документ успешно добавлен в БД с ID: {doc_id}")
                
                # Обновляем прогресс
                # self.update_progress_step(2, True)  # Отключено - прогресс-индикатор удален
                # self.update_progress_step(3, True)
                
                # Испускаем сигнал об успешном добавлении
                self.document_added.emit()
                
                # Показываем сообщение об успехе
                QMessageBox.information(
                    self,
                    "✅ Успешно",
                    f"Документ '{title}' успешно добавлен!\n\n"
                    f"📄 ID: {doc_id}\n"
                    f"📁 Путь: {new_file_path or 'файл не прикреплен'}"
                )
                
                # Закрываем диалог
                self.accept()
            else:
                raise Exception("Метод add_document вернул None")
                
        except Exception as e:
            print(f"❌ ОШИБКА при сохранении документа: {e}")
            import traceback
            traceback.print_exc()
            
            QMessageBox.critical(
                self,
                "❌ Ошибка сохранения",
                f"Не удалось сохранить документ в базу данных:\n\n{str(e)}"
            )
            return

    def showEvent(self, event):
        """Центрируем окно при показе"""
        super().showEvent(event)
        
        if self.parent():
            parent_rect = self.parent().geometry()
            self.move(
                parent_rect.x() + (parent_rect.width() - self.width()) // 2,
                parent_rect.y() + (parent_rect.height() - self.height()) // 2
            )
