"""Qt GUI bootstrap (PySide6)."""
from __future__ import annotations

import argparse
import sys


def run_gui(args: argparse.Namespace) -> int:
    """Launch the Qt application. Imported lazily."""
    try:
        from PySide6.QtWidgets import QApplication  # noqa: PLC0415
        from PySide6.QtCore import Qt  # noqa: PLC0415
    except ImportError as exc:
        print("PySide6 is required for the GUI.\n"
              "Install it with:  python -m pip install PySide6", file=sys.stderr)
        return 1

    from app.logging_conf import setup_logging  # noqa: PLC0415
    from app.ui.main_window import MainWindow  # noqa: PLC0415
    from app.privacy.tray import TrayController  # noqa: PLC0415

    import logging

    setup_logging(logging.INFO)
    app = QApplication(sys.argv)
    app.setApplicationName("HADJ AIR TOUCH")
    app.setOrganizationName("HADJ")
    app.setStyle("Fusion")

    window = MainWindow(args)
    window.show()

    # System tray (best-effort)
    window.tray = TrayController()  # type: ignore[attr-defined]
    window.tray.install(window)

    code = app.exec()
    window.tray = None  # type: ignore[attr-defined]
    return code