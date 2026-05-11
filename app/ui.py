"""Interface utilisateur PySide6 : welcome, écran principal, paramètres."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import chess
from PySide6.QtCore import Qt, QTimer, Signal
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
from .training_bot import (
    BOT_MODE_FROM_LABEL,
    BOT_MODE_LABELS,
    BotMode,
    MoveAssessment,
    MoveQuality,
    TrainingBot,
)


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
    """Écran d'accueil : choix du mode, de la couleur, de l'ouverture."""

    # params : {mode, color, opening, variation, bot_mode}
    start_requested = Signal(dict)

    def __init__(self, book: OpeningBook, settings: Settings, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.book = book
        self.settings = settings
        self.setObjectName("root")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(48, 32, 48, 32)
        outer.setSpacing(16)

        title = QLabel(__app_name__)
        title.setObjectName("h1")
        subtitle = QLabel("Travaillez vos ouvertures, affrontez le bot théorique, analysez après partie.")
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

        # ---- Carte gauche : configuration ----
        config_card = QFrame()
        config_card.setObjectName("card")
        config_layout = QVBoxLayout(config_card)
        config_layout.setContentsMargins(24, 22, 24, 22)
        config_layout.setSpacing(12)

        config_layout.addWidget(self._h2("Nouvelle session"))

        # Mode
        config_layout.addWidget(self._muted("Mode :"))
        mode_row = QVBoxLayout()
        self.radio_mode_analyse = QRadioButton("Mode Analyse — j'entre les coups, le programme recommande")
        self.radio_mode_bot = QRadioButton("Mode Bot d'entraînement — je joue contre un bot qui suit la théorie")
        if settings.get("last_mode", "analyse") == "bot":
            self.radio_mode_bot.setChecked(True)
        else:
            self.radio_mode_analyse.setChecked(True)
        mode_row.addWidget(self.radio_mode_analyse)
        mode_row.addWidget(self.radio_mode_bot)
        config_layout.addLayout(mode_row)

        config_layout.addWidget(_divider())

        # Couleur
        config_layout.addWidget(self._muted("Vous jouez :"))
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
        config_layout.addWidget(self._muted("Ouverture à travailler :"))
        self.combo_opening = QComboBox()
        config_layout.addWidget(self.combo_opening)

        # Options spécifiques au bot (variante + comportement)
        self.bot_box = QWidget()
        bot_layout = QVBoxLayout(self.bot_box)
        bot_layout.setContentsMargins(0, 0, 0, 0)
        bot_layout.setSpacing(8)
        bot_layout.addWidget(self._muted("Variante (mode bot) :"))
        self.combo_variation = QComboBox()
        bot_layout.addWidget(self.combo_variation)
        bot_layout.addWidget(self._muted("Comportement du bot :"))
        self.combo_bot_mode = QComboBox()
        for label in BOT_MODE_LABELS.values():
            self.combo_bot_mode.addItem(label)
        self.combo_bot_mode.setCurrentText(BOT_MODE_LABELS[BotMode.MIXED])
        bot_layout.addWidget(self.combo_bot_mode)
        config_layout.addWidget(self.bot_box)

        self.idea_box = QLabel()
        self.idea_box.setWordWrap(True)
        self.idea_box.setObjectName("muted")
        self.idea_box.setMinimumHeight(48)
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

        # ---- Carte droite : visuel ----
        visual_card = QFrame()
        visual_card.setObjectName("card")
        visual_layout = QVBoxLayout(visual_card)
        visual_layout.setContentsMargins(20, 20, 20, 20)
        self.preview_board = BoardWidget()
        self.preview_board.set_input_enabled(False)
        self.preview_board.setMinimumSize(360, 360)
        visual_layout.addWidget(self.preview_board, 1)
        tagline = QLabel(
            "Bibliothèque d'ouvertures riche, bot qui joue de vraies variantes théoriques, "
            "Stockfish en filet de sécurité."
        )
        tagline.setObjectName("muted")
        tagline.setWordWrap(True)
        tagline.setAlignment(Qt.AlignCenter)
        visual_layout.addWidget(tagline)
        lib_row = QHBoxLayout()
        lib_row.addStretch()
        self.btn_library = QPushButton("📚 Voir toutes les ouvertures")
        self.btn_library.clicked.connect(self._open_library)
        lib_row.addWidget(self.btn_library)
        lib_row.addStretch()
        visual_layout.addLayout(lib_row)
        body.addWidget(visual_card, 1)

        # Wiring
        self.radio_white.toggled.connect(self._refresh_openings)
        self.radio_mode_bot.toggled.connect(self._refresh_mode)
        self.combo_opening.currentIndexChanged.connect(self._refresh_opening_dependent)
        self.btn_start.clicked.connect(self._on_start)

        self._refresh_openings()
        self._refresh_mode()

    # -- small builders --
    @staticmethod
    def _h2(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("h2")
        return label

    @staticmethod
    def _muted(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("muted")
        return label

    def _open_library(self) -> None:
        OpeningsDialog(self.book, self).exec()

    # -- state --
    def _is_bot(self) -> bool:
        return self.radio_mode_bot.isChecked()

    def _refresh_mode(self) -> None:
        bot = self._is_bot()
        self.bot_box.setVisible(bot)
        self.btn_start.setText("Commencer contre le bot" if bot else "Commencer")
        # en mode bot une ouverture est obligatoire : on retire "Aucune"
        self._refresh_openings()

    def _refresh_openings(self) -> None:
        color = "white" if self.radio_white.isChecked() else "black"
        prev = self.combo_opening.currentData()
        self.combo_opening.blockSignals(True)
        self.combo_opening.clear()
        if not self._is_bot():
            self.combo_opening.addItem("— Aucune (analyse libre) —", userData=None)
        for op in self.book.list_for_color(color):
            self.combo_opening.addItem(op.name, userData=op.name)
        # restaurer la sélection
        target = prev or self.settings.get("last_opening", "")
        if target:
            idx = self.combo_opening.findData(target)
            if idx >= 0:
                self.combo_opening.setCurrentIndex(idx)
        self.combo_opening.blockSignals(False)
        self._refresh_opening_dependent()

    def _refresh_opening_dependent(self) -> None:
        name = self.combo_opening.currentData()
        # idée
        if not name:
            self.idea_box.setText("Mode libre : suivez la théorie de toute ouverture détectée par transposition.")
        else:
            op = next((o for o in self.book.openings if o.name == name), None)
            self.idea_box.setText(f"Idée — {op.idea}" if op else "")
        # variantes (mode bot)
        self.combo_variation.blockSignals(True)
        self.combo_variation.clear()
        self.combo_variation.addItem("Au hasard (le bot choisit)", userData=None)
        if name:
            op = next((o for o in self.book.openings if o.name == name), None)
            if op:
                for v in op.variations:
                    self.combo_variation.addItem(v.name, userData=v.name)
        self.combo_variation.blockSignals(False)

    def _on_start(self) -> None:
        color = "white" if self.radio_white.isChecked() else "black"
        opening = self.combo_opening.currentData()
        mode = "bot" if self._is_bot() else "analyse"
        if mode == "bot" and not opening:
            # fallback : prendre la première ouverture de la couleur
            ops = self.book.list_for_color(color)
            opening = ops[0].name if ops else None
        self.settings.set("last_color", color)
        self.settings.set("last_opening", opening or "")
        self.settings.set("last_mode", mode)
        self.start_requested.emit(
            {
                "mode": mode,
                "color": color,
                "opening": opening or "",
                "variation": self.combo_variation.currentData() if mode == "bot" else None,
                "bot_mode": BOT_MODE_FROM_LABEL.get(self.combo_bot_mode.currentText(), BotMode.MIXED),
            }
        )


# -----------------------------------------------------------------------------
# Settings dialog
# -----------------------------------------------------------------------------

class OpeningsDialog(QDialog):
    """Affiche la bibliothèque d'ouvertures, regroupée par famille."""

    def __init__(self, book: OpeningBook, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Bibliothèque d'ouvertures")
        self.setModal(True)
        self.resize(760, 620)

        from .opening_book import FAMILY_LABELS  # local import to avoid cycle at top

        n_op = len(book.openings)
        n_var = sum(len(o.variations) for o in book.openings)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(10)
        title = QLabel("Bibliothèque d'ouvertures")
        title.setObjectName("h2")
        layout.addWidget(title)
        sub = QLabel(f"{n_op} ouvertures · {n_var} variantes — éditable dans openings.json")
        sub.setObjectName("muted")
        layout.addWidget(sub)
        layout.addWidget(_divider())

        view = QPlainTextEdit()
        view.setReadOnly(True)
        lines: List[str] = []
        # ordre d'affichage des familles
        order = [
            "open_games", "semi_open", "closed_games",
            "indian", "flexible_d4", "english", "reti", "flank", "other",
        ]
        by_family: dict = {}
        for op in book.openings:
            by_family.setdefault(op.family, []).append(op)
        for fam in order:
            ops = by_family.get(fam)
            if not ops:
                continue
            lines.append(f"━━ {FAMILY_LABELS.get(fam, fam)} ━━")
            for op in ops:
                color = "Blancs" if op.color == "white" else "Noirs"
                lines.append(f"  • {op.name}  [{color}, {op.eco}, {len(op.variations)} variantes]")
                for v in op.variations:
                    lines.append(f"      – {v.name}")
            lines.append("")
        view.setPlainText("\n".join(lines))
        layout.addWidget(view, 1)

        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.button(QDialogButtonBox.Close).setText("Fermer")
        bb.rejected.connect(self.reject)
        bb.accepted.connect(self.accept)
        layout.addWidget(bb)


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
        self.label_opening = QLabel("Ouverture choisie : —")
        self.label_variation = QLabel("Variante : —")
        self.label_family = QLabel("Famille : —")
        self.label_transpo = QLabel("")
        self.label_transpo.setStyleSheet("color: #E5C27A; font-style: italic;")
        for w in (
            self.label_color,
            self.label_opening,
            self.label_variation,
            self.label_family,
            self.label_transpo,
        ):
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
        self.label_opening.setText(f"Ouverture choisie : {opening_name or 'Libre'}")
        self.label_variation.setText("Variante : —")
        self.label_family.setText("Famille : —")
        self.label_transpo.setText("")
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
            label = "Source : Transposition" if rec.is_transposition else "Source : Base d'ouvertures"
            self.rec_source.setText(label)
            self.rec_source.setStyleSheet("background:#143324; border:1px solid #1F5A40; color:#7AE5B0; border-radius:999px; padding:4px 12px;")
            self.label_variation.setText(f"Variante : {rec.variation_name or '—'}")
            if rec.is_transposition and rec.original_opening:
                self.label_transpo.setText(
                    f"⇄ Transposition : {rec.original_opening} → {rec.opening_name}"
                )
            else:
                self.label_transpo.setText("")
        elif rec.source == "engine":
            extra = ""
            if rec.eval_pawns is not None:
                extra = f"  ·  éval {rec.eval_pawns:+.2f}"
            if rec.depth is not None:
                extra += f"  ·  profondeur {rec.depth}"
            self.rec_source.setText(f"Source : Stockfish{extra}")
            self.rec_source.setStyleSheet("background:#142133; border:1px solid #1F3A5A; color:#7AB6E5; border-radius:999px; padding:4px 12px;")
            self.label_variation.setText("Variante : hors livre")
            self.label_transpo.setText("")
        else:
            self.rec_source.setText("Source : —")
            self.rec_source.setStyleSheet("background:#332714; border:1px solid #5A4220; color:#E5C27A; border-radius:999px; padding:4px 12px;")
            self.label_transpo.setText("")

        # Famille d'ouverture
        if rec.family_label:
            self.label_family.setText(f"Famille : {rec.family_label}")
        else:
            self.label_family.setText("Famille : —")

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
# Bot training screen
# -----------------------------------------------------------------------------

_QUALITY_STYLE = {
    MoveQuality.PERFECT: "ok",
    MoveQuality.ALTERNATIVE: "ok",
    MoveQuality.TRANSPOSITION: "info",
    MoveQuality.IMPRECISE: "warn",
    MoveQuality.OUT_OF_THEORY: "warn",
    MoveQuality.ILLEGAL: "err",
}

_QUALITY_TITLE = {
    MoveQuality.PERFECT: "Coup parfait",
    MoveQuality.ALTERNATIVE: "Coup théorique alternatif",
    MoveQuality.TRANSPOSITION: "Transposition",
    MoveQuality.IMPRECISE: "Coup imprécis",
    MoveQuality.OUT_OF_THEORY: "Hors théorie",
    MoveQuality.ILLEGAL: "Coup illégal",
}


def _chip_style(kind: str) -> str:
    if kind == "ok":
        return "background:#143324; border:1px solid #1F5A40; color:#7AE5B0; border-radius:999px; padding:4px 12px;"
    if kind == "err":
        return "background:#33181A; border:1px solid #5A292C; color:#E58993; border-radius:999px; padding:4px 12px;"
    if kind == "warn":
        return "background:#332714; border:1px solid #5A4220; color:#E5C27A; border-radius:999px; padding:4px 12px;"
    return "background:#142133; border:1px solid #1F3A5A; color:#7AB6E5; border-radius:999px; padding:4px 12px;"


class BotTrainingScreen(QWidget):
    """Mode bot : je joue contre un bot qui suit la théorie de l'ouverture choisie."""

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
        self.bot: Optional[TrainingBot] = None
        self._user_color: chess.Color = chess.WHITE
        self._opening_name: str = ""
        self._variation_name: Optional[str] = None
        self._bot_mode: BotMode = BotMode.MIXED
        self._pending_move: Optional[chess.Move] = None  # coup utilisateur en attente de confirmation

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        # Header
        header = QHBoxLayout()
        title = QLabel(f"{__app_name__} — Bot d'entraînement")
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

        body = QHBoxLayout()
        body.setSpacing(14)
        root.addLayout(body, 1)

        # ---- Gauche : infos ----
        left_card = QFrame()
        left_card.setObjectName("card")
        left = QVBoxLayout(left_card)
        left.setContentsMargins(18, 18, 18, 18)
        left.setSpacing(10)
        left.addWidget(self._h2("Session bot"))
        self.label_color = QLabel("Couleur : —")
        self.label_opening = QLabel("Ouverture : —")
        self.label_variation = QLabel("Variante visée : —")
        self.label_bot_mode = QLabel("Comportement : —")
        self.label_bot_following = QLabel("")
        self.label_bot_following.setStyleSheet("color:#7AB6E5; font-style:italic;")
        for w in (
            self.label_color, self.label_opening, self.label_variation,
            self.label_bot_mode, self.label_bot_following,
        ):
            w.setWordWrap(True)
            left.addWidget(w)
        left.addWidget(_divider())
        left.addWidget(QLabel("Tour"))
        self.turn_chip = _chip("—", "info")
        left.addWidget(self.turn_chip, 0, Qt.AlignLeft)
        left.addWidget(_divider())
        left.addWidget(QLabel("Stockfish"))
        self.engine_status = QLabel("…")
        self.engine_status.setObjectName("muted")
        self.engine_status.setWordWrap(True)
        left.addWidget(self.engine_status)
        left.addStretch()
        body.addWidget(left_card, 0)

        # ---- Centre : échiquier ----
        center_card = QFrame()
        center_card.setObjectName("card")
        center = QVBoxLayout(center_card)
        center.setContentsMargins(18, 18, 18, 18)
        center.setSpacing(10)
        self.board_widget = BoardWidget()
        self.board_widget.move_played.connect(self._on_user_dropped_move)
        self.board_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        center.addWidget(self.board_widget, 1)

        input_row = QHBoxLayout()
        self.move_input = QLineEdit()
        self.move_input.setPlaceholderText("Ton coup (e6, Nf3, e2e4, O-O…)")
        self.move_input.returnPressed.connect(self._submit_typed_move)
        btn_validate = QPushButton("Jouer")
        btn_validate.clicked.connect(self._submit_typed_move)
        self.btn_show_best = QPushButton("Voir le bon coup")
        self.btn_show_best.clicked.connect(self._show_best_move)
        input_row.addWidget(self.move_input, 1)
        input_row.addWidget(btn_validate)
        input_row.addWidget(self.btn_show_best)
        center.addLayout(input_row)

        action_row = QHBoxLayout()
        self.btn_undo = QPushButton("Revenir en arrière")
        self.btn_undo.clicked.connect(self._undo)
        self.btn_replay = QPushButton("Rejouer la variante")
        self.btn_replay.clicked.connect(self._replay)
        self.btn_new = QPushButton("Nouvelle session")
        self.btn_new.clicked.connect(self.new_game_requested.emit)
        self.btn_flip = QPushButton("Retourner l'échiquier")
        self.btn_flip.clicked.connect(self.board_widget.flip)
        self.btn_pgn = QPushButton("Exporter PGN")
        self.btn_pgn.clicked.connect(self._export_pgn)
        for b in (self.btn_undo, self.btn_replay, self.btn_new, self.btn_flip, self.btn_pgn):
            action_row.addWidget(b)
        action_row.addStretch()
        center.addLayout(action_row)
        body.addWidget(center_card, 1)

        # ---- Droite : feedback + historique ----
        right_card = QFrame()
        right_card.setObjectName("card")
        right = QVBoxLayout(right_card)
        right.setContentsMargins(18, 18, 18, 18)
        right.setSpacing(10)
        right.addWidget(self._h2("Correction"))
        self.fb_badge = _chip("En attente", "info")
        right.addWidget(self.fb_badge, 0, Qt.AlignLeft)
        self.fb_message = QLabel("Choisis ton coup. Le bot répondra avec la théorie de l'ouverture.")
        self.fb_message.setWordWrap(True)
        right.addWidget(self.fb_message)
        self.fb_detail = QLabel("")
        self.fb_detail.setObjectName("muted")
        self.fb_detail.setWordWrap(True)
        right.addWidget(self.fb_detail)

        # Ligne de boutons "après coup imprécis"
        self.confirm_row = QWidget()
        confirm_layout = QHBoxLayout(self.confirm_row)
        confirm_layout.setContentsMargins(0, 0, 0, 0)
        self.btn_continue = QPushButton("Continuer quand même")
        self.btn_continue.setObjectName("primary")
        self.btn_continue.clicked.connect(self._confirm_pending_move)
        self.btn_take_back = QPushButton("Annuler ce coup")
        self.btn_take_back.clicked.connect(self._cancel_pending_move)
        confirm_layout.addWidget(self.btn_continue)
        confirm_layout.addWidget(self.btn_take_back)
        confirm_layout.addStretch()
        self.confirm_row.setVisible(False)
        right.addWidget(self.confirm_row)

        right.addWidget(_divider())
        right.addWidget(QLabel("Réponse du bot"))
        self.bot_msg = QLabel("—")
        self.bot_msg.setObjectName("muted")
        self.bot_msg.setWordWrap(True)
        right.addWidget(self.bot_msg)

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

    # -- builders --
    @staticmethod
    def _h2(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("h2")
        return label

    # ---------- lifecycle ----------

    def start_session(
        self,
        color: str,
        opening_name: str,
        variation_name: Optional[str],
        bot_mode: BotMode,
    ) -> None:
        self._user_color = chess.WHITE if color == "white" else chess.BLACK
        self._opening_name = opening_name
        self._variation_name = variation_name
        self._bot_mode = bot_mode
        self.game.new_game(self._user_color, opening_name or None)
        self.bot = TrainingBot(
            self.book, self.engine, self._user_color, opening_name,
            variation_name=variation_name, mode=bot_mode,
        )
        self._pending_move = None
        self.board_widget.set_board(self.game.board)
        self.board_widget.set_orientation(self._user_color == chess.WHITE)
        self.board_widget.set_last_move(None)
        self.board_widget.set_recommended_move(None)

        self.label_color.setText(f"Couleur : {'Blancs' if self._user_color == chess.WHITE else 'Noirs'}")
        self.label_opening.setText(f"Ouverture : {opening_name or '—'}")
        self.label_variation.setText(f"Variante visée : {variation_name or 'au hasard'}")
        self.label_bot_mode.setText(f"Comportement : {BOT_MODE_LABELS.get(bot_mode, '—')}")
        self.label_bot_following.setText("")
        self.history_view.setPlainText("")
        self.move_input.clear()
        self.confirm_row.setVisible(False)
        self._set_feedback(MoveQuality.PERFECT, "Session prête.", "Joue ton coup quand c'est ton tour.", reset=True)
        self.bot_msg.setText("—")
        self.update_engine_status()

        # Si le bot joue les Blancs, il commence
        if self.game.board.turn != self._user_color:
            self._set_turn("Le bot réfléchit…", "info")
            self._lock_board(True)
            QTimer.singleShot(450, self._bot_play)
        else:
            self._set_turn("À toi de jouer", "ok")
            self._lock_board(False)

    def update_engine_status(self) -> None:
        path = self.settings.get("stockfish_path", "")
        if self.engine.available and path:
            self.engine_chip.setText("Stockfish : prêt")
            self.engine_chip.setStyleSheet(_chip_style("ok"))
            self.engine_status.setText("Détecté — utilisé seulement après la théorie.")
        elif path:
            self.engine_chip.setText("Stockfish : erreur")
            self.engine_chip.setStyleSheet(_chip_style("err"))
            self.engine_status.setText(f"Chemin inutilisable : {path}")
        else:
            self.engine_chip.setText("Stockfish : non configuré")
            self.engine_chip.setStyleSheet(_chip_style("warn"))
            self.engine_status.setText("Non configuré : la théorie reste pleinement utilisable.")

    # ---------- helpers UI ----------

    def _set_turn(self, text: str, kind: str) -> None:
        self.turn_chip.setText(text)
        self.turn_chip.setStyleSheet(_chip_style(kind))

    def _set_feedback(self, quality: MoveQuality, message: str, detail: str = "", reset: bool = False) -> None:
        kind = _QUALITY_STYLE.get(quality, "info")
        title = "Correction" if reset else _QUALITY_TITLE.get(quality, "Correction")
        self.fb_badge.setText(title)
        self.fb_badge.setStyleSheet(_chip_style(kind))
        self.fb_message.setText(message)
        self.fb_detail.setText(detail)

    def _lock_board(self, locked: bool) -> None:
        self.board_widget.set_input_enabled(not locked)
        self.move_input.setEnabled(not locked)
        self.btn_show_best.setEnabled(not locked)

    def _refresh_history(self) -> None:
        lines: List[str] = []
        for i in range(0, len(self.game.history_san), 2):
            num = i // 2 + 1
            white = self.game.history_san[i]
            black = self.game.history_san[i + 1] if i + 1 < len(self.game.history_san) else ""
            lines.append(f"{num}. {white} {black}".rstrip())
        self.history_view.setPlainText("\n".join(lines))

    # ---------- user move ----------

    def _submit_typed_move(self) -> None:
        text = self.move_input.text().strip()
        if not text:
            return
        move = self.game.parse_move(text)
        if move is None:
            self._set_feedback(MoveQuality.ILLEGAL, "Coup illégal ou notation invalide.", "Exemples : e6, Nf3, O-O, e2e4.")
            return
        self.move_input.clear()
        self._handle_user_move(move)

    def _on_user_dropped_move(self, uci: str) -> None:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            return
        if move not in self.game.board.legal_moves:
            return
        self._handle_user_move(move)

    def _handle_user_move(self, move: chess.Move) -> None:
        if self.bot is None or self.game.board.turn != self._user_color:
            return
        assessment = self.bot.assess_user_move(self.game.board, list(self.game.history_san), move)
        if assessment.quality == MoveQuality.ILLEGAL:
            self._set_feedback(MoveQuality.ILLEGAL, assessment.message)
            return

        detail = self._assessment_detail(assessment)

        if assessment.is_good:
            # bon coup : on joue, et le bot répond automatiquement
            self.game.play_move(move)
            self.board_widget.set_board(self.game.board)
            self.board_widget.set_last_move(move)
            self.board_widget.set_recommended_move(None)
            self._refresh_history()
            self._set_feedback(assessment.quality, assessment.message, detail)
            self.confirm_row.setVisible(False)
            if self.game.is_game_over():
                self._on_game_over()
                return
            self._set_turn("Le bot réfléchit…", "info")
            self._lock_board(True)
            QTimer.singleShot(450, self._bot_play)
        else:
            # coup imprécis / transposition / hors théorie : on demande confirmation
            self._pending_move = move
            self._set_feedback(assessment.quality, assessment.message, detail)
            self.confirm_row.setVisible(True)
            self._set_turn("Coup à confirmer", "warn")
            # surligner le bon coup sur l'échiquier si connu
            if assessment.expected_san:
                try:
                    best = self.game.board.parse_san(assessment.expected_san)
                    self.board_widget.set_recommended_move(best)
                except Exception:
                    pass

    def _assessment_detail(self, a: MoveAssessment) -> str:
        bits = []
        if a.user_san:
            bits.append(f"Ton coup : {a.user_san}")
        if a.expected_san:
            bits.append(f"Coup principal : {a.expected_san}")
        if a.alternatives:
            bits.append("Alternatives : " + ", ".join(a.alternatives[:4]))
        if a.opening_name:
            bits.append(f"Ouverture : {a.opening_name}")
        if a.variation_name:
            bits.append(f"Variante : {a.variation_name}")
        if a.transposed_to:
            bits.append(f"Transpose vers : {a.transposed_to}")
        if a.idea and self.settings.get("show_explanations", True):
            bits.append(f"Idée : {a.idea}")
        return "\n".join(bits)

    def _confirm_pending_move(self) -> None:
        if self._pending_move is None:
            return
        move = self._pending_move
        self._pending_move = None
        self.confirm_row.setVisible(False)
        self.board_widget.set_recommended_move(None)
        self.game.play_move(move)
        self.board_widget.set_board(self.game.board)
        self.board_widget.set_last_move(move)
        self._refresh_history()
        if self.game.is_game_over():
            self._on_game_over()
            return
        self._set_turn("Le bot réfléchit…", "info")
        self._lock_board(True)
        QTimer.singleShot(450, self._bot_play)

    def _cancel_pending_move(self) -> None:
        self._pending_move = None
        self.confirm_row.setVisible(False)
        self.board_widget.set_recommended_move(None)
        self._set_feedback(MoveQuality.PERFECT, "Coup annulé. Rejoue un autre coup.", "", reset=True)
        self._set_turn("À toi de jouer", "ok")

    # ---------- bot move ----------

    def _bot_play(self) -> None:
        if self.bot is None or self.game.board.turn == self._user_color:
            return
        if self.game.is_game_over():
            self._on_game_over()
            return
        reply = self.bot.choose_bot_move(
            self.game.board, list(self.game.history_san),
            depth=int(self.settings.get("engine_depth", 14)),
            movetime_ms=int(self.settings.get("engine_movetime_ms", 600)),
        )
        if reply.move is None:
            self.bot_msg.setText(reply.message or "Le bot n'a pas de coup à jouer.")
            self._set_turn("Théorie terminée", "warn")
            self._lock_board(False)
            return
        self.game.play_move(reply.move)
        self.board_widget.set_board(self.game.board)
        self.board_widget.set_last_move(reply.move)
        self._refresh_history()

        # message du bot
        src = "Théorie" if reply.source == "theory" else ("Stockfish" if reply.source == "engine" else "—")
        parts = [f"{reply.move_san} ({src})"]
        if reply.opening_name and reply.source == "theory":
            parts.append(reply.opening_name)
        if reply.variation_name and reply.source == "theory":
            parts.append(reply.variation_name)
        if reply.eval_pawns is not None:
            parts.append(f"éval {reply.eval_pawns:+.2f}")
        self.bot_msg.setText(" · ".join(parts) + (f"\n{reply.message}" if reply.message else ""))
        if reply.variation_name and reply.source == "theory":
            self.label_bot_following.setText(f"Le bot suit : {reply.variation_name}")

        if self.game.is_game_over():
            self._on_game_over()
            return
        self._set_turn("À toi de jouer", "ok")
        self._lock_board(False)

    # ---------- misc actions ----------

    def _show_best_move(self) -> None:
        if self.bot is None or self.game.board.turn != self._user_color:
            return
        san = self.bot.best_theory_move(self.game.board, list(self.game.history_san))
        if not san:
            self._set_feedback(
                MoveQuality.OUT_OF_THEORY,
                "Plus de coup théorique connu ici.",
                "Tu peux jouer librement (Stockfish prendra le relais côté bot) ou rejouer la variante.",
            )
            return
        try:
            move = self.game.board.parse_san(san)
            self.board_widget.set_recommended_move(move)
        except Exception:
            pass
        self._set_feedback(MoveQuality.PERFECT, f"Le coup théorique principal ici est : {san}.", "", reset=True)

    def _undo(self) -> None:
        # annule le dernier coup du bot + le dernier coup utilisateur (1 paire)
        self._pending_move = None
        self.confirm_row.setVisible(False)
        undone = False
        # défaire jusqu'à ce que ce soit de nouveau au tour de l'utilisateur (max 2)
        for _ in range(2):
            if not self.game.history_san:
                break
            self.game.undo()
            undone = True
            if self.game.board.turn == self._user_color:
                break
        if not undone:
            return
        self.board_widget.set_board(self.game.board)
        self.board_widget.set_last_move(self.game.board.peek() if self.game.board.move_stack else None)
        self.board_widget.set_recommended_move(None)
        self._refresh_history()
        self._set_feedback(MoveQuality.PERFECT, "Retour en arrière.", "", reset=True)
        if self.game.board.turn == self._user_color:
            self._set_turn("À toi de jouer", "ok")
            self._lock_board(False)
        else:
            self._set_turn("Le bot réfléchit…", "info")
            self._lock_board(True)
            QTimer.singleShot(450, self._bot_play)

    def _replay(self) -> None:
        self.start_session(
            "white" if self._user_color == chess.WHITE else "black",
            self._opening_name, self._variation_name, self._bot_mode,
        )

    def _on_game_over(self) -> None:
        reason = self.game.game_over_reason() or "Partie terminée."
        self._set_turn(reason, "warn")
        self._set_feedback(MoveQuality.OUT_OF_THEORY, reason, "Tu peux rejouer la variante ou commencer une nouvelle session.", reset=True)
        self._lock_board(False)

    def _export_pgn(self) -> None:
        if not self.game.history_san:
            QMessageBox.information(self, "Export PGN", "Aucun coup à exporter.")
            return
        target = self.settings.get("pgn_export_dir", "")
        path = self.game.export_pgn(Path(target) if target else None, opening_name=self._opening_name)
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
        self.bot_screen = BotTrainingScreen(book, engine, settings)
        self.stack.addWidget(self.welcome)
        self.stack.addWidget(self.main_screen)
        self.stack.addWidget(self.bot_screen)
        self.setCentralWidget(self.stack)

        self.welcome.start_requested.connect(self._start_session)
        self.main_screen.back_requested.connect(self._show_welcome)
        self.main_screen.settings_requested.connect(self._open_settings)
        self.main_screen.new_game_requested.connect(self._show_welcome)
        self.bot_screen.back_requested.connect(self._show_welcome)
        self.bot_screen.settings_requested.connect(self._open_settings)
        self.bot_screen.new_game_requested.connect(self._show_welcome)

        sb = QStatusBar()
        self.setStatusBar(sb)
        self.fairplay_label = QLabel(
            "Outil d'entraînement personnel — ne pas utiliser pendant une partie en ligne."
        )
        sb.addWidget(self.fairplay_label, 1)

        self.main_screen.update_engine_status()
        self.bot_screen.update_engine_status()

    def _start_session(self, params: dict) -> None:
        mode = params.get("mode", "analyse")
        color = params.get("color", "white")
        opening = params.get("opening", "")
        if mode == "bot":
            self.bot_screen.start_session(
                color, opening, params.get("variation"),
                params.get("bot_mode", BotMode.MIXED),
            )
            self.bot_screen.update_engine_status()
            self.stack.setCurrentWidget(self.bot_screen)
        else:
            self.main_screen.start_new_game(color, opening)
            self.main_screen.update_engine_status()
            self.stack.setCurrentWidget(self.main_screen)

    def _show_welcome(self) -> None:
        self.welcome._refresh_openings()
        self.stack.setCurrentWidget(self.welcome)

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.settings, self.engine, self)
        if dlg.exec() == QDialog.Accepted:
            self.main_screen.update_engine_status()
            self.bot_screen.update_engine_status()


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
