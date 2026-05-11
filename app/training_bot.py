"""Bot d'entraînement aux ouvertures.

Le bot joue le camp adverse en suivant la théorie de l'ouverture choisie
(depuis openings.json). Il peut jouer la ligne principale ou des variantes,
et n'utilise Stockfish qu'en dernier recours. Il fournit aussi une évaluation
pédagogique de chaque coup de l'utilisateur.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

import chess

from .engine import EngineManager
from .opening_book import Opening, OpeningBook, Variation


class BotMode(str, Enum):
    MAIN = "main"
    VARIATIONS = "variations"
    RANDOM = "random"
    MIXED = "mixed"


BOT_MODE_LABELS = {
    BotMode.MAIN: "Ligne principale",
    BotMode.VARIATIONS: "Variantes théoriques",
    BotMode.RANDOM: "Aléatoire théorique",
    BotMode.MIXED: "Mixte (principale + variantes)",
}

BOT_MODE_FROM_LABEL = {v: k for k, v in BOT_MODE_LABELS.items()}


class MoveQuality(str, Enum):
    PERFECT = "perfect"
    ALTERNATIVE = "alternative"
    TRANSPOSITION = "transposition"
    IMPRECISE = "imprecise"
    OUT_OF_THEORY = "out_of_theory"
    ILLEGAL = "illegal"


@dataclass
class MoveAssessment:
    quality: MoveQuality
    user_san: Optional[str] = None
    expected_san: Optional[str] = None
    alternatives: List[str] = field(default_factory=list)
    opening_name: Optional[str] = None
    variation_name: Optional[str] = None
    idea: Optional[str] = None
    message: str = ""
    transposed_to: Optional[str] = None

    @property
    def is_good(self) -> bool:
        return self.quality in (MoveQuality.PERFECT, MoveQuality.ALTERNATIVE)


@dataclass
class BotReply:
    move: Optional[chess.Move] = None
    move_san: Optional[str] = None
    source: str = "none"  # "theory" | "engine" | "none"
    opening_name: Optional[str] = None
    variation_name: Optional[str] = None
    message: str = ""
    eval_pawns: Optional[float] = None
    is_transposition: bool = False


class TrainingBot:
    def __init__(
        self,
        book: OpeningBook,
        engine: EngineManager,
        user_color: chess.Color,
        opening_name: str,
        variation_name: Optional[str] = None,
        mode: BotMode = BotMode.MIXED,
    ) -> None:
        self.book = book
        self.engine = engine
        self.user_color = user_color
        self.opening_name = opening_name
        self.mode = mode
        self._opening: Optional[Opening] = next(
            (o for o in book.openings if o.name == opening_name), None
        )
        self._preferred_variation_name = variation_name
        self._locked: Optional[Variation] = None
        if variation_name and self._opening:
            self._locked = next(
                (v for v in self._opening.variations if v.name == variation_name), None
            )

    # ---------- helpers ----------

    def _variations(self) -> List[Variation]:
        return list(self._opening.variations) if self._opening else []

    def _consistent_variations(self, history_san: List[str]) -> List[Variation]:
        """Variations dont la séquence commence par history_san, avec au moins un coup restant."""
        n = len(history_san)
        out: List[Variation] = []
        for v in self._variations():
            if len(v.moves_san) <= n:
                continue
            if v.moves_san[:n] == history_san:
                out.append(v)
        # si l'utilisateur a fixé une variante, on la met en tête si possible
        if self._preferred_variation_name:
            out.sort(key=lambda v: 0 if v.name == self._preferred_variation_name else 1)
        return out

    def has_followed_any_line(self, history_san: List[str]) -> bool:
        n = len(history_san)
        for v in self._variations():
            if len(v.moves_san) >= n and v.moves_san[:n] == history_san:
                return True
        return False

    # ---------- évaluation du coup utilisateur ----------

    def assess_user_move(
        self,
        board_before: chess.Board,
        history_before: List[str],
        move: chess.Move,
    ) -> MoveAssessment:
        if move not in board_before.legal_moves:
            return MoveAssessment(
                quality=MoveQuality.ILLEGAL,
                message="Coup illégal — vérifie la notation ou la position.",
            )
        user_san = board_before.san(move)
        idx = len(history_before)
        consistent = self._consistent_variations(history_before)
        main_var = consistent[0] if consistent else None
        expected_san = main_var.moves_san[idx] if main_var else None

        alt_moves: List[str] = []
        for v in consistent:
            m = v.moves_san[idx]
            if m not in alt_moves:
                alt_moves.append(m)

        # 1) coup parfait
        if expected_san and user_san == expected_san:
            self._locked = main_var
            return MoveAssessment(
                quality=MoveQuality.PERFECT,
                user_san=user_san,
                expected_san=expected_san,
                alternatives=[m for m in alt_moves if m != user_san],
                opening_name=self.opening_name,
                variation_name=main_var.name if main_var else None,
                idea=(main_var.idea if main_var else None)
                or (self._opening.idea if self._opening else None),
                message=f"Excellent — c'est le coup théorique principal de {self.opening_name}.",
            )

        # 2) coup théorique alternatif (autre variation, même ouverture)
        if user_san in alt_moves:
            matching = next((v for v in consistent if v.moves_san[idx] == user_san), None)
            self._locked = matching
            return MoveAssessment(
                quality=MoveQuality.ALTERNATIVE,
                user_san=user_san,
                expected_san=expected_san,
                alternatives=[m for m in alt_moves if m != user_san],
                opening_name=self.opening_name,
                variation_name=matching.name if matching else None,
                idea=matching.idea if matching else None,
                message=(
                    "Coup correct — ce n'est pas la ligne principale mais une variante "
                    f"théorique connue ({matching.name if matching else '—'})."
                ),
            )

        # On joue le coup pour analyser la position résultante
        board_after = board_before.copy()
        board_after.push(move)
        hits = self.book.find_for_position(board_after, self.user_color, self.opening_name)

        # 3a) transposition vers une autre variante de la MÊME ouverture
        same_op = next((h for h in hits if h.opening.name == self.opening_name), None)
        if same_op:
            return MoveAssessment(
                quality=MoveQuality.ALTERNATIVE,
                user_san=user_san,
                expected_san=expected_san,
                alternatives=[m for m in alt_moves if m != user_san],
                opening_name=self.opening_name,
                variation_name=same_op.variation.name,
                idea=same_op.variation.idea,
                message=(
                    f"Coup correct — tu transposes vers une autre variante de "
                    f"{self.opening_name} ({same_op.variation.name})."
                ),
            )

        # 3b) transposition vers une AUTRE ouverture connue
        other = hits[0] if hits else None
        if other:
            extra = f" Le coup théorique attendu était : {expected_san}." if expected_san else ""
            return MoveAssessment(
                quality=MoveQuality.TRANSPOSITION,
                user_san=user_san,
                expected_san=expected_san,
                alternatives=[m for m in alt_moves if m != user_san],
                opening_name=self.opening_name,
                variation_name=other.variation.name,
                idea=other.variation.idea,
                transposed_to=other.opening.name,
                message=(
                    f"Coup légal, mais il ne correspond pas à {self.opening_name}. "
                    f"Il transpose plutôt vers : {other.opening.name} ({other.variation.name})."
                    + extra
                ),
            )

        # 4) théorie épuisée / sortie de livre
        if not consistent:
            return MoveAssessment(
                quality=MoveQuality.OUT_OF_THEORY,
                user_san=user_san,
                opening_name=self.opening_name,
                message=(
                    "Fin de la ligne théorique connue — tu peux continuer (Stockfish "
                    "prend le relais) ou rejouer la variante."
                ),
            )

        # 5) légal mais imprécis
        extra = f" Le coup recommandé est : {expected_san}." if expected_san else ""
        return MoveAssessment(
            quality=MoveQuality.IMPRECISE,
            user_san=user_san,
            expected_san=expected_san,
            alternatives=[m for m in alt_moves if m != user_san],
            opening_name=self.opening_name,
            variation_name=main_var.name if main_var else None,
            idea=main_var.idea if main_var else None,
            message="Ce coup est légal, mais il sort de la variante choisie." + extra,
        )

    # ---------- coup du bot ----------

    def choose_bot_move(
        self,
        board: chess.Board,
        history_san: List[str],
        depth: int = 14,
        movetime_ms: int = 600,
    ) -> BotReply:
        if board.is_game_over(claim_draw=True):
            return BotReply(message="Partie terminée.")

        idx = len(history_san)
        consistent = self._consistent_variations(history_san)
        if consistent:
            chosen = self._pick_variation(consistent)
            self._locked = chosen
            san = chosen.moves_san[idx]
            try:
                move = board.parse_san(san)
            except Exception:
                move = None
            if move is not None:
                distinct = {v.moves_san[idx] for v in consistent}
                msg = f"Le bot a choisi : {chosen.name}." if len(distinct) > 1 else ""
                return BotReply(
                    move=move,
                    move_san=san,
                    source="theory",
                    opening_name=self.opening_name,
                    variation_name=chosen.name,
                    message=msg,
                )

        # Fallback FEN (transpositions)
        hits = self.book.find_for_position(board, board.turn, self.opening_name)
        playable = [h for h in hits if h.recommended_san]
        if playable:
            pref = [h for h in playable if h.opening.name == self.opening_name]
            pool = pref if pref else playable
            if self.mode in (BotMode.RANDOM, BotMode.VARIATIONS, BotMode.MIXED):
                hit = random.choice(pool[: min(3, len(pool))])
            else:
                hit = pool[0]
            try:
                move = board.parse_san(hit.recommended_san)
            except Exception:
                move = None
            if move is not None:
                is_transpo = hit.opening.name != self.opening_name
                msg = (
                    f"Transposition : on passe à {hit.opening.name} ({hit.variation.name})."
                    if is_transpo
                    else ""
                )
                return BotReply(
                    move=move,
                    move_san=hit.recommended_san,
                    source="theory",
                    opening_name=hit.opening.name,
                    variation_name=hit.variation.name,
                    message=msg,
                    is_transposition=is_transpo,
                )

        # Stockfish en dernier recours
        move, ev, _ = self.engine.best_move(board, depth=depth, movetime_ms=movetime_ms)
        if move is not None:
            try:
                san = board.san(move)
            except Exception:
                san = move.uci()
            return BotReply(
                move=move,
                move_san=san,
                source="engine",
                message="Fin de la théorie connue — le bot continue avec Stockfish.",
                eval_pawns=ev,
            )

        return BotReply(
            message=(
                "Fin de la théorie connue et Stockfish indisponible : "
                "configure le moteur dans les Paramètres, ou rejoue la variante."
            )
        )

    def _pick_variation(self, consistent: List[Variation]) -> Variation:
        if self._locked in consistent and self.mode != BotMode.RANDOM:
            if not (self.mode == BotMode.MIXED and random.random() < 0.30):
                return self._locked
        if self.mode == BotMode.MAIN:
            return consistent[0]
        if self.mode == BotMode.MIXED:
            return consistent[0] if random.random() < 0.65 else random.choice(consistent)
        return random.choice(consistent)

    # ---------- "voir le bon coup" ----------

    def best_theory_move(self, board: chess.Board, history_san: List[str]) -> Optional[str]:
        consistent = self._consistent_variations(history_san)
        if consistent:
            return consistent[0].moves_san[len(history_san)]
        hits = self.book.find_for_position(board, board.turn, self.opening_name)
        playable = [h for h in hits if h.recommended_san]
        if playable:
            pref = [h for h in playable if h.opening.name == self.opening_name]
            return (pref or playable)[0].recommended_san
        return None
