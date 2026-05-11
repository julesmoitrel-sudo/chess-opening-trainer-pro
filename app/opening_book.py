"""Chargement et interrogation de la base d'ouvertures (openings.json).

Stratégie :
- on charge le JSON
- pour chaque variante on rejoue les coups SAN sur un échiquier python-chess
- on indexe chaque position FEN (clef position-only, sans demi-coups)
  vers une liste de "candidats" : (opening, variation, move_index, recommended_move).
- la reconnaissance fonctionne par FEN, donc supporte les transpositions.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import chess

from .utils import resource_path, log


def _position_key(board: chess.Board) -> str:
    """FEN sans les compteurs de coups, pour matcher les transpositions."""
    parts = board.fen().split(" ")
    # parts: piece_placement turn castling en_passant halfmove fullmove
    return " ".join(parts[:4])


@dataclass
class Variation:
    name: str
    moves_san: List[str]
    idea: str
    alternatives: List[str] = field(default_factory=list)


@dataclass
class Opening:
    name: str
    color: str  # "white" or "black"
    eco: str
    idea: str
    variations: List[Variation]
    family: str = "other"


FAMILY_LABELS: Dict[str, str] = {
    "open_games": "Débuts ouverts (1.e4 e5)",
    "semi_open": "Débuts semi-ouverts (1.e4 ...)",
    "closed_games": "Débuts fermés (1.d4 d5)",
    "indian": "Défenses indiennes (1.d4 Nf6)",
    "flexible_d4": "Débuts flexibles 1.d4",
    "english": "Anglaise (1.c4)",
    "reti": "Réti (1.Nf3)",
    "flank": "Ouvertures de flanc",
    "other": "Théorie d'ouverture",
}


def family_for_first_moves(history_san: List[str]) -> str:
    """Devine la famille d'ouverture à partir des 1-2 premiers coups SAN."""
    if not history_san:
        return "other"
    first = history_san[0]
    second = history_san[1] if len(history_san) > 1 else None
    if first == "e4":
        if second == "e5":
            return "open_games"
        return "semi_open"
    if first == "d4":
        if second == "d5":
            return "closed_games"
        if second == "Nf6":
            return "indian"
        return "flexible_d4"
    if first == "c4":
        return "english"
    if first == "Nf3":
        return "reti"
    if first in ("f4", "b3", "g3", "b4", "Nc3"):
        return "flank"
    return "other"


@dataclass
class TheoryHit:
    opening: Opening
    variation: Variation
    move_index: int  # nombre de demi-coups joués pour atteindre cette position
    recommended_san: Optional[str]  # le prochain coup théorique, ou None si fin de variante
    alternatives: List[str]
    side_to_move_is_user: bool

    @property
    def remaining_depth(self) -> int:
        return max(0, len(self.variation.moves_san) - self.move_index)


class OpeningBook:
    def __init__(self) -> None:
        self.openings: List[Opening] = []
        # position_key -> list[(opening, variation, move_index)]
        self._index: Dict[str, List[Tuple[Opening, Variation, int]]] = {}
        self.load_default()

    def load_default(self) -> None:
        path = resource_path("openings.json")
        self.load(path)

    def load(self, path: Path) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            log(f"Impossible de charger {path}: {exc}")
            self.openings = []
            self._index = {}
            return

        self.openings = []
        self._index = {}

        for op in data.get("openings", []):
            try:
                variations = [
                    Variation(
                        name=v.get("name", "?"),
                        moves_san=list(v.get("moves", [])),
                        idea=v.get("idea", ""),
                        alternatives=list(v.get("alternatives", [])),
                    )
                    for v in op.get("variations", [])
                ]
                opening = Opening(
                    name=op.get("name", "?"),
                    color=op.get("color", "white"),
                    eco=op.get("eco", ""),
                    idea=op.get("idea", ""),
                    variations=variations,
                    family=op.get("family", "other"),
                )
                self.openings.append(opening)
                self._index_opening(opening)
            except Exception as exc:
                log(f"Variante ignorée ({op.get('name', '?')}) : {exc}")

    def _index_opening(self, opening: Opening) -> None:
        for variation in opening.variations:
            board = chess.Board()
            # Index la position de départ également
            self._add_index_entry(board, opening, variation, 0)
            for i, san in enumerate(variation.moves_san):
                try:
                    board.push_san(san)
                except (ValueError, chess.IllegalMoveError, chess.InvalidMoveError, chess.AmbiguousMoveError):
                    log(
                        f"Coup invalide '{san}' dans {opening.name}/{variation.name}"
                        f" (coup {i + 1}). Le reste de la variante est ignoré."
                    )
                    break
                self._add_index_entry(board, opening, variation, i + 1)

    def _add_index_entry(
        self,
        board: chess.Board,
        opening: Opening,
        variation: Variation,
        move_index: int,
    ) -> None:
        key = _position_key(board)
        self._index.setdefault(key, []).append((opening, variation, move_index))

    # ----- Public lookup -----

    def find_for_position(
        self,
        board: chess.Board,
        user_color: chess.Color,
        preferred_opening: Optional[str] = None,
    ) -> List[TheoryHit]:
        """Retourne tous les hits théoriques correspondant à la position."""
        key = _position_key(board)
        entries = self._index.get(key, [])
        hits: List[TheoryHit] = []
        for opening, variation, move_index in entries:
            recommended: Optional[str] = None
            if move_index < len(variation.moves_san):
                recommended = variation.moves_san[move_index]
            hits.append(
                TheoryHit(
                    opening=opening,
                    variation=variation,
                    move_index=move_index,
                    recommended_san=recommended,
                    alternatives=list(variation.alternatives),
                    side_to_move_is_user=(board.turn == user_color),
                )
            )

        # Trier : ouverture préférée d'abord, puis profondeur restante
        def sort_key(hit: TheoryHit) -> Tuple[int, int]:
            preferred = 0 if (preferred_opening and hit.opening.name == preferred_opening) else 1
            return (preferred, -hit.remaining_depth)

        hits.sort(key=sort_key)
        return hits

    def best_recommendation(
        self,
        board: chess.Board,
        user_color: chess.Color,
        preferred_opening: Optional[str] = None,
    ) -> Optional[TheoryHit]:
        hits = self.find_for_position(board, user_color, preferred_opening)
        if not hits:
            return None
        # Privilégier les hits où le coup recommandé existe (variante non terminée)
        with_move = [h for h in hits if h.recommended_san]
        if with_move:
            return with_move[0]
        return hits[0]

    def list_for_color(self, color: str) -> List[Opening]:
        return [o for o in self.openings if o.color == color]
