from PyQt5.QtCore import QThread, pyqtSignal
import time

class DocumentLoader(QThread):
    """Асинхронная загрузка и обработка документов"""
    
    # Сигналы для коммуникации с UI
    text_loaded = pyqtSignal(str, str)  # текст, имя файла
    loading_progress = pyqtSignal(str)  # статус загрузки
    error_occurred = pyqtSignal(str)    # ошибка
    
    def __init__(self, document_handler, filename, max_chars=15000):
        super().__init__()
        self.document_handler = document_handler
        self.filename = filename
        self.max_chars = max_chars
        self._is_cancelled = False
    
    def cancel(self):
        """Отменить загрузку"""
        self._is_cancelled = True
        self.loading_progress.emit("❌ Загрузка отменена")
    
    def run(self):
        """Основной поток загрузки"""
        try:
            if self._is_cancelled:
                return
                
            self.loading_progress.emit(f"📖 Читаем {self.filename}...")
            
            # Имитируем прогресс для UI
            self.msleep(100)  # Небольшая задержка для плавности
            
            if self._is_cancelled:
                return
            
            # Извлекаем текст
            start_time = time.time()
            text = self.document_handler.extract_text(self.filename)
            load_time = time.time() - start_time
            
            if self._is_cancelled:
                return
            
            self.loading_progress.emit("⚡️ Обрабатываем текст...")
            
            # Обрабатываем текст
            if not text or not text.strip():
                text = "📄 Документ пуст или не содержит читаемого текста"
            else:
                # Ограничиваем размер для производительности
                original_length = len(text)
                if len(text) > self.max_chars:
                    text = text[:self.max_chars]
                    text += f"\n\n{'='*60}\n📊 СТАТИСТИКА ПРЕДПРОСМОТРА:\n"
                    text += f"• Показано: {self.max_chars:,} символов\n"
                    text += f"• Всего в документе: {original_length:,} символов\n"
                    text += f"• Скрыто: {original_length - self.max_chars:,} символов\n"
                    text += f"• Время загрузки: {load_time:.2f} сек\n"
                    text += f"{'='*60}"
            
            if self._is_cancelled:
                return
            
            # Финальная обработка
            text = text.replace('\r\n', '\n').replace('\r', '\n')
            
            # Отправляем результат
            self.text_loaded.emit(text, self.filename)
            
        except Exception as e:
            if not self._is_cancelled:
                error_msg = f"❌ Ошибка при загрузке '{self.filename}':\n\n{str(e)}"
                self.error_occurred.emit(error_msg)
