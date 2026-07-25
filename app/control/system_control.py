"""
Sistem denetimi — fare, klavye ve uygulama başlatma.

Hem göz izleme (imleç + tıklama) hem de ses (yazma, uygulama açma, sistem
komutları) bu katmanı kullanır. pynput yoksa uygulama çökmez; işlemler
sessizce yok sayılır ve `available` False olur.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import platform


class SystemControl:
    def __init__(self, screen_w: int = 1920, screen_h: int = 1080):
        """screen_w/screen_h: FİZİKSEL piksel çözünürlüğü (uinput sanal fare
        için gerekir; pynput zaten kendi koordinat uzayını kullanır)."""
        self.available = False
        self._mouse = None
        self._kb = None
        self._Key = None
        self._Button = None
        # Wayland'da pynput'un XTest/XWayland köprüsü sistem geneli imleç
        # denetimini güvenilir yapamaz (bkz. app/doctor.py aynı denetim).
        self.wayland_limited = (
            platform.system() == "Linux"
            and os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
        )
        try:
            from pynput.mouse import Controller as MouseController, Button
            from pynput.keyboard import Controller as KbController, Key
            self._mouse = MouseController()
            self._kb = KbController()
            self._Key = Key
            self._Button = Button
            self.available = True
        except Exception as exc:  # pragma: no cover - ortam bağımlı
            self._error = str(exc)

        # Wayland'da imleç/tıklama için pynput yerine çekirdek seviyesinde
        # sanal fare (/dev/uinput) dene — compositor'dan bağımsız çalışır.
        self._uinput = None
        self.using_uinput = False
        if self.wayland_limited and platform.system() == "Linux":
            try:
                from app.control.uinput_mouse import UInputMouse
                candidate = UInputMouse(screen_w, screen_h)
                if candidate.available:
                    self._uinput = candidate
                    self.using_uinput = True
                    self.available = True
            except Exception:
                pass

    # ---- İşaretçi ----
    def position(self) -> tuple[int, int]:
        """Şu anki (yaklaşık) imleç konumu — elle hareket algılamak için.

        uinput yolunda bu GERÇEK sistem imlecinin yankısı DEĞİLDİR (Wayland
        istemcilere gerçek konumu vermez); yalnız kendi yazdığımız son
        değerdir. Gerçek elle-hareket algısı o durumda
        app/control/real_mouse_watch.py ile yapılır."""
        if self._uinput:
            return self._uinput.position()
        if not self._mouse:
            return (0, 0)
        try:
            px, py = self._mouse.position
            return (int(px), int(py))
        except Exception:
            return (0, 0)

    def move_to(self, x: int, y: int):
        if self._uinput:
            self._uinput.move_to(x, y)
            return
        if self._mouse:
            try:
                self._mouse.position = (int(x), int(y))
            except Exception:
                pass

    def move_by(self, dx: float, dy: float):
        if self._uinput:
            self._uinput.move_by(dx, dy)
            return
        if self._mouse:
            px, py = self._mouse.position
            self._mouse.position = (int(px + dx), int(py + dy))

    def click(self, button: str = "left", double: bool = False):
        if self._uinput:
            self._uinput.click(button, double)
            return
        if not self._mouse:
            return
        btn = {"right": self._Button.right,
               "middle": self._Button.middle}.get(button, self._Button.left)
        try:
            self._mouse.click(btn, 2 if double else 1)
        except Exception:
            pass

    def scroll(self, dy: int):
        if self._uinput:
            self._uinput.scroll(dy)
            return
        if self._mouse:
            self._mouse.scroll(0, dy)

    # ---- Klavye ----
    def type_text(self, text: str):
        if self._kb:
            self._kb.type(text)

    def press(self, *keys: str):
        """Tek tuş ya da kısayol. Örn: press('ctrl','c')."""
        if not self._kb:
            return
        resolved = [self._resolve_key(k) for k in keys]
        for k in resolved:
            self._kb.press(k)
        for k in reversed(resolved):
            self._kb.release(k)

    def _resolve_key(self, name: str):
        name = name.lower()
        return getattr(self._Key, name, name)

    # ---- Uygulama başlatma ----
    def launch(self, candidates: list[str]) -> bool:
        """Aday komutlardan ilk bulunanı başlatır. Bulursa True."""
        for cmd in candidates:
            exe = cmd.split()[0]
            if shutil.which(exe) or os.path.exists(exe):
                try:
                    if platform.system() == "Windows":
                        subprocess.Popen(cmd, shell=True)
                    else:
                        subprocess.Popen(cmd.split(),
                                         stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL)
                    return True
                except Exception:
                    continue
        # Windows'ta 'start' ile dene (tarayıcı vb.)
        if platform.system() == "Windows" and candidates:
            try:
                os.startfile(candidates[0])  # type: ignore[attr-defined]
                return True
            except Exception:
                return False
        return False

    def close(self):
        """Sanal uinput aygıtını serbest bırak (uygulama kapanırken çağır)."""
        if self._uinput:
            self._uinput.close()

    def open_url(self, url: str) -> bool:
        import webbrowser
        try:
            webbrowser.open(url)
            return True
        except Exception:
            return False
