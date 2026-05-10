"""Utility helpers : chemins, ressources, logging léger."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def app_root() -> Path:
    """Retourne le dossier racine de l'application.

    Compatible exécution Python normale et bundle PyInstaller (sys._MEIPASS).
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


def user_data_dir() -> Path:
    """Dossier utilisateur où l'on peut écrire (config, exports)."""
    if getattr(sys, "frozen", False):
        base = Path(os.path.expanduser("~")) / ".chess_opening_trainer_pro"
    else:
        base = app_root()
    base.mkdir(parents=True, exist_ok=True)
    return base


def resource_path(*parts: str) -> Path:
    """Chemin vers une ressource embarquée (read-only en mode .exe)."""
    return app_root().joinpath(*parts)


def log(message: str) -> None:
    print(f"[ChessOpeningTrainer] {message}")
