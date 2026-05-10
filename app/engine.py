"""Détection et utilisation de Stockfish via python-chess."""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional, Tuple

import chess
import chess.engine

from .utils import log


CANDIDATE_PATHS = [
    "stockfish",
    "stockfish.exe",
    r"C:\Stockfish\stockfish.exe",
    r"C:\Program Files\Stockfish\stockfish.exe",
    r"C:\Program Files (x86)\Stockfish\stockfish.exe",
    "/usr/local/bin/stockfish",
    "/opt/homebrew/bin/stockfish",
    "/usr/bin/stockfish",
]


def detect_stockfish(saved_path: Optional[str] = None) -> Optional[str]:
    """Tente de localiser un binaire Stockfish utilisable.

    Renvoie le chemin résolu (str) ou None.
    """
    if saved_path:
        if _is_executable(saved_path):
            return saved_path

    # PATH (which/where)
    found = shutil.which("stockfish")
    if found and _is_executable(found):
        return found

    for candidate in CANDIDATE_PATHS:
        if _is_executable(candidate):
            return candidate
        which = shutil.which(candidate)
        if which and _is_executable(which):
            return which
    return None


def _is_executable(path: str) -> bool:
    if not path:
        return False
    p = Path(path)
    if p.is_file():
        return os.access(str(p), os.X_OK) or p.suffix.lower() == ".exe" or os.name == "nt"
    return False


def test_engine(path: str) -> Tuple[bool, str]:
    """Lance une connexion test à Stockfish, retourne (ok, message)."""
    if not path:
        return False, "Aucun chemin Stockfish fourni."
    try:
        with chess.engine.SimpleEngine.popen_uci(path) as engine:
            name = engine.id.get("name", "Stockfish")
            return True, f"Connecté à {name}."
    except Exception as exc:  # pragma: no cover - dépend du système
        return False, f"Échec : {exc}"


class EngineManager:
    """Encapsule un moteur UCI persistant pour réutilisation."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path: Optional[str] = path
        self._engine: Optional[chess.engine.SimpleEngine] = None

    @property
    def available(self) -> bool:
        return self._engine is not None

    def open(self, path: Optional[str] = None) -> bool:
        if path:
            self.path = path
        self.close()
        if not self.path:
            return False
        try:
            self._engine = chess.engine.SimpleEngine.popen_uci(self.path)
            return True
        except Exception as exc:
            log(f"Stockfish indisponible : {exc}")
            self._engine = None
            return False

    def close(self) -> None:
        if self._engine is not None:
            try:
                self._engine.quit()
            except Exception:
                pass
            self._engine = None

    def best_move(
        self,
        board: chess.Board,
        depth: int = 16,
        movetime_ms: int = 800,
    ) -> Tuple[Optional[chess.Move], Optional[float], Optional[int]]:
        """Retourne (move, eval_pawns, depth) ou (None, None, None) en cas d'échec."""
        if self._engine is None:
            if not self.open():
                return None, None, None
        if self._engine is None:
            return None, None, None
        try:
            limit = chess.engine.Limit(depth=depth, time=movetime_ms / 1000.0)
            info = self._engine.analyse(board, limit)
            move = info.get("pv", [None])[0] if info.get("pv") else None
            score = info.get("score")
            eval_value: Optional[float] = None
            if score is not None:
                pov = score.white() if board.turn == chess.WHITE else score.black()
                if pov.is_mate():
                    mate = pov.mate()
                    eval_value = 100.0 if (mate or 0) > 0 else -100.0
                else:
                    cp = pov.score(mate_score=10000)
                    if cp is not None:
                        eval_value = cp / 100.0
            return move, eval_value, info.get("depth")
        except Exception as exc:
            log(f"Erreur Stockfish : {exc}")
            self.close()
            return None, None, None

    def __del__(self) -> None:  # pragma: no cover
        self.close()
