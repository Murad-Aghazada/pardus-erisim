"""Ana pencere — kenar çubuğu, sayfa yığını ve global durdurma."""

from __future__ import annotations

from PySide6.QtCore import Qt, QSize, QPointF, QRectF, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QStackedWidget, QButtonGroup,
)

from app.theme import Palette, Space, Type, stylesheet
from app.ui.widgets import StatusPill
from app.ui.pages.dashboard import DashboardPage
from app.ui.pages.eye_page import EyePage
from app.ui.pages.voice_page import VoicePage
from app.ui.pages.assist_page import AssistPage
from app.ui.pages.settings_page import SettingsPage
from app.ui.pages.help_page import HelpPage


class Mark(QWidget):
    """Küçük amblem — göz + ses dalgasını birleştiren işaret."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(34, 34)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(Palette.accent))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(1, 1, 32, 32))
        # iris
        p.setBrush(QColor(Palette.surface))
        p.drawEllipse(QPointF(17, 17), 6.5, 6.5)
        p.setBrush(QColor(Palette.accent_deep))
        p.drawEllipse(QPointF(17, 17), 3, 3)
        # ses yayı
        pen = QPen(QColor(Palette.surface), 2); pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(19, 9, 16, 16), -60 * 16, 120 * 16)


class Sidebar(QWidget):
    navigate = Signal(str)
    stop_all = Signal()
    quit_app = Signal()

    NAV = [
        ("dashboard", "Genel Bakış"),
        ("eye", "Kafa Kontrolü"),
        ("voice", "Ses Kontrolü"),
        ("assist", "Asistan"),
        ("help", "Yardım"),
        ("settings", "Ayarlar"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(248)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(Space.md, Space.lg, Space.md, Space.lg)
        lay.setSpacing(Space.xs)

        # marka
        brand = QHBoxLayout(); brand.setSpacing(10)
        brand.addWidget(Mark(), 0)
        wm = QVBoxLayout(); wm.setSpacing(0)
        w1 = QLabel("Pardus Erişim"); w1.setObjectName("Wordmark")
        w2 = QLabel("BAKIŞ  ·  SES"); w2.setObjectName("WordmarkSub")
        wm.addWidget(w1); wm.addWidget(w2)
        brand.addLayout(wm); brand.addStretch(1)
        lay.addLayout(brand)
        lay.addSpacing(Space.lg)

        # nav
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._btns: dict[str, QPushButton] = {}
        for key, label in self.NAV:
            b = QPushButton(label)
            b.setObjectName("NavItem")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.navigate.emit(k))
            self._group.addButton(b)
            self._btns[key] = b
            lay.addWidget(b)

        lay.addStretch(1)

        # global durum + durdurma + çıkış
        self.status = StatusPill("Sistemler kapalı", "idle")
        lay.addWidget(self.status)
        lay.addSpacing(Space.sm)
        self.stop_btn = QPushButton("Tümünü durdur")
        self.stop_btn.setObjectName("Danger")
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.clicked.connect(self.stop_all.emit)
        self.stop_btn.setEnabled(False)
        lay.addWidget(self.stop_btn)
        lay.addSpacing(Space.sm)

        # Büyük çıkış düğmesi: kafa ile kolayca hedeflenebilir boyutta.
        # Uygulamayı kullanan kişi her an, yardımsız çıkabilmeli.
        self.quit_btn = QPushButton("✕   ÇIKIŞ")
        self.quit_btn.setObjectName("QuitBig")
        self.quit_btn.setCursor(Qt.PointingHandCursor)
        self.quit_btn.setMinimumHeight(64)
        self.quit_btn.setToolTip("Uygulamayı kapat (sesle: “çıkış”)")
        self.quit_btn.clicked.connect(self.quit_app.emit)
        lay.addWidget(self.quit_btn)

    def select(self, key: str):
        if key in self._btns:
            self._btns[key].setChecked(True)

    def set_global(self, any_active: bool):
        self.stop_btn.setEnabled(any_active)
        if any_active:
            self.status.set_status("Sistem etkin", "live", True)
        else:
            self.status.set_status("Sistemler kapalı", "idle")


class MainWindow(QMainWindow):
    def __init__(self, state, bridge):
        super().__init__()
        self.state = state
        self.bridge = bridge
        self.setWindowTitle("Pardus Erişim · Bakış ve Ses")
        self.setMinimumSize(1080, 720)

        root = QWidget(); root.setObjectName("Root")
        lay = QHBoxLayout(root); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.navigate.connect(self.navigate)
        self.sidebar.stop_all.connect(bridge.stop_all)
        self.sidebar.quit_app.connect(self.close)
        lay.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        lay.addWidget(self.stack, 1)
        self.setCentralWidget(root)

        # sayfalar
        self.pages = {
            "dashboard": DashboardPage(state, bridge),
            "eye": EyePage(state, bridge),
            "voice": VoicePage(state, bridge),
            "assist": AssistPage(state, bridge),
            "help": HelpPage(state, bridge),
            "settings": SettingsPage(state, bridge),
        }
        for w in self.pages.values():
            self.stack.addWidget(w)
        self.navigate("dashboard")

        # global durum güncelleme
        state.eye_active_changed.connect(lambda *_: self._update_global())
        state.voice_active_changed.connect(lambda *_: self._update_global())

        # güvenlik kısayolu — Esc her şeyi durdurur
        sc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        sc.activated.connect(bridge.stop_all)

    def navigate(self, key: str):
        if key in self.pages:
            self.stack.setCurrentWidget(self.pages[key])
            self.sidebar.select(key)

    def _update_global(self):
        self.sidebar.set_global(self.state.eye_active or self.state.voice_active)

    def closeEvent(self, e):
        self.bridge.shutdown()
        super().closeEvent(e)
