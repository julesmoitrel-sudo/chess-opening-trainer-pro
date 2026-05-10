"""Interface utilisateur PySide6 : welcome, écran principal, paramètres."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import chess
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from . import __app_name__, __version__
from .board_widget import BoardWidget
from .engine import EngineManager, detect_stockfish, test_engine
from .game_manager import GameManager, Recommendation
from .opening_book import OpeningBook
from .settings import Settings


# -----------------------------------------------------------------------------
# Style
# -----------------------------------------------------------------------------

DARK_QSS = """
* { font-family: 'Segoe UI', 'Inter', 'Helvetica Neue', Arial, sans-serif; color: #E8ECF1; }
QWidget#root, QMainWindow, QDialog { background-color: #0E1116; }

QLabel#h1 { font-size: 30px; font-weight: 700; letter-spacing: 0.5px; color: #F4F6FA; }
QLabel#h2 { font-size: 18px; font-weight: 600; color: #C9D1DC; }
QLabel#muted { color: #7A8597; font-size: 12px; }
QLabel#warn { color: #E5B25E; font-size: 12px; font-style: italic; }

QFrame#card {
    background-color: #161A22;
    border: 1px solid #232936;
    border-radius: 14px;
}

QFrame#chip {
    background-color: #1B2230;
    border: 1px solid #2B3447;
    border-radius: 999px;
    padding: 4px 10px;
}

QPushButton {
    background-color: #1F2733;
    border: 1px solid #2B3447;
    border-radius: 10px;
    padding: 8px 14px;
    font-weight: 500;
    color: #E8ECF1;
}
QPushButton:hover { background-color: #28324A; }
QPushButton:pressed { background-color: #1A2030; }
QPushButton:disabled { color: #5C6473; background-color: #161A22; }

QPushButton#primary {
    background-color: #5469F4;
    border: 1px solid #6378FF;
    color: white;
}
QPushButton#primary:hover { background-color: #6378FF; }
QPushButton#primary:pressed { background-color: #3F52D6; }

QPushButton#danger {
    background-color: #2B1F1F;
    border: 1px solid #5A3030;
    color: #E5A6A6;
}
QPushButton#danger:hover { background-color: #3A2626; }

QLineEdit, QPlainTextEdit, QComboBox, QSpinBox {
    background-color: #11151D;
    border: 1px solid #2B3447;
    border-radius: 8px;
    padding: 6px 8px;
    selection-background-color: #5469F4;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {
    border-color: #5469F4;
}

QComboBox QAbstractItemView {
    background-color: #11151D;
    border: 1px solid #2B3447;
    selection-background-color: #5469F4;
}

QStatusBar { background: #11151D; color: #7A8597; border-top: 1px solid #232936; }

QLabel#statusOk { color: #6BD4A0; font-weight: 600; }
QLabel#statusWarn { color: #E5B25E; font-weight: 600; }
QLabel#statusErr { color: #E57373; font-weight: 600; }

QFrame#divider { background-color: #232936; max-height: 1px; min-height: 1px; }

QRadioButton, QCheckBox { spacing: 8px; }
QRadioButton::indicator, QCheckBox::indicator { width: 16px; height: 16px; }
"""


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _chip(text: str, kind: str = "default") -> QLabel:
    label = QLabel(text)
    label.setObjectName("chip")
    if kind == "ok":
        label.setStyleSheet("background:#143324; border:1px solid #1F5A40; color:#7AE5B0; border-radius:999px; padding:4px 12px;")
    elif kind == "warn":
        label.setStyleSheet("background:#332714; border:1px solid #5A4220; color:#E5C27A; border-radius:999px; padding:4px 12px;")
    elif kind == "err":
        label.setStyleSheet("background:#33181A; border:1px solid #5A292C; color:#E58993; border-radius:999px; padding:4px 12px;")
    elif kind == "info":
        label.setStyleSheet("background:#142133; border:1px solid #1F3A5A; color:#7AB6E5; border-radius:999px; padding:4px 12px;")
    return label


def _divider() -> QFrame:
    line = QFrame()
    line.setObjectName("divider")
    line.setFrameShape(QFrame.NoFrame)
    return line


# -----------------------------------------------------------------------------
# Welcome screen
# -----------------------------------------------------------------------------

class WelcomeScreen(QWidget):
    """Écran d'accueil : choix couleur, choix ouverture, démarrage."""

    start_requested = Signal(str, str)  # color ("white"/"black"), opening_name

    def __init__(self, book: OpeningBook, settings: Settings, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.book = book
        self.settings = settings
        self.setObjectName("root")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(48, 36, 48, 36)
        outer.setSpacing(18)

        title = QLabel(__app_name__)
        title.setObjectName("h1")
        subtitle = QLabel("Travaillez vos ouvertures, comprenez les idées, analysez après partie.")
        subtitle.setObjectName("muted")
        outer.addWidget(title)
        outer.addWidget(subtitle)

        warn = QLabel(
            "⚠ Outil d'entraînement et d'analyse personnelle. À ne pas utiliser pendant "
            "une partie en ligne sur Chess.com, Lichess ou autre plateforme."
        )
        warn.setObjectName("warn")
        warn.setWordWrap(True)
        outer.addWidget(warn)

        outer.addWidget(_divider())

        body = QHBoxLayout()
        body.setSpacing(20)
        outer.addLayout(body, 1)

        # Carte gauche : configuration
        config_card = QFrame()
        config_card.setObjectName("card")
        config_layout = QVBoxLayout(config_card)
        config_layout.setContentsMargins(24, 24, 24, 24)
        config_layout.setSpacing(14)

        h2 = QLabel("Nouvelle analyse")
        h2.setObjectName("h2")
        config_layout.addWidget(h2)

        # Couleur
        color_label = QLabel("Vous jouez :")
        color_label.setObjectName("muted")
        config_layout.addWidget(color_label)
        color_row = QHBoxLayout()
        self.radio_white = QRadioButton("Blancs")
        self.radio_black = QRadioButton("Noirs")
        if settings.get("last_color", "white") == "black":
            self.radio_black.setChecked(True)
        else:
            self.radio_white.setChecked(True)
        color_row.addWidget(self.radio_white)
        color_row.addWidget(self.radio_black)
        color_row.addStretch()
        config_layout.addLayout(color_row)

        # Ouverture
        op_label = QLabel("Ouverture à travailler :")
        op_label.setObjectName("muted")
        config_layout.addWidget(op_label)
        self.combo_opening = QComboBox()
        config_layout.addWidget(self.combo_opening)

        self.idea_box = QLabel()
        self.idea_box.setWordWrap(True)
        self.idea_box.setObjectName("muted")
        self.idea_box.setMinimumHeight(60)
        config_layout.addWidget(self.idea_box)

        config_layout.addStretch()

        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("Commencer")
        self.btn_start.setObjectName("primary")
        self.btn_start.setMinimumHeight(40)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_start)
        config_layout.addLayout(btn_row)

        body.addWidget(config_card, 1)

        # Carte droite : visuel
        visual_card = QFrame()
        visual_card.setObjectName("card")
        visual_layout = QVBoxLayout(visual_card)
        visual_layout.setContentsMargins(20, 20, 20, 20)
        self.preview_board = BoardWidget()
        self.preview_board.setMinimumSize(360, 360)
        visual_layout.addWidget(self.preview_board, 1)
        tagline = QLabel("Une bibliothèque d'ouvertures riche, des explications claires, Stockfish en filet de sécurité.")
        tagline.setObjectName("muted")
        tagline.setWordWrap(True)
        tagline.setAlignment(Qt.AlignCenter)
        visual_layout.addWidget(tagline)
        body.addWidget(visual_card, 1)

        # Wiring
        self.radio_white.toggled.connect(self._refresh_openings)
        self.combo_opening.currentIndexChanged.connect(self._refresh_idea)
        self.btn_start.clicked.connect(self._on_start)

        self._refresh_openings()

    def _refresh_openings(self) -> None:
        color = "white" if self.radio_white.isChecked() else "black"
        self.combo_opening.blockSignals(True)
        self.combo_opening.clear()
        self.combo_opening.addItem("— Aucune (analyse libre) —", userData=None)
        for op in self.book.list_for_color(color):
            self.combo_opening.addItem(op.name, userData=op.name)

        last = self.settings.get("last_opening", "")
        if last:
            idx = self.combo_opening.findData(last)
            if idx >= 0:
                self.combo_opening.setCurrentIndex(idx)
        self.combo_opening.blockSignals(False)
        self._refresh_idea()

    def _refresh_idea(self) -> None:
        name = self.combo_opening.currentData()
        if not name:
            self.idea_box.setText("Mode libre : suivez la théorie de toute ouverture détectée par transposition.")
            return
        for op in self.book.openings:
            if op.name == name:
                self.idea_box.setText(f"Idée — {op.idea}")
                return
        self.idea_box.setText("")

    def _on_start(self) -> None:
        color = "white" if self.radio_white.isChecked() else "black"
        opening = self.combo_opening.currentData()
        self.settings.set("last_color", color)
        self.settings.set("last_opening", opening or "")
        self.start_requested.emit(color, opening or "")


# -----------------------------------------------------------------------------
# Settings dialog
# -----------------------------------------------------------------------------

class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, engine: EngineManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Paramètres")
        self.setModal(True)
        self.resize(560, 460)
        self.settings = settings
        self.engine = engine

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("Paramètres")
        title.setObjectName("h2")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        # Stockfish path
        path_row = QHBoxLayout()
        self.path_edit = QLineEdit(settings.get("stockfish_path", "") or "")
        browse = QPushButton("Parcourir…")
        browse.clicked.connect(self._browse_stockfish)
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(browse)
        path_widget = QWidget()
        path_widget.setLayout(path_row)
        form.addRow("Chemin Stockfish :", path_widget)

        # Test button + status
        self.status_label = QLabel()
        self.status_label.setObjectName("muted")
        test_btn = QPushButton("Tester Stockfish")
        test_btn.clicked.connect(self._test_stockfish)
        test_row = QHBoxLayout()
        test_row.addWidget(test_btn)
        test_row.addWidget(self.status_label, 1)
        test_widget = QWidget()
        test_widget.setLayout(test_row)
        form.addRow("", test_widget)

        # Depth
        self.spin_depth = QSpinBox()
        self.spin_depth.setRange(4, 30)
        self.spin_depth.setValue(int(settings.get("engine_depth", 16)))
        form.addRow("Profondeur d'analyse :", self.spin_depth)

        # Movetime
        self.spin_time = QSpinBox()
        self.spin_time.setRange(50, 10000)
        self.spin_time.setSingleStep(50)
        self.spin_time.setSuffix(" ms")
        self.spin_time.setValue(int(settings.get("engine_movetime_ms", 800)))
        form.addRow("Temps max par coup :", self.spin_time)

        # Explanations
        self.cb_expl = QCheckBox("Afficher les explications stratégiques")
        self.cb_expl.setChecked(bool(settings.get("show_explanations", True)))
        form.addRow("", self.cb_expl)

        # PGN dir
        pgn_row = QHBoxLayout()
        self.pgn_dir_edit = QLineEdit(settings.get("pgn_export_dir", "") or "")
        pgn_browse = QPushButton("Parcourir…")
        pgn_browse.clicked.connect(self._browse_pgn)
        pgn_row.addWidget(self.pgn_dir_edit, 1)
        pgn_row.addWidget(pgn_browse)
        pgn_widget = QWidget()
        pgn_widget.setLayout(pgn_row)
        form.addRow("Dossier PGN :", pgn_widget)

        layout.addLayout(form)
        layout.addStretch()

        # Boutons
        btn_row = QHBoxLayout()
        reset_btn = QPushButton("Réinitialiser")
        reset_btn.setObjectName("danger")
        reset_btn.clicked.connect(self._on_reset)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Save).setText("Enregistrer")
        bb.button(QDialogButtonBox.Cancel).setText("Annuler")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()
        btn_row.addWidget(bb)
        layout.addLayout(btn_row)

    def _browse_stockfish(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Sélectionner Stockfish")
        if path:
            self.path_edit.setText(path)

    def _browse_pgn(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choisir le dossier PGN")
        if path:
            self.pgn_dir_edit.setText(path)

    def _test_stockfish(self) -> None:
        ok, msg = test_engine(self.path_edit.text().strip())
        self.status_label.setText(msg)
        self.status_label.setObjectName("statusOk" if ok else "statusErr")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _on_reset(self) -> None:
        if QMessageBox.question(self, "Réinitialiser", "Réinitialiser tous les paramètres ?") == QMessageBox.Yes:
            self.settings.reset()
            self.path_edit.setText("")
            self.spin_depth.setValue(16)
            self.spin_time.setValue(800)
            self.cb_expl.setChecked(True)
            self.pgn_dir_edit.setText("")

    def accept(self) -> None:  # noqa: D401
        self.settings.set("stockfish_path", self.path_edit.text().strip())
        self.settings.set("engine_depth", int(self.spin_depth.value()))
        self.settings.set("engine_movetime_ms", int(self.spin_time.value()))
        self.settings.set("show_explanations", bool(self.cb_expl.isChecked()))
        self.settings.set("pgn_export_dir", self.pgn_dir_edit.text().strip())
        # Recharger le moteur si le chemin a changé
        new_path = self.settings.get("stockfish_path", "")
        if new_path:
            self.engine.open(new_path)
        super().accept()


# -----------------------------------------------------------------------------
# Main analysis screen
# -----------------------------------------------------------------------------

class MainScreen(QWidget):
    back_requested = Signal()
    settings_requested = Signal()
    new_game_requested = Signal()

    def __init__(
        self,
        book: OpeningBook,
        engine: EngineManager,
        settings: Settings,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("root")
        self.book = book
        self.engine = engine
        self.settings = settings
        self.game = GameManager(book, engine)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        # Header
        header = QHBoxLayout()
        title = QLabel(__app_name__)
        title.setObjectName("h2")
        header.addWidget(title)
        header.addStretch()
        self.engine_chip = _chip("Stockfish: ?", "warn")
        header.addWidget(self.engine_chip)
        back = QPushButton("← Accueil")
        back.clicked.connect(self.back_requested.emit)
        header.addWidget(back)
        settings_btn = QPushButton("Paramètres")
        settings_btn.clicked.connect(self.settings_requested.emit)
        header.addWidget(settings_btn)
        root.addLayout(header)

        # Body
        body = QHBoxLayout()
        body.setSpacing(14)
        root.addLayout(body, 1)

        # --- Colonne gauche : infos partie ---
        left_card = QFrame()
        left_card.setObjectName("card")
        left = QVBoxLayout(left_card)
        left.setContentsMargins(18, 18, 18, 18)
        left.setSpacing(10)

        info_title = QLabel("Partie")
        info_title.setObjectName("h2")
        left.addWidget(info_title)

        self.label_color = QLabel("Couleur : —")
        self.label_opening = QLabel("Ouverture : —")
        self.label_variation = QLabel("Variante : —")
        for w in (self.label_color, self.label_opening, self.label_variation):
            w.setWordWrap(True)
            left.addWidget(w)

        left.addWidget(_divider())
        left.addWidget(QLabel("Statut"))
        self.status_chip = _chip("En attente", "info")
        left.addWidget(self.status_chip, 0, Qt.AlignLeft)

        left.addWidget(_divider())
        left.addWidget(QLabel("Stockfish"))
        self.engine_status = QLabel("Détection en cours…")
        self.engine_status.setObjectName("muted")
        self.engine_status.setWordWrap(True)
        left.addWidget(self.engine_status)
        engine_row = QHBoxLayout()
        btn_test = QPushButton("Tester")
        btn_test.clicked.connect(self._test_engine_clicked)
        btn_change = QPushButton("Modifier")
        btn_change.clicked.connect(self.settings_requested.emit)
        engine_row.addWidget(btn_test)
        engine_row.addWidget(btn_change)
        engine_row.addStretch()
        left.addLayout(engine_row)

        left.addStretch()
        body.addWidget(left_card, 0)

        # --- Centre : échiquier ---
        center_card = QFrame()
        center_card.setObjectName("card")
        center = QVBoxLayout(center_card)
        center.setContentsMargins(18, 18, 18, 18)
        center.setSpacing(10)

        self.board_widget = BoardWidget()
        self.board_widget.move_played.connect(self._on_user_dropped_move)
        self.board_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        center.addWidget(self.board_widget, 1)

        # Saisie + boutons d'action
        input_row = QHBoxLayout()
        self.move_input = QLineEdit()
        self.move_input.setPlaceholderText("Coup adverse (e4, Nf3, e2e4, O-O…)")
        self.move_input.returnPressed.connect(self._submit_move)
        btn_validate = QPushButton("Valider")
        btn_validate.clicked.connect(self._submit_move)
        btn_best = QPushButton("Meilleur coup")
        btn_best.setObjectName("primary")
        btn_best.clicked.connect(self._play_recommended)
        input_row.addWidget(self.move_input, 1)
        input_row.addWidget(btn_validate)
        input_row.addWidget(btn_best)
        center.addLayout(input_row)

        action_row = QHBoxLayout()
        btn_undo = QPushButton("Retour")
        btn_undo.clicked.connect(self._undo)
        btn_new = QPushButton("Nouvelle partie")
        btn_new.clicked.connect(self.new_game_requested.emit)
        btn_flip = QPushButton("Retourner l'échiquier")
        btn_flip.clicked.connect(self.board_widget.flip)
        btn_pgn = QPushButton("Exporter PGN")
        btn_pgn.clicked.connect(self._export_pgn)
        for b in (btn_undo, btn_new, btn_flip, btn_pgn):
            action_row.addWidget(b)
        action_row.addStretch()
        center.addLayout(action_row)

        body.addWidget(center_card, 1)

        # --- Droite : recommandation + historique ---
        right_card = QFrame()
        right_card.setObjectName("card")
        right = QVBoxLayout(right_card)
        right.setContentsMargins(18, 18, 18, 18)
        right.setSpacing(10)

        rec_title = QLabel("Recommandation")
        rec_title.setObjectName("h2")
        right.addWidget(rec_title)

        self.rec_move = QLabel("—")
        font = QFont()
        font.setPointSize(28)
        font.setBold(True)
        self.rec_move.setFont(font)
        right.addWidget(self.rec_move)

        self.rec_source = _chip("—", "info")
        right.addWidget(self.rec_source, 0, Qt.AlignLeft)

        self.rec_idea = QLabel("")
        self.rec_idea.setWordWrap(True)
        self.rec_idea.setObjectName("muted")
        right.addWidget(self.rec_idea)

        right.addWidget(_divider())
        right.addWidget(QLabel("Alternatives"))
        self.rec_alts = QLabel("—")
        self.rec_alts.setObjectName("muted")
        self.rec_alts.setWordWrap(True)
        right.addWidget(self.rec_alts)

        right.addWidget(_divider())
        right.addWidget(QLabel("Historique"))
        self.history_view = QPlainTextEdit()
        self.history_view.setReadOnly(True)
        self.history_view.setMinimumHeight(140)
        right.addWidget(self.history_view, 1)

        body.addWidget(right_card, 0)

        body.setStretch(0, 0)
        body.setStretch(1, 1)
        body.setStretch(2, 0)

    # ----- Lifecycle -----

    def start_new_game(self, color: str, opening_name: str) -> None:
        user_color = chess.WHITE if color == "white" else chess.BLACK
        self.game.new_game(user_color, opening_name or None)
        self.board_widget.set_board(self.game.board)
        self.board_widget.set_orientation(user_color == chess.WHITE)
        self.board_widget.set_last_move(None)
        self.board_widget.set_recommended_move(None)
        self.label_color.setText(f"Couleur : {'Blancs' if user_color == chess.WHITE else 'Noirs'}")
        self.label_opening.setText(f"Ouverture : {opening_name or 'Libre'}")
        self.label_variation.setText("Variante : —")
        self.history_view.setPlainText("")
        self.move_input.clear()
        self._update_status_chip("Prêt", "info")
        self.rec_move.setText("—")
        self.rec_source.setText("—")
        self.rec_idea.setText("")
        self.rec_alts.setText("—")

        # Si c'est au tour de l'utilisateur de jouer, on lui propose le coup d'ouverture
        if self.game.board.turn == user_color:
            self._refresh_recommendation()

    def update_engine_status(self) -> None:
        path = self.settings.get("stockfish_path", "")
        if self.engine.available and path:
            self.engine_chip.setText(f"Stockfish : prêt")
            self.engine_chip.setStyleSheet("background:#143324; border:1px solid #1F5A40; color:#7AE5B0; border-radius:999px; padding:4px 12px;")
            self.engine_status.setText(f"Détecté : {path}")
        elif path:
            self.engine_chip.setText("Stockfish : erreur")
            self.engine_chip.setStyleSheet("background:#33181A; border:1px solid #5A292C; color:#E58993; border-radius:999px; padding:4px 12px;")
            self.engine_status.setText(f"Chemin enregistré mais inutilisable : {path}")
        else:
            self.engine_chip.setText("Stockfish : non configuré")
            self.engine_chip.setStyleSheet("background:#332714; border:1px solid #5A4220; color:#E5C27A; border-radius:999px; padding:4px 12px;")
            self.engine_status.setText("Aucun moteur configuré : la théorie reste utilisable.")

    def _test_engine_clicked(self) -> None:
        path = self.settings.get("stockfish_path", "")
        ok, msg = test_engine(path)
        QMessageBox.information(self, "Test Stockfish", msg)
        if ok:
            self.engine.open(path)
        self.update_engine_status()

    # ----- User actions -----

    def _submit_move(self) -> None:
        text = self.move_input.text().strip()
        if not text:
            return
        move = self.game.parse_move(text)
        if move is None:
            self._update_status_chip("Coup illégal ou notation invalide", "err")
            return
        self.move_input.clear()
        self._apply_move(move)

    def _on_user_dropped_move(self, uci: str) -> None:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            return
        if move not in self.game.board.legal_moves:
            return
        self._apply_move(move)

    def _apply_move(self, move: chess.Move) -> None:
        if not self.game.play_move(move):
            self._update_status_chip("Coup refusé", "err")
            return
        self.board_widget.set_board(self.game.board)
        self.board_widget.set_last_move(move)
        self.board_widget.set_recommended_move(None)
        self._refresh_history()

        if self.game.is_game_over():
            self._update_status_chip(self.game.game_over_reason(), "warn")
            self.rec_move.setText("Fin")
            self.rec_source.setText("—")
            self.rec_idea.setText(self.game.game_over_reason())
            self.rec_alts.setText("—")
            return

        self._refresh_recommendation()

    def _refresh_recommendation(self) -> None:
        rec: Recommendation = self.game.recommend(
            depth=int(self.settings.get("engine_depth", 16)),
            movetime_ms=int(self.settings.get("engine_movetime_ms", 800)),
        )
        if rec.move_san:
            self.rec_move.setText(rec.move_san)
        else:
            self.rec_move.setText("—")

        if rec.source == "theory":
            self.rec_source.setText("Source : Base d'ouvertures")
            self.rec_source.setStyleSheet("background:#143324; border:1px solid #1F5A40; color:#7AE5B0; border-radius:999px; padding:4px 12px;")
            self.label_opening.setText(f"Ouverture : {rec.opening_name or '—'}")
            self.label_variation.setText(f"Variante : {rec.variation_name or '—'}")
        elif rec.source == "engine":
            extra = ""
            if rec.eval_pawns is not None:
                extra = f"  ·  éval {rec.eval_pawns:+.2f}"
            if rec.depth is not None:
                extra += f"  ·  profondeur {rec.depth}"
            self.rec_source.setText(f"Source : Stockfish{extra}")
            self.rec_source.setStyleSheet("background:#142133; border:1px solid #1F3A5A; color:#7AB6E5; border-radius:999px; padding:4px 12px;")
        else:
            self.rec_source.setText("Source : —")
            self.rec_source.setStyleSheet("background:#332714; border:1px solid #5A4220; color:#E5C27A; border-radius:999px; padding:4px 12px;")

        if self.settings.get("show_explanations", True) and rec.idea:
            self.rec_idea.setText(rec.idea)
        else:
            self.rec_idea.setText("")

        if rec.alternatives:
            self.rec_alts.setText(" · ".join(rec.alternatives))
        else:
            self.rec_alts.setText("—")

        # Statut
        kind = "ok" if rec.source == "theory" else ("info" if rec.source == "engine" else "warn")
        self._update_status_chip(rec.status, kind)

        # Surligner le coup recommandé sur l'échiquier
        if rec.move_uci:
            try:
                rec_move = chess.Move.from_uci(rec.move_uci)
                self.board_widget.set_recommended_move(rec_move)
            except ValueError:
                self.board_widget.set_recommended_move(None)
        else:
            self.board_widget.set_recommended_move(None)

    def _play_recommended(self) -> None:
        rec = self.game.last_recommendation
        if rec is None or not rec.move_uci:
            self._refresh_recommendation()
            rec = self.game.last_recommendation
        if rec is None or not rec.move_uci:
            self._update_status_chip("Aucun coup disponible.", "warn")
            return
        try:
            move = chess.Move.from_uci(rec.move_uci)
        except ValueError:
            return
        if move not in self.game.board.legal_moves:
            self._update_status_chip("Coup recommandé invalide.", "err")
            return
        self._apply_move(move)

    def _undo(self) -> None:
        if not self.game.undo():
            return
        self.board_widget.set_board(self.game.board)
        self.board_widget.set_last_move(None)
        self.board_widget.set_recommended_move(None)
        self._refresh_history()
        self._refresh_recommendation()

    def _refresh_history(self) -> None:
        lines: List[str] = []
        for i in range(0, len(self.game.history_san), 2):
            num = i // 2 + 1
            white = self.game.history_san[i]
            black = self.game.history_san[i + 1] if i + 1 < len(self.game.history_san) else ""
            lines.append(f"{num}. {white} {black}".rstrip())
        self.history_view.setPlainText("\n".join(lines))

    def _update_status_chip(self, text: str, kind: str) -> None:
        self.status_chip.setText(text)
        if kind == "ok":
            css = "background:#143324; border:1px solid #1F5A40; color:#7AE5B0;"
        elif kind == "err":
            css = "background:#33181A; border:1px solid #5A292C; color:#E58993;"
        elif kind == "warn":
            css = "background:#332714; border:1px solid #5A4220; color:#E5C27A;"
        else:
            css = "background:#142133; border:1px solid #1F3A5A; color:#7AB6E5;"
        self.status_chip.setStyleSheet(css + " border-radius:999px; padding:4px 12px;")

    def _export_pgn(self) -> None:
        if not self.game.history_san:
            QMessageBox.information(self, "Export PGN", "Aucun coup à exporter.")
            return
        target = self.settings.get("pgn_export_dir", "")
        target_dir = Path(target) if target else None
        path = self.game.export_pgn(
            target_dir,
            opening_name=self.game.preferred_opening,
        )
        if path is None:
            QMessageBox.warning(self, "Export PGN", "Impossible d'écrire le fichier PGN.")
        else:
            QMessageBox.information(self, "Export PGN", f"Partie exportée :\n{path}")


# -----------------------------------------------------------------------------
# Main window
# -----------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self, settings: Settings, book: OpeningBook, engine: EngineManager) -> None:
        super().__init__()
        self.settings = settings
        self.book = book
        self.engine = engine

        self.setWindowTitle(f"{__app_name__} v{__version__}")
        self.resize(1280, 820)
        self.setMinimumSize(1080, 720)

        self.stack = QStackedWidget()
        self.welcome = WelcomeScreen(book, settings)
        self.main_screen = MainScreen(book, engine, settings)
        self.stack.addWidget(self.welcome)
        self.stack.addWidget(self.main_screen)
        self.setCentralWidget(self.stack)

        self.welcome.start_requested.connect(self._start_game)
        self.main_screen.back_requested.connect(self._show_welcome)
        self.main_screen.settings_requested.connect(self._open_settings)
        self.main_screen.new_game_requested.connect(self._show_welcome)

        sb = QStatusBar()
        self.setStatusBar(sb)
        self.fairplay_label = QLabel(
            "Outil d'entraînement personnel — ne pas utiliser pendant une partie en ligne."
        )
        sb.addWidget(self.fairplay_label, 1)

        self.main_screen.update_engine_status()

    def _start_game(self, color: str, opening_name: str) -> None:
        self.main_screen.start_new_game(color, opening_name)
        self.stack.setCurrentWidget(self.main_screen)
        self.main_screen.update_engine_status()

    def _show_welcome(self) -> None:
        self.welcome._refresh_openings()
        self.stack.setCurrentWidget(self.welcome)

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.settings, self.engine, self)
        if dlg.exec() == QDialog.Accepted:
            self.main_screen.update_engine_status()


# -----------------------------------------------------------------------------
# App bootstrap
# -----------------------------------------------------------------------------

def build_app(argv: Optional[List[str]] = None) -> QApplication:
    app = QApplication.instance() or QApplication(argv or [])
    app.setStyleSheet(DARK_QSS)

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#0E1116"))
    palette.setColor(QPalette.Base, QColor("#11151D"))
    palette.setColor(QPalette.Text, QColor("#E8ECF1"))
    palette.setColor(QPalette.WindowText, QColor("#E8ECF1"))
    palette.setColor(QPalette.Highlight, QColor("#5469F4"))
    palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.Button, QColor("#1F2733"))
    palette.setColor(QPalette.ButtonText, QColor("#E8ECF1"))
    app.setPalette(palette)

    return app


def run() -> int:
    settings = Settings()

    # Détection Stockfish (silencieuse)
    saved = settings.get("stockfish_path", "")
    detected = detect_stockfish(saved)
    if detected and detected != saved:
        settings.set("stockfish_path", detected)

    book = OpeningBook()
    engine = EngineManager(settings.get("stockfish_path", "") or None)
    if settings.get("stockfish_path", ""):
        engine.open()

    app = build_app([])
    window = MainWindow(settings, book, engine)
    window.show()

    code = app.exec()
    engine.close()
    return int(code)
