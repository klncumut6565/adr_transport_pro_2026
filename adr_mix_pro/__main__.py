"""Uygulama giriş noktası.

Çalıştırmak için proje kök dizininden:

    python -m adr_mix_pro

veya kök dizindeki ``run.py`` ile:

    python run.py
"""

from __future__ import annotations

import sys


def main() -> int:
    from PyQt6.QtWidgets import QApplication

    from .logging_setup import setup_logging
    from .ui.main_window import MainWindow

    logger = setup_logging()
    logger.info("Uygulama başlatılıyor...")

    app = QApplication(sys.argv)
    app.setApplicationName("ADR Mix Checker Pro")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
