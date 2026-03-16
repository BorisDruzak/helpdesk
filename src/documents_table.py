from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from datetime import datetime
from doc_prew import DocumentPreviewDialog
from ui_styles import AppColors, AppStyles, AppLayout
class DocumentsTableModel(QAbstractTableModel):
    """Оптимизированная модель таблицы документов с современным дизайном"""
    
    def __init__(self, data, headers):
        super().__init__()
        self._data = data
        self._headers = headers
        
        # Редактируемые колонки (исключаем ID и filename)
        self.editable_columns = {
            'title': 1,           # Название
            'reg_number': 2,      # Рег. номер  
            'reg_date': 3,        # Дата регистрации
            'status': 4,          # Статус
            'type_doc': 5,        # Тип документа
        }
        self._sort_column = 0
        self._sort_order = Qt.AscendingOrder
    
    def rowCount(self, parent=QModelIndex()):
        return len(self._data) if self._data else 0
    
    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)
    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not self._data:
            return None
            
        row = index.row()
        col = index.column()
        
        if row >= len(self._data) or col >= len(self._data[row]):
            return None
        
        value = self._data[row][col]
        
        if role == Qt.DisplayRole or role == Qt.EditRole:
            # Форматирование даты
            if col == 3 and value:  # Дата регистрации
                try:
                    if isinstance(value, str):
                        date_obj = datetime.strptime(value, "%Y-%m-%d")
                        return date_obj.strftime("%d.%m.%Y")
                except:
                    pass
            
            # Ограничиваем длину названия для экономии места
            
            
            # Скрытые колонки - возвращаем как есть для ToolTip
            return str(value) if value is not None else ""
        
        elif role == Qt.BackgroundRole:
            # Современная цветовая схема с градиентами
            if row % 2 == 0:
                return QColor(252, 253, 254)  # Очень светлый серый
            else:
                return QColor(255, 255, 255)  # Белый
        
        elif role == Qt.ForegroundRole:
            # Умная цветовая схема
            if col == 0:  # ID
                return QColor(52, 58, 64)  # Темно-серый
            elif col == 4:  # Статус
                status = str(value).lower() if value else ""
                if "действующий" in status:
                    return QColor(40, 167, 69)  # Зеленый
                elif "отменён" in status or "утратил" in status:
                    return QColor(220, 53, 69)  # Красный  
                elif "дополнения" in status or "изменения" in status:
                    return QColor(255, 193, 7)  # Желтый
                else:
                    return QColor(108, 117, 125)  # Серый
            elif col == 5:  # Тип документа
                return QColor(111, 66, 193)  # Фиолетовый
            
            return QColor(33, 37, 41)  # Основной темный цвет
        
        elif role == Qt.FontRole:
            font = QFont("Inter", 9)  # Современный шрифт
            if col == 0:  # ID
                font.setBold(True)
                font.setPointSize(8)
            elif col == 1:  # Название
                font.setPointSize(9)
                font.setWeight(QFont.Medium)
            return font
        
        elif role == Qt.TextAlignmentRole:
            if col == 0:  # ID
                return Qt.AlignCenter
            elif col in [2, 3]:  # Рег. номер, дата
                return Qt.AlignCenter
            return Qt.AlignLeft | Qt.AlignVCenter
        
        elif role == Qt.ToolTipRole:
            # Детальные подсказки
            if col == 1 and isinstance(value, str) and len(value) > 40:
                return f"<b>Полное название:</b><br>{value}"
            elif col == 4:  # Статус
                return f"<b>Текущий статус документа:</b><br>{value}"
            elif col == 6:  # Исполнитель
                return f"<b>Ответственный исполнитель:</b><br>{value}"
            elif col == 7:  # Тема
                return f"<b>Тематика документа:</b><br>{value}"
            
            return None
        
        elif role == Qt.SizeHintRole:
            return QSize(-1, 32)
        
        return None
    
    def flags(self, index):
        """Определяем редактируемые ячейки"""
        if not index.isValid():
            return Qt.ItemIsEnabled
        
        col = index.column()
        
        # ID (0) - только для выбора
        if col == 0:
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable
        
        # Остальные основные колонки редактируемы
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable
    
    def setData(self, index, value, role=Qt.EditRole):
        """Обработка редактирования"""
        if role != Qt.EditRole or not index.isValid():
            return False
        
        row = index.row()
        col = index.column()
        
        # Запрещаем редактирование ID
        if col == 0:
            return False
        
        # Валидация даты
        if col == 3:  # reg_date
            try:
                if isinstance(value, str) and value.strip():
                    for fmt in ["%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"]:
                        try:
                            date_obj = datetime.strptime(value.strip(), fmt)
                            value = date_obj.strftime("%Y-%m-%d")
                            break
                        except:
                            continue
            except:
                return False
        
        # Обновляем данные
        if row < len(self._data) and col < len(self._data[row]):
            self._data[row][col] = value
            self.dataChanged.emit(index, index, [role])
            return True
        
        return False
    
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        """Заголовки с современным стилем"""
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if section < len(self._headers):
                return self._headers[section]
        elif orientation == Qt.Horizontal and role == Qt.FontRole:
            font = QFont("Inter", 9)
            font.setBold(True)
            return font
        elif orientation == Qt.Horizontal and role == Qt.BackgroundRole:
            return QColor(248, 249, 250)  # Светлый фон заголовка
        elif orientation == Qt.Horizontal and role == Qt.ForegroundRole:
            return QColor(52, 58, 64)  # Темный текст
        
        return None
    
    def sort(self, column, order):
        """Сортировка с учетом типов данных"""
        self.layoutAboutToBeChanged.emit()
        
        try:
            def get_key(value):
                if value is None:
                    return ""
                
                if column == 0:  # ID
                    try:
                        return int(value)
                    except:
                        return value
                
                if column == 3:  # Дата
                    try:
                        if isinstance(value, str):
                            for fmt in ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"]:
                                try:
                                    return datetime.strptime(value, fmt)
                                except:
                                    continue
                    except:
                        pass
                
                return str(value).lower()
            
            self._data.sort(key=lambda x: get_key(x[column]), 
                           reverse=order == Qt.DescendingOrder)
            
            self._sort_column = column
            self._sort_order = order
            
        except Exception as e:
            print(f"Ошибка сортировки: {e}")
        
        self.layoutChanged.emit()
    
    def update_data(self, new_data):
        """Обновление данных модели"""
        self.beginResetModel()
        self._data = new_data
        self.endResetModel()


class DocumentsTableView(QTableView):
    """Оптимизированный виджет таблицы документов"""
    
    document_selected = pyqtSignal(int)
    document_edited = pyqtSignal(int, dict)
    show_metadata_tab = pyqtSignal(int)
    document_preview_requested = pyqtSignal(int)
    open_file_requested = pyqtSignal(int) 
    def __init__(self, db_manager, document_handler):
        super().__init__()
        self.db_manager = db_manager
        self.document_handler = document_handler
        self.current_page = 1
        self.per_page = 100  # Количество документов на загрузку
        self.total_documents = 0
        self.has_more = False
        self.current_filters = None
        self._all_loaded_data = []  # Хранилище всех загруженных данных
        self._is_loading = False  # Флаг процесса загрузки
        self.setup_table()
        self.load_documents()
    def setup_table(self):
        """Современная настройка таблицы"""
        # Основные настройки
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(False)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragEnabled(False)  # Отключаем drag&drop
        self.viewport().setMouseTracking(True)  # Включаем отслеживание мыши
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setFocusPolicy(Qt.NoFocus)
        
        # Современный стиль
        self.setStyleSheet(AppStyles.table_view())
        
        # Настройки заголовков
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.verticalHeader().setVisible(False)
        
        # Подключение сигналов
        self.clicked.connect(self.on_cell_clicked)
        self.doubleClicked.connect(self.on_cell_double_clicked)
        self.verticalScrollBar().valueChanged.connect(self.on_scroll)
        self.horizontalHeader().sortIndicatorChanged.connect(self.on_sort_changed)
    
    def on_sort_changed(self, column, order):
        """Обработчик изменения сортировки"""
        if hasattr(self, 'model_instance'):
            self.model_instance.sort(column, order)
    
    
    
    def setup_column_sizes(self):
        """Настройка размеров колонок"""
        if not self.model():
            return
        
        column_sizes = {
            0: 400,   # Название (увеличено)
            1: 80,   # Рег. номер
            2: 100,   # Дата
            3: 150,   # Статус
            4: 150,   # Тип
            5: 100,   # Исполнитель
            6: 150,   # Тема
            7: 30,    # ID (в конце, уменьшено)
        }
        
        for col, size in column_sizes.items():
            if col < self.model().columnCount():
                self.setColumnWidth(col, size)
        
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    def load_documents(self, filters=None, reset=True):
        """
        Загрузка документов с пагинацией и автоподгрузкой
        
        Args:
            filters: Словарь с фильтрами поиска
            reset: Сбросить текущую загрузку (True при новом поиске)
        """
        try:
            # Предотвращаем множественные одновременные загрузки
            if self._is_loading:
                return
            
            self._is_loading = True
            
            # При новом поиске сбрасываем все
            if reset:
                self.current_page = 1
                self._all_loaded_data = []
                self.current_filters = filters
            
            # Используем метод пагинации
            documents, total_count, has_more = self.db_manager.get_documents_paginated(
                page=self.current_page,
                per_page=self.per_page,
                filters=self.current_filters
            )
            
            self.total_documents = total_count
            self.has_more = has_more
            
            # Преобразуем документы в формат таблицы
            table_data = []
            for doc in documents:
                row = [
                    doc.get('title') or "Без названия",
                    doc.get('reg_number') or "-",
                    doc.get('reg_date') or "-",
                    doc.get('status_name') or "Не указан",
                    doc.get('type_name') or "Не указан",
                    doc.get('executor_name') or "Не назначен",
                    doc.get('theme_name') or "Не указана",
                    doc.get('id', ''),
                ]
                table_data.append(row)
            
            # Добавляем к уже загруженным данным
            self._all_loaded_data.extend(table_data)
            
            # Обновляем модель таблицы
            if not hasattr(self, 'model_instance'):
                headers = ["Название", "№", "Дата", "Статус", "Тип", "Исполнитель", "Тема", "ID"]
                self.model_instance = DocumentsTableModel(self._all_loaded_data, headers)
                self.setModel(self.model_instance)
                self.model_instance.dataChanged.connect(self.on_data_changed)
            else:
                self.model_instance.update_data(self._all_loaded_data)
            
            self.setup_column_sizes()
            
            # Эмитим сигнал для обновления UI
            self.emit_pagination_info()
            
            loaded = len(self._all_loaded_data)
            print(f"✅ Загружено: {loaded}/{self.total_documents} (страница {self.current_page})")
            
            self._is_loading = False
            
        except Exception as e:
            print(f"❌ Ошибка загрузки документов: {e}")
            import traceback
            traceback.print_exc()
            self._is_loading = False
    def load_more_documents(self):
        """
        Загрузить следующую порцию документов
        Вызывается автоматически при скролле вниз
        """
        if not self.has_more or self._is_loading:
            return
        
        print(f"⬇️ Автозагрузка: загружаем страницу {self.current_page + 1}")
        self.current_page += 1
        self.load_documents(filters=self.current_filters, reset=False)
    def emit_pagination_info(self):
        """
        Отправить информацию о пагинации в главное окно
        """
        try:
            loaded = len(self._all_loaded_data)
            total = self.total_documents
            has_more = self.has_more
            
            # Ищем главное окно
            main_window = self.window()
            if hasattr(main_window, 'update_pagination_info'):
                main_window.update_pagination_info(loaded, total, has_more)
        except Exception as e:
            print(f"⚠️ Не удалось обновить UI пагинации: {e}")
    def on_scroll(self, value):
        """
        Обработчик прокрутки - автозагрузка при достижении конца
        """
        scrollbar = self.verticalScrollBar()
        
        # Проверяем достигли ли мы ~90% конца списка
        if scrollbar.maximum() > 0:
            scroll_position = value / scrollbar.maximum()
            
            # Если проскроллили до 90% и есть еще документы - загружаем
            if scroll_position > 0.9 and self.has_more and not self._is_loading:
                print(f"📜 Достигнут конец списка, загружаем еще...")
                self.load_more_documents()
    def update_documents(self, documents):
        """
        Обновление таблицы на основе списка документов
        ИСПОЛЬЗУЕТСЯ для результатов поиска/фильтрации
        """
        try:
            # Сбрасываем пагинацию
            self.current_page = 1
            self._all_loaded_data = []
            
            # Преобразуем документы в формат таблицы
            table_data = []
            for doc in documents:
                row = [
                    doc.get('title') or "Без названия",
                    doc.get('reg_number') or "-",
                    doc.get('reg_date') or "-",
                    doc.get('status') or "Не указан",
                    doc.get('type_doc') or "Не указан",
                    doc.get('executor_name') or "Не назначен",
                    doc.get('theme_name') or "Не указана",
                    doc.get('id', ''),
                ]
                table_data.append(row)
            
            self._all_loaded_data = table_data
            self.total_documents = len(table_data)
            self.has_more = False  # Все документы уже загружены
            
            # Обновляем модель
            if not hasattr(self, 'model_instance'):
                headers = ["Название", "№", "Дата", "Статус", "Тип", "Исполнитель", "Тема", "ID"]
                self.model_instance = DocumentsTableModel(table_data, headers)
                self.setModel(self.model_instance)
                self.model_instance.dataChanged.connect(self.on_data_changed)
            else:
                self.model_instance.update_data(table_data)
            
            self.setup_column_sizes()
            self.emit_pagination_info()
            
            print(f"✅ Обновлено документов: {len(table_data)}")
            
        except Exception as e:
            print(f"❌ Ошибка обновления таблицы: {e}")
    
    def on_cell_clicked(self, index):
        """Обработчик клика"""
        if not index.isValid():
            return
        
        try:
            row = index.row()
            doc_id = self.model()._data[row][7]
            self.document_selected.emit(doc_id)
            print(f"📋 Выбран документ ID: {doc_id}")
        except Exception as e:
            print(f"❌ Ошибка при клике: {e}")
    
    def on_cell_double_clicked(self, index):
        """Обработчик двойного клика - открывает редактор метаданных"""
        if not index.isValid():
            return
        
        try:
            row = index.row()
            # ✅ ID правильно берется из позиции [7]
            doc_id = self.model()._data[row][7]
            # ✅ ИСПРАВЛЕНО: Открываем редактор метаданных, а не предпросмотр
            self.show_metadata_tab.emit(doc_id)
            print(f"🎯 Двойной клик: открываем редактор для документа ID {doc_id}")
        except Exception as e:
            print(f"❌ Ошибка при двойном клике: {e}")
            import traceback
            traceback.print_exc()
    
    def on_data_changed(self, top_left, bottom_right, roles):
        """Обработчик изменения данных"""
        try:
            if not top_left.isValid():
                return
            
            row = top_left.row()
            col = top_left.column()
            doc_id = self.model()._data[row][0]
            
            field_mapping = {
                1: 'title',
                2: 'reg_number', 
                3: 'reg_date',
                4: 'status',
                5: 'type_doc',
            }
            
            if col in field_mapping:
                field_name = field_mapping[col]
                new_value = self.model()._data[row][col]
                self.save_field_change(doc_id, field_name, new_value)
        except Exception as e:
            print(f"❌ Ошибка при сохранении изменений: {e}")
    
    def save_field_change(self, doc_id, field_name, new_value):
        """Сохранение изменения в БД"""
        try:
            update_data = {field_name: new_value}
            self.db_manager.update_document(doc_id, update_data)
            self.document_edited.emit(doc_id, update_data)
        except Exception as e:
            print(f"❌ Ошибка сохранения в БД: {e}")
            QMessageBox.warning(self, "Ошибка", f"Не удалось сохранить:\n{str(e)}")
    
    def update_table_data(self, table_data):
        """Обновление данных таблицы"""
        if hasattr(self, 'model_instance'):
            self.model_instance.update_data(table_data)
            self.setup_column_sizes()
    
    def open_metadata_tab(self, doc_id):
        """Открывает вкладку редактора метаданных"""
        if hasattr(self, 'parent') and hasattr(self.parent(), 'central_widget'):
            self.parent().central_widget.setCurrentIndex(1)
        if hasattr(self, 'parent') and hasattr(self.parent(), 'open_metadata_editor_tab'):
            self.parent().open_metadata_editor_tab(doc_id)
    
    def contextMenuEvent(self, event):
        """Контекстное меню"""
        try:
            index = self.indexAt(event.pos())
            if not index.isValid():
                return
            
            menu = QMenu(self)
            menu.setStyleSheet(AppStyles.menu())
            
            row = index.row()
            doc_id = self.model()._data[row][7]  # ID в конце
            doc_title = self.model()._data[row][0]  # Название первое
            reg_number = self.model()._data[row][1]  # Рег номер
            selection_model = self.selectionModel()
            selected_count = len(selection_model.selectedRows()) if selection_model else 0
            
            # Предпросмотр
            quick_preview_action = QAction("⚡ Быстрый просмотр", self)
            quick_preview_action.setIcon(QIcon())  # Можно добавить иконку
            quick_preview_action.triggered.connect(
                lambda: self.document_preview_requested.emit(doc_id))
            
            # ✅ НОВОЕ: Загрузить в быстрый доступ
            if selected_count > 1:
                # Если выделено несколько документов
                quick_access_action = QAction(f"📌 Загрузить выделенные ({selected_count}) в быстрый доступ", self)
                quick_access_action.triggered.connect(
                    lambda: self.add_selected_to_quick_access_from_table())
            else:
                # Если выделен один документ
                quick_access_action = QAction("📌 Загрузить в быстрый доступ", self)
                quick_access_action.triggered.connect(
                    lambda: self.add_to_quick_access_from_table(doc_id))
            
            # Открыть в Word
            open_in_word_action = QAction("📂 Открыть в Word/LibreOffice", self)
            open_in_word_action.triggered.connect(
                lambda: self.open_file_requested.emit(doc_id))
            
            # Редактировать метаданные - переход в редактор
            metadata_action = QAction("📋 Редактировать метаданные", self)
            metadata_action.triggered.connect(
                lambda: self.show_metadata_tab.emit(doc_id))
            
            # Копировать рег номер
            copy_reg_action = QAction(f"📄 Копировать рег. номер: {reg_number}", self)
            copy_reg_action.triggered.connect(
                lambda: QApplication.clipboard().setText(str(reg_number)))
            
            # Копировать название
            copy_title_action = QAction("📝 Копировать название", self)
            copy_title_action.triggered.connect(
                lambda: QApplication.clipboard().setText(doc_title))
            menu.addSeparator()
            delete_action = QAction("🗑️ Удалить документ", self)
            delete_action.setIcon(QIcon())
            delete_action.triggered.connect(
                lambda: self.delete_document_from_table(doc_id, doc_title))

            menu.addAction(delete_action)
            # ✅ НОВОЕ: Экспорт документов
            if selected_count > 1:
                # Если выделено несколько документов - экспорт выделенных
                export_action = QAction(f"📤 Экспортировать выделенные ({selected_count})", self)
                export_action.triggered.connect(self.export_selected_documents)
            else:
                # Если выделен один документ - показываем оба варианта
                export_selected_action = QAction("📤 Экспортировать документ", self)
                export_selected_action.triggered.connect(self.export_selected_documents)
                
                export_all_action = QAction("📤 Экспортировать все из таблицы", self)
                export_all_action.triggered.connect(self.export_all_from_table)
            
            menu.addAction(quick_preview_action)
            menu.addAction(quick_access_action)  # ✅ НОВОЕ
            menu.addSeparator()
            menu.addAction(open_in_word_action)
            menu.addAction(metadata_action)
            menu.addSeparator()
            
            # Добавляем пункты экспорта
            if selected_count > 1:
                menu.addAction(export_action)
            else:
                menu.addAction(export_selected_action)
                menu.addAction(export_all_action)
            
            menu.addSeparator()
            menu.addAction(copy_reg_action)
            menu.addAction(copy_title_action)
            
            menu.exec_(event.globalPos())
        except Exception as e:
            print(f"❌ Ошибка контекстного меню: {e}")
    def delete_document_from_table(self, doc_id, doc_title):
        """
        Удалить документ из базы данных
        
        Args:
            doc_id: ID документа
            doc_title: Название документа для подтверждения
        """
        try:
            # Запрашиваем подтверждение
            reply = QMessageBox.question(
                self,
                "⚠️ Подтверждение удаления",
                f"Вы действительно хотите удалить документ?\n\n"
                f"📄 {doc_title}\n"
                f"🆔 ID: {doc_id}\n\n"
                f"⚠️ ЭТО ДЕЙСТВИЕ НЕЛЬЗЯ ОТМЕНИТЬ!",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
            
            # Удаляем документ из базы данных
            self.db_manager.delete_document(doc_id)
            
            # Обновляем таблицу
            self.load_documents(filters=self.current_filters, reset=True)
            
            QMessageBox.information(
                self,
                "✅ Успешно",
                f"Документ успешно удалён:\n{doc_title}"
            )
            
            print(f"✅ Документ ID {doc_id} удален из БД")
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "❌ Ошибка удаления",
                f"Не удалось удалить документ:\n\n{str(e)}"
            )
            print(f"❌ Ошибка удаления документа: {e}")
            import traceback
            traceback.print_exc()
    def add_to_quick_access_from_table(self, doc_id):
        """
        Добавить документ в быстрый доступ из основной таблицы
        
        Args:
            doc_id: ID документа
        """
        try:
            # Получаем главное окно
            main_window = self.window()
            
            if hasattr(main_window, 'add_to_quick_access'):
                main_window.add_to_quick_access(doc_id)
            else:
                print("❌ Главное окно не имеет метода add_to_quick_access")
                
        except Exception as e:
            print(f"❌ Ошибка добавления в быстрый доступ: {e}")
            import traceback
            traceback.print_exc()
    def add_selected_to_quick_access_from_table(self):
        """
        Добавить все выделенные документы в быстрый доступ
        """
        try:
            # Получаем главное окно
            main_window = self.window()
            
            if hasattr(main_window, 'add_selected_to_quick_access'):
                main_window.add_selected_to_quick_access()
            else:
                print("❌ Главное окно не имеет метода add_selected_to_quick_access")
                
        except Exception as e:
            print(f"❌ Ошибка массового добавления: {e}")
            import traceback
            traceback.print_exc()
    def open_document_preview_dialog(self, doc_id):
        """Открывает диалог предпросмотра документа"""
        try:
            document_data = self.db_manager.get_document_by_id(doc_id)
            if document_data and document_data.get("document_path"):
                preview_dialog = DocumentPreviewDialog(
                    self.document_handler, 
                    document_data["document_path"], 
                    self
                )
                preview_dialog.exec_()
        except Exception as e:
            print(f"❌ Ошибка открытия предпросмотра: {e}")
    def get_selected_document_ids(self) -> list:
        """
        Получить список ID выделенных документов
        
        Returns:
            list: Список ID документов
        """
        try:
            selected_rows = self.selectionModel().selectedRows()
            doc_ids = []
            
            for index in selected_rows:
                row = index.row()
                # ID находится в последней колонке (индекс 7)
                doc_id = self.model()._data[row][7]
                doc_ids.append(doc_id)
            
            return doc_ids
            
        except Exception as e:
            print(f"❌ Ошибка получения выделенных документов: {e}")
            return []
    
    def get_all_document_ids_from_table(self) -> list:
        """
        Получить список ID ВСЕХ документов загруженных в таблицу
        
        Returns:
            list: Список ID всех документов в таблице
        """
        try:
            if not hasattr(self, 'model_instance') or not self.model_instance:
                return []
            
            doc_ids = []
            row_count = self.model_instance.rowCount()
            
            for row in range(row_count):
                # ID находится в последней колонке (индекс 7)
                doc_id = self.model_instance._data[row][7]
                doc_ids.append(doc_id)
            
            print(f"📊 В таблице загружено {len(doc_ids)} документов")
            return doc_ids
            
        except Exception as e:
            print(f"❌ Ошибка получения документов из таблицы: {e}")
            return []
    
    def get_all_documents_from_table(self) -> list:
        """
        Получить полные данные ВСЕХ документов из таблицы
        
        Returns:
            list: Список словарей с данными документов
        """
        try:
            doc_ids = self.get_all_document_ids_from_table()
            documents = []
            
            for doc_id in doc_ids:
                doc = self.db_manager.get_document_by_id(doc_id)
                if doc:
                    documents.append(doc)
            
            return documents
            
        except Exception as e:
            print(f"❌ Ошибка получения данных документов: {e}")
            return []
    def export_all_from_table(self):
        """
        Экспортировать ВСЕ документы из таблицы
        
        Экспортирует все документы что загружены в таблицу (с учетом примененных фильтров)
        """
        try:
            # Получаем все документы из таблицы
            documents = self.get_all_documents_from_table()
            
            if not documents:
                QMessageBox.warning(
                    self,
                    "⚠️ Таблица пуста",
                    "В таблице нет документов для экспорта"
                )
                return
            
            print(f"📤 Экспорт всех документов из таблицы: {len(documents)}")
            
            # Импортируем диалог экспорта
            from export_manager import ExportDialog
            
            # Создаем и показываем диалог
            dialog = ExportDialog(self.db_manager, self)
            dialog.set_documents_for_export(documents, mode='all_from_table')
            dialog.exec_()
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "❌ Ошибка",
                f"Не удалось открыть экспорт:\n\n{str(e)}"
            )
            print(f"❌ Ошибка экспорта всех документов: {e}")
            import traceback
            traceback.print_exc()
    
    def export_selected_documents(self):
        """
        Экспортировать выделенные документы
        
        Открывает диалог экспорта с предзаполненными выделенными документами
        """
        try:
            # Получаем ID выделенных документов
            selected_ids = self.get_selected_document_ids()
            
            if not selected_ids:
                QMessageBox.warning(
                    self,
                    "⚠️ Нет выделения",
                    "Выделите один или несколько документов для экспорта"
                )
                return
            
            print(f"📤 Экспорт {len(selected_ids)} выделенных документов: {selected_ids}")
            
            # Получаем полные данные документов
            documents = []
            for doc_id in selected_ids:
                doc = self.db_manager.get_document_by_id(doc_id)
                if doc:
                    documents.append(doc)
            
            # Импортируем диалог экспорта
            from export_manager import ExportDialog
            
            # Создаем и показываем диалог
            dialog = ExportDialog(self.db_manager, self)
            dialog.set_documents_for_export(documents, mode='selected')
            dialog.exec_()
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "❌ Ошибка",
                f"Не удалось открыть экспорт:\n\n{str(e)}"
            )
            print(f"❌ Ошибка экспорта выделенных: {e}")
            import traceback
            traceback.print_exc()