"""Yardım — ilk kullanım rehberi ve ipuçları."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QLabel

from app.theme import Palette, Space
from app.ui.pages.base import Page
from app.ui.widgets import Card, SectionHeader, Divider


class _Step(QHBoxLayout):
    def __init__(self, num: int, title: str, body: str):
        super().__init__()
        self.setSpacing(Space.md)
        badge = QLabel(str(num))
        badge.setFixedSize(38, 38)
        badge.setAlignment(Qt.AlignCenter)
        bf = QFont(); bf.setPointSizeF(15); bf.setWeight(QFont.Bold)
        badge.setFont(bf)
        badge.setStyleSheet(
            f"background: {Palette.accent_soft}; color: {Palette.accent_deep};"
            f"border-radius: 19px;")
        self.addWidget(badge, 0, Qt.AlignTop)

        box = QVBoxLayout(); box.setSpacing(3)
        t = QLabel(title); t.setObjectName("H3")
        b = QLabel(body); b.setObjectName("Lead"); b.setWordWrap(True)
        box.addWidget(t); box.addWidget(b)
        self.addLayout(box, 1)


class HelpPage(Page):
    def __init__(self, state, bridge, parent=None):
        super().__init__(parent)

        self.add(SectionHeader(
            "Yardım", "Birkaç dakikada başla",
            "Pardus Erişim'i ilk kez kullanıyorsan bu adımları izle. "
            "İstediğin an sadece gözle, sadece sesle ya da ikisiyle birlikte kullanabilirsin."))

        # Kafa
        eye = Card()
        eh = QLabel("Kafa ile kullanım"); eh.setObjectName("H2")
        eye.body.addWidget(eh)
        eye.body.addSpacing(Space.xs)
        eye.body.addLayout(_Step(1, "Rahat otur ve başlat",
            "Ekranın ortasına rahatça bakarken takibi başlat. İlk saniyede "
            "duruşun “merkez” kabul edilir; kalibrasyon yoktur."))
        eye.body.addWidget(Divider())
        eye.body.addLayout(_Step(2, "Kafanla yönlendir",
            "Kafanı hafifçe çevir: sağa bakınca imleç sağa, aşağı eğince "
            "aşağı gider. Oturuşun değişirse “ortala” de ya da Ortala "
            "düğmesine bak."))
        eye.body.addWidget(Divider())
        eye.body.addLayout(_Step(3, "Gözlerini yarım saniye kapat: tıklar",
            "İmleç hedefteyken gözlerini yaklaşık yarım saniye kapalı tut; "
            "yeşil halka belirir ve tıklama gerçekleşir. (Doğal göz kırpma "
            "çok kısa olduğu için tıklamaz.) İstersen bekleyerek tıklamayı "
            "ya da Ayarlar'dan kaş kaldırma / ağız açma jestini kullan. "
            "Köşe mıknatısı, kapat düğmesi gibi köşe hedeflerine imleci "
            "kendiliğinden oturtur."))
        self.add(eye)

        # Sesli okuma
        rd = Card()
        rh = QLabel("Otomatik sesli okuma"); rh.setObjectName("H2")
        rd.body.addWidget(rh)
        rd.body.addSpacing(Space.xs)
        rd.body.addLayout(_Step(1, "Aç",
            "Kafa Kontrolü ekranından “Otomatik okuma”yı aç ya da sesle "
            "“otomatik okumayı aç” de."))
        rd.body.addWidget(Divider())
        rd.body.addLayout(_Step(2, "İmleci metnin üstünde durdur",
            "İmleç bir yazının üzerinde bir-iki saniye durunca metin sesli "
            "okunur. Anında okutmak için “oku”, susturmak için “okumayı "
            "durdur” de."))
        self.add(rd)

        # Ses
        voice = Card()
        vh = QLabel("Sesle kullanım"); vh.setObjectName("H2")
        voice.body.addWidget(vh)
        voice.body.addSpacing(Space.xs)
        voice.body.addLayout(_Step(1, "Dinlemeyi başlat",
            "“Ses ile Kontrol” ekranından dinlemeyi aç. Mikrofon çevrimdışı çalışır, "
            "konuşman cihazdan çıkmaz."))
        voice.body.addWidget(Divider())
        voice.body.addLayout(_Step(2, "Komut ver",
            "“tıkla”, “aşağı”, “tarayıcı aç”, “sesi kıs” gibi kısa komutlar söyle. "
            "Tam listeyi komut kataloğunda bulabilirsin."))
        voice.body.addWidget(Divider())
        voice.body.addLayout(_Step(3, "Serbest yaz",
            "Metin yazmak için “yaz” de, ardından cümleni söyle. Örnek: "
            "“yaz merhaba dünya”."))
        self.add(voice)

        # İpuçları
        tips = Card()
        th = QLabel("İpuçları"); th.setObjectName("H2")
        tips.body.addWidget(th)
        for tip in [
            "Kamera ile arana yaklaşık bir kol boyu mesafe koymak takibi iyileştirir.",
            "İmleç titriyorsa yumuşatmayı artır; ekran kenarına zor ulaşıyorsan hassasiyeti yükselt.",
            "Yanlış tıklamalar oluyorsa bekleme süresini uzat ya da göz kırpma tıklamasını kapat.",
            "Kafa ve sesi birlikte kullan: kafanla hedefle, sesle “tıkla” de.",
            "Sayfayı sesle gezdir: “kaydır aşağı”, sonra ilginç yerde “oku”.",
        ]:
            r = QHBoxLayout(); r.setSpacing(Space.sm)
            dot = QLabel("·"); dot.setStyleSheet(
                f"color: {Palette.accent}; font-weight: 700; font-size: 20px;")
            lbl = QLabel(tip); lbl.setObjectName("Lead"); lbl.setWordWrap(True)
            r.addWidget(dot, 0, Qt.AlignTop); r.addWidget(lbl, 1)
            tips.body.addLayout(r)
        self.add(tips)
