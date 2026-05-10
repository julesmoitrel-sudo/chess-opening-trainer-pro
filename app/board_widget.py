"""Echiquier interactif avec drag & drop, surlignages, retournement.

Rendu custom (QPainter) pour rester totalement portable et indépendant
des images externes. Les pièces sont dessinées en Unicode (figurines).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional

import chess
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QResizeEvent,
)
from PySide6.QtWidgets import QWidget


# Glyphes Unicode pour chaque pièce
PIECE_GLYPHS: Dict[str, str] = {
    "K": "♔", "Q": "♕", "R": "♖",
    "B": "♗", "N": "♘", "P": "♙",
    "k": "♚", "q": "♛", "r": "♜",
    "b": "♝", "n": "♞", "p": "♟",
}


@dataclass
class BoardTheme:
    light_square: QColor
    dark_square: QColor
    light_piece: QColor
    dark_piece: QColor
    border: QColor
    coord_text: QColor
    last_move: QColor
    recommended: QColor
    selected: QColor
    legal_dot: QColor
    check: QColor


def dark_theme() -> BoardTheme:
    return BoardTheme(
        light_square=QColor("#E8DCC4"),
        dark_square=QColor("#7B6A52"),
        light_piece=QColor("#FFFFFF"),
        dark_piece=QColor("#1B1B1B"),
        border=QColor("#1B1B1B"),
        coord_text=QColor("#A89B82"),
        last_move=QColor(255, 213, 79, 110),
        recommended=QColor(80, 200, 120, 130),
        selected=QColor(80, 160, 230, 130),
        legal_dot=QColor(20, 20, 20, 110),
        check=QColor(220, 40, 40, 160),
    )


class BoardWidget(QWidget):
    """Widget d'échiquier avec interaction utilisateur complète.

    Émet :
      - move_played(uci): l'utilisateur a déposé une pièce sur une case légale.
    """

    move_played = Signal(str)  # UCI string

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(420, 420)
        self.setMouseTracking(True)
        self.theme: BoardTheme = dark_theme()

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
        margin = 18.0 if self._show_coords else 8.0
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
        # Convertir en (file, rank) selon orientation
        if self._orientation_white_bottom:
            file = col
            rank = 7 - row
        else:
            file = 7 - col
            rank = row
        return chess.square(file, rank)

    def _square_rect(self, square: int) -> QRectF:
        rect = self._board_rect()
        ss = self._square_size()
        file = chess.square_file(square)
        rank = chess.square_rank(square)
        if self._orientation_white_bottom:
            col = file
            row = 7 - rank
        else:
            col = 7 - file
            row = rank
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
        # Promotion automatique en dame
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
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)

        # Fond + bordure subtile
        rect = self._board_rect()
        outer = rect.adjusted(-6, -6, 6, 6)
        grad = QLinearGradient(outer.topLeft(), outer.bottomRight())
        grad.setColorAt(0, QColor("#23272f"))
        grad.setColorAt(1, QColor("#11141a"))
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(self.theme.border, 1.5))
        painter.drawRoundedRect(outer, 10, 10)

        # Cases
        ss = self._square_size()
        for square in chess.SQUARES:
            r = self._square_rect(square)
            light = (chess.square_file(square) + chess.square_rank(square)) % 2 == 1
            color = self.theme.light_square if light else self.theme.dark_square
            painter.fillRect(r, color)

        # Surlignages : dernier coup
        if self._last_move is not None:
            painter.fillRect(self._square_rect(self._last_move.from_square), self.theme.last_move)
            painter.fillRect(self._square_rect(self._last_move.to_square), self.theme.last_move)

        # Surlignage : coup recommandé
        if self._recommended_move is not None:
            painter.fillRect(self._square_rect(self._recommended_move.from_square), self.theme.recommended)
            painter.fillRect(self._square_rect(self._recommended_move.to_square), self.theme.recommended)

        # Sélection / cibles légales
        if self._selected_square is not None:
            painter.fillRect(self._square_rect(self._selected_square), self.theme.selected)
        if self._legal_targets:
            for target in self._legal_targets:
                tr = self._square_rect(target)
                cx = tr.center().x()
                cy = tr.center().y()
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
            f.setPointSizeF(max(8.0, ss * 0.18))
            f.setBold(True)
            painter.setFont(f)
            for i in range(8):
                rank = 7 - i if self._orientation_white_bottom else i
                file = i if self._orientation_white_bottom else 7 - i
                # rangées (à gauche)
                rect_left = QRectF(rect.left() - 16, rect.top() + i * ss, 14, ss)
                painter.drawText(rect_left, Qt.AlignVCenter | Qt.AlignRight, str(rank + 1))
                # colonnes (en bas)
                rect_bottom = QRectF(rect.left() + i * ss, rect.bottom() + 2, ss, 14)
                painter.drawText(rect_bottom, Qt.AlignHCenter | Qt.AlignTop, chr(ord("a") + file))

        # Pièces
        font = QFont(self.font())
        font.setPointSizeF(ss * 0.72)
        painter.setFont(font)
        fm = QFontMetricsF(font)

        for square in chess.SQUARES:
            if self._dragging_from == square:
                continue
            piece = self._board.piece_at(square)
            if piece is None:
                continue
            self._draw_piece(painter, piece, self._square_rect(square), fm)

        # Pièce en cours de drag (au-dessus)
        if self._dragging_from is not None and self._drag_pos is not None:
            piece = self._board.piece_at(self._dragging_from)
            if piece is not None:
                r = QRectF(self._drag_pos.x() - ss / 2, self._drag_pos.y() - ss / 2, ss, ss)
                self._draw_piece(painter, piece, r, fm)

        painter.end()

    def _draw_piece(
        self,
        painter: QPainter,
        piece: chess.Piece,
        rect: QRectF,
        fm: QFontMetricsF,
    ) -> None:
        symbol_white = piece.symbol().upper()
        glyph = PIECE_GLYPHS[symbol_white]  # on dessine toujours la silhouette pleine

        # Ombre subtile
        painter.setPen(QPen(QColor(0, 0, 0, 130)))
        shadow_rect = QRectF(rect)
        shadow_rect.translate(1.5, 2.0)
        painter.drawText(shadow_rect, Qt.AlignCenter, glyph)

        # Couleur de la pièce
        color = self.theme.light_piece if piece.color == chess.WHITE else self.theme.dark_piece
        painter.setPen(QPen(color))
        painter.drawText(rect, Qt.AlignCenter, glyph)

        # Contour fin pour lisibilité
        contour = QColor(0, 0, 0) if piece.color == chess.WHITE else QColor(255, 255, 255, 80)
        painter.setPen(QPen(contour, 0.6))
        painter.drawText(rect, Qt.AlignCenter, glyph)
