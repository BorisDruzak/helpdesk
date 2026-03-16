import sys
import os
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QMessageBox
from database_optimized import DatabaseManager, DatabaseSwitcher
from work_with_word_docs import WordDocumentHandler
from gui import MainWindow
import app_config
import datetime
def main():
    try:
        # Инициализация приложения PyQt
        app = QApplication(sys.argv)
        if getattr(sys, 'frozen', False):
                # Если запущен как exe
                icon_path = os.path.join(app_config.get_app_root(), "app_icon.ico")
                if os.path.exists(icon_path):
                    app.setWindowIcon(QIcon(icon_path))
        # 🆕 ДОБАВИТЬ: Инициализация структуры data/
        try:
            data_folder = initialize_data_structure()
        except Exception as e:
            QMessageBox.critical(
                None,
                "Ошибка инициализации",
                f"Не удалось создать структуру приложения:\n{str(e)}"
            )
            sys.exit(1)
        
        # Создаем switcher СНАЧАЛА
        switcher = DatabaseSwitcher()
        
        # Проверяем, подключился ли switcher к последней БД автоматически
        if switcher.current_manager and switcher.current_db:
            # Отлично! Используем автоматически загруженную БД
            print(f"✨ Используется автоматически загруженная БД: {switcher.current_db}")
            db_manager = switcher.current_manager
        else:
            # Первый запуск или нет сохраненной конфигурации
            print("🆕 Первый запуск - создание БД по умолчанию")
            
            # 🆕 ИЗМЕНИТЬ: Путь к БД по умолчанию в новой структуре
            default_db_folder = os.path.join(data_folder, "main")
            default_db_path = os.path.join(default_db_folder, "database.db")
            
            # Проверяем существует ли БД по умолчанию
            if not os.path.exists(default_db_path):
                # 🆕 Создаем структуру для БД по умолчанию
                try:
                    print("📁 Создание структуры для БД по умолчанию...")
                    os.makedirs(default_db_folder, exist_ok=True)
                    os.makedirs(os.path.join(default_db_folder, "files"), exist_ok=True)
                    
                    # Создаем пустую БД
                    db_manager = DatabaseManager(default_db_path, create_if_not_exists=True)
                    
                    # Регистрируем её в switcher
                    switcher.register_database("main", default_db_path, db_manager)
                    
                    print(f"✅ БД по умолчанию создана: {default_db_path}")
                    
                except Exception as e:
                    QMessageBox.critical(
                        None,
                        "Ошибка создания БД",
                        f"Не удалось создать базу данных по умолчанию:\n{str(e)}"
                    )
                    sys.exit(1)
            else:
                # БД существует - подключаемся
                try:
                    db_manager = DatabaseManager(default_db_path)
                    switcher.register_database("main", default_db_path, db_manager)
                    print(f"✅ Подключено к существующей БД: {default_db_path}")
                except Exception as e:
                    QMessageBox.critical(
                        None,
                        "Ошибка подключения к БД",
                        f"Не удалось подключиться к базе данных:\n{str(e)}"
                    )
                    sys.exit(1)
            
            try:
                # ИЗМЕНЕНИЕ: Создаем менеджер напрямую
                db_manager = DatabaseManager(default_db_path)
                
                # НОВОЕ: Регистрируем его в switcher как текущий
                switcher.register_database("main", default_db_path, db_manager)
                
                print(f"✅ БД по умолчанию создана и зарегистрирована")
                
            except Exception as e:
                QMessageBox.critical(
                    None,
                    "Ошибка подключения к БД",
                    f"Не удалось подключиться к базе данных:\n{str(e)}"
                )
                sys.exit(1)
    except Exception as e:
        # Показываем ошибку пользователю
        error_msg = f"Критическая ошибка при запуске приложения:\n\n{str(e)}"
        
        try:
            QMessageBox.critical(None, "Ошибка", error_msg)
        except:
            # Если даже QMessageBox не работает, выводим в консоль
            print(f"❌ {error_msg}")
            
        # Записываем в лог
        import traceback
        log_path = os.path.join(app_config.get_app_root(), "error.log")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"Дата: {datetime.now()}\n")
            f.write(error_msg + "\n\n")
            f.write(traceback.format_exc())
            
        sys.exit(1)


    # Инициализация обработчика документов
    document_handler = WordDocumentHandler()

    # ИЗМЕНЕНИЕ: Передаем switcher в MainWindow
    window = MainWindow(db_manager, document_handler, switcher)
    window.showMaximized()

    # Запуск цикла событий приложения
    sys.exit(app.exec_())
def initialize_data_structure():
    """
    Инициализировать структуру data/ при первом запуске
    """
    try:
        # СТАРЫЙ КОД:
        # script_dir = os.path.dirname(os.path.abspath(__file__))
        # project_root = os.path.dirname(script_dir)
        # data_folder = os.path.join(project_root, "data")
        
        # НОВЫЙ КОД:
        data_folder = app_config.get_data_path()
        
        if not os.path.exists(data_folder):
            print("🆕 Первый запуск - создаем папку data/")
            os.makedirs(data_folder, exist_ok=True)
            print(f"✅ Папка создана: {data_folder}")
        else:
            print(f"✅ Папка data/ существует: {data_folder}")
        
        return data_folder
        
    except Exception as e:
        print(f"❌ Ошибка создания структуры data/: {e}")
        raise
if __name__ == "__main__":
    main()