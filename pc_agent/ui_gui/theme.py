"""
Theme tokens and QSS helpers for the desktop agent GUI.

The module exposes semantic color tokens through module attributes like
`theme.BG_PAGE` and keeps them dynamic so existing widgets can read the
currently selected light or dark palette without large rewrites.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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

    @property
    def window_bg(self) -> str:
        return self.bg_page

    @property
    def panel_bg(self) -> str:
        return self.bg_card

    @property
    def panel_bg_alt(self) -> str:
        return self.bg_card_alt

    @property
    def card_bg(self) -> str:
        return self.list_item_bg

    @property
    def card_hover_bg(self) -> str:
        return self.list_item_hover

    @property
    def card_active_bg(self) -> str:
        return self.list_item_selected_bg

    @property
    def border_active(self) -> str:
        return self.list_item_selected_border

    @property
    def success(self) -> str:
        return self.status_online_fg

    @property
    def warning(self) -> str:
        return "#F59E0B" if self.mode == "dark" else "#D97706"

    @property
    def danger(self) -> str:
        return "#EF4444" if self.mode == "dark" else "#DC2626"

    @property
    def input_bg(self) -> str:
        return self.bg_input

    @property
    def button_bg(self) -> str:
        return self.primary_btn

    @property
    def button_text(self) -> str:
        return self.primary_btn_text


LIGHT_THEME = ThemePalette(
    mode="light",
    bg_page="#F6F8FC",
    bg_card="#ffffff",
    bg_card_alt="#F8FAFF",
    bg_input="#ffffff",
    border="#E5EAF3",
    border_soft="#EEF2F8",
    text_primary="#111827",
    text_secondary="#64748B",
    text_muted="#94A3B8",
    accent="#4F63F6",
    accent_soft="#DDE4FF",
    primary_btn="#4F63F6",
    primary_btn_hover="#3F51E8",
    primary_btn_text="#FFFFFF",
    danger_bg="#FEE2E2",
    danger_fg="#DC2626",
    danger_border="#FECACA",
    info_bg="#F4F6FF",
    info_fg="#3F51E8",
    link="#4F63F6",
    selection="#DDE4FF",
    list_item_bg="#ffffff",
    list_item_border="#E5EAF3",
    list_item_hover="#F8FAFF",
    list_item_hover_border="#D7E0F0",
    list_item_selected_bg="#F4F6FF",
    list_item_selected_border="#5B6CFF",
    bubble_self_bg="#EEF3FF",
    bubble_self_border="#CFDAFF",
    bubble_self_fg="#111827",
    bubble_support_bg="#ECFDF3",
    bubble_support_border="#BBF7D0",
    bubble_support_fg="#14532D",
    bubble_event_bg="#F8FAFC",
    bubble_event_border="#E5EAF3",
    bubble_event_fg="#64748B",
    bubble_event_muted="#94A3B8",
    timeline_scroll_bg="#F8FAFF",
    chat_screen_solid_open="#F6F8FC",
    chat_screen_solid_resolved="#F0FDF4",
    chat_screen_solid_closed="#F1F5F9",
    chat_send_bg="#4F63F6",
    chat_send_bg_hover="#3F51E8",
    chat_send_border="#4F63F6",
    chat_send_text="#FFFFFF",
    sidebar_shell_bg="#FFFFFF",
    sidebar_shell_bg_alt="#FFFFFF",
    sidebar_border="#E5EAF3",
    sidebar_text="#111827",
    sidebar_text_muted="#64748B",
    sidebar_action_bg="#4F63F6",
    sidebar_action_border="#4F63F6",
    sidebar_action_text="#FFFFFF",
    sidebar_nav_bg="transparent",
    sidebar_nav_bg_hover="#F8FAFF",
    sidebar_nav_bg_selected="#EEF2FF",
    sidebar_nav_border="transparent",
    sidebar_nav_border_selected="#E0E7FF",
    sidebar_profile_badge_bg="#EEF2FF",
    sidebar_profile_badge_fg="#4F63F6",
    status_online_bg="#DCFCE7",
    status_online_fg="#16A34A",
    status_busy_bg="#FEF3C7",
    status_busy_fg="#D97706",
    status_offline_bg="#F1F5F9",
    status_offline_fg="#64748B",
    footer_block_bg="#ffffff",
    footer_block_border="#E5EAF3",
    footer_label="#111827",
    footer_label_muted="#64748B",
)

DARK_THEME = ThemePalette(
    mode="dark",
    bg_page="#070B18",
    bg_card="#0D1426",
    bg_card_alt="#101A30",
    bg_input="#0A1020",
    border="#24324A",
    border_soft="#1C2940",
    text_primary="#F8FAFC",
    text_secondary="#94A3B8",
    text_muted="#64748B",
    accent="#5B6CFF",
    accent_soft="#273168",
    primary_btn="#5B6CFF",
    primary_btn_hover="#6F7DFF",
    primary_btn_text="#FFFFFF",
    danger_bg="#421D27",
    danger_fg="#FCA5A5",
    danger_border="#7F1D1D",
    info_bg="#132450",
    info_fg="#DDE4FF",
    link="#AAB6FF",
    selection="#273168",
    list_item_bg="#121D33",
    list_item_border="#24324A",
    list_item_hover="#17243D",
    list_item_hover_border="#334462",
    list_item_selected_bg="#132450",
    list_item_selected_border="#5368FF",
    bubble_self_bg="#172B58",
    bubble_self_border="#334B8F",
    bubble_self_fg="#F8FAFC",
    bubble_support_bg="#123323",
    bubble_support_border="#1D6F43",
    bubble_support_fg="#DCFCE7",
    bubble_event_bg="#101A30",
    bubble_event_border="#24324A",
    bubble_event_fg="#94A3B8",
    bubble_event_muted="#64748B",
    timeline_scroll_bg="#0A1020",
    chat_screen_solid_open="#070B18",
    chat_screen_solid_resolved="#07130E",
    chat_screen_solid_closed="#0D1426",
    chat_send_bg="#5B6CFF",
    chat_send_bg_hover="#6F7DFF",
    chat_send_border="#5B6CFF",
    chat_send_text="#FFFFFF",
    sidebar_shell_bg="#0D1426",
    sidebar_shell_bg_alt="#0D1426",
    sidebar_border="#1C2940",
    sidebar_text="#F8FAFC",
    sidebar_text_muted="#94A3B8",
    sidebar_action_bg="#5B6CFF",
    sidebar_action_border="#5B6CFF",
    sidebar_action_text="#FFFFFF",
    sidebar_nav_bg="transparent",
    sidebar_nav_bg_hover="#17243D",
    sidebar_nav_bg_selected="#1D2A58",
    sidebar_nav_border="transparent",
    sidebar_nav_border_selected="#2D3C78",
    sidebar_profile_badge_bg="#273168",
    sidebar_profile_badge_fg="#DDE4FF",
    status_online_bg="#123323",
    status_online_fg="#22C55E",
    status_busy_bg="#3A2A0C",
    status_busy_fg="#F59E0B",
    status_offline_bg="#17243D",
    status_offline_fg="#94A3B8",
    footer_block_bg="#101A30",
    footer_block_border="#24324A",
    footer_label="#F8FAFC",
    footer_label_muted="#94A3B8",
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
        "new": ("#4F63F6", "#EEF2FF"),
        "queued": ("#D97706", "#FEF3C7"),
        "triaged": ("#7C3AED", "#F3E8FF"),
        "assigned": ("#2563EB", "#DBEAFE"),
        "in_progress": ("#16A34A", "#DCFCE7"),
        "waiting_on_user": ("#D97706", "#FEF3C7"),
        "waiting_on_vendor": ("#B45309", "#FFEDD5"),
        "resolved": ("#15803D", "#DCFCE7"),
        "closed": ("#64748B", "#F1F5F9"),
        "unknown": ("#64748B", "#F1F5F9"),
    },
    "dark": {
        "new": ("#AAB6FF", "#1D2A58"),
        "queued": ("#F59E0B", "#3A2A0C"),
        "triaged": ("#C4B5FD", "#31204F"),
        "assigned": ("#93C5FD", "#172B58"),
        "in_progress": ("#22C55E", "#123323"),
        "waiting_on_user": ("#F59E0B", "#3A2A0C"),
        "waiting_on_vendor": ("#FBBF24", "#3B2F0F"),
        "resolved": ("#86EFAC", "#123323"),
        "closed": ("#94A3B8", "#17243D"),
        "unknown": ("#94A3B8", "#17243D"),
    },
}

UI_FONT_FAMILY = '"Segoe UI", "Tahoma", "Noto Sans"'
UI_FONT_PT = 10
BODY_PT = 11
TITLE_PT = 12
BUBBLE_BODY_PT = 14
LOGO_PATH = Path(r"C:\Users\admin-2\Desktop\лого\512-512.png")
ICONS_DIR = Path(__file__).resolve().parent / "assets" / "icons"

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


def icon_path(name: str) -> str:
    return str((ICONS_DIR / f"{name}.svg").resolve())


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
        QSplitter::handle {{
            background: transparent;
        }}
        QToolTip {{
            background: {p.bg_card};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 8px;
            padding: 6px 8px;
        }}
    """


def main_window_stylesheet() -> str:
    p = current_palette()
    return f"""
        QWidget#AgentRoot {{
            background: {p.bg_page};
        }}
        QFrame#Sidebar {{
            background: {p.sidebar_shell_bg};
            border: 1px solid {p.sidebar_border};
            border-radius: 20px;
        }}
        QLabel#BrandTitle {{
            color: {p.sidebar_text};
            font-size: 18px;
            font-weight: 800;
            background: transparent;
        }}
        QLabel#SidebarSectionLabel {{
            color: {p.sidebar_text_muted};
            font-size: 12px;
            font-weight: 700;
            background: transparent;
        }}
        QPushButton#SidebarButton,
        QPushButton#SidebarButtonActive {{
            min-height: 50px;
            padding: 0px 14px;
            border-radius: 14px;
            text-align: left;
            font-size: 14px;
            font-weight: 700;
            color: {p.sidebar_text};
            background: {p.sidebar_nav_bg};
            border: 1px solid {p.sidebar_nav_border};
        }}
        QPushButton#SidebarButton:hover {{
            background: {p.sidebar_nav_bg_hover};
            border-color: {p.sidebar_nav_border_selected};
        }}
        QPushButton#SidebarButtonActive,
        QPushButton#SidebarButton:checked {{
            background: {p.sidebar_nav_bg_selected};
            border-color: {p.sidebar_nav_border_selected};
            color: {p.accent if p.mode == "light" else p.text_primary};
        }}
        QPushButton#PrimaryButton,
        QPushButton#SidebarCreateButton {{
            min-height: 50px;
            padding: 0px 16px;
            border-radius: 14px;
            text-align: left;
            font-size: 14px;
            font-weight: 800;
            color: {p.primary_btn_text};
            background: {p.primary_btn};
            border: 1px solid {p.primary_btn};
        }}
        QPushButton#PrimaryButton:hover,
        QPushButton#SidebarCreateButton:hover {{
            background: {p.primary_btn_hover};
            border-color: {p.primary_btn_hover};
        }}
        QPushButton#SecondaryButton,
        QToolButton#SecondaryButton {{
            min-height: 42px;
            padding: 0px 14px;
            border-radius: 12px;
            font-size: 13px;
            font-weight: 700;
            color: {p.text_primary};
            background: {p.bg_input};
            border: 1px solid {p.border};
        }}
        QPushButton#SecondaryButton:hover,
        QToolButton#SecondaryButton:hover {{
            background: {p.list_item_hover};
            border-color: {p.list_item_hover_border};
        }}
        QFrame#ProfileCard,
        QFrame#AgentStatusCard {{
            background: {p.bg_card_alt if p.mode == "dark" else p.bg_card};
            border: 1px solid {p.border_soft if p.mode == "dark" else p.border};
            border-radius: 16px;
        }}
        QLabel#Avatar {{
            color: #FFFFFF;
            background: {p.primary_btn};
            border-radius: 24px;
            font-size: 17px;
            font-weight: 800;
        }}
        QLabel#CardKicker {{
            color: {p.text_secondary if p.mode == "light" else p.sidebar_text_muted};
            font-size: 12px;
            font-weight: 700;
            background: transparent;
        }}
        QLabel#CardTitle {{
            color: {p.text_primary};
            font-size: 14px;
            font-weight: 800;
            background: transparent;
        }}
        QLabel#CardMeta {{
            color: {p.text_secondary};
            font-size: 12px;
            font-weight: 600;
            background: transparent;
        }}
        QLabel#StatusDot {{
            min-width: 12px;
            max-width: 12px;
            min-height: 12px;
            max-height: 12px;
            border-radius: 6px;
            background: {p.status_offline_fg};
        }}
        QLabel#StatusDotOnline {{
            min-width: 12px;
            max-width: 12px;
            min-height: 12px;
            max-height: 12px;
            border-radius: 6px;
            background: {p.status_online_fg};
        }}
        QLabel#StatusDotBusy {{
            min-width: 12px;
            max-width: 12px;
            min-height: 12px;
            max-height: 12px;
            border-radius: 6px;
            background: {p.status_busy_fg};
        }}
        QLabel#MainTitle {{
            color: {p.text_primary};
            font-size: 28px;
            font-weight: 800;
            background: transparent;
        }}
        QLabel#MainSubtitle {{
            color: {p.text_secondary};
            font-size: 14px;
            font-weight: 600;
            background: transparent;
        }}
        QFrame#MainPanel {{
            background: {p.bg_card if p.mode == "light" else p.bg_card};
            border: 1px solid {p.border};
            border-radius: 20px;
        }}
    """


def window_chrome_stylesheet() -> str:
    p = current_palette()
    close_hover = "#DC2626" if p.mode == "light" else "#EF4444"
    return f"""
        QFrame#CustomTitleBar {{
            background: {p.bg_page};
            border: none;
            border-bottom: 1px solid {p.border_soft};
        }}
        QLabel#TitleBarIcon {{
            background: transparent;
            border: none;
        }}
        QLabel#TitleBarText {{
            color: {p.text_primary};
            font-size: 13px;
            font-weight: 700;
            background: transparent;
        }}
        QToolButton#TitleBarButton,
        QToolButton#TitleBarCloseButton {{
            border: none;
            border-radius: 8px;
            background: transparent;
            color: {p.text_primary};
            font-size: 15px;
            font-weight: 700;
            padding: 0px;
        }}
        QToolButton#TitleBarButton:hover {{
            background: {p.list_item_hover};
        }}
        QToolButton#TitleBarCloseButton:hover {{
            background: {close_hover};
            color: #FFFFFF;
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
        QFrame#MainPanel {{
            background: {p.bg_card};
            border: 1px solid {p.border};
            border-radius: 20px;
        }}
        QLabel#MainTitle {{
            font-size: 28px;
            font-weight: 800;
            color: {p.text_primary};
            background: transparent;
        }}
        QLabel#MainSubtitle {{
            font-size: 14px;
            font-weight: 600;
            color: {p.text_secondary};
            background: transparent;
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
            background: transparent;
            outline: none;
            padding: 0px;
            border-radius: 0px;
        }}
        QListView#TicketsListView > QWidget {{
            background-color: transparent;
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
        QPushButton#TicketFilterChip,
        QPushButton#TicketFilterChipActive {{
            min-height: 38px;
            padding: 0px 16px;
            border-radius: 12px;
            font-size: 14px;
            font-weight: 700;
            color: {p.text_secondary};
            background: transparent;
            border: 1px solid transparent;
            text-align: center;
        }}
        QPushButton#TicketFilterChip:hover {{
            background: {p.list_item_hover};
            border-color: {p.border_soft};
        }}
        QPushButton#TicketFilterChipActive {{
            color: {p.accent if p.mode == "light" else p.text_primary};
            background: {p.info_bg};
            border-color: {p.list_item_selected_border};
        }}
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
        QLineEdit#SearchInput {{
            border-radius: 14px;
            background: {p.bg_input};
            border: 1px solid {p.border};
            padding: 0px 16px;
            font-size: 14px;
            font-weight: 600;
            color: {p.text_primary};
        }}
        QLineEdit#SearchInput:focus {{
            border-color: {p.accent};
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
