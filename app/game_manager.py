"""Pilote la partie : board, historique, recommandations théorie/Stockfish."""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import chess
import chess.pgn

from .engine import EngineManager
from .opening_book import (
    FAMILY_LABELS,
    OpeningBook,
    TheoryHit,
    family_for_first_moves,
)


@dataclass
class Recommendation:
    move_san: Optional[str]
    move_uci: Optional[str]
    source: str  # "theory" | "engine" | "none"
    status: str
    opening_name: Optional[str] = None
    variation_name: Optional[str] = None
    idea: Optional[str] = None
    alternatives: Optional[List[str]] = None
    eval_pawns: Optional[float] = None
    depth: Optional[int] = None
    multi_variations: bool = False
    is_transposition: bool = False
    original_opening: Optional[str] = None
    family_label: Optional[str] = None


class GameManager:
    """Encapsule la logique d'une partie d'analyse."""

    def __init__(self, book: OpeningBook, engine: EngineManager) -> None:
        self.book = book
        self.engine = engine
        self.board: chess.Board = chess.Board()
        self.user_color: chess.Color = chess.WHITE
        self.preferred_opening: Optional[str] = None
        self.history_san: List[str] = []
        self.history_boards: List[str] = [self.board.fen()]
        self.last_recommendation: Optional[Recommendation] = None

    # ----- Setup -----

    def new_game(self, user_color: chess.Color, preferred_opening: Optional[str]) -> None:
        self.board = chess.Board()
        self.user_color = user_color
        self.preferred_opening = preferred_opening
        self.history_san = []
        self.history_boards = [self.board.fen()]
        self.last_recommendation = None

    # ----- Move input -----

    def parse_move(self, text: str) -> Optional[chess.Move]:
        """Accepte SAN ou UCI. Retourne un Move légal ou None."""
        text = (text or "").strip()
        if not text:
            return None
        # Essayer SAN
        try:
            return self.board.parse_san(text)
        except (ValueError, chess.InvalidMoveError, chess.IllegalMoveError, chess.AmbiguousMoveError):
            pass
        # Essayer UCI
        try:
            move = chess.Move.from_uci(text.lower())
            if move in self.board.legal_moves:
                return move
        except (ValueError, chess.InvalidMoveError):
            pass
        return None

    def play_move(self, move: chess.Move) -> bool:
        if move not in self.board.legal_moves:
            return False
        san = self.board.san(move)
        self.board.push(move)
        self.history_san.append(san)
        self.history_boards.append(self.board.fen())
        return True

    def undo(self) -> bool:
        if len(self.history_san) == 0:
            return False
        self.board.pop()
        self.history_san.pop()
        self.history_boards.pop()
        self.last_recommendation = None
        return True

    # ----- Status -----

    def is_game_over(self) -> bool:
        return self.board.is_game_over(claim_draw=True)

    def game_over_reason(self) -> str:
        if self.board.is_checkmate():
            winner = "Blancs" if self.board.turn == chess.BLACK else "Noirs"
            return f"Échec et mat. Victoire des {winner}."
        if self.board.is_stalemate():
            return "Pat. Partie nulle."
        if self.board.is_insufficient_material():
            return "Matériel insuffisant. Nulle."
        if self.board.can_claim_threefold_repetition():
            return "Triple répétition. Nulle."
        if self.board.can_claim_fifty_moves():
            return "Règle des 50 coups. Nulle."
        return ""

    # ----- Recommendation -----

    def recommend(self, depth: int = 16, movetime_ms: int = 800) -> Recommendation:
        if self.is_game_over():
            rec = Recommendation(
                move_san=None,
                move_uci=None,
                source="none",
                status=self.game_over_reason() or "Partie terminée.",
            )
            self.last_recommendation = rec
            return rec

        # ---------- TIER 1 : recherche par position FEN dans toute la base ----------
        hits = self.book.find_for_position(
            self.board, self.user_color, self.preferred_opening
        )

        playable_hits = [h for h in hits if h.recommended_san]
        if playable_hits:
            best = playable_hits[0]
            multi = len({h.variation.name for h in playable_hits}) > 1

            try:
                move = self.board.parse_san(best.recommended_san)
                uci = move.uci()
            except Exception:
                uci = None

            total = len(best.variation.moves_san)
            is_transpo = bool(
                self.preferred_opening
                and self.preferred_opening != best.opening.name
            )

            if is_transpo:
                status = f"Transposition détectée · {best.opening.name}"
            else:
                status = f"Dans la théorie · coup {best.move_index + 1}/{total}"
            if multi:
                status += " · plusieurs variantes possibles"

            alternatives: List[str] = []
            seen = set()
            for h in playable_hits[:5]:
                if (
                    h.recommended_san
                    and h.recommended_san not in seen
                    and h.recommended_san != best.recommended_san
                ):
                    alternatives.append(f"{h.recommended_san} ({h.variation.name})")
                    seen.add(h.recommended_san)
            for alt in best.alternatives:
                if alt not in alternatives:
                    alternatives.append(alt)

            family_label = FAMILY_LABELS.get(best.opening.family, FAMILY_LABELS["other"])

            rec = Recommendation(
                move_san=best.recommended_san,
                move_uci=uci,
                source="theory",
                status=status,
                opening_name=best.opening.name,
                variation_name=best.variation.name,
                idea=best.variation.idea or best.opening.idea,
                alternatives=alternatives,
                multi_variations=multi,
                is_transposition=is_transpo,
                original_opening=self.preferred_opening if is_transpo else None,
                family_label=family_label,
            )
            self.last_recommendation = rec
            return rec

        # ---------- TIER 2 : sortie de théorie, mais on garde le contexte ----------
        family_key = family_for_first_moves(self.history_san)
        family_label = FAMILY_LABELS.get(family_key, FAMILY_LABELS["other"])
        is_early = len(self.history_san) <= 14

        move, eval_pawns, eng_depth = self.engine.best_move(
            self.board, depth=depth, movetime_ms=movetime_ms
        )
        if move is not None:
            try:
                san = self.board.san(move)
            except Exception:
                san = move.uci()
            if is_early:
                status = f"Hors livre · toujours dans la famille « {family_label} » · Stockfish"
            else:
                status = "Sortie de théorie · analyse Stockfish"
            rec = Recommendation(
                move_san=san,
                move_uci=move.uci(),
                source="engine",
                status=status,
                eval_pawns=eval_pawns,
                depth=eng_depth,
                family_label=family_label,
            )
            self.last_recommendation = rec
            return rec

        rec = Recommendation(
            move_san=None,
            move_uci=None,
            source="none",
            status=(
                f"Position hors livre ({family_label}). "
                "Stockfish n'est pas configuré : ouvrez les Paramètres."
            ),
            family_label=family_label,
        )
        self.last_recommendation = rec
        return rec

    # ----- Export -----

    def to_pgn(
        self,
        white_name: str = "Joueur",
        black_name: str = "Adversaire",
        opening_name: Optional[str] = None,
    ) -> str:
        game = chess.pgn.Game()
        game.headers["Event"] = "Chess Opening Trainer Pro"
        game.headers["Site"] = "Local"
        game.headers["Date"] = _dt.date.today().strftime("%Y.%m.%d")
        game.headers["White"] = white_name
        game.headers["Black"] = black_name
        if opening_name:
            game.headers["Opening"] = opening_name

        node = game
        board = chess.Board()
        for san in self.history_san:
            try:
                move = board.parse_san(san)
            except Exception:
                break
            node = node.add_main_variation(move)
            board.push(move)

        result = self.board.result(claim_draw=True)
        game.headers["Result"] = result
        return str(game)

    def export_pgn(
        self,
        target_dir: Optional[Path],
        white_name: str = "Joueur",
        black_name: str = "Adversaire",
        opening_name: Optional[str] = None,
    ) -> Optional[Path]:
        if target_dir is None:
            target_dir = Path.home()
        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        path = target_dir / f"partie-{ts}.pgn"
        try:
            path.write_text(self.to_pgn(white_name, black_name, opening_name), encoding="utf-8")
            return path
        except OSError:
            return None
