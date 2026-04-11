"""
Тёплая бежевая палитра для GUI агента (Qt stylesheets и константы).
"""

from __future__ import annotations

# --- Базовые поверхности ---
BG_PAGE = "#f2ebe0"
BG_CARD = "#faf6ef"
BG_CARD_ALT = "#f7f1e8"
BG_INPUT = "#fffdf9"
BORDER = "#d4c4b0"
BORDER_SOFT = "#e5d9ca"
TEXT_PRIMARY = "#2a2319"
TEXT_SECONDARY = "#5a5248"
TEXT_MUTED = "#7d7366"
ACCENT = "#8b6914"
ACCENT_SOFT = "#c9a227"
PRIMARY_BTN = "#9a7b4f"
PRIMARY_BTN_HOVER = "#7f6540"
PRIMARY_BTN_TEXT = "#fffdf9"
DANGER_BG = "#f8e8e4"
DANGER_FG = "#9a3412"
DANGER_BORDER = "#e7b5a8"
INFO_BG = "#ebe3d4"
INFO_FG = "#5c4a2e"
LINK = "#6b5a3a"
SELECTION = "#c4a574"

# Список тикетов
LIST_ITEM_BG = "#fffdf9"
LIST_ITEM_BORDER = BORDER_SOFT
LIST_ITEM_HOVER = "#f0e8dc"
LIST_ITEM_HOVER_BORDER = "#c9b89a"
LIST_ITEM_SELECTED_BG = "#e8dcc8"
LIST_ITEM_SELECTED_BORDER = ACCENT

# Статусы тикетов (fg, bg) — приглушённые тёплые тона
STATUS_COLORS_WARM: dict[str, tuple[str, str]] = {
    "new": ("#1e4d8c", "#d8e4f5"),
    "triaged": ("#5b3d7a", "#e8dff2"),
    "in_progress": ("#1d6b5c", "#d4efe8"),
    "waiting_on_user": ("#8a5b12", "#f5e9c9"),
    "waiting_on_vendor": ("#7a4a1a", "#f0e0b8"),
    "resolved": ("#1f5c45", "#d5ebe0"),
    "closed": ("#5c564c", "#e8e4de"),
    "unknown": ("#5c564c", "#e8e4de"),
}

# Пузыри чата
BUBBLE_SELF_BG = "#e8dfd0"
BUBBLE_SELF_BORDER = "#c9b89a"
BUBBLE_SELF_FG = "#2a2319"
BUBBLE_SUPPORT_BG = "#dde8d4"
BUBBLE_SUPPORT_BORDER = "#a8bc96"
BUBBLE_SUPPORT_FG = "#1e3318"
BUBBLE_EVENT_BG = "#f2ebe3"
BUBBLE_EVENT_BORDER = BORDER_SOFT
BUBBLE_EVENT_FG = TEXT_SECONDARY
BUBBLE_EVENT_MUTED = TEXT_MUTED

# Область таймлайна (только непрозрачные цвета — иначе на Windows «двойной экран» / смаз)
TIMELINE_SCROLL_BG = "#ebe4d8"

# Фон корня экрана чата (без alpha)
CHAT_SCREEN_SOLID_OPEN = "#e6dfd3"
CHAT_SCREEN_SOLID_RESOLVED = "#d2e0d6"
CHAT_SCREEN_SOLID_CLOSED = "#dbd6ce"

# Кнопка «Отправить» в чате — выше контраст
CHAT_SEND_BG = "#5a4030"
CHAT_SEND_BG_HOVER = "#6d4f3b"
CHAT_SEND_BORDER = "#3d2a1f"
CHAT_SEND_TEXT = "#fffdf8"

# Типографика (pt — стабильнее на Windows, чем наследование QFont с pointSize -1)
UI_FONT_FAMILY = 'Segoe UI", "Tahoma", "Noto Sans'
UI_FONT_PT = 10
BODY_PT = 11
TITLE_PT = 12
BUBBLE_BODY_PT = 14


def chat_panel_stylesheet() -> str:
    return f"""
        QWidget#AgentChatPanel {{
            background-color: {BG_PAGE};
        }}
        QStackedWidget#TicketStack {{
            background-color: {BG_PAGE};
        }}
        QWidget#TicketListScreen, QWidget#ChatScreenRoot {{
            background-color: {BG_PAGE};
        }}
        QWidget {{
            font-family: {UI_FONT_FAMILY};
            font-size: {UI_FONT_PT}pt;
            color: {TEXT_PRIMARY};
            background-color: transparent;
        }}
        QGroupBox {{
            font-weight: 700;
            font-size: {TITLE_PT}pt;
            border: 1px solid {BORDER};
            border-radius: 20px;
            margin-top: 12px;
            background: {BG_CARD};
        }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 4px 8px; }}
        QListWidget {{
            font-family: {UI_FONT_FAMILY};
            font-size: {UI_FONT_PT}pt;
            border: none;
            background: transparent;
            outline: none;
            padding: 2px;
        }}
        QListView {{
            font-family: {UI_FONT_FAMILY};
            font-size: {UI_FONT_PT}pt;
            border: none;
            background: {BG_CARD_ALT};
            outline: none;
            padding: 4px;
            border-radius: 16px;
        }}
        /* Viewport — дочерний QWidget; иначе матчится QWidget{{transparent}} и на Windows даёт чёрный/битый фон */
        QListView#TicketsListView > QWidget {{
            background-color: {BG_CARD_ALT};
        }}
        QListView::item {{
            border: none;
            background: transparent;
            padding: 0px;
            margin: 0px;
        }}
        QListView::item:selected {{ background: transparent; }}
        QListView::item:hover {{ background: transparent; }}
        QPushButton {{
            border: 1px solid {BORDER};
            border-radius: 14px;
            background: {BG_INPUT};
            padding: 10px 18px;
            min-height: 22px;
            font-weight: 600;
            font-size: {BODY_PT}pt;
        }}
        QPushButton:hover {{ background: {LIST_ITEM_HOVER}; border-color: {LIST_ITEM_HOVER_BORDER}; }}
        QPushButton#SecondaryButton {{
            background: {BG_CARD_ALT};
            color: {TEXT_PRIMARY};
            font-weight: 700;
        }}
        QPushButton#SecondaryButton:hover {{ background: {LIST_ITEM_HOVER}; }}
        QToolButton {{
            border: 2px solid {BORDER};
            border-radius: 14px;
            background: {BG_INPUT};
            padding: 10px 14px;
            font-size: 12pt;
            font-weight: 700;
            min-width: 44px;
            min-height: 40px;
            color: {TEXT_PRIMARY};
        }}
        QToolButton:hover {{ background: {LIST_ITEM_HOVER}; border-color: {ACCENT}; }}
        QToolButton#JumpToLatestButton {{
            min-width: 48px;
            min-height: 48px;
            max-width: 48px;
            max-height: 48px;
            padding: 0px;
            border-radius: 24px;
            border: 1px solid {PRIMARY_BTN};
            background: {PRIMARY_BTN};
            color: {PRIMARY_BTN_TEXT};
            font-size: 16pt;
            font-weight: 800;
            margin: 0 16px 16px 0;
        }}
        QToolButton#JumpToLatestButton:hover {{
            background: {PRIMARY_BTN_HOVER};
            border-color: {PRIMARY_BTN_HOVER};
        }}
        QPushButton#PrimaryButton {{
            background: {PRIMARY_BTN};
            color: {PRIMARY_BTN_TEXT};
            border-color: {PRIMARY_BTN};
            font-weight: 700;
            font-size: {BODY_PT}pt;
            padding: 12px 22px;
            min-height: 24px;
        }}
        QPushButton#PrimaryButton:hover {{ background: {PRIMARY_BTN_HOVER}; }}
        QPushButton#ChatSendButton {{
            background-color: {CHAT_SEND_BG};
            color: {CHAT_SEND_TEXT};
            border: 2px solid {CHAT_SEND_BORDER};
            font-weight: 800;
            font-size: 12pt;
            padding: 14px 28px;
            min-width: 150px;
            min-height: 28px;
        }}
        QPushButton#ChatSendButton:hover {{
            background-color: {CHAT_SEND_BG_HOVER};
            border-color: {CHAT_SEND_BORDER};
        }}
        QPushButton#ChatSendButton:pressed {{
            background-color: {CHAT_SEND_BORDER};
        }}
        QPushButton#DangerButton {{
            background: {DANGER_BG};
            color: {DANGER_FG};
            border-color: {DANGER_BORDER};
            font-weight: 700;
        }}
        QPushButton#DangerButton:hover {{ background: #f0ddd8; }}
        QPushButton#DangerButton:disabled {{
            background: {BG_CARD_ALT};
            color: {TEXT_MUTED};
            border-color: {BORDER_SOFT};
        }}
        QLineEdit, QTextEdit, QComboBox {{
            border: 1px solid {BORDER};
            border-radius: 14px;
            background: {BG_INPUT};
            padding: 10px 14px;
            font-size: {BODY_PT}pt;
            selection-background-color: {SELECTION};
            selection-color: {TEXT_PRIMARY};
        }}
        QLineEdit#ChatInputLine {{
            border: 2px solid {BORDER};
            padding: 12px 16px;
            font-size: {BUBBLE_BODY_PT}pt;
            background: {LIST_ITEM_BG};
        }}
        QLineEdit#ChatInputLine:focus {{ border-color: {ACCENT}; }}
        QScrollArea#TimelineScroll {{
            background-color: {TIMELINE_SCROLL_BG};
            border: 1px solid {BORDER};
            border-radius: 22px;
        }}
        QScrollArea#TimelineScroll > QWidget > QWidget {{
            background-color: {TIMELINE_SCROLL_BG};
        }}
        QScrollArea#TimelineScroll QScrollBar:vertical {{
            background: #dfd5c7;
            width: 12px;
            margin: 8px 6px 8px 0px;
            border-radius: 8px;
        }}
        QScrollArea#TimelineScroll QScrollBar::handle:vertical {{
            background: #a68b6a;
            min-height: 40px;
            border-radius: 8px;
        }}
        QScrollArea#TimelineScroll QScrollBar::add-line:vertical,
        QScrollArea#TimelineScroll QScrollBar::sub-line:vertical {{ height: 0px; }}
        QScrollArea#TimelineScroll QScrollBar:vertical:hover,
        QScrollArea#TimelineScroll QScrollBar:vertical:pressed {{
            background: #d4c4b0;
        }}
        QComboBox QAbstractItemView,
        QMenu,
        QMenu#AgentPopupMenu {{
            background: {BG_INPUT};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER};
            border-radius: 14px;
            outline: none;
            padding: 6px;
        }}
        QComboBox QAbstractItemView::item,
        QMenu::item,
        QMenu#AgentPopupMenu::item {{
            background: transparent;
            border-radius: 10px;
            padding: 8px 12px;
            margin: 2px 0px;
        }}
        QComboBox QAbstractItemView::item:selected,
        QMenu::item:selected,
        QMenu#AgentPopupMenu::item:selected {{
            background: {LIST_ITEM_HOVER};
            color: {TEXT_PRIMARY};
        }}
        QMenu::separator,
        QMenu#AgentPopupMenu::separator {{
            height: 1px;
            background: {BORDER_SOFT};
            margin: 6px 10px;
        }}
    """


def agent_dialog_stylesheet() -> str:
    """QSS для модальных QDialog (настройки, профили): тёплый фон без «прозрачного» чёрного на Windows."""
    return f"""
        QDialog#AgentAppDialog {{
            background-color: {BG_PAGE};
        }}
        QWidget {{
            font-family: {UI_FONT_FAMILY};
            font-size: {UI_FONT_PT}pt;
            color: {TEXT_PRIMARY};
            background-color: transparent;
        }}
        QLabel {{
            color: {TEXT_PRIMARY};
            background-color: transparent;
        }}
        QGroupBox {{
            font-weight: 700;
            font-size: {TITLE_PT}pt;
            border: 1px solid {BORDER};
            border-radius: 16px;
            margin-top: 12px;
            background: {BG_CARD};
            padding-top: 8px;
        }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 4px 8px; }}
        QListWidget {{
            font-family: {UI_FONT_FAMILY};
            font-size: {UI_FONT_PT}pt;
            border: 1px solid {BORDER};
            background-color: {BG_CARD_ALT};
            border-radius: 14px;
            padding: 6px;
            outline: none;
        }}
        QListWidget::item {{
            padding: 6px 8px;
            border-radius: 8px;
        }}
        QListWidget::item:selected {{
            background: {LIST_ITEM_SELECTED_BG};
            color: {TEXT_PRIMARY};
        }}
        QListWidget::item:hover {{
            background: {LIST_ITEM_HOVER};
        }}
        QPushButton {{
            border: 1px solid {BORDER};
            border-radius: 14px;
            background: {BG_INPUT};
            padding: 10px 18px;
            min-height: 22px;
            font-weight: 600;
            font-size: {BODY_PT}pt;
            color: {TEXT_PRIMARY};
        }}
        QPushButton:hover {{ background: {LIST_ITEM_HOVER}; border-color: {LIST_ITEM_HOVER_BORDER}; }}
        QPushButton#PrimaryButton {{
            background: {PRIMARY_BTN};
            color: {PRIMARY_BTN_TEXT};
            border-color: {PRIMARY_BTN};
            font-weight: 700;
        }}
        QPushButton#PrimaryButton:hover {{ background: {PRIMARY_BTN_HOVER}; }}
        QPushButton#SecondaryButton {{
            background: {BG_CARD_ALT};
            color: {TEXT_PRIMARY};
            font-weight: 700;
        }}
        QPushButton#SecondaryButton:hover {{ background: {LIST_ITEM_HOVER}; }}
        QLineEdit, QTextEdit, QComboBox {{
            border: 1px solid {BORDER};
            border-radius: 14px;
            background: {BG_INPUT};
            padding: 10px 14px;
            font-size: {BODY_PT}pt;
            selection-background-color: {SELECTION};
            selection-color: {TEXT_PRIMARY};
            color: {TEXT_PRIMARY};
        }}
        QSpinBox {{
            border: 1px solid {BORDER};
            border-radius: 12px;
            background: {BG_INPUT};
            padding: 6px 10px;
            min-height: 28px;
            color: {TEXT_PRIMARY};
        }}
        QCheckBox {{
            color: {TEXT_PRIMARY};
            background: transparent;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border-radius: 4px;
            border: 1px solid {BORDER};
            background: {BG_INPUT};
        }}
        QCheckBox::indicator:checked {{
            background: {SELECTION};
            border-color: {ACCENT};
        }}
    """


def apply_agent_dialog_theme(dialog) -> None:
    """Сплошной фон окна + QSS (важно для QDialog без родительского AgentChatPanel)."""
    from PySide6.QtGui import QColor, QPalette

    dialog.setObjectName("AgentAppDialog")
    dialog.setStyleSheet(agent_dialog_stylesheet())
    dialog.setAutoFillBackground(True)
    pal = QPalette(dialog.palette())
    pal.setColor(QPalette.ColorRole.Window, QColor(BG_PAGE))
    dialog.setPalette(pal)


def profile_sidebar_stylesheet() -> str:
    return f"""
        QFrame#ProfileSidebar {{
            background: {BG_CARD};
            border: 1px solid {BORDER};
            border-radius: 18px;
        }}
        QLabel#ProfileSidebarTitle {{
            font-size: 15px;
            font-weight: 700;
            color: {TEXT_PRIMARY};
            background: transparent;
        }}
        QLabel#ProfileFieldLabel {{
            font-size: 11px;
            color: {TEXT_MUTED};
            background: transparent;
        }}
        QLabel#ProfileFieldValue {{
            font-size: 13px;
            color: {TEXT_PRIMARY};
            background: transparent;
        }}
        QLabel#ProfileHint {{
            font-size: 12px;
            color: {TEXT_MUTED};
            background: transparent;
        }}
    """
