"""Echiquier interactif : pièces SVG (chess.svg), drag & drop, surlignages.

Le rendu utilise les SVG de python-chess (chess.svg.piece) via QSvgRenderer,
garantissant une lisibilité maximale, des pièces nettement différenciées
(blanc à contour noir, noir à contour blanc) et un visuel premium.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import chess
import chess.svg

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QResizeEvent,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget


@dataclass
class BoardTheme:
    light_square: QColor
    dark_square: QColor
    border: QColor
    coord_text: QColor
    last_move: QColor
    recommended: QColor
    selected: QColor
    legal_dot: QColor
    capture_ring: QColor
    check: QColor


def premium_theme() -> BoardTheme:
    """Palette inspirée des thèmes 'wood/green' premium, très contrastée."""
    return BoardTheme(
        light_square=QColor("#EEEED2"),  # ivoire
        dark_square=QColor("#769656"),   # vert profond
        border=QColor("#0E1116"),
        coord_text=QColor("#C9D1DC"),
        last_move=QColor(245, 220, 80, 150),
        recommended=QColor(80, 200, 120, 160),
        selected=QColor(120, 200, 255, 130),
        legal_dot=QColor(20, 20, 20, 110),
        capture_ring=QColor(220, 60, 60, 180),
        check=QColor(220, 50, 50, 170),
    )


# -- SVG piece rendering -----------------------------------------------------

_renderer_cache: Dict[str, QSvgRenderer] = {}


def _get_renderer(piece: chess.Piece) -> QSvgRenderer:
    sym = piece.symbol()
    renderer = _renderer_cache.get(sym)
    if renderer is None:
        svg_text = chess.svg.piece(piece)
        renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
        _renderer_cache[sym] = renderer
    return renderer


_pixmap_cache: Dict[Tuple[str, int], QImage] = {}


def _piece_image(piece: chess.Piece, size: int) -> QImage:
    key = (piece.symbol(), size)
    img = _pixmap_cache.get(key)
    if img is None:
        img = QImage(size, size, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        painter = QPainter(img)
        painter.setRenderHints(
            QPainter.Antialiasing
            | QPainter.SmoothPixmapTransform
            | QPainter.TextAntialiasing
        )
        _get_renderer(piece).render(painter, QRectF(0, 0, size, size))
        painter.end()
        if len(_pixmap_cache) > 256:
            _pixmap_cache.clear()
        _pixmap_cache[key] = img
    return img


# -- Widget ------------------------------------------------------------------

class BoardWidget(QWidget):
    """Widget d'échiquier avec interaction utilisateur complète."""

    move_played = Signal(str)  # UCI string

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(440, 440)
        self.setMouseTracking(True)
        self.theme: BoardTheme = premium_theme()

        self._board: chess.Board = chess.Board()
        self._orientation_white_bottom: bool = True
        self._show_coords: bool = True

        # Interaction state
        self._selected_square: Optional[int] = None
        self._dragging_from: Optional[int] = None
        self._drag_pos: Optional[QPointF] = None
        self._legal_targets: set[int] = set()

        # Surlignages
        self._last_move: Optional[chess.Move] = None
        self._recommended_move: Optional[chess.Move] = None

    # ---------- API ----------

    def set_board(self, board: chess.Board) -> None:
        self._board = board
        self._selected_square = None
        self._dragging_from = None
        self._legal_targets.clear()
        self.update()

    def set_orientation(self, white_bottom: bool) -> None:
        self._orientation_white_bottom = white_bottom
        self.update()

    def flip(self) -> None:
        self._orientation_white_bottom = not self._orientation_white_bottom
        self.update()

    def set_last_move(self, move: Optional[chess.Move]) -> None:
        self._last_move = move
        self.update()

    def set_recommended_move(self, move: Optional[chess.Move]) -> None:
        self._recommended_move = move
        self.update()

    # ---------- Geometry ----------

    def _board_rect(self) -> QRectF:
        margin = 22.0 if self._show_coords else 10.0
        size = min(self.width(), self.height()) - 2 * margin
        size = max(size, 0.0)
        x = (self.width() - size) / 2.0
        y = (self.height() - size) / 2.0
        return QRectF(x, y, size, size)

    def _square_size(self) -> float:
        return self._board_rect().width() / 8.0

    def _square_at(self, point: QPointF) -> Optional[int]:
        rect = self._board_rect()
        if not rect.contains(point):
            return None
        ss = self._square_size()
        col = int((point.x() - rect.left()) // ss)
        row = int((point.y() - rect.top()) // ss)
        col = max(0, min(7, col))
        row = max(0, min(7, row))
        if self._orientation_white_bottom:
            file, rank = col, 7 - row
        else:
            file, rank = 7 - col, row
        return chess.square(file, rank)

    def _square_rect(self, square: int) -> QRectF:
        rect = self._board_rect()
        ss = self._square_size()
        file = chess.square_file(square)
        rank = chess.square_rank(square)
        if self._orientation_white_bottom:
            col, row = file, 7 - rank
        else:
            col, row = 7 - file, rank
        return QRectF(rect.left() + col * ss, rect.top() + row * ss, ss, ss)

    # ---------- Mouse ----------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.LeftButton:
            return
        sq = self._square_at(event.position())
        if sq is None:
            return
        piece = self._board.piece_at(sq)
        if piece is not None and piece.color == self._board.turn:
            self._dragging_from = sq
            self._selected_square = sq
            self._drag_pos = event.position()
            self._legal_targets = {
                m.to_square for m in self._board.legal_moves if m.from_square == sq
            }
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._dragging_from is not None:
            self._drag_pos = event.position()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._dragging_from is None:
            return
        target = self._square_at(event.position())
        from_sq = self._dragging_from
        self._dragging_from = None
        self._drag_pos = None

        if target is None or target == from_sq:
            self._legal_targets.clear()
            self.update()
            return

        move = chess.Move(from_sq, target)
        piece = self._board.piece_at(from_sq)
        if piece and piece.piece_type == chess.PAWN:
            target_rank = chess.square_rank(target)
            if (piece.color == chess.WHITE and target_rank == 7) or (
                piece.color == chess.BLACK and target_rank == 0
            ):
                move = chess.Move(from_sq, target, promotion=chess.QUEEN)

        if move in self._board.legal_moves:
            self._legal_targets.clear()
            self._selected_square = None
            self.move_played.emit(move.uci())
        else:
            self._legal_targets.clear()
            self._selected_square = None
            self.update()

    # ---------- Painting ----------

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.Antialiasing
            | QPainter.TextAntialiasing
            | QPainter.SmoothPixmapTransform
        )

        rect = self._board_rect()
        ss = self._square_size()

        # Cadre / bordure
        outer = rect.adjusted(-8, -8, 8, 8)
        grad = QLinearGradient(outer.topLeft(), outer.bottomRight())
        grad.setColorAt(0, QColor("#1A2030"))
        grad.setColorAt(1, QColor("#0A0D13"))
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(self.theme.border, 1.5))
        painter.drawRoundedRect(outer, 12, 12)

        # Cases
        for square in chess.SQUARES:
            r = self._square_rect(square)
            light = (chess.square_file(square) + chess.square_rank(square)) % 2 == 1
            color = self.theme.light_square if light else self.theme.dark_square
            painter.fillRect(r, color)

        # Surlignages dernier coup
        if self._last_move is not None:
            painter.fillRect(self._square_rect(self._last_move.from_square), self.theme.last_move)
            painter.fillRect(self._square_rect(self._last_move.to_square), self.theme.last_move)

        # Coup recommandé : flèche-encadrement
        if self._recommended_move is not None:
            self._draw_recommendation_overlay(painter, self._recommended_move, ss)

        # Sélection
        if self._selected_square is not None:
            painter.fillRect(self._square_rect(self._selected_square), self.theme.selected)

        # Cibles légales
        if self._legal_targets:
            for target in self._legal_targets:
                tr = self._square_rect(target)
                cx = tr.center().x()
                cy = tr.center().y()
                if self._board.piece_at(target) is not None:
                    # Anneau pour capture
                    pen = QPen(self.theme.capture_ring, max(2.0, ss * 0.045))
                    painter.setPen(pen)
                    painter.setBrush(Qt.NoBrush)
                    inset = ss * 0.06
                    painter.drawEllipse(tr.adjusted(inset, inset, -inset, -inset))
                else:
                    radius = ss * 0.16
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QBrush(self.theme.legal_dot))
                    painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # Échec
        if self._board.is_check():
            king_sq = self._board.king(self._board.turn)
            if king_sq is not None:
                painter.fillRect(self._square_rect(king_sq), self.theme.check)

        # Coordonnées
        if self._show_coords:
            painter.setPen(QPen(self.theme.coord_text))
            f = QFont(self.font())
            f.setPointSizeF(max(9.0, ss * 0.20))
            f.setBold(True)
            painter.setFont(f)
            for i in range(8):
                rank = 7 - i if self._orientation_white_bottom else i
                file = i if self._orientation_white_bottom else 7 - i
                rect_left = QRectF(rect.left() - 20, rect.top() + i * ss, 17, ss)
                painter.drawText(rect_left, Qt.AlignVCenter | Qt.AlignRight, str(rank + 1))
                rect_bottom = QRectF(rect.left() + i * ss, rect.bottom() + 3, ss, 16)
                painter.drawText(rect_bottom, Qt.AlignHCenter | Qt.AlignTop, chr(ord("a") + file))

        # Pièces (SVG cachées en QImage)
        piece_size = max(8, int(ss))
        for square in chess.SQUARES:
            if self._dragging_from == square:
                continue
            piece = self._board.piece_at(square)
            if piece is None:
                continue
            self._draw_piece(painter, piece, self._square_rect(square), piece_size)

        # Pièce en cours de drag (au-dessus)
        if self._dragging_from is not None and self._drag_pos is not None:
            piece = self._board.piece_at(self._dragging_from)
            if piece is not None:
                r = QRectF(self._drag_pos.x() - ss / 2, self._drag_pos.y() - ss / 2, ss, ss)
                self._draw_piece(painter, piece, r, piece_size)

        painter.end()

    def _draw_piece(
        self,
        painter: QPainter,
        piece: chess.Piece,
        rect: QRectF,
        piece_size: int,
    ) -> None:
        pad = max(2.0, rect.width() * 0.04)
        target = rect.adjusted(pad, pad, -pad, -pad)
        img = _piece_image(piece, piece_size)
        # Ombre subtile
        painter.setOpacity(0.32)
        painter.drawImage(target.translated(1.5, 2.0), img)
        painter.setOpacity(1.0)
        painter.drawImage(target, img)

    def _draw_recommendation_overlay(
        self,
        painter: QPainter,
        move: chess.Move,
        ss: float,
    ) -> None:
        from_rect = self._square_rect(move.from_square)
        to_rect = self._square_rect(move.to_square)
        painter.fillRect(from_rect, self.theme.recommended)
        painter.fillRect(to_rect, self.theme.recommended)
        # Fine bordure verte autour de la case d'arrivée
        pen = QPen(QColor(40, 160, 90, 220), max(2.0, ss * 0.045))
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(to_rect.adjusted(2, 2, -2, -2))
