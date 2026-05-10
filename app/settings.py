"""Gestion de la configuration persistante (config.json)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .utils import app_root, user_data_dir


DEFAULT_CONFIG: Dict[str, Any] = {
    "stockfish_path": "",
    "engine_depth": 16,
    "engine_movetime_ms": 800,
    "show_explanations": True,
    "pgn_export_dir": "",
    "theme": "dark",
    "board_orientation_auto": True,
    "last_color": "white",
    "last_opening": "",
}


class Settings:
    """Wrapper simple autour d'un fichier config.json."""

    def __init__(self) -> None:
        self.path: Path = self._resolve_config_path()
        self.data: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self.load()

    @staticmethod
    def _resolve_config_path() -> Path:
        # Priorité au config.json à côté du projet (mode dev),
        # fallback sur le dossier utilisateur (mode .exe).
        candidate = app_root() / "config.json"
        if candidate.exists():
            return candidate
        return user_data_dir() / "config.json"

    def load(self) -> None:
        try:
            if self.path.exists():
                with self.path.open("r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    for k, v in loaded.items():
                        self.data[k] = v
        except (OSError, json.JSONDecodeError):
            # On garde les valeurs par défaut si le fichier est corrompu
            pass

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

    def reset(self) -> None:
        self.data = dict(DEFAULT_CONFIG)
        self.save()
