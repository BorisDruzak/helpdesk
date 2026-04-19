"""
Theme tokens and QSS helpers for the desktop agent GUI.

The module exposes semantic color tokens through module attributes like
`theme.BG_PAGE` and keeps them dynamic so existing widgets can read the
currently selected light or dark palette without large rewrites.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemePalette:
    mode: str
    bg_page: str
    bg_card: str
    bg_card_alt: str
    bg_input: str
    border: str
    border_soft: str
    text_primary: str
    text_secondary: str
    text_muted: str
    accent: str
    accent_soft: str
    primary_btn: str
    primary_btn_hover: str
    primary_btn_text: str
    danger_bg: str
    danger_fg: str
    danger_border: str
    info_bg: str
    info_fg: str
    link: str
    selection: str
    list_item_bg: str
    list_item_border: str
    list_item_hover: str
    list_item_hover_border: str
    list_item_selected_bg: str
    list_item_selected_border: str
    bubble_self_bg: str
    bubble_self_border: str
    bubble_self_fg: str
    bubble_support_bg: str
    bubble_support_border: str
    bubble_support_fg: str
    bubble_event_bg: str
    bubble_event_border: str
    bubble_event_fg: str
    bubble_event_muted: str
    timeline_scroll_bg: str
    chat_screen_solid_open: str
    chat_screen_solid_resolved: str
    chat_screen_solid_closed: str
    chat_send_bg: str
    chat_send_bg_hover: str
    chat_send_border: str
    chat_send_text: str
    sidebar_shell_bg: str
    sidebar_shell_bg_alt: str
    sidebar_border: str
    sidebar_text: str
    sidebar_text_muted: str
    sidebar_action_bg: str
    sidebar_action_border: str
    sidebar_action_text: str
    sidebar_nav_bg: str
    sidebar_nav_bg_hover: str
    sidebar_nav_bg_selected: str
    sidebar_nav_border: str
    sidebar_nav_border_selected: str
    sidebar_profile_badge_bg: str
    sidebar_profile_badge_fg: str
    status_online_bg: str
    status_online_fg: str
    status_busy_bg: str
    status_busy_fg: str
    status_offline_bg: str
    status_offline_fg: str
    footer_block_bg: str
    footer_block_border: str
    footer_label: str
    footer_label_muted: str


LIGHT_THEME = ThemePalette(
    mode="light",
    bg_page="#f3f7fb",
    bg_card="#ffffff",
    bg_card_alt="#eef3f8",
    bg_input="#ffffff",
    border="#d6e0ea",
    border_soft="#e7eef5",
    text_primary="#17212b",
    text_secondary="#4c5d70",
    text_muted="#76879a",
    accent="#2f6fed",
    accent_soft="#8ab2ff",
    primary_btn="#2f6fed",
    primary_btn_hover="#245ed0",
    primary_btn_text="#f8fbff",
    danger_bg="#feeaec",
    danger_fg="#a53b46",
    danger_border="#f4c5cb",
    info_bg="#ebf3ff",
    info_fg="#264f84",
    link="#2f6fed",
    selection="#cbdfff",
    list_item_bg="#ffffff",
    list_item_border="#dee8f1",
    list_item_hover="#f2f7fd",
    list_item_hover_border="#bdd2ea",
    list_item_selected_bg="#e5f0ff",
    list_item_selected_border="#2f6fed",
    bubble_self_bg="#e8f0ff",
    bubble_self_border="#c2d7ff",
    bubble_self_fg="#17212b",
    bubble_support_bg="#eaf5ef",
    bubble_support_border="#c4dfcf",
    bubble_support_fg="#1c3f2d",
    bubble_event_bg="#f1f5f9",
    bubble_event_border="#dde6ef",
    bubble_event_fg="#4c5d70",
    bubble_event_muted="#76879a",
    timeline_scroll_bg="#edf2f7",
    chat_screen_solid_open="#f5f8fc",
    chat_screen_solid_resolved="#eef7f1",
    chat_screen_solid_closed="#f1f4f8",
    chat_send_bg="#2f6fed",
    chat_send_bg_hover="#245ed0",
    chat_send_border="#1f54be",
    chat_send_text="#f8fbff",
    sidebar_shell_bg="#244c82",
    sidebar_shell_bg_alt="#1a3963",
    sidebar_border="rgba(255, 255, 255, 0.12)",
    sidebar_text="#f7fbff",
    sidebar_text_muted="rgba(247, 251, 255, 0.74)",
    sidebar_action_bg="#2f6fed",
    sidebar_action_border="#79a5ff",
    sidebar_action_text="#f8fbff",
    sidebar_nav_bg="rgba(255, 255, 255, 0.08)",
    sidebar_nav_bg_hover="rgba(255, 255, 255, 0.16)",
    sidebar_nav_bg_selected="rgba(255, 255, 255, 0.24)",
    sidebar_nav_border="rgba(255, 255, 255, 0.12)",
    sidebar_nav_border_selected="rgba(255, 255, 255, 0.28)",
    sidebar_profile_badge_bg="rgba(255, 255, 255, 0.12)",
    sidebar_profile_badge_fg="#dfefff",
    status_online_bg="#dcf4e6",
    status_online_fg="#1d6c45",
    status_busy_bg="#e9f1ff",
    status_busy_fg="#295aa0",
    status_offline_bg="#ecf1f6",
    status_offline_fg="#5d6b7a",
    footer_block_bg="#ffffff",
    footer_block_border="#d6e0ea",
    footer_label="#17212b",
    footer_label_muted="#76879a",
)

DARK_THEME = ThemePalette(
    mode="dark",
    bg_page="#0f141b",
    bg_card="#161d26",
    bg_card_alt="#1d2632",
    bg_input="#0c1117",
    border="#2b3a4d",
    border_soft="#213041",
    text_primary="#eaf1f8",
    text_secondary="#b4c3d5",
    text_muted="#7f90a4",
    accent="#5d9bff",
    accent_soft="#8fbcff",
    primary_btn="#5d9bff",
    primary_btn_hover="#78adff",
    primary_btn_text="#0f141b",
    danger_bg="#40262c",
    danger_fg="#ffbec8",
    danger_border="#7a4e58",
    info_bg="#1d2f47",
    info_fg="#d9e7ff",
    link="#8fbcff",
    selection="#234a86",
    list_item_bg="#141b24",
    list_item_border="#273547",
    list_item_hover="#1d2a3a",
    list_item_hover_border="#3d5878",
    list_item_selected_bg="#203b61",
    list_item_selected_border="#5d9bff",
    bubble_self_bg="#20334d",
    bubble_self_border="#36557d",
    bubble_self_fg="#eaf1f8",
    bubble_support_bg="#18342a",
    bubble_support_border="#315a49",
    bubble_support_fg="#d9f3e5",
    bubble_event_bg="#1a2430",
    bubble_event_border="#28394d",
    bubble_event_fg="#b4c3d5",
    bubble_event_muted="#7f90a4",
    timeline_scroll_bg="#121922",
    chat_screen_solid_open="#101720",
    chat_screen_solid_resolved="#101c16",
    chat_screen_solid_closed="#161d26",
    chat_send_bg="#5d9bff",
    chat_send_bg_hover="#78adff",
    chat_send_border="#8fbcff",
    chat_send_text="#0f141b",
    sidebar_shell_bg="#152333",
    sidebar_shell_bg_alt="#1b2d43",
    sidebar_border="rgba(255, 255, 255, 0.10)",
    sidebar_text="#eef5fb",
    sidebar_text_muted="rgba(238, 245, 251, 0.70)",
    sidebar_action_bg="#5d9bff",
    sidebar_action_border="#8fbcff",
    sidebar_action_text="#0f141b",
    sidebar_nav_bg="rgba(255, 255, 255, 0.06)",
    sidebar_nav_bg_hover="rgba(255, 255, 255, 0.12)",
    sidebar_nav_bg_selected="rgba(255, 255, 255, 0.18)",
    sidebar_nav_border="rgba(255, 255, 255, 0.10)",
    sidebar_nav_border_selected="rgba(255, 255, 255, 0.22)",
    sidebar_profile_badge_bg="rgba(255, 255, 255, 0.08)",
    sidebar_profile_badge_fg="#d3e6ff",
    status_online_bg="#17392b",
    status_online_fg="#9de0b9",
    status_busy_bg="#1d2f47",
    status_busy_fg="#bcd6ff",
    status_offline_bg="#202a36",
    status_offline_fg="#bcc8d6",
    footer_block_bg="#161d26",
    footer_block_border="#2b3a4d",
    footer_label="#eaf1f8",
    footer_label_muted="#7f90a4",
)

PALETTES = {
    "light": LIGHT_THEME,
    "dark": DARK_THEME,
}

TOKEN_MAP = {
    "BG_PAGE": "bg_page",
    "BG_CARD": "bg_card",
    "BG_CARD_ALT": "bg_card_alt",
    "BG_INPUT": "bg_input",
    "BORDER": "border",
    "BORDER_SOFT": "border_soft",
    "TEXT_PRIMARY": "text_primary",
    "TEXT_SECONDARY": "text_secondary",
    "TEXT_MUTED": "text_muted",
    "ACCENT": "accent",
    "ACCENT_SOFT": "accent_soft",
    "PRIMARY_BTN": "primary_btn",
    "PRIMARY_BTN_HOVER": "primary_btn_hover",
    "PRIMARY_BTN_TEXT": "primary_btn_text",
    "DANGER_BG": "danger_bg",
    "DANGER_FG": "danger_fg",
    "DANGER_BORDER": "danger_border",
    "INFO_BG": "info_bg",
    "INFO_FG": "info_fg",
    "LINK": "link",
    "SELECTION": "selection",
    "LIST_ITEM_BG": "list_item_bg",
    "LIST_ITEM_BORDER": "list_item_border",
    "LIST_ITEM_HOVER": "list_item_hover",
    "LIST_ITEM_HOVER_BORDER": "list_item_hover_border",
    "LIST_ITEM_SELECTED_BG": "list_item_selected_bg",
    "LIST_ITEM_SELECTED_BORDER": "list_item_selected_border",
    "BUBBLE_SELF_BG": "bubble_self_bg",
    "BUBBLE_SELF_BORDER": "bubble_self_border",
    "BUBBLE_SELF_FG": "bubble_self_fg",
    "BUBBLE_SUPPORT_BG": "bubble_support_bg",
    "BUBBLE_SUPPORT_BORDER": "bubble_support_border",
    "BUBBLE_SUPPORT_FG": "bubble_support_fg",
    "BUBBLE_EVENT_BG": "bubble_event_bg",
    "BUBBLE_EVENT_BORDER": "bubble_event_border",
    "BUBBLE_EVENT_FG": "bubble_event_fg",
    "BUBBLE_EVENT_MUTED": "bubble_event_muted",
    "TIMELINE_SCROLL_BG": "timeline_scroll_bg",
    "CHAT_SCREEN_SOLID_OPEN": "chat_screen_solid_open",
    "CHAT_SCREEN_SOLID_RESOLVED": "chat_screen_solid_resolved",
    "CHAT_SCREEN_SOLID_CLOSED": "chat_screen_solid_closed",
    "CHAT_SEND_BG": "chat_send_bg",
    "CHAT_SEND_BG_HOVER": "chat_send_bg_hover",
    "CHAT_SEND_BORDER": "chat_send_border",
    "CHAT_SEND_TEXT": "chat_send_text",
}

STATUS_COLOR_TEMPLATES = {
    "light": {
        "new": ("#1f5da6", "#d9e8fb"),
        "triaged": ("#6a4392", "#eaddf7"),
        "in_progress": ("#1f715d", "#d7efe7"),
        "waiting_on_user": ("#9a6618", "#f8e8c2"),
        "waiting_on_vendor": ("#83501b", "#f0debc"),
        "resolved": ("#255f46", "#d4eadc"),
        "closed": ("#60594f", "#e7e1d9"),
        "unknown": ("#60594f", "#e7e1d9"),
    },
    "dark": {
        "new": ("#abd0ff", "#1a3858"),
        "triaged": ("#d4b6ff", "#37244d"),
        "in_progress": ("#a9ebd2", "#173b32"),
        "waiting_on_user": ("#ffd89a", "#49381a"),
        "waiting_on_vendor": ("#efc998", "#423116"),
        "resolved": ("#b6e8cb", "#1c3a2b"),
        "closed": ("#d2d7df", "#2b313a"),
        "unknown": ("#d2d7df", "#2b313a"),
    },
}

UI_FONT_FAMILY = '"Segoe UI", "Tahoma", "Noto Sans"'
UI_FONT_PT = 10
BODY_PT = 11
TITLE_PT = 12
BUBBLE_BODY_PT = 14

_current_mode = "light"


def normalize_theme_mode(mode: str | None) -> str:
    normalized = str(mode or "").strip().lower()
    if normalized not in PALETTES:
        return "light"
    return normalized


def current_theme_mode() -> str:
    return _current_mode


def set_theme_mode(mode: str | None) -> str:
    global _current_mode
    _current_mode = normalize_theme_mode(mode)
    return _current_mode


def current_palette() -> ThemePalette:
    return PALETTES[_current_mode]


def status_colors() -> dict[str, tuple[str, str]]:
    return STATUS_COLOR_TEMPLATES[_current_mode]


def build_palette():
    from PySide6.QtGui import QColor, QPalette

    p = current_palette()
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(p.bg_page))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(p.text_primary))
    pal.setColor(QPalette.ColorRole.Base, QColor(p.bg_input))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(p.bg_card_alt))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(p.bg_card))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(p.text_primary))
    pal.setColor(QPalette.ColorRole.Text, QColor(p.text_primary))
    pal.setColor(QPalette.ColorRole.Button, QColor(p.bg_card))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(p.text_primary))
    pal.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.Link, QColor(p.link))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(p.accent))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(p.primary_btn_text if p.mode == "dark" else p.text_primary))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(p.text_muted))
    try:
        pal.setColor(QPalette.ColorRole.Accent, QColor(p.accent))
    except Exception:
        pass
    return pal


def application_stylesheet() -> str:
    p = current_palette()
    return f"""
        QMainWindow, QWidget {{
            color: {p.text_primary};
        }}
        QStatusBar {{
            background: transparent;
            color: {p.footer_label};
            border-top: 1px solid {p.footer_block_border};
        }}
        QStatusBar::item {{
            border: none;
        }}
        QScrollArea {{
            border: none;
            background: transparent;
        }}
        QScrollBar:vertical {{
            background: {p.bg_card_alt};
            width: 12px;
            margin: 6px 0px 6px 0px;
            border-radius: 6px;
        }}
        QScrollBar::handle:vertical {{
            background: {p.border};
            min-height: 28px;
            border-radius: 6px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {p.accent_soft};
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical,
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {{
            height: 0px;
            background: transparent;
        }}
        QPlainTextEdit {{
            background: {p.bg_input};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 14px;
            selection-background-color: {p.selection};
            selection-color: {p.text_primary};
        }}
    """


def apply_application_theme(app, mode: str | None = None) -> str:
    resolved = set_theme_mode(mode)
    app.setStyle("Fusion")
    app.setPalette(build_palette())
    app.setStyleSheet(application_stylesheet())
    return resolved


def apply_widget_palette(widget) -> None:
    widget.setAutoFillBackground(True)
    widget.setPalette(build_palette())


def chat_panel_stylesheet() -> str:
    p = current_palette()
    return f"""
        QWidget#AgentChatPanel {{
            background-color: {p.bg_page};
        }}
        QStackedWidget#TicketStack {{
            background-color: {p.bg_page};
        }}
        QWidget#TicketListScreen, QWidget#ChatScreenRoot {{
            background-color: {p.bg_page};
        }}
        QWidget {{
            font-family: {UI_FONT_FAMILY};
            font-size: {UI_FONT_PT}pt;
            color: {p.text_primary};
            background-color: transparent;
        }}
        QGroupBox {{
            font-weight: 700;
            font-size: {TITLE_PT}pt;
            border: 1px solid {p.border};
            border-radius: 20px;
            margin-top: 12px;
            background: {p.bg_card};
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
            background: {p.bg_card_alt};
            outline: none;
            padding: 4px;
            border-radius: 16px;
        }}
        QListView#TicketsListView > QWidget {{
            background-color: {p.bg_card_alt};
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
            border: 1px solid {p.border};
            border-radius: 14px;
            background: {p.bg_input};
            padding: 10px 18px;
            min-height: 22px;
            font-weight: 600;
            font-size: {BODY_PT}pt;
            color: {p.text_primary};
        }}
        QPushButton:hover {{ background: {p.list_item_hover}; border-color: {p.list_item_hover_border}; }}
        QPushButton#SecondaryButton {{
            background: {p.bg_card_alt};
            color: {p.text_primary};
            font-weight: 700;
        }}
        QPushButton#SecondaryButton:hover {{ background: {p.list_item_hover}; }}
        QToolButton {{
            border: 2px solid {p.border};
            border-radius: 14px;
            background: {p.bg_input};
            padding: 10px 14px;
            font-size: 12pt;
            font-weight: 700;
            min-width: 44px;
            min-height: 40px;
            color: {p.text_primary};
        }}
        QToolButton:hover {{ background: {p.list_item_hover}; border-color: {p.accent}; }}
        QToolButton#JumpToLatestButton {{
            min-width: 48px;
            min-height: 48px;
            max-width: 48px;
            max-height: 48px;
            padding: 0px;
            border-radius: 24px;
            border: 1px solid {p.primary_btn};
            background: {p.primary_btn};
            color: {p.primary_btn_text};
            font-size: 16pt;
            font-weight: 800;
            margin: 0 16px 16px 0;
        }}
        QToolButton#JumpToLatestButton:hover {{
            background: {p.primary_btn_hover};
            border-color: {p.primary_btn_hover};
        }}
        QPushButton#PrimaryButton {{
            background: {p.primary_btn};
            color: {p.primary_btn_text};
            border-color: {p.primary_btn};
            font-weight: 700;
            font-size: {BODY_PT}pt;
            padding: 12px 22px;
            min-height: 24px;
        }}
        QPushButton#PrimaryButton:hover {{ background: {p.primary_btn_hover}; }}
        QPushButton#ChatSendButton {{
            background-color: {p.chat_send_bg};
            color: {p.chat_send_text};
            border: 2px solid {p.chat_send_border};
            font-weight: 800;
            font-size: 12pt;
            padding: 14px 28px;
            min-width: 150px;
            min-height: 28px;
        }}
        QPushButton#ChatSendButton:hover {{
            background-color: {p.chat_send_bg_hover};
            border-color: {p.chat_send_border};
        }}
        QPushButton#ChatSendButton:pressed {{
            background-color: {p.chat_send_border};
        }}
        QPushButton#DangerButton {{
            background: {p.danger_bg};
            color: {p.danger_fg};
            border-color: {p.danger_border};
            font-weight: 700;
        }}
        QPushButton#DangerButton:disabled {{
            background: {p.bg_card_alt};
            color: {p.text_muted};
            border-color: {p.border_soft};
        }}
        QLineEdit, QTextEdit, QComboBox {{
            border: 1px solid {p.border};
            border-radius: 14px;
            background: {p.bg_input};
            padding: 10px 14px;
            font-size: {BODY_PT}pt;
            selection-background-color: {p.selection};
            selection-color: {p.text_primary};
            color: {p.text_primary};
        }}
        QLineEdit#ChatInputLine {{
            border: 2px solid {p.border};
            padding: 12px 16px;
            font-size: {BUBBLE_BODY_PT}pt;
            background: {p.list_item_bg};
        }}
        QLineEdit#ChatInputLine:focus {{ border-color: {p.accent}; }}
        QScrollArea#TimelineScroll {{
            background-color: {p.timeline_scroll_bg};
            border: 1px solid {p.border};
            border-radius: 22px;
        }}
        QScrollArea#TimelineScroll > QWidget > QWidget {{
            background-color: {p.timeline_scroll_bg};
        }}
        QScrollArea#TimelineScroll QScrollBar:vertical {{
            background: {p.bg_card_alt};
            width: 12px;
            margin: 8px 6px 8px 0px;
            border-radius: 8px;
        }}
        QScrollArea#TimelineScroll QScrollBar::handle:vertical {{
            background: {p.border};
            min-height: 40px;
            border-radius: 8px;
        }}
        QScrollArea#TimelineScroll QScrollBar::add-line:vertical,
        QScrollArea#TimelineScroll QScrollBar::sub-line:vertical {{ height: 0px; }}
        QComboBox QAbstractItemView,
        QMenu,
        QMenu#AgentPopupMenu {{
            background: {p.bg_input};
            color: {p.text_primary};
            border: 1px solid {p.border};
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
            background: {p.list_item_hover};
            color: {p.text_primary};
        }}
        QMenu::separator,
        QMenu#AgentPopupMenu::separator {{
            height: 1px;
            background: {p.border_soft};
            margin: 6px 10px;
        }}
    """


def agent_dialog_stylesheet() -> str:
    p = current_palette()
    return f"""
        QDialog#AgentAppDialog, QWidget#AgentAppDialog {{
            background-color: {p.bg_page};
        }}
        QWidget {{
            font-family: {UI_FONT_FAMILY};
            font-size: {UI_FONT_PT}pt;
            color: {p.text_primary};
            background-color: transparent;
        }}
        QLabel {{
            color: {p.text_primary};
            background-color: transparent;
        }}
        QGroupBox {{
            font-weight: 700;
            font-size: {TITLE_PT}pt;
            border: 1px solid {p.border};
            border-radius: 16px;
            margin-top: 12px;
            background: {p.bg_card};
            padding-top: 8px;
        }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 4px 8px; }}
        QListWidget {{
            font-family: {UI_FONT_FAMILY};
            font-size: {UI_FONT_PT}pt;
            border: 1px solid {p.border};
            background-color: {p.bg_card_alt};
            border-radius: 14px;
            padding: 6px;
            outline: none;
        }}
        QListWidget::item {{
            padding: 6px 8px;
            border-radius: 8px;
        }}
        QListWidget::item:selected {{
            background: {p.list_item_selected_bg};
            color: {p.text_primary};
        }}
        QListWidget::item:hover {{
            background: {p.list_item_hover};
        }}
        QPushButton {{
            border: 1px solid {p.border};
            border-radius: 14px;
            background: {p.bg_input};
            padding: 10px 18px;
            min-height: 22px;
            font-weight: 600;
            font-size: {BODY_PT}pt;
            color: {p.text_primary};
        }}
        QPushButton:hover {{ background: {p.list_item_hover}; border-color: {p.list_item_hover_border}; }}
        QPushButton#PrimaryButton {{
            background: {p.primary_btn};
            color: {p.primary_btn_text};
            border-color: {p.primary_btn};
            font-weight: 700;
        }}
        QPushButton#PrimaryButton:hover {{ background: {p.primary_btn_hover}; }}
        QPushButton#SecondaryButton {{
            background: {p.bg_card_alt};
            color: {p.text_primary};
            font-weight: 700;
        }}
        QPushButton#SecondaryButton:hover {{ background: {p.list_item_hover}; }}
        QLineEdit, QTextEdit, QComboBox {{
            border: 1px solid {p.border};
            border-radius: 14px;
            background: {p.bg_input};
            padding: 10px 14px;
            font-size: {BODY_PT}pt;
            selection-background-color: {p.selection};
            selection-color: {p.text_primary};
            color: {p.text_primary};
        }}
        QSpinBox {{
            border: 1px solid {p.border};
            border-radius: 12px;
            background: {p.bg_input};
            padding: 6px 10px;
            min-height: 28px;
            color: {p.text_primary};
        }}
        QCheckBox {{
            color: {p.text_primary};
            background: transparent;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border-radius: 4px;
            border: 1px solid {p.border};
            background: {p.bg_input};
        }}
        QCheckBox::indicator:checked {{
            background: {p.selection};
            border-color: {p.accent};
        }}
    """


def apply_agent_dialog_theme(dialog) -> None:
    dialog.setObjectName("AgentAppDialog")
    dialog.setStyleSheet(agent_dialog_stylesheet())
    apply_widget_palette(dialog)


def profile_sidebar_stylesheet() -> str:
    p = current_palette()
    return f"""
        QFrame#ProfileSidebar {{
            background: {p.bg_card};
            border: 1px solid {p.border};
            border-radius: 18px;
        }}
        QLabel#ProfileSidebarTitle {{
            font-size: 15px;
            font-weight: 700;
            color: {p.text_primary};
            background: transparent;
        }}
        QLabel#ProfileFieldLabel {{
            font-size: 11px;
            color: {p.text_muted};
            background: transparent;
        }}
        QLabel#ProfileFieldValue {{
            font-size: 13px;
            color: {p.text_primary};
            background: transparent;
        }}
        QLabel#ProfileHint {{
            font-size: 12px;
            color: {p.text_muted};
            background: transparent;
        }}
    """


def __getattr__(name: str):
    if name == "STATUS_COLORS_WARM":
        return status_colors()
    if name in TOKEN_MAP:
        return getattr(current_palette(), TOKEN_MAP[name])
    raise AttributeError(name)
