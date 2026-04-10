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
    ROW_HEIGHT = 96

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

        rect = option.rect.adjusted(6, 4, -6, -4)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)

        status = str(ticket.get("status") or "unknown").strip().lower()
        _fg, status_bg = ticket_status_colors(status)
        if selected:
            bg = theme.LIST_ITEM_SELECTED_BG
            border_hex = theme.LIST_ITEM_SELECTED_BORDER
        elif hover:
            bg = theme.LIST_ITEM_HOVER
            border_hex = theme.LIST_ITEM_HOVER_BORDER
        else:
            bg = status_bg
            border_hex = theme.BORDER_SOFT

        painter.setBrush(QBrush(QColor(bg)))
        painter.setPen(QPen(QColor(border_hex), 1))
        painter.drawRoundedRect(rect, 14, 14)

        inner = rect.adjusted(14, 10, -14, -10)
        code = ticket.get("ticket_code") or str(ticket.get("ticket_id") or "")[:8]
        priority = ticket.get("priority_class") or ticket.get("priority") or "—"
        title = (ticket.get("title") or "Без названия").replace("\n", " ")
        requester = ticket.get("requester_display_name") or "Пользователь"
        updated_at = ticket.get("updated_at") or ticket.get("created_at") or ""
        ts = format_ts_short(updated_at) or "—"

        top_text = f"#{code}  •  {ticket_status_label(status)}  •  {priority}"
        meta_text = f"{requester}  •  {ts}"

        fm_top = self._px_font(option.font, 13, True)
        fm_mid = self._px_font(option.font, 15, True)
        fm_small = self._px_font(option.font, 12, False)

        painter.setFont(fm_top)
        painter.setPen(QColor(theme.TEXT_PRIMARY))
        text_w = inner.width() - 56
        top_rect = QRect(inner.left(), inner.top(), text_w, 20)
        painter.drawText(top_rect, Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextSingleLine, top_text)

        painter.setFont(fm_mid)
        mid_metrics = QFontMetrics(fm_mid)
        elided = mid_metrics.elidedText(title, Qt.TextElideMode.ElideRight, text_w)
        painter.drawText(
            QRect(inner.left(), inner.top() + 22, text_w, 24),
            Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextSingleLine,
            elided,
        )

        painter.setFont(fm_small)
        painter.setPen(QColor(theme.TEXT_SECONDARY))
        painter.drawText(
            QRect(inner.left(), inner.top() + 48, text_w, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextSingleLine,
            meta_text,
        )

        counters = ticket.get("chat_counters") or {}
        um = int(counters.get("requester_unread_messages") or 0)
        ut = int(counters.get("requester_unread_tool_calls") or 0)
        bx = inner.right() - 4
        painter.setFont(self._px_font(option.font, 11, True))
        if um > 0:
            self._draw_badge(painter, bx, inner.top() + 6, str(um), "#b91c1c")
            bx -= 36
        if ut > 0:
            self._draw_badge(painter, bx, inner.top() + 6, str(ut), theme.ACCENT)

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
