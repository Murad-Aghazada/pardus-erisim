"""
Görsel dil / tasarım sistemi.

Tek bir yerde tanımlı renk, tipografi, boşluk ve stil kuralları. GNOME/
libadwaita ile uyumlu (Pardus, Debian, Ubuntu ortak masaüstü) — Cantarell
yazı tipi, Adwaita mavi vurgu ve GNOME'un düz/az köşeli kart-buton dili.
Erişilebilirlik önceliği: yüksek kontrast, büyük hedefler, net odak halkaları.
"""

from __future__ import annotations


class Palette:
    """GNOME/Adwaita açık tema — nötr gri zemin + Adwaita mavisi vurgu."""

    # Zemin katmanları (Adwaita window/card/sidebar tonları)
    paper = "#FAFAFA"          # ana pencere zemini
    surface = "#FFFFFF"        # kartlar
    surface_raised = "#FFFFFF"  # öne çıkan yüzeyler
    sunken = "#EDEDED"         # gömük alanlar (girişler, yollar)

    # Mürekkep (GNOME window_fg_color kademeleri)
    ink = "#1A1A1A"            # ana metin
    ink_soft = "#5E5E5E"       # ikincil metin
    ink_faint = "#8B8B8B"      # üçüncül / ipuçları
    line = "#E8E8E8"           # ince ayraçlar (Adwaita hairline)
    line_strong = "#D6D6D6"

    # Kimlik — Adwaita mavisi (GNOME'un standart vurgu rengi)
    accent = "#3584E4"
    accent_deep = "#1C71D8"
    accent_soft = "#E3EDFB"    # mavi zemin dokunuşu
    ember = "#FF7800"          # Adwaita turuncusu (ikincil vurgu)
    ember_soft = "#FDE6CE"

    # Durum (Adwaita named colors: yeşil/sarı/kırmızı)
    live = "#2EC27E"
    live_soft = "#DEF5E9"
    warn = "#E5A50A"
    warn_soft = "#FBEFD2"
    danger = "#E01B24"
    danger_soft = "#FBDEDC"

    # Odak halkası (klavye + göz için net görünürlük)
    focus = "#3584E4"

    # Kamera / görsel katman
    scan = "#1C71D8"
    gaze = "#FF7800"


class Type:
    """Tipografi ölçeği. GNOME'un sistem yazı tipi (Cantarell) öncelikli."""

    sans = ('"Cantarell", "Inter", "Noto Sans", system-ui, '
            '"Segoe UI", sans-serif')
    serif = sans   # GNOME'da editoryal serif başlık yok — sans'a düşer
    mono = '"Source Code Pro", "Cascadia Code", "Noto Sans Mono", monospace'

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
    """GNOME/libadwaita düz köşe dili — önceki sürümden daha az yuvarlak."""
    sm = 6
    md = 9
    lg = 12
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
    background: {p.sunken};
    border-right: 1px solid {p.line};
}}

QLabel#Wordmark {{
    font-size: {t.h2}px;
    font-weight: 700;
    color: {p.ink};
}}
QLabel#WordmarkSub {{
    font-size: {t.micro}px;
    color: {p.ink_faint};
    letter-spacing: 1px;
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
    background: rgba(0, 0, 0, 0.05);
    color: {p.ink};
}}
QPushButton#NavItem:checked {{
    background: {p.accent_soft};
    color: {p.accent_deep};
    font-weight: 600;
}}

/* ---- Başlıklar ---- */
QLabel#Display {{
    font-size: {t.display}px;
    font-weight: 700;
    color: {p.ink};
}}
QLabel#H1 {{
    font-size: {t.h1}px;
    font-weight: 700;
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
    letter-spacing: 1.5px;
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

/* ---- Butonlar (GNOME 'suggested-action' / 'flat' / 'destructive-action') ---- */
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
QPushButton#Ghost:hover {{ background: rgba(0, 0, 0, 0.05); border-color: {p.accent}; color: {p.accent_deep}; }}

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
    letter-spacing: 1px;
}}
QPushButton#QuitBig:hover {{ background: #A51D2D; }}

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
