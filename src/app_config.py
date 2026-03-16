import os
import sys

def get_app_root():
    """Получить корневую директорию приложения"""
    if getattr(sys, 'frozen', False):
        # Если запущен как .exe
        return os.path.dirname(sys.executable)
    else:
        # Если запущен как .py
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_data_path():
    """Получить путь к папке data"""
    app_root = get_app_root()
    data_path = os.path.join(app_root, "data")
    
    # Создаем папку если её нет
    if not os.path.exists(data_path):
        os.makedirs(data_path, exist_ok=True)
    
    return data_path

APP_NAME = "ACTI Document Manager"
APP_VERSION = "2.1.0"
APP_AUTHOR = "Boris"