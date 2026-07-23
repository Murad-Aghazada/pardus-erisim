#!/usr/bin/env python3
"""
Pardus Erişim — bakış ve sesle bilgisayar kullanımı.

TEKNOFEST · Pardus İşletim Sistemi kategorisi.
Giriş noktası: uygulamayı başlatır, temayı uygular, motorları bağlar.
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    # Teşhis modu: arayüz açılmadan sistem gereksinimlerini denetle.
    # (Linux/Pardus'ta "açılmıyor" sorunlarını buradan bulun.)
    if "--doctor" in sys.argv or "-d" in sys.argv:
        from app.doctor import run
        return run()

    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QFont, QIcon
        from PySide6.QtWidgets import QApplication
    except Exception as exc:
        _fatal_qt(exc)
        return 1

    from app.theme import stylesheet
    from app.state import AppState
    from app.application import AppController
    from app.ui.main_window import MainWindow

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    try:
        app = QApplication(sys.argv)
    except Exception as exc:
        _fatal_qt(exc)
        return 1
    app.setApplicationName("Pardus Erişim")
    app.setOrganizationName("PardusErisim")
    app.setApplicationDisplayName("Pardus Erişim")

    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "assets", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Erişilebilirlik için okunur taban yazı boyutu
    base = QFont()
    base.setPointSizeF(10.5)
    app.setFont(base)
    app.setStyleSheet(stylesheet())

    state = AppState()
    controller = AppController(state)
    window = MainWindow(state, controller)
    controller.bind(window)
    window.showMaximized()

    return app.exec()


def _fatal_qt(exc: Exception) -> None:
    """Qt/arayüz başlatılamadı — büyük olasılıkla eksik sistem kitaplığı."""
    sys.stderr.write(
        "\n[Pardus Erişim] Arayüz başlatılamadı.\n"
        f"  Ayrıntı: {exc}\n\n"
        "  Linux/Pardus'ta en sık neden, Qt'nin sistem kitaplıklarının "
        "eksik olmasıdır\n"
        "  (özellikle Qt 6.5+ için libxcb-cursor0). Şu komutu çalıştır:\n\n"
        "      sudo apt install -y libxcb-cursor0 libxkbcommon-x11-0 "
        "libgl1 libegl1\n\n"
        "  Tam teşhis için:  python3 main.py --doctor\n"
        "  Tek adımda kurulum:  sh install-pardus.sh\n\n")


if __name__ == "__main__":
    sys.exit(main())
