"""QAbstractListModel + делегат для списка тикетов без полного clear() виджета."""

from __future__ import annotations

from typing import Any, List, Optional

from PySide6.QtCore import QAbstractListModel, QModelIndex, QRect, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QStyledItemDelegate, QStyle, QStyleOptionViewItem

from . import theme
from .ticket_format import format_ts_short, ticket_row_fingerprint, ticket_status_colors, ticket_status_label

TICKET_ROLE = Qt.ItemDataRole.UserRole + 7


class TicketsListModel(QAbstractListModel):
    def __init__(self, parent: Optional[Any] = None) -> None:
        super().__init__(parent)
        self._rows: List[dict] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        ticket = self._rows[index.row()]
        if role == TICKET_ROLE:
            return ticket
        if role == Qt.ItemDataRole.DisplayRole:
            return ticket.get("title") or ""
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def ticket_at_row(self, row: int) -> Optional[dict]:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def row_for_ticket_id(self, ticket_id: object) -> int:
        tid = str(ticket_id or "").strip()
        if not tid:
            return -1
        for i, t in enumerate(self._rows):
            if str(t.get("ticket_id") or "") == tid:
                return i
        return -1

    def set_rows(self, new_rows: List[dict]) -> None:
        new_rows = list(new_rows)
        old = self._rows

        if len(old) != len(new_rows) or [x.get("ticket_id") for x in old] != [x.get("ticket_id") for x in new_rows]:
            self.beginResetModel()
            self._rows = new_rows
            self.endResetModel()
            return

        changed_rows: List[int] = []
        for i, (a, b) in enumerate(zip(old, new_rows)):
            if ticket_row_fingerprint(a) != ticket_row_fingerprint(b):
                changed_rows.append(i)
        self._rows = new_rows
        for i in changed_rows:
            idx = self.index(i, 0)
            self.dataChanged.emit(idx, idx, [TICKET_ROLE, Qt.ItemDataRole.DisplayRole])


class TicketCardDelegate(QStyledItemDelegate):
    ROW_HEIGHT = 118

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        w = option.rect.width()
        if w <= 0:
            w = 360
        return QSize(w, self.ROW_HEIGHT)

    @staticmethod
    def _px_font(base: QFont, pixel: int, bold: bool = False) -> QFont:
        f = QFont(base)
        f.setPixelSize(max(11, pixel))
        f.setBold(bold)
        return f

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        ticket = index.data(TICKET_ROLE)
        if not isinstance(ticket, dict):
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = option.rect.adjusted(8, 5, -8, -5)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)

        status = str(ticket.get("status") or "unknown").strip().lower()
        status_fg, _status_bg = ticket_status_colors(status)
        if selected:
            bg = theme.LIST_ITEM_SELECTED_BG
            border_hex = theme.LIST_ITEM_SELECTED_BORDER
            border_width = 1.4
        elif hover:
            bg = theme.LIST_ITEM_HOVER
            border_hex = theme.LIST_ITEM_HOVER_BORDER
            border_width = 1.1
        else:
            bg = theme.LIST_ITEM_BG
            border_hex = theme.LIST_ITEM_BORDER
            border_width = 1.0

        painter.setBrush(QBrush(QColor(bg)))
        painter.setPen(QPen(QColor(border_hex), border_width))
        painter.drawRoundedRect(rect, 16, 16)

        inner = rect.adjusted(24, 18, -24, -18)
        code_raw = str(ticket.get("ticket_code") or str(ticket.get("ticket_id") or "")[:8]).strip()
        code = code_raw if code_raw.startswith("#") else f"#{code_raw}"
        priority = ticket.get("priority_class") or ticket.get("priority") or "—"
        title = (ticket.get("title") or "Без названия").replace("\n", " ")
        requester = (
            ticket.get("request_kind_label")
            or ticket.get("source_label")
            or ticket.get("ticket_type_label")
            or ticket.get("requester_display_name")
            or "Codex Live"
        )
        updated_at = ticket.get("updated_at") or ticket.get("created_at") or ""
        ts = format_ts_short(updated_at) or "—"

        top_text = code
        meta_text = f"{requester}  •  {ts}"

        fm_top = self._px_font(option.font, 13, False)
        fm_mid = self._px_font(option.font, 16, True)
        fm_small = self._px_font(option.font, 12, False)

        icon_rect = QRect(inner.left(), inner.top() + 14, 58, 58)
        icon_bg = QColor(theme.ACCENT_SOFT if theme.current_theme_mode() == "light" else "#1B2F52")
        painter.setBrush(QBrush(icon_bg))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(icon_rect, 18, 18)
        self._draw_ticket_icon(painter, icon_rect, QColor(theme.ACCENT if not selected else "#22D3EE"))

        content_left = icon_rect.right() + 24
        right_reserved = 92
        text_w = max(120, inner.right() - content_left - right_reserved)

        painter.setFont(fm_top)
        painter.setPen(QColor(theme.TEXT_MUTED))
        top_rect = QRect(content_left, inner.top(), text_w, 22)
        painter.drawText(top_rect, Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextSingleLine, top_text)

        status_x = content_left + QFontMetrics(fm_top).horizontalAdvance(top_text) + 12
        painter.setPen(QColor(theme.TEXT_MUTED))
        painter.drawText(QRect(status_x, inner.top(), 10, 22), Qt.AlignmentFlag.AlignCenter, "•")
        painter.setPen(QColor(status_fg))
        status_text = ticket_status_label(status)
        status_rect = QRect(status_x + 18, inner.top(), 110, 22)
        painter.drawText(status_rect, Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextSingleLine, status_text)

        priority_text = str(priority or "—")
        pr_font = self._px_font(option.font, 12, True)
        painter.setFont(pr_font)
        pr_w = max(32, QFontMetrics(pr_font).horizontalAdvance(priority_text) + 18)
        pr_x = min(status_rect.left() + QFontMetrics(fm_top).horizontalAdvance(status_text) + 12, inner.right() - right_reserved - pr_w)
        pr_rect = QRect(pr_x, inner.top() - 1, pr_w, 24)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(theme.INFO_BG)))
        painter.drawRoundedRect(pr_rect, 8, 8)
        painter.setPen(QColor(theme.INFO_FG))
        painter.drawText(pr_rect, Qt.AlignmentFlag.AlignCenter, priority_text)

        painter.setFont(fm_mid)
        painter.setPen(QColor(theme.TEXT_PRIMARY))
        mid_metrics = QFontMetrics(fm_mid)
        elided = mid_metrics.elidedText(title, Qt.TextElideMode.ElideRight, text_w)
        painter.drawText(
            QRect(content_left, inner.top() + 30, text_w, 26),
            Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextSingleLine,
            elided,
        )

        painter.setFont(fm_small)
        painter.setPen(QColor(theme.TEXT_SECONDARY))
        painter.drawText(
            QRect(content_left, inner.top() + 60, text_w, 22),
            Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextSingleLine,
            meta_text,
        )

        counters = ticket.get("chat_counters") or {}
        um = int(counters.get("requester_unread_messages") or 0)
        ut = int(counters.get("requester_unread_tool_calls") or 0)
        bx = inner.right() - 38
        painter.setFont(self._px_font(option.font, 11, True))
        if um > 0:
            self._draw_badge(painter, bx, inner.top() + 34, str(um), theme.current_palette().danger)
            bx -= 36
        if ut > 0:
            self._draw_badge(painter, bx, inner.top() + 34, str(ut), theme.ACCENT)

        self._draw_chevron(painter, QRect(inner.right() - 18, inner.top() + 35, 18, 28), QColor(theme.TEXT_MUTED))

        painter.restore()

    @staticmethod
    def _draw_badge(painter: QPainter, right_x: int, top_y: int, text: str, fill: str) -> None:
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(fill)))
        fm = painter.fontMetrics()
        w = max(24, fm.horizontalAdvance(text) + 14)
        r = QRect(right_x - w, top_y, w, 22)
        painter.drawRoundedRect(r, 11, 11)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(r, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    @staticmethod
    def _draw_ticket_icon(painter: QPainter, rect: QRect, color: QColor) -> None:
        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(color, 2))
        body = rect.adjusted(16, 18, -16, -18)
        painter.drawRoundedRect(body, 3, 3)
        painter.drawLine(body.left() + 6, body.top(), body.left() + 6, body.bottom())
        painter.drawLine(body.right() - 6, body.top(), body.right() - 6, body.bottom())
        painter.drawLine(body.left() + 10, body.center().y(), body.right() - 10, body.center().y())
        painter.restore()

    @staticmethod
    def _draw_chevron(painter: QPainter, rect: QRect, color: QColor) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(color, 2))
        mid_y = rect.center().y()
        painter.drawLine(rect.left() + 4, mid_y - 7, rect.right() - 4, mid_y)
        painter.drawLine(rect.right() - 4, mid_y, rect.left() + 4, mid_y + 7)
        painter.restore()
