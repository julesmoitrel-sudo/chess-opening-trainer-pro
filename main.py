"""Point d'entrée principal de Chess Opening Trainer Pro."""
from __future__ import annotations

import sys
import traceback


def _missing_dep_message(exc: Exception) -> str:
    return (
        "Une dépendance Python est manquante : " + str(exc) + "\n\n"
        "Installez les dépendances avec :\n"
        "    pip install -r requirements.txt\n"
    )


def main() -> int:
    try:
        from app.ui import run
    except ImportError as exc:
        print(_missing_dep_message(exc), file=sys.stderr)
        return 2

    try:
        return run()
    except Exception:  # pragma: no cover
        traceback.print_exc()
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(
                None,
                "Erreur fatale",
                "Une erreur inattendue est survenue.\n"
                "Consultez le terminal pour plus de détails.",
            )
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
