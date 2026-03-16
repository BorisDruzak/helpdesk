"""
Единая система стилей для приложения по работе с базой данных документов

Этот модуль содержит:
- Унифицированную цветовую палитру
- Готовые CSS-стили для всех компонентов
- Стандарты размеров и отступов

Использование:
    from ui_styles import AppColors, AppStyles, AppLayout
    
    button.setStyleSheet(AppStyles.button_primary())
"""

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from datetime import datetime
class AppColors:
    """
    Единая цветовая палитра приложения (Material Design inspired)
    """
    
    # ===============================================
    # ОСНОВНЫЕ ЦВЕТА
    # ===============================================
    PRIMARY = '#2196F3'           # Основной синий
    PRIMARY_DARK = '#1976D2'      # Темный синий
    PRIMARY_LIGHT = '#BBDEFB'     # Светлый синий
    
    SECONDARY = '#00BCD4'         # Вторичный (cyan)
    SECONDARY_DARK = '#0097A7'    # Темный cyan
    SECONDARY_LIGHT = '#B2EBF2'   # Светлый cyan
    
    # ===============================================
    # АКЦЕНТНЫЕ ЦВЕТА
    # ===============================================
    SUCCESS = '#4CAF50'           # Зеленый (успех)
    SUCCESS_DARK = '#388E3C'
    SUCCESS_LIGHT = '#C8E6C9'
    
    WARNING = '#FF9800'           # Оранжевый (предупреждение)
    WARNING_DARK = '#F57C00'
    WARNING_LIGHT = '#FFE0B2'
    
    DANGER = '#F44336'            # Красный (ошибка)
    DANGER_DARK = '#D32F2F'
    DANGER_LIGHT = '#FFCDD2'
    
    INFO = '#03A9F4'              # Информационный
    INFO_DARK = '#0288D1'
    INFO_LIGHT = '#B3E5FC'
    
    # ===============================================
    # НЕЙТРАЛЬНЫЕ ЦВЕТА
    # ===============================================
    GRAY_50 = '#FAFAFA'           # Самый светлый фон
    GRAY_100 = '#F5F5F5'          # Светлый фон
    GRAY_200 = '#EEEEEE'          # Фон панелей
    GRAY_300 = '#E0E0E0'          # Границы
    GRAY_400 = '#BDBDBD'          # Деактивированные элементы
    GRAY_500 = '#9E9E9E'          # Вторичный текст
    GRAY_600 = '#757575'          # Иконки
    GRAY_700 = '#616161'          # Основной текст
    GRAY_800 = '#424242'          # Темный текст
    GRAY_900 = '#212121'          # Самый темный
    
    # ===============================================
    # ФОНЫ
    # ===============================================
    BACKGROUND = '#FFFFFF'        # Основной фон
    BACKGROUND_ALT = '#FAFAFA'    # Альтернативный фон
    SURFACE = '#FFFFFF'           # Поверхности (карточки)
    
    # ===============================================
    # ТЕКСТ
    # ===============================================
    TEXT_PRIMARY = '#212121'      # Основной текст
    TEXT_SECONDARY = '#757575'    # Вторичный текст
    TEXT_DISABLED = "#302C2C"     # Выключенный текст
    TEXT_ON_PRIMARY = '#FFFFFF'   # Текст на primary


class AppStyles:
    """
    Готовые CSS-стили для компонентов Qt
    """
    
    @staticmethod
    def button_primary():
        """Основная кнопка (Primary Button)"""
        return f"""
            QPushButton {{background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {AppColors.PRIMARY}, stop:1 {AppColors.PRIMARY_DARK});
            color: white;
            border: none;
            border-radius: 6px;
            padding: 12px 20px;  /* Увеличил padding */
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 10pt;
            font-weight: 600;
            /* Убрал min-height */
        }}
            
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1E88E5, stop:1 #1565C0);
            }}
            
            QPushButton:pressed {{
                background: {AppColors.PRIMARY_DARK};
            }}
            
            QPushButton:disabled {{
                background: {AppColors.GRAY_400};
                color: {AppColors.TEXT_DISABLED};
            }}
        """
    
    @staticmethod
    def button_success(
            # ЦВЕТА
        bg_color=None,           
        bg_color_dark=None,      
        hover_light="#43A047",   
        hover_dark="#2E7D32",    
        text_color="white",      
        
        # РАЗМЕРЫ
        padding="10px 20px",     
        min_height="32px",       
        width=None,              
        height=None,             
        border_radius="6px",     
        
        # ШРИФТ
        font_size="10pt",        
        font_weight="600",       
        
        # ДОПОЛНИТЕЛЬНО
        border="none",           
        disabled_bg=None,        
        disabled_text=None,
        gradient=False            # ← НОВЫЙ ПАРАМЕТР для градиента
    ):
        """Универсальная кнопка с настраиваемыми параметрами"""
        
        # Дефолтные цвета если не переданы
        if bg_color is None:
            bg_color = AppColors.SUCCESS
        if bg_color_dark is None:
            bg_color_dark = AppColors.SUCCESS_DARK
        if disabled_bg is None:
            disabled_bg = AppColors.GRAY_400
        if disabled_text is None:
            disabled_text = AppColors.TEXT_DISABLED
        
        # Размеры (если заданы)
        width_style = f"min-width: {width}; max-width: {width};" if width else ""
        height_style = f"min-height: {height}; max-height: {height};" if height else f"min-height: {min_height};"
        
        # Фон с градиентом или без
        if gradient and bg_color == bg_color_dark:
            bg_style = f"""qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {bg_color}, stop:1 {bg_color_dark})"""
            hover_bg_style = f"""qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {hover_light}, stop:1 {hover_dark})"""
        else:
            bg_style = bg_color
            hover_bg_style = hover_light
        
        return f"""
            QPushButton {{
                background: {bg_style};
                color: {text_color};
                border: {border};
                border-radius: {border_radius};
                padding: {padding};
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: {font_size};
                font-weight: {font_weight};
                {height_style}
                {width_style}
            }}
            
            QPushButton:hover {{
                background: {hover_bg_style};
            }}
            
            QPushButton:pressed {{
                background: {bg_color_dark if gradient else bg_color};
            }}
            
            QPushButton:disabled {{
                background: {disabled_bg};
                color: {disabled_text};
            }}
        """
    @staticmethod
    def vbox_layout():
        """Стили для контейнера с QVBoxLayout"""
        return f"""
            QWidget {{
                background-color: white;
                border: 1px solid {AppColors.GRAY_300};
                border-radius: 8px;
                padding: 10px;
            }}
            
            QWidget:hover {{
                border: 1px solid {AppColors.PRIMARY_LIGHT};
            }}
            
            /* РАЗДЕЛИТЕЛИ */
            QFrame[frameShape="4"] {{  /* HLine */
                color: {AppColors.GRAY_300};
                background-color: {AppColors.GRAY_300};
                border: none;
                height: 1px;
                margin: 5px 0px;
            }}
            
            QFrame[frameShape="5"] {{  /* VLine */
                color: {AppColors.GRAY_300};
                background-color: {AppColors.GRAY_300};
                border: none;
                width: 1px;
                margin: 0px 5px;
            }}
        """
    @staticmethod
    def list_widget():
        """Стили для QListWidget"""
        return f"""
            QListWidget {{
                background-color: white;
                alternate-background-color: {AppColors.GRAY_50};
                border: 2px solid {AppColors.GRAY_300};
                border-radius: 8px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10pt;
                outline: none;
                selection-background-color: {AppColors.PRIMARY};
                selection-color: white;
            }}
            
            QListWidget::item {{
                padding: 12px 15px;
                border: none;
                border-bottom: 1px solid {AppColors.GRAY_200};
                color: {AppColors.GRAY_700};
            }}
            
            QListWidget::item:last {{
                border-bottom: none;
            }}
            
            QListWidget::item:selected {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.PRIMARY}, stop:1 {AppColors.PRIMARY_DARK});
                color: white;
                border: none;
            }}
            
            QListWidget::item:hover {{
                background-color: {AppColors.PRIMARY_LIGHT};
                color: {AppColors.PRIMARY_DARK};
            }}
            
            QListWidget::item:selected:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.PRIMARY_LIGHT}, stop:1 {AppColors.PRIMARY});
                color: white;
            }}
            
            /* СКРОЛЛБАР */
            QListWidget::vertical-scrollbar {{
                background: {AppColors.GRAY_100};
                width: 12px;
                border-radius: 6px;
            }}
            
            QListWidget::vertical-scrollbar::handle {{
                background: {AppColors.GRAY_400};
                border-radius: 6px;
                min-height: 20px;
            }}
            
            QListWidget::vertical-scrollbar::handle:hover {{
                background: {AppColors.PRIMARY};
            }}
            
            QListWidget::vertical-scrollbar::add-line,
            QListWidget::vertical-scrollbar::sub-line {{
                border: none;
                background: none;
            }}
        """
    @staticmethod
    def dia():
        return f"""QDialog {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #f8f9fa, stop:1 #e9ecef);
            border: 2px solid {AppColors.GRAY_400};
            border-radius: 12px;
            font-family: 'Segoe UI', Arial, sans-serif;
        }}
        
        /* ЗАГОЛОВОК ОКНА */
        QDialog::title {{
            background: {AppColors.PRIMARY};
            color: white;
            font-weight: bold;
            padding: 8px;
        }}
    """
    @staticmethod
    def line_e():
        return f"""QLineEdit {{
            border: 2px solid {AppColors.GRAY_300};
            border-radius: 6px;
            padding: 8px 12px;
            background: white;
            font-size: 10pt;
            min-height: 20px;
        }}
        
        QLineEdit:focus {{
            border: 2px solid {AppColors.PRIMARY};
            outline: none;
        }}
        
        QLineEdit:hover {{
            border: 2px solid {AppColors.PRIMARY_LIGHT};
        }}
    """
    @staticmethod
    def message_box():
        """Стили для QMessageBox"""
        return f"""
            QMessageBox {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f8f9fa);
                border: 2px solid {AppColors.GRAY_400};
                border-radius: 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
                min-width: 350px;
            }}
            
            /* ЗАГОЛОВОК */
            QMessageBox QLabel#qt_msgbox_label {{
                color: {AppColors.GRAY_800};
                font-size: 11pt;
                font-weight: 500;
                padding: 15px 20px;
                background: transparent;
            }}
            
            /* ИКОНКА */
            QMessageBox QLabel#qt_msgbox_icon {{
                padding: 10px;
                background: transparent;
            }}
            
            /* КНОПКИ */
            QMessageBox QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.GRAY_100}, stop:1 {AppColors.GRAY_200});
                border: 2px solid {AppColors.GRAY_300};
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 10pt;
                font-weight: 600;
                color: {AppColors.GRAY_700};
                min-width: 80px;
                min-height: 32px;
            }}
            
            QMessageBox QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.PRIMARY_LIGHT}, stop:1 {AppColors.GRAY_300});
                border: 2px solid {AppColors.PRIMARY};
                color: {AppColors.PRIMARY_DARK};
            }}
            
            QMessageBox QPushButton:pressed {{
                background: {AppColors.GRAY_400};
            }}
            
            /* КНОПКА OK - АКЦЕНТНАЯ */
            QMessageBox QPushButton[text="OK"],
            QMessageBox QPushButton[text="Да"],
            QMessageBox QPushButton[text="Yes"] {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.PRIMARY}, stop:1 {AppColors.PRIMARY_DARK});
                color: white;
                border: 2px solid {AppColors.PRIMARY_DARK};
            }}
            
            QMessageBox QPushButton[text="OK"]:hover,
            QMessageBox QPushButton[text="Да"]:hover,
            QMessageBox QPushButton[text="Yes"]:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.PRIMARY_LIGHT}, stop:1 {AppColors.PRIMARY});
            }}
            
            /* КНОПКА ОТМЕНЫ/НЕТ - КРАСНАЯ */
            QMessageBox QPushButton[text="Cancel"],
            QMessageBox QPushButton[text="Отмена"],
            QMessageBox QPushButton[text="Нет"],
            QMessageBox QPushButton[text="No"] {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ff6b6b, stop:1 #ee5a5a);
                color: white;
                border: 2px solid #cc4444;
            }}
            
            QMessageBox QPushButton[text="Cancel"]:hover,
            QMessageBox QPushButton[text="Отмена"]:hover,
            QMessageBox QPushButton[text="Нет"]:hover,
            QMessageBox QPushButton[text="No"]:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ff7979, stop:1 #ff6348);
            }}
        """
    @staticmethod
    def radio_button():
        """Стили для RadioButton с современным дизайном"""
        return f"""
            QRadioButton {{
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10pt;
                font-weight: 500;
                color: {AppColors.GRAY_700};
                spacing: 10px;
                padding: 4px;
            }}
            
            /* КРУЖОК РАДИОКНОПКИ (неотмеченный) */
            QRadioButton::indicator {{
                width: 20px;
                height: 20px;
                border: 3px solid {AppColors.GRAY_400};
                border-radius: 12px;  /* Делаем круглым */
                background: white;
            }}
            
            /* НАВЕДЕНИЕ на неотмеченный */
            QRadioButton::indicator:hover {{
                border: 3px solid {AppColors.PRIMARY};
                background: {AppColors.PRIMARY_LIGHT};
                transform: scale(1.05);
            }}
            
            /* ОТМЕЧЕННЫЙ радиобаттон */
            QRadioButton::indicator:checked {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.PRIMARY}, stop:1 {AppColors.PRIMARY_DARK});
                border: 3px solid {AppColors.PRIMARY_DARK};
            }}
            
            /* Внутренняя точка для отмеченного состояния */
            QRadioButton::indicator:checked::after {{
                content: '';
                width: 8px;
                height: 8px;
                border-radius: 6px;
                background: white;
                position: absolute;
                top: 50%;
                left: 50%;
                margin: -4px 0 0 -4px;
            }}
            
            /* НАВЕДЕНИЕ на отмеченный */
            QRadioButton::indicator:checked:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.PRIMARY_LIGHT}, stop:1 {AppColors.PRIMARY});
                border: 3px solid {AppColors.PRIMARY};
            }}
            
            /* ОТКЛЮЧЕННЫЙ неотмеченный */
            QRadioButton::indicator:disabled {{
                background: {AppColors.GRAY_200};
                border: 3px solid {AppColors.GRAY_300};
            }}
            
            /* ОТКЛЮЧЕННЫЙ отмеченный */
            QRadioButton::indicator:checked:disabled {{
                background: {AppColors.GRAY_400};
                border: 3px solid {AppColors.GRAY_400};
            }}
            
            /* ТЕКСТ отключенного радиобаттона */
            QRadioButton:disabled {{
                color: {AppColors.GRAY_400};
            }}
            
            /* ФОКУС */
            QRadioButton::indicator:focus {{
                border: 3px solid {AppColors.INFO};
                outline: 2px solid {AppColors.INFO_LIGHT};
            }}
            
            /* АКТИВНОЕ состояние (при нажатии) */
            QRadioButton::indicator:pressed {{
                background: {AppColors.GRAY_200};
                border: 3px solid {AppColors.GRAY_500};
            }}
            
            QRadioButton::indicator:checked:pressed {{
                background: {AppColors.PRIMARY_DARK};
                border: 3px solid {AppColors.GRAY_900};
            }}
        """

    @staticmethod  
    def radio_button_group():
        """Стили для группы RadioButton в QGroupBox"""
        return f"""
            QGroupBox {{
                border: 2px solid {AppColors.PRIMARY};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 16px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 11pt;
                font-weight: bold;
                color: {AppColors.TEXT_PRIMARY};
                background: white;
            }}
            
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 8px;
                background: white;
                color: {AppColors.PRIMARY};
            }}
            
            /* RadioButton внутри группы - уменьшенные отступы */
            QGroupBox QRadioButton {{
                margin: 6px 10px;
                padding: 6px;
            }}
            
            QGroupBox QRadioButton::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 11px;
            }}
        """

    @staticmethod
    def radio_button_compact():
        """Компактная версия RadioButton"""
        return f"""
            QRadioButton {{
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 9pt;
                font-weight: 500;
                color: {AppColors.GRAY_700};
                spacing: 6px;
                padding: 2px;
            }}
            
            QRadioButton::indicator {{
                width: 16px;
                height: 16px;
                border: 2px solid {AppColors.GRAY_400};
                border-radius: 10px;
                background: white;
            }}
            
            QRadioButton::indicator:hover {{
                border: 2px solid {AppColors.PRIMARY};
                background: {AppColors.PRIMARY_LIGHT};
            }}
            
            QRadioButton::indicator:checked {{
                background: {AppColors.PRIMARY};
                border: 2px solid {AppColors.PRIMARY_DARK};
            }}
            
            QRadioButton::indicator:checked::after {{
                width: 6px;
                height: 6px;
                border-radius: 4px;
                margin: -3px 0 0 -3px;
            }}
        """

    @staticmethod
    def radio_button_card():
        """RadioButton в виде карточки (для больших списков опций)"""
        return f"""
            QRadioButton {{
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10pt;
                font-weight: 500;
                color: {AppColors.GRAY_700};
                background: white;
                border: 2px solid {AppColors.GRAY_300};
                border-radius: 8px;
                padding: 12px 16px;
                margin: 4px;
                min-height: 40px;
            }}
            
            QRadioButton:hover {{
                border: 2px solid {AppColors.PRIMARY};
                background: {AppColors.PRIMARY_LIGHT};
                color: {AppColors.PRIMARY_DARK};
            }}
            
            QRadioButton:checked {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.PRIMARY_LIGHT}, stop:1 white);
                border: 3px solid {AppColors.PRIMARY};
                color: {AppColors.PRIMARY_DARK};
                font-weight: 600;
            }}
            
            /* Скрываем стандартный индикатор для карточного стиля */
            QRadioButton::indicator {{
                width: 0px;
                height: 0px;
            }}
            
            /* Добавляем галочку в правый верхний угол */
            QRadioButton:checked::before {{
                content: "✓";
                position: absolute;
                right: 8px;
                top: 8px;
                color: {AppColors.PRIMARY};
                font-size: 14pt;
                font-weight: bold;
            }}
        """

    @staticmethod
    def dock_widget():
        """Стили для QDockWidget"""
        return f"""
            QDockWidget {{
                background: white;
                border: 2px solid {AppColors.GRAY_300};
                border-radius: 0px;
                font-family: 'Segoe UI', Arial, sans-serif;
                titlebar-close-icon: none;
                titlebar-normal-icon: none;
            }}
            
            /* ЗАГОЛОВОК */
            QDockWidget::title {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.PRIMARY}, stop:1 {AppColors.PRIMARY_DARK});
                color: white;
                font-weight: 600;
                font-size: 11pt;
                padding: 12px 15px;
                text-align: left;
                border: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }}
            
            QDockWidget::close-button,
            QDockWidget::float-button {{
                border: none;
                background: transparent;
                width: 0px;
                height: 0px;
            }}
            
            /* СОДЕРЖИМОЕ */
            QDockWidget QWidget {{
                background: white;
                border: none;
            }}
            
            /* РАЗДЕЛИТЕЛЬ */
            QDockWidget::separator {{
                background: {AppColors.GRAY_400};
                width: 3px;
                height: 3px;
            }}
            
            QDockWidget::separator:hover {{
                background: {AppColors.PRIMARY};
            }}
        """
    @staticmethod
    def text_e():
        return f"""QTextEdit {{
            border: 2px solid {AppColors.GRAY_300};
            border-radius: 6px;
            padding: 8px;
            background: white;
            font-size: 10pt;
        }}
        
        QTextEdit:focus {{
            border: 2px solid {AppColors.PRIMARY};
            outline: none;
        }}
    """
    @staticmethod
    def check():
        return f"""QCheckBox {{
            font-size: 10pt;
            color: {AppColors.GRAY_700};
            spacing: 8px;
        }}
        
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid {AppColors.GRAY_400};
            border-radius: 4px;
            background: white;
        }}
        
        QCheckBox::indicator:checked {{
            background: {AppColors.PRIMARY};
            border: 2px solid {AppColors.PRIMARY_DARK};
            image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xIDQuNUw0LjUgOEwxMSAxIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8L3N2Zz4K);
        }}
    """
    @staticmethod
    def lable():
        return f"""QLabel {{
            color: {AppColors.GRAY_700};
            font-size: 10pt;
            font-weight: 500;
        }}
    """
    @staticmethod
    def butt():
        return f"""QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {AppColors.GRAY_100}, stop:1 {AppColors.GRAY_200});
            border: 2px solid {AppColors.GRAY_300};
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 10pt;
            font-weight: 600;
            color: {AppColors.GRAY_700};
            min-width: 80px;
            min-height: 32px;
        }}
        
        QPushButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {AppColors.PRIMARY_LIGHT}, stop:1 {AppColors.GRAY_300});
            border: 2px solid {AppColors.PRIMARY};
            color: {AppColors.PRIMARY_DARK};
        }}
        
        QPushButton:pressed {{
            background: {AppColors.GRAY_300};
        }}
    """
    @staticmethod
    def butt_ok():
        return f"""QPushButton[text="OK"] {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {AppColors.PRIMARY}, stop:1 {AppColors.PRIMARY_DARK});
            color: white;
            border: 2px solid {AppColors.PRIMARY_DARK};
        }}
        
        QPushButton[text="OK"]:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {AppColors.PRIMARY_LIGHT}, stop:1 {AppColors.PRIMARY});
        }}
    """
    @staticmethod
    def button_warning():
        """Кнопка предупреждения (Warning Button)"""
        return f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.WARNING}, stop:1 {AppColors.WARNING_DARK});
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10pt;
                font-weight: 600;
                min-height: 32px;
            }}
            
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FB8C00, stop:1 #E65100);
            }}
            
            QPushButton:pressed {{
                background: {AppColors.WARNING_DARK};
            }}
            
            QPushButton:disabled {{
                background: {AppColors.GRAY_400};
                color: {AppColors.TEXT_DISABLED};
            }}
        """
    
    @staticmethod
    def button_danger():
        """Кнопка опасности (Danger Button)"""
        return f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.DANGER}, stop:1 {AppColors.DANGER_DARK});
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10pt;
                font-weight: 600;
                min-height: 32px;
            }}
            
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #E53935, stop:1 #C62828);
            }}
            
            QPushButton:pressed {{
                background: {AppColors.DANGER_DARK};
            }}
            
            QPushButton:disabled {{
                background: {AppColors.GRAY_400};
                color: {AppColors.TEXT_DISABLED};
            }}
        """
    
    @staticmethod
    def button_neutral():
        """Нейтральная кнопка"""
        return f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.GRAY_500}, stop:1 {AppColors.GRAY_700});
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10pt;
                font-weight: 600;
                min-height: 32px;
            }}
            
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.GRAY_700}, stop:1 {AppColors.GRAY_900});
            }}
            
            QPushButton:disabled {{
                background: {AppColors.GRAY_400};
                color: {AppColors.TEXT_DISABLED};
            }}
        """
    @staticmethod
    def date_edit_style():
        """ОКОНЧАТЕЛЬНО ИСПРАВЛЕННЫЙ стиль календаря"""
        return f"""
            /* === ПОЛЕ ВВОДА ДАТЫ === */
            QDateEdit {{
                border: 2px solid {AppColors.GRAY_300};
                border-radius: 6px;
                padding: 8px 12px;
                background: white;
                color: {AppColors.TEXT_PRIMARY};
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10pt;
                min-height: 32px;
            }}
            
            QDateEdit:hover {{
                border-color: {AppColors.PRIMARY};
                background: {AppColors.GRAY_50};
            }}
            
            QDateEdit:focus {{
                border-color: {AppColors.PRIMARY};
                border-width: 2px;
                background: white;
            }}
            
            QDateEdit::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: right center;
                width: 30px;
                border-left: 1px solid {AppColors.GRAY_300};
                background: {AppColors.GRAY_100};
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }}
            
            QDateEdit::drop-down:hover {{
                background: {AppColors.PRIMARY};
            }}
            
            QDateEdit::down-arrow {{
                image: none;
                border: none;
                width: 0;
                height: 0;
            }}
            
            /* === ГЛАВНОЕ ОКНО КАЛЕНДАРЯ - УВЕЛИЧЕНО! === */
            QCalendarWidget {{
                background: white;
                border: 2px solid {AppColors.PRIMARY};
                border-radius: 12px;
                padding: 8px;
                min-width: 400px;
                max-width: 400px;
                min-height: 350px;
                max-height: 350px;
            }}
            
            /* === ВЕРХНЯЯ ПАНЕЛЬ НАВИГАЦИИ === */
            QCalendarWidget QWidget#qt_calendar_navigationbar {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.PRIMARY}, stop:1 {AppColors.PRIMARY_DARK});
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 8px;
                min-height: 55px;
                max-height: 55px;
            }}
            
            /* === КНОПКА МЕСЯЦ/ГОД (центральная) - УМЕНЬШЕНА === */
            QCalendarWidget QToolButton#qt_calendar_monthbutton,
            QCalendarWidget QToolButton#qt_calendar_yearbutton {{
                background: transparent;
                color: white;
                border: none;
                padding: 8px 12px;
                font-weight: bold;
                font-size: 11pt;
                min-width: 80px;
                max-width: 80px;
                min-height: 32px;
            }}
            
            QCalendarWidget QToolButton#qt_calendar_monthbutton:hover,
            QCalendarWidget QToolButton#qt_calendar_yearbutton:hover {{
                background: rgba(255, 255, 255, 0.2);
                border-radius: 6px;
            }}
            
            QCalendarWidget QToolButton#qt_calendar_monthbutton:pressed,
            QCalendarWidget QToolButton#qt_calendar_yearbutton:pressed {{
                background: rgba(255, 255, 255, 0.3);
            }}
            
            /* === КНОПКИ НАВИГАЦИИ (стрелки) - ТЕМНЫЕ СТРЕЛКИ НА БЕЛОМ! === */
            QCalendarWidget QToolButton#qt_calendar_prevmonth,
            QCalendarWidget QToolButton#qt_calendar_nextmonth {{
                background: white;
                color: {AppColors.PRIMARY_DARK};
                border: 2px solid white;
                border-radius: 20px;
                width: 40px;
                height: 40px;
                min-width: 40px;
                min-height: 40px;
                max-width: 40px;
                max-height: 40px;
                font-weight: bold;
                font-size: 20pt;
                margin: 0px 4px;
                text-align: center;
            }}
            
            QCalendarWidget QToolButton#qt_calendar_prevmonth:hover,
            QCalendarWidget QToolButton#qt_calendar_nextmonth:hover {{
                background: rgba(255, 255, 255, 0.95);
                border: 2px solid rgba(255, 255, 255, 0.95);
                transform: scale(1.05);
            }}
            
            QCalendarWidget QToolButton#qt_calendar_prevmonth:pressed,
            QCalendarWidget QToolButton#qt_calendar_nextmonth:pressed {{
                background: {AppColors.GRAY_100};
            }}
            
            /* === МЕНЮ ВЫБОРА МЕСЯЦА/ГОДА === */
            QCalendarWidget QMenu {{
                background: white;
                border: 2px solid {AppColors.PRIMARY};
                border-radius: 8px;
                padding: 5px;
            }}
            
            QCalendarWidget QMenu::item {{
                padding: 10px 24px;
                border-radius: 4px;
                font-size: 10pt;
            }}
            
            QCalendarWidget QMenu::item:selected {{
                background: {AppColors.PRIMARY};
                color: white;
            }}
            
            /* === СПИНБОКС ГОДА - УМЕНЬШЕН === */
            QCalendarWidget QSpinBox {{
                background: white;
                border: 2px solid {AppColors.GRAY_300};
                border-radius: 6px;
                padding: 6px;
                font-size: 10pt;
                font-weight: 600;
                color: {AppColors.TEXT_PRIMARY};
                min-width: 75px;
                max-width: 75px;
                selection-background-color: {AppColors.PRIMARY};
            }}
            
            QCalendarWidget QSpinBox:focus {{
                border-color: {AppColors.PRIMARY};
                border-width: 2px;
            }}
            
            QCalendarWidget QSpinBox::up-button,
            QCalendarWidget QSpinBox::down-button {{
                background: {AppColors.GRAY_100};
                border: none;
                width: 20px;
                border-radius: 3px;
            }}
            
            QCalendarWidget QSpinBox::up-button:hover,
            QCalendarWidget QSpinBox::down-button:hover {{
                background: {AppColors.PRIMARY};
            }}
            
            QCalendarWidget QSpinBox::up-arrow,
            QCalendarWidget QSpinBox::down-arrow {{
                width: 10px;
                height: 10px;
            }}
            
            /* === ЗАГОЛОВКИ ДНЕЙ НЕДЕЛИ === */
            QCalendarWidget QWidget {{
                alternate-background-color: white;
            }}
            
            QCalendarWidget QTableView {{
                border: none;
                background: white;
            }}
            
            QCalendarWidget QHeaderView::section {{
                background: {AppColors.GRAY_100};
                color: {AppColors.TEXT_PRIMARY};
                padding: 10px 4px;
                border: none;
                font-weight: bold;
                font-size: 10pt;
                border-bottom: 2px solid {AppColors.GRAY_200};
            }}
            
            /* === ЯЧЕЙКИ КАЛЕНДАРЯ === */
            QCalendarWidget QAbstractItemView {{
                background: white;
                color: {AppColors.TEXT_PRIMARY};
                font-size: 11pt;
                selection-background-color: {AppColors.PRIMARY};
                selection-color: white;
                outline: none;
                border: none;
                show-decoration-selected: 1;
            }}
            
            /* Обычные дни */
            QCalendarWidget QAbstractItemView::item {{
                padding: 10px;
                border-radius: 8px;
                margin: 1px;
                border: 1px solid transparent;
                transition: all 0.2s ease;  
            }}
            
            /* Наведение на день */
            QCalendarWidget QAbstractItemView::item:hover {{
                background: {AppColors.PRIMARY_LIGHT};
                color: {AppColors.INFO};
                font-weight: 600;
                border: 1px solid {AppColors.INFO_DARK};
                box-shadow: 0 2px 8px rgba(74, 144, 226, 0.4); 
            }}
            
            /* Выбранный день */
            QCalendarWidget QAbstractItemView::item:selected {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.PRIMARY}, stop:1 {AppColors.PRIMARY_DARK});
                color: white;
                font-weight: bold;
                border: 2px solid {AppColors.PRIMARY_DARK};
            }}
            
            /* Дни из других месяцев */
            QCalendarWidget QAbstractItemView::item:disabled {{
                color: {AppColors.GRAY_400};
                background: transparent;
            }}
            
            /* === ВЕРТИКАЛЬНЫЙ ЗАГОЛОВОК (номера недель) === */
            QCalendarWidget QHeaderView#qt_calendar_calendarview::section:vertical {{
                background: {AppColors.GRAY_100};
                color: {AppColors.TEXT_SECONDARY};
                padding: 8px 4px;
                border: none;
                font-size: 9pt;
                font-weight: 600;
                border-right: 1px solid {AppColors.GRAY_200};
            }}
        """
    @staticmethod
    def scroll_area():
        """Стили для QScrollArea"""
        return f"""
            QScrollArea {{
                background-color: white;
                border: 2px solid {AppColors.GRAY_300};
                border-radius: 8px;
                padding: 0px;
            }}
            
            QScrollArea:focus {{
                border: 2px solid {AppColors.PRIMARY};
            }}
            
            /* ОБЛАСТЬ СОДЕРЖИМОГО */
            QScrollArea > QWidget > QWidget {{
                background-color: white;
            }}
            
            QScrollArea QWidget#scrollAreaWidgetContents {{
                background-color: transparent;
            }}
            
            /* ВЕРТИКАЛЬНЫЙ СКРОЛЛБАР */
            QScrollArea QScrollBar:vertical {{
                background: {AppColors.GRAY_100};
                width: 14px;
                border-radius: 7px;
                margin: 0px;
            }}
            
            QScrollArea QScrollBar::handle:vertical {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppColors.GRAY_400}, stop:1 {AppColors.GRAY_500});
                border-radius: 7px;
                min-height: 20px;
                margin: 2px;
            }}
            
            QScrollArea QScrollBar::handle:vertical:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppColors.PRIMARY}, stop:1 {AppColors.PRIMARY_DARK});
            }}
            
            QScrollArea QScrollBar::handle:vertical:pressed {{
                background: {AppColors.PRIMARY_DARK};
            }}
            
            /* ГОРИЗОНТАЛЬНЫЙ СКРОЛЛБАР */
            QScrollArea QScrollBar:horizontal {{
                background: {AppColors.GRAY_100};
                height: 14px;
                border-radius: 7px;
                margin: 0px;
            }}
            
            QScrollArea QScrollBar::handle:horizontal {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.GRAY_400}, stop:1 {AppColors.GRAY_500});
                border-radius: 7px;
                min-width: 20px;
                margin: 2px;
            }}
            
            QScrollArea QScrollBar::handle:horizontal:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.PRIMARY}, stop:1 {AppColors.PRIMARY_DARK});
            }}
            
            /* СТРЕЛКИ СКРОЛЛБАРА - СКРЫТЬ */
            QScrollArea QScrollBar::add-line:vertical,
            QScrollArea QScrollBar::sub-line:vertical,
            QScrollArea QScrollBar::add-line:horizontal,
            QScrollArea QScrollBar::sub-line:horizontal {{
                border: none;
                background: none;
                width: 0px;
                height: 0px;
            }}
            
            /* УГЛЫ И ФОНЫ */
            QScrollArea QScrollBar::add-page:vertical,
            QScrollArea QScrollBar::sub-page:vertical,
            QScrollArea QScrollBar::add-page:horizontal,
            QScrollArea QScrollBar::sub-page:horizontal {{
                background: transparent;
            }}
            
            /* УГОЛ МЕЖДУ СКРОЛЛБАРАМИ */
            QScrollArea::corner {{
                background: {AppColors.GRAY_100};
            }}
        """
    @staticmethod
    def input_field():
        """Стили для полей ввода"""
        return f"""
            QLineEdit, QComboBox, QDateEdit, QSpinBox, QTextEdit {{
                border: 2px solid {AppColors.GRAY_300};
                border-radius: 6px;
                padding: 8px 12px;
                background: white;
                color: {AppColors.TEXT_PRIMARY};
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10pt;
                min-height: 32px;
            }}
            
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus, 
            QSpinBox:focus, QTextEdit:focus {{
                border-color: {AppColors.PRIMARY};
                background: {AppColors.GRAY_50};
            }}
            
            QLineEdit:hover, QComboBox:hover, QDateEdit:hover, 
            QSpinBox:hover, QTextEdit:hover {{
                border-color: {AppColors.GRAY_500};
            }}
            
            QLineEdit:disabled, QComboBox:disabled, QDateEdit:disabled, 
            QSpinBox:disabled, QTextEdit:disabled {{
                background: {AppColors.GRAY_100};
                border-color: {AppColors.GRAY_200};
                color: {AppColors.TEXT_DISABLED};
            }}
            
            /* Placeholder text */
            QLineEdit::placeholder {{
                color: {AppColors.TEXT_SECONDARY};
                font-style: italic;
            }}
            
            /* ComboBox dropdown */
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            
            QComboBox::down-arrow {{
                width: 12px;
                height: 12px;
            }}
            
            QComboBox QAbstractItemView {{
                border: 2px solid {AppColors.GRAY_300};
                background: white;
                selection-background-color: {AppColors.PRIMARY};
                selection-color: white;
            }}
        """
    
    @staticmethod
    def table_view():
        """Стили для таблиц"""
        return f"""
            QTableView {{
                background-color: white;
                alternate-background-color: {AppColors.GRAY_50};
                selection-background-color: {AppColors.PRIMARY};
                selection-color: white;
                gridline-color: {AppColors.GRAY_300};
                border: 2px solid {AppColors.GRAY_300};
                border-radius: 8px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10pt;
                outline: none;
            }}
            
            QTableView::item {{
                padding: 10px 8px;
                border: none;
                border-bottom: 1px solid {AppColors.GRAY_200};
                outline: none; 
            }}
            
            QTableView::item:selected {{
                background-color: {AppColors.PRIMARY};
                color: white;
            }}
            
            QTableView::item:hover {{
                background-color: {AppColors.PRIMARY_LIGHT};
            }}
            QTableWidget::item:focus {{
            border: none;           
            outline: none;          
            background: {AppColors.PRIMARY_LIGHT};
            outline: none;
            }}
            
            QHeaderView::section {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.PRIMARY}, stop:1 {AppColors.PRIMARY_DARK});
                color: white;
                font-weight: bold;
                padding: 12px 8px;
                border: none;
                border-right: 1px solid {AppColors.PRIMARY_DARK};
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10pt;
                outline: none;
            }}
            
            QHeaderView::section:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1E88E5, stop:1 #1565C0);
            }}
        """
    
    @staticmethod
    def tab_widget():
        """Стили для вкладок с ярким выделением"""
        return f"""
            QTabWidget::pane {{
                border: 2px solid {AppColors.GRAY_300};
                border-radius: 8px;
                background: white;
                margin-top: 2px;
            }}
            
            /* ОБЫЧНАЯ ВКЛАДКА (неактивная) */
            QTabBar::tab {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.GRAY_100}, stop:1 {AppColors.GRAY_200});
                border: 2px solid {AppColors.GRAY_300};
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 8px 16px;
                margin-right: 2px;
                color: {AppColors.GRAY_600};
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10pt;
                font-weight: 600;
                min-width: 160px;
                max-width: 250px;
            }}
            
            /* АКТИВНАЯ ВКЛАДКА (выбранная) - ЯРКОЕ ВЫДЕЛЕНИЕ */
            QTabBar::tab:selected {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.PRIMARY}, stop:1 {AppColors.PRIMARY_DARK});
                border: 3px solid {AppColors.PRIMARY_DARK};
                border-bottom: 3px solid white;
                color: white;
                font-weight: bold;
                font-size: 11pt;
                padding: 10px 18px;
            }}
            
            /* АКТИВНАЯ ВКЛАДКА - оставь только жирность */
            QTabBar::tab:selected {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.PRIMARY}, stop:1 {AppColors.PRIMARY_DARK});
                border: 3px solid {AppColors.PRIMARY_DARK};
                border-bottom: 3px solid white;
                color: white;
                font-weight: bold;
                font-size: 10pt;  /* ← УБЕРИ 11pt, оставь как у обычных */
                padding: 10px 18px;
            }}
            
            /* ОТКЛЮЧЕННАЯ ВКЛАДКА */
            QTabBar::tab:disabled {{
                background: {AppColors.GRAY_200};
                color: {AppColors.GRAY_400};
            }}
        """
    @staticmethod
    def checkbox_widget():
        """Стили для чекбоксов с современным дизайном"""
        return f"""
            QCheckBox {{
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10pt;
                font-weight: 500;
                color: {AppColors.GRAY_700};
                spacing: 8px;
                padding: 4px;
            }}
            
            /* КВАДРАТИК ЧЕКБОКСА (неотмеченный) */
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {AppColors.GRAY_400};
                border-radius: 4px;
                background: white;
            }}
            
            /* НАВЕДЕНИЕ на неотмеченный */
            QCheckBox::indicator:hover {{
                border: 2px solid {AppColors.PRIMARY};
                background: {AppColors.PRIMARY_LIGHT};
            }}
            
            /* ОТМЕЧЕННЫЙ чекбокс */
            QCheckBox::indicator:checked {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.PRIMARY}, stop:1 {AppColors.PRIMARY_DARK});
                border: 2px solid {AppColors.PRIMARY_DARK};
                image: url(:/icons/check-white.png);  /* или используй символ */
            }}
            
            /* НАВЕДЕНИЕ на отмеченный */
            QCheckBox::indicator:checked:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.PRIMARY_LIGHT}, stop:1 {AppColors.PRIMARY});
            }}
            
            /* ОТКЛЮЧЕННЫЙ неотмеченный */
            QCheckBox::indicator:disabled {{
                background: {AppColors.GRAY_200};
                border: 2px solid {AppColors.GRAY_300};
            }}
            
            /* ОТКЛЮЧЕННЫЙ отмеченный */
            QCheckBox::indicator:checked:disabled {{
                background: {AppColors.GRAY_400};
                border: 2px solid {AppColors.GRAY_400};
            }}
            
            /* ТЕКСТ отключенного чекбокса */
            QCheckBox:disabled {{
                color: {AppColors.GRAY_400};
            }}
            
            /* ЧАСТИЧНО ОТМЕЧЕННЫЙ (indeterminate) */
            QCheckBox::indicator:indeterminate {{
                background: {AppColors.PRIMARY};
                border: 2px solid {AppColors.PRIMARY_DARK};
                image: url(:/icons/minus-white.png);
            }}
        """
    @staticmethod
    def scroll_bar():
        """Стили для скроллбаров"""
        return f"""
            /* Вертикальный скроллбар */
            QScrollBar:vertical {{
                background: {AppColors.GRAY_100};
                width: 12px;
                border-radius: 6px;
                margin: 2px;
            }}
            
            QScrollBar::handle:vertical {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {AppColors.GRAY_500}, stop:1 {AppColors.GRAY_700});
                border-radius: 6px;
                min-height: 30px;
                margin: 2px;
            }}
            
            QScrollBar::handle:vertical:hover {{
                background: {AppColors.GRAY_700};
            }}
            
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                border: none;
                background: none;
                height: 0px;
            }}
            
            /* Горизонтальный скроллбар */
            QScrollBar:horizontal {{
                background: {AppColors.GRAY_100};
                height: 12px;
                border-radius: 6px;
                margin: 2px;
            }}
            
            QScrollBar::handle:horizontal {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {AppColors.GRAY_500}, stop:1 {AppColors.GRAY_700});
                border-radius: 6px;
                min-width: 30px;
                margin: 2px;
            }}
            
            QScrollBar::handle:horizontal:hover {{
                background: {AppColors.GRAY_700};
            }}
            
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {{
                border: none;
                background: none;
                width: 0px;
            }}
        """
    
    @staticmethod
    def group_box():
        """Стили для группировок"""
        return f"""
            QGroupBox {{
                border: 2px solid {AppColors.PRIMARY};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 16px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 11pt;
                font-weight: bold;
                color: {AppColors.TEXT_PRIMARY};
            }}
            
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 8px;
                background: white;
                color: {AppColors.PRIMARY};
            }}
        """
    
    @staticmethod
    def menu():
        """Стили для контекстных меню"""
        return f"""
            QMenu {{
                background: white;
                border: 2px solid {AppColors.GRAY_300};
                border-radius: 8px;
                padding: 6px;
            }}
            
            QMenu::item {{
                padding: 10px 20px;
                border-radius: 6px;
                color: {AppColors.TEXT_PRIMARY};
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10pt;
            }}
            
            QMenu::item:selected {{
                background: {AppColors.PRIMARY};
                color: white;
            }}
            
            QMenu::item:disabled {{
                color: {AppColors.TEXT_DISABLED};
            }}
            
            QMenu::separator {{
                height: 1px;
                background: {AppColors.GRAY_300};
                margin: 6px 10px;
            }}
        """
    
    @staticmethod
    def dialog():
        """Общие стили для диалогов"""
        return f"""
            QDialog {{
                background: {AppColors.GRAY_50};
                font-family: 'Segoe UI', Arial, sans-serif;
            }}
        """
    
    @staticmethod
    def label_header():
        """Стили для заголовков"""
        return f"""
            QLabel {{
                font-size: 14pt;
                font-weight: bold;
                color: {AppColors.PRIMARY};
                padding: 8px 0;
            }}
        """
    
    @staticmethod
    def label_secondary():
        """Стили для вторичного текста"""
        return f"""
            QLabel {{
                color: {AppColors.TEXT_SECONDARY};
                font-size: 9pt;
            }}
        """


class AppLayout:
    """
    Стандартные размеры и отступы
    """
    
    # ===============================================
    # ОТСТУПЫ МЕЖДУ ЭЛЕМЕНТАМИ (SPACING)
    # ===============================================
    SPACING_XS = 4    # Минимальное расстояние
    SPACING_SM = 8    # Малое расстояние
    SPACING_MD = 12   # Среднее расстояние
    SPACING_LG = 16   # Большое расстояние
    SPACING_XL = 24   # Очень большое расстояние
    SPACING_XXL = 32  # Максимальное расстояние
    
    # ===============================================
    # ВНЕШНИЕ ОТСТУПЫ (MARGINS)
    # ===============================================
    MARGIN_XS = 4
    MARGIN_SM = 8
    MARGIN_MD = 12
    MARGIN_LG = 16
    MARGIN_XL = 20
    
    # ===============================================
    # ВНУТРЕННИЕ ОТСТУПЫ (PADDING)
    # ===============================================
    PADDING_XS = 4
    PADDING_SM = 8
    PADDING_MD = 12
    PADDING_LG = 16
    
    # ===============================================
    # РАДИУСЫ СКРУГЛЕНИЯ
    # ===============================================
    RADIUS_SM = 4    # Малое скругление
    RADIUS_MD = 6    # Среднее скругление
    RADIUS_LG = 8    # Большое скругление
    RADIUS_XL = 12   # Очень большое скругление
    
    # ===============================================
    # ВЫСОТА ЭЛЕМЕНТОВ
    # ===============================================
    INPUT_HEIGHT = 36        # Поля ввода
    BUTTON_SM = 32          # Маленькие кнопки
    BUTTON_MD = 40          # Средние кнопки
    BUTTON_LG = 48          # Большие кнопки
    HEADER_HEIGHT = 60      # Заголовки
    ROW_HEIGHT = 40         # Строки таблицы
    
    # ===============================================
    # ШИРИНА ЭЛЕМЕНТОВ
    # ===============================================
    SIDEBAR_WIDTH = 300     # Боковая панель
    MIN_DIALOG_WIDTH = 400  # Минимальная ширина диалога
    MAX_DIALOG_WIDTH = 1200 # Максимальная ширина диалога


# ===============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ===============================================

def combine_styles(*styles):
    """
    Объединить несколько стилей в один
    
    Пример:
        style = combine_styles(
            AppStyles.button_primary(),
            "QPushButton { min-width: 150px; }"
        )
    """
    return "\n".join(styles)


def apply_shadow(widget, blur=10, offset_x=0, offset_y=2, color=(0, 0, 0, 50)):
    """
    Применить тень к виджету (требует QGraphicsDropShadowEffect)
    
    Пример:
        from PyQt5.QtWidgets import QGraphicsDropShadowEffect
        apply_shadow(button)
    """
    try:
        from PyQt5.QtWidgets import QGraphicsDropShadowEffect
        from PyQt5.QtGui import QColor
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(blur)
        shadow.setXOffset(offset_x)
        shadow.setYOffset(offset_y)
        shadow.setColor(QColor(*color))
        widget.setGraphicsEffect(shadow)
    except ImportError:
        print("⚠️ QGraphicsDropShadowEffect недоступен")
from PyQt5.QtWidgets import QStyledItemDelegate

class CalendarDelegate(QStyledItemDelegate):
    """Делегат для подсветки дат при наведении"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hovered_index = None
    
    def paint(self, painter, option, index):
        
        from PyQt5.QtCore import QRect
        from PyQt5.QtGui import QPen, QBrush
        
        # Если это наведенная ячейка - рисуем подсветку
        if index == self.hovered_index and option.state & QStyle.State_Enabled:
            painter.save()
            
            # Рисуем фон
            painter.setBrush(QBrush(QColor(AppColors.PRIMARY_LIGHT)))
            painter.setPen(QPen(QColor(AppColors.PRIMARY), 2))
            painter.drawRoundedRect(option.rect.adjusted(2, 2, -2, -2), 8, 8)
            
            painter.restore()
        
        # Стандартная отрисовка
        super().paint(painter, option, index)

class EnhancedDateEdit(QDateEdit):
    """Улучшенный QDateEdit - ФИНАЛЬНАЯ ВЕРСИЯ"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._calendar_configured = False
        self.setup_enhanced_features()
    
    def setup_enhanced_features(self):
        """Настройка улучшенных возможностей"""
        
        
        # Устанавливаем стиль
        self.setStyleSheet(AppStyles.date_edit_style())
        
        # Календарь появляется при клике
        self.setCalendarPopup(True)
        
        # Формат отображения даты
        self.setDisplayFormat("dd.MM.yyyy")
        
        # Размер виджета
        self.setMinimumWidth(140)
        self.setFixedHeight(40)
        
        # Устанавливаем по умолчанию сегодняшнюю дату
        self.setDate(QDate.currentDate())
        
        # Контекстное меню
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        # Подключаемся к сигналу открытия календаря
        self.dateChanged.connect(self._on_date_changed)
        # ❗️ КРИТИЧНО: Добавьте в конце этого метода:
        self.setFocusPolicy(Qt.StrongFocus)
        # Изначально отключаем шаговое изменение
    def showPopup(self):
        """Переопределяем открытие календаря для настройки"""
        super().showPopup()
        
        # Настраиваем календарь при первом показе
        calendar = self.calendarWidget()
        if calendar and not self._calendar_configured:
            self.setup_calendar(calendar)
            self._calendar_configured = True
            
            # ВАЖНО: Фиксируем размер календаря - УВЕЛИЧЕННЫЙ!
            calendar.setFixedSize(400, 350)
            
            # Подключаемся к сигналу смены месяца для переустановки форматирования
            calendar.currentPageChanged.connect(self._reapply_calendar_formatting)
    
    def setup_calendar(self, calendar):
        """Настройка виджета календаря"""
        
        
        # Первый день недели - понедельник
        calendar.setFirstDayOfWeek(Qt.Monday)
        
        # Показывать номера недель
        calendar.setVerticalHeaderFormat(QCalendarWidget.ISOWeekNumbers)
        
        # Навигация по сетке
        calendar.setNavigationBarVisible(True)
        calendar.setGridVisible(True)
        table_view = calendar.findChild(QTableView)
        if table_view:
            delegate = CalendarDelegate(table_view)
            table_view.setItemDelegate(delegate)
            table_view.setMouseTracking(True)
            table_view.viewport().setMouseTracking(True)
            
            # Обработчик движения мыши
            def mouse_move_handler(event):
                index = table_view.indexAt(event.pos())
                if index.isValid():
                    delegate.hovered_index = index
                    table_view.viewport().update()
                else:
                    delegate.hovered_index = None
                    table_view.viewport().update()
            
            table_view.viewport().mouseMoveEvent = mouse_move_handler
        # Применяем форматирование
        self._apply_calendar_formatting(calendar)
    def wheelEvent(self, event):
        """Блокировка прокрутки колесом мыши"""
        event.ignore()  # Всегда игнорируем, не важно в фокусе или нет
    
    def stepEnabled(self):
        """Отключаем шаговое изменение через клавиатуру и мышь"""
        return QAbstractSpinBox.StepNone
    
    def stepBy(self, steps):
        """Переопределяем шаговое изменение — ничего не делаем"""
        pass  # Пусто, значение не меняется
    def _apply_calendar_formatting(self, calendar):
        """Применить форматирование календаря"""
        
        
        # Выделение выходных дней
        weekend_format = QTextCharFormat()
        weekend_format.setForeground(QColor(AppColors.DANGER))
        weekend_format.setFontWeight(QFont.Bold)
        
        calendar.setWeekdayTextFormat(Qt.Saturday, weekend_format)
        calendar.setWeekdayTextFormat(Qt.Sunday, weekend_format)
        
        # Выделение текущего дня
        today_format = QTextCharFormat()
        today_format.setBackground(QColor(AppColors.WARNING_LIGHT))
        today_format.setForeground(QColor(AppColors.WARNING_DARK))
        today_format.setFontWeight(QFont.Bold)
        
        calendar.setDateTextFormat(QDate.currentDate(), today_format)
    
    def _reapply_calendar_formatting(self, year, month):
        """Переприменить форматирование при смене месяца"""
        calendar = self.calendarWidget()
        if calendar:
            self._apply_calendar_formatting(calendar)
    
    def _on_date_changed(self, date):
        """Обработчик изменения даты"""
        # Дополнительная проверка календаря
        calendar = self.calendarWidget()
        if calendar:
            self._apply_calendar_formatting(calendar)
    
    def show_context_menu(self, position):
        """Контекстное меню с быстрыми действиями"""
        
        
        menu = QMenu(self)
        menu.setStyleSheet(AppStyles.menu())
        
        # Действия
        today_action = QAction("📅 Сегодня", self)
        today_action.triggered.connect(lambda: self.setDate(QDate.currentDate()))
        
        yesterday_action = QAction("⬅️ Вчера", self)
        yesterday_action.triggered.connect(
            lambda: self.setDate(QDate.currentDate().addDays(-1)))
        
        tomorrow_action = QAction("➡️ Завтра", self)
        tomorrow_action.triggered.connect(
            lambda: self.setDate(QDate.currentDate().addDays(1)))
        
        menu.addAction(today_action)
        menu.addSeparator()
        menu.addAction(yesterday_action)
        menu.addAction(tomorrow_action)
        menu.addSeparator()
        
        # Навигация по месяцам
        prev_month_action = QAction("◀️ Предыдущий месяц", self)
        prev_month_action.triggered.connect(
            lambda: self.setDate(self.date().addMonths(-1)))
        
        next_month_action = QAction("▶️ Следующий месяц", self)
        next_month_action.triggered.connect(
            lambda: self.setDate(self.date().addMonths(1)))
        
        menu.addAction(prev_month_action)
        menu.addAction(next_month_action)
        menu.addSeparator()
        
        # Очистка
        clear_action = QAction("❌ Очистить", self)
        clear_action.triggered.connect(lambda: self.setDate(QDate.currentDate()))
        menu.addAction(clear_action)
        
        menu.exec_(self.mapToGlobal(position))
    
    def keyPressEvent(self, event):
        """Обработка горячих клавиш"""
        # Ctrl+T - сегодня
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_T:
            self.setDate(QDate.currentDate())
            return
        
        # Ctrl+Left - предыдущий день
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Left:
            self.setDate(self.date().addDays(-1))
            return
        
        # Ctrl+Right - следующий день
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Right:
            self.setDate(self.date().addDays(1))
            return
        
        # Ctrl+Up - предыдущий месяц
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Up:
            self.setDate(self.date().addMonths(-1))
            return
        
        # Ctrl+Down - следующий месяц
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Down:
            self.setDate(self.date().addMonths(1))
            return
        
        super().keyPressEvent(event)
class ModernToggleSwitch(QWidget):
    """
    Современный toggle switch в стиле iOS/Material Design - ИСПРАВЛЕНО
    """
    toggled = pyqtSignal(bool)
    
    def __init__(self, parent=None, width=120, height=50):
        super().__init__(parent)
        
        self.setFixedSize(width, height)
        self.setCursor(Qt.PointingHandCursor)
        
        # Состояния
        self._checked = False
        self._enabled = True
        
        # Анимация - ИСПРАВЛЕНО: используем QVariantAnimation вместо QPropertyAnimation
        self._circle_pos = 5
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(200)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self._animation.valueChanged.connect(self._on_animation_value_changed)
        
        # Цвета
        self.bg_color_off = QColor("#E0E0E0")
        self.bg_color_on = QColor("#2196F3")
        self.circle_color = QColor("#FFFFFF")
        self.text_color = QColor("#424242")
        
        # Текст
        self.text_on = "Диапазон"
        self.text_off = "Один день"
        
        # УБИРАЕМ setStyleSheet - не нужно для кастомного виджета
    
    def _on_animation_value_changed(self, value):
        """Обработчик изменения значения анимации"""
        self._circle_pos = value
        self.update()
    
    def setChecked(self, checked):
        if self._checked != checked:
            self._checked = checked
            self.animate_toggle()
            self.toggled.emit(checked)
    
    def isChecked(self):
        return self._checked
    
    def animate_toggle(self):
        """Анимация переключения - ИСПРАВЛЕНО"""
        start_pos = self._circle_pos
        end_pos = self.width() - 45 if self._checked else 5
        
        self._animation.setStartValue(start_pos)
        self._animation.setEndValue(end_pos)
        self._animation.start()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._enabled:
            self.setChecked(not self._checked)
        super().mousePressEvent(event)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Фон переключателя
        bg_color = self.bg_color_on if self._checked else self.bg_color_off
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 25, 25)
        
        # Кружок
        circle_size = 28  # Уменьшили размер кружка
        circle_y = (self.height() - circle_size) // 2  # Центрируем по вертикали
        circle_x = int(self._circle_pos)
        circle_rect = QRect(circle_x, circle_y, circle_size, circle_size)
        painter.setBrush(QBrush(self.circle_color))
        painter.drawEllipse(circle_rect)
        
        # Тень кружка (опционально)
        painter.setBrush(QBrush(QColor(0, 0, 0, 20)))
        shadow_rect = QRect(circle_x + 2, circle_y + 2, circle_size, circle_size)
        painter.drawEllipse(shadow_rect)
        
        # Текст
        painter.setPen(QPen(self.text_color))
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        
        if self._checked:
            text_rect = QRect(8, 0, 70, self.height())
            painter.drawText(text_rect, Qt.AlignCenter, self.text_on)
        else:
            text_rect = QRect(50, 0, 70, self.height())
            painter.drawText(text_rect, Qt.AlignCenter, self.text_off)
    
    def setText(self, text_on, text_off):
        """Установить тексты для состояний"""
        self.text_on = text_on
        self.text_off = text_off
        self.update()


class SegmentedControl(QWidget):
    """
    Сегментированный контрол в стиле iOS - ИСПРАВЛЕНО
    """
    selectionChanged = pyqtSignal(int)
    
    def __init__(self, items, parent=None):
        super().__init__(parent)
        
        self.items = items
        self.selected_index = 0
        self.button_rects = []
        
        # Размеры
        self.setMinimumHeight(40)
        self.setMinimumWidth(len(items) * 100)
        self.setCursor(Qt.PointingHandCursor)
        
        # Анимация - ИСПРАВЛЕНО
        self._selection_pos = 0
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(250)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self._animation.valueChanged.connect(self._on_selection_animation_changed)
        
        self.calculate_rects()
    
    def _on_selection_animation_changed(self, value):
        """Обработчик анимации выделения"""
        self._selection_pos = value
        self.update()
    
    def calculate_rects(self):
        """Вычислить прямоугольники кнопок"""
        self.button_rects = []
        if self.width() > 0:  # ИСПРАВЛЕНО: проверяем ширину
            button_width = self.width() / len(self.items)
            
            for i in range(len(self.items)):
                rect = QRectF(i * button_width, 0, button_width, self.height())
                self.button_rects.append(rect)
    
    def resizeEvent(self, event):
        self.calculate_rects()
        super().resizeEvent(event)
    
    def showEvent(self, event):
        """ДОБАВЛЕНО: пересчитываем при показе"""
        self.calculate_rects()
        super().showEvent(event)
    
    def setSelectedIndex(self, index):
        """Установить выбранный элемент"""
        if 0 <= index < len(self.items) and index != self.selected_index:
            old_index = self.selected_index
            self.selected_index = index
            
            # Анимация перемещения - ИСПРАВЛЕНО
            if self.button_rects and len(self.button_rects) > index:
                start_pos = self._selection_pos
                end_pos = self.button_rects[index].x()
                
                self._animation.setStartValue(start_pos)
                self._animation.setEndValue(end_pos)
                self._animation.start()
            
            self.selectionChanged.emit(index)
    
    def mousePressEvent(self, event):
        """Обработка клика"""
        if event.button() == Qt.LeftButton:
            for i, rect in enumerate(self.button_rects):
                if rect.contains(event.pos()):
                    self.setSelectedIndex(i)
                    break
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Фон контрола
        bg_rect = QRectF(0, 0, self.width(), self.height())
        painter.setBrush(QBrush(QColor("#F0F0F0")))
        painter.setPen(QPen(QColor("#D0D0D0"), 2))
        painter.drawRoundedRect(bg_rect, 20, 20)
        
        # Выбранный сегмент - ИСПРАВЛЕНО
        if self.button_rects and len(self.button_rects) > 0:
            button_width = self.width() / len(self.items)
            selected_rect = QRectF(self._selection_pos + 4, 4, button_width - 8, self.height() - 8)
            
            painter.setBrush(QBrush(QColor("#2196F3")))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(selected_rect, 16, 16)
        
        # Текст элементов
        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        
        for i, (rect, text) in enumerate(zip(self.button_rects, self.items)):
            if i == self.selected_index:
                painter.setPen(QPen(QColor("#FFFFFF")))
            else:
                painter.setPen(QPen(QColor("#666666")))
            
            painter.drawText(rect, Qt.AlignCenter, text)


class SliderToggle(QWidget):
    """
    Переключатель-слайдер с подписями - ИСПРАВЛЕНО
    """
    valueChanged = pyqtSignal(int)
    
    def __init__(self, label_left="Один день", label_right="Диапазон", parent=None):
        super().__init__(parent)
        
        self.label_left = label_left
        self.label_right = label_right
        self.current_value = 0
        
        self.setFixedSize(280, 60)
        self.setCursor(Qt.PointingHandCursor)
        
        self.track_rect = QRect(40, 20, 200, 20)
        self.thumb_rect = QRect(35, 15, 30, 30)
        
        # Анимация - ИСПРАВЛЕНО
        self._thumb_x = 35
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(300)
        self._animation.setEasingCurve(QEasingCurve.OutBack)
        self._animation.valueChanged.connect(self._on_thumb_animation_changed)
    
    def _on_thumb_animation_changed(self, value):
        """Обработчик анимации ползунка"""
        self._thumb_x = value
        self.thumb_rect.moveLeft(value)
        self.update()
    
    def setValue(self, value):
        """Установить значение (0 или 1)"""
        if value != self.current_value:
            self.current_value = value
            
            # Анимация - ИСПРАВЛЕНО
            start_x = self._thumb_x
            end_x = 215 if value == 1 else 35
            
            self._animation.setStartValue(start_x)
            self._animation.setEndValue(end_x)
            self._animation.start()
            
            self.valueChanged.emit(value)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            click_x = event.pos().x()
            new_value = 1 if click_x > self.width() / 2 else 0
            self.setValue(new_value)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Трек слайдера
        painter.setBrush(QBrush(QColor("#E0E0E0")))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.track_rect, 10, 10)
        
        # Активная часть трека
        if self.current_value == 1:
            active_rect = QRect(self.track_rect.x(), self.track_rect.y(), 
                              int(self._thumb_x) - self.track_rect.x() + 15, self.track_rect.height())
            painter.setBrush(QBrush(QColor("#4CAF50")))
            painter.drawRoundedRect(active_rect, 10, 10)
        
        # Ползунок
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.setPen(QPen(QColor("#CCCCCC"), 2))
        painter.drawEllipse(self.thumb_rect)
        
        # Подсветка ползунка
        highlight_rect = QRect(self.thumb_rect.x() + 5, self.thumb_rect.y() + 5, 20, 20)
        if self.current_value == 1:
            painter.setBrush(QBrush(QColor("#4CAF50")))
        else:
            painter.setBrush(QBrush(QColor("#2196F3")))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(highlight_rect)
        
        # Подписи
        painter.setPen(QPen(QColor("#424242")))
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        
        # Левая подпись
        left_color = "#2196F3" if self.current_value == 0 else "#999999"
        painter.setPen(QPen(QColor(left_color)))
        painter.drawText(QRect(0, 45, 100, 15), Qt.AlignLeft, self.label_left)
        
        # Правая подпись  
        right_color = "#4CAF50" if self.current_value == 1 else "#999999"
        painter.setPen(QPen(QColor(right_color)))
        painter.drawText(QRect(180, 45, 100, 15), Qt.AlignRight, self.label_right)


class CompactDateEdit(EnhancedDateEdit):
    """Компактная версия DateEdit для узких панелей"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setMinimumWidth(120)
        
        # Упрощенный формат
        self.setDisplayFormat("dd.MM.yy")
    
    def showPopup(self):
        """Переопределяем для компактного календаря"""
        super().showPopup()
        
        calendar = self.calendarWidget()
        if calendar:
            # Компактный размер
            calendar.setFixedSize(340, 300)
            calendar.setGridVisible(False)
            calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
class CompactDateEdit(EnhancedDateEdit):
    """Компактная версия DateEdit для узких панелей"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setMinimumWidth(120)
        
        # Упрощенный формат
        self.setDisplayFormat("dd.MM.yy")
    
    def showPopup(self):
        """Переопределяем для компактного календаря"""
        super().showPopup()
        
        calendar = self.calendarWidget()
        if calendar:
            # Компактный размер
            calendar.setFixedSize(300, 280)
            calendar.setGridVisible(False)
            calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
# ===============================================
# ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ
# ===============================================

if __name__ == "__main__":
    print("📦 Модуль ui_styles.py успешно импортирован!")
    print("\n✅ Доступные классы:")
    print("   - AppColors: Цветовая палитра")
    print("   - AppStyles: Готовые CSS-стили")
    print("   - AppLayout: Размеры и отступы")
    print("\n💡 Пример использования:")
    print("""
    from ui_styles import AppColors, AppStyles, AppLayout
    
    # Применить стиль к кнопке
    button.setStyleSheet(AppStyles.button_primary())
    
    # Использовать цвета
    label.setStyleSheet(f"color: {AppColors.PRIMARY};")
    
    # Использовать размеры
    layout.setSpacing(AppLayout.SPACING_MD)
    """)