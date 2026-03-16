import os
import sys
from typing import List, Tuple
from docx import Document
from pathlib import Path
import docx2txt
import chardet

# COM-модули только для Windows (pywin32)
if sys.platform == "win32":
    import pythoncom
    import win32com.client
else:
    pythoncom = None
    win32com = None


class WordDocumentHandler:
    """
    Обработчик документов Word с поддержкой .doc и .docx
    
    ИСПРАВЛЕНИЯ:
    1. ✅ Добавлена COM-инициализация для .doc файлов
    2. ✅ Удален жестко прописанный путь к файлам
    3. ✅ Улучшена обработка путей через database_optimized.py
    """
    
    def __init__(self):
        """
        Инициализирует обработчик документов.
        
        ⚠️ ИЗМЕНЕНИЕ: Больше НЕ использует self.directory
        Теперь все пути передаются в методы явно
        """
        pass  # Больше не нужен self.directory

    def list_files(self, directory: str) -> List[str]:
        """
        Возвращает список файлов в указанной директории.
        
        :param directory: Путь к директории с документами
        :return: Список имен файлов
        """
        if not os.path.exists(directory):
            print(f"⚠️ Директория не существует: {directory}")
            return []
        
        return [f for f in os.listdir(directory) 
                if f.endswith('.doc') or f.endswith('.docx')]
    
    def extract_text(self, filepath):
        """
        Извлекает текст из документа Word (.doc или .docx)
        
        ✅ ИСПРАВЛЕНО: 
        - Теперь принимает ПОЛНЫЙ путь к файлу
        - Больше НЕ строит путь относительно базовой папки
        - Добавлена COM-инициализация для .doc файлов
        
        :param filepath: ПОЛНЫЙ путь к файлу документа
        :return: Извлеченный текст или сообщение об ошибке
        """
        try:
            # ✅ ИСПРАВЛЕНИЕ 1: Используем переданный путь как есть
            full_path = Path(filepath)
            
            print(f"📄 Читаем: {full_path}")
            
            if not full_path.exists():
                raise FileNotFoundError(f"Файл не найден: {full_path}")
            
            file_extension = full_path.suffix.lower()
            
            if file_extension == '.docx':
                return self._extract_docx(full_path)
            elif file_extension == '.doc':
                return self._extract_doc_with_com(full_path)
            else:
                return f"Неподдерживаемый формат: {file_extension}"
                
        except Exception as e:
            error_msg = f"Ошибка при чтении файла '{filepath}': {str(e)}"
            print(f"❌ {error_msg}")
            return error_msg

    def _extract_docx(self, file_path):
        """
        Работа с .docx файлами - оптимизированная версия
        
        :param file_path: Path объект с путем к файлу
        :return: Извлеченный текст
        """
        try:
            doc = Document(str(file_path))
            text = '\n'.join([p.text for p in doc.paragraphs if p.text.strip()])
            print(f"✅ .docx прочитан: {len(text)} символов")
            return text
            
        except Exception as e:
            # Пробуем альтернативный метод
            try:
                text = docx2txt.process(str(file_path))
                print(f"✅ .docx через docx2txt: {len(text)} символов")
                return text
            except Exception as e2:
                return f"Не удалось прочитать .docx файл: {e2}"

    def _extract_doc_with_com(self, file_path):
        """
        Работа с .doc файлами через COM - ИСПРАВЛЕННАЯ версия
        
        ✅ КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Добавлена COM-инициализация
        ⚠️ Работает только на Windows (pywin32)
        
        :param file_path: Path объект с путем к файлу
        :return: Извлеченный текст
        """
        if sys.platform != "win32" or pythoncom is None:
            # На Linux/macOS пробуем docx2txt как fallback для .doc
            try:
                text = docx2txt.process(str(file_path))
                print(f"✅ .doc через docx2txt (Linux): {len(text)} символов")
                return text
            except Exception as e:
                return f"Файлы .doc поддерживаются только на Windows. Ошибка docx2txt: {e}"
        
        word_app = None
        doc = None
        
        try:
            # ⭐ КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: 
            # Инициализируем COM в текущем потоке
            pythoncom.CoInitialize()
            print("✅ COM инициализирован")
            
            print("🔄 Запускаем Word...")
            word_app = win32com.client.Dispatch("Word.Application")
            word_app.Visible = False
            word_app.DisplayAlerts = False  # Отключаем диалоги
            
            print("📖 Открываем документ...")
            doc = word_app.Documents.Open(str(file_path.absolute()))
            
            # Извлекаем текст
            text = doc.Content.Text
            print(f"✅ .doc прочитан: {len(text)} символов")
            
            return text
            
        except Exception as e:
            error_msg = f"Ошибка при чтении .doc файла: {e}"
            print(f"❌ {error_msg}")
            return error_msg
            
        finally:
            # Очистка ресурсов
            try:
                if doc:
                    doc.Close(SaveChanges=False)
                    print("✅ Документ закрыт")
            except:
                pass
            
            try:
                if word_app:
                    word_app.Quit()
                    print("✅ Word закрыт")
            except:
                pass
            
            try:
                # ⭐ КРИТИЧЕСКИ ВАЖНО: Освобождаем COM
                pythoncom.CoUninitialize()
                print("✅ COM освобожден")
            except:
                pass

    def prepare_preview(self, filepath: str, max_chars: int = 200) -> Tuple[str, str]:
        """
        Готовит предварительный просмотр документа.
        
        :param filepath: ПОЛНЫЙ путь к файлу документа
        :param max_chars: Максимальное количество символов для превью
        :return: Кортеж (заголовок, короткий отрывок текста)
        """
        text = self.extract_text(filepath)
        
        # Извлекаем имя файла для заголовка
        filename = Path(filepath).name
        title = filename.split('.')[0].replace('_', ' ').capitalize()
        
        # Создаем превью
        preview = text[:max_chars] + '...' if len(text) > max_chars else text
        
        return title, preview