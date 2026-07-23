"""
Görsel dil / tasarım sistemi.

Tek bir yerde tanımlı renk, tipografi, boşluk ve stil kuralları.
Erişilebilirlik önceliği: yüksek kontrast, büyük hedefler, net odak halkaları.
"""

from __future__ import annotations


class Palette:
    """Kağıt & mürekkep — sıcak, editoryal, yüksek kontrastlı açık tema."""

    # Zemin katmanları
    paper = "#F3EFE6"          # ana zemin, sıcak kağıt
    surface = "#FBF9F4"        # kartlar
    surface_raised = "#FFFFFF"  # öne çıkan yüzeyler
    sunken = "#ECE7DB"         # gömük alanlar (girişler, yollar)

    # Mürekkep
    ink = "#1B1A17"            # ana metin
    ink_soft = "#57534A"       # ikincil metin
    ink_faint = "#8A8478"      # üçüncül / ipuçları
    line = "#E2DBCC"           # ince ayraçlar
    line_strong = "#D2C9B6"

    # Kimlik — Pardus'tan esinli derin teal + sıcak kehribar
    accent = "#0E6E77"         # ana vurgu (teal)
    accent_deep = "#0A555C"
    accent_soft = "#D7E7E8"    # teal zemin dokunuşu
    ember = "#C4562A"          # sıcak ikincil (aktif / canlı)
    ember_soft = "#F4DECF"

    # Durum
    live = "#1F8A5B"           # etkin / bağlı
    live_soft = "#D6ECDF"
    warn = "#B5761A"
    warn_soft = "#F3E4C8"
    danger = "#B23B2E"
    danger_soft = "#F2D9D4"

    # Odak halkası (klavye + göz için net görünürlük)
    focus = "#0E6E77"

    # Kamera / görsel katman
    scan = "#13B3B8"
    gaze = "#C4562A"


class Type:
    """Tipografi ölçeği. Başlıklar serif (editoryal), gövde sans."""

    serif = '"Georgia", "Cambria", "Noto Serif", serif'
    sans = '"Segoe UI", "Inter", "Noto Sans", system-ui, sans-serif'
    mono = '"Cascadia Code", "Consolas", "Noto Sans Mono", monospace'

    # px ölçek — erişilebilirlik için gövde 16'dan başlar
    display = 40
    h1 = 28
    h2 = 21
    h3 = 17
    body = 16
    small = 14
    micro = 12.5


class Space:
    """8'lik ritim."""
    xs = 4
    sm = 8
    md = 16
    lg = 24
    xl = 36
    xxl = 56


class Radius:
    sm = 8
    md = 14
    lg = 20
    pill = 999


# Minimum dokunma / bakış hedefi — erişilebilirlik tabanı
MIN_TARGET = 52


def stylesheet() -> str:
    """Uygulama geneli QSS. Renk/ölçü değerleri Palette'ten türetilir."""
    p = Palette
    t = Type
    return f"""
* {{
    font-family: {t.sans};
    color: {p.ink};
    outline: none;
}}

QWidget#Root {{
    background: {p.paper};
}}

/* ---- Kenar çubuğu ---- */
QWidget#Sidebar {{
    background: {p.surface};
    border-right: 1px solid {p.line};
}}

QLabel#Wordmark {{
    font-family: {t.serif};
    font-size: {t.h2}px;
    font-weight: 600;
    color: {p.ink};
    letter-spacing: 0.5px;
}}
QLabel#WordmarkSub {{
    font-size: {t.micro}px;
    color: {p.ink_faint};
    letter-spacing: 2px;
}}

QPushButton#NavItem {{
    text-align: left;
    padding: 14px 16px;
    border: none;
    border-radius: {Radius.md}px;
    font-size: {t.body}px;
    color: {p.ink_soft};
    background: transparent;
}}
QPushButton#NavItem:hover {{
    background: {p.sunken};
    color: {p.ink};
}}
QPushButton#NavItem:checked {{
    background: {p.accent_soft};
    color: {p.accent_deep};
    font-weight: 600;
}}

/* ---- Başlıklar ---- */
QLabel#Display {{
    font-family: {t.serif};
    font-size: {t.display}px;
    font-weight: 600;
    color: {p.ink};
}}
QLabel#H1 {{
    font-family: {t.serif};
    font-size: {t.h1}px;
    font-weight: 600;
    color: {p.ink};
}}
QLabel#H2 {{
    font-size: {t.h2}px;
    font-weight: 600;
    color: {p.ink};
}}
QLabel#H3 {{
    font-size: {t.h3}px;
    font-weight: 600;
    color: {p.ink};
}}
QLabel#Lead {{
    font-size: {t.body}px;
    color: {p.ink_soft};
    line-height: 150%;
}}
QLabel#Muted {{
    font-size: {t.small}px;
    color: {p.ink_faint};
}}
QLabel#Kicker {{
    font-size: {t.micro}px;
    font-weight: 700;
    color: {p.accent};
    letter-spacing: 2px;
}}

/* ---- Kartlar ---- */
QFrame#Card {{
    background: {p.surface};
    border: 1px solid {p.line};
    border-radius: {Radius.lg}px;
}}
QFrame#CardRaised {{
    background: {p.surface_raised};
    border: 1px solid {p.line};
    border-radius: {Radius.lg}px;
}}

/* ---- Butonlar ---- */
QPushButton#Primary {{
    background: {p.accent};
    color: #FFFFFF;
    border: none;
    border-radius: {Radius.md}px;
    padding: 14px 22px;
    font-size: {t.body}px;
    font-weight: 600;
    min-height: {MIN_TARGET - 28}px;
}}
QPushButton#Primary:hover {{ background: {p.accent_deep}; }}
QPushButton#Primary:pressed {{ background: {p.accent_deep}; }}
QPushButton#Primary:disabled {{ background: {p.line_strong}; color: {p.ink_faint}; }}

QPushButton#Ghost {{
    background: transparent;
    color: {p.ink};
    border: 1.5px solid {p.line_strong};
    border-radius: {Radius.md}px;
    padding: 13px 20px;
    font-size: {t.body}px;
    font-weight: 600;
}}
QPushButton#Ghost:hover {{ border-color: {p.accent}; color: {p.accent_deep}; }}

QPushButton#Danger {{
    background: transparent;
    color: {p.danger};
    border: 1.5px solid {p.danger_soft};
    border-radius: {Radius.md}px;
    padding: 13px 20px;
    font-size: {t.body}px;
    font-weight: 600;
}}
QPushButton#Danger:hover {{ background: {p.danger_soft}; }}

QPushButton#QuitBig {{
    background: {p.danger};
    color: #FFFFFF;
    border: none;
    border-radius: {Radius.md}px;
    font-size: {t.h2}px;
    font-weight: 700;
    letter-spacing: 2px;
}}
QPushButton#QuitBig:hover {{ background: #93261B; }}

/* ---- Girişler ---- */
QLineEdit, QComboBox, QSpinBox {{
    background: {p.surface_raised};
    border: 1.5px solid {p.line_strong};
    border-radius: {Radius.sm}px;
    padding: 11px 13px;
    font-size: {t.body}px;
    selection-background-color: {p.accent_soft};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border-color: {p.focus};
}}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox QAbstractItemView {{
    background: {p.surface_raised};
    border: 1px solid {p.line_strong};
    border-radius: {Radius.sm}px;
    selection-background-color: {p.accent_soft};
    selection-color: {p.accent_deep};
    padding: 4px;
}}

/* ---- Kaydırıcı ---- */
QSlider::groove:horizontal {{
    height: 6px;
    background: {p.sunken};
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: {p.accent};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {p.surface_raised};
    border: 2.5px solid {p.accent};
    width: 22px;
    height: 22px;
    margin: -9px 0;
    border-radius: 13px;
}}
QSlider::handle:horizontal:hover {{ border-color: {p.accent_deep}; }}

/* ---- Kaydırma çubuğu ---- */
QScrollBar:vertical {{
    background: transparent; width: 12px; margin: 4px;
}}
QScrollBar::handle:vertical {{
    background: {p.line_strong}; border-radius: 6px; min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{ background: {p.ink_faint}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

/* ---- Araç ipucu ---- */
QToolTip {{
    background: {p.ink};
    color: {p.surface};
    border: none;
    border-radius: 6px;
    padding: 7px 10px;
    font-size: {t.small}px;
}}
"""
